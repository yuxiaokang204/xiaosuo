"""
Agent 管理端点 — /api/agents
"""
from fastapi import APIRouter, HTTPException

from .deps import _ensure_services_ready, agent_initializer

router = APIRouter(prefix="/api/agents", tags=["Agent"])


@router.get("")
async def list_agents():
    _ensure_services_ready()
    return {"agents": agent_initializer.get_registry().to_dict()}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    _ensure_services_ready()
    reg = agent_initializer.get_registry().get(agent_id)
    if not reg:
        raise HTTPException(404, f"未找到Agent: {agent_id}")
    return {"agent": reg}


@router.get("/capability/{capability}")
async def get_agents_by_capability(capability: str):
    _ensure_services_ready()
    agents = agent_initializer.get_registry().get_by_capability(capability)
    return {"capability": capability, "agents": agents}