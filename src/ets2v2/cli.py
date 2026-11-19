"""Command-line entrypoint for ets2v2."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from ets2v2 import __version__
from ets2v2.baseline import (
    BaselineManifest,
    CountriesBaseline,
    LocalesBaseline,
    extract_baseline,
    verify_baseline_bundle,
    write_baseline_bundle,
)
from ets2v2.package import (
    DEFAULT_AUTHOR,
    build_core_editions,
    generate_all_icons,
)
from ets2v2.registry import (
    DEFAULT_ANCHOR_YEAR,
    Season,
    build_realism_snapshot,
    load_law_registry,
    validate_law_registry,
    write_realism_snapshot,
)
from ets2v2.validate import (
    ValidationReport,
    validate_local_zip,
    validate_workshop_package,
)
from ets2v2.vfs import (
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsStack,
)
from ets2v2.vfs.hashfs import DEFAULT_SEEDED_PREFIXES

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

    issues = validate_law_registry(laws_dir, mappings_path, baseline_dir)
    country_count = 0
    if not issues:
        bundle = load_law_registry(laws_dir, mappings_path)
        country_count = len(bundle.laws_by_iso2)

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


def _parse_iso_date_arg(raw_date: str | None) -> date | None:
    if raw_date is None:
        return None
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError(f"invalid --date {raw_date!r} (expected ISO YYYY-MM-DD)") from exc
    if parsed_date.isoformat() != raw_date:
        raise ValueError(f"invalid --date {raw_date!r} (expected ISO YYYY-MM-DD)")
    return parsed_date


def _handle_registry_snapshot(args: argparse.Namespace) -> int:
    season = cast(Season, args.season)
    raw_date = cast(str | None, args.date)
    anchor_year = cast(int, args.anchor_year)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
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

        snapshot = build_realism_snapshot(
            registry,
            bl_countries,
            bl_locales,
            season,
            anchor_year=anchor_year,
            override_date=override_date,
            baseline_game_version=game_version,
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


def _handle_package_icons(args: argparse.Namespace) -> int:
    out_dir = cast(Path, args.out_dir)
    try:
        written = generate_all_icons(out_dir)
    except (OSError, ValueError) as exc:
        print(f"error: icon generation failed: {exc}", file=sys.stderr)
        return 1

    for edition in ("summer", "winter"):
        path = written[edition]
        print(f"Generated {edition} icon ({path.stat().st_size} bytes) -> {path}")
    return 0


def _handle_package_build(args: argparse.Namespace) -> int:
    edition_choice = cast(str, args.edition)
    out_dir = cast(Path, args.out_dir)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
    icons_dir = cast(Path, args.icons_dir)
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
    as_json = cast(bool, args.json)
    try:
        report = validate_workshop_package(target, baseline_dir=baseline_dir)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: workshop validation failed: {exc}", file=sys.stderr)
        return 1
    return _emit_validation_report(report, as_json=as_json)


def _handle_validate_local(args: argparse.Namespace) -> int:
    target = cast(Path, args.target)
    baseline_dir = cast(Path | None, args.baseline_dir)
    as_json = cast(bool, args.json)
    try:
        report = validate_local_zip(target, baseline_dir=baseline_dir)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: local ZIP validation failed: {exc}", file=sys.stderr)
        return 1
    return _emit_validation_report(report, as_json=as_json)


def _make_help_handler(subparser: argparse.ArgumentParser) -> CommandHandler:
    def _show_help(_args: argparse.Namespace) -> int:
        subparser.print_help()
        return 0

    return _show_help


def build_parser() -> argparse.ArgumentParser:
    """Build the root CLI argument parser for ``ets2v2``."""
    parser = argparse.ArgumentParser(
        prog="ets2v2",
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
        "--out",
        type=Path,
        required=True,
        help="Output JSON file path for the generated realism snapshot.",
    )
    registry_snapshot.set_defaults(handler=_handle_registry_snapshot)

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
        help="Generate clean-room 276x162 EXIF/ICC-stripped Summer and Winter JPEG icons.",
    )
    package_icons.add_argument(
        "--out-dir",
        type=Path,
        default=Path("assets/icons"),
        help="Output directory for summer.jpg and winter.jpg (default: assets/icons).",
    )
    package_icons.set_defaults(handler=_handle_package_icons)

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
        "--json",
        action="store_true",
        help="Print validation report as JSON.",
    )
    validate_local.set_defaults(handler=_handle_validate_local)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the ``ets2v2`` CLI and return a POSIX exit status code."""
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
