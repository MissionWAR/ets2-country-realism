"""Synthetic multi-map VFS scanner tests (.sui/.sii, base/, empty stubs, protected layers)."""

from __future__ import annotations

import pathlib
import struct
import zipfile

from ets2v2.merge.scanner import (
    ComboScanResult,
    ScannedMapCountry,
    scan_active_countries,
)
from ets2v2.vfs.stack import VfsStack


def _write_zip(dest: pathlib.Path, files: dict[str, bytes]) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, payload in sorted(files.items()):
            zf.writestr(rel, payload)
    return dest


def _write_encrypted_flag_zip(dest: pathlib.Path, files: dict[str, bytes]) -> pathlib.Path:
    _write_zip(dest, files)
    raw = bytearray(dest.read_bytes())

    pos = 0
    while True:
        idx = raw.find(b"PK\x03\x04", pos)
        if idx == -1:
            break
        flags = struct.unpack_from("<H", raw, idx + 6)[0]
        struct.pack_into("<H", raw, idx + 6, flags | 0x01)
        pos = idx + 4

    pos = 0
    while True:
        idx = raw.find(b"PK\x01\x02", pos)
        if idx == -1:
            break
        flags = struct.unpack_from("<H", raw, idx + 8)[0]
        struct.pack_into("<H", raw, idx + 8, flags | 0x01)
        pos = idx + 4

    dest.write_bytes(bytes(raw))
    return dest


def _country_sui(
    slug: str,
    *,
    country_id: int,
    name: str,
    code: str,
    iso3: str,
    wrap_siinunit: bool = False,
) -> bytes:
    body = (
        f"country_data : country.data.{slug}\n"
        "{\n"
        f"\tcountry_id: {country_id}\n"
        f'\tname: "{name}"\n'
        f'\tcountry_code: "{code}"\n'
        f"\tiso_country_code: {iso3}\n"
        "\tfuel_price: 1.50\n"
        "\tlights_mandatory: false\n"
        "\ttime_zone: 60\n"
        '\ttime_zone_name: "CET"\n'
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 36000\n"
        "}\n"
    )
    if wrap_siinunit:
        body = f"SiiNunit\n{{\n{body}}}\n"
    return body.encode("utf-8")


def _speed_limits_sii() -> bytes:
    return (
        b"SiiNunit\n"
        b"{\n"
        b"country_speed_limit : .speed_limit.car\n"
        b"{\n"
        b"\tvehicle_speed_class: car\n"
        b"\tlane_speed_class[]: local_road\n"
        b"\tlimit[]: 80\n"
        b"\turban_limit[]: 50\n"
        b"}\n"
        b"}\n"
    )


def test_scanner_handles_headerless_and_wrapped_sii_fragments_and_sui(
    tmp_path: pathlib.Path,
) -> None:
    # Real-world SEA / RoC / Project Japan @include-targeted .sii fragments are headerless,
    # while some mods may wrap a .sii fragment in SiiNunit { ... }.
    mod_zip = _write_zip(
        tmp_path / "asia_combo.scs",
        {
            "def/country.sii": (b'SiiNunit\n{\n@include "country/germany.sui"\n}\n'),
            "def/country.sea.sii": (
                b"SiiNunit\n{\n"
                b'@include "country/thailand.sii"\n'
                b'@include "country/taiwan.sii"\n'
                b'@include "country/aichi.sii"\n'
                b'@include "country/wrapped_land.sii"\n'
                b"}\n"
            ),
            "def/country/germany.sui": _country_sui(
                "germany", country_id=3, name="Germany", code="D", iso3="deu"
            ),
            "def/country/germany/speed_limits.sii": _speed_limits_sii(),
            "def/country/thailand.sii": _country_sui(
                "thailand", country_id=201, name="Thailand", code="TH", iso3="tha"
            ),
            "def/country/taiwan.sii": _country_sui(
                "taiwan", country_id=202, name="Taiwan", code="TW", iso3="twn"
            ),
            "def/country/aichi.sii": _country_sui(
                "aichi", country_id=203, name="Aichi", code="JP", iso3="jpn"
            ),
            "def/country/wrapped_land.sii": _country_sui(
                "wrapped_land",
                country_id=204,
                name="Wrapped",
                code="WL",
                iso3="wld",
                wrap_siinunit=True,
            ),
            # Dead unincluded file sitting in def/country/ must NEVER be scanned or emitted!
            "def/country/unused_country.sui": _country_sui(
                "unused_country", country_id=999, name="Unused", code="ZZ", iso3="zzz"
            ),
        },
    )

    with VfsStack.from_paths([mod_zip]) as stack:
        result: ComboScanResult = scan_active_countries(stack)

    by_slug: dict[str, ScannedMapCountry] = {c.slug: c for c in result.countries}
    assert set(by_slug.keys()) == {"germany", "thailand", "taiwan", "aichi", "wrapped_land"}
    assert "unused_country" not in by_slug

    assert by_slug["germany"].fragment_path == "def/country/germany.sui"
    assert by_slug["germany"].is_sii_fragment is False
    assert by_slug["germany"].has_siinunit_envelope is False
    assert by_slug["germany"].speed_limits_path == "def/country/germany/speed_limits.sii"
    assert by_slug["germany"].speed_limits_layer == "asia_combo.scs"
    assert by_slug["germany"].speed_limits_raw is not None

    for slug in ("thailand", "taiwan", "aichi"):
        assert by_slug[slug].fragment_path == f"def/country/{slug}.sii"
        assert by_slug[slug].is_sii_fragment is True
        assert by_slug[slug].has_siinunit_envelope is False
        assert by_slug[slug].speed_limits_path is None
        assert by_slug[slug].speed_limits_raw is None

    assert by_slug["wrapped_land"].is_sii_fragment is True
    assert by_slug["wrapped_land"].has_siinunit_envelope is True


def test_scanner_flattens_eaa_base_mount_prefix(tmp_path: pathlib.Path) -> None:
    eaa_zip = _write_zip(
        tmp_path / "eaa_rescaled.scs",
        {
            "base/def/country.eaa.sii": (b'SiiNunit\n{\n@include "country/brasil.sui"\n}\n'),
            "base/def/country/brasil.sui": _country_sui(
                "brasil", country_id=55, name="Brasil", code="BR", iso3="bra"
            ),
            "base/def/country/brasil/speed_limits.sii": _speed_limits_sii(),
        },
    )

    with VfsStack.from_paths([eaa_zip]) as stack:
        result = scan_active_countries(stack)

    assert len(result.countries) == 1
    br = result.countries[0]
    assert br.slug == "brasil"
    assert br.fragment_path == "def/country/brasil.sui"
    assert br.speed_limits_path == "def/country/brasil/speed_limits.sii"
    assert br.winning_layer == "eaa_rescaled.scs"


def test_scanner_honors_empty_siinunit_suppression_stubs(tmp_path: pathlib.Path) -> None:
    lower_zip = _write_zip(
        tmp_path / "map_7rm2.scs",
        {
            "def/country.7rm2.sii": (b'SiiNunit\n{\n@include "country/suppressed_only.sui"\n}\n'),
            "def/country.keep.sii": (b'SiiNunit\n{\n@include "country/kept.sui"\n}\n'),
            "def/country/suppressed_only.sui": _country_sui(
                "suppressed_only", country_id=301, name="Suppressed", code="SP", iso3="spp"
            ),
            "def/country/kept.sui": _country_sui(
                "kept", country_id=302, name="Kept", code="KP", iso3="kpt"
            ),
        },
    )
    umcf_stub_zip = _write_zip(
        tmp_path / "umcf_fix.scs",
        {
            "def/country.7rm2.sii": b"SiiNunit\n{\n# suppressed by UMCF\n}\n",
        },
    )

    with VfsStack.from_paths([lower_zip, umcf_stub_zip]) as stack:
        result = scan_active_countries(stack)

    assert [c.slug for c in result.countries] == ["kept"]
    assert len(result.suppressed_registration_files) == 1
    stub = result.suppressed_registration_files[0]
    assert stub.registration_path == "def/country.7rm2.sii"
    assert stub.layer_name == "umcf_fix.scs"


def test_scanner_survives_encrypted_and_3nk_payloads_and_cp1252_comments(
    tmp_path: pathlib.Path,
) -> None:
    # Lower encrypted registration + fragment
    enc_zip = _write_encrypted_flag_zip(
        tmp_path / "locked_map.scs",
        {
            "def/country.locked.sii": b'SiiNunit\n{\n@include "country/secret.sui"\n}\n',
            "def/country/secret.sui": _country_sui(
                "secret", country_id=401, name="Secret", code="SC", iso3="sec"
            ),
        },
    )
    # Readable layer with 3nK fragment + cp1252 comment in registration (like ProMods ME 2.85)
    mixed_zip = _write_zip(
        tmp_path / "mixed_map.scs",
        {
            "def/country.mideast.sii": (
                b"SiiNunit\n{\n# Legacy cp1252 comment: \xc5land\n"
                b'@include "country/jordan.sui"\n'
                b'@include "country/obf_3nk.sui"\n}\n'
            ),
            "def/country/jordan.sui": _country_sui(
                "jordan", country_id=63, name="Jordan", code="JO", iso3="jor"
            ),
            "def/country/obf_3nk.sui": b"3nK\x01\x00\x01obfuscated_country",
        },
    )

    with VfsStack.from_paths([enc_zip, mixed_zip]) as stack:
        result = scan_active_countries(stack)

    assert [c.slug for c in result.countries] == ["jordan"]
    diag_kinds = {d.kind for d in result.diagnostics}
    assert "protected_payload" in diag_kinds
    assert "three_nk_obfuscated" in diag_kinds


def test_scanner_guards_against_include_cycles(tmp_path: pathlib.Path) -> None:
    cyclic_zip = _write_zip(
        tmp_path / "cyclic.scs",
        {
            "def/country.cyc.sii": b'SiiNunit\n{\n@include "country/loop_a.sii"\n}\n',
            "def/country/loop_a.sii": b'@include "loop_b.sii"\n',
            "def/country/loop_b.sii": b'@include "loop_a.sii"\n',
        },
    )
    # Also test wrapper cycle outside def/country/<slug>
    wrapper_zip = _write_zip(
        tmp_path / "wrap_cycle.scs",
        {
            "def/country.wrap.sii": b'SiiNunit\n{\n@include "sub/a.sii"\n}\n',
            "def/sub/a.sii": b'@include "b.sii"\n',
            "def/sub/b.sii": b'@include "a.sii"\n',
        },
    )

    with VfsStack.from_paths([cyclic_zip, wrapper_zip]) as stack:
        result = scan_active_countries(stack)

    assert any(d.kind == "include_cycle" for d in result.diagnostics)


def test_scanner_detects_active_promods_fuel_modules(tmp_path: pathlib.Path) -> None:
    pm_assets = _write_zip(
        tmp_path / "promods_assets_sim.scs",
        {
            "locale/en_gb/local_module.pm_fuel.sii": (
                b"SiiNunit\n{\nlocalization_db : .pm_fuel\n{\n}\n}\n"
            ),
            "locale/de_de/local_module.pm_me_fuel.sii": (
                b"SiiNunit\n{\nlocalization_db : .pm_me_fuel\n{\n}\n}\n"
            ),
            # Empty suppression stub must NOT be detected as active
            "locale/en_gb/local_module.pm_tgs_fuel.sii": b"SiiNunit\n{\n}\n",
        },
    )

    with VfsStack.from_paths([pm_assets]) as stack:
        result = scan_active_countries(stack)

    assert result.detected_promods_fuel_modules == ["pm_fuel", "pm_me_fuel"]
