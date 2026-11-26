"""Automated provenance & CC BY 4.0 license-taint scanner across repo, snapshots, and packages."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ets2_realism.audit.models import TaintScanReport, TaintViolation
from ets2_realism.vfs.dir_archive import DirectoryArchive
from ets2_realism.vfs.hashfs import open_archive
from ets2_realism.vfs.types import VfsArchive

FORBIDDEN_LICENSE_TAINT_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("CC BY-SA", re.compile(r"cc[\s_-]*by[\s_-]*sa", re.IGNORECASE)),
    ("ODbL", re.compile(r"\bodbl\b", re.IGNORECASE)),
    ("OpenStreetMap", re.compile(r"openstreetmap", re.IGNORECASE)),
    (
        "osm-legal-default-speeds",
        re.compile(r"osm[\s_-]*legal[\s_-]*default[\s_-]*speeds", re.IGNORECASE),
    ),
    ("GlobalPetrolPrices", re.compile(r"globalpetrolprices", re.IGNORECASE)),
    ("CC BY-NC-ND", re.compile(r"cc[\s_-]*by[\s_-]*nc[\s_-]*nd", re.IGNORECASE)),
    ("MyLPG", re.compile(r"\bmylpg\b", re.IGNORECASE)),
    ("IEA", re.compile(r"(?:international\s+energy\s+agency|\biea\b)", re.IGNORECASE)),
)

_SCANNABLE_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".sii", ".sui", ".txt", ".json", ".md", ".csv", ".xml", ".yml", ".yaml", ".toml"}
)
_ARCHIVE_SUFFIXES: Final[frozenset[str]] = frozenset({".zip", ".scs"})
_MAX_EXCERPT_CHARS: Final[int] = 160
MAX_TAINT_TEXT_BYTES: Final[int] = 64 * 1024 * 1024  # 64 MiB bounded text read cap


def _read_bounded_text_bytes(path: Path, *, max_bytes: int | None = None) -> bytes:
    limit = max_bytes if max_bytes is not None else MAX_TAINT_TEXT_BYTES
    size = path.stat().st_size
    if size > limit:
        raise ValueError(
            f"File {path} size ({size} bytes) exceeds taint scanner limit ({limit} bytes)"
        )
    with path.open("rb") as fh:
        data = fh.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"File {path} exceeded taint scanner limit ({limit} bytes) while reading")
    return data


def _sanitize_excerpt(line: str) -> str:
    collapsed = " ".join(line.split())
    if not collapsed:
        return "(match)"
    if len(collapsed) > _MAX_EXCERPT_CHARS:
        return collapsed[: _MAX_EXCERPT_CHARS - 3] + "..."
    return collapsed


def _scan_text_bytes(raw: bytes, display_path: str) -> list[TaintViolation]:
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    violations: list[TaintViolation] = []
    seen: set[tuple[str, int]] = set()
    for label, pattern in FORBIDDEN_LICENSE_TAINT_PATTERNS:
        for match in pattern.finditer(text):
            line_idx = text.count("\n", 0, match.start()) + 1
            if (label, line_idx) in seen:
                continue
            seen.add((label, line_idx))
            excerpt_source = lines[line_idx - 1] if 1 <= line_idx <= len(lines) else match.group(0)
            violations.append(
                TaintViolation(
                    path=display_path,
                    marker=label,
                    line_number=line_idx,
                    excerpt=_sanitize_excerpt(excerpt_source),
                )
            )
    return violations


def _scan_vfs_archive(archive: VfsArchive, prefix: str) -> tuple[int, list[TaintViolation]]:
    files_scanned = 0
    violations: list[TaintViolation] = []
    for vfs_path in archive.list_paths():
        suffix = Path(vfs_path).suffix.lower()
        if suffix not in _SCANNABLE_TEXT_SUFFIXES:
            continue
        raw = archive.read_bytes(vfs_path)
        files_scanned += 1
        violations.extend(_scan_text_bytes(raw, f"{prefix}::{vfs_path}"))
    return files_scanned, violations


def scan_package_for_taint(package_path: Path) -> TaintScanReport:
    """Scan an unpacked Workshop/mod directory or ``.zip``/``.scs`` archive for taint markers."""
    if not package_path.exists():
        raise FileNotFoundError(f"Package path does not exist: {package_path}")

    files_scanned = 0
    violations: list[TaintViolation] = []
    prefix = package_path.as_posix()

    if package_path.is_dir():
        with DirectoryArchive(package_path) as dir_arch:
            for vfs_path in dir_arch.list_paths():
                suffix = Path(vfs_path).suffix.lower()
                if suffix in _SCANNABLE_TEXT_SUFFIXES:
                    raw = dir_arch.read_bytes(vfs_path)
                    files_scanned += 1
                    violations.extend(_scan_text_bytes(raw, f"{prefix}/{vfs_path}"))
                elif suffix in _ARCHIVE_SUFFIXES:
                    nested_path = package_path / vfs_path
                    with open_archive(nested_path) as nested_arch:
                        nested_count, nested_violations = _scan_vfs_archive(
                            nested_arch,
                            f"{prefix}/{vfs_path}",
                        )
                        files_scanned += nested_count
                        violations.extend(nested_violations)
    else:
        with open_archive(package_path) as arch:
            arch_count, arch_violations = _scan_vfs_archive(arch, prefix)
            files_scanned += arch_count
            violations.extend(arch_violations)

    sorted_violations = sorted(
        violations,
        key=lambda v: (v.path, v.line_number, v.marker, v.excerpt),
    )
    return TaintScanReport(
        ok=not sorted_violations,
        files_scanned=files_scanned,
        packages_scanned=1,
        snapshots_scanned=0,
        violation_count=len(sorted_violations),
        violations=sorted_violations,
    )


def _display_repo_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def scan_repo_and_artifacts_for_taint(
    repo_root: Path,
    *,
    snapshot_paths: Sequence[Path] = (),
    package_paths: Sequence[Path] = (),
) -> TaintScanReport:
    """Scan clean-room repo registries, lockfile, snapshots, and packages for D-16 taint markers."""
    files_scanned = 0
    violations: list[TaintViolation] = []

    repo_dirs = (
        repo_root / "data" / "laws",
        repo_root / "data" / "curated",
        repo_root / "data" / "mappings",
    )
    for target_dir in repo_dirs:
        if not target_dir.is_dir():
            continue
        for file_path in sorted(p for p in target_dir.rglob("*") if p.is_file()):
            if file_path.suffix.lower() not in _SCANNABLE_TEXT_SUFFIXES:
                continue
            files_scanned += 1
            violations.extend(
                _scan_text_bytes(
                    _read_bounded_text_bytes(file_path),
                    _display_repo_path(file_path, repo_root),
                )
            )

    root_files = (
        repo_root / "state" / "prices.lock.json",
        repo_root / "CHANGELOG_SUMMER.md",
        repo_root / "CHANGELOG_WINTER.md",
    )
    for extra_path in root_files:
        if extra_path.is_file():
            files_scanned += 1
            violations.extend(
                _scan_text_bytes(
                    _read_bounded_text_bytes(extra_path),
                    _display_repo_path(extra_path, repo_root),
                )
            )

    snapshots_scanned = 0
    for snap_path in snapshot_paths:
        if not snap_path.is_file():
            raise FileNotFoundError(f"Snapshot file does not exist: {snap_path}")
        snapshots_scanned += 1
        files_scanned += 1
        violations.extend(
            _scan_text_bytes(
                _read_bounded_text_bytes(snap_path),
                _display_repo_path(snap_path, repo_root),
            )
        )

    packages_scanned = 0
    for pkg_path in package_paths:
        pkg_report = scan_package_for_taint(pkg_path)
        packages_scanned += 1
        files_scanned += pkg_report.files_scanned
        violations.extend(pkg_report.violations)

    sorted_violations = sorted(
        violations,
        key=lambda v: (v.path, v.line_number, v.marker, v.excerpt),
    )
    return TaintScanReport(
        ok=not sorted_violations,
        files_scanned=files_scanned,
        packages_scanned=packages_scanned,
        snapshots_scanned=snapshots_scanned,
        violation_count=len(sorted_violations),
        violations=sorted_violations,
    )
