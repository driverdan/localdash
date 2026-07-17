"""Events feature: aggregate, de-duplicate, tag, and geocode area events.

Ported from the standalone chattevents PoC. A sibling feature beside
timeseries and news — events do not flow through collectors/ingest (they are
merged cross-source records, not entity state over time).

Pipeline: sources (config-driven, sources/) -> ingest (dedup + tag + geocode,
ingest.py) -> /api/v1/events/ (app/api/events.py) -> /events page.
"""

from __future__ import annotations

# The distance origin for the API and the Meetup search filter comes from the
# shared app-level center settings (get_settings().center in app/config.py).

# Meetup keywordSearch radius; not config — matches the PoC default.
MEETUP_RADIUS_MILES = 50
