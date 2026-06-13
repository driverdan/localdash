"""Shared test fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def hc911_payload() -> list[dict]:
    return json.loads((FIXTURE_DIR / "hc911_sample.json").read_text())


@pytest.fixture
def settings() -> Settings:
    return Settings()
