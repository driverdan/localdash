"""Unit tests for the Diff result object."""
from __future__ import annotations

from app.schemas import Diff


def test_empty_diff_is_empty():
    assert Diff(source_key="hc911").is_empty


def test_diff_with_new_is_not_empty():
    d = Diff(source_key="hc911", new=[{"type": "Feature"}])
    assert not d.is_empty


def test_diff_with_closed_is_not_empty():
    assert not Diff(source_key="hc911", closed=[1]).is_empty


def test_to_message_shape():
    d = Diff(source_key="hc911", new=[{"a": 1}], updated=[{"b": 2}], closed=[9])
    msg = d.to_message()
    assert msg == {
        "type": "diff",
        "source": "hc911",
        "new": [{"a": 1}],
        "updated": [{"b": 2}],
        "closed": [9],
    }
