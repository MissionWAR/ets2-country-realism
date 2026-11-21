"""Strict frozen Pydantic v2 domain models for Phase 3 fuel/FX normalization and prices lockfile."""

from __future__ import annotations

import math
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FuelGrade = Literal[
    "diesel",
    "diesel_plus",
    "petrol_95",
    "petrol_98",
    "petrol_100",
    "petrol_92",
    "e85",
    "lpg",
    "mpo",
]

CANONICAL_FUEL_GRADES: Final[tuple[FuelGrade, ...]] = (
    "diesel",
    "diesel_plus",
    "petrol_95",
    "petrol_98",
    "petrol_100",
    "petrol_92",
    "e85",
    "lpg",
    "mpo",
)

AlertSeverity = Literal["warning", "error"]

_ISO2_PATTERN: Final[str] = r"^[A-Z]{2}$"
_ISO4217_PATTERN: Final[str] = r"^[A-Z]{3}$"
_ISO_DATE_PATTERN: Final[str] = r"^\d{4}-\d{2}-\d{2}$"


class FxRateLockEntry(BaseModel):
    """Validated FX exchange rate entry (1 EUR = rate_per_eur <currency>) in prices.lock.json."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    currency: str = Field(pattern=_ISO4217_PATTERN)
    rate_per_eur: float = Field(gt=0.0, allow_inf_nan=False)
    provider: str = Field(min_length=1)
    validator_provider: str | None = None
    validator_rate_per_eur: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)
    divergence_pct: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    data_date: str = Field(pattern=_ISO_DATE_PATTERN)
    fetched_at: str = Field(min_length=1)
    fallback_used: bool = False


class CountryFuelLockEntry(BaseModel):
    """Canonical locked fuel price entry for one European territory in state/prices.lock.json."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=_ISO2_PATTERN)
    currency: str = Field(pattern=_ISO4217_PATTERN)
    eur_per_liter: float = Field(ge=0.01, le=5.00, allow_inf_nan=False)
    local_prices: dict[FuelGrade, float] = Field(default_factory=dict)
    derived_grades: list[FuelGrade] = Field(default_factory=list)
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    data_date: str = Field(pattern=_ISO_DATE_PATTERN)
    fetched_at: str = Field(min_length=1)
    fallback_used: bool = False

    @field_validator("local_prices")
    @classmethod
    def _validate_local_prices(cls, value: dict[FuelGrade, float]) -> dict[FuelGrade, float]:
        for grade, price in value.items():
            if not math.isfinite(price) or price <= 0.0:
                raise ValueError(f"local_prices[{grade!r}] must be finite and > 0.0, got {price!r}")
        return value


class LockAlert(BaseModel):
    """Structured FX, circuit-breaker, outage, or staleness alert persisted in prices.lock.json."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    severity: AlertSeverity
    code: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class PricesLockfile(BaseModel):
    """Schema version 1 canonical lockfile stored at state/prices.lock.json (D-04, D-05, D-13)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    updated_at: str = Field(min_length=1)
    fx_rates: dict[str, FxRateLockEntry]
    countries: dict[str, CountryFuelLockEntry]
    alerts: list[LockAlert] = Field(default_factory=list)


class NormalizedCurrencyPrice(BaseModel):
    """Typed pair separating 3-decimal EUR/L .sui pricing from native local pump pricing (D-15)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    currency: str = Field(pattern=_ISO4217_PATTERN)
    eur_per_liter: float = Field(gt=0.0, allow_inf_nan=False)
    local_display_price: float = Field(gt=0.0, allow_inf_nan=False)
    rate_per_eur: float = Field(gt=0.0, allow_inf_nan=False)
