"""Committed ETS2 1.62 baseline contract tests and @pytest.mark.local_ets2 round-trip checks."""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import cast

import pytest

from ets2v2.baseline import (
    BaselineBundle,
    BaselineManifest,
    CountriesBaseline,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
    extract_baseline,
    resolve_game_dir,
    verify_baseline_bundle,
)
from ets2v2.sii import (
    CountryDataPatch,
    LaneSpeedRule,
    normalize_sii_bytes,
    parse_country_data,
    parse_country_includes,
    parse_speed_limits,
    patch_country_data,
    patch_speed_limits,
    serialize_sii_text,
)
from ets2v2.vfs import open_archive

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
BASELINE_DIR = DATA_DIR / "baselines" / "ets2_1.62_def"
REQUIRED_FILES = (
    "manifest.json",
    "countries.json",
    "speed_limits.json",
    "fuel_boards.json",
    "locales.json",
)


def _has_local_ets2() -> bool:
    game_dir = resolve_game_dir()
    return (
        game_dir.is_dir()
        and (game_dir / "version.scs").is_file()
        and (game_dir / "def.scs").is_file()
        and (game_dir / "locale.scs").is_file()
    )


def _load_committed_bundle() -> BaselineBundle:
    manifest = BaselineManifest.model_validate_json(
        (BASELINE_DIR / "manifest.json").read_text("utf-8")
    )
    countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    speed_limits = SpeedLimitsBaseline.model_validate_json(
        (BASELINE_DIR / "speed_limits.json").read_text("utf-8")
    )
    fuel_boards = FuelBoardsBaseline.model_validate_json(
        (BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    return BaselineBundle(
        manifest=manifest,
        countries=countries,
        speed_limits=speed_limits,
        fuel_boards=fuel_boards,
        locales=locales,
    )


def test_no_raw_scs_files_committed_under_data() -> None:
    assert BASELINE_DIR.is_dir(), f"Missing baseline directory: {BASELINE_DIR}"
    if DATA_DIR.is_dir():
        raw_scs = [
            p for p in DATA_DIR.rglob("*") if p.is_file() and p.suffix.lower() in {".sii", ".sui"}
        ]
        assert raw_scs == [], f"Raw SCS files prohibited under data/: {raw_scs}"


def test_committed_baseline_manifest_and_sha256s() -> None:
    for filename in REQUIRED_FILES:
        fpath = BASELINE_DIR / filename
        assert fpath.is_file(), f"Missing committed baseline file: {fpath}"
        raw_bytes = fpath.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf"), f"BOM found in {filename}"
        assert b"\r" not in raw_bytes, f"CR/CRLF found in {filename}"

    raw_manifest_obj = cast(
        dict[str, object],
        json.loads((BASELINE_DIR / "manifest.json").read_text("utf-8")),
    )
    assert "timestamp" not in raw_manifest_obj
    assert "created_at" not in raw_manifest_obj

    bundle = _load_committed_bundle()
    m = bundle.manifest
    assert m.game_version == "1.62.3.3"
    assert m.application == "eut2"
    assert m.extractor_schema_version == 1
    assert m.country_count == 36
    assert m.speed_limit_count == 36
    assert m.fuel_board_count == 461
    assert m.active_fp_board_count == 373
    assert m.placeholder_or_blank_board_count == 88
    assert m.locale_count == 43
    assert m.tz_key_count == 12
    assert m.fp_key_count == 99

    expected_data_files = {
        "countries.json",
        "speed_limits.json",
        "fuel_boards.json",
        "locales.json",
    }
    assert set(m.file_sha256s) == expected_data_files
    for filename in expected_data_files:
        actual_digest = hashlib.sha256((BASELINE_DIR / filename).read_bytes()).hexdigest()
        assert m.file_sha256s[filename] == actual_digest

    assert verify_baseline_bundle(bundle, BASELINE_DIR) == []


def test_committed_countries_invariants() -> None:
    countries_bl = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    assert len(countries_bl.countries) == 36
    by_slug = {c.slug: c for c in countries_bl.countries}

    iceland = by_slug["iceland"]
    assert iceland.country_id == 26
    assert iceland.iso_country_code == "isl"
    assert iceland.iso_country_code_quoted is False
    assert iceland.mass_limit_per_axle_count == [18000, 29000, 38000, 46000, 60000]

    bosnia = by_slug["bosnia"]
    assert bosnia.iso_country_code == "bih"
    assert bosnia.iso_country_code_quoted is True

    for slug in ("bosnia", "finland", "norway", "spain", "sweden"):
        country = by_slug[slug]
        assert len(country.regions) > 0
        assert len(country.regions) == len(country.region_areas)

    assert "rep_srpska" in bosnia.regions
    assert "the_north" in by_slug["finland"].regions
    assert {"rc_train", "the_north"} <= set(by_slug["norway"].regions)
    assert {"catalonia", "navarre", "basque"} <= set(by_slug["spain"].regions)
    assert {"rc_train", "the_north", "inland"} <= set(by_slug["sweden"].regions)

    russia = by_slug["russia"]
    assert len(russia.secondary_time_zone_area) == 1
    assert len(russia.secondary_time_zone) == 1
    assert len(russia.secondary_time_zone_name) == 1


def test_committed_speed_limits_invariants() -> None:
    sl_bl = SpeedLimitsBaseline.model_validate_json(
        (BASELINE_DIR / "speed_limits.json").read_text("utf-8")
    )
    assert len(sl_bl.speed_limits) == 36
    by_slug = {s.slug: s for s in sl_bl.speed_limits}

    for slug in ("germany", "finland", "norway", "spain", "sweden", "uk"):
        assert by_slug[slug].has_train is True
        assert by_slug[slug].has_tram is True

    for slug in ("bosnia", "bulgaria", "iceland"):
        assert by_slug[slug].has_train is False
        assert by_slug[slug].has_tram is False

    for slug in ("bulgaria", "romania", "turkey"):
        car_block = next(b for b in by_slug[slug].blocks if b.vehicle_speed_class == "car")
        assert any(lane.uncommon is True for lane in car_block.lanes)


def test_committed_fuel_boards_invariants() -> None:
    boards_bl = FuelBoardsBaseline.model_validate_json(
        (BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    assert len(boards_bl.boards) == 461

    board_names = {b.board_name for b in boards_bl.boards}
    for highway_sign in ("fi_oulu_95", "fi_oulu_98", "rs_fuel_01", "ru_m_95", "ru_m_98"):
        assert highway_sign not in board_names
        assert highway_sign in boards_bl.excluded_fuel_keyword_boards

    active_fp = [b for b in boards_bl.boards if b.classification == "active_fp"]
    placeholders_blanks = [
        b for b in boards_bl.boards if b.classification in ("placeholder", "blank")
    ]
    assert len(active_fp) == 373
    assert len(placeholders_blanks) == 88

    for board in boards_bl.boards:
        assert board.model_name == ""
        assert board.items_count == 1
        if board.classification == "active_fp":
            assert board.fp_key is not None and board.fp_key.startswith("fp_")
        else:
            assert board.fp_key is None

    by_name = {b.board_name: b for b in boards_bl.boards}
    assert by_name["gas_ba_apus_lpg"].classification == "active_fp"
    assert by_name["gas_ba_apus_lpg"].fp_key == "fp_ba_diesel5"
    assert by_name["gas_is_skanfill_95"].classification == "placeholder"
    assert by_name["gas_is_skanfill_95"].fp_key is None


def test_committed_locales_invariants() -> None:
    locales_bl = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    assert len(locales_bl.active_locales) == 43
    assert "fr_qc" not in locales_bl.active_locales
    assert "fr_ca" in locales_bl.active_locales
    assert len(locales_bl.tz_keys) == 12
    assert all(key.startswith("tz_") for key in locales_bl.tz_keys)
    assert len(locales_bl.fp_keys) == 99
    assert all(key.startswith("fp_") for key in locales_bl.fp_keys)


@pytest.mark.local_ets2
@pytest.mark.skipif(not _has_local_ets2(), reason="Local ETS2 1.62.3.3s archives not present")
def test_local_ets2_extract_matches_committed_baseline_zero_diff() -> None:
    bundle = extract_baseline(resolve_game_dir())
    assert verify_baseline_bundle(bundle, BASELINE_DIR) == []


@pytest.mark.local_ets2
@pytest.mark.skipif(not _has_local_ets2(), reason="Local ETS2 1.62.3.3s archives not present")
def test_local_ets2_all_36_sii_surgical_round_trips_in_memory() -> None:
    def_scs = resolve_game_dir() / "def.scs"
    archive = open_archive(def_scs)
    try:
        includes = parse_country_includes(archive.read_bytes("def/country.sii"))
        assert len(includes) == 36

        for include_rel in includes:
            country_vfs = include_rel if include_rel.startswith("def/") else f"def/{include_rel}"
            raw_country = archive.read_bytes(country_vfs)
            noop_country = patch_country_data(raw_country, CountryDataPatch())
            assert serialize_sii_text(noop_country) == normalize_sii_bytes(raw_country).encode(
                "utf-8"
            )

            orig_model = parse_country_data(raw_country)
            edited_country = patch_country_data(raw_country, CountryDataPatch(fuel_price=1.999))
            edited_model = parse_country_data(edited_country)
            assert edited_model.fuel_price == pytest.approx(1.999)
            assert edited_model.country_id == orig_model.country_id
            assert edited_model.name == orig_model.name
            assert edited_model.iso_country_code == orig_model.iso_country_code
            assert edited_model.iso_country_code_quoted == orig_model.iso_country_code_quoted
            assert edited_model.regions == orig_model.regions
            assert edited_model.region_areas == orig_model.region_areas
            assert edited_model.secondary_time_zone == orig_model.secondary_time_zone
            assert edited_model.secondary_time_zone_area == orig_model.secondary_time_zone_area
            assert edited_model.secondary_time_zone_name == orig_model.secondary_time_zone_name
            assert edited_model.mass_limit_per_axle_count == orig_model.mass_limit_per_axle_count
            assert serialize_sii_text(
                patch_country_data(
                    edited_country.encode("utf-8"),
                    CountryDataPatch(fuel_price=1.999),
                )
            ) == serialize_sii_text(edited_country)

            slug = pathlib.Path(country_vfs).stem
            sl_vfs = f"def/country/{slug}/speed_limits.sii"
            raw_sl = archive.read_bytes(sl_vfs)
            noop_sl = patch_speed_limits(raw_sl, {})
            assert serialize_sii_text(noop_sl) == normalize_sii_bytes(raw_sl).encode("utf-8")

            parsed_sl = parse_speed_limits(raw_sl)
            car_block = parsed_sl.get_block("car")
            assert car_block is not None
            assert len(car_block.lanes) > 0
            first_lane = car_block.lanes[0]
            updated_lanes = list(car_block.lanes)
            updated_lanes[0] = LaneSpeedRule(
                lane_speed_class=first_lane.lane_speed_class,
                limit=(first_lane.limit + 5) if first_lane.limit is not None else 55,
                urban_limit=first_lane.urban_limit,
                max_limit=first_lane.max_limit,
                uncommon=first_lane.uncommon,
            )
            edited_sl = patch_speed_limits(raw_sl, {"car": updated_lanes})
            edited_parsed_sl = parse_speed_limits(edited_sl)

            for preserved_cls in ("truck", "bus", "train", "tram"):
                assert edited_parsed_sl.get_block(preserved_cls) == parsed_sl.get_block(
                    preserved_cls
                )

            norm_orig_sl = normalize_sii_bytes(raw_sl)
            for rail_marker in (
                "country_speed_limit : .speed_limit.train",
                "country_speed_limit : .speed_limit.tram",
            ):
                if rail_marker in norm_orig_sl:
                    orig_tail = norm_orig_sl[norm_orig_sl.index(rail_marker) :]
                    edit_tail = edited_sl[edited_sl.index(rail_marker) :]
                    assert edit_tail == orig_tail

            assert serialize_sii_text(
                patch_speed_limits(edited_sl.encode("utf-8"), {"car": updated_lanes})
            ) == serialize_sii_text(edited_sl)
    finally:
        archive.close()
