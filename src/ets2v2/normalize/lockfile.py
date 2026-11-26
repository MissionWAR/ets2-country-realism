"""Deterministic canonical JSON I/O and 14d/30d staleness evaluation for state/prices.lock.json."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Final

from ets2v2.baseline.models import CountriesBaseline
from ets2v2.normalize.currencies import (
    ALL_LOCKFILE_TERRITORY_ISO2S,
    ALL_REFERENCE_FX_RATES,
    ALL_TERRITORY_CURRENCIES,
    CORE_REFERENCE_FX_RATES,
    EXTENDED_GLOBAL_CURRENCIES,
    EXTENDED_PROMODS_CURRENCIES,
    PROMODS_EXTENDED_ISO2S,
    TIER3_CURATED_BASELINE_LICENSE,
    TIER3_CURATED_BASELINE_SOURCE,
    VANILLA_SLUG_TO_ISO2,
    load_tier3_fuel_baselines,
)
from ets2v2.normalize.fuel import (
    SEEDED_LOCKFILE_SOURCES,
    compute_secondary_grade_prices,
    round_local_price,
)
from ets2v2.normalize.fx import round_eur_per_liter
from ets2v2.normalize.models import (
    CountryFuelLockEntry,
    FuelGrade,
    FxRateLockEntry,
    LockAlert,
    PricesLockfile,
)

TIER1_STALE_DAYS: Final[int] = 14
TIER2_MONTHLY_STALE_DAYS: Final[int] = 45
TIER2_QUARTERLY_STALE_DAYS: Final[int] = 105
FALLBACK_STALE_DAYS: Final[int] = 30
TIER3_CURATED_STALE_DAYS: Final[int] = 180
BASELINE_SEEDED_SOURCE: Final[str] = "baseline_1.62_seeded"
BASELINE_SEEDED_LICENSE: Final[str] = "ETS2 1.62 baseline seed"
PROMODS_CURATED_SEED_SOURCE: Final[str] = "promods_curated_seed"
PROMODS_CURATED_SEED_LICENSE: Final[str] = "ProMods curated reference seed"
CURATED_TIER3_SOURCES: Final[frozenset[str]] = frozenset(
    {TIER3_CURATED_BASELINE_SOURCE, PROMODS_CURATED_SEED_SOURCE}
)

MONTHLY_LIVE_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "no_ssb_09654",
        "co_sicom",
        "co_creg",
        "ch_bfs_lik",
        "mk_erc",
        "il_moe",
        "ae_moei",
        "za_dmre_cef",
        "sa_aramco",
        "ng_nbs",
    }
)
QUARTERLY_TIER2_SOURCES: Final[frozenset[str]] = frozenset({"eg_fapc"})

# Deterministic Core reference FX rates (1 EUR = X <CURRENCY>) for backwards compatibility.
REFERENCE_FX_RATES: Final[dict[str, float]] = CORE_REFERENCE_FX_RATES

# Reference EU-27 diesel/petrol_95 EUR/L anchors for IE/CY/MT pre-warmed territories (D-04).
EXTRA_EU_SEED_EUR_PRICES: Final[dict[str, tuple[float, float]]] = {
    "CY": (1.520, 1.480),
    "IE": (1.740, 1.790),
    "MT": (1.210, 1.340),
}
_SEED_PETROL_TO_DIESEL_RATIO: Final[float] = 1.03
_SEEDED_SOURCES: Final[frozenset[str]] = SEEDED_LOCKFILE_SOURCES


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
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(raw)
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise
    return raw


def evaluate_lockfile_staleness(lockfile: PricesLockfile, as_of_date: date) -> list[LockAlert]:
    """Evaluate D-08 tier/cadence-aware staleness limits (14d/45d/105d/30d/180d)."""
    alerts: list[LockAlert] = []
    for iso2 in sorted(lockfile.countries):
        entry = lockfile.countries[iso2]
        entry_date = date.fromisoformat(entry.data_date)
        age_days = (as_of_date - entry_date).days

        if entry.source in CURATED_TIER3_SOURCES:
            if age_days > TIER3_CURATED_STALE_DAYS:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="stale_tier3_curated",
                        scope=iso2,
                        detail=(
                            f"Tier 3 curated baseline for {iso2} ({entry.source}) is "
                            f"{age_days} days old (data_date={entry.data_date}, "
                            f"limit={TIER3_CURATED_STALE_DAYS}d)."
                        ),
                    )
                )
        elif entry.fallback_used or entry.source == BASELINE_SEEDED_SOURCE:
            if entry.source in QUARTERLY_TIER2_SOURCES:
                fallback_limit = max(FALLBACK_STALE_DAYS, TIER2_QUARTERLY_STALE_DAYS)
            elif entry.source in MONTHLY_LIVE_SOURCES:
                fallback_limit = max(FALLBACK_STALE_DAYS, TIER2_MONTHLY_STALE_DAYS)
            else:
                fallback_limit = FALLBACK_STALE_DAYS
            if age_days > fallback_limit:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="stale_fallback",
                        scope=iso2,
                        detail=(
                            f"Fallback/seeded fuel entry for {iso2} ({entry.source}) is "
                            f"{age_days} days old (data_date={entry.data_date}, "
                            f"limit={fallback_limit}d)."
                        ),
                    )
                )
        elif entry.source in QUARTERLY_TIER2_SOURCES:
            if age_days > TIER2_QUARTERLY_STALE_DAYS:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="stale_tier2_quarterly",
                        scope=iso2,
                        detail=(
                            f"Quarterly Tier 2 fuel entry for {iso2} ({entry.source}) is "
                            f"{age_days} days old (data_date={entry.data_date}, "
                            f"limit={TIER2_QUARTERLY_STALE_DAYS}d)."
                        ),
                    )
                )
        elif entry.source in MONTHLY_LIVE_SOURCES:
            if age_days > TIER2_MONTHLY_STALE_DAYS:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="stale_tier2_monthly",
                        scope=iso2,
                        detail=(
                            f"Monthly fuel entry for {iso2} ({entry.source}) is "
                            f"{age_days} days old (data_date={entry.data_date}, "
                            f"limit={TIER2_MONTHLY_STALE_DAYS}d)."
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
    seed_date: str | None = None,
    updated_at: str = "2026-11-20T06:00:00Z",
) -> PricesLockfile:
    """Deterministically seed a 225-territory global v1 lockfile from 1.62 baseline + Tier 3."""
    mapping: Mapping[str, str] = slug_to_iso2 if slug_to_iso2 is not None else VANILLA_SLUG_TO_ISO2
    tier3_baselines = load_tier3_fuel_baselines().baselines
    effective_seed_date = seed_date if seed_date is not None else "2026-11-20"

    fx_rates: dict[str, FxRateLockEntry] = {}
    for currency in sorted(ALL_REFERENCE_FX_RATES):
        rate = ALL_REFERENCE_FX_RATES[currency]
        if currency == "EUR":
            provider = "pinned_eur"
            fallback_used = False
        elif currency == "BAM":
            provider = "cbbh_peg"
            fallback_used = True
        elif currency in EXTENDED_PROMODS_CURRENCIES:
            provider = "promods_reference_fx"
            fallback_used = True
        elif currency in EXTENDED_GLOBAL_CURRENCIES:
            provider = "global_reference_fx"
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
            data_date=effective_seed_date,
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
    for iso2 in sorted(ALL_LOCKFILE_TERRITORY_ISO2S):
        currency = ALL_TERRITORY_CURRENCIES[iso2]
        rate = fx_rates[currency].rate_per_eur

        if iso2 in baseline_eur_by_iso2:
            diesel_eur = baseline_eur_by_iso2[iso2]
            petrol_95_eur = round_eur_per_liter(diesel_eur * _SEED_PETROL_TO_DIESEL_RATIO)
            source_name = BASELINE_SEEDED_SOURCE
            license_name = BASELINE_SEEDED_LICENSE
            entry_data_date = effective_seed_date
        elif iso2 in EXTRA_EU_SEED_EUR_PRICES:
            diesel_eur, petrol_95_eur = EXTRA_EU_SEED_EUR_PRICES[iso2]
            source_name = BASELINE_SEEDED_SOURCE
            license_name = BASELINE_SEEDED_LICENSE
            entry_data_date = effective_seed_date
        elif iso2 in tier3_baselines:
            t3_entry = tier3_baselines[iso2]
            diesel_eur = round_eur_per_liter(t3_entry.diesel_eur_per_liter)
            petrol_95_eur = round_eur_per_liter(t3_entry.petrol_95_eur_per_liter)
            if iso2 in PROMODS_EXTENDED_ISO2S:
                source_name = PROMODS_CURATED_SEED_SOURCE
                license_name = PROMODS_CURATED_SEED_LICENSE
            else:
                source_name = TIER3_CURATED_BASELINE_SOURCE
                license_name = TIER3_CURATED_BASELINE_LICENSE
            entry_data_date = seed_date if seed_date is not None else t3_entry.verified_date
        else:
            raise ValueError(f"Missing fuel_price seed for territory {iso2!r}")

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
            source=source_name,
            license=license_name,
            data_date=entry_data_date,
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
