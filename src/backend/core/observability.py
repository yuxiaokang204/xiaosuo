"""
可观测性模块 v1.0 — LLM 调用追踪 + 结构化日志

特性：
- 可选集成 LangFuse（通过 LANGFUSE_ENABLED=true 开启）
- 无 LangFuse 时自动降级为结构化日志
- 追踪维度：token 消耗、延迟、成功率、错误类型
- 上下文注入：novel_id、chapter_idx、agent_name

用法:
    from .observability import trace_llm_call, TraceContext

    @trace_llm_call(agent_name="world_agent")
    async def generate(self, ...):
        ...
"""

import functools
import json
import logging
import os
import time
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("observability")

# ────────────────────────────────────────────────────
# 上下文变量
# ────────────────────────────────────────────────────

_current_novel_id: ContextVar[str] = ContextVar("novel_id", default="")
_current_chapter_idx: ContextVar[int] = ContextVar("chapter_idx", default=0)
_current_agent_name: ContextVar[str] = ContextVar("agent_name", default="unknown")

# ────────────────────────────────────────────────────
# LangFuse 可选集成
# ────────────────────────────────────────────────────

LANGFUSE_ENABLED = os.environ.get("LANGFUSE_ENABLED", "false").lower() in ("true", "1", "yes")
_langfuse_client = None

if LANGFUSE_ENABLED:
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        logger.info("[Observability] LangFuse 已连接")
    except ImportError:
        logger.warning("[Observability] langfuse 未安装，降级为结构化日志")
        _langfuse_client = None
    except Exception as e:
        logger.warning(f"[Observability] LangFuse 连接失败: {e}，降级为结构化日志")
        _langfuse_client = None


# ────────────────────────────────────────────────────
# TraceContext
# ────────────────────────────────────────────────────


class TraceContext:
    """追踪上下文管理器"""

    def __init__(self, novel_id: str = "", chapter_idx: int = 0, agent_name: str = "unknown"):
        self._token = None
        self._novel_id = novel_id
        self._chapter_idx = chapter_idx
        self._agent_name = agent_name

    def __enter__(self):
        self._token = (
            _current_novel_id.set(self._novel_id),
            _current_chapter_idx.set(self._chapter_idx),
            _current_agent_name.set(self._agent_name),
        )
        return self

    def __exit__(self, *args):
        if self._token:
            _current_novel_id.reset(self._token[0])
            _current_chapter_idx.reset(self._token[1])
            _current_agent_name.reset(self._token[2])


# ────────────────────────────────────────────────────
# 装饰器：追踪 LLM 调用
# ────────────────────────────────────────────────────


def trace_llm_call(func_name: str = "", agent_name: str = ""):
    """追踪 LLM 调用的装饰器

    自动记录：调用参数、响应内容、延迟、token 消耗、错误

    Args:
        func_name: 函数名（用于追踪）
        agent_name: Agent 名称
    """
    name = func_name or agent_name or "unknown"

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            trace_id = f"{int(start * 1000)}"

            # 结构化日志 — 调用开始
            context = {
                "trace_id": trace_id,
                "function": name,
                "novel_id": _current_novel_id.get(),
                "chapter_idx": _current_chapter_idx.get(),
                "agent": _current_agent_name.get() or agent_name,
            }

            try:
                result = await func(*args, **kwargs)
                elapsed_ms = int((time.time() - start) * 1000)

                # 提取 token 信息
                tokens = _extract_token_info(result)

                # 结构化日志 — 调用成功
                entry = {
                    **context,
                    "status": "success",
                    "latency_ms": elapsed_ms,
                    "tokens": tokens,
                    "response_len": len(str(result)) if result else 0,
                }
                logger.info(f"[Trace] LLM调用: {json.dumps(entry, ensure_ascii=False)}")

                # LangFuse 记录
                _langfuse_record(name, "success", elapsed_ms, tokens, context)

                return result

            except Exception as e:
                elapsed_ms = int((time.time() - start) * 1000)

                # 结构化日志 — 调用失败
                entry = {
                    **context,
                    "status": "error",
                    "error_type": type(e).__name__,
                    "error_msg": str(e)[:200],
                    "latency_ms": elapsed_ms,
                }
                logger.warning(f"[Trace] LLM调用失败: {json.dumps(entry, ensure_ascii=False)}")

                # LangFuse 记录错误
                _langfuse_record(name, "error", elapsed_ms, {}, context, error=str(e))

                raise

        return wrapper
    return decorator


def trace_stage(func: Callable):
    """追踪编排阶段的装饰器"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        stage_name = func.__name__
        start = time.time()
        novel_id = _current_novel_id.get()

        logger.info(f"[Trace] 阶段开始: {stage_name} (novel={novel_id[:8] if novel_id else '?'})")

        try:
            result = await func(*args, **kwargs)
            elapsed_ms = int((time.time() - start) * 1000)
            success = result.get("success", False) if isinstance(result, dict) else True
            logger.info(
                f"[Trace] 阶段完成: {stage_name} "
                f"({elapsed_ms}ms, {'OK' if success else 'FAIL'})"
            )
            return result
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.warning(f"[Trace] 阶段异常: {stage_name} ({elapsed_ms}ms, {type(e).__name__}: {e})")
            raise

    return wrapper


# ────────────────────────────────────────────────────
# 辅助函数
# ────────────────────────────────────────────────────


def _extract_token_info(result) -> Dict[str, int]:
    """从 LLM 响应中提取 token 信息"""
    tokens = {"total": 0, "prompt": 0, "completion": 0}
    if result is None:
        return tokens
    if hasattr(result, "usage"):
        usage = result.usage
        tokens["total"] = getattr(usage, "total_tokens", 0)
        tokens["prompt"] = getattr(usage, "prompt_tokens", 0)
        tokens["completion"] = getattr(usage, "completion_tokens", 0)
    elif isinstance(result, dict):
        usage = result.get("usage", {})
        if usage:
            tokens["total"] = usage.get("total_tokens", 0)
            tokens["prompt"] = usage.get("prompt_tokens", 0)
            tokens["completion"] = usage.get("completion_tokens", 0)
    return tokens


def _langfuse_record(name: str, status: str, latency_ms: int,
                     tokens: Dict, context: Dict, error: str = ""):
    """向 LangFuse 记录一次调用"""
    if _langfuse_client is None:
        return
    try:
        trace = _langfuse_client.trace(
            name=name,
            metadata={
                **context,
                "status": status,
                "latency_ms": latency_ms,
                "tokens": tokens,
            },
        )
        if status == "error":
            trace.generation(
                name=name,
                model=context.get("model", "unknown"),
                usage={
                    "input": tokens.get("prompt", 0),
                    "output": tokens.get("completion", 0),
                },
                metadata={"error": error[:500]},
            )
    except Exception:
        pass  # LangFuse 记录失败不阻塞主流程


def get_observability_stats() -> Dict[str, Any]:
    """获取可观测性状态"""
    return {
        "langfuse_enabled": LANGFUSE_ENABLED,
        "langfuse_connected": _langfuse_client is not None,
        "mode": "langfuse" if _langfuse_client else "structured_log",
    }