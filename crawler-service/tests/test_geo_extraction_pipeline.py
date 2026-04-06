from news_crawler.pipelines import GeoExtractionPipeline
from news_crawler.utils.enhanced_geo_processor import EnhancedGeoProcessor
from news_crawler.utils.geo_dictionary_loader import GeoDictionaryLoader
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


def test_admin1_dictionary_now_covers_top_50_countries():
    loader = GeoDictionaryLoader()
    loader.load_all()

    stats = loader.get_stats()

    assert stats["admin1_countries"] >= 50
    assert loader.find_admin1("Ontario", country_code="CA") is not None
    assert loader.find_admin1("Bavaria", country_code="DE") is not None
    assert loader.find_admin1("Maharashtra", country_code="IN") is not None
    assert loader.find_admin1("New South Wales", country_code="AU") is not None


def test_processor_extracts_newly_added_admin1_regions():
    processor = EnhancedGeoProcessor()

    entities = processor.extract_candidates_from_text(
        "Factories in Bavaria and Ontario are expanding while Maharashtra officials review chip subsidies.",
        max_entities=10,
    )

    geo_keys = {entity.get("geo_key") for entity in entities}
    admin1_names = {entity.get("admin1_name") for entity in entities if entity.get("type") == "province"}

    assert "DE.02" in geo_keys
    assert "CA.08" in geo_keys
    assert "IN.16" in geo_keys
    assert {"巴伐利亚州", "安大略", "马哈拉施特拉邦"} <= admin1_names


def test_loader_matches_common_chinese_admin1_aliases():
    loader = GeoDictionaryLoader()
    loader.load_all()

    assert loader.find_admin1("巴伐利亚", country_code="DE") is not None
    assert loader.find_admin1("安大略省", country_code="CA") is not None
    assert loader.find_admin1("新南威尔士州", country_code="AU") is not None
    assert loader.find_admin1("东京都", country_code="JP") is not None
