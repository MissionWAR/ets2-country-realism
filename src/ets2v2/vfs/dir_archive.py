"""Cross-platform unpacked mod directory reader with traversal & symlink containment."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    DiagnosticCollector,
    VfsEntryMeta,
    decode_vfs_text,
    filter_paths_by_prefixes,
    normalize_vfs_path,
    record_3nk_if_present,
)


def _is_dir_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction()) if callable(is_junction) else False


class DirectoryArchive:
    """Read-only unpacked mod directory reader enforcing archive-root containment."""

    format_name = "directory"

    def __init__(
        self,
        path: Path,
        *,
        include_top_dirs: frozenset[str] | None = None,
    ) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(self._path)
        if not self._path.is_dir():
            raise NotADirectoryError(self._path)
        self._resolved_root = self._path.resolve()
        self._include_top_dirs = (
            frozenset(name.lower() for name in include_top_dirs)
            if include_top_dirs is not None
            else None
        )
        self._files: dict[str, Path] = {}
        self._diag = DiagnosticCollector(self._path)
        self._three_nk_paths: set[str] = set()
        self._scan_tree()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return self._diag.items

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        return None

    def _is_within_root(self, candidate: Path) -> Path | None:
        try:
            resolved = candidate.resolve()
        except OSError:
            return None
        if not resolved.is_relative_to(self._resolved_root):
            return None
        return resolved

    def _scan_tree(self) -> None:
        visited_dirs: set[Path] = {self._resolved_root}
        for dirpath_str, dirnames, filenames in os.walk(self._path, followlinks=False):
            cur_dir = Path(dirpath_str)
            cur_resolved = self._is_within_root(cur_dir)
            if cur_resolved is None:
                dirnames[:] = []
                continue
            visited_dirs.add(cur_resolved)

            safe_dirs: list[str] = []
            is_root = cur_dir == self._path
            for dname in dirnames:
                if (
                    is_root
                    and self._include_top_dirs is not None
                    and dname.lower() not in self._include_top_dirs
                    and not dname.lower().startswith("dlc_")
                ):
                    continue
                dpath = cur_dir / dname
                is_junction = _is_dir_junction(dpath)
                if dpath.is_symlink() or is_junction:
                    resolved_dir = self._is_within_root(dpath)
                    if resolved_dir is None:
                        rel_dir = dpath.relative_to(self._path).as_posix()
                        detail = (
                            "Rejected directory junction escaping archive root"
                            if is_junction
                            else "Rejected directory symlink escaping archive root"
                        )
                        self._diag.add("path_traversal", rel_dir, detail)
                        continue
                    if is_junction:
                        if resolved_dir in visited_dirs:
                            continue
                        visited_dirs.add(resolved_dir)
                safe_dirs.append(dname)
            dirnames[:] = sorted(safe_dirs)

            for fname in sorted(filenames):
                fpath = cur_dir / fname
                rel_raw = fpath.relative_to(self._path).as_posix()
                resolved = self._is_within_root(fpath)
                if resolved is None:
                    self._diag.add(
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
                    self._diag.add(
                        "path_traversal",
                        rel_raw,
                        f"Rejected unsafe path: {exc}",
                    )
                    continue
                self._files[norm] = fpath.absolute()

    def exists(self, vfs_path: str) -> bool:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        return norm in self._files

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        target = self._files.get(norm)
        if target is None:
            return None
        resolved = self._is_within_root(target)
        if resolved is None:
            self._diag.add(
                "path_traversal",
                norm,
                "Path escaped archive root during metadata inspection",
            )
            return None
        try:
            size = resolved.stat().st_size
        except OSError:
            return None
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
        return filter_paths_by_prefixes(self._files, prefixes)

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        target = self._files.get(norm)
        if target is None:
            raise FileNotFoundError(f"{norm!r} not found in {self._path}")
        resolved = self._is_within_root(target)
        if resolved is None:
            self._diag.add(
                "path_traversal",
                norm,
                "Path escaped archive root during read",
            )
            raise ValueError(f"Path {norm!r} escapes archive root {self._path}")

        data = resolved.read_bytes()
        record_3nk_if_present(data, norm, self._three_nk_paths, self._diag)
        return data

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str:
        return decode_vfs_text(self.read_bytes(vfs_path), vfs_path, encoding)
