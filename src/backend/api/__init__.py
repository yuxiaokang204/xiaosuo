"""
API Router 注册 — 导出所有 router 和 register_routers(app) 函数
"""
from fastapi import FastAPI

from .agents import router as agents_router
from .memory import router as memory_router
from .learning import router as learning_router
from .create import router as create_router
from .llm import router as llm_router
from .orchestrator import router as orchestrator_router
from .novels import router as novels_router
from .settings import router as settings_router
from .prompts import router as prompts_router
from .continuity import router as continuity_router
from .executor import router as executor_router


def register_routers(app: FastAPI):
    """将所有 domain router 注册到 FastAPI app"""
    app.include_router(agents_router)
    app.include_router(memory_router)
    app.include_router(learning_router)
    app.include_router(create_router)
    app.include_router(llm_router)
    app.include_router(orchestrator_router)
    app.include_router(novels_router)
    app.include_router(settings_router)
    app.include_router(prompts_router)
    app.include_router(continuity_router)
    app.include_router(executor_router)