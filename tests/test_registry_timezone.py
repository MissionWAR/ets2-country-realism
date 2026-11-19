"""Unit and contract tests for dynamic zoneinfo + tzdata seasonal DST resolution."""

from __future__ import annotations

import importlib.metadata
import pathlib
from datetime import date
from zoneinfo import ZoneInfoNotFoundError

import pytest

from ets2v2.baseline.models import CountriesBaseline, LocalesBaseline
from ets2v2.registry import load_law_registry
from ets2v2.registry.timezone import (
    DEFAULT_ANCHOR_YEAR,
    IANA_NUMERIC_ABBR_OVERRIDES,
    SUMMER_ANCHOR_MONTH_DAY,
    WINTER_ANCHOR_MONTH_DAY,
    ResolvedTimezone,
    assert_leftside_traffic_immutable,
    resolve_ets2_timezone,
    resolve_season_anchor_date,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"

EXPECTED_TWELVE_TZ_KEYS: frozenset[str] = frozenset(
    {
        "tz_bst",
        "tz_cdt",
        "tz_cest",
        "tz_eest",
        "tz_eet",
        "tz_gmt",
        "tz_mdt",
        "tz_msk",
        "tz_mst",
        "tz_pdt",
        "tz_trt",
        "tz_west",
    }
)

FORBIDDEN_TZ_TOKENS: frozenset[str] = frozenset({"@@tz_cet@@", "@@tz_wet@@", "@@tz_ast@@"})

CET_ISO2: frozenset[str] = frozenset(
    {
        "AL",
        "AT",
        "BA",
        "BE",
        "CH",
        "CZ",
        "DE",
        "DK",
        "ES",
        "FR",
        "HR",
        "HU",
        "IT",
        "LU",
        "ME",
        "MK",
        "NL",
        "NO",
        "PL",
        "RS",
        "SE",
        "SI",
        "SK",
        "XK",
    }
)
EET_ISO2: frozenset[str] = frozenset({"BG", "EE", "FI", "GR", "LT", "LV", "RO"})


def _load_baseline_locales() -> LocalesBaseline:
    return LocalesBaseline.model_validate_json((BASELINE_DIR / "locales.json").read_text("utf-8"))


def _load_baseline_countries() -> CountriesBaseline:
    return CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )


def test_tzdata_package_is_installed() -> None:
    version = importlib.metadata.version("tzdata")
    assert version


def test_resolve_season_anchor_date_defaults_custom_year_and_override() -> None:
    assert DEFAULT_ANCHOR_YEAR == 2026
    assert SUMMER_ANCHOR_MONTH_DAY == (7, 15)
    assert WINTER_ANCHOR_MONTH_DAY == (1, 15)

    assert resolve_season_anchor_date("summer") == date(DEFAULT_ANCHOR_YEAR, 7, 15)
    assert resolve_season_anchor_date("winter") == date(DEFAULT_ANCHOR_YEAR, 1, 15)
    assert resolve_season_anchor_date("summer", anchor_year=2028) == date(2028, 7, 15)
    assert resolve_season_anchor_date("winter", anchor_year=2028) == date(2028, 1, 15)

    dst_boundary = date(2026, 3, 29)
    equinox = date(2026, 9, 22)
    assert resolve_season_anchor_date("summer", override_date=dst_boundary) == dst_boundary
    assert resolve_season_anchor_date("winter", anchor_year=2024, override_date=equinox) == equinox


def test_all_36_countries_summer_matches_1_62_baseline_and_kaliningrad_preserved() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    baseline_countries = _load_baseline_countries()
    baseline_locales = _load_baseline_locales()

    assert frozenset(baseline_locales.tz_keys) == EXPECTED_TWELVE_TZ_KEYS
    assert len(registry.laws_by_iso2) == 36

    baseline_by_slug = {country.slug: country for country in baseline_countries.countries}
    summer_date = resolve_season_anchor_date("summer")

    for iso2, law in sorted(registry.laws_by_iso2.items()):
        bl_country = baseline_by_slug[law.ets2_slug]
        resolved = resolve_ets2_timezone(
            law.iana_timezone,
            summer_date,
            baseline_locales.tz_keys,
        )
        assert isinstance(resolved, ResolvedTimezone)
        assert resolved.iana_timezone == law.iana_timezone
        assert resolved.ref_date == summer_date.isoformat()
        assert resolved.offset_minutes == bl_country.time_zone, f"{iso2} summer offset mismatch"
        assert resolved.ets2_time_zone_name == bl_country.time_zone_name, (
            f"{iso2} summer time_zone_name mismatch"
        )
        assert resolved.ets2_time_zone_name not in FORBIDDEN_TZ_TOKENS

    # Russia secondary Kaliningrad timezone remains permanent +120 / "@@tz_eet@@"
    bl_ru = baseline_by_slug["russia"]
    assert bl_ru.secondary_time_zone == [120]
    assert bl_ru.secondary_time_zone_name == ["@@tz_eet@@"]
    for ref_date in (resolve_season_anchor_date("summer"), resolve_season_anchor_date("winter")):
        kaliningrad = resolve_ets2_timezone(
            "Europe/Kaliningrad", ref_date, baseline_locales.tz_keys
        )
        assert kaliningrad.offset_minutes == 120
        assert kaliningrad.ets2_time_zone_name == "@@tz_eet@@"
        assert kaliningrad.is_dst is False
        assert kaliningrad.observes_dst is False


def test_all_36_countries_winter_offsets_names_and_whitelist() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    baseline_locales = _load_baseline_locales()
    winter_date = resolve_season_anchor_date("winter")

    assert len(CET_ISO2) == 24
    assert len(EET_ISO2) == 7
    assert CET_ISO2 | EET_ISO2 | {"PT", "GB", "IS", "RU", "TR"} == set(registry.laws_by_iso2)

    cet_count = 0
    eet_count = 0
    for iso2, law in sorted(registry.laws_by_iso2.items()):
        resolved = resolve_ets2_timezone(
            law.iana_timezone,
            winter_date,
            baseline_locales.tz_keys,
        )
        assert resolved.ref_date == winter_date.isoformat()
        assert resolved.is_dst is False
        assert resolved.ets2_time_zone_name not in FORBIDDEN_TZ_TOKENS

        if resolved.ets2_time_zone_name.startswith("@@"):
            assert resolved.ets2_time_zone_name.endswith("@@")
            token_key = resolved.ets2_time_zone_name[2:-2]
            assert token_key in EXPECTED_TWELVE_TZ_KEYS

        if iso2 in CET_ISO2:
            cet_count += 1
            assert resolved.offset_minutes == 60
            assert resolved.abbreviation == "CET"
            assert resolved.ets2_time_zone_name == "CET"
            assert resolved.observes_dst is True
        elif iso2 in EET_ISO2:
            eet_count += 1
            assert resolved.offset_minutes == 120
            assert resolved.abbreviation == "EET"
            assert resolved.ets2_time_zone_name == "@@tz_eet@@"
            assert resolved.observes_dst is True
        elif iso2 == "PT":
            assert resolved.offset_minutes == 0
            assert resolved.abbreviation == "WET"
            assert resolved.ets2_time_zone_name == "WET"
            assert resolved.observes_dst is True
        elif iso2 == "GB":
            assert resolved.offset_minutes == 0
            assert resolved.abbreviation == "GMT"
            assert resolved.ets2_time_zone_name == "@@tz_gmt@@"
            assert resolved.observes_dst is True
        elif iso2 == "IS":
            assert resolved.offset_minutes == 0
            assert resolved.abbreviation == "GMT"
            assert resolved.ets2_time_zone_name == "@@tz_gmt@@"
            assert resolved.observes_dst is False
        elif iso2 == "RU":
            assert resolved.offset_minutes == 180
            assert resolved.abbreviation == "MSK"
            assert resolved.ets2_time_zone_name == "@@tz_msk@@"
            assert resolved.observes_dst is False
        elif iso2 == "TR":
            assert resolved.offset_minutes == 180
            assert resolved.abbreviation == "TRT"
            assert resolved.ets2_time_zone_name == "@@tz_trt@@"
            assert resolved.observes_dst is False
        else:
            pytest.fail(f"Unexpected country ISO2: {iso2}")

    assert cet_count == 24
    assert eet_count == 7


@pytest.mark.parametrize(
    ("iana_tz", "expected_abbr", "expected_ets2_name"),
    [
        ("Europe/Istanbul", "TRT", "@@tz_trt@@"),
        ("Asia/Amman", "AST", "AST"),
        ("Asia/Damascus", "AST", "AST"),
    ],
)
@pytest.mark.parametrize(
    "ref_date",
    [date(2026, 7, 15), date(2026, 1, 15)],
)
def test_permanent_utc_plus_3_numeric_tzname_overrides(
    iana_tz: str,
    expected_abbr: str,
    expected_ets2_name: str,
    ref_date: date,
) -> None:
    baseline_locales = _load_baseline_locales()
    assert IANA_NUMERIC_ABBR_OVERRIDES[iana_tz] == expected_abbr

    resolved = resolve_ets2_timezone(iana_tz, ref_date, baseline_locales.tz_keys)
    assert resolved.offset_minutes == 180
    assert resolved.abbreviation == expected_abbr
    assert resolved.ets2_time_zone_name == expected_ets2_name
    assert resolved.ets2_time_zone_name != "+03"
    assert resolved.ets2_time_zone_name not in FORBIDDEN_TZ_TOKENS
    assert resolved.is_dst is False
    assert resolved.observes_dst is False


@pytest.mark.parametrize(
    ("iana_tz", "expected_offset", "expected_abbr"),
    [
        ("Asia/Tbilisi", 240, "UTC+4"),
        ("Asia/Tehran", 210, "UTC+3:30"),
        ("America/Sao_Paulo", -180, "UTC-3"),
    ],
)
def test_unmapped_numeric_tzname_deterministic_utc_fallback(
    iana_tz: str,
    expected_offset: int,
    expected_abbr: str,
) -> None:
    resolved = resolve_ets2_timezone(iana_tz, date(2026, 1, 15), EXPECTED_TWELVE_TZ_KEYS)
    assert resolved.offset_minutes == expected_offset
    assert resolved.abbreviation == expected_abbr
    assert resolved.ets2_time_zone_name == expected_abbr


def test_supported_tz_keys_whitelist_controls_token_wrapping() -> None:
    # Empty whitelist must emit plain abbreviations, never @@tz_*@@
    berlin_summer = resolve_ets2_timezone("Europe/Berlin", date(2026, 7, 15), ())
    assert berlin_summer.offset_minutes == 120
    assert berlin_summer.abbreviation == "CEST"
    assert berlin_summer.ets2_time_zone_name == "CEST"
    assert berlin_summer.is_dst is True
    assert berlin_summer.observes_dst is True

    istanbul = resolve_ets2_timezone("Europe/Istanbul", date(2026, 7, 15), ())
    assert istanbul.abbreviation == "TRT"
    assert istanbul.ets2_time_zone_name == "TRT"

    # Explicit 12-key whitelist wraps supported keys and leaves CET/WET/AST plain
    berlin_winter = resolve_ets2_timezone(
        "Europe/Berlin", date(2026, 1, 15), EXPECTED_TWELVE_TZ_KEYS
    )
    lisbon_winter = resolve_ets2_timezone(
        "Europe/Lisbon", date(2026, 1, 15), EXPECTED_TWELVE_TZ_KEYS
    )
    amman_winter = resolve_ets2_timezone("Asia/Amman", date(2026, 1, 15), EXPECTED_TWELVE_TZ_KEYS)
    assert berlin_winter.ets2_time_zone_name == "CET"
    assert lisbon_winter.ets2_time_zone_name == "WET"
    assert amman_winter.ets2_time_zone_name == "AST"
    assert {
        berlin_winter.ets2_time_zone_name,
        lisbon_winter.ets2_time_zone_name,
        amman_winter.ets2_time_zone_name,
    }.isdisjoint(FORBIDDEN_TZ_TOKENS)


@pytest.mark.parametrize("bad_tz", ["Invalid/Nowhere", "Europe/Atlantis"])
def test_invalid_iana_timezone_raises_value_error_chaining_zoneinfo_error(bad_tz: str) -> None:
    with pytest.raises(ValueError, match=bad_tz) as exc_info:
        resolve_ets2_timezone(bad_tz, date(2026, 7, 15), EXPECTED_TWELVE_TZ_KEYS)
    assert isinstance(exc_info.value.__cause__, ZoneInfoNotFoundError)


def test_empty_iana_timezone_raises_value_error() -> None:
    with pytest.raises(ValueError, match="IANA timezone"):
        resolve_ets2_timezone("", date(2026, 7, 15), EXPECTED_TWELVE_TZ_KEYS)


def test_leftside_traffic_immutability_guard_and_armenia_edge_case() -> None:
    baseline_countries = _load_baseline_countries()
    lht_slugs = [c.slug for c in baseline_countries.countries if c.leftside_traffic is True]
    assert lht_slugs == ["uk"]

    for country in baseline_countries.countries:
        assert_leftside_traffic_immutable(
            country.slug,
            country.leftside_traffic,
            country.leftside_traffic,
        )

    # Simulated Armenia (D-02) matching right-hand traffic passes
    assert_leftside_traffic_immutable("armenia", False, False)
    assert_leftside_traffic_immutable("armenia", None, None)
    assert_leftside_traffic_immutable("armenia", None, False)

    # Flipping Armenia or any non-UK country to leftside_traffic=True MUST fail
    with pytest.raises(ValueError, match="leftside_traffic"):
        assert_leftside_traffic_immutable("armenia", False, True)
    with pytest.raises(ValueError, match="leftside_traffic"):
        assert_leftside_traffic_immutable("armenia", None, True)
    with pytest.raises(ValueError, match="leftside_traffic"):
        assert_leftside_traffic_immutable("germany", None, True)

    # Flipping UK away from leftside_traffic=True MUST also fail
    with pytest.raises(ValueError, match="leftside_traffic"):
        assert_leftside_traffic_immutable("uk", True, False)
    with pytest.raises(ValueError, match="leftside_traffic"):
        assert_leftside_traffic_immutable("uk", True, None)
