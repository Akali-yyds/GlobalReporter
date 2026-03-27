"""enhance geo fields for multilevel support

Revision ID: 001_enhance_geo_fields
Revises: 
Create Date: 2026-03-24 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_enhance_geo_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add enhanced geo fields for multilevel geographic support."""
    
    # === geo_entities table enhancements ===
    
    # Add new geographic hierarchy fields
    op.add_column('geo_entities', sa.Column('country_name', sa.String(100), nullable=True))
    op.add_column('geo_entities', sa.Column('admin1_code', sa.String(10), nullable=True))
    op.add_column('geo_entities', sa.Column('admin1_name', sa.String(100), nullable=True))
    op.add_column('geo_entities', sa.Column('admin2_code', sa.String(10), nullable=True))
    op.add_column('geo_entities', sa.Column('admin2_name', sa.String(100), nullable=True))
    op.add_column('geo_entities', sa.Column('city_name', sa.String(100), nullable=True))
    op.add_column('geo_entities', sa.Column('district_name', sa.String(100), nullable=True))
    
    # Add precision and display fields
    op.add_column('geo_entities', sa.Column('precision_level', sa.String(20), nullable=True))
    op.add_column('geo_entities', sa.Column('display_mode', sa.String(20), nullable=True))
    op.add_column('geo_entities', sa.Column('geojson_key', sa.String(100), nullable=True))
    
    # Add check constraints for enum fields
    op.create_check_constraint(
        'ck_geo_entities_precision_level',
        'geo_entities',
        "precision_level IN ('COUNTRY', 'ADMIN1', 'ADMIN2', 'CITY', 'DISTRICT', 'POINT')"
    )
    op.create_check_constraint(
        'ck_geo_entities_display_mode',
        'geo_entities', 
        "display_mode IN ('POLYGON', 'POINT', 'LIST_ONLY')"
    )
    
    # Modify coordinate columns to use DECIMAL for better precision
    op.alter_column('geo_entities', 'lat', 
                   existing_type=sa.Float(),
                   type_=sa.DECIMAL(10, 8),
                   nullable=True)
    op.alter_column('geo_entities', 'lng',
                   existing_type=sa.Float(), 
                   type_=sa.DECIMAL(11, 8),
                   nullable=True)
    
    # Migrate existing data: geo_type -> precision_level
    op.execute("UPDATE geo_entities SET precision_level = 'COUNTRY' WHERE geo_type = 'country'")
    op.execute("UPDATE geo_entities SET precision_level = 'CITY' WHERE geo_type = 'city'")
    op.execute("UPDATE geo_entities SET precision_level = 'ADMIN1' WHERE geo_type = 'region'")
    
    # Set default display_mode based on precision_level
    op.execute("UPDATE geo_entities SET display_mode = 'POLYGON' WHERE precision_level IN ('COUNTRY', 'ADMIN1', 'ADMIN2')")
    op.execute("UPDATE geo_entities SET display_mode = 'POINT' WHERE precision_level IN ('CITY', 'DISTRICT', 'POINT')")
    
    # Remove old geo_type column
    op.drop_column('geo_entities', 'geo_type')
    
    # === event_geo_mappings table enhancements ===
    
    # Add extraction and analysis fields
    op.add_column('event_geo_mappings', sa.Column('matched_text', sa.String(500), nullable=True))
    op.add_column('event_geo_mappings', sa.Column('extraction_method', sa.String(50), nullable=True))
    op.add_column('event_geo_mappings', sa.Column('relevance_score', sa.DECIMAL(3, 2), nullable=True))
    op.add_column('event_geo_mappings', sa.Column('is_primary', sa.Boolean(), nullable=True, default=False))
    op.add_column('event_geo_mappings', sa.Column('source_text_position', sa.String(20), nullable=True))
    
    # Add check constraints
    op.create_check_constraint(
        'ck_event_geo_mappings_relevance_score',
        'event_geo_mappings',
        "relevance_score >= 0.0 AND relevance_score <= 1.0"
    )
    op.create_check_constraint(
        'ck_event_geo_mappings_source_position',
        'event_geo_mappings',
        "source_text_position IN ('title', 'summary', 'content')"
    )
    
    # Modify confidence column to use DECIMAL
    op.alter_column('event_geo_mappings', 'confidence',
                   existing_type=sa.Float(),
                   type_=sa.DECIMAL(3, 2),
                   nullable=True)
    
    # Set default values for existing records
    op.execute("UPDATE event_geo_mappings SET is_primary = FALSE WHERE is_primary IS NULL")
    op.execute("UPDATE event_geo_mappings SET extraction_method = 'legacy' WHERE extraction_method IS NULL")
    
    # Remove old columns
    op.drop_column('event_geo_mappings', 'geo_type')
    op.drop_column('event_geo_mappings', 'display_type')
    
    # === Create optimized indexes ===
    
    # geo_entities indexes
    op.create_index('idx_geo_entities_precision_level', 'geo_entities', ['precision_level'])
    op.create_index('idx_geo_entities_display_mode', 'geo_entities', ['display_mode'])
    op.create_index('idx_geo_entities_country_admin1', 'geo_entities', ['country_code', 'admin1_code'])
    op.create_index('idx_geo_entities_coords', 'geo_entities', ['lat', 'lng'])
    op.create_index('idx_geo_entities_geojson_key', 'geo_entities', ['geojson_key'])
    
    # event_geo_mappings indexes
    op.create_index('idx_event_geo_mappings_extraction_method', 'event_geo_mappings', ['extraction_method'])
    op.create_index('idx_event_geo_mappings_is_primary', 'event_geo_mappings', ['is_primary'])
    op.create_index('idx_event_geo_mappings_confidence', 'event_geo_mappings', ['confidence'])
    op.create_index('idx_event_geo_mappings_relevance_score', 'event_geo_mappings', ['relevance_score'])


def downgrade():
    """Revert geo fields enhancements."""
    
    # Drop new indexes
    op.drop_index('idx_event_geo_mappings_relevance_score', 'event_geo_mappings')
    op.drop_index('idx_event_geo_mappings_confidence', 'event_geo_mappings')
    op.drop_index('idx_event_geo_mappings_is_primary', 'event_geo_mappings')
    op.drop_index('idx_event_geo_mappings_extraction_method', 'event_geo_mappings')
    op.drop_index('idx_geo_entities_geojson_key', 'geo_entities')
    op.drop_index('idx_geo_entities_coords', 'geo_entities')
    op.drop_index('idx_geo_entities_country_admin1', 'geo_entities')
    op.drop_index('idx_geo_entities_display_mode', 'geo_entities')
    op.drop_index('idx_geo_entities_precision_level', 'geo_entities')
    
    # Restore old columns for event_geo_mappings
    op.add_column('event_geo_mappings', sa.Column('geo_type', sa.String(20), nullable=True))
    op.add_column('event_geo_mappings', sa.Column('display_type', sa.String(20), nullable=True, default='point'))
    
    # Restore old columns for geo_entities
    op.add_column('geo_entities', sa.Column('geo_type', sa.String(20), nullable=True))
    
    # Migrate data back
    op.execute("UPDATE geo_entities SET geo_type = 'country' WHERE precision_level = 'COUNTRY'")
    op.execute("UPDATE geo_entities SET geo_type = 'city' WHERE precision_level = 'CITY'")
    op.execute("UPDATE geo_entities SET geo_type = 'region' WHERE precision_level = 'ADMIN1'")
    
    # Remove new columns from event_geo_mappings
    op.drop_constraint('ck_event_geo_mappings_source_position', 'event_geo_mappings')
    op.drop_constraint('ck_event_geo_mappings_relevance_score', 'event_geo_mappings')
    op.drop_column('event_geo_mappings', 'source_text_position')
    op.drop_column('event_geo_mappings', 'is_primary')
    op.drop_column('event_geo_mappings', 'relevance_score')
    op.drop_column('event_geo_mappings', 'extraction_method')
    op.drop_column('event_geo_mappings', 'matched_text')
    
    # Revert confidence column type
    op.alter_column('event_geo_mappings', 'confidence',
                   existing_type=sa.DECIMAL(3, 2),
                   type_=sa.Float(),
                   nullable=True)
    
    # Remove new columns from geo_entities
    op.drop_constraint('ck_geo_entities_display_mode', 'geo_entities')
    op.drop_constraint('ck_geo_entities_precision_level', 'geo_entities')
    op.drop_column('geo_entities', 'geojson_key')
    op.drop_column('geo_entities', 'display_mode')
    op.drop_column('geo_entities', 'precision_level')
    op.drop_column('geo_entities', 'district_name')
    op.drop_column('geo_entities', 'city_name')
    op.drop_column('geo_entities', 'admin2_name')
    op.drop_column('geo_entities', 'admin2_code')
    op.drop_column('geo_entities', 'admin1_name')
    op.drop_column('geo_entities', 'admin1_code')
    op.drop_column('geo_entities', 'country_name')
    
    # Revert coordinate column types
    op.alter_column('geo_entities', 'lat',
                   existing_type=sa.DECIMAL(10, 8),
                   type_=sa.Float(),
                   nullable=True)
    op.alter_column('geo_entities', 'lng',
                   existing_type=sa.DECIMAL(11, 8), 
                   type_=sa.Float(),
                   nullable=True)
