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
    tdot_endpoints: str = (
        "RoadwayIncidents,RoadwayOperations,RoadwaySpecialEvents,RoadwaySevereImpact"
    )
    tdot_poll_interval: int = 120
    tdot_enabled: bool = True

    # EPB (Chattanooga) electric + fiber outages. The outage-storm-center map loads from
    # an unauthenticated public API at api.epb.com; one snapshot endpoint per service is
    # polled at {base}/{service}/incidents. See docs/epb-outage-api.md.
    epb_api_base_url: str = "https://api.epb.com/web/api/v2/outages"
    epb_services: str = "energy,fiber"
    epb_poll_interval: int = 60
    epb_enabled: bool = True

    # Tennessee American Water advisories (Chattanooga-area water). The public
    # Customer Advisory Map is an Esri Web AppBuilder app backed by an
    # unauthenticated ArcGIS MapServer; the national feed is filtered to
    # `tnaw_state` server-side and the two Active advisory layers are polled as
    # GeoJSON (polygons). See docs/tnaw-advisory-api.md.
    tnaw_api_base_url: str = (
        "https://utility.arcgis.com/usrsvcs/servers/482bbe2135c54d178ec406189303faf4"
        "/rest/services/CustomerAdvisoryMap/DisplayData_SDE/MapServer"
    )
    tnaw_state: str = "TN"
    # layer id -> advisory category. 17 = Active–Emergency, 16 = Active–General.
    # (15 = Lifted is intentionally not ingested; the closure sweep retires lifted
    # advisories when they drop out of the Active layers.)
    tnaw_layers: str = "17:emergency,16:general"
    tnaw_poll_interval: int = 300
    tnaw_enabled: bool = True

    user_agent: str = "LocalDash/0.1"

    # Shared app-level center coordinate (Chattanooga by default): the events
    # distance origin / source defaults and the weather location.
    center_lat: float = 35.0456
    center_lon: float = -85.3097

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
    # CitySpark calendar (The Pulse's local-events widget; undocumented internal
    # JSON API — see app/events/sources/cityspark.py). The defaults are the
    # portal's own: 25-mile radius around the Chattanooga center, 14-day window.
    events_cityspark_enabled: bool = True
    events_cityspark_slug: str = "ChattanoogaPulse"
    events_cityspark_ppid: int = 9824
    events_cityspark_radius_miles: float = 25
    events_cityspark_lookahead_days: int = 14
    # Nominatim's usage policy requires a descriptive User-Agent.
    events_geocoder_user_agent: str = "LocalDash/0.1 (events geocoder)"
    # Nominatim's usage policy caps clients at 1 request/second; <= 0 disables
    # the throttle (e.g. for a self-hosted instance).
    events_geocoder_min_interval_seconds: float = 1.0
    # Re-attempt cached geocode failures once their last attempt is older than
    # this many hours; non-positive disables the retry pass.
    events_geocode_retry_hours: float = 24
    # Max cached failures re-attempted per refresh cycle.
    events_geocode_retry_batch: int = 25
    # Drop newly ingested events whose address geocodes farther than this many
    # miles from the Chattanooga center; non-positive disables the filter.
    events_ingest_max_miles: float = 100

    # Weather feature (NWS proxy for the homepage strip; no DB, no scheduler —
    # fetch-on-demand at the shared center, cached in-process for the TTL below).
    weather_enabled: bool = True
    weather_cache_minutes: int = 10
    # AirNow AQI, folded into the weather payload and riding its cache. The key
    # doubles as the switch: empty means no AirNow requests and `aqi` null.
    airnow_api_key: str = ""

    # Frontend map config (served to the browser via /api/config). EPB's outage map
    # uses MapTiler's colorful "basic" style (green parks, blue water, cream roads),
    # but their key is domain-locked. CARTO Voyager is the closest no-key match and
    # keeps colored incident markers legible.
    tile_url: str = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
    tile_attribution: str = "&copy; OpenStreetMap &copy; CARTO"

    retention_days: int = 0

    @property
    def center(self) -> tuple[float, float]:
        """Shared center as a (lat, lon) tuple for distance/geo call sites."""
        return (self.center_lat, self.center_lon)

    @property
    def database_url_sync(self) -> str:
        """Sync SQLAlchemy URL (psycopg) for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()
