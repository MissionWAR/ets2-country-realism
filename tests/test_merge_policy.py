"""Unit and round-trip tests for ets2v2.merge.policy (FieldOwnershipPolicy, D-14, D-15)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ets2v2.baseline.models import LocalesBaseline
from ets2v2.merge.policy import (
    CountryPolicyResult,
    FieldOwnershipPolicy,
    SpeedLimitsPolicyResult,
    apply_country_policy,
    apply_speed_limits_policy,
    merge_axle_mass_limits,
    should_patch_timezone,
)
from ets2v2.registry.models import LaneSpeedOverride, RoadVehicleClass
from ets2v2.registry.snapshot import RealismSnapshotCountry, RealismSnapshotFuel
from ets2v2.sii.country import parse_country_data
from ets2v2.sii.document import SiiDocument
from ets2v2.sii.hygiene import validate_sii_hygiene
from ets2v2.sii.speed_limits import parse_speed_limits

_LOCALES_PATH = Path("data/baselines/ets2_1.62_def/locales.json")


def _make_snapshot_country(
    *,
    iso2: str = "DE",
    iso3: str = "deu",
    ets2_slug: str = "germany",
    iana_timezone: str = "Europe/Berlin",
    time_zone: int = 120,
    time_zone_name: str = "@@tz_cest@@",
    observes_dst: bool = True,
    lights_mandatory: bool = False,
    driving_tired_offence: bool = True,
    imperial_units: bool = False,
    mass_limit_per_axle_count: list[int] | None = None,
    fuel_eur: float = 1.72,
    speed_limits: dict[RoadVehicleClass, list[LaneSpeedOverride]] | None = None,
) -> RealismSnapshotCountry:
    default_speeds: dict[RoadVehicleClass, list[LaneSpeedOverride]] = {
        "car": [
            LaneSpeedOverride(lane_speed_class="local_road", limit=100, urban_limit=50),
            LaneSpeedOverride(lane_speed_class="expressway", limit=120, urban_limit=50),
            LaneSpeedOverride(lane_speed_class="motorway", limit=130, urban_limit=50, max_limit=0),
        ],
        "truck": [
            LaneSpeedOverride(lane_speed_class="local_road", limit=60, urban_limit=50),
            LaneSpeedOverride(lane_speed_class="expressway", limit=80, urban_limit=50),
            LaneSpeedOverride(lane_speed_class="motorway", limit=80, urban_limit=50),
        ],
        "bus": [
            LaneSpeedOverride(lane_speed_class="local_road", limit=80, urban_limit=50),
            LaneSpeedOverride(lane_speed_class="expressway", limit=100, urban_limit=50),
            LaneSpeedOverride(lane_speed_class="motorway", limit=100, urban_limit=50),
        ],
    }
    return RealismSnapshotCountry(
        iso2=iso2,
        iso3=iso3,
        ets2_slug=ets2_slug,
        iana_timezone=iana_timezone,
        time_zone=time_zone,
        time_zone_name=time_zone_name,
        observes_dst=observes_dst,
        lights_mandatory=lights_mandatory,
        driving_tired_offence=driving_tired_offence,
        imperial_units=imperial_units,
        mass_limit_per_axle_count=(
            mass_limit_per_axle_count
            if mass_limit_per_axle_count is not None
            else [18000, 26000, 36000, 40000, 44000]
        ),
        speed_limits=speed_limits if speed_limits is not None else default_speeds,
        fuel=RealismSnapshotFuel(
            currency="EUR",
            eur_per_liter=fuel_eur,
            local_prices={"diesel": fuel_eur},
            source="test_snapshot",
        ),
    )


def test_merge_axle_mass_limits_preserves_heavy_maps_and_upgrades_iceland() -> None:
    # EAA Brazil 7-axle 80t vs 5-axle 44t snapshot -> preserves 7-axle 80t
    eaa_axles = [16000, 23000, 33000, 45000, 57000, 74000, 80000]
    real_44t = [18000, 26000, 36000, 40000, 44000]
    assert merge_axle_mass_limits(eaa_axles, real_44t) == [
        18000,
        26000,
        36000,
        45000,
        57000,
        74000,
        80000,
    ]

    # RusMap / TST 6-axle 48t preserved against 44t snapshot
    tst_axles = [18000, 25000, 32000, 40000, 44000, 48000]
    assert merge_axle_mass_limits(tst_axles, real_44t) == [
        18000,
        26000,
        36000,
        40000,
        44000,
        48000,
    ]

    # Finland 10-axle 105t preserved verbatim against shorter 76t snapshot
    fi_map = [18000, 28000, 35000, 44000, 60000, 68000, 76000, 84000, 96000, 105000]
    fi_real = [18000, 28000, 35000, 44000, 60000, 68000, 76000]
    assert merge_axle_mass_limits(fi_map, fi_real) == fi_map

    # Stale 4-axle 40t Iceland upgraded to 5-axle 60t
    is_map = [18000, 26000, 36000, 40000]
    is_real = [18000, 29000, 38000, 46000, 60000]
    assert merge_axle_mass_limits(is_map, is_real) == [18000, 29000, 38000, 46000, 60000]

    # Empty-side fallbacks
    assert merge_axle_mass_limits([], is_real) == is_real
    assert merge_axle_mass_limits(tst_axles, []) == tst_axles

    # Non-monotonic map input clamped monotonically non-decreasing
    assert merge_axle_mass_limits([18000, 32000, 28000, 40000], [18000, 26000, 24000, 40000]) == [
        18000,
        32000,
        32000,
        40000,
    ]


def test_apply_country_policy_preserves_multi_tz_and_heavy_axles() -> None:
    # TST 27-TZ Russia with 6-axle 48t + cp1252 comment byte
    tst_russia = (
        b"country_data : country.data.russia\n"
        b"{\n"
        b"\t# TST comment with cp1252 byte \xc5land\n"
        b"\tcountry_id: 37\n"
        b'\tname: "Russia"\n'
        b'\tname_localized: "@@russia@@"\n'
        b'\tcountry_code: "RUS"\n'
        b"\tiso_country_code: rus\n"
        b"\tpos: (56000, 0, -25000)\n"
        b"\tfuel_price: 0.65\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\timperial_units: false\n"
        b"\tleftside_traffic: false\n"
        b"\ttime_zone: 180\n"
        b'\ttime_zone_name: "@@tz_msk@@"\n'
        b"\tsecondary_time_zone_area[]: (1000, 2000, 3000, 4000)\n"
        b"\tsecondary_time_zone[]: 300\n"
        b'\tsecondary_time_zone_name[]: "@@tz_yekt@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 25000\n"
        b"\tmass_limit_per_axle_count[]: 32000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"\tmass_limit_per_axle_count[]: 44000\n"
        b"\tmass_limit_per_axle_count[]: 48000\n"
        b"}\n"
    )
    snap_ru = _make_snapshot_country(
        iso2="RU",
        iso3="rus",
        ets2_slug="russia",
        iana_timezone="Europe/Moscow",
        time_zone=240,
        time_zone_name="OVERRIDE_SHOULD_NOT_APPLY",
        lights_mandatory=True,
        fuel_eur=0.72,
        mass_limit_per_axle_count=[18000, 25000, 32000, 40000, 44000],
    )
    map_ru = parse_country_data(tst_russia.decode("cp1252"))
    assert should_patch_timezone(map_ru) == (False, "skipped_multi_tz")

    res: CountryPolicyResult = apply_country_policy(
        tst_russia, map_ru, snap_ru, rel_path="def/country/russia.sui"
    )
    assert res.time_zone_action == "skipped_multi_tz"
    assert res.has_siinunit_envelope is False
    assert res.merged_axles == [18000, 25000, 32000, 40000, 44000, 48000]
    assert validate_sii_hygiene(res.rendered_bytes, require_siinunit=False) == []

    reparsed = parse_country_data(res.rendered_bytes)
    assert reparsed.time_zone == 180
    assert reparsed.time_zone_name == "@@tz_msk@@"
    assert reparsed.secondary_time_zone == [300]
    assert reparsed.secondary_time_zone_name == ["@@tz_yekt@@"]
    assert reparsed.secondary_time_zone_area == [(1000.0, 2000.0, 3000.0, 4000.0)]
    assert reparsed.fuel_price == 0.72
    assert reparsed.lights_mandatory is True
    assert reparsed.mass_limit_per_axle_count == [18000, 25000, 32000, 40000, 44000, 48000]
    assert reparsed.pos == (56000.0, 0.0, -25000.0)


def test_apply_country_policy_preserves_umcf_kz_and_eaa_brazil_multi_tz() -> None:
    umcf_kz = (
        "country_data : country.data.kazakhstan\n"
        "{\n"
        "\tcountry_id: 88\n"
        '\tname: "Kazakhstan"\n'
        '\tcountry_code: "KZ"\n'
        "\tiso_country_code: kaz\n"
        "\tfuel_price: 0.45\n"
        "\tlights_mandatory: false\n"
        "\tdriving_tired_offence: true\n"
        "\ttime_zone: 300\n"
        '\ttime_zone_name: "@@tz_aqtt@@"\n'
        "\tsecondary_time_zone_area[]: (10, 20, 30, 40)\n"
        "\tsecondary_time_zone[]: 360\n"
        '\tsecondary_time_zone_name[]: "@@tz_almt@@"\n'
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 25000\n"
        "\tmass_limit_per_axle_count[]: 38000\n"
        "}\n"
    )
    snap_kz = _make_snapshot_country(
        iso2="KZ",
        iso3="kaz",
        ets2_slug="kazakhstan",
        iana_timezone="Asia/Almaty",
        time_zone=300,
        time_zone_name="AQTT",
        lights_mandatory=True,
        fuel_eur=0.52,
        mass_limit_per_axle_count=[18000, 25000, 38000, 44000],
    )
    map_kz = parse_country_data(umcf_kz)
    res_kz = apply_country_policy(umcf_kz, map_kz, snap_kz)
    assert res_kz.time_zone_action == "skipped_multi_tz"
    parsed_kz = parse_country_data(res_kz.rendered_bytes)
    assert parsed_kz.time_zone_name == "@@tz_aqtt@@"
    assert parsed_kz.secondary_time_zone == [360]
    assert parsed_kz.lights_mandatory is True
    assert parsed_kz.mass_limit_per_axle_count == [18000, 25000, 38000, 44000]

    # EAA Brazil multi-TZ + 80t axles
    eaa_br = (
        "country_data : country.data.brasil\n"
        "{\n"
        "\tcountry_id: 201\n"
        '\tname: "Brasil"\n'
        '\tcountry_code: "BR"\n'
        "\tiso_country_code: bra\n"
        "\tfuel_price: 1.05\n"
        "\tlights_mandatory: false\n"
        "\tdriving_tired_offence: true\n"
        "\ttime_zone: -180\n"
        '\ttime_zone_name: "BRT"\n'
        '\tsecondary_time_zone_name[]: "AMT"\n'
        "\tmass_limit_per_axle_count[]: 16000\n"
        "\tmass_limit_per_axle_count[]: 23000\n"
        "\tmass_limit_per_axle_count[]: 33000\n"
        "\tmass_limit_per_axle_count[]: 45000\n"
        "\tmass_limit_per_axle_count[]: 57000\n"
        "\tmass_limit_per_axle_count[]: 74000\n"
        "\tmass_limit_per_axle_count[]: 80000\n"
        "}\n"
    )
    snap_br = _make_snapshot_country(
        iso2="BR",
        iso3="bra",
        ets2_slug="brasil",
        iana_timezone="America/Sao_Paulo",
        time_zone=-120,
        time_zone_name="BRST",
        lights_mandatory=True,
        fuel_eur=1.18,
    )
    map_br = parse_country_data(eaa_br)
    res_br = apply_country_policy(eaa_br, map_br, snap_br)
    assert res_br.time_zone_action == "skipped_multi_tz"
    parsed_br = parse_country_data(res_br.rendered_bytes)
    assert parsed_br.time_zone == -180
    assert parsed_br.time_zone_name == "BRT"
    assert parsed_br.mass_limit_per_axle_count[-1] == 80000


def test_apply_country_policy_preserves_uk_regions_and_applies_canary_tz_override() -> None:
    uk_sui = (
        "country_data : country.data.uk\n"
        "{\n"
        "\tcountry_id: 10\n"
        '\tname: "United Kingdom"\n'
        '\tname_localized: "@@uk@@"\n'
        '\tcountry_code: "UK"\n'
        "\tiso_country_code: gbr\n"
        "\tpos: (-45000, 0, -25000)\n"
        "\tfuel_price: 1.50\n"
        "\tlights_mandatory: false\n"
        "\tdriving_tired_offence: true\n"
        "\timperial_units: true\n"
        "\tleftside_traffic: true\n"
        "\ttime_zone: 0\n"
        '\ttime_zone_name: "@@tz_gmt@@"\n'
        "\tregions[]: scotland\n"
        "\tregions[]: wales\n"
        "\tregion_areas[]: (-50000, -40000, -30000, -20000)\n"
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 36000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
        "\tmass_limit_per_axle_count[]: 44000\n"
        "}\n"
    )
    snap_gb = _make_snapshot_country(
        iso2="GB",
        iso3="gbr",
        ets2_slug="uk",
        iana_timezone="Europe/London",
        time_zone=60,
        time_zone_name="@@tz_bst@@",
        imperial_units=True,
        fuel_eur=1.82,
    )
    res_uk = apply_country_policy(uk_sui, parse_country_data(uk_sui), snap_gb)
    assert res_uk.time_zone_action == "patched"
    parsed_uk = parse_country_data(res_uk.rendered_bytes)
    assert parsed_uk.regions == ["scotland", "wales"]
    assert parsed_uk.region_areas == [(-50000.0, -40000.0, -30000.0, -20000.0)]
    assert parsed_uk.pos == (-45000.0, 0.0, -25000.0)
    assert parsed_uk.leftside_traffic is True
    assert parsed_uk.imperial_units is True
    assert parsed_uk.time_zone == 60
    assert parsed_uk.time_zone_name == "@@tz_bst@@"

    # Canary Islands iana_timezone_override="Atlantic/Canary": WET winter, @@tz_west@@ summer
    locales = LocalesBaseline.model_validate_json(_LOCALES_PATH.read_text("utf-8"))
    can_sui = (
        "country_data : country.data.can_islands\n"
        "{\n"
        "\tcountry_id: 199\n"
        '\tname: "Canary Islands"\n'
        '\tcountry_code: "E"\n'
        "\tiso_country_code: esp\n"
        "\tfuel_price: 1.40\n"
        "\tlights_mandatory: false\n"
        "\tdriving_tired_offence: true\n"
        "\ttime_zone: 60\n"
        '\ttime_zone_name: "@@tz_cet@@"\n'
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
        "}\n"
    )
    snap_es_summer = _make_snapshot_country(
        iso2="ES",
        iso3="esp",
        ets2_slug="spain",
        iana_timezone="Europe/Madrid",
        time_zone=120,
        time_zone_name="@@tz_cest@@",
        fuel_eur=1.55,
    )
    res_can_summer = apply_country_policy(
        can_sui,
        parse_country_data(can_sui),
        snap_es_summer,
        iana_timezone_override="Atlantic/Canary",
        ref_date=date(2026, 7, 15),
        supported_tz_keys=locales.tz_keys,
    )
    assert res_can_summer.time_zone_action == "patched_iana_override"
    parsed_summer = parse_country_data(res_can_summer.rendered_bytes)
    assert parsed_summer.time_zone == 60
    assert parsed_summer.time_zone_name == "@@tz_west@@"

    res_can_winter = apply_country_policy(
        can_sui,
        parse_country_data(can_sui),
        snap_es_summer,
        iana_timezone_override="Atlantic/Canary",
        ref_date=date(2026, 1, 15),
        supported_tz_keys=locales.tz_keys,
    )
    assert res_can_winter.time_zone_action == "patched_iana_override"
    parsed_winter = parse_country_data(res_can_winter.rendered_bytes)
    assert parsed_winter.time_zone == 0
    assert parsed_winter.time_zone_name == "WET"


def test_apply_country_policy_preserves_headerless_and_wrapped_sii_and_missing_tz() -> None:
    # Headerless SEA/RoC/Project Japan .sii fragment (no SiiNunit wrapper) + missing time_zone
    headerless_sii = (
        "country_data : country.data.custom_de\n"
        "{\n"
        "\tcountry_id: 501\n"
        '\tname: "Custom DE"\n'
        '\tcountry_code: "D"\n'
        "\tiso_country_code: deu\n"
        "\tfuel_price: 1.50\n"
        "\tlights_mandatory: false\n"
        "\tdriving_tired_offence: true\n"
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
        "}\n"
    )
    snap_de = _make_snapshot_country()
    map_stub = parse_country_data(headerless_sii)
    assert should_patch_timezone(map_stub) == (False, "skipped_missing_tz")

    res_headerless = apply_country_policy(
        headerless_sii, map_stub, snap_de, rel_path="def/country/custom_de.sii"
    )
    assert res_headerless.has_siinunit_envelope is False
    assert res_headerless.time_zone_action == "skipped_missing_tz"
    assert not SiiDocument.parse(res_headerless.rendered_bytes).has_siinunit
    assert b"SiiNunit" not in res_headerless.rendered_bytes
    assert validate_sii_hygiene(res_headerless.rendered_bytes, require_siinunit=False) == []
    assert parse_country_data(res_headerless.rendered_bytes).time_zone is None

    # Wrapped .sii variant preserves SiiNunit { ... }
    wrapped_sii = f"SiiNunit\n{{\n{headerless_sii}}}\n"
    res_wrapped = apply_country_policy(
        wrapped_sii, parse_country_data(wrapped_sii), snap_de, rel_path="def/country/wrapped_de.sii"
    )
    assert res_wrapped.has_siinunit_envelope is True
    assert SiiDocument.parse(res_wrapped.rendered_bytes).has_siinunit is True
    assert validate_sii_hygiene(res_wrapped.rendered_bytes, require_siinunit=True) == []


def test_apply_speed_limits_policy_preserves_custom_lanes_train_tram_and_guards_imperial() -> None:
    custom_spd = (
        "SiiNunit\n"
        "{\n"
        "country_speed_limit : .speed_limit.car\n"
        "{\n"
        "\tvehicle_speed_class: car\n"
        "\n"
        "\t# Local road comment\n"
        "\tlane_speed_class[]: local_road\n"
        "\tlimit[]: 90\n"
        "\turban_limit[]: 50\n"
        "\n"
        "\t# Custom toll highway lane\n"
        "\tlane_speed_class[]: highway_toll\n"
        "\tlimit[]: 140\n"
        "\turban_limit[]: 60\n"
        "\n"
        "\tlane_speed_class[]: motorway\n"
        "\tlimit[]: 120\n"
        "\turban_limit[]: 50\n"
        "\tmax_limit[]: 130\n"
        "}\n"
        "\n"
        "country_speed_limit : .speed_limit.truck\n"
        "{\n"
        "\tvehicle_speed_class: truck\n"
        "\n"
        "\tlane_speed_class[]: local_road\n"
        "\tlimit[]: 70\n"
        "\turban_limit[]: 50\n"
        "\n"
        "\tlane_speed_class[]: highway_toll\n"
        "\tlimit[]: 95\n"
        "\turban_limit[]: 50\n"
        "\n"
        "\tlane_speed_class[]: motorway\n"
        "\tlimit[]: 85\n"
        "\turban_limit[]: 50\n"
        "}\n"
        "\n"
        "country_speed_limit : .speed_limit.train\n"
        "{\n"
        "\tvehicle_speed_class: train\n"
        "\tlane_speed_class[]: local_road\n"
        "\tlimit[]: 160\n"
        "}\n"
        "\n"
        "country_speed_limit : .speed_limit.tram\n"
        "{\n"
        "\tvehicle_speed_class: tram\n"
        "\tlane_speed_class[]: local_road\n"
        "\tlimit[]: 45\n"
        "}\n"
        "}\n"
    )
    de_sui = (
        "country_data : country.data.germany\n"
        "{\n"
        "\tcountry_id: 1\n"
        '\tname: "Germany"\n'
        "\timperial_units: false\n"
        "}\n"
    )
    snap_de = _make_snapshot_country(imperial_units=False)
    spd_res: SpeedLimitsPolicyResult = apply_speed_limits_policy(
        custom_spd,
        parse_country_data(de_sui),
        snap_de,
        rel_path="def/country/germany/speed_limits.sii",
    )
    assert spd_res.status == "patched"
    assert spd_res.rendered_bytes is not None
    assert spd_res.preserved_custom_lanes == {"car": ["highway_toll"], "truck": ["highway_toll"]}
    assert b"# Custom toll highway lane" in spd_res.rendered_bytes
    assert b"# Local road comment" in spd_res.rendered_bytes

    reparsed_spd = parse_speed_limits(spd_res.rendered_bytes)
    car_block = reparsed_spd.get_block("car")
    assert car_block is not None
    assert [lane.lane_speed_class for lane in car_block.lanes] == [
        "local_road",
        "highway_toll",
        "motorway",
    ]
    assert car_block.lanes[0].limit == 100
    assert car_block.lanes[1].limit == 140
    assert car_block.lanes[1].urban_limit == 60
    assert car_block.lanes[2].limit == 130
    assert car_block.lanes[2].max_limit == 0

    truck_block = reparsed_spd.get_block("truck")
    assert truck_block is not None
    assert truck_block.lanes[0].limit == 60
    assert truck_block.lanes[1].limit == 95
    assert truck_block.lanes[2].limit == 80

    train_block = reparsed_spd.get_block("train")
    tram_block = reparsed_spd.get_block("tram")
    assert train_block is not None and train_block.lanes[0].limit == 160
    assert tram_block is not None and tram_block.lanes[0].limit == 45

    # Imperial parity guard: Gibraltar imperial_units=true vs metric snapshot -> skipped!
    gi_sui = (
        "country_data : country.data.gibraltar\n"
        "{\n"
        "\tcountry_id: 90\n"
        '\tname: "Gibraltar"\n'
        "\timperial_units: true\n"
        "}\n"
    )
    mismatch_a = apply_speed_limits_policy(custom_spd, parse_country_data(gi_sui), snap_de)
    assert mismatch_a.status == "skipped_imperial_mismatch"
    assert mismatch_a.rendered_bytes is None
    assert mismatch_a.warnings

    # Reverse mismatch: metric map country vs mph UK snapshot -> skipped!
    snap_uk = _make_snapshot_country(iso2="GB", iso3="gbr", ets2_slug="uk", imperial_units=True)
    mismatch_b = apply_speed_limits_policy(custom_spd, parse_country_data(de_sui), snap_uk)
    assert mismatch_b.status == "skipped_imperial_mismatch"
    assert mismatch_b.rendered_bytes is None
    assert mismatch_b.warnings

    # Policy skip toggle
    skip_policy = FieldOwnershipPolicy(speed_limits_road="skip")
    skipped_res = apply_speed_limits_policy(
        custom_spd, parse_country_data(de_sui), snap_de, policy=skip_policy
    )
    assert skipped_res.status == "skipped_policy"
    assert skipped_res.rendered_bytes is None
