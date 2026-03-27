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
        from app.models import Base
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
