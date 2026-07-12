"""Pure tests for the events dedup key (ported from the chattevents PoC)."""
import datetime as dt

from app.events.dedup import canonical_key, normalize_title

UTC = dt.timezone.utc


def test_normalize_strips_punctuation_and_case():
    assert normalize_title("  Jazz, Night! ") == "jazz night"


def test_same_event_different_formatting_shares_key():
    start = dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    assert canonical_key("Jazz Night!", start) == canonical_key("jazz night", start)


def test_same_title_within_same_hour_shares_key():
    a = canonical_key("Jazz Night", dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC))
    b = canonical_key("Jazz Night", dt.datetime(2026, 7, 1, 19, 45, tzinfo=UTC))
    assert a == b


def test_different_day_produces_different_key():
    a = canonical_key("Jazz Night", dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC))
    b = canonical_key("Jazz Night", dt.datetime(2026, 7, 2, 19, 0, tzinfo=UTC))
    assert a != b


def test_key_compares_in_utc_across_timezones():
    # 19:00 UTC and 15:00 UTC-4 are the same instant, so the same event.
    utc = dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    local = dt.datetime(2026, 7, 1, 15, 0, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
    assert canonical_key("Jazz Night", utc) == canonical_key("Jazz Night", local)


def test_naive_datetime_treated_as_utc():
    aware = dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    naive = dt.datetime(2026, 7, 1, 19, 0)
    assert canonical_key("Jazz Night", aware) == canonical_key("Jazz Night", naive)
