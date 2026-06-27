"""
配置管理模块 - 集中管理所有配置项
支持环境变量 + .env 文件 + 默认值三层配置
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置 - 从环境变量/.env 加载"""

    # ── 应用基础配置 ──
    APP_NAME: str = "小说创作Agent系统"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── 服务器配置 ──
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    RELOAD: bool = True

    # ── 数据库配置 ──
    DATABASE_URL: str = "sqlite+aiosqlite:///./novel_agent.db"
    SQL_ECHO: bool = False

    # ── LLM 配置 ──
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_API_BASE: str = ""

    # ── 前端静态文件 ──
    FRONTEND_DIST: str = "./dist"

    # ── ChromaDB 配置 ──
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CHROMA_COLLECTION: str = "novel_memory"

    # ── 记忆系统配置 ──
    MEMORY_MAX_CONTEXT_TOKENS: int = 76800
    MEMORY_SHORT_TERM_MAX: int = 200

    # ── 编排器配置 ──
    ORCH_TTL_SECONDS: int = 7200  # 2小时
    ORCH_MAX_CONCURRENT: int = 50

    # ── CORS 配置 ──
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def llm_provider_meta(self) -> dict:
        """获取当前 LLM Provider 元信息"""
        from ..llm.client import PROVIDER_META
        return PROVIDER_META.get(self.LLM_PROVIDER, PROVIDER_META.get("mock", {}))

    @property
    def chroma_persist_path(self) -> str:
        """ChromaDB 持久化路径（绝对路径）"""
        import os
        return os.path.abspath(self.CHROMA_PERSIST_DIR)


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（缓存避免重复加载）"""
    return Settings()
