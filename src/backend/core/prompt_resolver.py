"""
Prompt 解析器 v1.0 — 两级 fallback 链

1. DB 中 is_active 的 prompt（可由前端 PromptManagerPage 动态编辑）
2. 代码中 prompts.py 的 build_*_*_prompt(depth_level) 硬编码

缓存策略：运行时缓存已解析的 prompt，避免重复 DB 查询。
前端保存/激活后调用 clear_cache() 实现热更新。
"""

import logging
from typing import Dict, Optional, Tuple

from ..db.models import AgentPromptDB
from ..db.database import AsyncSessionLocal
from sqlalchemy import select, and_, update

logger = logging.getLogger(__name__)

# 6 个可用的 agent_type
_VALID_AGENT_TYPES = {
    "story_architect", "world", "character", "opening_hook", "draft", "style_editor",
}

# agent_type → prompts.py 中 system_prompt 构建函数的映射
_SYSTEM_PROMPT_BUILDERS = {}  # 延迟导入，避免循环引用
_USER_PROMPT_BUILDERS = {}

_CACHE: Dict[Tuple, str] = {}  # (agent_type, depth_level, prompt_type, novel_id) → content


def _ensure_builders():
    """延迟导入 prompts.py 中的构建函数"""
    if _SYSTEM_PROMPT_BUILDERS:
        return
    from ..agents.prompts import (
        build_story_architect_system_prompt,
        build_world_system_prompt,
        build_character_system_prompt,
        build_opening_hook_system_prompt,
        build_draft_system_prompt,
        build_style_editor_system_prompt,
    )
    _SYSTEM_PROMPT_BUILDERS.update({
        "story_architect": build_story_architect_system_prompt,
        "world": build_world_system_prompt,
        "character": build_character_system_prompt,
        "opening_hook": build_opening_hook_system_prompt,
        "draft": build_draft_system_prompt,
        "style_editor": build_style_editor_system_prompt,
    })


async def resolve_system_prompt(
    agent_type: str,
    depth_level: int = 1,
    novel_id: Optional[str] = None,
) -> str:
    """
    解析 system_prompt（两级 fallback）

    优先级：
    1. DB 中 is_active=1 的记录（优先匹配 novel_id，再匹配通用模板）
    2. prompts.py 中的 build_*_system_prompt(depth_level)
    """
    _ensure_builders()

    if agent_type not in _VALID_AGENT_TYPES:
        logger.warning("未知 agent_type: %s，回退到硬编码", agent_type)
        builder = _SYSTEM_PROMPT_BUILDERS.get(agent_type)
        return builder(depth_level) if builder else ""

    cache_key = (agent_type, depth_level, "system", novel_id or "")
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        async with AsyncSessionLocal() as session:
            # 优先匹配小说专属 prompt
            stmt = select(AgentPromptDB).where(
                and_(
                    AgentPromptDB.agent_type == agent_type,
                    AgentPromptDB.depth_level == depth_level,
                    AgentPromptDB.prompt_type == "system",
                    AgentPromptDB.is_active == 1,
                )
            )
            if novel_id:
                stmt = stmt.where(AgentPromptDB.novel_id == novel_id)
                result = await session.execute(stmt.limit(1))
                prompt = result.scalar()
            else:
                result = await session.execute(
                    stmt.where(AgentPromptDB.novel_id.is_(None)).limit(1)
                )
                prompt = result.scalar()

            if prompt and prompt.content:
                # 更新使用计数
                try:
                    await session.execute(
                        update(AgentPromptDB)
                        .where(AgentPromptDB.id == prompt.id)
                        .values(usage_count=AgentPromptDB.usage_count + 1)
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()

                _CACHE[cache_key] = prompt.content
                logger.debug("从 DB 加载 %s system_prompt (depth=%d)", agent_type, depth_level)
                return prompt.content
    except Exception as e:
        logger.warning("DB 查询 prompt 失败: %s，回退到硬编码", e)

    # Fallback 到硬编码
    builder = _SYSTEM_PROMPT_BUILDERS.get(agent_type)
    if builder:
        try:
            content = builder(depth_level)
            _CACHE[cache_key] = content
            logger.debug("使用硬编码 %s system_prompt (depth=%d)", agent_type, depth_level)
            return content
        except Exception as e:
            logger.error("硬编码 prompt 构建失败: %s", e)
    return ""


async def resolve_user_prompt_template(
    agent_type: str,
    depth_level: int = 1,
    novel_id: Optional[str] = None,
) -> str:
    """
    解析 user_prompt 模板（含 {placeholder} 占位符）

    与 resolve_system_prompt 相同的两级 fallback 逻辑，
    但返回的是模板字符串（含占位符），由调用方 .format_map() 替换。
    """
    if agent_type not in _VALID_AGENT_TYPES:
        return ""

    cache_key = (agent_type, depth_level, "user", novel_id or "")
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(AgentPromptDB).where(
                and_(
                    AgentPromptDB.agent_type == agent_type,
                    AgentPromptDB.depth_level == depth_level,
                    AgentPromptDB.prompt_type == "user",
                    AgentPromptDB.is_active == 1,
                )
            )
            if novel_id:
                stmt = stmt.where(AgentPromptDB.novel_id == novel_id)
                result = await session.execute(stmt.limit(1))
                prompt = result.scalar()
            else:
                result = await session.execute(
                    stmt.where(AgentPromptDB.novel_id.is_(None)).limit(1)
                )
                prompt = result.scalar()

            if prompt and prompt.content:
                _CACHE[cache_key] = prompt.content
                return prompt.content
    except Exception as e:
        logger.warning("DB 查询 user prompt 模板失败: %s", e)

    return ""


def clear_cache():
    """清除所有运行时缓存（前端保存/激活 prompt 后调用）"""
    _CACHE.clear()
    logger.info("Prompt 缓存已清除")


def clear_cache_for(agent_type: str, depth_level: int, novel_id: str = ""):
    """清除指定 agent 的缓存"""
    keys_to_remove = []
    for key in _CACHE:
        if key[0] == agent_type and key[1] == depth_level:
            keys_to_remove.append(key)
    for key in keys_to_remove:
        del _CACHE[key]
    if keys_to_remove:
        logger.info("已清除 %d 个缓存项: %s (depth=%d)", len(keys_to_remove), agent_type, depth_level)