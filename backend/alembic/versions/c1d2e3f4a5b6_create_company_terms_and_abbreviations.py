"""create_company_terms_and_abbreviations

Revision ID: c1d2e3f4a5b6
Revises: b39c2faec5e2
Create Date: 2026-06-28 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b39c2faec5e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create company_terms table
    op.create_table('company_terms',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('term', sa.String(length=255), nullable=False),
        sa.Column('definition', sa.Text(), nullable=False),
        sa.Column('source_document_id', sa.Integer(), nullable=True),
        sa.Column('is_manual', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('company_id', 'term', name='uq_company_term'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_company_terms_company_id'),
        'company_terms', ['company_id'], unique=False,
    )

    # Create company_abbreviations table
    op.create_table('company_abbreviations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('abbreviation', sa.String(length=50), nullable=False),
        sa.Column('full_form', sa.String(length=500), nullable=False),
        sa.Column('source_document_id', sa.Integer(), nullable=True),
        sa.Column('is_manual', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('company_id', 'abbreviation', name='uq_company_abbreviation'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_company_abbreviations_company_id'),
        'company_abbreviations', ['company_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_company_abbreviations_company_id'), table_name='company_abbreviations')
    op.drop_table('company_abbreviations')
    op.drop_index(op.f('ix_company_terms_company_id'), table_name='company_terms')
    op.drop_table('company_terms')
