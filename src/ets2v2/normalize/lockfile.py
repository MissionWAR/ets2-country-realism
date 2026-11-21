"""Deterministic canonical JSON I/O and 14d/30d staleness evaluation for state/prices.lock.json."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Final

from ets2v2.normalize.models import LockAlert, PricesLockfile

TIER1_STALE_DAYS: Final[int] = 14
FALLBACK_STALE_DAYS: Final[int] = 30
BASELINE_SEEDED_SOURCE: Final[str] = "baseline_1.62_seeded"


def serialize_lockfile_bytes(lockfile: PricesLockfile) -> bytes:
    """Serialize ``PricesLockfile`` to canonical UTF-8 no-BOM LF sorted JSON bytes."""
    payload: object = lockfile.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def load_prices_lockfile(path: Path) -> PricesLockfile:
    """Load and strictly validate a ``state/prices.lock.json`` v1 lockfile."""
    if not path.is_file():
        raise FileNotFoundError(f"Prices lockfile does not exist: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"Prices lockfile must not contain a UTF-8 BOM: {path}")
    if b"\r" in raw:
        raise ValueError(f"Prices lockfile must use LF line endings only: {path}")
    return PricesLockfile.model_validate_json(raw.decode("utf-8"))


def write_prices_lockfile(lockfile: PricesLockfile, path: Path) -> bytes:
    """Write ``PricesLockfile`` deterministically to ``path`` and return serialized bytes."""
    raw = serialize_lockfile_bytes(lockfile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def evaluate_lockfile_staleness(lockfile: PricesLockfile, as_of_date: date) -> list[LockAlert]:
    """Evaluate D-08 staleness thresholds (>14d Tier 1, >30d fallback/seeded) across countries."""
    alerts: list[LockAlert] = []
    for iso2 in sorted(lockfile.countries):
        entry = lockfile.countries[iso2]
        entry_date = date.fromisoformat(entry.data_date)
        age_days = (as_of_date - entry_date).days
        is_fallback = entry.fallback_used or entry.source == BASELINE_SEEDED_SOURCE
        if is_fallback:
            if age_days > FALLBACK_STALE_DAYS:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="stale_fallback",
                        scope=iso2,
                        detail=(
                            f"Fallback/seeded fuel entry for {iso2} ({entry.source}) is "
                            f"{age_days} days old (data_date={entry.data_date}, "
                            f"limit={FALLBACK_STALE_DAYS}d)."
                        ),
                    )
                )
        elif age_days > TIER1_STALE_DAYS:
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="stale_tier1",
                    scope=iso2,
                    detail=(
                        f"Tier 1 fuel entry for {iso2} ({entry.source}) is {age_days} days old "
                        f"(data_date={entry.data_date}, limit={TIER1_STALE_DAYS}d)."
                    ),
                )
            )
    return alerts
