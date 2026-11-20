"""Workshop and local Core package metadata renderers (versions.sii, manifest.sii, description)."""

from __future__ import annotations

from typing import Final

from ets2v2.package.synthesize import format_sii_string
from ets2v2.registry.models import Season
from ets2v2.sii.hygiene import serialize_sii_text, validate_sii_hygiene

DEFAULT_AUTHOR: Final[str] = "ETS2 World Realism"
WORKSHOP_CATEGORIES: Final[tuple[str, str]] = ("other", "ai_traffic")
LOCAL_DISPLAY_NAMES: Final[dict[Season, str]] = {
    "summer": "ETS2 World Country Realism - Summer (Core)",
    "winter": "ETS2 World Country Realism - Winter (Core)",
}


def _assert_hygiene(raw: bytes, *, label: str) -> None:
    diagnostics = validate_sii_hygiene(raw, require_siinunit=True)
    if diagnostics:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in diagnostics)
        raise ValueError(f"Synthesized metadata hygiene failure for {label}: {summary}")


def render_versions_sii() -> bytes:
    """Render Workshop root ``versions.sii`` referencing the single ``universal`` package."""
    lines = [
        "SiiNunit",
        "{",
        "package_version_info : .universal",
        "{",
        '\tpackage_name: "universal"',
        "}",
        "}",
    ]
    raw = serialize_sii_text("\n".join(lines) + "\n")
    _assert_hygiene(raw, label="versions.sii")
    return raw


def render_manifest_sii(
    edition: Season,
    package_version: str,
    *,
    workshop: bool,
    author: str = DEFAULT_AUTHOR,
) -> bytes:
    """Render ``manifest.sii`` for Workshop (no ``display_name``) or local ZIP distribution."""
    if not package_version.strip():
        raise ValueError("package_version must be a non-empty string")
    if not author.strip():
        raise ValueError("author must be a non-empty string")

    lines: list[str] = [
        "SiiNunit",
        "{",
        "mod_package : .package_name",
        "{",
        f"\tpackage_version: {format_sii_string(package_version)}",
    ]
    if not workshop:
        lines.append(f"\tdisplay_name: {format_sii_string(LOCAL_DISPLAY_NAMES[edition])}")
    lines.append(f"\tauthor: {format_sii_string(author)}")
    for category in WORKSHOP_CATEGORIES:
        lines.append(f"\tcategory[]: {format_sii_string(category)}")
    lines.append('\ticon: "mod_icon.jpg"')
    lines.append('\tdescription_file: "description.txt"')
    lines.append("\tmp_mod_optional: true")
    lines.append("}")
    lines.append("}")

    raw = serialize_sii_text("\n".join(lines) + "\n")
    _assert_hygiene(raw, label="manifest.sii")
    return raw


def render_description_txt(edition: Season) -> bytes:
    """Render deterministic UTF-8 no-BOM LF ``description.txt`` without volatile timestamps."""
    is_summer = edition == "summer"
    title = (
        "ETS2 World Country Realism - Summer Edition (Core)"
        if is_summer
        else "ETS2 World Country Realism - Winter Edition (Core)"
    )
    if is_summer:
        season_summary = (
            "Seasonal profile: Summer peak (July 15 DST offsets and summer statutory rules).\n"
            "- Daylight Saving Time active across observing zones (CEST, EEST, WEST, BST).\n"
            "- Croatia daytime lights optional in clear summer daylight (DRL: false).\n"
            "- Finland (120/100), Estonia (110/110), and Lithuania (130/120) summer car limits."
        )
    else:
        season_summary = (
            "Seasonal profile: Winter peak (January 15 standard offsets and winter rules).\n"
            "- Standard winter time active across Europe (CET, EET, WET, GMT, MSK, TRT).\n"
            "- Croatia winter daytime lights mandatory (Nov 1 - Mar 31, lights_mandatory: true).\n"
            "- Finland (100/80), Estonia (90/90), and Lithuania (110/110) winter car limits."
        )

    body = (
        f"{title}\n"
        "==================================================\n\n"
        "Clean-room ETS2 1.62+ country realism mod covering all 36 Vanilla + DLC countries.\n"
        "Pairs cleanly with seasonal weather packs without modifying def/country.sii.\n\n"
        f"{season_summary}\n\n"
        "Key Realism Highlights:\n"
        "- Dynamic IANA/tzdata timezones honoring ETS2's 12 supported @@tz_*@@ locale keys.\n"
        "- Verified statutory speed limits across car, truck (>3.5t), and bus classes\n"
        "  (UK mph, Iceland 80 km/h truck, Austria 100 km/h expressway, Turkey 130 motorway).\n"
        "- Verified daytime running light (DRL) rules (Switzerland mandatory; Netherlands,\n"
        "  Albania, and Turkey optional in clear daylight).\n"
        "- Preserves ETS2 1.62 country regions[], Kaliningrad secondary timezone, axle\n"
        "  weight ceilings (incl. Iceland 60t 5-axle), slow_road/uncommon, and train/tram.\n"
        "- Convoy multiplayer optional (mp_mod_optional: true).\n\n"
        "Open-Source Attribution & Licensing:\n"
        "- Generator & build pipeline: MIT License (ETS2 World Realism).\n"
        "- Canonical statutory country registry data: CC BY 4.0.\n"
        "- Clean-room synthesis from open statutory records and ETS2 1.62 metadata schemas.\n"
    )
    return serialize_sii_text(body)
