"""
记忆系统端点 — /api/memory
"""
from typing import List, Dict

from fastapi import APIRouter

from .deps import _ensure_services_ready, novel_memory

router = APIRouter(prefix="/api/memory", tags=["Memory"])


@router.get("/stats")
async def get_memory_stats():
    _ensure_services_ready()
    return {"stats": novel_memory.get_context_stats()}


@router.post("/characters")
async def store_characters(characters: List[Dict]):
    """存储角色信息到长期记忆（Dict结构包含name/personality/background等字段）"""
    _ensure_services_ready()
    novel_memory.store_characters(characters)
    return {"success": True, "count": len(characters)}


@router.post("/world")
async def store_world_settings(settings: List[Dict]):
    """存储世界观设定到长期记忆"""
    _ensure_services_ready()
    novel_memory.store_world_settings(settings)
    return {"success": True, "count": len(settings)}