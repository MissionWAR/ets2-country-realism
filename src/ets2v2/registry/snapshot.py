"""Locked schema_version=1 realism-snapshot models and deterministic JSON emitter."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.baseline.models import CountriesBaseline, LocalesBaseline
from ets2v2.registry.loader import serialize_registry_json_bytes
from ets2v2.registry.models import (
    LaneSpeedOverride,
    LawRegistryBundle,
    RoadVehicleClass,
    Season,
)
from ets2v2.registry.timezone import (
    DEFAULT_ANCHOR_YEAR,
    resolve_ets2_timezone,
    resolve_season_anchor_date,
)

_ROAD_VEHICLE_CLASSES: Final[tuple[RoadVehicleClass, ...]] = ("car", "truck", "bus")
_BASELINE_FUEL_SOURCE: Final[str] = "baseline_1.62"


class RealismSnapshotFuel(BaseModel):
    """Per-country fuel snapshot block (extensible in Phase 3 for live local grades)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    currency: str = Field(pattern=r"^[A-Z]{3}$")
    eur_per_liter: float = Field(ge=0.0, allow_inf_nan=False)
    local_prices: dict[str, float] = Field(default_factory=dict)
    source: str = Field(min_length=1)


class RealismSnapshotCountry(BaseModel):
    """Resolved per-country seasonal realism parameters inside a v1 snapshot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    iso3: str = Field(pattern=r"^[a-z]{3}$")
    ets2_slug: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    iana_timezone: str = Field(min_length=1)
    time_zone: int
    time_zone_name: str = Field(min_length=1)
    observes_dst: bool
    lights_mandatory: bool
    driving_tired_offence: bool
    imperial_units: bool
    mass_limit_per_axle_count: list[int] = Field(min_length=3, max_length=12)
    speed_limits: dict[RoadVehicleClass, list[LaneSpeedOverride]]
    fuel: RealismSnapshotFuel


class RealismSnapshot(BaseModel):
    """Locked D-11 ``schema_version: 1`` seasonal realism snapshot contract."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    edition: Season
    anchor_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    baseline_game_version: str = Field(min_length=1)
    countries: dict[str, RealismSnapshotCountry]


def build_realism_snapshot(
    registry: LawRegistryBundle,
    baseline_countries: CountriesBaseline,
    baseline_locales: LocalesBaseline,
    edition: Season,
    *,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    override_date: date | None = None,
    baseline_game_version: str = "1.62.3.3",
) -> RealismSnapshot:
    """Resolve all registry countries for ``edition`` into a deterministic v1 snapshot."""
    ref_date = resolve_season_anchor_date(
        edition,
        anchor_year=anchor_year,
        override_date=override_date,
    )
    baseline_by_slug = {country.slug: country for country in baseline_countries.countries}

    countries: dict[str, RealismSnapshotCountry] = {}
    for iso2 in sorted(registry.laws_by_iso2):
        law = registry.laws_by_iso2[iso2]
        bl_country = baseline_by_slug.get(law.ets2_slug)
        if bl_country is None:
            raise ValueError(f"Missing baseline country entry for {iso2} ({law.ets2_slug!r})")

        if bl_country.fuel_price is None:
            raise ValueError(f"Missing baseline fuel_price for {iso2} ({law.ets2_slug!r})")

        resolved_tz = resolve_ets2_timezone(
            law.iana_timezone,
            ref_date,
            baseline_locales.tz_keys,
        )
        seasonal_rules = law.summer if edition == "summer" else law.winter
        speed_limits: dict[RoadVehicleClass, list[LaneSpeedOverride]] = {
            vehicle_class: list(seasonal_rules.speed_limits[vehicle_class])
            for vehicle_class in _ROAD_VEHICLE_CLASSES
        }

        countries[iso2] = RealismSnapshotCountry(
            iso2=law.iso2,
            iso3=law.iso3,
            ets2_slug=law.ets2_slug,
            iana_timezone=law.iana_timezone,
            time_zone=resolved_tz.offset_minutes,
            time_zone_name=resolved_tz.ets2_time_zone_name,
            observes_dst=resolved_tz.observes_dst,
            lights_mandatory=seasonal_rules.lights_mandatory,
            driving_tired_offence=law.driving_tired_offence,
            imperial_units=bl_country.imperial_units is True,
            mass_limit_per_axle_count=list(law.mass_limit_per_axle_count),
            speed_limits=speed_limits,
            fuel=RealismSnapshotFuel(
                currency=law.currency,
                eur_per_liter=bl_country.fuel_price,
                local_prices={},
                source=_BASELINE_FUEL_SOURCE,
            ),
        )

    return RealismSnapshot(
        schema_version=1,
        edition=edition,
        anchor_date=ref_date.isoformat(),
        baseline_game_version=baseline_game_version,
        countries=countries,
    )


def serialize_snapshot_bytes(snapshot: RealismSnapshot) -> bytes:
    """Serialize a v1 realism snapshot to canonical UTF-8 no-BOM LF sorted JSON bytes."""
    return serialize_registry_json_bytes(snapshot)


def write_realism_snapshot(snapshot: RealismSnapshot, path: Path) -> bytes:
    """Write a canonical v1 realism snapshot JSON file to ``path`` and return its bytes."""
    raw = serialize_snapshot_bytes(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw
