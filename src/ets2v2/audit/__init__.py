"""Strictly quarantined Layer 7C internal OSM speed-limit drift audit & taint subpackage."""

from __future__ import annotations

from ets2v2.audit.models import (
    LaneSpeedClass,
    OsmSpeedAuditReport,
    OverpassSpotCheck,
    OverpassTagCount,
    SpeedAuditAllowlist,
    SpeedAuditAllowlistEntry,
    SpeedDriftFinding,
    SpeedField,
    TaginfoDistribution,
    TaginfoValueEntry,
    TaintScanReport,
    TaintViolation,
    VehicleSpeedClass,
)
from ets2v2.audit.taint import (
    FORBIDDEN_LICENSE_TAINT_PATTERNS,
    scan_package_for_taint,
    scan_repo_and_artifacts_for_taint,
)

__all__ = [
    "FORBIDDEN_LICENSE_TAINT_PATTERNS",
    "LaneSpeedClass",
    "OsmSpeedAuditReport",
    "OverpassSpotCheck",
    "OverpassTagCount",
    "SpeedAuditAllowlist",
    "SpeedAuditAllowlistEntry",
    "SpeedDriftFinding",
    "SpeedField",
    "TaginfoDistribution",
    "TaginfoValueEntry",
    "TaintScanReport",
    "TaintViolation",
    "VehicleSpeedClass",
    "scan_package_for_taint",
    "scan_repo_and_artifacts_for_taint",
]
