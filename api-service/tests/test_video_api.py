import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _build_test_client():
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
    return app, test_engine, TestSessionLocal


def test_get_video_sources_and_probe(monkeypatch):
    os.environ["CRAWLER_ENABLED"] = "false"
    app, test_engine, _session = _build_test_client()

    from app.services import video_probe_service

    def fake_request_text(url: str, timeout: int = 20):
        if "youtube.com/embed" in url:
            return 200, "<html><body>live ok</body></html>"
        return 200, '<meta property="og:title" content="Sky News Live"><meta property="og:image" content="https://img.example/live.jpg">'

    monkeypatch.setattr(video_probe_service, "_request_text", fake_request_text)

    try:
      with TestClient(app) as client:
        response = client.get("/api/videos/sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 6
        assert any(item["video_type"] == "youtube_embed" for item in data)
        assert any(item["video_type"] == "hls" for item in data)

        probe = client.post("/api/videos/probe/sky_news_live")
        assert probe.status_code == 200
        payload = probe.json()
        assert payload["ok"] is True
        assert payload["source_code"] == "sky_news_live"
        assert payload["status"] == "live"
        assert payload["title"] == "Sky News Live"

        detail = client.get("/api/videos/sources/sky_news_live")
        assert detail.status_code == 200
        detail_json = detail.json()
        assert detail_json["checkpoint"] is not None
        assert detail_json["checkpoint"]["job_code"] == "manual_probe"
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()


def test_probe_hls_source(monkeypatch):
    os.environ["CRAWLER_ENABLED"] = "false"
    app, test_engine, _session = _build_test_client()

    from app.services import video_probe_service

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _size=-1):
            return b"#EXTM3U\n#EXT-X-VERSION:3\n"

    monkeypatch.setattr(video_probe_service, "urlopen", lambda *args, **kwargs: _FakeResponse())

    try:
        with TestClient(app) as client:
            probe = client.post("/api/videos/probe/wusa9_hls")
            assert probe.status_code == 200
            payload = probe.json()
            assert payload["ok"] is True
            assert payload["status"] == "live"
            assert payload["http_status"] == 200

            health = client.get("/api/videos/health", params={"video_type": "hls"})
            assert health.status_code == 200
            health_data = health.json()["sources"]
            assert any(item["source_code"] == "wusa9_hls" for item in health_data)
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
