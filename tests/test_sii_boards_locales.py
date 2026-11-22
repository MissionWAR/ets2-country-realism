"""Red-first tests for read-only sign_board_template and localization_db parsers."""

from __future__ import annotations

import pytest

from ets2v2.sii.localization import LocalizationEntry, parse_localization_db
from ets2v2.sii.sign_board import (
    SignBoardTemplate,
    SignTemplateTextSlot,
    parse_sign_board,
)


def test_parse_sign_board_fuel_totems_hex_floats_placeholders_blank_and_nil() -> None:
    gas_de_big_95 = (
        "SiiNunit\n"
        "{\n"
        "sign_board_template : _nameless.1a2b.3c4d\n"
        "{\n"
        '\tmodel_name: ""\n'
        "\tboard_size: (&3f800000, 2.0)\n"
        "\titems: 1\n"
        "\titems[0]: _nameless.1a2b.3c4e\n"
        "}\n"
        "\n"
        "sign_template_text : _nameless.1a2b.3c4e\n"
        "{\n"
        '\tfont_face: "/font/sign/gas_segment_7_standard.font"\n'
        "\tcoords_l: &c2a00000\n"
        "\tcoords_r: &42a00000\n"
        "\tcoords_t: &42200000\n"
        "\tcoords_b: &c2200000\n"
        "\th_align: center\n"
        "\tv_align: center\n"
        '\ttext: "@@fp_de_natural95@@"\n'
        "}\n"
        "}\n"
    )
    board = parse_sign_board(gas_de_big_95)
    assert isinstance(board, SignBoardTemplate)
    assert board.unit_name == "_nameless.1a2b.3c4d"
    assert board.model_name == ""
    assert board.board_size == (1.0, 2.0)
    assert board.items_count == 1
    assert board.child_types == ["sign_template_text"]
    assert board.is_single_text_fuel_candidate is True
    assert len(board.text_slots) == 1

    slot = board.text_slots[0]
    assert isinstance(slot, SignTemplateTextSlot)
    assert slot.slot_index == 0
    assert slot.font_face == "/font/sign/gas_segment_7_standard.font"
    assert slot.coords_l == pytest.approx(-80.0)
    assert slot.coords_r == pytest.approx(80.0)
    assert slot.coords_t == pytest.approx(40.0)
    assert slot.coords_b == pytest.approx(-40.0)
    assert slot.h_align == "center"
    assert slot.v_align == "center"
    assert slot.text == "@@fp_de_natural95@@"
    assert slot.localization_key == "fp_de_natural95"

    # Numeric placeholder ("123.9") and blank (" ") templates with nil attributes
    placeholder_board = (
        "SiiNunit\n"
        "{\n"
        "sign_board_template : .board\n"
        "{\n"
        '\tmodel_name: ""\n'
        "\tboard_size: nil\n"
        "\titems: 1\n"
        "\titems[0]: .text\n"
        "}\n"
        "sign_template_text : .text\n"
        "{\n"
        "\tfont_face: nil\n"
        "\tcoords_l: -10.5\n"
        "\tcoords_r: 10.5\n"
        "\tcoords_t: nil\n"
        "\tcoords_b: nil\n"
        "\th_align: left\n"
        "\tv_align: nil\n"
        '\ttext: "123.9"\n'
        "}\n"
        "}\n"
    )
    ph = parse_sign_board(placeholder_board)
    assert ph.board_size is None
    assert ph.is_single_text_fuel_candidate is True
    assert ph.text_slots[0].font_face is None
    assert ph.text_slots[0].coords_l == pytest.approx(-10.5)
    assert ph.text_slots[0].coords_t is None
    assert ph.text_slots[0].v_align is None
    assert ph.text_slots[0].text == "123.9"
    assert ph.text_slots[0].localization_key is None

    blank_board = placeholder_board.replace('"123.9"', '" "')
    bl = parse_sign_board(blank_board)
    assert bl.text_slots[0].text == " "
    assert bl.text_slots[0].localization_key is None


def test_parse_sign_board_162_full_rendering_attributes() -> None:
    """Verify all 6 sign_board_template and 18 sign_template_text ETS2 1.62 attributes."""
    authentic_162 = (
        "SiiNunit\n"
        "{\n"
        "sign_board_template : _nameless.2.2a34.f3e0 {\n"
        ' board_name: "gas de big diesel"\n'
        " width: &3fc00000\n"
        " height: &3f2b851f\n"
        ' model_name: ""\n'
        " items: 1\n"
        " items[0]: _nameless.2.1160.beb0\n"
        " dynamic_attributes: 0\n"
        "}\n"
        "\n"
        "sign_template_text : _nameless.2.1160.beb0 {\n"
        ' text: "@@fp_de_diesel@@"\n'
        ' font_face: "/font/sign/gas_roadgeek_2005_mittelschrift.font"\n'
        " font_size: &3eb33333\n"
        " text_halign: center\n"
        " text_valign: bottom\n"
        " font_color: 200\n"
        " font_opacity: 1\n"
        " line_spacing: &3e4ccccd\n"
        " letter_spacing: 0\n"
        " id: 2435448831\n"
        ' area_name: ""\n'
        " area_idx: nil\n"
        " coords_l: &3dd04570\n"
        " coords_r: &3fa1a08b\n"
        " coords_t: &3f0b9214\n"
        " coords_b: &3de4c050\n"
        " z_order: 1\n"
        ' tag: ""\n'
        "}\n"
        "\n"
        "}\n"
    )
    board = parse_sign_board(authentic_162)
    assert board.unit_name == "_nameless.2.2a34.f3e0"
    assert board.board_name == "gas de big diesel"
    assert board.width == pytest.approx(1.5)
    assert board.height == pytest.approx(0.67, abs=1e-6)
    assert board.model_name == ""
    assert board.items_count == 1
    assert board.dynamic_attributes == 0
    assert board.is_single_text_fuel_candidate is True

    slot = board.text_slots[0]
    assert slot.unit_name == "_nameless.2.1160.beb0"
    assert slot.text == "@@fp_de_diesel@@"
    assert slot.localization_key == "fp_de_diesel"
    assert slot.font_face == "/font/sign/gas_roadgeek_2005_mittelschrift.font"
    assert slot.font_size == pytest.approx(0.35, abs=1e-6)
    assert slot.text_halign == "center"
    assert slot.text_valign == "bottom"
    assert slot.font_color == 200
    assert slot.font_opacity == pytest.approx(1.0)
    assert slot.line_spacing == pytest.approx(0.2, abs=1e-6)
    assert slot.letter_spacing == pytest.approx(0.0)
    assert slot.text_id == 2435448831
    assert slot.area_name == ""
    assert slot.area_idx is None
    assert slot.coords_l == pytest.approx(0.10169494, abs=1e-6)
    assert slot.coords_r == pytest.approx(1.2627119, abs=1e-6)
    assert slot.coords_t == pytest.approx(0.5451977, abs=1e-6)
    assert slot.coords_b == pytest.approx(0.11169493, abs=1e-6)
    assert slot.z_order == 1
    assert slot.tag == ""

    # Verify font_color: nil and area_idx: 0 round-trip distinctly
    nil_color_board = (
        authentic_162.replace("font_color: 200", "font_color: nil")
        .replace("area_idx: nil", "area_idx: 0")
        .replace('area_name: ""', "area_name: nil")
        .replace('tag: ""', 'tag: "price"')
    )
    parsed_alt = parse_sign_board(nil_color_board)
    alt_slot = parsed_alt.text_slots[0]
    assert alt_slot.font_color is None
    assert alt_slot.area_idx == 0
    assert alt_slot.area_name is None
    assert alt_slot.tag == "price"


def test_parse_sign_board_handles_multi_item_highway_sign_for_exclusion() -> None:
    fi_oulu_95 = (
        "SiiNunit\n"
        "{\n"
        "sign_board_template : _nameless.1\n"
        "{\n"
        '\tmodel_name: "/model/sign/fi_highway.pmd"\n'
        "\titems: 8\n"
        "\titems[0]: _nameless.f0\n"
        "\titems[1]: _nameless.i1\n"
        "\titems[2]: _nameless.t2\n"
        "\titems[3]: _nameless.t3\n"
        "\titems[4]: _nameless.i4\n"
        "\titems[5]: _nameless.t5\n"
        "\titems[6]: _nameless.i6\n"
        "\titems[7]: _nameless.t7\n"
        "}\n"
        "sign_template_frame : _nameless.f0 {\n}\n"
        "sign_template_image : _nameless.i1 {\n}\n"
        'sign_template_text : _nameless.t2 {\n\ttext: "Oulu"\n}\n'
        'sign_template_text : _nameless.t3 {\n\ttext: "95"\n}\n'
        "sign_template_image : _nameless.i4 {\n}\n"
        'sign_template_text : _nameless.t5 {\n\ttext: "E75"\n}\n'
        "sign_template_image : _nameless.i6 {\n}\n"
        'sign_template_text : _nameless.t7 {\n\ttext: "12 km"\n}\n'
        "}\n"
    )
    board = parse_sign_board(fi_oulu_95)
    assert board.model_name == "/model/sign/fi_highway.pmd"
    assert board.items_count == 8
    assert board.is_single_text_fuel_candidate is False
    assert [slot.text for slot in board.text_slots] == ["Oulu", "95", "E75", "12 km"]
    assert board.child_types[0] == "sign_template_frame"
    assert board.child_types[1] == "sign_template_image"


def test_parse_sign_board_does_not_dos_on_inflated_items_count() -> None:
    malformed_count = (
        "SiiNunit\n"
        "{\n"
        "sign_board_template : .dos\n"
        "{\n"
        '\tmodel_name: ""\n'
        "\titems: 999999999\n"
        "\titems[0]: .t0\n"
        "}\n"
        'sign_template_text : .t0 {\n\ttext: "0.00"\n}\n'
        "}\n"
    )
    board = parse_sign_board(malformed_count)
    assert board.items_count == 999999999
    assert len(board.text_slots) == 1


def test_parse_localization_db_headerless_and_wrapped_multilingual() -> None:
    headerless = (
        b"\xef\xbb\xbf# vanilla fuel price strings\r\n"
        b'key[]: "fp_al_diesel"\r\n'
        b'val[]: "211"\r\n'
        b'key[]: "fp_uk_diesel"\r\n'
        b'val[]: "2.10<sup>0</sup>"\t# micro-tag\r\n'
        b'key[]: "fp_cz_natural95"\r\n'
        b'val[]: "48.10"\r\n'
    )
    entries = parse_localization_db(headerless)
    assert entries == [
        LocalizationEntry(key="fp_al_diesel", val="211"),
        LocalizationEntry(key="fp_uk_diesel", val="2.10<sup>0</sup>"),
        LocalizationEntry(key="fp_cz_natural95", val="48.10"),
    ]

    cyrillic_label = "\u041c\u0421\u041a // \u0412\u0440\u0435\u043c\u044f"
    wrapped = (
        "SiiNunit\n"
        "{\n"
        "localization_db : .localization\n"
        "{\n"
        '\tkey[]: "tz_cest"\n'
        '\tval[]: "CEST"\n'
        '\tkey[]: "tz_msk"\n'
        f'\tval[]: "{cyrillic_label}"\n'
        '\tkey[]: "ui_cjk_ar"\n'
        '\tval[]: "東京 中文 العربية # tag"\n'
        "}\n"
        "}\n"
    ).encode()
    wrapped_entries = parse_localization_db(wrapped)
    assert wrapped_entries == [
        LocalizationEntry(key="tz_cest", val="CEST"),
        LocalizationEntry(key="tz_msk", val=cyrillic_label),
        LocalizationEntry(key="ui_cjk_ar", val="東京 中文 العربية # tag"),
    ]

    mismatched = 'key[]: "a"\nkey[]: "b"\nval[]: "1"\n'
    with pytest.raises(ValueError):
        parse_localization_db(mismatched)


def test_public_sii_package_exports() -> None:
    import ets2v2.sii as sii

    expected = {
        "CountryDataModel",
        "CountryDataPatch",
        "LaneSpeedRule",
        "LocalizationEntry",
        "SignBoardTemplate",
        "SignTemplateTextSlot",
        "SiiAttributeSpan",
        "SiiDiagnostic",
        "SiiDocument",
        "SiiEncodingError",
        "SiiIncludeSpan",
        "SiiSpan",
        "SiiUnitBlock",
        "SpeedLimitsFile",
        "VehicleSpeedLimitBlock",
        "normalize_sii_bytes",
        "parse_country_data",
        "parse_country_includes",
        "parse_localization_db",
        "parse_sign_board",
        "parse_sii_float",
        "parse_speed_limits",
        "patch_country_data",
        "patch_speed_limits",
        "scan_sii_structure",
        "serialize_sii_text",
        "validate_sii_hygiene",
    }
    assert expected <= set(sii.__all__)
    for name in expected:
        assert hasattr(sii, name)
