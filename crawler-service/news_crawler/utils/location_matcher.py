#!/usr/bin/env python3
"""
LocationMatcher: annotate normalized geo entities with matched_text and source_text_position
by scanning title/summary/content with simple heuristics.

Priority of positions: title > summary > content
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class LocationMatcher:
    def __init__(self) -> None:
        pass

    def annotate_matches(
        self,
        *,
        title: str,
        summary: Optional[str],
        content: Optional[str],
        entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not entities:
            return []
        title = (title or "").strip()
        summary = (summary or "").strip()
        content = (content or "").strip()

        for ent in entities:
            if ent.get("matched_text") and ent.get("source_text_position"):
                continue
            candidates = self._name_candidates(ent)
            found = self._find_in_text(title, candidates)
            if found:
                ent["matched_text"], ent["source_text_position"] = found[0], "title"
                ent["relevance_score"] = self._score(ent)
                continue
            found = self._find_in_text(summary, candidates)
            if found:
                ent["matched_text"], ent["source_text_position"] = found[0], "summary"
                ent["relevance_score"] = self._score(ent)
                continue
            found = self._find_in_text(content, candidates)
            if found:
                ent["matched_text"], ent["source_text_position"] = found[0], "content"
                ent["relevance_score"] = self._score(ent)
                continue
            # even if not matched, compute a baseline relevance from type/confidence
            ent.setdefault("relevance_score", self._score(ent))
        return entities

    @staticmethod
    def _name_candidates(ent: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        for key in ("matched_text", "name", "admin1_name", "city_name", "country_name"):
            v = (ent.get(key) or "").strip()
            if v and v not in out:
                out.append(v)
        return out

    @staticmethod
    def _find_in_text(text: str, names: List[str]) -> Optional[Tuple[str, Tuple[int, int]]]:
        if not text:
            return None
        for n in names:
            if not n:
                continue
            # direct substring match first
            idx = text.find(n)
            if idx >= 0:
                return (text[idx: idx + len(n)], (idx, idx + len(n)))
            # case-insensitive for ASCII names
            if n.isascii():
                rx = re.compile(r"\b" + re.escape(n) + r"\b", re.IGNORECASE)
                m = rx.search(text)
                if m:
                    return (m.group(0), (m.start(), m.end()))
        return None

    @staticmethod
    def _score(ent: Dict[str, Any]) -> float:
        pos = (ent.get("source_text_position") or "").lower()
        pos_weight = {"title": 1.0, "summary": 0.8, "content": 0.6}.get(pos, 0.5)
        typ = (ent.get("type") or "").lower()
        type_weight = {"admin1": 1.0, "city": 0.9, "country": 0.85}.get(typ, 0.8)
        conf = float(ent.get("confidence") or 1.0)
        # simple weighted score in [0,1]
        score = 0.6 * pos_weight + 0.3 * type_weight + 0.1 * max(0.0, min(conf, 1.0))
        return round(max(0.0, min(score, 1.0)), 2)
