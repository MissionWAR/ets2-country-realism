"""Workshop and local Core package metadata renderers (versions.sii, manifest.sii, description)."""

from __future__ import annotations

from typing import Final

from ets2v2.package.synthesize import format_sii_string
from ets2v2.registry.models import Season
from ets2v2.sii.hygiene import serialize_sii_text, validate_sii_hygiene

DEFAULT_AUTHOR: Final[str] = "ETS2 World Realism"
ETS2V2_MANIFEST_MARKER: Final[str] = "# ets2v2:managed-package"
WORKSHOP_CATEGORIES: Final[tuple[str, str]] = ("other", "ai_traffic")
LOCAL_DISPLAY_NAMES: Final[dict[Season, str]] = {
    "summer": "ETS2 World Country Realism - Summer (Core)",
    "winter": "ETS2 World Country Realism - Winter (Core)",
}
PROMODS_LOCAL_DISPLAY_NAMES: Final[dict[Season, str]] = {
    "summer": "ETS2 World Country Realism - Summer (ProMods Edition)",
    "winter": "ETS2 World Country Realism - Winter (ProMods Edition)",
}
COMBO_LOCAL_DISPLAY_NAMES: Final[dict[Season, str]] = {
    "summer": "ETS2 World Country Realism - Summer (Combo Patch)",
    "winter": "ETS2 World Country Realism - Winter (Combo Patch)",
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


def _render_managed_manifest_sii(
    display_name: str,
    package_version: str,
    *,
    kind: str,
    workshop: bool,
    author: str = DEFAULT_AUTHOR,
) -> bytes:
    if not package_version.strip():
        raise ValueError("package_version must be a non-empty string")
    if not author.strip():
        raise ValueError("author must be a non-empty string")

    lines: list[str] = [
        "SiiNunit",
        "{",
        f"{ETS2V2_MANIFEST_MARKER} kind={kind}",
        "mod_package : .package_name",
        "{",
        f"\tpackage_version: {format_sii_string(package_version)}",
    ]
    if not workshop:
        lines.append(f"\tdisplay_name: {format_sii_string(display_name)}")
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


def render_manifest_sii(
    edition: Season,
    package_version: str,
    *,
    workshop: bool,
    author: str = DEFAULT_AUTHOR,
) -> bytes:
    """Render ``manifest.sii`` for Workshop (no ``display_name``) or local ZIP distribution."""
    return _render_managed_manifest_sii(
        LOCAL_DISPLAY_NAMES[edition],
        package_version,
        kind="core",
        workshop=workshop,
        author=author,
    )


def render_promods_manifest_sii(
    edition: Season,
    package_version: str,
    *,
    workshop: bool,
    author: str = DEFAULT_AUTHOR,
) -> bytes:
    """Render ``manifest.sii`` for standalone ProMods Edition Workshop or local ZIP (D-07, D-10)."""
    return _render_managed_manifest_sii(
        PROMODS_LOCAL_DISPLAY_NAMES[edition],
        package_version,
        kind="promods",
        workshop=workshop,
        author=author,
    )


def render_combo_manifest_sii(
    edition: Season,
    package_version: str,
    *,
    author: str = DEFAULT_AUTHOR,
) -> bytes:
    """Render local ``manifest.sii`` for ``zz_ETS2V2_ComboPatch_{Summer|Winter}.scs`` (D-10)."""
    return _render_managed_manifest_sii(
        COMBO_LOCAL_DISPLAY_NAMES[edition],
        package_version,
        kind="combo",
        workshop=False,
        author=author,
    )


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
        "- Option 4b Zero-DDS roadside fuel totems across 460 sign boards and all 43 active\n"
        "  ETS2 1.62 locales with native-currency pump formatting (zero .dds/.tobj assets).\n"
        "- Convoy multiplayer optional (mp_mod_optional: true).\n\n"
        "Open-Source Attribution & Licensing:\n"
        "- Generator & build pipeline: MIT License (ETS2 World Realism).\n"
        "- Canonical statutory country registry data: CC BY 4.0.\n"
        "- Open European fuel data: EC Weekly Oil Bulletin CC BY 4.0, fuel-prices.eu CC BY 4.0,\n"
        "  UK DESNZ OGL v3, Norway SSB CC BY 4.0, France Licence Ouverte, Italy MIMIT IODL 2.0,\n"
        "  Spain MITECO, Netherlands CBS, Germany Tankerkönig CC BY 4.0.\n"
        "- Open FX reference rates: Frankfurter v2 MIT, ECB, fawazahmed0 CC0.\n"
        "- Clean-room synthesis from open statutory records and ETS2 1.62 metadata schemas.\n"
    )
    return serialize_sii_text(body)


def render_promods_description_txt(edition: Season) -> bytes:
    """Render deterministic UTF-8 no-BOM LF ``description.txt`` for standalone ProMods Editions."""
    is_summer = edition == "summer"
    title = (
        "ETS2 World Country Realism - Summer (ProMods Edition)"
        if is_summer
        else "ETS2 World Country Realism - Winter (ProMods Edition)"
    )
    if is_summer:
        season_summary = (
            "Seasonal profile: Summer peak (July 15 DST offsets and summer statutory rules).\n"
            "- Daylight Saving Time active across observing zones (CEST, EEST, WEST, BST, IDT).\n"
            "- Croatia, Moldova, and Israel daytime lights optional in summer daylight.\n"
            "- Finland (120/100), Estonia (110/110), and Lithuania (130/120) summer car limits."
        )
    else:
        season_summary = (
            "Seasonal profile: Winter peak (January 15 standard offsets and winter rules).\n"
            "- Standard winter time active across Europe, Middle East, and Central Asia.\n"
            "- Croatia, Moldova, and Israel winter daytime lights mandatory.\n"
            "- Finland (100/80), Estonia (90/90), and Lithuania (110/110) winter car limits."
        )

    body = (
        f"{title}\n"
        "==================================================\n\n"
        "Standalone all-in-one ETS2 1.62+ realism mod for ProMods (EU + ME + MA + TGS).\n"
        "Replaces the Core Edition cleanly: enable ONLY this single mod ABOVE ProMods Def\n"
        "in Mod Manager (do not enable the Vanilla Core Edition alongside ProMods Edition).\n\n"
        f"{season_summary}\n\n"
        "Key ProMods Realism Highlights:\n"
        "- Surgically patches Vanilla + ProMods def/country/*.sui & speed_limits.sii without\n"
        "  ever emitting def/country.sii or def/country.*.sii registration files.\n"
        "- Preserves ProMods UK scotland/wales regions[], ProMods country geometry/IDs,\n"
        "  TGS multi-timezone Russia, custom lane classes, and train/tram rail blocks.\n"
        "- Monotonic carry-forward axle weight upgrades (incl. Iceland 60t 5-axle & heavy\n"
        "  truck 80 km/h) with imperial_units parity protection.\n"
        "- Option 4b Zero-DDS Vanilla sign boards + dynamic 43-locale local_module.ets2v2_fuel\n"
        "  and ProMods local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii (zero .dds/.tobj).\n"
        "- Convoy multiplayer optional (mp_mod_optional: true).\n\n"
        "Open-Source Attribution & Licensing:\n"
        "- Generator & build pipeline: MIT License (ETS2 World Realism).\n"
        "- Canonical statutory country registry data: CC BY 4.0.\n"
        "- Open European fuel data: EC Weekly Oil Bulletin CC BY 4.0, fuel-prices.eu CC BY 4.0,\n"
        "  UK DESNZ OGL v3, Norway SSB CC BY 4.0, France Licence Ouverte, Italy MIMIT IODL 2.0,\n"
        "  Spain MITECO, Netherlands CBS, Germany Tankerkönig CC BY 4.0.\n"
        "- Open FX reference rates: Frankfurter v2 MIT, ECB, fawazahmed0 CC0.\n"
        "- Built locally from user-installed ProMods archives (minimal realism-only footprint).\n"
    )
    return serialize_sii_text(body)


def render_combo_description_txt(edition: Season) -> bytes:
    """Render deterministic UTF-8 no-BOM LF ``description.txt`` for local ComboPatch (D-12)."""
    is_summer = edition == "summer"
    title = (
        "ETS2 World Country Realism - Summer (Local Map Combo Patch)"
        if is_summer
        else "ETS2 World Country Realism - Winter (Local Map Combo Patch)"
    )
    if is_summer:
        season_summary = (
            "Seasonal profile: Summer peak (July 15 DST offsets and summer statutory rules).\n"
            "- Daylight Saving Time active on single-TZ countries; multi-TZ maps preserved.\n"
            "- Croatia, Moldova, and Israel daytime lights optional in summer daylight."
        )
    else:
        season_summary = (
            "Seasonal profile: Winter peak (January 15 standard offsets and winter rules).\n"
            "- Standard winter time active on single-TZ countries; multi-TZ maps preserved.\n"
            "- Croatia, Moldova, and Israel winter daytime lights mandatory."
        )

    body = (
        f"{title}\n"
        "==================================================\n\n"
        "100% offline locally composed ETS2 1.62+ realism patch tailored to your active\n"
        "multi-map combo load order (ProMods, RusMap, TST, UMCF, Beyond, EAA, SEA, RoC,\n"
        "Project Japan, JRR, Africa, etc.).\n\n"
        "Mod Manager Load Order Placement:\n"
        "- Place this zz_ETS2V2_ComboPatch_*.scs package at the VERY TOP of Mod Manager\n"
        "  (highest priority, ABOVE all map mods, map fix packs, and ProMods Def).\n"
        "- Disable Vanilla Core and standalone ProMods Editions when using Combo Patch.\n"
        "- Weekly re-runs automatically exclude previous zz_ETS2V2_ComboPatch_*.scs builds.\n\n"
        f"{season_summary}\n\n"
        "FieldOwnershipPolicy Guardrails:\n"
        "- Preserves map-owned country IDs, geometry/pos, regions[], multi-timezone areas\n"
        "  (TST Russia, UMCF Kazakhstan, EAA Brazil), custom lane classes, and train/tram.\n"
        "- Never downgrades heavy map axle ladders (max_of_map_and_real carry-forward).\n"
        "- Enforces imperial_units parity protection on speed_limits.sii.\n"
        "- Emits zero def/country*.sii registration files and zero .dds/.tobj textures.\n"
        "- Convoy multiplayer optional (mp_mod_optional: true).\n\n"
        "Open-Source Attribution & Licensing:\n"
        "- Generator & build pipeline: MIT License (ETS2 World Realism).\n"
        "- Canonical statutory country registry data: CC BY 4.0.\n"
        "- Open European fuel data: EC Weekly Oil Bulletin CC BY 4.0, fuel-prices.eu CC BY 4.0,\n"
        "  UK DESNZ OGL v3, Norway SSB CC BY 4.0, France Licence Ouverte, Italy MIMIT IODL 2.0,\n"
        "  Spain MITECO, Netherlands CBS, Germany Tankerkönig CC BY 4.0.\n"
        "- Open FX reference rates: Frankfurter v2 MIT, ECB, fawazahmed0 CC0.\n"
    )
    return serialize_sii_text(body)
