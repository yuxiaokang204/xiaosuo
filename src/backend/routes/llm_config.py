"""
LLM 配置路由 - Provider 管理和配置 CRUD
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
import json
import os
import httpx

router = APIRouter(tags=["LLM"])


class LLMConfigRequest(BaseModel):
    provider: str = Field(..., description="Provider ID")
    api_key: Optional[str] = Field("", description="API Key")
    model: Optional[str] = Field("", description="模型名")
    api_base: Optional[str] = Field("", description="自定义 API 基础 URL")


class SaveLLMConfigRequest(BaseModel):
    name: str
    provider: str
    api_key: str = ""
    model: str = ""
    api_base: str = ""


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


@router.get("/llm/providers")
async def list_llm_providers():
    """列出所有可用的 LLM Provider"""
    from ..llm.client import list_providers, get_default_llm_client
    return {
        "providers": list_providers(),
        "current_provider": type(get_default_llm_client()).__name__,
    }


@router.get("/llm/config")
async def get_llm_config():
    """获取当前 LLM 配置摘要"""
    from ..llm.client import get_default_llm_client
    client = get_default_llm_client()
    return {
        "provider_type": client.__class__.__name__,
        "model": getattr(client, "model", ""),
        "api_base": getattr(client, "api_base", ""),
        "has_api_key": bool(getattr(client, "api_key", None)),
    }


@router.post("/llm/config")
async def set_llm_config(req: LLMConfigRequest):
    """切换 LLM Provider / 模型 / API Key"""
    from ..llm.client import create_llm_client, set_default_llm_client
    try:
        client = create_llm_client(
            provider=req.provider,
            api_key=req.api_key or None,
            model=req.model or None,
            api_base=req.api_base or None,
        )
        set_default_llm_client(client)
        _save_llm_config_to_env(req.provider, req.api_key, req.model, req.api_base)

        return {
            "success": True,
            "provider": client.__class__.__name__,
            "model": getattr(client, "model", ""),
            "message": "LLM 配置已切换并持久化",
        }
    except Exception as e:
        raise HTTPException(400, f"配置失败: {e}")


@router.post("/llm/test")
async def test_llm():
    """测试当前 LLM 是否正常工作"""
    import time
    from ..llm.client import get_default_llm_client, LLMMessage
    client = get_default_llm_client()
    start = time.time()
    try:
        r = await client.generate(
            [LLMMessage(role="user", content="用一句话回复:你好。")],
            temperature=0.0, max_tokens=50,
        )
        return {
            "success": True,
            "content": r.content,
            "provider": r.provider,
            "latency_ms": int((time.time() - start) * 1000),
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "provider": client.__class__.__name__}


@router.post("/llm/models")
async def fetch_custom_models(req: LLMConfigRequest):
    """通过 /models 接口获取可用模型列表"""
    base = req.api_base or ""
    base = base.rstrip("/")
    models_url = base + "/models"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), verify=False) as client:
            headers = {"Authorization": f"Bearer {req.api_key or ''}"}
            r = await client.get(models_url, headers=headers)

            if r.status_code != 200:
                return {"models": [], "error": f"HTTP {r.status_code}: {r.text[:200]}"}

            data = r.json()
            models = [m.get("id", "") for m in (data.get("data", []) or []) if m.get("id")]
            return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)[:200]}


# ── LLM 配置 CRUD ──

@router.get("/llm/configs", tags=["LLM"], description="获取所有已保存的LLM配置列表")
async def list_llm_configs():
    from ..db.database import AsyncSessionLocal
    from ..db.models import LLMConfigDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LLMConfigDB).order_by(LLMConfigDB.updated_at.desc())
        )
        configs = result.scalars().all()
        return {
            "configs": [
                {
                    "id": c.id, "name": c.name, "provider": c.provider,
                    "model": c.model, "api_base": c.api_base,
                    "has_api_key": bool(c.api_key),
                    "is_default": bool(c.is_default),
                    "created_at": str(c.created_at) if c.created_at else None,
                    "updated_at": str(c.updated_at) if c.updated_at else None,
                }
                for c in configs
            ]
        }


@router.post("/llm/configs", tags=["LLM"], description="保存新的LLM配置")
async def create_llm_config(req: SaveLLMConfigRequest):
    from ..db.database import AsyncSessionLocal
    from ..db.models import LLMConfigDB
    from sqlalchemy import select, update
    from datetime import datetime

    async with AsyncSessionLocal() as session:
        now = datetime.now()
        cfg = LLMConfigDB(
            id=str(uuid.uuid4()),
            name=req.name,
            provider=req.provider,
            api_key=req.api_key,
            model=req.model,
            api_base=req.api_base,
            is_default=0,
            created_at=now,
            updated_at=now,
        )
        session.add(cfg)

        result = await session.execute(select(LLMConfigDB))
        count = len(result.scalars().all())
        if count == 1:
            cfg.is_default = 1

        await session.commit()
        return {"success": True, "id": cfg.id, "is_default": bool(cfg.is_default)}


@router.put("/llm/configs/{config_id}", tags=["LLM"], description="更新LLM配置")
async def update_llm_config(config_id: str, req: SaveLLMConfigRequest):
    from ..db.database import AsyncSessionLocal
    from ..db.models import LLMConfigDB
    from sqlalchemy import select
    from datetime import datetime

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LLMConfigDB).where(LLMConfigDB.id == config_id))
        cfg = result.scalar_one_or_none()
        if not cfg:
            raise HTTPException(404, "配置不存在")
        cfg.name = req.name
        cfg.provider = req.provider
        if req.api_key:
            cfg.api_key = req.api_key
        cfg.model = req.model
        cfg.api_base = req.api_base
        cfg.updated_at = datetime.now()
        await session.commit()
        return {"success": True, "id": cfg.id}


@router.delete("/llm/configs/{config_id}", tags=["LLM"], description="删除LLM配置")
async def delete_llm_config(config_id: str):
    from ..db.database import AsyncSessionLocal
    from ..db.models import LLMConfigDB
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LLMConfigDB).where(LLMConfigDB.id == config_id))
        cfg = result.scalar_one_or_none()
        if not cfg:
            raise HTTPException(404, "配置不存在")
        await session.delete(cfg)
        await session.commit()
        return {"success": True}


@router.post("/llm/configs/{config_id}/set-default", tags=["LLM"], description="设为默认配置")
async def set_default_llm_config(config_id: str):
    from ..db.database import AsyncSessionLocal
    from ..db.models import LLMConfigDB
    from ..llm.client import create_llm_client, set_default_llm_client
    from sqlalchemy import select, update
    from datetime import datetime

    async with AsyncSessionLocal() as session:
        await session.execute(update(LLMConfigDB).values(is_default=0))
        result = await session.execute(select(LLMConfigDB).where(LLMConfigDB.id == config_id))
        cfg = result.scalar_one_or_none()
        if not cfg:
            raise HTTPException(404, "配置不存在")
        cfg.is_default = 1
        cfg.updated_at = datetime.now()

        try:
            client = create_llm_client(
                provider=cfg.provider,
                api_key=cfg.api_key or None,
                model=cfg.model or None,
                api_base=cfg.api_base or None,
            )
            set_default_llm_client(client)
            print(f"[LLM Config] 🔄 默认配置切换为: {cfg.name} ({cfg.provider}/{cfg.model})")
        except Exception as e:
            print(f"[LLM Config] ⚠️ 创建客户端失败: {e}")

        await session.commit()
        return {"success": True, "default_id": config_id}
