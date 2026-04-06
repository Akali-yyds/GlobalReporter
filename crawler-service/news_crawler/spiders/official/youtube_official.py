"""
Official YouTube channel RSS spider.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator
import xml.etree.ElementTree as ET

import requests
from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class YouTubeOfficialSpider(BaseNewsSpider):
    name = "youtube_official"
    source_name = "YouTube Official Channels"
    source_code = "youtube_official"
    source_url = "https://www.youtube.com/"
    country = "US"
    language = "en"
    category = "technology"

    FEEDS = (
        {
            "channel_name": "Google Developers Official",
            "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw",
            "channel_url": "https://www.youtube.com/@GoogleDevelopers",
        },
        {
            "channel_name": "NVIDIA Official",
            "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCHuiy8bXnmK5nisYHUd1J5g",
            "channel_url": "https://www.youtube.com/@NVIDIA",
        },
        {
            "channel_name": "OpenAI Official",
            "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCXZCJLdBC09xxGZ6gcdrc6A",
            "channel_url": "https://www.youtube.com/@OpenAI",
        },
        {
            "channel_name": "GitHub Official",
            "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC7c3Kb6jYCRj4JOHHZTxKsQ",
            "channel_url": "https://www.youtube.com/@GitHub",
        },
    )
    _POSITIVE_HINTS = (
        "ai",
        "gemma",
        "agent",
        "developer",
        "copilot",
        "open source",
        "maintainer",
        "security",
        "release",
        "launch",
        "update",
        "model",
        "gpu",
        "inference",
        "robotics",
        "cloud",
        "android",
        "coding",
        "github",
        "cuda",
    )
    _NEGATIVE_HINTS = (
        "spotlight",
        "office hours",
        "livestream replay",
        "weekly recap",
        "rubber duck thursday",
        "rubber duck thursdays",
    )

    def start_requests(self) -> Iterator[Request]:
        for feed in self.FEEDS:
            yield Request(
                url=feed["feed_url"],
                callback=self.parse_feed,
                dont_filter=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/atom+xml, application/xml, text/xml, */*",
                },
                meta=feed,
            )

    def parse_feed(self, response, **kwargs) -> Iterator[NewsArticle]:
        if len(self.crawled_items) >= self.max_items:
            return

        feed_meta = response.meta
        root = self._parse_xml(response.text, response.url)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "media": "http://search.yahoo.com/mrss/",
        }

        for entry in root.findall("atom:entry", ns):
            if len(self.crawled_items) >= self.max_items:
                break

            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            video_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            url = ""
            for link in entry.findall("atom:link", ns):
                href = (link.get("href") or "").strip()
                rel = (link.get("rel") or "").strip().lower()
                if href and rel in {"alternate", ""}:
                    url = href
                    break
            if not url and video_id:
                url = video_id
            if not title or not url:
                continue

            description = (
                entry.findtext("media:group/media:description", default="", namespaces=ns) or ""
            ).strip()
            if not self._is_meaningful_entry(title, description):
                continue
            summary = self.clean_text(description)
            channel_name = feed_meta.get("channel_name") or "YouTube Official"
            if channel_name:
                summary = self.clean_text(f"{channel_name} | {summary}" if summary else channel_name)

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = summary
            item["url"] = url
            item["published_at"] = (
                entry.findtext("atom:published", default="", namespaces=ns)
                or entry.findtext("atom:updated", default="", namespaces=ns)
                or None
            )
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = feed_meta.get("channel_url") or self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(35, 78 - len(self.crawled_items))
            item["tags"] = ["youtube", "official"]
            item["hash"] = self.compute_hash(title, self.source_code, url)
            self.crawled_items.append(item)
            yield item

    @staticmethod
    def _parse_xml(text: str, url: str):
        try:
            return ET.fromstring(text)
        except ET.ParseError:
            xml_text = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
            return ET.fromstring(xml_text)

    def _is_meaningful_entry(self, title: str, description: str) -> bool:
        haystack = f"{title} {description}".lower()
        has_positive = any(hint in haystack for hint in self._POSITIVE_HINTS)
        has_negative = any(hint in haystack for hint in self._NEGATIVE_HINTS)
        title_lower = (title or "").lower()
        if any(hint in title_lower for hint in self._NEGATIVE_HINTS):
            return False
        if has_negative and not has_positive:
            return False
        return has_positive
