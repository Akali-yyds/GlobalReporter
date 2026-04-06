"""
OpenAI official news RSS spider.
"""
from datetime import datetime
from typing import Iterator
import xml.etree.ElementTree as ET

import requests
from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class OpenAIOfficialSpider(BaseNewsSpider):
    name = "openai_official"
    source_name = "OpenAI News"
    source_code = "openai_official"
    source_url = "https://openai.com/news/"
    country = "US"
    language = "en"
    category = "technology"

    RSS_URL = "https://openai.com/news/rss.xml"

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            url=self.RSS_URL,
            callback=self.parse_feed,
            dont_filter=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )

    def parse_feed(self, response, **kwargs) -> Iterator[NewsArticle]:
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            xml_text = requests.get(response.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
            root = ET.fromstring(xml_text)
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for it in items:
            if len(self.crawled_items) >= self.max_items:
                break
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if not link:
                link_el = it.find("{http://www.w3.org/2005/Atom}link")
                if link_el is not None:
                    link = (link_el.attrib.get("href") or "").strip()
            if not title or not link:
                continue
            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text((
                it.findtext("description")
                or it.findtext("summary")
                or it.findtext("{http://www.w3.org/2005/Atom}summary")
                or it.findtext("content")
                or ""
            ).strip())
            item["url"] = link
            item["published_at"] = (
                (it.findtext("pubDate") or "").strip()
                or (it.findtext("published") or "").strip()
                or (it.findtext("{http://www.w3.org/2005/Atom}published") or "").strip()
                or (it.findtext("updated") or "").strip()
                or (it.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
                or None
            )
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(1, 75 - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
