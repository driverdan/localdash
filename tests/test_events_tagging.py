"""Pure tests for events topic tagging (ported from the chattevents PoC)."""
from app.events.tagging import tag_event


def test_music_keyword_detected():
    assert "music" in tag_event("Live Jazz Concert")


def test_multiple_topics_detected():
    tags = tag_event("Kids Art Workshop", "A family friendly art class")
    assert {"arts", "family", "education"} <= tags


def test_no_match_returns_empty_set():
    assert tag_event("Untitled", "") == set()
