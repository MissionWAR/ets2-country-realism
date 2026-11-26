"""Command-line entrypoint for ets2-realism."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from ets2_realism import __version__
from ets2_realism.audit import (
    DEFAULT_ALLOWLIST_PATH,
    DEFAULT_WESTNORDOST_RULES_URL,
    render_osm_speed_drift_markdown,
    run_osm_speed_audit,
    scan_repo_and_artifacts_for_taint,
    serialize_audit_report_bytes,
)
from ets2_realism.baseline import (
    BaselineManifest,
    CountriesBaseline,
    LocalesBaseline,
    extract_baseline,
    verify_baseline_bundle,
    write_baseline_bundle,
)
from ets2_realism.fetch import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpFetchError,
    redact_url_secrets,
    run_price_fetch,
)
from ets2_realism.merge import ModlistOrder, build_promods_editions, compose_local
from ets2_realism.normalize import PricesLockfile, load_prices_lockfile
from ets2_realism.package import (
    DEFAULT_AUTHOR,
    build_core_editions,
    generate_all_icons,
    generate_promods_icons,
)
from ets2_realism.publish import run_phase_a_release
from ets2_realism.registry import (
    DEFAULT_ANCHOR_YEAR,
    RealismSnapshot,
    Season,
    build_realism_snapshot,
    load_law_registry,
    load_realism_snapshot,
    validate_law_registry,
    verify_snapshot_file,
    write_realism_snapshot,
)
from ets2_realism.validate import (
    PackageProfile,
    ValidationReport,
    validate_local_zip,
    validate_workshop_package,
)
from ets2_realism.vfs import (
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsStack,
)
from ets2_realism.vfs.hashfs import DEFAULT_SEEDED_PREFIXES

CommandHandler = Callable[[argparse.Namespace], int]


def _handle_vfs_inspect(args: argparse.Namespace) -> int:
    raw_paths = cast(list[Path], args.paths)
    raw_prefixes = cast(list[str] | None, args.prefixes)
    limit = cast(int, args.limit)
    as_json = cast(bool, args.json)

    for path in raw_paths:
        if not path.exists():
            print(f"error: VFS path does not exist: {path}", file=sys.stderr)
            return 1

    seeds = tuple(raw_prefixes) if raw_prefixes else DEFAULT_SEEDED_PREFIXES
    try:
        stack = VfsStack.from_paths(raw_paths, seeded_prefixes=seeds)
    except (OSError, ValueError) as exc:
        print(f"error: failed to open VFS archive(s): {exc}", file=sys.stderr)
        return 1

    with stack:
        if raw_prefixes:
            matched: set[str] = set()
            for prefix in raw_prefixes:
                matched.update(stack.list_paths(prefix))
            paths_list = sorted(matched)
        else:
            paths_list = stack.list_paths()

        diagnostics = stack.diagnostics()
        layer_summaries = [
            {
                "name": layer.name,
                "priority": layer.priority,
                "format": layer.archive.format_name,
                "path": str(layer.archive.path),
            }
            for layer in stack.layers
        ]

    sample = paths_list[: max(limit, 0)]
    if as_json:
        payload = {
            "layers": layer_summaries,
            "entry_count": len(paths_list),
            "sample_paths": sample,
            "diagnostics": [diag.model_dump(mode="json") for diag in diagnostics],
        }
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    for layer_info in layer_summaries:
        print(
            f"Layer [{layer_info['priority']}] {layer_info['name']} "
            f"({layer_info['format']}): {layer_info['path']}"
        )
    print(f"Entries: {len(paths_list)}")
    for entry_path in sample:
        print(f"  {entry_path}")
    if len(paths_list) > len(sample):
        print(f"  ... ({len(paths_list) - len(sample)} more)")
    if diagnostics:
        print(f"Diagnostics ({len(diagnostics)}):")
        for diag in diagnostics:
            loc = f" [{diag.entry_path}]" if diag.entry_path else ""
            print(f"  {diag.kind}{loc}: {diag.detail}")
    return 0


def _handle_baseline_extract(args: argparse.Namespace) -> int:
    game_dir = cast(Path | None, args.game_dir)
    out_dir = cast(Path, args.out_dir)
    raw_cache_dir = cast(Path | None, args.raw_cache_dir)
    check_only = cast(bool, args.check)

    if raw_cache_dir is not None:
        resolved_out = out_dir.resolve()
        resolved_raw = raw_cache_dir.resolve()
        if (
            resolved_raw == resolved_out
            or resolved_raw.is_relative_to(resolved_out)
            or resolved_out.is_relative_to(resolved_raw)
        ):
            print(
                "error: --raw-cache-dir must not overlap --out-dir",
                file=sys.stderr,
            )
            return 1

    try:
        bundle = extract_baseline(
            game_dir,
            raw_cache_dir=None if check_only else raw_cache_dir,
        )
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        ProtectedPayloadError,
        UnsupportedCompressionError,
    ) as exc:
        print(f"error: baseline extraction failed: {exc}", file=sys.stderr)
        return 1

    m = bundle.manifest
    if check_only:
        issues = verify_baseline_bundle(bundle, out_dir)
        if issues:
            for issue in issues:
                print(f"mismatch: {issue}", file=sys.stderr)
            return 1
        print(
            f"Baseline check passed ({m.application} {m.game_version}): "
            f"{m.country_count} countries, {m.speed_limit_count} speed limits, "
            f"{m.fuel_board_count} fuel boards ({m.active_fp_board_count} active fp), "
            f"{m.locale_count} locales, {m.tz_key_count} tz keys, {m.fp_key_count} fp keys."
        )
        return 0

    written = write_baseline_bundle(bundle, out_dir)
    print(
        f"Extracted baseline ({m.application} {m.game_version}) -> {out_dir} "
        f"[{len(written)} JSON files]: {m.country_count} countries, "
        f"{m.speed_limit_count} speed limits, {m.fuel_board_count} fuel boards "
        f"({m.active_fp_board_count} active fp, {m.placeholder_or_blank_board_count} "
        f"placeholder/blank), {m.locale_count} locales, {m.tz_key_count} tz keys, "
        f"{m.fp_key_count} fp keys."
    )
    return 0


def _handle_registry_validate(args: argparse.Namespace) -> int:
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
    as_json = cast(bool, args.json)

    try:
        issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
        country_count = 0
        if not issues:
            bundle = load_law_registry(laws_dir, mappings_path)
            country_count = len(bundle.laws_by_iso2)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        if as_json:
            payload_err: dict[str, object] = {
                "country_count": 0,
                "issue_count": 1,
                "issues": [str(exc)],
                "ok": False,
            }
            print(json.dumps(payload_err, indent=2, sort_keys=True, ensure_ascii=False))
            return 1
        print(f"error: registry validation failed: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload: dict[str, object] = {
            "country_count": country_count,
            "issue_count": len(issues),
            "issues": issues,
            "ok": not issues,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if not issues else 1

    if issues:
        for issue in issues:
            print(f"error: {issue}", file=sys.stderr)
        return 1

    print(f"Registry validation passed ({country_count} countries).")
    return 0


def _parse_iso_date_arg(raw_date: str | None, *, flag_name: str = "--date") -> date | None:
    if raw_date is None:
        return None
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError(f"invalid {flag_name} {raw_date!r} (expected ISO YYYY-MM-DD)") from exc
    if parsed_date.isoformat() != raw_date:
        raise ValueError(f"invalid {flag_name} {raw_date!r} (expected ISO YYYY-MM-DD)")
    return parsed_date


def _handle_registry_snapshot(args: argparse.Namespace) -> int:
    season = cast(Season, args.season)
    raw_date = cast(str | None, args.date)
    anchor_year = cast(int, args.anchor_year)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
    prices_lock_path = cast(Path | None, args.prices_lock)
    out_path = cast(Path, args.out)

    try:
        override_date = _parse_iso_date_arg(raw_date)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        registry = load_law_registry(laws_dir, mappings_path)
        bl_countries = CountriesBaseline.model_validate_json(
            (baseline_dir / "countries.json").read_text("utf-8")
        )
        bl_locales = LocalesBaseline.model_validate_json(
            (baseline_dir / "locales.json").read_text("utf-8")
        )
        manifest_path = baseline_dir / "manifest.json"
        if manifest_path.is_file():
            bl_manifest = BaselineManifest.model_validate_json(manifest_path.read_text("utf-8"))
            game_version = bl_manifest.game_version
        else:
            game_version = registry.mappings.baseline_game_version

        loaded_prices_lock: PricesLockfile | None = (
            load_prices_lockfile(prices_lock_path) if prices_lock_path is not None else None
        )

        snapshot = build_realism_snapshot(
            registry,
            bl_countries,
            bl_locales,
            season,
            anchor_year=anchor_year,
            override_date=override_date,
            baseline_game_version=game_version,
            prices_lock=loaded_prices_lock,
        )
        write_realism_snapshot(snapshot, out_path)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: snapshot export failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote realism snapshot ({snapshot.edition}, {snapshot.anchor_date}, "
        f"{len(snapshot.countries)} countries) -> {out_path}"
    )
    return 0


def _handle_registry_snapshot_verify(args: argparse.Namespace) -> int:
    snapshot_path = cast(Path, args.snapshot_path)
    checksums_path = cast(Path | None, args.checksums)
    expected_edition = cast(Season | None, args.expected_edition)
    as_json = cast(bool, args.json)

    result = verify_snapshot_file(
        snapshot_path,
        checksums_path=checksums_path,
        expected_edition=expected_edition,
    )

    if as_json:
        payload: object = result.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if result.ok else 1

    if not result.ok:
        for issue in result.issues:
            print(f"error: {issue}", file=sys.stderr)
        return 1

    checksum_note = "checksum verified" if result.checksum_verified else "no checksum manifest"
    print(
        f"Snapshot verification passed ({result.edition}, {result.anchor_date}, "
        f"{result.country_count} countries, {checksum_note}): {snapshot_path}"
    )
    return 0


def _handle_package_icons(args: argparse.Namespace) -> int:
    out_dir = cast(Path, args.out_dir)
    try:
        written_core = generate_all_icons(out_dir)
        written_promods = generate_promods_icons(out_dir)
    except (OSError, ValueError) as exc:
        print(f"error: icon generation failed: {exc}", file=sys.stderr)
        return 1

    for edition in ("summer", "winter"):
        path = written_core[edition]
        print(f"Generated {edition} icon ({path.stat().st_size} bytes) -> {path}")
    for edition in ("summer", "winter"):
        pm_path = written_promods[edition]
        print(f"Generated promods_{edition} icon ({pm_path.stat().st_size} bytes) -> {pm_path}")
    return 0


def _handle_package_promods_icons(args: argparse.Namespace) -> int:
    out_dir = cast(Path, args.out_dir)
    try:
        written = generate_promods_icons(out_dir)
    except (OSError, ValueError) as exc:
        print(f"error: ProMods icon generation failed: {exc}", file=sys.stderr)
        return 1

    for edition in ("summer", "winter"):
        path = written[edition]
        print(f"Generated promods_{edition} icon ({path.stat().st_size} bytes) -> {path}")
    return 0


def _handle_package_promods(args: argparse.Namespace) -> int:
    edition_choice = cast(str, args.edition)
    mod_dir = cast(Path | None, args.mod_dir)
    game_dir = cast(Path | None, args.game_dir)
    out_dir = cast(Path, args.out_dir)
    snapshot_path = cast(Path | None, args.snapshot)
    checksums_path = cast(Path | None, args.checksums)
    require_all_packs = cast(bool, args.require_all_packs)
    eu_def = cast(Path | None, args.promods_eu)
    eu_assets = cast(Path | None, args.promods_eu_assets)
    me_def = cast(Path | None, args.promods_me)
    me_assets = cast(Path | None, args.promods_me_assets)
    ma_def = cast(Path | None, args.promods_ma)
    ma_assets = cast(Path | None, args.promods_ma_assets)
    tgs_def = cast(Path | None, args.promods_tgs)
    tgs_assets = cast(Path | None, args.promods_tgs_assets)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    aliases_path = cast(Path, args.aliases)
    baseline_dir = cast(Path, args.baseline_dir)
    icons_dir = cast(Path, args.icons_dir)
    prices_lock_path = cast(Path, args.prices_lock)
    package_version = cast(str | None, args.package_version)
    author = cast(str, args.author)
    as_json = cast(bool, args.json)

    editions: tuple[Season, ...] = (
        ("summer", "winter")
        if edition_choice == "all"
        else ("summer",)
        if edition_choice == "summer"
        else ("winter",)
    )

    try:
        reports = build_promods_editions(
            out_dir,
            editions=editions,
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
        )
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        ValidationError,
        ProtectedPayloadError,
        UnsupportedCompressionError,
    ) as exc:
        print(f"error: ProMods companion build failed: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = {
            edition: reports[edition].model_dump(mode="json") for edition in editions
        }
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    for edition in editions:
        rep = reports[edition]
        print(
            f"Built {rep.edition} ProMods Edition ({rep.package_version}): "
            f"{rep.countries_patched} countries ({rep.vanilla_countries_emitted} vanilla + "
            f"{rep.promods_countries_emitted} ProMods), pm_fuel={rep.pm_fuel_modules_emitted}, "
            f"workshop={rep.workshop_dir} ({rep.workshop_file_count} files), "
            f"local={rep.local_zip_path} (sha256={rep.local_zip_sha256[:12]}...)"
        )
    return 0


def _handle_package_build(args: argparse.Namespace) -> int:
    edition_choice = cast(str, args.edition)
    out_dir = cast(Path, args.out_dir)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
    icons_dir = cast(Path, args.icons_dir)
    prices_lock_path = cast(Path, args.prices_lock)
    package_version = cast(str | None, args.package_version)
    author = cast(str, args.author)
    raw_date = cast(str | None, args.date)
    anchor_year = cast(int, args.anchor_year)

    try:
        override_date = _parse_iso_date_arg(raw_date)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    editions: tuple[Season, ...] = (
        ("summer", "winter")
        if edition_choice == "all"
        else ("summer",)
        if edition_choice == "summer"
        else ("winter",)
    )

    try:
        built = build_core_editions(
            out_dir,
            editions=editions,
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            baseline_dir=baseline_dir,
            icons_dir=icons_dir,
            prices_lock_path=prices_lock_path,
            package_version=package_version,
            author=author,
            anchor_year=anchor_year,
            override_date=override_date,
        )
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: package build failed: {exc}", file=sys.stderr)
        return 1

    for edition in editions:
        info = built[edition]
        print(
            f"Built {info.edition} Core ({info.package_version}): "
            f"workshop={info.workshop_dir} ({info.workshop_file_count} files), "
            f"local={info.local_zip_path} (sha256={info.local_zip_sha256[:12]}...)"
        )
    return 0


def _emit_validation_report(report: ValidationReport, *, as_json: bool) -> int:
    if as_json:
        payload: object = report.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if report.ok else 1

    if report.ok:
        print(f"Validation passed ({report.mode}): {report.target} (0 errors, 0 warnings).")
        return 0

    for issue in report.issues:
        loc = f" [{issue.path}]" if issue.path else ""
        print(f"{issue.severity.upper()} {issue.code}{loc}: {issue.detail}", file=sys.stderr)
    return 1


def _handle_validate_workshop(args: argparse.Namespace) -> int:
    target = cast(Path, args.target)
    baseline_dir = cast(Path | None, args.baseline_dir)
    profile = cast(PackageProfile, args.profile)
    as_json = cast(bool, args.json)
    try:
        report = validate_workshop_package(target, baseline_dir=baseline_dir, profile=profile)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: workshop validation failed: {exc}", file=sys.stderr)
        return 1
    return _emit_validation_report(report, as_json=as_json)


def _handle_validate_local(args: argparse.Namespace) -> int:
    target = cast(Path, args.target)
    baseline_dir = cast(Path | None, args.baseline_dir)
    profile = cast(PackageProfile, args.profile)
    as_json = cast(bool, args.json)
    try:
        report = validate_local_zip(target, baseline_dir=baseline_dir, profile=profile)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: local ZIP validation failed: {exc}", file=sys.stderr)
        return 1
    return _emit_validation_report(report, as_json=as_json)


def _handle_publish_release(args: argparse.Namespace) -> int:
    state_path = cast(Path, args.state)
    prices_lock_path = cast(Path, args.prices_lock)
    out_dir = cast(Path, args.out_dir)
    changelogs_dir = cast(Path, args.changelogs_dir)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
    icons_dir = cast(Path, args.icons_dir)
    raw_build_date = cast(str | None, args.build_date)
    author = cast(str, args.author)
    anchor_year = cast(int | None, args.anchor_year)
    write_state = cast(bool, args.write_state)
    force_run = cast(bool, args.force)
    previous_snapshots_dir = cast(Path | None, args.previous_snapshots_dir)
    as_json = cast(bool, args.json)

    try:
        parsed_build_date = _parse_iso_date_arg(raw_build_date, flag_name="--build-date")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        previous_snapshots: dict[Season, RealismSnapshot] | None = None
        if previous_snapshots_dir is not None:
            if not previous_snapshots_dir.is_dir():
                raise FileNotFoundError(
                    f"--previous-snapshots-dir does not exist or is not a directory: "
                    f"{previous_snapshots_dir}"
                )
            loaded_prev: dict[Season, RealismSnapshot] = {}
            for edition_name in ("summer", "winter"):
                snap_file = previous_snapshots_dir / f"realism-snapshot-{edition_name}.json"
                if snap_file.is_file():
                    loaded_prev[edition_name] = load_realism_snapshot(snap_file)
            if loaded_prev:
                previous_snapshots = loaded_prev

        summary = run_phase_a_release(
            state_path=state_path,
            prices_lock_path=prices_lock_path,
            out_dir=out_dir,
            changelogs_dir=changelogs_dir,
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            baseline_dir=baseline_dir,
            icons_dir=icons_dir,
            build_date=parsed_build_date,
            author=author,
            anchor_year=anchor_year,
            write_state=write_state,
            force_run=force_run,
            previous_snapshots=previous_snapshots,
        )
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: Phase A release failed: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = summary.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    changed_label = ", ".join(summary.changed_editions) if summary.changed_editions else "none"
    print(
        f"Phase A release complete ({summary.build_date}): "
        f"any_changed={str(summary.any_changed).lower()}, "
        f"snapshots_changed={str(summary.snapshots_changed).lower()}, "
        f"changed_editions=[{changed_label}], "
        f"force_run={str(summary.force_run).lower()}"
    )
    for edition in ("summer", "winter"):
        res = summary.editions[edition]
        status = "CHANGED" if res.changed else "NO-OP"
        print(
            f"  {edition}: {status} version={res.package_version} "
            f"payload_sha256={res.payload_sha256[:12]}... "
            f"snapshot_sha256={res.snapshot_sha256[:12]}..."
        )
    return 0


def _handle_fetch(args: argparse.Namespace) -> int:
    lock_path = cast(Path, args.lock_path)
    baseline_dir = cast(Path, args.baseline_dir)
    allow_jumps = cast(list[str] | None, args.allow_jump) or []
    fx_only = cast(bool, args.fx_only)
    seed_offline = cast(bool, args.seed_offline)
    no_global = cast(bool, args.no_global)
    no_tier2 = cast(bool, args.no_tier2)
    timeout = cast(float, args.timeout)
    dry_run = cast(bool, args.dry_run)
    as_json = cast(bool, args.json)

    if not math.isfinite(timeout) or timeout <= 0.0:
        print(
            f"error: --timeout must be finite and > 0.0, got {timeout!r}",
            file=sys.stderr,
        )
        return 1

    try:
        report = run_price_fetch(
            lock_path=lock_path,
            baseline_dir=baseline_dir,
            allow_jump_iso2=frozenset(code.strip().upper() for code in allow_jumps if code.strip()),
            fx_only=fx_only,
            seed_offline=seed_offline,
            include_global=not no_global,
            include_tier2=not no_tier2,
            timeout=timeout,
            write_lock=not dry_run,
        )
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: price fetch failed: {redact_url_secrets(str(exc))}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = report.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if report.ok else 1

    status_label = "OK" if report.ok else "FAILED"
    mode_label = "dry-run" if report.dry_run else f"lock={report.lock_path}"
    if report.fx_only:
        print(
            f"FX fetch {status_label} ({mode_label}): "
            f"{report.fx_currencies_validated} currencies validated, "
            f"{len(report.alerts)} alerts."
        )
    else:
        print(
            f"Price fetch {status_label} ({mode_label}): "
            f"tier1={report.tier1_feeds_succeeded} ok/{report.tier1_feeds_failed} failed, "
            f"global_tier1={report.global_tier1_feeds_succeeded} ok/"
            f"{report.global_tier1_feeds_failed} failed, "
            f"tier2={report.tier2_feeds_succeeded} ok/{report.tier2_feeds_failed} failed, "
            f"countries={report.countries_updated} updated/{report.countries_fallback} fallback, "
            f"fx={report.fx_currencies_validated}, alerts={len(report.alerts)}."
        )
    for alert in report.alerts:
        print(
            f"  {alert.severity.upper()} {alert.code} [{alert.scope}]: {alert.detail}",
            file=sys.stderr if alert.severity == "error" else sys.stdout,
        )
    return 0 if report.ok else 1


def _handle_compose_local(args: argparse.Namespace) -> int:
    season = cast(Season, args.season)
    game_log = cast(Path | None, args.game_log)
    profile = cast(Path | None, args.profile)
    modlist = cast(Path | None, args.modlist)
    modlist_order = cast(ModlistOrder, args.modlist_order)
    mod_dir = cast(Path | None, args.mod_dir)
    workshop_dir = cast(Path | None, args.workshop_dir)
    game_dir = cast(Path | None, args.game_dir)
    out_dir = cast(Path, args.out_dir)
    snapshot_path = cast(Path | None, args.snapshot)
    checksums_path = cast(Path | None, args.checksums)
    user_aliases_path = cast(Path | None, args.aliases)
    unpacked_defs = cast(list[Path] | None, args.unpacked_defs) or []
    strict_protected = cast(bool, args.strict_protected)
    patch_hardcoded_totems = cast(bool, args.patch_hardcoded_totems)
    no_totems = cast(bool, args.no_totems)
    no_self_exclude = cast(bool, args.no_self_exclude)
    dry_run = cast(bool, args.dry_run)
    report_json_path = cast(Path | None, args.report_json)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
    prices_lock_path = cast(Path, args.prices_lock)
    package_version = cast(str | None, args.package_version)
    author = cast(str, args.author)
    as_json = cast(bool, args.json)

    try:
        report = compose_local(
            season,
            out_dir=out_dir,
            game_log=game_log,
            profile=profile,
            modlist=modlist,
            modlist_order=modlist_order,
            mod_dir=mod_dir,
            workshop_dir=workshop_dir,
            game_dir=game_dir,
            snapshot_path=snapshot_path,
            checksums_path=checksums_path,
            user_aliases_path=user_aliases_path,
            unpacked_defs=unpacked_defs,
            strict_protected=strict_protected,
            patch_hardcoded_totems=patch_hardcoded_totems,
            no_totems=no_totems,
            exclude_self=not no_self_exclude,
            dry_run=dry_run,
            report_json_path=report_json_path,
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            baseline_dir=baseline_dir,
            prices_lock_path=prices_lock_path,
            package_version=package_version,
            author=author,
        )
    except (
        FileNotFoundError,
        NotADirectoryError,
        OSError,
        ValueError,
        ValidationError,
        ProtectedPayloadError,
        UnsupportedCompressionError,
    ) as exc:
        print(f"error: compose-local failed: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = report.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if report.ok else 1

    mode_label = "DRY-RUN" if report.dry_run else str(report.output_path)
    status_label = "OK" if report.ok else "FAILED"
    print(
        f"compose-local {status_label} ({report.edition}, {report.package_version}, "
        f"source={report.load_order_source}): "
        f"{report.countries_patched}/{report.countries_scanned} countries patched "
        f"({report.countries_unmatched} unmatched), "
        f"speed_limits={report.speed_limits_patched}, "
        f"pm_fuel={report.promods_fuel_modules_emitted}, "
        f"output={mode_label}"
    )
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 0 if report.ok else 1


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(data)
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise


def _handle_audit_osm_speeds(args: argparse.Namespace) -> int:
    iso2_raw = cast(str | None, args.iso2)
    include_overpass = cast(bool, args.overpass)
    include_taginfo = cast(bool, args.taginfo)
    rules_url = cast(str, args.rules_url)
    rules_file = cast(Path | None, args.rules_file)
    allowlist_path = cast(Path | None, args.allowlist)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    out_md = cast(Path | None, args.out_md)
    out_json = cast(Path | None, args.out_json)
    timeout = cast(float, args.timeout)
    fail_on_drift = cast(bool, args.fail_on_drift)
    as_json = cast(bool, args.json)

    if not math.isfinite(timeout) or timeout <= 0.0:
        print(f"error: --timeout must be finite and > 0, got {timeout!r}", file=sys.stderr)
        return 1

    iso2_filter: list[str] | None = None
    if iso2_raw is not None and iso2_raw.strip():
        iso2_filter = [part.strip().upper() for part in iso2_raw.split(",") if part.strip()]

    try:
        report = run_osm_speed_audit(
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            allowlist_path=allowlist_path,
            rules_file=rules_file,
            rules_url=rules_url,
            iso2_filter=iso2_filter,
            include_overpass=include_overpass,
            include_taginfo=include_taginfo,
            timeout=timeout,
        )
        if out_md is not None:
            md_text = render_osm_speed_drift_markdown(report)
            _write_bytes_atomic(out_md, md_text.encode("utf-8"))
        if out_json is not None:
            _write_bytes_atomic(out_json, serialize_audit_report_bytes(report))
    except (OSError, ValueError, ValidationError, HttpFetchError) as exc:
        print(f"error: audit osm-speeds failed: {redact_url_secrets(str(exc))}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = report.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            f"OSM speed audit: checked={report.countries_checked}, "
            f"matched={report.countries_matched_in_osm}, "
            f"unacknowledged_drift={report.unacknowledged_drift_count}, "
            f"acknowledged={report.acknowledged_difference_count}"
        )

    if fail_on_drift and report.unacknowledged_drift_count > 0:
        return 1
    return 0


def _handle_audit_taint(args: argparse.Namespace) -> int:
    repo_root = cast(Path, args.repo_root)
    snapshots = cast(list[Path] | None, args.snapshot) or []
    packages = cast(list[Path] | None, args.package) or []
    as_json = cast(bool, args.json)

    try:
        report = scan_repo_and_artifacts_for_taint(
            repo_root,
            snapshot_paths=snapshots,
            package_paths=packages,
        )
    except (
        OSError,
        ValueError,
        ValidationError,
        ProtectedPayloadError,
        UnsupportedCompressionError,
    ) as exc:
        print(f"error: audit taint failed: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = report.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        status = "PASSED" if report.ok else "FAILED"
        print(
            f"License taint scan {status}: files_scanned={report.files_scanned}, "
            f"snapshots={report.snapshots_scanned}, packages={report.packages_scanned}, "
            f"violations={report.violation_count}"
        )
        for violation in report.violations:
            print(
                f"error: [{violation.marker}] {violation.path}:{violation.line_number}: "
                f"{violation.excerpt}",
                file=sys.stderr,
            )
    return 0 if report.ok else 1


def _make_help_handler(subparser: argparse.ArgumentParser) -> CommandHandler:
    def _show_help(_args: argparse.Namespace) -> int:
        subparser.print_help()
        return 0

    return _show_help


def build_parser() -> argparse.ArgumentParser:
    """Build the root CLI argument parser for ``ets2-realism``."""
    parser = argparse.ArgumentParser(
        prog="ets2-realism",
        description="Clean-room ETS2 1.62+ country realism generator and VFS/SII toolkit.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    vfs_parser = subparsers.add_parser(
        "vfs",
        help="Inspect VFS archives and overlays.",
    )
    vfs_parser.set_defaults(handler=_make_help_handler(vfs_parser))
    vfs_subparsers = vfs_parser.add_subparsers(dest="vfs_command", metavar="SUBCOMMAND")
    vfs_inspect = vfs_subparsers.add_parser(
        "inspect",
        help="Inspect one or more .scs/.zip archives or unpacked directories.",
    )
    vfs_inspect.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Archive or directory path(s) ordered from lowest to highest priority.",
    )
    vfs_inspect.add_argument(
        "--prefix",
        action="append",
        default=None,
        dest="prefixes",
        help="Seeded or filter VFS prefix (can be repeated).",
    )
    vfs_inspect.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum sample entry paths to display (default: 20).",
    )
    vfs_inspect.add_argument(
        "--json",
        action="store_true",
        help="Print inspection output as JSON.",
    )
    vfs_inspect.set_defaults(handler=_handle_vfs_inspect)

    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Extract and verify clean-room ETS2 baseline JSON schemas.",
    )
    baseline_parser.set_defaults(handler=_make_help_handler(baseline_parser))
    baseline_subparsers = baseline_parser.add_subparsers(
        dest="baseline_command",
        metavar="SUBCOMMAND",
    )
    baseline_extract = baseline_subparsers.add_parser(
        "extract",
        help="Extract clean-room ETS2 baseline JSONs from game archives.",
    )
    baseline_extract.add_argument(
        "--game-dir",
        type=Path,
        default=None,
        help="ETS2 install directory (overrides ETS2_GAME_DIR and default Steam path).",
    )
    baseline_extract.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Target directory for clean-room baseline JSON files.",
    )
    baseline_extract.add_argument(
        "--raw-cache-dir",
        type=Path,
        default=None,
        help="Optional gitignored directory to dump raw .sii/.sui files for local testing.",
    )
    baseline_extract.add_argument(
        "--check",
        action="store_true",
        help="Verify existing baseline JSONs match extraction with zero byte diff.",
    )
    baseline_extract.set_defaults(handler=_handle_baseline_extract)

    registry_parser = subparsers.add_parser(
        "registry",
        help="Validate and inspect canonical per-country realism law registries.",
    )
    registry_parser.set_defaults(handler=_make_help_handler(registry_parser))
    registry_subparsers = registry_parser.add_subparsers(
        dest="registry_command",
        metavar="SUBCOMMAND",
    )
    registry_validate = registry_subparsers.add_parser(
        "validate",
        help="Validate country law JSON files and mappings against the ETS2 baseline.",
    )
    registry_validate.add_argument(
        "--laws-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory containing countries/<iso2>.json law records (default: data/laws).",
    )
    registry_validate.add_argument(
        "--mappings",
        type=Path,
        default=Path("data/mappings/ets2_countries.json"),
        help="Path to ets2_countries.json mapping file.",
    )
    registry_validate.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    registry_validate.add_argument(
        "--json",
        action="store_true",
        help="Print validation report as JSON.",
    )
    registry_validate.set_defaults(handler=_handle_registry_validate)

    registry_snapshot = registry_subparsers.add_parser(
        "snapshot",
        help="Export a deterministic schema_version=1 realism-snapshot JSON file.",
    )
    registry_snapshot.add_argument(
        "--season",
        choices=("summer", "winter"),
        required=True,
        help="Seasonal edition to resolve (summer or winter).",
    )
    registry_snapshot.add_argument(
        "--date",
        type=str,
        default=None,
        help="Optional ISO YYYY-MM-DD override date for timezone resolution.",
    )
    registry_snapshot.add_argument(
        "--anchor-year",
        type=int,
        default=DEFAULT_ANCHOR_YEAR,
        help=f"Anchor year when --date is omitted (default: {DEFAULT_ANCHOR_YEAR}).",
    )
    registry_snapshot.add_argument(
        "--laws-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory containing countries/<iso2>.json law records (default: data/laws).",
    )
    registry_snapshot.add_argument(
        "--mappings",
        type=Path,
        default=Path("data/mappings/ets2_countries.json"),
        help="Path to ets2_countries.json mapping file.",
    )
    registry_snapshot.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    registry_snapshot.add_argument(
        "--prices-lock",
        type=Path,
        default=None,
        help="Optional path to state/prices.lock.json to inject live/locked fuel prices.",
    )
    registry_snapshot.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON file path for the generated realism snapshot.",
    )
    registry_snapshot.set_defaults(handler=_handle_registry_snapshot)

    registry_snapshot_verify = registry_subparsers.add_parser(
        "snapshot-verify",
        help="Verify a v1 realism snapshot file offline (schema, hygiene, and SHA256SUMS.txt).",
    )
    registry_snapshot_verify.add_argument(
        "snapshot_path",
        type=Path,
        help="Path to the realism-snapshot-{summer,winter}.json file to verify.",
    )
    registry_snapshot_verify.add_argument(
        "--checksums",
        type=Path,
        default=None,
        help=(
            "Optional path to SHA256SUMS.txt manifest (auto-checks sibling SHA256SUMS.txt "
            "next to snapshot_path when omitted)."
        ),
    )
    registry_snapshot_verify.add_argument(
        "--expected-edition",
        choices=("summer", "winter"),
        default=None,
        help="Optional expected seasonal edition (summer or winter).",
    )
    registry_snapshot_verify.add_argument(
        "--json",
        action="store_true",
        help="Print SnapshotVerificationResult as JSON.",
    )
    registry_snapshot_verify.set_defaults(handler=_handle_registry_snapshot_verify)

    package_parser = subparsers.add_parser(
        "package",
        help="Generate clean-room icons and build seasonal Workshop/local Core packages.",
    )
    package_parser.set_defaults(handler=_make_help_handler(package_parser))
    package_subparsers = package_parser.add_subparsers(
        dest="package_command",
        metavar="SUBCOMMAND",
    )

    package_icons = package_subparsers.add_parser(
        "icons",
        help="Generate clean-room 276x162 Core and ProMods Summer/Winter JPEG icons.",
    )
    package_icons.add_argument(
        "--out-dir",
        type=Path,
        default=Path("assets/icons"),
        help="Output directory for Core & ProMods JPEG icons (default: assets/icons).",
    )
    package_icons.set_defaults(handler=_handle_package_icons)

    package_promods_icons = package_subparsers.add_parser(
        "promods-icons",
        help="Generate clean-room 276x162 ProMods Summer and Winter JPEG icons.",
    )
    package_promods_icons.add_argument(
        "--out-dir",
        type=Path,
        default=Path("assets/icons"),
        help="Output directory for promods_{summer,winter}.jpg (default: assets/icons).",
    )
    package_promods_icons.set_defaults(handler=_handle_package_promods_icons)

    package_promods = package_subparsers.add_parser(
        "promods",
        help="Build standalone all-in-one ProMods Editions from local ProMods archives (offline).",
    )
    package_promods.add_argument(
        "--edition",
        choices=("summer", "winter", "all"),
        default="all",
        help="Seasonal ProMods Edition(s) to compile (default: all).",
    )
    package_promods.add_argument(
        "--mod-dir",
        type=Path,
        default=None,
        help="ETS2 mod directory containing ProMods def/defmap & assets archives.",
    )
    package_promods.add_argument(
        "--game-dir",
        type=Path,
        default=None,
        help="Optional ETS2 install dir containing Vanilla def.scs (defaults to 1.62 baseline).",
    )
    package_promods.add_argument(
        "--out-dir",
        type=Path,
        default=Path("dist"),
        help="Root output directory for workshop/promods-* and local/ targets (default: dist).",
    )
    package_promods.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Optional offline v1 realism-snapshot-{summer,winter}.json path.",
    )
    package_promods.add_argument(
        "--checksums",
        type=Path,
        default=None,
        help="Optional SHA256SUMS.txt manifest path to verify --snapshot.",
    )
    package_promods.add_argument(
        "--require-all-packs",
        action="store_true",
        help="Fail fast unless EU, ME, MA, and TGS def/defmap + EU/ME/TGS assets are all present.",
    )
    package_promods.add_argument(
        "--promods-eu", type=Path, default=None, help="Explicit EU def path."
    )
    package_promods.add_argument(
        "--promods-eu-assets", type=Path, default=None, help="Explicit EU assets path."
    )
    package_promods.add_argument(
        "--promods-me", type=Path, default=None, help="Explicit ME defmap path."
    )
    package_promods.add_argument(
        "--promods-me-assets", type=Path, default=None, help="Explicit ME assets path."
    )
    package_promods.add_argument(
        "--promods-ma", type=Path, default=None, help="Explicit MA defmap path."
    )
    package_promods.add_argument(
        "--promods-ma-assets", type=Path, default=None, help="Explicit MA assets path."
    )
    package_promods.add_argument(
        "--promods-tgs", type=Path, default=None, help="Explicit TGS defmap path."
    )
    package_promods.add_argument(
        "--promods-tgs-assets", type=Path, default=None, help="Explicit TGS assets path."
    )
    package_promods.add_argument(
        "--laws-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory containing countries/<iso2>.json law records (default: data/laws).",
    )
    package_promods.add_argument(
        "--mappings",
        type=Path,
        default=Path("data/mappings/ets2_countries.json"),
        help="Path to ets2_countries.json mapping file.",
    )
    package_promods.add_argument(
        "--aliases",
        type=Path,
        default=Path("data/mappings/country_aliases.json"),
        help="Path to bundled country_aliases.json mapping file.",
    )
    package_promods.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    package_promods.add_argument(
        "--icons-dir",
        type=Path,
        default=Path("assets/icons"),
        help="Directory containing checked-in promods_{summer,winter}.jpg icons.",
    )
    package_promods.add_argument(
        "--prices-lock",
        type=Path,
        default=Path("state/prices.lock.json"),
        help="Path to canonical state/prices.lock.json lockfile (used when --snapshot is omitted).",
    )
    package_promods.add_argument(
        "--package-version",
        type=str,
        default=None,
        help="Optional explicit package_version override.",
    )
    package_promods.add_argument(
        "--author",
        type=str,
        default=DEFAULT_AUTHOR,
        help=f"Mod author string for manifest.sii (default: {DEFAULT_AUTHOR!r}).",
    )
    package_promods.add_argument(
        "--json",
        action="store_true",
        help="Print ProModsBuildReport mapping as JSON.",
    )
    package_promods.set_defaults(handler=_handle_package_promods)

    package_build = package_subparsers.add_parser(
        "build",
        help="Build unpacked Workshop roots and deterministic local ZIP Core mods.",
    )
    package_build.add_argument(
        "--edition",
        choices=("summer", "winter", "all"),
        default="all",
        help="Seasonal edition(s) to compile (default: all).",
    )
    package_build.add_argument(
        "--out-dir",
        type=Path,
        default=Path("dist"),
        help="Root output directory for workshop/ and local/ targets (default: dist).",
    )
    package_build.add_argument(
        "--laws-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory containing countries/<iso2>.json law records (default: data/laws).",
    )
    package_build.add_argument(
        "--mappings",
        type=Path,
        default=Path("data/mappings/ets2_countries.json"),
        help="Path to ets2_countries.json mapping file.",
    )
    package_build.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    package_build.add_argument(
        "--icons-dir",
        type=Path,
        default=Path("assets/icons"),
        help="Directory containing checked-in summer.jpg and winter.jpg icons.",
    )
    package_build.add_argument(
        "--prices-lock",
        type=Path,
        default=Path("state/prices.lock.json"),
        help="Path to canonical state/prices.lock.json lockfile (default: state/prices.lock.json).",
    )
    package_build.add_argument(
        "--package-version",
        type=str,
        default=None,
        help="Optional explicit package_version override (default: ISO week of anchor date).",
    )
    package_build.add_argument(
        "--author",
        type=str,
        default=DEFAULT_AUTHOR,
        help=f"Mod author string for manifest.sii (default: {DEFAULT_AUTHOR!r}).",
    )
    package_build.add_argument(
        "--date",
        type=str,
        default=None,
        help="Optional ISO YYYY-MM-DD override date for timezone resolution.",
    )
    package_build.add_argument(
        "--anchor-year",
        type=int,
        default=DEFAULT_ANCHOR_YEAR,
        help=f"Anchor year when --date is omitted (default: {DEFAULT_ANCHOR_YEAR}).",
    )
    package_build.set_defaults(handler=_handle_package_build)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Run the Offline SCS Workshop Validator and 1.62 realism invariant checks.",
    )
    validate_parser.set_defaults(handler=_make_help_handler(validate_parser))
    validate_subparsers = validate_parser.add_subparsers(
        dest="validate_command",
        metavar="SUBCOMMAND",
    )

    validate_workshop = validate_subparsers.add_parser(
        "workshop",
        help="Validate an unpacked Steam Workshop directory root (versions.sii + universal/).",
    )
    validate_workshop.add_argument(
        "target",
        type=Path,
        help="Path to the staged Workshop root directory.",
    )
    validate_workshop.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    validate_workshop.add_argument(
        "--profile",
        choices=("core", "promods", "combo"),
        default="core",
        help="Validation profile: core (default), promods, or combo.",
    )
    validate_workshop.add_argument(
        "--json",
        action="store_true",
        help="Print validation report as JSON.",
    )
    validate_workshop.set_defaults(handler=_handle_validate_workshop)

    validate_local = validate_subparsers.add_parser(
        "local",
        help="Validate a standalone local playtest .zip package.",
    )
    validate_local.add_argument(
        "target",
        type=Path,
        help="Path to the standalone local .zip archive.",
    )
    validate_local.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    validate_local.add_argument(
        "--profile",
        choices=("core", "promods", "combo"),
        default="core",
        help="Validation profile: core (default), promods, or combo.",
    )
    validate_local.add_argument(
        "--json",
        action="store_true",
        help="Print validation report as JSON.",
    )
    validate_local.set_defaults(handler=_handle_validate_local)

    publish_parser = subparsers.add_parser(
        "publish",
        help="Run Phase A diff-gated release orchestration and changelog generation.",
    )
    publish_parser.set_defaults(handler=_make_help_handler(publish_parser))
    publish_subparsers = publish_parser.add_subparsers(
        dest="publish_command",
        metavar="SUBCOMMAND",
    )

    publish_release = publish_subparsers.add_parser(
        "release",
        help="Build, offline-validate, diff-gate, and emit Phase A seasonal Core releases.",
    )
    publish_release.add_argument(
        "--state",
        type=Path,
        default=Path("state/published.json"),
        help="Path to the v1 published release ledger (default: state/published.json).",
    )
    publish_release.add_argument(
        "--prices-lock",
        type=Path,
        default=Path("state/prices.lock.json"),
        help="Path to canonical state/prices.lock.json lockfile (default: state/prices.lock.json).",
    )
    publish_release.add_argument(
        "--out-dir",
        type=Path,
        default=Path("dist"),
        help="Output directory for workshop/, local/, snapshots/, and release_summary.json.",
    )
    publish_release.add_argument(
        "--changelogs-dir",
        type=Path,
        default=Path("."),
        help="Output directory for CHANGELOG_SUMMER.md and CHANGELOG_WINTER.md (default: .).",
    )
    publish_release.add_argument(
        "--laws-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory containing countries/<iso2>.json law records (default: data/laws).",
    )
    publish_release.add_argument(
        "--mappings",
        type=Path,
        default=Path("data/mappings/ets2_countries.json"),
        help="Path to ets2_countries.json mapping file.",
    )
    publish_release.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    publish_release.add_argument(
        "--icons-dir",
        type=Path,
        default=Path("assets/icons"),
        help="Directory containing checked-in summer.jpg and winter.jpg icons.",
    )
    publish_release.add_argument(
        "--build-date",
        type=str,
        default=None,
        help="Optional ISO YYYY-MM-DD date used for ISO-week package_version resolution.",
    )
    publish_release.add_argument(
        "--author",
        type=str,
        default=DEFAULT_AUTHOR,
        help=f"Mod author string for manifest.sii (default: {DEFAULT_AUTHOR!r}).",
    )
    publish_release.add_argument(
        "--anchor-year",
        type=int,
        default=None,
        help="Anchor year for seasonal DST resolution (default: build date year).",
    )
    publish_release.add_argument(
        "--write-state",
        action="store_true",
        help="Update --state published ledger file when one or more editions changed.",
    )
    publish_release.add_argument(
        "--force",
        action="store_true",
        help="Emit validated changelogs and artifacts even when canonical hashes are unchanged.",
    )
    publish_release.add_argument(
        "--previous-snapshots-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory containing previous realism-snapshot-{summer,winter}.json "
            "files for structured changelog diffing."
        ),
    )
    publish_release.add_argument(
        "--json",
        action="store_true",
        help="Print PhaseAReleaseSummary as JSON.",
    )
    publish_release.set_defaults(handler=_handle_publish_release)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch live European FX rates and open fuel data into state/prices.lock.json.",
    )
    fetch_parser.add_argument(
        "--lock-path",
        type=Path,
        default=Path("state/prices.lock.json"),
        help="Path to the prices.lock.json state file (default: state/prices.lock.json).",
    )
    fetch_parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    fetch_parser.add_argument(
        "--allow-jump",
        action="append",
        default=None,
        help="Explicitly allow >25%% WoW price jump for an ISO-2 country code (repeatable).",
    )
    fetch_parser.add_argument(
        "--fx-only",
        action="store_true",
        help="Fetch and cross-validate multi-provider FX rates only.",
    )
    fetch_parser.add_argument(
        "--seed-offline",
        action="store_true",
        help="Deterministically seed state/prices.lock.json offline from 1.62 baseline.",
    )
    fetch_parser.add_argument(
        "--no-global",
        action="store_true",
        help="Skip non-EU Global Tier 1 fuel collectors (EU Core only).",
    )
    fetch_parser.add_argument(
        "--no-tier2",
        action="store_true",
        help="Skip Tier 2 guarded national portal scrapers.",
    )
    fetch_parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-request HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    fetch_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate fetched data without modifying --lock-path on disk.",
    )
    fetch_parser.add_argument(
        "--json",
        action="store_true",
        help="Print FetchRunReport as JSON.",
    )
    fetch_parser.set_defaults(handler=_handle_fetch)

    compose_parser = subparsers.add_parser(
        "compose-local",
        help="Compose an offline validated zz_ETS2_Realism_ComboPatch_*.scs for local map combos.",
    )
    compose_parser.add_argument(
        "--season",
        choices=("summer", "winter"),
        required=True,
        help="Seasonal realism edition to compose (summer or winter).",
    )
    load_order_group = compose_parser.add_mutually_exclusive_group(required=True)
    load_order_group.add_argument(
        "--game-log",
        type=Path,
        default=None,
        help="Path to ETS2 game.log.txt for active mount order discovery.",
    )
    load_order_group.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Path to plaintext ETS2 profile.sii (ScsC-encrypted profiles are refused).",
    )
    load_order_group.add_argument(
        "--modlist",
        type=Path,
        default=None,
        help="Path to line-delimited mod list text file.",
    )
    compose_parser.add_argument(
        "--modlist-order",
        choices=("top-to-bottom", "bottom-to-top"),
        default="top-to-bottom",
        help="Priority ordering of --modlist lines (default: top-to-bottom Mod Manager UI order).",
    )
    compose_parser.add_argument(
        "--mod-dir",
        type=Path,
        default=None,
        help="ETS2 local mod directory containing .scs/.zip/unpacked mods.",
    )
    compose_parser.add_argument(
        "--workshop-dir",
        type=Path,
        default=None,
        help="Optional Steam Workshop 227300 directory (steamapps/workshop/content/227300).",
    )
    compose_parser.add_argument(
        "--game-dir",
        type=Path,
        default=None,
        help="Optional ETS2 install directory containing def.scs (defaults to clean-room 1.62).",
    )
    compose_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("dist/local"),
        help=(
            "Output directory for zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs "
            "(default: dist/local)."
        ),
    )
    compose_parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Optional offline v1 realism-snapshot-{summer,winter}.json path.",
    )
    compose_parser.add_argument(
        "--checksums",
        type=Path,
        default=None,
        help="Optional SHA256SUMS.txt manifest path to verify --snapshot.",
    )
    compose_parser.add_argument(
        "--aliases",
        type=Path,
        default=None,
        help="Optional user country_aliases.json override merged atop bundled aliases.",
    )
    compose_parser.add_argument(
        "--unpacked-defs",
        action="append",
        type=Path,
        default=None,
        help=(
            "Repeatable unpacked def directory (stem-matched child dirs substitute protected "
            "archives in-place; raw def/locale dirs mount as high-priority overrides)."
        ),
    )
    compose_parser.add_argument(
        "--strict-protected",
        action="store_true",
        help="Exit non-zero without writing .scs if any protected archive remains unsubstituted.",
    )
    compose_parser.add_argument(
        "--patch-hardcoded-totems",
        action="store_true",
        help="Opt-in surgical rewriting of verified JRR/7RM hardcoded numeric gas boards.",
    )
    compose_parser.add_argument(
        "--no-totems",
        action="store_true",
        help="Emit def/country/ realism patches only (skip all sign boards and fuel locales).",
    )
    compose_parser.add_argument(
        "--no-self-exclude",
        action="store_true",
        help="Disable automatic D-10 exclusion of previous managed packages in the load order.",
    )
    compose_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and audit the full combo merge without writing a .scs file.",
    )
    compose_parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional path to write the deterministic sorted JSON ComposeReport.",
    )
    compose_parser.add_argument(
        "--laws-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory containing countries/<iso2>.json law records (default: data/laws).",
    )
    compose_parser.add_argument(
        "--mappings",
        type=Path,
        default=Path("data/mappings/ets2_countries.json"),
        help="Path to ets2_countries.json mapping file.",
    )
    compose_parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("data/baselines/ets2_1.62_def"),
        help="Directory containing clean-room ETS2 baseline JSON files.",
    )
    compose_parser.add_argument(
        "--prices-lock",
        type=Path,
        default=Path("state/prices.lock.json"),
        help="Path to canonical state/prices.lock.json (used only when --snapshot is omitted).",
    )
    compose_parser.add_argument(
        "--package-version",
        type=str,
        default=None,
        help="Optional explicit package_version override.",
    )
    compose_parser.add_argument(
        "--author",
        type=str,
        default=DEFAULT_AUTHOR,
        help=f"Mod author string for manifest.sii (default: {DEFAULT_AUTHOR!r}).",
    )
    compose_parser.add_argument(
        "--json",
        action="store_true",
        help="Print ComposeReport as deterministic JSON.",
    )
    compose_parser.set_defaults(handler=_handle_compose_local)

    audit_parser = subparsers.add_parser(
        "audit",
        help="Quarantined internal OSM speed-limit drift audit and CC BY 4.0 license-taint checks.",
    )
    audit_parser.set_defaults(handler=_make_help_handler(audit_parser))
    audit_subparsers = audit_parser.add_subparsers(
        dest="audit_command",
        metavar="SUBCOMMAND",
    )

    audit_osm_parser = audit_subparsers.add_parser(
        "osm-speeds",
        help="Compare data/laws/ statutory limits against westnordost/osm-legal-default-speeds.",
    )
    audit_osm_parser.add_argument(
        "--iso2",
        type=str,
        default=None,
        help="Optional comma-separated ISO-2 country codes to audit (default: all countries).",
    )
    audit_osm_parser.add_argument(
        "--overpass",
        action="store_true",
        help="Opt-in Overpass tags-only spot-checks (requires <= 10 selected ISO-2 codes).",
    )
    audit_osm_parser.add_argument(
        "--taginfo",
        action="store_true",
        help="Opt-in Taginfo API v4 global maxspeed value distributions.",
    )
    audit_osm_parser.add_argument(
        "--rules-url",
        type=str,
        default=DEFAULT_WESTNORDOST_RULES_URL,
        help=(
            "HTTPS URL to westnordost legal_default_speeds.json "
            f"(default: {DEFAULT_WESTNORDOST_RULES_URL})."
        ),
    )
    audit_osm_parser.add_argument(
        "--rules-file",
        type=Path,
        default=None,
        help="Optional local path to westnordost legal_default_speeds.json (offline mode).",
    )
    audit_osm_parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST_PATH,
        help=f"Clean-room statutory deviation allowlist JSON (default: {DEFAULT_ALLOWLIST_PATH}).",
    )
    audit_osm_parser.add_argument(
        "--laws-dir",
        type=Path,
        default=Path("data/laws"),
        help="Directory containing countries/<iso2>.json law records (default: data/laws).",
    )
    audit_osm_parser.add_argument(
        "--mappings",
        type=Path,
        default=Path("data/mappings/ets2_countries.json"),
        help="Path to ets2_countries.json mapping file.",
    )
    audit_osm_parser.add_argument(
        "--out-md",
        type=Path,
        default=None,
        help="Optional output path for sanitized Markdown drift report.",
    )
    audit_osm_parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Optional output path for deterministic sorted JSON drift report.",
    )
    audit_osm_parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    audit_osm_parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit non-zero if unacknowledged speed-limit drift is detected.",
    )
    audit_osm_parser.add_argument(
        "--json",
        action="store_true",
        help="Print OsmSpeedAuditReport as deterministic sorted JSON.",
    )
    audit_osm_parser.set_defaults(handler=_handle_audit_osm_speeds)

    audit_taint_parser = audit_subparsers.add_parser(
        "taint",
        help="Scan data/, state/, snapshots, and packages for forbidden license/source markers.",
    )
    audit_taint_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root directory to scan (default: current directory).",
    )
    audit_taint_parser.add_argument(
        "--snapshot",
        action="append",
        type=Path,
        default=None,
        help="Repeatable realism-snapshot-*.json path to include in taint scan.",
    )
    audit_taint_parser.add_argument(
        "--package",
        action="append",
        type=Path,
        default=None,
        help="Repeatable unpacked Workshop dir or .zip/.scs package path to scan.",
    )
    audit_taint_parser.add_argument(
        "--json",
        action="store_true",
        help="Print TaintScanReport as deterministic sorted JSON.",
    )
    audit_taint_parser.set_defaults(handler=_handle_audit_taint)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the ``ets2-realism`` CLI and return a POSIX exit status code."""
    parser = build_parser()
    arg_list = list(argv) if argv is not None else None
    try:
        args = parser.parse_args(arg_list)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1

    raw_handler: object = getattr(args, "handler", None)
    if callable(raw_handler):
        handler = cast(CommandHandler, raw_handler)
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
