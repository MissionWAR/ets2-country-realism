"""Clean-room read-only ZIP / ZIP-wrapped .scs container reader."""

from __future__ import annotations

import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    CompressionKind,
    DiagnosticKind,
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsEntryMeta,
    detect_3nk,
    normalize_vfs_path,
)


def _matches_prefixes(path: str, normalized_prefixes: list[str]) -> bool:
    if not normalized_prefixes or "" in normalized_prefixes:
        return True
    return any(path == pref or path.startswith(f"{pref}/") for pref in normalized_prefixes)


class ZipArchive:
    """Read-only ZIP and ZIP-wrapped ``.scs`` reader with encrypted entry inspection."""

    format_name = "zip"

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(self._path)
        self._entries: dict[str, zipfile.ZipInfo] = {}
        self._diagnostics: list[ArchiveDiagnostic] = []
        self._diag_keys: set[tuple[DiagnosticKind, str | None, str]] = set()
        self._three_nk_paths: set[str] = set()
        self._active_zip: zipfile.ZipFile | None = None
        self._load_central_directory()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return list(self._diagnostics)

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
            self._add_diagnostic(
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
                self._add_diagnostic(
                    "path_traversal",
                    info.filename,
                    f"Rejected unsafe ZIP entry path: {exc}",
                )
                continue
            if not norm:
                continue

            self._entries[norm] = info
            if info.flag_bits & 0x1:
                self._add_diagnostic(
                    "encrypted_zip",
                    norm,
                    "Password-encrypted ZIP entry (flag_bits & 0x1); "
                    "central-directory path inspected only.",
                )
            elif self._compression_for(info) == "unknown":
                self._add_diagnostic(
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
            encrypted=bool(info.flag_bits & 0x1),
            three_nk=norm in self._three_nk_paths,
        )

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]:
        norm_prefixes = (
            [normalize_vfs_path(p, allow_empty=True) for p in prefixes]
            if prefixes is not None
            else []
        )
        return sorted(p for p in self._entries if _matches_prefixes(p, norm_prefixes))

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        info = self._entries.get(norm)
        if info is None:
            raise FileNotFoundError(f"{norm!r} not found in {self._path}")
        if info.flag_bits & 0x1:
            self._add_diagnostic(
                "encrypted_zip",
                norm,
                "Password-encrypted ZIP entry (flag_bits & 0x1); decryption is unsupported.",
            )
            raise ProtectedPayloadError(f"Cannot read encrypted ZIP entry {norm!r} in {self._path}")
        if self._compression_for(info) == "unknown":
            self._add_diagnostic(
                "unsupported_compression",
                norm,
                f"Unsupported ZIP compression method {info.compress_type}",
            )
            raise UnsupportedCompressionError(
                f"Unsupported ZIP compression method {info.compress_type} for {norm!r}"
            )

        try:
            if self._active_zip is not None:
                data = self._active_zip.read(info.filename)
            else:
                with zipfile.ZipFile(self._path, "r") as zf:
                    data = zf.read(info.filename)
        except (zipfile.BadZipFile, zlib.error, RuntimeError, EOFError) as exc:
            self._add_diagnostic(
                "corrupt_archive",
                norm,
                f"Failed to read ZIP entry payload: {exc}",
            )
            raise ValueError(f"Corrupt ZIP entry {norm!r} in {self._path}") from exc

        if detect_3nk(data):
            self._three_nk_paths.add(norm)
            self._add_diagnostic(
                "three_nk_obfuscated",
                norm,
                "3nK\\x01 obfuscated payload detected; decryption is disabled.",
            )
        return data

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str:
        data = self.read_bytes(vfs_path)
        if detect_3nk(data):
            raise ProtectedPayloadError(
                f"Cannot decode 3nK\\x01 obfuscated payload {vfs_path!r} as text"
            )
        return data.decode(encoding)
