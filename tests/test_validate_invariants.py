"""ETS2 1.62 core realism invariants and reference-mod regression tests."""

from __future__ import annotations

import pathlib
import shutil
import zipfile

import pytest

from ets2v2.baseline.models import (
    CountriesBaseline,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.package import BuiltEditionPaths, build_core_editions
from ets2v2.sii.country import CountryDataModel, parse_country_data
from ets2v2.sii.document import SiiDocument
from ets2v2.sii.localization import LocalizationEntry, parse_localization_db
from ets2v2.sii.sign_board import SignBoardTemplate, parse_sign_board
from ets2v2.sii.speed_limits import SpeedLimitsFile, parse_speed_limits
from ets2v2.validate import (
    ValidationCollector,
    ValidationReport,
    validate_core_realism_invariants,
    validate_local_zip,
    validate_totem_invariants,
    validate_workshop_package,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
ICONS_DIR = REPO_ROOT / "assets" / "icons"


@pytest.fixture(scope="module")
def built_editions(tmp_path_factory: pytest.TempPathFactory) -> dict[str, BuiltEditionPaths]:
    out_dir = tmp_path_factory.mktemp("inv_dist")
    built = build_core_editions(
        out_dir,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
    )
    return {"summer": built["summer"], "winter": built["winter"]}


@pytest.fixture(scope="module")
def baselines() -> tuple[CountriesBaseline, SpeedLimitsBaseline, LocalesBaseline]:
    return (
        CountriesBaseline.model_validate_json((BASELINE_DIR / "countries.json").read_text("utf-8")),
        SpeedLimitsBaseline.model_validate_json(
            (BASELINE_DIR / "speed_limits.json").read_text("utf-8")
        ),
        LocalesBaseline.model_validate_json((BASELINE_DIR / "locales.json").read_text("utf-8")),
    )


def _clone_workshop(src: pathlib.Path, dst: pathlib.Path) -> pathlib.Path:
    shutil.copytree(src, dst)
    return dst


def _issue_codes(report: ValidationReport) -> set[str]:
    return {issue.code for issue in report.issues}


def _load_models_from_workshop(
    workshop_dir: pathlib.Path,
) -> tuple[dict[str, CountryDataModel], dict[str, SpeedLimitsFile]]:
    country_dir = workshop_dir / "universal" / "def" / "country"
    countries = {
        p.stem: parse_country_data(p.read_bytes()) for p in sorted(country_dir.glob("*.sui"))
    }
    speeds = {
        p.parent.name: parse_speed_limits(p.read_bytes())
        for p in sorted(country_dir.glob("*/speed_limits.sii"))
    }
    return countries, speeds


def test_positive_invariants_summer_and_winter_workshop_and_local_zips(
    built_editions: dict[str, BuiltEditionPaths],
) -> None:
    for edition in ("summer", "winter"):
        info = built_editions[edition]
        ws_report = validate_workshop_package(info.workshop_dir, baseline_dir=BASELINE_DIR)
        assert ws_report.ok is True, ws_report.issues

        local_report = validate_local_zip(info.local_zip_path, baseline_dir=BASELINE_DIR)
        assert local_report.ok is True, local_report.issues


def test_invariant_rejects_estonia_corrupted_name_3249064596(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_estonia")
    est = ws / "universal" / "def" / "country" / "estonia.sui"
    est.write_bytes(est.read_bytes().replace(b'name: "Eesti"', b'name: "@@tz_eest@@i"'))
    report = validate_workshop_package(ws, baseline_dir=BASELINE_DIR)
    assert report.ok is False
    assert "ETS2V2-INV-IDENTITY" in _issue_codes(report)


def test_invariant_rejects_non_uk_leftside_traffic_flip(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_leftside")
    alb = ws / "universal" / "def" / "country" / "albania.sui"
    alb.write_bytes(
        alb.read_bytes().replace(
            b"\tdriving_tired_offence: true\n",
            b"\tdriving_tired_offence: true\n\tleftside_traffic: true\n",
        )
    )
    report = validate_workshop_package(ws, baseline_dir=BASELINE_DIR)
    assert report.ok is False
    assert "ETS2V2-INV-LEFTSIDE" in _issue_codes(report)


def test_invariant_rejects_spain_stripped_regions_3668352310(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_spain")
    spain = ws / "universal" / "def" / "country" / "spain.sui"
    filtered = "\n".join(
        line
        for line in spain.read_text("utf-8").splitlines()
        if "regions[]" not in line and "region_areas[]" not in line
    )
    spain.write_text(filtered + "\n", encoding="utf-8")
    report = validate_workshop_package(ws, baseline_dir=BASELINE_DIR)
    assert report.ok is False
    assert "ETS2V2-INV-REGIONS" in _issue_codes(report)


def test_invariant_rejects_iceland_40t_axles_and_90kmh_truck(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_ax = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_is_ax")
    isl = ws_ax / "universal" / "def" / "country" / "iceland.sui"
    text = isl.read_text("utf-8")
    old_block = (
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 29000\n"
        "\tmass_limit_per_axle_count[]: 38000\n"
        "\tmass_limit_per_axle_count[]: 46000\n"
        "\tmass_limit_per_axle_count[]: 60000\n"
    )
    new_block = (
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 36000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
    )
    assert old_block in text
    isl.write_text(text.replace(old_block, new_block), encoding="utf-8")
    r_ax = validate_workshop_package(ws_ax, baseline_dir=BASELINE_DIR)
    assert r_ax.ok is False
    codes_ax = _issue_codes(r_ax)
    assert "ETS2V2-INV-AXLE" in codes_ax
    assert "ETS2V2-INV-ICELAND" in codes_ax

    ws_spd = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_is_spd")
    isl_spd = ws_spd / "universal" / "def" / "country" / "iceland" / "speed_limits.sii"
    isl_spd.write_bytes(isl_spd.read_bytes().replace(b"limit[]: 80", b"limit[]: 90"))
    r_spd = validate_workshop_package(ws_spd, baseline_dir=BASELINE_DIR)
    assert r_spd.ok is False
    assert "ETS2V2-INV-ICELAND" in _issue_codes(r_spd)


def test_invariant_rejects_germany_dropped_train_tram_and_bulgaria_dropped_slow_road(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_de = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_de_rail")
    de_spd = ws_de / "universal" / "def" / "country" / "germany" / "speed_limits.sii"
    de_text = de_spd.read_text("utf-8")
    de_doc = SiiDocument.parse(de_text, require_siinunit=True)
    rail_units = [
        unit
        for unit in de_doc.find_units(class_name="country_speed_limit")
        if (scalar := unit.get_scalar("vehicle_speed_class")) is not None
        and scalar.raw_value.strip() in {"train", "tram"}
    ]
    assert rail_units, "Expected train/tram blocks in Germany speed_limits.sii"
    cut_idx = min(unit.span.start for unit in rail_units)
    de_spd.write_text(de_text[:cut_idx] + "}\n", encoding="utf-8")
    r_de = validate_workshop_package(ws_de, baseline_dir=BASELINE_DIR)
    assert r_de.ok is False
    assert "ETS2V2-INV-SPEED-BLOCKS" in _issue_codes(r_de)

    ws_bg = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_bg_slow")
    bg_spd = ws_bg / "universal" / "def" / "country" / "bulgaria" / "speed_limits.sii"
    bg_lines = bg_spd.read_text("utf-8").splitlines()
    out_lines: list[str] = []
    skipping_slow = False
    for line in bg_lines:
        if "lane_speed_class[]: slow_road" in line:
            skipping_slow = True
            continue
        if skipping_slow:
            if line.strip() == "}" or line.strip() == "":
                skipping_slow = False
                out_lines.append(line)
            continue
        out_lines.append(line)
    bg_spd.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    r_bg = validate_workshop_package(ws_bg, baseline_dir=BASELINE_DIR)
    assert r_bg.ok is False
    assert "ETS2V2-INV-SPEED-BLOCKS" in _issue_codes(r_bg)


def test_invariant_rejects_unsupported_tz_tokens_cet_and_wet(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_de = _clone_workshop(built_editions["winter"].workshop_dir, tmp_path / "ws_cet")
    de = ws_de / "universal" / "def" / "country" / "germany.sui"
    de.write_bytes(
        de.read_bytes().replace(b'time_zone_name: "CET"', b'time_zone_name: "@@tz_cet@@"')
    )
    r_de = validate_workshop_package(ws_de, baseline_dir=BASELINE_DIR)
    assert r_de.ok is False
    assert "ETS2V2-INV-TZ-TOKEN" in _issue_codes(r_de)

    ws_pt = _clone_workshop(built_editions["winter"].workshop_dir, tmp_path / "ws_wet")
    pt = ws_pt / "universal" / "def" / "country" / "portugal.sui"
    pt.write_bytes(
        pt.read_bytes().replace(b'time_zone_name: "WET"', b'time_zone_name: "@@tz_wet@@"')
    )
    r_pt = validate_workshop_package(ws_pt, baseline_dir=BASELINE_DIR)
    assert r_pt.ok is False
    assert "ETS2V2-INV-TZ-TOKEN" in _issue_codes(r_pt)


def test_invariant_rejects_russia_dropped_secondary_tz_and_greece_axle_downgrade(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_ru = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_ru")
    ru = ws_ru / "universal" / "def" / "country" / "russia.sui"
    ru_filtered = "\n".join(
        line for line in ru.read_text("utf-8").splitlines() if "secondary_time_zone" not in line
    )
    ru.write_text(ru_filtered + "\n", encoding="utf-8")
    r_ru = validate_workshop_package(ws_ru, baseline_dir=BASELINE_DIR)
    assert r_ru.ok is False
    assert "ETS2V2-INV-SECONDARY-TZ" in _issue_codes(r_ru)

    ws_gr = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_gr")
    gr = ws_gr / "universal" / "def" / "country" / "greece.sui"
    gr.write_bytes(
        gr.read_bytes().replace(
            b"mass_limit_per_axle_count[]: 44000",
            b"mass_limit_per_axle_count[]: 40000",
        )
    )
    r_gr = validate_workshop_package(ws_gr, baseline_dir=BASELINE_DIR)
    assert r_gr.ok is False
    assert "ETS2V2-INV-AXLE" in _issue_codes(r_gr)


def test_invariant_runs_on_local_zip_and_direct_auditor_catches_count_and_hct_truncation(
    built_editions: dict[str, BuiltEditionPaths],
    baselines: tuple[CountriesBaseline, SpeedLimitsBaseline, LocalesBaseline],
    tmp_path: pathlib.Path,
) -> None:
    # Local ZIP mutation: corrupt estonia.sui inside local ZIP
    bad_zip = tmp_path / "bad_estonia.zip"
    with (
        zipfile.ZipFile(built_editions["summer"].local_zip_path, "r") as zin,
        zipfile.ZipFile(bad_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout,
    ):
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "def/country/estonia.sui":
                data = data.replace(b'name: "Eesti"', b'name: "@@tz_eest@@i"')
            zout.writestr(info, data)
    local_report = validate_local_zip(bad_zip, baseline_dir=BASELINE_DIR)
    assert local_report.ok is False
    assert "ETS2V2-INV-IDENTITY" in _issue_codes(local_report)

    # Direct auditor checks: truncated Finland 10-element HCT array + missing country slug
    bl_countries, bl_speeds, bl_locales = baselines
    countries, speeds = _load_models_from_workshop(built_editions["summer"].workshop_dir)
    fin_truncated = countries["finland"].model_copy(
        update={"mass_limit_per_axle_count": countries["finland"].mass_limit_per_axle_count[:5]}
    )
    countries_mut = dict(countries)
    countries_mut["finland"] = fin_truncated
    del countries_mut["uk"]

    collector = ValidationCollector()
    validate_core_realism_invariants(
        countries_mut,
        speeds,
        bl_countries,
        bl_speeds,
        bl_locales,
        collector,
    )
    report = collector.build_report("direct", "workshop")
    assert report.ok is False
    codes = _issue_codes(report)
    assert "ETS2V2-INV-COUNTRY-COUNT" in codes
    assert "ETS2V2-INV-AXLE" in codes


def test_invariant_md05_lane_sequence_uncommon_and_max_limit_nullability(
    built_editions: dict[str, BuiltEditionPaths],
    baselines: tuple[CountriesBaseline, SpeedLimitsBaseline, LocalesBaseline],
) -> None:
    bl_countries, bl_speeds, bl_locales = baselines
    countries, base_speeds = _load_models_from_workshop(built_editions["summer"].workshop_dir)

    # 1. Duplicate / reordered lane_speed_class sequence -> ETS2V2-INV-SPEED-BLOCKS
    de_speed = base_speeds["germany"]
    de_reordered_blocks = [
        block.model_copy(update={"lanes": list(reversed(block.lanes))})
        if block.vehicle_speed_class == "car"
        else block
        for block in de_speed.blocks
    ]
    speeds_reorder = dict(base_speeds)
    speeds_reorder["germany"] = de_speed.model_copy(update={"blocks": de_reordered_blocks})
    c_reorder = ValidationCollector()
    validate_core_realism_invariants(
        countries, speeds_reorder, bl_countries, bl_speeds, bl_locales, c_reorder
    )
    assert "ETS2V2-INV-SPEED-BLOCKS" in _issue_codes(c_reorder.build_report("reorder", "workshop"))

    # 2. Spurious uncommon=True where baseline has uncommon=None -> ETS2V2-INV-SPEED-BLOCKS
    de_uncommon_blocks = [
        block.model_copy(
            update={
                "lanes": [block.lanes[0].model_copy(update={"uncommon": True}), *block.lanes[1:]]
            }
        )
        if block.vehicle_speed_class == "car"
        else block
        for block in de_speed.blocks
    ]
    speeds_uncommon = dict(base_speeds)
    speeds_uncommon["germany"] = de_speed.model_copy(update={"blocks": de_uncommon_blocks})
    c_uncommon = ValidationCollector()
    validate_core_realism_invariants(
        countries, speeds_uncommon, bl_countries, bl_speeds, bl_locales, c_uncommon
    )
    assert "ETS2V2-INV-SPEED-BLOCKS" in _issue_codes(
        c_uncommon.build_report("uncommon", "workshop")
    )

    # 3. max_limit removed on Iceland truck block -> ETS2V2-INV-SPEED-BLOCKS + ETS2V2-INV-ICELAND
    is_speed = base_speeds["iceland"]
    is_missing_max_blocks = [
        block.model_copy(
            update={"lanes": [lane.model_copy(update={"max_limit": None}) for lane in block.lanes]}
        )
        if block.vehicle_speed_class == "truck"
        else block
        for block in is_speed.blocks
    ]
    speeds_is = dict(base_speeds)
    speeds_is["iceland"] = is_speed.model_copy(update={"blocks": is_missing_max_blocks})
    c_is = ValidationCollector()
    validate_core_realism_invariants(
        countries, speeds_is, bl_countries, bl_speeds, bl_locales, c_is
    )
    is_codes = _issue_codes(c_is.build_report("iceland_max", "workshop"))
    assert "ETS2V2-INV-SPEED-BLOCKS" in is_codes
    assert "ETS2V2-INV-ICELAND" in is_codes


# ---------------------------------------------------------------------------
# D-12: Totem Locale Sync & 460-Board Integrity Invariants
# ---------------------------------------------------------------------------


def _load_totems_from_workshop(
    workshop_dir: pathlib.Path,
) -> tuple[dict[str, SignBoardTemplate], dict[str, list[LocalizationEntry]]]:
    board_dir = workshop_dir / "universal" / "def" / "sign" / "board"
    boards = {p.stem: parse_sign_board(p.read_bytes()) for p in sorted(board_dir.glob("*.sii"))}
    locale_root = workshop_dir / "universal" / "locale"
    locales = {
        p.parent.name: parse_localization_db(p.read_bytes())
        for p in sorted(locale_root.glob("*/local_module.ets2v2_fuel.sii"))
    }
    return boards, locales


def test_d12_locale_sync_fault_injections(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    bl_fuel_boards = FuelBoardsBaseline.model_validate_json(
        (BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )

    # 1. Missing 1 of 43 active locales -> ETS2V2-INV-LOCALE-SYNC
    ws_miss = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_miss_loc")
    (ws_miss / "universal" / "locale" / "de_de" / "local_module.ets2v2_fuel.sii").unlink()
    r_miss = validate_workshop_package(ws_miss, baseline_dir=BASELINE_DIR)
    assert r_miss.ok is False
    assert "ETS2V2-INV-LOCALE-SYNC" in _issue_codes(r_miss)

    # 2. Stray deprecated fr_qc locale -> ETS2V2-INV-LOCALE-SYNC
    ws_frqc = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_fr_qc")
    fr_qc_dir = ws_frqc / "universal" / "locale" / "fr_qc"
    fr_qc_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        ws_frqc / "universal" / "locale" / "fr_ca" / "local_module.ets2v2_fuel.sii",
        fr_qc_dir / "local_module.ets2v2_fuel.sii",
    )
    r_frqc = validate_workshop_package(ws_frqc, baseline_dir=BASELINE_DIR)
    assert r_frqc.ok is False
    assert "ETS2V2-INV-LOCALE-SYNC" in _issue_codes(r_frqc)

    # 3. Mismatched val[] in a single locale -> ETS2V2-INV-LOCALE-SYNC
    ws_drift = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_loc_drift")
    fr_loc = ws_drift / "universal" / "locale" / "fr_fr" / "local_module.ets2v2_fuel.sii"
    fr_loc.write_bytes(fr_loc.read_bytes().replace(b'val[]: "1', b'val[]: "9', 1))
    r_drift = validate_workshop_package(ws_drift, baseline_dir=BASELINE_DIR)
    assert r_drift.ok is False
    assert "ETS2V2-INV-LOCALE-SYNC" in _issue_codes(r_drift)

    # 4. Direct auditor checks: duplicate key, bad key name, comma decimal, currency symbol
    boards, base_locales = _load_totems_from_workshop(built_editions["summer"].workshop_dir)

    for bad_entry in (
        LocalizationEntry(key=base_locales["en_gb"][0].key, val=base_locales["en_gb"][0].val),
        LocalizationEntry(key="fp_de_diesel_missing_suffix", val="1.79"),
        LocalizationEntry(key="fp_de_extra_ets2v2", val="1,78"),
        LocalizationEntry(key="fp_de_extra_ets2v2", val="1.78€"),
    ):
        mut_locales = {lang: [*entries, bad_entry] for lang, entries in base_locales.items()}
        col = ValidationCollector()
        validate_totem_invariants(boards, mut_locales, bl_fuel_boards, bl_locales, col)
        rep = col.build_report("bad_locale_entry", "workshop")
        assert rep.ok is False
        assert "ETS2V2-INV-LOCALE-SYNC" in _issue_codes(rep), bad_entry


def test_d12_totem_boards_fault_injections(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    bl_fuel_boards = FuelBoardsBaseline.model_validate_json(
        (BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )

    # 1. Dangling token in def/sign/board/gas_de_big_diesel.sii -> ETS2V2-INV-TOTEM-BOARDS
    ws_dang = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_dangling")
    de_big = ws_dang / "universal" / "def" / "sign" / "board" / "gas_de_big_diesel.sii"
    de_big.write_bytes(
        de_big.read_bytes().replace(b"@@fp_de_diesel_ets2v2@@", b"@@fp_xx_missing_ets2v2@@")
    )
    r_dang = validate_workshop_package(ws_dang, baseline_dir=BASELINE_DIR)
    assert r_dang.ok is False
    assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(r_dang)

    # 2. Orphan unused key in local_module.ets2v2_fuel.sii -> ETS2V2-INV-TOTEM-BOARDS
    boards, base_locales = _load_totems_from_workshop(built_editions["summer"].workshop_dir)
    orphan_entry = LocalizationEntry(key="fp_zz_unused_ets2v2", val="1.99")
    orphan_locales = {
        lang: sorted([*entries, orphan_entry], key=lambda e: e.key)
        for lang, entries in base_locales.items()
    }
    col_orphan = ValidationCollector()
    validate_totem_invariants(boards, orphan_locales, bl_fuel_boards, bl_locales, col_orphan)
    assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(
        col_orphan.build_report("orphan_token", "workshop")
    )

    # 3. Emitted gas_empty.sii and emitted highway sign fi_oulu_95.sii -> ETS2V2-INV-TOTEM-BOARDS
    ws_empty = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_empty")
    sample_raw = (
        ws_empty / "universal" / "def" / "sign" / "board" / "gas_de_big_diesel.sii"
    ).read_bytes()
    (ws_empty / "universal" / "def" / "sign" / "board" / "gas_empty.sii").write_bytes(sample_raw)
    r_empty = validate_workshop_package(ws_empty, baseline_dir=BASELINE_DIR)
    assert r_empty.ok is False
    assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(r_empty)

    ws_hw = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_highway")
    (ws_hw / "universal" / "def" / "sign" / "board" / "fi_oulu_95.sii").write_bytes(sample_raw)
    r_hw = validate_workshop_package(ws_hw, baseline_dir=BASELINE_DIR)
    assert r_hw.ok is False
    assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(r_hw)

    # 4. Mutated visual/geometry attributes (font_color, font_face, coords_r, width)
    ws_attr = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_attr")
    board_file = ws_attr / "universal" / "def" / "sign" / "board" / "gas_de_big_diesel.sii"
    orig_board_raw = board_file.read_bytes()
    for target_bytes, repl_bytes in (
        (b"font_color: 200", b"font_color: 16777215"),
        (
            b'font_face: "/font/sign/gas_roadgeek_2005_mittelschrift.font"',
            b'font_face: "/font/sign/gas_karnivore_lite.font"',
        ),
        (b"coords_r: 1.262711883", b"coords_r: 2.5"),
        (b"width: 1.5", b"width: 2.0"),
    ):
        assert target_bytes in orig_board_raw, f"Expected {target_bytes!r} in gas_de_big_diesel.sii"
        board_file.write_bytes(orig_board_raw.replace(target_bytes, repl_bytes, 1))
        r_attr = validate_workshop_package(ws_attr, baseline_dir=BASELINE_DIR)
        assert r_attr.ok is False
        assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(r_attr), target_bytes
    board_file.write_bytes(orig_board_raw)

    # 5. Swapped D-09 gas_is_yokull_95 token -> ETS2V2-INV-TOTEM-BOARDS
    ws_swap = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_swap")
    yokull = ws_swap / "universal" / "def" / "sign" / "board" / "gas_is_yokull_95.sii"
    yokull.write_bytes(
        yokull.read_bytes().replace(b"@@fp_is_petrol_95_ets2v2@@", b"@@fp_is_diesel_ets2v2@@")
    )
    r_swap = validate_workshop_package(ws_swap, baseline_dir=BASELINE_DIR)
    assert r_swap.ok is False
    assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(r_swap)

    # 6. Local ZIP board corruption triggers ETS2V2-INV-TOTEM-BOARDS
    bad_zip = tmp_path / "bad_totem.zip"
    with (
        zipfile.ZipFile(built_editions["summer"].local_zip_path, "r") as zin,
        zipfile.ZipFile(bad_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout,
    ):
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "def/sign/board/gas_is_yokull_95.sii":
                data = data.replace(b"@@fp_is_petrol_95_ets2v2@@", b"@@fp_is_diesel_ets2v2@@")
            zout.writestr(info, data)
    r_zip = validate_local_zip(bad_zip, baseline_dir=BASELINE_DIR)
    assert r_zip.ok is False
    assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(r_zip)

    # 7. Non-<sup> 7-segment board (gas_de_enz_diesel) referencing a token whose value contains
    # <sup> markup -> ETS2V2-INV-TOTEM-BOARDS (MD-04)
    ws_sup = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_7seg_sup")
    de_enz = ws_sup / "universal" / "def" / "sign" / "board" / "gas_de_enz_diesel.sii"
    de_enz.write_bytes(
        de_enz.read_bytes().replace(b"@@fp_de_diesel_3_ets2v2@@", b"@@fp_de_diesel_ets2v2@@")
    )
    r_sup = validate_workshop_package(ws_sup, baseline_dir=BASELINE_DIR)
    assert r_sup.ok is False
    assert any(
        issue.code == "ETS2V2-INV-TOTEM-BOARDS" and "<sup>" in issue.detail
        for issue in r_sup.issues
    )
