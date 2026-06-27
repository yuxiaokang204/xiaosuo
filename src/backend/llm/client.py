"""
LLM客户端抽象层 + 多Provider实现
┌─────────────────────────────────────────────────────────────┐
│ Provider列表:                                                   │
│   MOCK          (本地模拟，无API Key也可用)                       │
│   OpenAI        (GPT-4o / GPT-4o-mini / GPT-3.5-turbo)         │
│   DeepSeek      (deepseek-chat / deepseek-reasoner)             │
│   Anthropic     (Claude 3.5 Sonnet / Opus / Haiku)              │
│   Google        (Gemini 2.0 / 1.5 Pro / Flash)                  │
│   Qwen / 阿里   (通义千问 Qwen2.5 / Qwen-plus / Qwen-max)       │
│   Moonshot      (月之暗面 Kimi / Kimi-128k)                     │
│   Ollama        (本地模型，如 qwen2.5 / llama3 / deepseek)       │
│   OpenRouter    (统一入口，支持上百种模型)                        │
│   自定义          (兼容OpenAI格式的任意API，如智谱 / 硅基流动等)  │
│                                                                 │
│ 特性:                                                             │
│   ✅ Provider切换零侵入 —— 前端通过 /api/llm/config 切换          │
│   ✅ 统一 generate(prompt, temp, max_tokens) 接口                   │
│   ✅ 自动JSON解析 + Mock回退                                      │
│   ✅ latency / token 统计                                          │
│                                                                 │
│ 使用示例:                                                         │
│   client = create_llm_client("deepseek", api_key="...")           │
│   response = await client.generate([...])                         │
│   print(response.content)                                         │
└─────────────────────────────────────────────────────────────┘
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib
import time
import os
import json
import random
import asyncio


class LLMProvider(str, Enum):
    MOCK = "mock"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    QWEN = "qwen"
    MOONSHOT = "moonshot"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    CUSTOM_OPENAI = "custom_openai"


# Provider元信息表（前端下拉菜单使用）
PROVIDER_META: Dict[str, Dict[str, Any]] = {
    "mock": {
        "label": "本地模拟 (Mock)",
        "description": "零依赖，生成示例占位内容，无API Key也可用",
        "api_base": "",
        "models": ["mock-local"],
        "needs_api_key": False,
    },
    "openai": {
        "label": "OpenAI (GPT-4o / GPT-4o-mini)",
        "description": "全球领先的大语言模型提供商",
        "api_base": "https://api.openai.com/v1/chat/completions",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "gpt-4.1", "o1", "o3-mini"],
        "needs_api_key": True,
    },
    "deepseek": {
        "label": "DeepSeek (深度求索)",
        "description": "国产高性能大模型，推理能力强",
        "api_base": "https://api.deepseek.com/chat/completions",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "needs_api_key": True,
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "description": "安全可靠的 Claude 系列模型",
        "api_base": "https://api.anthropic.com/v1/messages",
        "models": ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
        "needs_api_key": True,
    },
    "google": {
        "label": "Google Gemini",
        "description": "Gemini 系列多模态模型",
        "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "models": ["gemini-2.0-pro-exp", "gemini-1.5-pro", "gemini-1.5-flash"],
        "needs_api_key": True,
    },
    "qwen": {
        "label": "通义千问 (Qwen)",
        "description": "阿里大模型，兼容OpenAI接口",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "models": ["qwen2.5-72b-instruct", "qwen2.5-32b-instruct", "qwen-plus", "qwen-max"],
        "needs_api_key": True,
    },
    "moonshot": {
        "label": "月之暗面 Kimi",
        "description": "超长上下文 Kimi，支持200万token",
        "api_base": "https://api.moonshot.cn/v1/chat/completions",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "needs_api_key": True,
    },
    "ollama": {
        "label": "Ollama (本地运行)",
        "description": "本地部署开源模型，免费、隐私友好",
        "api_base": "http://localhost:11434/v1/chat/completions",
        "models": ["qwen2.5", "llama3.1", "deepseek-v2", "gemma2", "mistral"],
        "needs_api_key": False,
    },
    "openrouter": {
        "label": "OpenRouter (统一入口)",
        "description": "聚合上百种模型的统一API入口",
        "api_base": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["gpt-4o", "anthropic/claude-3.5-sonnet", "deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct"],
        "needs_api_key": True,
    },
    "custom_openai": {
        "label": "自定义 (OpenAI兼容)",
        "description": "适用于中国移动MAAS、智谱AI、硅基流动、零一万物等兼容OpenAI格式的平台",
        "api_base": "",
        "models": ["minimax-m25", "qwen36-35b"],
        "needs_api_key": True,
    },
}


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


# ── LLM 响应缓存（避免相同 prompt 重复调用 LLM）──
_llm_cache: Dict[str, LLMResponse] = {}
_llm_cache_max = 200
_llm_cache_lock = asyncio.Lock()  # 保护缓存写入/淘汰，避免并发下 del 竞争


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


class LLMClient(ABC):
    """LLM客户端抽象基类"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, api_base: Optional[str] = None):
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

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        english = len(text) - chinese
        return int(chinese / 1.5 + english / 4) + 10


# =====================================================================
# Mock Provider（本地模拟，不需要任何API Key）
# =====================================================================

class MockProvider(LLMClient):
    async def generate(
        self, messages, temperature=0.7, max_tokens=8000, system_prompt=None, **kwargs
    ) -> LLMResponse:
        user_text = ""
        for m in reversed(messages):
            msg = m.to_dict() if isinstance(m, LLMMessage) else m
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break

        content = self._mock_generate(user_text, system_prompt or "")
        total = self.estimate_tokens(user_text + content)

        return LLMResponse(
            content=content,
            provider="mock",
            model="mock-local",
            input_tokens=self.estimate_tokens(user_text),
            output_tokens=self.estimate_tokens(content),
            total_tokens=total,
            latency_ms=random.randint(150, 600),
            raw=None,
        )

    async def generate_stream(self, messages, temperature=0.7, max_tokens=8000,
                               system_prompt=None, **kwargs):
        """流式生成 - mock实现：按字典格式返回"""
        response = await self.generate(messages, temperature, max_tokens, system_prompt, **kwargs)
        content = response.content
        # 按段落分段流式输出，返回 dict 格式
        chunks = [p for p in content.split("\n") if p.strip()]
        if not chunks:
            chunks = [content]
        for chunk in chunks:
            yield {"type": "token", "content": chunk + "\n", "model": "mock-local"}
        yield {"type": "done", "content": ""}

    def _mock_generate(self, user_msg: str, system_prompt: str) -> str:
        msg = user_msg.lower()

        # 大纲生成
        if "大纲" in user_msg or "outline" in msg or "章节" in user_msg:
            chapters = []
            titles = ["初入江湖", "英雄初现", "风云际会", "暗流涌动", "生死考验",
                      "绝地反击", "真相初显", "师徒反目", "决战前夕", "终局之战"]
            for i, t in enumerate(titles):
                chapters.append({
                    "title": f"第{i+1}章 {t}",
                    "summary": f"情节推进的关键阶段：{t}，主角在此阶段面临新的挑战。",
                    "key_events": [f"事件{i*2+1}", f"事件{i*2+2}"],
                })
            return json.dumps({"chapters": chapters[:max(5, min(10, len(user_msg)//10))]},
                              ensure_ascii=False, indent=2)

        # 角色设计
        if "角色" in user_msg or "character" in msg:
            return json.dumps({
                "name": "李云舟",
                "aliases": ["云舟", "小李"],
                "role": "主角",
                "personality": "沉稳内敛，重情重义，外柔内刚，偶尔幽默自嘲",
                "background": "原为现代大学生，意外穿越到青云界，身怀未知血脉，初时软弱但韧性极强",
                "goals": ["寻找回家之路", "保护身边之人", "揭开身世之谜"],
                "conflicts": ["既依赖修行力量，又怕被力量异化", "对师门忠诚与对敌人宽容之间的矛盾"],
                "arc": {"start_state": "迷茫的外来者",
                        "mid_state": "找到目标，但代价沉重",
                        "end_state": "接受命运，主动承担责任"},
                "speech_pattern": "话不多但句句中肯，偶尔使用现代俚语自嘲",
                "appearance": "中等身材，眼神清澈，着素色道袍，腰间系着一只破旧的玉佩",
            }, ensure_ascii=False, indent=2)

        # 世界观
        if "世界" in user_msg or "world" in msg or "设定" in user_msg:
            return json.dumps({
                "name": "青云界",
                "category": "magic",
                "description": "一个灵气复苏的异世界，古老宗门林立，资源争夺激烈",
                "rules": ["存在灵气体系，修士可修炼延寿", "灵气分布不均，上古遗迹浓度最高", "修炼分九境，每境三转"],
                "key_locations": ["青云宗", "天堑山脉", "幽冥海", "落日城"],
                "factions": ["正道联盟", "魔教", "散修"],
                "inspirations": ["参考《诛仙》", "参考《诡秘之主》"],
            }, ensure_ascii=False, indent=2)

        # 风格指南
        if "风格" in user_msg or "style" in msg:
            return json.dumps({
                "vocabulary_preference": ["凝练", "克制", "动词优先"],
                "sentence_patterns": ["短句优先", "避免冗长修饰", "排比增强气势"],
                "pacing_preference": "快慢结合，关键场景拉长节奏",
                "tone": "冷峻带温情",
                "anti_patterns": ["眼中闪过一丝", "心中涌起一股", "忍不住"],
                "reference_works": ["余华", "村上春树"],
            }, ensure_ascii=False, indent=2)

        # 审查
        if "审查" in user_msg or "review" in msg or "评" in user_msg:
            return json.dumps({
                "overall_score": 7.5,
                "strengths": ["情节推进清晰", "人物动机合理", "语言流畅"],
                "issues": [
                    {"type": "plot", "text": "中段缺少紧张感"},
                    {"type": "pacing", "text": "某些过渡段落略长"},
                ],
                "suggestions": ["增加反派存在感", "缩短过渡描写"],
                "word_count": len(user_msg),
            }, ensure_ascii=False, indent=2)

        # 情节分析
        if "情节" in user_msg or "plot" in msg or "推进" in user_msg:
            return json.dumps({
                "analysis": "当前处于故事中段，主角已完成初步成长，但主要冲突尚未解决。读者对反派动机缺乏了解。",
                "next_plot_points": [
                    {"title": "引入关键情报",
                     "description": "让主角获得关于反派计划的关键情报，推动其做出新的抉择",
                     "foreshadowing": "情报中提到的某个人名将在后续成为关键人物"},
                    {"title": "重要盟友反水",
                     "description": "一个看似盟友的角色暴露自己的真实目的，增加紧张感",
                     "foreshadowing": "其之前对话中留下的细微破绽此刻变得合理"},
                ],
                "unresolved_items": ["主角的真实身世", "反派幕后首领", "远古力量来源"],
                "pacing_suggestion": "建议节奏紧张，对话减少，动作与决策主导",
            }, ensure_ascii=False, indent=2)

        # 默认 → 小说章节内容
        return (f"夜色如墨。\n\n"
                f"李云舟独自走在青石板铺就的小径上，身后是那座他刚刚离开的小山村。山风带着松涛的声音，远处传来几声不知名鸟儿的啼鸣。\n\n"
                f"该往哪里去呢？他低声自语，从怀里摸出一张泛黄的地图——这是他唯一从那个世界带来的东西。\n\n"
                f"一阵急促的脚步声从身后传来。他猛地回头，只见一道人影从林间冲出，朝他扑来。\n\n"
                f"小心！\n\n"
                f"话音未落，李云舟侧身一闪，堪堪躲过对方的攻击。月光下，他看清那人的面容——竟是村里的猎户老王。\n\n"
                f"别问那么多，跟我走！老王压低声音，一把抓住他的手腕，朝山林深处奔去。\n\n"
                f"（本章由Mock Provider生成，接入真实LLM后将获得更流畅的创作内容）")


# =====================================================================
# 通用 OpenAI 格式 Provider（所有兼容OpenAI的平台都可复用）
# =====================================================================

class OpenAICompatibleProvider(LLMClient):
    """所有兼容OpenAI格式的平台都可以复用这个实现"""

    def __init__(self, api_base: str, provider_name: str, api_key: Optional[str] = None,
                 model: Optional[str] = None, extra_headers: Optional[Dict[str, str]] = None,
                 auth_header: str = "Authorization", auth_prefix: str = "Bearer"):
        super().__init__(api_key=api_key, model=model)
        self.api_base = api_base
        self.provider_name = provider_name
        self.extra_headers = extra_headers or {}
        self.auth_header = auth_header
        self.auth_prefix = auth_prefix

    async def generate(
        self, messages, temperature=0.7, max_tokens=8000, system_prompt=None, **kwargs
    ) -> LLMResponse:
        # 1. 检查缓存（仅非流式模式下使用）
        cache_hit = False
        if not kwargs.get("stream"):
            key = _llm_cache_key(messages, system_prompt, temperature, self.model or self._default_model())
            if key in _llm_cache:
                cached = _llm_cache[key]
                print(f"[LLM Cache] 命中缓存 (latency={cached.latency_ms}ms)")
                return cached

        import httpx
        start = time.time()

        final_messages = self._build_messages(messages, system_prompt)

        payload = {
            "model": self.model or self._default_model(),
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = self._build_headers()

        try:
            verify = self.provider_name not in ("ollama", "custom_openai")
            async with httpx.AsyncClient(timeout=60.0, verify=verify) as client:
                r = await client.post(self.api_base, json=payload, headers=headers)
                latency_ms = int((time.time() - start) * 1000)

                if r.status_code != 200:
                    error_text = r.text[:500] if r.text else "(empty response)"
                    print(f"[LLM] HTTP错误 {r.status_code}: {error_text}")
                    return LLMResponse(
                        content="", provider=self.provider_name,
                        model=self.model or self._default_model(),
                        latency_ms=latency_ms,
                        error=f"HTTP {r.status_code}: {error_text}",
                    )

                data = r.json()
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                if not content:
                    print(f"[LLM] 警告: API返回空内容. data={data}")
                response = LLMResponse(
                    content=content,
                    provider=self.provider_name,
                    model=self.model or self._default_model(),
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    latency_ms=latency_ms,
                    raw=data,
                )

                # 2. 存入缓存（加锁避免并发淘汰时的 KeyError 竞争）
                if not kwargs.get("stream"):
                    key = _llm_cache_key(messages, system_prompt, temperature, self.model or self._default_model())
                    async with _llm_cache_lock:
                        while len(_llm_cache) >= _llm_cache_max:
                            oldest = next(iter(_llm_cache))
                            _llm_cache.pop(oldest, None)
                        _llm_cache[key] = response

                return response
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            import traceback
            error_detail = f"{type(e).__name__}: {e}"
            print(f"[LLM] 请求异常: {error_detail}\n{traceback.format_exc()}")
            return LLMResponse(
                content="", provider=self.provider_name,
                model=self.model or self._default_model(),
                latency_ms=latency_ms, error=error_detail,
            )

    async def generate_stream(self, messages, temperature=0.7, max_tokens=8000,
                              system_prompt=None, **kwargs):
        """流式生成：逐 token yield，用于实时推送到前端"""
        import httpx
        start = time.time()

        final_messages = self._build_messages(messages, system_prompt)

        payload = {
            "model": self.model or self._default_model(),
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        headers = self._build_headers()

        try:
            verify = self.provider_name not in ("ollama", "custom_openai")
            async with httpx.AsyncClient(timeout=120.0, verify=verify) as client:
                async with client.stream("POST", self.api_base, json=payload, headers=headers) as r:
                    if r.status_code != 200:
                        error_text = await r.aread()
                        print(f"[LLM Stream] HTTP错误 {r.status_code}: {error_text[:500]}")
                        yield {"type": "error", "error": f"HTTP {r.status_code}"}
                        return

                    full_content = ""
                    buffer = ""
                    async for line in r.aiter_lines():
                        if not line:
                            # 空行：尝试解析缓冲区中的累积数据
                            if buffer.strip():
                                # 去掉可能存在的 "data: " 前缀
                                data_str = buffer.strip()
                                if data_str.startswith("data: "):
                                    data_str = data_str[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                                    token = delta.get("content", "")
                                    if token:
                                        full_content += token
                                        yield {"type": "token", "content": token}
                                except json.JSONDecodeError:
                                    # 记录但不中断：便于排查 provider 返回异常分片
                                    print(f"[LLM Stream] 跳过无法解析的分片: {data_str[:120]!r}")
                                buffer = ""
                            continue

                        # 累积行到缓冲区
                        if buffer:
                            buffer += line
                        else:
                            buffer = line

                        # 尝试解析当前缓冲区
                        data_str = buffer.strip()
                        if data_str.startswith("data: "):
                            data_str = data_str[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                full_content += token
                                yield {"type": "token", "content": token}
                            buffer = ""
                        except json.JSONDecodeError:
                            # JSON 不完整，继续累积
                            continue

                    latency_ms = int((time.time() - start) * 1000)
                    yield {"type": "done", "content": full_content, "latency_ms": latency_ms,
                           "provider": self.provider_name, "model": self.model or self._default_model()}
        except Exception as e:
            import traceback
            yield {"type": "error", "error": f"{type(e).__name__}: {e}"}

    def _build_messages(self, messages, system_prompt=None):
        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        for m in messages:
            if isinstance(m, LLMMessage):
                final_messages.append(m.to_dict())
            else:
                final_messages.append(m)
        return final_messages

    def _build_headers(self):
        return {
            "Content-Type": "application/json",
            self.auth_header: f"{self.auth_prefix} {self.api_key or ''}" if self.api_key else self.auth_prefix,
            **self.extra_headers,
        }

    def _default_model(self) -> str:
        return PROVIDER_META.get(self.provider_name, {}).get("models", ["default"])[0]


# =====================================================================
# 各平台 Provider
# =====================================================================

class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, api_key=None, model=None, api_base=None):
        base = api_base or PROVIDER_META["openai"]["api_base"]
        super().__init__(base, "openai", api_key=api_key, model=model or "gpt-4o-mini")


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, api_key=None, model=None, api_base=None):
        base = api_base or PROVIDER_META["deepseek"]["api_base"]
        super().__init__(base, "deepseek", api_key=api_key, model=model or "deepseek-chat")


class GoogleProvider(OpenAICompatibleProvider):
    def __init__(self, api_key=None, model=None, api_base=None):
        base = api_base or PROVIDER_META["google"]["api_base"]
        super().__init__(base, "google", api_key=api_key, model=model or "gemini-1.5-pro")


class QwenProvider(OpenAICompatibleProvider):
    def __init__(self, api_key=None, model=None, api_base=None):
        base = api_base or PROVIDER_META["qwen"]["api_base"]
        super().__init__(base, "qwen", api_key=api_key, model=model or "qwen-plus")


class MoonshotProvider(OpenAICompatibleProvider):
    def __init__(self, api_key=None, model=None, api_base=None):
        base = api_base or PROVIDER_META["moonshot"]["api_base"]
        super().__init__(base, "moonshot", api_key=api_key, model=model or "moonshot-v1-128k")


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, api_key="ollama", model=None, api_base=None):
        base = api_base or PROVIDER_META["ollama"]["api_base"]
        super().__init__(base, "ollama", api_key="ollama", model=model or "qwen2.5")


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(self, api_key=None, model=None, api_base=None):
        base = api_base or PROVIDER_META["openrouter"]["api_base"]
        super().__init__(base, "openrouter", api_key=api_key, model=model or "gpt-4o")


class CustomOpenAIProvider(OpenAICompatibleProvider):
    DEFAULT_MODEL = "minimax-m25"
    
    def __init__(self, api_key=None, model=None, api_base=None):
        api_base = (api_base or "").rstrip("/")
        # 如果用户提供的是基础URL（不以 /chat/completions 结尾），自动追加
        if api_base and not api_base.endswith("/chat/completions"):
            api_base = api_base + "/chat/completions"
        super().__init__(api_base, "custom_openai", api_key=api_key, model=model or self.DEFAULT_MODEL)


# =====================================================================
# Anthropic Provider（使用自有消息格式，需单独实现）
# =====================================================================

class AnthropicProvider(LLMClient):
    def __init__(self, api_key=None, model=None, api_base=None):
        super().__init__(api_key=api_key, model=model or "claude-3-5-sonnet-20240620",
                         api_base=api_base or PROVIDER_META["anthropic"]["api_base"])

    async def generate(
        self, messages, temperature=0.7, max_tokens=8000, system_prompt=None, **kwargs
    ) -> LLMResponse:
        import aiohttp
        start = time.time()

        final_messages = []
        for m in messages:
            if isinstance(m, LLMMessage):
                final_messages.append(m.to_dict())
            else:
                final_messages.append(m)

        # Claude: system 消息需作为参数传递，不能混入 messages
        user_messages = [m for m in final_messages if m.get("role") != "system"]
        system_text = system_prompt or ""
        if not system_text:
            for m in final_messages:
                if m.get("role") == "system":
                    system_text = m.get("content", "")
                    break

        payload = {
            "model": self.model,
            "messages": user_messages or [{"role": "user", "content": "请继续"}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            payload["system"] = system_text

        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=180)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_base, json=payload, headers=headers) as r:
                    data = await r.json()
                    latency_ms = int((time.time() - start) * 1000)
                    if r.status != 200:
                        return LLMResponse(content="", provider="anthropic",
                                           model=self.model, latency_ms=latency_ms,
                                           error=f"HTTP {r.status}: {json.dumps(data, ensure_ascii=False)[:200]}")

                    blocks = data.get("content", [])
                    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                    usage = data.get("usage", {})
                    return LLMResponse(
                        content=text, provider="anthropic", model=self.model,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                        latency_ms=latency_ms, raw=data,
                    )
        except Exception as e:
            return LLMResponse(content="", provider="anthropic", model=self.model,
                               latency_ms=int((time.time() - start) * 1000), error=str(e))

    async def generate_stream(self, messages, temperature=0.7, max_tokens=8000,
                               system_prompt=None, **kwargs):
        """流式生成 - Anthropic SSE 格式（event: / data: 分行协议）"""
        import httpx
        start = time.time()

        final_messages = []
        for m in messages:
            if isinstance(m, LLMMessage):
                final_messages.append(m.to_dict())
            else:
                final_messages.append(m)

        user_messages = [m for m in final_messages if m.get("role") != "system"]
        system_text = system_prompt or ""
        if not system_text:
            for m in final_messages:
                if m.get("role") == "system":
                    system_text = m.get("content", "")
                    break

        payload = {
            "model": self.model,
            "messages": user_messages or [{"role": "user", "content": "请继续"}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if system_text:
            payload["system"] = system_text

        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
                async with client.stream("POST", self.api_base, json=payload, headers=headers) as r:
                    if r.status_code != 200:
                        error_text = await r.aread()
                        print(f"[Anthropic Stream] HTTP错误 {r.status_code}: {error_text[:500]}")
                        yield {"type": "error", "error": f"HTTP {r.status_code}"}
                        return

                    full_content = ""
                    async for line in r.aiter_lines():
                        if not line:
                            continue

                        # Anthropic SSE: "event: <type>" 或 "data: <json>"
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data = json.loads(data_str)
                                event_type = data.get("type", "")
                                if event_type == "content_block_delta":
                                    delta = data.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        text = delta.get("text", "")
                                        if text:
                                            full_content += text
                                            yield {"type": "token", "content": text}
                                elif event_type == "message_stop":
                                    break
                            except json.JSONDecodeError:
                                print(f"[Anthropic Stream] 跳过无法解析: {data_str[:120]!r}")

                    latency_ms = int((time.time() - start) * 1000)
                    yield {"type": "done", "content": full_content, "latency_ms": latency_ms,
                           "provider": "anthropic", "model": self.model}
        except Exception as e:
            import traceback
            print(f"[Anthropic Stream] 异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            yield {"type": "error", "error": f"{type(e).__name__}: {e}"}


# =====================================================================
# 工厂函数 & 全局客户端
# =====================================================================

_PROVIDER_CLASS_MAP = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "deepseek": DeepSeekProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "qwen": QwenProvider,
    "moonshot": MoonshotProvider,
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider,
    "custom_openai": CustomOpenAIProvider,
}


def create_llm_client(
    provider: str = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None,
) -> LLMClient:
    """
    根据配置创建LLM客户端
    - provider=None 时，从环境变量 LLM_PROVIDER 读取
    - api_key=None 时，从环境变量 LLM_API_KEY 读取
    - 任何不合法或缺少密钥的情况，优雅降级到 MockProvider
    """
    # 1. 判断 provider
    if not provider:
        provider = os.environ.get("LLM_PROVIDER", "mock").lower()

    # 2. 判断 api_key（Mock 和 Ollama 允许空 key）
    key_required = PROVIDER_META.get(provider, {}).get("needs_api_key", True)
    if key_required and not api_key:
        api_key = os.environ.get("LLM_API_KEY")

    # 3. 选择实现类
    cls = _PROVIDER_CLASS_MAP.get(provider)
    if cls is None:
        print(f"[LLM] ⚠️ 未知 provider '{provider}', 降级使用 MockProvider")
        return MockProvider()

    # 4. 需要密钥但无密钥 → 降级 Mock
    if cls not in (MockProvider, OllamaProvider) and not api_key:
        print(f"[LLM] ⚠️ provider='{provider}' 未配置API Key，降级使用 MockProvider")
        return MockProvider()

    try:
        if cls is MockProvider:
            return MockProvider()
        return cls(api_key=api_key, model=model, api_base=api_base)
    except Exception as e:
        print(f"[LLM] ⚠️ 初始化 {provider} 失败 ({e})，降级使用 MockProvider")
        return MockProvider()


_global_llm_client: Optional[LLMClient] = None


def get_default_llm_client() -> LLMClient:
    """懒获取全局默认 LLM 客户端"""
    global _global_llm_client
    if _global_llm_client is None:
        _global_llm_client = create_llm_client()
        print(f"[LLM] ✅ 默认客户端: {_global_llm_client.__class__.__name__}")
    return _global_llm_client


def set_default_llm_client(client: LLMClient) -> None:
    """热切换全局默认 LLM 客户端（供配置API调用）"""
    global _global_llm_client
    _global_llm_client = client
    print(f"[LLM] 🔄 已切换为: {client.__class__.__name__} (model={getattr(client, 'model', '?')})")


def list_providers() -> List[Dict[str, Any]]:
    """返回所有 Provider 的元信息（供前端下拉菜单）"""
    return [
        {
            "id": pid,
            "label": meta["label"],
            "description": meta["description"],
            "api_base": meta["api_base"],
            "models": meta["models"],
            "needs_api_key": meta["needs_api_key"],
        }
        for pid, meta in PROVIDER_META.items()
    ]
