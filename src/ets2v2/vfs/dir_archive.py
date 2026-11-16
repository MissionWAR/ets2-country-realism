"""Cross-platform unpacked mod directory reader with traversal & symlink containment."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    DiagnosticKind,
    ProtectedPayloadError,
    VfsEntryMeta,
    detect_3nk,
    normalize_vfs_path,
)


def _matches_prefixes(path: str, normalized_prefixes: list[str]) -> bool:
    if not normalized_prefixes or "" in normalized_prefixes:
        return True
    return any(path == pref or path.startswith(f"{pref}/") for pref in normalized_prefixes)


class DirectoryArchive:
    """Read-only unpacked mod directory reader enforcing archive-root containment."""

    format_name = "directory"

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(self._path)
        if not self._path.is_dir():
            raise NotADirectoryError(self._path)
        self._resolved_root = self._path.resolve()
        self._files: dict[str, Path] = {}
        self._diagnostics: list[ArchiveDiagnostic] = []
        self._diag_keys: set[tuple[DiagnosticKind, str | None, str]] = set()
        self._three_nk_paths: set[str] = set()
        self._scan_tree()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return list(self._diagnostics)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        return None

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

    def _is_within_root(self, candidate: Path) -> Path | None:
        try:
            resolved = candidate.resolve()
        except OSError:
            return None
        if not resolved.is_relative_to(self._resolved_root):
            return None
        return resolved

    def _scan_tree(self) -> None:
        for dirpath_str, dirnames, filenames in os.walk(self._path, followlinks=False):
            cur_dir = Path(dirpath_str)

            safe_dirs: list[str] = []
            for dname in dirnames:
                dpath = cur_dir / dname
                if dpath.is_symlink() and self._is_within_root(dpath) is None:
                    rel_dir = dpath.relative_to(self._path).as_posix()
                    self._add_diagnostic(
                        "path_traversal",
                        rel_dir,
                        "Rejected directory symlink escaping archive root",
                    )
                    continue
                safe_dirs.append(dname)
            dirnames[:] = sorted(safe_dirs)

            for fname in sorted(filenames):
                fpath = cur_dir / fname
                rel_raw = fpath.relative_to(self._path).as_posix()
                resolved = self._is_within_root(fpath)
                if resolved is None:
                    self._add_diagnostic(
                        "path_traversal",
                        rel_raw,
                        "Rejected file symlink escaping archive root",
                    )
                    continue
                if not resolved.is_file():
                    continue
                try:
                    norm = normalize_vfs_path(rel_raw)
                except ValueError as exc:
                    self._add_diagnostic(
                        "path_traversal",
                        rel_raw,
                        f"Rejected unsafe path: {exc}",
                    )
                    continue
                self._files[norm] = resolved

    def exists(self, vfs_path: str) -> bool:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        return norm in self._files

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        target = self._files.get(norm)
        if target is None:
            return None
        size = target.stat().st_size
        return VfsEntryMeta(
            path=norm,
            is_dir=False,
            size=size,
            compressed_size=size,
            compression="none",
            encrypted=False,
            three_nk=norm in self._three_nk_paths,
        )

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]:
        norm_prefixes = (
            [normalize_vfs_path(p, allow_empty=True) for p in prefixes]
            if prefixes is not None
            else []
        )
        return sorted(p for p in self._files if _matches_prefixes(p, norm_prefixes))

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        target = self._files.get(norm)
        if target is None:
            raise FileNotFoundError(f"{norm!r} not found in {self._path}")
        resolved = self._is_within_root(target)
        if resolved is None:
            self._add_diagnostic(
                "path_traversal",
                norm,
                "Path escaped archive root during read",
            )
            raise ValueError(f"Path {norm!r} escapes archive root {self._path}")

        data = resolved.read_bytes()
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
