"""Interleaved per-lane reader and surgical editor for ETS2 ``speed_limits.sii``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.sii.document import SiiDocument
from ets2v2.sii.lexer import SiiAttributeSpan, SiiUnitBlock, unquote_sii_string

_LANE_FIELDS = ("limit", "urban_limit", "max_limit", "uncommon")


class LaneSpeedRule(BaseModel):
    """Speed limits for one ``lane_speed_class[]`` inside a ``country_speed_limit`` unit."""

    model_config = ConfigDict(frozen=True)

    lane_speed_class: str
    limit: int | None = None
    urban_limit: int | None = None
    max_limit: int | None = None
    uncommon: bool | None = None


class VehicleSpeedLimitBlock(BaseModel):
    """All lane speed rules for one ``vehicle_speed_class`` (car/truck/bus/train/tram)."""

    model_config = ConfigDict(frozen=True)

    unit_name: str
    vehicle_speed_class: str
    lanes: list[LaneSpeedRule] = Field(default_factory=list)


class SpeedLimitsFile(BaseModel):
    """Structured view of all ``country_speed_limit`` blocks in ``speed_limits.sii``."""

    model_config = ConfigDict(frozen=True)

    blocks: list[VehicleSpeedLimitBlock] = Field(default_factory=list)

    @property
    def vehicle_classes(self) -> list[str]:
        return [block.vehicle_speed_class for block in self.blocks]

    def get_block(self, vehicle_speed_class: str) -> VehicleSpeedLimitBlock | None:
        for block in self.blocks:
            if block.vehicle_speed_class == vehicle_speed_class:
                return block
        return None


@dataclass
class _LaneSpanGroup:
    lane_speed_class: str
    lane_attr: SiiAttributeSpan
    fields: dict[str, SiiAttributeSpan]
    ordered_attrs: list[SiiAttributeSpan]


def _parse_bool(raw: str) -> bool:
    token = raw.strip().lower()
    if token == "true":
        return True
    if token == "false":
        return False
    raise ValueError(f"Invalid SII boolean value: {raw!r}")


def _extract_vehicle_class(unit: SiiUnitBlock) -> str:
    scalar = unit.get_scalar("vehicle_speed_class")
    if scalar is not None and scalar.raw_value:
        return unquote_sii_string(scalar.raw_value)[0]
    if "." in unit.unit_name:
        tail = unit.unit_name.rsplit(".", maxsplit=1)[-1]
        if tail:
            return tail
    raise ValueError(f"Missing vehicle_speed_class on unit {unit.unit_name!r}")


def _extract_lane_groups(unit: SiiUnitBlock) -> list[_LaneSpanGroup]:
    groups: list[_LaneSpanGroup] = []
    current: _LaneSpanGroup | None = None

    for attr in unit.attributes:
        if attr.key == "vehicle_speed_class":
            continue
        if attr.key == "lane_speed_class":
            lane_name = unquote_sii_string(attr.raw_value)[0]
            current = _LaneSpanGroup(
                lane_speed_class=lane_name,
                lane_attr=attr,
                fields={},
                ordered_attrs=[attr],
            )
            groups.append(current)
            continue
        if attr.key in _LANE_FIELDS:
            if current is None:
                raise ValueError(
                    f"Found {attr.key}[] before lane_speed_class[] in {unit.unit_name!r}"
                )
            if attr.key in current.fields:
                raise ValueError(f"Duplicate {attr.key}[] within lane {current.lane_speed_class!r}")
            current.fields[attr.key] = attr
            current.ordered_attrs.append(attr)

    return groups


def _group_to_rule(group: _LaneSpanGroup) -> LaneSpeedRule:
    limit_attr = group.fields.get("limit")
    urban_attr = group.fields.get("urban_limit")
    max_attr = group.fields.get("max_limit")
    uncommon_attr = group.fields.get("uncommon")

    return LaneSpeedRule(
        lane_speed_class=group.lane_speed_class,
        limit=int(limit_attr.raw_value.strip()) if limit_attr is not None else None,
        urban_limit=int(urban_attr.raw_value.strip()) if urban_attr is not None else None,
        max_limit=int(max_attr.raw_value.strip()) if max_attr is not None else None,
        uncommon=_parse_bool(uncommon_attr.raw_value) if uncommon_attr is not None else None,
    )


def _format_lane_rule_lines(rule: LaneSpeedRule, indent: str) -> list[str]:
    lines = [f"{indent}lane_speed_class[]: {rule.lane_speed_class}"]
    if rule.limit is not None:
        lines.append(f"{indent}limit[]: {rule.limit}")
    if rule.urban_limit is not None:
        lines.append(f"{indent}urban_limit[]: {rule.urban_limit}")
    if rule.max_limit is not None:
        lines.append(f"{indent}max_limit[]: {rule.max_limit}")
    if rule.uncommon is not None:
        lines.append(f"{indent}uncommon[]: {'true' if rule.uncommon else 'false'}")
    return lines


def _desired_field_str(rule: LaneSpeedRule, field_name: str) -> str | None:
    if field_name == "limit":
        return str(rule.limit) if rule.limit is not None else None
    if field_name == "urban_limit":
        return str(rule.urban_limit) if rule.urban_limit is not None else None
    if field_name == "max_limit":
        return str(rule.max_limit) if rule.max_limit is not None else None
    if field_name == "uncommon":
        if rule.uncommon is None:
            return None
        return "true" if rule.uncommon else "false"
    raise KeyError(field_name)


def _patch_unit_lanes_in_place(
    doc: SiiDocument,
    unit_index: int,
    new_lanes: Sequence[LaneSpeedRule],
) -> None:
    for lane_idx, rule in enumerate(new_lanes):
        for field_name in _LANE_FIELDS:
            current_unit = doc.units[unit_index]
            groups = _extract_lane_groups(current_unit)
            group = groups[lane_idx]
            existing_attr = group.fields.get(field_name)
            desired = _desired_field_str(rule, field_name)

            if existing_attr is not None and desired is not None:
                doc.update_attribute_value(existing_attr, desired)
            elif existing_attr is not None and desired is None:
                doc.remove_attribute_line(existing_attr)
            elif existing_attr is None and desired is not None:
                anchor = group.lane_attr
                field_pos = _LANE_FIELDS.index(field_name)
                for prev_name in _LANE_FIELDS[:field_pos]:
                    prev_attr = group.fields.get(prev_name)
                    if prev_attr is not None:
                        anchor = prev_attr
                indent = anchor.indent or current_unit.indent
                doc.insert_lines_after_attribute(anchor, [f"{indent}{field_name}[]: {desired}"])


def _replace_unit_lane_region(
    doc: SiiDocument,
    unit_index: int,
    new_lanes: Sequence[LaneSpeedRule],
) -> None:
    current_unit = doc.units[unit_index]
    groups = _extract_lane_groups(current_unit)
    indent = current_unit.indent

    formatted_blocks = ["\n".join(_format_lane_rule_lines(rule, indent)) for rule in new_lanes]
    replacement_body = "\n\n".join(formatted_blocks)

    if not groups:
        if not new_lanes:
            return
        lines: list[str] = []
        for idx, rule in enumerate(new_lanes):
            if idx > 0:
                lines.append("")
            lines.extend(_format_lane_rule_lines(rule, indent))
        close_pos = current_unit.close_brace_pos
        brace_line_start = doc.text.rfind("\n", 0, close_pos) + 1
        payload = "".join(f"{line}\n" for line in lines)
        doc.replace_span(brace_line_start, brace_line_start, payload)
        return

    region_start = groups[0].ordered_attrs[0].line_span.start
    region_end = groups[-1].ordered_attrs[-1].line_span.end

    if not new_lanes:
        if region_end < len(doc.text) and doc.text[region_end] == "\n":
            region_end += 1
        doc.replace_span(region_start, region_end, "")
        return

    doc.replace_span(region_start, region_end, replacement_body)


def parse_speed_limits(source: str | bytes) -> SpeedLimitsFile:
    """Parse all ``country_speed_limit`` units into interleaved ``LaneSpeedRule`` blocks."""
    doc = SiiDocument.parse(source)
    blocks: list[VehicleSpeedLimitBlock] = []
    for unit in doc.find_units(class_name="country_speed_limit"):
        vehicle_class = _extract_vehicle_class(unit)
        groups = _extract_lane_groups(unit)
        blocks.append(
            VehicleSpeedLimitBlock(
                unit_name=unit.unit_name,
                vehicle_speed_class=vehicle_class,
                lanes=[_group_to_rule(group) for group in groups],
            )
        )
    return SpeedLimitsFile(blocks=blocks)


def patch_speed_limits(
    source: str | bytes,
    updates: Mapping[str, Sequence[LaneSpeedRule]],
) -> str:
    """Surgically update targeted ``vehicle_speed_class`` blocks while keeping others intact."""
    doc = SiiDocument.parse(source)
    unit_index_by_class: dict[str, int] = {}
    for unit in doc.find_units(class_name="country_speed_limit"):
        vehicle_class = _extract_vehicle_class(unit)
        unit_index_by_class[vehicle_class] = unit.index

    for vehicle_class, new_lanes in updates.items():
        if vehicle_class not in unit_index_by_class:
            raise ValueError(
                f"Vehicle speed class {vehicle_class!r} not found in speed_limits file"
            )
        unit_index = unit_index_by_class[vehicle_class]
        current_unit = doc.units[unit_index]
        existing_groups = _extract_lane_groups(current_unit)
        existing_names = [g.lane_speed_class for g in existing_groups]
        target_names = [r.lane_speed_class for r in new_lanes]

        if existing_names == target_names:
            _patch_unit_lanes_in_place(doc, unit_index, new_lanes)
        else:
            _replace_unit_lane_region(doc, unit_index, new_lanes)

    return doc.render()
