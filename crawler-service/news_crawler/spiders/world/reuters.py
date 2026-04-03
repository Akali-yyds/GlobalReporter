"""
Reuters (路透社) Spider — RSS-first with HTML fallback.
"""
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)


class ReutersSpider(BaseNewsSpider):

    name = "reuters"
    source_name = "Reuters"
    source_code = "reuters"
    source_name = "NPR"
    source_code = "npr"
    source_url = "https://www.npr.org"
    country = "US"
    language = "en"
    category = "news"

    # RSS feeds (primary) — RSSHub mirrors and direct
    RSS_URLS = [
        "https://www.npr.org/rss/rss.php?id=1001",
    ]

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self) -> Iterator[Request]:
        for url in self.RSS_URLS:
            yield Request(
                url=url,
                callback=self.parse_rss,
                dont_filter=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        items = response.xpath("//item")
        if not items:
            logger.warning(
                "NPR replacement feed returned no items: %s status=%s",
                response.url,
                response.status,
            )
            return
        for it in items:
            if len(self.crawled_items) >= self.max_items:
                break
            title = (it.xpath("string(title)").get() or "").strip()
            link = (
                it.xpath("link/text()").get()
                or it.xpath("guid/text()").get()
                or ""
            ).strip()
            if not title or not link:
                continue
            desc = (it.xpath("string(description)").get() or "").strip()
            pub = (it.xpath("pubDate/text()").get() or "").strip()
            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(desc)
            item["url"] = link
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["published_at"] = pub or None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

    def parse(self, response, **kwargs) -> Iterator[NewsArticle]:
        count = 0

        # Primary selector: article links in the main news stream
        # Reuters wraps headlines in <a data-id="..." href="...">
        # and also uses standard <article> with <h3><a href="..."> headline
        links = response.css(
            'article[data-component="article-card"] a[href*="/world/"]::attr(href)'
        ).getall()

        if not links:
            # Fallback: any link that looks like a Reuters article
            links = response.css(
                'h3 a[href*="reuters.com"]::attr(href)'
            ).getall()

        if not links:
            links = response.css(
                'a[href*="/world/"], a[href*="/middle-east/"], a[href*="/europe/"]'
            ).xpath("@href").getall()

        seen: set[str] = set()

        for raw_url in links:
            if count >= self.max_items:
                break
            url = raw_url.strip()
            if not url or url in seen:
                continue
            if not url.startswith("http"):
                url = "https://www.reuters.com" + url
            seen.add(url)
            count += 1

            item = NewsArticle()
            item["title"] = None  # filled from the list page if available
            item["url"] = url
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["hash"] = self.compute_hash(url, self.source_code)
            self.crawled_items.append(item)
            yield item

        if count == 0:
            logger.warning(
                "Reuters: no article links found on %s. Body snippet: %s",
                response.url,
                response.text[:600],
            )
