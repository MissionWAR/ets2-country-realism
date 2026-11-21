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
    FuelBoardEntry,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.sii.country import CountryDataModel
from ets2v2.sii.localization import LocalizationEntry
from ets2v2.sii.sign_board import SignBoardTemplate
from ets2v2.sii.speed_limits import SpeedLimitsFile
from ets2v2.validate.models import ValidationCollector

_TZ_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"@@([^@]+)@@")
_NUMERIC_TZ_RE: Final[re.Pattern[str]] = re.compile(r"^[+-]\d{2}(?::?\d{2})?$")
_TOTEM_TOKEN_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$")
_TOTEM_VALUE_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+(?:\.[0-9]+)?(?:<sup>[0-9]</sup>)?$")
_ICELAND_AXLES: Final[list[int]] = [18000, 29000, 38000, 46000, 60000]
_ICELAND_HEAVY_TRUCK_LIMIT: Final[int] = 80
_REQUIRED_ROAD_CLASSES: Final[tuple[str, ...]] = ("car", "truck", "bus")
_RAIL_CLASSES: Final[tuple[str, ...]] = ("train", "tram")
_FLOAT_TOL: Final[float] = 1e-5
_D09_EXACT_BOARD_TOKEN_BASES: Final[dict[str, str]] = {
    "gas_is_ip1_98": "fp_is_petrol_98",
    "gas_is_yokull_95": "fp_is_petrol_95",
    "gas_is_yokull_diesel": "fp_is_diesel",
    "gas_ba_apus_lpg": "fp_ba_lpg",
    "gas_ba_bts_lpg": "fp_ba_lpg",
    "gas_dk_92": "fp_dk_petrol_92",
}


def _float_close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=_FLOAT_TOL, abs_tol=_FLOAT_TOL)


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


def _token_matches_base(token: str, token_base: str) -> bool:
    return token in {
        f"{token_base}_ets2v2",
        f"{token_base}_3_ets2v2",
        f"{token_base}_c_ets2v2",
    }


def _check_single_totem_board(
    board_name: str,
    candidate: SignBoardTemplate,
    baseline: FuelBoardEntry,
    canonical_tokens: frozenset[str],
    board_path: str,
    collector: ValidationCollector,
) -> str | None:
    if not candidate.is_single_text_fuel_candidate or len(candidate.text_slots) != 1:
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"Board {board_name!r} is not a single-text empty-model fuel totem "
            f"(model_name={candidate.model_name!r}, items_count={candidate.items_count}, "
            f"slots={len(candidate.text_slots)})",
        )
        return None

    if candidate.unit_name != baseline.unit_name:
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"unit_name mismatch on {board_name!r}: got {candidate.unit_name!r}, "
            f"expected {baseline.unit_name!r}",
        )
    if candidate.board_name != baseline.template_board_name:
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"board_name mismatch on {board_name!r}: got {candidate.board_name!r}, "
            f"expected {baseline.template_board_name!r}",
        )
    if not _float_close(candidate.width, baseline.width):
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"width mismatch on {board_name!r}: got {candidate.width!r}, "
            f"expected {baseline.width!r}",
        )
    if not _float_close(candidate.height, baseline.height):
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"height mismatch on {board_name!r}: got {candidate.height!r}, "
            f"expected {baseline.height!r}",
        )
    if candidate.dynamic_attributes != baseline.dynamic_attributes:
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"dynamic_attributes mismatch on {board_name!r}: got {candidate.dynamic_attributes!r}, "
            f"expected {baseline.dynamic_attributes!r}",
        )

    slot = candidate.text_slots[0]
    base_slot = baseline.slot

    discrete_checks: tuple[tuple[str, object, object], ...] = (
        ("slot.unit_name", slot.unit_name, base_slot.unit_name),
        ("font_face", slot.font_face, base_slot.font_face),
        ("text_halign", slot.text_halign, base_slot.text_halign),
        ("text_valign", slot.text_valign, base_slot.text_valign),
        ("font_color", slot.font_color, base_slot.font_color),
        ("id", slot.text_id, base_slot.text_id),
        ("area_name", slot.area_name, base_slot.area_name),
        ("area_idx", slot.area_idx, base_slot.area_idx),
        ("z_order", slot.z_order, base_slot.z_order),
        ("tag", slot.tag, base_slot.tag),
    )
    for attr_name, actual_val, expected_val in discrete_checks:
        if actual_val != expected_val:
            collector.error(
                "ETS2V2-INV-TOTEM-BOARDS",
                board_path,
                f"{attr_name} drifted on {board_name!r}: got {actual_val!r}, "
                f"expected {expected_val!r}",
            )

    float_checks: tuple[tuple[str, float | None, float | None], ...] = (
        ("font_size", slot.font_size, base_slot.font_size),
        ("font_opacity", slot.font_opacity, base_slot.font_opacity),
        ("line_spacing", slot.line_spacing, base_slot.line_spacing),
        ("letter_spacing", slot.letter_spacing, base_slot.letter_spacing),
        ("coords_l", slot.coords_l, base_slot.coords_l),
        ("coords_r", slot.coords_r, base_slot.coords_r),
        ("coords_t", slot.coords_t, base_slot.coords_t),
        ("coords_b", slot.coords_b, base_slot.coords_b),
    )
    for attr_name, actual_f, expected_f in float_checks:
        if not _float_close(actual_f, expected_f):
            collector.error(
                "ETS2V2-INV-TOTEM-BOARDS",
                board_path,
                f"{attr_name} drifted on {board_name!r}: got {actual_f!r}, expected {expected_f!r}",
            )

    if slot.font_opacity is None or not math.isclose(slot.font_opacity, 1.0, abs_tol=_FLOAT_TOL):
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"font_opacity on identifiable board {board_name!r} must be 1.0, "
            f"got {slot.font_opacity!r}",
        )

    token = slot.localization_key
    if token is None or _TOTEM_TOKEN_KEY_RE.fullmatch(token) is None or slot.text != f"@@{token}@@":
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"Invalid totem localization reference {slot.text!r} on {board_name!r}; "
            "expected @@fp_<cc>_<grade>[_<variant>]_ets2v2@@",
        )
        return None

    if canonical_tokens and token not in canonical_tokens:
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"Dangling totem token {token!r} on {board_name!r} missing from "
            "local_module.ets2v2_fuel.sii",
        )

    # Explicit D-09 regression checks
    expected_base = _D09_EXACT_BOARD_TOKEN_BASES.get(board_name)
    if expected_base is not None and not _token_matches_base(token, expected_base):
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"D-09 mapping regression on {board_name!r}: got {token!r}, "
            f"expected base {expected_base!r}",
        )
    if board_name.startswith("gas_ie_") and not token.startswith("fp_ie_"):
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"D-09 Irish board {board_name!r} must map to fp_ie_*, got {token!r}",
        )
    if board_name.startswith("gas_bi_") and not token.startswith("fp_gb_"):
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            board_path,
            f"D-09 British Isles board {board_name!r} must map to fp_gb_*, got {token!r}",
        )

    return token


def validate_fuel_locale_modules_consistency(
    fuel_locales: Mapping[str, Sequence[LocalizationEntry]],
    collector: ValidationCollector,
    *,
    expected_locales: frozenset[str] | None = None,
    path_prefix: str = "",
) -> frozenset[str]:
    """Validate D-12 fuel locale module parity, key/value hygiene, and fr_qc exclusion."""
    rel_prefix = f"{path_prefix}/" if path_prefix else ""

    if "fr_qc" in fuel_locales:
        collector.error(
            "ETS2V2-INV-LOCALE-SYNC",
            f"{rel_prefix}locale/fr_qc/local_module.ets2v2_fuel.sii",
            "Deprecated locale 'fr_qc' must not be emitted (D-09 / D-12)",
        )

    if expected_locales is not None:
        actual_locales = frozenset(fuel_locales)
        if actual_locales != expected_locales:
            missing = sorted(expected_locales - actual_locales)
            extra = sorted(actual_locales - expected_locales)
            collector.error(
                "ETS2V2-INV-LOCALE-SYNC",
                f"{rel_prefix}locale",
                f"Expected exact {len(expected_locales)} active fuel locale modules "
                f"(missing={missing}, extra={extra})",
            )

    reference_lang: str | None = None
    reference_pairs: list[tuple[str, str]] | None = None
    canonical_tokens: frozenset[str] = frozenset()

    for lang in sorted(fuel_locales):
        loc_path = f"{rel_prefix}locale/{lang}/local_module.ets2v2_fuel.sii"
        entries = list(fuel_locales[lang])
        if not entries:
            collector.error(
                "ETS2V2-INV-LOCALE-SYNC",
                loc_path,
                f"Fuel locale module for {lang!r} has zero key/val entries",
            )
            continue

        keys = [entry.key for entry in entries]
        if len(keys) != len(set(keys)):
            seen: set[str] = set()
            dup_set: set[str] = set()
            for k in keys:
                if k in seen:
                    dup_set.add(k)
                else:
                    seen.add(k)
            dups = sorted(dup_set)
            collector.error(
                "ETS2V2-INV-LOCALE-SYNC",
                loc_path,
                f"Duplicate localization keys in {lang!r}: {dups}",
            )

        if keys != sorted(keys):
            collector.error(
                "ETS2V2-INV-LOCALE-SYNC",
                loc_path,
                f"Localization keys in {lang!r} are not strictly sorted",
            )

        for entry in entries:
            if _TOTEM_TOKEN_KEY_RE.fullmatch(entry.key) is None:
                collector.error(
                    "ETS2V2-INV-LOCALE-SYNC",
                    loc_path,
                    f"Invalid fuel localization key {entry.key!r}; "
                    "expected ^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$",
                )
            if not entry.val or _TOTEM_VALUE_RE.fullmatch(entry.val) is None:
                collector.error(
                    "ETS2V2-INV-LOCALE-SYNC",
                    loc_path,
                    f"Invalid fuel localization value {entry.val!r} for key {entry.key!r}; "
                    "only digits, uniform '.', and optional <sup>[0-9]</sup> allowed",
                )

        pairs = [(entry.key, entry.val) for entry in entries]
        if reference_pairs is None:
            reference_lang = lang
            reference_pairs = pairs
            canonical_tokens = frozenset(keys)
        elif pairs != reference_pairs:
            collector.error(
                "ETS2V2-INV-LOCALE-SYNC",
                loc_path,
                f"Locale {lang!r} fuel entries diverge from reference locale {reference_lang!r}",
            )

    return canonical_tokens


def validate_totem_invariants(
    sign_boards: Mapping[str, SignBoardTemplate],
    fuel_locales: Mapping[str, Sequence[LocalizationEntry]],
    baseline_fuel_boards: FuelBoardsBaseline,
    baseline_locales: LocalesBaseline,
    collector: ValidationCollector,
    *,
    path_prefix: str = "",
) -> None:
    """Audit emitted Option 4b fuel totem boards and 43 locale modules against D-12 invariants."""
    rel_prefix = f"{path_prefix}/" if path_prefix else ""
    expected_locales = frozenset(baseline_locales.active_locales)

    canonical_tokens = validate_fuel_locale_modules_consistency(
        fuel_locales,
        collector,
        expected_locales=expected_locales,
        path_prefix=path_prefix,
    )

    excluded_highways = frozenset(baseline_fuel_boards.excluded_fuel_keyword_boards)
    base_by_name = {board.board_name: board for board in baseline_fuel_boards.boards}
    spacers = frozenset(
        board.board_name
        for board in baseline_fuel_boards.boards
        if board.board_name == "gas_empty"
        or (board.slot.font_size == 0.0 and board.slot.font_opacity == 0.0)
    )
    expected_boards = frozenset(
        name for name in base_by_name if name not in spacers and name not in excluded_highways
    )

    for spacer in sorted(spacers):
        if spacer in sign_boards:
            collector.error(
                "ETS2V2-INV-TOTEM-BOARDS",
                f"{rel_prefix}def/sign/board/{spacer}.sii",
                f"Structural spacer board {spacer!r} must not be emitted (D-09 / D-12)",
            )

    for hw in sorted(excluded_highways):
        if hw in sign_boards:
            collector.error(
                "ETS2V2-INV-TOTEM-BOARDS",
                f"{rel_prefix}def/sign/board/{hw}.sii",
                f"Excluded multi-item highway sign {hw!r} must not be emitted (D-09 / D-12)",
            )

    actual_boards = frozenset(sign_boards)
    if actual_boards != expected_boards:
        missing = sorted(expected_boards - actual_boards)
        extra = sorted(actual_boards - expected_boards)
        collector.error(
            "ETS2V2-INV-TOTEM-BOARDS",
            f"{rel_prefix}def/sign/board",
            f"Expected exact {len(expected_boards)} identifiable fuel boards "
            f"(got {len(actual_boards)}; missing={missing[:10]}, extra={extra[:10]})",
        )

    referenced_tokens: set[str] = set()
    for board_name in sorted(sign_boards):
        baseline = base_by_name.get(board_name)
        if baseline is None or board_name in spacers or board_name in excluded_highways:
            continue
        board_path = f"{rel_prefix}def/sign/board/{board_name}.sii"
        resolved_token = _check_single_totem_board(
            board_name,
            sign_boards[board_name],
            baseline,
            canonical_tokens,
            board_path,
            collector,
        )
        if resolved_token is not None:
            referenced_tokens.add(resolved_token)

    if canonical_tokens and sign_boards:
        orphans = sorted(canonical_tokens - referenced_tokens)
        if orphans:
            collector.error(
                "ETS2V2-INV-TOTEM-BOARDS",
                f"{rel_prefix}locale",
                f"Orphan unused totem localization keys in local_module.ets2v2_fuel.sii: "
                f"{orphans[:10]}",
            )
