"""Unit tests for opt-in --patch-hardcoded-totems (JRR/7RM numeric boards, D-16)."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from ets2_realism.baseline.models import FuelBoardsBaseline
from ets2_realism.merge.hardcoded_totems import (
    JRR_NUMERIC_BOARD_SIGNATURES,
    HardcodedTotemResult,
    patch_hardcoded_numeric_totems,
)
from ets2_realism.registry.models import LaneSpeedOverride
from ets2_realism.registry.snapshot import (
    RealismSnapshot,
    RealismSnapshotCountry,
    RealismSnapshotFuel,
    load_or_build_snapshot,
)
from ets2_realism.sii.hygiene import validate_sii_hygiene
from ets2_realism.sii.sign_board import parse_sign_board
from ets2_realism.vfs.hashfs import open_archive
from ets2_realism.vfs.stack import VfsStack

_BASELINE_DIR = Path("data/baselines/ets2_1.62_def")


def _single_text_board_sii(
    board_name: str,
    text: str,
    *,
    font_face: str = "/font/sign/dot_matrix.font",
    model_name: str = "",
) -> bytes:
    content = (
        "SiiNunit\n"
        "{\n"
        f"sign_board_template : _nameless.100.{board_name[:8]}\n"
        "{\n"
        f'\tboard_name: "{board_name}"\n'
        "\twidth: 1.5\n"
        "\theight: 0.6\n"
        f'\tmodel_name: "{model_name}"\n'
        "\titems: 1\n"
        "\titems[0]: _nameless.200.slot0\n"
        "\tdynamic_attributes: 0\n"
        "}\n"
        "\n"
        "sign_template_text : _nameless.200.slot0\n"
        "{\n"
        f'\tfont_face: "{font_face}"\n'
        "\tfont_size: 0.35\n"
        '\ttext_halign: "center"\n'
        '\ttext_valign: "center"\n'
        f'\ttext: "{text}"\n'
        "}\n"
        "}\n"
    )
    return content.encode("utf-8")


def _multi_item_highway_board_sii(board_name: str) -> bytes:
    content = (
        "SiiNunit\n"
        "{\n"
        f"sign_board_template : _nameless.300.{board_name[:8]}\n"
        "{\n"
        f'\tboard_name: "{board_name}"\n'
        "\twidth: 4.5\n"
        "\theight: 2.0\n"
        '\tmodel_name: "/model/sign/hw_exit.pmd"\n'
        "\titems: 15\n"
        "\titems[0]: _nameless.301.slot0\n"
        "}\n"
        "\n"
        "sign_template_text : _nameless.301.slot0\n"
        "{\n"
        '\tfont_face: "/font/sign/dot_matrix.font"\n'
        '\ttext: "500"\n'
        "}\n"
        "}\n"
    )
    return content.encode("utf-8")


def _make_snapshot_with_id() -> RealismSnapshot:
    base = load_or_build_snapshot("summer")
    id_country = RealismSnapshotCountry(
        iso2="ID",
        iso3="idn",
        ets2_slug="indonesia",
        iana_timezone="Asia/Jakarta",
        time_zone=420,
        time_zone_name="WIB",
        observes_dst=False,
        lights_mandatory=False,
        driving_tired_offence=True,
        imperial_units=False,
        mass_limit_per_axle_count=[18000, 26000, 36000, 40000],
        speed_limits={
            "car": [LaneSpeedOverride(lane_speed_class="local_road", limit=80, urban_limit=50)],
            "truck": [LaneSpeedOverride(lane_speed_class="local_road", limit=60, urban_limit=40)],
            "bus": [LaneSpeedOverride(lane_speed_class="local_road", limit=70, urban_limit=40)],
        },
        fuel=RealismSnapshotFuel(
            currency="IDR",
            eur_per_liter=0.75,
            local_prices={
                "diesel": 6800.0,
                "petrol_92": 13300.0,
                "petrol_95": 10000.0,
                "petrol_98": 15100.0,
            },
            source="test_id_snapshot",
        ),
    )
    merged_countries = dict(base.countries)
    merged_countries["ID"] = id_country
    return base.model_copy(update={"countries": merged_countries})


def test_jrr_numeric_boards_rewrite_when_id_in_snapshot_and_skip_when_absent(
    tmp_path: Path,
) -> None:
    assert len(JRR_NUMERIC_BOARD_SIGNATURES) == 8
    bl_boards = FuelBoardsBaseline.model_validate_json(
        (_BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )

    mod_zip = tmp_path / "JRR_Assets.scs"
    jrr_numeric_prices = {
        "indo_gas_totem_01a": "15100",
        "indo_gas_totem_01p": "15100",
        "indo_gas_totem_01l": "13300",
        "indo_gas_totem_01m": "13300",
        "indo_gas_totem_01n": "10000",
        "indo_gas_totem_01q": "10000",
        "indo_gas_totem_01o": "6800",
        "indo_gas_totem_01r": "6800",
    }
    with ZipFile(mod_zip, "w") as zf:
        for name, txt in jrr_numeric_prices.items():
            zf.writestr(f"def/sign/board/{name}.sii", _single_text_board_sii(name, txt))

    # 1. With ID present in snapshot -> all 8 boards surgically rewritten with 4 tokens
    snap_with_id = _make_snapshot_with_id()
    stack = VfsStack()
    try:
        stack.mount(open_archive(mod_zip), name="jrr", priority=10)
        res: HardcodedTotemResult = patch_hardcoded_numeric_totems(stack, snap_with_id, bl_boards)
    finally:
        stack.close()

    assert len(res.board_files) == 8
    assert res.extra_locale_tokens == {
        "fp_id_diesel_ets2r": "6800",
        "fp_id_petrol_92_ets2r": "13300",
        "fp_id_petrol_95_ets2r": "10000",
        "fp_id_petrol_98_ets2r": "15100",
    }
    for name, (_, grade) in JRR_NUMERIC_BOARD_SIGNATURES.items():
        path = f"def/sign/board/{name}.sii"
        assert path in res.board_files
        raw = res.board_files[path]
        assert validate_sii_hygiene(raw, require_siinunit=True) == []
        parsed = parse_sign_board(raw)
        assert parsed.text_slots[0].font_face == "/font/sign/dot_matrix.font"
        assert parsed.text_slots[0].localization_key == f"fp_id_{grade}_ets2r"

    # 2. Against Phase 5 225-territory snapshot (where ID is now canonical!) -> all 8 patched
    snap_global = load_or_build_snapshot("summer")
    assert len(snap_global.countries) == 225
    assert "ID" in snap_global.countries
    stack2 = VfsStack()
    try:
        stack2.mount(open_archive(mod_zip), name="jrr", priority=10)
        res_global = patch_hardcoded_numeric_totems(stack2, snap_global, bl_boards)
    finally:
        stack2.close()

    assert len(res_global.board_files) == 8
    assert len(res_global.actions) == 8
    assert all(a.status == "patched" for a in res_global.actions)

    # 3. Against synthetic snapshot lacking ID -> all 8 skipped_not_in_snapshot preserved
    snap_without_id = snap_global.model_copy(
        update={"countries": {iso2: c for iso2, c in snap_global.countries.items() if iso2 != "ID"}}
    )
    assert "ID" not in snap_without_id.countries
    stack3 = VfsStack()
    try:
        stack3.mount(open_archive(mod_zip), name="jrr", priority=10)
        res_absent = patch_hardcoded_numeric_totems(stack3, snap_without_id, bl_boards)
    finally:
        stack3.close()

    assert res_absent.board_files == {}
    assert res_absent.extra_locale_tokens == {}
    assert len(res_absent.actions) == 8
    assert all(a.status == "skipped_not_in_snapshot" for a in res_absent.actions)


def test_jrr_excluded_labels_station_ids_and_multi_item_signs_remain_untouched(
    tmp_path: Path,
) -> None:
    bl_boards = FuelBoardsBaseline.model_validate_json(
        (_BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    snap_with_id = _make_snapshot_with_id()

    mod_zip = tmp_path / "JRR_Excluded.scs"
    label_boards = {
        "indo_gas_totem_01b": "PERTAMAX 92",
        "indo_gas_totem_01c": "PERTAMAX TURBO",
        "indo_gas_totem_01d": "PERTALITE",
        "indo_gas_totem_01e": "BIO SOLAR",
        "indo_gas_totem_01f": "DEXLITE",
        "indo_gas_totem_01g": "PERTAMINA DEX",
        "indo_gas_totem_01h": "PREMIUM",
        "indo_gas_totem_01i": "GAS",
        "indo_gas_totem_01j": "34.138.06",
        "indo_gas_totem_01k": "34.138.07",
    }
    with ZipFile(mod_zip, "w") as zf:
        for name, txt in label_boards.items():
            zf.writestr(f"def/sign/board/{name}.sii", _single_text_board_sii(name, txt))
        zf.writestr(
            "def/sign/board/indo_hw_gas_exit_01.sii",
            _multi_item_highway_board_sii("indo_hw_gas_exit_01"),
        )

    stack = VfsStack()
    try:
        stack.mount(open_archive(mod_zip), name="jrr_excl", priority=10)
        res = patch_hardcoded_numeric_totems(stack, snap_with_id, bl_boards)
    finally:
        stack.close()

    assert res.board_files == {}
    assert res.extra_locale_tokens == {}
    by_name = {a.board_name: a.status for a in res.actions}
    for name in label_boards:
        assert by_name[name] == "skipped_non_numeric"
    assert by_name["indo_hw_gas_exit_01"] == "skipped_multi_item"


def test_7rm_numeric_boards_and_ambiguous_or_localized_boards(tmp_path: Path) -> None:
    bl_boards = FuelBoardsBaseline.model_validate_json(
        (_BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    snap_phase4 = load_or_build_snapshot("summer")

    mod_zip = tmp_path / "7RM_Signs.scs"
    with ZipFile(mod_zip, "w") as zf:
        zf.writestr(
            "def/sign/board/kz_gas_totem_95.sii",
            _single_text_board_sii("kz_gas_totem_95", "205"),
        )
        zf.writestr(
            "def/sign/board/uz_gas_diesel.sii",
            _single_text_board_sii("uz_gas_diesel", "11500"),
        )
        zf.writestr(
            "def/sign/board/ru_gas_already_loc_95.sii",
            _single_text_board_sii("ru_gas_already_loc_95", "@@fp_ru_natural95@@"),
        )
        zf.writestr(
            "def/sign/board/unknown_sign_99.sii",
            _single_text_board_sii("unknown_sign_99", "100"),
        )

    stack = VfsStack()
    try:
        stack.mount(open_archive(mod_zip), name="7rm", priority=10)
        res = patch_hardcoded_numeric_totems(stack, snap_phase4, bl_boards)
    finally:
        stack.close()

    assert set(res.board_files) == {
        "def/sign/board/kz_gas_totem_95.sii",
        "def/sign/board/uz_gas_diesel.sii",
    }
    assert set(res.extra_locale_tokens) == {
        "fp_kz_petrol_95_ets2r",
        "fp_uz_diesel_ets2r",
    }
    # Native integer KZT & UZS strings (no decimals)
    assert res.extra_locale_tokens["fp_kz_petrol_95_ets2r"].isdigit()
    assert res.extra_locale_tokens["fp_uz_diesel_ets2r"].isdigit()

    kz_parsed = parse_sign_board(res.board_files["def/sign/board/kz_gas_totem_95.sii"])
    assert kz_parsed.text_slots[0].localization_key == "fp_kz_petrol_95_ets2r"
    assert kz_parsed.text_slots[0].font_face == "/font/sign/dot_matrix.font"

    uz_parsed = parse_sign_board(res.board_files["def/sign/board/uz_gas_diesel.sii"])
    assert uz_parsed.text_slots[0].localization_key == "fp_uz_diesel_ets2r"

    by_name = {a.board_name: a.status for a in res.actions}
    assert by_name["kz_gas_totem_95"] == "patched"
    assert by_name["uz_gas_diesel"] == "patched"
    assert by_name["ru_gas_already_loc_95"] == "skipped_already_localized"
    assert by_name["unknown_sign_99"] == "skipped_ambiguous"


def test_md02_hardcoded_totems_isolate_hygiene_3nk_and_read_errors(tmp_path: Path) -> None:
    """MD-02 regression: >12-char unit segment, 3nK, and read ValueError/OSError skip cleanly."""
    bl_boards = FuelBoardsBaseline.model_validate_json(
        (_BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    snap_phase4 = load_or_build_snapshot("summer")

    long_unit_board = (
        b"SiiNunit\n{\n"
        b"sign_board_template : sign_templ.kz_gas_diesel_long\n{\n"
        b'\tboard_name: "kz_gas_diesel"\n'
        b"\twidth: 1.5\n\theight: 0.6\n"
        b'\tmodel_name: ""\n'
        b"\titems: 1\n\titems[0]: _nameless.200.slot0\n"
        b"}\n"
        b"sign_template_text : _nameless.200.slot0\n{\n"
        b'\tfont_face: "/font/sign/dot_matrix.font"\n'
        b'\ttext: "205"\n'
        b"}\n}\n"
    )

    mod_zip = tmp_path / "malformed_boards.scs"
    with ZipFile(mod_zip, "w") as zf:
        zf.writestr("def/sign/board/kz_gas_diesel.sii", long_unit_board)
        zf.writestr("def/sign/board/uz_gas_95.sii", b"3nK\x01\x00\x01obfuscated_board")
        zf.writestr("def/sign/board/kz_gas_95.sii", _single_text_board_sii("kz_gas_95", "205"))

    stack = VfsStack()
    try:
        stack.mount(open_archive(mod_zip), name="malformed", priority=10)
        res = patch_hardcoded_numeric_totems(stack, snap_phase4, bl_boards)
    finally:
        stack.close()

    by_name = {a.board_name: a for a in res.actions}
    assert by_name["kz_gas_diesel"].status == "skipped_unreadable"
    assert "hygiene" in (by_name["kz_gas_diesel"].detail or "").lower()
    assert by_name["uz_gas_95"].status == "skipped_unreadable"
    assert "3nK" in (by_name["uz_gas_95"].detail or "")
    assert by_name["kz_gas_95"].status == "patched"
    assert list(res.board_files) == ["def/sign/board/kz_gas_95.sii"]
