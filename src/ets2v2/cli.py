"""Command-line entrypoint for ets2v2."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import cast

from ets2v2 import __version__

CommandHandler = Callable[[argparse.Namespace], int]


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
    parser.add_subparsers(dest="command", metavar="COMMAND")
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
