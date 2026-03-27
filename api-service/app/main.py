"""
FastAPI application entry point.
"""
import logging
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db
from app.api import news, globe, sources, jobs, hotspots
from app.crawler_runner import start_background_crawler, stop_background_crawler

# Configure logging with ASCII-safe format to avoid encoding issues
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting GlobalReporter API Service...")
    init_db()
    logger.info("Database initialized.")
    start_background_crawler()
    yield
    # Shutdown
    stop_background_crawler()
    logger.info("Shutting down GlobalReporter API Service...")


# Create FastAPI application
app = FastAPI(
    title="GlobalReporter API",
    description="Global Hot News 3D Globe Visualization System API",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(news.router, prefix="/api/news", tags=["News"])
app.include_router(globe.router, prefix="/api/globe", tags=["Globe"])
app.include_router(sources.router, prefix="/api/sources", tags=["Sources"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(hotspots.router, prefix="/api/hotspots", tags=["Hotspots"])

class GeoDataCacheMiddleware(BaseHTTPMiddleware):
    """Inject Cache-Control headers for static geodata assets."""
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/geodata/"):
            if path.endswith(".geojson"):
                response.headers["Cache-Control"] = "public, max-age=3600"
            else:
                response.headers["Cache-Control"] = "public, max-age=600"
        return response

app.add_middleware(GeoDataCacheMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Serve static geodata assets (GeoJSON files for globe rendering)
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "GlobalReporter API",
        "version": "1.0.0",
        "description": "Global Hot News 3D Globe Visualization System API",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
