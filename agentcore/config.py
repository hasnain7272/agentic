"""
AgentCore Configuration - Minimalist Pydantic Settings
Single source of truth for all environment-based configuration.
"""
import os
from functools import lru_cache
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation and defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AgentCore"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = True
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # Database (SQLite default, PostgreSQL via env)
    database_url: str = "sqlite+aiosqlite:///./agentcore.db"
    database_echo: bool = False

    # Redis (for queue/broker)
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    # JWT Auth
    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    refresh_token_expire_days: int = 30

    # MCP
    mcp_enabled: bool = True
    mcp_stdio_timeout: int = 30
    mcp_max_retries: int = 3

    # LLM
    default_model: str = "gpt-4o-mini"
    litellm_master_key: Optional[str] = None
    llm_api_key: Optional[str] = Field(default="", alias="LLM_API_KEY")
    llm_base_url: Optional[str] = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = 0.2
    llm_top_p: Optional[float] = 0.95
    llm_max_tokens: int = 8192

    # Web Search
    search_enabled: bool = True
    search_provider: str = "duckduckgo"  # duckduckgo, brave, serper
    search_brave_api_key: Optional[str] = None
    search_serper_api_key: Optional[str] = None
    search_cache_ttl: int = 3600
    search_max_results: int = 10

    # Governance
    default_risk_mode: str = "auto"  # auto, strict
    governance_enabled: bool = True

    # Queue
    queue_backend: str = "redis"  # redis, local
    queue_task_ttl: int = 86400

    # WebSocket
    ws_heartbeat_interval: int = 30
    ws_max_message_size: int = 1024 * 1024  # 1MB

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance - use everywhere."""
    return Settings()


# For backwards compatibility
settings = get_settings()