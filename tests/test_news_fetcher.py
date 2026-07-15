"""Offline tests for feed parsing helpers (no network, no DB)."""

from __future__ import annotations

import feedparser

from app.news.fetcher import _entry_image


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
