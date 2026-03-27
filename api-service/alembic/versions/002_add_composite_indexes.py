"""add composite indexes for hot query paths

Revision ID: 002_composite_indexes
Revises: 001_enhance_geo_fields
Create Date: 2026-03-26 17:00:00.000000

"""
from alembic import op

revision = '002_composite_indexes'
down_revision = '001_enhance_geo_fields'
branch_labels = None
depends_on = None


def upgrade():
    # news_events: (main_country, heat_score DESC) — hot news by country
    op.create_index(
        'ix_news_events_country_heat',
        'news_events',
        ['main_country', 'heat_score'],
        postgresql_ops={'heat_score': 'DESC'},
    )
    # news_events: last_seen_at — recency queries
    op.create_index(
        'ix_news_events_last_seen_at',
        'news_events',
        ['last_seen_at'],
    )
    # event_geo_mappings: (event_id, is_primary) — fast primary geo lookup
    op.create_index(
        'ix_event_geo_mappings_event_primary',
        'event_geo_mappings',
        ['event_id', 'is_primary'],
    )
    # event_geo_mappings: (geo_key, event_id) — region news queries
    op.create_index(
        'ix_event_geo_mappings_geokey_event',
        'event_geo_mappings',
        ['geo_key', 'event_id'],
    )


def downgrade():
    op.drop_index('ix_event_geo_mappings_geokey_event', table_name='event_geo_mappings')
    op.drop_index('ix_event_geo_mappings_event_primary', table_name='event_geo_mappings')
    op.drop_index('ix_news_events_last_seen_at', table_name='news_events')
    op.drop_index('ix_news_events_country_heat', table_name='news_events')
