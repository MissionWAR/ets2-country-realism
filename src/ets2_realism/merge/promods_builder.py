"""Standalone all-in-one ProMods Companion Builder (MAP-01, D-04..D-08)."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from ets2_realism.baseline.models import (
    BaselineManifest,
    CountriesBaseline,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2_realism.merge.aliases import CountryResolver
from ets2_realism.merge.load_order import BaselineVirtualArchive
from ets2_realism.merge.policy import apply_country_policy, apply_speed_limits_policy
from ets2_realism.merge.promods_discovery import (
    discover_promods_packs,
    resolve_mod_dir,
)
from ets2_realism.merge.promods_fuel import compile_promods_fuel_locales
from ets2_realism.merge.scanner import ScannedMapCountry, scan_active_countries
from ets2_realism.package.builder import (
    default_package_version,
    ensure_contained,
    validate_rel_path,
    write_deterministic_zip,
    write_workshop_tree,
)
from ets2_realism.package.metadata import (
    DEFAULT_AUTHOR,
    render_promods_description_txt,
    render_promods_manifest_sii,
    render_versions_sii,
)
from ets2_realism.package.totems import compile_totem_payloads, snapshot_to_totem_lockfile
from ets2_realism.registry.loader import load_country_aliases
from ets2_realism.registry.models import Season
from ets2_realism.registry.snapshot import load_or_build_snapshot
from ets2_realism.registry.timezone import DEFAULT_ANCHOR_YEAR
from ets2_realism.validate.workshop import validate_local_zip, validate_workshop_package
from ets2_realism.vfs.hashfs import open_archive
from ets2_realism.vfs.stack import VfsStack

PROMODS_LOCAL_ZIP_FILENAMES: Final[dict[Season, str]] = {
    "summer": "ETS2_Country_Realism_ProMods_Summer.zip",
    "winter": "ETS2_Country_Realism_ProMods_Winter.zip",
}

_ALLOWED_REPO_OUTPUT_SUBDIRS: Final[frozenset[str]] = frozenset(
    {"dist", "out", "build", "raw", "vendor"}
)


class ProModsBuildReport(BaseModel):
    """Structured build & validation summary for one standalone ProMods Edition."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    edition: Season
    package_version: str
    packs_discovered: list[str]
    countries_patched: int
    vanilla_countries_emitted: int
    promods_countries_emitted: int
    pm_fuel_modules_emitted: list[str]
    workshop_dir: Path
    local_zip_path: Path
    workshop_file_count: int
    local_zip_sha256: str
    validation_ok: bool


def _is_repo_root(path: Path) -> bool:
    return (path / ".git").exists() or (path / "pyproject.toml").is_file()


def _candidate_repo_roots(explicit_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    if explicit_root is not None:
        roots.append(explicit_root.resolve())
        return roots

    package_root = Path(__file__).resolve().parents[3]
    roots.append(package_root)
    cwd = Path.cwd().resolve()
    if cwd != package_root and _is_repo_root(cwd):
        roots.append(cwd)
    return roots


def assert_out_dir_not_tracked(out_dir: Path, *, repo_root: Path | None = None) -> None:
    """Refuse ``--out-dir`` at repo root or inside non-gitignored repo subdirs (D-08, T-04-05)."""
    resolved_out = out_dir.resolve()
    for root in _candidate_repo_roots(repo_root):
        if resolved_out == root:
            raise ValueError(
                f"Refusing to write ProMods/Combo output directly into repository root: {out_dir}"
            )
        if resolved_out.is_relative_to(root):
            top_dir = resolved_out.relative_to(root).parts[0]
            if top_dir.lower() not in _ALLOWED_REPO_OUTPUT_SUBDIRS:
                raise ValueError(
                    f"Refusing to write ProMods/Combo output inside tracked/unignored repository "
                    f"directory {root / top_dir}: {out_dir}"
                )


def _deduplicate_scanned_countries(
    countries: Sequence[ScannedMapCountry],
) -> list[ScannedMapCountry]:
    """Keep the highest-priority scanned fragment per slug to prevent duplicate .sui/.sii emits."""
    winners: dict[str, ScannedMapCountry] = {}
    for item in countries:
        existing = winners.get(item.slug)
        if existing is None or (item.winning_priority, item.fragment_path) >= (
            existing.winning_priority,
            existing.fragment_path,
        ):
            winners[item.slug] = item
    return [winners[slug] for slug in sorted(winners)]


def build_promods_edition(
    edition: Season,
    out_dir: Path,
    *,
    mod_dir: Path | None = None,
    game_dir: Path | None = None,
    snapshot_path: Path | None = None,
    checksums_path: Path | None = None,
    require_all_packs: bool = False,
    eu_def: Path | None = None,
    eu_assets: Path | None = None,
    me_def: Path | None = None,
    me_assets: Path | None = None,
    ma_def: Path | None = None,
    ma_assets: Path | None = None,
    tgs_def: Path | None = None,
    tgs_assets: Path | None = None,
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    aliases_path: Path = Path("data/mappings/country_aliases.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    icons_dir: Path = Path("assets/icons"),
    prices_lock_path: Path = Path("state/prices.lock.json"),
    package_version: str | None = None,
    author: str = DEFAULT_AUTHOR,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    repo_root: Path | None = None,
) -> ProModsBuildReport:
    """Build & offline-validate one standalone all-in-one ProMods Edition (Workshop + local ZIP)."""
    assert_out_dir_not_tracked(out_dir, repo_root=repo_root)

    icon_src = icons_dir / f"promods_{edition}.jpg"
    if not icon_src.is_file():
        raise FileNotFoundError(
            f"Missing checked-in clean-room ProMods icon for {edition!r}: {icon_src}"
        )
    icon_bytes = icon_src.read_bytes()

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
    aliases = load_country_aliases(aliases_path)

    snapshot = load_or_build_snapshot(
        edition,
        snapshot_path=snapshot_path,
        checksums_path=checksums_path,
        laws_dir=laws_dir,
        mappings_path=mappings_path,
        baseline_dir=baseline_dir,
        prices_lock_path=prices_lock_path,
        anchor_year=anchor_year,
    )

    manifest_json_path = baseline_dir / "manifest.json"
    if manifest_json_path.is_file():
        bl_manifest = BaselineManifest.model_validate_json(manifest_json_path.read_text("utf-8"))
        game_version = bl_manifest.game_version
    else:
        game_version = snapshot.baseline_game_version

    ref_date = date.fromisoformat(snapshot.anchor_date)
    resolved_version = (
        package_version
        if package_version is not None
        else default_package_version(ref_date, game_version)
    )

    effective_mod_dir = (
        resolve_mod_dir(mod_dir) if (mod_dir is not None or eu_def is None) else None
    )
    pack_set = discover_promods_packs(
        effective_mod_dir,
        require_eu_def=True,
        require_all_packs=require_all_packs,
        eu_def=eu_def,
        eu_assets=eu_assets,
        me_def=me_def,
        me_assets=me_assets,
        ma_def=ma_def,
        ma_assets=ma_assets,
        tgs_def=tgs_def,
        tgs_assets=tgs_assets,
    )

    ordered_packs = pack_set.ordered_packs()
    stack = VfsStack()
    try:
        if game_dir is not None:
            def_scs = game_dir / "def.scs"
            if not def_scs.is_file():
                raise FileNotFoundError(
                    f"Required Vanilla def.scs missing under --game-dir: {def_scs}"
                )
            stack.mount(open_archive(def_scs), name="vanilla_def", priority=0)
        else:
            stack.mount(
                BaselineVirtualArchive.from_baselines(bl_countries, bl_speeds, snapshot=snapshot),
                name="vanilla_baseline_1_62",
                priority=0,
            )

        for pack_spec in ordered_packs:
            stack.mount(
                open_archive(pack_spec.path),
                name=pack_spec.layer_name,
                priority=pack_spec.priority,
            )

        scan_result = scan_active_countries(stack)
        active_countries = _deduplicate_scanned_countries(scan_result.countries)
        vanilla_slugs = frozenset(c.slug for c in bl_countries.countries)
        resolver = CountryResolver(snapshot, aliases)

        shared_payloads: dict[str, bytes] = {
            "mod_icon.jpg": icon_bytes,
            "description.txt": render_promods_description_txt(edition),
        }

        vanilla_emitted = 0
        promods_emitted = 0

        for scanned in active_countries:
            resolution = resolver.resolve(scanned.slug, scanned.country_data)
            if resolution.country is None:
                continue

            snapshot_country = resolution.country
            clean_frag_rel = validate_rel_path(scanned.fragment_path)
            country_result = apply_country_policy(
                scanned.raw_bytes,
                scanned.country_data,
                snapshot_country,
                iana_timezone_override=resolution.iana_timezone_override,
                ref_date=ref_date,
                supported_tz_keys=bl_locales.tz_keys,
                rel_path=clean_frag_rel,
            )
            shared_payloads[clean_frag_rel] = country_result.rendered_bytes
            if scanned.slug in vanilla_slugs:
                vanilla_emitted += 1
            else:
                promods_emitted += 1

            if scanned.speed_limits_path is not None and scanned.speed_limits_raw is not None:
                spd_rel = validate_rel_path(scanned.speed_limits_path)
                spd_result = apply_speed_limits_policy(
                    scanned.speed_limits_raw,
                    scanned.country_data,
                    snapshot_country,
                    rel_path=spd_rel,
                )
                if spd_result.rendered_bytes is not None:
                    shared_payloads[spd_rel] = spd_result.rendered_bytes

        # Vanilla Option 4b 460 sign boards + 43-locale local_module.ets2r_fuel.sii
        totem_lockfile = snapshot_to_totem_lockfile(snapshot)
        compiled_totems = compile_totem_payloads(bl_fuel_boards, bl_locales, totem_lockfile)
        for rel_path, payload in compiled_totems.board_files.items():
            clean_rel = validate_rel_path(rel_path)
            shared_payloads[clean_rel] = payload
        for rel_path, payload in compiled_totems.locale_files.items():
            clean_rel = validate_rel_path(rel_path)
            shared_payloads[clean_rel] = payload

        # ProMods 43-locale local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii
        compiled_pm_fuel = compile_promods_fuel_locales(stack, bl_locales, snapshot)
        for rel_path, payload in compiled_pm_fuel.locale_files.items():
            clean_rel = validate_rel_path(rel_path)
            shared_payloads[clean_rel] = payload
        pm_modules_emitted: list[str] = [str(name) for name in sorted(compiled_pm_fuel.modules)]
    finally:
        stack.close()

    # Target A: Workshop unpacked root (<out_dir>/workshop/promods-{summer|winter}/)
    workshop_parent = out_dir / "workshop"
    workshop_dir = workshop_parent / f"promods-{edition}"
    workshop_files: dict[str, bytes] = {
        "versions.sii": render_versions_sii(),
        "universal/manifest.sii": render_promods_manifest_sii(
            edition,
            resolved_version,
            workshop=True,
            author=author,
        ),
    }
    for rel_path, payload in shared_payloads.items():
        workshop_files[validate_rel_path(f"universal/{rel_path}")] = payload

    # Target B: Deterministic local ZIP (<out_dir>/local/ETS2_Country_Realism_ProMods_*.zip)
    local_entries: dict[str, bytes] = {
        "manifest.sii": render_promods_manifest_sii(
            edition,
            resolved_version,
            workshop=False,
            author=author,
        ),
        **shared_payloads,
    }
    local_parent = out_dir / "local"
    local_zip_path = local_parent / PROMODS_LOCAL_ZIP_FILENAMES[edition]
    ensure_contained(workshop_dir, out_dir)
    ensure_contained(local_zip_path, out_dir)

    workshop_parent.mkdir(parents=True, exist_ok=True)
    local_parent.mkdir(parents=True, exist_ok=True)

    staged_ws = Path(tempfile.mkdtemp(dir=workshop_parent, prefix=f".tmp_promods-{edition}_"))
    with tempfile.NamedTemporaryFile(
        dir=local_parent,
        prefix=f".tmp_promods_{edition}_",
        suffix=".zip",
        delete=False,
    ) as tmp_zip_fh:
        staged_zip = Path(tmp_zip_fh.name)

    backup_ws: Path | None = None
    try:
        workshop_file_count = write_workshop_tree(staged_ws, out_dir, workshop_files)
        local_zip_sha256 = write_deterministic_zip(staged_zip, local_entries)

        # Mandatory Offline SCS Validator hard gate on BOTH staged targets BEFORE promotion (HI-05)
        ws_report = validate_workshop_package(
            staged_ws,
            baseline_dir=baseline_dir,
            profile="promods",
        )
        if not ws_report.ok:
            details = "; ".join(f"{i.code} [{i.path}]: {i.detail}" for i in ws_report.issues[:10])
            raise ValueError(f"ProMods Workshop validation failed for {workshop_dir}: {details}")

        zip_report = validate_local_zip(
            staged_zip,
            baseline_dir=baseline_dir,
            profile="promods",
        )
        if not zip_report.ok:
            details = "; ".join(f"{i.code} [{i.path}]: {i.detail}" for i in zip_report.issues[:10])
            raise ValueError(f"ProMods local ZIP validation failed for {local_zip_path}: {details}")

        # Both staged targets passed validation -> promote atomically
        if workshop_dir.is_symlink() or workshop_dir.is_file():
            workshop_dir.unlink()
        elif workshop_dir.exists():
            backup_ws = workshop_parent / f".bak_{staged_ws.name}"
            if backup_ws.exists():
                shutil.rmtree(backup_ws)
            workshop_dir.rename(backup_ws)
        try:
            staged_ws.rename(workshop_dir)
            os.replace(staged_zip, local_zip_path)
        except Exception:
            if backup_ws is not None and backup_ws.exists() and not workshop_dir.exists():
                backup_ws.rename(workshop_dir)
            raise
        if backup_ws is not None and backup_ws.exists():
            shutil.rmtree(backup_ws, ignore_errors=True)
    except Exception:
        if staged_ws.exists():
            shutil.rmtree(staged_ws, ignore_errors=True)
        if staged_zip.exists():
            staged_zip.unlink(missing_ok=True)
        raise

    return ProModsBuildReport(
        edition=edition,
        package_version=resolved_version,
        packs_discovered=[spec.layer_name for spec in ordered_packs],
        countries_patched=vanilla_emitted + promods_emitted,
        vanilla_countries_emitted=vanilla_emitted,
        promods_countries_emitted=promods_emitted,
        pm_fuel_modules_emitted=pm_modules_emitted,
        workshop_dir=workshop_dir,
        local_zip_path=local_zip_path,
        workshop_file_count=workshop_file_count,
        local_zip_sha256=local_zip_sha256,
        validation_ok=True,
    )


def build_promods_editions(
    out_dir: Path,
    *,
    editions: Sequence[Season] = ("summer", "winter"),
    mod_dir: Path | None = None,
    game_dir: Path | None = None,
    snapshot_path: Path | None = None,
    checksums_path: Path | None = None,
    require_all_packs: bool = False,
    eu_def: Path | None = None,
    eu_assets: Path | None = None,
    me_def: Path | None = None,
    me_assets: Path | None = None,
    ma_def: Path | None = None,
    ma_assets: Path | None = None,
    tgs_def: Path | None = None,
    tgs_assets: Path | None = None,
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    aliases_path: Path = Path("data/mappings/country_aliases.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    icons_dir: Path = Path("assets/icons"),
    prices_lock_path: Path = Path("state/prices.lock.json"),
    package_version: str | None = None,
    author: str = DEFAULT_AUTHOR,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    repo_root: Path | None = None,
) -> dict[Season, ProModsBuildReport]:
    """Build one or both standalone seasonal ProMods Editions."""
    if snapshot_path is not None and len(editions) > 1:
        raise ValueError(
            "--snapshot targets a single season; pass --edition summer or --edition winter"
        )

    results: dict[Season, ProModsBuildReport] = {}
    for edition in editions:
        results[edition] = build_promods_edition(
            edition,
            out_dir,
            mod_dir=mod_dir,
            game_dir=game_dir,
            snapshot_path=snapshot_path,
            checksums_path=checksums_path,
            require_all_packs=require_all_packs,
            eu_def=eu_def,
            eu_assets=eu_assets,
            me_def=me_def,
            me_assets=me_assets,
            ma_def=ma_def,
            ma_assets=ma_assets,
            tgs_def=tgs_def,
            tgs_assets=tgs_assets,
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            aliases_path=aliases_path,
            baseline_dir=baseline_dir,
            icons_dir=icons_dir,
            prices_lock_path=prices_lock_path,
            package_version=package_version,
            author=author,
            anchor_year=anchor_year,
            repo_root=repo_root,
        )
    return results


__all__ = [
    "PROMODS_LOCAL_ZIP_FILENAMES",
    "ProModsBuildReport",
    "assert_out_dir_not_tracked",
    "build_promods_edition",
    "build_promods_editions",
]
