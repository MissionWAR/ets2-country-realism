"""Core VFS types, diagnostics, exceptions, and POSIX path canonicalizer."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

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


@runtime_checkable
class VfsArchive(Protocol):
    """Read-only virtual filesystem container contract."""

    @property
    def path(self) -> Path: ...

    @property
    def format_name(self) -> str: ...

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]: ...

    def exists(self, vfs_path: str) -> bool: ...

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None: ...

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]: ...

    def read_bytes(self, vfs_path: str) -> bytes: ...

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str: ...

    def close(self) -> None: ...
