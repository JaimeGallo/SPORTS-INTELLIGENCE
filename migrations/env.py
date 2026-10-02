"""Alembic environment. The URL comes from the caller (packages.storage.db) or DATABASE_URL."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine

from packages.storage.schema import metadata

config = context.config
url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
if not url:
    raise RuntimeError("no database URL: set DATABASE_URL")

engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
