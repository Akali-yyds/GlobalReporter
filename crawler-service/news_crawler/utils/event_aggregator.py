"""
Event aggregation module.
Groups similar news articles into events.
"""
import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass
class Article:
    """Represents a news article."""
    id: str
    title: str
    summary: str
    content: str
    source_name: str
    publish_time: datetime
    country_tags: List[str] = field(default_factory=list)
    hash: str = ""


@dataclass
class Event:
    """Represents a news event."""
    id: str
    title: str
    summary: str
    main_country: str
    event_level: str
    heat_score: int
    article_count: int
    articles: List[Article] = field(default_factory=list)


class EventAggregator:
    """
    Aggregates similar news articles into events.
    Uses title similarity and time proximity.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn = None
        # Similarity threshold (0-1)
        self.similarity_threshold = 0.6
        # Time window for grouping (hours)
        self.time_window_hours = 24

    @property
    def conn(self):
        """Get database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.database_url)
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def compute_title_hash(self, title: str) -> str:
        """Compute a normalized hash of the title."""
        # Normalize: lowercase, remove special chars, sort words
        normalized = title.lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        words = sorted(normalized.split())
        normalized = ' '.join(words)
        return hashlib.md5(normalized.encode()).hexdigest()

    def compute_similarity(self, title1: str, title2: str) -> float:
        """Compute similarity between two titles."""
        if not title1 or not title2:
            return 0.0

        # Normalize
        t1 = self.compute_title_hash(title1)
        t2 = self.compute_title_hash(title2)

        # If hashes match, it's the same
        if t1 == t2:
            return 1.0

        # Simple word-based Jaccard similarity
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """Extract important keywords from text."""
        if not text:
            return []

        # Simple keyword extraction: most frequent words
        words = re.findall(r'\b[\w]{2,}\b', text.lower())
        
        # Remove stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how',
            '的', '是', '在', '和', '了', '有', '我', '他', '她', '它', '们',
        }

        # Count word frequencies
        word_count = {}
        for word in words:
            if word not in stop_words and len(word) > 1:
                word_count[word] = word_count.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]

    def get_country_from_tags(self, country_tags: List[str]) -> str:
        """Determine main country from tags."""
        if not country_tags:
            return "UNKNOWN"
        
        # Prioritize certain countries
        priority = ['CN', 'US', 'GB', 'RU', 'JP', 'KR', 'DE', 'FR', 'IN', 'AU']
        
        for country in priority:
            if country in country_tags:
                return country
        
        return country_tags[0] if country_tags else "UNKNOWN"

    def find_similar_event(self, article: Article, existing_events: List[Event]) -> Optional[Event]:
        """Find an existing event that matches this article."""
        for event in existing_events:
            # Check title similarity with primary article
            if event.articles:
                primary = event.articles[0]
                similarity = self.compute_similarity(article.title, primary.title)
                
                if similarity >= self.similarity_threshold:
                    # Also check time proximity
                    time_diff = abs((article.publish_time - event.articles[0].publish_time).total_seconds())
                    if time_diff <= self.time_window_hours * 3600:
                        return event
        
        return None

    def calculate_event_heat(self, event: Event) -> int:
        """Calculate heat score for an event."""
        if not event.articles:
            return 0
        
        # Base score from article count
        base_score = len(event.articles) * 100
        
        # Factor in source diversity
        sources = set(a.source_name for a in event.articles)
        diversity_bonus = len(sources) * 50
        
        # Factor in recency
        latest = max(a.publish_time for a in event.articles)
        age_hours = (datetime.now() - latest).total_seconds() / 3600
        recency_factor = max(0, 1 - (age_hours / 48))  # Decay over 48 hours
        
        return int((base_score + diversity_bonus) * recency_factor)

    def aggregate_articles(self, articles: List[Article]) -> List[Event]:
        """Aggregate articles into events."""
        if not articles:
            return []

        events: List[Event] = []

        for article in articles:
            # Try to find existing event
            existing = self.find_similar_event(article, events)
            
            if existing:
                existing.articles.append(article)
                # Update event title if this article has more info
                if len(article.title) > len(existing.title):
                    existing.title = article.title
            else:
                # Create new event
                keywords = self.extract_keywords(article.title + " " + article.summary)
                event = Event(
                    id="",  # Will be set when saving to DB
                    title=article.title,
                    summary=article.summary[:500] if article.summary else "",
                    main_country=self.get_country_from_tags(article.country_tags),
                    event_level="country",  # Default to country level
                    heat_score=article.country_tags.__len__() * 100,  # Placeholder
                    article_count=1,
                    articles=[article]
                )
                events.append(event)

        # Calculate final heat scores
        for event in events:
            event.heat_score = self.calculate_event_heat(event)
            event.article_count = len(event.articles)

        return events

    def save_events(self, events: List[Event]) -> int:
        """Save events and their article mappings to database."""
        saved_count = 0
        
        for event in events:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if event already exists
                title_hash = self.compute_title_hash(event.title)
                cur.execute(
                    "SELECT id FROM news_events WHERE title_hash = %s",
                    (title_hash,)
                )
                existing = cur.fetchone()

                if existing:
                    event.id = existing['id']
                    # Update event
                    cur.execute(
                        """
                        UPDATE news_events 
                        SET heat_score = %s, 
                            article_count = %s,
                            last_seen_at = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (event.heat_score, event.article_count, datetime.now(), datetime.now(), event.id)
                    )
                else:
                    # Insert new event
                    cur.execute(
                        """
                        INSERT INTO news_events 
                        (title, summary, main_country, event_level, heat_score, article_count, 
                         first_seen_at, last_seen_at, title_hash, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            event.title, event.summary, event.main_country, event.event_level,
                            event.heat_score, event.article_count, datetime.now(), datetime.now(),
                            title_hash, datetime.now(), datetime.now()
                        )
                    )
                    event.id = cur.fetchone()['id']
                    saved_count += 1

                # Link articles to event
                for article in event.articles:
                    cur.execute(
                        """
                        INSERT INTO event_articles (event_id, article_id, is_primary, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (event.id, article.id, article == event.articles[0], datetime.now())
                    )

                self.conn.commit()

        return saved_count

    def run_aggregation(self, limit: int = 100) -> Dict:
        """Run the full aggregation process."""
        # Fetch recent articles without events
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM news_articles
                WHERE id NOT IN (
                    SELECT article_id FROM event_articles
                )
                AND crawl_time >= %s
                ORDER BY crawl_time DESC
                LIMIT %s
                """,
                (datetime.now() - timedelta(hours=48), limit)
            )
            rows = cur.fetchall()

        articles = [
            Article(
                id=row['id'],
                title=row['title'],
                summary=row['summary'] or "",
                content=row['content'] or "",
                source_name=row['source_name'],
                publish_time=row['publish_time'],
                country_tags=row['country_tags'] or [],
                hash=row['hash']
            )
            for row in rows
        ]

        # Aggregate
        events = self.aggregate_articles(articles)

        # Save
        saved_count = self.save_events(events)

        return {
            'articles_processed': len(articles),
            'events_created': saved_count,
            'events_updated': len(events) - saved_count,
            'total_events': len(events),
        }


def main():
    import os
    from dotenv import load_dotenv

    load_dotenv()
    database_url = os.getenv('DATABASE_URL', 'postgresql://ainewser:ainewser_pass@localhost:5432/ainewser')

    aggregator = EventAggregator(database_url)
    result = aggregator.run_aggregation()
    
    print(f"Aggregation complete:")
    print(f"  Articles processed: {result['articles_processed']}")
    print(f"  Events created: {result['events_created']}")
    print(f"  Events updated: {result['events_updated']}")

    aggregator.close()


if __name__ == '__main__':
    main()
