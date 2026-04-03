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
    source_name = "People.cn"
    source_code = "peoplecn"
    source_url = "http://www.people.com.cn"
    country = "CN"
    language = "zh"
    category = "news"
    START_URLS = [
        "http://world.people.com.cn/",
    ]
    
    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "COOKIES_ENABLED": False,
    }
    
    def start_requests(self) -> Iterator[Request]:
        for url in self.START_URLS:
            yield Request(
                url=url,
                callback=self.parse_html,
                dont_filter=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )

    def parse_html(self, response, **kwargs) -> Iterator[NewsArticle]:
        count_before = len(self.crawled_items)
        seen_local: set[str] = set()

        for link_sel in response.css("a[href]"):
            if len(self.crawled_items) >= self.max_items:
                break

            raw_href = (link_sel.attrib.get("href") or "").strip()
            title = self.clean_text(link_sel.xpath("normalize-space(string())").get())
            if not raw_href or not title or len(title) < 8:
                continue

            url = response.urljoin(raw_href)
            if "/n1/20" not in url or ".html" not in url:
                continue
            if url in seen_local:
                continue

            seen_local.add(url)

            news_item = NewsArticle()
            news_item["title"] = title
            news_item["summary"] = None
            news_item["url"] = url
            news_item["source_name"] = self.source_name
            news_item["source_code"] = self.source_code
            news_item["source_url"] = self.source_url
            news_item["published_at"] = None
            news_item["crawled_at"] = datetime.now().isoformat()
            news_item["language"] = self.language
            news_item["country"] = self.country
            news_item["category"] = self.category
            news_item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            news_item["hash"] = self.compute_hash(title, self.source_code, url)

            self.crawled_items.append(news_item)
            yield news_item

        if len(self.crawled_items) == count_before:
            logger.warning(
                "People.cn replacement page returned no items: %s status=%s",
                response.url,
                response.status,
            )
