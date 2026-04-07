"""EONET backfill job variant."""

from news_crawler.spiders.events.eonet_events import EONETEventsSpider


class EONETEventsBackfillSpider(EONETEventsSpider):
    name = "eonet_events_backfill"
    job_name = "eonet_events_backfill"
    job_mode = "backfill"
