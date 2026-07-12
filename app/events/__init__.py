"""Events feature: aggregate, de-duplicate, tag, and geocode area events.

Ported from the standalone chattevents PoC. A sibling feature beside
timeseries and news — events do not flow through collectors/ingest (they are
merged cross-source records, not entity state over time).

Pipeline: sources (config-driven, sources/) -> ingest (dedup + tag + geocode,
ingest.py) -> /api/v1/events/ (app/api/events.py) -> /events page.
"""
from __future__ import annotations

# Distance origin for the API and the Meetup search filter (lat, lon).
CHATTANOOGA_CENTER: tuple[float, float] = (35.0456, -85.3097)

# Meetup keywordSearch radius; not config — matches the PoC default.
MEETUP_RADIUS_MILES = 50
