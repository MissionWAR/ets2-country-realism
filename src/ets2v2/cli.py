"""Command-line entrypoint for ets2v2."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from ets2v2 import __version__
from ets2v2.baseline import (
    extract_baseline,
    verify_baseline_bundle,
    write_baseline_bundle,
)
from ets2v2.registry import load_law_registry, validate_law_registry
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
