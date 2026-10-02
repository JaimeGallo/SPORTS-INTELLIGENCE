"""Identifier helpers.

Adapted from JEV Trading (JaimeGallo/Multi-broker, packages/common), see ADR-0004.

Canonical entity ids and prediction ids are DETERMINISTIC: the same inputs always produce the same id, so
re-running an ingestion or a backtest regenerates identical ids instead of duplicating rows.
"""

from __future__ import annotations

import hashlib
import secrets
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _base32(data: bytes, length: int) -> str:
    number = int.from_bytes(data, "big")
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[number & 31])
        number >>= 5
    return "".join(reversed(chars))


def digest(*parts: object, length: int = 10) -> str:
    """Stable short hash of the given parts (Crockford base32)."""
    raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return _base32(hashlib.sha256(raw).digest(), length)


def new_id(prefix: str) -> str:
    """Random, roughly time-sortable id for records that need no determinism (runs)."""
    millis = int(time.time() * 1000).to_bytes(6, "big")
    return f"{prefix}_{_base32(millis + secrets.token_bytes(10), 26)}"


def canonical_id(entity_type: str, *natural_key: object) -> str:
    """Deterministic canonical id, e.g. canonical_id('team', 'ENG', 'Arsenal') -> 'team_XXXXXXXXXXXX'."""
    return f"{entity_type}_{digest(entity_type, *natural_key, length=12)}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
