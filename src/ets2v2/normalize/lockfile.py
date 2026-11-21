"""Deterministic canonical JSON I/O and 14d/30d staleness evaluation for state/prices.lock.json."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Final

from ets2v2.baseline.models import CountriesBaseline
from ets2v2.normalize.currencies import (
    BAM_FIXED_PEG_PER_EUR,
    EUROPEAN_TERRITORY_ISO2S,
    TERRITORY_CURRENCIES,
    VANILLA_SLUG_TO_ISO2,
)
from ets2v2.normalize.fuel import compute_secondary_grade_prices, round_local_price
from ets2v2.normalize.fx import round_eur_per_liter
from ets2v2.normalize.models import (
    CountryFuelLockEntry,
    FuelGrade,
    FxRateLockEntry,
    LockAlert,
    PricesLockfile,
)

TIER1_STALE_DAYS: Final[int] = 14
FALLBACK_STALE_DAYS: Final[int] = 30
BASELINE_SEEDED_SOURCE: Final[str] = "baseline_1.62_seeded"
BASELINE_SEEDED_LICENSE: Final[str] = "ETS2 1.62 baseline seed"

# Deterministic reference FX rates (1 EUR = X <CURRENCY>) within D-07 sanity bands for offline seed.
REFERENCE_FX_RATES: Final[dict[str, float]] = {
    "ALL": 98.5,
    "BAM": BAM_FIXED_PEG_PER_EUR,
    "CHF": 0.94,
    "CZK": 25.2,
    "DKK": 7.46,
    "EUR": 1.0,
    "GBP": 0.84,
    "HUF": 400.0,
    "ISK": 148.0,
    "MKD": 61.5,
    "NOK": 11.7,
    "PLN": 4.30,
    "RON": 4.97,
    "RSD": 117.1,
    "RUB": 95.0,
    "SEK": 11.4,
    "TRY": 36.5,
}

# Reference EU-27 diesel/petrol_95 EUR/L anchors for IE/CY/MT pre-warmed territories (D-04).
EXTRA_EU_SEED_EUR_PRICES: Final[dict[str, tuple[float, float]]] = {
    "CY": (1.520, 1.480),
    "IE": (1.740, 1.790),
    "MT": (1.210, 1.340),
}
_SEED_PETROL_TO_DIESEL_RATIO: Final[float] = 1.03


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
    """Atomically write ``PricesLockfile`` deterministically to ``path`` and return bytes."""
    raw = serialize_lockfile_bytes(lockfile)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_bytes(raw)
    os.replace(tmp_path, path)
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


def seed_initial_lockfile(
    baseline_countries: CountriesBaseline,
    slug_to_iso2: Mapping[str, str] | None = None,
    *,
    seed_date: str = "2026-11-20",
    updated_at: str = "2026-11-20T06:00:00Z",
) -> PricesLockfile:
    """Deterministically seed a 39-territory v1 lockfile from ETS2 1.62 baseline + reference FX."""
    mapping: Mapping[str, str] = slug_to_iso2 if slug_to_iso2 is not None else VANILLA_SLUG_TO_ISO2

    fx_rates: dict[str, FxRateLockEntry] = {}
    for currency in sorted(REFERENCE_FX_RATES):
        rate = REFERENCE_FX_RATES[currency]
        if currency == "EUR":
            provider = "pinned_eur"
            fallback_used = False
        elif currency == "BAM":
            provider = "cbbh_peg"
            fallback_used = True
        else:
            provider = "baseline_reference_fx"
            fallback_used = True
        fx_rates[currency] = FxRateLockEntry(
            currency=currency,
            rate_per_eur=rate,
            provider=provider,
            validator_provider=None,
            validator_rate_per_eur=None,
            divergence_pct=0.0,
            data_date=seed_date,
            fetched_at=updated_at,
            fallback_used=fallback_used,
        )

    baseline_eur_by_iso2: dict[str, float] = {}
    for country in baseline_countries.countries:
        iso2 = mapping.get(country.slug)
        if iso2 is None:
            continue
        if country.fuel_price is None:
            raise ValueError(f"Baseline country {country.slug!r} is missing fuel_price")
        baseline_eur_by_iso2[iso2] = round_eur_per_liter(country.fuel_price)

    countries: dict[str, CountryFuelLockEntry] = {}
    for iso2 in sorted(EUROPEAN_TERRITORY_ISO2S):
        currency = TERRITORY_CURRENCIES[iso2]
        rate = fx_rates[currency].rate_per_eur

        if iso2 in baseline_eur_by_iso2:
            diesel_eur = baseline_eur_by_iso2[iso2]
            petrol_95_eur = round_eur_per_liter(diesel_eur * _SEED_PETROL_TO_DIESEL_RATIO)
        elif iso2 in EXTRA_EU_SEED_EUR_PRICES:
            diesel_eur, petrol_95_eur = EXTRA_EU_SEED_EUR_PRICES[iso2]
        else:
            raise ValueError(f"Missing baseline fuel_price seed for territory {iso2!r}")

        anchor_local: dict[FuelGrade, float] = {
            "diesel": round_local_price(diesel_eur * rate),
            "petrol_95": round_local_price(petrol_95_eur * rate),
        }
        full_local_prices, derived_grades = compute_secondary_grade_prices(anchor_local)
        countries[iso2] = CountryFuelLockEntry(
            iso2=iso2,
            currency=currency,
            eur_per_liter=diesel_eur,
            local_prices=full_local_prices,
            derived_grades=derived_grades,
            source=BASELINE_SEEDED_SOURCE,
            license=BASELINE_SEEDED_LICENSE,
            data_date=seed_date,
            fetched_at=updated_at,
            fallback_used=True,
        )

    return PricesLockfile(
        schema_version=1,
        updated_at=updated_at,
        fx_rates=fx_rates,
        countries=countries,
        alerts=[],
    )
