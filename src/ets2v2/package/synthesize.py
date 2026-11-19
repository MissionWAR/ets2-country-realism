"""Clean-room ETS2 1.62 ``.sui`` and ``speed_limits.sii`` synthesizers."""

from __future__ import annotations

import math
import re
from typing import Final

from ets2v2.baseline.models import BaselineCountry, BaselineSpeedLimit
from ets2v2.registry.models import RoadVehicleClass
from ets2v2.registry.snapshot import RealismSnapshotCountry
from ets2v2.sii.hygiene import serialize_sii_text, validate_sii_hygiene
from ets2v2.sii.speed_limits import LaneSpeedRule

_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+$")
_UNIT_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^\.?[a-z0-9_]+(\.[a-z0-9_]+)*$")
_ROAD_CLASSES: Final[frozenset[RoadVehicleClass]] = frozenset({"car", "truck", "bus"})


def format_sii_string(value: str) -> str:
    """Format a safe SII string literal, rejecting backslashes and NUL bytes."""
    if "\\" in value or "\x00" in value:
        raise ValueError(f"Disallowed backslash or NUL in SII string literal: {value!r}")
    escaped = (
        value.replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    )
    return f'"{escaped}"'


_format_sii_string = format_sii_string


def _format_token(value: str, *, field_name: str) -> str:
    """Validate an unquoted lowercase SII identifier token."""
    if _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"Invalid SII token for {field_name}: {value!r}")
    return value


def _format_unit_name(unit_name: str) -> str:
    """Validate an SII unit name identifier."""
    if _UNIT_NAME_RE.fullmatch(unit_name) is None:
        raise ValueError(f"Invalid SII unit name: {unit_name!r}")
    return unit_name


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_fuel_price(value: float) -> str:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid fuel_price: {value!r}")
    formatted = f"{value:.6f}".rstrip("0")
    if formatted.endswith("."):
        formatted += "0"
    return formatted


def _format_float(value: float) -> str:
    """Format a finite float canonically without scientific notation or trailing noise."""
    if not math.isfinite(value):
        raise ValueError(f"Non-finite float value in SII synthesis: {value!r}")
    if value == 0.0:
        return "0"
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _format_tuple3(values: tuple[float, float, float]) -> str:
    return f"({_format_float(values[0])}, {_format_float(values[1])}, {_format_float(values[2])})"


def _format_tuple4(values: tuple[float, float, float, float]) -> str:
    return (
        f"({_format_float(values[0])}, {_format_float(values[1])}, "
        f"{_format_float(values[2])}, {_format_float(values[3])})"
    )


def _format_lane_rule_lines(rule: LaneSpeedRule, indent: str) -> list[str]:
    lane_token = _format_token(rule.lane_speed_class, field_name="lane_speed_class")
    lines = [f"{indent}lane_speed_class[]: {lane_token}"]
    if rule.limit is not None:
        lines.append(f"{indent}limit[]: {rule.limit}")
    if rule.urban_limit is not None:
        lines.append(f"{indent}urban_limit[]: {rule.urban_limit}")
    if rule.max_limit is not None:
        lines.append(f"{indent}max_limit[]: {rule.max_limit}")
    if rule.uncommon is not None:
        lines.append(f"{indent}uncommon[]: {_format_bool(rule.uncommon)}")
    return lines


def _assert_hygiene(raw: bytes, *, require_siinunit: bool, label: str) -> None:
    diagnostics = validate_sii_hygiene(raw, require_siinunit=require_siinunit)
    if diagnostics:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in diagnostics)
        raise ValueError(f"Synthesized SII hygiene failure for {label}: {summary}")


def synthesize_country_sui(
    baseline: BaselineCountry,
    resolved: RealismSnapshotCountry,
) -> bytes:
    """Synthesize a clean-room headerless ``def/country/<slug>.sui`` payload."""
    if baseline.slug != resolved.ets2_slug:
        raise ValueError(
            f"Country slug mismatch: baseline={baseline.slug!r}, resolved={resolved.ets2_slug!r}"
        )

    unit_name = _format_unit_name(baseline.unit_name)
    lines: list[str] = [f"country_data : {unit_name}", "{"]

    lines.append(f"\tcountry_id: {baseline.country_id}")
    lines.append(f"\tname: {_format_sii_string(baseline.name)}")
    if baseline.name_localized is not None:
        lines.append(f"\tname_localized: {_format_sii_string(baseline.name_localized)}")
    lines.append(f"\tcountry_code: {_format_sii_string(baseline.country_code)}")
    if baseline.iso_country_code_quoted:
        iso_literal = _format_sii_string(baseline.iso_country_code)
    else:
        iso_literal = _format_token(baseline.iso_country_code, field_name="iso_country_code")
    lines.append(f"\tiso_country_code: {iso_literal}")
    if baseline.pos is not None:
        lines.append(f"\tpos: {_format_tuple3(baseline.pos)}")
    if baseline.fuel_price is not None:
        lines.append(f"\tfuel_price: {_format_fuel_price(baseline.fuel_price)}")

    lines.append(f"\tlights_mandatory: {_format_bool(resolved.lights_mandatory)}")
    if baseline.driving_tired_offence is not None:
        lines.append(f"\tdriving_tired_offence: {_format_bool(baseline.driving_tired_offence)}")
    if baseline.imperial_units is not None:
        lines.append(f"\timperial_units: {_format_bool(baseline.imperial_units)}")
    if baseline.leftside_traffic is not None:
        lines.append(f"\tleftside_traffic: {_format_bool(baseline.leftside_traffic)}")
    if baseline.trailer_standalone is not None:
        lines.append(f"\ttrailer_standalone: {_format_bool(baseline.trailer_standalone)}")

    lines.append(f"\ttime_zone: {resolved.time_zone}")
    lines.append(f"\ttime_zone_name: {_format_sii_string(resolved.time_zone_name)}")

    if (
        baseline.secondary_time_zone_area
        or baseline.secondary_time_zone
        or baseline.secondary_time_zone_name
    ):
        lines.append("")
        for area in baseline.secondary_time_zone_area:
            lines.append(f"\tsecondary_time_zone_area[]: {_format_tuple4(area)}")
        for sec_tz in baseline.secondary_time_zone:
            lines.append(f"\tsecondary_time_zone[]: {sec_tz}")
        for sec_name in baseline.secondary_time_zone_name:
            lines.append(f"\tsecondary_time_zone_name[]: {_format_sii_string(sec_name)}")

    if resolved.mass_limit_per_axle_count:
        lines.append("")
        for mass_kg in resolved.mass_limit_per_axle_count:
            lines.append(f"\tmass_limit_per_axle_count[]: {mass_kg}")

    if baseline.regions or baseline.region_areas:
        lines.append("")
        for region_name in baseline.regions:
            lines.append(f"\tregions[]: {_format_sii_string(region_name)}")
        for region_area in baseline.region_areas:
            lines.append(f"\tregion_areas[]: {_format_tuple4(region_area)}")

    if baseline.extra_attributes:
        lines.append("")
        for key in sorted(baseline.extra_attributes):
            safe_key = _format_token(key, field_name="extra_attribute_key")
            raw_values = baseline.extra_attributes[key]
            if len(raw_values) == 1:
                val = raw_values[0]
                if "\r" in val or "\n" in val or "\x00" in val:
                    raise ValueError(f"Invalid control character in extra attribute {key!r}")
                lines.append(f"\t{safe_key}: {val}")
            else:
                for val in raw_values:
                    if "\r" in val or "\n" in val or "\x00" in val:
                        raise ValueError(f"Invalid control character in extra attribute {key!r}")
                    lines.append(f"\t{safe_key}[]: {val}")

    lines.append("}")
    raw = serialize_sii_text("\n".join(lines) + "\n")
    _assert_hygiene(raw, require_siinunit=False, label=f"def/country/{baseline.slug}.sui")
    return raw


def synthesize_speed_limits_sii(
    baseline: BaselineSpeedLimit,
    resolved: RealismSnapshotCountry,
) -> bytes:
    """Synthesize a clean-room ``def/country/<slug>/speed_limits.sii`` payload."""
    if baseline.slug != resolved.ets2_slug:
        raise ValueError(
            f"Speed limit slug mismatch: baseline={baseline.slug!r}, "
            f"resolved={resolved.ets2_slug!r}"
        )

    lines: list[str] = ["SiiNunit", "{"]
    for block_idx, block in enumerate(baseline.blocks):
        if block_idx > 0:
            lines.append("")
        unit_name = _format_unit_name(block.unit_name)
        vehicle_class = _format_token(
            block.vehicle_speed_class,
            field_name="vehicle_speed_class",
        )
        lines.append(f"country_speed_limit : {unit_name}")
        lines.append("{")
        lines.append(f"\tvehicle_speed_class: {vehicle_class}")

        if vehicle_class in _ROAD_CLASSES:
            road_class: RoadVehicleClass = (
                "car" if vehicle_class == "car" else "truck" if vehicle_class == "truck" else "bus"
            )
            lanes = [
                LaneSpeedRule(
                    lane_speed_class=override.lane_speed_class,
                    limit=override.limit,
                    urban_limit=override.urban_limit,
                    max_limit=override.max_limit,
                    uncommon=override.uncommon,
                )
                for override in resolved.speed_limits[road_class]
            ]
        else:
            lanes = list(block.lanes)

        for rule in lanes:
            lines.append("")
            lines.extend(_format_lane_rule_lines(rule, "\t"))

        lines.append("}")

    lines.append("}")
    raw = serialize_sii_text("\n".join(lines) + "\n")
    _assert_hygiene(
        raw,
        require_siinunit=True,
        label=f"def/country/{baseline.slug}/speed_limits.sii",
    )
    return raw
