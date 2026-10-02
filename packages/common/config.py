"""Validated configuration.

Adapted from JEV Trading (JaimeGallo/Multi-broker, packages/common), see ADR-0004.

Precedence: config/default.yaml < profile file < env vars JEVS__SECTION__KEY < explicit overrides.
The schema is strict (`extra="forbid"`): a misspelled key is an error, never a silently ignored value.
Secrets are NOT part of this model; they are read from the environment only (see packages.common.secrets).
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.common.errors import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"
ENV_PREFIX = "JEVS__"


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class AppSection(Section):
    name: str = "jev-sports-intelligence"
    environment: str = "local"


class DatabaseSection(Section):
    url: str = "postgresql+psycopg://postgres@127.0.0.1:5432/jevs"


class CompetitionConfig(Section):
    competition_key: str  # stable canonical key, e.g. 'ENG-PL'
    name: str
    country: str
    enabled: bool = True
    football_data_div: str | None = None  # football-data.co.uk division code (E0, SP1, ...)


class IngestionSection(Section):
    raw_dir: str = "data/raw"
    manifests_dir: str = "data/manifests"
    provider_timezone: str = "Europe/London"  # football-data.co.uk dates/times are UK local time
    # Point-in-time rules (ADR-0003). Conservative estimates of when a fact became knowable.
    result_delay_hours: float = Field(default=3.0, gt=0)
    unknown_kickoff_local_time: str = "23:59"  # used when the source has no kickoff time
    prematch_odds_lead_hours: float = Field(default=24.0, gt=0)


class PredictionSection(Section):
    lead_minutes: int = Field(default=60, ge=0)  # as_of = kickoff - lead


class LoggingSection(Section):
    level: str = "INFO"
    json_format: bool = False


class AppConfig(Section):
    app: AppSection = Field(default_factory=AppSection)
    database: DatabaseSection = Field(default_factory=DatabaseSection)
    competitions: list[CompetitionConfig] = Field(default_factory=list)
    ingestion: IngestionSection = Field(default_factory=IngestionSection)
    prediction: PredictionSection = Field(default_factory=PredictionSection)
    logging: LoggingSection = Field(default_factory=LoggingSection)

    def enabled_competitions(self) -> list[CompetitionConfig]:
        return [c for c in self.competitions if c.enabled]


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def env_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    """Translate JEVS__SECTION__KEY=value variables into a nested mapping (values parsed as YAML scalars)."""
    result: dict[str, Any] = {}
    for name, raw in environ.items():
        if not name.startswith(ENV_PREFIX):
            continue
        path = [part.lower() for part in name[len(ENV_PREFIX) :].split("__") if part]
        if not path:
            continue
        cursor = result
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = yaml.safe_load(raw) if raw != "" else None
    return result


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain a mapping: {path}")
    return data


def load_config(
    path: str | Path | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    env = os.environ if environ is None else environ
    data: dict[str, Any] = read_yaml(DEFAULT_CONFIG_PATH) if DEFAULT_CONFIG_PATH.exists() else {}
    if path is not None:
        data = deep_merge(data, read_yaml(Path(path)))
    data = deep_merge(data, env_overrides(env))
    if env.get("DATABASE_URL"):
        data = deep_merge(data, {"database": {"url": env["DATABASE_URL"]}})
    if overrides:
        data = deep_merge(data, overrides)
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid configuration:\n{exc}") from exc


def config_hash(config: BaseModel) -> str:
    """Stable fingerprint of a configuration (recorded with every run)."""
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
