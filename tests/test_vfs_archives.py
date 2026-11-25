"""Clean-room tests for HashFS v1/v2, ZIP, unpacked directory, and protected archives."""

from __future__ import annotations

import io
import os
import pathlib
import struct
import zipfile
import zlib
from dataclasses import dataclass
from typing import IO

import pytest

import ets2v2.vfs.hashfs as hashfs_mod
import ets2v2.vfs.zip_archive as zip_archive_mod
from ets2v2.vfs.cityhash import hash_vfs_path
from ets2v2.vfs.dir_archive import DirectoryArchive
from ets2v2.vfs.hashfs import (
    MAX_V2_TABLE_BYTES,
    HashFsV1Archive,
    HashFsV2Archive,
    ProtectedArchiveStub,
    detect_3nk,
    open_archive,
)
from ets2v2.vfs.types import ProtectedPayloadError, UnsupportedCompressionError, VfsArchive
from ets2v2.vfs.zip_archive import ZipArchive


@dataclass(frozen=True)
class _SyntheticV2Spec:
    entries: list[tuple[int, list[int], int]]  # (hash, meta_words, flags)
    payloads: list[tuple[int, bytes]]  # (offset_blocks, raw_bytes)


def _build_hashfs_v1(
    dest: pathlib.Path,
    files: dict[str, tuple[bytes, bool]],
    *,
    dirs: dict[str, list[str]],
    salt: int = 0,
) -> pathlib.Path:
    """Build a synthetic HashFS v1 archive (32-byte header, 32-byte entries)."""
    data_chunks: list[bytes] = []
    cursor = 32  # right after header
    records: list[tuple[int, int, int, int, int, int]] = []

    for dir_path, items in dirs.items():
        h = hash_vfs_path(dir_path, salt=salt)
        raw = ("\n".join(items) + "\n").encode("utf-8") if items else b""
        zraw = zlib.compress(raw)
        crc = zlib.crc32(raw) & 0xFFFFFFFF
        records.append((h, cursor, 1 | 2, crc, len(raw), len(zraw)))
        data_chunks.append(zraw)
        cursor += len(zraw)

    for file_path, (raw, compress) in files.items():
        h = hash_vfs_path(file_path, salt=salt)
        if compress:
            stored = zlib.compress(raw)
            flags = 2
        else:
            stored = raw
            flags = 0
        crc = zlib.crc32(raw) & 0xFFFFFFFF
        records.append((h, cursor, flags, crc, len(raw), len(stored)))
        data_chunks.append(stored)
        cursor += len(stored)

    records.sort(key=lambda r: r[0])
    entry_table = b"".join(struct.pack("<QQIIII", *r) for r in records)
    header = struct.pack(
        "<4sHH4sIQQ",
        b"SCS#",
        1,
        salt,
        b"CITY",
        len(records),
        cursor,
        0,
    )
    dest.write_bytes(header + b"".join(data_chunks) + entry_table)
    return dest


def _encode_v2_dir_listing(items: list[str]) -> bytes:
    encoded = [item.encode("utf-8") for item in items]
    header = struct.pack("<I", len(encoded))
    lengths = bytes(len(e) for e in encoded)
    return header + lengths + b"".join(encoded)


def _build_hashfs_v2(
    dest: pathlib.Path,
    files: dict[str, tuple[bytes, int]],  # path -> (stored_bytes, comp_nibble)
    *,
    dirs: dict[str, list[str]],
    raw_sizes: dict[str, int] | None = None,
    salt: int = 0,
    compress_tables: bool = True,
    extra_meta_entries: list[tuple[int, list[int], int]] | None = None,
) -> pathlib.Path:
    """Build a synthetic HashFS v2 archive with 16-byte alignment and optional compressed tables."""
    cursor = 128  # aligned past 44-byte header
    blob_parts: list[bytes] = [b"\x00" * (cursor - 44)]
    meta_words: list[int] = []
    entry_rows: list[tuple[int, int, int, int]] = []

    def append_blob(payload: bytes) -> int:
        nonlocal cursor
        pad = (-cursor) % 16
        if pad:
            blob_parts.append(b"\x00" * pad)
            cursor += pad
        off_blocks = cursor // 16
        blob_parts.append(payload)
        cursor += len(payload)
        return off_blocks

    for dir_path, items in dirs.items():
        h = hash_vfs_path(dir_path, salt=salt)
        raw = _encode_v2_dir_listing(items)
        zraw = zlib.compress(raw)
        off_blocks = append_blob(zraw)
        midx = len(meta_words)
        meta_words.extend(
            [
                (0x81 << 24) | (midx + 1),
                (1 << 28) | len(zraw),
                len(raw),
                0,
                off_blocks,
            ]
        )
        entry_rows.append((h, midx, 1, 5))

    for file_path, (raw, comp_nibble) in files.items():
        h = hash_vfs_path(file_path, salt=salt)
        if comp_nibble == 1:
            stored = zlib.compress(raw)
            raw_len = (raw_sizes or {}).get(file_path, len(raw))
        else:
            stored = raw
            raw_len = (raw_sizes or {}).get(file_path, len(raw))
        off_blocks = append_blob(stored)
        midx = len(meta_words)
        meta_words.extend(
            [
                (0x80 << 24) | (midx + 1),
                (comp_nibble << 28) | len(stored),
                raw_len,
                0,
                off_blocks,
            ]
        )
        entry_rows.append((h, midx, 1, 4))

    for extra_hash, extra_words, extra_flags in extra_meta_entries or []:
        midx = len(meta_words)
        meta_words.extend(extra_words)
        entry_rows.append((extra_hash, midx, 1, extra_flags))

    entry_rows.sort(key=lambda r: r[0])
    raw_entry_table = b"".join(struct.pack("<QIHH", *row) for row in entry_rows)
    raw_meta_table = struct.pack(f"<{len(meta_words)}I", *meta_words) if meta_words else b""

    stored_entry_table = zlib.compress(raw_entry_table) if compress_tables else raw_entry_table
    stored_meta_table = zlib.compress(raw_meta_table) if compress_tables else raw_meta_table

    pad_e = (-cursor) % 16
    if pad_e:
        blob_parts.append(b"\x00" * pad_e)
        cursor += pad_e
    entry_table_offset = cursor
    blob_parts.append(stored_entry_table)
    cursor += len(stored_entry_table)

    pad_m = (-cursor) % 16
    if pad_m:
        blob_parts.append(b"\x00" * pad_m)
        cursor += pad_m
    meta_table_offset = cursor
    blob_parts.append(stored_meta_table)
    cursor += len(stored_meta_table)

    header = struct.pack(
        "<4sHH4sIIIIQQ",
        b"SCS#",
        2,
        salt,
        b"CITY",
        len(entry_rows),
        len(stored_entry_table),
        len(meta_words),
        len(stored_meta_table),
        entry_table_offset,
        meta_table_offset,
    )
    dest.write_bytes(header + b"".join(blob_parts))
    return dest


def test_hashfs_v1_tracer_read_walk_and_3nk(tmp_path: pathlib.Path) -> None:
    iceland = b"country_data : country.data.iceland {\n\tcountry_id: 26\n}\n"
    obfuscated = b"3nK\x01\x00\x2a" + b"\x99\xaa\xbb\xcc"
    archive_path = _build_hashfs_v1(
        tmp_path / "mod_v1.scs",
        files={
            "def/country/iceland.sui": (iceland, True),
            "def/country/germany/speed_limits.sii": (obfuscated, False),
        },
        dirs={
            "": ["*def"],
            "def": ["*country"],
            "def/country": ["iceland.sui", "*germany"],
            "def/country/germany": ["speed_limits.sii"],
        },
        salt=17,
    )

    archive = HashFsV1Archive(archive_path)
    assert archive.salt == 17
    assert archive.walk() == [
        "def/country/germany/speed_limits.sii",
        "def/country/iceland.sui",
    ]
    assert archive.read_bytes("/def\\country\\iceland.sui") == iceland
    assert archive.diagnostics == []

    # Inspecting 3nK payload returns raw bytes without decrypting and logs diagnostic
    raw_3nk = archive.read_bytes("def/country/germany/speed_limits.sii")
    assert detect_3nk(raw_3nk) is True
    assert raw_3nk == obfuscated
    assert any(d.kind == "three_nk_obfuscated" for d in archive.diagnostics)


def test_hashfs_v2_small_compressed_tables_version_scs_case(tmp_path: pathlib.Path) -> None:
    # 2 entries => raw entry_table = 32 bytes, zlib-compressed = 36 bytes (compressed > raw!)
    version_payload = b'SiiNunit\n{\nversion_info : .version {\n\tversion: "1.62.3.3"\n}\n}\n'
    archive_path = _build_hashfs_v2(
        tmp_path / "version.scs",
        files={"version.sii": (version_payload, 1)},
        dirs={"": ["version.sii"]},
        compress_tables=True,
    )
    raw = archive_path.read_bytes()
    _, _, _, _, entry_count, entry_table_size, *_ = struct.unpack_from("<4sHH4sIIIIQQ", raw, 0)
    assert entry_count == 2
    assert entry_table_size > entry_count * 16

    archive = HashFsV2Archive(archive_path)
    assert archive.walk() == ["version.sii"]
    assert archive.read_bytes("version.sii") == version_payload


def test_hashfs_v2_seeded_walk_and_deduplication(tmp_path: pathlib.Path) -> None:
    # Stripped root (omits "" root, like locale.scs) + cyclic subdir reference "/locale"
    fp_bytes = b"key[]: fp_de_diesel\nval[]: 1.85\n"
    en_bytes = b"key[]: tz_gmt\nval[]: GMT\n"
    archive_path = _build_hashfs_v2(
        tmp_path / "locale.scs",
        files={
            "locale/fuel_price_strings.sui": (fp_bytes, 1),
            "locale/en_gb/localization.sui": (en_bytes, 1),
        },
        dirs={
            "locale": ["fuel_price_strings.sui", "/en_gb"],
            "locale/en_gb": ["localization.sui", "/.."],  # adversarial cycle/backref entry
        },
        compress_tables=True,
    )

    archive = HashFsV2Archive(archive_path, seeded_prefixes=("locale", "def"))
    walked = archive.walk(["locale", "locale/en_gb"])
    assert walked == [
        "locale/en_gb/localization.sui",
        "locale/fuel_price_strings.sui",
    ]
    # Calling walk() without explicit prefixes falls back to seeded_prefixes when "" is missing
    assert archive.walk() == walked
    assert archive.read_bytes("locale/fuel_price_strings.sui") == fp_bytes
    assert any(d.kind == "path_traversal" for d in archive.diagnostics)


def test_hashfs_v2_non_plain_metadata_bounds_and_unsupported_compression(
    tmp_path: pathlib.Path,
) -> None:
    iceland = b"country_data : country.data.iceland {\n\tcountry_id: 26\n}\n"
    sample_hash = hash_vfs_path("material/sample.dds")
    # Put a 2-word non-0x80/0x81 metadata entry at the tail (fewer than 5 words!)
    archive_path = _build_hashfs_v2(
        tmp_path / "mixed_meta.scs",
        files={
            "def/country/iceland.sui": (iceland, 1),
            "def/custom_zstd.bin": (b"FAKEZSTD", 2),
        },
        dirs={
            "": ["/def"],
            "def": ["/country", "custom_zstd.bin"],
            "def/country": ["iceland.sui"],
        },
        extra_meta_entries=[
            (sample_hash, [0x01000000, 0x00800080], 0),
        ],
        compress_tables=False,
    )

    archive = HashFsV2Archive(archive_path)
    assert archive.read_bytes("def/country/iceland.sui") == iceland
    assert archive.walk() == ["def/country/iceland.sui", "def/custom_zstd.bin"]

    kinds = {d.kind for d in archive.diagnostics}
    assert "unsupported_metadata" in kinds
    assert "unsupported_compression" in kinds

    with pytest.raises(UnsupportedCompressionError):
        archive.read_bytes("def/custom_zstd.bin")


def _build_mixed_encrypted_zip(dest: pathlib.Path) -> pathlib.Path:
    """Create a ZIP-wrapped .scs archive containing directory, plain, 3nK, and encrypted entries."""
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("def/", b"")
        zf.writestr("def/country/", b"")
        zf.writestr(
            "def/country/uk.sui",
            b"country_data : country.data.uk {\n\tcountry_id: 2\n}\n",
        )
        zf.writestr("def\\country\\france.sui", b"country_data : country.data.france {}\n")
        zf.writestr("def/country/germany/speed_limits.sii", b"3nK\x01\x00\x11\xaa\xbb")
        zf.writestr("def/country/beyond.sui", b"secret-content-bytes")

    # Patch the central directory + local header of def/country/beyond.sui to set flag_bits |= 0x1
    raw = bytearray(dest.read_bytes())
    target = b"def/country/beyond.sui"

    # Patch local file header flag_bits (offset +6 from PK\x03\x04)
    lf_pos = raw.find(target)
    assert lf_pos > 30
    lf_hdr = raw.rfind(b"PK\x03\x04", 0, lf_pos)
    assert lf_hdr != -1
    raw[lf_hdr + 6] |= 0x01

    # Patch central directory file header flag_bits (offset +8 from PK\x01\x02)
    cd_pos = raw.find(target, lf_pos + len(target))
    assert cd_pos > 46
    cd_hdr = raw.rfind(b"PK\x01\x02", 0, cd_pos)
    assert cd_hdr != -1
    raw[cd_hdr + 8] |= 0x01

    dest.write_bytes(bytes(raw))
    return dest


def test_zip_archive_mixed_plain_3nk_and_encrypted_entries(tmp_path: pathlib.Path) -> None:
    zip_path = _build_mixed_encrypted_zip(tmp_path / "hybrid_mod.scs")

    arc = ZipArchive(zip_path)
    assert arc.format_name == "zip"
    assert arc.list_paths() == [
        "def/country/beyond.sui",
        "def/country/france.sui",
        "def/country/germany/speed_limits.sii",
        "def/country/uk.sui",
    ]
    assert arc.exists("def/country/beyond.sui")
    assert not arc.exists("def/country")  # directory-only entries excluded

    plain_meta = arc.get_meta("def/country/uk.sui")
    assert plain_meta is not None
    assert plain_meta.encrypted is False
    assert b"country_id: 2" in arc.read_bytes("/def\\country/uk.sui")

    enc_meta = arc.get_meta("def/country/beyond.sui")
    assert enc_meta is not None
    assert enc_meta.encrypted is True
    assert any(
        d.kind == "encrypted_zip" and d.entry_path == "def/country/beyond.sui"
        for d in arc.diagnostics
    )

    with pytest.raises(ProtectedPayloadError):
        arc.read_bytes("def/country/beyond.sui")

    raw_3nk = arc.read_bytes("def/country/germany/speed_limits.sii")
    assert detect_3nk(raw_3nk)
    with pytest.raises(ProtectedPayloadError):
        arc.read_text("def/country/germany/speed_limits.sii")
    assert any(
        d.kind == "three_nk_obfuscated" and d.entry_path == "def/country/germany/speed_limits.sii"
        for d in arc.diagnostics
    )


def test_zip_archive_rejects_traversal_entry_in_central_directory(tmp_path: pathlib.Path) -> None:
    zip_path = tmp_path / "traversal.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../evil.txt", b"bad")
        zf.writestr("def/ok.sui", b"ok")
    arc = ZipArchive(zip_path)
    assert arc.list_paths() == ["def/ok.sui"]
    assert any(d.kind == "path_traversal" for d in arc.diagnostics)


def test_hashfs_v2_multi_descriptor_0x80_with_0x06_and_bad_scs_version(
    tmp_path: pathlib.Path,
) -> None:
    # Build HashFS v2 with a 2-descriptor [0x80, 0x06] entry (like dlc_north.scs .pmg)
    payload = b"\x15gmPmodeldata"
    path = "model/sign.pmg"
    file_hash = hash_vfs_path(path)
    dir_hash = hash_vfs_path("")
    dir_raw = _encode_v2_dir_listing(["/model"])
    sub_hash = hash_vfs_path("model")
    sub_raw = _encode_v2_dir_listing(["sign.pmg"])

    blob = bytearray(b"\x00" * (128 - 44))

    def add_blob(buf: bytearray, data: bytes) -> int:
        offset = 44 + len(buf)
        pad = (-offset) % 16
        if pad:
            buf.extend(b"\x00" * pad)
            offset += pad
        blk = offset // 16
        buf.extend(data)
        return blk

    dir_blk = add_blob(blob, dir_raw)
    sub_blk = add_blob(blob, sub_raw)
    file_blk = add_blob(blob, payload)

    metas = [
        (0x81 << 24) | 1,
        len(dir_raw),
        len(dir_raw),
        0,
        dir_blk,
        (0x81 << 24) | 6,
        len(sub_raw),
        len(sub_raw),
        0,
        sub_blk,
        (0x80 << 24) | 12,
        (0x06 << 24) | 16,
        len(payload),
        len(payload),
        0,
        file_blk,
        0,
        0,
    ]
    rows = sorted(
        [(dir_hash, 0, 1, 5), (sub_hash, 5, 1, 5), (file_hash, 10, 2, 0)],
        key=lambda r: r[0],
    )
    eu = zlib.compress(b"".join(struct.pack("<QIHH", *r) for r in rows))
    mu = zlib.compress(struct.pack(f"<{len(metas)}I", *metas))
    eto = add_blob(blob, eu) * 16
    mto = add_blob(blob, mu) * 16
    hdr = struct.pack(
        "<4sHH4sIIIIQQ",
        b"SCS#",
        2,
        0,
        b"CITY",
        len(rows),
        len(eu),
        len(metas),
        len(mu),
        eto,
        mto,
    )
    v2_path = tmp_path / "multi_desc.scs"
    v2_path.write_bytes(hdr + bytes(blob))

    arc = HashFsV2Archive(v2_path)
    assert arc.walk() == ["model/sign.pmg"]
    assert arc.read_bytes("model/sign.pmg") == payload
    assert arc.diagnostics == []

    # Unsupported SCS# version returns ProtectedArchiveStub with corrupt_archive
    bad_ver = tmp_path / "scs_v99.scs"
    bad_ver.write_bytes(b"SCS#\x63\x00CITY" + b"\x00" * 32)
    stub = open_archive(bad_ver)
    assert isinstance(stub, ProtectedArchiveStub)
    assert stub.diagnostics[0].kind == "corrupt_archive"


def test_directory_archive_reads_normalizes_and_blocks_escapes(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "unpacked_mod"
    (root / "def" / "country" / "poland").mkdir(parents=True)
    (root / "def" / "country" / "poland.sui").write_bytes(
        b"country_data : country.data.poland {}\n"
    )
    (root / "def" / "country" / "poland" / "speed_limits.sii").write_bytes(
        b"3nK\x01\x00\x05\x10\x20"
    )

    outside = tmp_path / "outside_secret.txt"
    outside.write_text("do-not-read", encoding="utf-8")

    symlink_created = False
    try:
        os.symlink(outside, root / "def" / "escape.sui")
        symlink_created = True
    except OSError:
        symlink_created = False

    arc = DirectoryArchive(root)
    assert arc.format_name == "directory"
    paths = arc.list_paths()
    assert paths == [
        "def/country/poland.sui",
        "def/country/poland/speed_limits.sii",
    ]
    assert "def/escape.sui" not in paths
    assert b"country.data.poland" in arc.read_bytes("\\def\\country/poland.sui")

    if symlink_created:
        assert any(d.kind == "path_traversal" for d in arc.diagnostics)
        assert not arc.exists("def/escape.sui")

    with pytest.raises(ValueError):
        arc.read_bytes("../outside_secret.txt")
    with pytest.raises(ValueError):
        arc.exists("def/../../outside_secret.txt")

    raw_3nk = arc.read_bytes("def/country/poland/speed_limits.sii")
    assert detect_3nk(raw_3nk)
    assert any(d.kind == "three_nk_obfuscated" for d in arc.diagnostics)


def test_open_archive_dispatches_all_formats_and_protected_stubs(tmp_path: pathlib.Path) -> None:
    # 1. Directory
    mod_dir = tmp_path / "dir_mod"
    (mod_dir / "def").mkdir(parents=True)
    (mod_dir / "def" / "country.sii").write_text("SiiNunit\n{\n}\n", encoding="utf-8")
    assert isinstance(open_archive(mod_dir), DirectoryArchive)

    # 2. ZIP
    zip_path = tmp_path / "zip_mod.scs"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("def/country.sii", b"SiiNunit {}")
    assert isinstance(open_archive(zip_path), ZipArchive)

    # 3. HashFS v1
    v1_path = _build_hashfs_v1(
        tmp_path / "v1.scs",
        files={"def/country.sii": (b"SiiNunit {}", True)},
        dirs={"": ["*def"], "def": ["country.sii"]},
    )
    assert isinstance(open_archive(v1_path), HashFsV1Archive)

    # 4. HashFS v2
    v2_path = _build_hashfs_v2(
        tmp_path / "v2.scs",
        files={"def/country.sii": (b"SiiNunit {}", 1)},
        dirs={"": ["/def"], "def": ["country.sii"]},
    )
    assert isinstance(open_archive(v2_path), HashFsV2Archive)

    # 5. AEM! protected archive
    aem_path = tmp_path / "ProjectRussia.scs"
    aem_path.write_bytes(b"AEM!\x01\x00\x00\x00encrypted-blob")
    aem_stub = open_archive(aem_path)
    assert isinstance(aem_stub, ProtectedArchiveStub)
    assert aem_stub.list_paths() == []
    assert not aem_stub.exists("def/country.sii")
    assert aem_stub.diagnostics[0].kind == "aem_protected"
    with pytest.raises(ProtectedPayloadError):
        aem_stub.read_bytes("def/country.sii")

    # 6. Unknown magic & empty/short files
    bad_path = tmp_path / "rain_bad_magic.scs"
    bad_path.write_bytes(b"BAD!\xde\xad\xbe\xef")
    bad_stub = open_archive(bad_path)
    assert isinstance(bad_stub, ProtectedArchiveStub)
    assert bad_stub.diagnostics[0].kind == "unknown_magic"

    tiny_path = tmp_path / "tiny.scs"
    tiny_path.write_bytes(b"xy")
    tiny_stub = open_archive(tiny_path)
    assert isinstance(tiny_stub, ProtectedArchiveStub)
    assert tiny_stub.diagnostics[0].kind == "unknown_magic"

    # 7. Corrupt ZIP with PK magic
    corrupt_zip = tmp_path / "corrupt.zip"
    corrupt_zip.write_bytes(b"PK\x03\x04not-a-valid-zip-archive")
    corrupt_arc = open_archive(corrupt_zip)
    assert corrupt_arc.list_paths() == []
    assert any(d.kind == "corrupt_archive" for d in corrupt_arc.diagnostics)


def test_hashfs_v2_table_bomb_and_entry_decompression_caps(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. entry_count * 16 > MAX_V2_TABLE_BYTES (4 GiB claim on tiny file)
    tiny_z = zlib.compress(b"\x00" * 16)
    entry_bomb = tmp_path / "entry_bomb.scs"
    hdr_entry_bomb = struct.pack(
        "<4sHH4sIIIIQQ",
        b"SCS#",
        2,
        0,
        b"CITY",
        0x10000000,
        len(tiny_z),
        0,
        0,
        44,
        44 + len(tiny_z),
    )
    entry_bomb.write_bytes(hdr_entry_bomb + tiny_z)
    arc1 = HashFsV2Archive(entry_bomb)
    assert arc1.walk() == []
    assert any(d.kind == "corrupt_archive" for d in arc1.diagnostics)

    # 2. metadata_count * 4 > MAX_V2_TABLE_BYTES (1 GiB claim on tiny file)
    meta_bomb = tmp_path / "meta_bomb.scs"
    hdr_meta_bomb = struct.pack(
        "<4sHH4sIIIIQQ",
        b"SCS#",
        2,
        0,
        b"CITY",
        1,
        len(tiny_z),
        (MAX_V2_TABLE_BYTES // 4) + 1,
        len(tiny_z),
        44,
        44 + len(tiny_z),
    )
    meta_bomb.write_bytes(hdr_meta_bomb + tiny_z + tiny_z)
    arc2 = HashFsV2Archive(meta_bomb)
    assert arc2.walk() == []
    assert any(d.kind == "corrupt_archive" for d in arc2.diagnostics)

    # 3. Compressed stream exceeding declared expected_size is rejected as corrupt_archive
    small_bomb = _build_hashfs_v2(
        tmp_path / "small_bomb.scs",
        files={"def/bomb.sii": (b"A" * 100, 1)},
        dirs={"": ["/def"], "def": ["bomb.sii"]},
        raw_sizes={"def/bomb.sii": 4},
    )
    arc_small = HashFsV2Archive(small_bomb)
    with pytest.raises(ValueError, match="Corrupt zlib payload"):
        arc_small.read_bytes("def/bomb.sii")
    assert any(d.kind == "corrupt_archive" for d in arc_small.diagnostics)

    # 4. _read_record_bytes enforces MAX_ENTRY_DECOMPRESSED_BYTES
    v2_path = _build_hashfs_v2(
        tmp_path / "big_entry.scs",
        files={"def/big.sii": (b"X" * 128, 1)},
        dirs={"": ["/def"], "def": ["big.sii"]},
    )
    arc3 = HashFsV2Archive(v2_path)
    monkeypatch.setattr(hashfs_mod, "MAX_ENTRY_DECOMPRESSED_BYTES", 64)
    with pytest.raises(ValueError, match="exceeds cap"):
        arc3.read_bytes("def/big.sii")
    assert any(d.kind == "corrupt_archive" for d in arc3.diagnostics)


def test_zip_archive_streaming_size_cap_and_multi_chunk_read(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload_90k = b"ABCD" * 22500  # 90,000 bytes (> 65536 read chunk)
    zip_path = tmp_path / "chunked.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("def/large.sii", payload_90k)

    arc = ZipArchive(zip_path)
    assert arc.read_bytes("def/large.sii") == payload_90k

    # Header size > MAX_ZIP_ENTRY_BYTES rejected before opening stream
    monkeypatch.setattr(zip_archive_mod, "MAX_ZIP_ENTRY_BYTES", 1024)
    with pytest.raises(ValueError, match="exceeds size cap"):
        arc.read_bytes("def/large.sii")
    assert any(d.kind == "corrupt_archive" for d in arc.diagnostics)

    # Lying ZipInfo.file_size (10 bytes) in real ZIP triggers BadZipFile -> ValueError
    bomb_zip = tmp_path / "lying_bomb.zip"
    with zipfile.ZipFile(bomb_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("def/bomb.sii", payload_90k)
    raw = bytearray(bomb_zip.read_bytes())
    target = b"def/bomb.sii"
    lf_pos = raw.find(target)
    lf_hdr = raw.rfind(b"PK\x03\x04", 0, lf_pos)
    struct.pack_into("<I", raw, lf_hdr + 22, 10)
    cd_pos = raw.find(target, lf_pos + len(target))
    cd_hdr = raw.rfind(b"PK\x01\x02", 0, cd_pos)
    struct.pack_into("<I", raw, cd_hdr + 24, 10)
    bomb_zip.write_bytes(bytes(raw))

    bomb_arc = ZipArchive(bomb_zip)
    monkeypatch.setattr(zip_archive_mod, "MAX_ZIP_ENTRY_BYTES", 70000)
    with pytest.raises(ValueError, match="Corrupt ZIP entry"):
        bomb_arc.read_bytes("def/bomb.sii")
    assert any(d.kind == "corrupt_archive" for d in bomb_arc.diagnostics)

    # Streaming chunk abort when member yields more bytes than MAX_ZIP_ENTRY_BYTES
    def fake_open(*_args: object, **_kwargs: object) -> IO[bytes]:
        return io.BytesIO(payload_90k)

    monkeypatch.setattr(zipfile.ZipFile, "open", fake_open)
    with pytest.raises(ValueError, match="exceeded decompression cap"):
        bomb_arc.read_bytes("def/bomb.sii")


def test_list_paths_empty_prefixes_consistent_across_all_archives(tmp_path: pathlib.Path) -> None:
    dir_root = tmp_path / "dir_mod"
    (dir_root / "def").mkdir(parents=True)
    (dir_root / "def" / "a.sui").write_bytes(b"a")

    zip_path = tmp_path / "zip_mod.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("def/a.sui", b"a")

    v1_path = _build_hashfs_v1(
        tmp_path / "v1_mod.scs",
        files={"def/a.sui": (b"a", True)},
        dirs={"": ["*def"], "def": ["a.sui"]},
    )
    v2_path = _build_hashfs_v2(
        tmp_path / "v2_mod.scs",
        files={"def/a.sui": (b"a", 1)},
        dirs={"": ["/def"], "def": ["a.sui"]},
    )
    aem_path = tmp_path / "aem_mod.scs"
    aem_path.write_bytes(b"AEM!\x00\x00\x00\x01")

    archives: list[VfsArchive] = [
        open_archive(dir_root),
        open_archive(zip_path),
        open_archive(v1_path),
        open_archive(v2_path),
    ]
    for arc in archives:
        with arc:
            assert isinstance(arc, VfsArchive)
            assert arc.list_paths() == ["def/a.sui"]
            assert arc.list_paths(None) == ["def/a.sui"]
            assert arc.list_paths([]) == []
            assert arc.list_paths(()) == []
            assert arc.list_paths(["def"]) == ["def/a.sui"]
            assert arc.list_paths(["locale"]) == []

    stub = open_archive(aem_path)
    with stub:
        assert isinstance(stub, VfsArchive)
        assert stub.list_paths(None) == []
        assert stub.list_paths([]) == []


def test_zip_archive_strong_encryption_0x40_and_duplicate_path_diagnostics(
    tmp_path: pathlib.Path,
) -> None:
    # 1. Strong encryption flag bit 0x40 (without 0x01)
    strong_zip = tmp_path / "strong.zip"
    with zipfile.ZipFile(strong_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("def/strong.sui", b"secret")
    raw = bytearray(strong_zip.read_bytes())
    target = b"def/strong.sui"
    lf_pos = raw.find(target)
    lf_hdr = raw.rfind(b"PK\x03\x04", 0, lf_pos)
    raw[lf_hdr + 6] |= 0x40
    cd_pos = raw.find(target, lf_pos + len(target))
    cd_hdr = raw.rfind(b"PK\x01\x02", 0, cd_pos)
    raw[cd_hdr + 8] |= 0x40
    strong_zip.write_bytes(bytes(raw))

    strong_arc = ZipArchive(strong_zip)
    meta = strong_arc.get_meta("def/strong.sui")
    assert meta is not None
    assert meta.encrypted is True
    assert any(
        d.kind == "encrypted_zip" and d.entry_path == "def/strong.sui"
        for d in strong_arc.diagnostics
    )
    with pytest.raises(ProtectedPayloadError):
        strong_arc.read_bytes("def/strong.sui")

    # 2. Duplicate normalized path: encrypted (0x01) overwritten by plaintext -> no stale diag;
    #    unsupported compress_type=99 overwritten by plaintext -> no stale diag;
    #    plaintext overwritten by strong-encrypted (0x40) -> encrypted_zip diagnostic present.
    dup_zip = tmp_path / "dup.zip"
    with zipfile.ZipFile(dup_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("def/enc_then_plain.sui", b"old-enc")
        zf.writestr("/def/enc_then_plain.sui", b"new-plain")
        zf.writestr("def/badcomp_then_plain.sui", b"old-badcomp")
        zf.writestr("/def/badcomp_then_plain.sui", b"new-plain-2")
        zf.writestr("def/plain_then_enc.sui", b"old-plain")
        zf.writestr("/def/plain_then_enc.sui", b"new-strong-enc")

    dup_raw = bytearray(dup_zip.read_bytes())
    cd_start = dup_raw.find(b"PK\x01\x02")
    assert cd_start != -1

    def patch_cd_entry(
        name_bytes: bytes,
        *,
        flag_or: int = 0,
        method: int | None = None,
    ) -> None:
        pos = dup_raw.find(name_bytes, cd_start)
        assert pos != -1
        cd_idx = dup_raw.rfind(b"PK\x01\x02", cd_start, pos)
        assert cd_idx != -1
        if flag_or:
            dup_raw[cd_idx + 8] |= flag_or
        if method is not None:
            struct.pack_into("<H", dup_raw, cd_idx + 10, method)

    patch_cd_entry(b"def/enc_then_plain.sui", flag_or=0x01)
    patch_cd_entry(b"def/badcomp_then_plain.sui", method=99)
    patch_cd_entry(b"/def/plain_then_enc.sui", flag_or=0x40)

    dup_zip.write_bytes(bytes(dup_raw))
    dup_arc = ZipArchive(dup_zip)
    assert dup_arc.read_bytes("def/enc_then_plain.sui") == b"new-plain"
    assert dup_arc.read_bytes("def/badcomp_then_plain.sui") == b"new-plain-2"
    assert [d.entry_path for d in dup_arc.diagnostics] == ["def/plain_then_enc.sui"]
    assert dup_arc.diagnostics[0].kind == "encrypted_zip"
    with pytest.raises(ProtectedPayloadError):
        dup_arc.read_bytes("def/plain_then_enc.sui")


def test_directory_archive_junction_pruning_and_get_meta_containment(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "mod_root"
    (root / "def").mkdir(parents=True)
    (root / "def" / "ok.sui").write_bytes(b"ok")

    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.sui"
    outside_file.write_bytes(b"outside-secret")

    # 1. Pruning escaping junction in os.walk
    escape_dir = root / "escape_junc"
    escape_dir.mkdir()
    (escape_dir / "hidden.sui").write_bytes(b"should-not-be-walked")
    orig_resolve = pathlib.Path.resolve

    def fake_is_junction(self: pathlib.Path) -> bool:
        return self.name == "escape_junc"

    def fake_resolve_junction(self: pathlib.Path, strict: bool = False) -> pathlib.Path:
        if self.name == "escape_junc":
            return orig_resolve(outside_dir, strict=strict)
        return orig_resolve(self, strict=strict)

    monkeypatch.setattr(pathlib.Path, "is_junction", fake_is_junction, raising=False)
    monkeypatch.setattr(pathlib.Path, "resolve", fake_resolve_junction)
    arc = DirectoryArchive(root)
    assert arc.list_paths() == ["def/ok.sui"]
    assert any(
        d.kind == "path_traversal" and d.entry_path == "escape_junc" for d in arc.diagnostics
    )

    # 2. get_meta() re-verifies containment
    monkeypatch.undo()
    arc_meta = DirectoryArchive(root)
    assert arc_meta.get_meta("def/ok.sui") is not None

    def fake_resolve_escaped_file(self: pathlib.Path, strict: bool = False) -> pathlib.Path:
        if self.name == "ok.sui":
            return orig_resolve(outside_file, strict=strict)
        return orig_resolve(self, strict=strict)

    monkeypatch.setattr(pathlib.Path, "resolve", fake_resolve_escaped_file)
    assert arc_meta.get_meta("def/ok.sui") is None
    assert any(
        d.kind == "path_traversal" and d.entry_path == "def/ok.sui" for d in arc_meta.diagnostics
    )


def test_hashfs_walk_skips_dir_records_listed_as_files_and_backwards_meta_ref(
    tmp_path: pathlib.Path,
) -> None:
    # 1. Corrupt archive listing a directory record as a non-subdir file entry
    corrupt_v2 = _build_hashfs_v2(
        tmp_path / "dir_as_file.scs",
        files={"def/real.sui": (b"real", 1)},
        dirs={
            "": ["/def"],
            "def": ["real.sui", "sneaky_dir"],  # missing leading '/'!
            "def/sneaky_dir": ["nested.sui"],
        },
    )
    arc_corrupt = HashFsV2Archive(corrupt_v2)
    assert arc_corrupt.walk() == ["def/real.sui"]

    # 2. HashFS v2 backwards metadata reference + non-plain high-bits descriptor
    payload_a = b"alpha"
    payload_b = b"beta"
    blk_dir_root = 8
    dir_root_raw = _encode_v2_dir_listing(["a.txt", "b.txt"])
    # Build manually using explicit metadata table where entry B points backwards to entry A's block
    cursor = 128
    blob = bytearray(b"\x00" * (cursor - 44))

    def add_blob(data: bytes) -> int:
        nonlocal cursor
        pad = (-cursor) % 16
        if pad:
            blob.extend(b"\x00" * pad)
            cursor += pad
        blk = cursor // 16
        blob.extend(data)
        cursor += len(data)
        return blk

    blk_dir = add_blob(dir_root_raw)
    blk_a = add_blob(payload_a)
    assert blk_dir >= blk_dir_root

    # Metadata words:
    # [0..4]: root dir (kind 0x81 -> word 1)
    # [5..9]: file a (kind 0x80 -> word 6)
    # [10]: file b (kind 0x80 -> backwards ref to word 6!)
    # [11]: non-plain entry (kind 0x06 with large flags >= total_meta_words)
    metas = [
        (0x81 << 24) | 1,
        len(dir_root_raw),
        len(dir_root_raw),
        0,
        blk_dir,
        (0x80 << 24) | 6,
        len(payload_a),
        len(payload_a),
        0,
        blk_a,
        (0x80 << 24) | 6,
        (0x06 << 24) | 0x00123456,
    ]
    rows = sorted(
        [
            (hash_vfs_path(""), 0, 1, 5),
            (hash_vfs_path("a.txt"), 5, 1, 4),
            (hash_vfs_path("b.txt"), 10, 1, 4),
            (hash_vfs_path("nonplain.dds"), 11, 1, 0),
        ],
        key=lambda r: r[0],
    )
    eu = zlib.compress(b"".join(struct.pack("<QIHH", *r) for r in rows))
    mu = zlib.compress(struct.pack(f"<{len(metas)}I", *metas))
    eto = add_blob(eu) * 16
    mto = add_blob(mu) * 16
    hdr = struct.pack(
        "<4sHH4sIIIIQQ",
        b"SCS#",
        2,
        0,
        b"CITY",
        len(rows),
        len(eu),
        len(metas),
        len(mu),
        eto,
        mto,
    )
    backref_path = tmp_path / "backref.scs"
    backref_path.write_bytes(hdr + bytes(blob))

    arc_back = HashFsV2Archive(backref_path)
    assert arc_back.walk() == ["a.txt", "b.txt"]
    assert arc_back.read_bytes("a.txt") == payload_a
    assert arc_back.read_bytes("b.txt") == payload_a
    assert [d.kind for d in arc_back.diagnostics] == ["unsupported_metadata"]
    assert payload_b != payload_a


def test_lo03_hashfs_list_direct_files_records_traversal_diag_and_deduplicates(
    tmp_path: pathlib.Path,
) -> None:
    """LO-03 regression: list_direct_files() logs path_traversal diagnostics and deduplicates."""
    archive_path = _build_hashfs_v2(
        tmp_path / "dup_traversal.scs",
        files={"def/country.sii": (b"SiiNunit\n{\n}\n", 1)},
        dirs={
            "": ["/def"],
            "def": ["country.sii", "country.sii", "..", "../escape.sii", "/sub"],
            "def/sub": [],
        },
        compress_tables=True,
    )
    with HashFsV2Archive(archive_path) as arc:
        direct = arc.list_direct_files("def")
        assert direct == ["def/country.sii"]
        traversal_diags = [d for d in arc.diagnostics if d.kind == "path_traversal"]
        assert len(traversal_diags) >= 2


def test_lo04_directory_archive_enforces_max_entry_bytes_cap(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LO-04 regression: DirectoryArchive.read_bytes() enforces MAX_DIR_ENTRY_BYTES cap."""
    import ets2v2.vfs.dir_archive as dir_mod

    assert dir_mod.MAX_DIR_ENTRY_BYTES == 128 * 1024 * 1024

    mod_root = tmp_path / "unpacked_mod"
    (mod_root / "def").mkdir(parents=True)
    (mod_root / "def" / "small.sii").write_bytes(b"ok-bytes")
    (mod_root / "def" / "oversized.sii").write_bytes(b"x" * 128)

    monkeypatch.setattr(dir_mod, "MAX_DIR_ENTRY_BYTES", 64)
    with dir_mod.DirectoryArchive(mod_root) as arc:
        assert arc.read_bytes("def/small.sii") == b"ok-bytes"
        with pytest.raises(ValueError, match="exceeds maximum directory entry size"):
            arc.read_bytes("def/oversized.sii")
