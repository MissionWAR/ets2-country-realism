"""Clean-room read-only HashFS v1 & v2 readers and 3nK detection."""

from __future__ import annotations

import struct
import zlib
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Self, cast

from ets2v2.vfs.cityhash import hash_vfs_path
from ets2v2.vfs.dir_archive import DirectoryArchive
from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    CompressionKind,
    DiagnosticKind,
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsArchive,
    VfsEntryMeta,
    detect_3nk,
    normalize_vfs_path,
)
from ets2v2.vfs.zip_archive import ZipArchive

DEFAULT_SEEDED_PREFIXES: tuple[str, ...] = ("locale", "def", "base")
_V1_HEADER_STRUCT = struct.Struct("<4sHH4sIQQ")
_V1_ENTRY_STRUCT = struct.Struct("<QQIIII")
_V2_HEADER_STRUCT = struct.Struct("<4sHH4sIIIIQQ")
_V2_ENTRY_STRUCT = struct.Struct("<QIHH")


@dataclass(frozen=True, slots=True)
class _HashFsRecord:
    entry_hash: int
    offset: int
    size: int
    compressed_size: int
    compression: CompressionKind
    is_dir: bool
    comp_code: int = 0


def _bounded_zlib_decompress(raw: bytes, expected_size: int) -> bytes:
    decompressor = zlib.decompressobj()
    out = decompressor.decompress(raw, expected_size + 1)
    if len(out) > expected_size:
        raise zlib.error(f"Decompressed payload exceeds expected size {expected_size}")
    tail = decompressor.flush()
    out += tail
    if len(out) != expected_size or not decompressor.eof:
        raise zlib.error(f"Decompressed length {len(out)} does not match expected {expected_size}")
    return out


class _BaseHashFsArchive:
    """Shared HashFS lookup, bounded reading, diagnostic tracking, and walk logic."""

    _format_name: str

    def __init__(
        self,
        path: Path,
        *,
        seeded_prefixes: Sequence[str] = DEFAULT_SEEDED_PREFIXES,
    ) -> None:
        self._path = Path(path)
        self._seeded_prefixes = tuple(
            normalize_vfs_path(p, allow_empty=True) for p in seeded_prefixes
        )
        self._salt = 0
        self._records: dict[int, _HashFsRecord] = {}
        self._diagnostics: list[ArchiveDiagnostic] = []
        self._diag_keys: set[tuple[DiagnosticKind, str | None, str]] = set()
        self._three_nk_paths: set[str] = set()
        self._file_size = 0
        self._active_handle: BinaryIO | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def format_name(self) -> str:
        return self._format_name

    @property
    def salt(self) -> int:
        return self._salt

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return list(self._diagnostics)

    def __enter__(self) -> Self:
        if self._active_handle is None:
            self._active_handle = self._path.open("rb")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._active_handle is not None:
            self._active_handle.close()
            self._active_handle = None

    def _add_diagnostic(
        self,
        kind: DiagnosticKind,
        entry_path: str | None,
        detail: str,
    ) -> None:
        key = (kind, entry_path, detail)
        if key in self._diag_keys:
            return
        self._diag_keys.add(key)
        self._diagnostics.append(
            ArchiveDiagnostic(
                kind=kind,
                archive_path=str(self._path),
                entry_path=entry_path,
                detail=detail,
            )
        )

    def _replace_hash_diagnostic_path(self, entry_hash: int, resolved_path: str) -> None:
        hash_label = f"hash:{entry_hash:016x}"
        updated: list[ArchiveDiagnostic] = []
        new_keys: set[tuple[DiagnosticKind, str | None, str]] = set()
        for diag in self._diagnostics:
            if diag.entry_path == hash_label:
                diag = diag.model_copy(update={"entry_path": resolved_path})
            new_keys.add((diag.kind, diag.entry_path, diag.detail))
            updated.append(diag)
        self._diagnostics = updated
        self._diag_keys = new_keys

    def _read_slice(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self._file_size:
            raise ValueError(f"Out-of-bounds read offset={offset} length={length} in {self._path}")
        if length == 0:
            return b""
        if self._active_handle is not None:
            self._active_handle.seek(offset)
            return self._active_handle.read(length)
        with self._path.open("rb") as fh:
            fh.seek(offset)
            return fh.read(length)

    def _read_record_bytes(self, record: _HashFsRecord, entry_label: str) -> bytes:
        if record.compression == "unknown":
            self._add_diagnostic(
                "unsupported_compression",
                entry_label,
                f"Unsupported compression code {record.comp_code}",
            )
            raise UnsupportedCompressionError(
                f"Unsupported compression code {record.comp_code} for "
                f"{entry_label!r} in {self._path}"
            )

        if record.compression == "zlib":
            raw = self._read_slice(record.offset, record.compressed_size)
            try:
                return _bounded_zlib_decompress(raw, record.size)
            except zlib.error as exc:
                self._add_diagnostic(
                    "corrupt_archive",
                    entry_label,
                    f"Corrupt zlib stream: {exc}",
                )
                raise ValueError(f"Corrupt zlib payload for {entry_label!r}") from exc

        read_len = record.size if record.size > 0 else record.compressed_size
        return self._read_slice(record.offset, read_len)

    def exists(self, vfs_path: str) -> bool:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        return hash_vfs_path(norm, salt=self._salt) in self._records

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        record = self._records.get(hash_vfs_path(norm, salt=self._salt))
        if record is None:
            return None
        return VfsEntryMeta(
            path=norm,
            is_dir=record.is_dir,
            size=record.size,
            compressed_size=record.compressed_size,
            compression=record.compression,
            encrypted=False,
            three_nk=norm in self._three_nk_paths,
        )

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        entry_hash = hash_vfs_path(norm, salt=self._salt)
        record = self._records.get(entry_hash)
        if record is None:
            raise FileNotFoundError(f"{norm!r} not found in {self._path}")
        if record.is_dir:
            raise IsADirectoryError(f"{norm!r} is a directory in {self._path}")

        self._replace_hash_diagnostic_path(entry_hash, norm)
        payload = self._read_record_bytes(record, norm)
        if detect_3nk(payload):
            self._three_nk_paths.add(norm)
            self._add_diagnostic(
                "three_nk_obfuscated",
                norm,
                "3nK\\x01 obfuscated payload detected; decryption is disabled.",
            )
        return payload

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str:
        payload = self.read_bytes(vfs_path)
        if detect_3nk(payload):
            raise ProtectedPayloadError(
                f"Cannot decode 3nK\\x01 obfuscated payload {vfs_path!r} as text"
            )
        return payload.decode(encoding)

    def _parse_dir_listing(self, data: bytes, dir_path: str) -> list[tuple[str, bool]]:
        raise NotImplementedError

    def _walk_with_parser(
        self,
        prefixes: Sequence[str] | None,
        parse_dir: Callable[[bytes, str], list[tuple[str, bool]]],
    ) -> list[str]:
        if prefixes is not None:
            seeds = [normalize_vfs_path(p, allow_empty=True) for p in prefixes]
        else:
            root_hash = hash_vfs_path("", salt=self._salt)
            root_rec = self._records.get(root_hash)
            if root_rec is not None and root_rec.is_dir:
                seeds = [""]
            else:
                seeds = list(self._seeded_prefixes)

        visited_dir_hashes: set[int] = set()
        visited_dir_paths: set[str] = set()
        seen_files: set[str] = set()
        results: list[str] = []

        for seed in seeds:
            seed_hash = hash_vfs_path(seed, salt=self._salt)
            seed_rec = self._records.get(seed_hash)
            if seed_rec is None:
                continue
            if not seed_rec.is_dir:
                if seed and seed not in seen_files:
                    seen_files.add(seed)
                    results.append(seed)
                continue
            if seed_hash in visited_dir_hashes or seed in visited_dir_paths:
                continue

            visited_dir_hashes.add(seed_hash)
            visited_dir_paths.add(seed)
            queue: deque[str] = deque([seed])

            while queue:
                cur_dir = queue.popleft()
                cur_hash = hash_vfs_path(cur_dir, salt=self._salt)
                cur_rec = self._records.get(cur_hash)
                if cur_rec is None or not cur_rec.is_dir:
                    continue
                self._replace_hash_diagnostic_path(cur_hash, cur_dir or "/")
                try:
                    raw_listing = self._read_record_bytes(cur_rec, cur_dir or "/")
                except (UnsupportedCompressionError, ValueError):
                    continue

                children = parse_dir(raw_listing, cur_dir)
                for child_name, is_sub in children:
                    if (
                        child_name in ("", ".", "..")
                        or "/" in child_name
                        or "\\" in child_name
                        or "\x00" in child_name
                    ):
                        self._add_diagnostic(
                            "path_traversal",
                            cur_dir or "/",
                            f"Rejected unsafe directory entry name {child_name!r}",
                        )
                        continue

                    child_path = f"{cur_dir}/{child_name}" if cur_dir else child_name
                    child_hash = hash_vfs_path(child_path, salt=self._salt)
                    child_rec = self._records.get(child_hash)
                    if child_rec is not None:
                        self._replace_hash_diagnostic_path(child_hash, child_path)

                    if is_sub:
                        if (
                            child_rec is not None
                            and child_rec.is_dir
                            and child_hash not in visited_dir_hashes
                            and child_path not in visited_dir_paths
                        ):
                            visited_dir_hashes.add(child_hash)
                            visited_dir_paths.add(child_path)
                            queue.append(child_path)
                    elif child_path not in seen_files and child_rec is not None:
                        seen_files.add(child_path)
                        results.append(child_path)

        return sorted(results)

    def walk(self, prefixes: Sequence[str] | None = None) -> list[str]:
        return self._walk_with_parser(prefixes, self._parse_dir_listing)

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]:
        return self.walk(prefixes)


class HashFsV1Archive(_BaseHashFsArchive):
    """Clean-room HashFS v1 (``SCS#\\x01``) container reader."""

    _format_name = "hashfs_v1"

    def __init__(
        self,
        path: Path,
        *,
        seeded_prefixes: Sequence[str] = DEFAULT_SEEDED_PREFIXES,
    ) -> None:
        super().__init__(path, seeded_prefixes=seeded_prefixes)
        self._load_table()

    def _load_table(self) -> None:
        with self._path.open("rb") as fh:
            fh.seek(0, 2)
            self._file_size = fh.tell()
            if self._file_size < _V1_HEADER_STRUCT.size:
                self._add_diagnostic(
                    "corrupt_archive",
                    None,
                    f"Truncated HashFS v1 header ({self._file_size} bytes)",
                )
                return
            fh.seek(0)
            hdr = fh.read(_V1_HEADER_STRUCT.size)
            magic, version, salt, hash_method, num_entries, start_offset, _ = (
                _V1_HEADER_STRUCT.unpack_from(hdr, 0)
            )
            if magic != b"SCS#" or version != 1 or hash_method != b"CITY":
                self._add_diagnostic(
                    "corrupt_archive",
                    None,
                    f"Invalid HashFS v1 header: magic={magic!r}, "
                    f"ver={version}, method={hash_method!r}",
                )
                return

            self._salt = salt
            table_bytes_len = num_entries * _V1_ENTRY_STRUCT.size
            if start_offset + table_bytes_len > self._file_size:
                self._add_diagnostic(
                    "corrupt_archive",
                    None,
                    "HashFS v1 entry table extends past end of file",
                )
                return

            fh.seek(start_offset)
            table_bytes = fh.read(table_bytes_len)

        for row in _V1_ENTRY_STRUCT.iter_unpack(table_bytes):
            entry_hash, offset, flags, _crc, size, zsize = cast(
                tuple[int, int, int, int, int, int],
                row,
            )
            is_dir = bool(flags & 1)
            compressed = bool(flags & 2)
            compression: CompressionKind = "zlib" if compressed else "none"
            self._records[entry_hash] = _HashFsRecord(
                entry_hash=entry_hash,
                offset=offset,
                size=size,
                compressed_size=zsize if compressed else size,
                compression=compression,
                is_dir=is_dir,
                comp_code=1 if compressed else 0,
            )

    def _parse_dir_listing(self, data: bytes, dir_path: str) -> list[tuple[str, bool]]:
        text = data.decode("utf-8", errors="replace")
        entries: list[tuple[str, bool]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip("\r\n")
            if not line:
                continue
            if line.startswith("*"):
                entries.append((line[1:], True))
            else:
                entries.append((line, False))
        return entries


class HashFsV2Archive(_BaseHashFsArchive):
    """Clean-room HashFS v2 (``SCS#\\x02``) container reader."""

    _format_name = "hashfs_v2"

    def __init__(
        self,
        path: Path,
        *,
        seeded_prefixes: Sequence[str] = DEFAULT_SEEDED_PREFIXES,
    ) -> None:
        super().__init__(path, seeded_prefixes=seeded_prefixes)
        self._load_tables()

    def _decode_table(self, raw: bytes, expected_size: int, label: str) -> bytes | None:
        if expected_size == 0:
            return b""
        if raw:
            try:
                return _bounded_zlib_decompress(raw, expected_size)
            except zlib.error:
                if len(raw) == expected_size:
                    return raw
        self._add_diagnostic(
            "corrupt_archive",
            None,
            f"Failed to decode HashFS v2 {label} (raw={len(raw)}, expected={expected_size})",
        )
        return None

    def _load_tables(self) -> None:
        with self._path.open("rb") as fh:
            fh.seek(0, 2)
            self._file_size = fh.tell()
            if self._file_size < _V2_HEADER_STRUCT.size:
                self._add_diagnostic(
                    "corrupt_archive",
                    None,
                    f"Truncated HashFS v2 header ({self._file_size} bytes)",
                )
                return
            fh.seek(0)
            hdr = fh.read(_V2_HEADER_STRUCT.size)
            (
                magic,
                version,
                salt,
                hash_method,
                entry_count,
                entry_table_size,
                metadata_count,
                metadata_table_size,
                entry_table_offset,
                metadata_table_offset,
            ) = _V2_HEADER_STRUCT.unpack_from(hdr, 0)

            if magic != b"SCS#" or version != 2 or hash_method != b"CITY":
                self._add_diagnostic(
                    "corrupt_archive",
                    None,
                    f"Invalid HashFS v2 header: magic={magic!r}, "
                    f"ver={version}, method={hash_method!r}",
                )
                return

            self._salt = salt
            if (
                entry_table_offset + entry_table_size > self._file_size
                or metadata_table_offset + metadata_table_size > self._file_size
            ):
                self._add_diagnostic(
                    "corrupt_archive",
                    None,
                    "HashFS v2 entry or metadata table extends past end of file",
                )
                return

            fh.seek(entry_table_offset)
            raw_entry_table = fh.read(entry_table_size)
            fh.seek(metadata_table_offset)
            raw_meta_table = fh.read(metadata_table_size)

        entry_bytes = self._decode_table(
            raw_entry_table,
            entry_count * _V2_ENTRY_STRUCT.size,
            "entry_table",
        )
        meta_bytes = self._decode_table(
            raw_meta_table,
            metadata_count * 4,
            "metadata_table",
        )
        if entry_bytes is None or meta_bytes is None:
            return

        metas: tuple[int, ...] = (
            cast(tuple[int, ...], struct.unpack_from(f"<{metadata_count}I", meta_bytes, 0))
            if metadata_count
            else cast(tuple[int, ...], ())
        )
        total_meta_words = len(metas)

        for row in _V2_ENTRY_STRUCT.iter_unpack(entry_bytes):
            entry_hash, meta_idx, meta_cnt, flags = cast(
                tuple[int, int, int, int],
                row,
            )
            if meta_cnt == 0 or meta_idx + meta_cnt > total_meta_words:
                self._add_diagnostic(
                    "corrupt_archive",
                    f"hash:{entry_hash:016x}",
                    f"Out-of-bounds metadata span ({meta_idx}+{meta_cnt} > {total_meta_words})",
                )
                continue

            seen_kinds: list[int] = []
            selected_record: _HashFsRecord | None = None

            for desc_idx in range(meta_cnt):
                header_word = metas[meta_idx + desc_idx]
                kind = header_word >> 24
                payload_idx = header_word & 0x00FFFFFF
                seen_kinds.append(kind)

                if kind not in (0x80, 0x81):
                    if payload_idx >= total_meta_words:
                        self._add_diagnostic(
                            "corrupt_archive",
                            f"hash:{entry_hash:016x}",
                            "Out-of-bounds non-plain metadata index "
                            f"{payload_idx} >= {total_meta_words}",
                        )
                    continue

                if meta_cnt == 1 and payload_idx < meta_idx + meta_cnt:
                    payload_idx = meta_idx + 1

                if payload_idx + 4 > total_meta_words:
                    self._add_diagnostic(
                        "corrupt_archive",
                        f"hash:{entry_hash:016x}",
                        f"Truncated {kind:#x} metadata block at word {payload_idx}",
                    )
                    continue

                w1 = metas[payload_idx]
                w2 = metas[payload_idx + 1]
                w4 = metas[payload_idx + 3]
                comp_nibble = w1 >> 28
                zsize = w1 & 0x0FFFFFFF
                size = w2
                offset = w4 * 16
                is_dir = kind == 0x81 or bool(flags & 1)

                if comp_nibble == 0:
                    compression: CompressionKind = "none"
                elif comp_nibble == 1:
                    compression = "zlib"
                else:
                    compression = "unknown"
                    self._add_diagnostic(
                        "unsupported_compression",
                        f"hash:{entry_hash:016x}",
                        f"Unsupported HashFS v2 compression nibble {comp_nibble}",
                    )

                selected_record = _HashFsRecord(
                    entry_hash=entry_hash,
                    offset=offset,
                    size=size,
                    compressed_size=zsize,
                    compression=compression,
                    is_dir=is_dir,
                    comp_code=comp_nibble,
                )
                break

            if selected_record is not None:
                self._records[entry_hash] = selected_record
            elif seen_kinds:
                kinds_text = ", ".join(f"{k:#x}" for k in seen_kinds)
                self._add_diagnostic(
                    "unsupported_metadata",
                    f"hash:{entry_hash:016x}",
                    f"Skipped entry with non-0x80/0x81 metadata kind(s): {kinds_text}",
                )

    def _parse_dir_listing(self, data: bytes, dir_path: str) -> list[tuple[str, bool]]:
        if len(data) < 4:
            self._add_diagnostic(
                "corrupt_archive",
                dir_path or "/",
                f"Truncated HashFS v2 directory listing ({len(data)} bytes)",
            )
            return []

        count: int = struct.unpack_from("<I", data, 0)[0]
        if 4 + count > len(data):
            self._add_diagnostic(
                "corrupt_archive",
                dir_path or "/",
                "HashFS v2 directory length table exceeds listing payload",
            )
            return []

        lengths = data[4 : 4 + count]
        pos = 4 + count
        entries: list[tuple[str, bool]] = []
        for name_len in lengths:
            if pos + name_len > len(data):
                self._add_diagnostic(
                    "corrupt_archive",
                    dir_path or "/",
                    "HashFS v2 directory entry string exceeds listing payload",
                )
                break
            raw_name = data[pos : pos + name_len].decode("utf-8", errors="replace")
            pos += name_len
            if raw_name.startswith("/"):
                entries.append((raw_name[1:], True))
            else:
                entries.append((raw_name, False))
        return entries


class ProtectedArchiveStub:
    """Read-only stub for unreadable/protected containers (AEM!, unknown magic, corrupt)."""

    def __init__(
        self,
        path: Path,
        *,
        format_name: str = "protected",
        diagnostics: Sequence[ArchiveDiagnostic],
    ) -> None:
        self._path = Path(path)
        self._format_name = format_name
        self._diagnostics = list(diagnostics)
        if not self._diagnostics:
            raise ValueError("ProtectedArchiveStub requires at least one diagnostic")

    @property
    def path(self) -> Path:
        return self._path

    @property
    def format_name(self) -> str:
        return self._format_name

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return list(self._diagnostics)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        return None

    def exists(self, vfs_path: str) -> bool:
        normalize_vfs_path(vfs_path, allow_empty=True)
        return False

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None:
        normalize_vfs_path(vfs_path, allow_empty=True)
        return None

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]:
        return []

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        first = self._diagnostics[0]
        raise ProtectedPayloadError(
            f"Cannot read {norm!r} from protected/unreadable archive "
            f"{self._path} ({first.kind}: {first.detail})"
        )

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(vfs_path).decode(encoding)


def open_archive(
    path: Path,
    *,
    seeded_prefixes: Sequence[str] = DEFAULT_SEEDED_PREFIXES,
) -> VfsArchive:
    """Open a directory, ZIP, HashFS v1/v2 archive, or return a ProtectedArchiveStub."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(target)
    if target.is_dir():
        return DirectoryArchive(target)

    with target.open("rb") as fh:
        head = fh.read(8)

    if len(head) < 4:
        return ProtectedArchiveStub(
            target,
            format_name="unknown_magic",
            diagnostics=[
                ArchiveDiagnostic(
                    kind="unknown_magic",
                    archive_path=str(target),
                    entry_path=None,
                    detail=f"Archive is too small ({len(head)} bytes) to identify magic bytes.",
                )
            ],
        )

    if head[:4] == b"AEM!":
        return ProtectedArchiveStub(
            target,
            format_name="aem_protected",
            diagnostics=[
                ArchiveDiagnostic(
                    kind="aem_protected",
                    archive_path=str(target),
                    entry_path=None,
                    detail="AEM! protected archive header detected; decryption is unsupported.",
                )
            ],
        )

    if head[:2] == b"PK":
        return ZipArchive(target)

    if head[:4] == b"SCS#":
        if len(head) < 6:
            return ProtectedArchiveStub(
                target,
                format_name="corrupt_archive",
                diagnostics=[
                    ArchiveDiagnostic(
                        kind="corrupt_archive",
                        archive_path=str(target),
                        entry_path=None,
                        detail="Truncated SCS# archive header.",
                    )
                ],
            )
        version: int = struct.unpack_from("<H", head, 4)[0]
        if version == 1:
            return HashFsV1Archive(target, seeded_prefixes=seeded_prefixes)
        if version == 2:
            return HashFsV2Archive(target, seeded_prefixes=seeded_prefixes)
        return ProtectedArchiveStub(
            target,
            format_name="corrupt_archive",
            diagnostics=[
                ArchiveDiagnostic(
                    kind="corrupt_archive",
                    archive_path=str(target),
                    entry_path=None,
                    detail=f"Unsupported SCS# HashFS version {version}.",
                )
            ],
        )

    return ProtectedArchiveStub(
        target,
        format_name="unknown_magic",
        diagnostics=[
            ArchiveDiagnostic(
                kind="unknown_magic",
                archive_path=str(target),
                entry_path=None,
                detail=f"Unknown archive magic bytes: {head[:4]!r}",
            )
        ],
    )
