"""
Geo schema definitions.
"""
from typing import Optional, List
from pydantic import BaseModel


class GeoEntityBase(BaseModel):
    """Base geo entity schema."""
    name: str
    geo_key: str
    geo_type: str
    country_code: str


class GeoEntityResponse(GeoEntityBase):
    """Schema for geo entity response."""
    id: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class HotspotResponse(BaseModel):
    """Schema for hotspot response."""
    event_id: str
    geo_key: str
    geo_name: Optional[str] = None
    geo_type: str
    display_type: str
    heat_score: int
    confidence: float
    title: str
    summary: Optional[str] = None
    center: Optional[List[float]] = None
    color: Optional[str] = None


class HotspotListResponse(BaseModel):
    """Schema for hotspot list response."""
    hotspots: List[HotspotResponse]


class CountryHotspotItem(BaseModel):
    """Aggregated heat data for one country."""
    country_code: str
    country_name: Optional[str] = None
    iso_a3: Optional[str] = None
    heat_total: int
    event_count: int
    center: Optional[List[float]] = None


class CountryHotspotListResponse(BaseModel):
    """Response for country-level hotspot aggregation."""
    total: int
    countries: List[CountryHotspotItem]


class Admin1HotspotItem(BaseModel):
    """Aggregated heat data for one admin1 region."""
    admin1_code: Optional[str] = None
    admin1_name: Optional[str] = None
    geo_key: Optional[str] = None
    heat_total: int
    event_count: int
    center: Optional[List[float]] = None


class Admin1HotspotListResponse(BaseModel):
    """Response for admin1-level hotspot aggregation within a country."""
    country_code: str
    total: int
    admin1_list: List[Admin1HotspotItem]


class CityHotspotItem(BaseModel):
    """Aggregated heat data for one city."""
    city_name: Optional[str] = None
    admin1_name: Optional[str] = None
    geo_key: Optional[str] = None
    heat_total: int
    event_count: int
    center: Optional[List[float]] = None


class CityHotspotListResponse(BaseModel):
    """Response for city-level hotspot aggregation within a country."""
    country_code: str
    total: int
    cities: List[CityHotspotItem]
