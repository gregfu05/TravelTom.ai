"""add local auth sessions table

Revision ID: 202603072215
Revises: 202603072030
Create Date: 2026-03-07 22:15:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "202603072215"
down_revision = "202603072030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auth_issuer", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("idx_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("idx_auth_sessions_revoked_at", table_name="auth_sessions")
    op.drop_index("idx_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
