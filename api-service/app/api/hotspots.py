"""
Hotspots API - country-level and admin1-level geographic heat aggregation.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.geo_service import get_country_hotspots, get_admin1_hotspots, get_city_hotspots
from app.utils.ttl_cache import country_hotspot_cache, admin1_hotspot_cache, city_hotspot_cache
from app.schemas.geo import (
    CountryHotspotItem,
    CountryHotspotListResponse,
    Admin1HotspotItem,
    Admin1HotspotListResponse,
    CityHotspotItem,
    CityHotspotListResponse,
)

router = APIRouter()


@router.get("/countries", response_model=CountryHotspotListResponse)
async def country_hotspots(
    scope: Optional[str] = Query(None, pattern="^(all|china|world)$"),
    min_heat: Optional[int] = Query(None, ge=0),
    limit: int = Query(80, ge=1, le=200),
    since_hours: Optional[int] = Query(None, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """
    Aggregated heat score per country, sorted by total heat descending.
    Useful for globe country polygon tinting.

    - **scope**: all / china / world
    - **min_heat**: minimum total heat threshold
    - **limit**: max countries to return (default 80)
    """
    cache_key = f"countries:{scope}:{min_heat}:{limit}:{since_hours}"
    hit, cached = country_hotspot_cache.get(cache_key)
    if hit:
        return cached
    rows = get_country_hotspots(db, scope=scope, limit=limit, min_heat=min_heat, since_hours=since_hours)
    items = [CountryHotspotItem(**r) for r in rows]
    result = CountryHotspotListResponse(total=len(items), countries=items)
    country_hotspot_cache.set(cache_key, result)
    return result


@router.get("/admin1/{country_code}", response_model=Admin1HotspotListResponse)
async def admin1_hotspots(
    country_code: str,
    limit: int = Query(50, ge=1, le=100),
    since_hours: Optional[int] = Query(None, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """
    Aggregated heat score per admin1 region within a country.
    Useful for drill-down after clicking a country polygon.

    - **country_code**: ISO 3166-1 alpha-2 country code (e.g. US, CN, GB)
    - **limit**: max admin1 regions to return (default 50)
    """
    cc = country_code.upper()
    cache_key = f"admin1:{cc}:{limit}:{since_hours}"
    hit, cached = admin1_hotspot_cache.get(cache_key)
    if hit:
        return cached
    rows = get_admin1_hotspots(db, country_code=cc, limit=limit, since_hours=since_hours)
    items = [Admin1HotspotItem(**r) for r in rows]
    result = Admin1HotspotListResponse(country_code=cc, total=len(items), admin1_list=items)
    admin1_hotspot_cache.set(cache_key, result)
    return result


@router.get("/cities/{country_code}", response_model=CityHotspotListResponse)
async def city_hotspots(
    country_code: str,
    min_heat: Optional[int] = Query(None, ge=0),
    limit: int = Query(30, ge=1, le=80),
    since_hours: Optional[int] = Query(None, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """
    Aggregated heat score per city within a country.
    Only returns cities with known coordinates (lat/lng).

    - **country_code**: ISO 3166-1 alpha-2 country code (e.g. US, CN, GB)
    - **min_heat**: minimum total heat threshold
    - **limit**: max cities to return (default 30)
    """
    cc = country_code.upper()
    cache_key = f"cities:{cc}:{min_heat}:{limit}:{since_hours}"
    hit, cached = city_hotspot_cache.get(cache_key)
    if hit:
        return cached
    rows = get_city_hotspots(db, country_code=cc, limit=limit, min_heat=min_heat, since_hours=since_hours)
    items = [CityHotspotItem(**r) for r in rows]
    result = CityHotspotListResponse(country_code=cc, total=len(items), cities=items)
    city_hotspot_cache.set(cache_key, result)
    return result
