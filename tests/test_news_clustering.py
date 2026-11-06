"""Offline tests for news clustering, text helpers, and the story read model."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

from app.news.clustering import ClusterArticle, assign_clusters
from app.news.stories import build_stories
from app.news.textutil import strip_html, title_tokens, truncate_sentences

FIXTURE = Path(__file__).parent / "fixtures" / "news_clustering.json"

# Regression gates for the labeled fixture (design D6). The tuned thresholds reach
# precision 0.897 / recall 0.476; the ported algorithm scored 0.142 / 0.852.
MIN_PRECISION = 0.85
MIN_RECALL = 0.45

T0 = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)

# Token weights come from document frequency, so the unit tests weight against a
# small background of everyday local headlines. Without it, every token shared by
# a two-article test would look common and carry no weight.
BACKGROUND = [
    "Man arrested after police chase in East Ridge",
    "Man charged with theft at Hamilton County store",
    "Woman in critical condition after crash on I-24",
    "Police investigate shooting in East Chattanooga",
    "Two hurt in crash on Highway 153",
    "Man killed in motorcycle crash Friday night",
    "Chattanooga police seek suspect in robbery",
    "Hamilton County Schools announces new calendar",
    "Crash closes lanes on I-75 near Ooltewah",
    "Man shot Friday night is in critical condition",
    "County Commission approves budget amendment",
    "Police: Woman hit by vehicle on Brainerd Road",
    "Fire crews respond to house fire in Hixson",
    "Chattanooga City Council votes on zoning change",
    "Man dies after shooting on Main Street",
    "Driver killed in crash on Highway 58",
    "Police make arrest in Friday night shooting",
    "Woman charged after crash injures child",
    "Hamilton County deputies investigate theft",
    "Red Bank police respond to crash",
]


def _art(aid, source, hours, title, summary=""):
    return ClusterArticle(aid, source, T0 + timedelta(hours=hours), title, summary)


def _cluster(*articles):
    corpus = [(t, "") for t in BACKGROUND] + [(a.title, a.summary) for a in articles]
    return assign_clusters(articles, corpus)


def _pairs(mapping):
    """Unordered pairs of article ids that share a cluster/story label."""
    groups = {}
    for aid, label in mapping.items():
        groups.setdefault(label, []).append(aid)
    return {frozenset(p) for g in groups.values() for p in combinations(sorted(g), 2)}


def pairwise_precision_recall(predicted, gold):
    """Score {article_id: cluster_id} against {article_id: gold story label}."""
    pred_pairs, gold_pairs = _pairs(predicted), _pairs(gold)
    hits = len(pred_pairs & gold_pairs)
    precision = hits / len(pred_pairs) if pred_pairs else 1.0
    recall = hits / len(gold_pairs) if gold_pairs else 1.0
    return precision, recall


def _load_fixture():
    rows = json.loads(FIXTURE.read_text())["articles"]
    source_ids = {slug: i for i, slug in enumerate(sorted({r["source"] for r in rows}))}
    articles = [
        ClusterArticle(
            r["id"],
            source_ids[r["source"]],
            datetime.fromisoformat(r["published"].replace("Z", "+00:00")),
            r["title"],
            r["summary"],
        )
        for r in rows
    ]
    return articles, {r["id"]: r["story"] for r in rows}


def test_same_story_from_two_outlets_clusters():
    clusters = _cluster(
        _art(1, 1, 0, "46-year-old killed in wrong-way crash on Highway 27"),
        _art(2, 2, 3, "Person Killed In Wrong-Way Crash On Highway 27"),
    )
    assert clusters[1] == clusters[2] == 1


def test_formulaic_same_outlet_headlines_stay_separate():
    # Near-identical template; the district numbers disagree (the year is ignored).
    clusters = _cluster(
        _art(1, 1, 0, "DECISION 2026: Tennessee State House Dist. 23"),
        _art(2, 1, 0.1, "DECISION 2026: Tennessee State House Dist. 24"),
    )
    assert clusters[1] != clusters[2]


def test_shared_generic_words_do_not_merge_different_events():
    clusters = _cluster(
        _art(
            1,
            1,
            0,
            "Man in critical condition following officer-involved shooting at Chickamauga Dam",
        ),
        _art(
            2,
            2,
            2,
            "Man, 42, Hit While Crossing Lee Highway On Friday Night Is In Critical Condition",
        ),
    )
    assert clusters[1] != clusters[2]


# Two different water main breaks. Feed summaries run a few hundred characters,
# enough that the shared title doesn't dominate the title+summary overlap.
WATER_A = (
    "Crews spent the morning repairing a ruptured pipe that flooded storefronts and closed "
    "Broad Street between Fourth and Sixth. Business owners along the block said water reached "
    "their doorsteps before the city shut off the line, and the repair is expected to keep the "
    "road closed through the evening commute."
)
WATER_B = (
    "A neighborhood near Missionary Ridge lost service overnight while utility crews replaced "
    "an aging valve on a residential cul-de-sac. Residents were asked to boil tap water until "
    "testing confirms it is safe, and bottled water is being handed out at the community "
    "center on Shallowford Road."
)


def test_weak_link_does_not_chain_two_stories():
    # Story A has three members. Article 4 (story B) and article 5 match only
    # member 1 of A by title: the summary veto separates them from 2 and 3.
    # One match out of three is not a majority, so neither joins A, and 5 joins B.
    title = "Water main break floods downtown street"
    clusters = _cluster(
        _art(1, 1, 0, title),  # no summary, so no summary veto against anyone
        _art(2, 2, 1, title, WATER_A),
        _art(3, 3, 2, title, WATER_A),
        _art(4, 4, 3, title, WATER_B),
        _art(5, 5, 4, title, WATER_B),
    )
    assert clusters[1] == clusters[2] == clusters[3] == 1
    assert clusters[4] == clusters[5] == 4


def test_follow_up_after_story_window_starts_new_story():
    original = _art(1, 1, 0, "Man hit by vehicle on Lee Hwy in critical condition")
    follow_up_title = "Man Hit by Vehicle on Lee Hwy Dies from Injuries"
    # Inside the window the two reports match ...
    assert len(set(_cluster(original, _art(2, 2, 20, follow_up_title)).values())) == 1
    # ... but 40h after the story's first article the follow-up is a new story.
    clusters = _cluster(original, _art(2, 2, 40, follow_up_title))
    assert clusters[1] != clusters[2]


def test_window_is_anchored_to_story_start_not_newest_member():
    # Each report is 20h after the previous one, so each is inside 36h of its
    # predecessor, but the third is 40h after the story began.
    title = "Missing hiker found on Signal Mountain trail"
    clusters = _cluster(_art(1, 1, 0, title), _art(2, 2, 20, title), _art(3, 3, 40, title))
    assert clusters[1] == clusters[2]
    assert clusters[3] != clusters[1]


def test_recurring_same_title_column_stays_separate():
    clusters = _cluster(
        _art(1, 1, 0, "Latest Hamilton County Arrest Report"),
        _art(2, 1, 24, "Latest Hamilton County Arrest Report"),
        # The outlet sometimes pluralizes the column's title.
        _art(3, 1, 48, "Latest Hamilton County Arrest Reports"),
    )
    assert len({clusters[1], clusters[2], clusters[3]}) == 3


def test_same_outlet_duplicate_merges():
    clusters = _cluster(
        _art(1, 1, 0, "Missing hiker found on Signal Mountain trail"),
        _art(2, 1, 2, "Missing hiker found safe on Signal Mountain trail"),
    )
    assert clusters[1] == clusters[2] == 1


def test_summary_veto_separates_similar_titles():
    title = "Water main break floods downtown street"
    with_summaries = _cluster(_art(1, 1, 0, title, WATER_A), _art(2, 2, 1, title, WATER_B))
    assert with_summaries[1] != with_summaries[2]
    # Same titles with only one summary: the veto needs both, so they merge.
    one_summary = _cluster(_art(1, 1, 0, title, WATER_A), _art(2, 2, 1, title))
    assert one_summary[1] == one_summary[2]


def test_fixture_cluster_ids_are_smallest_member_ids():
    articles, _ = _load_fixture()
    clusters = assign_clusters(articles)
    members = {}
    for aid, cid in clusters.items():
        members.setdefault(cid, []).append(aid)
    assert all(cid == min(ids) for cid, ids in members.items())


def test_clustering_is_deterministic():
    articles, _ = _load_fixture()
    expected = assign_clusters(articles)
    shuffled = articles[:]
    random.Random(7).shuffle(shuffled)
    assert assign_clusters(shuffled) == expected


def test_fixture_precision_and_recall():
    articles, gold = _load_fixture()
    precision, recall = pairwise_precision_recall(assign_clusters(articles), gold)
    assert precision >= MIN_PRECISION, f"precision {precision:.3f} < {MIN_PRECISION}"
    assert recall >= MIN_RECALL, f"recall {recall:.3f} < {MIN_RECALL}"


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
    # Numbers of any length are kept: a highway or district number pins the event.
    assert {"27", "highway"} <= title_tokens("Wreck on Highway 27")
    assert "1" in title_tokens("1 dead in crash")
