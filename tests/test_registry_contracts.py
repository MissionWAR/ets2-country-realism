"""Contract tests for committed 36-country realism law JSONs and ETS2 mappings."""

from __future__ import annotations

import pathlib

import pytest

from ets2_realism.baseline.models import CountriesBaseline
from ets2_realism.cli import main
from ets2_realism.registry import (
    load_country_aliases,
    load_law_registry,
    serialize_registry_json_bytes,
    validate_law_registry,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
LAWS_DIR = DATA_DIR / "laws"
COUNTRIES_LAWS_DIR = LAWS_DIR / "countries"
MAPPINGS_PATH = DATA_DIR / "mappings" / "ets2_countries.json"
ALIASES_PATH = DATA_DIR / "mappings" / "country_aliases.json"
BASELINE_DIR = DATA_DIR / "baselines" / "ets2_1.62_def"

EXPECTED_CURRENCIES: dict[str, str] = {
    "AL": "ALL",
    "AT": "EUR",
    "BA": "BAM",
    "BE": "EUR",
    "BG": "EUR",
    "CH": "CHF",
    "CZ": "CZK",
    "DE": "EUR",
    "DK": "DKK",
    "EE": "EUR",
    "ES": "EUR",
    "FI": "EUR",
    "FR": "EUR",
    "GB": "GBP",
    "GR": "EUR",
    "HR": "EUR",
    "HU": "HUF",
    "IS": "ISK",
    "IT": "EUR",
    "LT": "EUR",
    "LU": "EUR",
    "LV": "EUR",
    "ME": "EUR",
    "MK": "MKD",
    "NL": "EUR",
    "NO": "NOK",
    "PL": "PLN",
    "PT": "EUR",
    "RO": "RON",
    "RS": "RSD",
    "RU": "RUB",
    "SE": "SEK",
    "SI": "EUR",
    "SK": "EUR",
    "TR": "TRY",
    "XK": "EUR",
}

EXPECTED_TIMEZONES: dict[str, str] = {
    "AL": "Europe/Tirane",
    "AT": "Europe/Vienna",
    "BA": "Europe/Sarajevo",
    "BE": "Europe/Brussels",
    "BG": "Europe/Sofia",
    "CH": "Europe/Zurich",
    "CZ": "Europe/Prague",
    "DE": "Europe/Berlin",
    "DK": "Europe/Copenhagen",
    "EE": "Europe/Tallinn",
    "ES": "Europe/Madrid",
    "FI": "Europe/Helsinki",
    "FR": "Europe/Paris",
    "GB": "Europe/London",
    "GR": "Europe/Athens",
    "HR": "Europe/Zagreb",
    "HU": "Europe/Budapest",
    "IS": "Atlantic/Reykjavik",
    "IT": "Europe/Rome",
    "LT": "Europe/Vilnius",
    "LU": "Europe/Luxembourg",
    "LV": "Europe/Riga",
    "ME": "Europe/Podgorica",
    "MK": "Europe/Skopje",
    "NL": "Europe/Amsterdam",
    "NO": "Europe/Oslo",
    "PL": "Europe/Warsaw",
    "PT": "Europe/Lisbon",
    "RO": "Europe/Bucharest",
    "RS": "Europe/Belgrade",
    "RU": "Europe/Moscow",
    "SE": "Europe/Stockholm",
    "SI": "Europe/Ljubljana",
    "SK": "Europe/Bratislava",
    "TR": "Europe/Istanbul",
    "XK": "Europe/Belgrade",
}

YEAR_ROUND_DRL_TRUE: frozenset[str] = frozenset(
    {
        "BA",
        "BG",
        "CH",
        "CZ",
        "DK",
        "EE",
        "FI",
        "HU",
        "IS",
        "IT",
        "LT",
        "LV",
        "ME",
        "MK",
        "NO",
        "PL",
        "RO",
        "RS",
        "RU",
        "SE",
        "SI",
        "SK",
        "XK",
    }
)
YEAR_ROUND_DRL_FALSE: frozenset[str] = frozenset(
    {"AL", "AT", "BE", "DE", "ES", "FR", "GB", "GR", "LU", "NL", "PT", "TR"}
)


def test_committed_registry_exact_225_global_territories_and_clean_room_hygiene() -> None:
    assert MAPPINGS_PATH.is_file(), f"Missing {MAPPINGS_PATH}"
    assert COUNTRIES_LAWS_DIR.is_dir(), f"Missing {COUNTRIES_LAWS_DIR}"

    law_files = sorted(COUNTRIES_LAWS_DIR.glob("*.json"))
    assert len(law_files) == 225

    raw_scs = [
        p for p in DATA_DIR.rglob("*") if p.is_file() and p.suffix.lower() in {".sii", ".sui"}
    ]
    assert raw_scs == []

    bundle = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    assert len(bundle.mappings.countries) == 225
    assert len(bundle.laws_by_iso2) == 225

    vanilla_entries = [e for e in bundle.mappings.countries if e.vanilla_1_62]
    non_vanilla_entries = [e for e in bundle.mappings.countries if not e.vanilla_1_62]
    assert len(vanilla_entries) == 36
    assert len(non_vanilla_entries) == 189
    assert all(e.country_id is not None for e in vanilla_entries)
    assert all(e.country_id is None for e in non_vanilla_entries)

    # 100% coverage of all country_aliases.json ISO-2 targets
    aliases = load_country_aliases(ALIASES_PATH)
    assert {entry.iso2 for entry in aliases.aliases.values()} <= set(bundle.laws_by_iso2)

    expected_promods_sample = {
        "AM",
        "JO",
        "SY",
        "SM",
        "SJ",
        "KZ",
        "CN",
        "MA",
        "TN",
        "EG",
        "IL",
        "SA",
        "IE",
        "CY",
        "MT",
        "UA",
        "MD",
        "UZ",
    }
    non_vanilla_iso2s = {e.iso2 for e in non_vanilla_entries}
    assert expected_promods_sample <= non_vanilla_iso2s

    assert validate_law_registry(LAWS_DIR, MAPPINGS_PATH, BASELINE_DIR) == []

    assert MAPPINGS_PATH.read_bytes() == serialize_registry_json_bytes(bundle.mappings)
    for iso2, record in bundle.laws_by_iso2.items():
        law_file = COUNTRIES_LAWS_DIR / f"{iso2.lower()}.json"
        assert law_file.read_bytes() == serialize_registry_json_bytes(record)


def test_committed_registry_currencies_timezones_and_axle_mass_invariants() -> None:
    bundle = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_by_slug = {c.slug: c for c in bl_countries.countries}
    vanilla_iso2s = {e.iso2 for e in bundle.mappings.countries if e.vanilla_1_62}

    assert vanilla_iso2s == set(EXPECTED_CURRENCIES)
    assert vanilla_iso2s == set(EXPECTED_TIMEZONES)

    for iso2 in sorted(vanilla_iso2s):
        record = bundle.laws_by_iso2[iso2]
        assert record.currency == EXPECTED_CURRENCIES[iso2], f"Currency mismatch for {iso2}"
        assert record.iana_timezone == EXPECTED_TIMEZONES[iso2], f"Timezone mismatch for {iso2}"

        bl = bl_by_slug[record.ets2_slug]
        assert len(record.mass_limit_per_axle_count) >= len(bl.mass_limit_per_axle_count)
        for idx, bl_limit in enumerate(bl.mass_limit_per_axle_count):
            assert record.mass_limit_per_axle_count[idx] >= bl_limit

    assert bundle.laws_by_iso2["IS"].mass_limit_per_axle_count == [
        18000,
        29000,
        38000,
        46000,
        60000,
    ]
    assert bundle.laws_by_iso2["FI"].mass_limit_per_axle_count == [
        18000,
        26000,
        36000,
        44000,
        56000,
        60000,
        68000,
        74000,
        84000,
        105000,
    ]


def test_committed_registry_statutory_drl_policies() -> None:
    bundle = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    vanilla_iso2s = {e.iso2 for e in bundle.mappings.countries if e.vanilla_1_62}
    assert len(YEAR_ROUND_DRL_TRUE) == 23
    assert len(YEAR_ROUND_DRL_FALSE) == 12
    assert YEAR_ROUND_DRL_TRUE | YEAR_ROUND_DRL_FALSE | {"HR"} == vanilla_iso2s

    for iso2 in YEAR_ROUND_DRL_TRUE:
        rec = bundle.laws_by_iso2[iso2]
        assert rec.summer.lights_mandatory is True, f"{iso2} summer DRL must be True"
        assert rec.winter.lights_mandatory is True, f"{iso2} winter DRL must be True"

    for iso2 in YEAR_ROUND_DRL_FALSE:
        rec = bundle.laws_by_iso2[iso2]
        assert rec.summer.lights_mandatory is False, f"{iso2} summer DRL must be False"
        assert rec.winter.lights_mandatory is False, f"{iso2} winter DRL must be False"

    hr = bundle.laws_by_iso2["HR"]
    assert hr.summer.lights_mandatory is False
    assert hr.winter.lights_mandatory is True

    # Key ProMods statutory DRL, timezone, and speed_unit contracts (D-01)
    for seasonal_iso2 in ("MD", "IL", "PS"):
        rec = bundle.laws_by_iso2[seasonal_iso2]
        assert rec.summer.lights_mandatory is False, f"{seasonal_iso2} summer DRL must be False"
        assert rec.winter.lights_mandatory is True, f"{seasonal_iso2} winter DRL must be True"

    ua = bundle.laws_by_iso2["UA"]
    assert ua.summer.lights_mandatory is True
    assert ua.winter.lights_mandatory is True

    assert bundle.laws_by_iso2["KZ"].iana_timezone == "Asia/Almaty"
    assert bundle.laws_by_iso2["UZ"].iana_timezone == "Asia/Tashkent"
    assert bundle.laws_by_iso2["JO"].iana_timezone == "Asia/Amman"
    assert bundle.laws_by_iso2["SY"].iana_timezone == "Asia/Damascus"

    for mph_iso2 in ("GG", "IM", "JE"):
        assert bundle.laws_by_iso2[mph_iso2].speed_unit == "mph"
    assert bundle.laws_by_iso2["GI"].speed_unit == "kmh"


def test_committed_registry_statutory_speed_fixes_and_seasonal_drops() -> None:
    bundle = load_law_registry(LAWS_DIR, MAPPINGS_PATH)

    # Seasonal winter drops: FI, EE, LT
    fi = bundle.laws_by_iso2["FI"]
    assert [(lane.limit, lane.urban_limit) for lane in fi.summer.speed_limits["car"]] == [
        (80, 50),
        (100, 50),
        (120, 80),
    ]
    assert [(lane.limit, lane.urban_limit) for lane in fi.winter.speed_limits["car"]] == [
        (80, 50),
        (80, 50),
        (100, 80),
    ]

    ee = bundle.laws_by_iso2["EE"]
    assert [(lane.limit, lane.urban_limit) for lane in ee.summer.speed_limits["car"]] == [
        (90, 50),
        (110, 50),
        (110, 90),
    ]
    assert [(lane.limit, lane.urban_limit) for lane in ee.winter.speed_limits["car"]] == [
        (90, 50),
        (90, 50),
        (90, 90),
    ]

    lt = bundle.laws_by_iso2["LT"]
    assert [(lane.limit, lane.urban_limit) for lane in lt.summer.speed_limits["car"]] == [
        (90, 50),
        (120, 50),
        (130, 130),
    ]
    assert [(lane.limit, lane.urban_limit) for lane in lt.winter.speed_limits["car"]] == [
        (90, 50),
        (110, 50),
        (110, 110),
    ]

    # Statutory fixes: AT, HU, IS, TR
    at = bundle.laws_by_iso2["AT"]
    assert [lane.limit for lane in at.summer.speed_limits["car"]] == [100, 100, 130]
    assert [lane.limit for lane in at.winter.speed_limits["car"]] == [100, 100, 130]

    hu = bundle.laws_by_iso2["HU"]
    assert [(lane.limit, lane.max_limit) for lane in hu.summer.speed_limits["truck"]] == [
        (70, 70),
        (70, 70),
        (80, 80),
    ]

    iceland = bundle.laws_by_iso2["IS"]
    assert [
        (lane.limit, lane.urban_limit, lane.max_limit)
        for lane in iceland.summer.speed_limits["truck"]
    ] == [(80, 50, 80), (80, 50, 80), (80, 50, 80)]
    assert iceland.winter.speed_limits["truck"] == iceland.summer.speed_limits["truck"]

    tr = bundle.laws_by_iso2["TR"]
    assert [(lane.limit, lane.urban_limit) for lane in tr.summer.speed_limits["car"]] == [
        (90, 50),
        (110, 50),
        (130, 130),
        (30, 30),
    ]

    # UK imperial mph
    gb = bundle.laws_by_iso2["GB"]
    assert gb.speed_unit == "mph"
    assert [(lane.limit, lane.urban_limit) for lane in gb.summer.speed_limits["car"]] == [
        (60, 30),
        (70, 30),
        (70, 70),
    ]
    assert [(lane.limit, lane.urban_limit) for lane in gb.summer.speed_limits["truck"]] == [
        (50, 30),
        (60, 30),
        (60, 60),
    ]
    assert [(lane.limit, lane.urban_limit) for lane in gb.summer.speed_limits["bus"]] == [
        (50, 30),
        (60, 30),
        (70, 70),
    ]

    # Germany unlimited expressway / motorway (0)
    de = bundle.laws_by_iso2["DE"]
    assert [(lane.limit, lane.urban_limit) for lane in de.summer.speed_limits["car"]] == [
        (100, 50),
        (0, 50),
        (0, 0),
    ]

    # BG/RO/TR slow_road + uncommon flags
    for iso2 in ("BG", "RO", "TR"):
        rec = bundle.laws_by_iso2[iso2]
        for vehicle_class in ("car", "truck", "bus"):
            lanes = rec.summer.speed_limits[vehicle_class]
            assert [lane.lane_speed_class for lane in lanes] == [
                "local_road",
                "expressway",
                "motorway",
                "slow_road",
            ]
            assert [lane.uncommon for lane in lanes] == [False, False, False, True]

    # RO & SE max_limit != limit preserved
    ro_truck = bundle.laws_by_iso2["RO"].summer.speed_limits["truck"]
    assert ro_truck[1].lane_speed_class == "expressway"
    assert ro_truck[1].limit == 80
    assert ro_truck[1].max_limit == 100

    se_truck = bundle.laws_by_iso2["SE"].summer.speed_limits["truck"]
    assert se_truck[0].lane_speed_class == "local_road"
    assert se_truck[0].limit == 70
    assert se_truck[0].max_limit == 80

    # Urban motorway limits preserved on CZ, EE, FI, GR, IS, RU, SK
    expected_urban_motorway = {
        "CZ": 80,
        "EE": 90,
        "FI": 80,
        "GR": 80,
        "IS": 50,
        "RU": 60,
        "SK": 90,
    }
    for iso2, urban_mw in expected_urban_motorway.items():
        car_mw = bundle.laws_by_iso2[iso2].summer.speed_limits["car"][2]
        assert car_mw.lane_speed_class == "motorway"
        assert car_mw.urban_limit == urban_mw, f"{iso2} urban motorway limit mismatch"


def test_cli_registry_validate_default_committed_tree(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["registry", "validate"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "225 countries" in captured.out
