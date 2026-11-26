"""Red-first tests for SII/SUI structural lexer and surgical span-preserving editor."""

from __future__ import annotations

import struct

import pytest

from ets2_realism.sii.document import (
    SiiAttributeSpan,
    SiiDocument,
    SiiIncludeSpan,
    SiiUnitBlock,
)
from ets2_realism.sii.lexer import SiiSpan, parse_sii_float, scan_sii_structure


def test_parse_sii_float_decimal_and_ieee754_hex() -> None:
    assert parse_sii_float("2.244") == pytest.approx(2.244)
    assert parse_sii_float(" -15.5 ") == pytest.approx(-15.5)
    assert parse_sii_float("&3f800000") == pytest.approx(1.0)
    assert parse_sii_float("&BF800000") == pytest.approx(-1.0)
    assert parse_sii_float("&42a00000") == pytest.approx(80.0)
    assert parse_sii_float("&c2a00000") == pytest.approx(-80.0)

    expected_pi = struct.unpack(">f", bytes.fromhex("40490f5a"))[0]
    assert parse_sii_float("&40490f5a") == pytest.approx(expected_pi)

    for invalid in ("", "nil", "&123", "&zzzzzzzz", "not_a_float"):
        with pytest.raises(ValueError):
            parse_sii_float(invalid)


def test_scan_sii_structure_handles_comments_strings_includes_and_arrays() -> None:
    sample = (
        "SiiNunit\n"
        "{\n"
        "/* Multi-line comment\n"
        ' * brace { } # ignore @include "fake.sui"\n'
        " */\n"
        '@include "country/first.sui"\n'
        "country_data : country.data.estonia // header comment\n"
        "{\n"
        "\tcountry_id: 22\n"
        '\tname: "Eesti # not comment // nope"  # keep this comment\n'
        "\titems: 2\n"
        "\titems[0]: .first\n"
        "\titems[1]: .second\n"
        "\tmass_limit_per_axle_count[]: 18000\t# 2-axle\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "}\n"
        "}\n"
    )
    scan = scan_sii_structure(sample, require_siinunit=True)
    assert scan.has_siinunit is True
    assert list(scan.diagnostics) == []
    assert len(scan.includes) == 1
    assert scan.includes[0].path == "country/first.sui"
    assert scan.includes[0].is_column_zero is True
    assert isinstance(scan.includes[0].span, SiiSpan)

    assert len(scan.units) == 1
    unit = scan.units[0]
    assert unit.class_name == "country_data"
    assert unit.unit_name == "country.data.estonia"
    assert unit.indent == "\t"

    name_attr = next(a for a in unit.attributes if a.key == "name")
    assert name_attr.raw_value == '"Eesti # not comment // nope"'
    assert name_attr.inline_comment == "# keep this comment"

    items_scalar = next(a for a in unit.attributes if a.key == "items" and a.index is None)
    assert items_scalar.raw_value == "2"
    indexed = [a for a in unit.attributes if a.key == "items" and a.index is not None]
    assert [(a.index, a.raw_value) for a in indexed] == [(0, ".first"), (1, ".second")]

    axles = [a for a in unit.attributes if a.key == "mass_limit_per_axle_count" and a.is_append]
    assert [a.raw_value for a in axles] == ["18000", "26000"]


def test_document_preserves_untouched_bytes_and_normalizes_bom_crlf() -> None:
    clean_bytes = (
        b"country_data : country.data.isl\n"
        b"{\n"
        b"\tcountry_id: 26\n"
        b"\tiso_country_code: isl\n"
        b"\t\n"
        b"\tfuel_price: 2.307\t\t# ISK converted\n"
        b"}\n"
    )
    doc = SiiDocument.parse(clean_bytes)
    assert isinstance(doc.units[0], SiiUnitBlock)
    assert isinstance(doc.units[0].attributes[0], SiiAttributeSpan)
    assert doc.to_bytes() == clean_bytes

    bom_crlf = b"\xef\xbb\xbf" + clean_bytes.replace(b"\n", b"\r\n")
    doc_bom = SiiDocument.parse(bom_crlf)
    pass1 = doc_bom.to_bytes()
    assert pass1 == clean_bytes
    assert SiiDocument.parse(pass1).to_bytes() == pass1


def test_document_surgical_scalar_update_and_absent_key_insertion_before_brace_and_include() -> (
    None
):
    base = (
        "country_data : country.data.germany\n"
        "{\n"
        "    country_id: 2\n"
        '    name: "Deutschland" // localized separately\n'
        "    fuel_price: 2.244\t# base price\n"
        "    time_zone: 60 /* CET */\n"
        "}\n"
    )
    doc = SiiDocument.parse(base)
    unit = doc.units[0]
    doc.set_scalar(unit, "fuel_price", "2.099")
    doc.set_scalar(unit, "lights_mandatory", "false")
    doc.set_scalar(unit, "driving_tired_offence", "true")

    rendered = doc.render()
    expected = (
        "country_data : country.data.germany\n"
        "{\n"
        "    country_id: 2\n"
        '    name: "Deutschland" // localized separately\n'
        "    fuel_price: 2.099\t# base price\n"
        "    time_zone: 60 /* CET */\n"
        "    lights_mandatory: false\n"
        "    driving_tired_offence: true\n"
        "}\n"
    )
    assert rendered == expected

    # Trailing @include inside unit block: insert BEFORE trailing @include, keep col-0 @include.
    with_vtd = (
        "country_data : country.data.germany\n"
        "{\n"
        "\tcountry_id: 2\n"
        "\tfuel_price: 2.244\n"
        '@include "_vtd/germany.sui"\n'
        "}\n"
    )
    doc_vtd = SiiDocument.parse(with_vtd)
    assert len(doc_vtd.includes) == 1
    assert isinstance(doc_vtd.includes[0], SiiIncludeSpan)
    doc_vtd.set_scalar(doc_vtd.units[0], "lights_mandatory", "false")
    assert doc_vtd.render() == (
        "country_data : country.data.germany\n"
        "{\n"
        "\tcountry_id: 2\n"
        "\tfuel_price: 2.244\n"
        "\tlights_mandatory: false\n"
        '@include "_vtd/germany.sui"\n'
        "}\n"
    )


def test_document_replace_array_append_handles_expansion_shrink_and_absence() -> None:
    text = (
        "country_data : country.data.iceland\n"
        "{\n"
        "\tcountry_id: 26\n"
        "\t# axle weights\n"
        "\tmass_limit_per_axle_count[]: 18000\t# 2-axle vehicle\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 36000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
        "\n"
        "\tregions[]: highland\n"
        "}\n"
    )
    doc = SiiDocument.parse(text)
    doc.replace_array_append(
        doc.units[0],
        "mass_limit_per_axle_count",
        ["18000", "26000", "36000", "40000", "60000"],
    )
    expanded = doc.render()
    assert expanded == (
        "country_data : country.data.iceland\n"
        "{\n"
        "\tcountry_id: 26\n"
        "\t# axle weights\n"
        "\tmass_limit_per_axle_count[]: 18000\t# 2-axle vehicle\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 36000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
        "\tmass_limit_per_axle_count[]: 60000\n"
        "\n"
        "\tregions[]: highland\n"
        "}\n"
    )

    doc2 = SiiDocument.parse(expanded)
    doc2.replace_array_append(doc2.units[0], "mass_limit_per_axle_count", ["18000", "25000"])
    assert doc2.render() == (
        "country_data : country.data.iceland\n"
        "{\n"
        "\tcountry_id: 26\n"
        "\t# axle weights\n"
        "\tmass_limit_per_axle_count[]: 18000\t# 2-axle vehicle\n"
        "\tmass_limit_per_axle_count[]: 25000\n"
        "\n"
        "\tregions[]: highland\n"
        "}\n"
    )

    # Absent array insertion
    no_array = "country_data : .empty {\n}\n"
    doc3 = SiiDocument.parse(no_array)
    doc3.replace_array_append(doc3.units[0], "regions", ["the_north"])
    assert doc3.render() == "country_data : .empty {\n\tregions[]: the_north\n}\n"


def test_document_parses_headerless_bare_attributes() -> None:
    fragment = (
        "# headerless localization fragment\n"
        'key[]: "fp_de_diesel"\n'
        'val[]: "1.959"\n'
        'key[]: "fp_cz_natural95"\n'
        'val[]: "48.10"\t# always ends with .X0\n'
    )
    doc = SiiDocument.parse(fragment)
    assert doc.has_siinunit is False
    assert doc.units == []
    keys = [a.raw_value for a in doc.get_root_attributes("key")]
    vals = [a.raw_value for a in doc.get_root_attributes("val")]
    assert keys == ['"fp_de_diesel"', '"fp_cz_natural95"']
    assert vals == ['"1.959"', '"48.10"']


def test_document_single_line_and_shared_brace_mutations_preserve_braces() -> None:
    single_line = "country_data : .a { regions[]: north }\n"
    doc = SiiDocument.parse(single_line)
    doc.replace_array_append(doc.units[0], "regions", ["north", "south"])
    expanded = doc.render()
    assert expanded == "country_data : .a { regions[]: north\n\tregions[]: south }\n"
    assert [a.raw_value for a in SiiDocument.parse(expanded).units[0].attributes] == [
        "north",
        "south",
    ]

    # Shrink from 2 down to 1 (removing attribute sharing line with '}')
    doc_shrink = SiiDocument.parse(expanded)
    doc_shrink.replace_array_append(doc_shrink.units[0], "regions", ["north"])
    assert doc_shrink.render() == "country_data : .a { regions[]: north\n}\n"

    # Remove single remaining attribute sharing line with '{' and '}'
    doc_clear = SiiDocument.parse(single_line)
    doc_clear.remove_attribute_line(doc_clear.units[0].attributes[0])
    assert doc_clear.render() == "country_data : .a {}\n"
    assert SiiDocument.parse(doc_clear.render()).diagnostics == []

    # Shared opening brace on line 1, shared closing brace on line 2
    two_line_shared = "country_data : .a { regions[]: north\n\tregions[]: south }\n"
    doc_two = SiiDocument.parse(two_line_shared)
    doc_two.replace_array_append(doc_two.units[0], "regions", [])
    assert doc_two.render() == "country_data : .a {\n}\n"

    # Fixed-array replacement when single-line brace is shared
    fixed_single = (
        "country_data : .a { mass_limit_per_axle_count: 2\n"
        "\tmass_limit_per_axle_count[0]: 18000\n"
        "\tmass_limit_per_axle_count[1]: 26000 }\n"
    )
    doc_fixed = SiiDocument.parse(fixed_single)
    doc_fixed.replace_array_append(
        doc_fixed.units[0],
        "mass_limit_per_axle_count",
        ["18000", "25000", "38000"],
    )
    rendered_fixed = doc_fixed.render()
    assert rendered_fixed == (
        "country_data : .a {\n"
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 25000\n"
        "\tmass_limit_per_axle_count[]: 38000\n"
        "}\n"
    )

    # Indented unit (inside SiiNunit) where anchor shares line with closing '}' (WR-11)
    indented_shared_close = (
        "SiiNunit\n{\n\tcountry_data : .a {\n\t\tmass_limit_per_axle_count[0]: 18000 }\n}\n"
    )
    doc_indented = SiiDocument.parse(indented_shared_close)
    doc_indented.replace_array_append(
        doc_indented.units[0],
        "mass_limit_per_axle_count",
        ["18000", "26000"],
    )
    assert doc_indented.render() == (
        "SiiNunit\n"
        "{\n"
        "\tcountry_data : .a {\n"
        "\t\tmass_limit_per_axle_count[]: 18000\n"
        "\t\tmass_limit_per_axle_count[]: 26000\n"
        "\t}\n"
        "}\n"
    )


def test_scan_sii_structure_unclosed_paren_and_eof_unit_span_clamp() -> None:
    malformed = (
        "country_data : .a {\n"
        "\tpos: (1.0, 2.0\n"
        "\tfuel_price: 1.5\n"
        "}\n"
        "country_data : .b {\n"
        "\tcountry_id: 2\n"
        "}\n"
    )
    scan = scan_sii_structure(malformed)
    assert any(d.code == "unbalanced_paren" for d in scan.diagnostics)
    assert len(scan.units) == 2
    assert scan.units[0].unit_name == ".a"
    fuel = scan.units[0].get_scalar("fuel_price")
    assert fuel is not None and fuel.raw_value == "1.5"
    assert scan.units[1].unit_name == ".b"

    same_line_unclosed = (
        "country_data : .a { pos: (1.0, 2.0 }\ncountry_data : .b { country_id: 2 }\n"
    )
    scan_sl = scan_sii_structure(same_line_unclosed)
    assert any(d.code == "unbalanced_paren" for d in scan_sl.diagnostics)
    assert len(scan_sl.units) == 2

    unclosed_eof = "country_data : .eof {\n\tpos: (1.0, 2.0"
    scan_eof = scan_sii_structure(unclosed_eof)
    codes = {d.code for d in scan_eof.diagnostics}
    assert {"unbalanced_paren", "unbalanced_brace"} <= codes
    assert len(scan_eof.units) == 1
    assert scan_eof.units[0].span.end <= len(unclosed_eof)


def test_document_duplicate_scalar_last_wins() -> None:
    text = "country_data : .dup {\n\tfuel_price: 1.1\n\tfuel_price: 2.2\n}\n"
    doc = SiiDocument.parse(text)
    scalar = doc.units[0].get_scalar("fuel_price")
    assert scalar is not None
    assert scalar.raw_value == "2.2"
    doc.set_scalar(doc.units[0], "fuel_price", "3.3")
    assert doc.render() == "country_data : .dup {\n\tfuel_price: 1.1\n\tfuel_price: 3.3\n}\n"
