"""Structural SII/SUI lexer, hygiene validator, surgical editor, and ETS2 adapters."""

from __future__ import annotations

from ets2_realism.sii.country import (
    CountryDataModel,
    CountryDataPatch,
    parse_country_data,
    parse_country_includes,
    patch_country_data,
)
from ets2_realism.sii.document import (
    SiiAttributeSpan,
    SiiDocument,
    SiiIncludeSpan,
    SiiUnitBlock,
)
from ets2_realism.sii.hygiene import (
    SiiDiagnostic,
    SiiEncodingError,
    normalize_sii_bytes,
    serialize_sii_text,
    validate_sii_hygiene,
)
from ets2_realism.sii.lexer import SiiSpan, parse_sii_float, scan_sii_structure
from ets2_realism.sii.localization import LocalizationEntry, parse_localization_db
from ets2_realism.sii.sign_board import (
    SignBoardTemplate,
    SignTemplateTextSlot,
    parse_sign_board,
)
from ets2_realism.sii.speed_limits import (
    LaneSpeedRule,
    SpeedLimitsFile,
    VehicleSpeedLimitBlock,
    parse_speed_limits,
    patch_speed_limits,
)

__all__ = [
    "CountryDataModel",
    "CountryDataPatch",
    "LaneSpeedRule",
    "LocalizationEntry",
    "SignBoardTemplate",
    "SignTemplateTextSlot",
    "SiiAttributeSpan",
    "SiiDiagnostic",
    "SiiDocument",
    "SiiEncodingError",
    "SiiIncludeSpan",
    "SiiSpan",
    "SiiUnitBlock",
    "SpeedLimitsFile",
    "VehicleSpeedLimitBlock",
    "normalize_sii_bytes",
    "parse_country_data",
    "parse_country_includes",
    "parse_localization_db",
    "parse_sign_board",
    "parse_sii_float",
    "parse_speed_limits",
    "patch_country_data",
    "patch_speed_limits",
    "scan_sii_structure",
    "serialize_sii_text",
    "validate_sii_hygiene",
]
