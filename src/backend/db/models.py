import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.types import TypeDecorator, TEXT
from .database import Base


class JSONType(TypeDecorator):
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


class NovelDB(Base):
    __tablename__ = "novels"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    genre = Column(String)
    target_word_count = Column(Integer)
    current_word_count = Column(Integer, default=0)
    status = Column(String, default="planning", index=True)
    # world_id 与 world_settings.novel_id 构成循环引用，仅加索引避免 create_all 顺序问题
    world_id = Column(String, index=True)
    style_guide_id = Column(String)
    collaboration_mode = Column(String, default="semi_auto")
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now)

    volumes = relationship("VolumeDB", back_populates="novel", cascade="all, delete-orphan")
    characters = relationship("CharacterDB", back_populates="novel", cascade="all, delete-orphan")
    world_settings = relationship("WorldSettingDB", back_populates="novel", cascade="all, delete-orphan")
    style_guides = relationship("StyleGuideDB", back_populates="novel", cascade="all, delete-orphan")


class VolumeDB(Base):
    __tablename__ = "volumes"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    word_count = Column(Integer, default=0)
    sort_order = Column(Integer)

    novel = relationship("NovelDB", back_populates="volumes")
    chapters = relationship("ChapterDB", back_populates="volume", cascade="all, delete-orphan")


class ChapterDB(Base):
    __tablename__ = "chapters"

    id = Column(String, primary_key=True, index=True)
    volume_id = Column(String, ForeignKey("volumes.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_chapter_id = Column(String, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String, nullable=False)
    outline = Column(Text)
    content = Column(Text)
    word_count = Column(Integer, default=0)
    status = Column(String, default="outline", index=True)
    version = Column(Integer, default=1)
    characters_present = Column(MutableList.as_mutable(JSONType), default=list)
    locations = Column(MutableList.as_mutable(JSONType), default=list)
    foreshadowing = Column(MutableList.as_mutable(JSONType), default=list)
    callbacks = Column(MutableList.as_mutable(JSONType), default=list)
    sort_order = Column(Integer)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now)

    volume = relationship("VolumeDB", back_populates="chapters")


class ChapterVersionDB(Base):
    __tablename__ = "chapter_versions"

    id = Column(String, primary_key=True, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content = Column(Text)
    diff = Column(Text)
    note = Column(Text)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.now)


class AgentConfigDB(Base):
    __tablename__ = "agent_configs"

    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    agent_type = Column(String, nullable=False)
    capabilities = Column(MutableList.as_mutable(JSONType), default=list)
    config = Column(JSONType)
    is_enabled = Column(Integer, default=1)
    version = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class CharacterDB(Base):
    __tablename__ = "characters"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    aliases = Column(MutableList.as_mutable(JSONType), default=list)
    role = Column(String, index=True)
    personality = Column(Text)
    background = Column(Text)
    goals = Column(MutableList.as_mutable(JSONType), default=list)
    conflicts = Column(MutableList.as_mutable(JSONType), default=list)
    speech_pattern = Column(Text)
    appearance = Column(Text)
    arc_data = Column(JSONType)
    world_id = Column(String, ForeignKey("world_settings.id", ondelete="SET NULL"), nullable=True, index=True)
    # v6.0 角色代入式创作：扩展结构化字段，保证人物行为一致性
    psychological_profile = Column(JSONType)   # 心理画像: {core_drive, inner_conflict, decision_pattern, breaking_point}
    behavior_tags = Column(MutableList.as_mutable(JSONType), default=list)  # 行为标签: ["紧张时转笔", "决策前沉默3秒"]
    relationship_webs = Column(MutableList.as_mutable(JSONType), default=list)  # 关系网: [{target, type, dynamic}]
    speech_fingerprint = Column(JSONType)      # 语言指纹: {pattern, catchphrase, pace, taboo_words}
    first_appear_chapter = Column(Integer)     # 首次出场章节
    last_appear_chapter = Column(Integer)      # 最后出场章节（null=全程在场）
    character_status = Column(String, default="active")  # active/exited/dead
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    novel = relationship("NovelDB", back_populates="characters")
    relationships = relationship("CharacterRelationshipDB", back_populates="character",
                                 cascade="all, delete-orphan",
                                 foreign_keys="[CharacterRelationshipDB.character_id]")
    memories = relationship("CharacterMemoryDB", back_populates="character",
                            cascade="all, delete-orphan",
                            foreign_keys="[CharacterMemoryDB.character_id]")


class CharacterRelationshipDB(Base):
    __tablename__ = "character_relationships"

    id = Column(String, primary_key=True, index=True)
    character_id = Column(String, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    target_character_id = Column(String, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String)
    description = Column(Text)

    character = relationship("CharacterDB", back_populates="relationships",
                          foreign_keys=[character_id])


class WorldSettingDB(Base):
    __tablename__ = "world_settings"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String)
    description = Column(Text)
    rules = Column(MutableList.as_mutable(JSONType), default=list)
    history = Column(JSONType)
    # v6.0 角色代入式创作：扩展世界观结构化字段
    key_locations = Column(MutableList.as_mutable(JSONType), default=list)  # 关键地点: [{name, sensory, function}]
    factions = Column(MutableList.as_mutable(JSONType), default=list)       # 势力格局: [{name, goal, conflict_with}]
    unique_appeal = Column(String)  # 独特卖点
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    novel = relationship("NovelDB", back_populates="world_settings")


class CharacterMemoryDB(Base):
    """角色经历记忆链 — 保证人物行为一致性的核心数据结构

    记录角色在每章经历的所有重要事件，使角色后续行为基于其过往经历
    形成的认知和性格变化，而非"失忆"状态。
    """
    __tablename__ = "character_memories"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id = Column(String, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_idx = Column(Integer, index=True, nullable=False)
    # 角色经历记忆（非互动记录，是角色自己的经历）
    experienced_events = Column(Text)              # 该角色在此章经历的所有重要事件（第一人称视角记录）
    emotional_trajectory = Column(String)          # 情绪变化轨迹（如"平静→震惊→愤怒→释然"）
    cognition_updates = Column(MutableList.as_mutable(JSONType), default=list)   # 认知更新：新获得的认知/信念改变
    personality_shifts = Column(Text)               # 性格微调：因此章经历产生的性格变化
    decisions_made = Column(MutableList.as_mutable(JSONType), default=list)      # 该角色在此章做出的关键决策
    information_gained = Column(MutableList.as_mutable(JSONType), default=list)  # 该角色在此章获得的关键信息
    relationships_change = Column(JSONType)         # 关系变化（该角色对他人看法的改变）
    created_at = Column(DateTime, default=datetime.now)

    character = relationship("CharacterDB", back_populates="memories",
                             foreign_keys=[character_id])


class StyleGuideDB(Base):
    __tablename__ = "style_guides"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    vocabulary_preference = Column(MutableList.as_mutable(JSONType), default=list)
    sentence_patterns = Column(MutableList.as_mutable(JSONType), default=list)
    pacing_preference = Column(String)
    tone = Column(String)
    anti_patterns = Column(MutableList.as_mutable(JSONType), default=list)
    reference_works = Column(MutableList.as_mutable(JSONType), default=list)
    updated_at = Column(DateTime, default=datetime.now)

    novel = relationship("NovelDB", back_populates="style_guides")


class UserFeedbackDB(Base):
    __tablename__ = "user_feedback"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    feedback_type = Column(String, index=True)
    before_text = Column(Text)
    after_text = Column(Text)
    feedback_metadata = Column("metadata", JSONType)
    created_at = Column(DateTime, default=datetime.now, index=True)


class AgentExecutionDB(Base):
    __tablename__ = "agent_executions"

    id = Column(String, primary_key=True, index=True)
    # 执行记录可能来自无小说上下文的独立 agent 调用，故不强制外键，仅建索引
    novel_id = Column(String, nullable=False, index=True)
    agent_type = Column(String)
    task_type = Column(String)
    input_summary = Column(Text)
    output_summary = Column(Text)
    token_usage = Column(Integer)
    error_log = Column(Text)
    status = Column(String, index=True)
    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.now, index=True)


class LLMConfigDB(Base):
    """多模型配置 — 用户可保存多套LLM配置，AI生成时选择"""
    __tablename__ = "llm_configs"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)           # 用户自定义名称，如"中国移动MAAS"
    provider = Column(String, nullable=False)        # mock/openai/deepseek/custom_openai...
    api_key = Column(String, default="")              # API密钥
    model = Column(String, default="")                # 模型名
    api_base = Column(String, default="")             # 自定义API地址
    is_default = Column(Integer, default=0)           # 是否默认配置
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class AgentPromptDB(Base):
    """Agent Prompt 库 — 持久化 6 个 Skill Agent 的优质提示词

    - novel_id = None 表示"通用模板"（所有小说可复用）
    - novel_id = <id> 表示"该小说专属"的 prompt 变体
    - is_active = 1 表示当前被 Agent 读取使用的版本
    """
    __tablename__ = "agent_prompts"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, index=True, nullable=True)   # NULL = 通用模板
    agent_type = Column(String, index=True, nullable=False)  # story_architect/world/character/opening_hook/draft/style_editor
    depth_level = Column(Integer, default=1)                 # 0=SKELETON, 1=DETAIL, 2=POLISH
    prompt_type = Column(String, default="system")           # system | user
    title = Column(String, default="")                        # 人类可读的标题
    content = Column(Text, nullable=False)                    # prompt 正文
    quality_score = Column(Integer, default=0)                # 用户/系统打分 0-100
    usage_count = Column(Integer, default=0)                  # 被引用次数
    is_active = Column(Integer, default=0)                    # 1=当前使用的版本
    meta_info = Column(JSONType, default=dict)                # {loop_index, platform, theme, notes...}
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class ChapterContinuityDB(Base):
    """章节衔接记录 — 记录每章结尾的结构化钩子，供下章开头强制衔接使用"""
    __tablename__ = "chapter_continuity"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_idx = Column(Integer, index=True, nullable=False)
    chapter_title = Column(String, default="")
    ending_text = Column(Text)                              # 章末原文（最后 500 字）
    scene = Column(JSONType, default=dict)                  # {location, time, atmosphere}
    character_states = Column(JSONType, default=list)       # [{name, status, action}]
    unresolved = Column(JSONType, default=list)             # 未解决的情节/悬念/任务
    tension_points = Column(JSONType, default=list)         # 张力点/钩子
    continuity_score = Column(Integer, default=7)           # 用户评分 1-10
    user_notes = Column(Text, default="")                   # 用户反馈/备注
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


# v5.3: 编排器运行记录 — 持久化工作流状态，支持暂停/恢复/重启
class OrchestratorRunDB(Base):
    __tablename__ = "orchestrator_runs"

    id = Column(String, primary_key=True, index=True)
    novel_id = Column(String, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    theme = Column(String, nullable=False)
    tone = Column(String, default="史诗")
    chapter_count = Column(Integer, default=10)
    platform = Column(String, default="番茄")
    state_json = Column(Text)  # 完整 OrchestratorState JSON 快照
    current_loop = Column(Integer, default=0)
    depth_level = Column(Integer, default=0)
    current_stage = Column(String, default="planning")
    completed_stages = Column(MutableList.as_mutable(JSONType), default=list)
    status = Column(String, default="running", index=True)  # running/paused/completed/failed
    error_log = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
