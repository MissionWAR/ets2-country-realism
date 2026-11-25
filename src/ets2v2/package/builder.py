"""Dual-target Workshop unpacked and deterministic local ZIP Core mod packager."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from ets2v2.baseline.models import (
    BaselineManifest,
    CountriesBaseline,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.normalize.lockfile import load_prices_lockfile
from ets2v2.normalize.models import PricesLockfile
from ets2v2.package.metadata import (
    DEFAULT_AUTHOR,
    render_description_txt,
    render_manifest_sii,
    render_versions_sii,
)
from ets2v2.package.synthesize import (
    synthesize_country_sui,
    synthesize_speed_limits_sii,
)
from ets2v2.package.totems import compile_totem_payloads
from ets2v2.registry.loader import load_law_registry
from ets2v2.registry.models import Season
from ets2v2.registry.snapshot import build_realism_snapshot
from ets2v2.registry.timezone import DEFAULT_ANCHOR_YEAR, resolve_season_anchor_date
from ets2v2.vfs.types import normalize_vfs_path

ZIP_FIXED_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
ZIP_UNIX_SYSTEM: Final[int] = 3
ZIP_FILE_EXTERNAL_ATTR: Final[int] = 0o100644 << 16
ZIP_COMPRESS_LEVEL: Final[int] = 6

LOCAL_ZIP_FILENAMES: Final[dict[Season, str]] = {
    "summer": "ETS2V2_Core_Summer.zip",
    "winter": "ETS2V2_Core_Winter.zip",
}


class BuiltEditionPaths(BaseModel):
    """Output paths and deterministic metadata for one built seasonal Core edition."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    edition: Season
    package_version: str
    workshop_dir: Path
    local_zip_path: Path
    workshop_file_count: int
    local_zip_sha256: str


def validate_rel_path(rel_path: str) -> str:
    """Validate and normalize a relative POSIX staging/archive path (rejecting \\ and ..)."""
    if "\\" in rel_path or rel_path.startswith("/"):
        raise ValueError(f"Invalid relative package path: {rel_path!r}")
    normalized = normalize_vfs_path(rel_path)
    if normalized != rel_path:
        raise ValueError(f"Non-canonical relative package path: {rel_path!r} -> {normalized!r}")
    return normalized


def ensure_contained(target: Path, root: Path) -> Path:
    """Verify ``target`` resolves strictly beneath ``root`` (preventing traversal/unsafe clean)."""
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    if resolved_target == resolved_root or not resolved_target.is_relative_to(resolved_root):
        raise ValueError(f"Target path {target} escapes root directory {root}")
    return resolved_target


def default_package_version(ref_date: date, game_version: str) -> str:
    parts = game_version.split(".")
    major_minor = ".".join(parts[:2]) if len(parts) >= 2 else "1.62"
    iso_year, iso_week, _ = ref_date.isocalendar()
    return f"{major_minor}-{iso_year}.{iso_week:02d}"


def write_deterministic_zip(zip_path: Path, entries: Mapping[str, bytes]) -> str:
    """Write entries into a byte-deterministic ZIP archive and return its SHA-256 hex digest."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path in sorted(entries):
            clean_path = validate_rel_path(rel_path)
            zinfo = zipfile.ZipInfo(filename=clean_path, date_time=ZIP_FIXED_TIMESTAMP)
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            zinfo.create_system = ZIP_UNIX_SYSTEM
            zinfo.external_attr = ZIP_FILE_EXTERNAL_ATTR
            zf.writestr(
                zinfo,
                entries[rel_path],
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=ZIP_COMPRESS_LEVEL,
            )
    return hashlib.sha256(zip_path.read_bytes()).hexdigest()


def write_workshop_tree(
    workshop_dir: Path,
    out_dir: Path,
    workshop_files: Mapping[str, bytes],
) -> int:
    """Write a clean unpacked Workshop root strictly contained inside ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_contained(workshop_dir, out_dir)
    if workshop_dir.is_symlink() or workshop_dir.is_file():
        workshop_dir.unlink()
    elif workshop_dir.exists():
        shutil.rmtree(workshop_dir)
    workshop_dir.mkdir(parents=True, exist_ok=True)

    for rel_path in sorted(workshop_files):
        clean_rel = validate_rel_path(rel_path)
        dest = workshop_dir / clean_rel
        ensure_contained(dest, workshop_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(workshop_files[rel_path])
    return len(workshop_files)


# Backwards-compatible private aliases
_validate_rel_path = validate_rel_path
_ensure_contained = ensure_contained
_default_package_version = default_package_version
_write_deterministic_zip = write_deterministic_zip


def build_core_edition(
    edition: Season,
    out_dir: Path,
    *,
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    icons_dir: Path = Path("assets/icons"),
    prices_lock_path: Path = Path("state/prices.lock.json"),
    prices_lock: PricesLockfile | None = None,
    package_version: str | None = None,
    author: str = DEFAULT_AUTHOR,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    override_date: date | None = None,
) -> BuiltEditionPaths:
    """Build unpacked Workshop root and deterministic local ZIP for one seasonal Core edition."""
    icon_src = icons_dir / f"{edition}.jpg"
    if not icon_src.is_file():
        raise FileNotFoundError(f"Missing checked-in clean-room icon for {edition!r}: {icon_src}")
    icon_bytes = icon_src.read_bytes()

    registry = load_law_registry(laws_dir, mappings_path)
    bl_countries = CountriesBaseline.model_validate_json(
        (baseline_dir / "countries.json").read_text("utf-8")
    )
    bl_speeds = SpeedLimitsBaseline.model_validate_json(
        (baseline_dir / "speed_limits.json").read_text("utf-8")
    )
    bl_fuel_boards = FuelBoardsBaseline.model_validate_json(
        (baseline_dir / "fuel_boards.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (baseline_dir / "locales.json").read_text("utf-8")
    )
    resolved_lock = (
        prices_lock if prices_lock is not None else load_prices_lockfile(prices_lock_path)
    )

    manifest_json_path = baseline_dir / "manifest.json"
    if manifest_json_path.is_file():
        bl_manifest = BaselineManifest.model_validate_json(manifest_json_path.read_text("utf-8"))
        game_version = bl_manifest.game_version
    else:
        game_version = registry.mappings.baseline_game_version

    ref_date = resolve_season_anchor_date(
        edition,
        anchor_year=anchor_year,
        override_date=override_date,
    )
    resolved_version = (
        package_version
        if package_version is not None
        else _default_package_version(ref_date, game_version)
    )

    snapshot = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        edition,
        anchor_year=anchor_year,
        override_date=override_date,
        baseline_game_version=game_version,
        prices_lock=resolved_lock,
    )

    resolved_by_slug = {country.ets2_slug: country for country in snapshot.countries.values()}
    speeds_by_slug = {entry.slug: entry for entry in bl_speeds.speed_limits}

    # Shared mod payload entries (relative to universal/ or local ZIP root)
    shared_payloads: dict[str, bytes] = {
        "mod_icon.jpg": icon_bytes,
        "description.txt": render_description_txt(edition),
    }

    for bl_country in sorted(bl_countries.countries, key=lambda c: c.slug):
        slug = bl_country.slug
        resolved_country = resolved_by_slug.get(slug)
        if resolved_country is None:
            raise ValueError(f"Missing resolved snapshot country for baseline slug {slug!r}")
        bl_speed = speeds_by_slug.get(slug)
        if bl_speed is None:
            raise ValueError(f"Missing baseline speed_limits entry for slug {slug!r}")

        sui_rel = _validate_rel_path(f"def/country/{slug}.sui")
        speed_rel = _validate_rel_path(f"def/country/{slug}/speed_limits.sii")
        shared_payloads[sui_rel] = synthesize_country_sui(bl_country, resolved_country)
        shared_payloads[speed_rel] = synthesize_speed_limits_sii(bl_speed, resolved_country)

    compiled_totems = compile_totem_payloads(bl_fuel_boards, bl_locales, resolved_lock)
    for rel_path, payload in compiled_totems.board_files.items():
        clean_rel = _validate_rel_path(rel_path)
        if clean_rel in shared_payloads:
            raise ValueError(f"Duplicate package payload path: {clean_rel!r}")
        shared_payloads[clean_rel] = payload
    for rel_path, payload in compiled_totems.locale_files.items():
        clean_rel = _validate_rel_path(rel_path)
        if clean_rel in shared_payloads:
            raise ValueError(f"Duplicate package payload path: {clean_rel!r}")
        shared_payloads[clean_rel] = payload

    # Target A: Workshop unpacked root (<out_dir>/workshop/<edition>/)
    workshop_dir = out_dir / "workshop" / edition
    workshop_files: dict[str, bytes] = {
        "versions.sii": render_versions_sii(),
        "universal/manifest.sii": render_manifest_sii(
            edition,
            resolved_version,
            workshop=True,
            author=author,
        ),
    }
    for rel_path, payload in shared_payloads.items():
        workshop_files[validate_rel_path(f"universal/{rel_path}")] = payload

    workshop_file_count = write_workshop_tree(workshop_dir, out_dir, workshop_files)

    # Target B: Deterministic local ZIP (<out_dir>/local/ETS2V2_Core_{Summer|Winter}.zip)
    local_entries: dict[str, bytes] = {
        "manifest.sii": render_manifest_sii(
            edition,
            resolved_version,
            workshop=False,
            author=author,
        ),
        **shared_payloads,
    }
    local_zip_path = out_dir / "local" / LOCAL_ZIP_FILENAMES[edition]
    ensure_contained(local_zip_path, out_dir)
    local_zip_sha256 = write_deterministic_zip(local_zip_path, local_entries)

    return BuiltEditionPaths(
        edition=edition,
        package_version=resolved_version,
        workshop_dir=workshop_dir,
        local_zip_path=local_zip_path,
        workshop_file_count=workshop_file_count,
        local_zip_sha256=local_zip_sha256,
    )


def build_core_editions(
    out_dir: Path,
    *,
    editions: Sequence[Season] = ("summer", "winter"),
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    icons_dir: Path = Path("assets/icons"),
    prices_lock_path: Path = Path("state/prices.lock.json"),
    prices_lock: PricesLockfile | None = None,
    package_version: str | None = None,
    package_versions: Mapping[Season, str] | None = None,
    author: str = DEFAULT_AUTHOR,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    override_date: date | None = None,
) -> dict[Season, BuiltEditionPaths]:
    """Build one or both seasonal Core editions (Workshop unpacked + deterministic local ZIP)."""
    results: dict[Season, BuiltEditionPaths] = {}
    for edition in editions:
        edition_version = (
            package_versions[edition]
            if package_versions is not None and edition in package_versions
            else package_version
        )
        results[edition] = build_core_edition(
            edition,
            out_dir,
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            baseline_dir=baseline_dir,
            icons_dir=icons_dir,
            prices_lock_path=prices_lock_path,
            prices_lock=prices_lock,
            package_version=edition_version,
            author=author,
            anchor_year=anchor_year,
            override_date=override_date,
        )
    return results
