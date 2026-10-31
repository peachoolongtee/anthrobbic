from functools import lru_cache
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment or `apps/api/.env`.

    Every field has a default so the app can start with nothing set. Required
    values are checked where they are used (see `app.supabase`), not here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SUPABASE_URL: str = ""
    # Server-only secret key. Never expose it to the browser or log it.
    SUPABASE_SECRET_KEY: SecretStr = SecretStr("")
    # Comma-separated list of allowed browser origins.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # `live` runs spend money, so they are refused unless this is set to 1.
    ALLOW_LIVE: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ALLOW_LIVE", mode="before")
    @classmethod
    def _only_one_allows_live(cls, value: object) -> bool:
        return value is True or (isinstance(value, str) and value.strip() == "1")


@lru_cache
def get_settings() -> Settings:
    return Settings()
