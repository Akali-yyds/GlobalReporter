# Schemas package
from app.schemas.common import PaginatedResponse, BaseResponse
from app.schemas.news import (
    NewsArticleBase,
    NewsArticleCreate,
    NewsArticleResponse,
    NewsArticleListResponse,
)
from app.schemas.event import (
    NewsEventBase,
    NewsEventListItem,
    NewsEventResponse,
    NewsEventListResponse,
    EventGeoMappingResponse,
)
from app.schemas.geo import (
    GeoEntityBase,
    GeoEntityResponse,
    HotspotResponse,
    HotspotListResponse,
    CountryHotspotItem,
    CountryHotspotListResponse,
    Admin1HotspotItem,
    Admin1HotspotListResponse,
)

__all__ = [
    "PaginatedResponse",
    "BaseResponse",
    "NewsArticleBase",
    "NewsArticleCreate",
    "NewsArticleResponse",
    "NewsArticleListResponse",
    "NewsEventBase",
    "NewsEventListItem",
    "NewsEventResponse",
    "NewsEventListResponse",
    "EventGeoMappingResponse",
    "GeoEntityBase",
    "GeoEntityResponse",
    "HotspotResponse",
    "HotspotListResponse",
    "CountryHotspotItem",
    "CountryHotspotListResponse",
    "Admin1HotspotItem",
    "Admin1HotspotListResponse",
]
