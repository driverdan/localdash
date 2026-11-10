"""Tests for the shared text helpers in app/text.py."""

from __future__ import annotations

from app.text import keyword_matches

TABLE = {
    "music": ["concert", "jazz"],
    "food": ["brunch", "jazz brunch"],
    "tech": [" ai ", "coding"],
}


def test_yields_every_match_in_table_order():
    text = "Sunday jazz brunch and a coding club"
    assert list(keyword_matches(text, TABLE)) == ["music", "food", "tech"]
    # classify takes the first element.
    assert next(keyword_matches(text, TABLE)) == "music"


def test_order_follows_the_table_not_the_text():
    assert list(keyword_matches("coding then brunch then concert", TABLE)) == [
        "music",
        "food",
        "tech",
    ]


def test_padded_keyword_matches_at_the_edges_of_the_text():
    assert list(keyword_matches("AI meetup", TABLE)) == ["tech"]
    assert list(keyword_matches("Meetup about AI", TABLE)) == ["tech"]
    assert list(keyword_matches("AI", TABLE)) == ["tech"]


def test_padded_keyword_does_not_match_inside_a_word():
    assert list(keyword_matches("Fair trail day", TABLE)) == []


def test_matching_is_case_insensitive():
    assert list(keyword_matches("CONCERT Tonight", TABLE)) == ["music"]


def test_empty_text_yields_nothing():
    assert list(keyword_matches("", TABLE)) == []
