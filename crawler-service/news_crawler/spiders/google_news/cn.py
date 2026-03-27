"""
Google News Spider (Chinese) — uses Google News RSS for Chinese-language world news.
Covers Chinese sources reporting international news.
"""
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)

# Google News Chinese RSS endpoints
RSS_URLS = [
    # Chinese: world news
    "https://news.google.com/rss/search?q=国际新闻&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    # Chinese: Asia news
    "https://news.google.com/rss/search?q=亚洲新闻&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    # Chinese: Europe news
    "https://news.google.com/rss/search?q=欧洲新闻&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    # Chinese: US news
    "https://news.google.com/rss/search?q=美国新闻&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    # Chinese: Middle East
    "https://news.google.com/rss/search?q=中东局势&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
]


class GoogleNewsCNSpider(BaseNewsSpider):

    name = "google_news_cn"
    source_name = "谷歌新闻"
    source_code = "google_news_cn"
    source_url = "https://news.google.com"
    country = "CN"
    language = "zh"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1,
    }

    def start_requests(self) -> Iterator[Request]:
        for url in RSS_URLS:
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
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        items = response.xpath("//item")
        if not items:
            items = response.xpath("//entry")

        if not items:
            logger.warning(
                "GoogleNewsCN: no items from %s. Status=%s body[:300]=%s",
                response.url,
                response.status,
                response.text[:300],
            )
            return

        seen: set[str] = set()

        for it in items:
            if len(self.crawled_items) >= self.max_items:
                break

            title = (it.xpath("string(title)").get() or "").strip()
            link = (
                it.xpath("link/text()").get() or
                it.xpath("link").get() or
                it.xpath("@href").get() or
                it.xpath("guid/text()").get() or
                ""
            ).strip()
            if not title or not link:
                continue

            real_url = link
            if "/articles/" in link:
                idx = link.find("/articles/")
                raw = link[idx:]
                parts = raw.split("?")
                real_url = parts[0].replace("/articles/", "https://")
                if len(parts) > 1:
                    real_url += "?" + parts[1]

            if real_url in seen:
                continue
            seen.add(real_url)

            desc = (it.xpath("string(description)").get() or "").strip()
            pub = (it.xpath("pubDate/text()").get() or "").strip()
            source = (it.xpath("source/text()").get() or "").strip()

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(desc)
            item["url"] = real_url
            item["source_name"] = source or self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["published_at"] = pub or None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, real_url)
            self.crawled_items.append(item)
            yield item
