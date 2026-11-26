"""Offline SCS Workshop Validator and ETS2 1.62 realism invariant facade."""

from __future__ import annotations

from ets2_realism.validate.invariants import (
    FORBIDDEN_LICENSE_TAINT_PATTERNS,
    check_license_taint_bytes,
    validate_combo_invariants,
    validate_core_realism_invariants,
    validate_promods_locale_modules_consistency,
    validate_promods_realism_invariants,
    validate_totem_invariants,
)
from ets2_realism.validate.models import (
    PackageProfile,
    ValidationCollector,
    ValidationIssue,
    ValidationMode,
    ValidationReport,
    ValidationSeverity,
)
from ets2_realism.validate.workshop import (
    ALLOWED_MANIFEST_ATTRS,
    ALLOWED_SCS_ASSET_EXTENSIONS,
    FORBIDDEN_EXTENSIONS,
    FORBIDDEN_TOTEM_EXTENSIONS,
    MAX_DESCRIPTION_BYTES,
    MAX_ICON_BYTES,
    MAX_ICON_PIXELS,
    REQUIRED_ICON_SIZE,
    VALID_SCS_CATEGORIES,
    validate_local_zip,
    validate_workshop_package,
)

__all__ = [
    "ALLOWED_MANIFEST_ATTRS",
    "ALLOWED_SCS_ASSET_EXTENSIONS",
    "FORBIDDEN_EXTENSIONS",
    "FORBIDDEN_LICENSE_TAINT_PATTERNS",
    "FORBIDDEN_TOTEM_EXTENSIONS",
    "MAX_DESCRIPTION_BYTES",
    "MAX_ICON_BYTES",
    "MAX_ICON_PIXELS",
    "REQUIRED_ICON_SIZE",
    "VALID_SCS_CATEGORIES",
    "PackageProfile",
    "ValidationCollector",
    "ValidationIssue",
    "ValidationMode",
    "ValidationReport",
    "ValidationSeverity",
    "check_license_taint_bytes",
    "validate_combo_invariants",
    "validate_core_realism_invariants",
    "validate_local_zip",
    "validate_promods_locale_modules_consistency",
    "validate_promods_realism_invariants",
    "validate_totem_invariants",
    "validate_workshop_package",
]
