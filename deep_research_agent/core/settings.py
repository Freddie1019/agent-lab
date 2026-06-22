"""
集中化配置管理
所有环境变量、API Key、参数默认值都在这里
"""
from pydantic import Field
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

    # === Service ===
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_debug: bool = Field(default=False)
    api_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # === Limits ===
    rate_limit_per_minute: int = Field(default=10, ge=1)
    max_concurrent_agents: int = Field(default=5, ge=1, le=100)

# 全局单例
_settings: Settings | None = None

def get_settings() -> Settings:
    """单例 + 延迟加载"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings