"""Heuristics for freshness-era intake quality, topic tags, and coarse category."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Iterable


@dataclass
class NewsSignalResult:
    category: str | None
    tags: list[str]
    priority_score: int
    low_value_score: int
    should_drop: bool
    matched_positive: list[str]
    matched_negative: list[str]


_TOPIC_KEYWORDS: list[tuple[str, str, tuple[str, ...]]] = [
    ("ai", "technology", (
        " ai ", "artificial intelligence", "openai", "chatgpt", "gpt-", "large language model",
        "llm", "anthropic", "gemini", "deepmind", "deepseek", "machine learning",
        "人工智能", "大模型", "模型推理", "生成式ai", "生成式人工智能",
    )),
    ("chip", "technology", (
        "semiconductor", "chip", "chips", "tsmc", "nvidia", "amd", "intel", "qualcomm",
        "broadcom", "arm ", "wafer", "gpu", "cpu", "foundry",
        "芯片", "半导体", "晶圆", "显卡", "算力", "gpu", "cpu",
    )),
    ("cybersecurity", "technology", (
        "cybersecurity", "cyber attack", "ransomware", "malware", "data breach", "hacker",
        "hackers", "zero-day", "zero day", "vulnerability", "phishing", "ddos",
        "网络安全", "勒索软件", "数据泄露", "漏洞", "黑客", "攻击面",
    )),
    ("space", "science", (
        "nasa", "spacex", "rocket", "satellite", "space station", "launch vehicle",
        "astronomy", "telescope", "orbiter",
        "航天", "火箭", "卫星", "空间站", "天文", "发射任务",
    )),
    ("science", "science", (
        "scientists", "researchers", "study finds", "journal", "laboratory", "breakthrough",
        "experiment", "research team",
        "科学家", "研究团队", "研究显示", "实验室", "突破", "科研",
    )),
    ("conflict", "conflict", (
        "war", "missile", "airstrike", "drone strike", "troops", "military", "ceasefire",
        "artillery", "offensive", "defense ministry", "defence ministry", "navy", "armed forces",
        "冲突", "战争", "导弹", "空袭", "袭击", "无人机袭击", "停火", "军方", "军队", "国防部",
    )),
    ("disaster", "disaster", (
        "earthquake", "flood", "wildfire", "typhoon", "hurricane", "storm", "volcano",
        "landslide", "tsunami", "evacuation order", "heatwave",
        "地震", "洪水", "山火", "台风", "飓风", "风暴", "火山", "山体滑坡", "海啸", "疏散令", "高温",
    )),
    ("climate", "science", (
        "climate", "global warming", "emissions", "carbon", "greenhouse gas", "extreme weather",
        "气候", "全球变暖", "碳排放", "温室气体", "极端天气",
    )),
    ("policy", "policy", (
        "white house", "ministry", "cabinet", "executive order", "regulation", "bill", "senate",
        "parliament", "tariff", "sanction", "central bank", "supreme court",
        "政策", "法案", "监管", "国务院", "部委", "央行", "制裁", "关税", "最高法院",
    )),
    ("economy", "business", (
        "inflation", "gdp", "market", "stocks", "bond yield", "interest rate", "trade data",
        "earnings", "revenue", "layoffs", "manufacturing",
        "经济", "股市", "通胀", "利率", "财报", "营收", "裁员", "制造业",
    )),
]

_LOW_VALUE_KEYWORDS: tuple[str, ...] = (
    "tv series", "drama", "idol", "celebrity", "box office", "variety show", "fan meeting",
    "dating rumor", "dating rumours", "wedding rumor", "entertainment news", "concert tour",
    "episode finale", "talent show",
    "电视剧", "综艺", "明星", "偶像", "粉丝", "票房", "恋情", "演唱会", "开播", "杀青", "定档",
    "cp", "饭圈", "选秀", "男团", "女团", "八卦", "绯闻",
)

_PRIORITY_TERMS: tuple[str, ...] = (
    "breaking", "urgent", "alert", "evacuation", "announces", "launches", "security advisory",
    "confirmed", "official statement", "emergency",
    "突发", "紧急", "警报", "通报", "发布", "宣布", "预警", "应急",
)


def _prepare_text(*parts: str | None) -> tuple[str, str]:
    raw = " ".join((part or "") for part in parts)
    lowered = f" {re.sub(r'\\s+', ' ', raw).lower()} "
    return raw, lowered


@lru_cache(maxsize=512)
def _ascii_keyword_regex(keyword: str) -> re.Pattern[str]:
    normalized = keyword.strip().lower()
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    prefix = r"(?<![a-z0-9])" if normalized[:1].isalnum() else ""
    suffix = r"(?![a-z0-9])" if normalized[-1:].isalnum() else ""
    return re.compile(f"{prefix}{escaped}{suffix}", re.IGNORECASE)


def _matches_keywords(raw_text: str, lowered_text: str, keywords: Iterable[str]) -> list[str]:
    matches: list[str] = []
    for keyword in keywords:
        normalized = keyword.strip()
        if not normalized:
            continue
        if normalized.isascii():
            if _ascii_keyword_regex(normalized).search(lowered_text):
                matches.append(normalized)
        else:
            if normalized in raw_text:
                matches.append(normalized)
    return matches


def classify_news_signal(
    *,
    title: str | None,
    summary: str | None,
    content: str | None,
    source_code: str | None = None,
    base_category: str | None = None,
) -> NewsSignalResult:
    raw_text, lowered_text = _prepare_text(title, summary, content)
    tags: list[str] = []
    matched_positive: list[str] = []
    matched_negative = _matches_keywords(raw_text, lowered_text, _LOW_VALUE_KEYWORDS)

    score = 0
    category_scores: dict[str, int] = {}
    for tag, category, keywords in _TOPIC_KEYWORDS:
        found = _matches_keywords(raw_text, lowered_text, keywords)
        if not found:
            continue
        tags.append(tag)
        matched_positive.extend(found)
        category_scores[category] = category_scores.get(category, 0) + len(found)
        score += 2 + min(2, len(found))

    priority_hits = _matches_keywords(raw_text, lowered_text, _PRIORITY_TERMS)
    score += min(3, len(priority_hits))
    matched_positive.extend(priority_hits)

    # Social feeds with no strong positive signal are more likely to be noise.
    if (source_code or "").strip().lower() in {"weibo"}:
        score -= 1

    low_value_score = len(matched_negative) * 2
    should_drop = low_value_score >= 2 and score < 3

    if category_scores:
        category = max(category_scores.items(), key=lambda item: item[1])[0]
    else:
        category = base_category

    ordered_tags: list[str] = []
    for tag in tags:
        if tag not in ordered_tags:
            ordered_tags.append(tag)

    return NewsSignalResult(
        category=category,
        tags=ordered_tags,
        priority_score=score,
        low_value_score=low_value_score,
        should_drop=should_drop,
        matched_positive=matched_positive,
        matched_negative=matched_negative,
    )
