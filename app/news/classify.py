"""Per-article content categorization for news.

An article's category is derived from the article itself, not inherited wholesale
from the feed (outlet section) it arrived in. Resolution is a three-tier rule,
first match wins, and always yields one of registry.CATEGORIES:

  1. a mapped feed ``<category>`` tag (the WordPress outlets emit per-item
     tags; only a curated, high-confidence subset maps into our vocabulary —
     everything else is ignored, and a source registered with
     ``use_feed_tags: False`` skips this tier entirely because its tags are
     boilerplate — the fetcher passes it an empty tag list);
  2. a keyword match on the title + summary (topic->keywords, modeled on the
     sibling events classifier, app/events/tagging.py);
  3. the feed's registered section category, as the last-resort fallback so an
     article is never left uncategorized (this is the pre-change behavior).

Both maps are defined here in code — the source of truth, mirroring registry.py.
"""

from __future__ import annotations

# Feed <category> tag (lowercased) -> normalized category. Kept deliberately
# small and high-confidence: the WordPress feeds mix real topics with geography
# ("Marion County"), editorial flags ("Featured", "Top Stories"), campaign names
# ("Golden Apple Award"), and free-text one-offs. Only unambiguous topical tags
# belong here; unmapped tags fall through to keyword matching. "Commentary" is
# the high-value one — opinion is a format, not a topic, so keywords miss it.
TAG_CATEGORY_MAP: dict[str, str] = {
    "commentary": "opinion",
    "opinion": "opinion",
    "editorial": "opinion",
    "local news": "news",
    "news": "news",
    "top stories": "news",
    "local": "news",
    "sports": "sports",
    "business": "business",
    "politics": "politics",
}

# Normalized category -> keywords (case-insensitive substring match against the
# title + summary). "news" is intentionally absent: it is the generic fallback,
# not a keyword-matched topic. Categories are tried in this order; first hit
# wins, so more distinctive topics precede the broad "life" bucket.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "sports": [
        "football",
        "basketball",
        "baseball",
        "soccer",
        "hockey",
        "golf",
        "lookouts",
        "mocs",
        "vols",
        "titans",
        "braves",
        "playoff",
        "touchdown",
        "quarterback",
        "tournament",
        "championship",
        "season opener",
        "nfl",
        "nba",
        "mlb",
        "athlete",
        "athletic",
        "scoreless",
        "halftime",
    ],
    "politics": [
        "election",
        "campaign trail",
        "election campaign",
        "ballot",
        "city council",
        "county commission",
        "commissioner",
        "mayor",
        "governor",
        "senate",
        "congress",
        "legislature",
        "legislation",
        "republican",
        "democrat",
        "primary election",
        "candidate",
        "polling place",
    ],
    "business": [
        "business",
        "economy",
        "jobs report",
        "unemployment",
        "startup",
        "revenue",
        "earnings",
        "investment",
        "layoff",
        "hiring",
        "retail",
        "manufacturing",
        "headquarters",
        "development project",
        "small business",
        "chamber of commerce",
    ],
    "opinion": [
        "op-ed",
        "editorial",
        "commentary",
        "guest column",
        "our view",
        "viewpoint",
        "letter to the editor",
    ],
    "life": [
        "festival",
        "concert",
        "live music",
        "restaurant",
        "recipe",
        "gallery",
        "exhibit",
        "theatre",
        "theater",
        "museum",
        "wedding",
        "movie",
        "film",
        "novelist",
        "book signing",
        "garden",
        "fashion",
        "entertainment",
        "nightlife",
        "celebration",
    ],
}


def classify(
    title: str,
    summary: str,
    feed_tags: list[str],
    feed_category: str,
) -> str:
    """Resolve one normalized category for an article (see module docstring)."""
    # Tier 1: a mapped feed <category> tag. A specific category wins over a
    # generic 'news' tag on the same item (e.g. "Commentary" beats "Top
    # Stories"), so 'news' is only used if no specific tag mapped.
    news_tag_seen = False
    for tag in feed_tags:
        mapped = TAG_CATEGORY_MAP.get(tag.strip().lower())
        if mapped == "news":
            news_tag_seen = True
        elif mapped:
            return mapped
    if news_tag_seen:
        return "news"

    # Tier 2: keyword match on title + summary.
    haystack = f" {title} {summary} ".lower()
    for category, keywords in TOPIC_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return category

    # Tier 3: the feed's registered section category.
    return feed_category
