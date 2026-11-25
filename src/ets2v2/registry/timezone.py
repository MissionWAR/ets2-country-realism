"""Dynamic stdlib zoneinfo + tzdata seasonal DST resolver and ETS2 tz-key mapper."""

from __future__ import annotations

from collections.abc import Collection
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict

from ets2v2.registry.models import Season

DEFAULT_ANCHOR_YEAR: Final[int] = 2026
SUMMER_ANCHOR_MONTH_DAY: Final[tuple[int, int]] = (7, 15)
WINTER_ANCHOR_MONTH_DAY: Final[tuple[int, int]] = (1, 15)

# Explicit ETS2/human abbreviation overrides for IANA zones whose tzname() is numeric ("+03").
# Tuple entries map (standard_abbr, dst_abbr) for seasonal numeric zones such as America/Nuuk.
IANA_NUMERIC_ABBR_OVERRIDES: Final[dict[str, str | tuple[str, str]]] = {
    "Africa/Casablanca": "WEST",
    "Africa/El_Aaiun": "WEST",
    "America/Argentina/Buenos_Aires": "ART",
    "America/Asuncion": "PYT",
    "America/Bogota": "COT",
    "America/Caracas": "VET",
    "America/Cayenne": "GFT",
    "America/Guayaquil": "ECT",
    "America/Guyana": "GYT",
    "America/La_Paz": "BOT",
    "America/Lima": "PET",
    "America/Miquelon": ("PMST", "PMDT"),
    "America/Montevideo": "UYT",
    "America/Nuuk": ("WGT", "WGST"),
    "America/Paramaribo": "SRT",
    "America/Santiago": ("CLT", "CLST"),
    "America/Sao_Paulo": "BRT",
    "Asia/Aden": "AST",
    "Asia/Almaty": "AQTT",
    "Asia/Amman": "AST",
    "Asia/Ashgabat": "TMT",
    "Asia/Baghdad": "AST",
    "Asia/Bahrain": "AST",
    "Asia/Baku": "AZT",
    "Asia/Bangkok": "ICT",
    "Asia/Bishkek": "KGT",
    "Asia/Brunei": "BNT",
    "Asia/Colombo": "SLST",
    "Asia/Damascus": "AST",
    "Asia/Dhaka": "BDT",
    "Asia/Dili": "TLT",
    "Asia/Dubai": "GST",
    "Asia/Dushanbe": "TJT",
    "Asia/Ho_Chi_Minh": "ICT",
    "Asia/Kabul": "AFT",
    "Asia/Kathmandu": "NPT",
    "Asia/Kuala_Lumpur": "MYT",
    "Asia/Kuwait": "AST",
    "Asia/Muscat": "GST",
    "Asia/Phnom_Penh": "ICT",
    "Asia/Qatar": "AST",
    "Asia/Riyadh": "AST",
    "Asia/Singapore": "SGT",
    "Asia/Tashkent": "UZT",
    "Asia/Tbilisi": "GET",
    "Asia/Tehran": "IRST",
    "Asia/Thimphu": "BTT",
    "Asia/Ulaanbaatar": "ULAT",
    "Asia/Vientiane": "ICT",
    "Asia/Yangon": "MMT",
    "Asia/Yerevan": "AMT",
    "Atlantic/Cape_Verde": "CVT",
    "Atlantic/Stanley": "FKST",
    "Europe/Istanbul": "TRT",
    "Europe/Minsk": "MSK",
    "Indian/Mahe": "SCT",
    "Indian/Maldives": "MVT",
    "Indian/Mauritius": "MUT",
    "Indian/Reunion": "RET",
    "Pacific/Apia": "WST",
    "Pacific/Efate": "VUT",
    "Pacific/Fiji": "FJT",
    "Pacific/Funafuti": "TVT",
    "Pacific/Guadalcanal": "SBT",
    "Pacific/Majuro": "MHT",
    "Pacific/Nauru": "NRT",
    "Pacific/Niue": "NUT",
    "Pacific/Noumea": "NCT",
    "Pacific/Palau": "PWT",
    "Pacific/Pohnpei": "PONT",
    "Pacific/Port_Moresby": "PGT",
    "Pacific/Rarotonga": "CKT",
    "Pacific/Tahiti": "TAHT",
    "Pacific/Tarawa": "GILT",
    "Pacific/Tongatapu": "TOT",
}


class ResolvedTimezone(BaseModel):
    """Resolved seasonal timezone offset, abbreviation, and ETS2 localization token."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iana_timezone: str
    ref_date: str
    offset_minutes: int
    abbreviation: str
    ets2_time_zone_name: str
    is_dst: bool
    observes_dst: bool


def resolve_season_anchor_date(
    season: Season,
    *,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    override_date: date | None = None,
) -> date:
    """Return the seasonal peak anchor date (Jul 15 or Jan 15) or an explicit override date."""
    if override_date is not None:
        return override_date
    month, day = SUMMER_ANCHOR_MONTH_DAY if season == "summer" else WINTER_ANCHOR_MONTH_DAY
    return date(anchor_year, month, day)


def _format_utc_offset_fallback(offset_minutes: int) -> str:
    sign = "+" if offset_minutes >= 0 else "-"
    hours, mins = divmod(abs(offset_minutes), 60)
    return f"UTC{sign}{hours}" if mins == 0 else f"UTC{sign}{hours}:{mins:02d}"


def resolve_ets2_timezone(
    iana_tz: str,
    ref_date: date,
    supported_tz_keys: Collection[str],
) -> ResolvedTimezone:
    """Resolve an IANA timezone on ``ref_date`` (12:00 local noon) into ETS2 fields."""
    if not iana_tz:
        raise ValueError("IANA timezone identifier must be a non-empty string")

    try:
        tz = ZoneInfo(iana_tz)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise ValueError(f"Unknown or invalid IANA timezone {iana_tz!r}") from exc

    dt = datetime(ref_date.year, ref_date.month, ref_date.day, 12, 0, tzinfo=tz)
    offset = dt.utcoffset()
    if offset is None:
        raise ValueError(f"Unable to compute UTC offset for {iana_tz!r} on {ref_date.isoformat()}")

    offset_minutes = int(offset.total_seconds() // 60)
    dst_delta = dt.dst()
    is_dst = bool(dst_delta is not None and dst_delta.total_seconds() != 0)

    jan_month, jan_day = WINTER_ANCHOR_MONTH_DAY
    jul_month, jul_day = SUMMER_ANCHOR_MONTH_DAY
    jan_dst = datetime(ref_date.year, jan_month, jan_day, 12, 0, tzinfo=tz).dst()
    jul_dst = datetime(ref_date.year, jul_month, jul_day, 12, 0, tzinfo=tz).dst()
    if jan_dst is None or jul_dst is None:
        raise ValueError(f"Unable to compute seasonal DST offsets for {iana_tz!r}")
    observes_dst = bool(jan_dst) or bool(jul_dst)

    raw_abbr = dt.tzname()
    if raw_abbr is None or not raw_abbr or raw_abbr[0] in {"+", "-"}:
        if iana_tz in IANA_NUMERIC_ABBR_OVERRIDES:
            override = IANA_NUMERIC_ABBR_OVERRIDES[iana_tz]
            if isinstance(override, tuple):
                abbr = override[1] if is_dst else override[0]
            else:
                abbr = override
        else:
            abbr = _format_utc_offset_fallback(offset_minutes)
    else:
        abbr = raw_abbr

    supported_set = frozenset(supported_tz_keys)
    candidate_key = f"tz_{abbr.lower()}"
    ets2_time_zone_name = f"@@{candidate_key}@@" if candidate_key in supported_set else abbr

    return ResolvedTimezone(
        iana_timezone=iana_tz,
        ref_date=ref_date.isoformat(),
        offset_minutes=offset_minutes,
        abbreviation=abbr,
        ets2_time_zone_name=ets2_time_zone_name,
        is_dst=is_dst,
        observes_dst=observes_dst,
    )


def assert_leftside_traffic_immutable(
    slug: str,
    baseline_leftside: bool | None,
    candidate_leftside: bool | None,
) -> None:
    """Assert that map-owned ``leftside_traffic`` has not been flipped relative to baseline."""
    baseline_is_lht = baseline_leftside is True
    candidate_is_lht = candidate_leftside is True
    if baseline_is_lht != candidate_is_lht:
        raise ValueError(
            f"leftside_traffic is immutable for {slug!r}: "
            f"baseline={baseline_leftside!r}, candidate={candidate_leftside!r}"
        )
