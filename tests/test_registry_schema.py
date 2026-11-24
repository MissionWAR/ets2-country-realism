"""Unit and CLI tracer tests for strict Pydantic law registry models and loader."""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
from pydantic import ValidationError

from ets2v2.baseline.models import (
    BaselineCountry,
    BaselineSpeedLimit,
    CountriesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.cli import main
from ets2v2.registry import (
    CountryLawRecord,
    CountryMappingEntry,
    CountryMappingRegistry,
    LaneSpeedOverride,
    SeasonalRuleSet,
    load_law_registry,
    serialize_registry_json_bytes,
    validate_law_registry,
)
from ets2v2.sii.speed_limits import LaneSpeedRule, VehicleSpeedLimitBlock


def _make_seasonal_ruleset(
    *,
    lights_mandatory: bool = True,
    car_motorway: int = 90,
    truck_limit: int = 80,
) -> SeasonalRuleSet:
    return SeasonalRuleSet(
        lights_mandatory=lights_mandatory,
        speed_limits={
            "car": [
                LaneSpeedOverride(lane_speed_class="local_road", limit=90, urban_limit=50),
                LaneSpeedOverride(lane_speed_class="expressway", limit=90, urban_limit=50),
                LaneSpeedOverride(lane_speed_class="motorway", limit=car_motorway, urban_limit=50),
            ],
            "truck": [
                LaneSpeedOverride(
                    lane_speed_class="local_road",
                    limit=truck_limit,
                    urban_limit=50,
                    max_limit=truck_limit,
                ),
                LaneSpeedOverride(
                    lane_speed_class="expressway",
                    limit=truck_limit,
                    urban_limit=50,
                    max_limit=truck_limit,
                ),
                LaneSpeedOverride(
                    lane_speed_class="motorway",
                    limit=truck_limit,
                    urban_limit=50,
                    max_limit=truck_limit,
                ),
            ],
            "bus": [
                LaneSpeedOverride(
                    lane_speed_class="local_road", limit=90, urban_limit=50, max_limit=90
                ),
                LaneSpeedOverride(
                    lane_speed_class="expressway", limit=90, urban_limit=50, max_limit=90
                ),
                LaneSpeedOverride(
                    lane_speed_class="motorway", limit=90, urban_limit=50, max_limit=90
                ),
            ],
        },
    )


def _make_iceland_law_record(
    *,
    mass_limits: list[int] | None = None,
    speed_unit: str = "kmh",
) -> CountryLawRecord:
    rules = _make_seasonal_ruleset()
    return CountryLawRecord(
        iso2="IS",
        iso3="isl",
        ets2_slug="iceland",
        iana_timezone="Atlantic/Reykjavik",
        speed_unit="mph" if speed_unit == "mph" else "kmh",
        currency="ISK",
        driving_tired_offence=True,
        mass_limit_per_axle_count=(
            mass_limits if mass_limits is not None else [18000, 29000, 38000, 46000, 60000]
        ),
        summer=rules,
        winter=rules,
        statutory_notes=["Umferdarlog nr. 77/2019 Art. 37 heavy truck 80 km/h limit."],
        sources=["https://island.is/en/driving-in-iceland"],
    )


def _write_synthetic_registry(
    tmp_path: pathlib.Path,
    *,
    record: CountryLawRecord | None = None,
    imperial_baseline: bool = False,
) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    laws_dir = tmp_path / "laws"
    countries_dir = laws_dir / "countries"
    countries_dir.mkdir(parents=True, exist_ok=True)
    mappings_path = tmp_path / "mappings" / "ets2_countries.json"
    mappings_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    law = record or _make_iceland_law_record(speed_unit="mph" if imperial_baseline else "kmh")
    (countries_dir / f"{law.iso2.lower()}.json").write_bytes(serialize_registry_json_bytes(law))

    mapping = CountryMappingRegistry(
        schema_version=1,
        baseline_game_version="1.62.3.3",
        countries=[
            CountryMappingEntry(
                ets2_slug=law.ets2_slug,
                iso2=law.iso2,
                iso3=law.iso3,
                country_id=26,
                name_english="Iceland",
                vanilla_1_62=True,
            )
        ],
    )
    mappings_path.write_bytes(serialize_registry_json_bytes(mapping))

    countries_baseline = CountriesBaseline(
        countries=[
            BaselineCountry(
                slug=law.ets2_slug,
                vfs_path=f"def/country/{law.ets2_slug}.sui",
                include_path=f"country/{law.ets2_slug}.sui",
                unit_name=f"country.data.{law.ets2_slug}",
                country_id=26,
                name="Ísland",
                name_localized="@@iceland@@",
                country_code="IS",
                iso_country_code=law.iso3,
                iso_country_code_quoted=False,
                pos=(-64300.0, 0.0, -98000.0),
                fuel_price=2.307,
                lights_mandatory=True,
                driving_tired_offence=True,
                imperial_units=True if imperial_baseline else None,
                time_zone=0,
                time_zone_name="@@tz_gmt@@",
                mass_limit_per_axle_count=[18000, 29000, 38000, 46000, 60000],
            )
        ]
    )
    (baseline_dir / "countries.json").write_bytes(serialize_registry_json_bytes(countries_baseline))

    sl_baseline = SpeedLimitsBaseline(
        speed_limits=[
            BaselineSpeedLimit(
                slug=law.ets2_slug,
                vfs_path=f"def/country/{law.ets2_slug}/speed_limits.sii",
                vehicle_classes=["car", "truck", "bus"],
                has_train=False,
                has_tram=False,
                blocks=[
                    VehicleSpeedLimitBlock(
                        unit_name=".speed_limit.car",
                        vehicle_speed_class="car",
                        lanes=[
                            LaneSpeedRule(lane_speed_class="local_road", limit=90, urban_limit=50),
                            LaneSpeedRule(lane_speed_class="expressway", limit=90, urban_limit=50),
                            LaneSpeedRule(lane_speed_class="motorway", limit=90, urban_limit=50),
                        ],
                    ),
                    VehicleSpeedLimitBlock(
                        unit_name=".speed_limit.truck",
                        vehicle_speed_class="truck",
                        lanes=[
                            LaneSpeedRule(
                                lane_speed_class="local_road",
                                limit=90,
                                urban_limit=50,
                                max_limit=90,
                            ),
                            LaneSpeedRule(
                                lane_speed_class="expressway",
                                limit=90,
                                urban_limit=50,
                                max_limit=90,
                            ),
                            LaneSpeedRule(
                                lane_speed_class="motorway",
                                limit=90,
                                urban_limit=50,
                                max_limit=90,
                            ),
                        ],
                    ),
                    VehicleSpeedLimitBlock(
                        unit_name=".speed_limit.bus",
                        vehicle_speed_class="bus",
                        lanes=[
                            LaneSpeedRule(
                                lane_speed_class="local_road",
                                limit=90,
                                urban_limit=50,
                                max_limit=90,
                            ),
                            LaneSpeedRule(
                                lane_speed_class="expressway",
                                limit=90,
                                urban_limit=50,
                                max_limit=90,
                            ),
                            LaneSpeedRule(
                                lane_speed_class="motorway",
                                limit=90,
                                urban_limit=50,
                                max_limit=90,
                            ),
                        ],
                    ),
                ],
            )
        ]
    )
    (baseline_dir / "speed_limits.json").write_bytes(serialize_registry_json_bytes(sl_baseline))
    return laws_dir, mappings_path, baseline_dir


def test_strict_pydantic_rejects_extra_keys_and_bool_as_int() -> None:
    with pytest.raises(ValidationError):
        LaneSpeedOverride.model_validate_json(
            json.dumps(
                {
                    "lane_speed_class": "local_road",
                    "limit": 80,
                    "urban_limit": 50,
                    "unknown_field": 1,
                }
            )
        )

    with pytest.raises(ValidationError):
        LaneSpeedOverride.model_validate_json(
            json.dumps(
                {
                    "lane_speed_class": "local_road",
                    "limit": True,
                    "urban_limit": 50,
                }
            )
        )

    with pytest.raises(ValidationError):
        LaneSpeedOverride.model_validate_json(
            json.dumps(
                {
                    "lane_speed_class": "local_road",
                    "limit": "80",
                    "urban_limit": 50,
                }
            )
        )


def test_strict_pydantic_rejects_bad_axle_limits_and_car_max_limit() -> None:
    record = _make_iceland_law_record()
    payload: dict[str, Any] = record.model_dump(mode="json")

    non_monotonic = dict(payload, mass_limit_per_axle_count=[18000, 30000, 25000, 40000])
    with pytest.raises(ValidationError):
        CountryLawRecord.model_validate_json(json.dumps(non_monotonic))

    too_small = dict(payload, mass_limit_per_axle_count=[9000, 26000, 36000, 40000])
    with pytest.raises(ValidationError):
        CountryLawRecord.model_validate_json(json.dumps(too_small))

    too_large = dict(payload, mass_limit_per_axle_count=[18000, 26000, 36000, 160000])
    with pytest.raises(ValidationError):
        CountryLawRecord.model_validate_json(json.dumps(too_large))

    bad_car_max = dict(payload)
    bad_car_max["summer"] = {
        **payload["summer"],
        "speed_limits": {
            **payload["summer"]["speed_limits"],
            "car": [
                {
                    "lane_speed_class": "local_road",
                    "limit": 90,
                    "urban_limit": 50,
                    "max_limit": 90,
                    "uncommon": None,
                },
                *payload["summer"]["speed_limits"]["car"][1:],
            ],
        },
    }
    with pytest.raises(ValidationError):
        CountryLawRecord.model_validate_json(json.dumps(bad_car_max))

    missing_bus = dict(payload)
    missing_bus["summer"] = {
        "lights_mandatory": True,
        "speed_limits": {
            "car": payload["summer"]["speed_limits"]["car"],
            "truck": payload["summer"]["speed_limits"]["truck"],
        },
    }
    with pytest.raises(ValidationError):
        CountryLawRecord.model_validate_json(json.dumps(missing_bus))


def test_loader_and_validator_pass_on_valid_synthetic_registry(tmp_path: pathlib.Path) -> None:
    laws_dir, mappings_path, baseline_dir = _write_synthetic_registry(tmp_path)

    bundle = load_law_registry(laws_dir, mappings_path)
    assert bundle.mappings.schema_version == 1
    assert set(bundle.laws_by_iso2) == {"IS"}
    assert bundle.laws_by_iso2["IS"].ets2_slug == "iceland"

    assert validate_law_registry(laws_dir, mappings_path, baseline_dir) == []


def test_validator_rejects_bom_crlf_and_unsorted_json(tmp_path: pathlib.Path) -> None:
    laws_dir, mappings_path, baseline_dir = _write_synthetic_registry(tmp_path)
    law_file = laws_dir / "countries" / "is.json"
    original = law_file.read_bytes()

    law_file.write_bytes(b"\xef\xbb\xbf" + original)
    bom_issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
    assert any("BOM" in issue for issue in bom_issues)

    law_file.write_bytes(original.replace(b"\n", b"\r\n"))
    crlf_issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
    assert any("LF" in issue for issue in crlf_issues)

    parsed: dict[str, Any] = json.loads(original.decode("utf-8"))
    unsorted_payload = {
        "sources": parsed["sources"],
        **{k: v for k, v in parsed.items() if k != "sources"},
    }
    law_file.write_bytes(
        (json.dumps(unsorted_payload, indent=2, sort_keys=False) + "\n").encode("utf-8")
    )
    unsorted_issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
    assert any("canonical" in issue.lower() for issue in unsorted_issues)


def test_validator_rejects_axle_downgrade_speed_unit_mismatch_and_duplicate_slug(
    tmp_path: pathlib.Path,
) -> None:
    downgraded = _make_iceland_law_record(mass_limits=[18000, 26000, 36000, 40000])
    laws_dir, mappings_path, baseline_dir = _write_synthetic_registry(
        tmp_path / "case_axle", record=downgraded
    )
    axle_issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
    assert any("mass_limit_per_axle_count" in issue for issue in axle_issues)

    wrong_unit = _make_iceland_law_record(speed_unit="kmh")
    laws_dir_imp, mappings_imp, baseline_imp = _write_synthetic_registry(
        tmp_path / "case_imperial",
        record=wrong_unit,
        imperial_baseline=True,
    )
    unit_issues = validate_law_registry(laws_dir_imp, mappings_imp, baseline_imp)
    assert any("speed_unit" in issue for issue in unit_issues)

    laws_dup, mappings_dup, baseline_dup = _write_synthetic_registry(tmp_path / "case_dup")
    dup_mapping = CountryMappingRegistry(
        schema_version=1,
        baseline_game_version="1.62.3.3",
        countries=[
            CountryMappingEntry(
                ets2_slug="iceland",
                iso2="IS",
                iso3="isl",
                country_id=26,
                name_english="Iceland",
                vanilla_1_62=True,
            ),
            CountryMappingEntry(
                ets2_slug="iceland",
                iso2="NO",
                iso3="nor",
                country_id=35,
                name_english="Norway",
                vanilla_1_62=True,
            ),
        ],
    )
    mappings_dup.write_bytes(serialize_registry_json_bytes(dup_mapping))
    dup_issues = validate_law_registry(laws_dup, mappings_dup, baseline_dup)
    assert any("duplicate ets2_slug" in issue.lower() for issue in dup_issues)


def test_cli_registry_validate_tracer(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    laws_dir, mappings_path, baseline_dir = _write_synthetic_registry(tmp_path)

    exit_ok = main(
        [
            "registry",
            "validate",
            "--laws-dir",
            str(laws_dir),
            "--mappings",
            str(mappings_path),
            "--baseline-dir",
            str(baseline_dir),
        ]
    )
    out_ok = capsys.readouterr()
    assert exit_ok == 0
    assert "passed" in out_ok.out.lower()

    (laws_dir / "countries" / "is.json").unlink()
    exit_fail = main(
        [
            "registry",
            "validate",
            "--laws-dir",
            str(laws_dir),
            "--mappings",
            str(mappings_path),
            "--baseline-dir",
            str(baseline_dir),
        ]
    )
    out_fail = capsys.readouterr()
    assert exit_fail == 1
    assert out_fail.err.strip() != ""


def test_validator_rejects_stray_subdirectory_and_uppercase_json_extension(
    tmp_path: pathlib.Path,
) -> None:
    laws_dir, mappings_path, baseline_dir = _write_synthetic_registry(tmp_path)
    (laws_dir / "countries" / "stray_subdir").mkdir()
    (laws_dir / "countries" / "de.JSON").write_text("{}\n", encoding="utf-8")

    issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
    assert any("non-file" in issue.lower() and "stray_subdir" in issue for issue in issues)
    assert any("non-json" in issue.lower() and "de.JSON" in issue for issue in issues)


def test_country_mapping_entry_allows_null_country_id_strictly_for_non_vanilla() -> None:
    non_vanilla = CountryMappingEntry(
        ets2_slug="gibraltar",
        iso2="GI",
        iso3="gib",
        country_id=None,
        name_english="Gibraltar",
        vanilla_1_62=False,
    )
    assert non_vanilla.country_id is None
    assert non_vanilla.vanilla_1_62 is False

    with pytest.raises(ValidationError, match="country_id"):
        CountryMappingEntry(
            ets2_slug="germany",
            iso2="DE",
            iso3="deu",
            country_id=None,
            name_english="Germany",
            vanilla_1_62=True,
        )


def test_validator_partitions_baseline_checks_and_validates_non_vanilla_entries(
    tmp_path: pathlib.Path,
) -> None:
    laws_dir, mappings_path, baseline_dir = _write_synthetic_registry(tmp_path)

    gib_record = CountryLawRecord(
        iso2="GI",
        iso3="gib",
        ets2_slug="gibraltar",
        iana_timezone="Europe/Gibraltar",
        speed_unit="kmh",
        currency="GBP",
        driving_tired_offence=True,
        mass_limit_per_axle_count=[18000, 26000, 36000, 40000],
        summer=_make_seasonal_ruleset(lights_mandatory=False, car_motorway=50, truck_limit=50),
        winter=_make_seasonal_ruleset(lights_mandatory=False, car_motorway=50, truck_limit=50),
        statutory_notes=["Gibraltar metric km/h limits."],
        sources=["https://www.gibraltarlaws.gov.gi/"],
    )
    (laws_dir / "countries" / "gi.json").write_bytes(serialize_registry_json_bytes(gib_record))

    mapping = CountryMappingRegistry(
        schema_version=1,
        baseline_game_version="1.62.3.3",
        countries=[
            CountryMappingEntry(
                ets2_slug="gibraltar",
                iso2="GI",
                iso3="gib",
                country_id=None,
                name_english="Gibraltar",
                vanilla_1_62=False,
            ),
            CountryMappingEntry(
                ets2_slug="iceland",
                iso2="IS",
                iso3="isl",
                country_id=26,
                name_english="Iceland",
                vanilla_1_62=True,
            ),
        ],
    )
    mappings_path.write_bytes(serialize_registry_json_bytes(mapping))
    assert validate_law_registry(laws_dir, mappings_path, baseline_dir) == []

    # Marking a baseline slug as vanilla_1_62=False must fail loudly
    bad_mapping = CountryMappingRegistry(
        schema_version=1,
        baseline_game_version="1.62.3.3",
        countries=[
            CountryMappingEntry(
                ets2_slug="gibraltar",
                iso2="GI",
                iso3="gib",
                country_id=None,
                name_english="Gibraltar",
                vanilla_1_62=False,
            ),
            CountryMappingEntry(
                ets2_slug="iceland",
                iso2="IS",
                iso3="isl",
                country_id=26,
                name_english="Iceland",
                vanilla_1_62=False,
            ),
        ],
    )
    mappings_path.write_bytes(serialize_registry_json_bytes(bad_mapping))
    issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
    assert any("vanilla_1_62=true" in issue for issue in issues)
