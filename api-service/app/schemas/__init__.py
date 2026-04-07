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
from app.schemas.source import (
    NewsSourceResponse,
    SourcePolicyResponse,
    SourceFeedProfileResponse,
    SourceFeedProfilePatchRequest,
    SourceFeedPromoteRequest,
    SourceFeedHealthItem,
    SourceAnalyticsResponse,
    SourceAnalyticsItem,
    SourceTierAnalyticsItem,
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
    "NewsSourceResponse",
    "SourcePolicyResponse",
    "SourceFeedProfileResponse",
    "SourceFeedProfilePatchRequest",
    "SourceFeedPromoteRequest",
    "SourceFeedHealthItem",
    "SourceAnalyticsResponse",
    "SourceAnalyticsItem",
    "SourceTierAnalyticsItem",
]
