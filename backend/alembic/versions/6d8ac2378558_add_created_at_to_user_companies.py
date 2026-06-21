"""add_created_at_to_user_companies

Revision ID: 6d8ac2378558
Revises: c0d1e2f3a4b5
Create Date: 2026-06-21 15:39:08.922843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d8ac2378558'
down_revision: Union[str, None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add created_at to user_companies (nullable->fill->non-nullable)."""
    # Add as nullable, fill existing rows, then make non-nullable
    with op.batch_alter_table("user_companies") as batch_op:
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE user_companies SET created_at = datetime('now') WHERE created_at IS NULL")
    with op.batch_alter_table("user_companies") as batch_op:
        batch_op.alter_column("created_at", nullable=False)


def downgrade() -> None:
    """Reverse: drop created_at."""
    op.drop_column('user_companies', 'created_at')
