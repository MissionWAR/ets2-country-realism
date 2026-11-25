"""Phase 5 (GLB-03) global 225-territory & ~156-currency registry expansion contract tests."""

from __future__ import annotations

import json
import pathlib
import re

import pytest
from pydantic import ValidationError

from ets2v2.baseline.models import CountriesBaseline
from ets2v2.normalize.currencies import (
    ALL_CURRENCY_SANITY_BANDS,
    ALL_LOCKFILE_TERRITORY_ISO2S,
    ALL_REFERENCE_FX_RATES,
    ALL_TERRITORY_CURRENCIES,
    BAM_FIXED_PEG_PER_EUR,
    CORE_REFERENCE_FX_RATES,
    CURRENCY_SANITY_BANDS,
    DEFAULT_CURRENCIES_JSON_PATH,
    DEFAULT_TIER3_BASELINES_JSON_PATH,
    ECB_COVERED_CURRENCIES,
    EUROPEAN_TERRITORY_ISO2S,
    EXTENDED_CURRENCY_SANITY_BANDS,
    EXTENDED_ECB_CURRENCIES,
    EXTENDED_GLOBAL_CURRENCIES,
    EXTENDED_PROMODS_CURRENCIES,
    EXTENDED_REFERENCE_FX_RATES,
    EXTRA_EU_TERRITORY_ISO2S,
    MAJOR_ECB_CURRENCIES,
    PROMODS_EXTENDED_ISO2S,
    PROMODS_SEED_EUR_PRICES,
    TERRITORY_CURRENCIES,
    TIER3_CURATED_BASELINE_LICENSE,
    TIER3_CURATED_BASELINE_SOURCE,
    VANILLA_36_ISO2S,
    VANILLA_SLUG_TO_ISO2,
    VOLATILE_NON_ECB_CURRENCIES,
    CurrencyMetadataEntry,
    CurrencyRegistry,
    Tier3FuelBaselineEntry,
    Tier3FuelBaselineRegistry,
    load_currency_registry,
    load_tier3_fuel_baselines,
)
from ets2v2.normalize.fuel import (
    SEEDED_LOCKFILE_SOURCES,
    normalize_country_fuel_prices,
)
from ets2v2.normalize.fx import (
    CBR_FX_PROVIDER,
    ECB_FX_PROVIDER,
    FAWAZ_FX_PROVIDER,
    PRIMARY_FX_PROVIDER,
    FxProviderQuote,
    cross_validate_fx_rates,
)
from ets2v2.normalize.lockfile import (
    BASELINE_SEEDED_SOURCE,
    PROMODS_CURATED_SEED_SOURCE,
    seed_initial_lockfile,
)
from ets2v2.normalize.totem_format import (
    EXTENDED_INTEGER_CURRENCY_ISO2S,
    THREE_DEC_NATIONAL_ISO2S,
    format_national_pump_price,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"

_FORBIDDEN_TAINT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("CC BY-SA", re.compile(r"cc[\s-]*by[\s-]*sa", re.IGNORECASE)),
    ("ODbL", re.compile(r"\bodbl\b", re.IGNORECASE)),
    ("OpenStreetMap", re.compile(r"openstreetmap", re.IGNORECASE)),
    ("osm-legal-default-speeds", re.compile(r"osm-legal-default-speeds", re.IGNORECASE)),
    ("GlobalPetrolPrices", re.compile(r"globalpetrolprices", re.IGNORECASE)),
    ("CC BY-NC-ND", re.compile(r"cc[\s-]*by[\s-]*nc[\s-]*nd", re.IGNORECASE)),
    ("MyLPG", re.compile(r"\bmylpg\b", re.IGNORECASE)),
    ("IEA", re.compile(r"(?:international\s+energy\s+agency|\biea\b)", re.IGNORECASE)),
)


def _assert_clean_room_canonical_json(path: pathlib.Path, model_dump: object) -> None:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM detected in {path}"
    assert b"\r" not in raw, f"CRLF line endings detected in {path}"
    text = raw.decode("utf-8")
    expected = json.dumps(model_dump, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert text == expected, f"Non-canonical sorted JSON formatting in {path}"
    for label, pattern in _FORBIDDEN_TAINT_PATTERNS:
        assert pattern.search(text) is None, f"Forbidden taint marker {label!r} found in {path}"


def test_currencies_json_schema_hygiene_and_taint_free(tmp_path: pathlib.Path) -> None:
    assert DEFAULT_CURRENCIES_JSON_PATH.is_file()
    registry = load_currency_registry()
    assert isinstance(registry, CurrencyRegistry)
    assert registry.schema_version == 1
    _assert_clean_room_canonical_json(
        DEFAULT_CURRENCIES_JSON_PATH,
        registry.model_dump(mode="json"),
    )

    pinned = [c for c, m in registry.currencies.items() if m.tier == "pinned"]
    core = [c for c, m in registry.currencies.items() if m.tier == "core"]
    extended = [c for c, m in registry.currencies.items() if m.tier == "extended"]
    assert pinned == ["EUR"]
    assert len(core) == 16
    assert len(extended) == 134
    assert len(registry.currencies) == 151
    assert len(registry.territory_currencies) == 225
    assert set(registry.territory_currencies.values()) == set(registry.currencies.keys())

    for iso2, code in registry.territory_currencies.items():
        assert len(iso2) == 2 and iso2.isupper()
        assert code in registry.currencies

    # Verified 2024-2026 ISO-4217 currency updates
    assert registry.territory_currencies["CW"] == "XCG"
    assert registry.territory_currencies["SX"] == "XCG"
    assert registry.territory_currencies["ZW"] == "ZWG"
    assert registry.territory_currencies["SL"] == "SLE"
    assert registry.territory_currencies["BG"] == "EUR"
    assert registry.currencies["SYP"].sanity_min == pytest.approx(80.0)
    assert registry.currencies["SYP"].sanity_max == pytest.approx(250.0)

    # Negative schema & hygiene checks
    bom_file = tmp_path / "bom.json"
    bom_file.write_bytes(b"\xef\xbb\xbf" + DEFAULT_CURRENCIES_JSON_PATH.read_bytes())
    with pytest.raises(ValueError, match="UTF-8"):
        load_currency_registry(bom_file)

    crlf_file = tmp_path / "crlf.json"
    crlf_file.write_bytes(DEFAULT_CURRENCIES_JSON_PATH.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="LF"):
        load_currency_registry(crlf_file)

    with pytest.raises(ValidationError):
        CurrencyMetadataEntry.model_validate(
            {
                "tier": "extended",
                "ecb_covered": False,
                "major_ecb": False,
                "reference_rate_per_eur": 500.0,
                "sanity_min": 10.0,
                "sanity_max": 100.0,
            }
        )

    with pytest.raises(ValidationError):
        CurrencyMetadataEntry.model_validate(
            {
                "tier": "extended",
                "ecb_covered": False,
                "major_ecb": False,
                "reference_rate_per_eur": 50.0,
                "sanity_min": 10.0,
                "sanity_max": 100.0,
                "unexpected_extra": True,
            }
        )


def test_tier3_fuel_baselines_json_schema_hygiene_and_floor_clamping(
    tmp_path: pathlib.Path,
) -> None:
    assert DEFAULT_TIER3_BASELINES_JSON_PATH.is_file()
    baselines_reg = load_tier3_fuel_baselines()
    assert isinstance(baselines_reg, Tier3FuelBaselineRegistry)
    assert baselines_reg.schema_version == 1
    assert baselines_reg.license == "CC BY 4.0"
    _assert_clean_room_canonical_json(
        DEFAULT_TIER3_BASELINES_JSON_PATH,
        baselines_reg.model_dump(mode="json"),
    )

    expected_iso2s = ALL_LOCKFILE_TERRITORY_ISO2S - EUROPEAN_TERRITORY_ISO2S
    assert len(expected_iso2s) == 186
    assert set(baselines_reg.baselines) == expected_iso2s

    for iso2, entry in baselines_reg.baselines.items():
        assert isinstance(entry, Tier3FuelBaselineEntry)
        assert 0.01 <= entry.diesel_eur_per_liter <= 5.00, iso2
        assert 0.01 <= entry.petrol_95_eur_per_liter <= 5.00, iso2
        assert entry.source_note.strip()

    # D-11: Ultra-subsidized oil producers clamped and annotated at 0.010 EUR/L floor
    assert baselines_reg.baselines["IR"].clamped_to_floor is True
    assert baselines_reg.baselines["IR"].diesel_eur_per_liter == pytest.approx(0.01)
    assert baselines_reg.baselines["VE"].clamped_to_floor is True
    assert baselines_reg.baselines["VE"].diesel_eur_per_liter == pytest.approx(0.01)

    # Negative hygiene & bounds checks
    bom_file = tmp_path / "bom_t3.json"
    bom_file.write_bytes(b"\xef\xbb\xbf" + DEFAULT_TIER3_BASELINES_JSON_PATH.read_bytes())
    with pytest.raises(ValueError, match="UTF-8"):
        load_tier3_fuel_baselines(bom_file)

    crlf_file = tmp_path / "crlf_t3.json"
    crlf_file.write_bytes(DEFAULT_TIER3_BASELINES_JSON_PATH.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="LF"):
        load_tier3_fuel_baselines(crlf_file)

    with pytest.raises(ValidationError):
        Tier3FuelBaselineEntry.model_validate(
            {
                "diesel_eur_per_liter": 0.005,
                "petrol_95_eur_per_liter": 0.02,
                "clamped_to_floor": True,
                "verified_date": "2026-11-25",
                "source_note": "Below ETS2 floor",
            }
        )

    with pytest.raises(ValidationError):
        Tier3FuelBaselineEntry.model_validate(
            {
                "diesel_eur_per_liter": 0.90,
                "petrol_95_eur_per_liter": 0.95,
                "clamped_to_floor": False,
                "verified_date": "2026-11-25",
                "source_note": "Extra field check",
                "extra_key": 123,
            }
        )


def test_normalize_currencies_backwards_compatible_exports() -> None:
    assert len(VANILLA_SLUG_TO_ISO2) == 36
    assert len(VANILLA_36_ISO2S) == 36
    assert len(EXTRA_EU_TERRITORY_ISO2S) == 3
    assert len(EUROPEAN_TERRITORY_ISO2S) == 39
    assert len(PROMODS_EXTENDED_ISO2S) == 37
    assert len(ALL_LOCKFILE_TERRITORY_ISO2S) == 225
    assert len(TERRITORY_CURRENCIES) == 39
    assert len(ALL_TERRITORY_CURRENCIES) == 225
    assert len(MAJOR_ECB_CURRENCIES) == 10
    assert len(VOLATILE_NON_ECB_CURRENCIES) == 6
    assert len(ECB_COVERED_CURRENCIES) == 11
    assert len(EXTENDED_ECB_CURRENCIES) == 18
    expected_ext_ecb = frozenset(
        {
            "AUD",
            "BRL",
            "CAD",
            "CNY",
            "HKD",
            "IDR",
            "ILS",
            "INR",
            "JPY",
            "KRW",
            "MXN",
            "MYR",
            "NZD",
            "PHP",
            "SGD",
            "THB",
            "USD",
            "ZAR",
        }
    )
    assert expected_ext_ecb == EXTENDED_ECB_CURRENCIES
    assert len(EXTENDED_PROMODS_CURRENCIES) == 24
    assert EXTENDED_PROMODS_CURRENCIES < EXTENDED_GLOBAL_CURRENCIES
    assert len(CURRENCY_SANITY_BANDS) == 16
    assert len(EXTENDED_CURRENCY_SANITY_BANDS) == len(EXTENDED_GLOBAL_CURRENCIES)
    assert len(CORE_REFERENCE_FX_RATES) == 17
    assert len(EXTENDED_REFERENCE_FX_RATES) == len(EXTENDED_GLOBAL_CURRENCIES)
    assert len(ALL_REFERENCE_FX_RATES) == 151
    assert set(ALL_TERRITORY_CURRENCIES.values()) == set(ALL_REFERENCE_FX_RATES.keys())
    assert len(ALL_CURRENCY_SANITY_BANDS) == len(ALL_REFERENCE_FX_RATES) - 1
    assert pytest.approx(1.95583) == BAM_FIXED_PEG_PER_EUR
    assert len(PROMODS_SEED_EUR_PRICES) == 37
    assert ALL_TERRITORY_CURRENCIES["CW"] == "XCG"
    assert ALL_TERRITORY_CURRENCIES["SX"] == "XCG"
    assert ALL_TERRITORY_CURRENCIES["ZW"] == "ZWG"
    assert ALL_TERRITORY_CURRENCIES["SL"] == "SLE"
    assert ALL_TERRITORY_CURRENCIES["BG"] == "EUR"
    assert TIER3_CURATED_BASELINE_SOURCE == "tier3_curated_baseline"
    assert TIER3_CURATED_BASELINE_LICENSE == "CC BY 4.0"
    assert TIER3_CURATED_BASELINE_SOURCE in SEEDED_LOCKFILE_SOURCES


def _core_provider_quotes() -> dict[str, FxProviderQuote]:
    core_rates = {c: v for c, v in CORE_REFERENCE_FX_RATES.items() if c != "EUR"}
    ecb_rates = {c: core_rates[c] for c in ECB_COVERED_CURRENCIES}
    return {
        PRIMARY_FX_PROVIDER: FxProviderQuote(
            provider=PRIMARY_FX_PROVIDER,
            data_date="2026-11-25",
            rates=dict(core_rates),
        ),
        ECB_FX_PROVIDER: FxProviderQuote(
            provider=ECB_FX_PROVIDER,
            data_date="2026-11-25",
            rates=ecb_rates,
        ),
        FAWAZ_FX_PROVIDER: FxProviderQuote(
            provider=FAWAZ_FX_PROVIDER,
            data_date="2026-11-25",
            rates=dict(core_rates),
        ),
        CBR_FX_PROVIDER: FxProviderQuote(
            provider=CBR_FX_PROVIDER,
            data_date="2026-11-25",
            rates={"RUB": core_rates["RUB"]},
        ),
    }


def test_isolated_global_fx_validation_and_redenomination_guards() -> None:
    quotes = _core_provider_quotes()

    # Default include_extended=False returns strictly 17 Core European currencies
    core_only = cross_validate_fx_rates(
        quotes,
        previous_fx=None,
        fetched_at="2026-11-25T06:00:00Z",
    )
    assert core_only.ok is True
    assert len(core_only.rates) == 17

    # include_extended=True isolates missing exotic currencies cleanly without failing Core CI
    extended = cross_validate_fx_rates(
        quotes,
        previous_fx=None,
        fetched_at="2026-11-25T06:00:00Z",
        include_extended=True,
    )
    assert extended.ok is True
    assert len(extended.rates) == len(ALL_REFERENCE_FX_RATES)
    fallback_scopes = {
        a.scope
        for a in extended.alerts
        if a.code == "fx_reference_fallback" and a.severity == "warning"
    }
    for exotic in ("XCG", "ZWG", "SLE", "VES", "IRR", "KPW", "SYP"):
        assert exotic in fallback_scopes
        assert extended.rates[exotic].fallback_used is True

    # Un-redenominated SLL (~24,000) or pre-2026 SYP (~14,000) rejected cleanly via sanity bands
    poisoned_primary_rates = dict(quotes[PRIMARY_FX_PROVIDER].rates)
    poisoned_primary_rates["SLE"] = 24000.0
    poisoned_primary_rates["SYP"] = 14000.0
    poisoned_quotes = {
        **quotes,
        PRIMARY_FX_PROVIDER: FxProviderQuote(
            provider=PRIMARY_FX_PROVIDER,
            data_date="2026-11-25",
            rates=poisoned_primary_rates,
        ),
    }
    poisoned_res = cross_validate_fx_rates(
        poisoned_quotes,
        previous_fx=None,
        fetched_at="2026-11-25T06:00:00Z",
        include_extended=True,
    )
    assert poisoned_res.ok is True
    assert poisoned_res.rates["SLE"].rate_per_eur == pytest.approx(ALL_REFERENCE_FX_RATES["SLE"])
    assert poisoned_res.rates["SYP"].rate_per_eur == pytest.approx(ALL_REFERENCE_FX_RATES["SYP"])
    assert any(
        a.code == "fx_sanity_rejected" and a.scope == "SLE" and a.severity == "warning"
        for a in poisoned_res.alerts
    )
    assert any(
        a.code == "fx_sanity_rejected" and a.scope == "SYP" and a.severity == "warning"
        for a in poisoned_res.alerts
    )

    # Core European non-EUR currency outage (PLN) still fails hard!
    missing_pln_quotes = {
        name: FxProviderQuote(
            provider=q.provider,
            data_date=q.data_date,
            rates={k: v for k, v in q.rates.items() if k != "PLN"},
        )
        for name, q in quotes.items()
    }
    failed_core = cross_validate_fx_rates(
        missing_pln_quotes,
        previous_fx=None,
        fetched_at="2026-11-25T06:00:00Z",
        include_extended=True,
    )
    assert failed_core.ok is False
    assert "PLN" in failed_core.missing_currencies


def test_ultra_subsidized_floor_clamping_vs_live_bounds_enforcement() -> None:
    baseline_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    lock = seed_initial_lockfile(baseline_countries)
    assert len(lock.countries) == 225
    assert len(lock.fx_rates) == len(ALL_REFERENCE_FX_RATES)

    # IR and VE are clamped cleanly at 0.010 EUR/L (never underflowing to 0.000)
    for iso2 in ("IR", "VE"):
        entry = lock.countries[iso2]
        assert entry.eur_per_liter == pytest.approx(0.01)
        assert entry.source == TIER3_CURATED_BASELINE_SOURCE
        assert entry.license == TIER3_CURATED_BASELINE_LICENSE
        assert entry.local_prices["diesel"] > 0.0

    # Core and ProMods seed provenance remain intact
    assert lock.countries["DE"].source == BASELINE_SEEDED_SOURCE
    assert lock.countries["AD"].source == PROMODS_CURATED_SEED_SOURCE
    assert lock.countries["US"].source == TIER3_CURATED_BASELINE_SOURCE

    # Live fuel feeds MUST still enforce the hard [0.01, 5.00] EUR/L lower bound!
    us_fx = lock.fx_rates["USD"]
    corrupt_live = normalize_country_fuel_prices(
        "US",
        live_local_prices={"diesel": 0.005, "petrol_95": 0.85},
        source="us_eia_v2",
        license_name="U.S. Public Domain",
        data_date="2026-11-25",
        fx_entry=us_fx,
        previous_entry=lock.countries["US"],
        allow_jump_iso2=frozenset(),
        fetched_at="2026-11-25T06:00:00Z",
    )
    assert corrupt_live.accepted is False
    assert any(a.code == "price_bounds_rejected" for a in corrupt_live.alerts)

    # First live Tier 1 transition from Tier 3 seed bypasses false >25% WoW rejection
    first_live = normalize_country_fuel_prices(
        "US",
        live_local_prices={"diesel": 1.45, "petrol_95": 1.35},
        source="us_eia_v2",
        license_name="U.S. Public Domain",
        data_date="2026-11-25",
        fx_entry=us_fx,
        previous_entry=lock.countries["US"],
        allow_jump_iso2=frozenset(),
        fetched_at="2026-11-25T06:00:00Z",
    )
    assert first_live.accepted is True
    assert first_live.entry.source == "us_eia_v2"


@pytest.mark.parametrize(
    ("iso2", "local_price", "expected"),
    [
        ("JP", 155.4, "155"),
        ("KR", 1689.6, "1690"),
        ("ID", 6800.4, "6800"),
        ("VN", 21450.5, "21451"),
        ("CL", 1049.6, "1050"),
        ("CO", 2950.2, "2950"),
        ("PY", 7290.5, "7291"),
        ("UG", 5120.4, "5120"),
        ("TZ", 3150.6, "3151"),
        ("RW", 1620.4, "1620"),
        ("IR", 450.4, "450"),
        ("KH", 4150.6, "4151"),
        ("LA", 22500.4, "22500"),
        ("MM", 2750.5, "2751"),
        ("KW", 0.1154, "0.115"),
        ("BH", 0.1805, "0.181"),
        ("OM", 0.2584, "0.258"),
    ],
)
def test_global_totem_formatting_integer_and_three_decimal_markets(
    iso2: str,
    local_price: float,
    expected: str,
) -> None:
    if len(expected.split(".")) == 1:
        assert iso2 in EXTENDED_INTEGER_CURRENCY_ISO2S
    else:
        assert iso2 in THREE_DEC_NATIONAL_ISO2S
    assert format_national_pump_price(iso2, local_price) == expected
