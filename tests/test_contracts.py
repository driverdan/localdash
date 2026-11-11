"""The shared response-model pieces in app/contracts.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.contracts import ApiModel, IsoDateTime


class _Stamp(ApiModel):
    at: IsoDateTime
    maybe: IsoDateTime | None = None


def _json(**fields) -> str:
    return _Stamp(**fields).model_dump_json()


def test_utc_datetime_keeps_numeric_offset():
    at = datetime(2026, 7, 10, 10, 0, tzinfo=UTC)
    assert _json(at=at) == '{"at":"2026-07-10T10:00:00+00:00","maybe":null}'


def test_non_utc_offset_is_kept():
    at = datetime(2026, 11, 6, 22, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert _Stamp(at=at).model_dump(mode="json")["at"] == "2026-11-06T22:00:00-05:00"


def test_microseconds_only_when_non_zero():
    at = datetime(2026, 7, 10, 10, 5, 30, 250000, tzinfo=UTC)
    assert _Stamp(at=at).model_dump(mode="json")["at"] == "2026-07-10T10:05:30.250000+00:00"
    whole = at.replace(microsecond=0)
    assert _Stamp(at=whole).model_dump(mode="json")["at"] == "2026-07-10T10:05:30+00:00"


def test_optional_datetime_serialises_when_set():
    at = datetime(2026, 7, 10, tzinfo=UTC)
    assert _Stamp(at=at, maybe=at).model_dump(mode="json")["maybe"] == "2026-07-10T00:00:00+00:00"


def test_api_model_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        _Stamp(at=datetime.now(UTC), extra="nope")
