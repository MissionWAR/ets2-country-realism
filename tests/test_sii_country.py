"""Red-first tests for country.sii @include and country_data surgical adapters."""

from __future__ import annotations

import pytest

from ets2_realism.sii.country import (
    CountryDataModel,
    CountryDataPatch,
    parse_country_data,
    parse_country_includes,
    patch_country_data,
)
from ets2_realism.sii.hygiene import normalize_sii_bytes, serialize_sii_text


def test_parse_country_includes_handles_bom_comments_sui_and_sii_fragments() -> None:
    raw = (
        b"\xef\xbb\xbfSiiNunit\r\n"
        b"{\r\n"
        b"# Vanilla countries\r\n"
        b'@include "country/germany.sui"\r\n'
        b'@include "country/iceland.sui"\t# 1.62 60t\r\n'
        b"/* Map mod .sii fragment */\r\n"
        b'@include "country/thailand.sii"\r\n'
        b"}\r\n"
    )
    includes = parse_country_includes(raw)
    assert includes == [
        "country/germany.sui",
        "country/iceland.sui",
        "country/thailand.sii",
    ]

    empty_stub = "SiiNunit\n{\n}\n"
    assert parse_country_includes(empty_stub) == []


def test_parse_country_includes_rejects_non_col0_and_bad_paths() -> None:
    indented = 'SiiNunit\n{\n\t@include "country/germany.sui"\n}\n'
    with pytest.raises(ValueError):
        parse_country_includes(indented)

    bad_sep = 'SiiNunit\n{\n@include "country\\germany.sui"\n}\n'
    with pytest.raises(ValueError):
        parse_country_includes(bad_sep)

    bad_dotdot = 'SiiNunit\n{\n@include "../country/germany.sui"\n}\n'
    with pytest.raises(ValueError):
        parse_country_includes(bad_dotdot)


def test_parse_country_data_extracts_all_20_attributes_and_extra_fields() -> None:
    russia_like = (
        "country_data : country.data.russia\n"
        "{\n"
        "\tcountry_id: 37\n"
        '\tname: "Россия"\n'
        '\tname_localized: "@@russia@@"\n'
        '\tcountry_code: "RUS"\n'
        '\tiso_country_code: "rus"\n'
        "\tpos: (55.75, 37.61, 0)\n"
        "\tfuel_price: 0.908\t# RUB -> EUR\n"
        "\tlights_mandatory: true\n"
        "\tdriving_tired_offence: true\n"
        "\timperial_units: false\n"
        "\tleftside_traffic: false\n"
        "\ttrailer_standalone: false\n"
        "\ttime_zone: 180\t\t# +3 hours\n"
        '\ttime_zone_name: "@@tz_msk@@"\n'
        "\tsecondary_time_zone_area[]: (12000, 15000, -5000, 8000)\n"
        "\tsecondary_time_zone[]: 240\n"
        '\tsecondary_time_zone_name[]: "@@tz_samt@@"\n'
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 25000\n"
        "\tmass_limit_per_axle_count[]: 38000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
        "\tmass_limit_per_axle_count[]: 44000\n"
        "\tmass_limit_per_axle_count[]: 48000\n"
        "\tregions[]: the_north\n"
        "\tregion_areas[]: (1000, 2000, -3000, -1000)\n"
        '\tcustom_mod_tag: "rusmap_ext"\n'
        "}\n"
    )
    model = parse_country_data(russia_like)
    assert isinstance(model, CountryDataModel)
    assert model.unit_name == "country.data.russia"
    assert model.country_id == 37
    assert model.name == "Россия"
    assert model.name_localized == "@@russia@@"
    assert model.country_code == "RUS"
    assert model.iso_country_code == "rus"
    assert model.iso_country_code_quoted is True
    assert model.pos == (55.75, 37.61, 0.0)
    assert model.fuel_price == pytest.approx(0.908)
    assert model.lights_mandatory is True
    assert model.driving_tired_offence is True
    assert model.imperial_units is False
    assert model.leftside_traffic is False
    assert model.trailer_standalone is False
    assert model.time_zone == 180
    assert model.time_zone_name == "@@tz_msk@@"
    assert model.secondary_time_zone_area == [(12000.0, 15000.0, -5000.0, 8000.0)]
    assert model.secondary_time_zone == [240]
    assert model.secondary_time_zone_name == ["@@tz_samt@@"]
    assert model.mass_limit_per_axle_count == [18000, 25000, 38000, 40000, 44000, 48000]
    assert model.regions == ["the_north"]
    assert model.region_areas == [(1000.0, 2000.0, -3000.0, -1000.0)]
    assert model.extra_attributes == {"custom_mod_tag": ['"rusmap_ext"']}


def test_patch_country_data_preserves_estonia_name_quoting_regions_and_secondary_tz() -> None:
    estonia = (
        "country_data : country.data.estonia\n"
        "{\n"
        "\tcountry_id: 22\n"
        '\tname: "Eesti"\n'
        '\tname_localized: "@@estonia@@"\n'
        '\tcountry_code: "EST"\n'
        "\tiso_country_code: est\n"
        "\tfuel_price: 1.799\n"
        "\tlights_mandatory: true\n"
        "\ttime_zone: 120\n"
        '\ttime_zone_name: "@@tz_eet@@"\n'
        "}\n"
    )
    patched_est = patch_country_data(
        estonia,
        CountryDataPatch(
            fuel_price=1.654,
            time_zone=180,
            time_zone_name="@@tz_eest@@",
        ),
    )
    assert '\tname: "Eesti"\n' in patched_est
    assert "@@tz_eest@@i" not in patched_est
    assert "\tiso_country_code: est\n" in patched_est
    assert "\tfuel_price: 1.654\n" in patched_est
    assert "\ttime_zone: 180\n" in patched_est
    assert '\ttime_zone_name: "@@tz_eest@@"\n' in patched_est

    # Bosnia quoted iso_country_code ("bih") + regions[] + region_areas[] + trailing @include
    bosnia = (
        "country_data : country.data.bosnia\n"
        "{\n"
        "\tcountry_id: 42\n"
        '\tname: "Bosna i Hercegovina"\n'
        '\tiso_country_code: "bih"\n'
        "\tfuel_price: 1.45\t# BAM->EUR\n"
        "\tleftside_traffic: false\n"
        "\tregions[]: rep_srpska\n"
        "\tregion_areas[]: (44.0, 19.0, 45.0, 20.0)\n"
        '@include "_vtd/bosnia.sui"\n'
        "}\n"
    )
    patched_bih = patch_country_data(
        bosnia,
        CountryDataPatch(
            fuel_price=1.52,
            lights_mandatory=True,
            driving_tired_offence=True,
        ),
    )
    assert patched_bih == (
        "country_data : country.data.bosnia\n"
        "{\n"
        "\tcountry_id: 42\n"
        '\tname: "Bosna i Hercegovina"\n'
        '\tiso_country_code: "bih"\n'
        "\tfuel_price: 1.52\t# BAM->EUR\n"
        "\tleftside_traffic: false\n"
        "\tregions[]: rep_srpska\n"
        "\tregion_areas[]: (44.0, 19.0, 45.0, 20.0)\n"
        "\tlights_mandatory: true\n"
        "\tdriving_tired_offence: true\n"
        '@include "_vtd/bosnia.sui"\n'
        "}\n"
    )

    # Pass 2 zero-diff idempotency check
    pass1_bytes = serialize_sii_text(patched_bih)
    pass2 = patch_country_data(
        pass1_bytes,
        CountryDataPatch(
            fuel_price=1.52,
            lights_mandatory=True,
            driving_tired_offence=True,
        ),
    )
    assert serialize_sii_text(pass2) == pass1_bytes


def test_patch_country_data_expands_axles_and_preserves_unquoted_isl_and_noop() -> None:
    iceland = (
        b"\xef\xbb\xbfcountry_data : country.data.iceland\r\n"
        b"{\r\n"
        b"\tcountry_id: 26\r\n"
        b'\tname: "\xc3\x8dsland"\r\n'
        b"\tiso_country_code: isl\r\n"
        b"\tfuel_price: 2.307\r\n"
        b"\tmass_limit_per_axle_count[]: 18000\t# 2-axle\r\n"
        b"\tmass_limit_per_axle_count[]: 26000\r\n"
        b"\tmass_limit_per_axle_count[]: 36000\r\n"
        b"\tmass_limit_per_axle_count[]: 40000\r\n"
        b"}\r\n"
    )
    patched = patch_country_data(
        iceland,
        CountryDataPatch(
            lights_mandatory=True,
            mass_limit_per_axle_count=[18000, 26000, 36000, 40000, 60000],
        ),
    )
    model = parse_country_data(patched)
    assert model.iso_country_code == "isl"
    assert model.iso_country_code_quoted is False
    assert model.lights_mandatory is True
    assert model.mass_limit_per_axle_count == [18000, 26000, 36000, 40000, 60000]
    assert "\tmass_limit_per_axle_count[]: 18000\t# 2-axle\n" in patched
    assert "\tlights_mandatory: true\n" in patched

    # No-op patch on already normalized file -> 0 byte diff on pass 1!
    clean_bytes = serialize_sii_text(patched)
    noop_out = patch_country_data(clean_bytes, CountryDataPatch())
    assert serialize_sii_text(noop_out) == clean_bytes
    assert normalize_sii_bytes(clean_bytes) == noop_out


def test_country_fixed_array_parse_and_patch_removes_stale_count_and_indices() -> None:
    fixed_array_country = (
        "country_data : country.data.test\n"
        "{\n"
        "\tcountry_id: 99\n"
        '\tname: "Testland"\n'
        "\tiso_country_code: tst\n"
        "\tfuel_price: 1.5\n"
        "\tmass_limit_per_axle_count: 4\n"
        "\tmass_limit_per_axle_count[2]: 36000\n"
        "\tmass_limit_per_axle_count[0]: 18000\n"
        "\tmass_limit_per_axle_count[3]: 40000\n"
        "\tmass_limit_per_axle_count[1]: 26000\n"
        "\tregions[]: central\n"
        "}\n"
    )
    parsed = parse_country_data(fixed_array_country)
    assert parsed.mass_limit_per_axle_count == [18000, 26000, 36000, 40000]
    assert parsed.regions == ["central"]

    patched = patch_country_data(
        fixed_array_country,
        CountryDataPatch(mass_limit_per_axle_count=[18000, 25000, 38000, 40000, 60000]),
    )
    assert "mass_limit_per_axle_count: 4" not in patched
    assert "mass_limit_per_axle_count[0]" not in patched
    assert "mass_limit_per_axle_count[3]" not in patched
    assert "\tregions[]: central\n" in patched

    reparsed = parse_country_data(patched)
    assert reparsed.mass_limit_per_axle_count == [18000, 25000, 38000, 40000, 60000]
    assert reparsed.regions == ["central"]

    # Pass 2 zero-diff idempotency
    assert (
        patch_country_data(
            patched, CountryDataPatch(mass_limit_per_axle_count=[18000, 25000, 38000, 40000, 60000])
        )
        == patched
    )


def test_patch_country_data_escapes_newlines_tabs_quotes_and_rejects_backslash_nul() -> None:
    base = (
        "country_data : country.data.test\n"
        "{\n"
        "\tcountry_id: 1\n"
        "\tfuel_price: 1.85\n"
        '\ttime_zone_name: "@@tz_cet@@"\n'
        "}\n"
    )
    injected = '@@tz_cet@@"\n\tfuel_price: 0.01'
    patched = patch_country_data(base, CountryDataPatch(time_zone_name=injected))
    model = parse_country_data(patched)
    assert model.fuel_price == pytest.approx(1.85)
    assert model.time_zone_name == injected

    tabbed = patch_country_data(base, CountryDataPatch(time_zone_name="tz\r\tname"))
    assert "\\r\\t" in tabbed
    assert parse_country_data(tabbed).time_zone_name == "tz\r\tname"

    for bad in ("bad\\slash", "bad\x00nul"):
        with pytest.raises(ValueError):
            patch_country_data(base, CountryDataPatch(time_zone_name=bad))


def test_patch_country_data_duplicate_scalar_uses_last_wins() -> None:
    dup_country = (
        "country_data : country.data.dup\n"
        "{\n"
        "\tcountry_id: 5\n"
        "\tfuel_price: 1.11\n"
        "\tfuel_price: 2.22\n"
        "}\n"
    )
    assert parse_country_data(dup_country).fuel_price == pytest.approx(2.22)
    patched = patch_country_data(dup_country, CountryDataPatch(fuel_price=3.33))
    assert parse_country_data(patched).fuel_price == pytest.approx(3.33)
    assert "\tfuel_price: 1.11\n" in patched
    assert "\tfuel_price: 3.33\n" in patched
