"""
BBC News Spider.
Crawls BBC RSS (reliable XML; CSS selectors often fail on namespaced RSS).
"""
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)


class BBCSpider(BaseNewsSpider):
    """
    Spider for BBC News via RSS.
    URL: https://www.bbc.com/news/rss.xml
    """

    name = "bbc"
    source_name = "BBC News"
    source_code = "bbc"
    source_url = "https://www.bbc.com/news"
    country = "GB"
    language = "en"
    category = "news"

    API_URL = "https://www.bbc.com/news/rss.xml"

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            url=self.API_URL,
            callback=self.parse_rss,
            dont_filter=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        """Parse RSS: use XPath — CSS 'item' fails on XML with default namespaces."""
        items = response.xpath("//item")
        logger.info("BBC RSS: matched %d <item> nodes", len(items))

        if not items:
            logger.warning("BBC RSS: no items via XPath, trying //channel/item")
            items = response.xpath("//channel/item")

        for idx, it in enumerate(items):
            if idx >= self.max_items:
                break

            title = (it.xpath("string(title)").get() or "").strip()
            link = (it.xpath("link/text()").get() or "").strip()
            if not link:
                link = (it.xpath("guid/text()").get() or "").strip()
            description = (it.xpath("string(description)").get() or "").strip()
            pub_date = (it.xpath("pubDate/text()").get() or "").strip()

            if not title or not link:
                continue

            news_item = NewsArticle()
            news_item["title"] = self.clean_text(title)
            news_item["summary"] = self.clean_text(description)
            news_item["url"] = link
            news_item["published_at"] = pub_date or None
            news_item["source_name"] = self.source_name
            news_item["source_code"] = self.source_code
            news_item["source_url"] = self.source_url
            news_item["crawled_at"] = datetime.now().isoformat()
            news_item["language"] = self.language
            news_item["country"] = self.country
            news_item["category"] = self.category
            news_item["heat_score"] = max(1, 50 - idx)
            news_item["hash"] = self.compute_hash(title, self.source_code, link)

            self.crawled_items.append(news_item)
            yield news_item

        if not self.crawled_items:
            logger.warning("BBC RSS yielded zero items; body snippet: %s", response.text[:400])
