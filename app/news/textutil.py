"""HTML stripping, title normalization, and summary truncation helpers.

Ported verbatim from ChattNews.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

STOPWORDS = frozenset(
    """a an and are as at be but by for from has have in into is it its of on
    or over says say said than that the their this to under up was were will
    with after before during new more amid""".split()
)

_WORD_RE = re.compile(r"[a-z0-9']+")
_WS_RE = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def strip_html(text: str) -> str:
    """Return plain text from an HTML fragment."""
    if not text:
        return ""
    extractor = _TextExtractor()
    extractor.feed(html.unescape(text))
    return _WS_RE.sub(" ", " ".join(extractor.parts)).strip()


def title_tokens(title: str) -> frozenset:
    words = _WORD_RE.findall(title.lower())
    return frozenset(w for w in words if len(w) > 2 and w not in STOPWORDS)


def truncate_sentences(text: str, max_chars: int = 400) -> str:
    """Cut text at a sentence boundary near max_chars."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in (". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[: idx + 1]
    idx = cut.rfind(" ")
    return (cut[:idx] if idx > 0 else cut).rstrip(",;:") + "…"
