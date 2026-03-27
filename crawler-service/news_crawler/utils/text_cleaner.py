"""
Text cleaning utilities for news content.
"""
import re
from typing import Optional, List
from html import unescape


class TextCleaner:
    """
    Utility class for cleaning and normalizing text content.
    """
    
    # HTML tag pattern
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    
    # Extra whitespace pattern
    WHITESPACE_PATTERN = re.compile(r'\s+')
    
    # URL pattern
    URL_PATTERN = re.compile(r'https?://\S+')
    
    # Email pattern
    EMAIL_PATTERN = re.compile(r'\S+@\S+\.\S+')
    
    @classmethod
    def clean_html(cls, text: Optional[str]) -> Optional[str]:
        """
        Remove all HTML tags from text.
        """
        if not text:
            return None
        
        # Unescape HTML entities
        text = unescape(text)
        
        # Remove HTML tags
        text = cls.HTML_TAG_PATTERN.sub(' ', text)
        
        # Remove extra whitespace
        text = cls.normalize_whitespace(text)
        
        return text.strip() or None
    
    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        """
        Normalize whitespace in text.
        """
        if not text:
            return ""
        
        return cls.WHITESPACE_PATTERN.sub(' ', text).strip()
    
    @classmethod
    def remove_urls(cls, text: str) -> str:
        """
        Remove URLs from text.
        """
        if not text:
            return ""
        
        return cls.URL_PATTERN.sub('', text)
    
    @classmethod
    def remove_emails(cls, text: str) -> str:
        """
        Remove email addresses from text.
        """
        if not text:
            return ""
        
        return cls.EMAIL_PATTERN.sub('', text)
    
    @classmethod
    def truncate(cls, text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to maximum length.
        """
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)].rstrip() + suffix
    
    @classmethod
    def clean_title(cls, title: Optional[str]) -> Optional[str]:
        """
        Clean news title.
        Removes special characters and normalizes format.
        """
        if not title:
            return None
        
        # Remove HTML
        title = cls.clean_html(title)
        
        # Remove extra whitespace
        title = cls.normalize_whitespace(title)
        
        # Remove common title suffixes
        title = re.sub(r'[-_—|]\s*(新浪|腾讯|网易|搜狐|微博)$', '', title)
        
        return title.strip() or None
    
    @classmethod
    def extract_summary(cls, content: str, max_length: int = 200) -> str:
        """
        Extract summary from full content.
        Takes first paragraph or truncates.
        """
        if not content:
            return ""
        
        # Clean HTML
        content = cls.clean_html(content)
        
        # Split into paragraphs
        paragraphs = content.split('\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if not paragraphs:
            return ""
        
        # Try to get first meaningful paragraph
        for para in paragraphs:
            if len(para) > 50:  # Skip very short paragraphs
                return cls.truncate(para, max_length)
        
        # Fallback to first paragraph
        return cls.truncate(paragraphs[0], max_length)
    
    @classmethod
    def clean_batch(cls, texts: List[str]) -> List[str]:
        """
        Clean a batch of texts.
        """
        return [cls.clean_html(t) or "" for t in texts]
