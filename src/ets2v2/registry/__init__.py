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

__all__ = [
    "CountryLawRecord",
    "CountryMappingEntry",
    "CountryMappingRegistry",
    "LaneClass",
    "LaneSpeedOverride",
    "LawRegistryBundle",
    "RoadVehicleClass",
    "Season",
    "SeasonalRuleSet",
    "SpeedUnit",
    "load_law_registry",
    "serialize_registry_json_bytes",
    "validate_law_registry",
]
