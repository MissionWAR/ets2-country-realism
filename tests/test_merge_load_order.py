"""Unit and synthetic VFS tests for multi-source load-order resolution (MAP-03, D-09..D-11)."""

from __future__ import annotations

import pathlib
import struct
import zipfile

import pytest

from ets2v2.merge.load_order import (
    ETS2V2_MANIFEST_MARKER,
    MAX_TEXT_INPUT_BYTES,
    BaselineVirtualArchive,
    EncryptedProfileError,
    LoadOrderEntry,
    build_combo_vfs_stack,
    is_ets2v2_self_package,
    parse_game_log,
    parse_modlist,
    parse_profile_sii,
    resolve_workshop_dir,
    resolve_workshop_package_path,
)
from ets2v2.vfs.hashfs import open_archive
from ets2v2.vfs.types import VfsArchive


def _write_zip(dest: pathlib.Path, files: dict[str, bytes]) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, payload in sorted(files.items()):
            zf.writestr(rel, payload)
    return dest


def _write_encrypted_flag_zip(dest: pathlib.Path, files: dict[str, bytes]) -> pathlib.Path:
    """Create a ZIP with central-directory & local-header encryption flag bit (0x01) set."""
    _write_zip(dest, files)
    raw = bytearray(dest.read_bytes())

    # Set bit 0 (encrypted) in every local file header (PK\x03\x04, flag offset +6)
    pos = 0
    while True:
        idx = raw.find(b"PK\x03\x04", pos)
        if idx == -1:
            break
        flags = struct.unpack_from("<H", raw, idx + 6)[0]
        struct.pack_into("<H", raw, idx + 6, flags | 0x01)
        pos = idx + 4

    # Set bit 0 (encrypted) in every central directory header (PK\x01\x02, flag offset +8)
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


def test_parse_profile_sii_priority_order_and_workshop_hex(tmp_path: pathlib.Path) -> None:
    profile = tmp_path / "profile.sii"
    profile.write_text(
        "SiiNunit\n"
        "{\n"
        "user_profile : _nameless.1\n"
        "{\n"
        " active_mods: 4\n"
        ' active_mods[0]: "RusMap_Def [EVO3]|RusMap Def"\n'
        ' active_mods[1]: "gmc.beyond.fix|GMC Beyond Fix"\n'
        ' active_mods[2]: "My Map (1)|My Map"\n'
        ' active_mods[3]: "mod_workshop_package.00000000CE350CEA|Steam Mod"\n'
        "}\n"
        "}\n",
        encoding="utf-8",
        newline="\n",
    )

    entries = parse_profile_sii(profile)
    assert [e.package_name for e in entries] == [
        "RusMap_Def [EVO3]",
        "gmc.beyond.fix",
        "My Map (1)",
        "mod_workshop_package.00000000CE350CEA",
    ]
    assert [e.display_name for e in entries] == [
        "RusMap Def",
        "GMC Beyond Fix",
        "My Map",
        "Steam Mod",
    ]
    assert [e.source for e in entries] == ["local", "local", "local", "workshop"]
    assert entries[3].workshop_id == "3459583210"


def test_parse_profile_sii_refuses_scsc_encrypted(tmp_path: pathlib.Path) -> None:
    profile = tmp_path / "profile.sii"
    profile.write_bytes(b"ScsC\x00\x00\x00\x00encrypted_payload_bytes")

    with pytest.raises(EncryptedProfileError) as exc_info:
        parse_profile_sii(profile)

    msg = str(exc_info.value)
    assert "--game-log" in msg
    assert "g_save_format" in msg


def test_resolve_workshop_versions_sii_prefers_162_over_universal_and_skips_info(
    tmp_path: pathlib.Path,
) -> None:
    workshop_dir = tmp_path / "227300"
    item_162 = workshop_dir / "3459583210"
    item_162.mkdir(parents=True)
    (item_162 / "versions.sii").write_text(
        "SiiNunit\n"
        "{\n"
        "package_version_info : .info\n"
        "{\n"
        '\tpackage_name: "readme_only"\n'
        "\tinformational: true\n"
        "}\n"
        "package_version_info : .universal\n"
        "{\n"
        '\tpackage_name: "universal"\n'
        "}\n"
        "package_version_info : .v162\n"
        "{\n"
        '\tpackage_name: "pkg_162"\n'
        '\tcompatible_versions[]: "1.62.*"\n'
        "}\n"
        "}\n",
        encoding="utf-8",
        newline="\n",
    )
    (item_162 / "universal").mkdir()
    _write_zip(item_162 / "pkg_162.zip", {"manifest.sii": b"SiiNunit\n{\n}\n"})

    resolved_162 = resolve_workshop_package_path("3459583210", workshop_dir)
    assert resolved_162 == (item_162 / "pkg_162.zip").resolve()

    # Fallback to universal when 1.62.* is absent (still skipping informational: true)
    item_univ = workshop_dir / "111222333"
    item_univ.mkdir(parents=True)
    (item_univ / "versions.sii").write_text(
        "SiiNunit\n"
        "{\n"
        "package_version_info : .info\n"
        "{\n"
        '\tpackage_name: "info_pkg"\n'
        "\tinformational: true\n"
        "}\n"
        "package_version_info : .old\n"
        "{\n"
        '\tpackage_name: "old_150"\n'
        '\tcompatible_versions[]: "1.50.*"\n'
        "}\n"
        "package_version_info : .univ\n"
        "{\n"
        '\tpackage_name: "universal"\n'
        "}\n"
        "}\n",
        encoding="utf-8",
        newline="\n",
    )
    (item_univ / "universal").mkdir()
    resolved_univ = resolve_workshop_package_path("111222333", workshop_dir)
    assert resolved_univ == (item_univ / "universal").resolve()


def test_resolve_workshop_rejects_traversal_package_name(tmp_path: pathlib.Path) -> None:
    workshop_dir = tmp_path / "227300"
    item_dir = workshop_dir / "9999"
    item_dir.mkdir(parents=True)
    (item_dir / "versions.sii").write_text(
        'SiiNunit\n{\npackage_version_info : .bad\n{\n\tpackage_name: "../../escape"\n}\n}\n',
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ValueError, match=r"Unsafe|escapes|traversal"):
        resolve_workshop_package_path("9999", workshop_dir)


def test_parse_game_log_ignores_startup_scan_and_takes_last_session(
    tmp_path: pathlib.Path,
) -> None:
    log_file = tmp_path / "game.log.txt"
    log_file.write_text(
        # Startup scan noise (must NOT be treated as active profile mods!)
        "00:00:01.000 : [zipfs] D:\\ETS2\\mod\\unused_scan_mod.scs: Created, 120 entries\n"
        "00:00:01.010 : [fs] device D:\\ETS2\\mod\\unused_scan_mod.scs mounted.\n"
        "00:00:01.020 : [zipfs] D:\\ETS2\\mod\\unused_scan_mod.scs: Unmounted\n"
        "00:00:01.030 : [hashfs] /home/user/.local/share/ETS2/mod/unused.scs: Created, 10\n"
        # Session 1 (older profile before switch)
        '00:00:05.000 : [mod_package_manager] Mod "Old Base" has been mounted. '
        "(package_name: old_base_mod, version: 1.0, source: Local)\n"
        # Profile switch boundary
        '00:00:10.000 : [mod_package_manager] Mod "Old Base" has been unmounted. '
        "(package_name: old_base_mod)\n"
        # Session 2 (final active profile — lowest priority mounted first)
        '00:00:12.000 : [mod_package_manager] Mod "RusMap (1)" has been mounted. '
        "(package_name: RusMap_Def (1), version: 2.52, source: Local)\n"
        '00:00:12.010 : [mod_package_manager] Mod "GMC Beyond Fix" has been mounted. '
        "(package_name: gmc.beyond.fix, version: 1.2, source: Local)\n"
        '00:00:12.020 : [mod_package_manager] Mod "Steam Workshop Addon" has been mounted. '
        "(package_name: mod_workshop_package.00000000CE350CEA, "
        "version: 1.0, source: Steam Workshop)\n"
        # Shutdown unmount at game exit must NOT erase the final active session!
        '00:05:00.000 : [mod_package_manager] Mod "Steam Workshop Addon" has been unmounted.\n',
        encoding="utf-8",
        newline="\n",
    )

    entries = parse_game_log(log_file)
    assert [e.package_name for e in entries] == [
        "RusMap_Def (1)",
        "gmc.beyond.fix",
        "mod_workshop_package.00000000CE350CEA",
    ]
    assert entries[2].source == "workshop"
    assert entries[2].workshop_id == "3459583210"


def test_parse_modlist_top_to_bottom_and_bottom_to_top(tmp_path: pathlib.Path) -> None:
    modlist = tmp_path / "mods.txt"
    modlist.write_text(
        "# Highest priority in Mod Manager\n"
        "\n"
        "gmc.beyond.fix.scs\n"
        "workshop:3459583210\n"
        "RusMap_Def\n",
        encoding="utf-8",
        newline="\n",
    )

    top_down = parse_modlist(modlist, order="top-to-bottom")
    assert [e.package_name for e in top_down] == [
        "RusMap_Def",
        "mod_workshop_package.00000000CE350CEA",
        "gmc.beyond.fix",
    ]
    assert top_down[1].source == "workshop"
    assert top_down[1].workshop_id == "3459583210"

    bottom_up = parse_modlist(modlist, order="bottom-to-top")
    assert [e.package_name for e in bottom_up] == [
        "gmc.beyond.fix",
        "mod_workshop_package.00000000CE350CEA",
        "RusMap_Def",
    ]


def test_self_exclusion_skips_filename_patterns_and_renamed_manifest_marker(
    tmp_path: pathlib.Path,
) -> None:
    mod_dir = tmp_path / "mod"
    mod_dir.mkdir()

    combo_scs = _write_zip(mod_dir / "zz_ETS2V2_ComboPatch_Summer.scs", {"def/x.sii": b"a"})
    core_zip = _write_zip(mod_dir / "ETS2V2_Core_Summer.zip", {"def/x.sii": b"a"})
    promods_zip = _write_zip(mod_dir / "ETS2V2_ProMods_Winter.zip", {"def/x.sii": b"a"})
    renamed_self = _write_zip(
        mod_dir / "my_custom_patch.scs",
        {
            "manifest.sii": (
                f"SiiNunit\n{{\n{ETS2V2_MANIFEST_MARKER} kind=combo\n"
                'mod_package : .package_name\n{\n\tauthor: "ETS2"\n}\n}\n'
            ).encode()
        },
    )
    normal_mod = _write_zip(
        mod_dir / "real_map.scs",
        {"def/country/germany.sui": b"country_data : country.data.germany { }\n"},
    )

    with open_archive(renamed_self) as arch:
        is_self, reason = is_ets2v2_self_package(renamed_self, arch)
        assert is_self is True
        assert reason == "manifest_marker"

    entries = [
        LoadOrderEntry(package_name=p.stem, source="local", raw_spec=p.name)
        for p in (normal_mod, core_zip, promods_zip, combo_scs, renamed_self)
    ]

    with build_combo_vfs_stack(entries, mod_dir=mod_dir) as res:
        assert len(res.resolved_entries) == 1
        assert res.resolved_entries[0].package_name == "real_map"
        assert {ex.package_name for ex in res.excluded_self_packages} == {
            "ETS2V2_Core_Summer",
            "ETS2V2_ProMods_Winter",
            "zz_ETS2V2_ComboPatch_Summer",
            "my_custom_patch",
        }
        renamed_rec = next(
            ex for ex in res.excluded_self_packages if ex.package_name == "my_custom_patch"
        )
        assert renamed_rec.reason == "manifest_marker"


def test_protected_archives_and_smart_unpacked_defs_in_place_priority(
    tmp_path: pathlib.Path,
) -> None:
    mod_dir = tmp_path / "mod"
    mod_dir.mkdir()

    # Priority 1: AEM! protected archive
    aem_path = mod_dir / "Locked_AEM_Map.scs"
    aem_path.write_bytes(b"AEM!\x00\x01\x02\x03protected_payload")

    # Priority 2: Password-encrypted ZIP with visible def/country* and def/sign/board* paths
    enc_zip = _write_encrypted_flag_zip(
        mod_dir / "Beyond_by_TerraMaps_1.scs",
        {
            "def/country.beyond.sii": b'SiiNunit\n{\n@include "country/beyond_country.sui"\n}\n',
            "def/country/beyond_country.sui": b"country_data : country.data.beyond_country { }\n",
            "def/sign/board/beyond_gas.sii": b"SiiNunit\n{\n}\n",
            "material/unrelated.mat": b"mat",
        },
    )

    # Priority 3: Higher plain-ZIP fix pack overriding beyond_country.sui
    fix_zip = _write_zip(
        mod_dir / "gmc.beyond.fix.scs",
        {
            "def/country/beyond_country.sui": (
                b'country_data : country.data.beyond_country\n{\n\tname: "FixWinner"\n}\n'
            )
        },
    )

    # Priority 4: 3nK obfuscated country file in plain ZIP
    three_nk_zip = _write_zip(
        mod_dir / "Obfuscated_3nK.scs",
        {"def/country/obf.sui": b"3nK\x01\x00\x01obfuscated"},
    )

    entries = [
        LoadOrderEntry(package_name=p.stem, source="local", raw_spec=p.name)
        for p in (aem_path, enc_zip, fix_zip, three_nk_zip)
    ]

    # Run 1: Without --unpacked-defs -> diagnostics populated without crashing or decrypting
    with build_combo_vfs_stack(entries, mod_dir=mod_dir) as res:
        by_layer = {d.layer_name: d for d in res.protected_archives}
        assert "Locked_AEM_Map.scs" in by_layer
        assert by_layer["Locked_AEM_Map.scs"].protection_kind == "aem_protected"

        assert "Beyond_by_TerraMaps_1.scs" in by_layer
        beyond_diag = by_layer["Beyond_by_TerraMaps_1.scs"]
        assert beyond_diag.protection_kind == "encrypted_zip"
        assert "def/country.beyond.sii" in beyond_diag.visible_relevant_paths
        assert "def/country/beyond_country.sui" in beyond_diag.visible_relevant_paths
        assert "def/sign/board/beyond_gas.sii" in beyond_diag.visible_relevant_paths
        assert "material/unrelated.mat" not in beyond_diag.visible_relevant_paths
        assert beyond_diag.substituted_by is None

        assert "Obfuscated_3nK.scs" in by_layer
        assert by_layer["Obfuscated_3nK.scs"].protection_kind == "three_nk_obfuscated"
        assert "def/country/obf.sui" in by_layer["Obfuscated_3nK.scs"].visible_relevant_paths

    # Run 2: Smart repeatable --unpacked-defs:
    # (a) Stem-matched child dir substitutes Beyond_by_TerraMaps_1 IN-PLACE at priority 2,
    #     so gmc.beyond.fix at priority 3 STILL overrides beyond_country.sui!
    # (b) Raw def/ override dir mounts ABOVE priority 4.
    unpacked_parent = tmp_path / "unpacked_stems"
    sub_beyond = unpacked_parent / "Beyond_by_TerraMaps_1" / "def" / "country"
    sub_beyond.mkdir(parents=True)
    (sub_beyond / "beyond_country.sui").write_text(
        'country_data : country.data.beyond_country\n{\n\tname: "UnpackedBase"\n}\n',
        encoding="utf-8",
        newline="\n",
    )
    (sub_beyond / "beyond_only.sui").write_text(
        'country_data : country.data.beyond_only\n{\n\tname: "FromUnpacked"\n}\n',
        encoding="utf-8",
        newline="\n",
    )

    raw_override = tmp_path / "raw_override"
    (raw_override / "def" / "country").mkdir(parents=True)
    (raw_override / "def" / "country" / "top_override.sui").write_text(
        'country_data : country.data.top_override\n{\n\tname: "TopOverride"\n}\n',
        encoding="utf-8",
        newline="\n",
    )

    with build_combo_vfs_stack(
        entries,
        mod_dir=mod_dir,
        unpacked_defs=[unpacked_parent, raw_override],
    ) as res:
        # Higher-priority fix pack STILL wins over in-place substituted Beyond_by_TerraMaps_1!
        assert b"FixWinner" in res.stack.read_bytes("def/country/beyond_country.sui")
        # Non-overridden file from in-place substitution IS readable!
        assert b"FromUnpacked" in res.stack.read_bytes("def/country/beyond_only.sui")
        # Raw override dir mounted cleanly at top
        assert b"TopOverride" in res.stack.read_bytes("def/country/top_override.sui")
        assert res.unpacked_overrides == [raw_override]

        beyond_diag = next(
            d for d in res.protected_archives if d.layer_name == "Beyond_by_TerraMaps_1.scs"
        )
        assert beyond_diag.substituted_by == (unpacked_parent / "Beyond_by_TerraMaps_1")


def test_baseline_virtual_archive_fallback_provides_all_36_vanilla_countries() -> None:
    archive = BaselineVirtualArchive.from_baseline_dir(pathlib.Path("data/baselines/ets2_1.62_def"))
    assert isinstance(archive, VfsArchive)
    assert archive.exists("def/country.sii")

    sui_paths = [
        p for p in archive.list_paths(["def/country"]) if p.endswith(".sui") and p.count("/") == 2
    ]
    speed_paths = [
        p for p in archive.list_paths(["def/country"]) if p.endswith("/speed_limits.sii")
    ]
    assert len(sui_paths) == 36
    assert len(speed_paths) == 36

    with build_combo_vfs_stack([]) as res:
        assert res.base_layer_name == "vanilla_baseline_1_62"
        assert res.stack.exists("def/country/germany.sui")
        assert res.stack.exists("def/country/uk/speed_limits.sii")


def test_resolve_workshop_dir_explicit_and_env(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = tmp_path / "custom_ws"
    assert resolve_workshop_dir(explicit) == explicit

    env_ws = tmp_path / "env_ws"
    monkeypatch.setenv("ETS2_WORKSHOP_DIR", str(env_ws))
    assert resolve_workshop_dir() == env_ws


def test_text_input_size_cap_constant_enforced(tmp_path: pathlib.Path) -> None:
    assert MAX_TEXT_INPUT_BYTES == 64 * 1024 * 1024
    # Verify normal empty modlist works without error
    empty_ml = tmp_path / "empty.txt"
    empty_ml.write_text("# comment only\n\n", encoding="utf-8", newline="\n")
    assert parse_modlist(empty_ml) == []


def test_encrypted_zip_overridden_by_higher_layer_flag(tmp_path: pathlib.Path) -> None:
    mod_dir = tmp_path / "mod"
    mod_dir.mkdir()

    enc = _write_encrypted_flag_zip(
        mod_dir / "Beyond_Base.scs",
        {"def/country/foo.sui": b"country_data : country.data.foo { }\n"},
    )
    fix = _write_zip(
        mod_dir / "Beyond_Fix.scs",
        {"def/country/foo.sui": b'country_data : country.data.foo\n{\n\tname: "Plain"\n}\n'},
    )
    entries = [
        LoadOrderEntry(package_name=enc.stem, source="local", raw_spec=enc.name),
        LoadOrderEntry(package_name=fix.stem, source="local", raw_spec=fix.name),
    ]
    with build_combo_vfs_stack(entries, mod_dir=mod_dir) as res:
        assert len(res.protected_archives) == 1
        assert res.protected_archives[0].overridden_by_higher_layer is True


def test_hi01_profile_and_game_log_cannot_escape_mod_dir(tmp_path: pathlib.Path) -> None:
    outside_dir = tmp_path / "outside_secret"
    outside_dir.mkdir()
    _write_zip(
        outside_dir / "escaped.scs",
        {"def/country/escaped.sui": b"country_data : country.data.escaped { }\n"},
    )
    mod_dir = tmp_path / "mod"
    mod_dir.mkdir()

    # 1. profile.sii with traversal token (no |Display) must remain source="local" and not mount
    profile = tmp_path / "profile.sii"
    profile.write_text(
        "SiiNunit\n{\nuser_profile : _nameless.1\n{\n"
        ' active_mods[0]: "../outside_secret/escaped.scs"\n'
        "}\n}\n",
        encoding="utf-8",
        newline="\n",
    )
    prof_entries = parse_profile_sii(profile)
    assert len(prof_entries) == 1
    assert prof_entries[0].source == "local"
    with build_combo_vfs_stack(prof_entries, mod_dir=mod_dir) as res:
        assert res.resolved_entries == []
        assert len(res.missing_entries) == 1
        assert not res.stack.exists("def/country/escaped.sui")

    # 2. game.log.txt mount line omitting ", source: ..." must remain source="local" and not mount
    log_file = tmp_path / "game.log.txt"
    log_file.write_text(
        '00:00:12.000 : [mod_package_manager] Mod "Escape" has been mounted. '
        "(package_name: ../outside_secret/escaped.scs)\n",
        encoding="utf-8",
        newline="\n",
    )
    log_entries = parse_game_log(log_file)
    assert len(log_entries) == 1
    assert log_entries[0].source == "local"
    with build_combo_vfs_stack(log_entries, mod_dir=mod_dir) as res:
        assert res.resolved_entries == []
        assert len(res.missing_entries) == 1
        assert not res.stack.exists("def/country/escaped.sui")


def test_hi01_unc_nul_and_modlist_relative_traversal_rejected(tmp_path: pathlib.Path) -> None:
    mod_dir = tmp_path / "mod"
    (mod_dir / "sub").mkdir(parents=True)
    sub_mod = _write_zip(
        mod_dir / "sub" / "nested.scs",
        {"def/country/nested.sui": b"country_data : country.data.nested { }\n"},
    )
    abs_mod = _write_zip(
        tmp_path / "abs_pack" / "direct.scs",
        {"def/country/direct.sui": b"country_data : country.data.direct { }\n"},
    )
    _write_zip(
        tmp_path / "outside.scs",
        {"def/country/outside.sui": b"country_data : country.data.outside { }\n"},
    )

    # UNC paths and NUL bytes rejected in parse_modlist / parse_profile_sii / parse_game_log
    for bad_spec in (
        r"\\attacker-host\share\mod.scs",
        "//attacker-host/share/mod.scs",
        "bad\x00mod.scs",
    ):
        ml_bad = tmp_path / "bad_modlist.txt"
        ml_bad.write_text(f"{bad_spec}\n", encoding="utf-8", newline="\n")
        with pytest.raises(ValueError, match="Unsafe or UNC"):
            parse_modlist(ml_bad)

        gl_bad = tmp_path / "bad_game.log.txt"
        gl_bad.write_text(
            f'00:00:01.000 : [mod_package_manager] Mod "Bad" has been mounted. '
            f"(package_name: {bad_spec})\n",
            encoding="utf-8",
            newline="\n",
        )
        with pytest.raises(ValueError, match="Unsafe or UNC"):
            parse_game_log(gl_bad)

    # Relative escape in --modlist rejected by build_combo_vfs_stack
    ml_escape = tmp_path / "escape_modlist.txt"
    ml_escape.write_text("../outside.scs\n", encoding="utf-8", newline="\n")
    escape_entries = parse_modlist(ml_escape)
    assert escape_entries[0].source == "explicit_path"
    with pytest.raises(ValueError, match="escapes --mod-dir"):
        build_combo_vfs_stack(escape_entries, mod_dir=mod_dir)

    # Direct LoadOrderEntry UNC explicit_path rejected in resolver
    unc_entry = LoadOrderEntry(
        package_name="mod",
        source="explicit_path",
        raw_spec=r"\\attacker-host\share\mod.scs",
    )
    with pytest.raises(ValueError, match="Unsafe or UNC"):
        build_combo_vfs_stack([unc_entry], mod_dir=mod_dir)

    # Contained relative path inside mod_dir AND explicit local absolute path both succeed
    ml_ok = tmp_path / "ok_modlist.txt"
    ml_ok.write_text(
        f"sub/nested.scs\n{abs_mod}\n",
        encoding="utf-8",
        newline="\n",
    )
    ok_entries = parse_modlist(ml_ok)
    with build_combo_vfs_stack(ok_entries, mod_dir=mod_dir) as res:
        assert {e.resolved_path for e in res.resolved_entries} == {sub_mod.resolve(), abs_mod}
        assert res.stack.exists("def/country/nested.sui")
        assert res.stack.exists("def/country/direct.sui")


def test_hi02_combo_scoped_archive_exposes_nested_wrapper_includes(tmp_path: pathlib.Path) -> None:
    from ets2v2.merge.scanner import scan_active_countries

    mod_dir = tmp_path / "mod"
    mod_dir.mkdir()
    wrapper_zip = _write_zip(
        mod_dir / "nested_wrapper.scs",
        {
            "def/country.wrap.sii": b'SiiNunit\n{\n@include "country_wrap_list.sui"\n}\n',
            "def/country_wrap_list.sui": b'@include "country/subdir/sublist.sii"\n',
            "def/country/subdir/sublist.sii": b'@include "/def/country/mytest.sui"\n',
            "def/country/mytest.sui": (
                b"country_data : country.data.mytest\n"
                b"{\n"
                b"\tcountry_id: 777\n"
                b'\tname: "MyTest"\n'
                b'\tcountry_code: "D"\n'
                b"\tiso_country_code: deu\n"
                b"\tfuel_price: 1.50\n"
                b"}\n"
            ),
        },
    )
    entries = [
        LoadOrderEntry(package_name="nested_wrapper", source="local", raw_spec=wrapper_zip.name)
    ]
    with build_combo_vfs_stack(entries, mod_dir=mod_dir) as res:
        scan = scan_active_countries(res.stack)
        assert "mytest" in {c.slug for c in scan.countries}
        assert not [d for d in scan.diagnostics if d.kind == "missing_include_target"]


def test_md07_resolve_workshop_rejects_versions_sii_symlink_escape(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workshop_dir = tmp_path / "227300"
    item_dir = workshop_dir / "88888"
    item_dir.mkdir(parents=True)
    outside_versions = tmp_path / "outside_versions.sii"
    outside_versions.write_text(
        'SiiNunit\n{\npackage_version_info : .u\n{\n\tpackage_name: "universal"\n}\n}\n',
        encoding="utf-8",
        newline="\n",
    )
    versions_path = item_dir / "versions.sii"

    try:
        versions_path.symlink_to(outside_versions)
    except OSError:
        # Windows without symlink privilege: simulate symlink resolution escape cleanly
        versions_path.write_text(outside_versions.read_text("utf-8"), encoding="utf-8")
        orig_resolve = pathlib.Path.resolve

        def fake_resolve(self: pathlib.Path, strict: bool = False) -> pathlib.Path:
            if self.name == "versions.sii" and self.parent == item_dir.resolve():
                return outside_versions.resolve()
            return orig_resolve(self, strict=strict)

        monkeypatch.setattr(pathlib.Path, "resolve", fake_resolve)

    with pytest.raises(ValueError, match=r"versions\.sii escapes item directory"):
        resolve_workshop_package_path("88888", workshop_dir)
