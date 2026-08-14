"""
集中化配置管理
所有环境变量、API Key、参数默认值都在这里
"""
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # === LLM ===
    openai_api_key: str = Field(..., description="OpenAI / 兼容 API Key")
    openai_base_url: str = Field(default="https://api.gptsapi.net")
    default_model: str = Field(default="gpt-4o-mini")

    # === Tools ===
    tavily_api_key: str = Field(..., description="Tavily Search API Key")

    # === Agent ===
    default_max_steps: int = Field(default=10, ge=1, le=50)
    default_token_budget: int = Field(default=50_000, ge=1000, le=1_000_000)
    default_context_window: int = Field(default=8000, ge=1000, le=128_000)

    # === AsyncIO 边界 ===
    LLM_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0, le=600)
    TOOL_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=300)

    # === Service ===
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_debug: bool = Field(default=False)
    api_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # === Limits ===
    rate_limit_per_minute: int = Field(default=10, ge=1)
    max_concurrent_agents: int = Field(default=5, ge=1, le=100)

    # === Day13 JWT 配置 ===
    JWT_SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # 添加 DB 
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/agent_lab.db"

    # === Day20 Heartbeat ===
    RUN_HEARTBEAT_INTERVAL_SECONDS: int = Field(default=5, ge=1)
    RUN_STALE_AFTER_SECONDS: int = Field(default=20, ge=1)
    RUN_RECONCILE_INTERVAL_SECONDS: int = Field(default=5, ge=1)
    RUN_RECONCILE_ON_STARTUP: bool = True

    @model_validator(mode="after")
    def validate_run_health_setting(self):
        minmum_stale_seconds = (
            self.RUN_HEARTBEAT_INTERVAL_SECONDS * 3
        )

        if self.RUN_STALE_AFTER_SECONDS < minmum_stale_seconds:
            raise ValueError(
                "RUN_STALE_AFTER_SECONDS 至少应为 "
                "RUN_HEARTBEAT_INTERVAL_SECONDS 的 3 倍"
            )

        return self

# 全局单例
_settings: Settings | None = None

def get_settings() -> Settings:
    """单例 + 延迟加载"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
