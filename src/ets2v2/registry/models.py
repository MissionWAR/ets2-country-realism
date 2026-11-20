"""Strict frozen Pydantic v2 schemas for canonical country laws and ETS2 mappings."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Season = Literal["summer", "winter"]
RoadVehicleClass = Literal["car", "truck", "bus"]
SpeedUnit = Literal["kmh", "mph"]
LaneClass = Literal["local_road", "expressway", "motorway", "slow_road"]

_REQUIRED_VEHICLE_CLASSES: Final[frozenset[RoadVehicleClass]] = frozenset({"car", "truck", "bus"})
_CANONICAL_LANE_ORDERS: Final[tuple[tuple[str, ...], ...]] = (
    ("local_road", "expressway", "motorway"),
    ("local_road", "expressway", "motorway", "slow_road"),
)


class LaneSpeedOverride(BaseModel):
    """Statutory lane speed values for one ETS2 road class."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    lane_speed_class: LaneClass
    limit: int = Field(ge=0, le=200)
    urban_limit: int = Field(ge=0, le=200)
    max_limit: int | None = Field(default=None, ge=0, le=200)
    uncommon: bool | None = None


class SeasonalRuleSet(BaseModel):
    """Season-specific statutory rules for daytime lights and road vehicle speed limits."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    lights_mandatory: bool
    speed_limits: dict[RoadVehicleClass, list[LaneSpeedOverride]]

    @model_validator(mode="after")
    def _validate_vehicle_and_lane_structure(self) -> SeasonalRuleSet:
        actual_classes = frozenset(self.speed_limits.keys())
        if actual_classes != _REQUIRED_VEHICLE_CLASSES:
            missing = sorted(_REQUIRED_VEHICLE_CLASSES - actual_classes)
            extra = sorted(actual_classes - _REQUIRED_VEHICLE_CLASSES)
            raise ValueError(
                f"speed_limits must define exact classes car/truck/bus "
                f"(missing={missing}, extra={extra})"
            )

        observed_orders: set[tuple[str, ...]] = set()
        for vehicle_class, lanes in self.speed_limits.items():
            lane_order = tuple(lane.lane_speed_class for lane in lanes)
            if len(set(lane_order)) != len(lane_order):
                raise ValueError(
                    f"Duplicate lane_speed_class entries in {vehicle_class!r}: {lane_order}"
                )
            if lane_order not in _CANONICAL_LANE_ORDERS:
                raise ValueError(
                    f"Non-canonical lane_speed_class order in {vehicle_class!r}: {lane_order}"
                )
            if vehicle_class == "car" and any(lane.max_limit is not None for lane in lanes):
                raise ValueError("car lane overrides must have max_limit=None")
            observed_orders.add(lane_order)

        if len(observed_orders) != 1:
            raise ValueError(
                f"Inconsistent lane_speed_class sets across car/truck/bus: {observed_orders}"
            )
        return self


class CountryLawRecord(BaseModel):
    """Canonical per-country statutory law record under ``data/laws/countries/<iso2>.json``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    iso3: str = Field(pattern=r"^[a-z]{3}$")
    ets2_slug: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    iana_timezone: str = Field(min_length=1)
    speed_unit: SpeedUnit = "kmh"
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    driving_tired_offence: bool = True
    mass_limit_per_axle_count: list[int] = Field(min_length=3, max_length=12)
    summer: SeasonalRuleSet
    winter: SeasonalRuleSet
    statutory_notes: list[str] = Field(default_factory=list)
    sources: list[str] = Field(min_length=1)

    @field_validator("mass_limit_per_axle_count")
    @classmethod
    def _validate_axle_mass_limits(cls, values: list[int]) -> list[int]:
        if any(v < 10_000 or v > 150_000 for v in values):
            raise ValueError("Axle mass limits must be between 10000 and 150000 kg")
        if values != sorted(values):
            raise ValueError("mass_limit_per_axle_count must be non-decreasing")
        return values


class CountryMappingEntry(BaseModel):
    """Canonical mapping entry between an ETS2 country slug and ISO-3166 alpha-2 code."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ets2_slug: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    iso3: str = Field(pattern=r"^[a-z]{3}$")
    country_id: int = Field(ge=1)
    name_english: str = Field(min_length=1)
    vanilla_1_62: bool


class CountryMappingRegistry(BaseModel):
    """Top-level ``data/mappings/ets2_countries.json`` schema."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    baseline_game_version: str = Field(min_length=1)
    countries: list[CountryMappingEntry] = Field(min_length=1)


class LawRegistryBundle(BaseModel):
    """Loaded canonical mapping and per-country statutory law registry."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    mappings: CountryMappingRegistry
    laws_by_iso2: dict[str, CountryLawRecord]
