"""
Tencent News (腾讯新闻) Spider — multi-strategy.
Tries the hot ranking API, then falls back to HTML page parsing.
"""
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

    # Primary: hot ranking list JSON API
    HOT_API = "https://r.inews.qq.com/gw/event/hot_ranking_list?page_size=20&ptr=0"
    # Fallback 1: older hot ranking API
    HOT_API_V2 = "https://i.news.qq.com/gw/event/pc_hot_ranking_list?offset=0&page_size=20&rank_type=1"
    # Fallback 2: hot news page
    HOT_PAGE = "https://news.qq.com/hotnews/"

    def start_requests(self) -> Iterator[Request]:
        headers = {
            "Referer": "https://news.qq.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        yield Request(url=self.HOT_API, callback=self.parse_api,
                      headers=headers, dont_filter=True)
        yield Request(url=self.HOT_API_V2, callback=self.parse_api,
                      headers=headers, dont_filter=True)
        yield Request(url=self.HOT_PAGE, callback=self.parse_html,
                      headers=headers, dont_filter=True)

    def parse_api(self, response, **kwargs) -> Iterator[NewsArticle]:
        """Parse hot ranking JSON API."""
        text = response.text.strip()
        # Strip JSONP wrapper if present
        if text.startswith("(") and text.endswith(")"):
            text = text[1:-1]

        try:
            import json
            data = json.loads(text)
        except Exception as e:
            logger.warning("Tencent API JSON parse error from %s: %s", response.url, e)
            return

        # Try multiple possible data key paths
        items = (
            data.get("idlist", [{}])[0].get("newslist") if data.get("idlist")
            else data.get("data", {}).get("list")
            or data.get("data")
            or []
        )
        if not items:
            logger.warning("Tencent API: no items in response from %s. keys=%s",
                           response.url, list(data.keys())[:10])
            return

        count = 0
        seen: set[str] = set()
        for row in items:
            if count >= self.max_items:
                break
            title = (row.get("title") or "").strip()
            link = (row.get("url") or row.get("article_url") or "").strip()
            if not title or not link:
                continue
            if link in seen:
                continue
            seen.add(link)
            count += 1

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(
                row.get("intro") or row.get("desc") or row.get("abstract") or ""
            )
            item["url"] = link
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
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

        if count == 0:
            logger.warning("Tencent API parsed 0 items from %s. Body[:400]: %s",
                           response.url, response.text[:400])

    def parse_html(self, response, **kwargs) -> Iterator[NewsArticle]:
        """Fallback: extract from the hot news HTML page."""
        count = 0
        seen: set[str] = set()

        # <a href="..."> inside news item containers
        raw_links = response.css(
            'div.hot-list a[href*="qq.com"], '
            'a[href*="/hotnews/"], '
            'a[href*="news.qq.com"]'
        ).xpath("@href").getall()

        titles = response.css(
            'div.hot-list a[href*="qq.com"]::text, '
            'a[href*="/hotnews/"]::text, '
            'h3 a::text, h2 a::text'
        ).getall()

        for raw_url in raw_links:
            if count >= self.max_items:
                break
            url = raw_url.strip()
            if not url or url in seen or "qq.com" not in url:
                continue
            if not url.startswith("http"):
                url = "https://news.qq.com" + url
            seen.add(url)
            count += 1

            item = NewsArticle()
            item["title"] = None
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
                "Tencent HTML: 0 items. Status=%s body[:500]: %s",
                response.status,
                response.text[:500],
            )

    def parse_fallback(self, response) -> Iterator[NewsArticle]:
        yield from self.parse_html(response)
