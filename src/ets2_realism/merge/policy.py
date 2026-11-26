"""Schema-enforced FieldOwnershipPolicy merge engine for local map combos (D-14, D-15)."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2_realism.registry.models import RoadVehicleClass
from ets2_realism.registry.snapshot import RealismSnapshotCountry
from ets2_realism.registry.timezone import resolve_ets2_timezone
from ets2_realism.sii.country import CountryDataModel, CountryDataPatch, patch_country_data
from ets2_realism.sii.document import SiiDocument
from ets2_realism.sii.hygiene import serialize_sii_text, validate_sii_hygiene
from ets2_realism.sii.speed_limits import LaneSpeedRule, parse_speed_limits, patch_speed_limits

_ROAD_VEHICLE_CLASSES: Final[tuple[RoadVehicleClass, ...]] = ("car", "truck", "bus")

TimeZoneAction = Literal[
    "patched",
    "patched_iana_override",
    "skipped_multi_tz",
    "skipped_missing_tz",
    "skipped_policy",
]
AxleAction = Literal["merged_max_of_map_and_real", "preserved_map"]
SpeedLimitsStatus = Literal[
    "patched",
    "skipped_imperial_mismatch",
    "skipped_policy",
    "skipped_no_road_blocks",
]


class FieldOwnershipPolicy(BaseModel):
    """Schema-enforced field ownership contract between map mods and realism snapshots."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fuel_price: Literal["always", "skip"] = "always"
    lights_mandatory: Literal["always", "skip"] = "always"
    driving_tired_offence: Literal["always", "skip"] = "always"
    speed_limits_road: Literal["always", "skip"] = "always"
    time_zone: Literal["patch_if_single_tz", "skip"] = "patch_if_single_tz"
    axle_mass_limits: Literal["max_of_map_and_real", "preserve_map"] = "max_of_map_and_real"


class CountryPolicyResult(BaseModel):
    """Structured outcome of applying ``FieldOwnershipPolicy`` to one country definition."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    rendered_bytes: bytes
    has_siinunit_envelope: bool
    fuel_price_patched: bool
    lights_mandatory_patched: bool
    driving_tired_offence_patched: bool
    time_zone_action: TimeZoneAction
    axle_action: AxleAction
    applied_time_zone: int | None = None
    applied_time_zone_name: str | None = None
    merged_axles: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SpeedLimitsPolicyResult(BaseModel):
    """Structured outcome of applying ``FieldOwnershipPolicy`` to ``speed_limits.sii``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    rendered_bytes: bytes | None
    status: SpeedLimitsStatus
    patched_vehicle_classes: list[str] = Field(default_factory=list)
    preserved_custom_lanes: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def _decode_third_party_sii(source: str | bytes) -> str:
    """Decode third-party SII/SUI bytes (UTF-8 first, cp1252 fallback for legacy mod comments)."""
    if isinstance(source, str):
        cleaned = source[1:] if source.startswith("\ufeff") else source
        return cleaned.replace("\r\n", "\n").replace("\r", "\n")
    payload = source[3:] if source.startswith(b"\xef\xbb\xbf") else source
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _clamp_monotonic(values: Sequence[int]) -> list[int]:
    out: list[int] = []
    running = 0
    for val in values:
        running = max(running, val)
        out.append(running)
    return out


def merge_axle_mass_limits(
    map_axles: Sequence[int],
    real_axles: Sequence[int],
) -> list[int]:
    """Merge axle mass limits per D-14: element-wise max with carry-forward + monotonic clamp."""
    if not map_axles:
        return _clamp_monotonic(real_axles)
    if not real_axles:
        return _clamp_monotonic(map_axles)

    target_len = max(len(map_axles), len(real_axles))
    merged: list[int] = []
    running_max = 0
    for idx in range(target_len):
        map_val = map_axles[min(idx, len(map_axles) - 1)]
        real_val = real_axles[min(idx, len(real_axles) - 1)]
        running_max = max(running_max, map_val, real_val)
        merged.append(running_max)
    return merged


def should_patch_timezone(
    map_country: CountryDataModel,
) -> tuple[bool, Literal["patched", "skipped_multi_tz", "skipped_missing_tz"]]:
    """Return ``(True, 'patched')`` strictly on single-TZ definitions omitting secondary TZs."""
    if (
        map_country.secondary_time_zone
        or map_country.secondary_time_zone_area
        or map_country.secondary_time_zone_name
    ):
        return False, "skipped_multi_tz"
    if map_country.time_zone is None:
        return False, "skipped_missing_tz"
    return True, "patched"


def apply_country_policy(
    raw_source: str | bytes,
    map_country: CountryDataModel,
    snapshot_country: RealismSnapshotCountry,
    *,
    policy: FieldOwnershipPolicy | None = None,
    iana_timezone_override: str | None = None,
    ref_date: date | None = None,
    supported_tz_keys: Collection[str] = (),
    rel_path: str = "<country>",
) -> CountryPolicyResult:
    """Surgically patch realism-owned fields on ``country_data``, preserving map-owned fields."""
    effective_policy = policy if policy is not None else FieldOwnershipPolicy()
    decoded_source = _decode_third_party_sii(raw_source)
    has_siinunit_envelope = SiiDocument.parse(decoded_source).has_siinunit

    tz_offset: int | None = None
    tz_name: str | None = None
    tz_action: TimeZoneAction
    if effective_policy.time_zone == "skip":
        tz_action = "skipped_policy"
    else:
        patch_tz, base_tz_action = should_patch_timezone(map_country)
        if not patch_tz:
            tz_action = base_tz_action
        elif iana_timezone_override is not None:
            if ref_date is None:
                raise ValueError(
                    f"ref_date is required when iana_timezone_override is set for {rel_path}"
                )
            resolved_tz = resolve_ets2_timezone(
                iana_timezone_override,
                ref_date,
                supported_tz_keys,
            )
            tz_offset = resolved_tz.offset_minutes
            tz_name = resolved_tz.ets2_time_zone_name
            tz_action = "patched_iana_override"
        else:
            tz_offset = snapshot_country.time_zone
            tz_name = snapshot_country.time_zone_name
            tz_action = "patched"

    axle_action: AxleAction
    if effective_policy.axle_mass_limits == "preserve_map":
        merged_axles = list(map_country.mass_limit_per_axle_count)
        patch_axles: list[int] | None = None
        axle_action = "preserved_map"
    else:
        merged_axles = merge_axle_mass_limits(
            map_country.mass_limit_per_axle_count,
            snapshot_country.mass_limit_per_axle_count,
        )
        patch_axles = merged_axles
        axle_action = "merged_max_of_map_and_real"

    fuel_patched = effective_policy.fuel_price == "always"
    lights_patched = effective_policy.lights_mandatory == "always"
    tired_patched = effective_policy.driving_tired_offence == "always"

    patch = CountryDataPatch(
        fuel_price=snapshot_country.fuel.eur_per_liter if fuel_patched else None,
        lights_mandatory=snapshot_country.lights_mandatory if lights_patched else None,
        driving_tired_offence=snapshot_country.driving_tired_offence if tired_patched else None,
        time_zone=tz_offset,
        time_zone_name=tz_name,
        mass_limit_per_axle_count=patch_axles,
    )
    rendered = patch_country_data(decoded_source, patch)
    out_bytes = serialize_sii_text(rendered)
    hygiene = validate_sii_hygiene(out_bytes, require_siinunit=has_siinunit_envelope)
    if hygiene:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in hygiene)
        raise ValueError(f"Patched country SII hygiene failure for {rel_path}: {summary}")

    return CountryPolicyResult(
        rendered_bytes=out_bytes,
        has_siinunit_envelope=has_siinunit_envelope,
        fuel_price_patched=fuel_patched,
        lights_mandatory_patched=lights_patched,
        driving_tired_offence_patched=tired_patched,
        time_zone_action=tz_action,
        axle_action=axle_action,
        applied_time_zone=tz_offset,
        applied_time_zone_name=tz_name,
        merged_axles=merged_axles,
    )


def apply_speed_limits_policy(
    raw_source: str | bytes,
    map_country: CountryDataModel,
    snapshot_country: RealismSnapshotCountry,
    *,
    policy: FieldOwnershipPolicy | None = None,
    rel_path: str = "<speed_limits.sii>",
) -> SpeedLimitsPolicyResult:
    """Patch canonical lanes in car/truck/bus while preserving custom lanes & train/tram (D-15)."""
    effective_policy = policy if policy is not None else FieldOwnershipPolicy()
    if effective_policy.speed_limits_road == "skip":
        return SpeedLimitsPolicyResult(rendered_bytes=None, status="skipped_policy")

    map_is_imperial = map_country.imperial_units is True
    if map_is_imperial != snapshot_country.imperial_units:
        warning = (
            f"imperial_units parity mismatch for {rel_path}: map imperial_units={map_is_imperial}, "
            f"snapshot ({snapshot_country.iso2}) imperial_units={snapshot_country.imperial_units}; "
            "skipping speed_limits.sii"
        )
        return SpeedLimitsPolicyResult(
            rendered_bytes=None,
            status="skipped_imperial_mismatch",
            warnings=[warning],
        )

    decoded_source = _decode_third_party_sii(raw_source)
    has_siinunit = SiiDocument.parse(decoded_source).has_siinunit
    parsed = parse_speed_limits(decoded_source)
    updates: dict[str, list[LaneSpeedRule]] = {}
    preserved_custom_lanes: dict[str, list[str]] = {}

    for vclass in _ROAD_VEHICLE_CLASSES:
        block = parsed.get_block(vclass)
        if block is None or not block.lanes:
            continue
        overrides_by_lane = {
            lane.lane_speed_class: lane for lane in snapshot_country.speed_limits[vclass]
        }
        new_lanes: list[LaneSpeedRule] = []
        custom_for_class: list[str] = []
        for existing_lane in block.lanes:
            override = overrides_by_lane.get(existing_lane.lane_speed_class)
            if override is None:
                # Preserve map-added custom lane classes verbatim in their exact slot
                new_lanes.append(existing_lane)
                custom_for_class.append(existing_lane.lane_speed_class)
            else:
                new_lanes.append(
                    LaneSpeedRule(
                        lane_speed_class=existing_lane.lane_speed_class,
                        limit=override.limit,
                        urban_limit=override.urban_limit,
                        max_limit=(
                            override.max_limit if existing_lane.max_limit is not None else None
                        ),
                        uncommon=existing_lane.uncommon,
                    )
                )
        updates[vclass] = new_lanes
        if custom_for_class:
            preserved_custom_lanes[vclass] = custom_for_class

    if not updates:
        return SpeedLimitsPolicyResult(rendered_bytes=None, status="skipped_no_road_blocks")

    rendered = patch_speed_limits(decoded_source, updates)
    out_bytes = serialize_sii_text(rendered)
    hygiene = validate_sii_hygiene(out_bytes, require_siinunit=has_siinunit)
    if hygiene:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in hygiene)
        raise ValueError(f"Patched speed_limits hygiene failure for {rel_path}: {summary}")

    return SpeedLimitsPolicyResult(
        rendered_bytes=out_bytes,
        status="patched",
        patched_vehicle_classes=sorted(updates.keys()),
        preserved_custom_lanes=preserved_custom_lanes,
    )


__all__ = [
    "AxleAction",
    "CountryPolicyResult",
    "FieldOwnershipPolicy",
    "SpeedLimitsPolicyResult",
    "SpeedLimitsStatus",
    "TimeZoneAction",
    "apply_country_policy",
    "apply_speed_limits_policy",
    "merge_axle_mass_limits",
    "should_patch_timezone",
]
