"""
Settings + Presets 端点 — /api/settings、/api/presets
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from .models import (
    SaveWorldRequest, SaveCharacterRequest,
    UpdateCharacterRequest, UpdateWorldRequest,
)

router = APIRouter(prefix="/api", tags=["预设"])


# ── Presets（获取所有已保存角色和世界观）────────────────────────

@router.get("/presets")
async def list_presets():
    """获取所有可用的预设角色和世界观（供全流程编排选择）"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import NovelDB, CharacterDB, WorldSettingDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        char_result = await session.execute(
            select(CharacterDB).order_by(CharacterDB.updated_at.desc())
        )
        characters = char_result.scalars().all()

        world_result = await session.execute(
            select(WorldSettingDB).order_by(WorldSettingDB.updated_at.desc())
        )
        worlds = world_result.scalars().all()

        novel_result = await session.execute(select(NovelDB))
        novels = {n.id: n.title for n in novel_result.scalars().all()}

        return {
            "characters": [
                {
                    "id": c.id,
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality,
                    "background": c.background,
                    "appearance": c.appearance,
                    "goals": c.goals or [],
                    "conflicts": c.conflicts or [],
                    "speech_pattern": c.speech_pattern or "",
                    "aliases": c.aliases or [],
                    "arc_data": c.arc_data or {},
                    "novel_id": c.novel_id,
                    "world_id": getattr(c, 'world_id', None),
                    "created_at": str(c.created_at) if c.created_at else None,
                    "updated_at": str(c.updated_at) if c.updated_at else None,
                    "novel_title": novels.get(c.novel_id, c.novel_id) if c.novel_id else "",
                }
                for c in characters
            ],
            "world_settings": [
                {
                    "id": w.id,
                    "name": w.name,
                    "category": w.category,
                    "description": w.description,
                    "rules": w.rules or [],
                    "history": w.history or [],
                    "novel_id": w.novel_id,
                    "created_at": str(w.created_at) if w.created_at else None,
                    "updated_at": str(w.updated_at) if w.updated_at else None,
                    "novel_title": novels.get(w.novel_id, w.novel_id) if w.novel_id else "",
                }
                for w in worlds
            ],
        }


# ── 保存世界观 / 角色 ──────────────────────────────────────────

@router.post("/settings/world", description="保存世界观到数据库")
async def save_world(req: SaveWorldRequest):
    """保存世界观，供全流程编排选取"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import NovelDB, WorldSettingDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        novel_result = await session.execute(
            select(NovelDB).limit(1)
        )
        novels = novel_result.scalars().all()
        if not novels:
            novel = NovelDB(id=str(uuid.uuid4()), title="默认小说", genre="未分类")
            session.add(novel)
            await session.flush()
            novel_id = novel.id
        else:
            novel_id = novels[0].id

        now = datetime.now()
        world = WorldSettingDB(
            id=str(uuid.uuid4()),
            novel_id=novel_id,
            name=req.name,
            category=req.category,
            description=req.description,
            rules=req.rules,
            history=req.history,
            created_at=now,
            updated_at=now,
        )
        session.add(world)
        await session.commit()
        return {"success": True, "id": world.id}


@router.post("/settings/character", description="保存角色到数据库")
async def save_character(req: SaveCharacterRequest):
    """保存角色，供全流程编排选取"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import NovelDB, CharacterDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        novel_result = await session.execute(
            select(NovelDB).limit(1)
        )
        novels = novel_result.scalars().all()
        if not novels:
            novel = NovelDB(id=str(uuid.uuid4()), title="默认小说", genre="未分类")
            session.add(novel)
            await session.flush()
            novel_id = novel.id
        else:
            novel_id = novels[0].id

        now = datetime.now()
        char = CharacterDB(
            id=str(uuid.uuid4()),
            novel_id=novel_id,
            name=req.name,
            role=req.role,
            personality=req.personality,
            background=req.background,
            appearance=req.appearance,
            goals=req.goals,
            conflicts=req.conflicts,
            speech_pattern=req.speech_pattern,
            aliases=req.aliases or [],
            world_id=req.world_id or None,
            arc_data=req.arc_data or {},
            created_at=now,
            updated_at=now,
        )
        session.add(char)
        await session.commit()
        return {"success": True, "id": char.id}


# ── 角色 CRUD ──────────────────────────────────────────────────

@router.get("/settings/character/{character_id}", description="获取单个角色详情")
async def get_character(character_id: str):
    from ...db.database import AsyncSessionLocal
    from ...db.models import CharacterDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CharacterDB).where(CharacterDB.id == character_id))
        char = result.scalar_one_or_none()
        if not char:
            raise HTTPException(404, "角色不存在")
        return {
            "id": char.id, "name": char.name, "role": char.role,
            "personality": char.personality, "background": char.background,
            "appearance": char.appearance, "goals": char.goals,
            "conflicts": char.conflicts, "speech_pattern": char.speech_pattern,
            "aliases": char.aliases, "arc_data": char.arc_data,
            "novel_id": char.novel_id,
            "world_id": getattr(char, 'world_id', None),
            "created_at": str(char.created_at) if getattr(char, 'created_at', None) else None,
            "updated_at": str(char.updated_at) if getattr(char, 'updated_at', None) else None,
        }


@router.put("/settings/character/{character_id}", description="更新角色")
async def update_character(character_id: str, req: UpdateCharacterRequest):
    from ...db.database import AsyncSessionLocal
    from ...db.models import CharacterDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CharacterDB).where(CharacterDB.id == character_id))
        char = result.scalar_one_or_none()
        if not char:
            raise HTTPException(404, "角色不存在")
        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(char, field):
                setattr(char, field, value)
        char.updated_at = datetime.now()
        await session.commit()
        return {"success": True, "id": char.id}


@router.delete("/settings/character/{character_id}", description="删除角色")
async def delete_character(character_id: str):
    from ...db.database import AsyncSessionLocal
    from ...db.models import CharacterDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CharacterDB).where(CharacterDB.id == character_id))
        char = result.scalar_one_or_none()
        if not char:
            raise HTTPException(404, "角色不存在")
        await session.delete(char)
        await session.commit()
        return {"success": True}


# ── 世界观 CRUD ────────────────────────────────────────────────

@router.get("/settings/world/{setting_id}", description="获取单个世界观详情")
async def get_world_setting(setting_id: str):
    from ...db.database import AsyncSessionLocal
    from ...db.models import WorldSettingDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(WorldSettingDB).where(WorldSettingDB.id == setting_id))
        world = result.scalar_one_or_none()
        if not world:
            raise HTTPException(404, "世界观不存在")
        return {
            "id": world.id, "name": world.name, "category": world.category,
            "description": world.description, "rules": world.rules,
            "history": world.history, "novel_id": world.novel_id,
            "created_at": str(world.created_at) if getattr(world, 'created_at', None) else None,
            "updated_at": str(world.updated_at) if getattr(world, 'updated_at', None) else None,
        }


@router.put("/settings/world/{setting_id}", description="更新世界观")
async def update_world_setting(setting_id: str, req: UpdateWorldRequest):
    from ...db.database import AsyncSessionLocal
    from ...db.models import WorldSettingDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(WorldSettingDB).where(WorldSettingDB.id == setting_id))
        world = result.scalar_one_or_none()
        if not world:
            raise HTTPException(404, "世界观不存在")
        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(world, field):
                setattr(world, field, value)
        world.updated_at = datetime.now()
        await session.commit()
        return {"success": True, "id": world.id}


@router.delete("/settings/world/{setting_id}", description="删除世界观")
async def delete_world_setting(setting_id: str):
    from ...db.database import AsyncSessionLocal
    from ...db.models import WorldSettingDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(WorldSettingDB).where(WorldSettingDB.id == setting_id))
        world = result.scalar_one_or_none()
        if not world:
            raise HTTPException(404, "世界观不存在")
        await session.delete(world)
        await session.commit()
        return {"success": True}


@router.post("/settings/world/batch-delete", description="批量删除世界观")
async def batch_delete_world(ids: list[str]):
    from ...db.database import AsyncSessionLocal
    from ...db.models import WorldSettingDB
    from sqlalchemy import select

    deleted = 0
    async with AsyncSessionLocal() as session:
        for world_id in ids:
            result = await session.execute(select(WorldSettingDB).where(WorldSettingDB.id == world_id))
            world = result.scalar_one_or_none()
            if world:
                await session.delete(world)
                deleted += 1
        await session.commit()
        return {"success": True, "deleted": deleted}


@router.post("/settings/character/batch-delete", description="批量删除角色")
async def batch_delete_character(ids: list[str]):
    from ...db.database import AsyncSessionLocal
    from ...db.models import CharacterDB
    from sqlalchemy import select

    deleted = 0
    async with AsyncSessionLocal() as session:
        for char_id in ids:
            result = await session.execute(select(CharacterDB).where(CharacterDB.id == char_id))
            char = result.scalar_one_or_none()
            if char:
                await session.delete(char)
                deleted += 1
        await session.commit()
        return {"success": True, "deleted": deleted}