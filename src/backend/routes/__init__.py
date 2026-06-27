"""
路由注册中心 - 聚合所有子路由并注册到 FastAPI 应用
"""
from fastapi import FastAPI
from typing import Optional


def register_routes(app: FastAPI, novel_memory=None, learning_engine=None) -> None:
    """
    注册所有子路由到 FastAPI 应用
    
    Args:
        app: FastAPI 应用实例
        novel_memory: 记忆系统实例（可选，用于部分路由）
        learning_engine: 学习引擎实例（可选，用于部分路由）
    """
    from .novels import router as novels_router
    from .orchestrator import router as orchestrator_router
    from .agents import router as agents_router
    from .memory import router as memory_router
    from .learning import router as learning_router
    from .llm_config import router as llm_config_router
    from .prompts import router as prompts_router

    # 注册路由（带 prefix）
    app.include_router(novels_router, prefix="/api")
    app.include_router(orchestrator_router, prefix="/api")
    app.include_router(agents_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(learning_router, prefix="/api")
    app.include_router(llm_config_router, prefix="/api")
    app.include_router(prompts_router, prefix="/api")
