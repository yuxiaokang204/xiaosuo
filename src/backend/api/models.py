"""
请求模型 — 所有 Pydantic BaseModel 请求/响应模型
供 api/ router 模块通过 `from .models import ...` 导入
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ── 创作 Agent 请求模型 ────────────────────────────────────────

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


# ── 学习引擎请求模型 ───────────────────────────────────────────

class FeedbackRequest(BaseModel):
    chapter_id: Optional[str] = None
    feedback_type: str = "style_edit"
    before_text: Optional[str] = None
    after_text: Optional[str] = None
    metadata: Optional[dict] = None


# ── LLM 配置请求模型 ───────────────────────────────────────────

class LLMConfigRequest(BaseModel):
    provider: str = Field(..., description="Provider ID，如 openai/deepseek/anthropic/google/qwen/moonshot/ollama/custom_openai/mock")
    api_key: Optional[str] = Field("", description="API Key（对 mock/ollama 可空）")
    model: Optional[str] = Field("", description="模型名，默认使用 Provider 的默认模型")
    api_base: Optional[str] = Field("", description="自定义 API 基础 URL，custom_openai 必填")


class SaveLLMConfigRequest(BaseModel):
    name: str
    provider: str
    api_key: str = ""
    model: str = ""
    api_base: str = ""


# 别名（兼容任务描述中的命名）
LLMSaveConfigRequest = SaveLLMConfigRequest
LLMSetConfigRequest = LLMConfigRequest
LLMModelsRequest = LLMConfigRequest


# ── Orchestrator 请求模型 ──────────────────────────────────────

class OrchestratorRequest(BaseModel):
    title: str = Field(..., min_length=1, description="小说标题")
    theme: str = Field(..., min_length=1, description="主题")
    tone: str = "史诗"
    chapter_count: int = 10
    novel_id: Optional[str] = None


class StageRequest(BaseModel):
    novel_id: str = Field(..., description="编排器 ID")
    stage: str = Field(..., description="要执行的阶段: worldbuilding/characters/style/outlining/drafting/editing/review")


# ── Novel 管理请求模型 ─────────────────────────────────────────

class CreateNovelRequest(BaseModel):
    title: str
    genre: str = ""


class ChapterUpdateRequest(BaseModel):
    content: str = Field(..., description="章节内容")


# ── Settings (角色/世界观 CRUD) 请求模型 ────────────────────────

class SaveWorldRequest(BaseModel):
    name: str
    category: str = "other"
    description: str = ""
    rules: list = []
    history: list = []
    locations: list = []
    factions: list = []


class SaveCharacterRequest(BaseModel):
    name: str
    role: str = "protagonist"
    personality: str = ""
    background: str = ""
    appearance: str = ""
    goals: list = []
    conflicts: list = []
    speech_pattern: str = ""
    aliases: list = []
    world_id: str = ""
    arc_data: dict = None


class UpdateCharacterRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    goals: Optional[list] = None
    conflicts: Optional[list] = None
    speech_pattern: Optional[str] = None
    aliases: Optional[list] = None
    arc_data: Optional[dict] = None
    world_id: Optional[str] = None


class UpdateWorldRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[list] = None
    history: Optional[list] = None


# 别名（兼容任务描述中的命名）
WorldSettingRequest = SaveWorldRequest
CharacterSettingRequest = SaveCharacterRequest
CharacterSettingUpdateRequest = UpdateCharacterRequest
WorldSettingUpdateRequest = UpdateWorldRequest


# ── Prompt 管理请求模型 ────────────────────────────────────────

class AgentPromptRequest(BaseModel):
    agent_type: str = Field(..., description="story_architect | world | character | opening_hook | draft | style_editor")
    depth_level: int = Field(1, ge=0, le=2, description="0=SKELETON, 1=DETAIL, 2=POLISH")
    prompt_type: str = Field("system", description="system | user")
    title: str = ""
    content: str = Field(..., min_length=1)
    quality_score: int = Field(0, ge=0, le=100)
    novel_id: Optional[str] = None
    is_active: int = 0
    metadata: Optional[Dict[str, Any]] = None


# 别名
PromptCreateRequest = AgentPromptRequest
PromptUpdateRequest = AgentPromptRequest


# ── Continuity 请求模型 ────────────────────────────────────────

class ContinuitySaveRequest(BaseModel):
    novel_id: str
    chapter_idx: int = Field(..., ge=1)
    chapter_title: str = ""
    ending_text: str = ""
    scene: Optional[Dict[str, Any]] = None
    character_states: Optional[List[Dict[str, Any]]] = None
    unresolved: Optional[List[str]] = None
    tension_points: Optional[List[str]] = None
    continuity_score: int = Field(7, ge=1, le=10)
    user_notes: str = ""


# ── AI 自动生成请求模型 ────────────────────────────────────────

class AutoGenWorldRequest(BaseModel):
    name: str
    category: str = "奇幻"
    config_id: str = ""


class AutoGenCharacterRequest(BaseModel):
    name: str
    role: str = "主角"
    world_name: str = ""
    world_category: str = ""
    world_description: str = ""
    world_rules: list = []
    config_id: str = ""