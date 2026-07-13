"""Pure tests for the events dedup key and fuzzy matcher.

The fuzzy-matcher cases pin real pairs observed in live data: upstream sites
listing the same event twice under different titles (must merge) and distinct
franchise events with near-identical titles in different cities (must not).
"""
import datetime as dt

from app.events.dedup import (
    MatchSide,
    canonical_key,
    events_match,
    normalize_title,
    titles_match,
)

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


# --- normalization with stopword folding ---


def test_stopword_variants_normalize_identically():
    assert normalize_title("Cars & Coffee Franklin") == normalize_title("Cars and Coffee Franklin")
    assert normalize_title("Ooltewah Cruise In @ Cambridge Square") == "ooltewah cruise cambridge square"


def test_stopword_variants_share_a_canonical_key():
    start = dt.datetime(2026, 7, 18, 13, 0, tzinfo=UTC)
    assert canonical_key("Cars & Coffee Franklin", start) == canonical_key(
        "Cars and Coffee Franklin", start
    )


def test_all_stopword_title_does_not_normalize_to_nothing():
    assert normalize_title("The In") == "the in"


# --- titles_match ---


def test_title_with_extra_word_matches():
    assert titles_match(
        "Scenic City Street Machines Sonic Cruise In",
        "Scenic City Street Machines Cruise in",
    )


def test_title_typo_matches_on_long_tokens():
    assert titles_match("Oltewah Cruise In", "Ooltewah Cruise In @ Cambridge Square")


def test_different_city_names_do_not_match():
    assert not titles_match("Cars and Coffee Franklin", "Cars And Coffee Memphis")


def test_short_distinctive_tokens_must_be_exact():
    # "731" must not fuzz away; {cars, coffee} would subset-match, but the
    # events differ by the short token only when it is on the smaller side.
    assert not titles_match("731 Cars and Coffee", "737 Cars and Coffee")


def test_single_token_title_never_matches():
    assert not titles_match("Show", "Show Boat Extravaganza Show")


# --- events_match: location gate ---


SONIC_A = MatchSide(
    title="Scenic City Street Machines Sonic Cruise In",
    start=dt.datetime(2026, 7, 23, 22, 0, tzinfo=UTC),
    venue_name="Sonic",
)
SONIC_B = MatchSide(
    title="Scenic City Street Machines Cruise in",
    start=dt.datetime(2026, 7, 23, 22, 0, tzinfo=UTC),
    venue_name="Sonic",
)


def test_observed_sonic_pair_merges_on_venue():
    assert events_match(SONIC_A, SONIC_B)


def test_typo_pair_merges_across_hour_boundary_when_coords_close():
    a = MatchSide(
        title="Oltewah Cruise In",
        start=dt.datetime(2026, 7, 13, 20, 0, tzinfo=UTC),
        coords=(35.0655, -85.0590),
    )
    b = MatchSide(
        title="Ooltewah Cruise In @ Cambridge Square",
        start=dt.datetime(2026, 7, 13, 21, 0, tzinfo=UTC),
        coords=(35.0651, -85.0585),
    )
    assert events_match(a, b)


def test_franchise_pair_far_apart_does_not_merge():
    a = MatchSide(
        title="731 Cars and Coffee",
        start=dt.datetime(2026, 7, 18, 13, 0, tzinfo=UTC),
        coords=(35.8256, -88.9070),  # Humboldt
    )
    b = MatchSide(
        title="Cars N' Coffee",
        start=dt.datetime(2026, 7, 18, 13, 0, tzinfo=UTC),
        coords=(35.9540, -85.0263),  # Crossville
    )
    assert not events_match(a, b)


def test_coords_take_precedence_over_matching_venue():
    # Same chain venue string in different cities: coordinates decide.
    a = SONIC_A._replace(coords=(35.0456, -85.3097))
    b = SONIC_B._replace(coords=(36.1627, -86.7816))  # Nashville
    assert not events_match(a, b)


def test_no_location_evidence_never_merges():
    a = SONIC_A._replace(venue_name=None)
    b = SONIC_B._replace(venue_name=None)
    assert not events_match(a, b)


def test_matching_address_text_merges_when_coords_missing():
    a = MatchSide(
        title="Downtown Cruise In",
        start=dt.datetime(2026, 8, 1, 22, 0, tzinfo=UTC),
        address="1 Broad St, Chattanooga, TN",
    )
    b = MatchSide(
        title="Downtown Sonic Cruise In",
        start=dt.datetime(2026, 8, 1, 22, 0, tzinfo=UTC),
        address="1 Broad St., Chattanooga TN",
    )
    assert events_match(a, b)


def test_start_times_more_than_two_hours_apart_do_not_merge():
    late = SONIC_B._replace(start=dt.datetime(2026, 7, 24, 1, 0, tzinfo=UTC))
    assert not events_match(SONIC_A, late)
