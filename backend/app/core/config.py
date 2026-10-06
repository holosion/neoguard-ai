from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NeoGuard Backend"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://neoguard:change-me@localhost:5432/neoguard"
    jwt_secret_key: str = "development-only-change-this-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000", "http://localhost:5173"]
    reading_stale_after_seconds: int = 600
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_email: str = "admin@neoguard.local"
    bootstrap_admin_password: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("bootstrap_admin_password", mode="before")
    @classmethod
    def blank_password_is_unset(cls, value):
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
