"""Bootstrap configuration. Read once from the environment.

Only settings needed before the database exists live here. Everything else
(providers, models, templates, users) is managed in the admin UI and stored in SQLite.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read .env from the repo root (../.env when running inside backend/) or the CWD.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    app_secret_key: str = Field(min_length=16)
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me-too"
    data_dir: Path = Path("./data")
    app_url: str = "http://localhost:8000"
    secure_cookies: bool = False

    session_ttl_hours: int = 24 * 14
    learn_max_chars_per_paper: int = 60_000
    learn_concurrency: int = 3
    frontend_dist: Path = Path("../frontend/dist")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def seed_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "seed"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir = settings.data_dir.resolve()
    return settings
