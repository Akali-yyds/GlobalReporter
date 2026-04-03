"""
AP News Spider — uses AP News RSS feed.
Covers top US and international news.
"""
import logging
import re
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)

START_URLS = [
    "https://apnews.com/hub/ap-top-news",
    "https://apnews.com/world-news",
]


class APNewsSpider(BaseNewsSpider):

    name = "ap"
    source_name = "AP News"
    source_code = "ap"
    source_url = "https://apnews.com"
    country = "US"
    language = "en"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1.5,
    }

    def start_requests(self) -> Iterator[Request]:
        for url in START_URLS:
            yield Request(
                url=url,
                callback=self.parse,
                dont_filter=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )

    def parse(self, response, **kwargs) -> Iterator[NewsArticle]:
        count = 0
        seen: set[str] = set()

        for link_sel in response.css("a[href]"):
            if count >= self.max_items:
                break

            raw_href = (link_sel.attrib.get("href") or "").strip()
            title = self.clean_text(link_sel.xpath("normalize-space(string())").get())
            if not raw_href or not title or len(title) < 16:
                continue

            url = response.urljoin(raw_href)
            if not self._is_story_url(url) or url in seen:
                continue

            seen.add(url)
            count += 1

            item = NewsArticle()
            item["title"] = title
            item["summary"] = None
            item["url"] = url
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["published_at"] = None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, url)
            self.crawled_items.append(item)
            yield item

        if count == 0:
            logger.warning("AP: no story links found on %s", response.url)

    @staticmethod
    def _is_story_url(url: str) -> bool:
        if not url.startswith("https://apnews.com/"):
            return False
        if re.search(r"/(hub|video|author|podcasts?|newsletter|newsletters|liveblog)/", url):
            return False
        return "/article/" in url or "/live/" in url
