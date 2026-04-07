"""
Scrapy Items for news crawling.

This module defines the data structures used by spiders to collect news data.
"""
import re
from datetime import datetime
from typing import Optional, List

from scrapy import Item, Field


class NewsArticle(Item):
    """
    News article item representing a single news article.
    """
    # Basic fields
    title = Field()
    url = Field()
    summary = Field()
    content = Field()
    
    # Metadata
    source_name = Field()
    source_code = Field()
    source_url = Field()
    source_class = Field()
    source_tier = Field()
    source_tier_level = Field()
    enabled = Field()
    fetch_mode = Field()
    schedule_minutes = Field()
    dedup_key_mode = Field()
    event_time_field_priority = Field()
    severity_mapping_rule = Field()
    geo_precision_rule = Field()
    default_params_json = Field()
    notes = Field()
    author = Field()
    published_at = Field()
    event_time = Field()
    event_status = Field()
    closed_at = Field()
    source_updated_at = Field()
    crawled_at = Field()

    # Categorization
    category = Field()
    tags = Field()
    language = Field()
    country = Field()
    freshness_sla_hours = Field()
    severity = Field()
    confidence = Field()
    geo = Field()
    geom_type = Field()
    raw_geometry = Field()
    display_geo = Field()
    bbox = Field()
    source_metadata = Field()
    license_mode = Field()
    canonical_url = Field()
    external_id = Field()
    
    # Engagement metrics (if available)
    views = Field()
    likes = Field()
    comments = Field()
    shares = Field()
    
    # Processed data
    heat_score = Field()
    hash = Field()
    
    # Geographic data
    geo_locations = Field()
    geo_entities = Field()
    region_tags = Field()


class NewsEvent(Item):
    """
    News event item representing a cluster of related articles.
    """
    title = Field()
    description = Field()
    start_time = Field()
    end_time = Field()
    scope = Field()  # china, world, all
    categories = Field()
    related_articles = Field()
    heat_score = Field()
    created_at = Field()


class GeoEntity(Item):
    """
    Geographic entity extracted from news articles.
    """
    name = Field()
    name_en = Field()
    country = Field()
    country_code = Field()
    latitude = Field()
    longitude = Field()
    entity_type = Field()  # city, country, region, etc.
    importance = Field()


class CrawlJob(Item):
    """
    Crawl job metadata for tracking crawling operations.
    """
    spider_name = Field()
    started_at = Field()
    finished_at = Field()
    status = Field()  # running, completed, failed
    items_scraped = Field()
    items_dropped = Field()
    error_message = Field()
