"""
小说管理端点 — /api/novels
"""
import os
import glob
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from .deps import _PROJECT_ROOT
from .models import CreateNovelRequest, ChapterUpdateRequest

router = APIRouter(prefix="/api/novels", tags=["小说"])


@router.get("")
async def list_novels():
    """获取所有已保存的小说列表（从数据库读取）"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import NovelDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NovelDB).order_by(NovelDB.updated_at.desc())
        )
        novels = result.scalars().all()
        return {
            "novels": [
                {
                    "id": n.id,
                    "title": n.title,
                    "genre": n.genre,
                    "status": n.status,
                    "current_word_count": n.current_word_count,
                    "target_word_count": n.target_word_count,
                    "created_at": str(n.created_at) if n.created_at else "",
                    "updated_at": str(n.updated_at) if n.updated_at else "",
                }
                for n in novels
            ]
        }


@router.post("", description="创建新小说（含初始卷）")
async def create_novel(req: CreateNovelRequest):
    """创建新小说并自动创建初始卷"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import NovelDB, VolumeDB

    async with AsyncSessionLocal() as session:
        novel_id = uuid.uuid4().hex[:10]
        now = datetime.now()

        novel = NovelDB(
            id=novel_id,
            title=req.title.strip(),
            genre=req.genre,
            status="planning",
            current_word_count=0,
            created_at=now,
            updated_at=now,
        )
        session.add(novel)

        volume = VolumeDB(
            id=f"{novel_id}_vol1",
            novel_id=novel_id,
            title="第一卷",
            description=req.genre,
            sort_order=1,
        )
        session.add(volume)
        await session.commit()

        return {
            "id": novel.id,
            "title": novel.title,
            "genre": novel.genre,
            "status": novel.status,
            "current_word_count": 0,
            "target_word_count": None,
            "created_at": str(now),
            "updated_at": str(now),
        }


@router.get("/{novel_id}")
async def get_novel(novel_id: str):
    """获取单部小说详情（含章节内容，从数据库读取）"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import NovelDB, VolumeDB, ChapterDB, CharacterDB, WorldSettingDB, StyleGuideDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        novel = await session.get(NovelDB, novel_id)
        if not novel:
            raise HTTPException(404, f"未找到小说: {novel_id}")

        ch_result = await session.execute(
            select(ChapterDB).where(ChapterDB.volume_id.like(f"{novel_id}_vol%"))
            .order_by(ChapterDB.sort_order)
        )
        chapters = ch_result.scalars().all()

        char_result = await session.execute(
            select(CharacterDB).where(CharacterDB.novel_id == novel_id)
        )
        characters = char_result.scalars().all()

        world_result = await session.execute(
            select(WorldSettingDB).where(WorldSettingDB.novel_id == novel_id)
        )
        worlds = world_result.scalars().all()

        style_result = await session.execute(
            select(StyleGuideDB).where(StyleGuideDB.novel_id == novel_id)
        )
        styles = style_result.scalars().all()

        return {
            "novel": {
                "id": novel.id,
                "title": novel.title,
                "genre": novel.genre,
                "status": novel.status,
                "current_word_count": novel.current_word_count,
            },
            "chapters": [
                {
                    "id": ch.id,
                    "title": ch.title,
                    "outline": ch.outline,
                    "content": ch.content,
                    "word_count": ch.word_count,
                    "status": ch.status,
                }
                for ch in chapters
            ],
            "characters": [
                {
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality,
                    "background": c.background,
                }
                for c in characters
            ],
            "world_settings": [
                {
                    "name": w.name,
                    "category": w.category,
                    "description": w.description,
                    "rules": w.rules,
                }
                for w in worlds
            ],
            "style_guides": [
                {
                    "tone": s.tone,
                    "pacing_preference": s.pacing_preference,
                }
                for s in styles
            ],
        }


@router.get("/{novel_id}/chapters/{chapter_id}/content")
async def get_chapter_content(novel_id: str, chapter_id: str):
    """获取单个章节的完整内容（纯文本）"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import ChapterDB, VolumeDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChapterDB).where(ChapterDB.id == chapter_id)
        )
        chapter = result.scalar_one_or_none()
        if not chapter:
            raise HTTPException(404, f"未找到章节: {chapter_id}")

        vol_result = await session.execute(
            select(VolumeDB).where(VolumeDB.id == chapter.volume_id)
        )
        volume = vol_result.scalar_one_or_none()
        if not volume or volume.novel_id != novel_id:
            raise HTTPException(404, f"章节不属于该小说")

        return {
            "id": chapter.id,
            "title": chapter.title,
            "content": chapter.content or "",
            "word_count": chapter.word_count,
            "status": chapter.status,
            "outline": chapter.outline,
        }


@router.put("/{novel_id}/chapters/{chapter_id}")
async def update_chapter(novel_id: str, chapter_id: str, req: ChapterUpdateRequest):
    """更新章节内容"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import ChapterDB, NovelDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        chapter = await session.get(ChapterDB, chapter_id)
        if not chapter:
            raise HTTPException(404, f"未找到章节: {chapter_id}")

        chapter.content = req.content
        chapter.word_count = len(req.content)
        chapter.status = "edited"
        chapter.updated_at = datetime.now()

        novel = await session.get(NovelDB, novel_id)
        if novel:
            ch_result = await session.execute(
                select(ChapterDB).where(ChapterDB.volume_id.like(f"{novel_id}_vol%"))
            )
            all_chapters = ch_result.scalars().all()
            novel.current_word_count = sum(len(ch.content or "") for ch in all_chapters)
            novel.updated_at = datetime.now()

        await session.commit()
        return {"success": True, "word_count": len(req.content)}


@router.delete("/{novel_id}")
async def delete_novel(novel_id: str):
    """删除小说及其所有关联数据"""
    from ...db.database import AsyncSessionLocal
    from ...db.models import NovelDB, VolumeDB, ChapterDB, CharacterDB, WorldSettingDB, StyleGuideDB, CharacterRelationshipDB
    from sqlalchemy import select, delete

    async with AsyncSessionLocal() as session:
        novel = await session.get(NovelDB, novel_id)
        if not novel:
            raise HTTPException(404, f"未找到小说: {novel_id}")

        char_result = await session.execute(
            select(CharacterDB).where(CharacterDB.novel_id == novel_id)
        )
        for char in char_result.scalars().all():
            await session.execute(
                delete(CharacterRelationshipDB).where(CharacterRelationshipDB.character_id == char.id)
            )

        vol_result = await session.execute(
            select(VolumeDB).where(VolumeDB.novel_id == novel_id)
        )
        for vol in vol_result.scalars().all():
            await session.execute(
                delete(ChapterDB).where(ChapterDB.volume_id == vol.id)
            )

        await session.execute(delete(CharacterDB).where(CharacterDB.novel_id == novel_id))
        await session.execute(delete(WorldSettingDB).where(WorldSettingDB.novel_id == novel_id))
        await session.execute(delete(StyleGuideDB).where(StyleGuideDB.novel_id == novel_id))
        await session.execute(delete(VolumeDB).where(VolumeDB.novel_id == novel_id))

        await session.delete(novel)
        await session.commit()

        output_dir = os.path.join(_PROJECT_ROOT, "output")
        for f in glob.glob(os.path.join(output_dir, f"*_{novel_id}.md")):
            try:
                os.remove(f)
            except Exception:
                pass

        return {"success": True, "message": f"小说 {novel_id} 已删除"}