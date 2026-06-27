"""
统一配置管理 v1.0

集中管理所有配置来源：
- .env 文件（环境变量）
- 硬编码默认值
- 数据库中的 LLM 配置

优先级：数据库 > .env > 默认值

用法:
    from core.config import settings
    model = settings.llm_model
    timeout = settings.request_timeout
"""

import os
from typing import Optional


class AppSettings:
    """应用配置单例"""

    def __init__(self):
        self._load_from_env()

    # ── LLM 配置 ──

    @property
    def llm_provider(self) -> str:
        return os.environ.get("LLM_PROVIDER", "custom_openai")

    @property
    def llm_model(self) -> str:
        return os.environ.get("LLM_MODEL", "qwen36-35b")

    @property
    def llm_api_key(self) -> str:
        return os.environ.get("LLM_API_KEY", "")

    @property
    def llm_api_base(self) -> str:
        return os.environ.get("LLM_API_BASE", "")

    # ── 韧性配置 ──

    @property
    def max_retries(self) -> int:
        return int(os.environ.get("NOVEL_MAX_RETRIES", "3"))

    @property
    def base_delay(self) -> float:
        return float(os.environ.get("NOVEL_BASE_DELAY", "1.0"))

    @property
    def rate_limit_rpm(self) -> int:
        return int(os.environ.get("NOVEL_RATE_LIMIT_RPM", "30"))

    @property
    def request_timeout(self) -> int:
        return int(os.environ.get("NOVEL_REQUEST_TIMEOUT", "60"))

    # ── 编排器配置 ──

    @property
    def max_loops(self) -> int:
        return int(os.environ.get("NOVEL_MAX_LOOPS", "3"))

    @property
    def quality_threshold(self) -> float:
        return float(os.environ.get("NOVEL_QUALITY_THRESHOLD", "6.5"))

    @property
    def chapters_per_draft_loop(self) -> int:
        return int(os.environ.get("NOVEL_CHAPTERS_PER_LOOP", "5"))

    @property
    def default_platform(self) -> str:
        return os.environ.get("NOVEL_DEFAULT_PLATFORM", "番茄")

    @property
    def default_tone(self) -> str:
        return os.environ.get("NOVEL_DEFAULT_TONE", "史诗")

    @property
    def default_chapter_count(self) -> int:
        return int(os.environ.get("NOVEL_DEFAULT_CHAPTERS", "10"))

    # ── 记忆配置 ──

    @property
    def memory_token_budget(self) -> int:
        return int(os.environ.get("NOVEL_MEMORY_TOKEN_BUDGET", "4000"))

    @property
    def vector_db_path(self) -> str:
        return os.environ.get("NOVEL_VECTOR_DB_PATH", "./data/vector_memory")

    @property
    def recent_chapters_count(self) -> int:
        return int(os.environ.get("NOVEL_RECENT_CHAPTERS", "3"))

    # ── 可观测性配置 ──

    @property
    def langfuse_enabled(self) -> bool:
        return os.environ.get("LANGFUSE_ENABLED", "false").lower() in ("true", "1", "yes")

    @property
    def langfuse_host(self) -> str:
        return os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # ── 数据库配置 ──

    @property
    def database_url(self) -> str:
        return os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///novel_agent.db")

    # ── 服务器配置 ──

    @property
    def host(self) -> str:
        return os.environ.get("HOST", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(os.environ.get("PORT", "8080"))

    @property
    def debug(self) -> bool:
        return os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    # ── 内部方法 ──

    def _load_from_env(self):
        """从 .env 文件加载环境变量"""
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
            except Exception:
                pass  # .env 加载失败不影响启动

    def to_dict(self) -> dict:
        """导出所有配置（不含敏感信息）"""
        return {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "rate_limit_rpm": self.rate_limit_rpm,
            "max_loops": self.max_loops,
            "quality_threshold": self.quality_threshold,
            "memory_token_budget": self.memory_token_budget,
            "langfuse_enabled": self.langfuse_enabled,
            "debug": self.debug,
        }


# 全局单例
settings = AppSettings()