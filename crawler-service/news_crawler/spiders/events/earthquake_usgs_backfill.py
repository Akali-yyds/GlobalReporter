"""USGS backfill job variant."""

from news_crawler.spiders.events.earthquake_usgs import USGSEarthquakeSpider


class USGSEarthquakeBackfillSpider(USGSEarthquakeSpider):
    name = "earthquake_usgs_backfill"
    job_name = "earthquake_usgs_backfill"
    job_mode = "backfill"
