"""Event de-duplication.

The same event is frequently published several times — by different sources
and by duplicate listings within one source — under slightly different titles
("Jazz Night!" vs "jazz night", "… Sonic Cruise In" vs "… Cruise in"). Ingest
collapses them in tiers: an exact source-listing match, then the exact
:func:`canonical_key` hash, then the fuzzy :func:`events_match` candidate
test. The fuzzy tier merges only when the listings' locations agree — title
similarity alone must never merge, because franchise events ("Cars and Coffee
<city>") share near-identical titles at the same hour in different cities.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import re
from typing import NamedTuple

_NON_ALNUM = re.compile(r"[^a-z0-9 ]")
_WHITESPACE = re.compile(r"\s+")

# Folded out of normalized titles so "Cars & Coffee" == "Cars and Coffee".
_STOPWORDS = frozenset({"a", "an", "and", "at", "in", "n", "of", "on", "the", "to", "with"})

# Fuzzy tier thresholds, chosen from observed duplicate/false pairs.
_FUZZY_TOKEN_MIN_LEN = 5  # shorter tokens must match exactly ("731", "memphis"[7] vs "franklin")
_MAX_START_DELTA = dt.timedelta(hours=2)
_MAX_MILES_APART = 0.5


def _title_tokens(title: str) -> list[str]:
    """Lowercased, punctuation-stripped tokens with stopwords folded out.

    An all-stopword title keeps its raw tokens rather than collapsing to
    nothing (which would merge every such title within an hour bucket).
    """
    tokens = _NON_ALNUM.sub(" ", title.lower()).split()
    kept = [t for t in tokens if t not in _STOPWORDS]
    return kept or tokens


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, drop stopwords."""
    return " ".join(_title_tokens(title))


def canonical_key(title: str, start_time: dt.datetime) -> str:
    """Stable de-duplication key for an event.

    Two events with the same normalized title that start within the same UTC
    hour are treated as the same event. Naive datetimes are taken as UTC.
    """
    basis = f"{normalize_title(title)}|{_as_utc(start_time).strftime('%Y-%m-%dT%H')}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in miles between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 3958.8 * math.asin(math.sqrt(h))


def _as_utc(t: dt.datetime) -> dt.datetime:
    if t.tzinfo is None:
        return t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc)


def _within_one_edit(a: str, b: str) -> bool:
    """True when a and b are equal or one insertion/deletion/substitution apart."""
    if len(a) > len(b):
        a, b = b, a
    if len(b) - len(a) > 1:
        return False
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1 :] == b[i + 1 :]
    return a[i:] == b[i + 1 :]


def _tokens_equal(a: str, b: str) -> bool:
    """Exact match, with one-edit typo tolerance for longer tokens only."""
    if a == b:
        return True
    if min(len(a), len(b)) < _FUZZY_TOKEN_MIN_LEN:
        return False
    return _within_one_edit(a, b)


def titles_match(a: str, b: str) -> bool:
    """True when one title's token set is contained in the other's.

    Covers the observed duplicate pattern — the same title with a word added
    or dropped — while requiring at least two tokens on the smaller side.
    Tokens compare with :func:`_tokens_equal`, so a minor typo
    ("Oltewah"/"Ooltewah") still matches but short distinctive tokens (city
    names, numbers) must be identical.
    """
    ta, tb = _title_tokens(a), _title_tokens(b)
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(small) < 2:
        return False
    remaining = list(big)
    for token in small:
        for i, other in enumerate(remaining):
            if _tokens_equal(token, other):
                del remaining[i]
                break
        else:
            return False
    return True


class MatchSide(NamedTuple):
    """One event's matching signals, detached from any storage model."""

    title: str
    start: dt.datetime
    coords: tuple[float, float] | None = None
    venue_name: str | None = None
    address: str | None = None


def events_match(a: MatchSide, b: MatchSide) -> bool:
    """Fuzzy duplicate test: similar titles, close starts, agreeing locations.

    Location agreement is a hard gate. When both sides are geocoded their
    coordinates decide (venue strings like "Sonic" repeat across cities);
    venue/address text equality applies only when coordinates are missing on
    at least one side. With no location evidence at all, this never matches —
    the exact canonical key still covers identical titles in the same hour.
    """
    if abs(_as_utc(a.start) - _as_utc(b.start)) > _MAX_START_DELTA:
        return False
    if not titles_match(a.title, b.title):
        return False
    if a.coords is not None and b.coords is not None:
        return haversine_miles(a.coords, b.coords) <= _MAX_MILES_APART
    for a_text, b_text in ((a.venue_name, b.venue_name), (a.address, b.address)):
        if a_text and b_text and normalize_title(a_text) == normalize_title(b_text):
            return True
    return False
