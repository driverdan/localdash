"""Pure tests for events topic tagging (ported from the chattevents PoC)."""
from app.events.tagging import tag_event


def test_music_keyword_detected():
    assert "music" in tag_event("Live Jazz Concert")


def test_multiple_topics_detected():
    tags = tag_event("Kids Art Workshop", "A family friendly art class")
    assert {"arts", "family", "education"} <= tags


def test_no_match_returns_empty_set():
    assert tag_event("Untitled", "") == set()


def test_cars_tagged_on_cruise_in():
    assert tag_event("Ooltewah Cruise In @ Cambridge Square") == {"cars"}


def test_cars_tagged_on_cars_and_coffee():
    assert "cars" in tag_event("Cars and Coffee Sunday Meetup")


def test_cars_not_tagged_on_carnival():
    assert "cars" not in tag_event("Downtown Carnival", "")
