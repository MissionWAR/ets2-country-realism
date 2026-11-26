"""Deterministic UTF-8 no-BOM LF Markdown changelog renderer for Summer and Winter editions."""

from __future__ import annotations

from typing import Final

from ets2v2.normalize.currencies import (
    CORE_REFERENCE_FX_RATES,
    EXTENDED_GLOBAL_CURRENCIES,
    VANILLA_36_ISO2S,
)
from ets2v2.normalize.lockfile import CURATED_TIER3_SOURCES
from ets2v2.normalize.models import LockAlert, PricesLockfile
from ets2v2.normalize.totem_format import format_national_pump_price
from ets2v2.publish.ledger import PublishedEditionState
from ets2v2.registry.models import LaneSpeedOverride, RoadVehicleClass, Season
from ets2v2.registry.snapshot import RealismSnapshot, RealismSnapshotCountry

_VEHICLE_ORDER: tuple[RoadVehicleClass, ...] = ("car", "truck", "bus")
_MAX_ALERT_DETAIL_LEN: int = 240
_EXTENDED_FX_ROLLUP_THRESHOLD: Final[int] = 20
_EXTENDED_FX_ALERT_ROLLUP_THRESHOLD: Final[int] = 5

_EU_TIER1_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "ec_weekly_oil_bulletin",
        "uk_desnz",
        "no_ssb_09654",
        "fr_economie_ods",
        "de_tankerkoenig",
        "es_miteco",
        "it_mimit",
        "nl_cbs_80416ned",
        "fionnhughes_ec_wob",
        "fuel_prices_eu",
    }
)
_GLOBAL_TIER1_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "us_eia_v2",
        "br_anp",
        "ar_energia",
        "co_sicom",
        "co_creg",
        "cl_cne",
        "my_opendosm",
        "jp_meti",
        "kr_opinet",
    }
)
_TIER2_PORTAL_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "is_gasvaktin",
        "ch_bfs_lik",
        "md_anre",
        "mk_erc",
        "ru_rosstat",
        "il_moe",
        "ae_moei",
        "za_dmre_cef",
        "sa_aramco",
        "ng_nbs",
    }
)


def _sanitize_markdown_inline(text: str, *, max_len: int = _MAX_ALERT_DETAIL_LEN) -> str:
    """Collapse whitespace/newlines and neutralize backticks, HTML, pipes, and brackets."""
    collapsed = " ".join(text.split())
    escaped = (
        collapsed.replace("`", "'")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "\\|")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )
    if len(escaped) > max_len:
        return escaped[:max_len].rstrip("\\")
    return escaped


def _format_markdown_local_price(iso2: str, price: float | None) -> str:
    if price is None:
        return "—"
    raw = format_national_pump_price(iso2, price, variant="standard")
    return raw.replace("<sup>", "").replace("</sup>", "")


def _render_fuel_summary_table(
    snapshot: RealismSnapshot,
    prices_lock: PricesLockfile | None,
) -> list[str]:
    if set(snapshot.countries) >= VANILLA_36_ISO2S:
        table_iso2s = sorted(iso2 for iso2 in snapshot.countries if iso2 in VANILLA_36_ISO2S)
    else:
        table_iso2s = sorted(snapshot.countries)

    lines: list[str] = [
        f"## {len(table_iso2s)}-Country Fuel Price Summary",
        "",
        "| ISO2 | Currency | EUR/L Diesel | Local Diesel | Local 95 | Source | Freshness |",
        "|------|----------|-------------:|-------------:|---------:|--------|-----------|",
    ]
    for iso2 in table_iso2s:
        country = snapshot.countries[iso2]
        lock_entry = prices_lock.countries.get(iso2) if prices_lock is not None else None
        local_diesel_val = country.fuel.local_prices.get("diesel")
        local_95_val = country.fuel.local_prices.get("petrol_95")
        if local_diesel_val is None and lock_entry is not None:
            local_diesel_val = lock_entry.local_prices.get("diesel")
        if local_95_val is None and lock_entry is not None:
            local_95_val = lock_entry.local_prices.get("petrol_95")

        currency_str = "GBP (p/L)" if iso2 == "GB" else country.fuel.currency
        eur_str = f"{country.fuel.eur_per_liter:.3f}"
        diesel_str = _format_markdown_local_price(iso2, local_diesel_val)
        p95_str = _format_markdown_local_price(iso2, local_95_val)
        source_str = f"`{country.fuel.source}`"
        if lock_entry is not None:
            freshness_str = (
                f"`{lock_entry.data_date}` (fallback)"
                if lock_entry.fallback_used
                else f"`{lock_entry.data_date}`"
            )
        else:
            freshness_str = "`baseline`"
        lines.append(
            f"| `{iso2}` | {currency_str} | {eur_str} | {diesel_str} | {p95_str} | "
            f"{source_str} | {freshness_str} |"
        )
    lines.append("")
    return lines


def _is_extended_fx_warning(alert: LockAlert) -> bool:
    return (
        alert.severity == "warning"
        and alert.code.startswith("fx_")
        and alert.scope in EXTENDED_GLOBAL_CURRENCIES
    )


def _render_alerts_section(
    snapshot: RealismSnapshot,
    prices_lock: PricesLockfile | None,
) -> list[str]:
    if prices_lock is None:
        return []
    tier3_stale_alerts = [a for a in prices_lock.alerts if a.code == "stale_tier3_curated"]
    ext_fx_warnings = [a for a in prices_lock.alerts if _is_extended_fx_warning(a)]
    roll_up_ext_fx = len(ext_fx_warnings) > _EXTENDED_FX_ALERT_ROLLUP_THRESHOLD
    itemized_alerts = [
        a
        for a in prices_lock.alerts
        if a.code != "stale_tier3_curated" and not (roll_up_ext_fx and _is_extended_fx_warning(a))
    ]

    non_tier3_fallback_countries = sorted(
        iso2
        for iso2, entry in prices_lock.countries.items()
        if iso2 in snapshot.countries
        and entry.fallback_used
        and entry.source not in CURATED_TIER3_SOURCES
    )
    tier3_fallback_countries = sorted(
        iso2
        for iso2, entry in prices_lock.countries.items()
        if iso2 in snapshot.countries
        and entry.fallback_used
        and entry.source in CURATED_TIER3_SOURCES
    )
    fallback_fx = sorted(ccy for ccy, fx in prices_lock.fx_rates.items() if fx.fallback_used)
    if (
        not itemized_alerts
        and not tier3_stale_alerts
        and not (roll_up_ext_fx and ext_fx_warnings)
        and not non_tier3_fallback_countries
        and not tier3_fallback_countries
        and not fallback_fx
    ):
        return []

    lines: list[str] = ["## Circuit-Breaker & Staleness Alerts", ""]
    for alert in itemized_alerts:
        safe_code = _sanitize_markdown_inline(alert.code, max_len=64)
        safe_scope = _sanitize_markdown_inline(alert.scope, max_len=64)
        safe_detail = _sanitize_markdown_inline(alert.detail)
        lines.append(
            f"- **[{alert.severity.upper()}] `{safe_code}` (`{safe_scope}`):** {safe_detail}"
        )
    if roll_up_ext_fx and ext_fx_warnings:
        code_counts: dict[str, int] = {}
        for alert in ext_fx_warnings:
            code_counts[alert.code] = code_counts.get(alert.code, 0) + 1
        breakdown = ", ".join(
            f"`{_sanitize_markdown_inline(code, max_len=64)}`={count}"
            for code, count in sorted(code_counts.items())
        )
        lines.append(
            f"- **[WARNING] `extended_fx_alerts` (`extended_fx`):** "
            f"`{len(ext_fx_warnings)}` extended global FX warning alerts ({breakdown})."
        )
    if non_tier3_fallback_countries:
        joined_cc = ", ".join(f"`{iso2}`" for iso2 in non_tier3_fallback_countries)
        lines.append(
            f"- **Fallback/Seeded Countries Retained ({len(non_tier3_fallback_countries)}):** "
            f"{joined_cc}"
        )
    if tier3_fallback_countries or tier3_stale_alerts:
        lines.append(
            f"- **Tier 3 Curated Global Baselines Retained:** `{len(tier3_fallback_countries)}` "
            f"territories (`{len(tier3_stale_alerts)}` overdue >180d)"
        )
    if fallback_fx:
        if len(fallback_fx) > _EXTENDED_FX_ROLLUP_THRESHOLD:
            core_fx = [ccy for ccy in fallback_fx if ccy in CORE_REFERENCE_FX_RATES]
            extended_count = len(fallback_fx) - len(core_fx)
            if core_fx:
                joined_core = ", ".join(f"`{ccy}`" for ccy in core_fx)
                lines.append(
                    f"- **Fallback FX Rates Retained ({len(fallback_fx)}):** "
                    f"Core: {joined_core}, plus `{extended_count}` extended global currencies."
                )
            else:
                lines.append(
                    f"- **Fallback FX Rates Retained ({len(fallback_fx)}):** "
                    f"`{extended_count}` extended global currencies."
                )
        else:
            joined_fx = ", ".join(f"`{ccy}`" for ccy in fallback_fx)
            lines.append(f"- **Fallback FX Rates Retained ({len(fallback_fx)}):** {joined_fx}")
    lines.append("")
    return lines


def _render_global_coverage_section(
    snapshot: RealismSnapshot,
    prices_lock: PricesLockfile | None,
) -> list[str]:
    total = len(snapshot.countries)
    core_count = len(VANILLA_36_ISO2S) if set(snapshot.countries) >= VANILLA_36_ISO2S else total
    live_eu_tier1 = 0
    live_global_tier1 = 0
    live_tier2 = 0
    tier3_curated = 0

    for iso2, country in snapshot.countries.items():
        lock_entry = prices_lock.countries.get(iso2) if prices_lock is not None else None
        source = lock_entry.source if lock_entry is not None else country.fuel.source
        fallback_used = lock_entry.fallback_used if lock_entry is not None else False

        if source in CURATED_TIER3_SOURCES:
            tier3_curated += 1
        elif not fallback_used and source in _GLOBAL_TIER1_SOURCES:
            live_global_tier1 += 1
        elif not fallback_used and source in _TIER2_PORTAL_SOURCES:
            live_tier2 += 1
        elif not fallback_used and source in _EU_TIER1_SOURCES:
            live_eu_tier1 += 1

    return [
        "## Global Snapshot Coverage",
        "",
        f"- **Total Snapshot Territories:** `{total}` "
        f"(`{core_count}` Core Vanilla+DLC Workshop countries)",
        f"- **Live Tier 1 EU Coverage:** `{live_eu_tier1}` territories",
        f"- **Live Tier 1 Global Coverage:** `{live_global_tier1}` territories",
        f"- **Live Tier 2 National Portals:** `{live_tier2}` territories",
        f"- **Tier 3 Curated Global Baselines:** `{tier3_curated}` territories",
        "",
    ]


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
    prices_lock: PricesLockfile | None = None,
) -> bytes:
    """Render deterministic UTF-8 no-BOM LF Markdown changelog bytes for one seasonal edition."""
    edition_title = "Summer" if edition == "summer" else "Winter"
    if previous_state is None:
        prev_version = "none (initial release)"
    elif previous_state.package_version == package_version:
        prev_version = "unchanged (forced rebuild)"
    else:
        prev_version = f"`{previous_state.package_version}`"

    if set(snapshot.countries) >= VANILLA_36_ISO2S and len(snapshot.countries) > len(
        VANILLA_36_ISO2S
    ):
        countries_line = (
            f"- **Countries Covered:** `{len(VANILLA_36_ISO2S)}` (Core) / "
            f"`{len(snapshot.countries)}` (Snapshot)"
        )
    else:
        countries_line = f"- **Countries Covered:** `{len(snapshot.countries)}`"

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
        countries_line,
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

    lines.extend(_render_alerts_section(snapshot, prices_lock))
    lines.extend(_render_fuel_summary_table(snapshot, prices_lock))
    lines.extend(_render_global_coverage_section(snapshot, prices_lock))

    lines.extend(
        [
            "## Attribution & Licensing",
            "",
            "- Generator source code is licensed under **MIT**.",
            "- Open statutory realism datasets and generated changelogs are published under "
            "**CC BY 4.0**.",
            "- Open European fuel data: EC Weekly Oil Bulletin CC BY 4.0, fuel-prices.eu "
            "CC BY 4.0, UK DESNZ OGL v3, Norway SSB CC BY 4.0, France Licence Ouverte, "
            "Italy MIMIT IODL 2.0, Spain MITECO, Netherlands CBS, Germany Tankerkönig CC BY 4.0.",
            "- Open Global Tier 1 fuel data: U.S. EIA, Brazil ANP, Argentina Energía, "
            "Colombia MinMinas/CREG, Chile CNE, Malaysia OpenDOSM CC BY 4.0, Japan METI, "
            "Korea KNOC Opinet.",
            "- Open Tier 2 national portals: Iceland Gasvaktin MIT, Switzerland BFS, "
            "Moldova ANRE, North Macedonia ERC, Russia Rosstat, Israel MoE, UAE MOEI, "
            "South Africa DMRE/CEF, Saudi Aramco, Nigeria NBS.",
            "- Open FX reference rates: Frankfurter v2 MIT, ECB, fawazahmed0 CC0.",
            "",
        ]
    )

    return "\n".join(lines).encode("utf-8")
