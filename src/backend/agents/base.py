"""
Agent基类 v2.0 — 统一接口层

重构目标：
- 统一依赖注入：LLMGateway + MemoryService + EventBus
- 统一执行入口：execute() 替代 process()
- 统一LLM调用：_call_llm() 内置缓存、重试、JSON解析
- 统一事件发布：通过 EventBus 发布执行生命周期事件
- 兼容旧接口：保留 process() 作为 execute() 的别名

依赖：
- LLMGateway (llm.gateway) - LLM统一网关
- NovelMemory (core.memory) - 三层记忆系统（复用现有实现）
- EventBus (core.event_bus) - Agent间通信机制
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import json
import re
import time
import uuid

from ..llm.gateway import LLMGateway, LLMMessage
from ..core.memory import NovelMemory
from ..core.event_bus import EventBus


class BaseAgent(ABC):
    """Agent抽象基类 v2.0"""

    # ════════════════════════════════════════════
    # 类级属性（子类可覆盖）
    # ════════════════════════════════════════════
    AGENT_ID: str = "base"
    AGENT_NAME: str = "Base Agent"
    CAPABILITIES: List[str] = []
    EXPECTS_JSON: bool = True
    FALLBACK_TO_MOCK: bool = True
    DEFAULT_TEMPERATURE: float = 0.8

    def __init__(
        self,
        gateway: LLMGateway,
        memory: NovelMemory,
        event_bus: EventBus,
    ):
        """
        初始化Agent基类

        Args:
            gateway: LLM统一网关，负责缓存、重试、限流
            memory: 三层记忆系统（工作记忆/短期/长期）
            event_bus: 事件总线，用于Agent间通信
        """
        self.gateway = gateway
        self.memory = memory
        self.event_bus = event_bus
        self._temperature_override: Optional[float] = None
        self._instance_id = uuid.uuid4().hex[:8]
        print(f"[Agent {self.AGENT_ID}] 初始化完成 (id={self._instance_id})")

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Agent任务 - 统一入口

        Args:
            context: 执行上下文，包含任务所需的所有输入数据

        Returns:
            包含 success, data, 元信息的结果字典
        """
        pass

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        兼容旧接口 - 调用 execute()

        Args:
            context: 执行上下文

        Returns:
            执行结果
        """
        return await self.execute(context)

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        expects_json: bool = True,
        temperature: float = None,
        max_tokens: int = 4000,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        调用LLM（带缓存、重试、JSON解析）

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            expects_json: 是否期望JSON格式输出
            temperature: 温度参数（覆盖默认值）
            max_tokens: 最大输出token数
            **kwargs: 其他传递给Provider的参数

        Returns:
            {
                "success": True/False,
                "fallback": True/False,
                "data": parsed_json_or_dict,
                "content": raw_text,
                "provider": str,
                "latency_ms": int,
                "error": str_or_None,
            }
        """
        start_time = time.time()
        messages = [LLMMessage(role="user", content=user_prompt)]
        temp = temperature if temperature is not None else (
            self._temperature_override if self._temperature_override is not None else self.DEFAULT_TEMPERATURE
        )

        # 发布LLM调用事件
        await self.event_bus.publish("agent.llm_call", {
            "agent_id": self.AGENT_ID,
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(user_prompt),
            "temperature": temp,
            "max_tokens": max_tokens,
        })

        try:
            # 通过Gateway调用LLM（自动处理缓存、重试、限流）
            response = await self.gateway.generate(
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                **kwargs,
            )

            latency_ms = response.latency_ms or int((time.time() - start_time) * 1000)

            # 检查LLM返回的错误
            if response.error:
                print(f"[Agent {self.AGENT_ID}] ⚠️ LLM返回错误: {response.error}")
                await self.event_bus.publish("agent.llm_error", {
                    "agent_id": self.AGENT_ID,
                    "error": response.error,
                })
                return {
                    "success": True,
                    "fallback": True,
                    "fallback_reason": "llm_error",
                    "error": response.error,
                    "data": self._mock_fallback(user_prompt) if self.FALLBACK_TO_MOCK else {},
                    "content": response.content,
                    "provider": response.provider,
                    "latency_ms": latency_ms,
                    "note": "LLM返回错误，使用内置mock数据",
                }

            # 非JSON模式直接返回
            if not expects_json:
                return {
                    "success": True,
                    "fallback": False,
                    "content": response.content,
                    "provider": response.provider,
                    "latency_ms": latency_ms,
                }

            # JSON解析流程
            parsed = self._safe_parse_json(response.content)
            if parsed is None and self.FALLBACK_TO_MOCK:
                error_info = response.error
                print(f"[Agent {self.AGENT_ID}] ⚠️ JSON解析失败，使用mock兜底数据. Provider: {response.provider}")
                if error_info:
                    print(f"[Agent {self.AGENT_ID}] ⚠️ LLM错误信息: {error_info}")
                print(f"[Agent {self.AGENT_ID}] ⚠️ LLM原始返回(前500字): {response.content[:500]!r}")
                await self.event_bus.publish("agent.json_parse_failed", {
                    "agent_id": self.AGENT_ID,
                    "reason": "llm_error" if error_info else "json_parse_error",
                })
                fallback_reason = "llm_error" if error_info else "json_parse_error"
                return {
                    "success": True,
                    "fallback": True,
                    "fallback_reason": fallback_reason,
                    "error": error_info,
                    "data": self._mock_fallback(user_prompt),
                    "content": response.content,
                    "provider": response.provider,
                    "latency_ms": latency_ms,
                    "note": "JSON解析失败，使用内置mock数据",
                }

            # 发布成功事件
            await self.event_bus.publish("agent.llm_success", {
                "agent_id": self.AGENT_ID,
                "provider": response.provider,
                "latency_ms": latency_ms,
                "tokens": {
                    "input": response.input_tokens,
                    "output": response.output_tokens,
                    "total": response.total_tokens,
                },
            })

            return {
                "success": True,
                "fallback": False,
                "data": parsed,
                "raw": response.content,
                "provider": response.provider,
                "latency_ms": latency_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            }

        except Exception as e:
            import traceback
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = f"{type(e).__name__}: {e}"
            print(f"[Agent {self.AGENT_ID}] ❌ LLM调用异常: {error_msg}\n{traceback.format_exc()}")
            await self.event_bus.publish("agent.llm_exception", {
                "agent_id": self.AGENT_ID,
                "error": error_msg,
                "traceback": traceback.format_exc(),
            })
            return {
                "success": True,
                "fallback": True,
                "fallback_reason": "llm_call_exception",
                "error": error_msg,
                "data": self._mock_fallback(user_prompt) if self.FALLBACK_TO_MOCK else {},
                "content": "",
                "provider": getattr(self.gateway.provider, '__class__.__name__', 'unknown'),
                "latency_ms": latency_ms,
                "note": "LLM调用异常，使用内置mock数据",
            }

    def _safe_parse_json(self, text: str) -> Optional[Dict]:
        """
        健壮的JSON解析：处理markdown代码块、部分JSON截取

        解析策略（按优先级）：
        1. 直接解析完整文本
        2. 提取 ```json ... ``` 代码块
        3. 提取第一个{到最后一个}的内容
        4. 提取第一个[到最后一个]的内容（数组）
        5. 修复常见问题：尾逗号、单引号

        Args:
            text: LLM返回的原始文本

        Returns:
            解析后的字典，失败返回None
        """
        if not text:
            return None
        cleaned = text.strip()

        # 1. 尝试直接解析
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 2. 去掉```json ... ```代码块
        code_block_pattern = re.compile(r'```(?:json)?\s*\n?', re.DOTALL)
        matches = list(code_block_pattern.finditer(cleaned))
        if matches:
            start_pos = matches[0].end()
            close_match = re.search(r'\n?```', cleaned[start_pos:])
            if close_match:
                content = cleaned[start_pos:start_pos + close_match.start()]
                content = content.strip()
                try:
                    return json.loads(content)
                except Exception:
                    pass
            # 回退：如果没有找到关闭标记，尝试从start_pos到末尾
            content = cleaned[start_pos:].strip()
            try:
                return json.loads(content)
            except Exception:
                pass

        # 3. 找到第一个{和最后一个}，截取中间内容
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # 4. 找最外层的[ ... ]（数组）
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # 5. 尝试修复常见问题：尾逗号、单引号
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
            candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except Exception:
                pass

        return None

    def _mock_fallback(self, user_prompt: str) -> Dict:
        """
        子类可覆盖：JSON解析失败时返回兜底数据

        Args:
            user_prompt: 用户提示词（用于生成切题的mock数据）

        Returns:
            兜底数据字典
        """
        return {"note": "mock_fallback_not_implemented", "user_prompt": user_prompt[:200]}

    async def _publish_execute_start(self, context: Dict[str, Any]) -> str:
        """
        发布执行开始事件

        Returns:
            execution_id: 本次执行的唯一标识
        """
        execution_id = uuid.uuid4().hex[:8]
        await self.event_bus.publish("agent.execute_start", {
            "agent_id": self.AGENT_ID,
            "execution_id": execution_id,
            "agent_name": self.AGENT_NAME,
            "capabilities": self.CAPABILITIES,
            "context_keys": list(context.keys()),
        })
        return execution_id

    async def _publish_execute_done(
        self,
        execution_id: str,
        result: Dict[str, Any],
    ):
        """
        发布执行完成事件

        Args:
            execution_id: 执行标识
            result: 执行结果
        """
        await self.event_bus.publish("agent.execute_done", {
            "agent_id": self.AGENT_ID,
            "execution_id": execution_id,
            "success": result.get("success", False),
            "fallback": result.get("fallback", False),
            "latency_ms": result.get("latency_ms", 0),
        })
