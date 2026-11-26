"""Pure offline FX cross-validation, currency-split guards, and 3-decimal EUR/L conversion."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ets2_realism.normalize.currencies import (
    ALL_CURRENCY_SANITY_BANDS,
    ALL_REFERENCE_FX_RATES,
    BAM_FIXED_PEG_PER_EUR,
    CURRENCY_SANITY_BANDS,
    ECB_COVERED_CURRENCIES,
    EXTENDED_ECB_CURRENCIES,
    EXTENDED_GLOBAL_CURRENCIES,
    EXTENDED_PROMODS_CURRENCIES,
    MAJOR_ECB_CURRENCIES,
    TERRITORY_CURRENCIES,
)
from ets2_realism.normalize.models import FxRateLockEntry, LockAlert, NormalizedCurrencyPrice

MAJOR_DIVERGENCE_WARN_PCT: Final[float] = 2.0
VOLATILE_DIVERGENCE_WARN_PCT: Final[float] = 5.0
DIVERGENCE_REJECT_PCT: Final[float] = 10.0

PRIMARY_FX_PROVIDER: Final[str] = "frankfurter_v2"
ECB_FX_PROVIDER: Final[str] = "ecb_xml"
FAWAZ_FX_PROVIDER: Final[str] = "fawazahmed0"
CBR_FX_PROVIDER: Final[str] = "cbr_xml"

_THREE_DP: Final[Decimal] = Decimal("0.001")
_REQUIRED_NON_EUR_CURRENCIES: Final[tuple[str, ...]] = tuple(sorted(CURRENCY_SANITY_BANDS))
_OPTIONAL_EXTENDED_CURRENCIES: Final[tuple[str, ...]] = tuple(sorted(EXTENDED_GLOBAL_CURRENCIES))
_ALL_ECB_COVERED: Final[frozenset[str]] = ECB_COVERED_CURRENCIES | EXTENDED_ECB_CURRENCIES
_ALL_MAJOR_ECB: Final[frozenset[str]] = MAJOR_ECB_CURRENCIES | EXTENDED_ECB_CURRENCIES


class FxProviderQuote(BaseModel):
    """Unvalidated provider FX snapshot passed into offline cross-validation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    data_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    rates: dict[str, float]

    @field_validator("data_date")
    @classmethod
    def _validate_data_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value


class FxValidationResult(BaseModel):
    """Outcome of D-07 multi-provider FX cross-validation across European + optional extended FX."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ok: bool
    rates: dict[str, FxRateLockEntry]
    alerts: list[LockAlert] = Field(default_factory=list)
    missing_currencies: list[str] = Field(default_factory=list)


def round_eur_per_liter(value: float) -> float:
    """Round a EUR/L price to 3 decimal places using exact Decimal ROUND_HALF_UP (D-15)."""
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"eur_per_liter must be finite and > 0.0, got {value!r}")
    quantized = Decimal(str(value)).quantize(_THREE_DP, rounding=ROUND_HALF_UP)
    if quantized <= 0:
        raise ValueError(f"eur_per_liter {value!r} underflows to 0.000 after 3-decimal rounding")
    return float(quantized)


def convert_local_to_eur_and_local(
    local_price: float,
    currency: str,
    rate_per_eur: float,
) -> NormalizedCurrencyPrice:
    """Convert a native currency/L pump price into 3-decimal EUR/L and typed local display price."""
    if not math.isfinite(local_price) or local_price <= 0.0:
        raise ValueError(f"local_price must be finite and > 0.0, got {local_price!r}")
    if not math.isfinite(rate_per_eur) or rate_per_eur <= 0.0:
        raise ValueError(f"rate_per_eur must be finite and > 0.0, got {rate_per_eur!r}")
    eur_price = round_eur_per_liter(local_price / rate_per_eur)
    return NormalizedCurrencyPrice(
        currency=currency,
        eur_per_liter=eur_price,
        local_display_price=local_price,
        rate_per_eur=rate_per_eur,
    )


def _compute_divergence_pct_decimal(rate_a: float, rate_b: float) -> Decimal:
    if not math.isfinite(rate_a) or rate_a <= 0.0:
        raise ValueError(f"rate_a must be finite and > 0.0, got {rate_a!r}")
    if not math.isfinite(rate_b) or rate_b <= 0.0:
        raise ValueError(f"rate_b must be finite and > 0.0, got {rate_b!r}")
    da = Decimal(str(rate_a))
    db = Decimal(str(rate_b))
    return (abs(da - db) / min(da, db)) * Decimal("100")


def compute_divergence_pct(rate_a: float, rate_b: float) -> float:
    """Compute symmetric relative divergence percentage ``|a - b| / min(a, b) * 100`` (D-07)."""
    return float(_compute_divergence_pct_decimal(rate_a, rate_b))


def _check_sanity_rate(currency: str, rate: float) -> str | None:
    if not math.isfinite(rate) or rate <= 0.0:
        return f"non-finite or non-positive rate {rate!r}"
    low, high = ALL_CURRENCY_SANITY_BANDS[currency]
    if not (low <= rate <= high):
        return f"rate {rate!r} outside sanity envelope [{low}, {high}] (possible inversion/scaling)"
    return None


def _validator_chain_for(currency: str) -> tuple[str, ...]:
    if currency in _ALL_ECB_COVERED:
        return (ECB_FX_PROVIDER, FAWAZ_FX_PROVIDER)
    if currency == "RUB":
        return (CBR_FX_PROVIDER, FAWAZ_FX_PROVIDER)
    return (FAWAZ_FX_PROVIDER,)


def _extract_provider_rate(
    provider_quotes: Mapping[str, FxProviderQuote],
    provider_name: str,
    currency: str,
) -> tuple[tuple[float, str] | None, str | None]:
    """Return ``((rate, data_date), None)``, ``(None, None)`` if omitted, or ``(None, reason)``."""
    quote = provider_quotes.get(provider_name)
    if quote is None or currency not in quote.rates:
        return None, None
    rate = quote.rates[currency]
    error_reason = _check_sanity_rate(currency, rate)
    if error_reason is not None:
        return None, f"{provider_name}: {error_reason}"
    return (rate, quote.data_date), None


def _resolve_fallback_or_missing(
    currency: str,
    *,
    previous_fx: Mapping[str, FxRateLockEntry],
    fetched_date: str,
    fetched_at: str,
    resolved: dict[str, FxRateLockEntry],
    alerts: list[LockAlert],
    missing: list[str],
    emit_retained_alert: bool,
    is_extended: bool = False,
) -> None:
    prev = previous_fx.get(currency)
    if prev is not None:
        resolved[currency] = prev.model_copy(update={"fallback_used": True})
        if emit_retained_alert:
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="fx_lockfile_retained",
                    scope=currency,
                    detail=f"Retained previous lockfile rate for {currency} ({prev.rate_per_eur}).",
                )
            )
        return

    if currency == "BAM":
        resolved["BAM"] = FxRateLockEntry(
            currency="BAM",
            rate_per_eur=BAM_FIXED_PEG_PER_EUR,
            provider="cbbh_peg",
            validator_provider=None,
            validator_rate_per_eur=None,
            divergence_pct=0.0,
            data_date=fetched_date,
            fetched_at=fetched_at,
            fallback_used=True,
        )
        alerts.append(
            LockAlert(
                severity="warning",
                code="fx_bam_peg_fallback",
                scope="BAM",
                detail=(
                    f"All BAM providers unavailable; using legal CBBH fixed peg "
                    f"1 EUR = {BAM_FIXED_PEG_PER_EUR} BAM."
                ),
            )
        )
        return

    if is_extended:
        ref_rate = ALL_REFERENCE_FX_RATES[currency]
        provider_name = (
            "promods_reference_fx"
            if currency in EXTENDED_PROMODS_CURRENCIES
            else "global_reference_fx"
        )
        resolved[currency] = FxRateLockEntry(
            currency=currency,
            rate_per_eur=ref_rate,
            provider=provider_name,
            validator_provider=None,
            validator_rate_per_eur=None,
            divergence_pct=0.0,
            data_date=fetched_date,
            fetched_at=fetched_at,
            fallback_used=True,
        )
        alerts.append(
            LockAlert(
                severity="warning",
                code="fx_reference_fallback",
                scope=currency,
                detail=(
                    f"No valid live FX provider or previous lockfile entry for extended "
                    f"currency {currency}; using curated reference rate 1 EUR = {ref_rate}."
                ),
            )
        )
        return

    missing.append(currency)
    alerts.append(
        LockAlert(
            severity="error",
            code="fx_missing_rate",
            scope=currency,
            detail=(
                f"No valid live FX provider or previous lockfile entry available for {currency}."
            ),
        )
    )


def _validate_single_currency(
    currency: str,
    *,
    is_extended: bool,
    provider_quotes: Mapping[str, FxProviderQuote],
    prev_map: Mapping[str, FxRateLockEntry],
    fetched_date: str,
    fetched_at: str,
    resolved: dict[str, FxRateLockEntry],
    alerts: list[LockAlert],
    missing: list[str],
) -> None:
    primary_data, primary_err = _extract_provider_rate(
        provider_quotes, PRIMARY_FX_PROVIDER, currency
    )
    if primary_err is not None:
        alerts.append(
            LockAlert(
                severity="warning" if is_extended else "error",
                code="fx_sanity_rejected",
                scope=currency,
                detail=f"Rejected primary FX quote for {currency}: {primary_err}.",
            )
        )
        primary_data = None

    validator_candidates: list[tuple[str, float, str]] = []
    for candidate_provider in _validator_chain_for(currency):
        cand_data, cand_err = _extract_provider_rate(provider_quotes, candidate_provider, currency)
        if cand_err is not None:
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="fx_sanity_rejected",
                    scope=currency,
                    detail=f"Ignored invalid validator FX quote for {currency}: {cand_err}.",
                )
            )
            continue
        if cand_data is not None:
            validator_candidates.append((candidate_provider, cand_data[0], cand_data[1]))

    is_single_source_extended = is_extended and currency not in _ALL_ECB_COVERED

    if primary_data is not None:
        active_provider = PRIMARY_FX_PROVIDER
        active_rate, active_date = primary_data
        fallback_used = False
        remaining_validators = validator_candidates
    elif validator_candidates:
        active_provider, active_rate, active_date = validator_candidates[0]
        remaining_validators = validator_candidates[1:]
        if is_single_source_extended and primary_err is None:
            # Non-ECB extended global currencies use fawazahmed0 as their primary live source.
            fallback_used = False
        else:
            fallback_used = True
            reason = (
                f"failed sanity bounds for {currency}"
                if primary_err is not None
                else f"omitted {currency}"
            )
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="fx_primary_fallback",
                    scope=currency,
                    detail=(
                        f"Primary FX provider {PRIMARY_FX_PROVIDER!r} {reason}; "
                        f"promoted {active_provider!r} ({active_rate})."
                    ),
                )
            )
    else:
        _resolve_fallback_or_missing(
            currency,
            previous_fx=prev_map,
            fetched_date=fetched_date,
            fetched_at=fetched_at,
            resolved=resolved,
            alerts=alerts,
            missing=missing,
            emit_retained_alert=primary_err is None,
            is_extended=is_extended,
        )
        return

    if remaining_validators:
        val_provider, val_rate, _val_date = remaining_validators[0]
        div_dec = _compute_divergence_pct_decimal(active_rate, val_rate)
        div_pct = float(div_dec)
        if div_dec > Decimal(str(DIVERGENCE_REJECT_PCT)):
            alerts.append(
                LockAlert(
                    severity="warning" if is_extended else "error",
                    code="fx_divergence_rejected",
                    scope=currency,
                    detail=(
                        f"{currency} FX divergence {div_pct:.2f}% exceeds "
                        f"{DIVERGENCE_REJECT_PCT:.1f}% limit "
                        f"({active_provider}={active_rate}, {val_provider}={val_rate})."
                    ),
                )
            )
            _resolve_fallback_or_missing(
                currency,
                previous_fx=prev_map,
                fetched_date=fetched_date,
                fetched_at=fetched_at,
                resolved=resolved,
                alerts=alerts,
                missing=missing,
                emit_retained_alert=False,
                is_extended=is_extended,
            )
            return

        warn_threshold = (
            MAJOR_DIVERGENCE_WARN_PCT
            if currency in _ALL_MAJOR_ECB
            else VOLATILE_DIVERGENCE_WARN_PCT
        )
        if div_dec > Decimal(str(warn_threshold)):
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="fx_divergence_warning",
                    scope=currency,
                    detail=(
                        f"{currency} FX divergence {div_pct:.2f}% exceeds "
                        f"{warn_threshold:.1f}% tier threshold "
                        f"({active_provider}={active_rate}, {val_provider}={val_rate})."
                    ),
                )
            )

        resolved[currency] = FxRateLockEntry(
            currency=currency,
            rate_per_eur=active_rate,
            provider=active_provider,
            validator_provider=val_provider,
            validator_rate_per_eur=val_rate,
            divergence_pct=round(div_pct, 4),
            data_date=active_date,
            fetched_at=fetched_at,
            fallback_used=fallback_used,
        )
    else:
        if not is_single_source_extended:
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="fx_validator_unavailable",
                    scope=currency,
                    detail=(
                        f"No cross-validator quote available for {currency}; "
                        f"accepted {active_provider!r} ({active_rate}) within sanity band."
                    ),
                )
            )
        resolved[currency] = FxRateLockEntry(
            currency=currency,
            rate_per_eur=active_rate,
            provider=active_provider,
            validator_provider=None,
            validator_rate_per_eur=None,
            divergence_pct=None,
            data_date=active_date,
            fetched_at=fetched_at,
            fallback_used=fallback_used,
        )


def cross_validate_fx_rates(
    provider_quotes: Mapping[str, FxProviderQuote],
    *,
    previous_fx: Mapping[str, FxRateLockEntry] | None,
    fetched_at: str,
    include_extended: bool = False,
) -> FxValidationResult:
    """Cross-validate multi-provider FX quotes per D-07 tolerances and CI isolation (T-04-03)."""
    if TERRITORY_CURRENCIES.get("BG") != "EUR":
        raise ValueError("Invariant violation: Bulgaria (BG) must be mapped to EUR")

    prev_map: Mapping[str, FxRateLockEntry] = previous_fx or {}
    fetched_date = fetched_at[:10]
    if len(fetched_date) != 10:
        raise ValueError(f"fetched_at must start with YYYY-MM-DD, got {fetched_at!r}")

    resolved: dict[str, FxRateLockEntry] = {
        "EUR": FxRateLockEntry(
            currency="EUR",
            rate_per_eur=1.0,
            provider="pinned_eur",
            validator_provider=None,
            validator_rate_per_eur=None,
            divergence_pct=0.0,
            data_date=fetched_date,
            fetched_at=fetched_at,
            fallback_used=False,
        )
    }
    if resolved["EUR"].rate_per_eur != 1.0:
        raise ValueError("Invariant violation: EUR rate_per_eur must be pinned to 1.0")

    alerts: list[LockAlert] = []
    missing: list[str] = []

    for currency in _REQUIRED_NON_EUR_CURRENCIES:
        _validate_single_currency(
            currency,
            is_extended=False,
            provider_quotes=provider_quotes,
            prev_map=prev_map,
            fetched_date=fetched_date,
            fetched_at=fetched_at,
            resolved=resolved,
            alerts=alerts,
            missing=missing,
        )

    if include_extended:
        for currency in _OPTIONAL_EXTENDED_CURRENCIES:
            _validate_single_currency(
                currency,
                is_extended=True,
                provider_quotes=provider_quotes,
                prev_map=prev_map,
                fetched_date=fetched_date,
                fetched_at=fetched_at,
                resolved=resolved,
                alerts=alerts,
                missing=missing,
            )

    sorted_rates = {code: resolved[code] for code in sorted(resolved)}
    return FxValidationResult(
        ok=len(missing) == 0,
        rates=sorted_rates,
        alerts=alerts,
        missing_currencies=missing,
    )
