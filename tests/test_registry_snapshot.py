"""Unit, contract, determinism, and CLI tests for schema_version=1 realism snapshots."""

from __future__ import annotations

import json
import pathlib
from datetime import date
from typing import cast

import pytest
from pydantic import ValidationError

from ets2v2.baseline.models import CountriesBaseline, LocalesBaseline
from ets2v2.cli import main
from ets2v2.registry import load_law_registry
from ets2v2.registry.snapshot import (
    RealismSnapshot,
    RealismSnapshotCountry,
    RealismSnapshotFuel,
    build_realism_snapshot,
    serialize_snapshot_bytes,
    write_realism_snapshot,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"

EXPECTED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {"schema_version", "edition", "anchor_date", "baseline_game_version", "countries"}
)
EXPECTED_COUNTRY_KEYS: frozenset[str] = frozenset(
    {
        "iso2",
        "iso3",
        "ets2_slug",
        "iana_timezone",
        "time_zone",
        "time_zone_name",
        "observes_dst",
        "lights_mandatory",
        "driving_tired_offence",
        "imperial_units",
        "mass_limit_per_axle_count",
        "speed_limits",
        "fuel",
    }
)
EXPECTED_FUEL_KEYS: frozenset[str] = frozenset(
    {"currency", "eur_per_liter", "local_prices", "source"}
)


def _load_inputs() -> tuple[CountriesBaseline, LocalesBaseline]:
    countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    return countries, locales


def test_build_summer_and_winter_snapshots_against_committed_data() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()
    bl_by_slug = {c.slug: c for c in bl_countries.countries}

    summer = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")
    winter = build_realism_snapshot(registry, bl_countries, bl_locales, "winter")

    assert summer.schema_version == 1
    assert winter.schema_version == 1
    assert summer.edition == "summer"
    assert winter.edition == "winter"
    assert summer.anchor_date == "2026-07-15"
    assert winter.anchor_date == "2026-01-15"
    assert summer.baseline_game_version == "1.62.3.3"
    assert winter.baseline_game_version == "1.62.3.3"

    assert len(summer.countries) == 36
    assert len(winter.countries) == 36
    assert list(summer.countries.keys()) == sorted(summer.countries.keys())
    assert set(summer.countries.keys()) == set(winter.countries.keys())

    # Croatia seasonal DRL (Nov 1 - Mar 31 only)
    assert summer.countries["HR"].lights_mandatory is False
    assert winter.countries["HR"].lights_mandatory is True

    # Finland, Estonia, Lithuania seasonal car speed differences
    assert [lane.limit for lane in summer.countries["FI"].speed_limits["car"]] == [80, 100, 120]
    assert [lane.limit for lane in winter.countries["FI"].speed_limits["car"]] == [80, 80, 100]
    assert [lane.limit for lane in summer.countries["EE"].speed_limits["car"]] == [90, 110, 110]
    assert [lane.limit for lane in winter.countries["EE"].speed_limits["car"]] == [90, 90, 90]
    assert [lane.limit for lane in summer.countries["LT"].speed_limits["car"]] == [90, 120, 130]
    assert [lane.limit for lane in winter.countries["LT"].speed_limits["car"]] == [90, 110, 110]

    # Iceland heavy truck 80 km/h limit and 5-element 60t axle ladder
    iceland = summer.countries["IS"]
    assert [lane.limit for lane in iceland.speed_limits["truck"]] == [80, 80, 80]
    assert iceland.mass_limit_per_axle_count == [18000, 29000, 38000, 46000, 60000]

    # Seasonal timezone transitions embedded per country
    assert summer.countries["DE"].time_zone == 120
    assert summer.countries["DE"].time_zone_name == "@@tz_cest@@"
    assert summer.countries["DE"].observes_dst is True
    assert winter.countries["DE"].time_zone == 60
    assert winter.countries["DE"].time_zone_name == "CET"
    assert winter.countries["DE"].observes_dst is True

    assert summer.countries["PT"].time_zone == 60
    assert summer.countries["PT"].time_zone_name == "@@tz_west@@"
    assert winter.countries["PT"].time_zone == 0
    assert winter.countries["PT"].time_zone_name == "WET"

    assert summer.countries["TR"].time_zone == 180
    assert summer.countries["TR"].time_zone_name == "@@tz_trt@@"
    assert summer.countries["TR"].observes_dst is False
    assert winter.countries["TR"].time_zone == 180
    assert winter.countries["TR"].time_zone_name == "@@tz_trt@@"

    # UK imperial units and baseline 1.62 fuel price preservation across all 36 countries (D-05)
    for iso2, country in summer.countries.items():
        assert isinstance(country, RealismSnapshotCountry)
        assert isinstance(country.fuel, RealismSnapshotFuel)
        bl = bl_by_slug[country.ets2_slug]
        assert country.imperial_units is (iso2 == "GB")
        assert country.fuel.source == "baseline_1.62"
        assert country.fuel.local_prices == {}
        assert country.fuel.eur_per_liter == bl.fuel_price
        assert winter.countries[iso2].fuel == country.fuel


def test_serialize_snapshot_bytes_is_deterministic_canonical_and_round_trips(
    tmp_path: pathlib.Path,
) -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()

    snap_a = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")
    snap_b = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")

    bytes_a = serialize_snapshot_bytes(snap_a)
    bytes_b = serialize_snapshot_bytes(snap_b)
    assert bytes_a == bytes_b
    assert not bytes_a.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in bytes_a
    assert bytes_a.endswith(b"\n")

    # Verify locked D-11 v1 JSON keys exactly (no stray fields or wall-clock timestamps)
    raw_obj = cast(dict[str, object], json.loads(bytes_a.decode("utf-8")))
    assert set(raw_obj.keys()) == EXPECTED_TOP_LEVEL_KEYS
    raw_countries = cast(dict[str, dict[str, object]], raw_obj["countries"])
    assert len(raw_countries) == 36
    sample_country = raw_countries["DE"]
    assert set(sample_country.keys()) == EXPECTED_COUNTRY_KEYS
    sample_fuel = cast(dict[str, object], sample_country["fuel"])
    assert set(sample_fuel.keys()) == EXPECTED_FUEL_KEYS

    # Strict Pydantic JSON round-trip
    restored = RealismSnapshot.model_validate_json(bytes_a.decode("utf-8"))
    assert restored == snap_a

    # write_realism_snapshot creates parent dirs and writes identical bytes
    out_file = tmp_path / "nested" / "realism-snapshot-summer.json"
    written = write_realism_snapshot(snap_a, out_file)
    assert written == bytes_a
    assert out_file.read_bytes() == bytes_a


def test_snapshot_schema_enforces_locked_v1_and_forbids_missing_fuel_price() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()

    snap = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        "winter",
        override_date=date(2026, 7, 15),
    )
    assert snap.edition == "winter"
    assert snap.anchor_date == "2026-07-15"
    assert snap.countries["DE"].time_zone == 120
    assert snap.countries["DE"].time_zone_name == "@@tz_cest@@"

    raw_payload = cast(
        dict[str, object], json.loads(serialize_snapshot_bytes(snap).decode("utf-8"))
    )
    raw_payload["schema_version"] = 2
    with pytest.raises(ValidationError):
        RealismSnapshot.model_validate_json(json.dumps(raw_payload))

    raw_payload["schema_version"] = 1
    raw_payload["generated_at"] = "2026-11-19T00:00:00Z"
    with pytest.raises(ValidationError):
        RealismSnapshot.model_validate_json(json.dumps(raw_payload))

    # Missing baseline fuel_price must fail loudly
    corrupted_countries = [
        c.model_copy(update={"fuel_price": None}) if c.slug == "germany" else c
        for c in bl_countries.countries
    ]
    with pytest.raises(ValueError, match="fuel_price"):
        build_realism_snapshot(
            registry,
            CountriesBaseline(countries=corrupted_countries),
            bl_locales,
            "summer",
        )


def test_cli_registry_snapshot_winter_date_override_and_invalid_date(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    winter_out = tmp_path / "realism-snapshot-winter.json"
    exit_code = main(
        [
            "registry",
            "snapshot",
            "--season",
            "winter",
            "--out",
            str(winter_out),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "36 countries" in captured.out
    assert winter_out.is_file()

    loaded_winter = RealismSnapshot.model_validate_json(winter_out.read_text("utf-8"))
    assert loaded_winter.schema_version == 1
    assert loaded_winter.edition == "winter"
    assert loaded_winter.anchor_date == "2026-01-15"
    assert loaded_winter.countries["HR"].lights_mandatory is True
    assert loaded_winter.countries["DE"].time_zone == 60
    assert loaded_winter.countries["DE"].time_zone_name == "CET"

    # Explicit --date override (D-03)
    override_out = tmp_path / "realism-snapshot-override.json"
    exit_override = main(
        [
            "registry",
            "snapshot",
            "--season",
            "winter",
            "--date",
            "2026-07-15",
            "--out",
            str(override_out),
        ]
    )
    _ = capsys.readouterr()
    assert exit_override == 0
    loaded_override = RealismSnapshot.model_validate_json(override_out.read_text("utf-8"))
    assert loaded_override.anchor_date == "2026-07-15"
    assert loaded_override.countries["DE"].time_zone == 120
    assert loaded_override.countries["DE"].time_zone_name == "@@tz_cest@@"

    # Invalid --date returns exit code 1 with stderr diagnostic
    bad_out = tmp_path / "should-not-exist.json"
    exit_bad = main(
        [
            "registry",
            "snapshot",
            "--season",
            "summer",
            "--date",
            "not-a-date",
            "--out",
            str(bad_out),
        ]
    )
    bad_captured = capsys.readouterr()
    assert exit_bad == 1
    assert "error:" in bad_captured.err
    assert not bad_out.exists()


def test_build_realism_snapshot_with_prices_lock_preserves_v1_and_excludes_extra_eu(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ets2v2.normalize.lockfile import seed_initial_lockfile, write_prices_lockfile
    from ets2v2.normalize.models import CANONICAL_FUEL_GRADES

    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()
    lock = seed_initial_lockfile(bl_countries)
    assert {"IE", "CY", "MT"} <= set(lock.countries.keys())

    # Override DE with an exact 3-decimal EUR/L and live national source to verify injection
    de_live = lock.countries["DE"].model_copy(
        update={
            "eur_per_liter": 1.659,
            "source": "de_tankerkoenig",
            "fallback_used": False,
        }
    )
    custom_lock = lock.model_copy(update={"countries": {**lock.countries, "DE": de_live}})

    snap = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        "summer",
        prices_lock=custom_lock,
    )
    assert snap.schema_version == 1
    # Core snapshot MUST remain strictly 36 Vanilla+DLC countries (IE/CY/MT excluded per D-04!)
    assert len(snap.countries) == 36
    assert "IE" not in snap.countries
    assert "CY" not in snap.countries
    assert "MT" not in snap.countries

    assert snap.countries["DE"].fuel.eur_per_liter == 1.659
    assert snap.countries["DE"].fuel.source == "de_tankerkoenig"
    assert snap.countries["DE"].fuel.currency == "EUR"
    assert set(snap.countries["DE"].fuel.local_prices.keys()) == set(CANONICAL_FUEL_GRADES)

    # Verify locked schema_version=1 JSON keys (extra="forbid" D-13)
    raw_obj = cast(dict[str, object], json.loads(serialize_snapshot_bytes(snap).decode("utf-8")))
    assert set(raw_obj.keys()) == EXPECTED_TOP_LEVEL_KEYS
    raw_countries = cast(dict[str, dict[str, object]], raw_obj["countries"])
    assert set(raw_countries["DE"].keys()) == EXPECTED_COUNTRY_KEYS
    assert set(cast(dict[str, object], raw_countries["DE"]["fuel"]).keys()) == EXPECTED_FUEL_KEYS

    # CLI: ets2v2 registry snapshot --prices-lock ...
    lock_file = tmp_path / "prices.lock.json"
    write_prices_lockfile(custom_lock, lock_file)
    snap_out = tmp_path / "snap-with-prices.json"
    exit_code = main(
        [
            "registry",
            "snapshot",
            "--season",
            "summer",
            "--prices-lock",
            str(lock_file),
            "--out",
            str(snap_out),
        ]
    )
    _ = capsys.readouterr()
    assert exit_code == 0
    restored = RealismSnapshot.model_validate_json(snap_out.read_text("utf-8"))
    assert restored == snap
