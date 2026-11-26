"""Tests for 460-board totem classification and Option 4b Zero-DDS 43-locale SII compilation."""

from __future__ import annotations

import pathlib
import re

import pytest

from ets2_realism.baseline.models import (
    FuelBoardEntry,
    FuelBoardsBaseline,
    FuelBoardSlot,
    LocalesBaseline,
)
from ets2_realism.normalize.lockfile import load_prices_lockfile
from ets2_realism.normalize.models import CountryFuelLockEntry
from ets2_realism.normalize.totem_catalog import (
    GRADE_SUFFIX_TO_CANONICAL,
    NON_GAS_LEGACY_BOARDS,
    REGION_ALIAS_TO_ISO2,
    STRUCTURAL_SPACER_BOARDS,
    TotemBoardClassification,
    classify_all_fuel_boards,
    classify_fuel_board,
)
from ets2_realism.package.totems import (
    FUEL_LOCALE_FILENAME,
    FUEL_LOCALE_UNIT_NAME,
    CompiledTotems,
    compile_totem_payloads,
    synthesize_fuel_locale_module_sii,
    synthesize_sign_board_sii,
)
from ets2_realism.sii.document import SiiDocument
from ets2_realism.sii.hygiene import validate_sii_hygiene
from ets2_realism.sii.localization import parse_localization_db
from ets2_realism.sii.sign_board import parse_sign_board

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
PRICES_LOCK_PATH = REPO_ROOT / "state" / "prices.lock.json"

_TOKEN_KEY_RE = re.compile(r"^fp_[a-z]{2}_[a-z0-9_]+_ets2r$")
_EXCLUDED_HIGHWAY_SIGNS = ("fi_oulu_95", "fi_oulu_98", "rs_fuel_01", "ru_m_95", "ru_m_98")


def _load_committed_inputs() -> tuple[FuelBoardsBaseline, LocalesBaseline]:
    fuel_boards = FuelBoardsBaseline.model_validate_json(
        (BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )
    locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    return fuel_boards, locales


def test_classify_all_461_committed_fuel_boards_and_d09_fixes() -> None:
    fuel_boards, _ = _load_committed_inputs()
    assert len(fuel_boards.boards) == 461
    assert set(STRUCTURAL_SPACER_BOARDS) == {"gas_empty"}
    assert set(NON_GAS_LEGACY_BOARDS) == {"es_95_01", "es_diesel_01", "pt_95_01", "pt_diesel_01"}
    assert REGION_ALIAS_TO_ISO2["bi"] == "GB"
    assert REGION_ALIAS_TO_ISO2["dortmund"] == "DE"
    assert GRADE_SUFFIX_TO_CANONICAL["superd"] == "diesel_plus"
    assert GRADE_SUFFIX_TO_CANONICAL["unleaded"] == "petrol_95"

    classified = classify_all_fuel_boards(fuel_boards)
    assert len(classified) == 460
    assert [c.board_name for c in classified] == sorted(c.board_name for c in classified)

    by_name = {c.board_name: c for c in classified}
    assert "gas_empty" not in by_name
    for highway_sign in _EXCLUDED_HIGHWAY_SIGNS:
        assert highway_sign not in by_name

    # Exact 37 countries: 36 Vanilla+DLC + IE (CY and MT have 0 vanilla boards)
    countries = {c.iso2 for c in classified}
    assert len(countries) == 37
    assert "IE" in countries
    assert "GB" in countries
    assert "CY" not in countries
    assert "MT" not in countries

    # Breakdown: 373 active_fp + 47 placeholder + 40 active blank = 460
    assert sum(1 for c in classified if c.classification == "active_fp") == 373
    assert sum(1 for c in classified if c.classification == "placeholder") == 47
    assert sum(1 for c in classified if c.classification == "blank") == 40

    # Explicit D-09 spot checks across all missing/swapped/blank/placeholder groups
    expected_pairs: dict[str, tuple[str, str]] = {
        "gas_bi_beldon_95": ("GB", "petrol_95"),
        "gas_bi_beldon_diesel": ("GB", "diesel"),
        "gas_bi_beldon_super": ("GB", "petrol_98"),
        "gas_bi_beldon_superd": ("GB", "diesel_plus"),
        "gas_bi_pegi_98": ("GB", "petrol_98"),
        "gas_bi_primel_100": ("GB", "petrol_100"),
        "gas_bi_sheltie_super": ("GB", "petrol_98"),
        "gas_bi_victory_superd": ("GB", "diesel_plus"),
        "gas_ie_cloveroil_95": ("IE", "petrol_95"),
        "gas_ie_cloveroil_diesel": ("IE", "diesel"),
        "gas_ie_cloveroil_super": ("IE", "petrol_98"),
        "gas_ie_cloveroil_superd": ("IE", "diesel_plus"),
        "gas_ie_opetrol_95": ("IE", "petrol_95"),
        "gas_ie_opetrol_diesel": ("IE", "diesel"),
        "gas_ie_opetrol_super": ("IE", "petrol_98"),
        "gas_ie_opetrol_superd": ("IE", "diesel_plus"),
        "gas_ie_pegi_95": ("IE", "petrol_95"),
        "gas_ie_pegi_diesel": ("IE", "diesel"),
        "gas_ie_pegi_98": ("IE", "petrol_98"),
        "gas_ie_pegi_100": ("IE", "petrol_100"),
        "gas_ie_primel_95": ("IE", "petrol_95"),
        "gas_ie_primel_diesel": ("IE", "diesel"),
        "gas_ie_primel_98": ("IE", "petrol_98"),
        "gas_ie_primel_100": ("IE", "petrol_100"),
        "gas_ba_apus_lpg": ("BA", "lpg"),
        "gas_ba_bts_lpg": ("BA", "lpg"),
        "gas_dk_92": ("DK", "petrol_92"),
        "gas_is_ip1_98": ("IS", "petrol_98"),
        "gas_is_yokull_95": ("IS", "petrol_95"),
        "gas_is_yokull_diesel": ("IS", "diesel"),
        "gas_hr_gryf_98": ("HR", "petrol_98"),
        "gas_lu_bnlx_98": ("LU", "petrol_98"),
        "gas_hr_bts_98": ("HR", "petrol_98"),
        "gas_nl_gryf_98": ("NL", "petrol_98"),
        "gas_dortmund_98": ("DE", "petrol_98"),
        "gas_dortmund_lpg": ("DE", "lpg"),
        "gas_al_apus_98": ("AL", "petrol_98"),
        "gas_al_apus_lpg": ("AL", "lpg"),
        "gas_no_tgq_98": ("NO", "petrol_98"),
        "gas_no_tqg_85": ("NO", "e85"),
        "es_95_01": ("ES", "petrol_95"),
        "es_diesel_01": ("ES", "diesel"),
        "pt_95_01": ("PT", "petrol_95"),
        "pt_diesel_01": ("PT", "diesel"),
    }
    for board_name, (exp_iso2, exp_grade) in expected_pairs.items():
        item = by_name[board_name]
        assert (item.iso2, item.grade) == (exp_iso2, exp_grade), board_name
        assert item.token_base == f"fp_{exp_iso2.lower()}_{exp_grade}"


def test_classify_fuel_board_rejects_unknown_boards_and_corrupt_spacer() -> None:
    fuel_boards, _ = _load_committed_inputs()
    gas_empty = next(b for b in fuel_boards.boards if b.board_name == "gas_empty")
    assert classify_fuel_board(gas_empty) is None

    # gas_empty with non-zero font_size/opacity must fail loudly (T-03-14)
    corrupt_empty = gas_empty.model_copy(
        update={"slot": gas_empty.slot.model_copy(update={"font_size": 0.35, "font_opacity": 1.0})}
    )
    with pytest.raises(ValueError, match="gas_empty"):
        classify_fuel_board(corrupt_empty)

    # Unknown board name must fail loudly
    unknown = gas_empty.model_copy(
        update={
            "board_name": "gas_zz_mystery_plasma",
            "slot": gas_empty.slot.model_copy(update={"font_size": 0.35, "font_opacity": 1.0}),
        }
    )
    with pytest.raises(ValueError, match="gas_zz_mystery_plasma"):
        classify_fuel_board(unknown)

    # Excluded multi-item highway sign injected into boards must fail loudly
    injected_highway = FuelBoardsBaseline(
        total_sign_boards=1,
        excluded_fuel_keyword_boards=["fi_oulu_95"],
        boards=[
            FuelBoardEntry(
                board_name="fi_oulu_95",
                vfs_path="def/sign/board/fi_oulu_95.sii",
                unit_name="_nameless.1",
                model_name="",
                items_count=1,
                classification="placeholder",
                slot=FuelBoardSlot(slot_index=0, unit_name="_nameless.2"),
            )
        ],
    )
    with pytest.raises(ValueError, match="fi_oulu_95"):
        classify_all_fuel_boards(injected_highway)


def test_compile_totem_payloads_round_trips_all_460_boards_and_43_locales() -> None:
    fuel_boards, locales = _load_committed_inputs()
    prices_lock = load_prices_lockfile(PRICES_LOCK_PATH)

    compiled = compile_totem_payloads(fuel_boards, locales, prices_lock)
    assert isinstance(compiled, CompiledTotems)
    assert compiled.skipped_boards == ["gas_empty"]
    assert len(compiled.board_files) == 460
    assert len(compiled.board_tokens) == 460
    assert len(compiled.locale_files) == 43
    assert "def/sign/board/gas_empty.sii" not in compiled.board_files
    for highway_sign in _EXCLUDED_HIGHWAY_SIGNS:
        assert f"def/sign/board/{highway_sign}.sii" not in compiled.board_files

    # Zero .dds or .tobj anywhere
    all_paths = list(compiled.board_files) + list(compiled.locale_files)
    assert not any(p.lower().endswith((".dds", ".tobj")) for p in all_paths)

    # Exact 43 active locales: fr_ca present, fr_qc absent, all byte-identical
    expected_locale_paths = {
        f"locale/{lang}/{FUEL_LOCALE_FILENAME}" for lang in locales.active_locales
    }
    assert set(compiled.locale_files) == expected_locale_paths
    assert f"locale/fr_ca/{FUEL_LOCALE_FILENAME}" in compiled.locale_files
    assert f"locale/fr_qc/{FUEL_LOCALE_FILENAME}" not in compiled.locale_files

    unique_locale_payloads = set(compiled.locale_files.values())
    assert len(unique_locale_payloads) == 1
    canonical_locale_raw = next(iter(unique_locale_payloads))
    assert validate_sii_hygiene(canonical_locale_raw, require_siinunit=True) == []

    locale_doc = SiiDocument.parse(canonical_locale_raw, require_siinunit=True)
    loc_unit = locale_doc.get_unit(class_name="localization_db")
    assert loc_unit is not None
    assert loc_unit.unit_name == FUEL_LOCALE_UNIT_NAME == ".ets2r_fuel"

    parsed_entries = parse_localization_db(canonical_locale_raw)
    parsed_keys = [entry.key for entry in parsed_entries]
    assert parsed_keys == sorted(parsed_keys)
    assert len(parsed_keys) == len(set(parsed_keys))
    parsed_token_map = {entry.key: entry.val for entry in parsed_entries}
    assert parsed_token_map == compiled.token_values
    assert len(parsed_token_map) == 164
    assert "<sup>" in parsed_token_map["fp_de_diesel_ets2r"]
    assert "<sup>" not in parsed_token_map["fp_de_diesel_3_ets2r"]
    assert "<sup>" not in parsed_token_map["fp_de_diesel_c_ets2r"]
    assert float(parsed_token_map["fp_gb_diesel_ets2r"]) > 50.0  # UK pence/L
    assert parsed_token_map["fp_is_diesel_ets2r"].isdigit()  # Integer ISK

    for key, val in parsed_token_map.items():
        assert _TOKEN_KEY_RE.fullmatch(key) is not None, key
        assert val != ""
        assert "," not in val  # D-11 uniform dot decimal separator

    # Round-trip ALL 460 synthesized def/sign/board/*.sii files verbatim
    boards_by_name = {b.board_name: b for b in fuel_boards.boards}
    referenced_tokens: set[str] = set()
    for rel_path, raw_bytes in compiled.board_files.items():
        assert validate_sii_hygiene(raw_bytes, require_siinunit=True) == [], rel_path
        parsed = parse_sign_board(raw_bytes)
        board_name = pathlib.Path(rel_path).stem
        baseline = boards_by_name[board_name]
        expected_token = compiled.board_tokens[board_name]
        referenced_tokens.add(expected_token)

        assert parsed.unit_name == baseline.unit_name
        assert parsed.board_name == baseline.template_board_name
        assert parsed.width == pytest.approx(baseline.width, rel=1e-6, abs=1e-7)
        assert parsed.height == pytest.approx(baseline.height, rel=1e-6, abs=1e-7)
        assert parsed.model_name == ""
        assert parsed.items_count == 1
        assert parsed.dynamic_attributes == baseline.dynamic_attributes
        assert parsed.is_single_text_fuel_candidate is True

        slot = parsed.text_slots[0]
        base_slot = baseline.slot
        assert slot.unit_name == base_slot.unit_name
        assert slot.text == f"@@{expected_token}@@"
        assert slot.localization_key == expected_token
        assert slot.font_face == base_slot.font_face
        assert slot.font_size == pytest.approx(base_slot.font_size, rel=1e-6, abs=1e-7)
        assert slot.text_halign == base_slot.text_halign
        assert slot.text_valign == base_slot.text_valign
        assert slot.font_color == base_slot.font_color
        assert slot.font_opacity == pytest.approx(base_slot.font_opacity, rel=1e-6, abs=1e-7)
        assert slot.line_spacing == pytest.approx(base_slot.line_spacing, rel=1e-6, abs=1e-7)
        assert slot.letter_spacing == pytest.approx(base_slot.letter_spacing, rel=1e-6, abs=1e-7)
        assert slot.text_id == base_slot.text_id
        assert slot.area_name == base_slot.area_name
        assert slot.area_idx == base_slot.area_idx
        assert slot.coords_l == pytest.approx(base_slot.coords_l, rel=1e-6, abs=1e-7)
        assert slot.coords_r == pytest.approx(base_slot.coords_r, rel=1e-6, abs=1e-7)
        assert slot.coords_t == pytest.approx(base_slot.coords_t, rel=1e-6, abs=1e-7)
        assert slot.coords_b == pytest.approx(base_slot.coords_b, rel=1e-6, abs=1e-7)
        assert slot.z_order == base_slot.z_order
        assert slot.tag == base_slot.tag

    # Zero dangling and zero orphan tokens
    assert referenced_tokens == set(parsed_token_map)


def test_totem_custom_resolver_and_hygiene_security_guards() -> None:
    fuel_boards, locales = _load_committed_inputs()
    prices_lock = load_prices_lockfile(PRICES_LOCK_PATH)

    # Custom TotemTokenResolver hook (Plan 03-04 extension point)
    def _custom_resolver(
        board: FuelBoardEntry,
        classification: TotemBoardClassification,
        entry: CountryFuelLockEntry,
    ) -> tuple[str, str]:
        if classification.iso2 == "DE" and "small" in board.board_name:
            return (f"{classification.token_base}_c_ets2r", "1.79")
        if classification.iso2 == "DE":
            return (f"{classification.token_base}_ets2r", "1.78<sup>9</sup>")
        val = entry.local_prices[classification.grade]
        return (f"{classification.token_base}_ets2r", f"{val:.2f}")

    compiled = compile_totem_payloads(
        fuel_boards,
        locales,
        prices_lock,
        resolver=_custom_resolver,
    )
    assert compiled.board_tokens["gas_de_big_diesel"] == "fp_de_diesel_ets2r"
    assert compiled.token_values["fp_de_diesel_ets2r"] == "1.78<sup>9</sup>"
    assert compiled.board_tokens["gas_de_small_diesel"] == "fp_de_diesel_c_ets2r"
    assert compiled.token_values["fp_de_diesel_c_ets2r"] == "1.79"

    # Security guards (T-03-13): reject invalid token keys, comma decimals, and backslash injection
    sample_board = next(b for b in fuel_boards.boards if b.board_name == "gas_de_big_diesel")
    with pytest.raises(ValueError, match="token"):
        synthesize_sign_board_sii(sample_board, "bad_token_name")

    with pytest.raises(ValueError, match="key"):
        synthesize_fuel_locale_module_sii({"bad_key": "1.79"})

    with pytest.raises(ValueError, match="comma"):
        synthesize_fuel_locale_module_sii({"fp_de_diesel_ets2r": "1,79"})

    with pytest.raises(ValueError, match=r"backslash|NUL"):
        synthesize_fuel_locale_module_sii({"fp_de_diesel_ets2r": "1.79\\n"})

    # Reject fr_qc if ever injected into locales
    bad_locales = LocalesBaseline(
        active_locales=[*locales.active_locales, "fr_qc"],
        tz_keys=locales.tz_keys,
        fp_keys=locales.fp_keys,
    )
    with pytest.raises(ValueError, match="fr_qc"):
        compile_totem_payloads(fuel_boards, bad_locales, prices_lock)
