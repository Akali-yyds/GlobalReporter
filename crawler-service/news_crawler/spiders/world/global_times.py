"""
Global Times spider using feed-first inputs.

The legacy official RSS endpoint often surfaces older archive content at the top,
so default rollout uses a fresher Google News site-search RSS feed. The original
Global Times feed is kept as PoC only for manual checks.
"""
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider
from news_crawler.utils.feed_control import build_feed_request_meta, record_feed_fetch

logger = logging.getLogger(__name__)

FEED_CONFIGS = [
    {
        "url": (
            "https://news.google.com/rss/search?"
            "q=site:globaltimes.cn+when:1d&hl=en-US&gl=US&ceid=US:en"
        ),
        "name": "global_times_google_news_latest",
        "code": "global_times_google_news_latest",
        "priority": 1,
        "freshness_sla_hours": 24,
        "license_mode": "aggregated_public",
    },
    {
        "url": "https://www.globaltimes.cn/rss/outbrain.xml",
        "name": "global_times_legacy_official_rss",
        "code": "global_times_legacy_official_rss",
        "priority": 20,
        "freshness_sla_hours": 24,
        "rollout_state": "poc",
        "license_mode": "publisher_public",
        "notes": "Legacy feed is frequently stale; kept as PoC only.",
    },
]


class GlobalTimesSpider(BaseNewsSpider):
    name = "global_times"
    source_name = "Global Times"
    source_code = "global_times"
    source_url = "https://www.globaltimes.cn"
    country = "CN"
    language = "en"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1.5,
    }

    def start_requests(self) -> Iterator[Request]:
        self._seen_urls: set[str] = set()
        for feed in self.get_controlled_feeds(FEED_CONFIGS):
            yield Request(
                url=feed["url"],
                callback=self.parse_rss,
                errback=self.handle_feed_error,
                dont_filter=True,
                meta=build_feed_request_meta(feed),
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
        feed = self.get_response_feed(response, FEED_CONFIGS)
        record_feed_fetch(
            self,
            feed_code=feed["code"],
            feed_name=feed["name"],
            feed_url=response.url,
            http_status=response.status,
            success=bool(items),
            error=None if items else "No RSS items found",
        )
        if not items:
            logger.warning(
                "Global Times: no items from %s. Status=%s body[:300]=%s",
                response.url,
                response.status,
                response.text[:300],
            )
            return

        feed_name = response.meta.get("feed_name") or feed["name"]
        feed_priority = int(response.meta.get("feed_priority") or feed["priority"])
        feed_sla = int(response.meta.get("feed_freshness_sla_hours") or feed["freshness_sla_hours"])
        feed_rollout_state = response.meta.get("feed_rollout_state") or feed["rollout_state"]
        feed_profile_id = response.meta.get("feed_profile_id") or feed.get("id")

        for it in items:
            if len(self.crawled_items) >= self.max_items:
                break

            title = self._clean_title((it.xpath("string(title)").get() or "").strip())
            link = (
                it.xpath("link/text()").get()
                or it.xpath("link").get()
                or it.xpath("guid/text()").get()
                or ""
            ).strip()
            if not title or not link or link in self._seen_urls:
                continue

            self._seen_urls.add(link)
            desc = (it.xpath("string(description)").get() or "").strip()
            pub = (it.xpath("pubDate/text()").get() or "").strip()
            cat = (it.xpath("category/text()").get() or "").strip()

            item = NewsArticle()
            item["title"] = title
            item["summary"] = self.clean_text(desc)
            item["url"] = link
            item["canonical_url"] = link
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["source_class"] = "news"
            item["source_tier"] = "authoritative"
            item["source_tier_level"] = 2
            item["freshness_sla_hours"] = feed_sla
            item["license_mode"] = feed.get("license_mode") or "publisher_public"
            item["published_at"] = pub or None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.clean_text(cat) or self.category
            item["source_metadata"] = {
                "fetch_via": "google_news_rss_fallback" if "google.com" in response.url else "official_rss",
                "publisher_domain": "globaltimes.cn",
                "publisher_name": "Global Times",
                "feed_url": response.url,
                "feed_code": feed["code"],
                "feed_name": feed_name,
                "feed_priority": feed_priority,
                "feed_profile_id": feed_profile_id,
                "feed_rollout_state": feed_rollout_state,
            }
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

    @staticmethod
    def _clean_title(value: str) -> str:
        value = value.strip()
        if value.endswith(" - Global Times"):
            value = value[:-15]
        return value.strip()
