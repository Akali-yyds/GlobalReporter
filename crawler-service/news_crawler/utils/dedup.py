"""
Deduplication utilities for news articles.
"""
import hashlib
import difflib
from typing import List, Optional, Set
from dataclasses import dataclass


@dataclass
class DedupResult:
    """Result of deduplication check."""
    is_duplicate: bool
    original_id: Optional[str] = None
    similarity: float = 0.0


class Deduplicator:
    """
    Deduplicates news articles based on content similarity.
    """
    
    # Similarity threshold for considering articles as duplicates
    DEFAULT_THRESHOLD = 0.85
    
    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._hash_set: Set[str] = set()
        self._title_set: Set[str] = set()
    
    def compute_hash(self, title: str, source: str, url: str = "") -> str:
        """
        Compute a hash for deduplication.
        Uses title + source + URL for uniqueness.
        """
        content = f"{title.lower().strip()}|{source.lower().strip()}|{url.lower().strip()}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def check_exact(self, news_item: dict) -> DedupResult:
        """
        Check for exact duplicate using hash.
        """
        if not news_item.get("title"):
            return DedupResult(is_duplicate=False)
        
        hash_value = self.compute_hash(
            news_item["title"],
            news_item.get("source_code", ""),
            news_item.get("article_url", "")
        )
        
        if hash_value in self._hash_set:
            return DedupResult(is_duplicate=True, similarity=1.0)
        
        # Add to set
        self._hash_set.add(hash_value)
        return DedupResult(is_duplicate=False)
    
    def check_similar(
        self,
        title1: str,
        title2: str,
        use_sequence_matcher: bool = True
    ) -> float:
        """
        Check similarity between two titles.
        Returns a float between 0 and 1.
        """
        if not title1 or not title2:
            return 0.0
        
        # Normalize
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()
        
        if t1 == t2:
            return 1.0
        
        if use_sequence_matcher:
            # Use SequenceMatcher for better fuzzy matching
            return difflib.SequenceMatcher(None, t1, t2).ratio()
        
        # Simple word-based similarity
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def is_duplicate_by_similarity(
        self,
        new_title: str,
        existing_titles: List[str]
    ) -> Optional[tuple]:
        """
        Check if new title is similar to any existing title.
        Returns (index, similarity) if duplicate, None otherwise.
        """
        for i, existing in enumerate(existing_titles):
            similarity = self.check_similar(new_title, existing)
            if similarity >= self.threshold:
                return (i, similarity)
        
        return None
    
    def add_title(self, title: str) -> None:
        """Add a title to the deduplication set."""
        if title:
            self._title_set.add(title.lower().strip())
    
    def clear(self) -> None:
        """Clear all stored data."""
        self._hash_set.clear()
        self._title_set.clear()
    
    def get_stats(self) -> dict:
        """Get deduplication statistics."""
        return {
            "total_hashes": len(self._hash_set),
            "total_titles": len(self._title_set),
        }


def batch_deduplicate(news_items: List[dict]) -> List[dict]:
    """
    Deduplicate a batch of news items.
    Returns list of unique items.
    """
    if not news_items:
        return []
    
    deduplicator = Deduplicator()
    unique_items = []
    
    for item in news_items:
        result = deduplicator.check_exact(item)
        
        if not result.is_duplicate:
            # Also check title similarity
            duplicate = deduplicator.is_duplicate_by_similarity(
                item.get("title", ""),
                [i.get("title", "") for i in unique_items]
            )
            
            if duplicate is None:
                unique_items.append(item)
                deduplicator.add_title(item.get("title", ""))
    
    return unique_items
