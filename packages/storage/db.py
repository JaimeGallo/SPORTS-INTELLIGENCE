"""Database engine helpers."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, create_engine

from packages.common.config import PROJECT_ROOT
from packages.common.secrets import redact_url


def make_engine(url: str) -> Engine:
    return create_engine(url, future=True, pool_pre_ping=True)


def alembic_config(url: str) -> AlembicConfig:
    cfg = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(PROJECT_ROOT / "migrations")))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade(url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(url), revision)


def describe(url: str) -> str:
    return redact_url(url) or ""
