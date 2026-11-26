"""Clean-room read-only ZIP / ZIP-wrapped .scs container reader."""

from __future__ import annotations

import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from ets2_realism.vfs.types import (
    ArchiveDiagnostic,
    CompressionKind,
    DiagnosticCollector,
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsEntryMeta,
    decode_vfs_text,
    filter_paths_by_prefixes,
    normalize_vfs_path,
    record_3nk_if_present,
)

MAX_ZIP_ENTRY_BYTES = 128 * 1024 * 1024
_ZIP_READ_CHUNK_BYTES = 65536


def _is_encrypted_zip_info(info: zipfile.ZipInfo) -> bool:
    return bool(info.flag_bits & 0x41)


def _read_zip_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size < 0 or info.file_size > MAX_ZIP_ENTRY_BYTES:
        raise ValueError(
            f"ZIP entry {info.filename!r} exceeds size cap "
            f"({info.file_size} > {MAX_ZIP_ENTRY_BYTES} bytes)"
        )
    chunks: list[bytes] = []
    total = 0
    with zf.open(info, "r") as member:
        while chunk := member.read(_ZIP_READ_CHUNK_BYTES):
            total += len(chunk)
            if total > MAX_ZIP_ENTRY_BYTES:
                raise ValueError(
                    f"ZIP entry {info.filename!r} exceeded decompression cap "
                    f"({MAX_ZIP_ENTRY_BYTES} bytes)"
                )
            chunks.append(chunk)
    return b"".join(chunks)


class ZipArchive:
    """Read-only ZIP and ZIP-wrapped ``.scs`` reader with encrypted entry inspection."""

    format_name = "zip"

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(self._path)
        self._entries: dict[str, zipfile.ZipInfo] = {}
        self._diag = DiagnosticCollector(self._path)
        self._three_nk_paths: set[str] = set()
        self._active_zip: zipfile.ZipFile | None = None
        self._load_central_directory()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return self._diag.items

    def __enter__(self) -> Self:
        if self._active_zip is None:
            try:
                self._active_zip = zipfile.ZipFile(self._path, "r")
            except zipfile.BadZipFile:
                self._active_zip = None
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._active_zip is not None:
            self._active_zip.close()
            self._active_zip = None

    def _compression_for(self, info: zipfile.ZipInfo) -> CompressionKind:
        if info.compress_type == zipfile.ZIP_STORED:
            return "none"
        if info.compress_type == zipfile.ZIP_DEFLATED:
            return "zlib"
        return "unknown"

    def _load_central_directory(self) -> None:
        try:
            with zipfile.ZipFile(self._path, "r") as zf:
                infos = zf.infolist()
        except (zipfile.BadZipFile, OSError) as exc:
            self._diag.add(
                "corrupt_archive",
                None,
                f"Invalid or corrupt ZIP archive: {exc}",
            )
            return

        for info in infos:
            if info.is_dir() or info.filename.endswith(("/", "\\")):
                continue
            try:
                norm = normalize_vfs_path(info.filename, allow_empty=True)
            except ValueError as exc:
                self._diag.add(
                    "path_traversal",
                    info.filename,
                    f"Rejected unsafe ZIP entry path: {exc}",
                )
                continue
            if not norm:
                continue

            self._entries[norm] = info

        for norm, info in self._entries.items():
            if _is_encrypted_zip_info(info):
                self._diag.add(
                    "encrypted_zip",
                    norm,
                    "Password-encrypted ZIP entry (flag_bits & 0x41); "
                    "central-directory path inspected only.",
                )
            elif self._compression_for(info) == "unknown":
                self._diag.add(
                    "unsupported_compression",
                    norm,
                    f"Unsupported ZIP compression method {info.compress_type}",
                )

    def exists(self, vfs_path: str) -> bool:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        return norm in self._entries

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        info = self._entries.get(norm)
        if info is None:
            return None
        return VfsEntryMeta(
            path=norm,
            is_dir=False,
            size=info.file_size,
            compressed_size=info.compress_size,
            compression=self._compression_for(info),
            encrypted=_is_encrypted_zip_info(info),
            three_nk=norm in self._three_nk_paths,
        )

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]:
        return filter_paths_by_prefixes(self._entries, prefixes)

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        info = self._entries.get(norm)
        if info is None:
            raise FileNotFoundError(f"{norm!r} not found in {self._path}")
        if _is_encrypted_zip_info(info):
            self._diag.add(
                "encrypted_zip",
                norm,
                "Password-encrypted ZIP entry (flag_bits & 0x41); decryption is unsupported.",
            )
            raise ProtectedPayloadError(f"Cannot read encrypted ZIP entry {norm!r} in {self._path}")
        if self._compression_for(info) == "unknown":
            self._diag.add(
                "unsupported_compression",
                norm,
                f"Unsupported ZIP compression method {info.compress_type}",
            )
            raise UnsupportedCompressionError(
                f"Unsupported ZIP compression method {info.compress_type} for {norm!r}"
            )

        try:
            if self._active_zip is not None:
                data = _read_zip_bounded(self._active_zip, info)
            else:
                with zipfile.ZipFile(self._path, "r") as zf:
                    data = _read_zip_bounded(zf, info)
        except ValueError as exc:
            self._diag.add(
                "corrupt_archive",
                norm,
                str(exc),
            )
            raise
        except (zipfile.BadZipFile, zlib.error, RuntimeError, EOFError) as exc:
            self._diag.add(
                "corrupt_archive",
                norm,
                f"Failed to read ZIP entry payload: {exc}",
            )
            raise ValueError(f"Corrupt ZIP entry {norm!r} in {self._path}") from exc

        record_3nk_if_present(data, norm, self._three_nk_paths, self._diag)
        return data

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str:
        return decode_vfs_text(self.read_bytes(vfs_path), vfs_path, encoding)
