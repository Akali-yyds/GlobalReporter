"""
API tests for news endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test health endpoint returns OK."""
        # Import here to avoid module-level database initialization
        from app.database import engine, SessionLocal
        from app.models import Base, CrawlJob, NewsSource
        from app.main import app
        from app.database import get_db

        # Create in-memory database for this test
        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}

        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)

    def test_root_endpoint(self):
        """Test root endpoint returns app info."""
        from app.main import app

        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "GlobalReporter API"
            assert data["version"] == "1.0.0"


class TestNewsEndpoints:
    """Tests for news API endpoints."""

    def test_get_hot_news_empty(self):
        """Test getting hot news when database is empty."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from app.api import news as news_api
        from app.models import Base
        from app.main import app
        from app.database import get_db

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        with TestClient(app) as client:
            response = client.get("/api/news/hot")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] == 0

        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)

    def test_ingest_structured_geo_entities_and_get_event_detail(self):
        from app.models import Base, NewsEvent, EventGeoMapping, GeoEntity
        from app.main import app
        from app.database import get_db

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        payload = {
            "title": "Canada officials in London discuss manufacturing",
            "summary": "Ontario leaders met investors in London.",
            "content": "Canada signaled support for factories near London, Ontario.",
            "url": "https://example.com/articles/canada-london-manufacturing",
            "source_name": "Example News",
            "source_code": "example",
            "source_url": "https://example.com",
            "language": "en",
            "country": "CA",
            "category": "business",
            "tags": ["ai", "chip"],
            "heat_score": 42,
            "hash": "geo-api-test-hash-0001",
            "region_tags": ["CA"],
            "geo_entities": [
                {
                    "name": "London",
                    "geo_key": "CA:6058560",
                    "type": "city",
                    "confidence": 0.97,
                    "country_code": "CA",
                    "country_name": "Canada",
                    "admin1_code": "08",
                    "admin1_name": "Ontario",
                    "city_name": "London",
                    "precision_level": "CITY",
                    "display_mode": "POINT",
                    "geojson_key": "CA:6058560",
                    "lat": 42.98339,
                    "lng": -81.23304,
                    "matched_text": "London",
                    "source_text_position": "title",
                    "relevance_score": 0.97,
                    "is_primary": True,
                },
                {
                    "name": "Canada",
                    "geo_key": "CA",
                    "type": "country",
                    "confidence": 0.91,
                    "country_code": "CA",
                    "country_name": "Canada",
                    "precision_level": "COUNTRY",
                    "display_mode": "POLYGON",
                    "geojson_key": "CA",
                    "lat": 45.41117,
                    "lng": -75.69812,
                    "matched_text": "Canada",
                    "source_text_position": "title",
                    "relevance_score": 0.91,
                    "is_primary": False,
                },
            ],
        }

        try:
            with TestClient(app) as client:
                ingest_response = client.post("/api/news/ingest", json=payload)
                assert ingest_response.status_code == 200
                ingest_data = ingest_response.json()
                assert ingest_data["ok"] is True
                assert ingest_data["created_articles"] == 1
                assert ingest_data["events_touched"] == 1

                db = TestSessionLocal()
                try:
                    event = db.query(NewsEvent).filter(NewsEvent.title == payload["title"]).first()
                    assert event is not None
                    assert event.main_country == "CA"
                    assert event.event_level == "city"
                    assert event.tags == ["ai", "chip"]

                    mappings = db.query(EventGeoMapping).filter(EventGeoMapping.event_id == event.id).all()
                    assert len(mappings) == 2
                    primary_mapping = next((m for m in mappings if m.is_primary), None)
                    assert primary_mapping is not None
                    assert primary_mapping.geo_key == "CA:6058560"
                    assert primary_mapping.matched_text == "London"

                    geo_records = db.query(GeoEntity).all()
                    assert len(geo_records) == 2
                finally:
                    db.close()

                detail_response = client.get(f"/api/news/events/{event.id}")
                assert detail_response.status_code == 200
                detail_data = detail_response.json()
                assert detail_data["main_country"] == "CA"
                assert detail_data["event_level"] == "city"
                assert detail_data["tags"] == ["ai", "chip"]
                assert len(detail_data["geo_mappings"]) == 2

                primary_geo = next((g for g in detail_data["geo_mappings"] if g["is_primary"]), None)
                assert primary_geo is not None
                assert primary_geo["geo_key"] == "CA:6058560"
                assert primary_geo["geo_type"] == "city"
                assert primary_geo["display_type"] == "point"
                assert primary_geo["geo_name"] == "London"
                assert primary_geo["matched_text"] == "London"
                assert primary_geo["source_text_position"] == "title"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_get_hot_news_can_filter_by_tag(self):
        from app.models import Base, CrawlJob, NewsSource
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        payloads = [
            {
                "title": "OpenAI launches new model",
                "summary": "AI systems expand rapidly",
                "content": "OpenAI and Nvidia announced infrastructure updates.",
                "url": "https://example.com/ai-1",
                "source_name": "Example News",
                "source_code": "example",
                "source_url": "https://example.com",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["ai", "chip"],
                "heat_score": 80,
                "hash": "tag-filter-hash-ai-1",
            },
            {
                "title": "Flooding worsens after storm",
                "summary": "Emergency teams were dispatched",
                "content": "Flood waters rose after the storm.",
                "url": "https://example.com/disaster-1",
                "source_name": "Example News",
                "source_code": "example",
                "source_url": "https://example.com",
                "language": "en",
                "country": "US",
                "category": "disaster",
                "tags": ["disaster"],
                "heat_score": 60,
                "hash": "tag-filter-hash-disaster-1",
            },
        ]

        try:
            with TestClient(app) as client:
                for payload in payloads:
                    response = client.post("/api/news/ingest", json=payload)
                    assert response.status_code == 200

                all_response = client.get("/api/news/hot")
                assert all_response.status_code == 200
                assert all_response.json()["total"] == 2

                ai_response = client.get("/api/news/hot", params={"tag": "ai"})
                assert ai_response.status_code == 200
                ai_data = ai_response.json()
                assert ai_data["total"] == 1
                assert ai_data["items"][0]["title"] == "OpenAI launches new model"
                assert "ai" in ai_data["items"][0]["tags"]

                disaster_response = client.get("/api/news/hot", params={"tag": "disaster"})
                assert disaster_response.status_code == 200
                disaster_data = disaster_response.json()
                assert disaster_data["total"] == 1
                assert disaster_data["items"][0]["title"] == "Flooding worsens after storm"
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_get_hot_news_can_filter_by_multiple_tags(self):
        from app.models import Base
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        payloads = [
            {
                "title": "OpenAI launches new model",
                "summary": "AI systems expand rapidly",
                "content": "OpenAI and Nvidia announced infrastructure updates.",
                "url": "https://example.com/ai-2",
                "source_name": "Example News",
                "source_code": "example",
                "source_url": "https://example.com",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["ai", "chip"],
                "heat_score": 80,
                "hash": "tag-filter-hash-ai-2",
            },
            {
                "title": "Security team responds to breach",
                "summary": "Incident response expanded overnight",
                "content": "Cybersecurity teams responded to a major breach.",
                "url": "https://example.com/cyber-1",
                "source_name": "Example News",
                "source_code": "example",
                "source_url": "https://example.com",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["cybersecurity"],
                "heat_score": 70,
                "hash": "tag-filter-hash-cyber-1",
            },
            {
                "title": "Flooding worsens after storm",
                "summary": "Emergency teams were dispatched",
                "content": "Flood waters rose after the storm.",
                "url": "https://example.com/disaster-2",
                "source_name": "Example News",
                "source_code": "example",
                "source_url": "https://example.com",
                "language": "en",
                "country": "US",
                "category": "disaster",
                "tags": ["disaster"],
                "heat_score": 60,
                "hash": "tag-filter-hash-disaster-2",
            },
        ]

        try:
            with TestClient(app) as client:
                for payload in payloads:
                    response = client.post("/api/news/ingest", json=payload)
                    assert response.status_code == 200

                any_response = client.get("/api/news/hot", params={"tags_any": "ai,disaster"})
                assert any_response.status_code == 200
                any_data = any_response.json()
                assert any_data["total"] == 2
                assert {item["title"] for item in any_data["items"]} == {
                    "OpenAI launches new model",
                    "Flooding worsens after storm",
                }

                all_response = client.get("/api/news/hot", params={"tags_all": "ai,chip"})
                assert all_response.status_code == 200
                all_data = all_response.json()
                assert all_data["total"] == 1
                assert all_data["items"][0]["title"] == "OpenAI launches new model"
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_similar_titles_cluster_into_single_event(self):
        from app.models import Base
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        payloads = [
            {
                "title": "OpenAI launches new AI model for developers",
                "summary": "New developer features are rolling out.",
                "content": "OpenAI introduced a new model with improved reasoning for developers.",
                "url": "https://example.com/openai-dev-model-1",
                "source_name": "Tech Wire",
                "source_code": "techwire",
                "source_url": "https://example.com",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["ai"],
                "heat_score": 68,
                "hash": "cluster-hash-openai-1",
            },
            {
                "title": "OpenAI unveils new AI model for developers",
                "summary": "The release targets coding and workflow automation.",
                "content": "The company unveiled a model aimed at developer tooling.",
                "url": "https://another.example.com/openai-dev-model-2",
                "source_name": "Global Tech",
                "source_code": "globaltech",
                "source_url": "https://another.example.com",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["ai"],
                "heat_score": 52,
                "hash": "cluster-hash-openai-2",
            },
        ]

        try:
            with TestClient(app) as client:
                for payload in payloads:
                    response = client.post("/api/news/ingest", json=payload)
                    assert response.status_code == 200

                response = client.get("/api/news/hot")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                event = data["items"][0]
                assert event["article_count"] == 2
                assert "ai" in event["tags"]
                assert event["heat_score"] > 90
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_distinct_titles_remain_separate_events(self):
        from app.models import Base
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        payloads = [
            {
                "title": "OpenAI launches new AI model for developers",
                "summary": "New developer features are rolling out.",
                "content": "OpenAI introduced a new model with improved reasoning for developers.",
                "url": "https://example.com/openai-separate-1",
                "source_name": "Tech Wire",
                "source_code": "techwire",
                "source_url": "https://example.com",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["ai"],
                "heat_score": 68,
                "hash": "cluster-separate-openai-1",
            },
            {
                "title": "Flooding worsens after tropical storm",
                "summary": "Emergency teams expanded evacuations.",
                "content": "Rescue operations continued after severe flooding.",
                "url": "https://example.com/flood-separate-1",
                "source_name": "Climate Desk",
                "source_code": "climatedesk",
                "source_url": "https://climate.example.com",
                "language": "en",
                "country": "US",
                "category": "disaster",
                "tags": ["disaster"],
                "heat_score": 70,
                "hash": "cluster-separate-flood-1",
            },
        ]

        try:
            with TestClient(app) as client:
                for payload in payloads:
                    response = client.post("/api/news/ingest", json=payload)
                    assert response.status_code == 200

                response = client.get("/api/news/hot")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 2
                titles = {item["title"] for item in data["items"]}
                assert "OpenAI launches new AI model for developers" in titles
                assert "Flooding worsens after tropical storm" in titles
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_source_tier_is_persisted_and_filterable(self):
        from app.models import Base, NewsEvent, NewsSource
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        payloads = [
            {
                "title": "NASA publishes new moon mission update",
                "summary": "Mission plans were updated overnight.",
                "content": "NASA published an official update on its moon mission timeline.",
                "url": "https://www.nasa.gov/mission-update",
                "source_name": "NASA Official",
                "source_code": "nasa_official",
                "source_url": "https://www.nasa.gov/newsroom",
                "language": "en",
                "country": "US",
                "category": "science",
                "tags": ["space", "science"],
                "heat_score": 64,
                "hash": "source-tier-official-1",
            },
            {
                "title": "BBC reports on energy market pressure",
                "summary": "Energy markets remain volatile.",
                "content": "BBC coverage focused on long-running pressure in energy markets.",
                "url": "https://www.bbc.com/news/business-energy",
                "source_name": "BBC News",
                "source_code": "bbc",
                "source_url": "https://www.bbc.com",
                "language": "en",
                "country": "GB",
                "category": "business",
                "tags": ["economy"],
                "heat_score": 58,
                "hash": "source-tier-authoritative-1",
            },
        ]

        try:
            with TestClient(app) as client:
                for payload in payloads:
                    response = client.post("/api/news/ingest", json=payload)
                    assert response.status_code == 200

                db = TestSessionLocal()
                try:
                    nasa_source = db.query(NewsSource).filter(NewsSource.code == "nasa_official").first()
                    assert nasa_source is not None
                    assert nasa_source.source_tier == "official"

                    nasa_event = db.query(NewsEvent).filter(NewsEvent.title.like("NASA publishes%")).first()
                    assert nasa_event is not None
                    assert nasa_event.source_tier == "official"
                finally:
                    db.close()

                hot_response = client.get("/api/news/hot", params={"source_tier": "official"})
                assert hot_response.status_code == 200
                hot_data = hot_response.json()
                assert hot_data["total"] == 1
                assert hot_data["items"][0]["title"] == "NASA publishes new moon mission update"

                sources_response = client.get("/api/sources", params={"tier": "official"})
                assert sources_response.status_code == 200
                sources_data = sources_response.json()
                assert len(sources_data) == 1
                assert sources_data[0]["code"] == "nasa_official"
                assert sources_data[0]["source_tier"] == "official"
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_source_tier_influences_heat_score(self):
        from app.models import Base
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        payloads = [
            {
                "title": "Google issues official AI safety update",
                "summary": "An official update was published today.",
                "content": "Google published an official safety update on AI systems.",
                "url": "https://blog.google/technology/ai/safety-update",
                "source_name": "Google Official Blog",
                "source_code": "google_official",
                "source_url": "https://blog.google",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["ai", "policy"],
                "heat_score": 40,
                "hash": "source-tier-heat-official-1",
            },
            {
                "title": "Viral post discusses AI safety update",
                "summary": "The topic spread quickly on social media.",
                "content": "A social media trend discussed the same theme.",
                "url": "https://x.com/example/status/1",
                "source_name": "X Hot",
                "source_code": "x_hot",
                "source_url": "https://x.com/explore",
                "language": "en",
                "country": "US",
                "category": "social",
                "tags": ["ai"],
                "heat_score": 40,
                "hash": "source-tier-heat-social-1",
            },
        ]

        try:
            with TestClient(app) as client:
                for payload in payloads:
                    response = client.post("/api/news/ingest", json=payload)
                    assert response.status_code == 200

                response = client.get("/api/news/hot")
                assert response.status_code == 200
                items = response.json()["items"]

                official_event = next(item for item in items if item["title"] == "Google issues official AI safety update")
                social_event = next(item for item in items if item["title"] == "Viral post discusses AI safety update")

                assert official_event["source_tier"] == "official"
                assert social_event["source_tier"] == "social"
                assert official_event["heat_score"] > social_event["heat_score"]
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_event_clustering_prefers_geo_overlap(self):
        from datetime import datetime, timedelta

        from app.models import Base, EventArticle, EventGeoMapping, GeoEntity, NewsArticle, NewsEvent, NewsSource
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        tokyo_geo = {
            "name": "Tokyo",
            "geo_key": "JP:13",
            "type": "admin1",
            "country_code": "JP",
            "country_name": "Japan",
            "admin1_code": "13",
            "admin1_name": "Tokyo",
            "precision_level": "ADMIN1",
            "display_mode": "POLYGON",
            "geojson_key": "JP:13",
            "confidence": 0.98,
            "relevance_score": 0.98,
            "is_primary": True,
        }
        osaka_geo = {
            "name": "Osaka",
            "geo_key": "JP:27",
            "type": "admin1",
            "country_code": "JP",
            "country_name": "Japan",
            "admin1_code": "27",
            "admin1_name": "Osaka",
            "precision_level": "ADMIN1",
            "display_mode": "POLYGON",
            "geojson_key": "JP:27",
            "confidence": 0.98,
            "relevance_score": 0.98,
            "is_primary": True,
        }

        db = TestSessionLocal()
        now = datetime.utcnow()
        try:
            nhk_source = NewsSource(
                name="NHK World",
                code="nhk",
                base_url="https://www3.nhk.or.jp/nhkworld/",
                country="JP",
                language="en",
                category="news",
                source_tier="authoritative",
                is_active=True,
            )
            db.add(nhk_source)
            db.flush()

            tokyo_event = NewsEvent(
                title="Earthquake disrupts rail service in Tokyo",
                summary="Tokyo commuters faced severe delays.",
                main_country="JP",
                event_level="admin1",
                heat_score=72,
                article_count=1,
                category="disaster",
                tags=["disaster", "earthquake"],
                source_tier="authoritative",
                title_hash="tokyo-event-hash",
                first_seen_at=now - timedelta(hours=4),
                last_seen_at=now - timedelta(hours=3),
            )
            osaka_event = NewsEvent(
                title="Subway service in Osaka slows after earthquake",
                summary="Osaka commuters faced severe delays.",
                main_country="JP",
                event_level="admin1",
                heat_score=71,
                article_count=1,
                category="disaster",
                tags=["disaster", "earthquake"],
                source_tier="authoritative",
                title_hash="osaka-event-hash",
                first_seen_at=now - timedelta(hours=2),
                last_seen_at=now - timedelta(hours=1),
            )
            db.add_all([tokyo_event, osaka_event])
            db.flush()

            tokyo_article = NewsArticle(
                title=tokyo_event.title,
                summary=tokyo_event.summary,
                content="A strong earthquake disrupted transport in Tokyo.",
                article_url="https://example.com/tokyo-quake-1",
                source_id=nhk_source.id,
                source_name=nhk_source.name,
                source_code=nhk_source.code,
                source_url=nhk_source.base_url,
                publish_time=now - timedelta(hours=4),
                crawl_time=now - timedelta(hours=4),
                heat_score=72,
                category="disaster",
                language="en",
                country_tags=["JP"],
                city_tags=[],
                region_tags=["JP"],
                tags=["disaster", "earthquake"],
                hash="geo-overlap-seeded-tokyo",
            )
            osaka_article = NewsArticle(
                title=osaka_event.title,
                summary=osaka_event.summary,
                content="A strong earthquake disrupted transport in Osaka.",
                article_url="https://example.com/osaka-quake-1",
                source_id=nhk_source.id,
                source_name=nhk_source.name,
                source_code=nhk_source.code,
                source_url=nhk_source.base_url,
                publish_time=now - timedelta(hours=2),
                crawl_time=now - timedelta(hours=2),
                heat_score=71,
                category="disaster",
                language="en",
                country_tags=["JP"],
                city_tags=[],
                region_tags=["JP"],
                tags=["disaster", "earthquake"],
                hash="geo-overlap-seeded-osaka",
            )
            db.add_all([tokyo_article, osaka_article])
            db.flush()

            db.add_all(
                [
                    EventArticle(event_id=tokyo_event.id, article_id=tokyo_article.id, is_primary=True),
                    EventArticle(event_id=osaka_event.id, article_id=osaka_article.id, is_primary=True),
                ]
            )

            tokyo_geo_record = GeoEntity(
                name="Tokyo",
                geo_key="JP:13",
                country_code="JP",
                country_name="Japan",
                admin1_code="13",
                admin1_name="Tokyo",
                precision_level="ADMIN1",
                display_mode="POLYGON",
                geojson_key="JP:13",
                is_active=True,
            )
            osaka_geo_record = GeoEntity(
                name="Osaka",
                geo_key="JP:27",
                country_code="JP",
                country_name="Japan",
                admin1_code="27",
                admin1_name="Osaka",
                precision_level="ADMIN1",
                display_mode="POLYGON",
                geojson_key="JP:27",
                is_active=True,
            )
            db.add_all([tokyo_geo_record, osaka_geo_record])
            db.flush()

            db.add_all(
                [
                    EventGeoMapping(
                        event_id=tokyo_event.id,
                        geo_id=tokyo_geo_record.id,
                        geo_key="JP:13",
                        confidence=0.98,
                        relevance_score=0.98,
                        is_primary=True,
                    ),
                    EventGeoMapping(
                        event_id=osaka_event.id,
                        geo_id=osaka_geo_record.id,
                        geo_key="JP:27",
                        confidence=0.98,
                        relevance_score=0.98,
                        is_primary=True,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        payload = {
            "title": "Earthquake disrupts rail service in Tokyo again",
            "summary": "Tokyo transport agencies were still recovering after the earthquake.",
            "content": "Tokyo officials warned of continued rail disruption after the earthquake.",
            "url": "https://example.com/tokyo-quake-2",
            "source_name": "BBC News",
            "source_code": "bbc",
            "source_url": "https://www.bbc.com",
            "language": "en",
            "country": "JP",
            "category": "disaster",
            "tags": ["disaster", "earthquake"],
            "heat_score": 68,
            "hash": "geo-overlap-tokyo-2",
            "region_tags": ["JP"],
            "geo_entities": [tokyo_geo],
        }

        try:
            with TestClient(app) as client:
                response = client.post("/api/news/ingest", json=payload)
                assert response.status_code == 200

                db = TestSessionLocal()
                try:
                    tokyo_event = db.query(NewsEvent).filter(NewsEvent.title == "Earthquake disrupts rail service in Tokyo").first()
                    osaka_event = db.query(NewsEvent).filter(NewsEvent.title == "Subway service in Osaka slows after earthquake").first()

                    assert tokyo_event is not None
                    assert osaka_event is not None
                    assert tokyo_event.article_count == 2
                    assert osaka_event.article_count == 1
                finally:
                    db.close()

                response = client.get("/api/news/hot", params={"tag": "earthquake"})
                assert response.status_code == 200
                assert response.json()["total"] == 2
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_source_analytics_groups_by_tier(self):
        from datetime import datetime, timedelta

        from app.models import Base, CrawlJob, NewsSource
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()
        now = datetime.utcnow()

        payloads = [
            {
                "title": "NASA shares new launch readiness update",
                "summary": "Launch officials confirmed the revised plan.",
                "content": "NASA published a fresh mission status note.",
                "url": "https://www.nasa.gov/launch-readiness",
                "source_name": "NASA Official",
                "source_code": "nasa_official",
                "source_url": "https://www.nasa.gov/newsroom",
                "language": "en",
                "country": "US",
                "category": "science",
                "tags": ["space"],
                "heat_score": 66,
                "hash": "source-analytics-official-1",
                "published_at": (now - timedelta(hours=2)).isoformat(),
            },
            {
                "title": "OpenAI Codex publishes new release candidate",
                "summary": "A new release candidate is available for testing.",
                "content": "The repository release notes announced a new Codex build.",
                "url": "https://github.com/openai/codex/releases/tag/v1.2.3",
                "source_name": "OpenAI Codex Releases",
                "source_code": "github_openai_releases",
                "source_url": "https://github.com/openai/codex/releases",
                "language": "en",
                "country": "US",
                "category": "technology",
                "tags": ["github", "release"],
                "heat_score": 58,
                "hash": "source-analytics-community-1",
                "published_at": (now - timedelta(hours=30)).isoformat(),
            },
            {
                "title": "Bilibili trend discusses AI hardware costs",
                "summary": "Creators debated inference cost and chip demand.",
                "content": "A social trend focused on AI hardware economics.",
                "url": "https://www.bilibili.com/video/BV1-test-social",
                "source_name": "Bilibili Hot",
                "source_code": "bilibili_hot",
                "source_url": "https://www.bilibili.com/",
                "language": "zh",
                "country": "CN",
                "category": "social",
                "tags": ["ai", "chip"],
                "heat_score": 52,
                "hash": "source-analytics-social-1",
                "geo_entities": [
                    {
                        "name": "Shanghai",
                        "geo_key": "CN:31",
                        "type": "admin1",
                        "confidence": 0.94,
                        "country_code": "CN",
                        "country_name": "China",
                        "admin1_code": "31",
                        "admin1_name": "Shanghai",
                        "precision_level": "ADMIN1",
                        "display_mode": "POLYGON",
                        "geojson_key": "CN:31",
                        "matched_text": "Shanghai",
                        "source_text_position": "title",
                        "relevance_score": 0.94,
                        "is_primary": True,
                    }
                ],
            },
        ]

        try:
            with TestClient(app) as client:
                for payload in payloads:
                    response = client.post("/api/news/ingest", json=payload)
                    assert response.status_code == 200

                db = TestSessionLocal()
                try:
                    nasa_source = db.query(NewsSource).filter(NewsSource.code == "nasa_official").first()
                    community_source = db.query(NewsSource).filter(NewsSource.code == "github_openai_releases").first()
                    social_source = db.query(NewsSource).filter(NewsSource.code == "bilibili_hot").first()

                    db.add_all(
                        [
                            CrawlJob(
                                source_id=nasa_source.id,
                                spider_name="nasa_official",
                                status="completed",
                                items_crawled=2,
                                items_processed=2,
                                started_at=now - timedelta(hours=1),
                                finished_at=now - timedelta(minutes=50),
                            ),
                            CrawlJob(
                                source_id=community_source.id,
                                spider_name="github_openai_releases",
                                status="failed",
                                items_crawled=0,
                                items_processed=0,
                                error_message="GitHub feed unavailable",
                                started_at=now - timedelta(hours=3),
                                finished_at=now - timedelta(hours=2, minutes=58),
                            ),
                            CrawlJob(
                                source_id=social_source.id,
                                spider_name="bilibili_hot",
                                status="completed",
                                items_crawled=3,
                                items_processed=1,
                                started_at=now - timedelta(hours=2),
                                finished_at=now - timedelta(hours=1, minutes=56),
                            ),
                            CrawlJob(
                                source_id=social_source.id,
                                spider_name="bilibili_hot",
                                status="failed",
                                items_crawled=0,
                                items_processed=0,
                                error_message="Upstream response changed",
                                started_at=now - timedelta(hours=5),
                                finished_at=now - timedelta(hours=4, minutes=59),
                            ),
                        ]
                    )
                    db.commit()
                finally:
                    db.close()

                response = client.get("/api/sources/analytics", params={"since_hours": 72, "freshness_hours": 24})
                assert response.status_code == 200
                data = response.json()

                assert data["freshness_hours"] == 24
                tiers = {item["source_tier"]: item for item in data["tiers"]}
                assert tiers["official"]["source_count"] == 1
                assert tiers["official"]["event_count"] == 1
                assert tiers["official"]["recent_job_count"] == 1
                assert tiers["official"]["success_rate"] == 1.0
                assert tiers["official"]["publish_time_coverage"] == 1.0
                assert tiers["official"]["fresh_article_ratio"] == 1.0
                assert tiers["community"]["event_count"] == 1
                assert tiers["community"]["recent_job_count"] == 1
                assert tiers["community"]["success_rate"] == 0.0
                assert tiers["community"]["fresh_article_ratio"] == 0.0
                assert tiers["social"]["article_count"] == 1
                assert tiers["social"]["recent_job_count"] == 2
                assert tiers["social"]["successful_job_count"] == 1
                assert tiers["social"]["success_rate"] == 0.5
                assert tiers["social"]["region_yield_ratio"] == 1.0

                sources = {item["code"]: item for item in data["sources"]}
                assert sources["nasa_official"]["source_tier"] == "official"
                assert sources["github_openai_releases"]["source_tier"] == "community"
                assert sources["bilibili_hot"]["source_tier"] == "social"
                assert sources["nasa_official"]["event_count"] == 1
                assert sources["nasa_official"]["recent_job_count"] == 1
                assert sources["nasa_official"]["success_rate"] == 1.0
                assert sources["nasa_official"]["last_job_status"] == "completed"
                assert sources["nasa_official"]["last_success_at"] is not None
                assert sources["nasa_official"]["latest_publish_at"] is not None
                assert sources["github_openai_releases"]["publish_time_coverage"] == 1.0
                assert sources["github_openai_releases"]["fresh_article_ratio"] == 0.0
                assert sources["github_openai_releases"]["last_job_status"] == "failed"
                assert sources["github_openai_releases"]["last_error_message"] == "GitHub feed unavailable"
                assert sources["bilibili_hot"]["publish_time_coverage"] == 0.0
                assert sources["bilibili_hot"]["tag_coverage_ratio"] == 1.0
                assert sources["bilibili_hot"]["low_signal_ratio"] == 0.0
                assert sources["bilibili_hot"]["region_yield_ratio"] == 1.0
                assert sources["bilibili_hot"]["recent_job_count"] == 2
                assert sources["bilibili_hot"]["success_rate"] == 0.5
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_source_policy_overrides_ingest_defaults(self):
        from datetime import datetime

        from app.models import Base, NewsArticle, NewsEvent, NewsSource, SourcePolicy
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        db = TestSessionLocal()
        try:
            db.add(
                SourcePolicy(
                    source_code="openai_official",
                    source_class="lead",
                    enabled=True,
                    fetch_mode="poll_feed",
                    schedule_minutes=360,
                    freshness_sla_hours=168,
                    dedup_key_mode="canonical_url",
                    event_time_field_priority=["published_at"],
                    severity_mapping_rule=None,
                    geo_precision_rule="text_geo",
                    default_params_json={},
                    license_mode="official_public",
                    notes="test override",
                )
            )
            db.commit()
        finally:
            db.close()

        payload = {
            "title": "OpenAI acquires TBPN",
            "summary": "Acquisition expands the media and product ecosystem.",
            "content": "OpenAI announced the acquisition in an official newsroom update.",
            "url": "https://openai.com/news/openai-acquires-tbpn",
            "source_name": "OpenAI News",
            "source_code": "openai_official",
            "source_url": "https://openai.com/news/",
            "language": "en",
            "country": "US",
            "category": "official",
            "heat_score": 64,
            "hash": "policy-override-hash-openai",
            "published_at": datetime.utcnow().isoformat(),
        }

        try:
            with TestClient(app) as client:
                response = client.post("/api/news/ingest", json=payload)
                assert response.status_code == 200

                db = TestSessionLocal()
                try:
                    source = db.query(NewsSource).filter(NewsSource.code == "openai_official").first()
                    article = db.query(NewsArticle).filter(NewsArticle.hash == "policy-override-hash-openai").first()
                    event = db.query(NewsEvent).filter(NewsEvent.title == payload["title"]).first()

                    assert source is not None
                    assert source.source_class == "lead"
                    assert source.freshness_sla_hours == 168
                    assert source.license_mode == "official_public"

                    assert article is not None
                    assert article.source_class == "lead"
                    assert article.freshness_sla_hours == 168
                    assert article.license_mode == "official_public"

                    assert event is not None
                    assert event.source_class == "lead"
                    assert event.freshness_sla_hours == 168
                    assert event.license_mode == "official_public"
                finally:
                    db.close()

                policy_response = client.get("/api/sources/policies")
                assert policy_response.status_code == 200
                policies = policy_response.json()
                assert len(policies) == 1
                assert policies[0]["source_code"] == "openai_official"
                assert policies[0]["freshness_sla_hours"] == 168
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_event_source_ingest_is_idempotent_and_preserves_lifecycle(self):
        from datetime import datetime, timedelta

        from app.models import Base, NewsArticle, NewsEvent, SourcePolicy
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        db = TestSessionLocal()
        try:
            db.add(
                SourcePolicy(
                    source_code="eonet_events",
                    source_class="event",
                    enabled=True,
                    fetch_mode="poll_api",
                    schedule_minutes=60,
                    freshness_sla_hours=168,
                    dedup_key_mode="external_id",
                    event_time_field_priority=["event_time", "source_updated_at"],
                    severity_mapping_rule="eonet_category",
                    geo_precision_rule="geometry",
                    default_params_json={"realtime": {"status": "open", "category": ["wildfires"]}},
                    license_mode="event_feed",
                    notes="test event policy",
                )
            )
            db.commit()
        finally:
            db.close()

        first_seen = datetime.utcnow() - timedelta(days=3)
        refreshed = datetime.utcnow()
        payload = {
            "title": "Wildfire near Alberta, Canada",
            "summary": "Active wildfire monitored in Alberta, Canada.",
            "content": "Persistent wildfire activity continues in Alberta.",
            "url": "https://eonet.gsfc.nasa.gov/api/v3/events/EONET_1234",
            "source_name": "NASA EONET",
            "source_code": "eonet_events",
            "source_url": "https://eonet.gsfc.nasa.gov/api/v3/events",
            "source_class": "event",
            "language": "en",
            "country": "CA",
            "category": "disaster",
            "tags": ["wildfires", "natural_event"],
            "heat_score": 72,
            "hash": "eonet-hash-1",
            "external_id": "EONET_1234",
            "canonical_url": "https://eonet.gsfc.nasa.gov/api/v3/events/EONET_1234",
            "event_time": first_seen.isoformat(),
            "event_status": "open",
            "source_updated_at": first_seen.isoformat(),
            "geom_type": "Point",
            "raw_geometry": {
                "type": "GeometryCollection",
                "geometries": [
                    {
                        "date": first_seen.isoformat(),
                        "type": "Point",
                        "coordinates": [-113.4, 53.5],
                    }
                ],
            },
            "display_geo": {"type": "Point", "coordinates": [-113.4, 53.5]},
            "bbox": [-113.4, 53.5, -113.4, 53.5],
            "geo_entities": [
                {
                    "name": "Wildfire near Alberta, Canada",
                    "geo_key": "EONET:1234",
                    "type": "point",
                    "confidence": 0.98,
                    "country_code": "CA",
                    "country_name": "Canada",
                    "precision_level": "POINT",
                    "display_mode": "POINT",
                    "geojson_key": "EONET:1234",
                    "lat": 53.5,
                    "lng": -113.4,
                    "matched_text": "Alberta, Canada",
                    "source_text_position": "title",
                    "relevance_score": 0.98,
                    "is_primary": True,
                }
            ],
            "region_tags": ["CA"],
        }

        updated_payload = dict(payload)
        updated_payload.update(
            {
                "summary": "Authorities say the wildfire remains active.",
                "hash": "eonet-hash-2",
                "heat_score": 84,
                "event_status": "closed",
                "closed_at": refreshed.isoformat(),
                "source_updated_at": refreshed.isoformat(),
            }
        )

        try:
            with TestClient(app) as client:
                first_response = client.post("/api/news/ingest", json=payload)
                assert first_response.status_code == 200
                assert first_response.json()["created_articles"] == 1

                second_response = client.post("/api/news/ingest", json=updated_payload)
                assert second_response.status_code == 200
                assert second_response.json()["created_articles"] == 0
                assert second_response.json()["events_touched"] == 1

                db = TestSessionLocal()
                try:
                    articles = db.query(NewsArticle).filter(NewsArticle.source_code == "eonet_events").all()
                    events = db.query(NewsEvent).filter(NewsEvent.source_code == "eonet_events").all()
                    assert len(articles) == 1
                    assert len(events) == 1

                    event = events[0]
                    assert event.external_id == "EONET_1234"
                    assert event.event_status == "closed"
                    assert event.closed_at is not None
                    assert event.source_updated_at is not None
                    assert event.article_count == 1
                    assert event.geom_type == "Point"
                    assert event.raw_geometry is not None
                    assert event.display_geo == {"type": "Point", "coordinates": [-113.4, 53.5]}
                    assert event.bbox == [-113.4, 53.5, -113.4, 53.5]
                finally:
                    db.close()
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_gdacs_ingest_enriches_existing_primary_event_without_creating_duplicate(self):
        from app.models import Base, NewsArticle, NewsEvent
        from app.main import app
        from app.database import get_db
        from app.api import news as news_api

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        news_api._hot_news_cache.invalidate()

        usgs_payload = {
            "title": "M 5.6 - Offshore Taiwan",
            "summary": "Moderate earthquake detected offshore Taiwan.",
            "content": "USGS reported a moderate offshore Taiwan earthquake.",
            "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000tw1",
            "source_name": "USGS Earthquake Hazards",
            "source_code": "earthquake_usgs",
            "source_url": "https://earthquake.usgs.gov/earthquakes/feed/",
            "source_class": "event",
            "language": "en",
            "country": "TW",
            "category": "disaster",
            "tags": ["earthquake", "disaster", "seismic"],
            "heat_score": 70,
            "hash": "usgs-gdacs-primary-hash",
            "external_id": "us7000tw1",
            "canonical_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000tw1",
            "event_time": "2026-04-06T08:00:00",
            "source_updated_at": "2026-04-06T08:10:00",
            "event_status": "closed",
            "closed_at": "2026-04-06T08:00:00",
            "severity": 72,
            "confidence": 95,
            "geom_type": "Point",
            "raw_geometry": {"type": "Point", "coordinates": [121.6, 24.0]},
            "display_geo": {"type": "Point", "coordinates": [121.6, 24.0]},
            "bbox": [121.6, 24.0, 121.6, 24.0],
            "geo_entities": [
                {
                    "name": "Offshore Taiwan",
                    "geo_key": "USGS:us7000tw1",
                    "type": "point",
                    "confidence": 0.98,
                    "country_code": "TW",
                    "country_name": "Taiwan",
                    "precision_level": "POINT",
                    "display_mode": "POINT",
                    "geojson_key": "USGS:us7000tw1",
                    "lat": 24.0,
                    "lng": 121.6,
                    "matched_text": "Taiwan",
                    "source_text_position": "title",
                    "relevance_score": 0.98,
                    "is_primary": True,
                }
            ],
            "region_tags": ["TW"],
        }

        gdacs_payload = {
            "title": "RED Earthquake in Taiwan",
            "summary": "GDACS alert indicates potential humanitarian impact.",
            "content": "GDACS raised a red earthquake alert for Taiwan after strong shaking.",
            "url": "https://www.gdacs.org/report.aspx?eventid=1102983",
            "source_name": "GDACS Alerts",
            "source_code": "disaster_gdacs",
            "source_url": "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH",
            "source_class": "event",
            "language": "en",
            "country": "TW",
            "category": "disaster",
            "tags": ["earthquake", "disaster", "gdacs"],
            "heat_score": 88,
            "hash": "gdacs-enrichment-hash",
            "external_id": "EQ:1102983",
            "canonical_url": "https://www.gdacs.org/report.aspx?eventid=1102983",
            "event_time": "2026-04-06T07:55:00",
            "source_updated_at": "2026-04-06T08:15:00",
            "event_status": "open",
            "severity": 92,
            "confidence": 90,
            "geom_type": "Point",
            "raw_geometry": {"type": "Point", "coordinates": [121.62, 24.02]},
            "display_geo": {"type": "Point", "coordinates": [121.62, 24.02]},
            "bbox": [121.62, 24.02, 121.62, 24.02],
            "source_metadata": {
                "role": "alert_enrichment",
                "event_type": "EQ",
                "alertlevel": "red",
                "alertscore": 2.3,
            },
            "geo_entities": [
                {
                    "name": "Taiwan alert",
                    "geo_key": "GDACS:EQ:1102983",
                    "type": "point",
                    "confidence": 0.94,
                    "country_code": "TW",
                    "country_name": "Taiwan",
                    "precision_level": "POINT",
                    "display_mode": "POINT",
                    "geojson_key": "GDACS:EQ:1102983",
                    "lat": 24.02,
                    "lng": 121.62,
                    "matched_text": "Taiwan",
                    "source_text_position": "title",
                    "relevance_score": 0.94,
                    "is_primary": True,
                }
            ],
            "region_tags": ["TW"],
        }

        try:
            with TestClient(app) as client:
                first = client.post("/api/news/ingest", json=usgs_payload)
                assert first.status_code == 200
                second = client.post("/api/news/ingest", json=gdacs_payload)
                assert second.status_code == 200

                db = TestSessionLocal()
                try:
                    events = db.query(NewsEvent).all()
                    articles = db.query(NewsArticle).order_by(NewsArticle.source_code).all()
                    assert len(events) == 1
                    assert len(articles) == 2

                    event = events[0]
                    assert event.source_code == "earthquake_usgs"
                    assert event.external_id == "us7000tw1"
                    assert event.article_count == 2
                    assert event.severity >= 88
                    assert event.source_updated_at is not None
                    assert event.source_metadata is not None
                    assert "disaster_gdacs" in event.source_metadata["supporting_sources"]
                    assert event.source_metadata["enrichment_sources"]["disaster_gdacs"]["alertlevel"] == "red"

                    gdacs_article = next(article for article in articles if article.source_code == "disaster_gdacs")
                    assert gdacs_article.source_metadata["role"] == "alert_enrichment"
                    assert gdacs_article.external_id == "EQ:1102983"
                finally:
                    db.close()
        finally:
            news_api._hot_news_cache.invalidate()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)


# Performance tests
class TestPerformance:
    """Performance tests for API."""

    def test_health_response_time(self):
        """Test that health endpoint responds within reasonable time."""
        import time
        from app.main import app

        with TestClient(app) as client:
            start = time.time()
            response = client.get("/health")
            elapsed = time.time() - start

            assert response.status_code == 200
            assert elapsed < 0.5, f"Response took {elapsed:.2f}s, expected < 0.5s"


class TestSourceFeedControlApi:
    """Tests for feed-level source control endpoints."""

    def test_feed_control_endpoints(self):
        from datetime import datetime

        from app.models import Base, SourceFeedHealth, SourceFeedProfile
        from app.main import app
        from app.database import get_db

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        def override_get_db():
            db = TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        db = TestSessionLocal()
        try:
            db.add_all(
                [
                    SourceFeedProfile(
                        id="feed-fox-latest",
                        source_code="fox_news",
                        feed_code="latest",
                        feed_url="https://moxie.foxnews.com/google-publisher/latest.xml",
                        feed_name="latest",
                        priority=1,
                        freshness_sla_hours=24,
                        rollout_state="default",
                        enabled=True,
                        expected_update_interval_hours=1,
                        license_mode="publisher_public_noncommercial",
                    ),
                    SourceFeedProfile(
                        id="feed-nbc-public",
                        source_code="nbc_news",
                        feed_code="public_news",
                        feed_url="https://feeds.nbcnews.com/nbcnews/public/news",
                        feed_name="public_news",
                        priority=1,
                        freshness_sla_hours=24,
                        rollout_state="poc",
                        enabled=True,
                        expected_update_interval_hours=4,
                        license_mode="publisher_public",
                    ),
                    SourceFeedHealth(
                        id="health-fox-latest",
                        source_code="fox_news",
                        feed_code="latest",
                        feed_profile_id="feed-fox-latest",
                        last_fetch_at=datetime.utcnow(),
                        last_success_at=datetime.utcnow(),
                        last_fresh_item_at=datetime.utcnow(),
                        last_http_status=200,
                        last_error=None,
                        scraped_count_24h=8,
                        dropped_stale_count_24h=1,
                        dropped_quality_count_24h=1,
                        stale_ratio_24h=0.125,
                        direct_ok_rate_24h=1.0,
                        consecutive_failures=0,
                        direct_attempt_count_24h=6,
                        direct_ok_count_24h=6,
                        window_started_at=datetime.utcnow(),
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        try:
            with TestClient(app) as client:
                list_response = client.get("/api/sources/feeds")
                assert list_response.status_code == 200
                feeds = list_response.json()
                assert len(feeds) == 2
                assert feeds[0]["source_code"] == "fox_news"

                health_response = client.get("/api/sources/feeds/health")
                assert health_response.status_code == 200
                health_items = {item["feed_profile_id"]: item for item in health_response.json()}
                assert health_items["feed-fox-latest"]["scraped_count_24h"] == 8
                assert health_items["feed-fox-latest"]["direct_ok_rate_24h"] == 1.0
                assert health_items["feed-nbc-public"]["scraped_count_24h"] == 0

                patch_response = client.patch(
                    "/api/sources/feeds/feed-fox-latest",
                    json={"priority": 3, "rollout_state": "canary"},
                )
                assert patch_response.status_code == 200
                assert patch_response.json()["priority"] == 3
                assert patch_response.json()["rollout_state"] == "canary"

                promote_response = client.post("/api/sources/feeds/feed-nbc-public/promote", json={})
                assert promote_response.status_code == 200
                assert promote_response.json()["rollout_state"] == "canary"

                pause_response = client.post("/api/sources/feeds/feed-fox-latest/pause")
                assert pause_response.status_code == 200
                assert pause_response.json()["rollout_state"] == "paused"
                assert pause_response.json()["enabled"] is False
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)
