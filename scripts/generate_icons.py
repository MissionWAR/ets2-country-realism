"""Thin reproducible wrapper to regenerate checked-in clean-room Workshop icons."""

from __future__ import annotations

from pathlib import Path

from ets2_realism.package.icons import generate_all_icons, generate_promods_icons

if __name__ == "__main__":
    icons_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
    generate_all_icons(icons_dir)
    generate_promods_icons(icons_dir)
