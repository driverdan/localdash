"""Headline tokenization for story clustering.

Ported verbatim from ChattNews. The general HTML-stripping and truncation
helpers live in app/text.py.
"""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an and are as at be but by for from has have in into is it its of on
    or over says say said than that the their this to under up was were will
    with after before during new more amid""".split()
)

_WORD_RE = re.compile(r"[a-z0-9']+")


def title_tokens(title: str) -> frozenset:
    """Clustering tokens: lowercase words over 2 chars minus stopwords, plus numbers.

    Numbers of any length are kept ("27", "41", "23"): a highway number, a score
    or a district number is often the most event-specific part of a headline.
    """
    words = _WORD_RE.findall(title.lower())
    return frozenset(w for w in words if (w.isdigit() or len(w) > 2) and w not in STOPWORDS)
