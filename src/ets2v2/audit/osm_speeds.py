"""Internal westnordost/osm-legal-default-speeds drift auditor & clean-room allowlist splitter."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal, cast

import httpx
from pydantic import BaseModel

from ets2v2.audit.models import (
    LaneSpeedClass,
    OsmSpeedAuditReport,
    OverpassSpotCheck,
    SpeedAuditAllowlist,
    SpeedAuditAllowlistEntry,
    SpeedDriftFinding,
    SpeedField,
    TaginfoDistribution,
    VehicleSpeedClass,
)
from ets2v2.audit.overpass import (
    fetch_overpass_speed_spot_checks,
    fetch_taginfo_maxspeed_distributions,
)
from ets2v2.fetch.http import (
    DEFAULT_TIMEOUT_SECONDS,
    create_http_client,
    fetch_bytes_with_retry,
)
from ets2v2.registry.loader import load_law_registry
from ets2v2.registry.models import CountryLawRecord

DEFAULT_WESTNORDOST_RULES_URL: Final[str] = (
    "https://westnordost.github.io/osm-legal-default-speeds/legal_default_speeds.json"
)
WESTNORDOST_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"westnordost.github.io", "raw.githubusercontent.com", "github.com"}
)
DEFAULT_ALLOWLIST_PATH: Final[Path] = Path("data/laws/speed_audit_allowlist.json")
DEFAULT_GITHUB_ISSUE_MAX_CHARS: Final[int] = 58_000

_KMH_PER_MPH: Final[float] = 1.609344
_ISO2_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2}$")
_MPH_SPEED_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*mph\b",
    re.IGNORECASE,
)
_KMH_SPEED_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(\d+(?:\.\d+)?)(?:\s*(?:km/h|kmh|kph))?\s*(?:@.*)?$",
    re.IGNORECASE,
)
_CONDITIONAL_NON_GENERAL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:wet|snow|rain|fog|ice|winter|summer|night|dusk|dawn|sunrise|sunset|school|"
    r"mo|tu|we|th|fr|sa|su)\b|\b\d{1,2}:\d{2}\b",
    re.IGNORECASE,
)
_NEGATED_CLAUSE_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[a-z0-9_:-]+\s*(?:!=|!~)\s*(?:'[^']*'|\"[^\"]*\"|[^\s)&|]+)"
)
_SKIP_SUBRULE_TOKENS: Final[tuple[str, ...]] = (
    "living_street",
    "pedestrian",
    "cycleway",
    "footway",
    "service",
    "track",
    "surface=",
    "unpaved",
    "gravel",
    "dirt",
    "lanes=",
    "zone",
    "school",
)
_GENERAL_FILTERS: Final[frozenset[str]] = frozenset(
    {
        "",
        "urban=true",
        "urban=yes",
        "urban=false",
        "urban=no",
        "rural=true",
        "rural=false",
        "roadtype=urban",
        "roadtype=rural",
        "highway=motorway",
        "highway=trunk",
        "motorroad=yes",
        "expressway=yes",
        "dual_carriageway=yes",
        "dual_carriageway=true",
    }
)
_VEHICLE_ORDER: Final[tuple[VehicleSpeedClass, ...]] = ("car", "truck", "bus")
_LANE_ORDER: Final[tuple[LaneSpeedClass, ...]] = ("local_road", "expressway", "motorway")

RoadBucket = Literal["urban", "local_road", "expressway", "motorway"]


def _sanitize_markdown_inline(text: str, *, max_len: int = 240) -> str:
    """Collapse whitespace/newlines and neutralize Markdown links, HTML, backticks, and pipes."""
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


def serialize_audit_report_bytes(model: BaseModel) -> bytes:
    """Serialize an audit report model to deterministic sorted UTF-8 no-BOM LF JSON bytes."""
    payload: object = model.model_dump(mode="json")
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def load_speed_audit_allowlist(path: Path = DEFAULT_ALLOWLIST_PATH) -> SpeedAuditAllowlist:
    """Strictly load clean-room UTF-8 no-BOM LF ``data/laws/speed_audit_allowlist.json`` (D-15)."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise ValueError(f"speed_audit_allowlist.json must be UTF-8 no-BOM LF: {path}")
    return SpeedAuditAllowlist.model_validate_json(raw.decode("utf-8"))


def _parse_osm_speed_value(
    raw_value: object,
    *,
    target_unit: Literal["kmh", "mph"],
) -> tuple[int, str] | None:
    """Normalize an OSM maxspeed value string/number into the country's target speed unit."""
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, (int, float)):
        numeric = float(raw_value)
        if not math.isfinite(numeric) or numeric < 0:
            return None
        converted = round(numeric) if target_unit == "kmh" else round(numeric / _KMH_PER_MPH)
        return (converted, str(raw_value))
    if not isinstance(raw_value, str):
        return None

    text = raw_value.strip()
    if not text:
        return None

    for raw_clause in text.split(";"):
        clause = raw_clause.strip()
        if not clause:
            continue
        if "@" in clause:
            head, condition = clause.split("@", 1)
            head = head.strip()
            if _CONDITIONAL_NON_GENERAL_RE.search(condition) is not None:
                continue
        else:
            head = clause

        lowered = head.lower()
        if lowered in {"walk", "living_street", "implicit", "signals", "variable", "national"}:
            continue
        if lowered in {"none", "unlimited"}:
            return (0, text)

        mph_match = _MPH_SPEED_RE.match(head)
        if mph_match is not None:
            mph_val = float(mph_match.group(1))
            if not math.isfinite(mph_val):
                continue
            converted = round(mph_val) if target_unit == "mph" else round(mph_val * _KMH_PER_MPH)
            return (converted, text)

        kmh_match = _KMH_SPEED_RE.match(head)
        if kmh_match is not None:
            kmh_val = float(kmh_match.group(1))
            if not math.isfinite(kmh_val):
                continue
            converted = round(kmh_val) if target_unit == "kmh" else round(kmh_val / _KMH_PER_MPH)
            return (converted, text)

    return None


def _rule_specificity(rule: dict[str, object]) -> int:
    """Return 0 for unqualified general rules and 1 for rules with additional filter clauses."""
    raw_filter = rule.get("filter")
    flt = " ".join(raw_filter.strip().lower().split()) if isinstance(raw_filter, str) else ""
    positive_flt = " ".join(_NEGATED_CLAUSE_RE.sub("", flt).split())
    cleaned = re.sub(r"^(?:and|or)\b|\b(?:and|or)$", "", positive_flt).strip()
    if cleaned in _GENERAL_FILTERS:
        return 0
    return 1


def _classify_rule_bucket(rule: dict[str, object]) -> RoadBucket | None:
    """Map a westnordost rule object to one of urban / local_road / expressway / motorway."""
    raw_name = rule.get("name")
    name = raw_name.strip().lower() if isinstance(raw_name, str) else ""
    raw_filter = rule.get("filter")
    flt = raw_filter.strip().lower() if isinstance(raw_filter, str) else ""
    positive_flt = _NEGATED_CLAUSE_RE.sub("", flt)
    combined = f"{name} {positive_flt}"

    if any(skip_tok in combined for skip_tok in _SKIP_SUBRULE_TOKENS):
        return None

    is_motorway = name == "motorway" or "highway=motorway" in positive_flt or "motorway" in name
    is_expressway = (
        name in {"trunk", "motorroad", "expressway", "dual_carriageway"}
        or "highway=trunk" in positive_flt
        or "motorroad=yes" in positive_flt
        or "expressway=yes" in positive_flt
        or "dual_carriageway=yes" in positive_flt
        or "dual_carriageway=true" in positive_flt
    )
    is_urban = (
        name in {"urban", "built_up", "built-up", "city"}
        or "urban=true" in positive_flt
        or "urban=yes" in positive_flt
        or "rural=false" in positive_flt
        or "roadtype=urban" in positive_flt
    )

    if is_urban and not is_motorway and not is_expressway:
        return "urban"
    if is_motorway:
        return "motorway"
    if is_expressway:
        return "expressway"
    if (
        name in {"rural", "local_road", "nonurban", "non-urban", "default"}
        or "urban=false" in positive_flt
        or "urban=no" in positive_flt
        or "rural=true" in positive_flt
        or "roadtype=rural" in positive_flt
        or any(
            hw in positive_flt
            for hw in (
                "highway=primary",
                "highway=secondary",
                "highway=tertiary",
                "highway=unclassified",
                "highway=road",
            )
        )
        or (not name and not positive_flt.strip())
    ):
        return "local_road"
    return None


def _extract_rule_tags(rule: dict[str, object]) -> dict[str, object]:
    tags_obj = rule.get("tags")
    if isinstance(tags_obj, dict):
        return cast(dict[str, object], tags_obj)
    return rule


def _extract_osm_country_speeds(
    rules: Sequence[object],
    *,
    target_unit: Literal["kmh", "mph"],
) -> dict[tuple[RoadBucket, VehicleSpeedClass], tuple[int, str]]:
    """Extract normalized OSM speed limits per (road_bucket, vehicle_class) from rule objects."""
    extracted: dict[tuple[RoadBucket, VehicleSpeedClass], tuple[int, str]] = {}
    extracted_specificity: dict[tuple[RoadBucket, VehicleSpeedClass], int] = {}

    for rule_obj in rules:
        if not isinstance(rule_obj, dict):
            continue
        rule = cast(dict[str, object], rule_obj)
        bucket = _classify_rule_bucket(rule)
        if bucket is None:
            continue

        specificity = _rule_specificity(rule)
        tags = _extract_rule_tags(rule)
        tag_candidates: dict[VehicleSpeedClass, tuple[str, ...]] = {
            "car": ("maxspeed",),
            "truck": ("maxspeed:hgv", "maxspeed:hgv:conditional", "maxspeed:goods"),
            "bus": ("maxspeed:bus", "maxspeed:bus:conditional"),
        }

        for vehicle_cls in _VEHICLE_ORDER:
            key = (bucket, vehicle_cls)
            prev_spec = extracted_specificity.get(key)
            if prev_spec is not None and specificity >= prev_spec:
                continue
            for tag_key in tag_candidates[vehicle_cls]:
                if tag_key not in tags:
                    continue
                parsed = _parse_osm_speed_value(tags[tag_key], target_unit=target_unit)
                if parsed is not None:
                    extracted[key] = parsed
                    extracted_specificity[key] = specificity
                    break

    return extracted


def _compare_country_against_osm(
    law: CountryLawRecord,
    country_name: str,
    osm_rules: Sequence[object],
    allowlist_by_key: dict[
        tuple[str, VehicleSpeedClass, LaneSpeedClass, SpeedField],
        SpeedAuditAllowlistEntry,
    ],
) -> tuple[list[SpeedDriftFinding], list[SpeedDriftFinding]]:
    """Compare one CountryLawRecord.summer baseline against parsed OSM rules."""
    unack: list[SpeedDriftFinding] = []
    ack: list[SpeedDriftFinding] = []

    osm_speeds = _extract_osm_country_speeds(osm_rules, target_unit=law.speed_unit)
    summer_limits = law.summer.speed_limits

    for vehicle_cls in _VEHICLE_ORDER:
        lanes_by_class = {
            lane.lane_speed_class: lane for lane in summer_limits.get(vehicle_cls, [])
        }

        # 1. Compare urban default against local_road.urban_limit
        local_lane = lanes_by_class.get("local_road")
        urban_osm = osm_speeds.get(("urban", vehicle_cls))
        if local_lane is not None and urban_osm is not None:
            osm_val, osm_raw = urban_osm
            law_val = local_lane.urban_limit
            if osm_val != law_val:
                key: tuple[str, VehicleSpeedClass, LaneSpeedClass, SpeedField] = (
                    law.iso2,
                    vehicle_cls,
                    "local_road",
                    "urban_limit",
                )
                allow_entry = allowlist_by_key.get(key)
                finding = SpeedDriftFinding(
                    iso2=law.iso2,
                    country_name=country_name,
                    vehicle_class=vehicle_cls,
                    lane_speed_class="local_road",
                    field="urban_limit",
                    speed_unit=law.speed_unit,
                    law_value=law_val,
                    osm_value=osm_val,
                    osm_raw=osm_raw,
                    acknowledged=allow_entry is not None,
                    statutory_rationale=(
                        allow_entry.statutory_rationale if allow_entry is not None else None
                    ),
                    verified_date=allow_entry.verified_date if allow_entry is not None else None,
                )
                if allow_entry is not None:
                    ack.append(finding)
                else:
                    unack.append(finding)

        # 2. Compare rural (local_road), expressway, and motorway limits
        for lane_cls in _LANE_ORDER:
            lane = lanes_by_class.get(lane_cls)
            osm_lane = osm_speeds.get((lane_cls, vehicle_cls))
            if lane is None or osm_lane is None:
                continue
            osm_val, osm_raw = osm_lane
            law_val = lane.limit
            if osm_val != law_val:
                key = (law.iso2, vehicle_cls, lane_cls, "limit")
                allow_entry = allowlist_by_key.get(key)
                finding = SpeedDriftFinding(
                    iso2=law.iso2,
                    country_name=country_name,
                    vehicle_class=vehicle_cls,
                    lane_speed_class=lane_cls,
                    field="limit",
                    speed_unit=law.speed_unit,
                    law_value=law_val,
                    osm_value=osm_val,
                    osm_raw=osm_raw,
                    acknowledged=allow_entry is not None,
                    statutory_rationale=(
                        allow_entry.statutory_rationale if allow_entry is not None else None
                    ),
                    verified_date=allow_entry.verified_date if allow_entry is not None else None,
                )
                if allow_entry is not None:
                    ack.append(finding)
                else:
                    unack.append(finding)

    return unack, ack


def _load_rules_payload(
    *,
    rules_file: Path | None,
    rules_url: str,
    client: httpx.Client | None,
    timeout: float,
    sleep_fn: Callable[[float], None] | None,
) -> tuple[dict[str, Sequence[object]], str]:
    if rules_file is not None:
        raw = rules_file.read_bytes()
        source_label = rules_file.as_posix()
    else:
        owns_client = client is None
        active_client = client if client is not None else create_http_client(timeout=timeout)
        try:
            raw = fetch_bytes_with_retry(
                active_client,
                rules_url,
                allowed_hosts=WESTNORDOST_ALLOWED_HOSTS,
                sleep_fn=sleep_fn,
            )
        finally:
            if owns_client:
                active_client.close()
        source_label = rules_url

    payload_obj: object = json.loads(raw.decode("utf-8"))
    if not isinstance(payload_obj, dict):
        raise ValueError("westnordost rules JSON root must be an object")
    payload = cast(dict[str, object], payload_obj)
    by_code_obj = payload.get("speedLimitsByCountryCode")
    if not isinstance(by_code_obj, dict):
        raise ValueError("westnordost rules JSON missing object 'speedLimitsByCountryCode'")

    by_code: dict[str, Sequence[object]] = {}
    for code_key, rules_val in cast(dict[str, object], by_code_obj).items():
        if _ISO2_RE.fullmatch(code_key) is None:
            continue
        if isinstance(rules_val, list):
            by_code[code_key] = cast(list[object], rules_val)
    return by_code, source_label


def run_osm_speed_audit(
    *,
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    allowlist_path: Path | None = DEFAULT_ALLOWLIST_PATH,
    rules_file: Path | None = None,
    rules_url: str = DEFAULT_WESTNORDOST_RULES_URL,
    iso2_filter: Sequence[str] | None = None,
    include_overpass: bool = False,
    include_taginfo: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> OsmSpeedAuditReport:
    """Compare data/laws/ statutory baselines against westnordost rules & opt-in spot-checks."""
    registry = load_law_registry(laws_dir, mappings_path)
    mappings_by_iso2 = {entry.iso2: entry for entry in registry.mappings.countries}

    allowlist_entries: dict[
        tuple[str, VehicleSpeedClass, LaneSpeedClass, SpeedField],
        SpeedAuditAllowlistEntry,
    ] = {}
    resolved_allowlist_str: str | None = None
    if allowlist_path is not None:
        if not allowlist_path.is_file():
            raise FileNotFoundError(f"Speed audit allowlist file does not exist: {allowlist_path}")
        allowlist = load_speed_audit_allowlist(allowlist_path)
        allowlist_entries = {entry.match_key(): entry for entry in allowlist.entries}
        resolved_allowlist_str = allowlist_path.as_posix()

    if iso2_filter is not None and len(iso2_filter) > 0:
        selected_iso2s: list[str] = []
        seen_iso2s: set[str] = set()
        for raw_code in iso2_filter:
            code = raw_code.strip().upper()
            if _ISO2_RE.fullmatch(code) is None:
                raise ValueError(f"Invalid ISO-2 country filter: {raw_code!r}")
            if code not in registry.laws_by_iso2:
                raise ValueError(f"ISO-2 country code {code!r} not found in law registry")
            if code not in seen_iso2s:
                seen_iso2s.add(code)
                selected_iso2s.append(code)
        target_iso2s = sorted(selected_iso2s)
    else:
        target_iso2s = sorted(registry.laws_by_iso2)

    rules_by_code, rules_source = _load_rules_payload(
        rules_file=rules_file,
        rules_url=rules_url,
        client=client,
        timeout=timeout,
        sleep_fn=sleep_fn,
    )

    unack_all: list[SpeedDriftFinding] = []
    ack_all: list[SpeedDriftFinding] = []
    matched_count = 0
    missing_in_osm: list[str] = []

    for iso2 in target_iso2s:
        law = registry.laws_by_iso2[iso2]
        mapping = mappings_by_iso2.get(iso2)
        country_name = mapping.name_english if mapping is not None else law.ets2_slug
        osm_rules = rules_by_code.get(iso2)
        if osm_rules is None:
            missing_in_osm.append(iso2)
            continue
        matched_count += 1
        unack, ack = _compare_country_against_osm(law, country_name, osm_rules, allowlist_entries)
        unack_all.extend(unack)
        ack_all.extend(ack)

    def _finding_sort_key(
        finding: SpeedDriftFinding,
    ) -> tuple[str, VehicleSpeedClass, LaneSpeedClass, SpeedField]:
        return (finding.iso2, finding.vehicle_class, finding.lane_speed_class, finding.field)

    unack_sorted = sorted(unack_all, key=_finding_sort_key)
    ack_sorted = sorted(ack_all, key=_finding_sort_key)

    overpass_checks: list[OverpassSpotCheck] = []
    taginfo_dists: list[TaginfoDistribution] = []
    if include_overpass or include_taginfo:
        owns_client = client is None
        active_client = client if client is not None else create_http_client(timeout=timeout)
        try:
            if include_overpass:
                overpass_checks = fetch_overpass_speed_spot_checks(
                    active_client,
                    target_iso2s,
                    sleep_fn=sleep_fn,
                )
            if include_taginfo:
                taginfo_dists = fetch_taginfo_maxspeed_distributions(
                    active_client,
                    sleep_fn=sleep_fn,
                )
        finally:
            if owns_client:
                active_client.close()

    generated_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return OsmSpeedAuditReport(
        schema_version=1,
        generated_at=generated_at,
        rules_source=rules_source,
        allowlist_path=resolved_allowlist_str,
        countries_checked=len(target_iso2s),
        countries_matched_in_osm=matched_count,
        countries_missing_in_osm=sorted(missing_in_osm),
        unacknowledged_drift_count=len(unack_sorted),
        acknowledged_difference_count=len(ack_sorted),
        unacknowledged_drifts=unack_sorted,
        acknowledged_differences=ack_sorted,
        overpass_spot_checks=overpass_checks,
        taginfo_distributions=taginfo_dists,
    )


def render_osm_speed_drift_markdown(report: OsmSpeedAuditReport) -> str:
    """Render a sanitized deterministic UTF-8 LF Markdown report for CI summaries and issues."""
    lines: list[str] = [
        "# OSM Speed-Limit Drift Audit Report",
        "",
        "> **Internal CI Maintainer Advisory Only:** Do NOT copy OSM values directly into "
        "`data/laws/`. Verify every drift finding against official national road-traffic statutes "
        "before updating clean-room `CC BY 4.0` law records or "
        "`data/laws/speed_audit_allowlist.json`.",
        "",
        f"- **Generated At:** `{_sanitize_markdown_inline(report.generated_at, max_len=64)}`",
        f"- **Rules Source:** `{_sanitize_markdown_inline(report.rules_source, max_len=200)}`",
        f"- **Countries Checked / Matched:** `{report.countries_checked}` / "
        f"`{report.countries_matched_in_osm}`",
        f"- **Unacknowledged Drift Findings:** `{report.unacknowledged_drift_count}`",
        f"- **Acknowledged Statutory Differences:** `{report.acknowledged_difference_count}`",
        "",
        "## Unacknowledged Drift",
        "",
    ]

    if not report.unacknowledged_drifts:
        lines.append("None — all compared speed limits match or are statutorily acknowledged.")
    else:
        lines.extend(
            [
                "| ISO2 | Country | Vehicle | Lane | Field | Unit | Law | OSM | Raw OSM Tag |",
                "|------|---------|---------|------|-------|------|----:|----:|-------------|",
            ]
        )
        for item in report.unacknowledged_drifts:
            lines.append(
                f"| `{item.iso2}` "
                f"| {_sanitize_markdown_inline(item.country_name, max_len=80)} "
                f"| `{item.vehicle_class}` "
                f"| `{item.lane_speed_class}` "
                f"| `{item.field}` "
                f"| `{item.speed_unit}` "
                f"| {item.law_value} "
                f"| {item.osm_value} "
                f"| `{_sanitize_markdown_inline(item.osm_raw, max_len=80)}` |"
            )

    lines.extend(["", "## Acknowledged Statutory Differences", ""])
    if not report.acknowledged_differences:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| ISO2 | Country | Vehicle | Lane | Field | Law | OSM | Verified | Rationale |",
                "|------|---------|---------|------|-------|----:|----:|----------|-----------|",
            ]
        )
        for item in report.acknowledged_differences:
            rationale = _sanitize_markdown_inline(item.statutory_rationale or "", max_len=160)
            verified = _sanitize_markdown_inline(item.verified_date or "", max_len=32)
            lines.append(
                f"| `{item.iso2}` "
                f"| {_sanitize_markdown_inline(item.country_name, max_len=80)} "
                f"| `{item.vehicle_class}` "
                f"| `{item.lane_speed_class}` "
                f"| `{item.field}` "
                f"| {item.law_value} "
                f"| {item.osm_value} "
                f"| `{verified}` "
                f"| {rationale} |"
            )

    if report.overpass_spot_checks:
        lines.extend(["", "## Overpass Highway Spot-Checks", ""])
        for spot in report.overpass_spot_checks:
            if not spot.ok:
                err = _sanitize_markdown_inline(spot.error or "unknown error", max_len=180)
                lines.append(f"- **`{spot.iso2}` (failed):** {err}")
                continue
            summary_parts: list[str] = []
            for hw, counts in sorted(spot.top_maxspeed_by_highway.items()):
                vals = ", ".join(
                    f"`{_sanitize_markdown_inline(c.value, max_len=40)}` ({c.count})"
                    for c in counts
                )
                summary_parts.append(f"{_sanitize_markdown_inline(hw, max_len=32)}: {vals}")
            joined = "; ".join(summary_parts) if summary_parts else "no maxspeed tags sampled"
            lines.append(f"- **`{spot.iso2}` ({spot.ways_sampled} ways):** {joined}")

    if report.taginfo_distributions:
        lines.extend(["", "## Taginfo Global Maxspeed Distributions", ""])
        for dist in report.taginfo_distributions:
            if not dist.ok:
                err = _sanitize_markdown_inline(dist.error or "unknown error", max_len=180)
                lines.append(
                    f"- **`{_sanitize_markdown_inline(dist.key, max_len=40)}` (failed):** {err}"
                )
                continue
            top_vals = ", ".join(
                f"`{_sanitize_markdown_inline(v.value, max_len=40)}` ({v.count})"
                for v in dist.values[:5]
            )
            lines.append(
                f"- **`{_sanitize_markdown_inline(dist.key, max_len=40)}`:** "
                f"{top_vals or 'no values'}"
            )

    return "\n".join(lines) + "\n"


def truncate_markdown_for_github_issue(
    markdown_text: str,
    *,
    max_chars: int = DEFAULT_GITHUB_ISSUE_MAX_CHARS,
    artifact_name: str = "osm-speed-drift-report",
) -> str:
    """Truncate a Markdown report on a line boundary to stay safely below GitHub's 65,536 cap."""
    if max_chars <= 0:
        raise ValueError(f"max_chars must be > 0, got {max_chars!r}")
    if len(markdown_text) <= max_chars:
        return markdown_text

    footer = (
        f"\n\n---\n\n"
        f"> **Report truncated** at `<= {max_chars:,}` characters to stay within GitHub's "
        f"65,536-character Issue body limit. Download the full untruncated report from the "
        f"`{artifact_name}` workflow artifact.\n"
    )
    budget = max(0, max_chars - len(footer))
    kept_lines: list[str] = []
    used = 0
    for line in markdown_text.splitlines():
        addition = len(line) + (1 if kept_lines else 0)
        if used + addition > budget:
            break
        kept_lines.append(line)
        used += addition
    if not kept_lines:
        return (markdown_text[:budget] + footer)[:max_chars]
    return "\n".join(kept_lines) + footer
