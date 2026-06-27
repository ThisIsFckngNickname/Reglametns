"""rename_holdings_to_companies

Revision ID: c0d1e2f3a4b5
Revises: a7b8c9d0e1f2
Create Date: 2026-06-21 12:00:00.000000

Renames tables:
  holdings      -> companies
  user_holdings -> user_companies (with column holding_id -> company_id)

Note on FK constraints:
  SQLite does not enforce foreign keys by default (PRAGMA foreign_keys = OFF).
  After renaming holdings -> companies, any FK referencing holdings.id becomes
  a dangling reference. This is harmless in dev and will be fully resolved
  when the User model (active_holding_id) and user_company FK are updated
  in a follow-up step.

Migration order (to keep Alembic reflection happy):
  1. Drop old indexes from user_holdings
  2. user_holdings -> user_companies with column rename (holdings still exists)
  3. holdings -> companies (FKs become dangling, harmless)
  4. users table recreate
  5. Create indexes with new table name, drop stale old-named indexes

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Drop old indexes from user_holdings ---
    op.drop_index("ix_user_holdings_holding_id", table_name="user_holdings")
    op.drop_index("ix_user_holdings_user_id", table_name="user_holdings")

    # --- 2. user_holdings -> user_companies + column rename ---
    # holdings still exists → FK reference resolves during reflection.
    with op.batch_alter_table("user_holdings") as batch_op:
        batch_op.alter_column("holding_id", new_column_name="company_id")
    op.rename_table("user_holdings", "user_companies")

    # --- 3. holdings -> companies ---
    op.rename_table("holdings", "companies")

    # --- 4. Rename documents.holding_id -> company_id ---
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("holding_id", new_column_name="company_id")

    # --- 5. Rename users.active_holding_id -> active_company_id ---
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.alter_column("active_holding_id", new_column_name="active_company_id")

    # --- 6. Create indexes with new table name ---
    op.create_index(
        op.f("ix_user_companies_company_id"),
        "user_companies",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_companies_user_id"),
        "user_companies",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    # --- Reverse indexes ---
    op.drop_index(op.f("ix_user_companies_user_id"), table_name="user_companies")
    op.drop_index(op.f("ix_user_companies_company_id"), table_name="user_companies")

    # --- Reverse users.active_company_id -> active_holding_id ---
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.alter_column("active_company_id", new_column_name="active_holding_id")

    # --- Reverse documents.company_id -> holding_id ---
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("company_id", new_column_name="holding_id")

    # --- Reverse companies -> holdings ---
    op.rename_table("companies", "holdings")

    # --- Reverse user_companies -> user_holdings + column rename ---
    op.rename_table("user_companies", "user_holdings")
    with op.batch_alter_table("user_holdings") as batch_op:
        batch_op.alter_column("company_id", new_column_name="holding_id")

    # --- Restore old indexes ---
    op.create_index(
        op.f("ix_user_holdings_user_id"),
        "user_holdings",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_holdings_holding_id"),
        "user_holdings",
        ["holding_id"],
        unique=False,
    )
