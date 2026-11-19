"""Canonical Workshop payload SHA-256 hashing, ISO-week versioning, and release ledger."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.registry.models import Season
from ets2v2.sii.document import SiiDocument
from ets2v2.vfs.types import normalize_vfs_path

CANONICAL_VERSION_SENTINEL: Final[str] = "__CANONICAL__"
_MANIFEST_REL_PATH: Final[str] = "universal/manifest.sii"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
_ISO_DATE_PATTERN: Final[str] = r"^\d{4}-\d{2}-\d{2}$"


class PublishedEditionState(BaseModel):
    """Per-edition canonical release state stored inside ``state/published.json``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    anchor_date: str = Field(pattern=_ISO_DATE_PATTERN)
    baseline_game_version: str = Field(min_length=1)
    country_count: int = Field(ge=1)
    file_count: int = Field(ge=1)
    package_version: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    snapshot_sha256: str = Field(pattern=_SHA256_PATTERN)


class PublishedLedger(BaseModel):
    """Locked D-11 ``schema_version: 1`` release ledger tracking editions independently."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    editions: dict[Season, PublishedEditionState] = Field(default_factory=dict)


def _normalize_manifest_bytes(raw: bytes) -> bytes:
    """Replace ``package_version`` with ``__CANONICAL__`` via span-preserving SiiDocument."""
    doc = SiiDocument.parse(raw, require_siinunit=True)
    mod_unit = doc.get_unit(class_name="mod_package")
    if mod_unit is None:
        raise ValueError("Missing mod_package unit in universal/manifest.sii")
    version_attr = mod_unit.get_scalar("package_version")
    if version_attr is None:
        raise ValueError("Missing package_version attribute in universal/manifest.sii")
    doc.update_attribute_value(version_attr, f'"{CANONICAL_VERSION_SENTINEL}"')
    return doc.to_bytes()


def compute_workshop_canonical_sha256(workshop_dir: Path) -> str:
    """Compute a length-prefixed SHA-256 over sorted POSIX files, ignoring ``package_version``."""
    if not workshop_dir.is_dir():
        raise FileNotFoundError(f"Workshop directory does not exist: {workshop_dir}")

    resolved_root = workshop_dir.resolve()
    entries: list[tuple[str, Path]] = []
    for candidate in workshop_dir.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(f"Symlinks are not allowed in Workshop payload: {candidate}")
        if not candidate.is_file():
            continue
        resolved_candidate = candidate.resolve()
        if not resolved_candidate.is_relative_to(resolved_root):
            raise ValueError(f"Workshop entry escapes root directory: {candidate}")
        rel_posix = candidate.relative_to(workshop_dir).as_posix()
        clean_rel = normalize_vfs_path(rel_posix)
        entries.append((clean_rel, candidate))

    entries.sort(key=lambda item: item[0])
    if not any(rel_path == _MANIFEST_REL_PATH for rel_path, _ in entries):
        raise ValueError(f"Missing {_MANIFEST_REL_PATH!r} under Workshop directory: {workshop_dir}")

    hasher = hashlib.sha256()
    for rel_path, file_path in entries:
        raw = file_path.read_bytes()
        payload = _normalize_manifest_bytes(raw) if rel_path == _MANIFEST_REL_PATH else raw
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(str(len(payload)).encode("ascii"))
        hasher.update(b"\x00")
        hasher.update(payload)
        hasher.update(b"\x00")
    return hasher.hexdigest()


def resolve_next_package_version(
    previous: PublishedEditionState | None,
    canonical_sha256: str,
    build_date: date,
    *,
    game_version_prefix: str = "1.62",
) -> tuple[str, bool]:
    """Resolve the next ISO-week ``package_version`` and whether canonical content changed."""
    if previous is not None and previous.payload_sha256 == canonical_sha256:
        return previous.package_version, False

    iso_year, iso_week, _ = build_date.isocalendar()
    base_version = f"{game_version_prefix}-{iso_year}.{iso_week:02d}"

    if previous is None:
        return base_version, True

    if previous.package_version == base_version:
        return f"{base_version}.2", True

    same_week_prefix = f"{base_version}."
    if previous.package_version.startswith(same_week_prefix):
        suffix = previous.package_version[len(same_week_prefix) :]
        if suffix.isdigit() and int(suffix) >= 2:
            return f"{base_version}.{int(suffix) + 1}", True
        return f"{base_version}.2", True

    return base_version, True


def serialize_ledger_bytes(ledger: PublishedLedger) -> bytes:
    """Serialize ``PublishedLedger`` to canonical UTF-8 no-BOM LF sorted JSON bytes."""
    payload: object = ledger.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def load_published_ledger(path: Path) -> PublishedLedger:
    """Load and strictly validate a ``state/published.json`` v1 release ledger."""
    if not path.is_file():
        raise FileNotFoundError(f"Published ledger does not exist: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"Published ledger must not contain a UTF-8 BOM: {path}")
    if b"\r" in raw:
        raise ValueError(f"Published ledger must use LF line endings only: {path}")
    return PublishedLedger.model_validate_json(raw.decode("utf-8"))


def write_published_ledger(ledger: PublishedLedger, path: Path) -> bytes:
    """Write ``PublishedLedger`` deterministically to ``path`` and return serialized bytes."""
    raw = serialize_ledger_bytes(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw
