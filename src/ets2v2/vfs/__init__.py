"""Clean-room cross-platform ETS2 VFS subsystem."""

from __future__ import annotations

from ets2v2.vfs.cityhash import cityhash64, hash_vfs_path
from ets2v2.vfs.dir_archive import DirectoryArchive
from ets2v2.vfs.hashfs import (
    HashFsV1Archive,
    HashFsV2Archive,
    ProtectedArchiveStub,
    detect_3nk,
    open_archive,
)
from ets2v2.vfs.stack import (
    EffectiveVfsEntry,
    VfsLayer,
    VfsStack,
    classify_mount_path,
    is_empty_sii_stub,
)
from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    CompressionKind,
    DiagnosticKind,
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsArchive,
    VfsEntryMeta,
    normalize_vfs_path,
)
from ets2v2.vfs.zip_archive import ZipArchive

__all__ = [
    "ArchiveDiagnostic",
    "CompressionKind",
    "DiagnosticKind",
    "DirectoryArchive",
    "EffectiveVfsEntry",
    "HashFsV1Archive",
    "HashFsV2Archive",
    "ProtectedArchiveStub",
    "ProtectedPayloadError",
    "UnsupportedCompressionError",
    "VfsArchive",
    "VfsEntryMeta",
    "VfsLayer",
    "VfsStack",
    "ZipArchive",
    "cityhash64",
    "classify_mount_path",
    "detect_3nk",
    "hash_vfs_path",
    "is_empty_sii_stub",
    "normalize_vfs_path",
    "open_archive",
]
