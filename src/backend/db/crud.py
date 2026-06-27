import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Any, Dict
from .models import (
    NovelDB, VolumeDB, ChapterDB, CharacterDB,
    CharacterRelationshipDB, WorldSettingDB, StyleGuideDB,
    UserFeedbackDB, AgentExecutionDB, CharacterMemoryDB
)
from ..models.schemas import (
    Novel, Volume, Chapter, Character, WorldSetting, StyleGuide,
    CreateNovelRequest, UpdateNovelRequest, CreateChapterRequest, UpdateChapterRequest,
    FeedbackType, UserFeedback
)


def generate_id() -> str:
    return str(uuid.uuid4())


class NovelCRUD:
    @staticmethod
    async def create(db: AsyncSession, request: CreateNovelRequest) -> Novel:
        novel_id = generate_id()
        db_novel = NovelDB(
            id=novel_id,
            title=request.title,
            genre=request.genre,
            target_word_count=request.target_word_count,
            current_word_count=0,
            status="planning",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(db_novel)
        await db.commit()
        await db.refresh(db_novel)
        return Novel(
            id=db_novel.id,
            title=db_novel.title,
            genre=db_novel.genre,
            target_word_count=db_novel.target_word_count,
            current_word_count=db_novel.current_word_count,
            status=db_novel.status,
            world_id=db_novel.world_id,
            created_at=db_novel.created_at,
            updated_at=db_novel.updated_at
        )

    @staticmethod
    async def get(db: AsyncSession, novel_id: str) -> Optional[Novel]:
        result = await db.execute(select(NovelDB).where(NovelDB.id == novel_id))
        db_novel = result.scalar_one_or_none()
        if db_novel:
            return Novel(
                id=db_novel.id,
                title=db_novel.title,
                genre=db_novel.genre,
                target_word_count=db_novel.target_word_count,
                current_word_count=db_novel.current_word_count,
                status=db_novel.status,
                world_id=db_novel.world_id,
                created_at=db_novel.created_at,
                updated_at=db_novel.updated_at
            )
        return None

    @staticmethod
    async def list_all(db: AsyncSession) -> List[Novel]:
        result = await db.execute(select(NovelDB).order_by(NovelDB.updated_at.desc()))
        db_novels = result.scalars().all()
        return [
            Novel(
                id=n.id,
                title=n.title,
                genre=n.genre,
                target_word_count=n.target_word_count,
                current_word_count=n.current_word_count,
                status=n.status,
                world_id=n.world_id,
                created_at=n.created_at,
                updated_at=n.updated_at
            )
            for n in db_novels
        ]

    @staticmethod
    async def update(db: AsyncSession, novel_id: str, request: UpdateNovelRequest) -> Optional[Novel]:
        result = await db.execute(select(NovelDB).where(NovelDB.id == novel_id))
        db_novel = result.scalar_one_or_none()
        if not db_novel:
            return None
        
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_novel, field, value)
        db_novel.updated_at = datetime.now()
        
        await db.commit()
        await db.refresh(db_novel)
        
        return Novel(
            id=db_novel.id,
            title=db_novel.title,
            genre=db_novel.genre,
            target_word_count=db_novel.target_word_count,
            current_word_count=db_novel.current_word_count,
            status=db_novel.status,
            world_id=db_novel.world_id,
            created_at=db_novel.created_at,
            updated_at=db_novel.updated_at
        )

    @staticmethod
    async def delete(db: AsyncSession, novel_id: str) -> bool:
        result = await db.execute(select(NovelDB).where(NovelDB.id == novel_id))
        db_novel = result.scalar_one_or_none()
        if db_novel:
            await db.delete(db_novel)
            await db.commit()
            return True
        return False


class ChapterCRUD:
    @staticmethod
    async def create(db: AsyncSession, request: CreateChapterRequest) -> Chapter:
        chapter_id = generate_id()
        db_chapter = ChapterDB(
            id=chapter_id,
            volume_id=request.volume_id,
            title=request.title,
            outline=request.outline,
            content=None,
            word_count=0,
            status="outline",
            sort_order=request.order,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(db_chapter)
        await db.commit()
        await db.refresh(db_chapter)
        return Chapter(
            id=db_chapter.id,
            volume_id=db_chapter.volume_id,
            title=db_chapter.title,
            outline=db_chapter.outline,
            content=db_chapter.content,
            word_count=db_chapter.word_count,
            status=db_chapter.status,
            characters_present=db_chapter.characters_present or [],
            locations=db_chapter.locations or [],
            foreshadowing=db_chapter.foreshadowing or [],
            callbacks=db_chapter.callbacks or [],
            order=db_chapter.sort_order,
            created_at=db_chapter.created_at,
            updated_at=db_chapter.updated_at
        )

    @staticmethod
    async def get(db: AsyncSession, chapter_id: str) -> Optional[Chapter]:
        result = await db.execute(select(ChapterDB).where(ChapterDB.id == chapter_id))
        db_chapter = result.scalar_one_or_none()
        if db_chapter:
            return Chapter(
                id=db_chapter.id,
                volume_id=db_chapter.volume_id,
                title=db_chapter.title,
                outline=db_chapter.outline,
                content=db_chapter.content,
                word_count=db_chapter.word_count,
                status=db_chapter.status,
                characters_present=db_chapter.characters_present or [],
                locations=db_chapter.locations or [],
                foreshadowing=db_chapter.foreshadowing or [],
                callbacks=db_chapter.callbacks or [],
                order=db_chapter.sort_order,
                created_at=db_chapter.created_at,
                updated_at=db_chapter.updated_at
            )
        return None

    @staticmethod
    async def list_by_novel(db: AsyncSession, novel_id: str) -> List[Chapter]:
        result = await db.execute(
            select(ChapterDB)
            .join(VolumeDB)
            .where(VolumeDB.novel_id == novel_id)
            .order_by(VolumeDB.sort_order, ChapterDB.sort_order)
        )
        db_chapters = result.scalars().all()
        return [
            Chapter(
                id=c.id,
                volume_id=c.volume_id,
                title=c.title,
                outline=c.outline,
                content=c.content,
                word_count=c.word_count,
                status=c.status,
                characters_present=c.characters_present or [],
                locations=c.locations or [],
                foreshadowing=c.foreshadowing or [],
                callbacks=c.callbacks or [],
                order=c.sort_order,
                created_at=c.created_at,
                updated_at=c.updated_at
            )
            for c in db_chapters
        ]

    @staticmethod
    async def update(db: AsyncSession, chapter_id: str, request: UpdateChapterRequest) -> Optional[Chapter]:
        result = await db.execute(select(ChapterDB).where(ChapterDB.id == chapter_id))
        db_chapter = result.scalar_one_or_none()
        if not db_chapter:
            return None
        
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_chapter, field, value)
        db_chapter.updated_at = datetime.now()
        
        if "content" in update_data and update_data["content"]:
            db_chapter.word_count = len(update_data["content"].split())
        
        await db.commit()
        await db.refresh(db_chapter)
        
        return Chapter(
            id=db_chapter.id,
            volume_id=db_chapter.volume_id,
            title=db_chapter.title,
            outline=db_chapter.outline,
            content=db_chapter.content,
            word_count=db_chapter.word_count,
            status=db_chapter.status,
            characters_present=db_chapter.characters_present or [],
            locations=db_chapter.locations or [],
            foreshadowing=db_chapter.foreshadowing or [],
            callbacks=db_chapter.callbacks or [],
            order=db_chapter.sort_order,
            created_at=db_chapter.created_at,
            updated_at=db_chapter.updated_at
        )


class CharacterCRUD:
    @staticmethod
    async def create(db: AsyncSession, novel_id: str, name: str, **kwargs) -> Character:
        char_id = generate_id()
        db_char = CharacterDB(
            id=char_id,
            novel_id=novel_id,
            name=name,
            role=kwargs.get("role", "supporting"),
            personality=kwargs.get("personality"),
            background=kwargs.get("background"),
            goals=kwargs.get("goals", []),
            conflicts=kwargs.get("conflicts", []),
            speech_pattern=kwargs.get("speech_pattern"),
            appearance=kwargs.get("appearance"),
            aliases=kwargs.get("aliases", []),
            # v6.0 角色代入式创作：结构化字段
            psychological_profile=kwargs.get("psychological_profile"),
            behavior_tags=kwargs.get("behavior_tags", []),
            relationship_webs=kwargs.get("relationship_webs", []),
            speech_fingerprint=kwargs.get("speech_fingerprint"),
            arc_data=kwargs.get("arc_data"),
            world_id=kwargs.get("world_id"),
            first_appear_chapter=kwargs.get("first_appear_chapter"),
            last_appear_chapter=kwargs.get("last_appear_chapter"),
            character_status=kwargs.get("character_status", "active"),
        )
        db.add(db_char)
        await db.commit()
        await db.refresh(db_char)
        return Character(
            id=db_char.id,
            novel_id=db_char.novel_id,
            name=db_char.name,
            aliases=db_char.aliases or [],
            role=db_char.role,
            personality=db_char.personality,
            background=db_char.background,
            goals=db_char.goals or [],
            conflicts=db_char.conflicts or [],
            speech_pattern=db_char.speech_pattern,
            appearance=db_char.appearance
        )
    
    @staticmethod
    async def update(db: AsyncSession, character_id: str, **kwargs) -> Optional[Character]:
        result = await db.execute(select(CharacterDB).where(CharacterDB.id == character_id))
        db_char = result.scalar_one_or_none()
        if not db_char:
            return None
        
        for key, value in kwargs.items():
            if hasattr(db_char, key):
                setattr(db_char, key, value)
        
        await db.commit()
        await db.refresh(db_char)
        return Character(
            id=db_char.id,
            novel_id=db_char.novel_id,
            name=db_char.name,
            aliases=db_char.aliases or [],
            role=db_char.role,
            personality=db_char.personality,
            background=db_char.background,
            goals=db_char.goals or [],
            conflicts=db_char.conflicts or [],
            speech_pattern=db_char.speech_pattern,
            appearance=db_char.appearance
        )
    
    @staticmethod
    async def delete(db: AsyncSession, character_id: str) -> bool:
        result = await db.execute(select(CharacterDB).where(CharacterDB.id == character_id))
        db_char = result.scalar_one_or_none()
        if db_char:
            await db.delete(db_char)
            await db.commit()
            return True
        return False
    
    @staticmethod
    async def list_by_novel(db: AsyncSession, novel_id: str) -> List[Character]:
        result = await db.execute(
            select(CharacterDB)
            .where(CharacterDB.novel_id == novel_id)
            .options(selectinload(CharacterDB.relationships))
        )
        db_characters = result.scalars().all()
        return [
            Character(
                id=c.id,
                novel_id=c.novel_id,
                name=c.name,
                aliases=c.aliases or [],
                role=c.role,
                personality=c.personality,
                background=c.background,
                goals=c.goals or [],
                conflicts=c.conflicts or [],
                speech_pattern=c.speech_pattern,
                appearance=c.appearance
            )
            for c in db_characters
        ]


class WorldSettingCRUD:
    @staticmethod
    async def create(db: AsyncSession, novel_id: str, name: str, category: str, **kwargs) -> WorldSetting:
        setting_id = generate_id()
        db_setting = WorldSettingDB(
            id=setting_id,
            novel_id=novel_id,
            name=name,
            category=category,
            description=kwargs.get("description"),
            rules=kwargs.get("rules", []),
            history=kwargs.get("history", []),
            # v6.0 角色代入式创作：扩展世界观结构化字段
            key_locations=kwargs.get("key_locations", []),
            factions=kwargs.get("factions", []),
            unique_appeal=kwargs.get("unique_appeal"),
        )
        db.add(db_setting)
        await db.commit()
        await db.refresh(db_setting)
        return WorldSetting(
            id=db_setting.id,
            novel_id=db_setting.novel_id,
            name=db_setting.name,
            category=db_setting.category,
            description=db_setting.description,
            rules=db_setting.rules or [],
            history=db_setting.history or []
        )
    
    @staticmethod
    async def update(db: AsyncSession, setting_id: str, **kwargs) -> Optional[WorldSetting]:
        result = await db.execute(select(WorldSettingDB).where(WorldSettingDB.id == setting_id))
        db_setting = result.scalar_one_or_none()
        if not db_setting:
            return None
        
        for key, value in kwargs.items():
            if hasattr(db_setting, key):
                setattr(db_setting, key, value)
        
        await db.commit()
        await db.refresh(db_setting)
        return WorldSetting(
            id=db_setting.id,
            novel_id=db_setting.novel_id,
            name=db_setting.name,
            category=db_setting.category,
            description=db_setting.description,
            rules=db_setting.rules or [],
            history=db_setting.history or []
        )
    
    @staticmethod
    async def delete(db: AsyncSession, setting_id: str) -> bool:
        result = await db.execute(select(WorldSettingDB).where(WorldSettingDB.id == setting_id))
        db_setting = result.scalar_one_or_none()
        if db_setting:
            await db.delete(db_setting)
            await db.commit()
            return True
        return False
    
    @staticmethod
    async def list_by_novel(db: AsyncSession, novel_id: str) -> List[WorldSetting]:
        result = await db.execute(select(WorldSettingDB).where(WorldSettingDB.novel_id == novel_id))
        db_settings = result.scalars().all()
        return [
            WorldSetting(
                id=w.id,
                novel_id=w.novel_id,
                name=w.name,
                category=w.category,
                description=w.description,
                rules=w.rules or [],
                history=w.history or []
            )
            for w in db_settings
        ]


class VolumeCRUD:
    @staticmethod
    async def create(db: AsyncSession, novel_id: str, title: str, order: int, description: Optional[str] = None) -> Volume:
        volume_id = generate_id()
        db_volume = VolumeDB(
            id=volume_id,
            novel_id=novel_id,
            title=title,
            description=description,
            word_count=0,
            sort_order=order
        )
        db.add(db_volume)
        await db.commit()
        await db.refresh(db_volume)
        return Volume(
            id=db_volume.id,
            novel_id=db_volume.novel_id,
            title=db_volume.title,
            description=db_volume.description,
            word_count=db_volume.word_count,
            order=db_volume.sort_order
        )
    
    @staticmethod
    async def list_by_novel(db: AsyncSession, novel_id: str) -> List[Volume]:
        result = await db.execute(
            select(VolumeDB).where(VolumeDB.novel_id == novel_id).order_by(VolumeDB.sort_order)
        )
        db_volumes = result.scalars().all()
        return [
            Volume(
                id=v.id,
                novel_id=v.novel_id,
                title=v.title,
                description=v.description,
                word_count=v.word_count,
                order=v.sort_order
            )
            for v in db_volumes
        ]
    
    @staticmethod
    async def get(db: AsyncSession, volume_id: str) -> Optional[Volume]:
        result = await db.execute(select(VolumeDB).where(VolumeDB.id == volume_id))
        db_volume = result.scalar_one_or_none()
        if db_volume:
            return Volume(
                id=db_volume.id,
                novel_id=db_volume.novel_id,
                title=db_volume.title,
                description=db_volume.description,
                word_count=db_volume.word_count,
                order=db_volume.sort_order
            )
        return None
    
    @staticmethod
    async def delete(db: AsyncSession, volume_id: str) -> bool:
        result = await db.execute(select(VolumeDB).where(VolumeDB.id == volume_id))
        db_volume = result.scalar_one_or_none()
        if db_volume:
            await db.delete(db_volume)
            await db.commit()
            return True
        return False


class UserFeedbackCRUD:
    @staticmethod
    async def create(db: AsyncSession, feedback: UserFeedback) -> UserFeedback:
        feedback_id = feedback.id or generate_id()
        db_feedback = UserFeedbackDB(
            id=feedback_id,
            novel_id=feedback.novel_id,
            chapter_id=feedback.chapter_id,
            feedback_type=feedback.feedback_type.value,
            before_text=feedback.before_text,
            after_text=feedback.after_text,
            metadata=feedback.metadata
        )
        db.add(db_feedback)
        await db.commit()
        await db.refresh(db_feedback)
        return UserFeedback(
            id=db_feedback.id,
            novel_id=db_feedback.novel_id,
            chapter_id=db_feedback.chapter_id,
            feedback_type=FeedbackType(db_feedback.feedback_type),
            before_text=db_feedback.before_text,
            after_text=db_feedback.after_text,
            metadata=db_feedback.metadata,
            created_at=db_feedback.created_at
        )
    
    @staticmethod
    async def list_by_novel(db: AsyncSession, novel_id: str) -> List[UserFeedback]:
        result = await db.execute(
            select(UserFeedbackDB).where(UserFeedbackDB.novel_id == novel_id).order_by(UserFeedbackDB.created_at.desc())
        )
        db_feedbacks = result.scalars().all()
        return [
            UserFeedback(
                id=f.id,
                novel_id=f.novel_id,
                chapter_id=f.chapter_id,
                feedback_type=FeedbackType(f.feedback_type),
                before_text=f.before_text,
                after_text=f.after_text,
                metadata=f.metadata,
                created_at=f.created_at
            )
            for f in db_feedbacks
        ]


class StyleGuideCRUD:
    @staticmethod
    async def create(db: AsyncSession, novel_id: str) -> StyleGuide:
        guide_id = generate_id()
        db_guide = StyleGuideDB(
            id=guide_id,
            novel_id=novel_id
        )
        db.add(db_guide)
        await db.commit()
        await db.refresh(db_guide)
        return StyleGuide(
            id=db_guide.id,
            novel_id=db_guide.novel_id,
            vocabulary_preference=db_guide.vocabulary_preference or [],
            sentence_patterns=db_guide.sentence_patterns or [],
            pacing_preference=db_guide.pacing_preference,
            tone=db_guide.tone,
            anti_patterns=db_guide.anti_patterns or [],
            reference_works=db_guide.reference_works or [],
            updated_at=db_guide.updated_at
        )
    
    @staticmethod
    async def get_by_novel(db: AsyncSession, novel_id: str) -> Optional[StyleGuide]:
        result = await db.execute(select(StyleGuideDB).where(StyleGuideDB.novel_id == novel_id))
        db_guide = result.scalar_one_or_none()
        if db_guide:
            return StyleGuide(
                id=db_guide.id,
                novel_id=db_guide.novel_id,
                vocabulary_preference=db_guide.vocabulary_preference or [],
                sentence_patterns=db_guide.sentence_patterns or [],
                pacing_preference=db_guide.pacing_preference,
                tone=db_guide.tone,
                anti_patterns=db_guide.anti_patterns or [],
                reference_works=db_guide.reference_works or [],
                updated_at=db_guide.updated_at
            )
        return None
    
    @staticmethod
    async def update(db: AsyncSession, guide_id: str, **kwargs) -> Optional[StyleGuide]:
        result = await db.execute(select(StyleGuideDB).where(StyleGuideDB.id == guide_id))
        db_guide = result.scalar_one_or_none()
        if not db_guide:
            return None
        
        for key, value in kwargs.items():
            if hasattr(db_guide, key):
                setattr(db_guide, key, value)
        db_guide.updated_at = datetime.now()
        
        await db.commit()
        await db.refresh(db_guide)
        return StyleGuide(
            id=db_guide.id,
            novel_id=db_guide.novel_id,
            vocabulary_preference=db_guide.vocabulary_preference or [],
            sentence_patterns=db_guide.sentence_patterns or [],
            pacing_preference=db_guide.pacing_preference,
            tone=db_guide.tone,
            anti_patterns=db_guide.anti_patterns or [],
            reference_works=db_guide.reference_works or [],
            updated_at=db_guide.updated_at
        )


class CharacterMemoryCRUD:
    """角色经历记忆链CRUD — 保证人物行为一致性的持久化层"""

    @staticmethod
    async def create(db: AsyncSession, novel_id: str, character_id: str, chapter_idx: int, **kwargs) -> Dict:
        memory_id = generate_id()
        db_memory = CharacterMemoryDB(
            id=memory_id,
            novel_id=novel_id,
            character_id=character_id,
            chapter_idx=chapter_idx,
            experienced_events=kwargs.get("experienced_events"),
            emotional_trajectory=kwargs.get("emotional_trajectory"),
            cognition_updates=kwargs.get("cognition_updates", []),
            personality_shifts=kwargs.get("personality_shifts"),
            decisions_made=kwargs.get("decisions_made", []),
            information_gained=kwargs.get("information_gained", []),
            relationships_change=kwargs.get("relationships_change"),
        )
        db.add(db_memory)
        await db.commit()
        await db.refresh(db_memory)
        return {
            "id": db_memory.id,
            "novel_id": db_memory.novel_id,
            "character_id": db_memory.character_id,
            "chapter_idx": db_memory.chapter_idx,
            "experienced_events": db_memory.experienced_events,
            "emotional_trajectory": db_memory.emotional_trajectory,
            "cognition_updates": db_memory.cognition_updates or [],
            "personality_shifts": db_memory.personality_shifts,
            "decisions_made": db_memory.decisions_made or [],
            "information_gained": db_memory.information_gained or [],
            "relationships_change": db_memory.relationships_change,
            "created_at": db_memory.created_at,
        }

    @staticmethod
    async def list_by_character(db: AsyncSession, character_id: str, up_to_chapter: int = None) -> List[Dict]:
        """获取角色的经历记忆链，可限制到某章之前"""
        stmt = select(CharacterMemoryDB).where(
            CharacterMemoryDB.character_id == character_id
        ).order_by(CharacterMemoryDB.chapter_idx)
        if up_to_chapter is not None:
            stmt = stmt.where(CharacterMemoryDB.chapter_idx < up_to_chapter)
        result = await db.execute(stmt)
        db_memories = result.scalars().all()
        return [
            {
                "chapter_idx": m.chapter_idx,
                "experienced_events": m.experienced_events,
                "emotional_trajectory": m.emotional_trajectory,
                "cognition_updates": m.cognition_updates or [],
                "personality_shifts": m.personality_shifts,
                "decisions_made": m.decisions_made or [],
                "information_gained": m.information_gained or [],
                "relationships_change": m.relationships_change,
            }
            for m in db_memories
        ]

    @staticmethod
    async def delete_by_character(db: AsyncSession, character_id: str) -> bool:
        result = await db.execute(
            select(CharacterMemoryDB).where(CharacterMemoryDB.character_id == character_id)
        )
        db_memories = result.scalars().all()
        for m in db_memories:
            await db.delete(m)
        await db.commit()
        return len(db_memories) > 0
