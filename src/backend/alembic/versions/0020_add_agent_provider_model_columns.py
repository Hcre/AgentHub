"""add provider, model, api_key_encrypted, base_url columns back to agents

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("agents")}

    if "provider" not in columns:
        op.add_column("agents", sa.Column("provider", sa.String(32), nullable=False, server_default="deepseek"))
    if "model" not in columns:
        op.add_column("agents", sa.Column("model", sa.String(128), nullable=False, server_default=""))
    if "api_key_encrypted" not in columns:
        op.add_column("agents", sa.Column("api_key_encrypted", sa.Text(), nullable=False, server_default=""))
    if "base_url" not in columns:
        op.add_column("agents", sa.Column("base_url", sa.String(512), nullable=True))


def downgrade() -> None:
    for col in ("base_url", "api_key_encrypted", "model", "provider"):
        op.drop_column("agents", col)
