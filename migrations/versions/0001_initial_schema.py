"""Initial schema (EXP-001a).

Revision ID: 0001
Revises:
The first revision materialises packages/storage/schema.py as of this commit. Later revisions must be
explicit `op.*` migrations, never create_all.
"""

from alembic import op

from packages.storage.schema import metadata

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    metadata.drop_all(op.get_bind())
