"""
Agent 管理路由 - Agent 注册、查询和调用
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from ..core.agent_registry_initializer import AgentRegistryInitializer

router = APIRouter(tags=["Agent"])


class OutlineRequest(BaseModel):
    theme: str = Field(..., description="小说主题，如'穿越异世修真'")
    tone: str = "史诗"
    chapter_count: int = 10
    world_info: Optional[str] = None
    characters: Optional[str] = None


class DraftRequest(BaseModel):
    chapter_title: str
    chapter_outline: str = ""
    summaries: Optional[str] = None
    characters: Optional[str] = None
    world: Optional[str] = None
    foreshadowing: Optional[str] = None
    style_guide: Optional[str] = None


class EditRequest(BaseModel):
    content: str = Field(..., description="待编辑原文")
    instructions: Optional[str] = None


class ReviewRequest(BaseModel):
    content: str
    context: Optional[str] = None


class WorldRequest(BaseModel):
    theme: str
    existing_world: Optional[str] = None
    title: Optional[str] = None


class CharacterRequest(BaseModel):
    role: str = "主角"
    world_info: Optional[str] = None
    theme: Optional[str] = None
    title: Optional[str] = None


class StyleRequest(BaseModel):
    preference: str = "默认风格"
    samples: Optional[str] = None


class PlotRequest(BaseModel):
    summaries: str = Field(..., description="最近章节概要，用于情节分析")
    characters: Optional[str] = None


# Agent ID 映射（向后兼容）
_AGENT_ID_MAP: Dict[str, str] = {
    "outline_agent": "story_architect",
    "plot_agent": "story_architect",
    "draft_agent": "draft",
    "edit_agent": "style_editor",
    "review_agent": "style_editor",
    "style_agent": "style_editor",
    "world_agent": "world",
    "character_agent": "character",
    "opening_hook_agent": "opening_hook",
    "story_architect": "story_architect",
    "world": "world",
    "character": "character",
    "opening_hook": "opening_hook",
    "draft": "draft",
    "style_editor": "style_editor",
}


def _resolve_agent_id(old_id: str) -> str:
    """将旧Agent ID映射到新ID"""
    return _AGENT_ID_MAP.get(old_id, old_id)


async def _call_agent_process(agent_id: str, context: Dict[str, Any]):
    """统一Agent调用入口：查注册表 → 获取实例 → 调用process()"""
    resolved_id = _resolve_agent_id(agent_id)
    from ..core.agent_registry_initializer import AgentRegistryInitializer
    
    global agent_initializer
    if agent_initializer is None:
        agent_initializer = AgentRegistryInitializer()
        agent_initializer.initialize()
    
    agent = agent_initializer.get_agent_instance(resolved_id)
    if not agent:
        raise HTTPException(404, f"未找到Agent: {agent_id} (resolved: {resolved_id})")
    try:
        return await agent.process(context)
    except Exception as e:
        raise HTTPException(500, f"Agent执行失败: {str(e)}")


# 全局初始化器（懒加载）
agent_initializer = None


@router.get("/agents")
async def list_agents():
    """列出所有已注册的Agent"""
    global agent_initializer
    if agent_initializer is None:
        agent_initializer = AgentRegistryInitializer()
        agent_initializer.initialize()
    return {"agents": agent_initializer.get_registry().to_dict()}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """获取单个Agent详情"""
    global agent_initializer
    if agent_initializer is None:
        agent_initializer = AgentRegistryInitializer()
        agent_initializer.initialize()
    reg = agent_initializer.get_registry().get(agent_id)
    if not reg:
        raise HTTPException(404, f"未找到Agent: {agent_id}")
    return {"agent": reg}


@router.get("/agents/capability/{capability}")
async def get_agents_by_capability(capability: str):
    """按能力查询Agent"""
    global agent_initializer
    if agent_initializer is None:
        agent_initializer = AgentRegistryInitializer()
        agent_initializer.initialize()
    agents = agent_initializer.get_registry().get_by_capability(capability)
    return {"capability": capability, "agents": agents}


@router.post("/create/outline")
async def create_outline(req: OutlineRequest):
    """生成小说大纲"""
    result = await _call_agent_process("outline_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/create/draft")
async def create_draft(req: DraftRequest):
    """生成章节草稿"""
    result = await _call_agent_process("draft_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/create/edit")
async def create_edit(req: EditRequest):
    """编辑优化章节"""
    result = await _call_agent_process("edit_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/create/review")
async def create_review(req: ReviewRequest):
    """审查与评分章节"""
    result = await _call_agent_process("review_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/create/world", tags=["创作"], description="AI 生成世界观设定")
async def create_world(req: WorldRequest):
    """生成世界观设定"""
    result = await _call_agent_process("world_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/create/character", tags=["创作"], description="AI 生成角色设计")
async def create_character(req: CharacterRequest):
    """生成角色设计"""
    result = await _call_agent_process("character_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/create/style")
async def create_style(req: StyleRequest):
    """生成写作风格指南"""
    result = await _call_agent_process("style_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/create/plot")
async def analyze_plot(req: PlotRequest):
    """分析当前情节并给出推进建议"""
    result = await _call_agent_process("plot_agent", req.model_dump())
    return {"success": True, "data": result}
