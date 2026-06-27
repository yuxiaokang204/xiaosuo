"""
数据库迁移脚本 - 从 v1.1 迁移到 v2.0
自动检测并添加缺失的表和列
"""
import os
import sys
import asyncio
from sqlalchemy import text, inspect


async def migrate_database(db_url: str = None):
    """
    执行数据库迁移
    
    Args:
        db_url: 数据库 URL，默认从环境变量或配置读取
    """
    from .database import engine, DATABASE_URL

    url = db_url or DATABASE_URL
    is_sqlite = "sqlite" in url

    print(f"[Migration] 开始迁移: {url}")
    print(f"[Migration] SQLite: {is_sqlite}")

    if not is_sqlite:
        print("[Migration] ⚠️ 仅支持 SQLite 自动迁移")
        return

    async with engine.begin() as conn:
        # 检查表是否存在
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        existing_tables = {row[0] for row in result.fetchall()}
        print(f"[Migration] 现有表: {sorted(existing_tables)}")

        # ── 添加新表 ──
        new_tables = [
            "agent_prompts",
            "chapter_continuity",
            "orchestrator_runs",
        ]

        for table in new_tables:
            if table not in existing_tables:
                print(f"[Migration] ➕ 创建新表: {table}")
                await _create_table_if_missing(conn, table)
            else:
                print(f"[Migration] ✓ 表已存在: {table}")

        # ── 添加缺失的列 ──
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

        # ── 创建索引 ──
        index_specs = [
            ("ix_agent_prompts_agent_type", "agent_prompts", "agent_type"),
            ("ix_agent_prompts_novel_id", "agent_prompts", "novel_id"),
            ("ix_chapter_continuity_novel_id", "chapter_continuity", "novel_id"),
            ("ix_chapter_continuity_chapter_idx", "chapter_continuity", "chapter_idx"),
            ("ix_orchestrator_runs_novel_id", "orchestrator_runs", "novel_id"),
            ("ix_orchestrator_runs_status", "orchestrator_runs", "status"),
            ("ix_llm_configs_is_default", "llm_configs", "is_default"),
        ]

        for idx_name, table, column in index_specs:
            await _create_index_if_missing(conn, idx_name, table, column)

    print("[Migration] ✅ 迁移完成")


async def _create_table_if_missing(conn, table_name: str):
    """创建新表（如果不存在）"""
    create_sqls = {
        "agent_prompts": """
            CREATE TABLE IF NOT EXISTS agent_prompts (
                id TEXT PRIMARY KEY,
                novel_id TEXT,
                agent_type TEXT NOT NULL,
                depth_level INTEGER DEFAULT 1,
                prompt_type TEXT DEFAULT 'system',
                title TEXT DEFAULT '',
                content TEXT NOT NULL,
                quality_score INTEGER DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0,
                meta_info TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """,
        "chapter_continuity": """
            CREATE TABLE IF NOT EXISTS chapter_continuity (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                chapter_idx INTEGER NOT NULL,
                chapter_title TEXT DEFAULT '',
                ending_text TEXT,
                scene TEXT,
                character_states TEXT,
                unresolved TEXT,
                tension_points TEXT,
                continuity_score INTEGER DEFAULT 7,
                user_notes TEXT DEFAULT '',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
            )
        """,
        "orchestrator_runs": """
            CREATE TABLE IF NOT EXISTS orchestrator_runs (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                theme TEXT NOT NULL,
                tone TEXT DEFAULT '史诗',
                chapter_count INTEGER DEFAULT 10,
                platform TEXT DEFAULT '番茄',
                state_json TEXT,
                current_loop INTEGER DEFAULT 0,
                depth_level INTEGER DEFAULT 0,
                current_stage TEXT DEFAULT 'planning',
                completed_stages TEXT,
                status TEXT DEFAULT 'running',
                error_log TEXT DEFAULT '',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
            )
        """,
    }

    sql = create_sqls.get(table_name)
    if sql:
        await conn.execute(text(sql))


async def _add_column_if_missing(conn, table: str, column: str, col_type: str):
    """如果列不存在则添加"""
    try:
        result = await conn.execute(
            text(f"PRAGMA table_info({table})")
        )
        existing = [row[1] for row in result.fetchall()]
        if column not in existing:
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
            await conn.execute(text(sql))
            print(f"[Migration] ✅ 已添加列: {table}.{column}")
    except Exception as e:
        print(f"[Migration] ⚠️ 添加列失败 {table}.{column}: {e}")


async def _create_index_if_missing(conn, idx_name: str, table: str, column: str):
    """幂等地创建索引"""
    try:
        await conn.execute(
            text(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})')
        )
        print(f"[Migration] ✅ 已创建索引: {idx_name}")
    except Exception as e:
        print(f"[Migration] ⚠️ 创建索引失败 {idx_name}: {e}")


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(migrate_database(db_url))
