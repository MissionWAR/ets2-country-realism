"""Unit and 36-country round-trip synthesis tests for clean-room .sui and speed_limits.sii."""

from __future__ import annotations

import pathlib

import pytest

from ets2v2.baseline.models import (
    BaselineCountry,
    BaselineSpeedLimit,
    CountriesBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.package.synthesize import (
    synthesize_country_sui,
    synthesize_speed_limits_sii,
)
from ets2v2.registry.loader import load_law_registry
from ets2v2.registry.models import Season
from ets2v2.registry.snapshot import RealismSnapshot, build_realism_snapshot
from ets2v2.sii.country import parse_country_data
from ets2v2.sii.hygiene import validate_sii_hygiene
from ets2v2.sii.speed_limits import LaneSpeedRule, parse_speed_limits

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"


def _load_inputs() -> tuple[
    CountriesBaseline,
    SpeedLimitsBaseline,
    LocalesBaseline,
    dict[Season, RealismSnapshot],
]:
    bl_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_speeds = SpeedLimitsBaseline.model_validate_json(
        (BASELINE_DIR / "speed_limits.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    snapshots: dict[Season, RealismSnapshot] = {
        "summer": build_realism_snapshot(registry, bl_countries, bl_locales, "summer"),
        "winter": build_realism_snapshot(registry, bl_countries, bl_locales, "winter"),
    }
    return bl_countries, bl_speeds, bl_locales, snapshots


@pytest.mark.parametrize("season", ["summer", "winter"])
def test_synthesize_all_36_countries_round_trip_and_hygiene(season: Season) -> None:
    bl_countries, bl_speeds, _bl_locales, snapshots = _load_inputs()
    snapshot = snapshots[season]
    resolved_by_slug = {c.ets2_slug: c for c in snapshot.countries.values()}
    speeds_by_slug: dict[str, BaselineSpeedLimit] = {s.slug: s for s in bl_speeds.speed_limits}

    assert len(bl_countries.countries) == 36
    assert len(resolved_by_slug) == 36

    quoted_slugs: set[str] = set()
    unquoted_slugs: set[str] = set()
    rail_slugs: set[str] = set()

    for bl_country in bl_countries.countries:
        resolved = resolved_by_slug[bl_country.slug]
        sui_bytes = synthesize_country_sui(bl_country, resolved)
        # Determinism check
        assert sui_bytes == synthesize_country_sui(bl_country, resolved)
        # Hygiene check (headerless .sui)
        assert validate_sii_hygiene(sui_bytes, require_siinunit=False) == []
        assert not sui_bytes.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in sui_bytes
        assert b"SiiNunit" not in sui_bytes

        parsed_country = parse_country_data(sui_bytes)
        assert parsed_country.unit_name == bl_country.unit_name
        assert parsed_country.country_id == bl_country.country_id
        assert parsed_country.name == bl_country.name
        assert parsed_country.name_localized == bl_country.name_localized
        assert parsed_country.country_code == bl_country.country_code
        assert parsed_country.iso_country_code == bl_country.iso_country_code
        assert parsed_country.iso_country_code_quoted is bl_country.iso_country_code_quoted
        assert parsed_country.pos == bl_country.pos
        # D-05: preserve 1.62 baseline fuel_price verbatim
        assert parsed_country.fuel_price == bl_country.fuel_price
        assert parsed_country.lights_mandatory is resolved.lights_mandatory
        assert parsed_country.driving_tired_offence == bl_country.driving_tired_offence
        assert parsed_country.imperial_units == bl_country.imperial_units
        assert parsed_country.leftside_traffic == bl_country.leftside_traffic
        assert parsed_country.trailer_standalone == bl_country.trailer_standalone
        assert parsed_country.time_zone == resolved.time_zone
        assert parsed_country.time_zone_name == resolved.time_zone_name
        assert parsed_country.secondary_time_zone_area == bl_country.secondary_time_zone_area
        assert parsed_country.secondary_time_zone == bl_country.secondary_time_zone
        assert parsed_country.secondary_time_zone_name == bl_country.secondary_time_zone_name
        assert parsed_country.mass_limit_per_axle_count == resolved.mass_limit_per_axle_count
        assert parsed_country.regions == bl_country.regions
        assert parsed_country.region_areas == bl_country.region_areas
        assert parsed_country.extra_attributes == bl_country.extra_attributes

        if parsed_country.iso_country_code_quoted:
            quoted_slugs.add(bl_country.slug)
        else:
            unquoted_slugs.add(bl_country.slug)

        bl_speed = speeds_by_slug[bl_country.slug]
        sii_bytes = synthesize_speed_limits_sii(bl_speed, resolved)
        assert sii_bytes == synthesize_speed_limits_sii(bl_speed, resolved)
        assert validate_sii_hygiene(sii_bytes, require_siinunit=True) == []
        assert not sii_bytes.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in sii_bytes

        parsed_speeds = parse_speed_limits(sii_bytes)
        assert parsed_speeds.vehicle_classes == bl_speed.vehicle_classes

        for bl_block, parsed_block in zip(bl_speed.blocks, parsed_speeds.blocks, strict=True):
            assert parsed_block.unit_name == bl_block.unit_name
            assert parsed_block.vehicle_speed_class == bl_block.vehicle_speed_class
            if bl_block.vehicle_speed_class in ("car", "truck", "bus"):
                expected_lanes = [
                    LaneSpeedRule(
                        lane_speed_class=lane.lane_speed_class,
                        limit=lane.limit,
                        urban_limit=lane.urban_limit,
                        max_limit=lane.max_limit,
                        uncommon=lane.uncommon,
                    )
                    for lane in resolved.speed_limits[bl_block.vehicle_speed_class]
                ]
                assert parsed_block.lanes == expected_lanes
            else:
                assert parsed_block.lanes == bl_block.lanes
                rail_slugs.add(bl_country.slug)

    assert len(quoted_slugs) == 8
    assert quoted_slugs == {
        "albania",
        "bosnia",
        "croatia",
        "kosovo",
        "macedonia",
        "montenegro",
        "serbia",
        "slovenia",
    }
    assert len(unquoted_slugs) == 28
    assert len(rail_slugs) == 24


def test_synthesize_specific_162_realism_and_seasonal_invariants() -> None:
    bl_countries, bl_speeds, _bl_locales, snapshots = _load_inputs()
    bl_by_slug: dict[str, BaselineCountry] = {c.slug: c for c in bl_countries.countries}
    sp_by_slug: dict[str, BaselineSpeedLimit] = {s.slug: s for s in bl_speeds.speed_limits}
    summer_by_slug = {c.ets2_slug: c for c in snapshots["summer"].countries.values()}
    winter_by_slug = {c.ets2_slug: c for c in snapshots["winter"].countries.values()}

    # Estonia name verbatim "Eesti" + seasonal car speed drop (110 -> 90)
    ee_summer = parse_country_data(
        synthesize_country_sui(bl_by_slug["estonia"], summer_by_slug["estonia"])
    )
    assert ee_summer.name == "Eesti"
    ee_sp_summer = parse_speed_limits(
        synthesize_speed_limits_sii(sp_by_slug["estonia"], summer_by_slug["estonia"])
    )
    ee_sp_winter = parse_speed_limits(
        synthesize_speed_limits_sii(sp_by_slug["estonia"], winter_by_slug["estonia"])
    )
    ee_car_sum = ee_sp_summer.get_block("car")
    ee_car_win = ee_sp_winter.get_block("car")
    assert ee_car_sum is not None and ee_car_win is not None
    assert [lane.limit for lane in ee_car_sum.lanes] == [90, 110, 110]
    assert [lane.limit for lane in ee_car_win.lanes] == [90, 90, 90]

    # Finland and Lithuania seasonal car speed drops
    for slug, summer_limits, winter_limits in (
        ("finland", [80, 100, 120], [80, 80, 100]),
        ("lithuania", [90, 120, 130], [90, 110, 110]),
    ):
        sp_sum = parse_speed_limits(
            synthesize_speed_limits_sii(sp_by_slug[slug], summer_by_slug[slug])
        )
        sp_win = parse_speed_limits(
            synthesize_speed_limits_sii(sp_by_slug[slug], winter_by_slug[slug])
        )
        car_sum = sp_sum.get_block("car")
        car_win = sp_win.get_block("car")
        assert car_sum is not None and car_win is not None
        assert [lane.limit for lane in car_sum.lanes] == summer_limits
        assert [lane.limit for lane in car_win.lanes] == winter_limits

    # Regions preserved on all 5 regional countries
    for slug, expected_count in (
        ("bosnia", 6),
        ("finland", 1),
        ("norway", 2),
        ("spain", 4),
        ("sweden", 4),
    ):
        parsed = parse_country_data(synthesize_country_sui(bl_by_slug[slug], summer_by_slug[slug]))
        assert len(parsed.regions) == expected_count
        assert len(parsed.region_areas) == expected_count

    # Russia Kaliningrad secondary_time_zone* preserved
    ru_winter = parse_country_data(
        synthesize_country_sui(bl_by_slug["russia"], winter_by_slug["russia"])
    )
    assert ru_winter.secondary_time_zone == [120]
    assert ru_winter.secondary_time_zone_name == ["@@tz_eet@@"]
    assert len(ru_winter.secondary_time_zone_area) == 1

    # Iceland 5-element 60t axle array + 80 km/h heavy truck
    is_summer = parse_country_data(
        synthesize_country_sui(bl_by_slug["iceland"], summer_by_slug["iceland"])
    )
    assert is_summer.mass_limit_per_axle_count == [18000, 29000, 38000, 46000, 60000]
    is_speeds = parse_speed_limits(
        synthesize_speed_limits_sii(sp_by_slug["iceland"], summer_by_slug["iceland"])
    )
    is_truck = is_speeds.get_block("truck")
    assert is_truck is not None
    assert [lane.limit for lane in is_truck.lanes] == [80, 80, 80]

    # Croatia seasonal lights_mandatory (Summer False, Winter True)
    hr_summer = parse_country_data(
        synthesize_country_sui(bl_by_slug["croatia"], summer_by_slug["croatia"])
    )
    hr_winter = parse_country_data(
        synthesize_country_sui(bl_by_slug["croatia"], winter_by_slug["croatia"])
    )
    assert hr_summer.lights_mandatory is False
    assert hr_winter.lights_mandatory is True

    # UK imperial_units / leftside_traffic / trailer_standalone / mph limits
    uk_winter = parse_country_data(synthesize_country_sui(bl_by_slug["uk"], winter_by_slug["uk"]))
    assert uk_winter.imperial_units is True
    assert uk_winter.leftside_traffic is True
    assert uk_winter.trailer_standalone is False
    assert uk_winter.time_zone == 0
    assert uk_winter.time_zone_name == "@@tz_gmt@@"
    uk_speeds = parse_speed_limits(
        synthesize_speed_limits_sii(sp_by_slug["uk"], winter_by_slug["uk"])
    )
    uk_car = uk_speeds.get_block("car")
    assert uk_car is not None
    assert [lane.limit for lane in uk_car.lanes] == [60, 70, 70]

    # Germany unlimited 0 Autobahn / expressway
    de_speeds = parse_speed_limits(
        synthesize_speed_limits_sii(sp_by_slug["germany"], summer_by_slug["germany"])
    )
    de_car = de_speeds.get_block("car")
    assert de_car is not None
    assert [lane.limit for lane in de_car.lanes] == [100, 0, 0]

    # Bulgaria, Romania, Turkey slow_road + uncommon flags; Romania & Sweden max_limit != limit
    for slug in ("bulgaria", "romania", "turkey"):
        sp = parse_speed_limits(synthesize_speed_limits_sii(sp_by_slug[slug], summer_by_slug[slug]))
        car = sp.get_block("car")
        assert car is not None
        assert [lane.lane_speed_class for lane in car.lanes] == [
            "local_road",
            "expressway",
            "motorway",
            "slow_road",
        ]
        assert [lane.uncommon for lane in car.lanes] == [False, False, False, True]

    ro_truck = parse_speed_limits(
        synthesize_speed_limits_sii(sp_by_slug["romania"], summer_by_slug["romania"])
    ).get_block("truck")
    assert ro_truck is not None
    assert ro_truck.lanes[1].limit == 80
    assert ro_truck.lanes[1].max_limit == 100

    se_truck = parse_speed_limits(
        synthesize_speed_limits_sii(sp_by_slug["sweden"], summer_by_slug["sweden"])
    ).get_block("truck")
    assert se_truck is not None
    assert se_truck.lanes[0].limit == 70
    assert se_truck.lanes[0].max_limit == 80


@pytest.mark.parametrize("bad_value", ["bad\\path", "bad\x00nul"])
def test_synthesize_rejects_backslash_and_nul_injection(bad_value: str) -> None:
    bl_countries, _bl_speeds, _bl_locales, snapshots = _load_inputs()
    bl_estonia = next(c for c in bl_countries.countries if c.slug == "estonia")
    resolved_estonia = snapshots["summer"].countries["EE"]

    poisoned_baseline = bl_estonia.model_copy(update={"name": bad_value})
    with pytest.raises(ValueError, match="backslash or NUL"):
        synthesize_country_sui(poisoned_baseline, resolved_estonia)

    poisoned_resolved = resolved_estonia.model_copy(update={"time_zone_name": bad_value})
    with pytest.raises(ValueError, match="backslash or NUL"):
        synthesize_country_sui(bl_estonia, poisoned_resolved)


def test_synthesize_rejects_slug_mismatch() -> None:
    bl_countries, bl_speeds, _bl_locales, snapshots = _load_inputs()
    bl_estonia = next(c for c in bl_countries.countries if c.slug == "estonia")
    sp_estonia = next(s for s in bl_speeds.speed_limits if s.slug == "estonia")
    resolved_finland = snapshots["summer"].countries["FI"]

    with pytest.raises(ValueError, match="slug mismatch"):
        synthesize_country_sui(bl_estonia, resolved_finland)
    with pytest.raises(ValueError, match="slug mismatch"):
        synthesize_speed_limits_sii(sp_estonia, resolved_finland)
