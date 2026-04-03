from news_crawler.pipelines import GeoExtractionPipeline
from news_crawler.utils.enhanced_geo_processor import EnhancedGeoProcessor
from news_crawler.utils.geo_text_builder import build_geo_search_text


class _DummySpider:
    name = "test_spider"


def test_build_geo_search_text_keeps_location_rich_sentences():
    text = build_geo_search_text(
        "Storm batters southern California",
        "Officials warned more evacuations may follow.",
        (
            "The storm intensified overnight. "
            "LOS ANGELES, California - Authorities said mudslides threatened hillside neighborhoods in Pasadena. "
            "Crews in Altadena were also placed on alert."
        ),
    )

    assert "LOS ANGELES, California" in text
    assert "Pasadena" in text


def test_processor_prefers_city_matching_admin1_hint():
    processor = EnhancedGeoProcessor()

    entities = processor.extract_candidates_from_text(
        "Los Angeles County and Pasadena were hit as California crews responded.",
        country_hint="US",
        admin1_hints=["CA", "California"],
        max_entities=8,
    )

    pasadena = next(e for e in entities if e.get("city_name") == "Pasadena")
    assert pasadena["country_code"] == "US"
    assert pasadena["admin1_code"] == "CA"


def test_geo_pipeline_extracts_admin1_and_city_from_richer_text():
    pipeline = GeoExtractionPipeline()
    item = {
        "title": "Wildfire spreads across Los Angeles County as crews battle strong winds",
        "summary": "Officials in California said evacuations expanded overnight.",
        "content": (
            "The fire spread overnight after winds strengthened. "
            "LOS ANGELES, California - Firefighters said the blaze spread near Pasadena and Altadena as evacuations widened."
        ),
    }

    result = pipeline.process_item(item, _DummySpider())
    geo_entities = result.get("geo_entities") or []

    assert any(e.get("type") == "province" and e.get("admin1_code") == "CA" for e in geo_entities)
    assert any(e.get("type") == "city" and e.get("city_name") == "Pasadena" and e.get("admin1_code") == "CA" for e in geo_entities)
    assert result.get("region_tags") == ["US"]
