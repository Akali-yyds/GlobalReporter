"""add event lifecycle fields and indexes

Revision ID: 007_event_lifecycle
Revises: 006_source_policy
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "007_event_lifecycle"
down_revision = "006_source_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("news_events") as batch_op:
        batch_op.add_column(sa.Column("source_code", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("event_status", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("source_updated_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE news_events SET event_status = 'closed' WHERE event_status IS NULL")

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.alter_column("event_status", existing_type=sa.String(length=20), nullable=False)
        batch_op.create_index("ix_news_events_source_code", ["source_code"], unique=False)
        batch_op.create_index("ix_news_events_event_status", ["event_status"], unique=False)
        batch_op.create_index("ix_news_events_source_updated_at", ["source_updated_at"], unique=False)
        batch_op.create_index("ix_news_events_source_code_event_time", ["source_code", "event_time"], unique=False)
        batch_op.create_index("ix_news_events_event_status_event_time", ["event_status", "event_time"], unique=False)
        batch_op.create_unique_constraint("uq_news_events_source_external", ["source_code", "external_id"])

    conn = op.get_bind()
    json_type = "jsonb" if conn.dialect.name == "postgresql" else "json"
    op.execute(
        sa.text(
            f"""
            UPDATE source_policies
            SET default_params_json = CAST(:payload AS {json_type})
            WHERE source_code = 'earthquake_usgs'
            """
        ).bindparams(
            payload='{"realtime":{"feeds":["significant_hour","all_hour","significant_day","all_day"]},"backfill":{"feeds":["all_day"],"replay_window_days":7}}'
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE source_policies
            SET default_params_json = CAST(:payload AS {json_type})
            WHERE source_code = 'eonet_events'
            """
        ).bindparams(
            payload='{"realtime":{"status":"open","category":["wildfires","severeStorms","volcanoes"],"days":7,"limit":500},"backfill":{"status":"all","category":["wildfires","severeStorms","volcanoes"]}}'
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("news_events") as batch_op:
        batch_op.drop_constraint("uq_news_events_source_external", type_="unique")
        batch_op.drop_index("ix_news_events_event_status_event_time")
        batch_op.drop_index("ix_news_events_source_code_event_time")
        batch_op.drop_index("ix_news_events_source_updated_at")
        batch_op.drop_index("ix_news_events_event_status")
        batch_op.drop_index("ix_news_events_source_code")
        batch_op.drop_column("source_updated_at")
        batch_op.drop_column("closed_at")
        batch_op.drop_column("event_status")
        batch_op.drop_column("source_code")
