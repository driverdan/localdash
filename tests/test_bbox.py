"""Unit tests for the API bbox query-param parser."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.timeseries import _bbox_filter
from app.models import Entity


def test_bbox_none_returns_none():
    assert _bbox_filter(Entity.last_geom, None) is None
    assert _bbox_filter(Entity.last_geom, "") is None


def test_bbox_valid_returns_sql_expression():
    pred = _bbox_filter(Entity.last_geom, "-85.4,35.0,-85.1,35.2")
    # A SQLAlchemy ST_Intersects expression, not None.
    assert pred is not None
    assert "ST_Intersects" in str(pred)


def test_bbox_malformed_raises_400():
    for bad in ("1,2,3", "a,b,c,d", "1,2,3,4,5"):
        with pytest.raises(HTTPException) as exc:
            _bbox_filter(Entity.last_geom, bad)
        assert exc.value.status_code == 400
