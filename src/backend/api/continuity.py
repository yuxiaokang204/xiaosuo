"""
章节衔接引擎端点 — /api/continuity
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from .deps import learning_engine
from .models import ContinuitySaveRequest

router = APIRouter(prefix="/api/continuity", tags=["Continuity"])


@router.post("/save", description="保存章节结尾的结构化钩子")
async def save_continuity(req: ContinuitySaveRequest):
    from ...db.database import AsyncSessionLocal
    from ...db.models import ChapterContinuityDB
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChapterContinuityDB).where(and_(
                ChapterContinuityDB.novel_id == req.novel_id,
                ChapterContinuityDB.chapter_idx == req.chapter_idx,
            )).limit(1)
        )
        existing = result.scalar_one_or_none()
        now = datetime.now()
        if existing:
            existing.ending_text = req.ending_text or existing.ending_text
            existing.scene = req.scene or existing.scene
            existing.character_states = req.character_states or existing.character_states
            existing.unresolved = req.unresolved or existing.unresolved
            existing.tension_points = req.tension_points or existing.tension_points
            existing.continuity_score = req.continuity_score
            existing.user_notes = req.user_notes or existing.user_notes
            existing.updated_at = now
            cid = existing.id
        else:
            c = ChapterContinuityDB(
                id=str(uuid.uuid4()),
                novel_id=req.novel_id,
                chapter_idx=req.chapter_idx,
                chapter_title=req.chapter_title,
                ending_text=req.ending_text,
                scene=req.scene or {},
                character_states=req.character_states or [],
                unresolved=req.unresolved or [],
                tension_points=req.tension_points or [],
                continuity_score=req.continuity_score,
                user_notes=req.user_notes,
                created_at=now, updated_at=now,
            )
            session.add(c)
            cid = c.id
        await session.commit()
        return {"success": True, "id": cid}


@router.get("/{novel_id}", description="获取某小说的章节衔接记录")
async def list_continuity(novel_id: str, chapter_idx: Optional[int] = None):
    from ...db.database import AsyncSessionLocal
    from ...db.models import ChapterContinuityDB
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as session:
        stmt = select(ChapterContinuityDB).where(ChapterContinuityDB.novel_id == novel_id)
        if chapter_idx:
            stmt = stmt.where(ChapterContinuityDB.chapter_idx == chapter_idx)
        stmt = stmt.order_by(ChapterContinuityDB.chapter_idx.asc())
        result = await session.execute(stmt)
        items = result.scalars().all()
        return {
            "items": [
                {
                    "id": c.id, "chapter_idx": c.chapter_idx,
                    "chapter_title": c.chapter_title, "ending_text": c.ending_text,
                    "scene": c.scene, "character_states": c.character_states,
                    "unresolved": c.unresolved, "tension_points": c.tension_points,
                    "continuity_score": c.continuity_score, "user_notes": c.user_notes,
                    "updated_at": str(c.updated_at) if c.updated_at else "",
                }
                for c in items
            ],
            "total": len(items),
        }


@router.get("/{novel_id}/instruction", description="生成下一章的强制衔接指令（结合学习引擎偏好）")
async def get_continuity_instruction(novel_id: str, next_chapter_idx: int = 1):
    from ...db.database import AsyncSessionLocal
    from ...db.models import ChapterContinuityDB
    from sqlalchemy import select, and_

    prev_idx = max(1, next_chapter_idx - 1)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChapterContinuityDB).where(and_(
                ChapterContinuityDB.novel_id == novel_id,
                ChapterContinuityDB.chapter_idx == prev_idx,
            )).limit(1)
        )
        curr = result.scalar_one_or_none()

        prev_prev = None
        if prev_idx > 1:
            r = await session.execute(
                select(ChapterContinuityDB).where(and_(
                    ChapterContinuityDB.novel_id == novel_id,
                    ChapterContinuityDB.chapter_idx == prev_idx - 1,
                )).limit(1)
            )
            prev_prev = r.scalar_one_or_none()

    style_preference = ""
    if learning_engine:
        try:
            stats = learning_engine.get_statistics()
            top_patterns = stats.get("top_10_patterns", [])
            if top_patterns and isinstance(top_patterns, list):
                texts = []
                for x in top_patterns[:3]:
                    if isinstance(x, dict):
                        texts.append(str(x.get("pattern", "")))
                    elif isinstance(x, str):
                        texts.append(x)
                if texts:
                    style_preference = "参考用户偏好表达方式：" + "; ".join(texts)
        except Exception:
            pass

    if not curr:
        return {
            "instruction": "这是第一章，无需衔接前章。请直接进入场景。",
            "has_previous": False,
            "style_preference": style_preference,
        }

    ending_preview = (curr.ending_text or "")[-300:]
    parts = []
    parts.append(f"【衔接指令 — 第 {next_chapter_idx} 章】")
    parts.append(f"1. 本章开头必须直接接续第 {prev_idx} 章结尾的场景/动作/对话，不能跳跃时间线或突然换景。")
    parts.append(f'   上一章结尾原文："{ending_preview}"')
    parts.append("2. 必须自然承接上文的角色状态，角色的情绪、立场、目标应当与上一章结尾保持连续，不得突然反转。")
    if curr.character_states:
        for cs in (curr.character_states or [])[:3]:
            if isinstance(cs, dict):
                name = cs.get("name") or "角色"
                status = cs.get("status") or cs.get("action") or ""
                if status:
                    parts.append(f"   - {name}：{status}")
    if curr.tension_points:
        parts.append("3. 必须承接/呼应上一章留下的张力点或悬念：")
        for tp in (curr.tension_points or [])[:3]:
            parts.append(f"   - {tp}")
    if curr.unresolved:
        parts.append("4. 以下未解决的情节应当在本章有所推进或提及：")
        for u in (curr.unresolved or [])[:3]:
            parts.append(f"   - {u}")
    if prev_prev and prev_prev.tension_points:
        parts.append("5. 可以微妙呼应前一章留下的线索，但不可直接全部解决。")
    parts.append(f"6. 本章结尾应当再次留下新的张力点，为第 {next_chapter_idx + 1} 章留出钩子。")
    if style_preference:
        parts.append(f"\n【表达偏好】{style_preference}")

    return {
        "instruction": "\n".join(parts),
        "ending_preview": ending_preview,
        "scene": curr.scene or {},
        "character_states": curr.character_states or [],
        "tension_points": curr.tension_points or [],
        "unresolved": curr.unresolved or [],
        "continuity_score": curr.continuity_score,
        "style_preference": style_preference,
        "has_previous": True,
        "prev_chapter_idx": prev_idx,
        "next_chapter_idx": next_chapter_idx,
    }


@router.post("/{novel_id}/feedback", description="提交章节衔接评分（结合学习引擎）")
async def submit_continuity_feedback(novel_id: str, chapter_idx: int, score: int = 7, comment: str = ""):
    if score < 1 or score > 10:
        raise HTTPException(400, "评分必须在 1-10 之间")
    if learning_engine:
        learning_engine.record_continuity_feedback(
            novel_id=novel_id,
            chapter_idx=chapter_idx,
            score=score,
            comment=comment,
        )
        stats = learning_engine.get_continuity_statistics(novel_id)
        return {
            "success": True,
            "stats": stats,
            "intensity": learning_engine.get_continuity_intensity(novel_id),
        }
    return {"success": True, "stats": {"avg_score": score, "total": 1, "trend": "stable"}}


@router.get("/{novel_id}/stats", description="获取衔接评分统计")
async def get_continuity_stats(novel_id: str):
    if learning_engine:
        return learning_engine.get_continuity_statistics(novel_id)
    return {"avg_score": 7, "total": 0, "trend": "stable"}