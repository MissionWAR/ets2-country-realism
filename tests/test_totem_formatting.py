"""Exhaustive tests for 6-font SDF width-budget physics and native-currency totem formatting."""

from __future__ import annotations

import pathlib
from typing import Literal

import pytest

from ets2_realism.baseline.models import FuelBoardsBaseline
from ets2_realism.normalize.lockfile import load_prices_lockfile
from ets2_realism.normalize.totem_catalog import classify_all_fuel_boards
from ets2_realism.normalize.totem_format import (
    EUROZONE_3DEC_ISO2S,
    EUROZONE_TENTH_CENT_ISO2S,
    GAS_FONT_METRICS,
    INTEGER_CURRENCY_ISO2S,
    SUP_SCALE_FACTOR,
    WIDTH_TOLERANCE_FACTOR,
    GasFontMetrics,
    compute_rendered_text_width,
    format_national_pump_price,
    resolve_totem_token_and_value,
    verify_totem_glyph_and_width,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
PRICES_LOCK_PATH = REPO_ROOT / "state" / "prices.lock.json"


def _load_committed_boards() -> FuelBoardsBaseline:
    return FuelBoardsBaseline.model_validate_json(
        (BASELINE_DIR / "fuel_boards.json").read_text("utf-8")
    )


def test_gas_font_metrics_inventory_and_width_math() -> None:
    expected_fonts = {
        "gas_karnivore_lite.font": (0.577, 0.201, True),
        "gas_roadgeek_2005_mittelschrift.font": (0.552, 0.297, True),
        "gas_segment_7_standard.font": (0.716, 0.716, False),
        "gas_ds_digib.font": (0.610, 0.167, True),
        "gas_sign_digit.font": (0.584, 0.584, False),
        "gas_fundamental_brigade_schwer.font": (0.704, 0.220, True),
    }
    assert set(GAS_FONT_METRICS) == set(expected_fonts)
    assert pytest.approx(1.03) == WIDTH_TOLERANCE_FACTOR
    assert pytest.approx(0.65) == SUP_SCALE_FACTOR

    for font_name, (dw, pw, supports_sup) in expected_fonts.items():
        metric = GAS_FONT_METRICS[font_name]
        assert isinstance(metric, GasFontMetrics)
        assert metric.font_face == font_name
        assert metric.digit_width_ratio == pytest.approx(dw)
        assert metric.dot_width_ratio == pytest.approx(pw)
        assert metric.supports_sup is supports_sup
        # D-11: allowed glyphs strictly digits + dot (no commas, letters, or currency symbols)
        assert metric.allowed_chars == frozenset("0123456789.")

    # Exact width formula verification (full VFS path and bare filename both accepted)
    w_compact = compute_rendered_text_width(
        "1.79", "/font/sign/gas_karnivore_lite.font", font_size=1.0, letter_spacing=0.0
    )
    assert w_compact == pytest.approx(3 * 0.577 + 0.201, rel=1e-6)

    w_sup = compute_rendered_text_width(
        "1.78<sup>9</sup>", "gas_karnivore_lite.font", font_size=0.5, letter_spacing=0.02
    )
    expected_sup = (3 * 0.577 + 0.65 * 0.577 + 0.201) * 0.5 + 4 * 0.02
    assert w_sup == pytest.approx(expected_sup, rel=1e-6)

    w_7seg = compute_rendered_text_width(
        "1.789", "/font/sign/gas_segment_7_standard.font", font_size=1.0, letter_spacing=0.0
    )
    assert w_7seg == pytest.approx(5 * 0.716, rel=1e-6)

    with pytest.raises(ValueError, match="Unknown gas font"):
        compute_rendered_text_width("1.79", "/font/sign/unknown.font", font_size=0.5)


@pytest.mark.parametrize(
    ("iso2", "price", "variant", "expected"),
    [
        # UK pence with 1 decimal (D-10)
        ("GB", 1.429, "standard", "142.9"),
        ("GB", 1.4295, "standard", "143.0"),
        # Bulgaria post-2026 EUR 2 decimals (D-10)
        ("BG", 1.34, "standard", "1.34"),
        ("BG", 1.345, "standard", "1.35"),
        # High-unit integer currencies (D-10)
        ("AL", 184.5, "standard", "185"),
        ("HU", 614.6, "standard", "615"),
        ("IS", 312.4, "standard", "312"),
        ("RS", 197.5, "standard", "198"),
        # Czechia .X0 convention (< 100 -> XX.X0, >= 100 -> XXX.X carry-safe)
        ("CZ", 38.94, "standard", "38.90"),
        ("CZ", 38.95, "standard", "39.00"),
        ("CZ", 99.94, "standard", "99.90"),
        ("CZ", 99.95, "standard", "100.0"),
        ("CZ", 104.24, "standard", "104.2"),
        # Romania < 10 -> X.XX, >= 10 -> XX.X (including carry boundary 9.996 -> 10.0)
        ("RO", 7.454, "standard", "7.45"),
        ("RO", 9.994, "standard", "9.99"),
        ("RO", 9.996, "standard", "10.0"),
        ("RO", 10.14, "standard", "10.1"),
        # North Macedonia & Turkey < 100 -> XX.XX, >= 100 -> XXX.X (carry-safe)
        ("MK", 79.5, "standard", "79.50"),
        ("MK", 99.994, "standard", "99.99"),
        ("MK", 99.996, "standard", "100.0"),
        ("MK", 103.44, "standard", "103.4"),
        ("TR", 44.5, "standard", "44.50"),
        ("TR", 99.994, "standard", "99.99"),
        ("TR", 99.996, "standard", "100.0"),
        ("TR", 131.58, "standard", "131.6"),
        # Eurozone native 3-decimal (FI, GR, SI)
        ("FI", 1.789, "standard", "1.789"),
        ("GR", 1.8455, "standard", "1.846"),
        ("SI", 1.512, "standard", "1.512"),
        # 2-decimal national currencies (BA, CH, DK, NO, PL, RU, SE)
        ("BA", 2.65, "standard", "2.65"),
        ("CH", 1.894, "standard", "1.89"),
        ("DK", 14.29, "standard", "14.29"),
        ("NO", 22.45, "standard", "22.45"),
        ("PL", 6.49, "standard", "6.49"),
        ("RU", 68.5, "standard", "68.50"),
        ("SE", 18.95, "standard", "18.95"),
        # Eurozone tenth-cent 3-tier variants + carry edge case (1.7996 -> 1.80<sup>0</sup>)
        ("DE", 1.789, "standard", "1.78<sup>9</sup>"),
        ("DE", 1.7996, "standard", "1.80<sup>0</sup>"),
        ("DE", 1.789, "three_dec", "1.789"),
        ("DE", 1.785, "compact", "1.79"),
        ("IE", 1.749, "standard", "1.74<sup>9</sup>"),
        ("IT", 1.815, "compact", "1.82"),
    ],
)
def test_format_national_pump_price_conventions_and_rounding(
    iso2: str,
    price: float,
    variant: Literal["standard", "three_dec", "compact"],
    expected: str,
) -> None:
    formatted = format_national_pump_price(iso2, price, variant=variant)
    assert formatted == expected
    assert "," not in formatted
    visible = formatted.replace("<sup>", "").replace("</sup>", "")
    assert not any(sym in visible for sym in ("€", "£", "p", "$", " "))


def test_format_national_pump_price_rejects_non_positive_or_non_finite() -> None:
    for bad in (0.0, -1.5, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            format_national_pump_price("DE", bad)


def test_verify_totem_glyph_and_width_rejects_bad_glyphs_sup_on_7seg_and_overflow() -> None:
    fuel_boards = _load_committed_boards()
    boards_by_name = {b.board_name: b for b in fuel_boards.boards}

    # Narrow DE board overflows on <sup>9</sup> but fits compact 2-dec
    dortmund = boards_by_name["gas_dortmund_98"]
    assert verify_totem_glyph_and_width(dortmund, "1.89") == []
    assert verify_totem_glyph_and_width(dortmund, "1.88<sup>9</sup>") != []

    # 7-seg board rejects <sup> markup even when wide
    de_enz = boards_by_name["gas_de_enz_diesel"]
    assert verify_totem_glyph_and_width(de_enz, "1.789") == []
    sup_errors = verify_totem_glyph_and_width(de_enz, "1.78<sup>9</sup>")
    assert any("<sup>" in err for err in sup_errors)

    # Disallowed glyphs (comma, currency symbol, letters, empty string)
    wide_de = boards_by_name["gas_de_big_diesel"]
    for bad_text in ("", "1,79", "1.79€", "142.9p", "1.78<sup>99</sup>", "FREE"):
        assert verify_totem_glyph_and_width(wide_de, bad_text) != [], bad_text


def test_exhaustive_460_board_routing_and_width_budget_compliance() -> None:
    fuel_boards = _load_committed_boards()
    prices_lock = load_prices_lockfile(PRICES_LOCK_PATH)
    classifications = classify_all_fuel_boards(fuel_boards)
    boards_by_name = {b.board_name: b for b in fuel_boards.boards}

    assert len(classifications) == 460
    assert len(EUROZONE_TENTH_CENT_ISO2S) == 17
    assert set(EUROZONE_3DEC_ISO2S) == {"FI", "GR", "SI"}
    assert set(INTEGER_CURRENCY_ISO2S) == {"AL", "HU", "IS", "RS"}

    token_values: dict[str, str] = {}
    board_tokens: dict[str, str] = {}
    ez_sup_count = 0
    ez_3dec_count = 0
    ez_compact_count = 0

    for item in classifications:
        board = boards_by_name[item.board_name]
        entry = prices_lock.countries[item.iso2]
        token_key, display_value = resolve_totem_token_and_value(board, item, entry)

        assert verify_totem_glyph_and_width(board, display_value) == [], (
            f"{item.board_name}: {display_value!r}"
        )
        if token_key in token_values:
            assert token_values[token_key] == display_value
        token_values[token_key] = display_value
        board_tokens[item.board_name] = token_key

        if item.iso2 in EUROZONE_TENTH_CENT_ISO2S:
            if token_key.endswith("_3_ets2r"):
                ez_3dec_count += 1
                assert "<sup>" not in display_value
                assert len(display_value.split(".")[1]) == 3
            elif token_key.endswith("_c_ets2r"):
                ez_compact_count += 1
                assert "<sup>" not in display_value
                assert len(display_value.split(".")[1]) == 2
            else:
                ez_sup_count += 1
                assert "<sup>" in display_value and display_value.endswith("</sup>")

    # Exact Phase 3 Research §3.3 / §3.4 targets
    assert ez_sup_count == 136
    assert ez_3dec_count == 12
    assert ez_compact_count == 40
    assert ez_sup_count + ez_3dec_count + ez_compact_count == 188
    assert len(token_values) == 164

    # Explicit D-09 & D-10 spot assertions across currency & width groups
    gb_tok = board_tokens["gas_bi_beldon_diesel"]
    assert gb_tok == "fp_gb_diesel_ets2r"
    assert float(token_values[gb_tok]) > 50.0  # UK pence/L (e.g. 142.9), not GBP/L
    assert len(token_values[gb_tok].split(".")[1]) == 1

    ie_tok = board_tokens["gas_ie_cloveroil_95"]
    assert ie_tok == "fp_ie_petrol_95_3_ets2r"
    assert "<sup>" not in token_values[ie_tok]

    bg_tok = board_tokens["gas_bg_gryf_diesel"]
    assert bg_tok == "fp_bg_diesel_ets2r"
    assert "<sup>" not in token_values[bg_tok]
    assert len(token_values[bg_tok].split(".")[1]) == 2

    assert board_tokens["gas_dortmund_98"] == "fp_de_petrol_98_c_ets2r"
    assert board_tokens["gas_it_ini_diesel"] == "fp_it_diesel_c_ets2r"
    assert board_tokens["gas_de_enz_diesel"] == "fp_de_diesel_3_ets2r"
    assert board_tokens["gas_de_big_diesel"] == "fp_de_diesel_ets2r"
    assert "<sup>" in token_values["fp_de_diesel_ets2r"]

    for is_board, expected_tok in (
        ("gas_is_yokull_95", "fp_is_petrol_95_ets2r"),
        ("gas_is_yokull_diesel", "fp_is_diesel_ets2r"),
        ("gas_is_ip1_98", "fp_is_petrol_98_ets2r"),
    ):
        assert board_tokens[is_board] == expected_tok
        assert token_values[expected_tok].isdigit()


def test_all_460_boards_width_budget_under_elevated_fx_sanity_bands() -> None:
    from ets2_realism.normalize.currencies import (
        ALL_CURRENCY_SANITY_BANDS,
        ALL_TERRITORY_CURRENCIES,
    )
    from ets2_realism.normalize.fuel import compute_secondary_grade_prices
    from ets2_realism.normalize.models import CountryFuelLockEntry

    fuel_boards = _load_committed_boards()
    prices_lock = load_prices_lockfile(PRICES_LOCK_PATH)
    classifications = classify_all_fuel_boards(fuel_boards)
    boards_by_name = {b.board_name: b for b in fuel_boards.boards}

    # Stress-test every territory with elevated FX at upper sanity-band extreme (e.g. TRY=120,
    # CZK=35 -> 105+ CZK/L at 3.0 EUR/L, RON=8 -> 16+ RON/L, MKD=90 -> 180+ MKD/L)
    stress_entries: dict[str, CountryFuelLockEntry] = {}
    for iso2, base_entry in prices_lock.countries.items():
        ccy = ALL_TERRITORY_CURRENCIES[iso2]
        fx_high = 1.0 if ccy == "EUR" else ALL_CURRENCY_SANITY_BANDS[ccy][1]
        # Stress at elevated pump price: 2.00 EUR/L diesel / 2.20 EUR/L petrol_95 (and 3.00 EUR/L
        # for CZ so CZK crosses 100.00 CZK/L too)
        diesel_eur = 3.00 if iso2 == "CZ" else 2.00
        petrol_eur = 3.15 if iso2 == "CZ" else 2.20
        local_map, derived = compute_secondary_grade_prices(
            {"diesel": diesel_eur * fx_high, "petrol_95": petrol_eur * fx_high}
        )
        stress_entries[iso2] = base_entry.model_copy(
            update={
                "eur_per_liter": diesel_eur,
                "local_prices": local_map,
                "derived_grades": derived,
            }
        )

    # Confirm TR and CZ actually crossed 100 in this stress test!
    assert stress_entries["TR"].local_prices["diesel"] >= 100.0
    assert stress_entries["CZ"].local_prices["diesel"] >= 100.0

    for item in classifications:
        board = boards_by_name[item.board_name]
        entry = stress_entries[item.iso2]
        _token_key, display_value = resolve_totem_token_and_value(board, item, entry)
        assert verify_totem_glyph_and_width(board, display_value) == [], (
            f"{item.board_name} ({item.iso2}): {display_value!r}"
        )
