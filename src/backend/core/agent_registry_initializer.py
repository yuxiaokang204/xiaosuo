"""
Agent注册中心初始化器 v3.0 — 6个专业级创作Skill（方案A）
系统启动时自动创建并注册所有Skill
暴露统一的get()/get_by_capability()接口供调用方使用

方案A架构（8→6精简合并）：
  1. 故事架构师：大纲+爽点地图+情绪曲线（合并OutlineAgent + PlotAgent）
  2. 世界观构建师：保留
  3. 角色塑造师：保留
  4. 开篇钩子师：新增，专攻黄金三章+首章300字
  5. 专业写手：增强，含章节结尾悬念设计
  6. 文风精修师：合并StyleAgent + EditAgent + ReviewAgent
"""
from typing import Dict, Optional

from .agent_registry import AgentRegistry, AgentRegistration, AgentType
from .memory import NovelMemory, ModelConfig
from .event_bus import get_event_bus
from ..llm.client import get_default_llm_client

# 6个专业级Skill Agent
from ..agents.story_architect_agent import StoryArchitectAgent
from ..agents.opening_hook_agent import OpeningHookAgent
from ..agents.style_editor_agent import StyleEditorAgent
from ..agents.world_agent import WorldAgent
from ..agents.character_agent import CharacterAgent
from ..agents.draft_agent import DraftAgent


class AgentRegistryInitializer:
    def __init__(self):
        self.registry = AgentRegistry()
        # 实例映射: id → BaseAgent 实例
        self._agent_instances: Dict[str, object] = {}
        self._memory: Optional[NovelMemory] = None

    def set_memory(self, memory: NovelMemory):
        """设置记忆服务实例"""
        self._memory = memory

    def initialize(self) -> AgentRegistry:
        """注册全部6个Skill，返回就绪的Registry"""
        
        # 获取共享依赖
        llm_client = get_default_llm_client()
        event_bus = get_event_bus()
        memory = self._memory or NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)

        # 1. 故事架构师（合并Outline + Plot）
        story_architect = StoryArchitectAgent(
            gateway=llm_client,
            memory=memory,
            event_bus=event_bus
        )
        self._agent_instances["story_architect"] = story_architect
        self.registry.register(AgentRegistration(
            id="story_architect",
            name="故事架构师",
            agent_type=AgentType.WORKFLOW,
            capabilities=["outline", "planning", "plot", "structure", "excitement_map", "tension_curve", "causality_chain"],
            input_schema={"theme": "str", "tone": "str", "chapter_count": "int", "platform": "str"},
            output_schema={"chapters": "list", "narrative_arc": "dict", "tension_curve": "dict", "causality_chain": "list"},
            version="3.0.0",
        ))

        # 2. 世界观构建师（保留）
        world = WorldAgent(gateway=llm_client, memory=memory, event_bus=event_bus)
        self._agent_instances["world"] = world
        self.registry.register(AgentRegistration(
            id="world",
            name="世界观构建师",
            agent_type=AgentType.SPECIALIST,
            capabilities=["world_building", "setting", "lore", "sensory_anchor"],
            input_schema={"theme": "str", "existing_world": "str(可选)", "platform": "str(可选)"},
            output_schema={"name": "str", "rules": "list", "key_locations": "list", "factions": "list", "history": "list"},
            version="3.0.0",
        ))

        # 3. 角色塑造师（保留）
        character = CharacterAgent(gateway=llm_client, memory=memory, event_bus=event_bus)
        self._agent_instances["character"] = character
        self.registry.register(AgentRegistration(
            id="character",
            name="角色塑造师",
            agent_type=AgentType.SPECIALIST,
            capabilities=["character_design", "character_development", "persona", "behavior_tags", "speech_fingerprint"],
            input_schema={"role": "str(主角)", "world_info": "str(可选)", "platform": "str(可选)"},
            output_schema={"name": "str", "personality": "str", "background": "str", "goals": "list", "arc": "dict", "behavior_tags": "list"},
            version="3.0.0",
        ))

        # 4. 开篇钩子师（新增）
        opening_hook = OpeningHookAgent(gateway=llm_client, memory=memory, event_bus=event_bus)
        self._agent_instances["opening_hook"] = opening_hook
        self.registry.register(AgentRegistration(
            id="opening_hook",
            name="开篇钩子师",
            agent_type=AgentType.SPECIALIST,
            capabilities=["opening", "golden_three_chapters", "first_300_words", "hook_design", "platform_adaptation"],
            input_schema={"theme": "str", "platform": "str", "world_info": "str(可选)", "character_info": "str(可选)"},
            output_schema={"chapter_1": "dict", "chapter_2": "dict", "chapter_3": "dict", "platform_notes": "str"},
            version="3.0.0",
        ))

        # 5. 专业写手（增强）
        draft = DraftAgent(gateway=llm_client, memory=memory, event_bus=event_bus)
        self._agent_instances["draft"] = draft
        self.registry.register(AgentRegistration(
            id="draft",
            name="专业写手",
            agent_type=AgentType.WORKFLOW,
            capabilities=["writing", "draft", "composition", "chapter_ending_hook", "sensory_anchor", "platform_adaptation"],
            input_schema={"chapter_title": "str", "chapter_outline": "str", "summaries": "str(可选)", "platform": "str(可选)", "ending_hook_type": "str(可选)"},
            output_schema={"content": "str", "word_count": "int", "platform": "str"},
            version="3.0.0",
        ))

        # 6. 文风精修师（合并Style + Edit + Review）
        style_editor = StyleEditorAgent(gateway=llm_client, memory=memory, event_bus=event_bus)
        self._agent_instances["style_editor"] = style_editor
        self.registry.register(AgentRegistration(
            id="style_editor",
            name="文风精修师",
            agent_type=AgentType.WORKFLOW,
            capabilities=["style", "editing", "review", "refinement", "quality_check", "anti_ai_patterns"],
            input_schema={"content": "str", "theme": "str(可选)", "platform": "str(可选)", "mode": "str(full/style_only/edit_only/review_only)"},
            output_schema={"style_guide": "dict", "edited_content": "str", "review": "dict"},
            version="3.0.0",
        ))

        return self.registry

    def get_agent_instance(self, agent_id: str):
        """获取实际的Agent实例（用于调用process）"""
        return self._agent_instances.get(agent_id)

    def get_registry(self) -> AgentRegistry:
        return self.registry

    def get_memory(self) -> NovelMemory:
        """创建/返回一个新的NovelMemory（每次调用新建，避免上下文交叉污染）"""
        return NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)

    def describe(self) -> Dict:
        return {
            "total": len(self._agent_instances),
            "skills": list(self._agent_instances.keys()),
            "architecture": "方案A：8→6精简合并",
            "skills_detail": {
                "story_architect": "合并Outline+Plot，含爽点地图、情绪曲线",
                "world": "保留，增强感官锚点",
                "character": "保留，增强行为标签",
                "opening_hook": "新增，专攻黄金三章+首章300字",
                "draft": "增强，含章节结尾悬念设计",
                "style_editor": "合并Style+Edit+Review",
            },
        }
