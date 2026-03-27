"""
Tests for crawler utilities.
"""
import pytest
from datetime import datetime

from news_crawler.utils.text_cleaner import TextCleaner
from news_crawler.utils.geo_extractor import GeoExtractor
from news_crawler.utils.dedup import Deduplicator
from news_crawler.utils.normalizer import DataNormalizer


class TestTextCleaner:
    """Tests for TextCleaner."""

    def test_clean_html(self):
        """Test HTML tag removal."""
        html = "<p>Hello <b>World</b></p>"
        result = TextCleaner.clean_html(html)
        assert result == "Hello World"

    def test_clean_html_complex(self):
        """Test complex HTML cleaning."""
        html = """
        <div class="test">
            <script>alert('xss')</script>
            <p>Content here</p>
        </div>
        """
        result = TextCleaner.clean_html(html)
        assert "script" not in result
        assert "Content here" in result

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        text = "Hello    World\n\nTest"
        result = TextCleaner.normalize_whitespace(text)
        assert result == "Hello World Test"

    def test_remove_urls(self):
        """Test URL removal."""
        text = "Check https://example.com for more info"
        result = TextCleaner.remove_urls(text)
        assert "https://example.com" not in result

    def test_truncate(self):
        """Test text truncation."""
        text = "This is a very long text that should be truncated"
        result = TextCleaner.truncate(text, 20)
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    def test_clean_batch(self):
        """Test batch cleaning."""
        texts = ["<p>Text 1</p>", "<b>Text 2</b>", None]
        results = TextCleaner.clean_batch(texts)
        assert results == ["Text 1", "Text 2", ""]


class TestGeoExtractor:
    """Tests for GeoExtractor."""

    def test_extract_china(self):
        """Test China extraction."""
        text = "China announced new policy"
        results = GeoExtractor.extract_countries(text)
        assert len(results) >= 1
        assert any(r.geo_key == "CN" for r in results)

    def test_extract_usa(self):
        """Test USA extraction."""
        text = "United States presidential election"
        results = GeoExtractor.extract_countries(text)
        assert any(r.geo_key == "US" for r in results)

    def test_extract_mixed(self):
        """Test multiple country extraction."""
        text = "China and Japan meet with USA to discuss trade"
        results = GeoExtractor.extract_countries(text)
        geo_keys = [r.geo_key for r in results]
        assert "CN" in geo_keys
        assert "JP" in geo_keys
        assert "US" in geo_keys

    def test_get_primary_country(self):
        """Test primary country extraction."""
        text = "China announces new policy"
        primary = GeoExtractor.get_primary_country(text)
        assert primary == "CN"

    def test_chinese_text(self):
        """Test Chinese country names."""
        text = "中国宣布新政策"
        results = GeoExtractor.extract_countries(text)
        assert any(r.geo_key == "CN" for r in results)

    def test_no_country(self):
        """Test text without country mention."""
        text = "General news without specific location"
        results = GeoExtractor.extract_countries(text)
        assert len(results) == 0

    def test_extract_cities(self):
        """Test city extraction."""
        text = "Meeting in Beijing"
        results = GeoExtractor.extract_cities(text)
        assert any("beijing" in r.name.lower() for r in results)


class TestDeduplicator:
    """Tests for Deduplicator."""

    def test_exact_duplicate(self):
        """Test exact duplicate detection."""
        dedup = Deduplicator()
        
        item1 = {"title": "Test News", "source_code": "sina", "article_url": "http://example.com/1"}
        item2 = {"title": "Test News", "source_code": "sina", "article_url": "http://example.com/1"}
        
        result1 = dedup.check_exact(item1)
        assert not result1.is_duplicate
        
        result2 = dedup.check_exact(item2)
        assert result2.is_duplicate

    def test_different_articles(self):
        """Test different articles are not duplicates."""
        dedup = Deduplicator()
        
        item1 = {"title": "News about China", "source_code": "sina"}
        item2 = {"title": "News about USA", "source_code": "sina"}
        
        result1 = dedup.check_exact(item1)
        result2 = dedup.check_exact(item2)
        
        assert not result1.is_duplicate
        assert not result2.is_duplicate

    def test_similarity_check(self):
        """Test title similarity checking."""
        dedup = Deduplicator()
        
        similarity = dedup.check_similar(
            "China announces new economic policy",
            "China announces new economic policy today"
        )
        assert similarity > 0.8

    def test_low_similarity(self):
        """Test low similarity detection."""
        dedup = Deduplicator()
        
        similarity = dedup.check_similar(
            "China economic news",
            "USA sports results"
        )
        assert similarity < 0.3

    def test_batch_deduplicate(self):
        """Test batch deduplication using Deduplicator class."""
        dedup = Deduplicator()
        items = [
            {"title": "News 1", "source_code": "sina", "article_url": "http://example.com/1"},
            {"title": "News 2", "source_code": "sina", "article_url": "http://example.com/2"},
            {"title": "News 1", "source_code": "sina", "article_url": "http://example.com/1"},  # Duplicate
            {"title": "News 3", "source_code": "tencent", "article_url": "http://example.com/3"},
        ]

        unique = []
        for item in items:
            result = dedup.check_exact(item)
            if not result.is_duplicate:
                unique.append(item)

        assert len(unique) == 3


class TestDataNormalizer:
    """Tests for DataNormalizer."""

    def test_normalize_source_name(self):
        """Test source name normalization."""
        assert DataNormalizer.normalize_source_name("新浪网") == "新浪新闻"
        assert DataNormalizer.normalize_source_name("腾讯网") == "腾讯新闻"
        assert DataNormalizer.normalize_source_name("新浪") == "新浪新闻"

    def test_normalize_country_code(self):
        """Test country code normalization."""
        assert DataNormalizer.normalize_country_code("CN") == "CN"
        assert DataNormalizer.normalize_country_code("cn") == "CN"
        assert DataNormalizer.normalize_country_code("USA") == "US"
        assert DataNormalizer.normalize_country_code("INVALID") is None

    def test_normalize_heat_score(self):
        """Test heat score normalization."""
        assert DataNormalizer.normalize_heat_score(100) == 100
        assert DataNormalizer.normalize_heat_score(85.5) == 85
        assert DataNormalizer.normalize_heat_score("1000") == 1000
        assert DataNormalizer.normalize_heat_score(None) == 0

    def test_normalize_tags(self):
        """Test tag normalization."""
        assert DataNormalizer.normalize_tags("tag1,tag2,tag3") == ["tag1", "tag2", "tag3"]
        assert DataNormalizer.normalize_tags(["tag1", "tag2"]) == ["tag1", "tag2"]
        assert DataNormalizer.normalize_tags(None) == []

    def test_clean_title(self):
        """Test title cleaning."""
        assert DataNormalizer.clean_title("News Title - 新浪") == "News Title"
        assert DataNormalizer.clean_title("Title _ BBC") == "Title"
