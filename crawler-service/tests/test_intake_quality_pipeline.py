from datetime import datetime, timedelta

import pytest
from scrapy.exceptions import DropItem

from news_crawler.pipelines import IntakeQualityPipeline
from news_crawler.spiders.base import BaseNewsSpider
from news_crawler.utils.news_signal import classify_news_signal


class _DummySpider:
    name = "dummy"

    def parse_datetime(self, value):
        return BaseNewsSpider.parse_datetime(self, value)


def test_signal_classifier_extracts_ai_and_chip_tags():
    result = classify_news_signal(
        title="OpenAI and Nvidia push new AI chip infrastructure plans",
        summary="The companies said new large language model systems will need more GPU capacity.",
        content=None,
        source_code="bbc",
        base_category="news",
    )

    assert "ai" in result.tags
    assert "chip" in result.tags
    assert result.category == "technology"
    assert not result.should_drop


def test_signal_classifier_marks_low_value_entertainment():
    result = classify_news_signal(
        title="Popular TV drama announces new cast ahead of season launch",
        summary="Fans discussed the celebrity lineup and concert tour rumors.",
        content=None,
        source_code="weibo",
        base_category="social",
    )

    assert result.should_drop
    assert result.low_value_score >= 2


def test_intake_pipeline_drops_stale_items():
    spider = _DummySpider()
    pipeline = IntakeQualityPipeline(max_age_hours=24, filter_low_value=True, allow_missing_published_at=True)
    item = {
        "title": "Old earthquake report",
        "summary": "Archived follow-up",
        "content": None,
        "source_code": "bbc",
        "category": "news",
        "published_at": (datetime.utcnow() - timedelta(hours=48)).isoformat(),
    }

    with pytest.raises(DropItem):
        pipeline.process_item(item, spider)


def test_intake_pipeline_assigns_tags_and_semantic_category():
    spider = _DummySpider()
    pipeline = IntakeQualityPipeline(max_age_hours=24, filter_low_value=True, allow_missing_published_at=True)
    item = {
        "title": "OpenAI unveils new model for cybersecurity defense",
        "summary": "Researchers said the AI system can detect malware and zero-day behavior.",
        "content": None,
        "source_code": "guardian",
        "category": "news",
        "published_at": datetime.utcnow().isoformat(),
        "tags": ["breaking"],
    }

    result = pipeline.process_item(item, spider)
    assert result["category"] == "technology"
    assert "ai" in result["tags"]
    assert "cybersecurity" in result["tags"]
    assert "breaking" in result["tags"]


def test_intake_pipeline_drops_low_value_item():
    spider = _DummySpider()
    pipeline = IntakeQualityPipeline(max_age_hours=24, filter_low_value=True, allow_missing_published_at=True)
    item = {
        "title": "电视剧定档引发粉丝热议",
        "summary": "多位明星加盟综艺和演唱会消息同步曝光。",
        "content": None,
        "source_code": "weibo",
        "category": "social",
        "published_at": datetime.utcnow().isoformat(),
    }

    with pytest.raises(DropItem):
        pipeline.process_item(item, spider)
