"""add tags field to news_events

Revision ID: 003_add_event_tags
Revises: 002_composite_indexes
Create Date: 2026-04-03 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '003_add_event_tags'
down_revision = '002_composite_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('news_events', sa.Column('tags', sa.Text(), nullable=True))
    op.execute("UPDATE news_events SET tags = '[]' WHERE tags IS NULL")


def downgrade():
    op.drop_column('news_events', 'tags')
