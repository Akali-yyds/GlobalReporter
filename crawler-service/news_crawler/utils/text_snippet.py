"""Extract short text snippets from HTML or plain article bodies."""
from __future__ import annotations

import re
from typing import Optional


def first_paragraph(text: Optional[str], max_chars: int = 600) -> str:
    """
    First paragraph / lede: strip tags, then first sentence or first block.
    Used with title for lightweight geo extraction without full article fetch.
    """
    if not text:
        return ""
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    for sep in ("。", "！", "？", ". ", "! ", "? ", "\n"):
        if sep in t:
            chunk = t.split(sep)[0].strip()
            if len(chunk) > 15:
                return chunk[:max_chars]
    return t[:max_chars]
