"""
LLM 调用保护层 — 重试/限流/缓存
"""
import asyncio
import hashlib
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ResilientLLMClient:
    """带重试、限流、缓存的LLM客户端包装器"""

    def __init__(self, client, max_retries=3, base_delay=1.0, rate_limit_rpm=30, cache_size=100):
        self._client = client
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._rate_limit_rpm = rate_limit_rpm
        self._cache: Dict[str, tuple] = {}  # key -> (result, timestamp)
        self._cache_size = cache_size
        self._call_timestamps: List[float] = []

    async def generate(self, messages, temperature=0.7, max_tokens=8000, system_prompt=None, **kwargs):
        """带保护的 generate 调用"""
        cache_key = self._make_cache_key(messages, temperature, max_tokens, system_prompt)

        # 1. 检查缓存
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug(f"[ResilientLLM] 缓存命中，跳过 LLM 调用")
            return cached

        # 2. 限流
        await self._rate_limit()

        # 3. 重试
        last_error = None
        for attempt in range(self._max_retries):
            try:
                result = await self._client.generate(
                    messages, temperature=temperature, max_tokens=max_tokens,
                    system_prompt=system_prompt, **kwargs
                )
                # 缓存成功结果
                self._cache_set(cache_key, result)
                return result
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning(f"[ResilientLLM] 第{attempt+1}次调用失败，{delay:.1f}s后重试: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[ResilientLLM] 已达最大重试次数({self._max_retries}): {e}")

        raise last_error

    async def generate_stream(self, messages, temperature=0.7, max_tokens=8000, system_prompt=None, **kwargs):
        """流式调用（不缓存，但支持重试和限流）"""
        await self._rate_limit()

        last_error = None
        for attempt in range(self._max_retries):
            try:
                async for chunk in self._client.generate_stream(
                    messages, temperature=temperature, max_tokens=max_tokens,
                    system_prompt=system_prompt, **kwargs
                ):
                    yield chunk
                return
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning(f"[ResilientLLM] 流式第{attempt+1}次失败，{delay:.1f}s后重试: {e}")
                    await asyncio.sleep(delay)

        raise last_error

    def estimate_tokens(self, text: str) -> int:
        return self._client.estimate_tokens(text)

    # ── 内部方法 ──

    def _make_cache_key(self, messages, temperature, max_tokens, system_prompt) -> str:
        content = str(messages) + str(temperature) + str(max_tokens) + (system_prompt or "")
        return hashlib.md5(content.encode()).hexdigest()

    def _cache_get(self, key):
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < 3600:  # 1小时过期
                return result
            del self._cache[key]
        return None

    def _cache_set(self, key, result):
        if len(self._cache) >= self._cache_size:
            # 删除最旧的条目
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest]
        self._cache[key] = (result, time.time())

    async def _rate_limit(self):
        now = time.time()
        self._call_timestamps = [t for t in self._call_timestamps if now - t < 60]
        if len(self._call_timestamps) >= self._rate_limit_rpm:
            wait_time = 60 - (now - self._call_timestamps[0]) + 0.1
            logger.debug(f"[ResilientLLM] 限流等待 {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        self._call_timestamps.append(time.time())

    def clear_cache(self):
        self._cache.clear()
        logger.info("[ResilientLLM] 缓存已清除")