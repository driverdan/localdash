"""Offline tests for news clustering, text helpers, and the story read model."""

from __future__ import annotations

from app.news.clustering import assign_clusters
from app.news.stories import build_stories
from app.news.textutil import strip_html, title_tokens, truncate_sentences

# Two wordings of one story: 4 shared distinctive tokens (amnicola, warehouse,
# fire, firefighters) but low Jaccard/containment, so only the cross-outlet
# distinctive-token rule can merge them.
TITLE_A = "Amnicola warehouse fire injures two firefighters"
TITLE_B = "Crews respond to warehouse fire on Amnicola after firefighters hurt"


def test_cross_outlet_distinctive_tokens_merge():
    clusters = assign_clusters([(1, 1, TITLE_A), (2, 2, TITLE_B)])
    assert clusters[1] == clusters[2] == 1


def test_same_outlet_distinctive_tokens_do_not_merge():
    # Identical pair, same outlet: the distinctive rule is disabled within one
    # outlet (formulaic series headlines would falsely merge).
    clusters = assign_clusters([(1, 1, TITLE_A), (2, 1, TITLE_B)])
    assert clusters[1] != clusters[2]


def test_same_outlet_high_overlap_still_merges():
    clusters = assign_clusters(
        [
            (1, 1, "City council approves downtown stadium funding plan"),
            (2, 1, "City council approves downtown stadium funding"),
        ]
    )
    assert clusters[1] == clusters[2] == 1


def test_unrelated_titles_stay_separate():
    clusters = assign_clusters(
        [
            (1, 1, TITLE_A),
            (2, 2, "School board debates calendar changes for fall semester"),
        ]
    )
    assert clusters[1] != clusters[2]


def test_transitive_merge_uses_smallest_id():
    # 1 merges with 2 (cross-outlet distinctive), 2 merges with 3 (identical
    # titles) — all three end up in cluster 1.
    clusters = assign_clusters([(1, 1, TITLE_A), (2, 2, TITLE_B), (3, 3, TITLE_B)])
    assert clusters == {1: 1, 2: 1, 3: 1}


def _row(aid, cluster_id, slug, category="news", title=None, summary="", published="", image=None):
    return {
        "id": aid,
        "cluster_id": cluster_id,
        "url": f"https://example.com/{aid}",
        "title": title or f"Article {aid}",
        "summary": summary,
        "category": category,
        "published": published,
        "image_url": image,
        "source_name": slug.title(),
        "source_slug": slug,
    }


def test_build_stories_aggregates_cluster():
    rows = [  # sorted by published ASC, as the query guarantees
        _row(
            1,
            1,
            "alpha",
            "news",
            title="First report",
            summary="Short.",
            published="2026-07-10T10:00:00+00:00",
        ),
        _row(
            2,
            1,
            "beta",
            "politics",
            summary="A much longer summary with detail.",
            published="2026-07-10T11:00:00+00:00",
        ),
        _row(3, 1, "alpha", "politics", published="2026-07-10T12:00:00+00:00"),
    ]
    (story,) = build_stories(rows)
    assert story["title"] == "First report"  # earliest member
    assert story["summary"] == "A much longer summary with detail."  # wordiest
    assert story["category"] == "politics"  # 2:1 majority
    assert story["article_count"] == 3
    assert story["source_count"] == 2  # one link per outlet
    assert [s["slug"] for s in story["sources"]] == ["alpha", "beta"]
    assert story["first_published"] == "2026-07-10T10:00:00+00:00"
    assert story["latest_published"] == "2026-07-10T12:00:00+00:00"


def test_build_stories_borrows_earliest_member_image():
    # Earliest member has no image; a later one does — the story borrows it.
    rows = [
        _row(1, 1, "alpha", published="2026-07-10T10:00:00+00:00", image=None),
        _row(
            2,
            1,
            "beta",
            published="2026-07-10T11:00:00+00:00",
            image="https://example.com/first.jpg",
        ),
        _row(
            3,
            1,
            "gamma",
            published="2026-07-10T12:00:00+00:00",
            image="https://example.com/second.jpg",
        ),
    ]
    (story,) = build_stories(rows)
    assert story["image_url"] == "https://example.com/first.jpg"  # earliest with an image


def test_build_stories_no_member_image_is_none():
    rows = [
        _row(1, 1, "alpha", published="2026-07-10T10:00:00+00:00"),
        _row(2, 1, "beta", published="2026-07-10T11:00:00+00:00"),
    ]
    (story,) = build_stories(rows)
    assert story["image_url"] is None


def test_build_stories_specific_beats_news_on_tie():
    rows = [
        _row(1, 1, "alpha", "news", published="2026-07-10T10:00:00+00:00"),
        _row(2, 1, "beta", "sports", published="2026-07-10T11:00:00+00:00"),
    ]
    (story,) = build_stories(rows)
    assert story["category"] == "sports"


def test_build_stories_sorted_by_latest_activity():
    rows = [
        _row(1, 1, "alpha", published="2026-07-10T10:00:00+00:00"),
        _row(2, 2, "beta", published="2026-07-10T11:00:00+00:00"),
    ]
    stories = build_stories(rows)
    assert [s["id"] for s in stories] == [2, 1]


def test_truncate_sentences_cuts_at_boundary():
    text = ("A sentence that is fairly long and descriptive. " * 12).strip()
    out = truncate_sentences(text, 400)
    assert len(out) <= 400
    assert out.endswith(".")


def test_strip_html_and_tokens():
    assert strip_html("<p>Fire on <b>Main St</b> &amp; 3rd</p>") == "Fire on Main St & 3rd"
    toks = title_tokens("The fire on Amnicola Highway was contained")
    assert "amnicola" in toks and "highway" in toks
    assert "the" not in toks and "was" not in toks  # stopwords/short words dropped
