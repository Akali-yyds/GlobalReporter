"""
Google Blog official RSS spider.
"""
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class GoogleBlogSpider(BaseNewsSpider):
    name = "google_blog"
    source_name = "Google Blog"
    source_code = "google_blog"
    source_url = "https://blog.google/"
    country = "US"
    language = "en"
    category = "technology"

    RSS_URL = "https://blog.google/rss/"

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            url=self.RSS_URL,
            callback=self.parse_rss,
            dont_filter=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        for it in response.xpath("//item"):
            if len(self.crawled_items) >= self.max_items:
                break
            title = (it.xpath("string(title)").get() or "").strip()
            link = (it.xpath("link/text()").get() or it.xpath("guid/text()").get() or "").strip()
            if not title or not link:
                continue
            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text((it.xpath("string(description)").get() or "").strip())
            item["url"] = link
            item["published_at"] = (it.xpath("pubDate/text()").get() or "").strip() or None
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(1, 72 - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
