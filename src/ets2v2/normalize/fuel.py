"""Pure offline fuel price bounds, +/-25% WoW circuit breaker, and D-02 secondary grade spreads."""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.normalize.currencies import TERRITORY_CURRENCIES
from ets2v2.normalize.fx import round_eur_per_liter
from ets2v2.normalize.models import (
    CANONICAL_FUEL_GRADES,
    CountryFuelLockEntry,
    FuelGrade,
    FxRateLockEntry,
    LockAlert,
)

MIN_EUR_PER_LITER: Final[float] = 0.01
MAX_EUR_PER_LITER: Final[float] = 5.00
MAX_WOW_JUMP_RATIO: Final[float] = 0.25

# Verified European secondary-grade market spread ratios over live petrol_95/diesel anchors (D-02).
SECONDARY_GRADE_SPREADS: Final[dict[FuelGrade, tuple[FuelGrade, float]]] = {
    "petrol_98": ("petrol_95", 1.06),
    "petrol_100": ("petrol_95", 1.12),
    "diesel_plus": ("diesel", 1.07),
    "petrol_92": ("petrol_95", 0.96),
    "e85": ("petrol_95", 0.72),
    "mpo": ("diesel", 0.75),
    "lpg": ("petrol_95", 0.48),
}

_ISO2_ALIASES: Final[dict[str, str]] = {
    "EL": "GR",
    "UK": "GB",
}
_FOUR_DP: Final[Decimal] = Decimal("0.0001")
_DEFAULT_PETROL_TO_DIESEL_RATIO: Final[Decimal] = Decimal("1.03")
_BASELINE_SEEDED_SOURCE: Final[str] = "baseline_1.62_seeded"


class FuelNormalizationResult(BaseModel):
    """Result of D-02/D-06 offline fuel normalization and circuit-breaker evaluation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    accepted: bool
    entry: CountryFuelLockEntry
    alerts: list[LockAlert] = Field(default_factory=list)


def normalize_iso2_alias(code: str) -> str:
    """Normalize Eurostat/UK alias codes (``EL -> GR``, ``UK -> GB``) to uppercase ISO-2."""
    cleaned = code.strip().upper()
    return _ISO2_ALIASES.get(cleaned, cleaned)


def round_local_price(value: float) -> float:
    """Round a positive native-currency pump price to 4 decimal places via Decimal ROUND_HALF_UP."""
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"local price must be finite and > 0.0, got {value!r}")
    quantized = Decimal(str(value)).quantize(_FOUR_DP, rounding=ROUND_HALF_UP)
    return float(quantized)


def compute_secondary_grade_prices(
    live_local_prices: Mapping[FuelGrade, float],
) -> tuple[dict[FuelGrade, float], list[FuelGrade]]:
    """Fill missing canonical grades using verified D-02 spreads without overwriting live grades."""
    if not live_local_prices:
        raise ValueError("live_local_prices must contain at least one anchor grade")

    prices: dict[FuelGrade, float] = {}
    for grade, raw_val in live_local_prices.items():
        if not math.isfinite(raw_val) or raw_val <= 0.0:
            raise ValueError(f"Invalid live price for grade {grade!r}: {raw_val!r}")
        prices[grade] = round_local_price(raw_val)

    derived: list[FuelGrade] = []
    if "diesel" not in prices and "petrol_95" not in prices:
        raise ValueError("live_local_prices must contain at least 'diesel' or 'petrol_95'")

    if "petrol_95" not in prices:
        diesel_dec = Decimal(str(prices["diesel"]))
        prices["petrol_95"] = float(
            (diesel_dec * _DEFAULT_PETROL_TO_DIESEL_RATIO).quantize(
                _FOUR_DP, rounding=ROUND_HALF_UP
            )
        )
        derived.append("petrol_95")
    elif "diesel" not in prices:
        p95_dec = Decimal(str(prices["petrol_95"]))
        prices["diesel"] = float(
            (p95_dec / _DEFAULT_PETROL_TO_DIESEL_RATIO).quantize(_FOUR_DP, rounding=ROUND_HALF_UP)
        )
        derived.append("diesel")

    for grade in CANONICAL_FUEL_GRADES:
        if grade in prices:
            continue
        spread = SECONDARY_GRADE_SPREADS.get(grade)
        if spread is None:
            continue
        anchor_grade, multiplier = spread
        anchor_dec = Decimal(str(prices[anchor_grade]))
        computed = (anchor_dec * Decimal(str(multiplier))).quantize(
            _FOUR_DP, rounding=ROUND_HALF_UP
        )
        prices[grade] = float(computed)
        derived.append(grade)

    ordered_prices: dict[FuelGrade, float] = {
        grade: prices[grade] for grade in CANONICAL_FUEL_GRADES if grade in prices
    }
    sorted_derived = sorted(derived)
    return ordered_prices, sorted_derived


def _hold_previous(
    previous_entry: CountryFuelLockEntry | None,
    alerts: list[LockAlert],
    *,
    fallback_error: str,
) -> FuelNormalizationResult:
    if previous_entry is None:
        raise ValueError(fallback_error)
    held = previous_entry.model_copy(update={"fallback_used": True})
    return FuelNormalizationResult(accepted=False, entry=held, alerts=alerts)


def normalize_country_fuel_prices(
    iso2: str,
    *,
    live_local_prices: Mapping[FuelGrade, float],
    source: str,
    license_name: str,
    data_date: str,
    fx_entry: FxRateLockEntry,
    previous_entry: CountryFuelLockEntry | None,
    allow_jump_iso2: frozenset[str],
    fetched_at: str,
    is_fallback: bool = False,
) -> FuelNormalizationResult:
    """Enforce D-06 hard bounds (0.01-5.00 EUR/L), +/-25% WoW circuit breaker, and D-02 spreads."""
    canonical_iso2 = normalize_iso2_alias(iso2)
    expected_currency = TERRITORY_CURRENCIES.get(canonical_iso2)
    if expected_currency is None:
        raise ValueError(f"Unknown European territory ISO-2 code: {iso2!r}")
    if fx_entry.currency != expected_currency:
        raise ValueError(
            f"FX currency mismatch for {canonical_iso2}: expected {expected_currency!r}, "
            f"got {fx_entry.currency!r}"
        )

    alerts: list[LockAlert] = []
    if not live_local_prices:
        alerts.append(
            LockAlert(
                severity="warning",
                code="price_feed_missing",
                scope=canonical_iso2,
                detail=f"No live fuel prices provided for {canonical_iso2}; retaining lockfile.",
            )
        )
        return _hold_previous(
            previous_entry,
            alerts,
            fallback_error=(
                f"No live fuel prices and no previous lockfile entry for {canonical_iso2}"
            ),
        )

    rate = fx_entry.rate_per_eur
    # Step 1: Hard bounds [0.01, 5.00] EUR/L equivalent on every live grade (NEVER bypassed).
    for grade, local_val in sorted(live_local_prices.items()):
        if not math.isfinite(local_val) or local_val <= 0.0:
            alerts.append(
                LockAlert(
                    severity="error",
                    code="price_bounds_rejected",
                    scope=canonical_iso2,
                    detail=(
                        f"Rejected non-finite/non-positive {grade} price {local_val!r} "
                        f"for {canonical_iso2} from {source}."
                    ),
                )
            )
            return _hold_previous(
                previous_entry,
                alerts,
                fallback_error=f"Invalid {grade} price {local_val!r} for {canonical_iso2}",
            )

        eur_equiv = local_val / rate
        if not (MIN_EUR_PER_LITER <= eur_equiv <= MAX_EUR_PER_LITER):
            alerts.append(
                LockAlert(
                    severity="error",
                    code="price_bounds_rejected",
                    scope=canonical_iso2,
                    detail=(
                        f"Rejected {grade} price for {canonical_iso2} from {source}: "
                        f"{local_val} {fx_entry.currency}/L ({eur_equiv:.4f} EUR/L) outside "
                        f"[{MIN_EUR_PER_LITER:.2f}, {MAX_EUR_PER_LITER:.2f}] EUR/L hard bounds."
                    ),
                )
            )
            return _hold_previous(
                previous_entry,
                alerts,
                fallback_error=(
                    f"Out-of-bounds {grade} price ({eur_equiv:.4f} EUR/L) for {canonical_iso2}"
                ),
            )

    full_local_prices, derived_grades = compute_secondary_grade_prices(live_local_prices)
    diesel_local_for_eur = live_local_prices.get("diesel", full_local_prices["diesel"])
    diesel_eur = round_eur_per_liter(diesel_local_for_eur / rate)
    if not (MIN_EUR_PER_LITER <= diesel_eur <= MAX_EUR_PER_LITER):
        alerts.append(
            LockAlert(
                severity="error",
                code="price_bounds_rejected",
                scope=canonical_iso2,
                detail=(
                    f"Rejected diesel EUR/L {diesel_eur:.3f} for {canonical_iso2} outside "
                    f"[{MIN_EUR_PER_LITER:.2f}, {MAX_EUR_PER_LITER:.2f}] EUR/L hard bounds."
                ),
            )
        )
        return _hold_previous(
            previous_entry,
            alerts,
            fallback_error=f"Out-of-bounds diesel EUR/L {diesel_eur} for {canonical_iso2}",
        )

    # Step 2: +/-25% week-over-week circuit breaker against previous live lockfile entry (D-06).
    # Initial baseline_1.62_seeded entries are bootstrap placeholders (still hard-bounds protected
    # above) and transition cleanly to the first live feed without false WoW rejections.
    normalized_allow = {normalize_iso2_alias(code) for code in allow_jump_iso2}
    if previous_entry is not None and previous_entry.source != _BASELINE_SEEDED_SOURCE:
        jump_violations: list[str] = []
        prev_eur = previous_entry.eur_per_liter
        eur_delta_ratio = abs(diesel_eur - prev_eur) / prev_eur
        if eur_delta_ratio > MAX_WOW_JUMP_RATIO:
            jump_violations.append(
                f"diesel EUR/L {prev_eur:.3f} -> {diesel_eur:.3f} ({eur_delta_ratio * 100.0:.1f}%)"
            )
        for grade in sorted(live_local_prices):
            prev_local = previous_entry.local_prices.get(grade)
            if prev_local is None or prev_local <= 0.0:
                continue
            new_local = full_local_prices[grade]
            local_ratio = abs(new_local - prev_local) / prev_local
            if local_ratio > MAX_WOW_JUMP_RATIO:
                jump_violations.append(
                    f"{grade} local {prev_local} -> {new_local} {fx_entry.currency} "
                    f"({local_ratio * 100.0:.1f}%)"
                )

        if jump_violations:
            summary = "; ".join(jump_violations)
            if canonical_iso2 in normalized_allow:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="price_jump_override_accepted",
                        scope=canonical_iso2,
                        detail=(
                            f"Accepted >25% WoW price change for {canonical_iso2} via "
                            f"--allow-jump override: {summary}."
                        ),
                    )
                )
            else:
                alerts.append(
                    LockAlert(
                        severity="error",
                        code="price_jump_rejected",
                        scope=canonical_iso2,
                        detail=(
                            f"Rejected >25% WoW price jump for {canonical_iso2} from {source}: "
                            f"{summary}. Pass --allow-jump {canonical_iso2} to accept."
                        ),
                    )
                )
                return _hold_previous(
                    previous_entry,
                    alerts,
                    fallback_error=f"Price jump rejected for {canonical_iso2}: {summary}",
                )

    entry = CountryFuelLockEntry(
        iso2=canonical_iso2,
        currency=fx_entry.currency,
        eur_per_liter=diesel_eur,
        local_prices=full_local_prices,
        derived_grades=derived_grades,
        source=source,
        license=license_name,
        data_date=data_date,
        fetched_at=fetched_at,
        fallback_used=is_fallback,
    )
    return FuelNormalizationResult(accepted=True, entry=entry, alerts=alerts)
