"""Chattanooga Zoo events scraper source.

The zoo publishes no machine endpoint of any kind — ``.ics``, ``/feed``, ``/api``,
``/actions/element-api``, ``.rss``, and ``sitemap.xml`` all 404, and the markup
carries no JSON-LD, microdata, or Open Graph tags. It is a hand-rolled Craft CMS
site, so scraping the human-facing pages is the only route.

Unlike :mod:`app.events.sources.carcruisefinder`, this source is **two-hop**: it
fetches the listing page and then each linked detail page. That is not a
regression of CarCruiseFinder's listing-only rule — that rule exists because
*that* site's detail pages carry wrong UTC offsets (EST on August dates), which
would shift canonical keys and break cross-source dedup. The zoo's detail pages
carry no offsets at all, and they are the only place dates appear: the listing
page has nothing but title, image, and link.

**Year-less dates.** Detail pages render occurrences as free text with no year —
``March 22 | 9:00 AM - 5:00 PM`` — and they retain stale occurrences from earlier
in the year. Each occurrence is resolved by picking, among the previous, current,
and next calendar year, the candidate date nearest today, and then dropping
anything already over. Rolling a past-looking date forward instead would turn the
zoo's leftover March entry into a fictional next-year event; fabricating events is
worse than missing them. The rule is wrong for anything published more than
roughly six months out, which is accepted: it fails toward dropping, never toward
inventing.

One detail page routinely lists several dates (Adventure Days lists four), so a
page fans out into one :class:`RawEvent` per surviving occurrence, and
``source_event_id`` carries the occurrence date — the page slug alone would
collapse them on ingest's exact source-listing dedup tier.

Every zoo event is at one address, so the venue coordinates are supplied directly
and this source adds no geocoder load. The site serves plain requests fine, so no
browser User-Agent is spoofed. Breakage manifests as zero events plus logs,
contained by ``run_sources()``'s per-source failure isolation.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.events.sources.base import EventSource, RawEvent, clean_image_url

log = logging.getLogger("localdash.events")

LISTING_URL = "https://chattzoo.org/events/zooevents"
SOURCE_NAME = "Chattanooga Zoo"

# Every event on this calendar happens here, so coordinates are supplied rather
# than geocoded (the address is still supplied: it is displayed in the UI and
# used by the de-duplication location gate).
VENUE_NAME = "Chattanooga Zoo"
VENUE_ADDRESS = "301 North Holtzclaw Avenue, Chattanooga, TN 37404"
VENUE_LAT = 35.0430921
VENUE_LON = -85.2831511

# Naive times on the detail pages are venue-local.
LOCAL_TZ = ZoneInfo("America/New_York")

# "March 22 | 9:00 AM - 5:00 PM" — minutes are optional in practice.
_OCCURRENCE_RE = re.compile(
    r"""^\s*
    (?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})
    \s*\|\s*
    (?P<start>\d{1,2}(?::\d{2})?\s*[AaPp]\.?[Mm]\.?)
    \s*(?:-|–|—|to)\s*
    (?P<end>\d{1,2}(?::\d{2})?\s*[AaPp]\.?[Mm]\.?)
    \s*$""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class ListingEntry:
    """One card on the listing page: everything the listing knows."""

    title: str
    url: str
    image_url: str | None


def _clean_text(node) -> str:
    """Collapsed visible text of a BeautifulSoup node."""
    return " ".join(node.get_text(" ").split()) if node is not None else ""


def _parse_time(value: str) -> dt.time | None:
    """Parse "9:00 AM" / "9 AM" / "9 a.m." into a time, or None."""
    normalized = value.replace(".", "").upper().replace(" ", "")
    for fmt in ("%I:%M%p", "%I%p"):
        try:
            return dt.datetime.strptime(normalized, fmt).time()
        except ValueError:
            continue
    return None


def resolve_year(month: int, day: int, today: dt.date) -> dt.date | None:
    """The month/day date nearest ``today``, among last, this, and next year.

    Returns ``None`` when the month/day is not a real date in any candidate
    year (e.g. February 29 outside a leap year).
    """
    candidates: list[dt.date] = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(dt.date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda d: abs((d - today).days))


def parse_occurrence(text: str, now: dt.datetime) -> tuple[dt.datetime, dt.datetime] | None:
    """Resolve one year-less occurrence string to aware UTC start/end times.

    Returns ``None`` when the string is unparseable or the occurrence is over.
    """
    match = _OCCURRENCE_RE.match(text)
    if match is None:
        return None
    try:
        month = dt.datetime.strptime(match["month"][:3], "%b").month
    except ValueError:
        return None
    start_time = _parse_time(match["start"])
    end_time = _parse_time(match["end"])
    if start_time is None or end_time is None:
        return None

    now_local = now.astimezone(LOCAL_TZ)
    date = resolve_year(month, int(match["day"]), now_local.date())
    if date is None:
        return None

    start = dt.datetime.combine(date, start_time, tzinfo=LOCAL_TZ)
    end = dt.datetime.combine(date, end_time, tzinfo=LOCAL_TZ)
    if end <= start:  # crosses midnight
        end += dt.timedelta(days=1)
    if end < now:  # already over — in-progress events are kept
        return None
    return start.astimezone(dt.timezone.utc), end.astimezone(dt.timezone.utc)


def parse_listing(html: str, listing_url: str = LISTING_URL) -> list[ListingEntry]:
    """Extract the event cards from the listing page (pure, offline).

    The listing carries no dates; each entry must be followed to its detail page.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: list[ListingEntry] = []
    seen: set[str] = set()
    for card in soup.select("a.col.third.fundraiser[href]"):
        url = urljoin(listing_url, card["href"].strip())
        if url in seen:
            continue
        title = _clean_text(card.find(["h2", "h3"]))
        if not title:
            log.warning("chattzoo: listing card without a title skipped: %s", url)
            continue
        image = card.find("img")
        seen.add(url)
        entries.append(
            ListingEntry(
                title=title,
                url=url,
                image_url=clean_image_url(image.get("src") if image else None),
            )
        )
    return entries


def _description(soup: BeautifulSoup) -> str:
    """The event blurb: the tagline beside the dates, else the article body."""
    header = soup.select_one(".event-logo")
    if header is not None:
        tagline = " ".join(
            _clean_text(node) for node in header.find_all(["h3", "p"], recursive=False)
        )
        if tagline.strip():
            return tagline.strip()
    body = soup.select_one("#prices section.two-thirds")
    if body is not None:
        return " ".join(_clean_text(p) for p in body.find_all("p")).strip()
    return ""


def parse_detail(
    html: str,
    url: str,
    entry: ListingEntry,
    now: dt.datetime,
) -> list[RawEvent]:
    """Fan one detail page out into a raw event per surviving occurrence (pure)."""
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one(".event-logo h5")
    if header is None:
        log.warning("chattzoo: no occurrence block on detail page %s", url)
        return []

    title = _clean_text(soup.select_one(".intro h1")) or entry.title
    description = _description(soup)
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]

    events: list[RawEvent] = []
    for span in header.find_all("span"):
        text = _clean_text(span)
        if not text:
            continue
        window = parse_occurrence(text, now)
        if window is None:
            log.info("chattzoo: occurrence %r on %s not usable (unparseable or past)", text, url)
            continue
        start, end = window
        events.append(
            RawEvent(
                title=title,
                description=description,
                start_time=start,
                end_time=end,
                venue_name=VENUE_NAME,
                address=VENUE_ADDRESS,
                latitude=VENUE_LAT,
                longitude=VENUE_LON,
                image_url=entry.image_url,
                source_name=SOURCE_NAME,
                source_url=url,
                source_event_id=f"{slug}#{start.astimezone(LOCAL_TZ).date().isoformat()}",
            )
        )
    return events


class ChattZooSource(EventSource):
    name = SOURCE_NAME

    def __init__(
        self,
        url: str = LISTING_URL,
        user_agent: str = "LocalDash/0.1",
        timeout: int = 20,
    ):
        self.url = url
        self.user_agent = user_agent
        self.timeout = timeout

    async def fetch(self) -> list[RawEvent]:
        headers = {"User-Agent": self.user_agent}
        now = dt.datetime.now(dt.timezone.utc)
        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True, headers=headers
        ) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
            entries = parse_listing(resp.text, self.url)

            events: list[RawEvent] = []
            for entry in entries:
                # One bad detail page must not cost the other events.
                try:
                    detail = await client.get(entry.url)
                    detail.raise_for_status()
                except httpx.HTTPError as exc:
                    log.warning("chattzoo: detail page %s failed: %s", entry.url, exc)
                    continue
                events.extend(parse_detail(detail.text, entry.url, entry, now))
        return events
