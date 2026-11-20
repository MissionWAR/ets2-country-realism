"""Canonical per-country realism law registry schemas and validators."""

from __future__ import annotations

from ets2v2.registry.loader import (
    load_law_registry,
    serialize_registry_json_bytes,
    validate_law_registry,
)
from ets2v2.registry.models import (
    CountryLawRecord,
    CountryMappingEntry,
    CountryMappingRegistry,
    LaneClass,
    LaneSpeedOverride,
    LawRegistryBundle,
    RoadVehicleClass,
    Season,
    SeasonalRuleSet,
    SpeedUnit,
)
from ets2v2.registry.snapshot import (
    RealismSnapshot,
    RealismSnapshotCountry,
    RealismSnapshotFuel,
    build_realism_snapshot,
    serialize_snapshot_bytes,
    write_realism_snapshot,
)
from ets2v2.registry.timezone import (
    DEFAULT_ANCHOR_YEAR,
    IANA_NUMERIC_ABBR_OVERRIDES,
    SUMMER_ANCHOR_MONTH_DAY,
    WINTER_ANCHOR_MONTH_DAY,
    ResolvedTimezone,
    assert_leftside_traffic_immutable,
    resolve_ets2_timezone,
    resolve_season_anchor_date,
)

__all__ = [
    "DEFAULT_ANCHOR_YEAR",
    "IANA_NUMERIC_ABBR_OVERRIDES",
    "SUMMER_ANCHOR_MONTH_DAY",
    "WINTER_ANCHOR_MONTH_DAY",
    "CountryLawRecord",
    "CountryMappingEntry",
    "CountryMappingRegistry",
    "LaneClass",
    "LaneSpeedOverride",
    "LawRegistryBundle",
    "RealismSnapshot",
    "RealismSnapshotCountry",
    "RealismSnapshotFuel",
    "ResolvedTimezone",
    "RoadVehicleClass",
    "Season",
    "SeasonalRuleSet",
    "SpeedUnit",
    "assert_leftside_traffic_immutable",
    "build_realism_snapshot",
    "load_law_registry",
    "resolve_ets2_timezone",
    "resolve_season_anchor_date",
    "serialize_registry_json_bytes",
    "serialize_snapshot_bytes",
    "validate_law_registry",
    "write_realism_snapshot",
]
