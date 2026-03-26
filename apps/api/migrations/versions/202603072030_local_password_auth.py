"""add local password auth field to users

Revision ID: 202603072030
Revises: 202603071900
Create Date: 2026-03-07 20:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202603072030"
down_revision = "202603071900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
