from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class NovelStatus(str, Enum):
    PLANNING = "planning"
    WRITING = "writing"
    COMPLETED = "completed"


class ChapterStatus(str, Enum):
    OUTLINE = "outline"
    DRAFT = "draft"
    EDITED = "edited"
    COMPLETED = "completed"


class CollaborationMode(str, Enum):
    AUTO = "auto"
    SEMI_AUTO = "semi_auto"
    MANUAL = "manual"


class Relationship(BaseModel):
    target_character_id: str
    relationship_type: str
    description: str


class CharacterArc(BaseModel):
    start_state: str
    mid_state: str
    end_state: str
    key_events: List[str]


class TimelineEvent(BaseModel):
    date: str
    event: str
    impact: str


class Location(BaseModel):
    name: str
    description: str
    coordinates: Optional[str] = None


class Faction(BaseModel):
    name: str
    description: str
    members: List[str]


class MagicSystem(BaseModel):
    name: str
    rules: List[str]
    power_levels: List[str]


class Novel(BaseModel):
    id: str
    title: str
    genre: Optional[str] = None
    target_word_count: Optional[int] = None
    current_word_count: int = 0
    status: NovelStatus = NovelStatus.PLANNING
    world_id: Optional[str] = None
    style_guide_id: Optional[str] = None
    volumes: Optional[List[object]] = None
    characters: Optional[List[object]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Volume(BaseModel):
    id: str
    novel_id: str
    title: str
    description: Optional[str] = None
    word_count: int = 0
    order: int


class Chapter(BaseModel):
    id: str
    volume_id: str
    title: str
    outline: Optional[str] = None
    content: Optional[str] = None
    word_count: int = 0
    status: ChapterStatus = ChapterStatus.OUTLINE
    characters_present: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    foreshadowing: List[str] = Field(default_factory=list)
    callbacks: List[str] = Field(default_factory=list)
    order: int
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Character(BaseModel):
    id: str
    novel_id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    role: str = "supporting"
    personality: Optional[str] = None
    background: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    arc: Optional[CharacterArc] = None
    relationships: List[Relationship] = Field(default_factory=list)
    speech_pattern: Optional[str] = None
    appearance: Optional[str] = None


class WorldSetting(BaseModel):
    id: str
    novel_id: str
    name: str
    category: str
    description: Optional[str] = None
    rules: List[str] = Field(default_factory=list)
    history: List[TimelineEvent] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    factions: List[Faction] = Field(default_factory=list)
    magic_system: Optional[MagicSystem] = None


class StyleGuide(BaseModel):
    id: str
    novel_id: str
    vocabulary_preference: List[str] = Field(default_factory=list)
    sentence_patterns: List[str] = Field(default_factory=list)
    pacing_preference: Optional[str] = None
    tone: Optional[str] = None
    anti_patterns: List[str] = Field(default_factory=list)
    reference_works: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.now)


class Context(BaseModel):
    summaries: List[str] = Field(default_factory=list)
    characters: List[str] = Field(default_factory=list)
    world: List[str] = Field(default_factory=list)
    foreshadowing: List[str] = Field(default_factory=list)


class CreateNovelRequest(BaseModel):
    title: str
    genre: str
    target_word_count: int


class UpdateNovelRequest(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    target_word_count: Optional[int] = None
    status: Optional[NovelStatus] = None


class CreateChapterRequest(BaseModel):
    volume_id: str
    title: str
    order: int
    outline: Optional[str] = None


class UpdateChapterRequest(BaseModel):
    title: Optional[str] = None
    outline: Optional[str] = None
    content: Optional[str] = None
    status: Optional[ChapterStatus] = None


class OutlineRequest(BaseModel):
    theme: str
    tone: Optional[str] = None
    chapter_count: Optional[int] = 10


class DraftRequest(BaseModel):
    chapter_id: str
    additional_context: Optional[str] = None


class EditRequest(BaseModel):
    chapter_id: str
    instructions: Optional[str] = None


class ContinueRequest(BaseModel):
    chapter_id: str
    word_count: Optional[int] = 500


class FeedbackType(str, Enum):
    STYLE_EDIT = "style_edit"
    CHARACTER_EDIT = "character_edit"
    PLOT_EDIT = "plot_edit"
    DELETION = "deletion"
    LIKE = "like"


class FeedbackRequest(BaseModel):
    chapter_id: Optional[str] = None
    feedback_type: FeedbackType
    before_text: Optional[str] = None
    after_text: Optional[str] = None
    metadata: Optional[dict] = None


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    EPUB = "epub"
    DOCX = "docx"


class ExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.MARKDOWN
    include_outline: bool = True


class ExportResult(BaseModel):
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None


class Outline(BaseModel):
    theme: str
    tone: str
    volumes: List[Volume]


class DraftResult(BaseModel):
    success: bool
    content: Optional[str] = None
    word_count: int = 0
    warning: Optional[str] = None


class EditResult(BaseModel):
    success: bool
    edited_content: Optional[str] = None
    changes_count: int = 0


class ContinueResult(BaseModel):
    success: bool
    new_content: Optional[str] = None
    word_count: int = 0


class UserFeedback(BaseModel):
    id: Optional[str] = None
    novel_id: str
    chapter_id: Optional[str] = None
    feedback_type: FeedbackType
    before_text: Optional[str] = None
    after_text: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.now)


class NovelSummary(BaseModel):
    id: str
    title: str
    genre: str
    status: NovelStatus
    current_word_count: int
    target_word_count: int
    updated_at: datetime
