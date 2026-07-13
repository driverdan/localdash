"""Local fixtures source: code-as-config registry of feedless local events.

Some flagship local events publish no machine-readable feed at all (no iCal,
no structured data), so no network source can ever surface them. Following the
news feature's registry precedent (app/news/registry.py), this module declares
them in code and expands their recurrence into concrete RawEvents each run,
bounded to the next 90 days.

Honest caveat — this is manual curation and drifts when organizers change
plans. Mitigations: every emitted event's source_url is the organizer's page
(users can verify), and explicit-date entries must be re-dated each year when
the next edition is announced (dates are never extrapolated — a wrong guessed
date is worse than a missing one). A fixture with no occurrence in the next
366 days logs a review warning at fetch time.

No network I/O happens here; addresses are geocoded by the ingest pipeline
like any other source's.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dateutil.rrule import MONTHLY, SU, rrule

from app.events.sources.base import EventSource, RawEvent

log = logging.getLogger("localdash.events")

SOURCE_NAME = "Local fixtures"
# Fixtures are declared in venue-local wall-clock time, as organizers publish.
LOCAL_TZ = ZoneInfo("America/New_York")
HORIZON_DAYS = 90
STALE_LOOKAHEAD_DAYS = 366


@dataclass(frozen=True)
class Fixture:
    """One curated event: recurrence (`rule`) or explicit `dates`, never both."""

    slug: str
    title: str
    description: str
    venue_name: str
    address: str
    source_url: str
    starts: dt.time
    ends: dt.time
    rule: rrule | None = None
    dates: tuple[dt.date, ...] = ()

    def __post_init__(self) -> None:
        if (self.rule is None) == (not self.dates):
            raise ValueError(f"fixture {self.slug!r} needs exactly one of rule or dates")


def _local_dates(fixture: Fixture, window_start: dt.datetime, window_end: dt.datetime) -> list[dt.date]:
    """Candidate occurrence dates (local calendar) overlapping the UTC window."""
    if fixture.dates:
        return list(fixture.dates)
    # Pad a day on each side; the caller filters precisely on the UTC instant.
    naive_start = window_start.astimezone(LOCAL_TZ).replace(tzinfo=None) - dt.timedelta(days=1)
    naive_end = window_end.astimezone(LOCAL_TZ).replace(tzinfo=None) + dt.timedelta(days=1)
    return [occ.date() for occ in fixture.rule.between(naive_start, naive_end, inc=True)]


def expand(fixture: Fixture, window_start: dt.datetime, window_end: dt.datetime) -> list[RawEvent]:
    """Expand one fixture into RawEvents whose UTC start falls inside the window.

    Pure function of the fixture and an explicit aware-UTC window, so tests
    never depend on wall time. Local wall-clock times are localized per
    occurrence date, keeping 8am local correct on both sides of a DST change.
    """
    events: list[RawEvent] = []
    for day in _local_dates(fixture, window_start, window_end):
        start = dt.datetime.combine(day, fixture.starts, tzinfo=LOCAL_TZ).astimezone(dt.timezone.utc)
        if not window_start <= start <= window_end:
            continue
        end = dt.datetime.combine(day, fixture.ends, tzinfo=LOCAL_TZ).astimezone(dt.timezone.utc)
        events.append(
            RawEvent(
                title=fixture.title,
                description=fixture.description,
                start_time=start,
                end_time=end,
                venue_name=fixture.venue_name,
                address=fixture.address,
                source_name=SOURCE_NAME,
                source_url=fixture.source_url,
                source_event_id=f"{fixture.slug}-{day.isoformat()}",
            )
        )
    return events


def is_stale(fixture: Fixture, now: dt.datetime) -> bool:
    """True when the fixture yields nothing in the next STALE_LOOKAHEAD_DAYS."""
    return not expand(fixture, now, now + dt.timedelta(days=STALE_LOOKAHEAD_DAYS))


FIXTURES: tuple[Fixture, ...] = (
    Fixture(
        slug="chattanooga-cars-and-coffee",
        title="Chattanooga Cars and Coffee",
        description=(
            "Monthly open car meet on the third Sunday, March through November. "
            "All makes welcome; hosted at Chattanooga State Community College."
        ),
        venue_name="Chattanooga State Community College",
        address="4501 Amnicola Hwy, Chattanooga, TN 37406",
        source_url="https://chattanoogacarsandcoffee.com/",
        starts=dt.time(8, 0),
        ends=dt.time(12, 0),
        rule=rrule(MONTHLY, byweekday=SU(3), bymonth=tuple(range(3, 12)), dtstart=dt.datetime(2024, 1, 1)),
    ),
    Fixture(
        slug="riverside-chattanooga",
        title="Riverside Chattanooga",
        description=(
            "Annual auto-culture festival at Finley Stadium. Dates are the last "
            "announced edition (March 20-21, 2026); the organizer has announced "
            "March 2027 without dates yet - re-date this entry when they publish."
        ),
        venue_name="Finley Stadium / First Horizon Pavilion",
        address="1826 Reggie White Blvd, Chattanooga, TN 37402",
        source_url="https://www.riversidechattanooga.com/",
        starts=dt.time(9, 0),
        ends=dt.time(17, 0),
        dates=(dt.date(2026, 3, 20), dt.date(2026, 3, 21)),
    ),
    Fixture(
        slug="world-of-wheels-chattanooga",
        title="World of Wheels Chattanooga",
        description=(
            "Annual indoor custom car show at the Chattanooga Convention Center. "
            "Dates are the 2026 edition (January 9-11); re-date this entry when "
            "the next edition is announced."
        ),
        venue_name="Chattanooga Convention Center",
        address="1 Carter Plaza, Chattanooga, TN 37402",
        source_url="https://worldofwheels.net/chattanooga/",
        starts=dt.time(10, 0),
        ends=dt.time(18, 0),
        dates=(dt.date(2026, 1, 9), dt.date(2026, 1, 10), dt.date(2026, 1, 11)),
    ),
)


class FixturesSource(EventSource):
    name = SOURCE_NAME

    def __init__(self, fixtures: tuple[Fixture, ...] = FIXTURES):
        self.fixtures = fixtures

    async def fetch(self) -> list[RawEvent]:
        now = dt.datetime.now(dt.timezone.utc)
        window_end = now + dt.timedelta(days=HORIZON_DAYS)
        events: list[RawEvent] = []
        for fixture in self.fixtures:
            occurrences = expand(fixture, now, window_end)
            if not occurrences and is_stale(fixture, now):
                log.warning(
                    "events fixture %r has no occurrence in the next %d days - "
                    "needs review against %s",
                    fixture.slug, STALE_LOOKAHEAD_DAYS, fixture.source_url,
                )
            events.extend(occurrences)
        return events
