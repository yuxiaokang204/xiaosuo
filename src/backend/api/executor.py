"""
Agent 执行统计端点 — /api/executor
"""
from fastapi import APIRouter

from ..core.agent_executor import AgentExecutor

router = APIRouter(prefix="/api/executor", tags=["Executor"])


@router.get("/stats")
async def executor_stats():
    """全局 Agent 执行统计（总调用数 / 成功率 / 平均耗时 / 各 Agent 分布）"""
    return {"stats": AgentExecutor.stats()}


@router.get("/recent")
async def executor_recent(limit: int = 20):
    """最近 N 次 Agent 执行记录（仅内存，重启后清空）"""
    return {"recent": AgentExecutor.recent(limit=limit)}