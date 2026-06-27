"""
Orchestrator 全流程端点 — /api/orchestrator（含 SSE 实时推送）
"""
import json
import time as time_module
import asyncio
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .deps import (
    _ensure_services_ready, learning_engine,
    _active_orchestrators, _touch_orchestrator, _cleanup_orchestrators,
    _save_novel_to_db, _export_novel_to_file,
)
from .models import OrchestratorRequest, StageRequest

router = APIRouter(prefix="/api/orchestrator", tags=["编排"])


async def _run_orchestrator(orch, queue: asyncio.Queue, skip_editing_review: bool = False):
    """在后台运行编排器并持久化"""
    from ...core.orchestrator import NovelOrchestrator

    skip_stages = ["editing", "review"] if skip_editing_review else None
    result = await orch.run_all(skip_stages=skip_stages)

    try:
        await _save_novel_to_db(orch)
        _export_novel_to_file(orch)
        await queue.put({
            "event": "save_success",
            "novel_id": orch.state.novel_id,
            "title": orch.state.title,
            "chapters_count": len(orch.state.chapters),
            "message": f"✅ 已保存到数据库，共 {len(orch.state.chapters)} 章",
        })
        print(f"[Orchestrator] ✅ 小说已持久化: {orch.state.title} (ID: {orch.state.novel_id})")
    except Exception as e:
        print(f"[Orchestrator] ⚠️ 持久化失败: {e}")
    return result


# ── 启动端点 ───────────────────────────────────────────────────

@router.post("/start")
async def orchestrator_start(req: OrchestratorRequest):
    """创建并启动小说编排器 - 默认使用 v4.0 Loop 循环架构，完成后持久化"""
    from ...core.orchestrator import NovelOrchestrator

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


@router.post("/start-loop")
async def orchestrator_start_loop(req: OrchestratorRequest):
    """v4.0: 使用 Loop 循环架构启动编排器（SKELETON → DETAIL → POLISH）"""
    from ...core.orchestrator import NovelOrchestrator

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


@router.post("/start-linear")
async def orchestrator_start_linear(req: OrchestratorRequest):
    """（兼容模式）使用线性模式启动编排器，按顺序执行所有阶段"""
    from ...core.orchestrator import NovelOrchestrator

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


# ── 阶段/状态/导出 ─────────────────────────────────────────────

@router.post("/stage")
async def orchestrator_stage(req: StageRequest):
    """单独执行某个阶段（需要先通过 start 创建）"""
    orch = _active_orchestrators.get(req.novel_id)
    if not orch:
        raise HTTPException(404, "未找到该 novel_id 的编排器，请先调用 /api/orchestrator/start")
    result = await orch.run_stage(req.stage)
    return {"success": True, "novel_id": req.novel_id, "result": result, "status": orch.status()}


@router.get("/status")
async def orchestrator_status(novel_id: str):
    """查询编排器当前状态 / 已生成内容"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该 novel_id 的编排器")
    return orch.to_dict()


@router.get("/export")
async def orchestrator_export(novel_id: str):
    """导出所有章节为 Markdown 文本"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该 novel_id 的编排器")
    return {"success": True, "title": orch.state.title, "markdown": orch.export_chapters()}


@router.get("/list")
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


# ── 暂停/恢复/仪表盘 ───────────────────────────────────────────

@router.post("/{novel_id}/pause", description="暂停指定编排器的生成流程")
async def orchestrator_pause(novel_id: str):
    """暂停活跃的编排器"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该编排器")
    orch.pause()
    return {"success": True, "paused": True, "novel_id": novel_id}


@router.post("/{novel_id}/resume", description="恢复暂停的编排器生成流程")
async def orchestrator_resume(novel_id: str):
    """恢复暂停的编排器"""
    orch = _active_orchestrators.get(novel_id)
    if not orch:
        raise HTTPException(404, "未找到该编排器")
    orch.resume()
    return {"success": True, "paused": False, "novel_id": novel_id}


@router.get("/{novel_id}/dashboard", description="获取编排器仪表盘数据（状态跟踪、全局摘要、一致性审查）")
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


@router.post("/{novel_id}/check-consistency", description="对已完成章节进行一致性审查")
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


@router.get("/{novel_id}/memory-search", description="语义搜索记忆中的内容")
async def orchestrator_memory_search(novel_id: str, q: str = "", keyword: str = ""):
    """搜索记忆内容"""
    orch = _active_orchestrators.get(novel_id)
    if not orch or not orch._memory:
        return {"results": []}
    if q:
        results = orch._memory.semantic_search(q, top_k=5)
    elif keyword:
        results = orch._memory.search_by_keyword(keyword)
    else:
        return {"results": []}
    return {"query": q or keyword, "results": results}


# ── SSE 实时推送 ───────────────────────────────────────────────

@router.get("/stream", description="SSE 实时推送小说生成进度（含流式写作）")
async def orchestrator_stream(
    title: str,
    theme: str,
    tone: str = "史诗",
    chapter_count: int = 5,
    novel_id: Optional[str] = None,
    preset_character_id: Optional[str] = None,
    preset_world_id: Optional[str] = None,
    skip_editing_review: bool = False,
):
    """SSE 实时推送小说生成进度（GET 方式，兼容 EventSource）

    可选参数：
    - preset_character_id: 预设角色ID（从数据库已保存角色中选择）
    - preset_world_id: 预设世界观ID（从数据库已保存世界观中选择）
    - skip_editing_review: 是否跳过编辑和审查阶段（章节生成完即保存并停止）
    """
    from ...core.orchestrator import NovelOrchestrator

    queue: asyncio.Queue = asyncio.Queue()

    async def progress_callback(event_type: str, payload: Dict[str, Any]):
        await queue.put({"event": event_type, **payload})

    preset_characters = None
    preset_world = None
    if preset_character_id or preset_world_id:
        from ...db.database import AsyncSessionLocal
        from ...db.models import CharacterDB, WorldSettingDB
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            if preset_character_id:
                char = await session.get(CharacterDB, preset_character_id)
                if char:
                    preset_characters = [{
                        "name": char.name,
                        "role": char.role,
                        "personality": char.personality,
                        "background": char.background,
                        "appearance": char.appearance,
                        "goals": char.goals,
                        "aliases": char.aliases,
                    }]
                    print(f"[Orchestrator] 📌 使用预设角色: {char.name}")
            if preset_world_id:
                world = await session.get(WorldSettingDB, preset_world_id)
                if world:
                    preset_world = {
                        "name": world.name,
                        "category": world.category,
                        "description": world.description,
                        "rules": world.rules,
                    }
                    print(f"[Orchestrator] 📌 使用预设世界观: {world.name}")

    async def event_generator():
        orch = NovelOrchestrator(
            title=title, theme=theme, tone=tone,
            chapter_count=chapter_count, novel_id=novel_id,
            progress_callback=progress_callback,
            preset_characters=preset_characters,
            preset_world=preset_world,
            learning_engine=learning_engine,
        )
        _active_orchestrators[orch.state.novel_id] = orch
        _touch_orchestrator(orch.state.novel_id)
        _cleanup_orchestrators()

        task = asyncio.create_task(_run_orchestrator(orch, queue, skip_editing_review))

        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                event_type = data.get("event", "message")
                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                if task.done():
                    try:
                        result = task.result()
                        yield f"event: final_result\ndata: {json.dumps({'result': result}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                    break
                else:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': time_module.time()}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )