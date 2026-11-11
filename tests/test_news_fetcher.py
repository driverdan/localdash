"""Offline tests for feed parsing helpers (no network, no DB)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import feedparser

from app.news import fetcher
from app.news.fetcher import _article_row, _entry_image, _entry_summary


def _entry(item_xml: str):
    rss = (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
        f"<item><title>Headline</title><link>https://ex.com/a</link>{item_xml}</item>"
        "</channel></rss>"
    )
    return feedparser.parse(rss).entries[0]


def test_image_enclosure_is_captured():
    entry = _entry('<enclosure url="https://ex.com/pic.jpg" type="image/jpeg" length="1"/>')
    assert _entry_image(entry) == "https://ex.com/pic.jpg"


def test_inline_img_is_the_fallback():
    entry = _entry(
        "<description>&lt;p&gt;Text &lt;img src=&quot;https://ex.com/inline.png&quot;&gt;"
        "&lt;/p&gt;</description>"
    )
    assert _entry_image(entry) == "https://ex.com/inline.png"


def test_enclosure_wins_over_inline_img():
    entry = _entry(
        '<enclosure url="https://ex.com/enc.jpg" type="image/jpeg" length="1"/>'
        "<description>&lt;img src=&quot;https://ex.com/inline.png&quot;&gt;</description>"
    )
    assert _entry_image(entry) == "https://ex.com/enc.jpg"


def test_no_image_is_none():
    entry = _entry("<description>Just words, no markup.</description>")
    assert _entry_image(entry) is None


def test_non_image_enclosure_ignored():
    entry = _entry('<enclosure url="https://ex.com/audio.mp3" type="audio/mpeg" length="1"/>')
    assert _entry_image(entry) is None


# --- _entry_summary: raw-content priority ---


def test_summary_prefers_content_over_summary_and_description():
    entry = SimpleNamespace(
        content=[{"value": "<p>From content.</p>"}],
        summary="From summary.",
        description="From description.",
    )
    assert _entry_summary(entry) == "From content."


def test_summary_falls_back_to_summary_before_description():
    entry = SimpleNamespace(content=[], summary="<b>From summary.</b>", description="Desc.")
    assert _entry_summary(entry) == "From summary."


def test_summary_falls_back_to_description():
    entry = SimpleNamespace(summary="", description="From description.")
    assert _entry_summary(entry) == "From description."


def test_summary_is_empty_without_any_content():
    assert _entry_summary(SimpleNamespace()) == ""


def test_summary_from_a_parsed_feed_entry():
    entry = _entry("<description>&lt;p&gt;Hello &amp;amp; welcome.&lt;/p&gt;</description>")
    assert _entry_summary(entry) == "Hello & welcome."


# --- _article_row ---


def test_article_row_builds_the_nine_keys_and_passes_tags_to_classify(monkeypatch):
    calls = []

    def fake_classify(title, summary, tags, fallback):
        calls.append((title, summary, tags, fallback))
        return "classified"

    monkeypatch.setattr(fetcher, "classify", fake_classify)
    feed = SimpleNamespace(source_id=7, category="local")
    published = datetime(2026, 1, 1, 12, tzinfo=UTC)
    now = datetime(2026, 1, 1, 13, tzinfo=UTC)

    # The HTML listing path: no feed tags.
    row = _article_row(
        feed,
        guid="https://ex.com/a",
        url="https://ex.com/a",
        title="Headline",
        summary="Body.",
        image_url=None,
        tags=[],
        published=published,
        now=now,
    )

    assert row == {
        "source_id": 7,
        "guid": "https://ex.com/a",
        "url": "https://ex.com/a",
        "title": "Headline",
        "summary": "Body.",
        "image_url": None,
        "category": "classified",
        "published": published,
        "fetched_at": now,
    }
    assert calls == [("Headline", "Body.", [], "local")]
