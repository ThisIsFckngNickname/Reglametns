"""drop_orders_tables

Revision ID: 4f88650f2e15
Revises: 6d8ac2378558
Create Date: 2026-06-21 16:17:43.113089

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4f88650f2e15'
down_revision: Union[str, None] = '6d8ac2378558'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_order_document_links_document_id", table_name="order_document_links")
    op.drop_index("ix_order_document_links_order_id", table_name="order_document_links")
    op.drop_table("order_document_links")
    op.drop_index("ix_orders_holding_id", table_name="orders")
    op.drop_table("orders")


def downgrade() -> None:
    # Data loss — no downgrade path
    pass
