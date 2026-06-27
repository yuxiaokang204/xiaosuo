"""
记忆系统路由 - 记忆查询和操作
"""
from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter(tags=["记忆"])


@router.get("/memory/stats")
async def get_memory_stats(memory_service=None):
    """获取记忆系统统计信息"""
    if memory_service:
        return memory_service.get_stats()
    # 回退到旧版 NovelMemory
    global novel_memory
    if novel_memory is None:
        from ..core.memory import NovelMemory, ModelConfig
        novel_memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)
    return {"stats": novel_memory.get_context_stats()}


@router.post("/memory/characters")
async def store_characters(characters: List[Dict], memory_service=None):
    """存储角色信息到长期记忆"""
    if memory_service:
        return memory_service.store_characters(characters)
    global novel_memory
    if novel_memory is None:
        from ..core.memory import NovelMemory, ModelConfig
        novel_memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)
    novel_memory.store_characters(characters)
    return {"success": True, "count": len(characters)}


@router.post("/memory/world")
async def store_world_settings(settings: List[Dict], memory_service=None):
    """存储世界观设定到长期记忆"""
    if memory_service:
        return memory_service.store_world_settings(settings)
    global novel_memory
    if novel_memory is None:
        from ..core.memory import NovelMemory, ModelConfig
        novel_memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)
    novel_memory.store_world_settings(settings)
    return {"success": True, "count": len(settings)}


# 全局回退变量
novel_memory = None
