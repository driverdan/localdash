"""Topic tagging via keyword matching against the event title and description."""
from __future__ import annotations

# Topic -> keywords. Matching is case-insensitive substring matching.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "music": ["concert", "music", "band", "live music", "dj", "jazz", "symphony", "acoustic"],
    "food": ["food", "dinner", "brunch", "tasting", "beer", "brewery", "wine", "culinary"],
    "arts": ["art", "gallery", "exhibit", "theatre", "theater", "museum", "dance", "film"],
    "outdoors": ["hike", "trail", "river", "kayak", "outdoor", "park", "climb", "garden"],
    "family": ["family", "kids", "children", "story time", "storytime", "all ages"],
    "sports": ["game", "run", "race", "marathon", "lookouts", "soccer", "basketball", "cycling"],
    "tech": ["tech", "startup", "coding", "developer", "hackathon", " ai ", "data", "software"],
    "community": ["market", "fair", "fundraiser", "volunteer", "meetup", "networking", "charity"],
    "education": ["class", "workshop", "lecture", "seminar", "course", "talk", "learn"],
    "nightlife": ["bar", "club", "nightlife", "party", "trivia", "happy hour"],
}


def tag_text(text: str) -> set[str]:
    """Return the set of topics whose keywords appear in ``text``."""
    haystack = f" {text.lower()} "
    return {topic for topic, kws in TOPIC_KEYWORDS.items() if any(kw in haystack for kw in kws)}


def tag_event(title: str, description: str = "") -> set[str]:
    """Derive topic tags from an event's title and description."""
    return tag_text(f"{title} {description}")
