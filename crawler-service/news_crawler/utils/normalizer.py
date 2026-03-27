"""
Data normalization utilities.
"""
import re
from datetime import datetime
from typing import Optional, Dict, Any
from dateutil import parser as date_parser


class DataNormalizer:
    """
    Normalizes and standardizes news data.
    """
    
    # Standard country codes
    COUNTRY_CODES = {
        "CN", "TW", "HK", "MO",  # China region
        "US", "CA", "MX",  # North America
        "GB", "FR", "DE", "IT", "ES", "RU", "UA", "PL",  # Europe
        "JP", "KR", "IN", "AU",  # Asia Pacific
        "BR", "AR", "CL",  # South America
        "ZA", "EG", "NG",  # Africa
        "IL", "IR", "SA", "AE",  # Middle East
    }
    
    # Source name normalization map
    SOURCE_NORMALIZE = {
        "新浪新闻": "新浪新闻",
        "新浪网": "新浪新闻",
        "新浪": "新浪新闻",
        "腾讯新闻": "腾讯新闻",
        "腾讯网": "腾讯新闻",
        "腾讯": "腾讯新闻",
        "网易新闻": "网易新闻",
        "网易": "网易新闻",
        "搜狐新闻": "搜狐新闻",
        "搜狐": "搜狐新闻",
        "微博热搜": "微博热搜",
        "知乎热榜": "知乎热榜",
        "BBC": "BBC News",
        "bbc": "BBC News",
        "CNN": "CNN",
        "cnn": "CNN",
        "Reuters": "Reuters",
        "reuters": "Reuters",
    }
    
    @classmethod
    def normalize_source_name(cls, name: str) -> str:
        """Normalize source name to standard format."""
        if not name:
            return "Unknown"
        
        return cls.SOURCE_NORMALIZE.get(name, name)
    
    @classmethod
    def normalize_country_code(cls, code: str) -> Optional[str]:
        """Normalize country code to ISO format."""
        if not code:
            return None
        
        code = code.upper().strip()
        
        # Handle common variations (check mappings first)
        mappings = {
            "PRC": "CN",
            "MAINLAND": "CN",
            "UK": "GB",
            "AMERICA": "US",
            "USA": "US",
        }
        
        # Apply mapping if exists
        if code in mappings:
            return mappings[code]
        
        # Return code only if it's a valid country code
        return code if code in cls.COUNTRY_CODES else None
    
    @classmethod
    def normalize_datetime(cls, dt_str: str) -> Optional[datetime]:
        """
        Parse and normalize datetime string.
        Returns datetime object or None if parsing fails.
        """
        if not dt_str:
            return None
        
        try:
            # Try parsing with dateutil (handles many formats)
            return date_parser.parse(dt_str)
        except (ValueError, TypeError):
            pass
        
        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(dt_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    @classmethod
    def normalize_url(cls, url: str, base_url: str = "") -> str:
        """Normalize URL, handling relative URLs."""
        if not url:
            return ""
        
        url = url.strip()
        
        # Handle relative URLs
        if url.startswith("//"):
            return "https:" + url
        
        if url.startswith("/"):
            if base_url:
                from urllib.parse import urljoin
                return urljoin(base_url, url)
            return ""
        
        # Validate URL
        if not re.match(r'^https?://', url):
            return ""
        
        # Remove fragments
        if "#" in url:
            url = url.split("#")[0]
        
        return url
    
    @classmethod
    def normalize_heat_score(cls, score: Any) -> int:
        """
        Normalize heat/popularity score to integer.
        """
        if score is None:
            return 0
        
        if isinstance(score, int):
            return max(0, score)
        
        if isinstance(score, float):
            return max(0, int(score))
        
        if isinstance(score, str):
            # Extract number from string
            match = re.search(r'\d+', score)
            if match:
                return max(0, int(match.group()))
        
        return 0
    
    @classmethod
    def normalize_tags(cls, tags: Any) -> list:
        """
        Normalize tags to a list of strings.
        """
        if not tags:
            return []
        
        if isinstance(tags, str):
            # Split by comma
            return [t.strip() for t in tags.split(",") if t.strip()]
        
        if isinstance(tags, (list, tuple)):
            return [str(t).strip() for t in tags if t]
        
        return []
    
    @classmethod
    def normalize_content(cls, content: str) -> str:
        """
        Normalize article content.
        Removes excessive whitespace and special characters.
        """
        if not content:
            return ""
        
        # Remove excessive newlines
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Remove excessive spaces
        content = re.sub(r' {2,}', ' ', content)
        
        # Remove leading/trailing whitespace per line
        lines = [line.strip() for line in content.split('\n')]
        content = '\n'.join(lines)
        
        return content.strip()
    
    @classmethod
    def extract_content_hash(cls, title: str, content: str = "") -> str:
        """
        Extract a hash from title and content for deduplication.
        """
        import hashlib
        
        text = f"{title}|{content[:500]}"  # Use first 500 chars of content
        return hashlib.sha256(text.encode()).hexdigest()
    
    @classmethod
    def normalize_news_item(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize an entire news item.
        """
        normalized = item.copy()
        
        # Normalize fields
        normalized["source_name"] = cls.normalize_source_name(
            item.get("source_name", "")
        )
        normalized["title"] = cls.clean_title(item.get("title", ""))
        normalized["summary"] = cls.clean_text(item.get("summary", ""))
        
        # Normalize URLs
        normalized["article_url"] = cls.normalize_url(
            item.get("article_url", ""),
            item.get("source_url", "")
        )
        
        # Normalize datetime
        if item.get("publish_time"):
            normalized["publish_time"] = cls.normalize_datetime(
                item.get("publish_time")
            )
        
        # Normalize numeric fields
        normalized["heat_score"] = cls.normalize_heat_score(item.get("heat_score"))
        
        # Normalize tags
        normalized["tags"] = cls.normalize_tags(item.get("tags", []))
        
        # Add normalized timestamp
        normalized["crawl_time"] = datetime.now()
        
        return normalized
    
    @classmethod
    def clean_title(cls, title: str) -> str:
        """Clean news title."""
        if not title:
            return ""
        
        title = title.strip()
        
        # Remove common suffixes
        suffixes = [
            r'[-_—|]\s*(新浪|腾讯|网易|搜狐|微博|知乎|BBC|CNN|Reuters)$',
            r'[-_—|]\s*\d+$',  # Remove trailing numbers
        ]
        
        for suffix in suffixes:
            title = re.sub(suffix, '', title)
        
        return title.strip()
    
    @classmethod
    def clean_text(cls, text: str) -> str:
        """Clean generic text."""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
