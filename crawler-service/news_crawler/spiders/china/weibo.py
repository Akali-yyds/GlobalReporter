"""
Weibo (微博) Spider.
Crawls Weibo hot search topics.
"""
import json
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)


class WeiboSpider(BaseNewsSpider):
    """
    Spider for Weibo hot search topics.
    URL: https://s.weibo.com/top/summary
    """
    
    name = "weibo"
    source_name = "微博热搜"
    source_code = "weibo"
    source_url = "https://weibo.com"
    country = "CN"
    language = "zh"
    category = "social"
    
    # Weibo API
    API_URL = "https://weibo.com/ajax/side/hotSearch"
    
    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "COOKIES_ENABLED": True,
        "DOWNLOAD_DELAY": 1,
    }
    
    def start_requests(self) -> Iterator[Request]:
        """Generate initial requests for Weibo hot search."""
        yield Request(
            url=self.API_URL,
            callback=self.parse_api,
            method="GET",
            dont_filter=True,
            headers={
                "Referer": "https://weibo.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        )
    
    def parse_api(self, response, **kwargs) -> Iterator[NewsArticle]:
        """Parse Weibo's API response."""
        try:
            data = json.loads(response.text)
            items = data.get("data", {}).get("realtime", [])
            
            for idx, item_data in enumerate(items):
                if idx >= self.max_items:
                    break
                
                news_item = NewsArticle()
                
                news_item["title"] = item_data.get("word") or item_data.get("note")
                news_item["summary"] = item_data.get("raw_hot") or item_data.get("note")
                news_item["url"] = f"https://s.weibo.com/weibo?q={item_data.get('word', '')}"
                news_item["source_name"] = self.source_name
                news_item["source_code"] = self.source_code
                news_item["source_url"] = self.source_url
                news_item["crawled_at"] = datetime.now().isoformat()
                news_item["language"] = self.language
                news_item["country"] = self.country
                news_item["category"] = self.category
                news_item["heat_score"] = item_data.get("hot_score") or item_data.get("num")
                news_item["hash"] = self.compute_hash(
                    news_item["title"],
                    self.source_code
                )
                
                self.crawled_items.append(news_item)
                yield news_item
                
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse Weibo API response: {e}")
            yield from self.parse_fallback(response)
    
    def parse_fallback(self, response) -> Iterator[NewsArticle]:
        """Fallback parser for HTML page."""
        logger.info("Using fallback parser for Weibo")
        
        items = response.css("tr.hot-item, div.hot-item")
        
        for idx, item in enumerate(items):
            if idx >= self.max_items:
                break
            
            title = item.css("a::text, td.td-02 a::text").get()
            url = item.css("a::attr(href)").get()
            
            news_item = NewsArticle()
            news_item["title"] = self.clean_text(title)
            news_item["url"] = self.extract_article_url(url, self.source_url)
            news_item["source_name"] = self.source_name
            news_item["source_code"] = self.source_code
            news_item["source_url"] = self.source_url
            news_item["crawled_at"] = datetime.now().isoformat()
            news_item["language"] = self.language
            news_item["country"] = self.country
            news_item["hash"] = self.compute_hash(news_item["title"], self.source_code)
            
            self.crawled_items.append(news_item)
            yield news_item
