"""
Agent Prompt 管理端点 — /api/prompts
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException

from .deps import _VALID_AGENT_TYPES
from .models import AgentPromptRequest

router = APIRouter(prefix="/api/prompts", tags=["Prompt"])


@router.get("", description="列出所有Agent Prompt（支持按 agent_type / depth_level 过滤）")
async def list_prompts(agent_type: Optional[str] = None, depth_level: Optional[int] = None,
                        novel_id: Optional[str] = None, active_only: bool = False):
    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as session:
        stmt = select(AgentPromptDB)
        conds = []
        if agent_type:
            conds.append(AgentPromptDB.agent_type == agent_type)
        if depth_level is not None:
            conds.append(AgentPromptDB.depth_level == depth_level)
        if novel_id:
            conds.append(AgentPromptDB.novel_id == novel_id)
        if active_only:
            conds.append(AgentPromptDB.is_active == 1)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by(AgentPromptDB.quality_score.desc(), AgentPromptDB.updated_at.desc())
        result = await session.execute(stmt)
        prompts = result.scalars().all()
        return {
            "prompts": [
                {
                    "id": p.id,
                    "novel_id": p.novel_id,
                    "agent_type": p.agent_type,
                    "depth_level": p.depth_level,
                    "prompt_type": p.prompt_type,
                    "title": p.title,
                    "content": p.content,
                    "quality_score": p.quality_score,
                    "usage_count": p.usage_count,
                    "is_active": bool(p.is_active),
                    "metadata": p.meta_info or {},
                    "created_at": str(p.created_at) if p.created_at else "",
                    "updated_at": str(p.updated_at) if p.updated_at else "",
                }
                for p in prompts
            ],
            "total": len(prompts),
        }


@router.get("/{prompt_id}", description="获取单个 prompt 详情")
async def get_prompt(prompt_id: str):
    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB

    async with AsyncSessionLocal() as session:
        p = await session.get(AgentPromptDB, prompt_id)
        if not p:
            raise HTTPException(404, "Prompt 不存在")
        return {
            "id": p.id,
            "novel_id": p.novel_id,
            "agent_type": p.agent_type,
            "depth_level": p.depth_level,
            "prompt_type": p.prompt_type,
            "title": p.title,
            "content": p.content,
            "quality_score": p.quality_score,
            "usage_count": p.usage_count,
            "is_active": bool(p.is_active),
            "metadata": p.meta_info or {},
        }


@router.post("", description="新建 prompt")
async def create_prompt(req: AgentPromptRequest):
    if req.agent_type not in _VALID_AGENT_TYPES:
        raise HTTPException(400, f"无效 agent_type，必须为: {sorted(_VALID_AGENT_TYPES)}")
    if req.prompt_type not in ("system", "user"):
        raise HTTPException(400, "prompt_type 必须为 system 或 user")

    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB

    async with AsyncSessionLocal() as session:
        now = datetime.now()
        p = AgentPromptDB(
            id=str(uuid.uuid4()),
            novel_id=req.novel_id,
            agent_type=req.agent_type,
            depth_level=req.depth_level,
            prompt_type=req.prompt_type,
            title=req.title or f"{req.agent_type}-{req.prompt_type}-depth{req.depth_level}",
            content=req.content,
            quality_score=req.quality_score,
            is_active=req.is_active,
            meta_info=req.metadata or {},
            created_at=now, updated_at=now,
        )
        if req.is_active:
            from sqlalchemy import update, and_
            await session.execute(
                update(AgentPromptDB)
                .where(and_(AgentPromptDB.agent_type == req.agent_type,
                           AgentPromptDB.depth_level == req.depth_level,
                           AgentPromptDB.prompt_type == req.prompt_type,
                           (AgentPromptDB.novel_id == req.novel_id if req.novel_id else AgentPromptDB.novel_id.is_(None))))
                .values(is_active=0)
            )
        session.add(p)
        await session.commit()
        return {"success": True, "id": p.id}


@router.put("/{prompt_id}", description="更新 prompt 内容/评分")
async def update_prompt(prompt_id: str, req: AgentPromptRequest):
    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB

    async with AsyncSessionLocal() as session:
        p = await session.get(AgentPromptDB, prompt_id)
        if not p:
            raise HTTPException(404, "Prompt 不存在")
        p.title = req.title or p.title
        p.content = req.content
        p.quality_score = req.quality_score
        p.is_active = req.is_active
        p.meta_info = req.metadata or p.meta_info
        p.updated_at = datetime.now()
        if req.is_active:
            from sqlalchemy import update, and_
            await session.execute(
                update(AgentPromptDB)
                .where(and_(AgentPromptDB.agent_type == p.agent_type,
                           AgentPromptDB.depth_level == p.depth_level,
                           AgentPromptDB.prompt_type == p.prompt_type,
                           AgentPromptDB.id != p.id,
                           (AgentPromptDB.novel_id == p.novel_id if p.novel_id else AgentPromptDB.novel_id.is_(None))))
                .values(is_active=0)
            )
        await session.commit()
        return {"success": True, "id": p.id}


@router.delete("/{prompt_id}", description="删除 prompt")
async def delete_prompt(prompt_id: str):
    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB

    async with AsyncSessionLocal() as session:
        p = await session.get(AgentPromptDB, prompt_id)
        if not p:
            raise HTTPException(404, "Prompt 不存在")
        await session.delete(p)
        await session.commit()
        return {"success": True}


@router.post("/{prompt_id}/activate", description="将该 prompt 设为当前使用版本")
async def activate_prompt(prompt_id: str):
    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB
    from sqlalchemy import update, and_

    async with AsyncSessionLocal() as session:
        p = await session.get(AgentPromptDB, prompt_id)
        if not p:
            raise HTTPException(404, "Prompt 不存在")
        await session.execute(
            update(AgentPromptDB)
            .where(and_(AgentPromptDB.agent_type == p.agent_type,
                       AgentPromptDB.depth_level == p.depth_level,
                       AgentPromptDB.prompt_type == p.prompt_type,
                       (AgentPromptDB.novel_id == p.novel_id if p.novel_id else AgentPromptDB.novel_id.is_(None))))
            .values(is_active=0)
        )
        p.is_active = 1
        p.updated_at = datetime.now()
        await session.commit()
        return {"success": True, "id": p.id}


@router.get("/active/{agent_type}", description="获取指定 agent 当前激活的 prompt")
async def get_active_prompt(agent_type: str, depth_level: int = 1, prompt_type: str = "system", novel_id: Optional[str] = None):
    if agent_type not in _VALID_AGENT_TYPES:
        raise HTTPException(400, "无效 agent_type")
    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB
    from sqlalchemy import select, and_

    async with AsyncSessionLocal() as session:
        candidates = []
        if novel_id:
            r = await session.execute(
                select(AgentPromptDB).where(and_(
                    AgentPromptDB.agent_type == agent_type,
                    AgentPromptDB.depth_level == depth_level,
                    AgentPromptDB.prompt_type == prompt_type,
                    AgentPromptDB.novel_id == novel_id,
                    AgentPromptDB.is_active == 1,
                )).order_by(AgentPromptDB.quality_score.desc()).limit(1)
            )
            candidates = list(r.scalars())
        if not candidates:
            r = await session.execute(
                select(AgentPromptDB).where(and_(
                    AgentPromptDB.agent_type == agent_type,
                    AgentPromptDB.depth_level == depth_level,
                    AgentPromptDB.prompt_type == prompt_type,
                    AgentPromptDB.novel_id.is_(None),
                    AgentPromptDB.is_active == 1,
                )).order_by(AgentPromptDB.quality_score.desc()).limit(1)
            )
            candidates = list(r.scalars())
        if not candidates:
            r = await session.execute(
                select(AgentPromptDB).where(and_(
                    AgentPromptDB.agent_type == agent_type,
                    AgentPromptDB.depth_level == depth_level,
                    AgentPromptDB.prompt_type == prompt_type,
                    AgentPromptDB.novel_id.is_(None),
                )).order_by(AgentPromptDB.quality_score.desc()).limit(1)
            )
            candidates = list(r.scalars())
        if not candidates:
            return {"prompt": None, "using_default": True}
        p = candidates[0]
        p.usage_count = (p.usage_count or 0) + 1
        await session.commit()
        return {
            "prompt": {
                "id": p.id, "agent_type": p.agent_type,
                "depth_level": p.depth_level, "prompt_type": p.prompt_type,
                "title": p.title, "content": p.content,
                "quality_score": p.quality_score, "metadata": p.meta_info or {},
            },
            "using_default": False,
        }


@router.post("/save-from-run", description="将某次 loop 运行中的 prompt 批量保存为模板")
async def save_prompts_from_run(req: Dict[str, Any]):
    items = req.get("items") or []
    novel_id = req.get("novel_id")
    if not items:
        raise HTTPException(400, "items 不能为空")
    from ...db.database import AsyncSessionLocal
    from ...db.models import AgentPromptDB

    saved = []
    async with AsyncSessionLocal() as session:
        now = datetime.now()
        for item in items:
            at = item.get("agent_type")
            if at not in _VALID_AGENT_TYPES:
                continue
            p = AgentPromptDB(
                id=str(uuid.uuid4()),
                novel_id=novel_id,
                agent_type=at,
                depth_level=int(item.get("depth_level", 1)),
                prompt_type=item.get("prompt_type", "system"),
                title=item.get("title", f"{at}-模板"),
                content=item.get("content", ""),
                quality_score=int(item.get("quality_score", 80)),
                is_active=int(item.get("is_active", 0)),
                meta_info=item.get("metadata", {}),
                created_at=now, updated_at=now,
            )
            session.add(p)
            saved.append(p.id)
        await session.commit()
    return {"success": True, "saved_ids": saved, "count": len(saved)}


@router.post("/cache-clear", description="清理运行时 prompt 缓存（热更新）")
async def clear_prompt_cache():
    from ...core.prompt_resolver import clear_cache
    clear_cache()
    return {"success": True, "message": "Prompt 缓存已清除，下次调用将加载最新数据"}


@router.post("/seed-defaults", description="初始化6个Agent的默认Prompt模板到数据库")
async def seed_default_prompts():
    """
    从 prompts.py 读取 6 个 Agent 的统一 Skill 提示词，
    插入 AgentPromptDB 作为默认模板（is_active=1, novel_id=NULL）。

    每次调用先检查是否已有激活的默认模板，如果有则跳过（幂等）。
    v4.0: 从 18 条（6 Agent × 3 depth）合并为 6 条统一 Skill 提示词。
    """
    from ...db.models import AgentPromptDB
    from ...db.database import AsyncSessionLocal
    from ...agents.prompts import (
        build_story_architect_system_prompt,
        build_world_system_prompt,
        build_character_system_prompt,
        build_opening_hook_system_prompt,
        build_draft_system_prompt,
        build_style_editor_system_prompt,
    )
    from sqlalchemy import select, and_

    builders = {
        "story_architect": ("故事架构师", build_story_architect_system_prompt),
        "world": ("世界观构建师", build_world_system_prompt),
        "character": ("角色塑造师", build_character_system_prompt),
        "opening_hook": ("开篇钩子师", build_opening_hook_system_prompt),
        "draft": ("专业写手", build_draft_system_prompt),
        "style_editor": ("文风精修师", build_style_editor_system_prompt),
    }

    created = 0
    skipped = 0
    now = datetime.now()

    async with AsyncSessionLocal() as session:
        for agent_type, (label, builder) in builders.items():
            existing = await session.execute(
                select(AgentPromptDB).where(and_(
                    AgentPromptDB.agent_type == agent_type,
                    AgentPromptDB.prompt_type == "system",
                    AgentPromptDB.novel_id.is_(None),
                    AgentPromptDB.is_active == 1,
                )).limit(1)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            try:
                content = builder(1)
            except Exception:
                content = builder(1)

            if not content or len(content) < 20:
                skipped += 1
                continue

            p = AgentPromptDB(
                id=str(uuid.uuid4()),
                novel_id=None,
                agent_type=agent_type,
                depth_level=1,
                prompt_type="system",
                title=f"{label}（Skill 默认模板）",
                content=content,
                quality_score=80,
                usage_count=0,
                is_active=1,
                meta_info={"source": "seed_defaults", "label": label, "version": "v4.0-skill"},
                created_at=now,
                updated_at=now,
            )
            session.add(p)
            created += 1

        await session.commit()

    return {
        "success": True,
        "created": created,
        "skipped": skipped,
        "total": created + skipped,
        "message": f"已初始化 {created} 个默认 Skill 模板（跳过 {skipped} 个已存在的）",
    }