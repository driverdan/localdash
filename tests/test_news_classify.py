"""Offline tests for per-article content categorization (no network, no DB)."""

from __future__ import annotations

from app.news.classify import classify


def test_feed_tag_maps_to_opinion():
    # A News Chronicle "Commentary" tag wins ahead of keywords and feed section:
    # opinion is a format keywords cannot reliably detect.
    assert classify("A headline", "", ["Top Stories", "Commentary"], "news") == "opinion"


def test_keyword_match_when_no_mapped_tag():
    # No mappable tag -> keyword classification on title + summary.
    assert classify("Lookouts win season opener", "", [], "news") == "sports"


def test_unmapped_tags_and_no_keyword_fall_back_to_feed_category():
    # Only unmappable tags (geography, editorial flag) and no topic keyword:
    # keep the feed's registered category.
    assert (
        classify("A quiet afternoon downtown", "", ["Marion County", "Featured"], "life") == "life"
    )


def test_single_feed_outlet_is_categorized_individually():
    # The Pulse ships a single "life" feed; a business story must not collapse
    # into life just because of its feed section.
    assert classify("Downtown startup posts record revenue", "", [], "life") == "business"


def test_summary_contributes_to_the_match():
    # The title alone is generic; the summary carries the sports signal.
    assert (
        classify("Weekend roundup", "The Mocs clinched the championship.", [], "news") == "sports"
    )


def test_tag_exempt_source_flag_is_read_from_the_registry():
    from app.news.registry import uses_feed_tags

    # The library's News/Featured tags are boilerplate on every post; sources
    # without the key (and unknown slugs) keep the default tag behavior.
    assert uses_feed_tags("chattlibrary") is False
    assert uses_feed_tags("wtvc") is False
    assert uses_feed_tags("wdef") is True
    assert uses_feed_tags("no-such-source") is True


def test_wtvc_registers_a_single_local_rss_feed():
    from app.news.registry import SOURCES, FeedSpec, feed_kind

    # Sinclair tags every item "article", so WTVC is tag-exempt and its one
    # local feed falls back to "news" after keyword classification.
    wtvc = next(s for s in SOURCES if s.slug == "wtvc")
    assert wtvc.feeds == (FeedSpec(category="news", url="https://newschannel9.com/news/local.rss"),)
    assert feed_kind("https://newschannel9.com/news/local.rss") == "rss"


def test_suppressed_tags_let_the_feed_registration_categorize():
    # What the fetcher does for a use_feed_tags=False source — the same
    # library announcement flips from tag-driven "news" to the "life"
    # registration once its boilerplate tags are withheld.
    title = "Chattanooga Public Library Hosts Summer Reading Finale"
    assert classify(title, "", ["News", "Featured"], "life") == "news"
    assert classify(title, "", [], "life") == "life"


def test_registry_slugs_and_urls_are_unique_and_categories_known():
    from app.news.registry import CATEGORIES, SOURCES

    slugs = [outlet.slug for outlet in SOURCES]
    assert len(slugs) == len(set(slugs))
    feeds = [feed for outlet in SOURCES for feed in outlet.feeds]
    urls = [feed.url for feed in feeds]
    assert len(urls) == len(set(urls))
    assert {feed.category for feed in feeds} <= set(CATEGORIES)
    assert {feed.kind for feed in feeds} <= {"rss", "html"}
