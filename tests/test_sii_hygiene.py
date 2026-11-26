"""Red-first tests for SII/SUI encoding, normalization, and SCS hygiene checks."""

from __future__ import annotations

import pytest

from ets2_realism.sii.hygiene import (
    SiiDiagnostic,
    SiiEncodingError,
    normalize_sii_bytes,
    serialize_sii_text,
    validate_sii_hygiene,
)


def test_normalize_sii_bytes_strips_bom_and_normalizes_crlf_and_cr() -> None:
    raw = b'\xef\xbb\xbfSiiNunit\r\n{\r\t# comment\r\n\tname: "Eesti"\r}\r\n'
    normalized = normalize_sii_bytes(raw)
    assert normalized == 'SiiNunit\n{\n\t# comment\n\tname: "Eesti"\n}\n'

    pass1 = serialize_sii_text(normalized)
    assert not pass1.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in pass1

    # Pass 2+ round-trip must have zero byte diff.
    pass2 = serialize_sii_text(normalize_sii_bytes(pass1))
    assert pass2 == pass1


def test_clean_lf_no_bom_round_trips_zero_diff_on_pass_1() -> None:
    clean = (
        b"SiiNunit\n"
        b"{\n"
        b"country_data : country.data.estonia\n"
        b"{\n"
        b'\tname: "Eesti"\n'
        b"\tfuel_price: 1.799\t# keep\n"
        b"}\n"
        b"}"
    )
    assert serialize_sii_text(normalize_sii_bytes(clean)) == clean


def test_normalize_sii_bytes_rejects_invalid_utf8_strictly() -> None:
    bad_samples = [
        b"\xff\xfeS\x00i\x00i\x00",
        b'name: "caf\xe9"\n',
        b"\xef\xbb\xbf\xc3\x28\n",
    ]
    for bad in bad_samples:
        with pytest.raises(SiiEncodingError):
            normalize_sii_bytes(bad)


def test_serialize_sii_text_strips_bom_str_normalizes_cr_and_rejects_surrogates() -> None:
    emitted = serialize_sii_text("\ufeffSiiNunit\r\n{\r}\r\n")
    assert emitted == b"SiiNunit\n{\n}\n"

    with pytest.raises(SiiEncodingError):
        serialize_sii_text("bad: \ud800\n")


def test_validate_sii_hygiene_accepts_valid_sii_and_sui() -> None:
    sii_text = (
        "SiiNunit\n"
        "{\n"
        '@include "country/germany.sui"\n'
        "country_speed_limit : .speed_limit.car {\n"
        "\tvehicle_speed_class: car\n"
        "}\n"
        "}\n"
    )
    assert validate_sii_hygiene(sii_text, require_siinunit=True) == []

    sui_text = 'country_data : country.data.germany\n{\n\tcountry_id: 2\n\tname: "Deutschland"\n}\n'
    assert validate_sii_hygiene(sui_text, require_siinunit=False) == []


def test_validate_sii_hygiene_flags_bom_and_crlf_on_raw_bytes() -> None:
    raw = b"\xef\xbb\xbfSiiNunit\r\n{\r\n}\r\n"
    diags = validate_sii_hygiene(raw, require_siinunit=True)
    codes = {d.code for d in diags}
    assert "utf8_bom" in codes
    assert "non_lf_line_ending" in codes
    assert all(isinstance(d, SiiDiagnostic) for d in diags)

    normalized = normalize_sii_bytes(raw)
    assert validate_sii_hygiene(normalized, require_siinunit=True) == []


def test_validate_sii_hygiene_rejects_non_col0_include_but_ignores_comments_and_strings() -> None:
    bad_indented = 'SiiNunit\n{\n  @include "country/germany.sui"\n}\n'
    assert any(
        d.code == "include_not_column_0"
        for d in validate_sii_hygiene(bad_indented, require_siinunit=True)
    )

    bad_tabbed = 'SiiNunit\n{\n\t@include "country/germany.sui"\n}\n'
    assert any(
        d.code == "include_not_column_0"
        for d in validate_sii_hygiene(bad_tabbed, require_siinunit=True)
    )

    bad_inline = 'SiiNunit { @include "country/germany.sui"\n}\n'
    assert any(
        d.code == "include_not_column_0"
        for d in validate_sii_hygiene(bad_inline, require_siinunit=True)
    )

    valid_ignored = (
        "SiiNunit\n"
        "{\n"
        '# @include "ignored_hash.sui"\n'
        '// @include "ignored_slash.sui"\n'
        '/* @include "ignored_block.sui" */\n'
        "localization_db : .localization\n"
        "{\n"
        '\tkey[]: "hint"\n'
        '\tval[]: "Example:  @include \\"x.sui\\""\n'
        "}\n"
        "}\n"
    )
    assert validate_sii_hygiene(valid_ignored, require_siinunit=True) == []


def test_validate_sii_hygiene_rejects_backslashes_and_dotdot_paths() -> None:
    cases = [
        '@include "country\\germany.sui"\n',
        '@include "country\\new\\germany.sui"\n',
        '@include "../country/germany.sui"\n',
        '@include "country/../germany.sui"\n',
        'country_data : .demo\n{\n\ticon: "\\material\\ui\\flag.mat"\n}\n',
        'country_data : .demo\n{\n\ticon: "def\\new\\test.sui"\n}\n',
        'country_data : .demo\n{\n\ticon: "/material/../secret.mat"\n}\n',
    ]
    for sample in cases:
        diags = validate_sii_hygiene(sample)
        codes = {d.code for d in diags}
        assert codes & {"path_backslash", "path_parent_traversal"}, f"Expected path diag: {sample}"

    safe_strings = (
        "localization_db : .localization\n"
        "{\n"
        '\tkey[]: "msg"\n'
        '\tval[]: "Loading...\\nLine 2 \\"ok\\""\n'
        "}\n"
    )
    assert validate_sii_hygiene(safe_strings) == []


def test_validate_sii_hygiene_enforces_unit_segment_rules_and_braces() -> None:
    valid_units = (
        "SiiNunit\n"
        "{\n"
        "country_speed_limit : .speed_limit.car {\n"
        "\tvehicle_speed_class: car\n"
        "}\n"
        "sign_board_template : .package_name {\n"
        '\tmodel_name: ""\n'
        "}\n"
        "}\n"
    )
    assert validate_sii_hygiene(valid_units, require_siinunit=True) == []

    too_long = "country_data : country.data.bosnia_herzegovina\n{\n\tcountry_id: 1\n}\n"
    assert any(d.code == "unit_segment_too_long" for d in validate_sii_hygiene(too_long))

    invalid_chars = "country_data : Country.Bad-Name\n{\n\tcountry_id: 1\n}\n"
    assert any(d.code == "unit_segment_invalid" for d in validate_sii_hygiene(invalid_chars))

    empty_seg = "country_data : foo..bar\n{\n\tcountry_id: 1\n}\n"
    assert any(d.code == "unit_segment_invalid" for d in validate_sii_hygiene(empty_seg))

    dot_only = "country_data : .\n{\n\tcountry_id: 1\n}\n"
    assert any(d.code == "unit_segment_invalid" for d in validate_sii_hygiene(dot_only))

    unbalanced = "SiiNunit\n{\ncountry_data : .ok\n{\n\tcountry_id: 1\n}\n"
    assert any(d.code == "unbalanced_brace" for d in validate_sii_hygiene(unbalanced))

    missing_header = "country_data : .ok\n{\n\tcountry_id: 1\n}\n"
    assert any(
        d.code == "missing_siinunit_header"
        for d in validate_sii_hygiene(missing_header, require_siinunit=True)
    )


def test_validate_sii_hygiene_allows_valid_escapes_before_asset_ext_and_reports_col() -> None:
    safe_ui_with_ext = (
        "localization_db : .localization\n"
        "{\n"
        '\tkey[]: "msg_1"\n'
        '\tval[]: "Saved\\nreport.txt"\n'
        '\tkey[]: "msg_2"\n'
        '\tval[]: "Tab\\t/logs/out.png"\n'
        '\tkey[]: "msg_3"\n'
        '\tval[]: "Slash\\\\demo.sui"\n'
        "}\n"
    )
    assert validate_sii_hygiene(safe_ui_with_ext) == []

    # Path-attribute keys with backslash escapes still fail and report exact column
    bad_icon = 'country_data : .demo\n{\n\ticon: "def\\new\\test.sui"\n}\n'
    diags = validate_sii_hygiene(bad_icon)
    path_diags = [d for d in diags if d.code == "path_backslash"]
    assert len(path_diags) == 1
    assert path_diags[0].line == 3
    assert path_diags[0].column == len("\ticon: ") + 1

    # Mid-file ZWNBSP in str input is not misclassified as leading UTF-8 BOM
    mid_zwnbsp = 'localization_db : .loc\n{\n\tkey[]: "k"\n\tval[]: "a\ufeffb"\n}\n'
    assert validate_sii_hygiene(mid_zwnbsp) == []
    leading_bom = "\ufeff" + mid_zwnbsp
    assert any(d.code == "utf8_bom" for d in validate_sii_hygiene(leading_bom))
