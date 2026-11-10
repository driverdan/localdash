"""General text helpers: HTML stripping, sentence truncation, keyword-table matching.

`strip_html` and `truncate_sentences` were ported verbatim from ChattNews.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable, Iterator, Mapping
from html.parser import HTMLParser

_WS_RE = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(text: str) -> str:
    """Return plain text from an HTML fragment.

    Entities are unescaped before parsing, so encoded markup is stripped too.
    """
    if not text:
        return ""
    extractor = _TextExtractor()
    extractor.feed(html.unescape(text))
    return _WS_RE.sub(" ", " ".join(extractor.parts)).strip()


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


def keyword_matches(text: str, table: Mapping[str, Iterable[str]]) -> Iterator[str]:
    """Yield, in table order, each key of ``table`` with a keyword in ``text``.

    A keyword matches when it is a substring of the lower-cased text padded with
    one space on each side, so a padded keyword such as ``" ai "`` also matches
    at the start and end of the text. Keywords are expected in lower case.
    """
    haystack = f" {text.lower()} "
    for key, keywords in table.items():
        if any(kw in haystack for kw in keywords):
            yield key
