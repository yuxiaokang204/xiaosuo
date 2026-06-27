"""
规划器核心 (NovelPlannerAgent) — 全局工作流计划引擎

职责:
- 根据小说配置创建全局工作流计划
- 决定下一步执行哪个阶段
- 质量门控，判断章节是否达标

工作流状态机:
    planning → worldbuilding → characters → style → outlining →
      [draft_loop] → drafting → editing → review → [done | back_to_drafting]
"""
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from ..llm.gateway import LLMGateway, get_gateway
from .event_bus import EventBus
from .quality_gate import QualityGate, QualityScore


# ── 工作流阶段枚举 ──

class WorkflowStage(str, Enum):
    """工作流阶段"""
    PLANNING = "planning"
    WORLD_BUILDING = "worldbuilding"
    CHARACTERS = "characters"
    STYLE = "style"
    OUTLINING = "outlining"
    DRAFT_LOOP = "draft_loop"
    DRAFTING = "drafting"
    EDITING = "editing"
    REVIEW = "review"
    DONE = "done"
    BACK_TO_DRAFTING = "back_to_drafting"


# ── 计划数据结构 ──

@dataclass
class StagePlan:
    """单个阶段的计划"""
    stage: WorkflowStage
    name: str
    order: int
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | running | completed | skipped | failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value if isinstance(self.stage, WorkflowStage) else self.stage,
            "name": self.name,
            "order": self.order,
            "dependencies": self.dependencies,
            "config": self.config,
            "status": self.status,
        }


@dataclass
class NovelPlan:
    """全局小说创作计划"""
    novel_id: str
    title: str
    theme: str
    tone: str = "史诗"
    chapter_count: int = 10
    platform: str = "番茄"
    stages: List[StagePlan] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    current_stage: str = "planning"
    status: str = "planning"  # planning | running | paused | completed | failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "novel_id": self.novel_id,
            "title": self.title,
            "theme": self.theme,
            "tone": self.tone,
            "chapter_count": self.chapter_count,
            "platform": self.platform,
            "stages": [s.to_dict() for s in self.stages],
            "current_stage": self.current_stage,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class NovelPlannerAgent:
    """
    小说规划器 — 创建和管理全局工作流计划

    工作流顺序:
        planning → worldbuilding → characters → style → outlining → drafting → editing → review → done

    每个阶段完成后，可决定是否需要回到之前的阶段（如 review 不通过则 back_to_drafting）

    使用示例:
        planner = NovelPlannerAgent(
            event_bus=event_bus,
            quality_gate=quality_gate,
            gateway=llm_gateway,
        )
        plan = planner.create_plan({
            "title": "青云界传说",
            "theme": "穿越异世修真",
            "chapter_count": 20,
        })
        next_stage = planner.decide_next_stage(plan.current_stage, plan.status)
    """

    # 默认工作流阶段顺序
    DEFAULT_STAGES = [
        StagePlan(
            stage=WorkflowStage.PLANNING,
            name="初始规划",
            order=0,
        ),
        StagePlan(
            stage=WorkflowStage.WORLD_BUILDING,
            name="世界观构建",
            order=1,
            dependencies=["planning"],
        ),
        StagePlan(
            stage=WorkflowStage.CHARACTERS,
            name="角色设计",
            order=2,
            dependencies=["worldbuilding"],
        ),
        StagePlan(
            stage=WorkflowStage.STYLE,
            name="文风设定",
            order=3,
            dependencies=["characters"],
        ),
        StagePlan(
            stage=WorkflowStage.OUTLINING,
            name="大纲设计",
            order=4,
            dependencies=["worldbuilding", "characters", "style"],
        ),
        StagePlan(
            stage=WorkflowStage.DRAFT_LOOP,
            name="写作循环",
            order=5,
            dependencies=["outlining"],
        ),
        StagePlan(
            stage=WorkflowStage.DRAFTING,
            name="章节写作",
            order=6,
            dependencies=["draft_loop"],
        ),
        StagePlan(
            stage=WorkflowStage.EDITING,
            name="文风精修",
            order=7,
            dependencies=["drafting"],
        ),
        StagePlan(
            stage=WorkflowStage.REVIEW,
            name="品质审查",
            order=8,
            dependencies=["editing"],
        ),
        StagePlan(
            stage=WorkflowStage.DONE,
            name="完成",
            order=9,
            dependencies=["review"],
        ),
    ]

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        quality_gate: Optional[QualityGate] = None,
        gateway: Optional[LLMGateway] = None,
        enable_llm_planning: bool = True,
    ):
        """
        Args:
            event_bus: 事件总线实例
            quality_gate: 质量门控实例
            gateway: LLM 网关实例
            enable_llm_planning: 是否启用 LLM 辅助规划（否则使用默认规则规划）
        """
        self.event_bus = event_bus or EventBus()
        self.quality_gate = quality_gate or QualityGate()
        self.gateway = gateway or get_gateway()
        self.enable_llm_planning = enable_llm_planning
        self._plans: Dict[str, NovelPlan] = {}

    def create_plan(
        self,
        novel_config: Dict[str, Any],
        plan_id: Optional[str] = None,
    ) -> NovelPlan:
        """
        根据小说配置创建全局工作流计划

        Args:
            novel_config: 小说配置，包含 title, theme, chapter_count 等
            plan_id: 可选的计划 ID

        Returns:
            NovelPlan 计划对象
        """
        novel_id = plan_id or novel_config.get("novel_id", f"plan_{int(time.time())}")
        title = novel_config.get("title", "未命名小说")
        theme = novel_config.get("theme", "")
        tone = novel_config.get("tone", "史诗")
        chapter_count = novel_config.get("chapter_count", 10)
        platform = novel_config.get("platform", "番茄")

        # 构建计划
        stages = []
        for sp in self.DEFAULT_STAGES:
            stage_copy = StagePlan(
                stage=sp.stage,
                name=sp.name,
                order=sp.order,
                dependencies=list(sp.dependencies),
                config=sp.config.copy(),
            )

            # 为写作阶段注入章节数配置
            if sp.stage in (WorkflowStage.DRAFT_LOOP, WorkflowStage.DRAFTING):
                stage_copy.config["chapter_count"] = chapter_count
                stage_copy.config["chapters_per_loop"] = novel_config.get("chapters_per_loop", 5)
                stage_copy.config["enable_polish"] = novel_config.get("enable_polish", True)

            stages.append(stage_copy)

        plan = NovelPlan(
            novel_id=novel_id,
            title=title,
            theme=theme,
            tone=tone,
            chapter_count=chapter_count,
            platform=platform,
            stages=stages,
        )

        self._plans[novel_id] = plan

        # 发布计划创建事件
        self.event_bus.publish("plan.created", {
            "novel_id": novel_id,
            "title": title,
            "chapter_count": chapter_count,
        })

        return plan

    def decide_next_stage(
        self,
        current_stage: str,
        plan_status: str = "planning",
        chapter_scores: Optional[List[float]] = None,
    ) -> str:
        """
        根据当前状态决定下一步执行哪个阶段

        Args:
            current_stage: 当前阶段
            plan_status: 计划状态
            chapter_scores: 已完成章节的评分列表（用于 review 阶段决策）

        Returns:
            下一阶段名称
        """
        if plan_status in ("completed", "done"):
            return "done"

        if plan_status == "failed":
            return "planning"  # 失败后回到规划阶段

        # 状态机决策逻辑
        stage_transitions = {
            "planning": "worldbuilding",
            "worldbuilding": "characters",
            "characters": "style",
            "style": "outlining",
            "outlining": "draft_loop",
            "draft_loop": "drafting",
            "drafting": "editing",
            "editing": "review",
        }

        if current_stage in stage_transitions:
            next_stage = stage_transitions[current_stage]

            # review 阶段特殊处理：根据章节评分决定是否回退
            if current_stage == "review" and chapter_scores:
                avg_score = sum(chapter_scores) / len(chapter_scores)
                if avg_score < self.quality_gate.threshold:
                    return "back_to_drafting"

            return next_stage

        if current_stage == "back_to_drafting":
            return "drafting"

        return "done"

    async def quality_gate_check(
        self,
        chapter_content: str,
        outline: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        world_settings: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = None,
    ) -> QualityScore:
        """
        质量门控检查，判断章节是否达标

        Args:
            chapter_content: 章节正文内容
            outline: 章节大纲
            characters: 角色列表
            world_settings: 世界观设定
            threshold: 可选的质量阈值

        Returns:
            QualityScore 评分结果
        """
        if threshold:
            self.quality_gate.set_threshold(threshold)

        result = await self.quality_gate.check_quality(
            chapter_content=chapter_content,
            outline=outline,
            characters=characters,
            world_settings=world_settings,
        )

        # 发布质量检查事件
        await self.event_bus.publish("quality.check", result.to_dict())

        return result

    async def update_stage_status(
        self,
        novel_id: str,
        stage: str,
        status: str,
        error: Optional[str] = None,
    ) -> bool:
        """
        更新阶段状态

        Args:
            novel_id: 小说 ID
            stage: 阶段名称
            status: 新状态 (running | completed | failed)
            error: 可选的错误信息

        Returns:
            是否更新成功
        """
        plan = self._plans.get(novel_id)
        if not plan:
            print(f"[NovelPlanner] ⚠️ 未找到计划: {novel_id}")
            return False

        for sp in plan.stages:
            stage_val = sp.stage.value if isinstance(sp.stage, WorkflowStage) else sp.stage
            if stage_val == stage:
                sp.status = status
                plan.updated_at = time.time()
                plan.current_stage = stage

                if status == "completed":
                    await self.event_bus.publish("stage.completed", {
                        "novel_id": novel_id,
                        "stage": stage,
                    })
                elif status == "failed":
                    await self.event_bus.publish("stage.failed", {
                        "novel_id": novel_id,
                        "stage": stage,
                        "error": error,
                    })

                return True

        return False

    def get_plan(self, novel_id: str) -> Optional[NovelPlan]:
        """获取计划"""
        return self._plans.get(novel_id)

    def get_all_plans(self) -> Dict[str, NovelPlan]:
        """获取所有计划"""
        return self._plans

    def delete_plan(self, novel_id: str) -> bool:
        """删除计划"""
        if novel_id in self._plans:
            del self._plans[novel_id]
            self.event_bus.publish("plan.deleted", {"novel_id": novel_id})
            return True
        return False

    def get_plan_progress(self, novel_id: str) -> Dict[str, Any]:
        """
        获取计划进度

        Returns:
            {
                "novel_id": "...",
                "title": "...",
                "current_stage": "...",
                "completed_stages": [...],
                "total_stages": 10,
                "completed_count": 3,
                "progress_pct": 30.0,
            }
        """
        plan = self._plans.get(novel_id)
        if not plan:
            return {}

        completed = [s for s in plan.stages if s.status == "completed"]
        total = len(plan.stages)
        completed_count = len(completed)

        return {
            "novel_id": plan.novel_id,
            "title": plan.title,
            "current_stage": plan.current_stage,
            "completed_stages": [s.stage.value for s in completed],
            "total_stages": total,
            "completed_count": completed_count,
            "progress_pct": round(completed_count / total * 100, 1) if total > 0 else 0,
        }

    def get_config(self) -> Dict[str, Any]:
        """获取规划器配置"""
        return {
            "enable_llm_planning": self.enable_llm_planning,
            "quality_gate_threshold": self.quality_gate.threshold,
            "stages_count": len(self.DEFAULT_STAGES),
        }
