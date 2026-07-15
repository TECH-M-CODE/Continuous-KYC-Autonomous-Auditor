"""Centralized application settings, sourced from environment variables / .env."""
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    # NoDecode stops pydantic-settings from JSON-decoding the raw env value, so a
    # plain comma-separated string in .env (CORS_ORIGINS=http://a,http://b) reaches
    # the validator below instead of crashing json.loads. A JSON array still works too.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ]

    # Database & Infrastructure
    database_url: str = "sqlite+aiosqlite:///./data/sentinelai.db"
    chroma_persist_dir: str = "./data/chroma"
    redis_url: str = "redis://localhost:6379"

    # AI / LLM — priority: NVIDIA → Gemini → Mock
    # NVIDIA NIM (https://build.nvidia.com → Get API Key)
    nvidia_api_key: str = ""
    nvidia_primary_model: str = "meta/llama-3.3-70b-instruct"
    nvidia_fallback_model: str = "meta/llama-3.1-8b-instruct"
    # Google Gemini (fallback when nvidia_api_key is blank)
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    mask_pii_before_llm: bool = True

    # Telemetry
    otel_exporter_otlp_endpoint: str = ""

    # Datasets
    data_dir: str = "./data"

    # Loop D — autonomous self-assessment (red-team drill + dormancy sweep).
    # Design intent is nightly; kept short here so the behavior is observable in a
    # demo/dev run. Set to 0 to disable scheduling entirely.
    loop_d_interval_seconds: int = 900

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
