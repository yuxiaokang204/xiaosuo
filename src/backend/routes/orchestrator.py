"""
编排器路由 - 小说创作全流程控制
=================================

v2.0 L1 规划层集成:
- 保留所有原有 API 端点（向后兼容）
- 使用 NovelPlannerAgent 替代旧的 OrchestratorState
- 使用 WorkflowEngine 替代旧的 run_all_loop()
- 支持 SSE 事件推送（通过 EventBus）
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import time
import asyncio
import json
import os

router = APIRouter(tags=["编排"])

# ── 全局状态 ──

# 旧的编排器实例（保留兼容）
_active_orchestrators: Dict[str, Any] = {}
_orchestrator_last_seen: Dict[str, float] = {}
_ORCH_TTL_SECONDS = 2 * 3600
_ORCH_MAX = 50

# 新的工作流引擎（v2.0 L1 规划层）
from ..core.workflow import WorkflowEngine, LoopConfig
from ..core.planner import NovelPlannerAgent
from ..core.event_bus import get_event_bus, EventType

_workflow_engine = WorkflowEngine(planner=NovelPlannerAgent())
_event_bus = get_event_bus()


class OrchestratorRequest(BaseModel):
    title: str = Field(..., min_length=1, description="小说标题")
    theme: str = Field(..., min_length=1, description="主题")
    tone: str = "史诗"
    chapter_count: int = 10
    novel_id: Optional[str] = None


class StageRequest(BaseModel):
    novel_id: str = Field(..., description="编排器 ID")
    stage: str = Field(..., description="要执行的阶段: worldbuilding/characters/style/outlining/drafting/editing/review")


def _touch_orchestrator(novel_id: str):
    """记录/刷新编排器的最近访问时间。"""
    _orchestrator_last_seen[novel_id] = time.time()


def _cleanup_orchestrators():
    """清理过期或超量的编排器，避免长跑进程内存无限增长。"""
    now = time.time()
    expired = [
        nid for nid, ts in list(_orchestrator_last_seen.items())
        if now - ts > _ORCH_TTL_SECONDS
    ]
    for nid in expired:
        _active_orchestrators.pop(nid, None)
        _orchestrator_last_seen.pop(nid, None)
    if len(_active_orchestrators) > _ORCH_MAX:
        ordered = sorted(
            _active_orchestrators.keys(),
            key=lambda nid: _orchestrator_last_seen.get(nid, 0.0),
        )
        for nid in ordered[: len(_active_orchestrators) - _ORCH_MAX]:
            _active_orchestrators.pop(nid, None)
            _orchestrator_last_seen.pop(nid, None)


async def _save_novel_to_db(orch):
    """将编排器结果保存到 SQLite 数据库"""
    from .db.database import AsyncSessionLocal
    from .db.models import NovelDB, VolumeDB, ChapterDB, CharacterDB, WorldSettingDB, StyleGuideDB
    import uuid
    from datetime import datetime

    async with AsyncSessionLocal() as session:
        novel_id = orch.state.novel_id

        novel = await session.get(NovelDB, novel_id)
        if not novel:
            novel = NovelDB(
                id=novel_id,
                title=orch.state.title,
                genre=orch.state.theme,
                status="completed",
                current_word_count=sum(len(ch.get("content", "")) for ch in orch.state.chapters),
                created_at=datetime.now(),
            )
            session.add(novel)
        else:
            novel.status = "completed"
            novel.current_word_count = sum(len(ch.get("content", "")) for ch in orch.state.chapters)
            novel.updated_at = datetime.now()

        volume_id = f"{novel_id}_vol1"
        volume = await session.get(VolumeDB, volume_id)
        if not volume:
            volume = VolumeDB(
                id=volume_id,
                novel_id=novel_id,
                title="第一卷",
                description=orch.state.theme,
                word_count=sum(len(ch.get("content", "")) for ch in orch.state.chapters),
                sort_order=1,
            )
            session.add(volume)

        for idx, ch in enumerate(orch.state.chapters):
            ch_id = f"{novel_id}_ch{idx+1}"
            chapter = await session.get(ChapterDB, ch_id)
            content = ch.get("content", "")
            if not chapter:
                chapter = ChapterDB(
                    id=ch_id,
                    volume_id=volume_id,
                    title=ch.get("title", f"第{idx+1}章"),
                    outline=ch.get("summary", ""),
                    content=content,
                    word_count=len(content),
                    status=ch.get("status", "draft"),
                    sort_order=idx + 1,
                    created_at=datetime.now(),
                )
                session.add(chapter)
            else:
                chapter.content = content
                chapter.word_count = len(content)
                chapter.status = ch.get("status", "draft")
                chapter.updated_at = datetime.now()

        for c_data in orch.state.characters:
            if not isinstance(c_data, dict):
                continue
            c_id = f"{novel_id}_char_{c_data.get('name', uuid.uuid4().hex[:6])}"
            char = await session.get(CharacterDB, c_id)
            now = datetime.now()
            if not char:
                char = CharacterDB(
                    id=c_id,
                    novel_id=novel_id,
                    name=c_data.get("name", "未命名"),
                    aliases=c_data.get("aliases", []),
                    role=c_data.get("role", ""),
                    personality=c_data.get("personality", ""),
                    background=c_data.get("background", ""),
                    goals=c_data.get("goals", []),
                    conflicts=c_data.get("conflicts", []),
                    speech_pattern=c_data.get("speech_pattern", ""),
                    appearance=c_data.get("appearance", ""),
                    arc_data=c_data.get("arc", {}),
                    world_id=c_data.get("world_id", None),
                    created_at=now,
                    updated_at=now,
                )
                session.add(char)

        if orch.state.world_settings and isinstance(orch.state.world_settings, dict):
            ws = orch.state.world_settings
            ws_id = f"{novel_id}_world"
            world = await session.get(WorldSettingDB, ws_id)
            now = datetime.now()
            if not world:
                world = WorldSettingDB(
                    id=ws_id,
                    novel_id=novel_id,
                    name=ws.get("name", "未命名世界"),
                    category=ws.get("category", ""),
                    description=ws.get("description", ""),
                    rules=ws.get("rules", []),
                    history=ws.get("history", {}),
                    created_at=now,
                    updated_at=now,
                )
                session.add(world)

        if orch.state.style_guide and isinstance(orch.state.style_guide, dict):
            sg = orch.state.style_guide
            sg_id = f"{novel_id}_style"
            style = await session.get(StyleGuideDB, sg_id)
            if not style:
                style = StyleGuideDB(
                    id=sg_id,
                    novel_id=novel_id,
                    vocabulary_preference=sg.get("vocabulary_preference", []),
                    sentence_patterns=sg.get("sentence_patterns", []),
                    pacing_preference=sg.get("pacing_preference", ""),
                    tone=sg.get("tone", ""),
                    anti_patterns=sg.get("anti_patterns", []),
                    reference_works=sg.get("reference_works", []),
                )
                session.add(style)

        await session.commit()


def _export_novel_to_file(orch):
    """将小说导出为本地 Markdown 文件"""
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(_PROJECT_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)

    safe_title = "".join(c for c in orch.state.title if c.isalnum() or c in "._- ") or "novel"
    filename = f"{safe_title}_{orch.state.novel_id}.md"
    filepath = os.path.join(output_dir, filename)

    md_parts = [
        f"# {orch.state.title}\n",
        f"\n> 主题：{orch.state.theme}  |  文风：{orch.state.tone}  |  章节数：{len(orch.state.chapters)}\n",
    ]

    if orch.state.world_settings and isinstance(orch.state.world_settings, dict):
        ws = orch.state.world_settings
        md_parts.append(f"\n---\n\n## 🌍 世界观：{ws.get('name', '未命名')}\n")
        if ws.get("description"):
            md_parts.append(f"\n{ws['description']}\n")
        if ws.get("rules"):
            md_parts.append("\n### 规则\n")
            for r in ws["rules"]:
                md_parts.append(f"- {r}\n")

    if orch.state.characters:
        md_parts.append("\n---\n\n## 👥 角色\n")
        for c in orch.state.characters:
            if isinstance(c, dict):
                md_parts.append(f"\n### {c.get('name', '未命名')}\n")
                if c.get("role"):
                    md_parts.append(f"- 角色：{c['role']}\n")
                if c.get("personality"):
                    md_parts.append(f"- 性格：{c['personality']}\n")
                if c.get("background"):
                    md_parts.append(f"\n{c['background']}\n")

    if orch.state.chapters:
        md_parts.append("\n---\n\n## 正文\n")
        for ch in orch.state.chapters:
            title = ch.get("title", f"第{ch.get('index', '?')}章")
            content = ch.get("content", "")
            md_parts.append(f"\n### {title}\n\n{content}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(md_parts)

    print(f"[Export] 📄 小说已导出: {filepath}")


import os


@router.post("/orchestrator/start")
async def orchestrator_start(req: OrchestratorRequest, learning_engine=None):
    """创建并启动小说编排器 - 默认使用 v4.0 Loop 循环架构，完成后持久化"""
    from .core.orchestrator import NovelOrchestrator

    orch = NovelOrchestrator(
        title=req.title, theme=req.theme, tone=req.tone,
        chapter_count=req.chapter_count, novel_id=req.novel_id,
        learning_engine=learning_engine,
    )
    _active_orchestrators[orch.state.novel_id] = orch
    _touch_orchestrator(orch.state.novel_id)
    _cleanup_orchestrators()
    result = await orch.run_all_loop()

    try:
        await _save_novel_to_db(orch)
        _export_novel_to_file(orch)
        print(f"[Orchestrator] ✅ 小说已持久化: {orch.state.title} (ID: {orch.state.novel_id})")
    except Exception as e:
        print(f"[Orchestrator] ⚠️ 持久化失败（不影响返回结果）: {e}")

    return {"success": True, "novel_id": orch.state.novel_id, "result": result}


@router.post("/orchestrator/start-loop")
async def orchestrator_start_loop(req: OrchestratorRequest, learning_engine=None):
    """v4.0: 使用 Loop 循环架构启动编排器（SKELETON → DETAIL → POLISH）"""
    from .core.orchestrator import NovelOrchestrator

    orch = NovelOrchestrator(
        title=req.title, theme=req.theme, tone=req.tone,
        chapter_count=req.chapter_count, novel_id=req.novel_id,
        learning_engine=learning_engine,
    )
    _active_orchestrators[orch.state.novel_id] = orch
    _touch_orchestrator(orch.state.novel_id)
    _cleanup_orchestrators()
    result = await orch.run_all_loop()

    try:
        await _save_novel_to_db(orch)
        _export_novel_to_file(orch)
        print(f"[Orchestrator] ✅ (Loop) 小说已持久化: {orch.state.title} (ID: {orch.state.novel_id})")
    except Exception as e:
        print(f"[Orchestrator] ⚠️ (Loop) 持久化失败（不影响返回结果）: {e}")

    return {"success": True, "novel_id": orch.state.novel_id, "result": result, "mode": "loop"}


@router.post("/orchestrator/start-linear")
async def orchestrator_start_linear(req: OrchestratorRequest, learning_engine=None):
    """（兼容模式）使用线性模式启动编排器，按顺序执行所有阶段"""
    from .core.orchestrator import NovelOrchestrator

    orch = NovelOrchestrator(
        title=req.title, theme=req.theme, tone=req.tone,
        chapter_count=req.chapter_count, novel_id=req.novel_id,
        learning_engine=learning_engine,
    )
    _active_orchestrators[orch.state.novel_id] = orch
    _touch_orchestrator(orch.state.novel_id)
    _cleanup_orchestrators()
    result = await orch.run_all()

    try:
        await _save_novel_to_db(orch)
        _export_novel_to_file(orch)
        print(f"[Orchestrator] ✅ (Linear) 小说已持久化: {orch.state.title} (ID: {orch.state.novel_id})")
    except Exception as e:
        print(f"[Orchestrator] ⚠️ (Linear) 持久化失败（不影响返回结果）: {e}")

    return {"success": True, "novel_id": orch.state.novel_id, "result": result, "mode": "linear"}


@router.post("/orchestrator/stage")
async def orchestrator_stage(req: StageRequest, learning_engine=None):
    """单独执行某个阶段（需要先通过 start 创建）"""
    from ..core.orchestrator import NovelOrchestrator

    orch = _active_orchestrators.get(req.novel_id)
    if not orch:
        # 尝试懒加载
        orch = NovelOrchestrator(
            title="临时", theme="", tone="史诗",
            chapter_count=1, novel_id=req.novel_id,
            learning_engine=learning_engine,
        )
        _active_orchestrators[req.novel_id] = orch
    result = await orch.run_stage(req.stage)
    return {"success": True, "novel_id": req.novel_id, "result": result, "status": orch.status()}


@router.get("/orchestrator/status")
async def orchestrator_status(novel_id: str):
    """查询编排器当前状态 / 已生成内容"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该 novel_id 的编排器")
    return orch.to_dict()


@router.get("/orchestrator/export")
async def orchestrator_export(novel_id: str):
    """导出所有章节为 Markdown 文本"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该 novel_id 的编排器")
    return {"success": True, "title": orch.state.title, "markdown": orch.export_chapters()}


@router.get("/orchestrator/list", tags=["编排"], description="列出所有活跃的编排器")
async def orchestrator_list():
    """列出所有活跃的编排器（最近使用）"""
    return {
        "orchestrators": [
            {"novel_id": nid, "title": o.state.title, "theme": o.state.theme,
             "chapter_count": o.state.chapter_count, "current_stage": o.state.current_stage,
             "completed_stages": o.state.completed_stages, "paused": o.is_paused()}
            for nid, o in _active_orchestrators.items()
        ]
    }


@router.post("/orchestrator/{novel_id}/pause", tags=["编排"], description="暂停指定编排器的生成流程")
async def orchestrator_pause(novel_id: str):
    """暂停活跃的编排器"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该编排器")
    orch.pause()
    return {"success": True, "paused": True, "novel_id": novel_id}


@router.post("/orchestrator/{novel_id}/resume", tags=["编排"], description="恢复暂停的编排器生成流程")
async def orchestrator_resume(novel_id: str):
    """恢复暂停的编排器"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该编排器")
    orch.resume()
    return {"success": True, "paused": False, "novel_id": novel_id}


@router.get("/orchestrator/{novel_id}/dashboard", tags=["编排"], description="获取编排器仪表盘数据")
async def orchestrator_dashboard(novel_id: str):
    """获取编排器仪表盘数据"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该编排器或已结束")
    return {
        "novel_id": novel_id,
        "title": orch.state.title,
        "stage": orch.state.current_stage,
        "completed_stages": orch.state.completed_stages,
        "paused": orch.is_paused(),
        "state_tracker": orch.state_tracker.to_dict(),
        "global_summary": orch.global_summary.to_dict(),
        "consistency_issues": orch.consistency_checker.get_issues_summary(),
        "chapter_count": orch.state.chapter_count,
    }


@router.post("/orchestrator/{novel_id}/check-consistency", tags=["编排"], description="对已完成章节进行一致性审查")
async def orchestrator_check_consistency(novel_id: str, chapter_idx: int = 0):
    """一致性审查"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该编排器")
    if chapter_idx <= 0 or chapter_idx > len(orch.state.chapters):
        raise HTTPException(400, "无效的章节序号")

    ch = orch.state.chapters[chapter_idx - 1]
    issues = orch.consistency_checker.check_chapter(
        chapter_idx=chapter_idx,
        content=ch.get("content", ""),
        world_settings=orch.state.world_settings,
        characters=orch.state.characters,
    )
    return {
        "chapter": chapter_idx,
        "title": ch.get("title", ""),
        "issues": issues,
        "total_issues": len(issues),
    }


@router.get("/orchestrator/{novel_id}/memory-search", tags=["编排"], description="语义搜索记忆中的内容")
async def orchestrator_memory_search(novel_id: str, q: str = "", keyword: str = ""):
    """搜索记忆内容"""
    orch = _active_orchestrators.get(novel_id)
    if not orch or not hasattr(orch, '_memory') or not orch._memory:
        return {"results": []}
    if q:
        results = orch._memory.semantic_search(q, top_k=5)
    elif keyword:
        results = orch._memory.search_by_keyword(keyword)
    else:
        return {"results": []}
    return {"query": q or keyword, "results": results}


# ═══════════════════════════════════════════════════════════
# v2.0 L1 规划层 API 端点
# ═══════════════════════════════════════════════════════════


class PlanRequest(BaseModel):
    """创建工作流计划请求"""
    title: str = Field(..., min_length=1, description="小说标题")
    genre: str = Field(..., min_length=1, description="小说类型/题材")
    chapter_count: int = Field(default=30, ge=1, le=1000, description="章节数")
    mode: str = Field(default="loop", description="模式: loop 或 linear")
    theme: str = Field(default="", description="主题")
    tone: str = Field(default="史诗", description="文风")
    platform: str = Field(default="番茄", description="发布平台")
    quality_threshold: float = Field(default=6.0, ge=0, le=10, description="质量阈值")
    novel_id: Optional[str] = None


class LoopRequest(BaseModel):
    """执行 LOOP 循环请求"""
    title: str = Field(..., min_length=1, description="小说标题")
    genre: str = Field(..., min_length=1, description="小说类型/题材")
    chapter_count: int = Field(default=30, ge=1, le=1000, description="章节数")
    mode: str = Field(default="loop", description="模式: loop 或 linear")
    theme: str = Field(default="", description="主题")
    tone: str = Field(default="史诗", description="文风")
    platform: str = Field(default="番茄", description="发布平台")
    novel_id: Optional[str] = None
    # Loop 配置
    max_loops: int = Field(default=3, ge=1, le=10, description="最大循环次数")
    chapters_per_loop: int = Field(default=10, ge=1, le=100, description="每轮章节数")
    quality_threshold: float = Field(default=6.0, ge=0, le=10, description="质量阈值")
    enable_skeleton_loop: bool = Field(default=True, description="启用 SKELETON 循环")
    enable_detail_loop: bool = Field(default=True, description="启用 DETAIL 循环")
    enable_refine_loop: bool = Field(default=True, description="启用 REFINE 循环")
    temperature_profile: str = Field(default="gradient", description="温度曲线")


class PlanStatusResponse(BaseModel):
    """计划状态响应"""
    success: bool
    plan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/plan/create", tags=["规划"], description="创建小说工作流计划（v2.0 L1）")
async def plan_create(req: PlanRequest):
    """
    根据小说配置创建工作流计划

    使用 NovelPlannerAgent 创建全局工作流计划，返回包含所有阶段的 WorkflowPlan。
    """
    planner = _workflow_engine.planner

    plan = await planner.create_plan({
        "title": req.title,
        "genre": req.genre,
        "chapter_count": req.chapter_count,
        "mode": req.mode,
        "theme": req.theme,
        "tone": req.tone,
        "platform": req.platform,
        "quality_threshold": req.quality_threshold,
        "novel_id": req.novel_id,
    })

    return {
        "success": True,
        "plan": plan.to_dict(),
        "novel_id": plan.novel_id,
    }


@router.get("/plan/{novel_id}", tags=["规划"], description="获取工作流计划状态")
async def plan_get(novel_id: str):
    """获取指定小说的工作流计划状态"""
    planner = _workflow_engine.planner
    plan = planner.get_plan(novel_id)

    if not plan:
        raise HTTPException(404, f"未找到 novel_id={novel_id} 的工作流计划")

    return {
        "success": True,
        "plan": plan.to_dict(),
    }


@router.get("/plan/next-stage/{novel_id}", tags=["规划"], description="获取下一步执行阶段")
async def plan_next_stage(novel_id: str):
    """
    根据当前状态决定下一步执行哪个阶段

    返回下一步阶段信息，如果工作流结束则返回 null。
    """
    planner = _workflow_engine.planner
    plan = planner.get_plan(novel_id)

    if not plan:
        raise HTTPException(404, f"未找到 novel_id={novel_id} 的工作流计划")

    next_stage = planner.decide_next_stage(plan)

    return {
        "success": True,
        "novel_id": novel_id,
        "next_stage": next_stage.to_dict() if next_stage else None,
        "plan_status": plan.status,
    }


@router.post("/plan/{novel_id}/start-loop", tags=["规划"], description="启动工作流 LOOP 循环（v2.0 L1）")
async def plan_start_loop(req: LoopRequest, learning_engine=None):
    """
    使用 WorkflowEngine 启动 LOOP 循环

    执行 SKELETON → DETAIL → REFINE 三阶段循环架构，
    支持 SSE 事件推送和暂停/恢复控制。
    """
    novel_id = req.novel_id or f"loop_{int(time.time())}"

    # 注册学习引擎（如果提供）
    if learning_engine and _workflow_engine.learning_engine is None:
        from ..services.memory_service import MemoryService
        _workflow_engine.learning_engine = learning_engine

    # 异步启动循环（非阻塞）
    async def _run_with_persistence(novel_id, req):
        """运行循环并自动持久化结果"""
        try:
            result = await _workflow_engine.run_loop(
                novel_id=novel_id,
                loop_config=req.dict(),
            )

            # 持久化到数据库（如果需要）
            try:
                # 注意：这里需要 WorkflowEngine 返回章节数据后才能持久化
                # 简化版本：记录日志
                print(f"[WorkflowEngine] ✅ LOOP 循环完成: novel_id={novel_id}, result={result}")
            except Exception as e:
                print(f"[WorkflowEngine] ⚠️ 持久化失败: {e}")

            return result
        except Exception as e:
            print(f"[WorkflowEngine] ❌ LOOP 循环失败: {e}")
            return {"success": False, "error": str(e), "novel_id": novel_id}

    # 启动后台任务
    asyncio.create_task(_run_with_persistence(novel_id, req))

    return {
        "success": True,
        "novel_id": novel_id,
        "message": "LOOP 循环已启动",
        "status_url": f"/api/orchestrator/workflow/status/{novel_id}",
    }


@router.get("/orchestrator/workflow/status/{novel_id}", tags=["规划"], description="获取工作流引擎状态")
async def workflow_status(novel_id: str):
    """获取 WorkflowEngine 的工作流状态"""
    status = _workflow_engine.get_status(novel_id)

    if not status:
        raise HTTPException(404, f"未找到 novel_id={novel_id} 的工作流状态")

    return {
        "success": True,
        "status": status,
    }


@router.post("/orchestrator/workflow/{novel_id}/pause", tags=["规划"], description="暂停工作流")
async def workflow_pause(novel_id: str):
    """暂停指定工作流"""
    success = await _workflow_engine.pause(novel_id)

    if not success:
        raise HTTPException(404, f"未找到 novel_id={novel_id} 的工作流")

    return {
        "success": True,
        "paused": True,
        "novel_id": novel_id,
    }


@router.post("/orchestrator/workflow/{novel_id}/resume", tags=["规划"], description="恢复工作流")
async def workflow_resume(novel_id: str):
    """恢复暂停的工作流"""
    success = await _workflow_engine.resume(novel_id)

    if not success:
        raise HTTPException(404, f"未找到 novel_id={novel_id} 的工作流")

    return {
        "success": True,
        "paused": False,
        "novel_id": novel_id,
    }


@router.get("/orchestrator/workflow/list", tags=["规划"], description="列出所有工作流")
async def workflow_list():
    """列出所有工作流状态"""
    statuses = _workflow_engine.list_status()
    return {
        "success": True,
        "workflows": statuses,
        "total": len(statuses),
    }


@router.get("/orchestrator/event-history", tags=["规划"], description="获取事件历史（v2.0 L1）")
async def event_history(
    event_type: Optional[str] = Query(None, description="过滤事件类型"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    source: Optional[str] = Query(None, description="过滤事件来源"),
):
    """
    获取事件总线历史记录

    用于前端实时展示创作进度和调试。
    """
    history = _event_bus.get_history(
        event_type=event_type,
        limit=limit,
        source=source,
    )

    return {
        "success": True,
        "events": history,
        "total": len(history),
    }


@router.get("/orchestrator/event-stats", tags=["规划"], description="获取事件总线统计")
async def event_stats():
    """获取事件总线统计信息"""
    stats = _event_bus.get_stats()
    return {
        "success": True,
        "stats": stats,
    }


@router.get("/orchestrator/planner-stats", tags=["规划"], description="获取规划器统计信息")
async def planner_stats():
    """获取规划器统计信息"""
    stats = _workflow_engine.planner.get_statistics()
    return {
        "success": True,
        "stats": stats,
    }


@router.get("/orchestrator/quality-stats", tags=["规划"], description="获取质量门控统计")
async def quality_stats():
    """获取质量门控统计信息"""
    stats = _workflow_engine.planner.quality_gate.get_statistics()
    return {
        "success": True,
        "stats": stats,
    }
