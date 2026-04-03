"""Build geo-focused scan text from article fields."""
from __future__ import annotations

import re
from typing import Optional

from news_crawler.utils.text_snippet import first_paragraph


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?\.])\s+")
_LOCATION_CONTEXT_RE = re.compile(
    r"\b(in|at|from|near|across|throughout|outside|around|into|toward|inside)\b",
    re.IGNORECASE,
)
_DATELINE_RE = re.compile(
    r"^(?:[A-Z][A-Z .'\-]{2,}|[\u4e00-\u9fff]{2,20})(?:,\s*(?:[A-Z][A-Za-z .'\-]{2,}|[\u4e00-\u9fff]{2,20})){0,2}\s*[-—]"
)


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_geo_search_text(
    title: Optional[str],
    summary: Optional[str],
    content: Optional[str],
    *,
    max_chars: int = 2800,
    max_sentences: int = 8,
) -> str:
    """
    Build a geo-focused scan text.

    This keeps the lede plus a few location-rich body sentences so city/admin1
    mentions that appear after the first sentence still have a chance to be
    normalized.
    """
    title_text = _clean_text(title)
    summary_text = _clean_text(summary)
    content_text = _clean_text(content)

    parts: list[str] = []
    seen: set[str] = set()

    def add_part(value: str, *, limit: int | None = None) -> None:
        text = (value or "").strip()
        if not text:
            return
        if limit is not None:
            text = text[:limit].strip()
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        parts.append(text)

    add_part(title_text, limit=300)
    add_part(first_paragraph(summary_text), limit=400)
    add_part(first_paragraph(content_text), limit=500)

    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(content_text[:4500]) if s.strip()]
    ranked: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences):
        if len(sentence) < 20:
            continue
        score = 0.0
        if idx < 2:
            score += 2.2
        elif idx < 5:
            score += 1.0
        if _DATELINE_RE.search(sentence):
            score += 2.0
        if _LOCATION_CONTEXT_RE.search(sentence) or re.search(r"[在于从赴至位于省州市县郡区]", sentence):
            score += 1.1
        if len(re.findall(r"\b[A-Z][a-z]+(?:[\-'][A-Z][a-z]+)*\b", sentence)) >= 2:
            score += 0.7
        if re.search(r"[\u4e00-\u9fff]{2,}", sentence):
            score += 0.5
        ranked.append((score, idx, sentence))

    for _, _, sentence in sorted(ranked, key=lambda item: (-item[0], item[1]))[:max_sentences]:
        add_part(sentence, limit=420)

    return " ".join(parts).strip()[:max_chars]
