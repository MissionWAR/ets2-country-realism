"""Clean-room ETS2 1.62 SII/SUI synthesis, icons, metadata, and dual Core packager."""

from __future__ import annotations

from ets2v2.package.builder import (
    LOCAL_ZIP_FILENAMES,
    ZIP_COMPRESS_LEVEL,
    ZIP_FILE_EXTERNAL_ATTR,
    ZIP_FIXED_TIMESTAMP,
    ZIP_UNIX_SYSTEM,
    BuiltEditionPaths,
    build_core_edition,
    build_core_editions,
)
from ets2v2.package.icons import (
    ICON_SIZE,
    generate_all_icons,
    render_edition_icon_bytes,
)
from ets2v2.package.metadata import (
    DEFAULT_AUTHOR,
    LOCAL_DISPLAY_NAMES,
    WORKSHOP_CATEGORIES,
    render_description_txt,
    render_manifest_sii,
    render_versions_sii,
)
from ets2v2.package.synthesize import (
    format_sii_string,
    synthesize_country_sui,
    synthesize_speed_limits_sii,
)

__all__ = [
    "DEFAULT_AUTHOR",
    "ICON_SIZE",
    "LOCAL_DISPLAY_NAMES",
    "LOCAL_ZIP_FILENAMES",
    "WORKSHOP_CATEGORIES",
    "ZIP_COMPRESS_LEVEL",
    "ZIP_FILE_EXTERNAL_ATTR",
    "ZIP_FIXED_TIMESTAMP",
    "ZIP_UNIX_SYSTEM",
    "BuiltEditionPaths",
    "build_core_edition",
    "build_core_editions",
    "format_sii_string",
    "generate_all_icons",
    "render_description_txt",
    "render_edition_icon_bytes",
    "render_manifest_sii",
    "render_versions_sii",
    "synthesize_country_sui",
    "synthesize_speed_limits_sii",
]
