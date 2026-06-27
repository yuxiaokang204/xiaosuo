"""
共享依赖 — 全局变量、辅助函数、常量
供所有 api/ router 模块通过 `from .deps import ...` 导入
"""
import os
import time
from typing import Optional, Dict, Any

from ..db.database import init_db
from ..core.agent_registry_initializer import AgentRegistryInitializer
from ..core.memory import NovelMemory, ModelConfig
from ..core.learning_engine import LearningEngine
from ..llm.client import (
    create_llm_client, set_default_llm_client,
    get_default_llm_client,
)

# ── 路径常量 ──────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FRONTEND_DIST = os.path.join(_PROJECT_ROOT, "dist")

# ── 全局服务实例 ──────────────────────────────────────────────
agent_initializer: Optional[AgentRegistryInitializer] = None
novel_memory: Optional[NovelMemory] = None
learning_engine: Optional[LearningEngine] = None


def _ensure_services_ready():
    """懒加载初始化核心服务（确保TestClient也能正常工作）"""
    global agent_initializer, novel_memory, learning_engine
    if agent_initializer is None:
        agent_initializer = AgentRegistryInitializer()
        agent_initializer.initialize()
    if novel_memory is None:
        novel_memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)
    if learning_engine is None:
        learning_engine = LearningEngine()


# ── LLM 配置持久化 ────────────────────────────────────────────

def _save_llm_config_to_env(provider: str, api_key: str = "", model: str = "", api_base: str = ""):
    """将 LLM 配置持久化到 .env 文件"""
    env_path = os.path.join(_PROJECT_ROOT, ".env")

    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    env_vars = {
        "LLM_PROVIDER": provider,
        "LLM_API_KEY": api_key,
        "LLM_MODEL": model,
        "LLM_API_BASE": api_base,
    }

    updated_keys = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        for key, value in env_vars.items():
            if stripped.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                updated_keys.add(key)
                break

    for key, value in env_vars.items():
        if key not in updated_keys:
            lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    os.environ["LLM_PROVIDER"] = provider
    if api_key:
        os.environ["LLM_API_KEY"] = api_key
    if model:
        os.environ["LLM_MODEL"] = model
    if api_base:
        os.environ["LLM_API_BASE"] = api_base

    print(f"[LLM] 💾 配置已持久化到 .env: provider={provider}, model={model}")


def _load_llm_config_from_env():
    """启动时从 .env 加载持久化的 LLM 配置"""
    provider = os.environ.get("LLM_PROVIDER", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    api_base = os.environ.get("LLM_API_BASE", "").strip()

    if not provider or provider == "mock":
        print("[LLM] 📂 .env 中无自定义LLM配置，使用默认 MockProvider")
        return

    try:
        client = create_llm_client(
            provider=provider,
            api_key=api_key or None,
            model=model or None,
            api_base=api_base or None,
        )
        set_default_llm_client(client)
        print(f"[LLM] 📂 已从 .env 恢复配置: {client.__class__.__name__} (model={getattr(client, 'model', '?')})")
    except Exception as e:
        print(f"[LLM] ⚠️ 从 .env 恢复配置失败: {e}，使用默认 MockProvider")


# ── Agent ID 映射 & 统一调用入口 ───────────────────────────────

_AGENT_ID_MAP: Dict[str, str] = {
    "outline_agent": "story_architect",
    "plot_agent": "story_architect",
    "draft_agent": "draft",
    "edit_agent": "style_editor",
    "review_agent": "style_editor",
    "style_agent": "style_editor",
    "world_agent": "world",
    "character_agent": "character",
    "opening_hook_agent": "opening_hook",
    "story_architect": "story_architect",
    "world": "world",
    "character": "character",
    "opening_hook": "opening_hook",
    "draft": "draft",
    "style_editor": "style_editor",
}


def _resolve_agent_id(old_id: str) -> str:
    """将旧Agent ID映射到新ID"""
    return _AGENT_ID_MAP.get(old_id, old_id)


async def _call_agent_process(agent_id: str, context: Dict[str, Any]):
    """统一Agent调用入口：查注册表 → 获取实例 → 调用process()"""
    from fastapi import HTTPException
    _ensure_services_ready()
    resolved_id = _resolve_agent_id(agent_id)
    agent = agent_initializer.get_agent_instance(resolved_id)
    if not agent:
        raise HTTPException(404, f"未找到Agent: {agent_id} (resolved: {resolved_id})")
    try:
        return await agent.process(context)
    except Exception as e:
        raise HTTPException(500, f"Agent执行失败: {str(e)}")


# ── Orchestrator 全局状态管理 ──────────────────────────────────

from ..core.orchestrator import NovelOrchestrator  # noqa: E402

_active_orchestrators: Dict[str, "NovelOrchestrator"] = {}
_orchestrator_last_seen: Dict[str, float] = {}
_ORCH_TTL_SECONDS = 2 * 3600
_ORCH_MAX = 50


def _touch_orchestrator(novel_id: str):
    """记录/刷新编排器的最近访问时间。"""
    _orchestrator_last_seen[novel_id] = time.time()


def _cleanup_orchestrators():
    """清理过期或超量的编排器，避免长跑进程内存无限增长。"""
    now = time.time()
    expired = [
        nid for nid, ts in list(_orchestrator_last_seen.items())
        if now - ts > _ORCH_TTL_SECONDS
    ]
    for nid in expired:
        _active_orchestrators.pop(nid, None)
        _orchestrator_last_seen.pop(nid, None)
    if len(_active_orchestrators) > _ORCH_MAX:
        ordered = sorted(
            _active_orchestrators.keys(),
            key=lambda nid: _orchestrator_last_seen.get(nid, 0.0),
        )
        for nid in ordered[: len(_active_orchestrators) - _ORCH_MAX]:
            _active_orchestrators.pop(nid, None)
            _orchestrator_last_seen.pop(nid, None)


# ── 持久化 & 导出 ──────────────────────────────────────────────

async def _save_novel_to_db(orch: "NovelOrchestrator"):
    """将编排器结果保存到 SQLite 数据库"""
    from ..db.database import AsyncSessionLocal
    from ..db.models import NovelDB, VolumeDB, ChapterDB, CharacterDB, WorldSettingDB, StyleGuideDB
    import uuid
    from datetime import datetime

    async with AsyncSessionLocal() as session:
        novel_id = orch.state.novel_id

        novel = await session.get(NovelDB, novel_id)
        if not novel:
            novel = NovelDB(
                id=novel_id,
                title=orch.state.title,
                genre=orch.state.theme,
                status="completed",
                current_word_count=sum(len(ch.get("content", "")) for ch in orch.state.chapters),
                created_at=datetime.now(),
            )
            session.add(novel)
        else:
            novel.status = "completed"
            novel.current_word_count = sum(len(ch.get("content", "")) for ch in orch.state.chapters)
            novel.updated_at = datetime.now()

        volume_id = f"{novel_id}_vol1"
        volume = await session.get(VolumeDB, volume_id)
        if not volume:
            volume = VolumeDB(
                id=volume_id,
                novel_id=novel_id,
                title="第一卷",
                description=orch.state.theme,
                word_count=sum(len(ch.get("content", "")) for ch in orch.state.chapters),
                sort_order=1,
            )
            session.add(volume)

        for idx, ch in enumerate(orch.state.chapters):
            ch_id = f"{novel_id}_ch{idx+1}"
            chapter = await session.get(ChapterDB, ch_id)
            content = ch.get("content", "")
            if not chapter:
                chapter = ChapterDB(
                    id=ch_id,
                    volume_id=volume_id,
                    title=ch.get("title", f"第{idx+1}章"),
                    outline=ch.get("summary", ""),
                    content=content,
                    word_count=len(content),
                    status=ch.get("status", "draft"),
                    sort_order=idx + 1,
                    created_at=datetime.now(),
                )
                session.add(chapter)
            else:
                chapter.content = content
                chapter.word_count = len(content)
                chapter.status = ch.get("status", "draft")
                chapter.updated_at = datetime.now()

        for c_data in orch.state.characters:
            if not isinstance(c_data, dict):
                continue
            c_id = f"{novel_id}_char_{c_data.get('name', uuid.uuid4().hex[:6])}"
            char = await session.get(CharacterDB, c_id)
            now = datetime.now()
            if not char:
                char = CharacterDB(
                    id=c_id,
                    novel_id=novel_id,
                    name=c_data.get("name", "未命名"),
                    aliases=c_data.get("aliases", []),
                    role=c_data.get("role", ""),
                    personality=c_data.get("personality", ""),
                    background=c_data.get("background", ""),
                    goals=c_data.get("goals", []),
                    conflicts=c_data.get("conflicts", []),
                    speech_pattern=c_data.get("speech_pattern", ""),
                    appearance=c_data.get("appearance", ""),
                    arc_data=c_data.get("arc", {}),
                    world_id=c_data.get("world_id", None),
                    created_at=now,
                    updated_at=now,
                )
                session.add(char)

        if orch.state.world_settings and isinstance(orch.state.world_settings, dict):
            ws = orch.state.world_settings
            ws_id = f"{novel_id}_world"
            world = await session.get(WorldSettingDB, ws_id)
            now = datetime.now()
            if not world:
                world = WorldSettingDB(
                    id=ws_id,
                    novel_id=novel_id,
                    name=ws.get("name", "未命名世界"),
                    category=ws.get("category", ""),
                    description=ws.get("description", ""),
                    rules=ws.get("rules", []),
                    history=ws.get("history", {}),
                    created_at=now,
                    updated_at=now,
                )
                session.add(world)

        if orch.state.style_guide and isinstance(orch.state.style_guide, dict):
            sg = orch.state.style_guide
            sg_id = f"{novel_id}_style"
            style = await session.get(StyleGuideDB, sg_id)
            if not style:
                style = StyleGuideDB(
                    id=sg_id,
                    novel_id=novel_id,
                    vocabulary_preference=sg.get("vocabulary_preference", []),
                    sentence_patterns=sg.get("sentence_patterns", []),
                    pacing_preference=sg.get("pacing_preference", ""),
                    tone=sg.get("tone", ""),
                    anti_patterns=sg.get("anti_patterns", []),
                    reference_works=sg.get("reference_works", []),
                )
                session.add(style)

        await session.commit()


def _export_novel_to_file(orch: "NovelOrchestrator"):
    """将小说导出为本地 Markdown 文件"""
    output_dir = os.path.join(_PROJECT_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)

    safe_title = "".join(c for c in orch.state.title if c.isalnum() or c in "._- ") or "novel"
    filename = f"{safe_title}_{orch.state.novel_id}.md"
    filepath = os.path.join(output_dir, filename)

    md_parts = [
        f"# {orch.state.title}\n",
        f"\n> 主题：{orch.state.theme}  |  文风：{orch.state.tone}  |  章节数：{len(orch.state.chapters)}\n",
    ]

    if orch.state.world_settings and isinstance(orch.state.world_settings, dict):
        ws = orch.state.world_settings
        md_parts.append(f"\n---\n\n## 🌍 世界观：{ws.get('name', '未命名')}\n")
        if ws.get("description"):
            md_parts.append(f"\n{ws['description']}\n")
        if ws.get("rules"):
            md_parts.append("\n### 规则\n")
            for r in ws["rules"]:
                md_parts.append(f"- {r}\n")
        if ws.get("key_locations"):
            md_parts.append("\n### 地点\n")
            for l in ws["key_locations"]:
                md_parts.append(f"- {l}\n")

    if orch.state.characters:
        md_parts.append("\n---\n\n## 👥 角色\n")
        for c in orch.state.characters:
            if isinstance(c, dict):
                md_parts.append(f"\n### {c.get('name', '未命名')}\n")
                if c.get("role"):
                    md_parts.append(f"- 角色：{c['role']}\n")
                if c.get("personality"):
                    md_parts.append(f"- 性格：{c['personality']}\n")
                if c.get("background"):
                    md_parts.append(f"\n{c['background']}\n")

    if orch.state.outline:
        md_parts.append("\n---\n\n## 📋 大纲\n")
        for idx, ch in enumerate(orch.state.outline):
            if isinstance(ch, dict):
                md_parts.append(f"\n**第{idx+1}章 {ch.get('title', '')}**：{ch.get('summary', '')}\n")

    if orch.state.chapters:
        md_parts.append("\n---\n\n## 正文\n")
        for ch in orch.state.chapters:
            title = ch.get("title", f"第{ch.get('index', '?')}章")
            content = ch.get("content", "")
            md_parts.append(f"\n### {title}\n\n{content}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(md_parts)

    print(f"[Export] 📄 小说已导出: {filepath}")


# ── JSON 容错解析 ──────────────────────────────────────────────

def _close_open_structures(text: str) -> str:
    """补全未闭合的 JSON 结构（括号、花括号）"""
    in_string = False
    last_quote = -1
    for i, ch in enumerate(text):
        if ch == '"' and (i == 0 or text[i-1] != '\\'):
            in_string = not in_string
            if not in_string:
                last_quote = i

    if in_string:
        if last_quote >= 0:
            text = text[:last_quote + 1]
        else:
            text = text.rstrip('"')

    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    text += ']' * max(0, open_brackets)
    text += '}' * max(0, open_braces)
    return text


def _safe_parse_json(content: str, max_retries: int = 3) -> dict:
    """容错 JSON 解析：处理 LLM 输出被截断或格式不完整的情况"""
    import re
    import json

    content = content.strip()
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)

    for attempt in range(max_retries):
        try:
            return json.loads(content), None
        except json.JSONDecodeError as e:
            if attempt == max_retries - 1:
                return {}, f"JSON解析失败(已重试{max_retries}次): {str(e)}"

            if "Unterminated string" in str(e):
                content = content + '"'
                content = _close_open_structures(content)
            elif "Expecting" in str(e) or "Extra data" in str(e):
                content = _close_open_structures(content)
            else:
                last_good = max(
                    content.rfind('"}'),
                    content.rfind('"]'),
                    content.rfind('}"'),
                    content.rfind(']"'),
                )
                if last_good > 0:
                    content = content[:last_good + 2]
                    content = _close_open_structures(content)

    return {}, f"JSON解析失败: 无法修复"


# ── LLM 客户端（从数据库加载）──────────────────────────────────

async def _get_llm_client_from_db(config_id: Optional[str] = None):
    """从数据库加载LLM配置并创建客户端"""
    from ..db.database import AsyncSessionLocal
    from ..db.models import LLMConfigDB
    from sqlalchemy import select
    from ..llm.client import MockProvider

    async with AsyncSessionLocal() as session:
        if config_id:
            result = await session.execute(select(LLMConfigDB).where(LLMConfigDB.id == config_id))
            cfg = result.scalar_one_or_none()
        else:
            result = await session.execute(select(LLMConfigDB).where(LLMConfigDB.is_default == 1))
            cfg = result.scalar_one_or_none()
            if not cfg:
                result = await session.execute(select(LLMConfigDB).order_by(LLMConfigDB.updated_at.desc()).limit(1))
                cfg = result.scalar_one_or_none()

        if not cfg:
            return MockProvider()
        try:
            client = create_llm_client(
                provider=cfg.provider,
                api_key=cfg.api_key or None,
                model=cfg.model or None,
                api_base=cfg.api_base or None,
            )
            return client
        except Exception:
            return MockProvider()


# ── Prompt 验证常量 ────────────────────────────────────────────

_VALID_AGENT_TYPES = {"story_architect", "world", "character", "opening_hook", "draft", "style_editor"}