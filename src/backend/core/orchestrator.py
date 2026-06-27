"""
Orchestrator 工作流编排器 v4.0 — 6-Skill LOOP 循环架构
支持两种模式:
  ┌ 线性流水线 (v3.0): planning → worldbuilding → characters → opening_hook → style → outlining → drafting → done
  │
  └ 循环架构 (v4.0): Loop 1(SKELETON) → Loop 2(DETAIL) → Loop 3(POLISH) → Loop 4+(REFINE)

v4.0 Loop 架构:
  - 每个Skill可在不同Loop迭代中以递增深度运行
  - Loop 1: SKELETON 骨架层(深度0) — 粗略世界观 + 角色卡 + 大纲骨架 + 钩子设计
  - Loop 2: DETAIL 细节层(深度1) — 细化设定 + 关系网 + 完整大纲 + 文风 + 逐章写作
  - Loop 3: POLISH 精修层(深度2) — 精修编辑 + 品质审查 + 调整后续章节
  - Loop 4+: REFINE 持续层(深度3+) — 视需要继续
  - 每个Skill接收 loop_metadata: {loop_index, depth_level, previous_output}

使用示例(循环模式):
    orch = NovelOrchestrator(title="青云界传说", theme="穿越异世修真", chapter_count=10)
    result = await orch.run_all_loop(max_loops=3)

使用示例(传统线性):
    orch = NovelOrchestrator(
        title="青云界传说",
        theme="穿越异世修真",
        tone="史诗",
        chapter_count=10,
        platform="番茄",  # 新增平台参数
    )
    await orch.run_stage("worldbuilding")      # 单阶段
    await orch.run_all()                        # 全流程

    status = orch.status()                      # {"stage": "drafting", "chapters_generated": 3, ...}
"""
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .state_tracker import StateTracker
from .consistency_checker import ConsistencyChecker
from .global_summary import GlobalSummary
from .memory import NovelMemory
from .memory_coordination import MemoryCoordinationEngine

# 延迟导入 Agent（避免循环依赖）- 方案A：6个专业级Skill
def _lazy_load_agents():
    """延迟加载6个专业Skill Agent — 注入共享依赖（gateway, memory, event_bus）"""
    from ..agents.story_architect_agent import StoryArchitectAgent
    from ..agents.world_agent import WorldAgent
    from ..agents.character_agent import CharacterAgent
    from ..agents.opening_hook_agent import OpeningHookAgent
    from ..agents.draft_agent import DraftAgent
    from ..agents.style_editor_agent import StyleEditorAgent
    from ..llm.client import get_default_llm_client
    from .event_bus import get_event_bus
    from .memory import NovelMemory, ModelConfig

    llm_client = get_default_llm_client()
    event_bus = get_event_bus()
    memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)

    return {
        # 方案A：6个专业级Skill
        "story_architect": StoryArchitectAgent(gateway=llm_client, memory=memory, event_bus=event_bus),
        "world": WorldAgent(gateway=llm_client, memory=memory, event_bus=event_bus),
        "character": CharacterAgent(gateway=llm_client, memory=memory, event_bus=event_bus),
        "opening_hook": OpeningHookAgent(gateway=llm_client, memory=memory, event_bus=event_bus),
        "draft": DraftAgent(gateway=llm_client, memory=memory, event_bus=event_bus),
        "style_editor": StyleEditorAgent(gateway=llm_client, memory=memory, event_bus=event_bus),
    }


# v3.0 新阶段顺序（可选）
STAGE_ORDER_V3 = [
    "planning",       # 0 初始规划
    "worldbuilding",  # 1 世界观
    "characters",     # 2 角色
    "opening_hook",   # 3 开篇钩子师（新增）
    "style",          # 4 风格指南
    "outlining",      # 5 大纲（故事架构师）
    "drafting",       # 6 草稿（专业写手）
    "style_editor",   # 7 文风精修（合并editing+review，可选）
    "done",           # 8 完成
]

# 方案A：6阶段精简流程（主流程）
STAGE_ORDER = [
    "planning",       # 0 初始规划
    "worldbuilding",  # 1 世界观
    "characters",     # 2 角色
    "opening_hook",   # 3 开篇钩子（新增）
    "style",          # 4 风格指南
    "outlining",      # 5 大纲（故事架构师）
    "drafting",       # 6 草稿（专业写手）
    "done",           # 7 完成
]


@dataclass
class OrchestratorState:
    novel_id: str
    title: str
    theme: str
    tone: str = "史诗"
    chapter_count: int = 10
    platform: str = "番茄"  # v3.0: 新增平台参数
    current_stage: str = "planning"
    completed_stages: List[str] = field(default_factory=list)
    world_settings: Optional[Dict] = None
    characters: List[Dict] = field(default_factory=list)
    opening_hook: Optional[Dict] = None  # v3.0: 新增开篇钩子设计
    style_guide: Optional[Dict] = None
    outline: List[Dict] = field(default_factory=list)
    chapters: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # v4.0: Loop 元数据
    current_loop: int = 0
    total_loops: int = 0
    depth_level: int = 0  # 0=skeleton, 1=detail, 2=polish, 3+=refine
    loop_history: List[Dict] = field(default_factory=list)  # 每次Loop的产出记录

    # v6.0: 故事走向（基于标题/类型/风格生成，供角色代入和章节生成使用）
    story_direction: str = ""

    # v6.1: 标题核心要素分析结果（通用，不硬编码关键词）
    title_analysis: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "novel_id": self.novel_id,
            "title": self.title,
            "theme": self.theme,
            "tone": self.tone,
            "chapter_count": self.chapter_count,
            "platform": self.platform,
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages,
            "chapters_count": len(self.chapters),
            "characters_count": len(self.characters),
            "has_world": self.world_settings is not None,
            "has_opening_hook": self.opening_hook is not None,  # v3.0
            "has_outline": bool(self.outline),
            "errors_count": len(self.errors),
            # v6.0: 故事走向状态
            "has_story_direction": bool(self.story_direction),
            # v4.0: Loop 元数据
            "current_loop": self.current_loop,
            "total_loops": self.total_loops,
            "depth_level": self.depth_level,
            "loops_completed": len(self.loop_history),
        }


@dataclass
class SkillLoopConfig:
    """
    v4.0: Loop 架构配置
    控制6个Skill的循环迭代深度和行为。
    每个Loop相当于对作品的"一次完整审视"，深度递增。
    """
    max_loops: int = 3  # 默认3个主循环(SKELETON→DETAIL→POLISH)
    chapters_per_draft_loop: int = 10  # 写作循环每次写多少章
    quality_threshold: float = 6.5  # 章节平均评分阈值(用于决定是否需要继续REFINE循环)
    enable_skeleton_loop: bool = True  # Loop 1: 快速构建骨架
    enable_detail_loop: bool = True  # Loop 2: 细化内容
    enable_polish_loop: bool = True  # Loop 3: 精修审查
    enable_refine_loops: bool = False  # Loop 4+: 是否启用持续精修
    temperature_profile: str = "gradient"  # gradient=逐渐降低温度, high=全程高创意, low=全程低温度

    def depth_for_loop(self, loop_index: int) -> str:
        """返回循环的深度层名称(SKELETON/DETAIL/POLISH/REFINE)"""
        if loop_index == 0:
            return "SKELETON"
        elif loop_index == 1:
            return "DETAIL"
        elif loop_index == 2:
            return "POLISH"
        else:
            return "REFINE"

    def temperature_for_loop(self, loop_index: int) -> float:
        """按循环序号返回推荐温度，越后期越保守"""
        if self.temperature_profile == "high":
            return 0.85
        elif self.temperature_profile == "low":
            return 0.4
        else:  # gradient: 随循环递减
            base = 0.85
            decay = loop_index * 0.15
            return max(0.3, round(base - decay, 2))


class NovelOrchestrator:
    """工作流编排器 v4.0 — 6-Skill LOOP 循环架构"""

    # 各阶段推荐温度（0=最确定，1=最随机）
    STAGE_TEMPERATURES = {
        "worldbuilding": 0.7,
        "characters": 0.7,
        "opening_hook": 0.8,  # v3.0: 开篇钩子需要更多创意
        "style": 0.6,
        "outlining": 0.7,
        "drafting": 0.85,
        "editing": 0.3,
        "review": 0.5,
        "style_editor": 0.4,  # v3.0: 文风精修需要较低温度
    }

    def __init__(self, title: str, theme: str, tone: str = "史诗",
                 chapter_count: int = 10, novel_id: Optional[str] = None,
                 platform: str = "番茄",  # v3.0: 新增平台参数
                 progress_callback: Optional[callable] = None,
                 preset_characters: Optional[List[Dict]] = None,
                 preset_world: Optional[Dict] = None,
                 learning_engine: Optional[Any] = None):  # v5.2: 学习引擎集成
        self.state = OrchestratorState(
            novel_id=novel_id or uuid.uuid4().hex[:10],
            title=title,
            theme=theme,
            tone=tone,
            chapter_count=chapter_count,
            platform=platform,
        )
        self._agents = None
        self._task_log: List[Dict] = []
        self._progress_callback = progress_callback  # SSE 推送回调
        self._preset_characters = preset_characters  # 预设角色
        self._preset_world = preset_world  # 预设世界观
        self._paused = False  # 暂停标志
        self._pause_event = asyncio.Event()  # 暂停事件
        self._pause_event.set()  # 初始未暂停
        # v2.0 新模块 - 必须在 _memory_engine 之前初始化
        self.state_tracker = StateTracker()
        self.consistency_checker = ConsistencyChecker()
        self.global_summary = GlobalSummary()
        # v5.1: 三层记忆系统 + 记忆协调引擎
        self._novel_memory = NovelMemory()
        self._memory_engine = MemoryCoordinationEngine(
            state_tracker=self.state_tracker,
            global_summary=self.global_summary,
            novel_memory=self._novel_memory,
            total_token_budget=4000,
            learning_engine=learning_engine,  # v5.2: 学习引擎集成
        )
        self._memory = self._memory_engine  # 保持向后兼容的别名
        # 重置全局记忆（新小说开始）
        self._reset_global_memory()
        # v5.3: 持久化初始工作流状态（仅在事件循环可用时执行）
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._save_run_state())
        except RuntimeError:
            pass  # 无事件循环时跳过（如测试环境）

        # v6.1: 异步分析标题核心要素（不阻塞初始化）
        self._title_analysis: Dict = {}
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_analyze_title())
        except RuntimeError:
            pass  # 无事件循环时跳过

    async def _async_analyze_title(self):
        """异步分析标题核心要素，结果缓存到 self._title_analysis"""
        try:
            from ..utils.title_analyzer import analyze_title
            self._title_analysis = await analyze_title(self.state.title)
            print(f"[Orchestrator] ✅ 标题分析完成: {self.state.title[:20]}...")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ 标题分析失败（非致命）: {e}")
            self._title_analysis = {
                "title": self.state.title,
                "keywords": [],
                "themes": [],
                "genre_hints": [],
                "tone": "",
                "unique_elements": [],
                "story_premise": "",
                "prompt_inject": f"【标题核心要素】本故事需围绕标题《{self.state.title}》中的核心意象展开。",
            }

    def _ensure_agents(self) -> Dict:
        """延迟初始化 Agent"""
        if self._agents is None:
            try:
                self._agents = _lazy_load_agents()
                print(f"[Orchestrator] ✅ 6个Skill Agent加载完成")
            except Exception as e:
                print(f"[Orchestrator] ❌ Agent加载失败: {e}")
                import traceback
                traceback.print_exc()
                self._agents = {}  # 设为空字典避免重复尝试
        return self._agents

    async def _generate_story_direction(self) -> str:
        """v6.0 基于标题/类型/风格生成故事走向

        在 outlining 阶段后调用，为角色代入和章节生成提供故事方向指引。
        故事走向包含：主线脉络、关键转折、情感基调、爽点分布。
        """
        from ..agents.prompts import STORY_DIRECTION_SYSTEM_PROMPT, build_story_direction_user_prompt
        from ..llm.client import LLMMessage, get_default_llm_client

        try:
            client = get_default_llm_client()
            user_prompt = build_story_direction_user_prompt(
                title=self.state.title,
                theme=self.state.theme,
                tone=self.state.tone,
                platform=self.state.platform,
                chapter_count=self.state.chapter_count,
                world_info=self._stringify(self.state.world_settings)[:500],
            )
            result = await client.generate(
                [LLMMessage(role="user", content=user_prompt)],
                system_prompt=STORY_DIRECTION_SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=800,
            )
            direction = (result.content or "").strip()
            if direction:
                self.state.story_direction = direction
                print(f"[Orchestrator] ✅ 故事走向生成完成 ({len(direction)}字)")
                await self._emit("story_direction", {"data": direction})
                return direction
            else:
                print("[Orchestrator] ⚠️ 故事走向生成返回空内容")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ 故事走向生成失败: {e}")
        return ""

    async def _save_prompts_auto(self, used_prompts: Dict[str, Any], loop_index: int):
        """v5.0: 自动保存循环中使用的优质 prompt 到 DB"""
        from ..db.database import AsyncSessionLocal
        from ..db.models import AgentPromptDB
        from sqlalchemy import select, and_
        from datetime import datetime
        import uuid

        min_score = 7  # 只有 quality_score >= 此值才保存
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.now()
                saved_count = 0
                for agent_type, pdata in used_prompts.items():
                    score = pdata.get("quality_score", 0)
                    if score < min_score:
                        continue
                    content = pdata.get("content", "")
                    if not content or len(content) < 50:
                        continue
                    depth_level = pdata.get("depth_level", 1)
                    # 检查是否已有相同 content 的记录（去重）
                    existing = await session.execute(
                        select(AgentPromptDB).where(and_(
                            AgentPromptDB.agent_type == agent_type,
                            AgentPromptDB.depth_level == depth_level,
                            AgentPromptDB.content == content,
                        )).limit(1)
                    )
                    if existing.scalar_one_or_none():
                        continue
                    p = AgentPromptDB(
                        id=str(uuid.uuid4()),
                        novel_id=self.state.novel_id,
                        agent_type=agent_type,
                        depth_level=depth_level,
                        prompt_type=pdata.get("prompt_type", "system"),
                        title=f"Loop{loop_index}-{agent_type}",
                        content=content,
                        quality_score=score * 10,  # 转换 0-10 → 0-100
                        is_active=0,  # 不自动激活，用户手动选择
                        meta_info={"loop": loop_index, "auto_saved": True},
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(p)
                    saved_count += 1
                if saved_count > 0:
                    await session.commit()
                    print(f"[Orchestrator] 💾 已自动保存 {saved_count} 个 prompt 到模板库")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ prompt 自动保存失败: {e}")

    def _reset_global_memory(self):
        """重置全局记忆"""
        self.state_tracker.reset()
        self.consistency_checker.reset()
        self.global_summary.reset()
        if hasattr(self, "_memory_engine") and self._memory_engine:
            try:
                self._memory_engine.reset()
            except Exception:
                pass

    # v5.3: 工作流状态持久化
    async def _save_run_state(self):
        """将当前 OrchestratorState 序列化为 JSON 存入 OrchestratorRunDB"""
        from ..db.database import AsyncSessionLocal
        from ..db.models import OrchestratorRunDB
        from datetime import datetime
        from sqlalchemy import select

        try:
            state_dict = asdict(self.state)
            state_json = json.dumps(state_dict, ensure_ascii=False, default=str)

            async with AsyncSessionLocal() as session:
                now = datetime.now()
                existing = await session.execute(
                    select(OrchestratorRunDB).where(OrchestratorRunDB.id == self.state.novel_id)
                )
                existing_run = existing.scalar_one_or_none()

                if existing_run:
                    existing_run.state_json = state_json
                    existing_run.current_loop = self.state.current_loop
                    existing_run.depth_level = self.state.depth_level
                    existing_run.current_stage = self.state.current_stage
                    existing_run.completed_stages = self.state.completed_stages
                    existing_run.error_log = json.dumps(self.state.errors, ensure_ascii=False)
                    existing_run.status = "paused" if self._paused else "running"
                    existing_run.updated_at = now
                else:
                    run = OrchestratorRunDB(
                        id=self.state.novel_id,
                        novel_id=self.state.novel_id,
                        title=self.state.title,
                        theme=self.state.theme,
                        tone=self.state.tone,
                        chapter_count=self.state.chapter_count,
                        platform=self.state.platform,
                        state_json=state_json,
                        current_loop=self.state.current_loop,
                        depth_level=self.state.depth_level,
                        current_stage=self.state.current_stage,
                        completed_stages=self.state.completed_stages,
                        status="running",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(run)
                await session.commit()
                print(f"[Orchestrator] 💾 工作流状态已持久化 (stage={self.state.current_stage}, loop={self.state.current_loop})")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ 工作流状态保存失败: {e}")

    @staticmethod
    async def load_run_state(run_id: str):
        """从 DB 恢复工作流状态"""
        from ..db.database import AsyncSessionLocal
        from ..db.models import OrchestratorRunDB
        from sqlalchemy import select

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(OrchestratorRunDB).where(OrchestratorRunDB.id == run_id)
                )
                run = result.scalar_one_or_none()
                if run is None:
                    return None
                return run
        except Exception as e:
            print(f"[Orchestrator] ⚠️ 加载运行状态失败: {e}")
            return None

    # ────────── 状态查询 ──────────
    def status(self) -> Dict[str, Any]:
        gs = self.global_summary.to_dict() if self.global_summary else {}
        return {
            **self.state.to_dict(),
            "task_log": self._task_log,
            "memory_stats": {
                "total_chapters": gs.get("total_chapters", 0),
                "total_words": gs.get("total_words", 0),
                "scene_anchors": gs.get("scene_anchors_count", 0),
                "plot_progress": gs.get("plot_progress", {}),
                "novel_memory_stats": self._memory.get_context_stats() if self._memory else {},
            },
        }

    def pause(self):
        self._paused = True
        self._pause_event.clear()

    def resume(self):
        self._paused = False
        self._pause_event.set()

    def abort(self):
        self._paused = True
        self._pause_event.set()  # 唤醒可能正在等待的协程
        self.state.current_stage = "aborted"

    # ────────── 单阶段执行 ──────────
    async def run_stage(self, stage: str) -> Dict[str, Any]:
        """
        执行指定阶段，返回阶段结果
        v3.0: 支持新阶段opening_hook和style_editor，所有阶段传入platform参数
        """
        stage = stage.lower()
        # 支持新旧阶段
        valid_stages = set(STAGE_ORDER) | set(STAGE_ORDER_V3)
        if stage not in valid_stages:
            return {"success": False, "error": f"未知阶段: {stage}"}

        self.state.current_stage = stage
        self.state.updated_at = time.time()

        try:
            agents = self._ensure_agents()

            if not agents:
                raise RuntimeError("Agent 加载失败，无法执行阶段")

            # 按阶段调整温度（通过实例属性覆盖，避免修改类属性导致并发问题）
            agent = agents.get(stage)
            if agent and stage in self.STAGE_TEMPERATURES:
                agent._temperature_override = self.STAGE_TEMPERATURES[stage]

            await self._emit("stage_start", {"stage": stage, "title": self.state.title, "platform": self.state.platform})
            if stage == "worldbuilding":
                # 如果已有预设世界观，直接使用
                if self._preset_world:
                    self.state.world_settings = self._preset_world
                    self._mark_done(stage)
                    await self._save_run_state()  # v5.3
                    await self._emit("worldbuilding", {"data": self._preset_world, "preset": True})
                    return {"success": True, "data": self._preset_world, "preset": True}

                result = await agents["world"].process({
                    "theme": f"{self.state.theme} - {self.state.title}",
                    "existing_world": json.dumps(self.state.world_settings, ensure_ascii=False) if self.state.world_settings else "",
                    "title": self.state.title,
                    "genre": self.state.theme,
                    "tone": self.state.tone,
                    "platform": self.state.platform,  # v3.0
                    "title_analysis": self._title_analysis,  # v6.1 标题核心要素
                    "temperature": self.STAGE_TEMPERATURES.get(stage, 0.7),
                })
                if result.get("success"):
                    self.state.world_settings = result
                    self._mark_done(stage)
                    await self._save_run_state()  # v5.3
                    await self._emit("worldbuilding", {"data": result})
                return result

            if stage == "characters":
                # 如果已有预设角色，直接使用（不再生成）
                if self._preset_characters:
                    self.state.characters = self._preset_characters
                    self._mark_done(stage)
                    await self._save_run_state()  # v5.3
                    await self._emit("characters", {"data": self._preset_characters, "preset": True})
                    return {"success": True, "data": self._preset_characters, "preset": True}

                # 生成唯一主角 — 使用小说标题和主题
                world_json = json.dumps(self.state.world_settings, ensure_ascii=False) if self.state.world_settings else ""
                result = await agents["character"].process({
                    "role": f"唯一主角",
                    "theme": self.state.theme,
                    "title": self.state.title,
                    "world_info": f"世界观：{world_json}\n小说主题：{self.state.theme}\n小说标题：{self.state.title}\n【重要规则】本小说只有一位主角，请根据主题和标题设计唯一主角，确保角色与故事背景匹配。",
                    "platform": self.state.platform,  # v3.0
                    "title_analysis": self._title_analysis,  # v6.1 标题核心要素
                    "temperature": self.STAGE_TEMPERATURES.get(stage, 0.7),
                })
                if result.get("success"):
                    self.state.characters = [result]
                    self._mark_done(stage)
                    await self._save_run_state()  # v5.3
                    await self._emit("characters", {"data": self.state.characters})
                return result

            # v3.0 新阶段：开篇钩子师
            if stage == "opening_hook":
                world_json = json.dumps(self.state.world_settings, ensure_ascii=False) if self.state.world_settings else ""
                char_json = json.dumps(self.state.characters, ensure_ascii=False) if self.state.characters else ""
                result = await agents["opening_hook"].process({
                    "title": self.state.title,
                    "theme": self.state.theme,
                    "platform": self.state.platform,
                    "world_info": world_json,
                    "character_info": char_json,
                    "temperature": self.STAGE_TEMPERATURES.get(stage, 0.8),
                })
                if result.get("success"):
                    self.state.opening_hook = result
                    self._mark_done(stage)
                    await self._save_run_state()  # v5.3
                    await self._emit("opening_hook", {"data": result})
                return result

            if stage == "style":
                result = await agents["style_editor"].process({
                    "title": self.state.title,
                    "content": "",
                    "theme": self.state.theme,
                    "platform": self.state.platform,
                    "mode": "style_only",  # 仅文风设计
                    "temperature": self.STAGE_TEMPERATURES.get(stage, 0.6),
                })
                if result.get("success"):
                    self.state.style_guide = result.get("style_guide", {})
                    self._mark_done(stage)
                    await self._save_run_state()  # v5.3
                    await self._emit("style", {"data": result})
                return result

            if stage == "outlining":
                result = await agents["story_architect"].process({
                    "title": self.state.title,
                    "theme": self.state.theme,
                    "tone": self.state.tone,
                    "chapter_count": self.state.chapter_count,
                    "platform": self.state.platform,
                    "world_info": json.dumps(self.state.world_settings, ensure_ascii=False) if self.state.world_settings else "",
                    "characters": json.dumps(self.state.characters, ensure_ascii=False) if self.state.characters else "",
                    "title_analysis": self._title_analysis,  # v6.1 标题核心要素
                    "temperature": self.STAGE_TEMPERATURES.get(stage, 0.7),
                })
                if result.get("success"):
                    outline_chapters = result.get("chapters", []) or []
                    # 如果大纲章节数不足，让 AI 续写剩余章节
                    if len(outline_chapters) < self.state.chapter_count:
                        missing_count = self.state.chapter_count - len(outline_chapters)
                        print(f"[Orchestrator] 📝 大纲仅{len(outline_chapters)}章，续写剩余{missing_count}章...")
                        extra_result = await agents["story_architect"].process({
                            "title": self.state.title,
                            "theme": self.state.theme,
                            "tone": self.state.tone,
                            "chapter_count": missing_count,
                            "platform": self.state.platform,
                            "world_info": json.dumps(self.state.world_settings, ensure_ascii=False) if self.state.world_settings else "",
                            "characters": json.dumps(self.state.characters, ensure_ascii=False) if self.state.characters else "",
                            "start_chapter": len(outline_chapters) + 1,
                            "existing_outline": json.dumps(outline_chapters[-3:], ensure_ascii=False),
                            "title_analysis": self._title_analysis,  # v6.1 标题核心要素
                            "temperature": self.STAGE_TEMPERATURES.get(stage, 0.7),
                        })
                        if extra_result.get("success"):
                            extra_chapters = extra_result.get("chapters", []) or []
                            # 修正续写章节的序号
                            for i, ch in enumerate(extra_chapters):
                                if isinstance(ch, dict):
                                    ch["title"] = f"第{len(outline_chapters) + i + 1}章 {ch.get('title', '').replace(f'第{i+1}章', '').strip()}"
                            outline_chapters.extend(extra_chapters)
                        # 如果 AI 续写也不够，再用创意标题补齐
                        if len(outline_chapters) < self.state.chapter_count:
                            default_titles = [
                                "风云突变", "暗潮汹涌", "绝地反击", "柳暗花明", "棋逢对手",
                                "破局之时", "背水一战", "拨云见日", "尘埃落定", "新的篇章",
                            ]
                            for i in range(len(outline_chapters), self.state.chapter_count):
                                t = default_titles[(i - len(outline_chapters)) % len(default_titles)]
                                outline_chapters.append({
                                    "title": f"第{i+1}章 {t}",
                                    "summary": f"情节持续推进，{self.state.theme}的故事进入新阶段。",
                                })
                    self.state.outline = outline_chapters
                    self._mark_done(stage)
                    await self._save_run_state()  # v5.3
                    await self._emit("outlining", {"data": outline_chapters, "total": len(outline_chapters)})
                    # v6.0: 大纲完成后生成故事走向（供角色代入和章节生成使用）
                    if not self.state.story_direction:
                        await self._generate_story_direction()
                return result

            if stage == "drafting":
                # ── 6-Skill 协同写作管道（方案A）──
                from .chapter_pipeline import ChapterPipeline

                outline = self.state.outline or []
                if not outline:
                    default_titles = [
                        "初入异世", "觉醒之路", "初次试炼", "危机四伏", "突破瓶颈",
                        "崭露头角", "暗流涌动", "绝地反击", "真相浮现", "最终决战",
                    ]
                    for i in range(self.state.chapter_count):
                        t = default_titles[i % len(default_titles)]
                        outline.append({"title": f"第{i+1}章 {t}", "summary": f"情节持续推进。"})
                    print("[Orchestrator] ⚠️ 无大纲，使用默认标题")

                # 更新角色状态追踪
                for ch in self.state.characters:
                    if isinstance(ch, dict) and ch.get("name"):
                        self.state_tracker.track_character(ch["name"], ch.get("personality", ""))

                pipeline = ChapterPipeline(
                    agents=self._ensure_agents(),
                    emit=self._emit,
                    state_tracker=self.state_tracker,
                    global_summary=self.global_summary,
                    pause_event=self._pause_event,
                    paused_ref=lambda: self._paused,
                    memory_engine=self._memory_engine,
                )

                # 共享上下文（管道内部按字符串读取）
                shared_context = {
                    "title": self.state.title,
                    "theme": self.state.theme,
                    "genre": self.state.theme,
                    "tone": self.state.tone,
                    "world": self._stringify(self.state.world_settings),
                    "characters": self._stringify(self.state.characters),
                    "style": self._stringify(self.state.style_guide),
                    # v6.0: 注入角色列表（供角色代入使用）和故事走向
                    "characters_list": self.state.characters,
                    "story_direction": self.state.story_direction,
                }

                await self._emit("drafting_start", {"total": len(outline)})

                # 逐章生成正文
                chapters: List[Dict] = []
                existing_text = ""
                for i, ch_outline in enumerate(outline):
                    await self._pause_event.wait()  # 支持暂停
                    chapter_idx = i + 1
                    ch_title = ch_outline.get("title", f"第{chapter_idx}章")
                    ch_summary = ch_outline.get("summary", "")

                    await self._emit("chapter_start", {
                        "index": chapter_idx,
                        "title": ch_title,
                        "total": len(outline),
                    })

                    # 单章生成加入指数退避重试，避免一次瞬时失败就退化为占位内容
                    _MAX_CHAPTER_ATTEMPTS = 3
                    result = None
                    last_error = None
                    for attempt in range(1, _MAX_CHAPTER_ATTEMPTS + 1):
                        try:
                            # 提取上一章结尾原文（用于强制衔接）
                            prev_ending = ""
                            if chapters:
                                prev_content = chapters[-1].get("content", "")
                                prev_ending = prev_content[-800:] if len(prev_content) > 800 else prev_content
                            result = await pipeline.run(
                                chapter_idx=chapter_idx,
                                title=ch_title,
                                summary=ch_summary,
                                chapter_outline_ch=ch_outline,
                                context=shared_context,
                                existing_chapters_text=existing_text[-4000:],
                                previous_chapter_text=prev_ending,
                                novel_id=self.state.novel_id,
                            )
                            break
                        except Exception as chapter_error:
                            last_error = chapter_error
                            print(f"[Orchestrator] ⚠️ 第{chapter_idx}章生成失败"
                                  f"（第{attempt}/{_MAX_CHAPTER_ATTEMPTS}次）: {chapter_error}")
                            if attempt < _MAX_CHAPTER_ATTEMPTS:
                                await asyncio.sleep(2 ** (attempt - 1))  # 1s, 2s 退避

                    if result is not None:
                        chapter = {
                            "title": result.title,
                            "content": result.content,
                            "summary": ch_summary,
                            "word_count": result.word_count,
                            "status": "draft",
                            "score": result.overall_score,
                        }
                        chapters.append(chapter)
                        existing_text += f"\n\n第{chapter_idx}章 {ch_title}\n{result.content}"

                        # 更新全局摘要（用于后续章节衔接）
                        self.global_summary.add_chapter_summary(
                            chapter=chapter_idx,
                            title=ch_title,
                            summary=ch_summary,
                            last_paragraph=result.content[-300:] if result.content else "",
                            word_count=result.word_count,
                            quality_score=result.overall_score,
                        )

                        await self._emit("chapter_done", {
                            "index": chapter_idx,
                            "total": len(outline),
                            "chapter": chapter,
                        })
                    else:
                        # 多次重试仍失败：写入显式错误占位，且不污染后续章节上下文
                        print(f"[Orchestrator] ❌ 第{chapter_idx}章重试{_MAX_CHAPTER_ATTEMPTS}次仍失败，继续下一章")
                        fallback_content = f"[第{chapter_idx}章：{ch_title}]\n\n本章生成暂时遇到问题，后续可手动补充。"
                        chapter = {
                            "title": ch_title,
                            "content": fallback_content,
                            "summary": ch_summary,
                            "word_count": len(fallback_content),
                            "status": "draft_error",
                            "score": 0,
                        }
                        chapters.append(chapter)
                        self.state.errors.append(f"chapter_{chapter_idx}: {last_error}")
                        await self._emit("chapter_error", {
                            "index": chapter_idx,
                            "total": len(outline),
                            "error": str(last_error),
                        })

                self.state.chapters = chapters
                self._mark_done(stage)
                await self._save_run_state()  # v5.3
                await self._emit("drafting_done", {"total": len(chapters)})

                return {"success": True, "chapters": chapters}

            if stage == "editing":
                await self._emit("editing_start", {"total": len(self.state.chapters)})
                for ch in self.state.chapters:
                    await self._pause_event.wait()  # 支持暂停
                    if ch.get("content"):
                        try:
                            r = await agents["style_editor"].process({
                                "content": ch["content"],
                                "theme": self.state.theme,
                                "platform": self.state.platform,
                                "mode": "edit_only",  # 仅精修编辑
                                "temperature": self.STAGE_TEMPERATURES.get(stage, 0.3),
                            })
                            if r.get("success"):
                                ch["content"] = r.get("edited_content", ch["content"])
                                ch["status"] = "edited"
                        except Exception:
                            pass
                self._mark_done(stage)
                await self._save_run_state()  # v5.3
                await self._emit("editing_done", {"total": len(self.state.chapters)})
                return {"success": True, "stage": "editing", "edited": len(self.state.chapters)}

            if stage == "review":
                await self._emit("review_start", {"total": len(self.state.chapters)})
                scores: List[Dict] = []
                for ch in self.state.chapters:
                    await self._pause_event.wait()  # 支持暂停
                    if ch.get("content"):
                        try:
                            r = await agents["style_editor"].process({
                                "content": ch["content"],
                                "theme": self.state.theme,
                                "platform": self.state.platform,
                                "mode": "review_only",  # 仅品质审查
                                "temperature": self.STAGE_TEMPERATURES.get(stage, 0.5),
                            })
                            scores.append({"title": ch.get("title"), "review": r.get("review", {})})
                        except Exception:
                            pass
                self._mark_done(stage)
                await self._save_run_state()  # v5.3
                await self._emit("review_done", {"total": len(scores)})
                return {"success": True, "stage": "review", "reviews": scores}

            if stage == "style_editor":
                # 合并编辑+审查
                await self._emit("style_editor_start", {"total": len(self.state.chapters)})
                results = []
                for ch in self.state.chapters:
                    await self._pause_event.wait()
                    if ch.get("content"):
                        try:
                            r = await agents["style_editor"].process({
                                "content": ch["content"],
                                "theme": self.state.theme,
                                "platform": self.state.platform,
                                "mode": "full",  # 全流程：文风设计+编辑+审查
                                "temperature": self.STAGE_TEMPERATURES.get(stage, 0.4),
                            })
                            if r.get("success"):
                                ch["content"] = r.get("edited_content", ch["content"])
                                ch["status"] = "edited_and_reviewed"
                                ch["review"] = r.get("review", {})
                                results.append(r)
                        except Exception:
                            pass
                self._mark_done(stage)
                await self._save_run_state()  # v5.3
                await self._emit("style_editor_done", {"total": len(results)})
                return {"success": True, "stage": "style_editor", "results": results}

            if stage in ("planning", "done"):
                self._mark_done(stage)
                await self._save_run_state()  # v5.3
                return {"success": True, "stage": stage}

        except Exception as e:
            error_msg = f"阶段 {stage} 执行失败: {e}"
            print(f"[Orchestrator] ❌ {error_msg}")
            self.state.errors.append(error_msg)
            return {"success": False, "error": str(e), "stage": stage}

        return {"success": False, "error": "未知阶段", "stage": stage}

    # ────────── 全流程编排 (传统线性) ──────────
    async def run_all(self, skip_stages: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        按顺序执行所有阶段直到完成
        skip_stages: 可跳过的阶段列表，如 ["editing"] 跳过编辑阶段
        """
        skip_stages = set(skip_stages or []) | {"planning", "done"}
        results: Dict[str, Dict] = {}
        await self._emit("run_all_start", {"title": self.state.title, "chapter_count": self.state.chapter_count, "novel_id": self.state.novel_id})
        for stage in STAGE_ORDER:
            if stage in skip_stages:
                results[stage] = {"success": True, "note": "skip"}
                continue
            if stage == "done":
                break
            print(f"[Orchestrator] ▶ {stage}")
            try:
                result = await self.run_stage(stage)
                results[stage] = result
                # v3.0: 即使success=False也不中断（使用mock数据继续）
                if not result.get("success"):
                    print(f"[Orchestrator] ⚠️ 阶段 {stage} 失败，使用mock数据继续: {result.get('error', '')}")
                    results[stage]["__mock__"] = True
            except Exception as e:
                print(f"[Orchestrator] ❌ 阶段 {stage} 异常: {e}")
                results[stage] = {"success": False, "error": str(e), "__mock__": True}
                self.state.errors.append(f"{stage}: {e}")
        self.state.current_stage = "done"
        results["__status__"] = "completed"  # v3.0: 始终标记为完成
        await self._emit("run_all_done", {"status": "completed", "completed_stages": self.state.completed_stages})
        return {"success": True, "results": results, "state": self.state.to_dict()}

    # ────────── v4.0: 6-Skill LOOP 循环编排 ──────────
    async def run_all_loop(self, max_loops: Optional[int] = None,
                           config: Optional[SkillLoopConfig] = None) -> Dict[str, Any]:
        """
        v4.0: 6-Skill LOOP 循环架构 — 以多次循环迭代完成创作
        每个Loop = 对作品的"一次完整审视"，深度递增。

        Args:
            max_loops: 最大循环次数，默认使用config.max_loops (默认3)
            config: SkillLoopConfig 配置对象，控制循环行为

        循环流程:
            Loop 0 SKELETON(深度0): 粗略世界观 + 角色卡 + 大纲骨架 + 钩子设计
            Loop 1 DETAIL  (深度1): 细化设定 + 关系网/弧线 + 完整大纲 + 文风 + 逐章写作
            Loop 2 POLISH  (深度2): 精修编辑 + 品质审查 + 调整后续章节
            Loop 3+ REFINE(深度3+): 视需要继续

        Returns:
            {"success": True, "loops": [...], "state": {...}}
        """
        config = config or SkillLoopConfig()
        if max_loops is not None:
            config.max_loops = max_loops
        self.state.total_loops = config.max_loops

        agents = self._ensure_agents()
        loop_results: List[Dict[str, Any]] = []

        await self._emit("loop_start", {
            "title": self.state.title,
            "chapter_count": self.state.chapter_count,
            "max_loops": config.max_loops,
            "novel_id": self.state.novel_id,
        })

        # ── 主循环 ──
        for loop_index in range(config.max_loops):
            self.state.current_loop = loop_index
            self.state.depth_level = loop_index
            depth_name = config.depth_for_loop(loop_index)
            temperature = config.temperature_for_loop(loop_index)

            # 可配置的跳过逻辑
            if (loop_index == 0 and not config.enable_skeleton_loop
                    or loop_index == 1 and not config.enable_detail_loop
                    or loop_index == 2 and not config.enable_polish_loop
                    or loop_index >= 3 and not config.enable_refine_loops):
                print(f"[Orchestrator] ⏭ Loop {loop_index} ({depth_name}) - 已跳过")
                loop_results.append({"loop": loop_index, "depth": depth_name, "skipped": True})
                self.state.loop_history.append({"loop": loop_index, "depth": depth_name, "skipped": True})
                continue

            print(f"\n{'='*60}")
            print(f"[Orchestrator] 🌀 Loop {loop_index} · {depth_name} (深度={loop_index}, 温度={temperature})")
            print(f"{'='*60}")
            await self._emit("loop_iteration", {"loop_index": loop_index, "depth": depth_name, "temperature": temperature})

            loop_output: Dict[str, Any] = {}

            try:
                # ========== Loop 0: SKELETON 骨架层 ==========
                if loop_index == 0:
                    # v6.0: S1 世界观 → S2 角色（串行执行，角色依赖世界观）
                    # 原并行模式导致角色生成时 world_info 为空，角色背景无法嵌入世界观
                    async def _do_world_skeleton():
                        try:
                            result = await agents["world"].process({
                                "title": self.state.title,
                                "theme": self.state.theme,
                                "tone": self.state.tone,
                                "platform": self.state.platform,
                                "depth_level": 0,
                                "loop_metadata": {"loop": 0, "depth": depth_name, "previous": None},
                                "title_analysis": self._title_analysis,
                            })
                            return result
                        except Exception as e:
                            print(f"  └ S1 世界观构建师 异常: {e}")
                            return {"success": False, "error": str(e)}

                    # S1 世界观构建师（先执行）
                    world_result = await _do_world_skeleton()
                    if world_result and world_result.get("success"):
                        self.state.world_settings = world_result.get("world_settings") or world_result
                        loop_output["world"] = "skeleton_created"
                    print(f"  └ S1 世界观构建师: {'OK' if (world_result and world_result.get('success')) else 'MOCK'}")

                    # S2 角色塑造师（后执行，注入已生成的世界观）
                    try:
                        char_result = await agents["character"].process({
                            "title": self.state.title,
                            "theme": self.state.theme,
                            "world_info": self._stringify(self.state.world_settings)[:500],  # v6.0 注入世界观
                            "platform": self.state.platform,
                            "depth_level": 0,
                            "loop_metadata": {"loop": 0, "depth": depth_name, "previous": None},
                            "title_analysis": self._title_analysis,
                        })
                    except Exception as e:
                        print(f"  └ S2 角色塑造师 异常: {e}")
                        char_result = {"success": False, "error": str(e)}

                    if char_result and char_result.get("success"):
                        self.state.characters = char_result.get("characters") or []
                        for ch in self.state.characters:
                            if isinstance(ch, dict) and ch.get("name"):
                                self.state_tracker.track_character(ch["name"], ch.get("personality", ""))
                        loop_output["characters"] = f"{len(self.state.characters)}_created"
                    print(f"  └ S2 角色塑造师: {'OK' if (char_result and char_result.get('success')) else 'MOCK'}")

                    # S3 开篇钩子师 - 黄金三章设计（依赖 S1+S2）
                    hook_result = await agents["opening_hook"].process({
                        "title": self.state.title,
                        "theme": self.state.theme,
                        "world_info": self._stringify(self.state.world_settings)[:300],
                        "character_info": self._stringify(self.state.characters)[:300],
                        "depth_level": 0,
                    })
                    if hook_result.get("success"):
                        self.state.opening_hook = hook_result
                        loop_output["opening_hook"] = "designed"
                    print(f"  └ S3 开篇钩子师: {'OK' if hook_result.get('success') else 'MOCK'}")

                    # S4 文风精修师 - 关键词汇(深度0)
                    style_result = await agents["style_editor"].process({
                        "content": "",
                        "theme": self.state.theme,
                        "platform": self.state.platform,
                        "mode": "style_only",
                        "depth_level": 0,
                    })
                    if style_result.get("success"):
                        self.state.style_guide = style_result.get("style_guide", {})
                        loop_output["style"] = "keywords_created"
                    print(f"  └ S4 文风精修师: {'OK' if style_result.get('success') else 'MOCK'}")

                    # S5 故事架构师 - 大纲骨架
                    outline_result = await agents["story_architect"].process({
                        "title": self.state.title,
                        "theme": self.state.theme,
                        "tone": self.state.tone,
                        "chapter_count": self.state.chapter_count,
                        "platform": self.state.platform,
                        "world_info": self._stringify(self.state.world_settings),
                        "characters": self._stringify(self.state.characters),
                        "depth_level": 0,
                        "opening_hook": self.state.opening_hook,
                    })
                    if outline_result.get("success"):
                        self.state.outline = outline_result.get("chapters", []) or []
                        loop_output["outline"] = f"skeleton_{len(self.state.outline)}_chapters"
                    print(f"  └ S5 故事架构师: {'OK' if outline_result.get('success') else 'MOCK'}")

                    # v6.0: 大纲骨架完成后生成故事走向（供Loop 1+角色代入使用）
                    if not self.state.story_direction:
                        await self._generate_story_direction()
                        if self.state.story_direction:
                            loop_output["story_direction"] = "generated"

                    loop_output["success"] = True
                    self.state.completed_stages.append(f"loop_{loop_index}_skeleton")

                # ========== Loop 1: DETAIL 细节层 ==========
                elif loop_index == 1:
                    # v5.3: S1 世界观构建师 + S2 角色塑造师 并行执行（无依赖）
                    async def _do_world_detail():
                        try:
                            result = await agents["world"].process({
                                "title": self.state.title,
                                "theme": self.state.theme,
                                "tone": self.state.tone,
                                "platform": self.state.platform,
                                "existing_world": self._stringify(self.state.world_settings)[:500],
                                "depth_level": 1,
                                "loop_metadata": {"loop": 1, "depth": depth_name,
                                                   "previous": self._stringify(self.state.world_settings)[:200]},
                                "title_analysis": self._title_analysis,
                            })
                            return result
                        except Exception as e:
                            print(f"  └ S1 世界观构建师 并行异常: {e}")
                            return {"success": False, "error": str(e)}

                    async def _do_char_detail():
                        try:
                            result = await agents["character"].process({
                                "title": self.state.title,
                                "theme": self.state.theme,
                                "world_info": self._stringify(self.state.world_settings)[:500],
                                "platform": self.state.platform,
                                "existing_characters": self._stringify(self.state.characters)[:400],
                                "depth_level": 1,
                                "loop_metadata": {"loop": 1, "depth": depth_name,
                                                   "previous": f"{len(self.state.characters)} chars from loop 0"},
                                "title_analysis": self._title_analysis,
                            })
                            return result
                        except Exception as e:
                            print(f"  └ S2 角色塑造师 并行异常: {e}")
                            return {"success": False, "error": str(e)}

                    world_task = asyncio.create_task(_do_world_detail())
                    char_task = asyncio.create_task(_do_char_detail())
                    world_result, char_result = await asyncio.gather(world_task, char_task)

                    if world_result and world_result.get("success"):
                        existing = self.state.world_settings or {}
                        if isinstance(existing, dict):
                            for k, v in (world_result.get("world_settings") or world_result).items():
                                if k not in existing or not existing[k]:
                                    existing[k] = v
                                else:
                                    existing[k] = str(existing[k]) + "\n[细化] " + str(v)
                        self.state.world_settings = existing
                        loop_output["world"] = "refined"
                    print(f"  └ S1 世界观构建师: 细化完成")

                    if char_result and char_result.get("success"):
                        new_chars = char_result.get("characters") or []
                        if new_chars:
                            for i, ch in enumerate(self.state.characters):
                                if i < len(new_chars) and isinstance(new_chars[i], dict):
                                    for key in ("relationships", "arc", "motivation"):
                                        if key in new_chars[i]:
                                            ch[key] = new_chars[i][key]
                            if len(new_chars) > len(self.state.characters):
                                self.state.characters.extend(new_chars[len(self.state.characters):])
                        loop_output["characters"] = "relationships_and_arcs_added"
                    print(f"  └ S2 角色塑造师: 关系网+弧线")

                    # S4 文风精修师 - 完整文风指南
                    style_result = await agents["style_editor"].process({
                        "content": "",
                        "theme": self.state.theme,
                        "platform": self.state.platform,
                        "mode": "style_only",
                        "depth_level": 1,
                        "previous_style": self._stringify(self.state.style_guide),
                    })
                    if style_result.get("success"):
                        self.state.style_guide = style_result.get("style_guide", self.state.style_guide or {})
                        loop_output["style"] = "full_guide_created"
                    print(f"  └ S4 文风精修师: 完整文风指南")

                    # S5 故事架构师 - 细化大纲
                    outline_result = await agents["story_architect"].process({
                        "title": self.state.title,
                        "theme": self.state.theme,
                        "tone": self.state.tone,
                        "chapter_count": self.state.chapter_count,
                        "platform": self.state.platform,
                        "world_info": self._stringify(self.state.world_settings),
                        "characters": self._stringify(self.state.characters),
                        "existing_outline": self._stringify(self.state.outline),
                        "story_direction": self.state.story_direction,
                        "depth_level": 1,
                        "opening_hook": self.state.opening_hook,
                        "title_analysis": self._title_analysis,
                    })
                    if outline_result.get("success"):
                        self.state.outline = outline_result.get("chapters", self.state.outline) or self.state.outline
                        loop_output["outline"] = f"detailed_{len(self.state.outline)}_chapters"
                    print(f"  └ S5 故事架构师: 细化大纲")

                    # S3 开篇钩子师 - 钩子重审(基于细化后的大纲)
                    if self.state.outline:
                        hook_result = await agents["opening_hook"].process({
                            "title": self.state.title,
                            "theme": self.state.theme,
                            "world_info": self._stringify(self.state.world_settings)[:300],
                            "character_info": self._stringify(self.state.characters)[:300],
                            "first_chapters": self._stringify(self.state.outline[:3])[:400],
                            "depth_level": 1,
                        })
                        if hook_result.get("success"):
                            self.state.opening_hook = hook_result
                            loop_output["opening_hook"] = "refined"
                        print(f"  └ S3 开篇钩子师: 钩子重审")

                    # S6 专业写手 - 逐章写作(所有章节)
                    if self.state.outline:
                        outline = self.state.outline
                        await self._emit("drafting_start", {"total": len(outline), "loop": loop_index})
                        existing_text = ""
                        for i, ch_outline in enumerate(outline):
                            await self._pause_event.wait()
                            chapter_idx = i + 1
                            ch_title = ch_outline.get("title", f"第{chapter_idx}章")
                            ch_summary = ch_outline.get("summary", "")

                            from .chapter_pipeline import ChapterPipeline
                            pipeline = ChapterPipeline(
                                agents=agents,
                                emit=self._emit,
                                state_tracker=self.state_tracker,
                                global_summary=self.global_summary,
                                pause_event=self._pause_event,
                                paused_ref=lambda: self._paused,
                                memory_engine=self._memory_engine,
                            )
                            try:
                                shared_context = {
                                    "title": self.state.title,
                                    "theme": self.state.theme,
                                    "world": self._stringify(self.state.world_settings),
                                    "characters": self._stringify(self.state.characters),
                                    "style": self._stringify(self.state.style_guide),
                                    "opening_hook": self._stringify(self.state.opening_hook),
                                    # v6.0: 注入角色列表（供角色代入使用）和故事走向
                                    "characters_list": self.state.characters,
                                    "story_direction": self.state.story_direction,
                                }
                                result = await pipeline.run(
                                    chapter_idx=chapter_idx,
                                    title=ch_title,
                                    summary=ch_summary,
                                    chapter_outline_ch=ch_outline,
                                    context=shared_context,
                                    existing_chapters_text=existing_text[-4000:],
                                    loop_metadata={"loop": loop_index, "depth": depth_name, "depth_level": 1},
                                    novel_id=self.state.novel_id,
                                )
                                chapter_data = {
                                    "title": result.title,
                                    "content": result.content,
                                    "summary": ch_summary,
                                    "word_count": result.word_count,
                                    "status": "draft_v1",
                                    "score": result.overall_score,
                                    "created_in_loop": loop_index,
                                    "_used_prompts": getattr(pipeline, '_used_prompts', {}),
                                }
                                if i < len(self.state.chapters):
                                    self.state.chapters[i] = chapter_data
                                else:
                                    self.state.chapters.append(chapter_data)
                                existing_text += f"\n\n第{chapter_idx}章 {ch_title}\n{result.content}"
                                self.global_summary.add_chapter_summary(
                                    chapter=chapter_idx,
                                    title=ch_title,
                                    summary=ch_summary,
                                    last_paragraph=result.content[-300:] if result.content else "",
                                    word_count=result.word_count,
                                    quality_score=result.overall_score,
                                )
                            except Exception as ce:
                                print(f"    ❌ 第{chapter_idx}章失败: {ce}")
                                self.state.errors.append(f"loop_{loop_index}_ch{chapter_idx}: {ce}")
                        loop_output["chapters"] = f"{len(self.state.chapters)}_written_v1"
                        print(f"  └ S6 专业写手: {len(self.state.chapters)} 章 v1 完成")

                        # v5.0: 自动保存本次 loop 中使用的优质 prompt
                        try:
                            all_used = {}
                            for ch_data in self.state.chapters:
                                used = ch_data.get("_used_prompts", {})
                                for at, pdata in used.items():
                                    if at not in all_used or pdata.get("quality_score", 0) > all_used.get(at, {}).get("quality_score", 0):
                                        all_used[at] = pdata
                            if all_used:
                                await self._save_prompts_auto(all_used, loop_index)
                        except Exception:
                            pass  # prompt 保存失败不影响主流程
                    loop_output["success"] = True
                    self.state.completed_stages.append(f"loop_{loop_index}_detail")

                # ========== Loop 2: POLISH 精修层 ==========
                elif loop_index == 2:
                    # S4 文风精修师 - 逐章精修
                    edited_count = 0
                    review_scores = []
                    for i, ch in enumerate(self.state.chapters):
                        await self._pause_event.wait()
                        if ch.get("content"):
                            try:
                                r = await agents["style_editor"].process({
                                    "content": ch["content"],
                                    "theme": self.state.theme,
                                    "platform": self.state.platform,
                                    "mode": "edit_only",
                                    "depth_level": 2,
                                    "chapter_index": i + 1,
                                    "loop_metadata": {"loop": loop_index, "depth": depth_name,
                                                       "previous_score": ch.get("score", 0)},
                                })
                                if r.get("success"):
                                    ch["content"] = r.get("edited_content", ch["content"])
                                    ch["status"] = "polished"
                                    ch["edited_in_loop"] = loop_index
                                    edited_count += 1
                                # 品质审查
                                r2 = await agents["style_editor"].process({
                                    "content": ch["content"],
                                    "theme": self.state.theme,
                                    "platform": self.state.platform,
                                    "mode": "review_only",
                                    "depth_level": 2,
                                    "chapter_index": i + 1,
                                })
                                if r2.get("success") and r2.get("review"):
                                    ch["review"] = r2["review"]
                                    ch["final_score"] = r2["review"].get("overall", 0)
                                    review_scores.append(ch["final_score"])
                            except Exception:
                                pass
                    loop_output["edited"] = f"{edited_count}_chapters"
                    if review_scores:
                        avg_score = round(sum(review_scores) / len(review_scores), 2)
                        loop_output["avg_quality_score"] = avg_score
                        print(f"  └ S4 文风精修师: 精修{edited_count}章, 平均{avg_score}分")
                    else:
                        print(f"  └ S4 文风精修师: 精修{edited_count}章")

                    # S5 故事架构师 - 根据审查结果调整
                    low_score_chapters = [ch for ch in self.state.chapters
                                           if ch.get("final_score", 0) < config.quality_threshold
                                           and ch.get("final_score", 0) > 0]
                    if low_score_chapters:
                        loop_output["low_score_chapters"] = len(low_score_chapters)
                        print(f"  └ S5 故事架构师: {len(low_score_chapters)}章低于{config.quality_threshold}分")

                    loop_output["success"] = True
                    self.state.completed_stages.append(f"loop_{loop_index}_polish")

                # ========== Loop 3+: REFINE 持续层 ==========
                else:
                    # 只处理低于品质阈值的章节或补写
                    need_rewrite = [
                        (i, ch) for i, ch in enumerate(self.state.chapters)
                        if ch.get("final_score", 0) and ch["final_score"] < config.quality_threshold
                    ]
                    # 也可能补写未完成章节
                    if len(self.state.chapters) < self.state.chapter_count:
                        missing = self.state.chapter_count - len(self.state.chapters)
                        print(f"  └ S6 专业写手: 补写{missing}章")
                    if need_rewrite:
                        for i, ch in need_rewrite:
                            await self._pause_event.wait()
                            try:
                                r = await agents["style_editor"].process({
                                    "content": ch.get("content", ""),
                                    "theme": self.state.theme,
                                    "platform": self.state.platform,
                                    "mode": "edit_only",
                                    "depth_level": loop_index,
                                    "chapter_index": i + 1,
                                    "loop_metadata": {"loop": loop_index, "depth": depth_name,
                                                       "previous_score": ch.get("final_score", 0)},
                                })
                                if r.get("success"):
                                    ch["content"] = r.get("edited_content", ch["content"])
                                    ch["status"] = f"refined_v{loop_index - 1}"
                            except Exception:
                                pass
                        loop_output["refined"] = f"{len(need_rewrite)}_chapters"
                    else:
                        loop_output["refined"] = "none_needed"
                    loop_output["success"] = True
                    self.state.completed_stages.append(f"loop_{loop_index}_refine")

                # ── 记录本次Loop产出 ──
                loop_output["loop"] = loop_index
                loop_output["depth"] = depth_name
                loop_output["chapters_count"] = len(self.state.chapters)
                loop_output["timestamp"] = time.time()
                loop_results.append(loop_output)
                self.state.loop_history.append(loop_output)
                await self._emit("loop_done", {"loop_index": loop_index, "depth": depth_name,
                                                "output_summary": {k: v for k, v in loop_output.items()
                                                                    if k not in ("timestamp",)}})
                await self._save_run_state()  # v5.3: 每个 loop 完成后持久化

            except Exception as e:
                print(f"[Orchestrator] ❌ Loop {loop_index} 异常: {e}")
                self.state.errors.append(f"loop_{loop_index}: {e}")
                loop_results.append({"loop": loop_index, "depth": depth_name, "error": str(e), "success": False})
                self.state.loop_history.append({"loop": loop_index, "depth": depth_name, "error": str(e)})

        # ── 循环完成 ──
        self.state.current_stage = "done"
        print(f"\n{'='*60}")
        print(f"[Orchestrator] ✅ LOOP 编排完成 ({len(loop_results)} loops, {len(self.state.chapters)} 章)")
        print(f"{'='*60}")

        await self._emit("loop_all_done", {
            "total_loops": len(loop_results),
            "chapters_count": len(self.state.chapters),
            "state": self.state.to_dict(),
        })

        return {
            "success": True,
            "mode": "loop",
            "total_loops": len(loop_results),
            "loops": loop_results,
            "chapters_count": len(self.state.chapters),
            "state": self.state.to_dict(),
        }

    # ────────── 辅助方法 ──────────
    @staticmethod
    def _stringify(value: Any) -> str:
        """将世界观/角色/风格等结构化数据转为供管道注入 prompt 的纯文本"""
        if not value:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(value)

    def _mark_done(self, stage: str):
        if stage not in self.state.completed_stages:
            self.state.completed_stages.append(stage)

    async def _emit(self, event: str, data: Dict[str, Any]):
        """发送事件到 SSE 队列"""
        self._task_log.append({"event": event, "data": data, "time": time.time()})
        if self._progress_callback:
            try:
                await self._progress_callback(event, data)
            except Exception as e:
                print(f"[Orchestrator] ⚠️ 推送事件失败: {e}")
