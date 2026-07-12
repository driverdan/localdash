"""Event de-duplication.

The same event is frequently published by several sources with slightly
different titles ("Jazz Night!" vs "jazz night"). We collapse them onto a
single canonical event using a hash of the normalized title plus the start
day and hour, so minor wording differences still merge. Known caveat (ported
from the PoC): listings straddling an hour boundary do not merge.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re

_NON_ALNUM = re.compile(r"[^a-z0-9 ]")
_WHITESPACE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace."""
    text = _NON_ALNUM.sub(" ", title.lower())
    return _WHITESPACE.sub(" ", text).strip()


def canonical_key(title: str, start_time: dt.datetime) -> str:
    """Stable de-duplication key for an event.

    Two events with the same normalized title that start within the same UTC
    hour are treated as the same event. Naive datetimes are taken as UTC.
    """
    if start_time.tzinfo is not None:
        start_time = start_time.astimezone(dt.timezone.utc)
    basis = f"{normalize_title(title)}|{start_time.strftime('%Y-%m-%dT%H')}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]
