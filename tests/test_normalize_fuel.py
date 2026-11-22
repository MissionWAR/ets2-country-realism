"""Offline unit tests for ets2v2.normalize.fuel and 39-territory baseline seeding."""

from __future__ import annotations

import pathlib

import pytest

from ets2v2.baseline.models import CountriesBaseline
from ets2v2.normalize.currencies import (
    BAM_FIXED_PEG_PER_EUR,
    EUROPEAN_TERRITORY_ISO2S,
    TERRITORY_CURRENCIES,
)
from ets2v2.normalize.fuel import (
    MAX_EUR_PER_LITER,
    MAX_WOW_JUMP_RATIO,
    MIN_EUR_PER_LITER,
    SECONDARY_GRADE_SPREADS,
    compute_secondary_grade_prices,
    normalize_country_fuel_prices,
    normalize_iso2_alias,
)
from ets2v2.normalize.lockfile import (
    BASELINE_SEEDED_SOURCE,
    load_prices_lockfile,
    seed_initial_lockfile,
    serialize_lockfile_bytes,
    write_prices_lockfile,
)
from ets2v2.normalize.models import (
    CANONICAL_FUEL_GRADES,
    CountryFuelLockEntry,
    FuelGrade,
    FxRateLockEntry,
    PricesLockfile,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_COUNTRIES_PATH = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def" / "countries.json"


def _fx(currency: str, rate: float) -> FxRateLockEntry:
    return FxRateLockEntry(
        currency=currency,
        rate_per_eur=rate,
        provider="frankfurter_v2" if currency != "EUR" else "pinned_eur",
        validator_provider="ecb_xml" if currency != "EUR" else None,
        validator_rate_per_eur=rate if currency != "EUR" else None,
        divergence_pct=0.0,
        data_date="2026-11-20",
        fetched_at="2026-11-20T06:00:00Z",
        fallback_used=False,
    )


def _prev_entry(
    iso2: str,
    currency: str,
    eur_per_liter: float,
    local_prices: dict[FuelGrade, float],
) -> CountryFuelLockEntry:
    return CountryFuelLockEntry(
        iso2=iso2,
        currency=currency,
        eur_per_liter=eur_per_liter,
        local_prices=local_prices,
        derived_grades=[],
        source="ec_weekly_oil_bulletin",
        license="CC BY 4.0",
        data_date="2026-11-13",
        fetched_at="2026-11-13T06:00:00Z",
        fallback_used=False,
    )


def test_normalize_iso2_alias_maps_el_and_uk() -> None:
    assert normalize_iso2_alias("EL") == "GR"
    assert normalize_iso2_alias("el") == "GR"
    assert normalize_iso2_alias(" UK ") == "GB"
    assert normalize_iso2_alias("de") == "DE"
    assert normalize_iso2_alias("IE") == "IE"


def test_secondary_grade_spreads_match_verified_d02_ratios_and_preserve_live_grades() -> None:
    assert MIN_EUR_PER_LITER == 0.01
    assert MAX_EUR_PER_LITER == 5.00
    assert MAX_WOW_JUMP_RATIO == 0.25
    assert SECONDARY_GRADE_SPREADS == {
        "petrol_98": ("petrol_95", 1.06),
        "petrol_100": ("petrol_95", 1.12),
        "diesel_plus": ("diesel", 1.07),
        "petrol_92": ("petrol_95", 0.96),
        "e85": ("petrol_95", 0.72),
        "mpo": ("diesel", 0.75),
        "lpg": ("petrol_95", 0.48),
    }

    # Live LPG and petrol_98 must NOT be overwritten by spread ratios
    live: dict[FuelGrade, float] = {
        "diesel": 1.600,
        "petrol_95": 1.750,
        "petrol_98": 1.920,
        "lpg": 0.950,
    }
    full, derived = compute_secondary_grade_prices(live)
    assert set(full.keys()) == set(CANONICAL_FUEL_GRADES)
    assert full["diesel"] == pytest.approx(1.600)
    assert full["petrol_95"] == pytest.approx(1.750)
    assert full["petrol_98"] == pytest.approx(1.920)
    assert full["lpg"] == pytest.approx(0.950)
    assert full["petrol_100"] == pytest.approx(1.960)
    assert full["diesel_plus"] == pytest.approx(1.712)
    assert full["petrol_92"] == pytest.approx(1.680)
    assert full["e85"] == pytest.approx(1.260)
    assert full["mpo"] == pytest.approx(1.200)
    assert set(derived) == {"diesel_plus", "e85", "mpo", "petrol_100", "petrol_92"}


@pytest.mark.parametrize(
    ("iso2", "currency", "rate", "bad_prices"),
    [
        # Unscaled EUR/1000L bug (D-06)
        ("DE", "EUR", 1.0, {"diesel": 1642.50, "petrol_95": 1750.0}),
        # Unscaled pence-as-GBP bug (D-06): 142.9 GBP / 0.84 = 170.12 EUR/L
        ("GB", "GBP", 0.84, {"diesel": 142.9, "petrol_95": 138.4}),
        # Below lower bound (< 0.01 EUR/L)
        ("FR", "EUR", 1.0, {"diesel": 0.005, "petrol_95": 1.75}),
        # Above upper bound (> 5.00 EUR/L)
        ("NO", "NOK", 11.7, {"diesel": 65.0, "petrol_95": 22.0}),
    ],
)
def test_hard_bounds_reject_out_of_range_even_with_allow_jump(
    iso2: str,
    currency: str,
    rate: float,
    bad_prices: dict[FuelGrade, float],
) -> None:
    prev_diesel = round(1.60 * rate, 4)
    prev_p95 = round(1.70 * rate, 4)
    prev = _prev_entry(iso2, currency, 1.60, {"diesel": prev_diesel, "petrol_95": prev_p95})

    res = normalize_country_fuel_prices(
        iso2,
        live_local_prices=bad_prices,
        source="test_feed",
        license_name="CC BY 4.0",
        data_date="2026-11-20",
        fx_entry=_fx(currency, rate),
        previous_entry=prev,
        allow_jump_iso2=frozenset({iso2}),  # --allow-jump must NEVER bypass 0.01-5.00 hard bounds!
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert res.accepted is False
    assert res.entry.eur_per_liter == 1.60
    assert res.entry.fallback_used is True
    assert any(a.code == "price_bounds_rejected" and a.severity == "error" for a in res.alerts)


def test_wow_circuit_breaker_holds_previous_and_respects_allow_jump_override() -> None:
    prev = _prev_entry("DE", "EUR", 1.600, {"diesel": 1.600, "petrol_95": 1.700})

    # +30% jump (> 25%) without override -> rejected, previous entry held
    rejected = normalize_country_fuel_prices(
        "DE",
        live_local_prices={"diesel": 2.080, "petrol_95": 2.150},
        source="ec_weekly_oil_bulletin",
        license_name="CC BY 4.0",
        data_date="2026-11-20",
        fx_entry=_fx("EUR", 1.0),
        previous_entry=prev,
        allow_jump_iso2=frozenset(),
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert rejected.accepted is False
    assert rejected.entry.eur_per_liter == 1.600
    assert rejected.entry.fallback_used is True
    assert any(a.code == "price_jump_rejected" and a.severity == "error" for a in rejected.alerts)

    # Same +30% jump WITH --allow-jump DE -> accepted with audit warning
    accepted = normalize_country_fuel_prices(
        "DE",
        live_local_prices={"diesel": 2.080, "petrol_95": 2.150},
        source="ec_weekly_oil_bulletin",
        license_name="CC BY 4.0",
        data_date="2026-11-20",
        fx_entry=_fx("EUR", 1.0),
        previous_entry=prev,
        allow_jump_iso2=frozenset({"DE"}),
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert accepted.accepted is True
    assert accepted.entry.eur_per_liter == 2.080
    assert accepted.entry.fallback_used is False
    assert set(accepted.entry.local_prices.keys()) == set(CANONICAL_FUEL_GRADES)
    assert any(
        a.code == "price_jump_override_accepted" and a.severity == "warning"
        for a in accepted.alerts
    )


def test_normalize_country_fuel_prices_uses_3dp_round_half_up_for_eur_per_liter() -> None:
    # 1.4994 GBP / 0.84 = 1.7850 EUR/L -> 1.785; 1.49982 GBP / 0.84 = 1.7855 -> 1.786 (HALF_UP)
    res = normalize_country_fuel_prices(
        "UK",  # tests alias normalization UK -> GB
        live_local_prices={"diesel": 1.49982, "petrol_95": 1.429},
        source="uk_desnz",
        license_name="OGL v3.0",
        data_date="2026-11-20",
        fx_entry=_fx("GBP", 0.84),
        previous_entry=None,
        allow_jump_iso2=frozenset(),
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert res.accepted is True
    assert res.entry.iso2 == "GB"
    assert res.entry.currency == "GBP"
    assert res.entry.eur_per_liter == 1.786
    assert set(res.entry.local_prices.keys()) == set(CANONICAL_FUEL_GRADES)


def test_seed_initial_lockfile_produces_deterministic_39_territory_v1_lockfile(
    tmp_path: pathlib.Path,
) -> None:
    baseline = CountriesBaseline.model_validate_json(BASELINE_COUNTRIES_PATH.read_text("utf-8"))
    lock_a = seed_initial_lockfile(baseline)
    lock_b = seed_initial_lockfile(baseline)

    assert lock_a == lock_b
    assert lock_a.schema_version == 1
    assert set(lock_a.countries.keys()) == set(EUROPEAN_TERRITORY_ISO2S)
    assert len(lock_a.countries) == 39
    assert {"IE", "CY", "MT"} <= set(lock_a.countries.keys())
    assert lock_a.countries["BG"].currency == "EUR"
    assert lock_a.fx_rates["EUR"].rate_per_eur == 1.0
    assert lock_a.fx_rates["BAM"].rate_per_eur == BAM_FIXED_PEG_PER_EUR
    assert len(lock_a.fx_rates) == 17

    for iso2, entry in lock_a.countries.items():
        assert entry.currency == TERRITORY_CURRENCIES[iso2]
        assert MIN_EUR_PER_LITER <= entry.eur_per_liter <= MAX_EUR_PER_LITER
        assert set(entry.local_prices.keys()) == set(CANONICAL_FUEL_GRADES)
        assert entry.source == BASELINE_SEEDED_SOURCE
        assert entry.fallback_used is True

    # Canonical bytes round-trip cleanly
    out_path = tmp_path / "prices.lock.json"
    raw = write_prices_lockfile(lock_a, out_path)
    assert raw == serialize_lockfile_bytes(lock_b)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    restored = load_prices_lockfile(out_path)
    assert isinstance(restored, PricesLockfile)
    assert restored == lock_a


@pytest.mark.parametrize(
    ("prev_price", "new_price"),
    [
        (1.20, 1.50),  # exact +25.0% (binary float: 0.25000000000000006)
        (1.40, 1.75),  # exact +25.0%
        (2.20, 1.65),  # exact -25.0%
    ],
)
def test_exact_25pct_wow_boundary_accepted_without_float_noise(
    prev_price: float,
    new_price: float,
) -> None:
    prev = _prev_entry("DE", "EUR", prev_price, {"diesel": prev_price, "petrol_95": prev_price})
    res = normalize_country_fuel_prices(
        "DE",
        live_local_prices={"diesel": new_price, "petrol_95": new_price},
        source="ec_weekly_oil_bulletin",
        license_name="CC BY 4.0",
        data_date="2026-11-20",
        fx_entry=_fx("EUR", 1.0),
        previous_entry=prev,
        allow_jump_iso2=frozenset(),
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert res.accepted is True
    assert res.entry.eur_per_liter == pytest.approx(new_price)
    assert not any(a.code == "price_jump_rejected" for a in res.alerts)


def test_anchorless_grade_map_emits_price_anchor_missing_and_holds_previous() -> None:
    prev = _prev_entry("DE", "EUR", 1.640, {"diesel": 1.640, "petrol_95": 1.740, "lpg": 0.990})
    res = normalize_country_fuel_prices(
        "DE",
        live_local_prices={"lpg": 0.99},
        source="partial_feed",
        license_name="CC BY 4.0",
        data_date="2026-11-20",
        fx_entry=_fx("EUR", 1.0),
        previous_entry=prev,
        allow_jump_iso2=frozenset(),
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert res.accepted is False
    assert res.entry.eur_per_liter == pytest.approx(1.640)
    assert res.entry.source == "ec_weekly_oil_bulletin"
    assert res.entry.fallback_used is True
    assert any(
        a.code == "price_anchor_missing" and a.severity == "warning" and a.scope == "DE"
        for a in res.alerts
    )
