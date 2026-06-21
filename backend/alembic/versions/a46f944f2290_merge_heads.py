"""merge_heads

Revision ID: a46f944f2290
Revises: 20678de3c128, a1b2c3d4e5f6
Create Date: 2026-06-20 15:49:00.328457

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a46f944f2290'
down_revision: Union[str, None] = ('20678de3c128', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
