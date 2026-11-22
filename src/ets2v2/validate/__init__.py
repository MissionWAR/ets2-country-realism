"""Offline SCS Workshop Validator and ETS2 1.62 realism invariant facade."""

from __future__ import annotations

from ets2v2.validate.invariants import (
    validate_core_realism_invariants,
    validate_totem_invariants,
)
from ets2v2.validate.models import (
    ValidationCollector,
    ValidationIssue,
    ValidationMode,
    ValidationReport,
    ValidationSeverity,
)
from ets2v2.validate.workshop import (
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
    "FORBIDDEN_TOTEM_EXTENSIONS",
    "MAX_DESCRIPTION_BYTES",
    "MAX_ICON_BYTES",
    "MAX_ICON_PIXELS",
    "REQUIRED_ICON_SIZE",
    "VALID_SCS_CATEGORIES",
    "ValidationCollector",
    "ValidationIssue",
    "ValidationMode",
    "ValidationReport",
    "ValidationSeverity",
    "validate_core_realism_invariants",
    "validate_local_zip",
    "validate_totem_invariants",
    "validate_workshop_package",
]
