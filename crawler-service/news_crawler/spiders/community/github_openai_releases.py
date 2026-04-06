"""
GitHub releases Atom spider for openai/openai-python.
"""
from datetime import datetime
from typing import Iterator
import xml.etree.ElementTree as ET

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class GitHubOpenAIReleasesSpider(BaseNewsSpider):
    name = "github_openai_releases"
    source_name = "GitHub Releases"
    source_code = "github_openai_releases"
    source_url = "https://github.com/openai/codex/releases"
    country = "US"
    language = "en"
    category = "technology"

    ATOM_URL = "https://github.com/openai/codex/releases.atom"

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            url=self.ATOM_URL,
            callback=self.parse_atom,
            dont_filter=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/atom+xml, application/xml, text/xml, */*",
            },
        )

    def parse_atom(self, response, **kwargs) -> Iterator[NewsArticle]:
        root = ET.fromstring(response.text)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in entries:
            if len(self.crawled_items) >= self.max_items:
                break
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            link = (link_el.attrib.get("href") or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            summary = (
                entry.findtext("{http://www.w3.org/2005/Atom}content")
                or entry.findtext("{http://www.w3.org/2005/Atom}summary")
                or ""
            ).strip()
            published = (
                (entry.findtext("{http://www.w3.org/2005/Atom}published") or "").strip()
                or (entry.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
                or None
            )
            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(summary)
            item["url"] = link
            item["published_at"] = published
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = max(1, 66 - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
