"""Strict frozen Pydantic v2 DTOs for online FX and fuel fetching."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ets2_realism.normalize.models import FuelGrade, LockAlert

_ISO2_PATTERN: Final[str] = r"^[A-Z]{2}$"
_ISO4217_PATTERN: Final[str] = r"^[A-Z]{3}$"
_ISO_DATE_PATTERN: Final[str] = r"^\d{4}-\d{2}-\d{2}$"


def _validate_calendar_date(value: str) -> str:
    date.fromisoformat(value)
    return value


class RawFxProviderQuote(BaseModel):
    """Raw parsed FX rates returned by one upstream FX provider."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    data_date: str = Field(pattern=_ISO_DATE_PATTERN)
    rates: dict[str, float]

    @field_validator("data_date")
    @classmethod
    def _validate_data_date(cls, value: str) -> str:
        return _validate_calendar_date(value)


class ProviderFetchStatus(BaseModel):
    """Structured outcome for a single upstream FX or fuel feed attempt."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    ok: bool
    detail: str | None = None
    data_date: str | None = None

    @field_validator("data_date")
    @classmethod
    def _validate_data_date(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_calendar_date(value)
        return value


class FxFetchBundle(BaseModel):
    """Aggregated quotes and per-provider status reports from all FX providers."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    quotes: dict[str, RawFxProviderQuote]
    statuses: list[ProviderFetchStatus]


class RawCountryFuelQuote(BaseModel):
    """Raw parsed fuel prices for one country from an upstream Tier 1 or fallback feed."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=_ISO2_PATTERN)
    currency: str = Field(pattern=_ISO4217_PATTERN)
    prices_by_grade: dict[FuelGrade, float]
    unit_basis: Literal["eur_per_liter", "local_per_liter"]
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    data_date: str = Field(pattern=_ISO_DATE_PATTERN)

    @field_validator("data_date")
    @classmethod
    def _validate_data_date(cls, value: str) -> str:
        return _validate_calendar_date(value)


class RawFuelFeedResult(BaseModel):
    """Isolated fetch outcome for one upstream fuel feed collector."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    feed_name: str = Field(min_length=1)
    tier: Literal["tier1", "tier2", "fallback"]
    region_scope: Literal["eu_core", "global"] = "eu_core"
    ok: bool
    skipped: bool = False
    skip_reason: str | None = None
    error_code: str | None = None
    quotes: list[RawCountryFuelQuote] = Field(default_factory=list)
    error: str | None = None
    data_date: str | None = None

    @field_validator("data_date")
    @classmethod
    def _validate_data_date(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_calendar_date(value)
        return value


class FetchRunReport(BaseModel):
    """Machine-readable report emitted by ``ets2-realism fetch`` (supports ``--json``)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ok: bool
    fx_only: bool
    dry_run: bool
    lock_path: Path
    tier1_feeds_succeeded: int = Field(ge=0)
    tier1_feeds_failed: int = Field(ge=0)
    eu_tier1_feeds_succeeded: int = Field(default=0, ge=0)
    eu_tier1_feeds_failed: int = Field(default=0, ge=0)
    global_tier1_feeds_succeeded: int = Field(default=0, ge=0)
    global_tier1_feeds_failed: int = Field(default=0, ge=0)
    tier2_feeds_succeeded: int = Field(default=0, ge=0)
    tier2_feeds_failed: int = Field(default=0, ge=0)
    countries_updated: int = Field(ge=0)
    countries_fallback: int = Field(ge=0)
    fx_currencies_validated: int = Field(ge=0)
    alerts: list[LockAlert] = Field(default_factory=list)
    provider_statuses: list[ProviderFetchStatus] = Field(default_factory=list)
