"""100% offline local map-combo patch composer orchestrator (MAP-03..05, D-09..D-16)."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.baseline.models import BaselineManifest, FuelBoardsBaseline, LocalesBaseline
from ets2v2.merge.aliases import CountryResolver, MatchTier
from ets2v2.merge.hardcoded_totems import (
    HardcodedTotemBoardAction,
    patch_hardcoded_numeric_totems,
)
from ets2v2.merge.load_order import (
    ExcludedSelfPackage,
    LoadOrderEntry,
    ModlistOrder,
    ProtectedArchiveDiagnostic,
    build_combo_vfs_stack,
    parse_game_log,
    parse_modlist,
    parse_profile_sii,
    resolve_workshop_dir,
)
from ets2v2.merge.policy import (
    AxleAction,
    FieldOwnershipPolicy,
    TimeZoneAction,
    apply_country_policy,
    apply_speed_limits_policy,
)
from ets2v2.merge.promods_builder import assert_out_dir_not_tracked
from ets2v2.merge.promods_discovery import resolve_mod_dir
from ets2v2.merge.promods_fuel import compile_promods_fuel_locales
from ets2v2.merge.scanner import (
    ScanDiagnostic,
    SuppressedRegistrationStub,
    scan_active_countries,
)
from ets2v2.package.builder import (
    default_package_version,
    ensure_contained,
    validate_rel_path,
    write_deterministic_zip,
)
from ets2v2.package.icons import render_combo_icon_bytes
from ets2v2.package.metadata import (
    DEFAULT_AUTHOR,
    render_combo_description_txt,
    render_combo_manifest_sii,
)
from ets2v2.package.totems import (
    FUEL_LOCALE_FILENAME,
    compile_totem_payloads,
    snapshot_to_totem_lockfile,
    synthesize_fuel_locale_module_sii,
)
from ets2v2.registry.models import Season
from ets2v2.registry.snapshot import load_or_build_snapshot
from ets2v2.registry.timezone import DEFAULT_ANCHOR_YEAR
from ets2v2.sii.country import CountryDataModel
from ets2v2.validate.workshop import validate_local_zip

COMBO_SCS_FILENAMES: Final[dict[Season, str]] = {
    "summer": "zz_ETS2V2_ComboPatch_Summer.scs",
    "winter": "zz_ETS2V2_ComboPatch_Winter.scs",
}

LoadOrderSourceKind = Literal["game_log", "profile", "modlist"]


class ComposeCountryAudit(BaseModel):
    """Per-country resolution and FieldOwnershipPolicy audit entry in ``ComposeReport``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    slug: str
    fragment_path: str
    winning_layer: str
    winning_priority: int
    match_tier: MatchTier
    resolved_iso2: str | None = None
    unmatched_reason: str | None = None
    emitted: bool
    time_zone_action: TimeZoneAction | None = None
    axle_action: AxleAction | None = None
    speed_limits_path: str | None = None
    speed_limits_status: str | None = None
    preserved_custom_lanes: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ComposeReport(BaseModel):
    """Structured audit report emitted by ``compose_local()`` (D-11, D-12, D-16)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ok: bool
    edition: Season
    dry_run: bool
    strict_protected: bool
    load_order_source: LoadOrderSourceKind
    modlist_order: ModlistOrder | None = None
    base_layer_name: str
    package_version: str
    output_path: Path | None = None
    output_sha256: str | None = None
    output_entry_count: int = 0
    validation_ok: bool | None = None
    active_layers_mounted: int
    countries_scanned: int
    countries_patched: int
    countries_unmatched: int
    speed_limits_patched: int
    totems_enabled: bool
    vanilla_totem_boards_emitted: int = 0
    promods_fuel_modules_emitted: list[str] = Field(default_factory=list)
    hardcoded_totems_enabled: bool = False
    hardcoded_totems_patched: int = 0
    hardcoded_totem_actions: list[HardcodedTotemBoardAction] = Field(default_factory=list)
    excluded_self_packages: list[ExcludedSelfPackage] = Field(default_factory=list)
    missing_load_order_entries: list[LoadOrderEntry] = Field(default_factory=list)
    protected_archives: list[ProtectedArchiveDiagnostic] = Field(default_factory=list)
    suppressed_registration_files: list[SuppressedRegistrationStub] = Field(default_factory=list)
    scan_diagnostics: list[ScanDiagnostic] = Field(default_factory=list)
    countries: list[ComposeCountryAudit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _write_report_json(report: ComposeReport, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload: object = report.model_dump(mode="json")
    rendered = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    with tempfile.NamedTemporaryFile(
        dir=report_path.parent,
        prefix=".tmp_ets2v2_report_",
        suffix=".json",
        delete=False,
    ) as tmp_fh:
        tmp_path = Path(tmp_fh.name)
        tmp_fh.write(rendered)
    try:
        os.replace(tmp_path, report_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _check_map_owned_country_fields(
    slug: str,
    frag_path: str,
    country_data: CountryDataModel,
) -> list[str]:
    """Pre-check map-owned fields required by the combo validator before emitting (MD-07)."""
    issues: list[str] = []
    if country_data.country_id <= 0:
        issues.append(f"non-positive country_id={country_data.country_id}")
    if not country_data.name.strip():
        issues.append("missing required name")
    if not country_data.country_code.strip():
        issues.append("missing required country_code")
    if (country_data.time_zone is None) != (country_data.time_zone_name is None):
        issues.append("asymmetric time_zone/time_zone_name")
    if not issues:
        return []
    return [
        f"Skipping malformed third-party country fragment {frag_path!r} ({slug}): "
        + "; ".join(issues)
    ]


def _resolve_load_order(
    *,
    game_log: Path | None,
    profile: Path | None,
    modlist: Path | None,
    modlist_order: ModlistOrder,
) -> tuple[LoadOrderSourceKind, list[LoadOrderEntry]]:
    provided = sum(1 for item in (game_log, profile, modlist) if item is not None)
    if provided != 1:
        raise ValueError(
            "Specify exactly one load-order input: --game-log, --profile, or --modlist"
        )

    if game_log is not None:
        return "game_log", parse_game_log(game_log)
    if profile is not None:
        return "profile", parse_profile_sii(profile)
    assert modlist is not None
    return "modlist", parse_modlist(modlist, order=modlist_order)


def compose_local(
    edition: Season,
    *,
    out_dir: Path | None = None,
    game_log: Path | None = None,
    profile: Path | None = None,
    modlist: Path | None = None,
    modlist_order: ModlistOrder = "top-to-bottom",
    mod_dir: Path | None = None,
    workshop_dir: Path | None = None,
    game_dir: Path | None = None,
    snapshot_path: Path | None = None,
    checksums_path: Path | None = None,
    aliases_path: Path = Path("data/mappings/country_aliases.json"),
    user_aliases_path: Path | None = None,
    unpacked_defs: Sequence[Path] = (),
    strict_protected: bool = False,
    patch_hardcoded_totems: bool = False,
    no_totems: bool = False,
    exclude_self: bool = True,
    dry_run: bool = False,
    report_json_path: Path | None = None,
    policy: FieldOwnershipPolicy | None = None,
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    prices_lock_path: Path = Path("state/prices.lock.json"),
    package_version: str | None = None,
    author: str = DEFAULT_AUTHOR,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    repo_root: Path | None = None,
) -> ComposeReport:
    """Compose and offline-validate ``zz_ETS2V2_ComboPatch_{Summer|Winter}.scs`` (D-09..D-16)."""
    source_kind, entries = _resolve_load_order(
        game_log=game_log,
        profile=profile,
        modlist=modlist,
        modlist_order=modlist_order,
    )

    effective_out_dir = out_dir if out_dir is not None else Path("dist/local")
    if not dry_run:
        assert_out_dir_not_tracked(effective_out_dir, repo_root=repo_root)

    bl_fuel_boards = FuelBoardsBaseline.model_validate_json(
        (baseline_dir / "fuel_boards.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (baseline_dir / "locales.json").read_text("utf-8")
    )

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

    resolver = CountryResolver.from_paths(
        snapshot,
        bundled_aliases_path=aliases_path,
        user_aliases_path=user_aliases_path,
    )

    effective_mod_dir = resolve_mod_dir(mod_dir)
    effective_workshop_dir = resolve_workshop_dir(workshop_dir, game_dir=game_dir)

    warnings: list[str] = []
    errors: list[str] = []

    with build_combo_vfs_stack(
        entries,
        mod_dir=effective_mod_dir,
        workshop_dir=effective_workshop_dir,
        game_dir=game_dir,
        baseline_dir=baseline_dir,
        snapshot=snapshot,
        unpacked_defs=unpacked_defs,
        exclude_self=exclude_self,
    ) as vfs_result:
        unsubstituted_protected = [
            diag for diag in vfs_result.protected_archives if diag.substituted_by is None
        ]
        for diag in unsubstituted_protected:
            warnings.append(
                f"Protected archive {diag.archive_path.name!r} ({diag.protection_kind}): "
                f"{diag.hint}"
            )

        if strict_protected and unsubstituted_protected:
            for diag in unsubstituted_protected:
                errors.append(
                    f"--strict-protected refused unsubstituted protected archive "
                    f"{diag.archive_path.name!r} ({diag.protection_kind})"
                )
            failed_report = ComposeReport(
                ok=False,
                edition=edition,
                dry_run=dry_run,
                strict_protected=strict_protected,
                load_order_source=source_kind,
                modlist_order=modlist_order if source_kind == "modlist" else None,
                base_layer_name=vfs_result.base_layer_name,
                package_version=resolved_version,
                output_path=None,
                output_sha256=None,
                output_entry_count=0,
                validation_ok=None,
                active_layers_mounted=len(vfs_result.stack.layers),
                countries_scanned=0,
                countries_patched=0,
                countries_unmatched=0,
                speed_limits_patched=0,
                totems_enabled=not no_totems,
                hardcoded_totems_enabled=patch_hardcoded_totems and not no_totems,
                excluded_self_packages=vfs_result.excluded_self_packages,
                missing_load_order_entries=vfs_result.missing_entries,
                protected_archives=vfs_result.protected_archives,
                warnings=warnings,
                errors=errors,
            )
            if report_json_path is not None:
                _write_report_json(failed_report, report_json_path)
            return failed_report

        scan_result = scan_active_countries(vfs_result.stack)

        payloads: dict[str, bytes] = {
            "manifest.sii": render_combo_manifest_sii(edition, resolved_version, author=author),
            "mod_icon.jpg": render_combo_icon_bytes(edition),
            "description.txt": render_combo_description_txt(edition),
        }

        country_audits: list[ComposeCountryAudit] = []
        countries_patched = 0
        countries_unmatched = 0
        speed_limits_patched = 0

        for scanned in scan_result.countries:
            resolution = resolver.resolve(scanned.slug, scanned.country_data)
            if resolution.country is None:
                countries_unmatched += 1
                country_audits.append(
                    ComposeCountryAudit(
                        slug=scanned.slug,
                        fragment_path=scanned.fragment_path,
                        winning_layer=scanned.winning_layer,
                        winning_priority=scanned.winning_priority,
                        match_tier=resolution.match_tier,
                        resolved_iso2=resolution.resolved_iso2,
                        unmatched_reason=resolution.unmatched_reason,
                        emitted=False,
                    )
                )
                continue

            precheck_warnings = _check_map_owned_country_fields(
                scanned.slug,
                scanned.fragment_path,
                scanned.country_data,
            )
            if precheck_warnings:
                warnings.extend(precheck_warnings)
                country_audits.append(
                    ComposeCountryAudit(
                        slug=scanned.slug,
                        fragment_path=scanned.fragment_path,
                        winning_layer=scanned.winning_layer,
                        winning_priority=scanned.winning_priority,
                        match_tier=resolution.match_tier,
                        resolved_iso2=resolution.resolved_iso2,
                        unmatched_reason=None,
                        emitted=False,
                        warnings=precheck_warnings,
                    )
                )
                continue

            try:
                country_res = apply_country_policy(
                    scanned.raw_bytes,
                    scanned.country_data,
                    resolution.country,
                    policy=policy,
                    iana_timezone_override=resolution.iana_timezone_override,
                    ref_date=ref_date,
                    supported_tz_keys=bl_locales.tz_keys,
                    rel_path=scanned.fragment_path,
                )
            except ValueError as exc:
                warn_msg = (
                    f"Skipping country fragment {scanned.fragment_path!r} ({scanned.slug}) due to "
                    f"policy/SII error: {exc}"
                )
                warnings.append(warn_msg)
                country_audits.append(
                    ComposeCountryAudit(
                        slug=scanned.slug,
                        fragment_path=scanned.fragment_path,
                        winning_layer=scanned.winning_layer,
                        winning_priority=scanned.winning_priority,
                        match_tier=resolution.match_tier,
                        resolved_iso2=resolution.resolved_iso2,
                        unmatched_reason=None,
                        emitted=False,
                        warnings=[warn_msg],
                    )
                )
                continue

            clean_frag = validate_rel_path(scanned.fragment_path)
            payloads[clean_frag] = country_res.rendered_bytes
            countries_patched += 1

            country_warnings = list(country_res.warnings)
            spd_status = "skipped_absent"
            preserved_lanes: dict[str, list[str]] = {}
            if scanned.speed_limits_path is not None and scanned.speed_limits_raw is not None:
                try:
                    spd_res = apply_speed_limits_policy(
                        scanned.speed_limits_raw,
                        scanned.country_data,
                        resolution.country,
                        policy=policy,
                        rel_path=scanned.speed_limits_path,
                    )
                except ValueError as exc:
                    spd_status = "skipped_parse_error"
                    country_warnings.append(
                        f"Skipping malformed speed_limits.sii {scanned.speed_limits_path!r} "
                        f"({scanned.slug}): {exc}"
                    )
                else:
                    spd_status = spd_res.status
                    preserved_lanes = spd_res.preserved_custom_lanes
                    country_warnings.extend(spd_res.warnings)
                    if spd_res.rendered_bytes is not None:
                        clean_spd = validate_rel_path(scanned.speed_limits_path)
                        payloads[clean_spd] = spd_res.rendered_bytes
                        speed_limits_patched += 1

            warnings.extend(country_warnings)
            country_audits.append(
                ComposeCountryAudit(
                    slug=scanned.slug,
                    fragment_path=scanned.fragment_path,
                    winning_layer=scanned.winning_layer,
                    winning_priority=scanned.winning_priority,
                    match_tier=resolution.match_tier,
                    resolved_iso2=resolution.resolved_iso2,
                    unmatched_reason=None,
                    emitted=True,
                    time_zone_action=country_res.time_zone_action,
                    axle_action=country_res.axle_action,
                    speed_limits_path=scanned.speed_limits_path,
                    speed_limits_status=spd_status,
                    preserved_custom_lanes=preserved_lanes,
                    warnings=country_warnings,
                )
            )

        # Fuel totems (D-16): self-contained Vanilla Option 4b + detected ProMods pm*_fuel
        vanilla_boards_emitted = 0
        pm_modules_emitted: list[str] = []
        hardcoded_enabled = patch_hardcoded_totems and not no_totems
        hardcoded_patched = 0
        hardcoded_actions: list[HardcodedTotemBoardAction] = []

        if not no_totems:
            totem_lockfile = snapshot_to_totem_lockfile(snapshot)
            compiled_totems = compile_totem_payloads(bl_fuel_boards, bl_locales, totem_lockfile)
            for rel_path, raw in compiled_totems.board_files.items():
                payloads[validate_rel_path(rel_path)] = raw
            vanilla_boards_emitted = len(compiled_totems.board_files)

            merged_tokens = dict(compiled_totems.token_values)
            if hardcoded_enabled:
                hc_result = patch_hardcoded_numeric_totems(
                    vfs_result.stack,
                    snapshot,
                    bl_fuel_boards,
                )
                hardcoded_actions = hc_result.actions
                hardcoded_patched = len(hc_result.board_files)
                for rel_path, raw in hc_result.board_files.items():
                    payloads[validate_rel_path(rel_path)] = raw
                merged_tokens.update(hc_result.extra_locale_tokens)

            if merged_tokens != compiled_totems.token_values:
                locale_payload = synthesize_fuel_locale_module_sii(merged_tokens)
                for lang in sorted(bl_locales.active_locales):
                    rel_loc = validate_rel_path(f"locale/{lang}/{FUEL_LOCALE_FILENAME}")
                    payloads[rel_loc] = locale_payload
            else:
                for rel_path, raw in compiled_totems.locale_files.items():
                    payloads[validate_rel_path(rel_path)] = raw

            compiled_pm_fuel = compile_promods_fuel_locales(
                vfs_result.stack,
                bl_locales,
                snapshot,
            )
            for rel_path, raw in compiled_pm_fuel.locale_files.items():
                payloads[validate_rel_path(rel_path)] = raw
            pm_modules_emitted = [str(name) for name in sorted(compiled_pm_fuel.modules)]

        output_path: Path | None = None
        output_sha256: str | None = None
        validation_ok: bool | None = None

        if not dry_run:
            final_path = effective_out_dir / COMBO_SCS_FILENAMES[edition]
            ensure_contained(final_path, effective_out_dir)
            effective_out_dir.mkdir(parents=True, exist_ok=True)

            # Stage to temp file in target directory, hard-gate with Offline Validator, then replace
            with tempfile.NamedTemporaryFile(
                dir=effective_out_dir,
                prefix=".tmp_ets2v2_combo_",
                suffix=".scs",
                delete=False,
            ) as tmp_fh:
                staged_path = Path(tmp_fh.name)

            try:
                output_sha256 = write_deterministic_zip(staged_path, payloads)
                val_report = validate_local_zip(
                    staged_path,
                    baseline_dir=baseline_dir,
                    profile="combo",
                )
                if not val_report.ok:
                    details = "; ".join(
                        f"{issue.code} [{issue.path}]: {issue.detail}"
                        for issue in val_report.issues[:10]
                    )
                    raise ValueError(
                        f"ComboPatch pre-write validation failed for {final_path.name}: {details}"
                    )
                os.replace(staged_path, final_path)
            except Exception:
                staged_path.unlink(missing_ok=True)
                raise

            output_path = final_path
            validation_ok = True

        report = ComposeReport(
            ok=True,
            edition=edition,
            dry_run=dry_run,
            strict_protected=strict_protected,
            load_order_source=source_kind,
            modlist_order=modlist_order if source_kind == "modlist" else None,
            base_layer_name=vfs_result.base_layer_name,
            package_version=resolved_version,
            output_path=output_path,
            output_sha256=output_sha256,
            output_entry_count=len(payloads),
            validation_ok=validation_ok,
            active_layers_mounted=len(vfs_result.stack.layers),
            countries_scanned=len(scan_result.countries),
            countries_patched=countries_patched,
            countries_unmatched=countries_unmatched,
            speed_limits_patched=speed_limits_patched,
            totems_enabled=not no_totems,
            vanilla_totem_boards_emitted=vanilla_boards_emitted,
            promods_fuel_modules_emitted=pm_modules_emitted,
            hardcoded_totems_enabled=hardcoded_enabled,
            hardcoded_totems_patched=hardcoded_patched,
            hardcoded_totem_actions=hardcoded_actions,
            excluded_self_packages=vfs_result.excluded_self_packages,
            missing_load_order_entries=vfs_result.missing_entries,
            protected_archives=vfs_result.protected_archives,
            suppressed_registration_files=scan_result.suppressed_registration_files,
            scan_diagnostics=scan_result.diagnostics,
            countries=country_audits,
            warnings=warnings,
            errors=errors,
        )

    if report_json_path is not None:
        _write_report_json(report, report_json_path)
    return report


__all__ = [
    "COMBO_SCS_FILENAMES",
    "ComposeCountryAudit",
    "ComposeReport",
    "LoadOrderSourceKind",
    "compose_local",
]
