"""add_links_orders_and_version_notes

Revision ID: 20678de3c128
Revises: e5b1a2c3d4f5
Create Date: 2026-06-20 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20678de3c128'
down_revision: Union[str, None] = 'e5b1a2c3d4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add version_notes to document_versions
    op.add_column('document_versions',
        sa.Column('version_notes', sa.Text(), nullable=True)
    )

    # Create document_links table
    op.create_table('document_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_document_id', sa.Integer(), nullable=False),
        sa.Column('target_document_id', sa.Integer(), nullable=False),
        sa.Column('link_type', sa.String(length=20), nullable=False),
        sa.Column('is_manual', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_links_source_document_id'), 'document_links', ['source_document_id'], unique=False)
    op.create_index(op.f('ix_document_links_target_document_id'), 'document_links', ['target_document_id'], unique=False)

    # Create orders table
    op.create_table('orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('holding_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('order_number', sa.String(length=100), nullable=True),
        sa.Column('order_date', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_type', sa.String(length=10), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['holding_id'], ['holdings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_holding_id'), 'orders', ['holding_id'], unique=False)

    # Create order_document_links table
    op.create_table('order_document_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('link_type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_document_links_order_id'), 'order_document_links', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_document_links_document_id'), 'order_document_links', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_document_links_document_id'), table_name='order_document_links')
    op.drop_index(op.f('ix_order_document_links_order_id'), table_name='order_document_links')
    op.drop_table('order_document_links')
    op.drop_index(op.f('ix_orders_holding_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_document_links_target_document_id'), table_name='document_links')
    op.drop_index(op.f('ix_document_links_source_document_id'), table_name='document_links')
    op.drop_table('document_links')
    op.drop_column('document_versions', 'version_notes')
