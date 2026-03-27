# API package
from app.api.news import router as news_router
from app.api.globe import router as globe_router
from app.api.sources import router as sources_router
from app.api.jobs import router as jobs_router

__all__ = ["news_router", "globe_router", "sources_router", "jobs_router"]
