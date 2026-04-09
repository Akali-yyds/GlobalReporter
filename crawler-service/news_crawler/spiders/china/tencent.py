"""
Tencent News spider.

Uses the primary hot ranking API first, only falling back to secondary sources
when the first endpoint does not provide enough unique items. This avoids the
previous pattern where all endpoints were hit up-front and then mostly deduped
in the pipeline.
"""
import json
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)


class TencentSpider(BaseNewsSpider):
    name = "tencent"
    source_name = "腾讯新闻"
    source_code = "tencent"
    source_url = "https://news.qq.com"
    country = "CN"
    language = "zh"
    category = "news"

    HOT_API = "https://r.inews.qq.com/gw/event/hot_ranking_list?page_size=20&ptr=0"
    HOT_API_V2 = "https://i.news.qq.com/gw/event/pc_hot_ranking_list?offset=0&page_size=20&rank_type=1"
    HOT_PAGE = "https://news.qq.com/hotnews/"

    def start_requests(self) -> Iterator[Request]:
        self._seen_urls: set[str] = set()
        headers = self._headers(accept="application/json, text/plain, */*")
        yield Request(
            url=self.HOT_API,
            callback=self.parse_primary_api,
            headers=headers,
            dont_filter=True,
        )

    def parse_primary_api(self, response, **kwargs) -> Iterator[NewsArticle]:
        emitted = yield from self._parse_api_items(response)
        if len(self._seen_urls) < self.max_items:
            yield Request(
                url=self.HOT_API_V2,
                callback=self.parse_secondary_api,
                headers=self._headers(accept="application/json, text/plain, */*"),
                dont_filter=True,
            )
        elif emitted == 0:
            logger.warning("Tencent primary API produced 0 items from %s", response.url)

    def parse_secondary_api(self, response, **kwargs) -> Iterator[NewsArticle]:
        yield from self._parse_api_items(response)
        if len(self._seen_urls) < self.max_items:
            yield Request(
                url=self.HOT_PAGE,
                callback=self.parse_html,
                headers=self._headers(accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
                dont_filter=True,
            )

    def _parse_api_items(self, response) -> Iterator[NewsArticle]:
        text = response.text.strip()
        if text.startswith("(") and text.endswith(")"):
            text = text[1:-1]

        try:
            data = json.loads(text)
        except Exception as exc:
            logger.warning("Tencent API JSON parse error from %s: %s", response.url, exc)
            return

        items = (
            data.get("idlist", [{}])[0].get("newslist")
            if data.get("idlist")
            else data.get("data", {}).get("list")
            or data.get("data")
            or []
        )
        if not items:
            logger.warning(
                "Tencent API: no items in response from %s. keys=%s",
                response.url,
                list(data.keys())[:10],
            )
            return

        emitted = 0
        for row in items:
            if len(self.crawled_items) >= self.max_items:
                break

            title = (row.get("title") or "").strip()
            link = (row.get("url") or row.get("article_url") or "").strip()
            if not title or not link or link in self._seen_urls:
                continue

            self._seen_urls.add(link)
            emitted += 1
            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(
                row.get("intro") or row.get("desc") or row.get("abstract") or ""
            )
            item["url"] = link
            item["canonical_url"] = link
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["published_at"] = (
                row.get("publish_time") or row.get("ptime") or row.get("timestamp") or None
            )
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = row.get("category") or self.category
            item["heat_score"] = int(
                row.get("hotValue") or row.get("heat") or row.get("hot_score") or 0
            )
            item["source_metadata"] = {
                "fetch_via": "hot_api",
                "endpoint": response.url,
            }
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

        if emitted == 0:
            logger.warning(
                "Tencent API parsed 0 unique items from %s. Body[:400]: %s",
                response.url,
                response.text[:400],
            )

    def parse_html(self, response, **kwargs) -> Iterator[NewsArticle]:
        count = 0
        for link_sel in response.css("a[href]"):
            if len(self.crawled_items) >= self.max_items:
                break

            raw_url = (link_sel.attrib.get("href") or "").strip()
            if not raw_url:
                continue
            url = response.urljoin(raw_url)
            if (
                not url.startswith("https://")
                or "qq.com" not in url
                or url in self._seen_urls
            ):
                continue

            title = self.clean_text(link_sel.xpath("normalize-space(string())").get())
            if not title or len(title) < 8:
                continue

            self._seen_urls.add(url)
            count += 1

            item = NewsArticle()
            item["title"] = title
            item["url"] = url
            item["canonical_url"] = url
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["source_metadata"] = {
                "fetch_via": "hot_html_fallback",
                "endpoint": response.url,
            }
            item["hash"] = self.compute_hash(title, self.source_code, url)
            self.crawled_items.append(item)
            yield item

        if count == 0:
            logger.warning(
                "Tencent HTML fallback: 0 unique items. Status=%s body[:500]: %s",
                response.status,
                response.text[:500],
            )

    def _headers(self, *, accept: str) -> dict[str, str]:
        return {
            "Referer": "https://news.qq.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": accept,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
