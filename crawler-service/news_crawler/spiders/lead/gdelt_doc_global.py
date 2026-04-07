"""
GDELT DOC global lead spider.
"""
from datetime import datetime
from typing import Iterator
from urllib.parse import urlencode

import requests
from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class GDELTDocGlobalSpider(BaseNewsSpider):
    name = "gdelt_doc_global"
    source_name = "GDELT DOC Global"
    source_code = "gdelt_doc_global"
    source_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    country = "UNKNOWN"
    language = "en"
    category = "lead"

    DEFAULT_QUERY = "(earthquake OR flood OR wildfire OR cyclone OR conflict OR missile OR protest OR ai OR cybersecurity OR chip OR satellite OR volcano)"

    def __init__(self, *args, **kwargs):
        self.query = kwargs.pop("query", self.DEFAULT_QUERY)
        self.timespan = kwargs.pop("timespan", "1d")
        self.maxrecords = int(kwargs.pop("maxrecords", 25))
        super().__init__(*args, **kwargs)

    def start_requests(self) -> Iterator[Request]:
        params = {
            "query": self.query,
            "mode": "artlist",
            "maxrecords": max(1, min(50, self.maxrecords)),
            "timespan": self.timespan,
            "format": "json",
        }
        yield Request(
            url=f"{self.source_url}?{urlencode(params)}",
            callback=self.parse_feed,
            dont_filter=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, */*",
            },
        )

    def parse_feed(self, response, **kwargs) -> Iterator[NewsArticle]:
        try:
            payload = response.json()
        except Exception:
            payload = requests.get(response.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).json()

        for idx, article in enumerate(payload.get("articles") or []):
            if idx >= self.max_items:
                break
            title = self.clean_text(article.get("title") or "")
            link = (article.get("url") or "").strip()
            if not title or not link:
                continue
            item = NewsArticle()
            item["title"] = title
            item["summary"] = self.clean_text(
                " | ".join(
                    value for value in [
                        article.get("domain"),
                        article.get("sourcecountry"),
                    ] if value
                )
            )
            item["url"] = link
            item["published_at"] = self._normalize_seen_date(article.get("seendate"))
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["source_class"] = "lead"
            item["source_tier"] = "aggregator"
            item["freshness_sla_hours"] = 48
            item["license_mode"] = "aggregated_public"
            item["source_metadata"] = {
                "role": "global_lead",
                "domain": article.get("domain"),
                "sourcecountry": article.get("sourcecountry"),
                "query": self.query,
            }
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = "en"
            item["country"] = "UNKNOWN"
            item["category"] = self.category
            item["heat_score"] = max(1, 62 - idx)
            item["canonical_url"] = link
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

    @staticmethod
    def _normalize_seen_date(value: str | None) -> str | None:
        raw = str(value or "").strip()
        if len(raw) != 16 or not raw.endswith("Z"):
            return raw or None
        try:
            dt = datetime.strptime(raw, "%Y%m%dT%H%M%SZ")
            return dt.isoformat()
        except ValueError:
            return raw or None
