"""Core VFS types, diagnostics, exceptions, and POSIX path canonicalizer."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict

DiagnosticKind = Literal[
    "three_nk_obfuscated",
    "aem_protected",
    "unknown_magic",
    "encrypted_zip",
    "unsupported_compression",
    "unsupported_metadata",
    "corrupt_archive",
    "path_traversal",
]

CompressionKind = Literal["none", "zlib", "unknown"]


class ProtectedPayloadError(RuntimeError):
    """Raised when attempting to read an encrypted or protected container payload."""


class UnsupportedCompressionError(RuntimeError):
    """Raised when an archive entry uses an unsupported compression algorithm."""


def detect_3nk(data: bytes) -> bool:
    """Return True when ``data`` starts with an SCS ``3nK\\x01`` obfuscation header."""
    return data.startswith(b"3nK\x01")


class ArchiveDiagnostic(BaseModel):
    """Structured diagnostic emitted when inspecting protected or malformed VFS items."""

    model_config = ConfigDict(frozen=True)

    kind: DiagnosticKind
    archive_path: str
    entry_path: str | None = None
    detail: str


class VfsEntryMeta(BaseModel):
    """Metadata describing a file or directory entry within a VFS container."""

    model_config = ConfigDict(frozen=True)

    path: str
    is_dir: bool = False
    size: int = 0
    compressed_size: int = 0
    compression: CompressionKind = "none"
    encrypted: bool = False
    three_nk: bool = False


def normalize_vfs_path(path: str, *, allow_empty: bool = False) -> str:
    """Canonicalize a VFS path into a relative POSIX path without leading slashes.

    Rejects NUL bytes and ``..`` traversal segments.
    """
    if "\x00" in path:
        raise ValueError(f"VFS path contains NUL byte: {path!r}")

    unified = path.replace("\\", "/")
    segments: list[str] = []
    for raw_seg in unified.split("/"):
        if raw_seg in ("", "."):
            continue
        if raw_seg == "..":
            raise ValueError(f"Path traversal ('..') is not allowed in VFS path: {path!r}")
        segments.append(raw_seg)

    normalized = "/".join(segments)
    if not normalized and not allow_empty:
        raise ValueError(f"Empty VFS path is not allowed: {path!r}")
    return normalized


def matches_prefixes(path: str, normalized_prefixes: Sequence[str]) -> bool:
    """Return True if ``path`` equals or is under any prefix in ``normalized_prefixes``."""
    if "" in normalized_prefixes:
        return True
    return any(path == pref or path.startswith(f"{pref}/") for pref in normalized_prefixes)


def filter_paths_by_prefixes(
    paths: Iterable[str],
    prefixes: Sequence[str] | None = None,
) -> list[str]:
    """Return sorted VFS paths matching ``prefixes``.

    ``prefixes=None`` returns all paths; an empty non-``None`` sequence returns ``[]``.
    """
    if prefixes is None:
        return sorted(paths)
    if len(prefixes) == 0:
        return []
    norm_prefixes = [normalize_vfs_path(p, allow_empty=True) for p in prefixes]
    if "" in norm_prefixes:
        return sorted(paths)
    return sorted(p for p in paths if matches_prefixes(p, norm_prefixes))


class DiagnosticCollector:
    """Deduplicated per-archive ``ArchiveDiagnostic`` accumulator."""

    def __init__(self, archive_path: Path | str) -> None:
        self._archive_path = str(archive_path)
        self._items: list[ArchiveDiagnostic] = []
        self._keys: set[tuple[DiagnosticKind, str | None, str]] = set()

    @property
    def items(self) -> list[ArchiveDiagnostic]:
        return list(self._items)

    def add(
        self,
        kind: DiagnosticKind,
        entry_path: str | None,
        detail: str,
    ) -> None:
        key = (kind, entry_path, detail)
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(
            ArchiveDiagnostic(
                kind=kind,
                archive_path=self._archive_path,
                entry_path=entry_path,
                detail=detail,
            )
        )

    def replace_entry_path(self, old_entry_path: str, new_entry_path: str) -> None:
        updated: list[ArchiveDiagnostic] = []
        new_keys: set[tuple[DiagnosticKind, str | None, str]] = set()
        for diag in self._items:
            if diag.entry_path == old_entry_path:
                diag = diag.model_copy(update={"entry_path": new_entry_path})
            key = (diag.kind, diag.entry_path, diag.detail)
            if key not in new_keys:
                new_keys.add(key)
                updated.append(diag)
        self._items = updated
        self._keys = new_keys


def deduplicate_diagnostics(diagnostics: Iterable[ArchiveDiagnostic]) -> list[ArchiveDiagnostic]:
    """Return diagnostics in insertion order, deduplicated by all diagnostic fields."""
    seen: set[tuple[DiagnosticKind, str, str | None, str]] = set()
    result: list[ArchiveDiagnostic] = []
    for diag in diagnostics:
        key = (diag.kind, diag.archive_path, diag.entry_path, diag.detail)
        if key not in seen:
            seen.add(key)
            result.append(diag)
    return result


def decode_vfs_text(data: bytes, vfs_path: str, encoding: str = "utf-8") -> str:
    """Decode VFS payload bytes as text, refusing ``3nK\\x01`` obfuscated blobs."""
    if detect_3nk(data):
        raise ProtectedPayloadError(
            f"Cannot decode 3nK\\x01 obfuscated payload {vfs_path!r} as text"
        )
    return data.decode(encoding)


def record_3nk_if_present(
    data: bytes,
    norm_path: str,
    three_nk_paths: set[str],
    diagnostics: DiagnosticCollector,
) -> None:
    """Record ``3nK\\x01`` detection on ``norm_path`` when ``data`` carries the header."""
    if detect_3nk(data):
        three_nk_paths.add(norm_path)
        diagnostics.add(
            "three_nk_obfuscated",
            norm_path,
            "3nK\\x01 obfuscated payload detected; decryption is disabled.",
        )


@runtime_checkable
class VfsArchive(Protocol):
    """Read-only virtual filesystem container contract."""

    @property
    def path(self) -> Path: ...

    @property
    def format_name(self) -> str: ...

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *args: object) -> None: ...

    def exists(self, vfs_path: str) -> bool: ...

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None: ...

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]: ...

    def read_bytes(self, vfs_path: str) -> bytes: ...

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str: ...

    def close(self) -> None: ...
