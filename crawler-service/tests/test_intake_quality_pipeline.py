from datetime import datetime, timedelta

import pytest
from scrapy.exceptions import DropItem

from news_crawler.pipelines import (
    EventSchemaPipeline,
    IntakeQualityPipeline,
    SourceProfilePipeline,
    TimelinessPipeline,
)
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


def test_signal_classifier_does_not_tag_iran_story_as_ai_from_substrings():
    result = classify_news_signal(
        title="Japanese national believed to be NHK journalist detained in Iran released on bail",
        summary="Officials said the reporter was released after the detention case moved forward.",
        content=None,
        source_code="abc_news",
        base_category="news",
    )

    assert "ai" not in result.tags
    assert "science" not in result.tags


def test_signal_classifier_does_not_match_war_inside_warns():
    result = classify_news_signal(
        title="Trump warns Iran it could be destroyed in one night as deadline nears",
        summary="The deadline is approaching as diplomatic efforts continue.",
        content=None,
        source_code="euronews",
        base_category="news",
    )

    assert "conflict" not in result.tags
    assert result.category == "policy"


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


def test_signal_classifier_extracts_health_and_energy_tags():
    result = classify_news_signal(
        title="WHO warns hospitals as oil pipeline outage hits vaccine transport routes",
        summary="Public health teams are responding while energy infrastructure remains disrupted.",
        content=None,
        source_code="bbc",
        base_category="news",
    )

    assert "health" in result.tags
    assert "energy" in result.tags
    assert "transport" in result.tags


def test_signal_classifier_adds_other_tag_as_fallback():
    result = classify_news_signal(
        title="Regional mayor gives interview about local school opening schedule",
        summary="Officials discussed routine municipal planning for the coming week.",
        content=None,
        source_code="guardian",
        base_category="news",
    )

    assert result.tags == ["other"]
    assert not result.should_drop


def test_source_profile_assigns_lead_defaults():
    spider = _DummySpider()
    pipeline = SourceProfilePipeline()
    item = {
        "title": "OpenAI acquires TBPN",
        "url": "https://openai.com/news/openai-acquires-tbpn",
        "source_name": "OpenAI News",
        "source_code": "openai_official",
        "source_url": "https://openai.com/news/",
        "category": "official",
    }

    result = pipeline.process_item(item, spider)
    assert result["source_class"] == "lead"
    assert result["source_tier"] == "official"
    assert result["source_tier_level"] == 1
    assert result["freshness_sla_hours"] == 168
    assert result["license_mode"] == "official_public"


def test_timeliness_pipeline_drops_stale_news_items():
    spider = _DummySpider()
    pipeline = TimelinessPipeline(default_max_age_hours=24, allow_missing_published_at=True)
    item = {
        "title": "Old earthquake report",
        "summary": "Archived follow-up",
        "content": None,
        "source_code": "bbc",
        "source_class": "news",
        "freshness_sla_hours": 24,
        "category": "news",
        "published_at": (datetime.utcnow() - timedelta(hours=48)).isoformat(),
    }

    with pytest.raises(DropItem):
        pipeline.process_item(item, spider)


def test_intake_pipeline_assigns_tags_and_semantic_category():
    spider = _DummySpider()
    pipeline = IntakeQualityPipeline(filter_low_value=True)
    item = {
        "title": "OpenAI unveils new model for cybersecurity defense",
        "summary": "Researchers said the AI system can detect malware and zero-day behavior.",
        "content": None,
        "source_code": "guardian",
        "source_class": "news",
        "category": "news",
        "published_at": datetime.utcnow().isoformat(),
        "tags": ["breaking"],
    }

    result = pipeline.process_item(item, spider)
    assert result["category"] == "technology"
    assert "ai" in result["tags"]
    assert "cybersecurity" in result["tags"]
    assert "breaking" in result["tags"]


def test_intake_pipeline_preserves_other_fallback_tag():
    spider = _DummySpider()
    pipeline = IntakeQualityPipeline(filter_low_value=True)
    item = {
        "title": "Local officials discuss routine road maintenance budget",
        "summary": "The meeting covered administrative scheduling and ordinary planning updates.",
        "content": None,
        "source_code": "guardian",
        "source_class": "news",
        "category": "news",
        "published_at": datetime.utcnow().isoformat(),
    }

    result = pipeline.process_item(item, spider)
    assert result["tags"] == ["other"]


def test_intake_pipeline_drops_low_value_item():
    spider = _DummySpider()
    pipeline = IntakeQualityPipeline(filter_low_value=True)
    item = {
        "title": "Popular variety show announces celebrity comeback stage",
        "summary": "Concert rumors and fan voting heated up overnight.",
        "content": None,
        "source_code": "weibo",
        "source_class": "lead",
        "category": "social",
        "published_at": datetime.utcnow().isoformat(),
    }

    with pytest.raises(DropItem):
        pipeline.process_item(item, spider)


def test_event_schema_pipeline_validates_and_normalizes_event_item():
    spider = _DummySpider()
    pipeline = EventSchemaPipeline()
    item = {
        "title": "Magnitude 5.2 earthquake near Hualien",
        "url": "https://earthquake.usgs.gov/example/1",
        "source_code": "earthquake_usgs",
        "source_class": "event",
        "event_time": datetime.utcnow().isoformat(),
        "external_id": "usgs-evt-123",
        "severity": 4.6,
        "confidence": 0.87,
    }

    result = pipeline.process_item(item, spider)
    assert result["event_time"]
    assert result["severity"] == 5
    assert result["confidence"] == 87
    assert result["hash"]


def test_event_schema_pipeline_accepts_epoch_milliseconds():
    spider = _DummySpider()
    pipeline = EventSchemaPipeline()
    item = {
        "title": "Magnitude 4.8 earthquake near Alaska",
        "url": "https://earthquake.usgs.gov/example/2",
        "source_code": "earthquake_usgs",
        "source_class": "event",
        "event_time": 1775428800000,
        "source_updated_at": 1775429400000,
        "external_id": "usgs-evt-456",
    }

    result = pipeline.process_item(item, spider)
    assert result["event_time"].startswith("2026-")
    assert result["source_updated_at"].startswith("2026-")


def test_timeliness_pipeline_keeps_open_event_even_if_old():
    spider = _DummySpider()
    pipeline = TimelinessPipeline(default_max_age_hours=24, allow_missing_published_at=False)
    item = {
        "title": "Long-running wildfire event",
        "url": "https://eonet.gsfc.nasa.gov/api/v3/events/EONET_1",
        "source_code": "eonet_events",
        "source_class": "event",
        "event_status": "open",
        "event_time": (datetime.utcnow() - timedelta(days=4)).isoformat(),
        "source_updated_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
        "external_id": "EONET_1",
        "freshness_sla_hours": 24,
    }

    result = pipeline.process_item(item, spider)
    assert result["event_status"] == "open"
