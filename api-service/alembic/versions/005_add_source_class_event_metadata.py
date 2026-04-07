"""add source class and event metadata

Revision ID: 005_source_class_meta
Revises: 004_add_source_tiers
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "005_source_class_meta"
down_revision = "004_add_source_tiers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("news_sources") as batch_op:
        batch_op.add_column(sa.Column("source_class", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("source_tier_level", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("freshness_sla_hours", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("license_mode", sa.String(length=30), nullable=True))

    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.add_column(sa.Column("source_class", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("event_time", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("freshness_sla_hours", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("severity", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("confidence", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("geo", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("license_mode", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("canonical_url", sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column("external_id", sa.String(length=255), nullable=True))

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.add_column(sa.Column("source_class", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("severity", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("confidence", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("geo", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("source_tier_level", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("freshness_sla_hours", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("event_time", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("license_mode", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("canonical_url", sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column("external_id", sa.String(length=255), nullable=True))

    op.execute("UPDATE news_sources SET source_class = 'news' WHERE source_class IS NULL")
    op.execute("UPDATE news_sources SET source_tier_level = 2 WHERE source_tier_level IS NULL")
    op.execute("UPDATE news_sources SET freshness_sla_hours = 24 WHERE freshness_sla_hours IS NULL")
    op.execute("UPDATE news_sources SET license_mode = 'public_web' WHERE license_mode IS NULL")

    op.execute("UPDATE news_articles SET source_class = 'news' WHERE source_class IS NULL")
    op.execute("UPDATE news_articles SET freshness_sla_hours = 24 WHERE freshness_sla_hours IS NULL")
    op.execute("UPDATE news_articles SET severity = 0 WHERE severity IS NULL")
    op.execute("UPDATE news_articles SET confidence = 100 WHERE confidence IS NULL")
    op.execute("UPDATE news_articles SET license_mode = 'public_web' WHERE license_mode IS NULL")
    op.execute("UPDATE news_articles SET canonical_url = article_url WHERE canonical_url IS NULL")

    op.execute("UPDATE news_events SET source_class = 'news' WHERE source_class IS NULL")
    op.execute("UPDATE news_events SET severity = 0 WHERE severity IS NULL")
    op.execute("UPDATE news_events SET confidence = 100 WHERE confidence IS NULL")
    op.execute("UPDATE news_events SET source_tier_level = 2 WHERE source_tier_level IS NULL")
    op.execute("UPDATE news_events SET freshness_sla_hours = 24 WHERE freshness_sla_hours IS NULL")
    op.execute("UPDATE news_events SET license_mode = 'public_web' WHERE license_mode IS NULL")

    with op.batch_alter_table("news_sources") as batch_op:
        batch_op.alter_column("source_class", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("source_tier_level", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("freshness_sla_hours", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("license_mode", existing_type=sa.String(length=30), nullable=False)
        batch_op.create_index("ix_news_sources_source_class", ["source_class"], unique=False)
        batch_op.create_index("ix_news_sources_source_tier_level", ["source_tier_level"], unique=False)

    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.alter_column("source_class", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("freshness_sla_hours", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("severity", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("confidence", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("license_mode", existing_type=sa.String(length=30), nullable=False)
        batch_op.create_index("ix_news_articles_source_class", ["source_class"], unique=False)
        batch_op.create_index("ix_news_articles_event_time", ["event_time"], unique=False)
        batch_op.create_index("ix_news_articles_geo", ["geo"], unique=False)
        batch_op.create_index("ix_news_articles_canonical_url", ["canonical_url"], unique=False)
        batch_op.create_index("ix_news_articles_external_id", ["external_id"], unique=False)

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.alter_column("source_class", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("severity", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("confidence", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("source_tier_level", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("freshness_sla_hours", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("license_mode", existing_type=sa.String(length=30), nullable=False)
        batch_op.create_index("ix_news_events_source_class", ["source_class"], unique=False)
        batch_op.create_index("ix_news_events_source_tier_level", ["source_tier_level"], unique=False)
        batch_op.create_index("ix_news_events_event_time", ["event_time"], unique=False)
        batch_op.create_index("ix_news_events_geo", ["geo"], unique=False)
        batch_op.create_index("ix_news_events_canonical_url", ["canonical_url"], unique=False)
        batch_op.create_index("ix_news_events_external_id", ["external_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("news_events") as batch_op:
        batch_op.drop_index("ix_news_events_external_id")
        batch_op.drop_index("ix_news_events_canonical_url")
        batch_op.drop_index("ix_news_events_geo")
        batch_op.drop_index("ix_news_events_event_time")
        batch_op.drop_index("ix_news_events_source_tier_level")
        batch_op.drop_index("ix_news_events_source_class")
        batch_op.drop_column("external_id")
        batch_op.drop_column("canonical_url")
        batch_op.drop_column("license_mode")
        batch_op.drop_column("event_time")
        batch_op.drop_column("freshness_sla_hours")
        batch_op.drop_column("source_tier_level")
        batch_op.drop_column("geo")
        batch_op.drop_column("confidence")
        batch_op.drop_column("severity")
        batch_op.drop_column("source_class")

    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.drop_index("ix_news_articles_external_id")
        batch_op.drop_index("ix_news_articles_canonical_url")
        batch_op.drop_index("ix_news_articles_geo")
        batch_op.drop_index("ix_news_articles_event_time")
        batch_op.drop_index("ix_news_articles_source_class")
        batch_op.drop_column("external_id")
        batch_op.drop_column("canonical_url")
        batch_op.drop_column("license_mode")
        batch_op.drop_column("geo")
        batch_op.drop_column("confidence")
        batch_op.drop_column("severity")
        batch_op.drop_column("freshness_sla_hours")
        batch_op.drop_column("event_time")
        batch_op.drop_column("source_class")

    with op.batch_alter_table("news_sources") as batch_op:
        batch_op.drop_index("ix_news_sources_source_tier_level")
        batch_op.drop_index("ix_news_sources_source_class")
        batch_op.drop_column("license_mode")
        batch_op.drop_column("freshness_sla_hours")
        batch_op.drop_column("source_tier_level")
        batch_op.drop_column("source_class")
