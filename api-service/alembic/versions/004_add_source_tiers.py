"""add source tiers

Revision ID: 004_add_source_tiers
Revises: 003_add_event_tags
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004_add_source_tiers"
down_revision = "003_add_event_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("news_sources") as batch_op:
        batch_op.add_column(sa.Column("source_tier", sa.String(length=20), nullable=True))

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.add_column(sa.Column("source_tier", sa.String(length=20), nullable=True))

    op.execute("UPDATE news_sources SET source_tier = 'authoritative' WHERE source_tier IS NULL")
    op.execute("UPDATE news_events SET source_tier = 'authoritative' WHERE source_tier IS NULL")

    with op.batch_alter_table("news_sources") as batch_op:
        batch_op.alter_column("source_tier", existing_type=sa.String(length=20), nullable=False)
        batch_op.create_index("ix_news_sources_source_tier", ["source_tier"], unique=False)

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.alter_column("source_tier", existing_type=sa.String(length=20), nullable=False)
        batch_op.create_index("ix_news_events_source_tier", ["source_tier"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("news_events") as batch_op:
        batch_op.drop_index("ix_news_events_source_tier")
        batch_op.drop_column("source_tier")

    with op.batch_alter_table("news_sources") as batch_op:
        batch_op.drop_index("ix_news_sources_source_tier")
        batch_op.drop_column("source_tier")
