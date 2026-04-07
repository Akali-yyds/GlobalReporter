import json

from scrapy.http import Request, TextResponse, XmlResponse

from news_crawler.spiders.asia.cna import CnaSpider
from news_crawler.spiders.asia.ndtv import NDTVSpider
from news_crawler.spiders.asia.scmp import ScmpSpider
from news_crawler.spiders.asia.straits_times import StraitsTimesSpider
from news_crawler.spiders.world.aljazeera import AlJazeeraSpider
from news_crawler.spiders.world.abc_news import AbcNewsSpider
from news_crawler.spiders.world.ap import APNewsSpider
from news_crawler.spiders.world.bbc import BBCSpider
from news_crawler.spiders.world.cbs_news import CbsNewsSpider
from news_crawler.spiders.world.dw import DWSpider
from news_crawler.spiders.world.ft import FtSpider
from news_crawler.spiders.world.france24 import France24Spider
from news_crawler.spiders.world.guardian import GuardianSpider
from news_crawler.spiders.world.nhk_world import NHKWorldSpider
from news_crawler.spiders.world.nbc_news import NbcNewsSpider
from news_crawler.spiders.world.pbs_newshour import PbsNewsHourSpider
from news_crawler.spiders.world.reuters import ReutersSpider
from news_crawler.spiders.world.euronews import EuronewsSpider
from news_crawler.spiders.world.fox_news import FoxNewsSpider
from news_crawler.spiders.world.sky_news import SkyNewsSpider
from news_crawler.spiders.world.times_of_india import TimesOfIndiaSpider
from news_crawler.spiders.world.voa import VoaSpider
from news_crawler.utils.feed_control import resolve_feed_profiles
from news_crawler.spiders.lead.gdelt_doc_global import GDELTDocGlobalSpider
from news_crawler.spiders.official.dod_official import DODOfficialSpider
from news_crawler.spiders.official.nvidia_official import NvidiaOfficialSpider
from news_crawler.spiders.official.youtube_blog import YouTubeBlogSpider


def test_nvidia_official_parses_rss_item():
    spider = NvidiaOfficialSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>NVIDIA announces new AI platform</title>
          <link>https://blogs.nvidia.com/blog/new-ai-platform/</link>
          <description>New AI infrastructure update.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = TextResponse(
        url="https://blogs.nvidia.com/feed/",
        request=Request(url="https://blogs.nvidia.com/feed/"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    item = items[0]
    assert item["source_class"] == "lead"
    assert item["source_tier"] == "official"
    assert item["freshness_sla_hours"] == 168
    assert item["category"] == "official"


def test_youtube_blog_parses_rss_item():
    spider = YouTubeBlogSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>YouTube shares creator policy updates</title>
          <link>https://blog.youtube/news-and-events/creator-policy-updates/</link>
          <description>New YouTube policy update.</description>
          <pubDate>Sun, 06 Apr 2026 07:30:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = TextResponse(
        url="https://blog.youtube/rss/",
        request=Request(url="https://blog.youtube/rss/"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "youtube_blog"
    assert items[0]["source_tier"] == "official"


def test_dod_official_parses_rss_item():
    spider = DODOfficialSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Defense Department updates cyber posture</title>
          <link>https://www.defense.gov/News/News-Stories/Article/article/1/</link>
          <description>Cyber posture update.</description>
          <pubDate>Sun, 06 Apr 2026 06:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = TextResponse(
        url="https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?max=20&ContentType=1&Site=945",
        request=Request(url="https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?max=20&ContentType=1&Site=945"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "dod_official"
    assert items[0]["freshness_sla_hours"] == 72


def test_gdelt_doc_global_parses_lead_items():
    spider = GDELTDocGlobalSpider(max_items=2)
    body = json.dumps(
        {
            "articles": [
                {
                    "url": "https://example.com/world/earthquake-alert",
                    "title": "Earthquake alert issued after strong shaking",
                    "seendate": "20260406T081500Z",
                    "domain": "example.com",
                    "sourcecountry": "Japan",
                }
            ]
        }
    )
    response = TextResponse(
        url="https://api.gdeltproject.org/api/v2/doc/doc?query=test&mode=artlist&format=json",
        request=Request(url="https://api.gdeltproject.org/api/v2/doc/doc?query=test&mode=artlist&format=json"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    item = items[0]
    assert item["source_class"] == "lead"
    assert item["source_tier"] == "aggregator"
    assert item["freshness_sla_hours"] == 48
    assert item["source_metadata"]["role"] == "global_lead"


def test_bbc_parses_official_rss_item():
    spider = BBCSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>BBC covers major summit</title>
          <link>https://www.bbc.com/news/world-123</link>
          <description>BBC item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.bbc.com/news/rss.xml",
        request=Request(url="https://www.bbc.com/news/rss.xml"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_class"] == "news"
    assert items[0]["source_tier"] == "authoritative"
    assert items[0]["source_metadata"]["fetch_via"] == "official_rss"


def test_guardian_parses_official_rss_item():
    spider = GuardianSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Guardian world story</title>
          <link>https://www.theguardian.com/world/2026/apr/06/story</link>
          <description>Guardian item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.theguardian.com/world/rss",
        request=Request(url="https://www.theguardian.com/world/rss"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_tier_level"] == 2
    assert items[0]["license_mode"] == "publisher_public"


def test_aljazeera_parses_official_rss_item():
    spider = AlJazeeraSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Al Jazeera reports on region</title>
          <link>https://www.aljazeera.com/news/2026/04/06/story</link>
          <description>Al Jazeera item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>news</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.aljazeera.com/xml/rss/all.xml",
        request=Request(url="https://www.aljazeera.com/xml/rss/all.xml"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_metadata"]["feed_url"] == "https://www.aljazeera.com/xml/rss/all.xml"


def test_reuters_google_news_fallback_parses_items():
    spider = ReutersSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Reuters headline - Reuters</title>
          <link>https://news.google.com/rss/articles/reuters-1</link>
          <description>Reuters via Google News.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en",
        request=Request(url="https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    assert items[0]["title"] == "Reuters headline"
    assert items[0]["source_metadata"]["fetch_via"] == "google_news_rss_fallback"


def test_ap_google_news_fallback_parses_items():
    spider = APNewsSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>AP headline - AP News</title>
          <link>https://news.google.com/rss/articles/ap-1</link>
          <description>AP via Google News.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://news.google.com/rss/search?q=site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en",
        request=Request(url="https://news.google.com/rss/search?q=site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    assert items[0]["title"] == "AP headline"
    assert items[0]["source_metadata"]["publisher_domain"] == "apnews.com"


def test_cna_parses_official_rss_item():
    spider = CnaSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>CNA world update</title>
          <link>https://www.channelnewsasia.com/world/story-1</link>
          <description>CNA item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6311",
        request=Request(url="https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6311"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["license_mode"] == "publisher_public_noncommercial"
    assert items[0]["source_metadata"]["usage_note"] == "personal_noncommercial_only"


def test_dw_parses_official_rdf_item():
    spider = DWSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <item rdf:about="https://www.dw.com/en/story/a-1">
        <title>DW world update</title>
        <link>https://www.dw.com/en/story/a-1</link>
        <description>DW item description.</description>
        <dc:date>2026-04-06T08:00:00Z</dc:date>
      </item>
    </rdf:RDF>"""
    response = XmlResponse(
        url="https://rss.dw.com/rdf/rss-en-world",
        request=Request(url="https://rss.dw.com/rdf/rss-en-world"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_metadata"]["fetch_via"] == "official_rss"


def test_ndtv_parses_official_rss_item():
    spider = NDTVSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>NDTV world update</title>
          <link>https://www.ndtv.com/world-news/story-1</link>
          <description>NDTV item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://feeds.feedburner.com/ndtvnews-world-news",
        request=Request(url="https://feeds.feedburner.com/ndtvnews-world-news"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["license_mode"] == "publisher_public_noncommercial"
    assert items[0]["source_metadata"]["usage_note"] == "personal_noncommercial_only"


def test_abc_news_parses_official_rss_item():
    spider = AbcNewsSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>ABC News world update</title>
          <link>https://abcnews.go.com/International/story-1</link>
          <description>ABC item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://feeds.abcnews.com/abcnews/internationalheadlines",
        request=Request(url="https://feeds.abcnews.com/abcnews/internationalheadlines"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "abc_news"
    assert items[0]["source_metadata"]["fetch_via"] == "official_rss"


def test_voa_parses_official_rss_item():
    spider = VoaSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>VOA top story</title>
          <link>https://www.voanews.com/a/story-1/123456.html</link>
          <description>VOA item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>top story</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.voanews.com/api/",
        request=Request(url="https://www.voanews.com/api/"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "voa"


def test_cbs_news_parses_official_rss_item():
    spider = CbsNewsSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>CBS News latest update</title>
          <link>https://www.cbsnews.com/news/story-1/</link>
          <description>CBS item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.cbsnews.com/latest/rss/main",
        request=Request(url="https://www.cbsnews.com/latest/rss/main"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "cbs_news"


def test_sky_news_parses_official_rss_item():
    spider = SkyNewsSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Sky News world update</title>
          <link>https://news.sky.com/story/story-1</link>
          <description>Sky item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="http://feeds.skynews.com/feeds/rss/world.xml",
        request=Request(url="http://feeds.skynews.com/feeds/rss/world.xml"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "sky_news"


def test_nhk_world_parses_official_rss_poc_item():
    spider = NHKWorldSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>NHK World update</title>
          <link>https://www3.nhk.or.jp/news/html/20260406/k1001.html</link>
          <description>NHK item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www3.nhk.or.jp/rss/news/cat0.xml",
        request=Request(url="https://www3.nhk.or.jp/rss/news/cat0.xml"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_metadata"]["rollout"] == "poc_only"


def test_france24_parses_official_rss_poc_item():
    spider = France24Spider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>France24 world update</title>
          <link>https://www.france24.com/en/story-1</link>
          <description>France24 item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.france24.com/en/rss",
        request=Request(url="https://www.france24.com/en/rss"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_metadata"]["rollout"] == "poc_only"


def test_pbs_newshour_parses_official_rss_item():
    spider = PbsNewsHourSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title><![CDATA[PBS NewsHour latest story]]></title>
          <link>https://www.pbs.org/newshour/world/story-1</link>
          <description><![CDATA[PBS item description.]]></description>
          <pubDate>Mon, 06 Apr 2026 10:01:56 -0400</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.pbs.org/newshour/feeds/rss/headlines",
        request=Request(url="https://www.pbs.org/newshour/feeds/rss/headlines"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "pbs_newshour"
    assert items[0]["source_metadata"]["feed_name"] == "headlines"


def test_euronews_parses_official_rss_item():
    spider = EuronewsSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
      <channel>
        <item>
          <title>Euronews world update</title>
          <link>https://www.euronews.com/2026/04/06/story-1</link>
          <description>Euronews item description.</description>
          <pubDate>Mon, 06 Apr 2026 15:55:51 +0200</pubDate>
          <category>news</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.euronews.com/rss?format=mrss&level=theme&name=news",
        request=Request(url="https://www.euronews.com/rss?format=mrss&level=theme&name=news"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "euronews"
    assert items[0]["source_metadata"]["feed_name"] == "world_news"


def test_nbc_news_parses_rss_poc_item():
    spider = NbcNewsSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>NBC News top story</title>
          <link>https://www.nbcnews.com/news/story-1</link>
          <description>NBC item description.</description>
          <pubDate>Mon, 06 Apr 2026 12:49:23 GMT</pubDate>
          <category>news</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://feeds.nbcnews.com/nbcnews/public/news",
        request=Request(url="https://feeds.nbcnews.com/nbcnews/public/news"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "nbc_news"
    assert items[0]["source_metadata"]["rollout"] == "poc_only"


def test_fox_news_parses_official_rss_item():
    spider = FoxNewsSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Fox News latest update</title>
          <link>https://www.foxnews.com/world/story-1</link>
          <description>Fox item description.</description>
          <pubDate>Mon, 06 Apr 2026 10:00:29 -0400</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://moxie.foxnews.com/google-publisher/latest.xml",
        request=Request(url="https://moxie.foxnews.com/google-publisher/latest.xml"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["license_mode"] == "publisher_public_noncommercial"
    assert items[0]["source_metadata"]["feed_name"] == "latest"


def test_times_of_india_parses_official_rss_item():
    spider = TimesOfIndiaSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>TOI top story</title>
          <link>https://timesofindia.indiatimes.com/india/story-1/articleshow/123.cms</link>
          <description>TOI item description.</description>
          <pubDate>Mon, 06 Apr 2026 18:04:22 +0530</pubDate>
          <category>Top Stories</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        request=Request(url="https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["license_mode"] == "publisher_public_noncommercial"
    assert items[0]["source_metadata"]["feed_name"] == "top_stories"


def test_scmp_parses_official_rss_item():
    spider = ScmpSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>SCMP world update</title>
          <link>https://www.scmp.com/news/world/article/1</link>
          <description>SCMP item description.</description>
          <pubDate>Sun, 06 Apr 2026 08:00:00 GMT</pubDate>
          <category>world</category>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.scmp.com/rss/91/feed",
        request=Request(url="https://www.scmp.com/rss/91/feed"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_tier_level"] == 2


def test_straits_times_parses_official_rss_item():
    spider = StraitsTimesSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Straits Times world update</title>
          <link>https://www.straitstimes.com/world/story-1</link>
          <description>ST item description.</description>
          <pubDate>Mon, 06 Apr 2026 20:45:16 +0800</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.straitstimes.com/news/world/rss.xml",
        request=Request(url="https://www.straitstimes.com/news/world/rss.xml"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_code"] == "straits_times"
    assert items[0]["source_metadata"]["feed_url"] == "https://www.straitstimes.com/news/world/rss.xml"


def test_ft_parses_official_rss_poc_item():
    spider = FtSpider(max_items=2)
    body = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>FT international update</title>
          <link>https://www.ft.com/content/abc123</link>
          <description>FT item description.</description>
          <pubDate>Mon, 06 Apr 2026 10:45:57 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    response = XmlResponse(
        url="https://www.ft.com/rss/home/international",
        request=Request(url="https://www.ft.com/rss/home/international"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_rss(response))
    assert len(items) == 1
    assert items[0]["source_metadata"]["rollout"] == "poc_only"


def test_feed_scope_filters_default_vs_poc_rollout():
    fallback_feeds = [
        {
            "url": "https://example.com/default.xml",
            "name": "default_feed",
            "priority": 1,
            "freshness_sla_hours": 24,
            "rollout_state": "default",
        },
        {
            "url": "https://example.com/poc.xml",
            "name": "poc_feed",
            "priority": 2,
            "freshness_sla_hours": 24,
            "rollout_state": "poc",
        },
    ]

    default_feeds = resolve_feed_profiles("example_source", fallback_feeds, feed_scope="default")
    poc_feeds = resolve_feed_profiles("example_source", fallback_feeds, feed_scope="poc")
    canary_feeds = resolve_feed_profiles("example_source", fallback_feeds, feed_scope="canary")

    assert [feed["name"] for feed in default_feeds] == ["default_feed"]
    assert canary_feeds == []
    assert [feed["name"] for feed in poc_feeds] == ["poc_feed"]
