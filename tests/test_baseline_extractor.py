"""CI-safe synthetic HashFS v2 tests for baseline extraction and CLI commands."""

from __future__ import annotations

import hashlib
import json
import pathlib
import struct
import zipfile
import zlib

import pytest

from ets2v2.baseline import (
    DEFAULT_ETS2_GAME_DIR,
    BaselineBundle,
    BaselineManifest,
    CountriesBaseline,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
    extract_baseline,
    resolve_game_dir,
    verify_baseline_bundle,
    write_baseline_bundle,
)
from ets2v2.cli import main
from ets2v2.vfs.cityhash import hash_vfs_path


def _encode_v2_dir_listing(items: list[str]) -> bytes:
    encoded = [item.encode("utf-8") for item in items]
    header = struct.pack("<I", len(encoded))
    lengths = bytes(len(e) for e in encoded)
    return header + lengths + b"".join(encoded)


def _build_hashfs_v2(
    dest: pathlib.Path,
    files: dict[str, bytes],
    *,
    dirs: dict[str, list[str]],
    compress: bool = True,
) -> pathlib.Path:
    """Build a synthetic HashFS v2 archive with 16-byte alignment."""
    cursor = 128
    blob_parts: list[bytes] = [b"\x00" * (cursor - 44)]
    meta_words: list[int] = []
    entry_rows: list[tuple[int, int, int, int]] = []

    def append_blob(payload: bytes) -> int:
        nonlocal cursor
        pad = (-cursor) % 16
        if pad:
            blob_parts.append(b"\x00" * pad)
            cursor += pad
        off_blocks = cursor // 16
        blob_parts.append(payload)
        cursor += len(payload)
        return off_blocks

    for dir_path, items in dirs.items():
        h = hash_vfs_path(dir_path)
        raw = _encode_v2_dir_listing(items)
        stored = zlib.compress(raw) if compress else raw
        comp_nibble = 1 if compress else 0
        off_blocks = append_blob(stored)
        midx = len(meta_words)
        meta_words.extend(
            [
                (0x81 << 24) | (midx + 1),
                (comp_nibble << 28) | len(stored),
                len(raw),
                0,
                off_blocks,
            ]
        )
        entry_rows.append((h, midx, 1, 5))

    for file_path, raw in files.items():
        h = hash_vfs_path(file_path)
        stored = zlib.compress(raw) if compress else raw
        comp_nibble = 1 if compress else 0
        off_blocks = append_blob(stored)
        midx = len(meta_words)
        meta_words.extend(
            [
                (0x80 << 24) | (midx + 1),
                (comp_nibble << 28) | len(stored),
                len(raw),
                0,
                off_blocks,
            ]
        )
        entry_rows.append((h, midx, 1, 4))

    entry_rows.sort(key=lambda r: r[0])
    raw_entry_table = b"".join(struct.pack("<QIHH", *row) for row in entry_rows)
    raw_meta_table = struct.pack(f"<{len(meta_words)}I", *meta_words) if meta_words else b""
    stored_entry_table = zlib.compress(raw_entry_table)
    stored_meta_table = zlib.compress(raw_meta_table)

    pad_e = (-cursor) % 16
    if pad_e:
        blob_parts.append(b"\x00" * pad_e)
        cursor += pad_e
    entry_table_offset = cursor
    blob_parts.append(stored_entry_table)
    cursor += len(stored_entry_table)

    pad_m = (-cursor) % 16
    if pad_m:
        blob_parts.append(b"\x00" * pad_m)
        cursor += pad_m
    meta_table_offset = cursor
    blob_parts.append(stored_meta_table)
    cursor += len(stored_meta_table)

    header = struct.pack(
        "<4sHH4sIIIIQQ",
        b"SCS#",
        2,
        0,
        b"CITY",
        len(entry_rows),
        len(stored_entry_table),
        len(meta_words),
        len(stored_meta_table),
        entry_table_offset,
        meta_table_offset,
    )
    dest.write_bytes(header + b"".join(blob_parts))
    return dest


def _create_synthetic_ets2_install(root: pathlib.Path) -> pathlib.Path:
    """Create a synthetic HashFS v2 ETS2 install (version.scs, def.scs, stripped locale.scs)."""
    root.mkdir(parents=True, exist_ok=True)

    _build_hashfs_v2(
        root / "version.scs",
        files={
            "version.sii": (
                b"SiiNunit\n{\nfs_pack_set : _nameless.1.1 {\n"
                b"\tapplication: eut2\n"
                b'\tversion: "1.62.3.3"\n'
                b"}\n}\n"
            )
        },
        dirs={"": ["version.sii"]},
    )

    country_sii = (
        b"\xef\xbb\xbfSiiNunit\r\n{\r\n"
        b'@include "country/iceland.sui"\r\n'
        b'@include "country/bosnia.sui"\r\n'
        b'@include "country/russia.sui"\r\n'
        b"}\r\n"
    )
    iceland_sui = (
        b"country_data : country.data.iceland\n{\n"
        b"\tcountry_id: 26\n"
        b'\tname: "\xc3\x8dsland"\n'
        b'\tname_localized: "@@iceland@@"\n'
        b'\tcountry_code: "IS"\n'
        b"\tiso_country_code: isl\n"
        b"\tpos: (-83000, 0, -68000)\n"
        b"\tfuel_price: 2.307\n"
        b"\tlights_mandatory: true\n"
        b"\tdriving_tired_offence: true\n"
        b"\timperial_units: false\n"
        b"\tleftside_traffic: false\n"
        b"\ttrailer_standalone: false\n"
        b"\ttime_zone: 0\n"
        b'\ttime_zone_name: "@@tz_gmt@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 29000\n"
        b"\tmass_limit_per_axle_count[]: 38000\n"
        b"\tmass_limit_per_axle_count[]: 46000\n"
        b"\tmass_limit_per_axle_count[]: 60000\n"
        b"}\n"
    )
    bosnia_sui = (
        b"country_data : country.data.bosnia\n{\n"
        b"\tcountry_id: 17\n"
        b'\tname: "Bosna i Hercegovina"\n'
        b'\tcountry_code: "BIH"\n'
        b'\tiso_country_code: "bih"\n'
        b"\tfuel_price: 1.45\n"
        b"\ttime_zone: 120\n"
        b'\ttime_zone_name: "@@tz_cest@@"\n'
        b"\tregions[]: rep_srpska\n"
        b"\tregion_areas[]: (41000, 48000, 35000, 42000)\n"
        b"}\n"
    )
    russia_sui = (
        b"country_data : country.data.russia\n{\n"
        b"\tcountry_id: 38\n"
        b'\tname: "\xd0\xa0\xd0\xbe\xd1\x81\xd1\x81\xd0\xb8\xd1\x8f"\n'
        b'\tcountry_code: "RU"\n'
        b"\tiso_country_code: rus\n"
        b"\tfuel_price: 0.74\n"
        b"\ttime_zone: 180\n"
        b'\ttime_zone_name: "@@tz_msk@@"\n'
        b"\tsecondary_time_zone_area[]: (20000, 50000, -50000, -10000)\n"
        b"\tsecondary_time_zone[]: 120\n"
        b'\tsecondary_time_zone_name[]: "@@tz_eest@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 25000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"\tmass_limit_per_axle_count[]: 44000\n"
        b"}\n"
    )

    sl_iceland = (
        b"SiiNunit\n{\n"
        b"country_speed_limit : .speed_limit.car {\n"
        b"\tvehicle_speed_class: car\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 90\n\turban_limit[]: 50\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.truck {\n"
        b"\tvehicle_speed_class: truck\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.bus {\n"
        b"\tvehicle_speed_class: bus\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n"
        b"}\n"
        b"}\n"
    )
    sl_bosnia = (
        b"SiiNunit\n{\n"
        b"country_speed_limit : .speed_limit.car {\n"
        b"\tvehicle_speed_class: car\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n"
        b"\tlane_speed_class[]: slow_road\n\tlimit[]: 60\n\turban_limit[]: 40\n\tuncommon[]: true\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.truck {\n"
        b"\tvehicle_speed_class: truck\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.bus {\n"
        b"\tvehicle_speed_class: bus\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n"
        b"}\n"
        b"}\n"
    )
    sl_russia = (
        b"SiiNunit\n{\n"
        b"country_speed_limit : .speed_limit.car {\n"
        b"\tvehicle_speed_class: car\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 90\n\turban_limit[]: 60\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.truck {\n"
        b"\tvehicle_speed_class: truck\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 70\n\turban_limit[]: 60\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.bus {\n"
        b"\tvehicle_speed_class: bus\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 90\n\turban_limit[]: 60\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.train {\n"
        b"\tvehicle_speed_class: train\n"
        b"\tlane_speed_class[]: local_road\n\turban_limit[]: 60\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.tram {\n"
        b"\tvehicle_speed_class: tram\n"
        b"\tlane_speed_class[]: local_road\n\turban_limit[]: 60\n"
        b"}\n"
        b"}\n"
    )

    gas_de_big_95 = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.1.1 {\n"
        b'\tmodel_name: ""\n\tboard_size: (1.0, 2.0)\n\titems: 1\n\titems[0]: _nameless.1.2\n'
        b"}\n"
        b"sign_template_text : _nameless.1.2 {\n"
        b'\tfont_face: "/font/sign/gas_segment_7.font"\n'
        b"\tcoords_l: &c2a00000\n\tcoords_r: &42a00000\n"
        b"\tcoords_t: &42200000\n\tcoords_b: &c2200000\n"
        b"\th_align: center\n\tv_align: center\n"
        b'\ttext: "@@fp_de_natural95@@"\n'
        b"}\n}\n"
    )
    es_95_01 = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.2.1 {\n"
        b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.2.2\n'
        b"}\n"
        b"sign_template_text : _nameless.2.2 {\n"
        b'\tfont_face: "/font/sign/es_gas.font"\n'
        b"\tcoords_l: -40\n\tcoords_r: 40\n\tcoords_t: 20\n\tcoords_b: -20\n"
        b"\th_align: right\n\tv_align: center\n"
        b'\ttext: "@@fp_es_natural95@@"\n'
        b"}\n}\n"
    )
    gas_ba_apus_lpg = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.3.1 {\n"
        b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.3.2\n'
        b"}\n"
        b"sign_template_text : _nameless.3.2 {\n"
        b'\tfont_face: "/font/sign/ba_gas.font"\n'
        b"\tcoords_l: -30\n\tcoords_r: 30\n\tcoords_t: 15\n\tcoords_b: -15\n"
        b"\th_align: center\n\tv_align: center\n"
        b'\ttext: "@@fp_ba_diesel5@@ "\n'
        b"}\n}\n"
    )
    gas_placeholder = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.4.1 {\n"
        b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.4.2\n'
        b"}\n"
        b"sign_template_text : _nameless.4.2 {\n"
        b'\ttext: "123.9"\n'
        b"}\n}\n"
    )
    gas_skanfill = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.5.1 {\n"
        b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.5.2\n'
        b"}\n"
        b"sign_template_text : _nameless.5.2 {\n"
        b'\ttext: "@@000.0@@"\n'
        b"}\n}\n"
    )
    gas_blank = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.6.1 {\n"
        b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.6.2\n'
        b"}\n"
        b"sign_template_text : _nameless.6.2 {\n"
        b'\ttext: " "\n'
        b"}\n}\n"
    )
    fi_oulu_95 = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.7.1 {\n"
        b'\tmodel_name: "poc_5g0ps"\n\titems: 2\n'
        b"\titems[0]: _nameless.7.2\n\titems[1]: _nameless.7.3\n"
        b"}\n"
        b"sign_template_frame : _nameless.7.2 {}\n"
        b'sign_template_text : _nameless.7.3 {\n\ttext: "95"\n}\n'
        b"}\n"
    )
    rs_fuel_01 = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.8.1 {\n"
        b'\tmodel_name: "blkw_14005"\n\titems: 2\n'
        b"\titems[0]: _nameless.8.2\n\titems[1]: _nameless.8.3\n"
        b"}\n"
        b"sign_template_image : _nameless.8.2 {}\n"
        b'sign_template_text : _nameless.8.3 {\n\ttext: "FUEL"\n}\n'
        b"}\n"
    )
    de_kiel_01 = (
        b"SiiNunit\n{\n"
        b"sign_board_template : _nameless.9.1 {\n"
        b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.9.2\n'
        b"}\n"
        b'sign_template_text : _nameless.9.2 {\n\ttext: "Kiel-Zentrum"\n}\n'
        b"}\n"
    )

    _build_hashfs_v2(
        root / "def.scs",
        files={
            "def/country.sii": country_sii,
            "def/country/iceland.sui": iceland_sui,
            "def/country/bosnia.sui": bosnia_sui,
            "def/country/russia.sui": russia_sui,
            "def/country/iceland/speed_limits.sii": sl_iceland,
            "def/country/bosnia/speed_limits.sii": sl_bosnia,
            "def/country/russia/speed_limits.sii": sl_russia,
            "def/sign/board/gas_de_big_95.sii": gas_de_big_95,
            "def/sign/board/es_95_01.sii": es_95_01,
            "def/sign/board/gas_ba_apus_lpg.sii": gas_ba_apus_lpg,
            "def/sign/board/gas_ie_cloveroil_95.sii": gas_placeholder,
            "def/sign/board/gas_is_skanfill_95.sii": gas_skanfill,
            "def/sign/board/gas_empty.sii": gas_blank,
            "def/sign/board/fi_oulu_95.sii": fi_oulu_95,
            "def/sign/board/rs_fuel_01.sii": rs_fuel_01,
            "def/sign/board/de_kiel_01.sii": de_kiel_01,
        },
        dirs={
            "": ["/def"],
            "def": ["country.sii", "/country", "/sign"],
            "def/country": [
                "iceland.sui",
                "bosnia.sui",
                "russia.sui",
                "/iceland",
                "/bosnia",
                "/russia",
            ],
            "def/country/iceland": ["speed_limits.sii"],
            "def/country/bosnia": ["speed_limits.sii"],
            "def/country/russia": ["speed_limits.sii"],
            "def/sign": ["/board"],
            "def/sign/board": [
                "gas_de_big_95.sii",
                "es_95_01.sii",
                "gas_ba_apus_lpg.sii",
                "gas_ie_cloveroil_95.sii",
                "gas_is_skanfill_95.sii",
                "gas_empty.sii",
                "fi_oulu_95.sii",
                "rs_fuel_01.sii",
                "de_kiel_01.sii",
            ],
        },
    )

    # Stripped-root locale.scs (omits "" root, walked via seeded "locale" prefix)
    _build_hashfs_v2(
        root / "locale.scs",
        files={
            "locale/fuel_price_strings.sui": (
                b'key[]: "fp_ba_diesel5"\nval[]: "2.49"\n'
                b'key[]: "fp_de_natural95"\nval[]: "1.85"\n'
                b'key[]: "fp_es_natural95"\nval[]: "1.62"\n'
                b'key[]: "ui_unrelated_fuel_hdr"\nval[]: "Ignore Me"\n'
            ),
            "locale/en_gb/localization.sui": (
                b"SiiNunit\n{\nlocalization_db : .localization\n{\n"
                b'\tkey[]: "lang_name"\n\tval[]: "English (UK)"\n'
                b'\tkey[]: "tz_cest"\n\tval[]: "CEST"\n'
                b'\tkey[]: "tz_gmt"\n\tval[]: "GMT"\n'
                b'\tkey[]: "tz_msk"\n\tval[]: "MSK"\n'
                b'\tkey[]: "moded_game"\n\tval[]: "Modified"\n'
                b"}\n}\n"
            ),
            "locale/de_de/localization.sui": (
                b"SiiNunit\n{\nlocalization_db : .localization\n{\n"
                b'\tkey[]: "lang_name"\n\tval[]: "Deutsch"\n'
                b'\tkey[]: "tz_cest"\n\tval[]: "MESZ"\n'
                b'\tkey[]: "tz_gmt"\n\tval[]: "GMT"\n'
                b'\tkey[]: "tz_msk"\n\tval[]: "MSK"\n'
                b"}\n}\n"
            ),
        },
        dirs={
            "locale": ["fuel_price_strings.sui", "/en_gb", "/de_de"],
            "locale/en_gb": ["localization.sui"],
            "locale/de_de": ["localization.sui"],
        },
    )

    # DLC audits: dlc_north has 1 def/country entry, dlc_east has 0
    _build_hashfs_v2(
        root / "dlc_north.scs",
        files={
            "def/country/iceland/traffic.dlc_north.sii": (
                b"SiiNunit\n{\ncountry_traffic_info : .dlc_north.info {}\n}\n"
            )
        },
        dirs={
            "": ["/def"],
            "def": ["/country"],
            "def/country": ["/iceland"],
            "def/country/iceland": ["traffic.dlc_north.sii"],
        },
    )
    _build_hashfs_v2(
        root / "dlc_east.scs",
        files={"def/cargo/apples.sui": b"cargo_data : cargo.apples {}\n"},
        dirs={"": ["/def"], "def": ["/cargo"], "def/cargo": ["apples.sui"]},
    )
    return root


def test_resolve_game_dir_precedence(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ETS2_GAME_DIR", raising=False)
    assert resolve_game_dir() == DEFAULT_ETS2_GAME_DIR

    env_dir = tmp_path / "env_ets2"
    monkeypatch.setenv("ETS2_GAME_DIR", str(env_dir))
    assert resolve_game_dir() == env_dir

    explicit_dir = tmp_path / "explicit_ets2"
    assert resolve_game_dir(explicit_dir) == explicit_dir


def test_extract_baseline_synthetic_hashfs_v2_filters_and_verifies(
    tmp_path: pathlib.Path,
) -> None:
    install_dir = _create_synthetic_ets2_install(tmp_path / "ets2")
    raw_cache_dir = tmp_path / "build" / "raw_cache"
    out_dir = tmp_path / "out_baseline"

    bundle = extract_baseline(install_dir, raw_cache_dir=raw_cache_dir)
    assert isinstance(bundle, BaselineBundle)
    assert isinstance(bundle.manifest, BaselineManifest)
    assert isinstance(bundle.countries, CountriesBaseline)
    assert isinstance(bundle.speed_limits, SpeedLimitsBaseline)
    assert isinstance(bundle.fuel_boards, FuelBoardsBaseline)
    assert isinstance(bundle.locales, LocalesBaseline)

    m = bundle.manifest
    assert m.game_version == "1.62.3.3"
    assert m.application == "eut2"
    assert m.extractor_schema_version == 1
    assert m.def_entry_count == 16
    assert m.locale_entry_count == 3
    assert m.country_count == 3
    assert m.speed_limit_count == 3
    assert m.total_sign_boards == 9
    assert m.fuel_board_count == 6
    assert m.active_fp_board_count == 3
    assert m.placeholder_or_blank_board_count == 3
    assert m.excluded_fuel_keyword_boards == ["fi_oulu_95", "rs_fuel_01"]
    assert m.locale_count == 2
    assert m.tz_key_count == 3
    assert m.fp_key_count == 3
    assert m.dlc_country_audit == {"dlc_east.scs": 0, "dlc_north.scs": 1}

    by_slug = {c.slug: c for c in bundle.countries.countries}
    assert by_slug["iceland"].mass_limit_per_axle_count == [18000, 29000, 38000, 46000, 60000]
    assert by_slug["iceland"].iso_country_code_quoted is False
    assert by_slug["bosnia"].iso_country_code == "bih"
    assert by_slug["bosnia"].iso_country_code_quoted is True
    assert by_slug["bosnia"].regions == ["rep_srpska"]
    assert len(by_slug["bosnia"].region_areas) == 1
    assert by_slug["russia"].secondary_time_zone == [120]
    assert by_slug["russia"].secondary_time_zone_name == ["@@tz_eest@@"]

    sl_by_slug = {s.slug: s for s in bundle.speed_limits.speed_limits}
    assert sl_by_slug["russia"].has_train is True
    assert sl_by_slug["russia"].has_tram is True
    assert sl_by_slug["bosnia"].has_train is False
    bos_car = next(b for b in sl_by_slug["bosnia"].blocks if b.vehicle_speed_class == "car")
    assert bos_car.lanes[1].uncommon is True

    board_map = {b.board_name: b for b in bundle.fuel_boards.boards}
    assert set(board_map) == {
        "es_95_01",
        "gas_ba_apus_lpg",
        "gas_de_big_95",
        "gas_empty",
        "gas_ie_cloveroil_95",
        "gas_is_skanfill_95",
    }
    assert "fi_oulu_95" not in board_map
    assert "rs_fuel_01" not in board_map
    assert "de_kiel_01" not in board_map

    de_board = board_map["gas_de_big_95"]
    assert de_board.model_name == ""
    assert de_board.items_count == 1
    assert de_board.classification == "active_fp"
    assert de_board.fp_key == "fp_de_natural95"
    assert de_board.slot.coords_l == pytest.approx(-80.0)
    assert de_board.slot.font_face == "/font/sign/gas_segment_7.font"
    assert de_board.slot.h_align == "center"
    assert de_board.slot.v_align == "center"

    ba_board = board_map["gas_ba_apus_lpg"]
    assert ba_board.classification == "active_fp"
    assert ba_board.fp_key == "fp_ba_diesel5"
    assert ba_board.slot.text == "@@fp_ba_diesel5@@ "

    assert board_map["gas_is_skanfill_95"].classification == "placeholder"
    assert board_map["gas_is_skanfill_95"].fp_key is None
    assert board_map["gas_empty"].classification == "blank"

    assert bundle.locales.active_locales == ["de_de", "en_gb"]
    assert bundle.locales.tz_keys == ["tz_cest", "tz_gmt", "tz_msk"]
    assert bundle.locales.fp_keys == ["fp_ba_diesel5", "fp_de_natural95", "fp_es_natural95"]

    # Raw cache written outside out_dir
    assert (raw_cache_dir / "def" / "country" / "iceland.sui").is_file()
    assert (raw_cache_dir / "locale" / "fuel_price_strings.sui").is_file()

    # Write deterministic JSONs and verify 0-diff + SHA-256 + UTF-8 no-BOM LF
    written = write_baseline_bundle(bundle, out_dir)
    assert set(written) == {
        "manifest.json",
        "countries.json",
        "speed_limits.json",
        "fuel_boards.json",
        "locales.json",
    }
    assert list(out_dir.rglob("*.sui")) == []
    assert list(out_dir.rglob("*.sii")) == []

    for fname, fpath in written.items():
        raw_bytes = fpath.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf")
        assert b"\r\n" not in raw_bytes
        if fname != "manifest.json":
            assert hashlib.sha256(raw_bytes).hexdigest() == m.file_sha256s[fname]

    manifest_raw = json.loads((out_dir / "manifest.json").read_text("utf-8"))
    assert "timestamp" not in manifest_raw
    assert verify_baseline_bundle(bundle, out_dir) == []

    # Tampering triggers verification failure
    countries_path = out_dir / "countries.json"
    countries_path.write_bytes(countries_path.read_bytes() + b" ")
    assert verify_baseline_bundle(bundle, out_dir) != []


def test_cli_vfs_inspect_and_baseline_extract_commands(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_dir = _create_synthetic_ets2_install(tmp_path / "ets2")
    out_dir = tmp_path / "json_out"
    raw_cache_dir = tmp_path / "raw_cache"

    # 1. vfs inspect
    code = main(
        [
            "vfs",
            "inspect",
            str(install_dir / "def.scs"),
            "--prefix",
            "def/country",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "def/country/iceland.sui" in out

    # Missing archive returns non-zero
    assert main(["vfs", "inspect", str(tmp_path / "missing.scs")]) != 0
    capsys.readouterr()

    # vfs inspect --json & subcommand help invocations
    assert main(["vfs", "inspect", str(install_dir / "version.scs"), "--json"]) == 0
    inspect_json = json.loads(capsys.readouterr().out)
    assert inspect_json["entry_count"] == 1
    assert inspect_json["sample_paths"] == ["version.sii"]
    assert main(["vfs"]) == 0
    assert main(["baseline"]) == 0
    capsys.readouterr()

    # Overlapping --raw-cache-dir and --out-dir rejected cleanly
    assert (
        main(
            [
                "baseline",
                "extract",
                "--game-dir",
                str(install_dir),
                "--out-dir",
                str(out_dir),
                "--raw-cache-dir",
                str(out_dir / "raw"),
            ]
        )
        != 0
    )
    capsys.readouterr()

    # 2. baseline extract
    code = main(
        [
            "baseline",
            "extract",
            "--game-dir",
            str(install_dir),
            "--out-dir",
            str(out_dir),
            "--raw-cache-dir",
            str(raw_cache_dir),
        ]
    )
    assert code == 0
    extract_out = capsys.readouterr().out
    assert "1.62.3.3" in extract_out
    assert (out_dir / "manifest.json").is_file()
    assert (raw_cache_dir / "def" / "country.sii").is_file()
    assert list(out_dir.rglob("*.sui")) == []

    # 3. baseline extract --check (0 diff)
    assert (
        main(
            [
                "baseline",
                "extract",
                "--game-dir",
                str(install_dir),
                "--out-dir",
                str(out_dir),
                "--check",
            ]
        )
        == 0
    )
    capsys.readouterr()

    # 4. --check detects drift
    (out_dir / "locales.json").write_bytes(b"{}\n")
    assert (
        main(
            [
                "baseline",
                "extract",
                "--game-dir",
                str(install_dir),
                "--out-dir",
                str(out_dir),
                "--check",
            ]
        )
        != 0
    )
    capsys.readouterr()

    # 5. Missing game dir fails non-zero
    assert (
        main(
            [
                "baseline",
                "extract",
                "--game-dir",
                str(tmp_path / "no_ets2"),
                "--out-dir",
                str(out_dir),
            ]
        )
        != 0
    )


def test_cli_baseline_extract_handles_protected_and_unsupported_archives(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    protected_dir = _create_synthetic_ets2_install(tmp_path / "protected_ets2")
    (protected_dir / "version.scs").write_bytes(b"AEM!\x00\x00\x00\x00")
    out_dir = tmp_path / "out_protected"
    assert (
        main(
            [
                "baseline",
                "extract",
                "--game-dir",
                str(protected_dir),
                "--out-dir",
                str(out_dir),
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "baseline extraction failed" in err

    unsupported_dir = _create_synthetic_ets2_install(tmp_path / "unsupported_ets2")
    with zipfile.ZipFile(
        unsupported_dir / "version.scs",
        "w",
        compression=zipfile.ZIP_BZIP2,
    ) as zf:
        zf.writestr("version.sii", "SiiNunit\n{\n}\n")
    assert (
        main(
            [
                "baseline",
                "extract",
                "--game-dir",
                str(unsupported_dir),
                "--out-dir",
                str(tmp_path / "out_unsupported"),
            ]
        )
        == 1
    )
    err_zip = capsys.readouterr().err
    assert "baseline extraction failed" in err_zip


def test_raw_cache_dir_guard_cwd_independent_and_base_mount_boards_and_dlc_audit(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_dir = _create_synthetic_ets2_install(tmp_path / "ets2")

    # Add a DLC with def/country.<short_stem>.sii (without 'dlc_' prefix) under def/
    _build_hashfs_v2(
        install_dir / "dlc_balkan_e.scs",
        files={
            "def/country.balkan_e.sii": b'SiiNunit\n{\n@include "country/romania.sui"\n}\n',
        },
        dirs={"": ["/def"], "def": ["country.balkan_e.sii"]},
    )

    # Change CWD to tmp_path (no local ./data dir) and verify repo data/ guard still blocks writes
    repo_data_cache = (
        pathlib.Path(__file__).resolve().parent.parent / "data" / "forbidden_raw_cache"
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="raw_cache_dir"):
        extract_baseline(install_dir, raw_cache_dir=repo_data_cache)

    # Verify base/-mounted sign board path works via def_stack and dlc_balkan_e audit == 1
    base_board_dir = tmp_path / "ets2_base_mount"
    _create_synthetic_ets2_install(base_board_dir)
    _build_hashfs_v2(
        base_board_dir / "def.scs",
        files={
            "def/country.sii": b'SiiNunit\n{\n@include "country/iceland.sui"\n}\n',
            "def/country/iceland.sui": (
                b"country_data : country.data.iceland\n{\n"
                b'\tcountry_id: 26\n\tname: "Iceland"\n\tiso_country_code: isl\n'
                b"}\n"
            ),
            "def/country/iceland/speed_limits.sii": (
                b"SiiNunit\n{\ncountry_speed_limit : .speed_limit.car {\n"
                b"\tvehicle_speed_class: car\n\tlane_speed_class[]: local_road\n\tlimit[]: 90\n"
                b"}\n}\n"
            ),
            "base/def/sign/board/gas_is_base_95.sii": (
                b"SiiNunit\n{\n"
                b"sign_board_template : _nameless.1.1 {\n"
                b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.1.2\n'
                b"}\n"
                b"sign_template_text : _nameless.1.2 {\n"
                b'\ttext: "@@fp_is_95@@"\n'
                b"}\n}\n"
            ),
        },
        dirs={
            "": ["/def", "/base"],
            "def": ["country.sii", "/country"],
            "def/country": ["iceland.sui", "/iceland"],
            "def/country/iceland": ["speed_limits.sii"],
            "base": ["/def"],
            "base/def": ["/sign"],
            "base/def/sign": ["/board"],
            "base/def/sign/board": ["gas_is_base_95.sii"],
        },
    )
    bundle_base = extract_baseline(base_board_dir)
    assert [b.board_name for b in bundle_base.fuel_boards.boards] == ["gas_is_base_95"]

    bundle_dlc = extract_baseline(install_dir)
    assert bundle_dlc.manifest.dlc_country_audit["dlc_balkan_e.scs"] == 1
