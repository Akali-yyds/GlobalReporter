"""
GeoEntity model.
"""
from sqlalchemy import Column, String, Boolean, DECIMAL

from app.models.base import BaseModel


class GeoEntity(BaseModel):
    """Geographic entity model for multilevel geographic support."""

    __tablename__ = "geo_entities"

    name = Column(String(100), nullable=False, index=True)
    geo_key = Column(String(20), nullable=False, unique=True, index=True)
    
    # Geographic hierarchy fields
    country_code = Column(String(10), nullable=False, index=True)
    country_name = Column(String(100), nullable=True)
    admin1_code = Column(String(10), nullable=True)
    admin1_name = Column(String(100), nullable=True)
    admin2_code = Column(String(10), nullable=True)
    admin2_name = Column(String(100), nullable=True)
    city_name = Column(String(100), nullable=True)
    district_name = Column(String(100), nullable=True)
    
    # Precision and display fields
    precision_level = Column(String(20), nullable=True, index=True)  # COUNTRY|ADMIN1|ADMIN2|CITY|DISTRICT|POINT
    display_mode = Column(String(20), nullable=True, index=True)  # POLYGON|POINT|LIST_ONLY
    geojson_key = Column(String(100), nullable=True, index=True)
    
    # Coordinate fields with higher precision
    lat = Column(DECIMAL(10, 8), nullable=True)
    lng = Column(DECIMAL(11, 8), nullable=True)
    
    is_active = Column(Boolean, default=True)
