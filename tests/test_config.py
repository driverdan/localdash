"""Unit tests for settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_sync_url_swaps_async_driver():
    s = Settings(database_url="postgresql+asyncpg://u:p@h:5432/db")
    assert s.database_url_sync == "postgresql+psycopg://u:p@h:5432/db"


def test_sync_url_noop_when_no_async_driver():
    s = Settings(database_url="postgresql+psycopg://u:p@h:5432/db")
    assert s.database_url_sync == "postgresql+psycopg://u:p@h:5432/db"


def test_defaults_present():
    s = Settings()
    assert s.hc911_poll_interval >= 60  # never poll faster than the source cadence
    assert s.hc911_api_url.startswith("https://")


def test_get_settings_is_cached():
    assert get_settings() is get_settings()


def test_center_defaults_and_tuple_property():
    s = Settings()
    assert s.center == (35.0456, -85.3097)  # Chattanooga defaults
    assert s.center == (s.center_lat, s.center_lon)


def test_center_is_env_overridable():
    s = Settings(center_lat=36.0, center_lon=-86.0)
    assert s.center == (36.0, -86.0)


@pytest.mark.parametrize("field", ["user_agent", "events_geocoder_user_agent"])
@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_user_agent_settings_are_rejected(field, blank):
    # Every outbound request must send a real User-Agent; a blank one fails at load.
    with pytest.raises(ValidationError, match=field):
        Settings(_env_file=None, **{field: blank})


@pytest.mark.parametrize("field", ["user_agent", "events_geocoder_user_agent"])
def test_user_agent_settings_have_non_blank_defaults(field):
    assert getattr(Settings(_env_file=None), field).strip()
