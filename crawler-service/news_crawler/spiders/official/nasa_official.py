"""
NASA official news feed spider.
"""
from datetime import datetime
from typing import Iterator
import xml.etree.ElementTree as ET

import requests
from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class NASAOfficialSpider(BaseNewsSpider):
    name = "nasa_official"
    source_name = "NASA News"
    source_code = "nasa_official"
    source_url = "https://www.nasa.gov/news/"
    country = "US"
    language = "en"
    category = "science"

    RSS_URLS = [
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    ]

    def start_requests(self) -> Iterator[Request]:
        for url in self.RSS_URLS:
            yield Request(
                url=url,
                callback=self.parse_rss,
                dont_filter=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                },
            )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            xml_text = requests.get(response.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
            root = ET.fromstring(xml_text)
        for it in root.findall(".//item"):
            if len(self.crawled_items) >= self.max_items:
                break
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or it.findtext("guid") or "").strip()
            if not title or not link:
                continue
            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text((it.findtext("description") or "").strip())
            item["url"] = link
            item["published_at"] = (it.findtext("pubDate") or "").strip() or None
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(1, 70 - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
