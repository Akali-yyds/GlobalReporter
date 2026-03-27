"""
Zhihu (知乎) Spider.
Crawls Zhihu hot topics.
"""
import json
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)


class ZhihuSpider(BaseNewsSpider):
    """
    Spider for Zhihu hot topics.
    URL: https://www.zhihu.com/hot
    """
    
    name = "zhihu"
    source_name = "知乎热榜"
    source_code = "zhihu"
    source_url = "https://www.zhihu.com"
    country = "CN"
    language = "zh"
    category = "q&A"
    
    # Zhihu API
    API_URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
    
    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "COOKIES_ENABLED": True,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    def start_requests(self) -> Iterator[Request]:
        """Generate initial requests for Zhihu hot news."""
        yield Request(
            url=self.API_URL,
            callback=self.parse_api,
            method="GET",
            dont_filter=True,
            headers={
                "Referer": "https://www.zhihu.com/",
                "User-Agent": self.custom_settings["USER_AGENT"],
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
    
    def parse_api(self, response, **kwargs) -> Iterator[NewsArticle]:
        """Parse Zhihu's API response."""
        try:
            data = json.loads(response.text)
            items = data.get("data", [])
            
            for idx, item_data in enumerate(items):
                if idx >= self.max_items:
                    break
                
                news_item = NewsArticle()
                
                # Extract target data (question info)
                target = item_data.get("target", {})
                question = target.get("question", {})
                
                news_item["title"] = question.get("title") or target.get("title")
                news_item["summary"] = target.get("excerpt") or question.get("excerpt")
                news_item["url"] = f"https://www.zhihu.com/question/{question.get('id')}"
                news_item["source_name"] = self.source_name
                news_item["source_code"] = self.source_code
                news_item["source_url"] = self.source_url
                news_item["published_at"] = item_data.get("created_at")
                news_item["crawled_at"] = datetime.now().isoformat()
                news_item["language"] = self.language
                news_item["country"] = self.country
                news_item["category"] = self.category
                news_item["heat_score"] = item_data.get("follower_count") or item_data.get("hot_score")
                news_item["hash"] = self.compute_hash(
                    news_item["title"],
                    self.source_code
                )
                
                self.crawled_items.append(news_item)
                yield news_item
                
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse Zhihu API response: {e}")
            yield from self.parse_fallback(response)
    
    def parse_fallback(self, response) -> Iterator[NewsArticle]:
        """Fallback parser for HTML page."""
        logger.info("Using fallback parser for Zhihu")
        
        items = response.css("div.HotItem")
        
        for idx, item in enumerate(items):
            if idx >= self.max_items:
                break
            
            title = item.css("h2.HotItem-title::text").get()
            url = item.css("a.HotItem-title::attr(href)").get()
            excerpt = item.css("p.HotItem-excerpt::text").get()
            
            news_item = NewsArticle()
            news_item["title"] = self.clean_text(title)
            news_item["summary"] = self.clean_text(excerpt)
            news_item["url"] = url
            news_item["source_name"] = self.source_name
            news_item["source_code"] = self.source_code
            news_item["source_url"] = self.source_url
            news_item["crawled_at"] = datetime.now().isoformat()
            news_item["language"] = self.language
            news_item["country"] = self.country
            news_item["hash"] = self.compute_hash(news_item["title"], self.source_code)
            
            self.crawled_items.append(news_item)
            yield news_item
