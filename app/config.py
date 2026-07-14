"""Centralized application settings, sourced from environment variables / .env."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    project_name: str = "CXKYC - Continuous KYC Autonomous Auditor"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    log_level: str = "INFO"

    # Security
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    rate_limit_per_minute: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]

    # Database & Infrastructure
    database_url: str = "sqlite+aiosqlite:///./data/sentinelai.db"
    chroma_persist_dir: str = "./data/chroma"
    redis_url: str = "redis://localhost:6379"

    # AI / LLM
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    mask_pii_before_llm: bool = True

    # Telemetry
    otel_exporter_otlp_endpoint: str = ""

    # Datasets
    data_dir: str = "./data"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
