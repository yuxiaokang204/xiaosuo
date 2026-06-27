import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from dotenv import load_dotenv

# load_dotenv 需要显式指定 .env 路径（uvicorn 子进程的 cwd 可能不是项目根目录）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_env_path = os.path.join(_PROJECT_ROOT, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./novel_agent.db")

# SQL 回显默认关闭，避免生产日志噪音/性能损耗；需要调试时设置 SQL_ECHO=true
_SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes")

engine = create_async_engine(
    DATABASE_URL,
    echo=_SQL_ECHO,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ORM 基类
Base = declarative_base()


# ────────────────────────────────────────────────────────
# 数据库初始化与迁移
# ────────────────────────────────────────────────────────


async def _add_column_if_missing(conn, table: str, column: str, col_type: str):
    """如果列不存在则添加（幂等操作）"""
    try:
        result = await conn.execute(
            text(f"PRAGMA table_info({table})")
        )
        existing = [row[1] for row in result.fetchall()]
        if column not in existing:
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
            await conn.execute(text(sql))
            print(f"[DB] ✅ 已添加列: {table}.{column}")
    except Exception as e:
        print(f"[DB] ⚠️ 添加列失败 {table}.{column}: {e}")


async def _migrate_db(conn):
    """执行数据库结构迁移（幂等操作）"""
    result = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    existing_tables = {row[0] for row in result.fetchall()}

    # ── 列迁移（v2.0 → v3.0）──
    column_migrations = {
        "novels": [
            ("target_word_count", "INTEGER DEFAULT 0"),
            ("style_guide_id", "TEXT"),
            ("collaboration_mode", "TEXT DEFAULT 'semi_auto'"),
        ],
        "chapters": [
            ("parent_chapter_id", "TEXT"),
            ("version", "INTEGER DEFAULT 1"),
            ("characters_present", "TEXT"),
            ("locations", "TEXT"),
            ("foreshadowing", "TEXT"),
            ("callbacks", "TEXT"),
        ],
        "agent_configs": [
            ("is_enabled", "INTEGER DEFAULT 1"),
            ("version", "TEXT"),
        ],
    }
    for table, columns in column_migrations.items():
        if table in existing_tables:
            for col_name, col_type in columns:
                await _add_column_if_missing(conn, table, col_name, col_type)

    # ── 列迁移（v3.0 → v4.0）──
    v4_columns = {
        "novels": [
            ("platform", "TEXT DEFAULT '番茄'"),
        ],
    }
    for table, columns in v4_columns.items():
        if table in existing_tables:
            for col_name, col_type in columns:
                await _add_column_if_missing(conn, table, col_name, col_type)

    # ── 列迁移（v5.3 → v6.0）──
    v6_char_columns = [
        ("psychological_profile", "TEXT"),
        ("behavior_tags", "TEXT"),
        ("relationship_webs", "TEXT"),
        ("speech_fingerprint", "TEXT"),
        ("first_appear_chapter", "INTEGER"),
        ("last_appear_chapter", "INTEGER"),
        ("character_status", "TEXT DEFAULT 'active'"),
    ]
    if "characters" in existing_tables:
        for col_name, col_type in v6_char_columns:
            await _add_column_if_missing(conn, "characters", col_name, col_type)

    v6_world_columns = [
        ("key_locations", "TEXT"),
        ("factions", "TEXT"),
        ("unique_appeal", "TEXT"),
    ]
    if "world_settings" in existing_tables:
        for col_name, col_type in v6_world_columns:
            await _add_column_if_missing(conn, "world_settings", col_name, col_type)

    # ── 创建索引 ──
    index_specs = [
        ("ix_novels_created_at", "novels", "created_at"),
        ("ix_novels_status", "novels", "status"),
        ("ix_chapters_novel_id", "chapters", "novel_id"),
        ("ix_chapters_chapter_idx", "chapters", "chapter_idx"),
        ("ix_world_settings_novel_id", "world_settings", "novel_id"),
        ("ix_characters_novel_id", "characters", "novel_id"),
        ("ix_llm_configs_is_default", "llm_configs", "is_default"),
        ("ix_agent_configs_agent_type", "agent_configs", "agent_type"),
        ("ix_agent_prompts_agent_type", "agent_prompts", "agent_type"),
        ("ix_agent_prompts_novel_id", "agent_prompts", "novel_id"),
        ("ix_chapter_continuity_novel_id", "chapter_continuity", "novel_id"),
        ("ix_chapter_continuity_chapter_idx", "chapter_continuity", "chapter_idx"),
        ("ix_orchestrator_runs_novel_id", "orchestrator_runs", "novel_id"),
        ("ix_orchestrator_runs_status", "orchestrator_runs", "status"),
        ("ix_character_memories_novel_id", "character_memories", "novel_id"),
        ("ix_character_memories_character_name", "character_memories", "character_name"),
    ]
    for idx_name, table, column in index_specs:
        try:
            await conn.execute(
                text(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})')
            )
        except Exception as e:
            print(f"[DB] ⚠️ 创建索引失败 {idx_name}: {e}")

    print("[DB] ✅ 数据库迁移完成")


async def init_db():
    """初始化数据库：创建所有表并执行迁移"""
    async with engine.begin() as conn:
        await _migrate_db(conn)


async def get_db() -> AsyncSession:
    """获取数据库会话（FastAPI 依赖注入）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
