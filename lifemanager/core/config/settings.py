"""
Application settings — loaded once at startup from .env
Access via: from lifemanager.core.config.settings import settings
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class DatabaseSettings:
    driver: str = field(default_factory=lambda: os.getenv("DB_DRIVER", "postgresql+psycopg2"))
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "lifemanager"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def url(self) -> str:
        return f"{self.driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass(frozen=True)
class AppSettings:
    env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    locale: str = field(default_factory=lambda: os.getenv("APP_LOCALE", "fr_FR"))
    currency: str = field(default_factory=lambda: os.getenv("APP_CURRENCY", "EUR"))
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)

    @property
    def is_dev(self) -> bool:
        return self.env == "development"


@dataclass(frozen=True)
class ApiSettings:
    off_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OFF_API_BASE", "https://world.openfoodfacts.org/api/v2"
        )
    )
    off_user_agent: str = field(
        default_factory=lambda: os.getenv("OFF_USER_AGENT", "LifeManager/0.1")
    )


@dataclass(frozen=True)
class Settings:
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    app: AppSettings = field(default_factory=AppSettings)
    api: ApiSettings = field(default_factory=ApiSettings)


# Singleton — import this everywhere
settings = Settings()
