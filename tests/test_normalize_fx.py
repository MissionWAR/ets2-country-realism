"""Unit tests for offline ets2v2.normalize currency map, FX validation, and lockfile I/O."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from ets2v2.normalize import (
    BAM_FIXED_PEG_PER_EUR,
    CANONICAL_FUEL_GRADES,
    CURRENCY_SANITY_BANDS,
    ECB_COVERED_CURRENCIES,
    EUROPEAN_TERRITORY_ISO2S,
    EXTRA_EU_TERRITORY_ISO2S,
    MAJOR_ECB_CURRENCIES,
    TERRITORY_CURRENCIES,
    VANILLA_36_ISO2S,
    VANILLA_SLUG_TO_ISO2,
    VOLATILE_NON_ECB_CURRENCIES,
    CountryFuelLockEntry,
    FxProviderQuote,
    FxRateLockEntry,
    LockAlert,
    NormalizedCurrencyPrice,
    PricesLockfile,
    compute_divergence_pct,
    convert_local_to_eur_and_local,
    cross_validate_fx_rates,
    evaluate_lockfile_staleness,
    load_prices_lockfile,
    round_eur_per_liter,
    serialize_lockfile_bytes,
    write_prices_lockfile,
)

_BASELINE_RATES: dict[str, float] = {
    "ALL": 98.5,
    "BAM": 1.95583,
    "CHF": 0.94,
    "CZK": 25.2,
    "DKK": 7.46,
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


def _make_full_previous_fx() -> dict[str, FxRateLockEntry]:
    entries: dict[str, FxRateLockEntry] = {
        "EUR": FxRateLockEntry(
            currency="EUR",
            rate_per_eur=1.0,
            provider="pinned_eur",
            data_date="2026-11-13",
            fetched_at="2026-11-13T06:00:00Z",
        )
    }
    for currency, rate in _BASELINE_RATES.items():
        entries[currency] = FxRateLockEntry(
            currency=currency,
            rate_per_eur=rate,
            provider="frankfurter_v2",
            validator_provider="ecb_xml" if currency in ECB_COVERED_CURRENCIES else "fawazahmed0",
            validator_rate_per_eur=rate,
            divergence_pct=0.0,
            data_date="2026-11-13",
            fetched_at="2026-11-13T06:00:00Z",
        )
    return entries


def _make_clean_provider_quotes() -> dict[str, FxProviderQuote]:
    ecb_rates = {c: _BASELINE_RATES[c] for c in ECB_COVERED_CURRENCIES}
    return {
        "frankfurter_v2": FxProviderQuote(
            provider="frankfurter_v2",
            data_date="2026-11-20",
            rates=dict(_BASELINE_RATES),
        ),
        "ecb_xml": FxProviderQuote(
            provider="ecb_xml",
            data_date="2026-11-20",
            rates=ecb_rates,
        ),
        "fawazahmed0": FxProviderQuote(
            provider="fawazahmed0",
            data_date="2026-11-20",
            rates=dict(_BASELINE_RATES),
        ),
        "cbr_xml": FxProviderQuote(
            provider="cbr_xml",
            data_date="2026-11-20",
            rates={"RUB": _BASELINE_RATES["RUB"]},
        ),
    }


def test_39_territory_currency_registry_invariants() -> None:
    assert len(TERRITORY_CURRENCIES) == 39
    assert len(EUROPEAN_TERRITORY_ISO2S) == 39
    assert len(VANILLA_36_ISO2S) == 36
    assert len(VANILLA_SLUG_TO_ISO2) == 36
    assert frozenset({"IE", "CY", "MT"}) == EXTRA_EU_TERRITORY_ISO2S
    assert VANILLA_36_ISO2S | EXTRA_EU_TERRITORY_ISO2S == EUROPEAN_TERRITORY_ISO2S
    assert set(TERRITORY_CURRENCIES) == set(EUROPEAN_TERRITORY_ISO2S)
    assert set(VANILLA_SLUG_TO_ISO2.values()) == set(VANILLA_36_ISO2S)

    # D-04 & D-07 currency mappings
    assert TERRITORY_CURRENCIES["BG"] == "EUR"
    assert TERRITORY_CURRENCIES["ME"] == "EUR"
    assert TERRITORY_CURRENCIES["XK"] == "EUR"
    assert TERRITORY_CURRENCIES["IE"] == "EUR"
    assert TERRITORY_CURRENCIES["CY"] == "EUR"
    assert TERRITORY_CURRENCIES["MT"] == "EUR"
    assert TERRITORY_CURRENCIES["BA"] == "BAM"
    assert pytest.approx(1.95583) == BAM_FIXED_PEG_PER_EUR

    # Tier disjointness & coverage of all 16 non-EUR currencies
    non_eur = {ccy for ccy in TERRITORY_CURRENCIES.values() if ccy != "EUR"}
    assert len(non_eur) == 16
    assert MAJOR_ECB_CURRENCIES.isdisjoint(VOLATILE_NON_ECB_CURRENCIES)
    assert non_eur == MAJOR_ECB_CURRENCIES | VOLATILE_NON_ECB_CURRENCIES
    assert MAJOR_ECB_CURRENCIES | frozenset({"TRY"}) == ECB_COVERED_CURRENCIES
    assert set(CURRENCY_SANITY_BANDS) == non_eur
    for ccy, (low, high) in CURRENCY_SANITY_BANDS.items():
        assert 0.0 < low < high, f"Invalid sanity band for {ccy}"


def test_canonical_fuel_grades_match_d14() -> None:
    assert CANONICAL_FUEL_GRADES == (
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


def test_pydantic_models_strict_frozen_and_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        FxRateLockEntry(
            currency="GBP",
            rate_per_eur=float("nan"),
            provider="frankfurter_v2",
            data_date="2026-11-20",
            fetched_at="2026-11-20T06:00:00Z",
        )

    with pytest.raises(ValidationError):
        FxRateLockEntry(
            currency="GBP",
            rate_per_eur=0.0,
            provider="frankfurter_v2",
            data_date="2026-11-20",
            fetched_at="2026-11-20T06:00:00Z",
        )

    with pytest.raises(ValidationError):
        CountryFuelLockEntry.model_validate(
            {
                "iso2": "DE",
                "currency": "EUR",
                "eur_per_liter": 5.50,
                "local_prices": {"diesel": 5.50},
                "source": "ec_wob",
                "license": "CC BY 4.0",
                "data_date": "2026-11-20",
                "fetched_at": "2026-11-20T06:00:00Z",
            }
        )

    with pytest.raises(ValidationError):
        CountryFuelLockEntry.model_validate(
            {
                "iso2": "DE",
                "currency": "EUR",
                "eur_per_liter": 1.65,
                "local_prices": {"diesel": float("inf")},
                "source": "ec_wob",
                "license": "CC BY 4.0",
                "data_date": "2026-11-20",
                "fetched_at": "2026-11-20T06:00:00Z",
            }
        )

    with pytest.raises(ValidationError):
        LockAlert.model_validate(
            {
                "severity": "warning",
                "code": "fx_divergence_warning",
                "scope": "GBP",
                "detail": "test",
                "unexpected": "forbidden",
            }
        )


def test_lockfile_serialization_roundtrip_and_hygiene_guards(tmp_path: Path) -> None:
    lockfile = PricesLockfile(
        schema_version=1,
        updated_at="2026-11-20T06:00:00Z",
        fx_rates=_make_full_previous_fx(),
        countries={
            "DE": CountryFuelLockEntry(
                iso2="DE",
                currency="EUR",
                eur_per_liter=1.642,
                local_prices={"diesel": 1.642, "petrol_95": 1.789},
                derived_grades=["petrol_98"],
                source="ec_wob",
                license="CC BY 4.0",
                data_date="2026-11-19",
                fetched_at="2026-11-20T06:00:00Z",
                fallback_used=False,
            )
        },
        alerts=[
            LockAlert(
                severity="warning",
                code="fx_divergence_warning",
                scope="GBP",
                detail="GBP divergence 2.4%",
            )
        ],
    )

    lock_path = tmp_path / "prices.lock.json"
    raw = write_prices_lockfile(lockfile, lock_path)
    assert raw == serialize_lockfile_bytes(lockfile)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")

    reloaded = load_prices_lockfile(lock_path)
    assert reloaded == lockfile

    # Missing file
    with pytest.raises(FileNotFoundError):
        load_prices_lockfile(tmp_path / "missing.lock.json")

    # BOM rejection
    bom_path = tmp_path / "bom.lock.json"
    bom_path.write_bytes(b"\xef\xbb\xbf" + raw)
    with pytest.raises(ValueError, match="BOM"):
        load_prices_lockfile(bom_path)

    # CRLF rejection
    crlf_path = tmp_path / "crlf.lock.json"
    crlf_path.write_bytes(raw.replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="LF"):
        load_prices_lockfile(crlf_path)

    # Extra key rejection
    extra_path = tmp_path / "extra.lock.json"
    extra_path.write_text(
        raw.decode("utf-8").replace('"schema_version": 1,', '"schema_version": 1, "extra_k": 1,'),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ValidationError):
        load_prices_lockfile(extra_path)


def test_cross_validate_fx_rates_clean_happy_path() -> None:
    result = cross_validate_fx_rates(
        _make_clean_provider_quotes(),
        previous_fx=_make_full_previous_fx(),
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert result.ok is True
    assert result.missing_currencies == []
    assert result.alerts == []
    assert len(result.rates) == 17
    assert result.rates["EUR"].rate_per_eur == 1.0
    assert result.rates["EUR"].provider == "pinned_eur"
    assert result.rates["RUB"].validator_provider == "cbr_xml"
    assert result.rates["GBP"].validator_provider == "ecb_xml"
    assert result.rates["ALL"].validator_provider == "fawazahmed0"


@pytest.mark.parametrize(
    ("currency", "validator_provider", "factor", "expected_alert", "expect_held"),
    [
        # Major / ECB tier: warn >2%, reject >10%
        ("GBP", "ecb_xml", 1.015, None, False),
        ("GBP", "ecb_xml", 1.025, "fx_divergence_warning", False),
        ("GBP", "ecb_xml", 1.110, "fx_divergence_rejected", True),
        ("PLN", "ecb_xml", 1.025, "fx_divergence_warning", False),
        ("CZK", "ecb_xml", 1.110, "fx_divergence_rejected", True),
        # Volatile / non-ECB tier: warn >5%, reject >10%
        ("TRY", "ecb_xml", 1.040, None, False),
        ("TRY", "ecb_xml", 1.065, "fx_divergence_warning", False),
        ("TRY", "ecb_xml", 1.120, "fx_divergence_rejected", True),
        ("RUB", "cbr_xml", 1.040, None, False),
        ("RUB", "cbr_xml", 1.065, "fx_divergence_warning", False),
        ("RUB", "cbr_xml", 1.120, "fx_divergence_rejected", True),
        ("RSD", "fawazahmed0", 1.040, None, False),
        ("RSD", "fawazahmed0", 1.065, "fx_divergence_warning", False),
        ("RSD", "fawazahmed0", 1.120, "fx_divergence_rejected", True),
    ],
)
def test_cross_validate_fx_tiered_divergence_rules(
    currency: str,
    validator_provider: str,
    factor: float,
    expected_alert: str | None,
    expect_held: bool,
) -> None:
    quotes = _make_clean_provider_quotes()
    base_rate = _BASELINE_RATES[currency]
    # Primary shifted relative to validator while staying inside sanity envelope
    new_primary = base_rate * factor
    quotes["frankfurter_v2"] = FxProviderQuote(
        provider="frankfurter_v2",
        data_date="2026-11-20",
        rates={**quotes["frankfurter_v2"].rates, currency: new_primary},
    )
    previous = _make_full_previous_fx()
    previous[currency] = previous[currency].model_copy(update={"rate_per_eur": base_rate * 0.99})

    result = cross_validate_fx_rates(
        quotes,
        previous_fx=previous,
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert result.ok is True
    matching_alerts = [a for a in result.alerts if a.scope == currency]
    if expected_alert is None:
        assert matching_alerts == []
    else:
        assert any(a.code == expected_alert for a in matching_alerts)

    if expect_held:
        assert result.rates[currency].rate_per_eur == pytest.approx(base_rate * 0.99)
        assert result.rates[currency].fallback_used is True
    else:
        assert result.rates[currency].rate_per_eur == pytest.approx(new_primary)
        assert result.rates[currency].validator_provider == validator_provider
        assert result.rates[currency].fallback_used is False


@pytest.mark.parametrize(
    ("currency", "corrupt_rate"),
    [
        ("HUF", 0.0025),  # inverted X/EUR instead of EUR/X
        ("CZK", 0.04),  # inverted
        ("GBP", float("nan")),
        ("NOK", float("inf")),
        ("PLN", -4.3),
        ("SEK", 0.0),
    ],
)
def test_cross_validate_fx_rejects_inverted_and_non_finite_rates(
    currency: str,
    corrupt_rate: float,
) -> None:
    quotes = _make_clean_provider_quotes()
    quotes["frankfurter_v2"] = FxProviderQuote(
        provider="frankfurter_v2",
        data_date="2026-11-20",
        rates={**quotes["frankfurter_v2"].rates, currency: corrupt_rate},
    )
    previous = _make_full_previous_fx()

    result = cross_validate_fx_rates(
        quotes,
        previous_fx=previous,
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert result.ok is True
    assert result.rates[currency].rate_per_eur == pytest.approx(_BASELINE_RATES[currency])
    assert result.rates[currency].fallback_used is True
    assert any(a.scope == currency and a.code == "fx_sanity_rejected" for a in result.alerts)


def test_cross_validate_fx_promotes_validator_on_primary_omission_and_bam_peg_fallback() -> None:
    quotes = _make_clean_provider_quotes()
    # Omit GBP, RUB, and BAM from Frankfurter v2; also omit BAM from fawazahmed0
    ff_rates = {
        k: v for k, v in quotes["frankfurter_v2"].rates.items() if k not in {"GBP", "RUB", "BAM"}
    }
    fawaz_rates = {k: v for k, v in quotes["fawazahmed0"].rates.items() if k != "BAM"}
    quotes["frankfurter_v2"] = FxProviderQuote(
        provider="frankfurter_v2",
        data_date="2026-11-20",
        rates=ff_rates,
    )
    quotes["fawazahmed0"] = FxProviderQuote(
        provider="fawazahmed0",
        data_date="2026-11-20",
        rates=fawaz_rates,
    )

    result = cross_validate_fx_rates(
        quotes,
        previous_fx=None,
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert result.ok is True
    assert result.rates["GBP"].provider == "ecb_xml"
    assert result.rates["GBP"].fallback_used is True
    assert result.rates["RUB"].provider == "cbr_xml"
    assert result.rates["RUB"].validator_provider == "fawazahmed0"
    assert result.rates["RUB"].fallback_used is True
    # Legal CBBH peg fallback when all APIs omit BAM
    assert result.rates["BAM"].provider == "cbbh_peg"
    assert result.rates["BAM"].rate_per_eur == pytest.approx(BAM_FIXED_PEG_PER_EUR)
    assert result.rates["BAM"].fallback_used is True
    assert any(a.scope == "BAM" and a.code == "fx_bam_peg_fallback" for a in result.alerts)


def test_round_eur_per_liter_and_currency_conversion() -> None:
    # Decimal ROUND_HALF_UP (1.7855 -> 1.786, NOT banker's rounding)
    assert round_eur_per_liter(1.7855) == 1.786
    assert round_eur_per_liter(1.7845) == 1.785
    assert round_eur_per_liter(1.6424) == 1.642

    converted = convert_local_to_eur_and_local(1.429, "GBP", 0.84)
    assert isinstance(converted, NormalizedCurrencyPrice)
    assert converted.currency == "GBP"
    assert converted.local_display_price == pytest.approx(1.429)
    assert converted.rate_per_eur == pytest.approx(0.84)
    assert converted.eur_per_liter == round_eur_per_liter(1.429 / 0.84)

    assert compute_divergence_pct(100.0, 102.5) == pytest.approx(2.5)

    with pytest.raises(ValueError):
        round_eur_per_liter(float("nan"))
    with pytest.raises(ValueError):
        convert_local_to_eur_and_local(-1.0, "GBP", 0.84)
    with pytest.raises(ValueError):
        convert_local_to_eur_and_local(1.429, "GBP", math.inf)


def test_evaluate_lockfile_staleness_14d_and_30d_thresholds() -> None:
    as_of = date(2026, 11, 20)
    lockfile = PricesLockfile(
        schema_version=1,
        updated_at="2026-11-20T06:00:00Z",
        fx_rates=_make_full_previous_fx(),
        countries={
            # 14 days old Tier 1 -> clean
            "DE": CountryFuelLockEntry(
                iso2="DE",
                currency="EUR",
                eur_per_liter=1.642,
                local_prices={"diesel": 1.642},
                source="ec_wob",
                license="CC BY 4.0",
                data_date="2026-11-06",
                fetched_at="2026-11-20T06:00:00Z",
                fallback_used=False,
            ),
            # 15 days old Tier 1 -> stale_tier1
            "FR": CountryFuelLockEntry(
                iso2="FR",
                currency="EUR",
                eur_per_liter=1.680,
                local_prices={"diesel": 1.680},
                source="fr_economie",
                license="Licence Ouverte v2.0",
                data_date="2026-11-05",
                fetched_at="2026-11-20T06:00:00Z",
                fallback_used=False,
            ),
            # 30 days old fallback/seeded -> clean
            "AL": CountryFuelLockEntry(
                iso2="AL",
                currency="ALL",
                eur_per_liter=1.720,
                local_prices={"diesel": 169.4},
                source="baseline_1.62_seeded",
                license="ETS2 1.62 baseline",
                data_date="2026-10-21",
                fetched_at="2026-11-20T06:00:00Z",
                fallback_used=True,
            ),
            # 31 days old fallback -> stale_fallback
            "RS": CountryFuelLockEntry(
                iso2="RS",
                currency="RSD",
                eur_per_liter=1.690,
                local_prices={"diesel": 198.0},
                source="baseline_1.62_seeded",
                license="ETS2 1.62 baseline",
                data_date="2026-10-20",
                fetched_at="2026-11-20T06:00:00Z",
                fallback_used=True,
            ),
        },
        alerts=[],
    )

    alerts = evaluate_lockfile_staleness(lockfile, as_of)
    by_scope = {alert.scope: alert for alert in alerts}
    assert set(by_scope) == {"FR", "RS"}
    assert by_scope["FR"].code == "stale_tier1"
    assert by_scope["FR"].severity == "warning"
    assert by_scope["RS"].code == "stale_fallback"
    assert by_scope["RS"].severity == "warning"


def test_fx_exact_boundary_divergence_and_underflow_guards() -> None:
    # Exact Decimal boundary percentages (no IEEE-754 float noise)
    assert compute_divergence_pct(1.00, 1.02) == 2.0
    assert compute_divergence_pct(1.00, 1.10) == 10.0

    quotes = _make_clean_provider_quotes()
    # Exact 2.0% on CHF (major ECB tier: warn > 2.0%) -> no warning
    # Exact 10.0% on TRY (reject > 10.0%) -> warning (>5%) but NOT rejected!
    quotes["frankfurter_v2"] = FxProviderQuote(
        provider="frankfurter_v2",
        data_date="2026-11-20",
        rates={**quotes["frankfurter_v2"].rates, "CHF": 1.02, "TRY": 55.0},
    )
    quotes["ecb_xml"] = FxProviderQuote(
        provider="ecb_xml",
        data_date="2026-11-20",
        rates={**quotes["ecb_xml"].rates, "CHF": 1.00, "TRY": 50.0},
    )
    res = cross_validate_fx_rates(
        quotes,
        previous_fx=_make_full_previous_fx(),
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert res.ok is True
    assert not [a for a in res.alerts if a.scope == "CHF"]
    assert res.rates["CHF"].rate_per_eur == pytest.approx(1.02)
    assert res.rates["TRY"].rate_per_eur == pytest.approx(55.0)
    assert res.rates["TRY"].fallback_used is False
    assert any(a.scope == "TRY" and a.code == "fx_divergence_warning" for a in res.alerts)
    assert not any(a.scope == "TRY" and a.code == "fx_divergence_rejected" for a in res.alerts)

    # round_eur_per_liter rejects sub-mill underflow to 0.000 (LO-05)
    with pytest.raises(ValueError, match="underflows"):
        round_eur_per_liter(0.0004)


def test_fx_primary_sanity_rejection_promotes_healthy_live_validator() -> None:
    quotes = _make_clean_provider_quotes()
    quotes["frankfurter_v2"] = FxProviderQuote(
        provider="frankfurter_v2",
        data_date="2026-11-20",
        rates={**quotes["frankfurter_v2"].rates, "GBP": 999.0},
    )
    # Even with previous_fx=None, healthy ecb_xml + fawazahmed0 supply live GBP!
    res = cross_validate_fx_rates(
        quotes,
        previous_fx=None,
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert res.ok is True
    assert res.rates["GBP"].provider == "ecb_xml"
    assert res.rates["GBP"].validator_provider == "fawazahmed0"
    assert res.rates["GBP"].rate_per_eur == pytest.approx(_BASELINE_RATES["GBP"])
    assert res.rates["GBP"].fallback_used is True
    assert any(a.scope == "GBP" and a.code == "fx_sanity_rejected" for a in res.alerts)
    assert any(a.scope == "GBP" and a.code == "fx_primary_fallback" for a in res.alerts)


def test_calendar_date_validation_and_atomic_lockfile_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ets2v2.fetch.models import RawCountryFuelQuote, RawFxProviderQuote

    for bad_date in ("2026-99-01", "2026-02-30", "2026-13-01"):
        with pytest.raises(ValidationError):
            FxRateLockEntry(
                currency="GBP",
                rate_per_eur=0.84,
                provider="frankfurter_v2",
                data_date=bad_date,
                fetched_at="2026-11-20T06:00:00Z",
            )
        with pytest.raises(ValidationError):
            CountryFuelLockEntry(
                iso2="DE",
                currency="EUR",
                eur_per_liter=1.65,
                local_prices={"diesel": 1.65},
                source="ec_wob",
                license="CC BY 4.0",
                data_date=bad_date,
                fetched_at="2026-11-20T06:00:00Z",
            )
        with pytest.raises(ValidationError):
            FxProviderQuote(provider="frankfurter_v2", data_date=bad_date, rates={"GBP": 0.84})
        with pytest.raises(ValidationError):
            RawFxProviderQuote(provider="frankfurter_v2", data_date=bad_date, rates={"GBP": 0.84})
        with pytest.raises(ValidationError):
            RawCountryFuelQuote(
                iso2="DE",
                currency="EUR",
                prices_by_grade={"diesel": 1.65},
                unit_basis="eur_per_liter",
                source="ec_wob",
                license="CC BY 4.0",
                data_date=bad_date,
            )

    # Atomic lockfile write cleans up unique temp file if os.replace raises
    lockfile = PricesLockfile(
        schema_version=1,
        updated_at="2026-11-20T06:00:00Z",
        fx_rates=_make_full_previous_fx(),
        countries={},
        alerts=[],
    )
    lock_path = tmp_path / "prices.lock.json"

    def _boom_replace(_src: object, _dst: object) -> None:
        raise OSError("Simulated replace failure")

    monkeypatch.setattr("ets2v2.normalize.lockfile.os.replace", _boom_replace)
    with pytest.raises(OSError, match="Simulated replace failure"):
        write_prices_lockfile(lockfile, lock_path)
    assert list(tmp_path.iterdir()) == []


def test_extended_promods_currencies_syp_redenomination_and_ci_outage_isolation() -> None:
    from ets2v2.normalize import (
        ALL_CURRENCY_SANITY_BANDS,
        ALL_LOCKFILE_TERRITORY_ISO2S,
        ALL_REFERENCE_FX_RATES,
        ALL_TERRITORY_CURRENCIES,
        EXTENDED_CURRENCY_SANITY_BANDS,
        EXTENDED_ECB_CURRENCIES,
        EXTENDED_GLOBAL_CURRENCIES,
        EXTENDED_PROMODS_CURRENCIES,
        PROMODS_CURATED_SEED_SOURCE,
        PROMODS_EXTENDED_ISO2S,
    )

    assert len(PROMODS_EXTENDED_ISO2S) == 37
    assert len(ALL_LOCKFILE_TERRITORY_ISO2S) == 225
    assert len(ALL_TERRITORY_CURRENCIES) == 225
    assert len(EXTENDED_PROMODS_CURRENCIES) == 24
    assert len(EXTENDED_ECB_CURRENCIES) == 18
    assert {"CNY", "ILS"} < EXTENDED_ECB_CURRENCIES
    assert set(EXTENDED_CURRENCY_SANITY_BANDS) == EXTENDED_GLOBAL_CURRENCIES
    assert len(ALL_CURRENCY_SANITY_BANDS) == len(ALL_REFERENCE_FX_RATES) - 1
    assert len(ALL_REFERENCE_FX_RATES) == len(EXTENDED_GLOBAL_CURRENCIES) + 17
    assert PROMODS_CURATED_SEED_SOURCE == "promods_curated_seed"

    # Exotic outage (SYP, TMT, LBP omitted from all live providers) -> ok=True with warning fallback
    quotes = _make_clean_provider_quotes()
    quotes["frankfurter_v2"] = FxProviderQuote(
        provider="frankfurter_v2",
        data_date="2026-11-20",
        rates={
            **quotes["frankfurter_v2"].rates,
            "CNY": 7.85,
            "ILS": 4.00,
            "KZT": 540.0,
            "SYP": 14000.0,  # Un-redenominated old SYP -> MUST be rejected by (80, 250) band!
        },
    )
    quotes["ecb_xml"] = FxProviderQuote(
        provider="ecb_xml",
        data_date="2026-11-20",
        rates={**quotes["ecb_xml"].rates, "CNY": 7.86, "ILS": 4.01},
    )
    quotes["fawazahmed0"] = FxProviderQuote(
        provider="fawazahmed0",
        data_date="2026-11-20",
        rates={
            **quotes["fawazahmed0"].rates,
            "CNY": 7.85,
            "ILS": 4.00,
            "KZT": 541.0,
            "SYP": 14000.0,  # Both live feeds stale un-redenominated SYP -> fallback safely
        },
    )

    res = cross_validate_fx_rates(
        quotes,
        previous_fx=None,
        fetched_at="2026-11-20T06:00:00Z",
        include_extended=True,
    )
    assert res.ok is True
    assert res.missing_currencies == []
    assert len(res.rates) == len(ALL_REFERENCE_FX_RATES)
    assert res.rates["CNY"].validator_provider == "ecb_xml"
    assert res.rates["ILS"].validator_provider == "ecb_xml"
    assert res.rates["KZT"].rate_per_eur == pytest.approx(540.0)
    assert res.rates["KZT"].fallback_used is False
    # Un-redenominated SYP rejected and isolated via reference fallback without failing CI
    assert res.rates["SYP"].rate_per_eur == pytest.approx(140.0)
    assert res.rates["SYP"].fallback_used is True
    assert any(a.scope == "SYP" and a.code == "fx_sanity_rejected" for a in res.alerts)
    assert any(a.scope == "SYP" and a.code == "fx_reference_fallback" for a in res.alerts)
    assert any(a.scope == "TMT" and a.code == "fx_reference_fallback" for a in res.alerts)
    assert any(a.scope == "LBP" and a.code == "fx_reference_fallback" for a in res.alerts)

    # Valid post-2026 redenominated SYP (140.0) is accepted live
    quotes_valid_syp = {
        **quotes,
        "frankfurter_v2": FxProviderQuote(
            provider="frankfurter_v2",
            data_date="2026-11-20",
            rates={**quotes["frankfurter_v2"].rates, "SYP": 142.0},
        ),
        "fawazahmed0": FxProviderQuote(
            provider="fawazahmed0",
            data_date="2026-11-20",
            rates={**quotes["fawazahmed0"].rates, "SYP": 143.0},
        ),
    }
    res_syp = cross_validate_fx_rates(
        quotes_valid_syp,
        previous_fx=None,
        fetched_at="2026-11-20T06:00:00Z",
        include_extended=True,
    )
    assert res_syp.ok is True
    assert res_syp.rates["SYP"].rate_per_eur == pytest.approx(142.0)
    assert res_syp.rates["SYP"].fallback_used is False


def test_healthy_global_fx_run_emits_zero_spurious_non_ecb_extended_alerts_hi03() -> None:
    """HI-03: Healthy Friday FX run emits zero spurious alerts for single-source extended FX."""
    from ets2v2.normalize.currencies import (
        ALL_REFERENCE_FX_RATES,
        CURRENCY_SANITY_BANDS,
        ECB_COVERED_CURRENCIES,
        EXTENDED_ECB_CURRENCIES,
        EXTENDED_GLOBAL_CURRENCIES,
    )

    all_ecb = ECB_COVERED_CURRENCIES | EXTENDED_ECB_CURRENCIES
    core_non_eur = set(CURRENCY_SANITY_BANDS)
    # Realistic healthy Friday FX run:
    # - frankfurter_v2 covers Core 16 + 18 Extended ECB (omits ~116 non-ECB extended)
    # - ecb_xml covers all 29 ECB currencies
    # - cbr_xml covers RUB
    # - fawazahmed0 covers all 150 non-EUR currencies
    ff_rates = {c: ALL_REFERENCE_FX_RATES[c] for c in sorted(core_non_eur | all_ecb)}
    ecb_rates = {c: ALL_REFERENCE_FX_RATES[c] for c in sorted(all_ecb)}
    fawaz_rates = {c: r for c, r in ALL_REFERENCE_FX_RATES.items() if c != "EUR"}

    quotes = {
        "frankfurter_v2": FxProviderQuote(
            provider="frankfurter_v2", data_date="2026-11-20", rates=ff_rates
        ),
        "ecb_xml": FxProviderQuote(provider="ecb_xml", data_date="2026-11-20", rates=ecb_rates),
        "fawazahmed0": FxProviderQuote(
            provider="fawazahmed0", data_date="2026-11-20", rates=fawaz_rates
        ),
        "cbr_xml": FxProviderQuote(
            provider="cbr_xml",
            data_date="2026-11-20",
            rates={"RUB": ALL_REFERENCE_FX_RATES["RUB"]},
        ),
    }

    res = cross_validate_fx_rates(
        quotes,
        previous_fx=None,
        fetched_at="2026-11-20T06:00:00Z",
        include_extended=True,
    )
    assert res.ok is True
    assert len(res.rates) == len(ALL_REFERENCE_FX_RATES)
    assert res.alerts == []
    assert all(not entry.fallback_used for entry in res.rates.values())
    for ccy in sorted(EXTENDED_GLOBAL_CURRENCIES - all_ecb):
        assert res.rates[ccy].provider == "fawazahmed0"
        assert res.rates[ccy].fallback_used is False

    # Core European non-EUR currency omitted from frankfurter_v2 STILL emits fx_primary_fallback
    no_pln_ff = {k: v for k, v in ff_rates.items() if k != "PLN"}
    res_core_fallback = cross_validate_fx_rates(
        {
            **quotes,
            "frankfurter_v2": FxProviderQuote(
                provider="frankfurter_v2", data_date="2026-11-20", rates=no_pln_ff
            ),
        },
        previous_fx=None,
        fetched_at="2026-11-20T06:00:00Z",
        include_extended=True,
    )
    assert res_core_fallback.ok is True
    assert any(
        a.scope == "PLN" and a.code == "fx_primary_fallback" for a in res_core_fallback.alerts
    )
    assert res_core_fallback.rates["PLN"].fallback_used is True
