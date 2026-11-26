"""Strict frozen Pydantic v2 DTOs for the isolated Layer 7C audit subpackage (GLB-04)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VehicleSpeedClass = Literal["car", "truck", "bus"]
LaneSpeedClass = Literal["local_road", "expressway", "motorway"]
SpeedField = Literal["limit", "urban_limit", "max_limit"]


class SpeedAuditAllowlistEntry(BaseModel):
    """Clean-room statutory deviation entry in data/laws/speed_audit_allowlist.json (D-15)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    vehicle_class: VehicleSpeedClass
    lane_speed_class: LaneSpeedClass
    field: SpeedField
    statutory_rationale: str = Field(min_length=1)
    verified_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("verified_date")
    @classmethod
    def _validate_iso_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    def match_key(self) -> tuple[str, VehicleSpeedClass, LaneSpeedClass, SpeedField]:
        return (self.iso2, self.vehicle_class, self.lane_speed_class, self.field)


class SpeedAuditAllowlist(BaseModel):
    """Top-level clean-room speed_audit_allowlist.json contract (D-15)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    entries: list[SpeedAuditAllowlistEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_keys(self) -> SpeedAuditAllowlist:
        seen: set[tuple[str, VehicleSpeedClass, LaneSpeedClass, SpeedField]] = set()
        for entry in self.entries:
            key = entry.match_key()
            if key in seen:
                raise ValueError(f"Duplicate speed_audit_allowlist entry for {key!r}")
            seen.add(key)
        return self


class SpeedDriftFinding(BaseModel):
    """Single speed-limit comparison discrepancy between data/laws/ and OSM default rules."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    country_name: str = Field(min_length=1)
    vehicle_class: VehicleSpeedClass
    lane_speed_class: LaneSpeedClass
    field: SpeedField
    speed_unit: Literal["kmh", "mph"]
    law_value: int = Field(ge=0)
    osm_value: int = Field(ge=0)
    osm_raw: str = Field(min_length=1)
    acknowledged: bool = False
    statutory_rationale: str | None = None
    verified_date: str | None = None


class OverpassTagCount(BaseModel):
    """Modal tag value frequency observed in an Overpass highway sample."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    value: str = Field(min_length=1)
    count: int = Field(ge=1)


class OverpassSpotCheck(BaseModel):
    """Opt-in Overpass highway maxspeed tag spot-check summary for one ISO-2 country (D-13)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    ok: bool
    ways_sampled: int = Field(default=0, ge=0)
    top_maxspeed_by_highway: dict[str, list[OverpassTagCount]] = Field(default_factory=dict)
    top_maxspeed_hgv_by_highway: dict[str, list[OverpassTagCount]] = Field(default_factory=dict)
    top_maxspeed_bus_by_highway: dict[str, list[OverpassTagCount]] = Field(default_factory=dict)
    error: str | None = None


class TaginfoValueEntry(BaseModel):
    """Single Taginfo v4 key/values frequency row."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    value: str = Field(min_length=1)
    count: int = Field(ge=0)
    fraction: float = Field(ge=0.0, allow_inf_nan=False)


class TaginfoDistribution(BaseModel):
    """Opt-in Taginfo v4 global tag value distribution for one maxspeed key (D-13)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    ok: bool
    values: list[TaginfoValueEntry] = Field(default_factory=list)
    error: str | None = None


class OsmSpeedAuditReport(BaseModel):
    """Deterministic machine-readable output of ``ets2v2 audit osm-speeds`` (D-13, D-15)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    generated_at: str = Field(min_length=1)
    rules_source: str = Field(min_length=1)
    allowlist_path: str | None = None
    countries_checked: int = Field(ge=0)
    countries_matched_in_osm: int = Field(ge=0)
    countries_missing_in_osm: list[str] = Field(default_factory=list)
    unacknowledged_drift_count: int = Field(ge=0)
    acknowledged_difference_count: int = Field(ge=0)
    unacknowledged_drifts: list[SpeedDriftFinding] = Field(default_factory=list)
    acknowledged_differences: list[SpeedDriftFinding] = Field(default_factory=list)
    overpass_spot_checks: list[OverpassSpotCheck] = Field(default_factory=list)
    taginfo_distributions: list[TaginfoDistribution] = Field(default_factory=list)


class TaintViolation(BaseModel):
    """Single forbidden non-CC-BY-4.0 license/source marker detection (D-16)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    marker: str = Field(min_length=1)
    line_number: int = Field(ge=1)
    excerpt: str = Field(min_length=1)


class TaintScanReport(BaseModel):
    """Deterministic output of ``ets2v2 audit taint`` and package taint scans (D-16)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ok: bool
    files_scanned: int = Field(ge=0)
    packages_scanned: int = Field(default=0, ge=0)
    snapshots_scanned: int = Field(default=0, ge=0)
    violation_count: int = Field(ge=0)
    violations: list[TaintViolation] = Field(default_factory=list)
