"""Tests for multi-layer VfsStack overlay, base/ normalization, and empty SiiNunit {} stubs."""

from __future__ import annotations

import pathlib
import struct
import zipfile
import zlib

import pytest

import ets2v2.vfs.stack as stack_mod
from ets2v2.vfs import (
    DirectoryArchive,
    EffectiveVfsEntry,
    ProtectedPayloadError,
    VfsLayer,
    VfsStack,
    hash_vfs_path,
    is_empty_sii_stub,
    open_archive,
)


def _build_hashfs_v1_simple(
    dest: pathlib.Path,
    files: dict[str, bytes],
    dirs: dict[str, list[str]],
) -> pathlib.Path:
    chunks: list[bytes] = []
    cursor = 32
    records: list[tuple[int, int, int, int, int, int]] = []
    for dpath, items in dirs.items():
        raw = ("\n".join(items) + "\n").encode("utf-8") if items else b""
        zraw = zlib.compress(raw)
        records.append(
            (hash_vfs_path(dpath), cursor, 1 | 2, zlib.crc32(raw) & 0xFFFFFFFF, len(raw), len(zraw))
        )
        chunks.append(zraw)
        cursor += len(zraw)
    for fpath, raw in files.items():
        zraw = zlib.compress(raw)
        records.append(
            (hash_vfs_path(fpath), cursor, 2, zlib.crc32(raw) & 0xFFFFFFFF, len(raw), len(zraw))
        )
        chunks.append(zraw)
        cursor += len(zraw)
    records.sort(key=lambda r: r[0])
    header = struct.pack("<4sHH4sIQQ", b"SCS#", 1, 0, b"CITY", len(records), cursor, 0)
    entry_table = b"".join(struct.pack("<QQIIII", *r) for r in records)
    dest.write_bytes(header + b"".join(chunks) + entry_table)
    return dest


def _build_encrypted_single_zip(
    dest: pathlib.Path, entry_name: str, payload: bytes
) -> pathlib.Path:
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(entry_name, payload)
    raw = bytearray(dest.read_bytes())
    target = entry_name.encode("utf-8")
    lf_pos = raw.find(target)
    lf_hdr = raw.rfind(b"PK\x03\x04", 0, lf_pos)
    raw[lf_hdr + 6] |= 0x01
    cd_pos = raw.find(target, lf_pos + len(target))
    cd_hdr = raw.rfind(b"PK\x01\x02", 0, cd_pos)
    raw[cd_hdr + 8] |= 0x01
    dest.write_bytes(bytes(raw))
    return dest


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"SiiNunit { }", True),
        (b"\xef\xbb\xbfSiiNunit\r\n{\r\n}\r\n", True),
        (b"SiiNunit\n{\n\t# suppressed by UMCF\n\t// blank\n\t/* empty */\n}\n", True),
        (b"{ }", True),
        (b"{ /* nothing */ }", True),
        (b"", False),
        (b"   \n# only a comment\n", False),
        (b'SiiNunit\n{\n@include "country/beyond.sui"\n}\n', False),
        (b'SiiNunit\n{\ncomment: "/* not empty */"\n}\n', False),
        (b"SiiNunit\n{\ncountry_data : country.data.uk {\n}\n}\n", False),
        (b"3nK\x01\x00\x05\xff\xfe", False),
        (b"\xff\xfe\xfd", False),
    ],
)
def test_is_empty_sii_stub(raw: bytes, expected: bool) -> None:
    assert is_empty_sii_stub(raw) is expected


def test_vfs_stack_multi_layer_priority_base_dlc_and_empty_stub_shadowing(
    tmp_path: pathlib.Path,
) -> None:
    # Layer 0 (lowest): HashFS v1 base package
    base_v1 = _build_hashfs_v1_simple(
        tmp_path / "00_base.scs",
        files={
            "def/country/uk.sui": b"country_data : country.data.uk { fuel_price: 1.50 }\n",
            "def/country.beyond.sii": b'SiiNunit\n{\n@include "country/beyond.sui"\n}\n',
            "def/country/germany/speed_limits.sii": b"3nK\x01\x00\x09\xaa\xbb",
        },
        dirs={
            "": ["*def"],
            "def": ["country.beyond.sii", "*country"],
            "def/country": ["uk.sui", "*germany"],
            "def/country/germany": ["speed_limits.sii"],
        },
    )

    # Layer 1 (mid): ZIP package with base/ mount prefix and dlc_north/
    eaa_zip = tmp_path / "10_eaa_base.zip"
    with zipfile.ZipFile(eaa_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "base/def/country/uk.sui",
            b"country_data : country.data.uk { fuel_price: 1.65 }\n",
        )
        zf.writestr(
            "base/def/country.eaa.sii",
            b'SiiNunit\n{\n@include "country/brazil.sui"\n}\n',
        )
        zf.writestr(
            "dlc_north/def/country/norway/traffic.dlc_north.sii",
            b"SiiNunit\n{\ncountry_traffic_info : .dlc_north.info {}\n}\n",
        )

    # Layer 2 (high): Unpacked dir overriding def/country.beyond.sii with empty SiiNunit {} stub
    fix_dir = tmp_path / "20_umcf_fix"
    (fix_dir / "def").mkdir(parents=True)
    (fix_dir / "def" / "country.beyond.sii").write_text(
        "SiiNunit\n{\n  /* suppressed by combo fix */\n}\n",
        encoding="utf-8",
    )

    # Layer 3 (protected AEM! mod)
    aem_mod = tmp_path / "30_aem.scs"
    aem_mod.write_bytes(b"AEM!\x00\x00\x00\x01payload")

    # Layer 4 (encrypted ZIP mod)
    enc_zip = _build_encrypted_single_zip(
        tmp_path / "40_encrypted.scs",
        "def/country/locked.sui",
        b"locked",
    )

    stack = VfsStack.from_paths([base_v1, eaa_zip, fix_dir, aem_mod, enc_zip])

    # base/ normalized into canonical def/ paths, higher layer overrides lower layer
    uk_entry = stack.resolve("\\def\\country\\uk.sui")
    assert isinstance(uk_entry, EffectiveVfsEntry)
    assert uk_entry.canonical_path == "def/country/uk.sui"
    assert uk_entry.raw_path == "base/def/country/uk.sui"
    assert uk_entry.layer_name == "10_eaa_base.zip"
    assert uk_entry.priority == 1
    assert uk_entry.mount_scope == "base"
    assert uk_entry.is_empty_stub is False
    assert b"fuel_price: 1.65" in stack.read_bytes("/def/country/uk.sui")

    # Accessing with explicit base/ prefix resolves the normalized entry too
    assert stack.resolve("base/def/country.eaa.sii") == stack.resolve("def/country.eaa.sii")
    eaa_entry = stack.resolve("def/country.eaa.sii")
    assert eaa_entry is not None
    assert eaa_entry.mount_scope == "base"
    assert eaa_entry.raw_path == "base/def/country.eaa.sii"

    # Empty SiiNunit {} stub in higher layer shadows lower layer's @include declaration
    beyond_entry = stack.resolve("def/country.beyond.sii")
    assert beyond_entry is not None
    assert beyond_entry.layer_name == "20_umcf_fix"
    assert beyond_entry.mount_scope == "root"
    assert beyond_entry.is_empty_stub is True
    assert "@include" not in stack.read_text("def/country.beyond.sii")
    assert stack.empty_stub_paths() == ["def/country.beyond.sii"]

    # dlc_<id>/ is NOT flattened unconditionally into root by default
    assert stack.resolve("def/country/norway/traffic.dlc_north.sii") is None
    dlc_entry = stack.resolve("dlc_north/def/country/norway/traffic.dlc_north.sii")
    assert dlc_entry is not None
    assert dlc_entry.mount_scope == "dlc:north"

    # Canonical listing reflects merged overlay
    assert stack.list_paths("def") == [
        "def/country.beyond.sii",
        "def/country.eaa.sii",
        "def/country/germany/speed_limits.sii",
        "def/country/locked.sui",
        "def/country/uk.sui",
    ]

    # Reading 3nK payload returns raw bytes and flags three_nk_obfuscated
    raw_3nk = stack.read_bytes("def/country/germany/speed_limits.sii")
    assert raw_3nk.startswith(b"3nK\x01")
    with pytest.raises(ProtectedPayloadError):
        stack.read_text("def/country/germany/speed_limits.sii")

    # Reading encrypted ZIP winner raises ProtectedPayloadError cleanly
    with pytest.raises(ProtectedPayloadError):
        stack.read_bytes("def/country/locked.sui")

    # Diagnostics aggregated across all layers
    diag_kinds = {d.kind for d in stack.diagnostics()}
    assert {"aem_protected", "encrypted_zip", "three_nk_obfuscated"} <= diag_kinds


def test_vfs_stack_enabled_dlcs_and_manual_mount_order(tmp_path: pathlib.Path) -> None:
    mod_dir = tmp_path / "dlc_mod"
    (mod_dir / "base" / "def").mkdir(parents=True)
    (mod_dir / "dlc_balt" / "def").mkdir(parents=True)
    (mod_dir / "base" / "def" / "shared.sii").write_text("SiiNunit\n{\n}\n", encoding="utf-8")
    (mod_dir / "dlc_balt" / "def" / "shared.sii").write_text(
        'SiiNunit\n{\n@include "balt.sui"\n}\n',
        encoding="utf-8",
    )

    stack = VfsStack(enabled_dlcs={"dlc_balt"})
    stack.mount(open_archive(mod_dir), name="dlc_mod", priority=10)

    resolved = stack.resolve("def/shared.sii")
    assert resolved is not None
    assert resolved.mount_scope == "dlc:balt"
    assert resolved.raw_path == "dlc_balt/def/shared.sii"
    assert resolved.is_empty_stub is False
    assert stack.empty_stub_paths() == []


def test_vfs_stack_rejects_path_traversal(tmp_path: pathlib.Path) -> None:
    empty_dir = tmp_path / "empty_mod"
    empty_dir.mkdir()
    stack = VfsStack([VfsLayer(name="empty", priority=0, archive=open_archive(empty_dir))])
    with pytest.raises(ValueError):
        stack.resolve("../escape.sii")
    with pytest.raises(ValueError):
        stack.read_bytes("def/../../escape.sii")


def test_vfs_stack_higher_non_empty_layer_unsuppresses_empty_stub(
    tmp_path: pathlib.Path,
) -> None:
    low = tmp_path / "0_low"
    (low / "def").mkdir(parents=True)
    (low / "def" / "country.beyond.sii").write_text(
        'SiiNunit\n{\n@include "country/old.sui"\n}\n',
        encoding="utf-8",
    )

    mid = tmp_path / "1_mid"
    (mid / "def").mkdir(parents=True)
    (mid / "def" / "country.beyond.sii").write_text("SiiNunit { }\n", encoding="utf-8")

    high = tmp_path / "2_high"
    (high / "def").mkdir(parents=True)
    (high / "def" / "country.beyond.sii").write_text(
        'SiiNunit\n{\n@include "country/new.sui"\n}\n',
        encoding="utf-8",
    )

    stack = VfsStack.from_paths([low, mid, high])
    resolved = stack.resolve("def/country.beyond.sii")
    assert resolved is not None
    assert resolved.layer_name == "2_high"
    assert resolved.is_empty_stub is False
    assert stack.empty_stub_paths() == []


def test_vfs_stack_resolve_refreshes_three_nk_meta_on_first_call(tmp_path: pathlib.Path) -> None:
    arc_path = _build_hashfs_v1_simple(
        tmp_path / "3nk.scs",
        files={"def/country/germany/speed_limits.sii": b"3nK\x01\x00\x09\xaa\xbb"},
        dirs={
            "": ["*def"],
            "def": ["*country"],
            "def/country": ["*germany"],
            "def/country/germany": ["speed_limits.sii"],
        },
    )
    stack = VfsStack.from_paths([arc_path], seeded_prefixes=("def",))
    assert not hasattr(stack, "_seeded_prefixes")

    with stack:
        entry = stack.resolve("def/country/germany/speed_limits.sii")
        assert entry is not None
        assert entry.meta.three_nk is True
        assert entry.is_empty_stub is False
        assert any(d.kind == "three_nk_obfuscated" for d in stack.diagnostics())


def test_vfs_stack_skips_stub_inspection_above_max_stub_inspect_bytes(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod_dir = tmp_path / "large_sii_mod"
    (mod_dir / "def").mkdir(parents=True)
    big_payload = b"SiiNunit\n{\n" + (b"\t# comment\n" * 20) + b"}\n"
    (mod_dir / "def" / "huge.sii").write_bytes(big_payload)
    (mod_dir / "def" / "small.sii").write_bytes(b"SiiNunit { }")

    monkeypatch.setattr(stack_mod, "MAX_STUB_INSPECT_BYTES", 32)
    arc = DirectoryArchive(mod_dir)
    read_calls: list[str] = []
    orig_read_bytes = arc.read_bytes

    def tracked_read_bytes(vfs_path: str) -> bytes:
        read_calls.append(vfs_path)
        return orig_read_bytes(vfs_path)

    monkeypatch.setattr(arc, "read_bytes", tracked_read_bytes)

    stack = VfsStack([VfsLayer(name="mod", priority=0, archive=arc)], seeded_prefixes=("def",))
    assert not hasattr(stack, "_seeded_prefixes")

    huge_entry = stack.resolve("def/huge.sii")
    assert huge_entry is not None
    assert huge_entry.is_empty_stub is False
    assert read_calls == []
    assert stack.empty_stub_paths() == ["def/small.sii"]
    assert read_calls == ["def/small.sii"]
    assert stack.read_bytes("def/huge.sii") == big_payload
