"""ETS2 1.62 core realism invariant auditor guarding against reference-mod regressions."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Final

from ets2v2.baseline.models import (
    BaselineCountry,
    BaselineSpeedLimit,
    CountriesBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.sii.country import CountryDataModel
from ets2v2.sii.speed_limits import SpeedLimitsFile
from ets2v2.validate.models import ValidationCollector

_TZ_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"@@([^@]+)@@")
_NUMERIC_TZ_RE: Final[re.Pattern[str]] = re.compile(r"^[+-]\d{2}(?::?\d{2})?$")
_ICELAND_AXLES: Final[list[int]] = [18000, 29000, 38000, 46000, 60000]
_ICELAND_HEAVY_TRUCK_LIMIT: Final[int] = 80
_REQUIRED_ROAD_CLASSES: Final[tuple[str, ...]] = ("car", "truck", "bus")
_RAIL_CLASSES: Final[tuple[str, ...]] = ("train", "tram")
_FLOAT_TOL: Final[float] = 1e-5


def _tuple_close(a: Sequence[float], b: Sequence[float]) -> bool:
    if len(a) != len(b):
        return False
    return all(
        math.isclose(x, y, rel_tol=_FLOAT_TOL, abs_tol=_FLOAT_TOL)
        for x, y in zip(a, b, strict=True)
    )


def _areas_close(
    a: Sequence[tuple[float, float, float, float]],
    b: Sequence[tuple[float, float, float, float]],
) -> bool:
    if len(a) != len(b):
        return False
    return all(_tuple_close(x, y) for x, y in zip(a, b, strict=True))


def _check_country_identity_and_laws(
    slug: str,
    candidate: CountryDataModel,
    baseline: BaselineCountry,
    allowed_tz_keys: frozenset[str],
    sui_path: str,
    collector: ValidationCollector,
) -> None:
    if candidate.unit_name != baseline.unit_name:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"unit_name mismatch: got {candidate.unit_name!r}, expected {baseline.unit_name!r}",
        )
    if candidate.country_id != baseline.country_id:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"country_id mismatch: got {candidate.country_id}, expected {baseline.country_id}",
        )
    if candidate.name != baseline.name:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"name mismatch: got {candidate.name!r}, expected baseline {baseline.name!r}",
        )
    if candidate.name_localized != baseline.name_localized:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"name_localized mismatch: got {candidate.name_localized!r}, "
            f"expected {baseline.name_localized!r}",
        )
    if candidate.country_code != baseline.country_code:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"country_code mismatch: got {candidate.country_code!r}, "
            f"expected {baseline.country_code!r}",
        )
    if candidate.iso_country_code != baseline.iso_country_code:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"iso_country_code mismatch: got {candidate.iso_country_code!r}, "
            f"expected {baseline.iso_country_code!r}",
        )
    if candidate.iso_country_code_quoted != baseline.iso_country_code_quoted:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"iso_country_code quoting mismatch: got {candidate.iso_country_code_quoted}, "
            f"expected {baseline.iso_country_code_quoted}",
        )
    if baseline.pos is not None and (
        candidate.pos is None or not _tuple_close(candidate.pos, baseline.pos)
    ):
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"pos mismatch: got {candidate.pos!r}, expected {baseline.pos!r}",
        )
    if candidate.trailer_standalone != baseline.trailer_standalone:
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"trailer_standalone mismatch: got {candidate.trailer_standalone!r}, "
            f"expected {baseline.trailer_standalone!r}",
        )

    expected_imperial = slug == "uk"
    if candidate.imperial_units != baseline.imperial_units or (
        bool(candidate.imperial_units) != expected_imperial
    ):
        collector.error(
            "ETS2V2-INV-IDENTITY",
            sui_path,
            f"imperial_units mismatch for {slug!r}: got {candidate.imperial_units!r}, "
            f"expected {baseline.imperial_units!r}",
        )

    # leftside_traffic must match baseline strictly (true ONLY for uk among the 36 countries)
    expected_leftside = slug == "uk"
    if candidate.leftside_traffic != baseline.leftside_traffic or (
        bool(candidate.leftside_traffic) != expected_leftside
    ):
        collector.error(
            "ETS2V2-INV-LEFTSIDE",
            sui_path,
            f"leftside_traffic violation for {slug!r}: got {candidate.leftside_traffic!r}, "
            f"expected {baseline.leftside_traffic!r}",
        )

    # regions[] & region_areas[] verbatim baseline preservation (bosnia/finland/norway/spain/sweden)
    if candidate.regions != baseline.regions or not _areas_close(
        candidate.region_areas,
        baseline.region_areas,
    ):
        collector.error(
            "ETS2V2-INV-REGIONS",
            sui_path,
            f"regions[]/region_areas[] drifted from 1.62 baseline for {slug!r} "
            f"(got {len(candidate.regions)} regions/{len(candidate.region_areas)} areas, "
            f"expected {len(baseline.regions)}/{len(baseline.region_areas)})",
        )

    # secondary_time_zone* preservation (russia Kaliningrad)
    if (
        candidate.secondary_time_zone != baseline.secondary_time_zone
        or candidate.secondary_time_zone_name != baseline.secondary_time_zone_name
        or not _areas_close(candidate.secondary_time_zone_area, baseline.secondary_time_zone_area)
    ):
        collector.error(
            "ETS2V2-INV-SECONDARY-TZ",
            sui_path,
            f"secondary_time_zone* drifted from 1.62 baseline for {slug!r}",
        )

    # Zero axle truncations or downgrades vs 1.62 baseline
    cand_axles = candidate.mass_limit_per_axle_count
    base_axles = baseline.mass_limit_per_axle_count
    if len(cand_axles) < len(base_axles):
        collector.error(
            "ETS2V2-INV-AXLE",
            sui_path,
            f"mass_limit_per_axle_count[] truncated for {slug!r}: "
            f"got {len(cand_axles)} entries, baseline requires >= {len(base_axles)}",
        )
    else:
        for idx, base_limit in enumerate(base_axles):
            if cand_axles[idx] < base_limit:
                collector.error(
                    "ETS2V2-INV-AXLE",
                    sui_path,
                    f"mass_limit_per_axle_count[{idx}] downgraded for {slug!r}: "
                    f"got {cand_axles[idx]}, baseline requires >= {base_limit}",
                )
    if cand_axles != sorted(cand_axles):
        collector.error(
            "ETS2V2-INV-AXLE",
            sui_path,
            f"mass_limit_per_axle_count[] is not non-decreasing for {slug!r}: {cand_axles}",
        )

    # Iceland 5-element 60t axle ceiling invariant
    if slug == "iceland" and cand_axles != _ICELAND_AXLES:
        collector.error(
            "ETS2V2-INV-ICELAND",
            sui_path,
            f"Iceland mass_limit_per_axle_count[] must be {_ICELAND_AXLES}, got {cand_axles}",
        )

    # @@tz_*@@ 12-key whitelist compliance (no @@tz_cet@@ / @@tz_wet@@ / raw numeric "+03")
    tz_values: list[str] = []
    if candidate.time_zone_name is not None:
        tz_values.append(candidate.time_zone_name)
    tz_values.extend(candidate.secondary_time_zone_name)

    for tz_val in tz_values:
        if not tz_val.strip() or _NUMERIC_TZ_RE.fullmatch(tz_val.strip()) is not None:
            collector.error(
                "ETS2V2-INV-TZ-TOKEN",
                sui_path,
                f"Invalid or numeric-only time_zone_name {tz_val!r} for {slug!r}",
            )
        for match in _TZ_TOKEN_RE.finditer(tz_val):
            token_key = match.group(1)
            if token_key not in allowed_tz_keys:
                collector.error(
                    "ETS2V2-INV-TZ-TOKEN",
                    sui_path,
                    f"Unsupported localization token '@@{token_key}@@' in time_zone_name "
                    f"{tz_val!r} for {slug!r} (not in 1.62 12-key locales.json whitelist)",
                )


def _check_speed_limits_invariants(
    slug: str,
    candidate: SpeedLimitsFile,
    baseline: BaselineSpeedLimit,
    spd_path: str,
    collector: ValidationCollector,
) -> None:
    base_by_class = {block.vehicle_speed_class: block for block in baseline.blocks}

    for road_cls in _REQUIRED_ROAD_CLASSES:
        cand_block = candidate.get_block(road_cls)
        if cand_block is None or not cand_block.lanes:
            collector.error(
                "ETS2V2-INV-SPEED-BLOCKS",
                spd_path,
                f"Missing required {road_cls!r} speed limit block for {slug!r}",
            )
            continue

        base_block = base_by_class.get(road_cls)
        if base_block is not None:
            base_lane_order = [lane.lane_speed_class for lane in base_block.lanes]
            cand_lane_order = [lane.lane_speed_class for lane in cand_block.lanes]
            if cand_lane_order != base_lane_order:
                collector.error(
                    "ETS2V2-INV-SPEED-BLOCKS",
                    spd_path,
                    f"lane_speed_class[] sequence mismatch in {road_cls!r} block for {slug!r}: "
                    f"got {cand_lane_order!r}, expected {base_lane_order!r}",
                )
                continue

            for base_lane, cand_lane in zip(base_block.lanes, cand_block.lanes, strict=True):
                lane_name = base_lane.lane_speed_class
                if lane_name == "slow_road" and cand_lane != base_lane:
                    collector.error(
                        "ETS2V2-INV-SPEED-BLOCKS",
                        spd_path,
                        f"slow_road lane drifted from baseline in {road_cls!r} for {slug!r}: "
                        f"got {cand_lane!r}, expected {base_lane!r}",
                    )
                    continue
                if cand_lane.uncommon != base_lane.uncommon:
                    collector.error(
                        "ETS2V2-INV-SPEED-BLOCKS",
                        spd_path,
                        f"uncommon flag drifted on {lane_name!r} in {road_cls!r} for {slug!r}: "
                        f"got {cand_lane.uncommon!r}, expected {base_lane.uncommon!r}",
                    )
                if (cand_lane.max_limit is None) != (base_lane.max_limit is None):
                    collector.error(
                        "ETS2V2-INV-SPEED-BLOCKS",
                        spd_path,
                        f"max_limit nullability mismatch on {lane_name!r} in {road_cls!r} "
                        f"for {slug!r}: got {cand_lane.max_limit!r}, "
                        f"expected {'None' if base_lane.max_limit is None else 'non-None'}",
                    )

    for rail_cls in _RAIL_CLASSES:
        base_rail = base_by_class.get(rail_cls)
        if base_rail is None:
            continue
        cand_rail = candidate.get_block(rail_cls)
        if cand_rail is None:
            collector.error(
                "ETS2V2-INV-SPEED-BLOCKS",
                spd_path,
                f"Missing baseline {rail_cls!r} speed block for {slug!r}",
            )
        elif cand_rail != base_rail:
            collector.error(
                "ETS2V2-INV-SPEED-BLOCKS",
                spd_path,
                f"Baseline {rail_cls!r} speed block modified for {slug!r}",
            )

    if slug == "iceland":
        truck_block = candidate.get_block("truck")
        if truck_block is None:
            collector.error(
                "ETS2V2-INV-ICELAND",
                spd_path,
                "Missing truck speed limit block for Iceland",
            )
        else:
            for lane in truck_block.lanes:
                if (
                    lane.limit != _ICELAND_HEAVY_TRUCK_LIMIT
                    or lane.max_limit != _ICELAND_HEAVY_TRUCK_LIMIT
                ):
                    collector.error(
                        "ETS2V2-INV-ICELAND",
                        spd_path,
                        f"Iceland heavy truck limit on {lane.lane_speed_class!r} must be "
                        f"{_ICELAND_HEAVY_TRUCK_LIMIT} km/h "
                        f"(got limit={lane.limit}, max_limit={lane.max_limit})",
                    )


def validate_core_realism_invariants(
    country_models: Mapping[str, CountryDataModel],
    speed_models: Mapping[str, SpeedLimitsFile],
    baseline_countries: CountriesBaseline,
    baseline_speed_limits: SpeedLimitsBaseline,
    baseline_locales: LocalesBaseline,
    collector: ValidationCollector,
    *,
    path_prefix: str = "",
) -> None:
    """Audit parsed Core country and speed-limit models against ETS2 1.62 realism invariants."""
    rel_prefix = f"{path_prefix}/" if path_prefix else ""
    base_countries_by_slug = {c.slug: c for c in baseline_countries.countries}
    base_speeds_by_slug = {s.slug: s for s in baseline_speed_limits.speed_limits}
    expected_slugs = frozenset(base_countries_by_slug)
    allowed_tz_keys = frozenset(baseline_locales.tz_keys)

    actual_country_slugs = frozenset(country_models)
    actual_speed_slugs = frozenset(speed_models)

    if actual_country_slugs != expected_slugs:
        missing = sorted(expected_slugs - actual_country_slugs)
        extra = sorted(actual_country_slugs - expected_slugs)
        collector.error(
            "ETS2V2-INV-COUNTRY-COUNT",
            f"{rel_prefix}def/country",
            f"Expected exact {len(expected_slugs)} Vanilla+DLC countries "
            f"(missing={missing}, extra={extra})",
        )

    if actual_speed_slugs != expected_slugs:
        missing_spd = sorted(expected_slugs - actual_speed_slugs)
        extra_spd = sorted(actual_speed_slugs - expected_slugs)
        collector.error(
            "ETS2V2-INV-COUNTRY-COUNT",
            f"{rel_prefix}def/country",
            f"Expected exact {len(expected_slugs)} speed_limits.sii files "
            f"(missing={missing_spd}, extra={extra_spd})",
        )

    seen_ids: dict[int, str] = {}
    seen_units: dict[str, str] = {}
    for slug in sorted(country_models):
        model = country_models[slug]
        sui_path = f"{rel_prefix}def/country/{slug}.sui"
        if model.country_id in seen_ids:
            collector.error(
                "ETS2V2-INV-COUNTRY-COUNT",
                sui_path,
                f"Duplicate country_id {model.country_id} shared by {seen_ids[model.country_id]!r} "
                f"and {slug!r}",
            )
        else:
            seen_ids[model.country_id] = slug

        if model.unit_name in seen_units:
            collector.error(
                "ETS2V2-INV-COUNTRY-COUNT",
                sui_path,
                f"Duplicate unit_name {model.unit_name!r} shared by "
                f"{seen_units[model.unit_name]!r} and {slug!r}",
            )
        else:
            seen_units[model.unit_name] = slug

        base_country = base_countries_by_slug.get(slug)
        if base_country is not None:
            _check_country_identity_and_laws(
                slug,
                model,
                base_country,
                allowed_tz_keys,
                sui_path,
                collector,
            )

    for slug in sorted(speed_models):
        base_speed = base_speeds_by_slug.get(slug)
        if base_speed is None:
            continue
        spd_path = f"{rel_prefix}def/country/{slug}/speed_limits.sii"
        _check_speed_limits_invariants(
            slug,
            speed_models[slug],
            base_speed,
            spd_path,
            collector,
        )
