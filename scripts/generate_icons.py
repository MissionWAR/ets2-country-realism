"""Thin reproducible wrapper to regenerate checked-in clean-room Workshop icons."""

from __future__ import annotations

from pathlib import Path

from ets2v2.package.icons import generate_all_icons

if __name__ == "__main__":
    generate_all_icons(Path("assets/icons"))
