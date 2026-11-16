"""Read and surgical edit adapters for ETS2 ``country.sii`` and ``country_data`` units."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.sii.document import SiiDocument
from ets2v2.sii.lexer import SiiAttributeSpan, parse_sii_float, unquote_sii_string

_KNOWN_COUNTRY_ATTRS = frozenset(
    {
        "country_id",
        "name",
        "name_localized",
        "country_code",
        "iso_country_code",
        "pos",
        "fuel_price",
        "lights_mandatory",
        "driving_tired_offence",
        "imperial_units",
        "leftside_traffic",
        "trailer_standalone",
        "time_zone",
        "time_zone_name",
        "secondary_time_zone_area",
        "secondary_time_zone",
        "secondary_time_zone_name",
        "mass_limit_per_axle_count",
        "regions",
        "region_areas",
    }
)


class CountryDataModel(BaseModel):
    """Typed representation of an ETS2 ``country_data`` definition unit."""

    model_config = ConfigDict(frozen=True)

    unit_name: str
    country_id: int = 0
    name: str = ""
    name_localized: str | None = None
    country_code: str = ""
    iso_country_code: str = ""
    iso_country_code_quoted: bool = False
    pos: tuple[float, float, float] | None = None
    fuel_price: float | None = None
    lights_mandatory: bool | None = None
    driving_tired_offence: bool | None = None
    imperial_units: bool | None = None
    leftside_traffic: bool | None = None
    trailer_standalone: bool | None = None
    time_zone: int | None = None
    time_zone_name: str | None = None
    secondary_time_zone_area: list[tuple[float, float, float, float]] = Field(default_factory=list)
    secondary_time_zone: list[int] = Field(default_factory=list)
    secondary_time_zone_name: list[str] = Field(default_factory=list)
    mass_limit_per_axle_count: list[int] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    region_areas: list[tuple[float, float, float, float]] = Field(default_factory=list)
    extra_attributes: dict[str, list[str]] = Field(default_factory=dict)


class CountryDataPatch(BaseModel):
    """Surgical overlay patch for realism-owned ``country_data`` fields."""

    model_config = ConfigDict(frozen=True)

    fuel_price: float | None = None
    lights_mandatory: bool | None = None
    driving_tired_offence: bool | None = None
    time_zone: int | None = None
    time_zone_name: str | None = None
    mass_limit_per_axle_count: list[int] | None = None


def _parse_bool(raw: str) -> bool:
    token = raw.strip().lower()
    if token == "true":
        return True
    if token == "false":
        return False
    raise ValueError(f"Invalid SII boolean value: {raw!r}")


def _parse_float_3(raw: str) -> tuple[float, float, float]:
    parts = _split_tuple_components(raw, expected_len=3)
    return (parse_sii_float(parts[0]), parse_sii_float(parts[1]), parse_sii_float(parts[2]))


def _parse_float_4(raw: str) -> tuple[float, float, float, float]:
    parts = _split_tuple_components(raw, expected_len=4)
    return (
        parse_sii_float(parts[0]),
        parse_sii_float(parts[1]),
        parse_sii_float(parts[2]),
        parse_sii_float(parts[3]),
    )


def _split_tuple_components(raw: str, *, expected_len: int) -> list[str]:
    text = raw.strip()
    if not (text.startswith("(") and text.endswith(")")):
        raise ValueError(f"Expected parenthesized {expected_len}-tuple, got {raw!r}")
    parts = [part.strip() for part in text[1:-1].split(",")]
    if len(parts) != expected_len:
        raise ValueError(f"Expected {expected_len} components in tuple {raw!r}, got {len(parts)}")
    return parts


def _format_fuel_price(value: float) -> str:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid fuel_price: {value!r}")
    formatted = f"{value:.6f}".rstrip("0")
    if formatted.endswith("."):
        formatted += "0"
    return formatted


def _format_sii_string(value: str) -> str:
    if "\\" in value:
        raise ValueError(f"Backslash disallowed in SII string literal: {value!r}")
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _ordered_array_values(attrs: list[SiiAttributeSpan]) -> list[str]:
    """Return raw attribute values in document order or sorted fixed-index order."""
    indexed = [(attr.index, attr.raw_value) for attr in attrs if attr.index is not None]
    if indexed and len(indexed) == len(attrs):
        indexed.sort(key=lambda item: item[0])
        return [val for _, val in indexed]
    return [attr.raw_value for attr in attrs if attr.is_append or attr.index is not None]


def parse_country_includes(source: str | bytes) -> list[str]:
    """Extract ordered ``@include`` paths from ``def/country*.sii``, rejecting col!=0/bad paths."""
    doc = SiiDocument.parse(source)
    blocking_codes = {
        "include_not_column_0",
        "malformed_include",
        "path_backslash",
        "path_parent_traversal",
        "unbalanced_brace",
        "unterminated_comment",
        "unterminated_string",
    }
    errors = [diag for diag in doc.diagnostics if diag.code in blocking_codes]
    if errors:
        first = errors[0]
        raise ValueError(f"{first.code} at line {first.line}:{first.column}: {first.message}")
    return [inc.path for inc in doc.includes]


def parse_country_data(source: str | bytes) -> CountryDataModel:
    """Parse the ``country_data`` unit from a ``.sui`` or ``.sii`` country fragment."""
    doc = SiiDocument.parse(source)
    unit = doc.get_unit(class_name="country_data")
    if unit is None:
        raise ValueError("No country_data unit found in SII/SUI source")

    by_key: dict[str, list[SiiAttributeSpan]] = {}
    extra: dict[str, list[str]] = {}
    for attr in unit.attributes:
        if attr.key in _KNOWN_COUNTRY_ATTRS:
            by_key.setdefault(attr.key, []).append(attr)
        else:
            extra.setdefault(attr.key, []).append(attr.raw_value)

    def _scalar_raw(key: str) -> str | None:
        items = [a for a in by_key.get(key, []) if not a.is_append and a.index is None]
        if not items:
            return None
        val = items[-1].raw_value.strip()
        return None if val == "nil" else val

    country_id_raw = _scalar_raw("country_id")
    country_id = int(country_id_raw) if country_id_raw is not None else 0

    name_raw = _scalar_raw("name")
    name = unquote_sii_string(name_raw)[0] if name_raw is not None else ""

    name_loc_raw = _scalar_raw("name_localized")
    name_localized = unquote_sii_string(name_loc_raw)[0] if name_loc_raw is not None else None

    cc_raw = _scalar_raw("country_code")
    country_code = unquote_sii_string(cc_raw)[0] if cc_raw is not None else ""

    iso_raw = _scalar_raw("iso_country_code")
    if iso_raw is not None:
        iso_country_code, iso_quoted = unquote_sii_string(iso_raw)
    else:
        iso_country_code, iso_quoted = "", False

    pos_raw = _scalar_raw("pos")
    pos = _parse_float_3(pos_raw) if pos_raw is not None else None

    fuel_raw = _scalar_raw("fuel_price")
    fuel_price = parse_sii_float(fuel_raw) if fuel_raw is not None else None

    lights_raw = _scalar_raw("lights_mandatory")
    lights_mandatory = _parse_bool(lights_raw) if lights_raw is not None else None

    tired_raw = _scalar_raw("driving_tired_offence")
    driving_tired_offence = _parse_bool(tired_raw) if tired_raw is not None else None

    imperial_raw = _scalar_raw("imperial_units")
    imperial_units = _parse_bool(imperial_raw) if imperial_raw is not None else None

    leftside_raw = _scalar_raw("leftside_traffic")
    leftside_traffic = _parse_bool(leftside_raw) if leftside_raw is not None else None

    trailer_raw = _scalar_raw("trailer_standalone")
    trailer_standalone = _parse_bool(trailer_raw) if trailer_raw is not None else None

    tz_raw = _scalar_raw("time_zone")
    time_zone = int(tz_raw) if tz_raw is not None else None

    tz_name_raw = _scalar_raw("time_zone_name")
    time_zone_name = unquote_sii_string(tz_name_raw)[0] if tz_name_raw is not None else None

    sec_areas = [
        _parse_float_4(raw)
        for raw in _ordered_array_values(by_key.get("secondary_time_zone_area", []))
    ]
    sec_tzs = [
        int(raw.strip()) for raw in _ordered_array_values(by_key.get("secondary_time_zone", []))
    ]
    sec_tz_names = [
        unquote_sii_string(raw)[0]
        for raw in _ordered_array_values(by_key.get("secondary_time_zone_name", []))
    ]
    axles = [
        int(raw.strip())
        for raw in _ordered_array_values(by_key.get("mass_limit_per_axle_count", []))
    ]
    regions = [
        unquote_sii_string(raw)[0] for raw in _ordered_array_values(by_key.get("regions", []))
    ]
    region_areas = [
        _parse_float_4(raw) for raw in _ordered_array_values(by_key.get("region_areas", []))
    ]

    return CountryDataModel(
        unit_name=unit.unit_name,
        country_id=country_id,
        name=name,
        name_localized=name_localized,
        country_code=country_code,
        iso_country_code=iso_country_code,
        iso_country_code_quoted=iso_quoted,
        pos=pos,
        fuel_price=fuel_price,
        lights_mandatory=lights_mandatory,
        driving_tired_offence=driving_tired_offence,
        imperial_units=imperial_units,
        leftside_traffic=leftside_traffic,
        trailer_standalone=trailer_standalone,
        time_zone=time_zone,
        time_zone_name=time_zone_name,
        secondary_time_zone_area=sec_areas,
        secondary_time_zone=sec_tzs,
        secondary_time_zone_name=sec_tz_names,
        mass_limit_per_axle_count=axles,
        regions=regions,
        region_areas=region_areas,
        extra_attributes=extra,
    )


def patch_country_data(source: str | bytes, patch: CountryDataPatch) -> str:
    """Surgically update realism-owned fields on a ``country_data`` unit."""
    doc = SiiDocument.parse(source)
    unit = doc.get_unit(class_name="country_data")
    if unit is None:
        raise ValueError("No country_data unit found in SII/SUI source")

    if patch.fuel_price is not None:
        doc.set_scalar(unit, "fuel_price", _format_fuel_price(patch.fuel_price))
    if patch.lights_mandatory is not None:
        doc.set_scalar(unit, "lights_mandatory", "true" if patch.lights_mandatory else "false")
    if patch.driving_tired_offence is not None:
        doc.set_scalar(
            unit,
            "driving_tired_offence",
            "true" if patch.driving_tired_offence else "false",
        )
    if patch.time_zone is not None:
        doc.set_scalar(unit, "time_zone", str(patch.time_zone))
    if patch.time_zone_name is not None:
        doc.set_scalar(unit, "time_zone_name", _format_sii_string(patch.time_zone_name))
    if patch.mass_limit_per_axle_count is not None:
        doc.replace_array_append(
            unit,
            "mass_limit_per_axle_count",
            [str(weight) for weight in patch.mass_limit_per_axle_count],
        )

    return doc.render()
