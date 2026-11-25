"""Standalone all-in-one ProMods Companion Builder (MAP-01, D-04..D-08)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Final, Self

from pydantic import BaseModel, ConfigDict

from ets2v2.baseline.models import (
    BaselineManifest,
    CountriesBaseline,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.merge.promods_discovery import (
    discover_promods_packs,
    resolve_mod_dir,
)
from ets2v2.merge.promods_fuel import compile_promods_fuel_locales
from ets2v2.package.builder import (
    default_package_version,
    ensure_contained,
    validate_rel_path,
    write_deterministic_zip,
    write_workshop_tree,
)
from ets2v2.package.metadata import (
    DEFAULT_AUTHOR,
    render_promods_description_txt,
    render_promods_manifest_sii,
    render_versions_sii,
)
from ets2v2.package.synthesize import (
    synthesize_country_sui,
    synthesize_speed_limits_sii,
)
from ets2v2.package.totems import compile_totem_payloads, snapshot_to_totem_lockfile
from ets2v2.registry.loader import load_country_aliases
from ets2v2.registry.models import CountryAliasEntry, CountryAliasRegistry, RoadVehicleClass, Season
from ets2v2.registry.snapshot import (
    RealismSnapshot,
    RealismSnapshotCountry,
    load_or_build_snapshot,
)
from ets2v2.registry.timezone import DEFAULT_ANCHOR_YEAR, resolve_ets2_timezone
from ets2v2.sii.country import (
    CountryDataModel,
    CountryDataPatch,
    parse_country_data,
    parse_country_includes,
    patch_country_data,
)
from ets2v2.sii.hygiene import serialize_sii_text, validate_sii_hygiene
from ets2v2.sii.speed_limits import LaneSpeedRule, parse_speed_limits, patch_speed_limits
from ets2v2.validate.workshop import validate_local_zip, validate_workshop_package
from ets2v2.vfs.hashfs import open_archive
from ets2v2.vfs.stack import VfsStack
from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsEntryMeta,
    decode_vfs_text,
    filter_paths_by_prefixes,
    normalize_vfs_path,
)

PROMODS_LOCAL_ZIP_FILENAMES: Final[dict[Season, str]] = {
    "summer": "ETS2V2_ProMods_Summer.zip",
    "winter": "ETS2V2_ProMods_Winter.zip",
}

_FORBIDDEN_REPO_SUBDIRS: Final[tuple[str, ...]] = (
    "data",
    "src",
    "tests",
    "state",
    "assets",
    ".github",
    ".git",
)

_COUNTRY_REG_SII_RE: Final[re.Pattern[str]] = re.compile(r"^def/country(?:\.[^/]+)?\.sii$")
_COUNTRY_FRAG_RE: Final[re.Pattern[str]] = re.compile(r"^def/country/([a-z0-9_]+)\.(?:sui|sii)$")
_ROAD_CLASSES: Final[tuple[RoadVehicleClass, ...]] = ("car", "truck", "bus")


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


class _InMemoryBaselineArchive:
    """Clean-room in-memory Vanilla 1.62 VFS base layer when ``--game-dir`` is omitted."""

    def __init__(self, entries: Mapping[str, bytes]) -> None:
        self._path = Path("<baseline_1.62_virtual>")
        self._entries: dict[str, bytes] = {
            normalize_vfs_path(k): v for k, v in sorted(entries.items())
        }

    @property
    def path(self) -> Path:
        return self._path

    @property
    def format_name(self) -> str:
        return "virtual_baseline"

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def exists(self, vfs_path: str) -> bool:
        norm = normalize_vfs_path(vfs_path)
        return norm in self._entries

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None:
        norm = normalize_vfs_path(vfs_path)
        payload = self._entries.get(norm)
        if payload is None:
            return None
        return VfsEntryMeta(
            path=norm, is_dir=False, size=len(payload), compressed_size=len(payload)
        )

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]:
        return filter_paths_by_prefixes(self._entries.keys(), prefixes)

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        payload = self._entries.get(norm)
        if payload is None:
            raise FileNotFoundError(f"Entry {norm!r} not found in virtual baseline archive")
        return payload

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str:
        return decode_vfs_text(self.read_bytes(vfs_path), vfs_path, encoding=encoding)

    def close(self) -> None:
        return None


def _candidate_repo_roots(explicit_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    if explicit_root is not None:
        roots.append(explicit_root.resolve())
        return roots

    package_root = Path(__file__).resolve().parents[3]
    roots.append(package_root)
    cwd = Path.cwd().resolve()
    if cwd != package_root:
        roots.append(cwd)
    return roots


def assert_out_dir_not_tracked(out_dir: Path, *, repo_root: Path | None = None) -> None:
    """Refuse ``--out-dir`` inside tracked repository directories (D-08, T-04-05)."""
    resolved_out = out_dir.resolve()
    for root in _candidate_repo_roots(repo_root):
        for subdir in _FORBIDDEN_REPO_SUBDIRS:
            guarded = (root / subdir).resolve()
            if resolved_out == guarded or resolved_out.is_relative_to(guarded):
                raise ValueError(
                    f"Refusing to write ProMods output inside tracked repository directory "
                    f"{guarded}: {out_dir}"
                )


def _merge_axle_mass_limits(
    map_axles: Sequence[int],
    real_axles: Sequence[int],
) -> list[int]:
    """Element-wise max with carry-forward and monotonic non-decreasing enforcement (D-14)."""
    if not map_axles:
        return list(real_axles)
    if not real_axles:
        return list(map_axles)
    target_len = max(len(map_axles), len(real_axles))
    merged: list[int] = []
    running_max = 0
    for idx in range(target_len):
        map_val = map_axles[min(idx, len(map_axles) - 1)]
        real_val = real_axles[min(idx, len(real_axles) - 1)]
        running_max = max(running_max, map_val, real_val)
        merged.append(running_max)
    return merged


def _build_virtual_vanilla_base(
    bl_countries: CountriesBaseline,
    bl_speeds: SpeedLimitsBaseline,
    snapshot: RealismSnapshot,
) -> _InMemoryBaselineArchive:
    """Synthesize a clean-room Vanilla 1.62 virtual archive (def/country.sii + 36 countries)."""
    resolved_by_slug = {c.ets2_slug: c for c in snapshot.countries.values()}
    speeds_by_slug = {s.slug: s for s in bl_speeds.speed_limits}
    entries: dict[str, bytes] = {}
    include_lines: list[str] = ["SiiNunit", "{"]

    for bl_country in sorted(bl_countries.countries, key=lambda c: c.slug):
        slug = bl_country.slug
        resolved = resolved_by_slug.get(slug)
        bl_speed = speeds_by_slug.get(slug)
        if resolved is None or bl_speed is None:
            raise ValueError(f"Incomplete Vanilla baseline/snapshot for slug {slug!r}")
        include_lines.append(f'@include "country/{slug}.sui"')
        entries[f"def/country/{slug}.sui"] = synthesize_country_sui(bl_country, resolved)
        entries[f"def/country/{slug}/speed_limits.sii"] = synthesize_speed_limits_sii(
            bl_speed, resolved
        )

    include_lines.append("}")
    entries["def/country.sii"] = serialize_sii_text("\n".join(include_lines) + "\n")
    return _InMemoryBaselineArchive(entries)


def _decode_third_party_sii(raw: bytes) -> str:
    """Decode third-party SII/SUI bytes (UTF-8 first, cp1252 fallback for legacy mod comments)."""
    payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _discover_active_country_fragments(stack: VfsStack) -> dict[str, str]:
    """Follow ``def/country*.sii`` ``@include`` graphs into canonical active fragment paths."""
    reg_paths = sorted(
        p for p in stack.list_paths("def") if _COUNTRY_REG_SII_RE.fullmatch(p) is not None
    )
    active_fragments: dict[str, str] = {}
    visited_includes: set[str] = set()

    def _visit_include_source(source_path: str, raw_bytes: bytes) -> None:
        includes = parse_country_includes(_decode_third_party_sii(raw_bytes))
        parent_dir = source_path.rsplit("/", 1)[0] if "/" in source_path else ""
        for raw_inc in includes:
            norm_inc = normalize_vfs_path(raw_inc)
            if norm_inc.startswith("def/"):
                target = norm_inc
            elif parent_dir:
                target = normalize_vfs_path(f"{parent_dir}/{norm_inc}")
            else:
                target = norm_inc
            clean_target = validate_rel_path(target)
            if clean_target in visited_includes:
                continue
            visited_includes.add(clean_target)

            entry = stack.resolve(clean_target)
            if entry is None or entry.is_empty_stub:
                continue
            frag_match = _COUNTRY_FRAG_RE.fullmatch(clean_target)
            if frag_match is not None:
                slug = frag_match.group(1)
                active_fragments[slug] = clean_target
                continue
            try:
                nested_bytes = stack.read_bytes(clean_target)
            except (FileNotFoundError, ProtectedPayloadError, UnsupportedCompressionError):
                continue
            _visit_include_source(clean_target, nested_bytes)

    for reg_path in reg_paths:
        entry = stack.resolve(reg_path)
        if entry is None or entry.is_empty_stub:
            continue
        try:
            raw_reg = stack.read_bytes(reg_path)
        except (FileNotFoundError, ProtectedPayloadError, UnsupportedCompressionError):
            continue
        _visit_include_source(reg_path, raw_reg)

    return active_fragments


def _resolve_country_snapshot(
    slug: str,
    map_country: CountryDataModel,
    snapshot: RealismSnapshot,
    aliases: CountryAliasRegistry,
    by_iso3: Mapping[str, RealismSnapshotCountry],
    by_slug: Mapping[str, RealismSnapshotCountry],
) -> tuple[RealismSnapshotCountry | None, CountryAliasEntry | None]:
    """Deterministic 3-tier country lookup: alias -> ISO3/ISO2 -> canonical ets2_slug (D-13)."""
    norm_slug = slug.strip().lower()
    alias_entry = aliases.aliases.get(norm_slug)
    if alias_entry is not None:
        return snapshot.countries.get(alias_entry.iso2), alias_entry

    iso3 = map_country.iso_country_code.strip().lower()
    if iso3 and iso3 in by_iso3:
        return by_iso3[iso3], None

    cc = map_country.country_code.strip().upper()
    if cc and cc in snapshot.countries:
        return snapshot.countries[cc], None

    if norm_slug in by_slug:
        return by_slug[norm_slug], None

    return None, None


def _patch_country_fragment_bytes(
    raw_source: bytes,
    map_country: CountryDataModel,
    snapshot_country: RealismSnapshotCountry,
    alias_entry: CountryAliasEntry | None,
    *,
    ref_date: date,
    allowed_tz_keys: Sequence[str],
    rel_path: str,
) -> bytes:
    """Surgically patch realism-owned fields while preserving map geometry/regions/multi-TZ."""
    has_secondary_tz = bool(
        map_country.secondary_time_zone
        or map_country.secondary_time_zone_area
        or map_country.secondary_time_zone_name
    )
    should_patch_tz = (not has_secondary_tz) and (map_country.time_zone is not None)

    tz_offset: int | None = None
    tz_name: str | None = None
    if should_patch_tz:
        if alias_entry is not None and alias_entry.iana_timezone_override is not None:
            resolved_tz = resolve_ets2_timezone(
                alias_entry.iana_timezone_override,
                ref_date,
                allowed_tz_keys,
            )
            tz_offset = resolved_tz.offset_minutes
            tz_name = resolved_tz.ets2_time_zone_name
        else:
            tz_offset = snapshot_country.time_zone
            tz_name = snapshot_country.time_zone_name

    merged_axles = _merge_axle_mass_limits(
        map_country.mass_limit_per_axle_count,
        snapshot_country.mass_limit_per_axle_count,
    )
    patch = CountryDataPatch(
        fuel_price=snapshot_country.fuel.eur_per_liter,
        lights_mandatory=snapshot_country.lights_mandatory,
        driving_tired_offence=snapshot_country.driving_tired_offence,
        time_zone=tz_offset,
        time_zone_name=tz_name,
        mass_limit_per_axle_count=merged_axles,
    )
    rendered = patch_country_data(_decode_third_party_sii(raw_source), patch)
    out_bytes = serialize_sii_text(rendered)
    hygiene = validate_sii_hygiene(out_bytes, require_siinunit=False)
    if hygiene:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in hygiene)
        raise ValueError(f"Patched ProMods country SII hygiene failure for {rel_path}: {summary}")
    return out_bytes


def _patch_speed_limits_bytes(
    raw_source: bytes,
    map_country: CountryDataModel,
    snapshot_country: RealismSnapshotCountry,
    *,
    rel_path: str,
) -> bytes | None:
    """Surgically patch canonical road lanes preserving custom lanes & train/tram (D-15)."""
    map_is_imperial = map_country.imperial_units is True
    if map_is_imperial != snapshot_country.imperial_units:
        return None

    decoded_source = _decode_third_party_sii(raw_source)
    parsed = parse_speed_limits(decoded_source)
    updates: dict[str, list[LaneSpeedRule]] = {}
    for vclass in _ROAD_CLASSES:
        block = parsed.get_block(vclass)
        if block is None or not block.lanes:
            continue
        overrides_by_lane = {
            lane.lane_speed_class: lane for lane in snapshot_country.speed_limits[vclass]
        }
        new_lanes: list[LaneSpeedRule] = []
        for existing_lane in block.lanes:
            override = overrides_by_lane.get(existing_lane.lane_speed_class)
            if override is None:
                # Preserve map-added custom lane classes verbatim in their exact slot
                new_lanes.append(existing_lane)
            else:
                new_lanes.append(
                    LaneSpeedRule(
                        lane_speed_class=existing_lane.lane_speed_class,
                        limit=override.limit,
                        urban_limit=override.urban_limit,
                        max_limit=(
                            override.max_limit if existing_lane.max_limit is not None else None
                        ),
                        uncommon=existing_lane.uncommon,
                    )
                )
        updates[vclass] = new_lanes

    if not updates:
        return None

    rendered = patch_speed_limits(decoded_source, updates)
    out_bytes = serialize_sii_text(rendered)
    hygiene = validate_sii_hygiene(out_bytes, require_siinunit=True)
    if hygiene:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in hygiene)
        raise ValueError(f"Patched ProMods speed_limits hygiene failure for {rel_path}: {summary}")
    return out_bytes


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
                _build_virtual_vanilla_base(bl_countries, bl_speeds, snapshot),
                name="vanilla_baseline_1_62",
                priority=0,
            )

        for pack_spec in ordered_packs:
            stack.mount(
                open_archive(pack_spec.path),
                name=pack_spec.layer_name,
                priority=pack_spec.priority,
            )

        active_fragments = _discover_active_country_fragments(stack)
        vanilla_slugs = frozenset(c.slug for c in bl_countries.countries)
        by_iso3 = {c.iso3.lower(): c for c in snapshot.countries.values()}
        by_slug = {c.ets2_slug.lower(): c for c in snapshot.countries.values()}

        shared_payloads: dict[str, bytes] = {
            "mod_icon.jpg": icon_bytes,
            "description.txt": render_promods_description_txt(edition),
        }

        vanilla_emitted = 0
        promods_emitted = 0

        for slug in sorted(active_fragments):
            frag_path = active_fragments[slug]
            try:
                raw_country = stack.read_bytes(frag_path)
            except (FileNotFoundError, ProtectedPayloadError, UnsupportedCompressionError):
                continue

            map_country = parse_country_data(_decode_third_party_sii(raw_country))
            snapshot_country, alias_entry = _resolve_country_snapshot(
                slug,
                map_country,
                snapshot,
                aliases,
                by_iso3,
                by_slug,
            )
            if snapshot_country is None:
                continue

            clean_frag_rel = validate_rel_path(frag_path)
            shared_payloads[clean_frag_rel] = _patch_country_fragment_bytes(
                raw_country,
                map_country,
                snapshot_country,
                alias_entry,
                ref_date=ref_date,
                allowed_tz_keys=bl_locales.tz_keys,
                rel_path=clean_frag_rel,
            )
            if slug in vanilla_slugs:
                vanilla_emitted += 1
            else:
                promods_emitted += 1

            spd_rel = validate_rel_path(f"def/country/{slug}/speed_limits.sii")
            spd_entry = stack.resolve(spd_rel)
            if spd_entry is not None and not spd_entry.is_empty_stub:
                try:
                    raw_spd = stack.read_bytes(spd_rel)
                except (FileNotFoundError, ProtectedPayloadError, UnsupportedCompressionError):
                    raw_spd = None
                if raw_spd is not None:
                    patched_spd = _patch_speed_limits_bytes(
                        raw_spd,
                        map_country,
                        snapshot_country,
                        rel_path=spd_rel,
                    )
                    if patched_spd is not None:
                        shared_payloads[spd_rel] = patched_spd

        # Vanilla Option 4b 460 sign boards + 43-locale local_module.ets2v2_fuel.sii
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
    workshop_dir = out_dir / "workshop" / f"promods-{edition}"
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

    workshop_file_count = write_workshop_tree(workshop_dir, out_dir, workshop_files)

    # Target B: Deterministic local ZIP (<out_dir>/local/ETS2V2_ProMods_{Summer|Winter}.zip)
    local_entries: dict[str, bytes] = {
        "manifest.sii": render_promods_manifest_sii(
            edition,
            resolved_version,
            workshop=False,
            author=author,
        ),
        **shared_payloads,
    }
    local_zip_path = out_dir / "local" / PROMODS_LOCAL_ZIP_FILENAMES[edition]
    ensure_contained(local_zip_path, out_dir)
    local_zip_sha256 = write_deterministic_zip(local_zip_path, local_entries)

    # Mandatory Offline SCS Validator hard gate on BOTH targets (profile="promods")
    ws_report = validate_workshop_package(
        workshop_dir,
        baseline_dir=baseline_dir,
        profile="promods",
    )
    if not ws_report.ok:
        details = "; ".join(f"{i.code} [{i.path}]: {i.detail}" for i in ws_report.issues[:10])
        raise ValueError(f"ProMods Workshop validation failed for {workshop_dir}: {details}")

    zip_report = validate_local_zip(
        local_zip_path,
        baseline_dir=baseline_dir,
        profile="promods",
    )
    if not zip_report.ok:
        details = "; ".join(f"{i.code} [{i.path}]: {i.detail}" for i in zip_report.issues[:10])
        raise ValueError(f"ProMods local ZIP validation failed for {local_zip_path}: {details}")

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
