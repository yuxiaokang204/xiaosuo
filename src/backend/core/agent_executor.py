"""
Agent 执行器 - 统一负责 Agent 调用的日志记录与异常处理
- 将每次 Agent.process() 的输入/输出/耗时/错误写入 agent_executions 表
- 提供 API 查询执行历史
"""
import asyncio
import json
import time
import uuid
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
from datetime import datetime

try:
    from ..db.database import SessionLocal
    from ..db.models import AgentExecutionDB
except Exception:
    SessionLocal = None
    AgentExecutionDB = None


class AgentExecutor:
    """封装 Agent 调用 - 自动记录执行历史、异常处理、重试"""

    _recent_history = []  # 最近 100 次执行（内存快速访问）
    _MAX_HISTORY = 100

    @classmethod
    async def run(cls, agent: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行一个 Agent，自动记录日志并捕获异常
        返回: Agent.process() 的结果字典
        """
        start = time.time()
        novel_id = str(context.get("novel_id", "") or "")
        task_type = agent.__class__.__name__
        error = None
        result = {"success": False, "error": "未知错误"}
        tokens = 0

        try:
            result = await agent.process(context)
            tokens = int(result.get("total_tokens", 0) or 0) or 0
            if not tokens:
                tokens = int(result.get("token_usage", 0) or 0)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            result = {"success": False, "error": error, "agent": task_type}
            print(f"[EXECUTOR] ❌ {task_type} 执行失败: {error}")

        duration_ms = int((time.time() - start) * 1000)

        # 写入数据库（失败时静默）
        cls._write_to_db(
            novel_id=novel_id,
            agent_type=task_type,
            task_type=context.get("__task__", "generate"),
            input_summary=cls._snippet(str(context.get("theme", "") or context.get("chapter_title", "") or context.get("content", "") or "")),
            output_summary=cls._snippet(json.dumps(result, ensure_ascii=False, default=str))[:4000],
            token_usage=tokens,
            error_log=error,
            status="SUCCESS" if not error else "FAILED",
            duration_ms=duration_ms,
        )

        # 内存缓存（最近 100 次）
        record = {
            "id": uuid.uuid4().hex[:12],
            "agent": task_type,
            "status": "SUCCESS" if not error else "FAILED",
            "duration_ms": duration_ms,
            "novel_id": novel_id,
            "created_at": datetime.now().isoformat(),
        }
        cls._recent_history.insert(0, record)
        if len(cls._recent_history) > cls._MAX_HISTORY:
            cls._recent_history = cls._recent_history[:cls._MAX_HISTORY]

        return result

    @staticmethod
    def _snippet(text: str, limit: int = 4000) -> str:
        text = str(text or "")
        return text if len(text) <= limit else text[:limit] + "...(截断)"

    @staticmethod
    def _write_to_db(novel_id: str, agent_type: str, task_type: str,
                     input_summary: str, output_summary: str, token_usage: int,
                     error_log: Optional[str], status: str, duration_ms: int):
        if SessionLocal is None or AgentExecutionDB is None:
            return
        try:
            db = SessionLocal()
            try:
                row = AgentExecutionDB(
                    id=uuid.uuid4().hex,
                    novel_id=novel_id or "__system__",
                    agent_type=agent_type,
                    task_type=task_type,
                    input_summary=input_summary,
                    output_summary=output_summary,
                    token_usage=token_usage,
                    error_log=error_log,
                    status=status,
                    duration_ms=duration_ms,
                    created_at=datetime.now(),
                )
                db.add(row)
                db.commit()
            finally:
                db.close()
        except Exception:
            pass  # 日志写入失败不影响主流程

    @classmethod
    def recent(cls, limit: int = 20) -> list:
        return cls._recent_history[:limit]

    @classmethod
    def stats(cls) -> Dict[str, Any]:
        total = len(cls._recent_history)
        success = sum(1 for r in cls._recent_history if r["status"] == "SUCCESS")
        failed = total - success
        total_ms = sum(r["duration_ms"] for r in cls._recent_history) if cls._recent_history else 0
        avg_ms = int(total_ms / total) if total else 0
        # 每个Agent的汇总
        by_agent: Dict[str, Dict[str, int]] = {}
        for r in cls._recent_history:
            a = r["agent"]
            if a not in by_agent:
                by_agent[a] = {"count": 0, "total_ms": 0}
            by_agent[a]["count"] += 1
            by_agent[a]["total_ms"] += r["duration_ms"]
        agent_stats = [
            {"agent": a, "count": v["count"], "avg_ms": int(v["total_ms"] / v["count"])}
            for a, v in by_agent.items()
        ]
        return {
            "total_executions": total,
            "success": success,
            "failed": failed,
            "avg_duration_ms": avg_ms,
            "by_agent": agent_stats,
        }


async def run_agent(agent: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    """模块级便捷函数"""
    return await AgentExecutor.run(agent, context)
