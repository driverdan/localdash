"""Application settings, loaded from environment / .env via pydantic-settings.

Nothing source-specific is hardcoded — the hc911 token/origin, DB URL, and tile
layer all come from the environment so the same code runs in any deployment.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database — async URL used by the app; Alembic derives the sync form below.
    database_url: str = "postgresql+asyncpg://localdash:localdash@localhost:5432/localdash"

    # Hamilton County 911 source.
    hc911_api_url: str = "https://hc911server.com/api/calls"
    hc911_auth_token: str = "my-secure-token"
    hc911_origin: str = "https://www.hamiltontn911.gov"
    hc911_poll_interval: int = 60
    hc911_enabled: bool = True

    user_agent: str = "LocalDash/0.1"

    # Frontend map config (served to the browser via /api/config).
    tile_url: str = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
    tile_attribution: str = "Tiles &copy; Esri"

    retention_days: int = 0

    @property
    def database_url_sync(self) -> str:
        """Sync SQLAlchemy URL (psycopg) for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()
