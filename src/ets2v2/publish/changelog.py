"""Deterministic UTF-8 no-BOM LF Markdown changelog renderer for Summer and Winter editions."""

from __future__ import annotations

from ets2v2.publish.ledger import PublishedEditionState
from ets2v2.registry.models import LaneSpeedOverride, RoadVehicleClass, Season
from ets2v2.registry.snapshot import RealismSnapshot, RealismSnapshotCountry

_VEHICLE_ORDER: tuple[RoadVehicleClass, ...] = ("car", "truck", "bus")


def _format_lane_override(lane: LaneSpeedOverride) -> str:
    token = f"{lane.limit}({lane.urban_limit})"
    if lane.max_limit is not None and lane.max_limit != lane.limit:
        token += f"[max={lane.max_limit}]"
    if lane.uncommon is not None:
        token += f"[uncommon={str(lane.uncommon).lower()}]"
    return token


def _format_speed_summary(country: RealismSnapshotCountry) -> str:
    unit = "mph" if country.imperial_units else "km/h"
    parts: list[str] = []
    for vclass in _VEHICLE_ORDER:
        lanes = country.speed_limits.get(vclass, [])
        lane_str = "/".join(_format_lane_override(lane) for lane in lanes)
        parts.append(f"{vclass}={lane_str}")
    return f"{'; '.join(parts)} {unit}"


def _diff_country(
    prev: RealismSnapshotCountry,
    curr: RealismSnapshotCountry,
) -> list[str]:
    changes: list[str] = []
    if prev.time_zone != curr.time_zone or prev.time_zone_name != curr.time_zone_name:
        changes.append(
            f"timezone: `{prev.time_zone:+d}m ({prev.time_zone_name})` -> "
            f"`{curr.time_zone:+d}m ({curr.time_zone_name})`"
        )
    if prev.lights_mandatory != curr.lights_mandatory:
        changes.append(
            f"lights_mandatory: `{str(prev.lights_mandatory).lower()}` -> "
            f"`{str(curr.lights_mandatory).lower()}`"
        )
    if prev.driving_tired_offence != curr.driving_tired_offence:
        changes.append(
            f"driving_tired_offence: `{str(prev.driving_tired_offence).lower()}` -> "
            f"`{str(curr.driving_tired_offence).lower()}`"
        )
    if prev.mass_limit_per_axle_count != curr.mass_limit_per_axle_count:
        changes.append(
            f"mass_limit_per_axle_count: `{prev.mass_limit_per_axle_count}` -> "
            f"`{curr.mass_limit_per_axle_count}`"
        )
    if prev.speed_limits != curr.speed_limits:
        changes.append(
            f"speed_limits: `{_format_speed_summary(prev)}` -> `{_format_speed_summary(curr)}`"
        )
    if prev.fuel != curr.fuel:
        fuel_parts: list[str] = []
        if (
            prev.fuel.eur_per_liter != curr.fuel.eur_per_liter
            or prev.fuel.source != curr.fuel.source
            or prev.fuel.currency != curr.fuel.currency
        ):
            fuel_parts.append(
                f"`{prev.fuel.eur_per_liter} EUR/L [{prev.fuel.currency}] ({prev.fuel.source})` "
                f"-> `{curr.fuel.eur_per_liter} EUR/L [{curr.fuel.currency}] ({curr.fuel.source})`"
            )
        if prev.fuel.local_prices != curr.fuel.local_prices:
            all_grades = sorted(set(prev.fuel.local_prices) | set(curr.fuel.local_prices))
            grade_diffs = [
                (
                    f"{grade}: {prev.fuel.local_prices.get(grade)} -> "
                    f"{curr.fuel.local_prices.get(grade)}"
                )
                for grade in all_grades
                if prev.fuel.local_prices.get(grade) != curr.fuel.local_prices.get(grade)
            ]
            fuel_parts.append(f"local_prices({', '.join(grade_diffs)})")
        changes.append(f"fuel: {'; '.join(fuel_parts)}")
    return changes


def _render_snapshot_diff_lines(
    previous_snapshot: RealismSnapshot,
    current_snapshot: RealismSnapshot,
) -> list[str]:
    prev_keys = set(previous_snapshot.countries)
    curr_keys = set(current_snapshot.countries)
    added = sorted(curr_keys - prev_keys)
    removed = sorted(prev_keys - curr_keys)
    common = sorted(prev_keys & curr_keys)

    lines: list[str] = ["## Changes Since Previous Snapshot", ""]
    has_any = False

    if added:
        has_any = True
        for iso2 in added:
            country = current_snapshot.countries[iso2]
            lines.append(f"- **Added `{iso2}` (`{country.ets2_slug}`)**")

    if removed:
        has_any = True
        for iso2 in removed:
            country = previous_snapshot.countries[iso2]
            lines.append(f"- **Removed `{iso2}` (`{country.ets2_slug}`)**")

    for iso2 in common:
        prev_c = previous_snapshot.countries[iso2]
        curr_c = current_snapshot.countries[iso2]
        field_diffs = _diff_country(prev_c, curr_c)
        if field_diffs:
            has_any = True
            joined = "; ".join(field_diffs)
            lines.append(f"- **`{iso2}` (`{curr_c.ets2_slug}`)**: {joined}")

    if not has_any:
        lines.append(
            "- No country law field changes (packaging metadata, description, or icon update)."
        )

    lines.append("")
    return lines


def _render_initial_highlights(edition: Season, snapshot: RealismSnapshot) -> list[str]:
    season_label = "Summer" if edition == "summer" else "Winter"
    dst_summary = (
        "Dynamic July 15 DST offsets (`@@tz_cest@@`, `@@tz_eest@@`, `@@tz_west@@`, `@@tz_bst@@`, "
        "`@@tz_gmt@@`, `@@tz_msk@@`, `@@tz_trt@@`) computed via stdlib `zoneinfo` + `tzdata`."
        if edition == "summer"
        else "Dynamic January 15 standard-time offsets (`CET`, `WET`, `@@tz_eet@@`, `@@tz_gmt@@`, "
        "`@@tz_msk@@`, `@@tz_trt@@`) respecting ETS2 1.62's 12-key `@@tz_*@@` whitelist."
    )
    seasonal_speed_summary = (
        "Summer statutory road speed ceilings across all 36 Vanilla+DLC countries "
        "(Finland 120/100, Estonia 110, Lithuania 130/120, Austria 100 expressway, "
        "Hungary 70 truck expressway, Iceland 80 heavy truck, Turkey 130 motorway)."
        if edition == "summer"
        else "Winter statutory road speed reductions applied in Finland (100/80), Estonia (90), "
        "and Lithuania (110/110), alongside verified statutory fixes for Austria, Hungary, "
        "Iceland (80 km/h heavy truck), and Turkey."
    )
    drl_summary = (
        "Verified statutory daytime running lights (`CH: true`, `NL: false`, `AL: false`, "
        "`TR: false`, and seasonal `HR: false` for Summer)."
        if edition == "summer"
        else "Verified statutory daytime running lights (`CH: true`, `NL: false`, `AL: false`, "
        "`TR: false`, and seasonal `HR: true` for Nov 1 - Mar 31 Winter)."
    )
    return [
        f"## {season_label} Edition Highlights",
        "",
        f"- **Seasonal Timezones ({snapshot.anchor_date}):** {dst_summary}",
        f"- **Statutory Speed Limits:** {seasonal_speed_summary}",
        f"- **Daytime Running Lights:** {drl_summary}",
        "- **ETS2 1.62 Baseline Integrity:** Preserves all 36 Vanilla+DLC country identities, "
        "`regions[]`/`region_areas[]`, Russia Kaliningrad secondary timezone, Iceland 5-axle 60t "
        "and Finland 10-axle HCT mass ladders, `slow_road` rules, and `train`/`tram` rail blocks.",
        "- **Map-Mod Safe Core Layout:** Omits `def/country.sii` to avoid unit registration "
        "conflicts and passes the full Offline SCS Workshop Validator (`00001`-`00010`, "
        "`WARN 00001`/`WARN 00002`, and `1.62` realism invariants).",
        "",
    ]


def render_edition_changelog(
    edition: Season,
    package_version: str,
    payload_sha256: str,
    snapshot_sha256: str,
    snapshot: RealismSnapshot,
    *,
    file_count: int | None = None,
    previous_state: PublishedEditionState | None = None,
    previous_snapshot: RealismSnapshot | None = None,
) -> bytes:
    """Render deterministic UTF-8 no-BOM LF Markdown changelog bytes for one seasonal edition."""
    edition_title = "Summer" if edition == "summer" else "Winter"
    if previous_state is None:
        prev_version = "none (initial release)"
    elif previous_state.package_version == package_version:
        prev_version = "unchanged (forced rebuild)"
    else:
        prev_version = f"`{previous_state.package_version}`"

    lines: list[str] = [
        f"# ETS2 World Country Realism — {edition_title} Edition Changelog",
        "",
        "## Release Summary",
        "",
        f"- **Edition:** `{edition}`",
        f"- **Package Version:** `{package_version}`",
        f"- **Previous Version:** {prev_version}",
        f"- **ETS2 Baseline:** `{snapshot.baseline_game_version}`",
        f"- **Seasonal Anchor Date:** `{snapshot.anchor_date}`",
        f"- **Countries Covered:** `{len(snapshot.countries)}`",
    ]
    if file_count is not None:
        lines.append(f"- **Workshop Files:** `{file_count}`")
    lines.extend(
        [
            f"- **Canonical Payload SHA-256:** `{payload_sha256}`",
            f"- **Realism Snapshot SHA-256:** `{snapshot_sha256}`",
            "",
        ]
    )

    if previous_snapshot is not None:
        lines.extend(_render_snapshot_diff_lines(previous_snapshot, snapshot))
    else:
        lines.extend(_render_initial_highlights(edition, snapshot))

    lines.extend(
        [
            "## Attribution & Licensing",
            "",
            "- Generator source code is licensed under **MIT**.",
            "- Open statutory realism datasets and generated changelogs are published under "
            "**CC BY 4.0**.",
            "",
        ]
    )

    return "\n".join(lines).encode("utf-8")
