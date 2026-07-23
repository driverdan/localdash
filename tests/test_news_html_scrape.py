"""Offline tests for the kind='html' news scrape path (fixture HTML, no network,
no DB): the pure parse_html_listing parser and the feed_kind registry lookup."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.news.fetcher import parse_html_listing
from app.news.registry import feed_kind

FIXTURES = Path(__file__).parent / "fixtures" / "chattgov"
BASE_URL = "https://chattanooga.gov/stay-informed/latest-news"


def load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parses_rows_skipping_untitled():
    rows = parse_html_listing(load("listing.html"), BASE_URL)
    # Fixture has 5 .views-row blocks; the one without a title link is dropped.
    assert len(rows) == 4
    titles = [r["title"] for r in rows]
    assert "City of Chattanooga piloting Civic Dialogue with partners" in titles
    assert all("no title link" not in t for t in titles)


def test_absolute_url_is_guid():
    rows = parse_html_listing(load("listing.html"), BASE_URL)
    first = rows[0]
    assert first["url"] == (
        "https://chattanooga.gov/stay-informed/latest-news/"
        "city-chattanooga-piloting-civic-dialogue-partners"
    )
    assert first["guid"] == first["url"]


def test_summary_extracted_and_image_is_none():
    rows = parse_html_listing(load("listing.html"), BASE_URL)
    first = rows[0]
    assert first["summary"].startswith("Positioned at the forefront of civic innovation")
    assert first["image_url"] is None


def test_published_normalized_to_utc():
    rows = parse_html_listing(load("listing.html"), BASE_URL)
    first = rows[0]
    # 2026-07-22T15:28:48-04:00 -> 19:28:48Z
    assert first["published"] == datetime(2026, 7, 22, 19, 28, 48, tzinfo=timezone.utc)
    assert first["published"].tzinfo is not None


def test_row_without_body_gets_empty_summary():
    rows = parse_html_listing(load("listing.html"), BASE_URL)
    road = next(r for r in rows if "ROAD CLOSURES" in r["title"])
    assert road["summary"] == ""


def test_unparseable_date_falls_back_to_now():
    before = datetime.now(timezone.utc)
    rows = parse_html_listing(load("listing.html"), BASE_URL)
    after = datetime.now(timezone.utc)
    shooting = next(r for r in rows if r["title"] == "Shooting - Hawkins Oak Lane")
    assert before <= shooting["published"] <= after


def test_empty_page_yields_no_rows():
    assert parse_html_listing("<html><body>no view here</body></html>", BASE_URL) == []


def test_feed_kind_html_for_chattgov():
    assert feed_kind("https://chattanooga.gov/stay-informed/latest-news") == "html"


def test_feed_kind_rss_for_existing_feed():
    assert feed_kind("https://www.wdef.com/category/news/feed/") == "rss"


def test_feed_kind_defaults_to_rss_for_unknown_url():
    assert feed_kind("https://example.com/does-not-exist/feed") == "rss"
