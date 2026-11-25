"""Phase 4 offline Layer 9A ProMods Companion Builder and local map-combo composer."""

from __future__ import annotations

from ets2v2.merge.promods_builder import (
    PROMODS_LOCAL_ZIP_FILENAMES,
    ProModsBuildReport,
    assert_out_dir_not_tracked,
    build_promods_edition,
    build_promods_editions,
)
from ets2v2.merge.promods_discovery import (
    ProModsPackEntry,
    ProModsPackId,
    ProModsPackRole,
    ProModsPackSet,
    ProModsPackSpec,
    discover_promods_packs,
    ordered_pack_paths,
    resolve_mod_dir,
)
from ets2v2.merge.promods_fuel import (
    PM_EU_PREFIX_TO_ISO2,
    PM_FUEL_KEY_RE,
    PM_FUEL_MODULES,
    PM_ME_PREFIX_TO_ISO2,
    PM_MODULE_PREFIX_MAPS,
    PM_PREFIX_TAX_MULTIPLIERS,
    PM_TGS_PREFIX_TO_ISO2,
    CompiledProModsFuel,
    PmFormatRegime,
    ProModsFuelModuleName,
    ProModsFuelModuleResult,
    classify_pm_format_regime,
    compile_promods_fuel_locales,
    compile_promods_fuel_module,
    format_pm_fuel_value,
)

__all__ = [
    "PM_EU_PREFIX_TO_ISO2",
    "PM_FUEL_KEY_RE",
    "PM_FUEL_MODULES",
    "PM_ME_PREFIX_TO_ISO2",
    "PM_MODULE_PREFIX_MAPS",
    "PM_PREFIX_TAX_MULTIPLIERS",
    "PM_TGS_PREFIX_TO_ISO2",
    "PROMODS_LOCAL_ZIP_FILENAMES",
    "CompiledProModsFuel",
    "PmFormatRegime",
    "ProModsBuildReport",
    "ProModsFuelModuleName",
    "ProModsFuelModuleResult",
    "ProModsPackEntry",
    "ProModsPackId",
    "ProModsPackRole",
    "ProModsPackSet",
    "ProModsPackSpec",
    "assert_out_dir_not_tracked",
    "build_promods_edition",
    "build_promods_editions",
    "classify_pm_format_regime",
    "compile_promods_fuel_locales",
    "compile_promods_fuel_module",
    "discover_promods_packs",
    "format_pm_fuel_value",
    "ordered_pack_paths",
    "resolve_mod_dir",
]
