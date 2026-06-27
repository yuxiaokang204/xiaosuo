"""
工作流引擎 (WorkflowEngine) — LOOP 循环执行引擎

功能:
- 执行 LOOP 循环工作流
- Loop 0: SKELETON（骨架）- 并行执行 OutlineAgent + WorldAgent + CharacterAgent
- Loop 1: DETAIL（血肉）- 逐章生成，每5章执行一次 POLISH
- Loop 2: REFINE（精修）- 全局优化

与 planner.py 的关系:
- NovelPlannerAgent 创建计划和阶段决策
- WorkflowEngine 负责实际执行循环和阶段
"""
import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from .event_bus import EventBus
from .planner import NovelPlannerAgent, NovelPlan, WorkflowStage
from .quality_gate import QualityGate, QualityScore


@dataclass
class LoopConfig:
    """LOOP 循环配置"""
    max_loops: int = 3
    chapters_per_draft_loop: int = 5
    quality_threshold: float = 7.0
    enable_skeleton_loop: bool = True
    enable_detail_loop: bool = True
    enable_refine_loop: bool = True
    enable_polish_every_n_chapters: int = 5  # 每 N 章执行一次 POLISH
    temperature_profile: str = "gradient"  # gradient | high | low

    def depth_for_loop(self, loop_index: int) -> str:
        """返回循环的深度层名称"""
        if loop_index == 0:
            return "SKELETON"
        elif loop_index == 1:
            return "DETAIL"
        elif loop_index == 2:
            return "POLISH"
        else:
            return "REFINE"

    def temperature_for_loop(self, loop_index: int) -> float:
        """按循环序号返回推荐温度"""
        if self.temperature_profile == "high":
            return 0.85
        elif self.temperature_profile == "low":
            return 0.4
        else:  # gradient
            base = 0.85
            decay = loop_index * 0.15
            return max(0.3, round(base - decay, 2))


@dataclass
class LoopResult:
    """单个循环的执行结果"""
    loop_index: int
    depth: str
    success: bool = False
    chapters_written: int = 0
    quality_scores: List[float] = field(default_factory=list)
    output_summary: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loop_index": self.loop_index,
            "depth": self.depth,
            "success": self.success,
            "chapters_written": self.chapters_written,
            "avg_quality_score": round(sum(self.quality_scores) / len(self.quality_scores), 2) if self.quality_scores else 0,
            "output_summary": self.output_summary,
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class WorkflowEngine:
    """
    工作流引擎 — 执行 LOOP 循环工作流

    循环架构:
        Loop 0 (SKELETON): 并行执行 OutlineAgent + WorldAgent + CharacterAgent
        Loop 1 (DETAIL): 逐章生成，每5章执行一次 POLISH
        Loop 2 (REFINE): 全局优化

    使用示例:
        engine = WorkflowEngine(
            planner=planner,
            quality_gate=quality_gate,
            event_bus=event_bus,
        )
        result = await engine.run_loop(
            novel_id="xxx",
            loop_config=LoopConfig(),
            agents={...},  # Agent 实例字典
        )
    """

    def __init__(
        self,
        planner: Optional[NovelPlannerAgent] = None,
        quality_gate: Optional[QualityGate] = None,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Args:
            planner: 规划器实例
            quality_gate: 质量门控实例
            event_bus: 事件总线实例
        """
        self.planner = planner or NovelPlannerAgent()
        self.quality_gate = quality_gate or QualityGate()
        self.event_bus = event_bus or self.planner.event_bus
        self._loop_results: Dict[str, List[LoopResult]] = {}
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self._progress_callback = callback

    async def run_loop(
        self,
        novel_id: str,
        loop_config: Optional[LoopConfig] = None,
        agents: Optional[Dict[str, Any]] = None,
        novel_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行 LOOP 循环

        Args:
            novel_id: 小说 ID
            loop_config: 循环配置
            agents: Agent 实例字典，如 {"world": WorldAgent(), "character": CharacterAgent()}
            novel_data: 小说数据（包含 outline, characters, world_settings 等）

        Returns:
            {"success": True, "loops": [...], "total_chapters": N}
        """
        loop_config = loop_config or LoopConfig()
        novel_data = novel_data or {}

        print(f"\n{'='*60}")
        print(f"[WorkflowEngine] 🚀 开始执行 LOOP 循环 (novel_id={novel_id})")
        print(f"{'='*60}")

        # 发布循环开始事件
        await self.event_bus.publish("loop.start", {
            "novel_id": novel_id,
            "max_loops": loop_config.max_loops,
        })

        loop_results: List[LoopResult] = []
        all_chapters: List[Dict[str, Any]] = novel_data.get("chapters", [])

        for loop_index in range(loop_config.max_loops):
            depth_name = loop_config.depth_for_loop(loop_index)
            temperature = loop_config.temperature_for_loop(loop_index)

            # 检查是否跳过当前循环
            if (loop_index == 0 and not loop_config.enable_skeleton_loop
                    or loop_index == 1 and not loop_config.enable_detail_loop
                    or loop_index >= 2 and not loop_config.enable_refine_loop):
                print(f"[WorkflowEngine] ⏭ Loop {loop_index} ({depth_name}) - 已跳过")
                loop_results.append(LoopResult(
                    loop_index=loop_index,
                    depth=depth_name,
                    success=True,
                    output_summary={"skipped": True},
                ))
                continue

            loop_start_time = time.time()
            print(f"\n[WorkflowEngine] 🌀 Loop {loop_index} · {depth_name} "
                  f"(温度={temperature})")

            try:
                if loop_index == 0:
                    loop_result = await self._run_skeleton_loop(
                        novel_id=novel_id,
                        loop_config=loop_config,
                        agents=agents or {},
                        novel_data=novel_data,
                        temperature=temperature,
                    )
                elif loop_index == 1:
                    loop_result = await self._run_detail_loop(
                        novel_id=novel_id,
                        loop_config=loop_config,
                        agents=agents or {},
                        novel_data=novel_data,
                        temperature=temperature,
                    )
                else:
                    loop_result = await self._run_refine_loop(
                        novel_id=novel_id,
                        loop_config=loop_config,
                        agents=agents or {},
                        novel_data=novel_data,
                        temperature=temperature,
                    )

                loop_result.duration_seconds = time.time() - loop_start_time
                loop_results.append(loop_result)
                all_chapters = novel_data.get("chapters", all_chapters)

                await self.event_bus.publish("loop.done", {
                    "novel_id": novel_id,
                    "loop_index": loop_index,
                    "depth": depth_name,
                    "success": loop_result.success,
                })

            except Exception as e:
                print(f"[WorkflowEngine] ❌ Loop {loop_index} 异常: {e}")
                loop_results.append(LoopResult(
                    loop_index=loop_index,
                    depth=depth_name,
                    success=False,
                    error=str(e),
                ))
                await self.event_bus.publish("loop.error", {
                    "novel_id": novel_id,
                    "loop_index": loop_index,
                    "error": str(e),
                })

        # 发布循环完成事件
        await self.event_bus.publish("loop.all_done", {
            "novel_id": novel_id,
            "total_loops": len(loop_results),
            "total_chapters": len(all_chapters),
        })

        # 保存结果
        self._loop_results[novel_id] = loop_results

        # 更新规划器状态
        self.planner.update_stage_status(novel_id, "draft_loop", "completed")
        self.planner.update_stage_status(novel_id, "drafting", "completed")

        return {
            "success": True,
            "novel_id": novel_id,
            "total_loops": len(loop_results),
            "loops": [r.to_dict() for r in loop_results],
            "total_chapters": len(all_chapters),
        }

    async def _run_skeleton_loop(
        self,
        novel_id: str,
        loop_config: LoopConfig,
        agents: Dict[str, Any],
        novel_data: Dict[str, Any],
        temperature: float,
    ) -> LoopResult:
        """
        Loop 0: SKELETON（骨架）- 并行执行 OutlineAgent + WorldAgent + CharacterAgent

        并行任务:
        - WorldAgent: 构建世界观
        - CharacterAgent: 设计角色
        - (可选) OutlineAgent: 创建大纲骨架
        """
        print(f"[WorkflowEngine] 📐 SKELETON 循环开始")

        world_settings = novel_data.get("world_settings", {})
        characters = novel_data.get("characters", [])
        outline = novel_data.get("outline", [])

        tasks = {}

        # 世界观构建（如果尚未完成）
        world_agent = agents.get("world")
        if world_agent and not world_settings:
            tasks["world"] = self._execute_agent(
                agent=world_agent,
                agent_name="WorldAgent",
                context={
                    "theme": novel_data.get("theme", ""),
                    "title": novel_data.get("title", ""),
                    "depth_level": 0,
                    "temperature": temperature,
                },
            )

        # 角色设计（如果尚未完成）
        character_agent = agents.get("character")
        if character_agent and not characters:
            tasks["character"] = self._execute_agent(
                agent=character_agent,
                agent_name="CharacterAgent",
                context={
                    "theme": novel_data.get("theme", ""),
                    "title": novel_data.get("title", ""),
                    "world_info": json.dumps(world_settings, ensure_ascii=False) if world_settings else "",
                    "depth_level": 0,
                    "temperature": temperature,
                },
            )

        # 大纲骨架（如果尚未完成）
        outline_agent = agents.get("outline")
        if outline_agent and not outline:
            tasks["outline"] = self._execute_agent(
                agent=outline_agent,
                agent_name="OutlineAgent",
                context={
                    "theme": novel_data.get("theme", ""),
                    "chapter_count": novel_data.get("chapter_count", 10),
                    "world_info": json.dumps(world_settings, ensure_ascii=False) if world_settings else "",
                    "characters": json.dumps(characters, ensure_ascii=False) if characters else "",
                    "depth_level": 0,
                    "temperature": temperature,
                },
            )

        # 并行执行所有任务
        if tasks:
            results = await asyncio.gather(
                *[task for task in tasks.values()],
                return_exceptions=True,
            )

            for key, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    print(f"[WorkflowEngine] ⚠️ {key} 执行失败: {result}")
                elif isinstance(result, dict) and result.get("success"):
                    if key == "world":
                        world_settings = result.get("world_settings", result)
                        novel_data["world_settings"] = world_settings
                        print(f"[WorkflowEngine] ✅ WorldAgent 完成")
                    elif key == "character":
                        characters = result.get("characters", [])
                        novel_data["characters"] = characters
                        print(f"[WorkflowEngine] ✅ CharacterAgent 完成, {len(characters)} 个角色")
                    elif key == "outline":
                        outline = result.get("chapters", [])
                        novel_data["outline"] = outline
                        print(f"[WorkflowEngine] ✅ OutlineAgent 完成, {len(outline)} 章大纲")
        else:
            print(f"[WorkflowEngine] ℹ️ SKELETON 阶段数据已存在，跳过")

        novel_data["world_settings"] = world_settings
        novel_data["characters"] = characters
        novel_data["outline"] = outline

        return LoopResult(
            loop_index=0,
            depth="SKELETON",
            success=True,
            output_summary={
                "world": "created" if world_settings else "skipped",
                "characters": f"{len(characters)}_created" if characters else "skipped",
                "outline": f"{len(outline)}_chapters" if outline else "skipped",
            },
        )

    async def _run_detail_loop(
        self,
        novel_id: str,
        loop_config: LoopConfig,
        agents: Dict[str, Any],
        novel_data: Dict[str, Any],
        temperature: float,
    ) -> LoopResult:
        """
        Loop 1: DETAIL（血肉）- 逐章生成，每 N 章执行一次 POLISH

        工作流程:
        1. 细化世界观和角色
        2. 逐章生成内容
        3. 每 N 章执行质量检查和 POLISH
        """
        print(f"[WorkflowEngine] 📝 DETAIL 循环开始")

        outline = novel_data.get("outline", [])
        characters = novel_data.get("characters", [])
        world_settings = novel_data.get("world_settings", {})
        chapters = novel_data.get("chapters", [])
        draft_agent = agents.get("draft")

        if not outline or not draft_agent:
            print(f"[WorkflowEngine] ⚠️ 缺少大纲或写手 Agent，跳过 DETAIL 循环")
            return LoopResult(
                loop_index=1,
                depth="DETAIL",
                success=False,
                error="缺少 outline 或 draft agent",
            )

        quality_scores: List[float] = []
        chapters_written = 0
        polish_interval = loop_config.enable_polish_every_n_chapters

        for i, ch_outline in enumerate(outline):
            chapter_idx = i + 1
            ch_title = ch_outline.get("title", f"第{chapter_idx}章")
            ch_summary = ch_outline.get("summary", "")

            print(f"  └ 生成第{chapter_idx}章: {ch_title}")

            # 发布章节开始事件
            await self.event_bus.publish("chapter.start", {
                "novel_id": novel_id,
                "index": chapter_idx,
                "title": ch_title,
                "total": len(outline),
            })

            try:
                # 执行章节生成
                result = await self._execute_agent(
                    agent=draft_agent,
                    agent_name="DraftAgent",
                    context={
                        "chapter_idx": chapter_idx,
                        "title": ch_title,
                        "summary": ch_summary,
                        "outline": json.dumps(outline[:max(0, i-2)], ensure_ascii=False),
                        "characters": json.dumps(characters, ensure_ascii=False),
                        "world_info": json.dumps(world_settings, ensure_ascii=False),
                        "temperature": temperature,
                    },
                )

                if isinstance(result, dict) and result.get("success"):
                    chapter_data = {
                        "title": ch_title,
                        "content": result.get("content", ""),
                        "summary": ch_summary,
                        "status": "draft",
                        "score": result.get("overall_score", 0),
                    }
                    chapters.append(chapter_data)
                    novel_data["chapters"] = chapters
                    chapters_written += 1

                    # 检查质量
                    score = result.get("overall_score", 0)
                    quality_scores.append(score)

                    await self.event_bus.publish("chapter.done", {
                        "novel_id": novel_id,
                        "index": chapter_idx,
                        "title": ch_title,
                        "score": score,
                    })

                else:
                    print(f"[WorkflowEngine] ⚠️ 第{chapter_idx}章生成失败")

            except Exception as e:
                print(f"[WorkflowEngine] ❌ 第{chapter_idx}章生成异常: {e}")
                novel_data.setdefault("errors", []).append(f"chapter_{chapter_idx}: {e}")

            # 每 N 章执行 POLISH
            if polish_interval and chapter_idx % polish_interval == 0:
                print(f"  └ [{chapter_idx}章] 执行 POLISH...")
                await self._polish_chapters(
                    novel_id=novel_id,
                    chapters=chapters[-polish_interval:],
                    agents=agents,
                    quality_scores=quality_scores[-polish_interval:],
                )

        return LoopResult(
            loop_index=1,
            depth="DETAIL",
            success=True,
            chapters_written=chapters_written,
            quality_scores=quality_scores,
            output_summary={
                "chapters_written": chapters_written,
                "avg_score": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0,
            },
        )

    async def _run_refine_loop(
        self,
        novel_id: str,
        loop_config: LoopConfig,
        agents: Dict[str, Any],
        novel_data: Dict[str, Any],
        temperature: float,
    ) -> LoopResult:
        """
        Loop 2+: REFINE（精修）- 全局优化

        工作流程:
        1. 检查所有章节质量
        2. 对低分章节进行精修
        3. 全局一致性检查
        """
        print(f"[WorkflowEngine] ✨ REFINE 循环开始")

        chapters = novel_data.get("chapters", [])
        edit_agent = agents.get("edit")

        if not chapters:
            print(f"[WorkflowEngine] ⚠️ 没有章节可精修，跳过 REFINE 循环")
            return LoopResult(
                loop_index=2,
                depth="REFINE",
                success=False,
                error="没有章节可精修",
            )

        quality_scores: List[float] = []
        refined_count = 0

        for i, chapter in enumerate(chapters):
            content = chapter.get("content", "")
            if not content:
                continue

            # 检查质量
            score_result = await self.quality_gate.check_quality(
                chapter_content=content,
                outline=chapter,
                characters=novel_data.get("characters", []),
                world_settings=novel_data.get("world_settings", {}),
            )
            quality_scores.append(score_result.overall_score)

            # 如果低于阈值，进行精修
            if not score_result.passed and edit_agent:
                print(f"  └ 精修章节: {chapter.get('title', '未知')} "
                      f"(评分: {score_result.overall_score})")

                try:
                    result = await self._execute_agent(
                        agent=edit_agent,
                        agent_name="EditAgent",
                        context={
                            "content": content,
                            "suggestions": score_result.suggestions,
                            "temperature": temperature,
                        },
                    )

                    if isinstance(result, dict) and result.get("success"):
                        chapter["content"] = result.get("edited_content", content)
                        chapter["status"] = "refined"
                        refined_count += 1
                except Exception as e:
                    print(f"[WorkflowEngine] ⚠️ 精修失败: {e}")

        novel_data["chapters"] = chapters

        return LoopResult(
            loop_index=2,
            depth="REFINE",
            success=True,
            quality_scores=quality_scores,
            output_summary={
                "chapters_refined": refined_count,
                "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0,
            },
        )

    async def _polish_chapters(
        self,
        novel_id: str,
        chapters: List[Dict[str, Any]],
        agents: Dict[str, Any],
        quality_scores: List[float],
    ):
        """对一批章节执行 POLISH（质量检查 + 精修）"""
        avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        print(f"  └ └ 批次平均分: {avg_score:.2f}")

        if avg_score < self.quality_gate.threshold:
            edit_agent = agents.get("edit")
            if edit_agent:
                for chapter in chapters:
                    content = chapter.get("content", "")
                    if content:
                        try:
                            result = await self._execute_agent(
                                agent=edit_agent,
                                agent_name="EditAgent",
                                context={
                                    "content": content,
                                    "mode": "polish",
                                },
                            )
                            if isinstance(result, dict) and result.get("success"):
                                chapter["content"] = result.get("edited_content", content)
                                chapter["status"] = "polished"
                        except Exception as e:
                            print(f"[WorkflowEngine] ⚠️ POLISH 失败: {e}")

    async def _execute_agent(
        self,
        agent: Any,
        agent_name: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行单个 Agent 并捕获异常"""
        try:
            if asyncio.iscoroutinefunction(agent.process):
                result = await agent.process(context)
            else:
                result = agent.process(context)
            return result
        except Exception as e:
            print(f"[WorkflowEngine] ⚠️ {agent_name} 执行异常: {e}")
            return {"success": False, "error": str(e)}

    def get_loop_results(self, novel_id: str) -> List[LoopResult]:
        """获取循环结果"""
        return self._loop_results.get(novel_id, [])

    def get_all_loop_results(self) -> Dict[str, List[LoopResult]]:
        """获取所有循环结果"""
        return self._loop_results

    def get_stats(self) -> Dict[str, Any]:
        """获取工作流引擎统计"""
        total_runs = sum(len(v) for v in self._loop_results.values())
        return {
            "novels_processed": len(self._loop_results),
            "total_loop_runs": total_runs,
            "novel_ids": list(self._loop_results.keys()),
        }
