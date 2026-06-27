"""
小说创作Agent系统 v2.0 - FastAPI主入口
提供RESTful API：系统健康检查、路由注册、SSE流式、前端静态服务

使用:
    python run.py                     # 默认端口 8080
    或: python -m uvicorn src.backend.main:app --reload --port 8080
    打开 http://localhost:8080/docs 查看Swagger文档
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from typing import Optional
import os

from .db.database import init_db
from .db import models  # noqa: F401 - 注册SQLAlchemy模型
from .core.agent_registry_initializer import AgentRegistryInitializer
from .core.memory import NovelMemory, ModelConfig
from .core.learning_engine import LearningEngine
from .core.agent_executor import AgentExecutor
from .llm.client import (
    list_providers, create_llm_client, set_default_llm_client,
    get_default_llm_client,
)
from .routes import register_routes
from .config.settings import get_settings

# 前端构建产物路径
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FRONTEND_DIST = os.path.join(_PROJECT_ROOT, "dist")

# 全局服务实例
agent_initializer: Optional[AgentRegistryInitializer] = None
novel_memory: Optional[NovelMemory] = None
learning_engine: Optional[LearningEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 - 启动时初始化DB/Agent/记忆/学习引擎"""
    global agent_initializer, novel_memory, learning_engine

    try:
        await init_db()
        print("[STARTUP] ✅ 数据库初始化完成")
    except Exception as e:
        print(f"[STARTUP] ⚠️ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()

    agent_initializer = AgentRegistryInitializer()
    agent_initializer.initialize()

    novel_memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)
    learning_engine = LearningEngine()

    _load_llm_config_from_env()

    print("[STARTUP] ✅ 小说创作Agent系统 v2.0 启动完成")
    print(f"[STARTUP] - 已注册Agent: {agent_initializer.describe()['total']} 个")
    print(f"[STARTUP] - 上下文窗口: {ModelConfig.GPT_4O_CONTEXT} tokens")

    yield
    print("[SHUTDOWN] 系统优雅关闭")


app = FastAPI(
    title="小说创作Agent系统 v2.0",
    description="基于多Agent协作的AI小说创作平台 - 模块化重构版",
    version="2.0.0",
    lifespan=lifespan,
)


def _ensure_services_ready():
    """懒加载初始化核心服务"""
    global agent_initializer, novel_memory, learning_engine
    if agent_initializer is None:
        agent_initializer = AgentRegistryInitializer()
        agent_initializer.initialize()
    if novel_memory is None:
        novel_memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)
    if learning_engine is None:
        learning_engine = LearningEngine()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# 系统端点
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    _ensure_services_ready()
    if os.path.isdir(_FRONTEND_DIST):
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
    return {
        "message": "小说创作Agent系统 v2.0",
        "version": "2.0.0",
        "agents": agent_initializer.describe()["agents"],
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    _ensure_services_ready()
    client = get_default_llm_client()
    return {
        "status": "healthy",
        "agents_registered": agent_initializer.describe()["total"],
        "llm_provider": f"{client.__class__.__name__} (model={getattr(client, 'model', '?')})",
    }


@app.get("/api/health")
async def api_health_check():
    _ensure_services_ready()
    client = get_default_llm_client()
    return {
        "status": "healthy",
        "agents_registered": agent_initializer.describe()["total"],
        "llm_provider": f"{client.__class__.__name__} (model={getattr(client, 'model', '?')})",
    }


# ─────────────────────────────────────────────────────────────
# 注册模块化路由
# ─────────────────────────────────────────────────────────────

register_routes(app, novel_memory=novel_memory, learning_engine=learning_engine)


# ─────────────────────────────────────────────────────────────
# Agent 执行统计
# ─────────────────────────────────────────────────────────────

@app.get("/api/executor/stats")
async def executor_stats():
    """全局 Agent 执行统计"""
    return {"stats": AgentExecutor.stats()}


@app.get("/api/executor/recent")
async def executor_recent(limit: int = 20):
    """最近 N 次 Agent 执行记录"""
    return {"recent": AgentExecutor.recent(limit=limit)}


# ─────────────────────────────────────────────────────────────
# LLM 配置（从 .env 加载）
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# SSE 实时推送端点 - 全流程编排
# ─────────────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse
import asyncio
import json
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class OrchestratorStreamRequest(BaseModel):
    title: str
    theme: str
    tone: str = "史诗"
    chapter_count: int = 5
    novel_id: Optional[str] = None
    preset_character_id: Optional[str] = None
    preset_world_id: Optional[str] = None
    skip_editing_review: bool = False


@app.get("/api/orchestrator/stream", tags=["编排"], description="SSE 实时推送小说生成进度")
async def orchestrator_stream(
    title: str,
    theme: str,
    tone: str = "史诗",
    chapter_count: int = 5,
    novel_id: Optional[str] = None,
    preset_character_id: Optional[str] = None,
    preset_world_id: Optional[str] = None,
    skip_editing_review: bool = False,
):
    """SSE 实时推送小说生成进度"""
    queue: asyncio.Queue = asyncio.Queue()

    async def progress_callback(event_type: str, payload: Dict[str, Any]):
        await queue.put({"event": event_type, **payload})

    preset_characters = None
    preset_world = None
    if preset_character_id or preset_world_id:
        from .db.database import AsyncSessionLocal
        from .db.models import CharacterDB, WorldSettingDB
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            if preset_character_id:
                char = await session.get(CharacterDB, preset_character_id)
                if char:
                    preset_characters = [{
                        "name": char.name,
                        "role": char.role,
                        "personality": char.personality,
                        "background": char.background,
                        "appearance": char.appearance,
                        "goals": char.goals,
                        "aliases": char.aliases,
                    }]
                    print(f"[Orchestrator] 📌 使用预设角色: {char.name}")
            if preset_world_id:
                world = await session.get(WorldSettingDB, preset_world_id)
                if world:
                    preset_world = {
                        "name": world.name,
                        "category": world.category,
                        "description": world.description,
                        "rules": world.rules,
                    }
                    print(f"[Orchestrator] 📌 使用预设世界观: {world.name}")

    async def event_generator():
        from .core.orchestrator import NovelOrchestrator

        orch = NovelOrchestrator(
            title=title, theme=theme, tone=tone,
            chapter_count=chapter_count, novel_id=novel_id,
            progress_callback=progress_callback,
            preset_characters=preset_characters,
            preset_world=preset_world,
            learning_engine=learning_engine,
        )
        global _active_orchestrators
        _active_orchestrators[orch.state.novel_id] = orch

        task = asyncio.create_task(_run_orchestrator(orch, queue, skip_editing_review))

        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                event_type = data.get("event", "message")
                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                if task.done():
                    try:
                        result = task.result()
                        yield f"event: final_result\ndata: {json.dumps({'result': result}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                    break
                else:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': asyncio.get_event_loop().time()}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )


_active_orchestrators: Dict[str, Any] = {}


async def _run_orchestrator(orch, queue, skip_editing_review: bool = False):
    """在后台运行编排器并持久化"""
    skip_stages = ["editing", "review"] if skip_editing_review else None

    try:
        result = await orch.run_all(skip_stages=skip_stages)
    except Exception as e:
        await queue.put({"event": "error", "error": f"编排器执行失败: {str(e)}"})
        await queue.put({"event": "final_result", "success": False, "error": str(e)})
        return {"success": False, "error": str(e)}

    try:
        await _save_novel_to_db(orch)
        _export_novel_to_file(orch)
        await queue.put({
            "event": "save_success",
            "novel_id": orch.state.novel_id,
            "title": orch.state.title,
            "chapters_count": len(orch.state.chapters),
            "message": f"✅ 已保存到数据库，共 {len(orch.state.chapters)} 章",
        })
        print(f"[Orchestrator] ✅ 小说已持久化: {orch.state.title} (ID: {orch.state.novel_id})")
    except Exception as e:
        print(f"[Orchestrator] ⚠️ 持久化失败: {e}")
        await queue.put({"event": "save_error", "error": f"持久化失败: {str(e)}"})

    # 立即推送 final_result，不等 30s 超时
    await queue.put({
        "event": "final_result",
        "success": True,
        "novel_id": orch.state.novel_id,
        "title": orch.state.title,
        "chapters_count": len(orch.state.chapters),
    })
    return result


async def _save_novel_to_db(orch):
    """将编排器结果保存到 SQLite 数据库"""
    from .db.database import AsyncSessionLocal
    from .db.models import NovelDB, VolumeDB, ChapterDB, CharacterDB, WorldSettingDB, StyleGuideDB
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
                id=volume_id, novel_id=novel_id,
                title="第一卷", description=orch.state.theme,
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
                    id=ch_id, volume_id=volume_id,
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
                    id=c_id, novel_id=novel_id,
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
                    created_at=now, updated_at=now,
                )
                session.add(char)

        if orch.state.world_settings and isinstance(orch.state.world_settings, dict):
            ws = orch.state.world_settings
            ws_id = f"{novel_id}_world"
            world = await session.get(WorldSettingDB, ws_id)
            now = datetime.now()
            if not world:
                world = WorldSettingDB(
                    id=ws_id, novel_id=novel_id,
                    name=ws.get("name", "未命名世界"),
                    category=ws.get("category", ""),
                    description=ws.get("description", ""),
                    rules=ws.get("rules", []),
                    history=ws.get("history", {}),
                    created_at=now, updated_at=now,
                )
                session.add(world)

        await session.commit()


def _export_novel_to_file(orch):
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

    if orch.state.characters:
        md_parts.append("\n---\n\n## 👥 角色\n")
        for c in orch.state.characters:
            if isinstance(c, dict):
                md_parts.append(f"\n### {c.get('name', '未命名')}\n")

    if orch.state.chapters:
        md_parts.append("\n---\n\n## 正文\n")
        for ch in orch.state.chapters:
            title = ch.get("title", f"第{ch.get('index', '?')}章")
            content = ch.get("content", "")
            md_parts.append(f"\n### {title}\n\n{content}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(md_parts)

    print(f"[Export] 📄 小说已导出: {filepath}")


# ─────────────────────────────────────────────────────────────
# 预设管理端点
# ─────────────────────────────────────────────────────────────

@app.get("/api/presets", tags=["预设"], description="获取所有已保存的角色和世界观列表")
async def list_presets():
    """获取所有可用的预设角色和世界观"""
    from .db.database import AsyncSessionLocal
    from .db.models import NovelDB, CharacterDB, WorldSettingDB
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
                    "id": c.id, "name": c.name, "role": c.role,
                    "personality": c.personality, "background": c.background,
                    "appearance": c.appearance, "goals": c.goals or [],
                    "novel_id": c.novel_id,
                    "created_at": str(c.created_at) if c.created_at else None,
                    "updated_at": str(c.updated_at) if c.updated_at else None,
                    "novel_title": novels.get(c.novel_id, c.novel_id) if c.novel_id else "",
                }
                for c in characters
            ],
            "world_settings": [
                {
                    "id": w.id, "name": w.name, "category": w.category,
                    "description": w.description, "rules": w.rules or [],
                    "novel_id": w.novel_id,
                    "created_at": str(w.created_at) if w.created_at else None,
                    "updated_at": str(w.updated_at) if w.updated_at else None,
                    "novel_title": novels.get(w.novel_id, w.novel_id) if w.novel_id else "",
                }
                for w in worlds
            ],
        }


# ─────────────────────────────────────────────────────────────
# 前端静态文件服务
# ─────────────────────────────────────────────────────────────

if os.path.isdir(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback - 所有非 /api 请求返回 index.html"""
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        raise HTTPException(404, "前端构建文件未找到")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局兜底异常处理"""
    import traceback
    from fastapi.responses import JSONResponse
    print(f"[GLOBAL ERROR] {type(exc).__name__}: {exc}")
    print(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
    )
