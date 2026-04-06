"""
Bilibili tech/knowledge hot spider.

This spider intentionally does not try to mirror the general hot board.
Instead, it scans the public popular feed and keeps only items that look
like technology, science, current-affairs, or business signals.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class BilibiliHotSpider(BaseNewsSpider):
    name = "bilibili_hot"
    source_name = "Bilibili Hot"
    source_code = "bilibili_hot"
    source_url = "https://www.bilibili.com/"
    country = "CN"
    language = "zh"
    category = "social"

    API_URL = "https://api.bilibili.com/x/web-interface/popular?ps=20&pn={page}"
    MAX_PAGES = 8

    _PRIMARY_VERTICALS = frozenset({
        "数码",
        "科学科普",
        "社科·法律·心理",
        "财经商业",
        "资讯",
    })
    _CONDITIONAL_VERTICALS = frozenset({
        "知识",
        "历史",
    })
    _NEGATIVE_VERTICAL_HINTS = (
        "搞笑",
        "鬼畜",
        "音乐",
        "舞蹈",
        "游戏",
        "影视",
        "娱乐",
        "综艺",
        "动画",
        "美食",
        "时尚",
        "美妆",
        "动物圈",
        "汽车",
        "赛车",
        "运动",
    )
    _TECH_HINTS = (
        "ai",
        "人工智能",
        "大模型",
        "模型",
        "芯片",
        "半导体",
        "显卡",
        "gpu",
        "cpu",
        "安卓",
        "平板",
        "屏幕",
        "开源",
        "编程",
        "代码",
        "github",
        "openai",
        "google",
        "nvidia",
        "机器人",
        "智能家居",
        "手机",
        "笔记本",
        "处理器",
        "推理",
        "量化",
        "航天",
        "火箭",
        "卫星",
        "科技",
        "科学",
        "物理",
        "化学",
        "医学",
        "文献",
    )
    _CURRENT_AFFAIRS_HINTS = (
        "关税",
        "经济",
        "市场",
        "股市",
        "商业",
        "贸易",
        "制裁",
        "冲突",
        "战争",
        "地震",
        "洪水",
        "台风",
        "火灾",
        "事故",
        "美国",
        "中国",
        "欧盟",
        "俄罗斯",
        "乌克兰",
        "伊朗",
        "政策",
        "外交",
        "回应",
        "通报",
        "发布会",
        "反制",
    )
    _NEGATIVE_TEXT_HINTS = (
        "开播",
        "热舞",
        "翻唱",
        "恋爱",
        "甜妹",
        "整活",
        "电视剧",
        "综艺",
        "电影",
        "动画",
        "cos",
        "鬼畜",
        "搞笑",
        "抽象",
        "reaction",
        "吃播",
    )
    _TRUSTED_NEWS_OWNER_HINTS = (
        "央视",
        "新华社",
        "人民日报",
        "中国日报",
        "观察者",
        "澎湃",
        "财新",
        "第一财经",
        "中国天气",
    )
    _TRUSTED_TECH_OWNER_HINTS = (
        "哔哩哔哩科技",
        "bilibili科技",
        "极客湾",
        "geekerwan",
        "毕的二阶导",
        "冷却报告",
    )

    def start_requests(self) -> Iterator[Request]:
        for page in range(1, self.MAX_PAGES + 1):
            yield Request(
                url=self.API_URL.format(page=page),
                callback=self.parse_api,
                dont_filter=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com/",
                    "Accept": "application/json",
                },
                meta={"page": page},
            )

    def parse_api(self, response, **kwargs) -> Iterator[NewsArticle]:
        if len(self.crawled_items) >= self.max_items:
            return

        data = response.json()
        entries = data.get("data", {}).get("list", [])
        for entry in entries:
            if len(self.crawled_items) >= self.max_items:
                break
            if not self._is_meaningful_entry(entry):
                continue

            title = self.clean_text(entry.get("title"))
            bvid = (entry.get("bvid") or "").strip()
            url = (entry.get("short_link_v2") or "").strip()
            if not url and bvid:
                url = f"https://www.bilibili.com/video/{bvid}"
            if not title or not url:
                continue

            summary = self.clean_text(entry.get("desc"))
            owner = (entry.get("owner") or {}).get("name") or ""
            tname = entry.get("tname") or ""
            if owner or tname:
                prefix = " | ".join(part for part in [owner.strip(), tname.strip()] if part)
                summary = self.clean_text(f"{prefix} | {summary}" if summary else prefix)

            stats = entry.get("stat") or {}
            item = NewsArticle()
            item["title"] = title
            item["summary"] = summary
            item["url"] = url
            item["published_at"] = self._published_at_from_ts(entry.get("pubdate"))
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["heat_score"] = self._compute_heat_score(stats)
            item["likes"] = stats.get("like")
            item["views"] = stats.get("view") or stats.get("vv")
            item["comments"] = stats.get("reply")
            item["shares"] = stats.get("share")
            item["hash"] = self.compute_hash(title, self.source_code, url)
            self.crawled_items.append(item)
            yield item

    def _is_meaningful_entry(self, entry: dict) -> bool:
        title = str(entry.get("title") or "")
        desc = str(entry.get("desc") or "")
        category = str(entry.get("tname") or "")
        owner_name = str((entry.get("owner") or {}).get("name") or "")
        text = " ".join([title, desc, owner_name]).lower()

        in_primary_vertical = category in self._PRIMARY_VERTICALS
        in_conditional_vertical = category in self._CONDITIONAL_VERTICALS
        has_negative_vertical = any(hint in category for hint in self._NEGATIVE_VERTICAL_HINTS)
        has_tech_signal = any(hint in text for hint in self._TECH_HINTS)
        has_current_affairs_signal = any(hint in text for hint in self._CURRENT_AFFAIRS_HINTS)
        has_negative_signal = any(hint in text for hint in self._NEGATIVE_TEXT_HINTS)
        trusted_news_owner = any(hint.lower() in owner_name.lower() for hint in self._TRUSTED_NEWS_OWNER_HINTS)
        trusted_tech_owner = any(hint.lower() in owner_name.lower() for hint in self._TRUSTED_TECH_OWNER_HINTS)
        published_at = self._published_at_from_ts(entry.get("pubdate"))
        compact_title = title.replace(" ", "")

        if not published_at:
            return False
        if len(compact_title) < 8 and not (has_tech_signal or has_current_affairs_signal):
            return False
        if has_negative_vertical and not (has_tech_signal or has_current_affairs_signal):
            return False
        if has_negative_signal and not (has_tech_signal or has_current_affairs_signal):
            return False

        if in_primary_vertical:
            if category in {"数码", "科学科普"}:
                return has_tech_signal or trusted_tech_owner
            return has_current_affairs_signal or has_tech_signal or trusted_news_owner

        if in_conditional_vertical:
            return has_tech_signal or has_current_affairs_signal

        return (trusted_news_owner and has_current_affairs_signal) or (trusted_tech_owner and has_tech_signal)

    @staticmethod
    def _published_at_from_ts(value) -> str | None:
        try:
            ts = int(value)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None).isoformat()

    @staticmethod
    def _compute_heat_score(stats: dict) -> int:
        views = int(stats.get("view") or stats.get("vv") or 0)
        likes = int(stats.get("like") or 0)
        comments = int(stats.get("reply") or 0)
        shares = int(stats.get("share") or 0)
        score = 28 + (views // 150000) + (likes // 5000) + (comments // 300) + (shares // 250)
        return max(25, min(100, score))
