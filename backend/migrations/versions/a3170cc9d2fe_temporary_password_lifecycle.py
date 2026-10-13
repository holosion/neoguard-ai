"""Add temporary password lifecycle fields to users.

Revision ID: a3170cc9d2fe
Revises: 6ad430c12e8b
"""
from alembic import op
import sqlalchemy as sa


revision = "a3170cc9d2fe"
down_revision = "6ad430c12e8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
    op.drop_column("users", "password_expires_at")
    op.drop_column("users", "must_change_password")
