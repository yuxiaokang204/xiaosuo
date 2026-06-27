"""
统一 LLM 网关 - 缓存 + 重试 + 限流
在原有 Provider 架构之上添加通用横切关注点：
- 响应缓存（MD5 key，避免相同 prompt 重复调用）
- 自动重试（支持指数退避）
- 速率限制（防并发过载）
"""
import hashlib
import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class LLMMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    raw: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


# ── 缓存 ──

_llm_cache: Dict[str, LLMResponse] = {}
_llm_cache_max = 200
_llm_cache_lock = asyncio.Lock()


def _llm_cache_key(messages, system_prompt, temperature, model) -> str:
    """生成缓存 key：MD5(system_prompt + user_message + temperature + model)"""
    content = json.dumps({
        "msgs": [m.to_dict() if hasattr(m, 'to_dict') else m for m in messages],
        "sys": system_prompt,
        "temp": temperature,
        "model": model,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(content.encode()).hexdigest()


def clear_llm_cache():
    """清空 LLM 缓存"""
    _llm_cache.clear()


# ── 速率限制 ──

class RateLimiter:
    """简单令牌桶速率限制器"""
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: List[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.time()
            # 清理过期记录
            self._timestamps = [t for t in self._timestamps if now - t < self.window_seconds]
            if len(self._timestamps) >= self.max_requests:
                # 等待最老的一个过期
                wait_time = self._timestamps[0] + self.window_seconds - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    self._timestamps.clear()
            self._timestamps.append(time.time())


# ── Provider 基类 ──

class LLMProvider(ABC):
    """LLM Provider 基类 - 所有实现继承此类"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 api_base: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 8000,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        pass

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 8000,
        system_prompt: Optional[str] = None,
        **kwargs,
    ):
        """默认非流式回退 - 子类可覆写为真正的流式实现"""
        response = await self.generate(messages, temperature, max_tokens, system_prompt, **kwargs)
        content = response.content
        chunks = [p for p in content.split("\n") if p.strip()]
        if not chunks:
            chunks = [content]
        for chunk in chunks:
            yield {"type": "token", "content": chunk + "\n"}
        yield {"type": "done", "content": ""}

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        english = len(text) - chinese
        return int(chinese / 1.5 + english / 4) + 10


# ── 网关（缓存 + 重试 + 限流）──

class LLMGateway:
    """
    LLM 统一网关
    
    使用示例:
        gateway = LLMGateway(provider=OpenAIProvider(), max_retries=3)
        response = await gateway.generate([LLMMessage(role="user", content="你好")])
    """

    def __init__(
        self,
        provider: LLMProvider,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit: Optional[RateLimiter] = None,
        use_cache: bool = True,
    ):
        self.provider = provider
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limiter = rate_limit or RateLimiter()
        self.use_cache = use_cache

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 8000,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """带缓存和重试的生成"""
        # 1. 检查缓存
        if self.use_cache and not kwargs.get("stream"):
            key = _llm_cache_key(messages, system_prompt, temperature,
                                  self.provider.model or self.provider.api_base)
            if key in _llm_cache:
                cached = _llm_cache[key]
                print(f"[LLM Cache] 命中缓存 (latency={cached.latency_ms}ms)")
                return cached

        # 2. 速率限制
        await self.rate_limiter.acquire()

        # 3. 带重试的调用
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.provider.generate(
                    messages, temperature, max_tokens, system_prompt, **kwargs
                )
                if response.error:
                    raise Exception(response.error)

                # 存入缓存
                if self.use_cache and not kwargs.get("stream"):
                    key = _llm_cache_key(messages, system_prompt, temperature,
                                          self.provider.model or self.provider.api_base)
                    async with _llm_cache_lock:
                        while len(_llm_cache) >= _llm_cache_max:
                            oldest = next(iter(_llm_cache))
                            _llm_cache.pop(oldest, None)
                        _llm_cache[key] = response

                return response

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)
                    print(f"[LLM Gateway] 重试 {attempt + 1}/{self.max_retries}，等待 {wait}s: {e}")
                    await asyncio.sleep(wait)

        # 所有重试都失败
        return LLMResponse(
            content="",
            provider=self.provider.__class__.__name__.replace("Provider", ""),
            model=getattr(self.provider, "model", "unknown"),
            error=f"所有重试失败: {last_error}",
        )

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 8000,
        system_prompt: Optional[str] = None,
        **kwargs,
    ):
        """带重试的流式生成"""
        for attempt in range(self.max_retries):
            try:
                async for chunk in self.provider.generate_stream(
                    messages, temperature, max_tokens, system_prompt, **kwargs
                ):
                    yield chunk
                return
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)
                    print(f"[LLM Gateway Stream] 重试 {attempt + 1}/{self.max_retries}: {e}")
                    await asyncio.sleep(wait)
                else:
                    yield {"type": "error", "error": str(e)}


# ── 全局实例 ──

_global_gateway: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    """获取全局 LLM 网关单例"""
    global _global_gateway
    if _global_gateway is None:
        from .client import create_llm_client
        client = create_llm_client()
        _global_gateway = LLMGateway(provider=client)
    return _global_gateway
