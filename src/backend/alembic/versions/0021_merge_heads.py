"""merge two alembic heads

Revision ID: 0021
Revises: 0020, a1859d63e07b
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0021"
down_revision: tuple[str, str] | None = ("0020", "a1859d63e07b")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
