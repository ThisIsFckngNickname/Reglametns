"""add_document_analysis_table_and_fields

Revision ID: b39c2faec5e2
Revises: 4f88650f2e15
Create Date: 2026-06-28 10:12:46.880211

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'b39c2faec5e2'
down_revision: Union[str, None] = '4f88650f2e15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create document_analyses table
    op.create_table('document_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('document_version_id', sa.Integer(), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
        sa.Column('steps_status', sqlite.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_summary', sqlite.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_document_analyses_document_id'),
        'document_analyses', ['document_id'], unique=False,
    )

    # Add columns to documents table
    op.add_column(
        'documents',
        sa.Column('analysis_hash', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'documents',
        sa.Column('analysis_status', sa.String(length=10), nullable=False, server_default='none'),
    )


def downgrade() -> None:
    # Drop columns from documents table
    op.drop_column('documents', 'analysis_status')
    op.drop_column('documents', 'analysis_hash')

    # Drop document_analyses table
    op.drop_index(op.f('ix_document_analyses_document_id'), table_name='document_analyses')
    op.drop_table('document_analyses')
