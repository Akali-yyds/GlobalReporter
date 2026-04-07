"""GDACS backfill job variant."""

from news_crawler.spiders.events.disaster_gdacs import GDACSDisasterSpider


class GDACSDisasterBackfillSpider(GDACSDisasterSpider):
    name = "disaster_gdacs_backfill"
    job_name = "disaster_gdacs_backfill"
    job_mode = "backfill"
