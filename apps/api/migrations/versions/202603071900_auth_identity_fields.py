"""add external auth identity fields to users

Revision ID: 202603071900
Revises: 202602061530
Create Date: 2026-03-07 19:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202603071900"
down_revision = "202602061530"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_issuer", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("external_subject", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_users_auth_identity",
        "users",
        ["auth_issuer", "external_subject"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_auth_identity", "users", type_="unique")
    op.drop_column("users", "external_subject")
    op.drop_column("users", "auth_issuer")
