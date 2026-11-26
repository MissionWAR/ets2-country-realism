"""Unit tests for version-agnostic ProMods EU/ME/MA/TGS def + assets archive discovery."""

from __future__ import annotations

import pathlib

import pytest

from ets2_realism.merge.promods_discovery import (
    ProModsPackSet,
    ProModsPackSpec,
    discover_promods_packs,
    ordered_pack_paths,
    resolve_mod_dir,
)


def _touch(directory: pathlib.Path, name: str) -> pathlib.Path:
    path = directory / name
    path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    return path


def test_resolve_mod_dir_prefers_explicit_then_env(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = tmp_path / "explicit_mod"
    env_dir = tmp_path / "env_mod"
    monkeypatch.setenv("ETS2_MOD_DIR", str(env_dir))

    assert resolve_mod_dir(explicit) == explicit
    assert resolve_mod_dir() == env_dir

    monkeypatch.delenv("ETS2_MOD_DIR", raising=False)
    resolved_default = resolve_mod_dir()
    assert resolved_default.name.lower() == "mod"


def test_discover_promods_version_agnostic_selection_and_st_preference(
    tmp_path: pathlib.Path,
) -> None:
    # Older v284, equal-version -st- variant, and canonical v285 EU def
    _touch(tmp_path, "promods-def-v284.scs")
    _touch(tmp_path, "promods-def-st-v285.scs")
    eu_def_285 = _touch(tmp_path, "promods-eu-def-v285.scs")
    eu_assets_285 = _touch(tmp_path, "promods-eu-assets-v285.scs")
    tgs_def_171 = _touch(tmp_path, "promods-tgs-defmap-v171.scs")
    tgs_assets_171 = _touch(tmp_path, "promods-tgs-assets-v171.scs")
    me_def_285 = _touch(tmp_path, "promods-me-defmap-v285.scs")
    me_assets_285 = _touch(tmp_path, "promods-me-assets-v285.scs")
    ma_def_105 = _touch(tmp_path, "promods-ma-defmap-v105.scs")
    ma_assets_105 = _touch(tmp_path, "promods-ma-assets-v105.scs")

    pack_set = discover_promods_packs(tmp_path, require_all_packs=True)
    assert isinstance(pack_set, ProModsPackSet)
    assert isinstance(pack_set.eu_def, ProModsPackSpec)
    assert pack_set.eu_def.path == eu_def_285
    assert pack_set.eu_def.version == (2, 85)
    assert pack_set.eu_def.is_special_transport is False
    assert pack_set.eu_assets is not None and pack_set.eu_assets.path == eu_assets_285
    assert pack_set.tgs_def is not None and pack_set.tgs_def.path == tgs_def_171
    assert pack_set.tgs_assets is not None and pack_set.tgs_assets.path == tgs_assets_171
    assert pack_set.me_def is not None and pack_set.me_def.path == me_def_285
    assert pack_set.me_assets is not None and pack_set.me_assets.path == me_assets_285
    assert pack_set.ma_def is not None and pack_set.ma_def.path == ma_def_105
    assert pack_set.ma_assets is not None and pack_set.ma_assets.path == ma_assets_105

    # Official bottom-to-top stacking priority: EU < TGS < ME < MA (assets before defmap)
    ordered = ordered_pack_paths(pack_set)
    assert [path for _name, path in ordered] == [
        eu_assets_285,
        eu_def_285,
        tgs_assets_171,
        tgs_def_171,
        me_assets_285,
        me_def_285,
        ma_assets_105,
        ma_def_105,
    ]
    priorities = [spec.priority for spec in pack_set.ordered_packs()]
    assert priorities == sorted(priorities)
    assert len(set(priorities)) == len(priorities)


def test_discover_prefers_higher_version_and_handles_dotted_and_st_fallback(
    tmp_path: pathlib.Path,
) -> None:
    _touch(tmp_path, "promods-def-v285.scs")
    eu_v286 = _touch(tmp_path, "promods-def-v286.scs")
    _touch(tmp_path, "promods-assets-v285.zip")
    assets_v286 = _touch(tmp_path, "promods-assets-v286.scs")

    pack_set = discover_promods_packs(tmp_path)
    assert pack_set.eu_def is not None and pack_set.eu_def.path == eu_v286
    assert pack_set.eu_assets is not None and pack_set.eu_assets.path == assets_v286

    # Only -st- present still discovers cleanly
    st_dir = tmp_path / "st_only"
    st_dir.mkdir()
    st_file = _touch(st_dir, "promods-def-st-v285.scs")
    st_set = discover_promods_packs(st_dir)
    assert st_set.eu_def is not None
    assert st_set.eu_def.path == st_file
    assert st_set.eu_def.is_special_transport is True


def test_discover_modular_subset_vs_require_all_packs_and_missing_eu_def(
    tmp_path: pathlib.Path,
) -> None:
    # Missing EU def raises FileNotFoundError by default
    with pytest.raises(FileNotFoundError, match="ProMods EU def"):
        discover_promods_packs(tmp_path)

    # require_eu_def=False allows probing safely
    empty_set = discover_promods_packs(tmp_path, require_eu_def=False)
    assert empty_set.eu_def is None
    assert ordered_pack_paths(empty_set) == []

    # EU-only subset succeeds when require_all_packs=False
    eu_def = _touch(tmp_path, "promods-def-v285.scs")
    eu_only = discover_promods_packs(tmp_path, require_all_packs=False)
    assert eu_only.eu_def is not None and eu_only.eu_def.path == eu_def
    assert eu_only.me_def is None
    assert eu_only.tgs_def is None
    assert eu_only.ma_def is None

    # Fails fast when require_all_packs=True and ME/MA/TGS or assets missing
    with pytest.raises(FileNotFoundError, match="require-all-packs"):
        discover_promods_packs(tmp_path, require_all_packs=True)


def test_discover_honors_explicit_per_pack_overrides(tmp_path: pathlib.Path) -> None:
    _touch(tmp_path, "promods-eu-def-v285.scs")
    custom_eu = _touch(tmp_path, "custom_eu_override.scs")
    custom_me_assets = _touch(tmp_path, "custom_me_assets.zip")

    pack_set = discover_promods_packs(
        tmp_path,
        eu_def=custom_eu,
        me_assets=custom_me_assets,
    )
    assert pack_set.eu_def is not None
    assert pack_set.eu_def.path == custom_eu
    assert pack_set.eu_def.is_explicit_override is True
    assert pack_set.me_assets is not None
    assert pack_set.me_assets.path == custom_me_assets
    assert pack_set.me_assets.is_explicit_override is True

    with pytest.raises(FileNotFoundError, match="override"):
        discover_promods_packs(tmp_path, tgs_def=tmp_path / "does_not_exist.scs")


def test_lo01_compact_vs_dotted_version_comparison_and_st_underscore_split(
    tmp_path: pathlib.Path,
) -> None:
    """LO-01 regression: compact v284 normalizes to (2, 84) < dotted v2.85 (2, 85) < v286."""
    mixed_a = tmp_path / "mixed_a"
    mixed_a.mkdir()
    _touch(mixed_a, "promods-def-v284.scs")
    dotted_285 = _touch(mixed_a, "promods-eu-def-v2.85.scs")
    pack_a = discover_promods_packs(mixed_a)
    assert pack_a.eu_def is not None
    assert pack_a.eu_def.path == dotted_285
    assert pack_a.eu_def.version == (2, 85)

    mixed_b = tmp_path / "mixed_b"
    mixed_b.mkdir()
    _touch(mixed_b, "promods-eu-def-v2.85.scs")
    compact_286 = _touch(mixed_b, "promods-eu-def-v286.scs")
    pack_b = discover_promods_packs(mixed_b)
    assert pack_b.eu_def is not None
    assert pack_b.eu_def.path == compact_286
    assert pack_b.eu_def.version == (2, 86)

    st_dir = tmp_path / "st_underscore"
    st_dir.mkdir()
    st_pack = _touch(st_dir, "promods-def-foo_st-v285.scs")
    pack_st = discover_promods_packs(st_dir)
    assert pack_st.eu_def is not None
    assert pack_st.eu_def.path == st_pack
    assert pack_st.eu_def.is_special_transport is True
