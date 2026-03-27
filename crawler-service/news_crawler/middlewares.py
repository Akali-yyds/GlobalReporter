"""Spider / downloader middlewares (optional; disabled in settings by default)."""
import logging

from scrapy import signals

logger = logging.getLogger(__name__)


class NewsSpiderMiddleware:
    """Spider middleware — pass-through."""

    @classmethod
    def from_crawler(cls, crawler):
        o = cls()
        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        return o

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        logger.error("Spider exception in %s: %s", spider.name, exception)
        return None

    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        logger.info("Spider opened: %s", spider.name)


class NewsDownloaderMiddleware:
    """Downloader middleware — pass-through."""

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        return None

    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        logger.warning("Downloader exception for %s: %s", request.url, exception)
        return None
