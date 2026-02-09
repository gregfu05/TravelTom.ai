"""scope event idempotency by session and event type

Revision ID: 202602061530
Revises: 202602042230
Create Date: 2026-02-06 15:30:00.000000
"""

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "202602061530"
down_revision = "202602042230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_events_idempotency", table_name="events")
    op.alter_column(
        "events",
        "session_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_index(
        "idx_events_idempotency",
        "events",
        ["session_id", "event_type", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_events_idempotency", table_name="events")
    op.alter_column(
        "events",
        "session_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_index(
        "idx_events_idempotency",
        "events",
        ["idempotency_key"],
        unique=True,
    )
