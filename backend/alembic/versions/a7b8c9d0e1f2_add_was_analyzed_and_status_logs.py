"""add_was_analyzed_and_status_logs

Revision ID: a7b8c9d0e1f2
Revises: 66e381707403
Create Date: 2026-06-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = '66e381707403'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add was_analyzed to documents
    op.add_column(
        'documents',
        sa.Column('was_analyzed', sa.Boolean(), nullable=False,
                  server_default=sa.text('0')),
    )

    # Create document_status_logs table
    op.create_table(
        'document_status_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_document_status_logs_document_id'),
        'document_status_logs', ['document_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_document_status_logs_document_id'),
        table_name='document_status_logs',
    )
    op.drop_table('document_status_logs')
    op.drop_column('documents', 'was_analyzed')
