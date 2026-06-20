"""add_full_text_to_document_versions

Revision ID: a1b2c3d4e5f6
Revises: e5b1a2c3d4f5
Create Date: 2026-06-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e5b1a2c3d4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'document_versions',
        sa.Column('full_text', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('document_versions', 'full_text')
