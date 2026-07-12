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

    # TDOT SmartWay source (Tennessee statewide roadway events).
    # Base URL + static app key are served to every SmartWay browser via the site's
    # runtime config.prod.json; see docs/tdot-smartway-api.md. Endpoints are the
    # event-style layers (they share one schema and are merged into this source).
    tdot_api_base_url: str = "https://www.tdot.tn.gov/opendata/api/public/"
    tdot_api_key: str = "8d3b7a82635d476795c09b2c41facc60"
    tdot_endpoints: str = "RoadwayIncidents,RoadwayOperations,RoadwaySpecialEvents,RoadwaySevereImpact"
    tdot_poll_interval: int = 120
    tdot_enabled: bool = True

    # EPB (Chattanooga) electric + fiber outages. The outage-storm-center map loads from
    # an unauthenticated public API at api.epb.com; one snapshot endpoint per service is
    # polled at {base}/{service}/incidents. See docs/epb-outage-api.md.
    epb_api_base_url: str = "https://api.epb.com/web/api/v2/outages"
    epb_services: str = "energy,fiber"
    epb_poll_interval: int = 60
    epb_enabled: bool = True

    user_agent: str = "LocalDash/0.1"

    # News feature (RSS aggregation; outlets/feeds live in app/news/registry.py).
    news_enabled: bool = True
    news_refresh_minutes: int = 15
    news_story_window_days: int = 7

    # Events feature (aggregation from configured sources; nothing is configured
    # by default, so the feature starts empty until feeds/token are set).
    events_enabled: bool = True
    events_refresh_minutes: int = 60
    events_ical_feeds: str = "https://carsandcoffeeevents.com/events/category/tennessee/?ical=1"  # comma-separated .ics URLs
    events_meetup_token: str = ""  # Meetup OAuth2 token; empty = source not registered
    events_meetup_query: str = ""  # optional Meetup keyword filter
    # Nominatim's usage policy requires a descriptive User-Agent.
    events_geocoder_user_agent: str = "LocalDash/0.1 (events geocoder)"
    # Nominatim's usage policy caps clients at 1 request/second; <= 0 disables
    # the throttle (e.g. for a self-hosted instance).
    events_geocoder_min_interval_seconds: float = 1.0

    # Frontend map config (served to the browser via /api/config). EPB's outage map
    # uses MapTiler's colorful "basic" style (green parks, blue water, cream roads),
    # but their key is domain-locked. CARTO Voyager is the closest no-key match and
    # keeps colored incident markers legible.
    tile_url: str = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
    tile_attribution: str = "&copy; OpenStreetMap &copy; CARTO"

    retention_days: int = 0

    @property
    def database_url_sync(self) -> str:
        """Sync SQLAlchemy URL (psycopg) for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()
