import json

from scrapy.http import Request, TextResponse

from news_crawler.spiders.events.disaster_gdacs import GDACSDisasterSpider
from news_crawler.spiders.events.earthquake_usgs import USGSEarthquakeSpider
from news_crawler.spiders.events.eonet_events import EONETEventsSpider


def test_usgs_spider_parses_structured_event_item():
    spider = USGSEarthquakeSpider(max_items=2)
    body = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "us7000test1",
                    "properties": {
                        "title": "M 5.1 - 12 km NE of Hualien City, Taiwan",
                        "place": "12 km NE of Hualien City, Taiwan",
                        "time": 1775428800000,
                        "updated": 1775429400000,
                        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000test1",
                        "detail": "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000test1",
                        "alert": "yellow",
                        "sig": 421,
                        "mag": 5.1,
                    },
                    "geometry": {"type": "Point", "coordinates": [121.6, 24.0, 10.2]},
                }
            ],
        }
    )
    response = TextResponse(
        url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
        request=Request(url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    item = items[0]
    assert item["source_class"] == "event"
    assert item["external_id"] == "us7000test1"
    assert item["event_status"] == "closed"
    assert item["source_updated_at"] == 1775429400000
    assert item["geo"] == "point"
    assert item["geom_type"] == "Point"
    assert item["display_geo"] == {"type": "Point", "coordinates": [121.6, 24.0]}
    assert item["geo_entities"][0]["precision_level"] == "POINT"
    assert item["region_tags"] == ["TW"]


def test_eonet_spider_parses_open_event_item():
    spider = EONETEventsSpider(max_items=2)
    body = json.dumps(
        {
            "title": "EONET Events",
            "description": "test",
            "link": "https://eonet.gsfc.nasa.gov/api/v3/events",
            "events": [
                {
                    "id": "EONET_1234",
                    "title": "Wildfire near Alberta, Canada",
                    "description": "Active wildfire monitored in Alberta, Canada.",
                    "link": "https://eonet.gsfc.nasa.gov/api/v3/events/EONET_1234",
                    "closed": None,
                    "categories": [{"id": "wildfires", "title": "Wildfires"}],
                    "sources": [{"id": "InciWeb", "url": "https://inciweb.wildfire.gov"}],
                    "geometry": [
                        {
                            "date": "2026-04-06T00:00:00Z",
                            "type": "Point",
                            "coordinates": [-113.4, 53.5],
                            "magnitudeValue": 2.0,
                            "magnitudeUnit": "MW",
                        }
                    ],
                }
            ],
        }
    )
    response = TextResponse(
        url="https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=7",
        request=Request(url="https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=7"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert len(items) == 1
    item = items[0]
    assert item["source_class"] == "event"
    assert item["external_id"] == "EONET_1234"
    assert item["event_status"] == "open"
    assert item["closed_at"] is None
    assert item["event_time"] == "2026-04-06T00:00:00Z"
    assert item["raw_geometry"]["type"] == "GeometryCollection"
    assert item["display_geo"] == {"type": "Point", "coordinates": [-113.4, 53.5]}
    assert item["geo_entities"][0]["precision_level"] == "POINT"
    assert item["region_tags"] == ["CA"]
    assert "wildfires" in item["tags"]


def test_usgs_spider_prefers_us_state_abbreviation_over_country_alias():
    spider = USGSEarthquakeSpider(max_items=1)
    feature = {
        "type": "Feature",
        "id": "nc75339732",
        "properties": {
            "title": "M 1.3 - 3 km NW of The Geysers, CA",
            "place": "3 km NW of The Geysers, CA",
            "time": 1775462541710,
            "updated": 1775462639372,
            "url": "https://earthquake.usgs.gov/earthquakes/eventpage/nc75339732",
            "detail": "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=nc75339732",
            "sig": 200,
            "mag": 1.3,
        },
        "geometry": {"type": "Point", "coordinates": [-122.78099822998, 38.7999992370605, 1.2]},
    }

    item = spider._build_item(feature)
    assert item is not None
    assert item["region_tags"][0] == "US"
    assert item["geo_entities"][0]["country_code"] == "US"
    assert any(entity.get("admin1_code") == "CA" for entity in item["geo_entities"])


def test_gdacs_spider_parses_alert_enrichment_item():
    spider = GDACSDisasterSpider(max_items=2)
    spider._checkpoint_updated_at = None
    spider._checkpoint_external_id = ""
    body = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "bbox": [138.7, 35.6, 138.7, 35.6],
                    "geometry": {"type": "Point", "coordinates": [138.7, 35.6]},
                    "properties": {
                        "eventtype": "EQ",
                        "eventid": "1102983",
                        "eventname": "Earthquake in Japan",
                        "country": "Japan",
                        "iso3": "JPN",
                        "description": "Strong shaking reported in central Japan.",
                        "datemodified": "2026-04-06T08:05:00Z",
                        "fromdate": "2026-04-06T07:55:00Z",
                        "todate": "2026-04-06T12:00:00Z",
                        "iscurrent": True,
                        "alertlevel": "Red",
                        "alertscore": 2.3,
                        "episodealertlevel": "Red",
                        "episodealertscore": 2.0,
                        "source": "USGS",
                        "sourceid": "usgs",
                        "url": "https://www.gdacs.org/report.aspx?eventid=1102983",
                    },
                }
            ],
        }
    )
    response = TextResponse(
        url="https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH?eventtype=EQ&page=1&format=geojson",
        request=Request(url="https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH?eventtype=EQ&page=1&format=geojson"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = [item for item in spider.parse_feed(response) if not isinstance(item, Request)]
    assert len(items) == 1
    item = items[0]
    assert item["source_class"] == "event"
    assert item["external_id"] == "EQ:1102983"
    assert item["event_status"] == "open"
    assert item["geo"] == "point"
    assert item["geom_type"] == "Point"
    assert item["display_geo"] == {"type": "Point", "coordinates": [138.7, 35.6]}
    assert item["bbox"] == [138.7, 35.6, 138.7, 35.6]
    assert item["source_metadata"]["role"] == "alert_enrichment"
    assert item["source_metadata"]["alertlevel"] == "red"
    assert "earthquake" in item["tags"]
    assert "gdacs" in item["tags"]
    assert item["region_tags"] == ["JP"]


def test_gdacs_spider_skips_checkpointed_realtime_items():
    spider = GDACSDisasterSpider(max_items=2)
    spider._checkpoint_updated_at = spider._coerce_datetime("2026-04-06T08:05:00")
    spider._checkpoint_external_id = "EQ:1102983"
    body = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "bbox": [138.7, 35.6, 138.7, 35.6],
                    "geometry": {"type": "Point", "coordinates": [138.7, 35.6]},
                    "properties": {
                        "eventtype": "EQ",
                        "eventid": "1102983",
                        "eventname": "Earthquake in Japan",
                        "country": "Japan",
                        "description": "Strong shaking reported in central Japan.",
                        "datemodified": "2026-04-06T08:05:00Z",
                        "fromdate": "2026-04-06T07:55:00Z",
                        "iscurrent": True,
                        "alertlevel": "Red",
                        "alertscore": 2.3,
                        "url": "https://www.gdacs.org/report.aspx?eventid=1102983",
                    },
                }
            ],
        }
    )
    response = TextResponse(
        url="https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH?eventtype=EQ&page=1&format=geojson",
        request=Request(url="https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH?eventtype=EQ&page=1&format=geojson"),
        body=body.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_feed(response))
    assert items == []
