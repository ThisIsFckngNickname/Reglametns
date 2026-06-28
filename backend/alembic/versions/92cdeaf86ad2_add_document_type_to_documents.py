"""add_document_type_to_documents

Revision ID: 92cdeaf86ad2
Revises: c1d2e3f4a5b6
Create Date: 2026-06-28 11:27:53.934733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92cdeaf86ad2'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column(
        'document_type', sa.String(length=50),
        server_default='regulation', nullable=False,
    ))
    op.create_index(op.f('ix_documents_document_type'), 'documents', ['document_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_documents_document_type'), table_name='documents')
    op.drop_column('documents', 'document_type')
