"""Application configuration loaded from environment variables via pydantic-settings.

Values come from the environment and an optional `.env` file (see `.env.example`).
All fields carry development defaults so the skeleton boots from a fresh clone;
secrets are placeholders only and must be overridden per environment before use.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    project_name: str = "Nestro"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/nestro"
    jwt_secret: str = "change-me"


settings = Settings()