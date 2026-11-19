"""Deterministic loader, serializer, and baseline cross-validator for the law registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ValidationError

from ets2v2.baseline.models import (
    BaselineCountry,
    BaselineSpeedLimit,
    CountriesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.registry.models import (
    CountryLawRecord,
    CountryMappingEntry,
    CountryMappingRegistry,
    LawRegistryBundle,
    RoadVehicleClass,
)

_ROAD_CLASSES: Final[tuple[RoadVehicleClass, ...]] = ("car", "truck", "bus")


def serialize_registry_json_bytes(model: BaseModel) -> bytes:
    """Serialize any registry model to canonical UTF-8 no-BOM LF sorted JSON bytes."""
    payload: object = model.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def _check_raw_hygiene(raw: bytes, label: str, issues: list[str]) -> str | None:
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(f"UTF-8 BOM detected in {label}")
    if b"\r" in raw:
        issues.append(f"Non-LF line endings detected in {label}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(f"Invalid UTF-8 in {label}: {exc}")
        return None


def _check_prohibited_scs_files(root: Path, label: str, issues: list[str]) -> None:
    if not root.is_dir():
        return
    prohibited = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".sii", ".sui"}
    )
    for rel in prohibited:
        issues.append(f"Prohibited raw SCS file under {label}: {rel}")


def load_law_registry(laws_dir: Path | str, mappings_path: Path | str) -> LawRegistryBundle:
    """Load and structurally verify the canonical mappings and per-country law JSON files."""
    laws_root = Path(laws_dir)
    mappings_file = Path(mappings_path)
    countries_dir = laws_root / "countries"

    if not mappings_file.is_file():
        raise FileNotFoundError(f"Missing country mappings file: {mappings_file}")
    if not countries_dir.is_dir():
        raise FileNotFoundError(f"Missing country laws directory: {countries_dir}")

    mappings = CountryMappingRegistry.model_validate_json(mappings_file.read_text("utf-8"))

    seen_map_iso2: set[str] = set()
    seen_map_slugs: set[str] = set()
    for entry in mappings.countries:
        if entry.iso2 in seen_map_iso2:
            raise ValueError(f"Duplicate iso2 in mappings: {entry.iso2}")
        if entry.ets2_slug in seen_map_slugs:
            raise ValueError(f"Duplicate ets2_slug in mappings: {entry.ets2_slug}")
        seen_map_iso2.add(entry.iso2)
        seen_map_slugs.add(entry.ets2_slug)

    law_files = sorted(countries_dir.glob("*.json"))
    if not law_files:
        raise ValueError(f"No country law JSON files found under {countries_dir}")

    laws_by_iso2: dict[str, CountryLawRecord] = {}
    seen_law_slugs: set[str] = set()
    for law_file in law_files:
        record = CountryLawRecord.model_validate_json(law_file.read_text("utf-8"))
        expected_name = f"{record.iso2.lower()}.json"
        if law_file.name != expected_name:
            raise ValueError(
                f"Filename {law_file.name!r} does not match record iso2 {record.iso2!r} "
                f"(expected {expected_name!r})"
            )
        if record.iso2 in laws_by_iso2:
            raise ValueError(f"Duplicate iso2 law record: {record.iso2}")
        if record.ets2_slug in seen_law_slugs:
            raise ValueError(f"Duplicate ets2_slug in law records: {record.ets2_slug}")
        laws_by_iso2[record.iso2] = record
        seen_law_slugs.add(record.ets2_slug)

    if set(laws_by_iso2.keys()) != seen_map_iso2:
        missing_laws = sorted(seen_map_iso2 - set(laws_by_iso2.keys()))
        extra_laws = sorted(set(laws_by_iso2.keys()) - seen_map_iso2)
        raise ValueError(
            f"Mappings/laws iso2 mismatch (missing_laws={missing_laws}, extra_laws={extra_laws})"
        )

    for entry in mappings.countries:
        law = laws_by_iso2[entry.iso2]
        if law.ets2_slug != entry.ets2_slug:
            raise ValueError(
                f"ets2_slug mismatch for {entry.iso2}: "
                f"mapping={entry.ets2_slug!r}, law={law.ets2_slug!r}"
            )
        if law.iso3 != entry.iso3:
            raise ValueError(
                f"iso3 mismatch for {entry.iso2}: mapping={entry.iso3!r}, law={law.iso3!r}"
            )

    return LawRegistryBundle(mappings=mappings, laws_by_iso2=laws_by_iso2)


def _validate_country_against_baseline(
    entry: CountryMappingEntry,
    record: CountryLawRecord,
    bl_country: BaselineCountry,
    bl_speed: BaselineSpeedLimit | None,
    issues: list[str],
) -> None:
    slug = entry.ets2_slug
    iso2 = entry.iso2

    if record.iso3 != bl_country.iso_country_code:
        issues.append(
            f"{iso2} ({slug}): iso3 {record.iso3!r} != baseline {bl_country.iso_country_code!r}"
        )
    if entry.iso3 != bl_country.iso_country_code:
        issues.append(
            f"{iso2} ({slug}): mapping iso3 {entry.iso3!r} != "
            f"baseline {bl_country.iso_country_code!r}"
        )
    if entry.country_id != bl_country.country_id:
        issues.append(
            f"{iso2} ({slug}): mapping country_id {entry.country_id} != "
            f"baseline {bl_country.country_id}"
        )

    expected_unit = "mph" if bl_country.imperial_units is True else "kmh"
    if record.speed_unit != expected_unit:
        issues.append(
            f"{iso2} ({slug}): speed_unit {record.speed_unit!r} != expected {expected_unit!r} "
            f"(baseline imperial_units={bl_country.imperial_units!r})"
        )

    bl_axles = bl_country.mass_limit_per_axle_count
    law_axles = record.mass_limit_per_axle_count
    if len(law_axles) < len(bl_axles):
        issues.append(
            f"{iso2} ({slug}): mass_limit_per_axle_count length {len(law_axles)} < "
            f"baseline length {len(bl_axles)}"
        )
    else:
        for idx, bl_val in enumerate(bl_axles):
            if law_axles[idx] < bl_val:
                issues.append(
                    f"{iso2} ({slug}): mass_limit_per_axle_count[{idx}] downgraded "
                    f"({law_axles[idx]} < baseline {bl_val})"
                )

    if bl_speed is None:
        issues.append(f"{iso2} ({slug}): missing entry in baseline speed_limits.json")
        return

    bl_blocks = {block.vehicle_speed_class: block for block in bl_speed.blocks}
    for season_name, season_rules in (("summer", record.summer), ("winter", record.winter)):
        for vehicle_class in _ROAD_CLASSES:
            bl_block = bl_blocks.get(vehicle_class)
            if bl_block is None:
                issues.append(
                    f"{iso2} ({slug}): baseline speed_limits.json missing {vehicle_class!r} block"
                )
                continue

            law_lanes = season_rules.speed_limits[vehicle_class]
            bl_lane_names = [lane.lane_speed_class for lane in bl_block.lanes]
            law_lane_names = [lane.lane_speed_class for lane in law_lanes]
            if law_lane_names != bl_lane_names:
                issues.append(
                    f"{iso2} ({slug}) [{season_name}.{vehicle_class}]: lane classes "
                    f"{law_lane_names} != baseline {bl_lane_names}"
                )
                continue

            for law_lane, bl_lane in zip(law_lanes, bl_block.lanes, strict=True):
                if law_lane.uncommon != bl_lane.uncommon:
                    issues.append(
                        f"{iso2} ({slug}) [{season_name}.{vehicle_class}."
                        f"{law_lane.lane_speed_class}]: uncommon {law_lane.uncommon!r} != "
                        f"baseline {bl_lane.uncommon!r}"
                    )
                if (law_lane.max_limit is None) != (bl_lane.max_limit is None):
                    issues.append(
                        f"{iso2} ({slug}) [{season_name}.{vehicle_class}."
                        f"{law_lane.lane_speed_class}]: max_limit nullability mismatch "
                        f"(law={law_lane.max_limit!r}, baseline={bl_lane.max_limit!r})"
                    )


def validate_law_registry(
    laws_dir: Path | str,
    mappings_path: Path | str,
    baseline_dir: Path | str,
) -> list[str]:
    """Validate formatting, schemas, bijectivity, and 1.62 baseline parity for the law registry."""
    laws_root = Path(laws_dir)
    mappings_file = Path(mappings_path)
    baseline_root = Path(baseline_dir)
    countries_dir = laws_root / "countries"
    issues: list[str] = []

    _check_prohibited_scs_files(laws_root, str(laws_root), issues)
    _check_prohibited_scs_files(mappings_file.parent, str(mappings_file.parent), issues)

    mappings: CountryMappingRegistry | None = None
    if not mappings_file.is_file():
        issues.append(f"Missing mappings file: {mappings_file}")
    else:
        raw_map = mappings_file.read_bytes()
        map_text = _check_raw_hygiene(raw_map, mappings_file.name, issues)
        if map_text is not None:
            try:
                mappings = CountryMappingRegistry.model_validate_json(map_text)
            except ValidationError as exc:
                issues.append(f"Invalid mappings schema in {mappings_file.name}: {exc}")
            else:
                expected_map = serialize_registry_json_bytes(mappings)
                if raw_map != expected_map:
                    issues.append(
                        f"Non-canonical JSON formatting in {mappings_file.name} "
                        f"(must match sorted UTF-8 no-BOM LF)"
                    )

    laws_by_iso2: dict[str, CountryLawRecord] = {}
    seen_law_slugs: dict[str, str] = {}
    seen_law_iso3: dict[str, str] = {}
    if not countries_dir.is_dir():
        issues.append(f"Missing country laws directory: {countries_dir}")
    else:
        non_json = sorted(
            p.name for p in countries_dir.iterdir() if p.is_file() and p.suffix.lower() != ".json"
        )
        for stray in non_json:
            issues.append(f"Unexpected non-JSON file in {countries_dir}: {stray}")

        law_files = sorted(countries_dir.glob("*.json"))
        if not law_files:
            issues.append(f"No country law JSON files found in {countries_dir}")

        for law_file in law_files:
            raw_law = law_file.read_bytes()
            law_text = _check_raw_hygiene(raw_law, law_file.name, issues)
            if law_text is None:
                continue
            try:
                record = CountryLawRecord.model_validate_json(law_text)
            except ValidationError as exc:
                issues.append(f"Invalid law schema in {law_file.name}: {exc}")
                continue

            expected_law = serialize_registry_json_bytes(record)
            if raw_law != expected_law:
                issues.append(
                    f"Non-canonical JSON formatting in {law_file.name} "
                    f"(must match sorted UTF-8 no-BOM LF)"
                )

            expected_filename = f"{record.iso2.lower()}.json"
            if law_file.name != expected_filename:
                issues.append(
                    f"Filename {law_file.name!r} does not match iso2 {record.iso2!r} "
                    f"(expected {expected_filename!r})"
                )

            try:
                ZoneInfo(record.iana_timezone)
            except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
                issues.append(
                    f"{record.iso2} ({record.ets2_slug}): invalid iana_timezone "
                    f"{record.iana_timezone!r}: {exc}"
                )

            if record.iso2 in laws_by_iso2:
                issues.append(f"Duplicate iso2 {record.iso2!r} across law files")
            else:
                laws_by_iso2[record.iso2] = record

            if record.ets2_slug in seen_law_slugs:
                issues.append(
                    f"Duplicate ets2_slug {record.ets2_slug!r} in law files "
                    f"({seen_law_slugs[record.ets2_slug]} and {record.iso2})"
                )
            else:
                seen_law_slugs[record.ets2_slug] = record.iso2

            if record.iso3 in seen_law_iso3:
                issues.append(
                    f"Duplicate iso3 {record.iso3!r} in law files "
                    f"({seen_law_iso3[record.iso3]} and {record.iso2})"
                )
            else:
                seen_law_iso3[record.iso3] = record.iso2

    bl_countries_path = baseline_root / "countries.json"
    bl_speeds_path = baseline_root / "speed_limits.json"
    countries_bl: CountriesBaseline | None = None
    speeds_bl: SpeedLimitsBaseline | None = None

    if not bl_countries_path.is_file():
        issues.append(f"Missing baseline countries.json: {bl_countries_path}")
    else:
        try:
            countries_bl = CountriesBaseline.model_validate_json(
                bl_countries_path.read_text("utf-8")
            )
        except ValidationError as exc:
            issues.append(f"Invalid baseline countries.json: {exc}")

    if not bl_speeds_path.is_file():
        issues.append(f"Missing baseline speed_limits.json: {bl_speeds_path}")
    else:
        try:
            speeds_bl = SpeedLimitsBaseline.model_validate_json(bl_speeds_path.read_text("utf-8"))
        except ValidationError as exc:
            issues.append(f"Invalid baseline speed_limits.json: {exc}")

    if mappings is None:
        return issues

    map_by_iso2: dict[str, CountryMappingEntry] = {}
    map_by_slug: dict[str, CountryMappingEntry] = {}
    seen_ids: dict[int, str] = {}
    seen_map_iso3: dict[str, str] = {}
    slug_order = [entry.ets2_slug for entry in mappings.countries]
    if slug_order != sorted(slug_order):
        issues.append("ets2_countries.json countries array must be sorted ascending by ets2_slug")

    for entry in mappings.countries:
        if entry.iso2 in map_by_iso2:
            issues.append(f"Duplicate iso2 {entry.iso2!r} in {mappings_file.name}")
        else:
            map_by_iso2[entry.iso2] = entry

        if entry.ets2_slug in map_by_slug:
            issues.append(f"Duplicate ets2_slug {entry.ets2_slug!r} in {mappings_file.name}")
        else:
            map_by_slug[entry.ets2_slug] = entry

        if entry.country_id in seen_ids:
            issues.append(
                f"Duplicate country_id {entry.country_id} in {mappings_file.name} "
                f"({seen_ids[entry.country_id]} and {entry.ets2_slug})"
            )
        else:
            seen_ids[entry.country_id] = entry.ets2_slug

        if entry.iso3 in seen_map_iso3:
            issues.append(
                f"Duplicate iso3 {entry.iso3!r} in {mappings_file.name} "
                f"({seen_map_iso3[entry.iso3]} and {entry.ets2_slug})"
            )
        else:
            seen_map_iso3[entry.iso3] = entry.ets2_slug

    missing_law_iso2 = sorted(set(map_by_iso2) - set(laws_by_iso2))
    extra_law_iso2 = sorted(set(laws_by_iso2) - set(map_by_iso2))
    for iso2 in missing_law_iso2:
        issues.append(f"Missing country law file for mapped iso2 {iso2!r}")
    for iso2 in extra_law_iso2:
        issues.append(f"Unmapped country law file for iso2 {iso2!r}")

    for iso2 in sorted(set(map_by_iso2) & set(laws_by_iso2)):
        entry = map_by_iso2[iso2]
        record = laws_by_iso2[iso2]
        if record.ets2_slug != entry.ets2_slug:
            issues.append(
                f"{iso2}: law ets2_slug {record.ets2_slug!r} != mapping {entry.ets2_slug!r}"
            )
        if record.iso3 != entry.iso3:
            issues.append(f"{iso2}: law iso3 {record.iso3!r} != mapping {entry.iso3!r}")

    if countries_bl is None or speeds_bl is None:
        return issues

    bl_countries_by_slug = {c.slug: c for c in countries_bl.countries}
    bl_speeds_by_slug = {s.slug: s for s in speeds_bl.speed_limits}

    missing_slugs = sorted(set(bl_countries_by_slug) - set(map_by_slug))
    extra_slugs = sorted(set(map_by_slug) - set(bl_countries_by_slug))
    for slug in missing_slugs:
        issues.append(f"Baseline country slug {slug!r} missing from {mappings_file.name}")
    for slug in extra_slugs:
        issues.append(f"Non-baseline country slug {slug!r} present in {mappings_file.name}")

    for slug in sorted(set(bl_countries_by_slug) & set(map_by_slug)):
        entry = map_by_slug[slug]
        record = laws_by_iso2.get(entry.iso2)
        if record is None:
            continue
        _validate_country_against_baseline(
            entry=entry,
            record=record,
            bl_country=bl_countries_by_slug[slug],
            bl_speed=bl_speeds_by_slug.get(slug),
            issues=issues,
        )

    return issues
