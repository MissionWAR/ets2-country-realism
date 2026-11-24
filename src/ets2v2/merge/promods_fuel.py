"""Dynamic 43-locale ProMods local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii compiler (D-08)."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.baseline.models import LocalesBaseline
from ets2v2.package.synthesize import format_sii_string
from ets2v2.registry.snapshot import RealismSnapshot, RealismSnapshotCountry
from ets2v2.sii.hygiene import (
    serialize_sii_text,
    validate_sii_hygiene,
    validate_unit_name_segments,
)
from ets2v2.sii.localization import parse_localization_db
from ets2v2.vfs.stack import VfsStack
from ets2v2.vfs.types import ProtectedPayloadError, UnsupportedCompressionError

ProModsFuelModuleName = Literal["pm_fuel", "pm_me_fuel", "pm_tgs_fuel"]
PmFormatRegime = Literal["decimal", "midrange", "integer"]

PM_FUEL_MODULES: Final[tuple[ProModsFuelModuleName, ...]] = (
    "pm_fuel",
    "pm_me_fuel",
    "pm_tgs_fuel",
)

PM_FUEL_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^fp_(?P<prefix>[a-z]{2,3})_"
    r"(?P<grade>natural95_plus|natural92|natural95|natural98|natural100|"
    r"diesel_plus|diesel_colour|diesel|lpg|e85|mpo|adblue|biogas|electric)"
    r"(?:_(?P<variant>v[0-4]))?$"
)

_LOCALE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z]{2}_[a-z]{2}$")

_QUANT_INT: Final[Decimal] = Decimal("1")
_QUANT_1DEC: Final[Decimal] = Decimal("0.1")
_QUANT_2DEC: Final[Decimal] = Decimal("0.01")
_QUANT_3DEC: Final[Decimal] = Decimal("0.001")
_HUNDRED: Final[Decimal] = Decimal("100")

# Module-scoped prefix -> ISO-2 maps (67 observed prefixes + 4 TGS v1.71 future-proof entries).
# COLLISION GUARD: "mn" = Montenegro (ME, EUR) in pm_fuel vs Mongolia (MN, MNT) in pm_tgs_fuel.
_PM_EU_DIRECT_ISO2S: Final[tuple[str, ...]] = (
    "am",
    "at",
    "ax",
    "az",
    "be",
    "bg",
    "by",
    "ch",
    "cy",
    "cz",
    "de",
    "dk",
    "ee",
    "es",
    "fi",
    "fo",
    "fr",
    "gb",
    "ge",
    "gg",
    "gi",
    "gl",
    "gr",
    "hr",
    "hu",
    "is",
    "it",
    "je",
    "lt",
    "lu",
    "lv",
    "mc",
    "md",
    "mt",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "rs",
    "ru",
    "se",
    "sj",
    "sk",
    "tr",
    "ua",
)

PM_EU_PREFIX_TO_ISO2: Final[dict[str, str]] = {
    **{code: code.upper() for code in _PM_EU_DIRECT_ISO2S},
    "alb": "AL",
    "and": "AD",
    "bih": "BA",
    "cni": "ES",
    "iom": "IM",
    "irl": "IE",
    "mn": "ME",
    "nmk": "MK",
    "slo": "SI",
    "xkk": "XK",
}

PM_ME_PREFIX_TO_ISO2: Final[dict[str, str]] = {
    "eg": "EG",
    "irq": "IQ",
    "isr": "IL",
    "jor": "JO",
    "ksa": "SA",
    "lbn": "LB",
    "ps": "PS",
    "syr": "SY",
}

PM_TGS_PREFIX_TO_ISO2: Final[dict[str, str]] = {
    "cn": "CN",
    "kg": "KG",
    "kz": "KZ",
    "mn": "MN",
    "tj": "TJ",
    "tm": "TM",
    "uz": "UZ",
}

PM_MODULE_PREFIX_MAPS: Final[dict[ProModsFuelModuleName, dict[str, str]]] = {
    "pm_fuel": PM_EU_PREFIX_TO_ISO2,
    "pm_me_fuel": PM_ME_PREFIX_TO_ISO2,
    "pm_tgs_fuel": PM_TGS_PREFIX_TO_ISO2,
}

# Canary Islands IGIC (~7% vs mainland 21% IVA) multiplier over mainland ES price
PM_PREFIX_TAX_MULTIPLIERS: Final[dict[str, float]] = {
    "cni": 0.92,
}

_CANONICAL_PM_GRADES: Final[dict[str, str]] = {
    "diesel": "diesel",
    "diesel_plus": "diesel_plus",
    "natural92": "petrol_92",
    "natural95": "petrol_95",
    "natural98": "petrol_98",
    "natural100": "petrol_100",
    "lpg": "lpg",
    "e85": "e85",
    "mpo": "mpo",
}

# 5 ProMods-only derived grades computed deterministically from canonical snapshot prices
_DERIVED_PM_GRADES: Final[dict[str, tuple[str, float]]] = {
    "natural95_plus": ("petrol_95", 1.04),
    "diesel_colour": ("diesel", 0.85),
    "adblue": ("diesel", 0.65),
    "biogas": ("petrol_95", 1.80),
    "electric": ("petrol_95", 0.30),
}

_DECIMAL_REGIME_CURRENCIES: Final[frozenset[str]] = frozenset(
    {
        "AZN",
        "BAM",
        "BYN",
        "CHF",
        "EUR",
        "GBP",
        "GEL",
        "ILS",
        "JOD",
        "LYD",
        "PLN",
        "SAR",
        "TMT",
    }
)

_MIDRANGE_REGIME_CURRENCIES: Final[frozenset[str]] = frozenset(
    {
        "CNY",
        "CZK",
        "DKK",
        "EGP",
        "KGS",
        "MAD",
        "MDL",
        "MKD",
        "NOK",
        "RON",
        "SEK",
        "TJS",
        "TND",
        "TRY",
    }
)

_INTEGER_REGIME_CURRENCIES: Final[frozenset[str]] = frozenset(
    {
        "ALL",
        "AMD",
        "DZD",
        "HUF",
        "IQD",
        "ISK",
        "KZT",
        "LBP",
        "MNT",
        "RSD",
        "RUB",
        "SYP",
        "UAH",
        "UZS",
    }
)


class ProModsFuelModuleResult(BaseModel):
    """Compiled result for one discovered ProMods fuel localization module."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    module_name: ProModsFuelModuleName
    unit_name: str = Field(min_length=2)
    source_path: str = Field(min_length=1)
    total_keys: int = Field(ge=0)
    updated_keys: int = Field(ge=0)
    preserved_keys: int = Field(ge=0)
    preserved_key_names: list[str] = Field(default_factory=list)
    entries: dict[str, str]
    rendered_bytes: bytes


class CompiledProModsFuel(BaseModel):
    """All discovered ProMods fuel modules replicated across all 43 active ETS2 locales."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modules: dict[ProModsFuelModuleName, ProModsFuelModuleResult]
    locale_files: dict[str, bytes]


def classify_pm_format_regime(iso2: str, currency: str) -> PmFormatRegime:
    """Classify a territory/currency into decimal, mid-range, or high-unit integer regime."""
    code = iso2.strip().upper()
    ccy = currency.strip().upper()
    if code == "GL":
        # Greenland DKK (~6.00 DKK/L) displays in sub-10 decimal regime
        return "decimal"
    if ccy in _INTEGER_REGIME_CURRENCIES:
        return "integer"
    if ccy in _MIDRANGE_REGIME_CURRENCIES:
        return "midrange"
    if ccy in _DECIMAL_REGIME_CURRENCIES:
        return "decimal"
    return "decimal"


def format_pm_fuel_value(
    price: float,
    variant: str | None,
    regime: PmFormatRegime,
) -> str:
    """Format a local price into ProMods ``_v0``..``_v4`` syntax with Decimal ROUND_HALF_UP."""
    if not math.isfinite(price) or price <= 0.0:
        raise ValueError(f"ProMods fuel price must be finite and > 0.0, got {price!r}")

    dec = Decimal(str(price))
    if regime == "decimal":
        if variant in (None, "v0"):
            return f"{dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP):.2f}"
        q3 = dec.quantize(_QUANT_3DEC, rounding=ROUND_HALF_UP)
        if variant == "v1":
            return f"{q3:.3f}"
        if variant == "v2":
            s3 = f"{q3:.3f}"
            return f"{s3[:-1]}<sup>{s3[-1]}</sup>"
        cents = (dec * _HUNDRED).quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP)
        if variant == "v3":
            return f"{cents:05.1f}"
        if variant == "v4":
            s_cents = f"{cents:05.1f}"
            int_part, tenth = s_cents.split(".", 1)
            return f"{int_part}.<sup>{tenth}</sup>"
        raise ValueError(f"Unsupported ProMods fuel variant: {variant!r}")

    if variant in (None, "v0"):
        if regime == "midrange":
            return f"{dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP):.2f}"
        return f"{dec.quantize(_QUANT_INT, rounding=ROUND_HALF_UP):.0f}"

    q1 = dec.quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP)
    if variant in ("v1", "v3"):
        return f"{q1:.1f}"
    if variant in ("v2", "v4"):
        s1 = f"{q1:.1f}"
        int_part, dec_digit = s1.split(".", 1)
        return f"{int_part}.<sup>{dec_digit}</sup>"
    raise ValueError(f"Unsupported ProMods fuel variant: {variant!r}")


def _resolve_grade_price(
    country: RealismSnapshotCountry,
    pm_grade: str,
    *,
    prefix: str,
) -> float | None:
    local_prices = country.fuel.local_prices
    canonical = _CANONICAL_PM_GRADES.get(pm_grade)
    if canonical is not None:
        base_price = local_prices.get(canonical)
        if base_price is None or not math.isfinite(base_price) or base_price <= 0.0:
            return None
        multiplier = PM_PREFIX_TAX_MULTIPLIERS.get(prefix, 1.0)
        return base_price * multiplier

    derived = _DERIVED_PM_GRADES.get(pm_grade)
    if derived is not None:
        base_grade, grade_factor = derived
        base_price = local_prices.get(base_grade)
        if base_price is None or not math.isfinite(base_price) or base_price <= 0.0:
            return None
        tax_factor = PM_PREFIX_TAX_MULTIPLIERS.get(prefix, 1.0)
        return base_price * grade_factor * tax_factor

    return None


def _render_promods_localization_db(unit_name: str, entries: dict[str, str]) -> bytes:
    seg_diags = validate_unit_name_segments(unit_name)
    if seg_diags:
        summary = "; ".join(f"{d.code}: {d.message}" for d in seg_diags)
        raise ValueError(f"Invalid ProMods localization unit name {unit_name!r}: {summary}")

    lines: list[str] = [
        "SiiNunit",
        "{",
        f"localization_db : {unit_name}",
        "{",
    ]
    for key in sorted(entries):
        val = entries[key]
        lines.append(f"\tkey[]: {format_sii_string(key)}")
        lines.append(f"\tval[]: {format_sii_string(val)}")
    lines.append("}")
    lines.append("}")
    raw = serialize_sii_text("\n".join(lines) + "\n")
    hygiene = validate_sii_hygiene(raw, require_siinunit=True)
    if hygiene:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in hygiene)
        raise ValueError(
            f"Synthesized ProMods localization hygiene failure for {unit_name}: {summary}"
        )
    return raw


def compile_promods_fuel_module(
    module_name: ProModsFuelModuleName,
    source_bytes: bytes,
    snapshot: RealismSnapshot,
    *,
    source_path: str,
) -> ProModsFuelModuleResult:
    """Compile one ProMods ``local_module.pm*_fuel.sii`` preserving unrecognized keys verbatim."""
    raw_entries = parse_localization_db(source_bytes)
    prefix_map = PM_MODULE_PREFIX_MAPS[module_name]
    unit_name = f".{module_name}"

    # Deduplicate deterministically (last wins) while tracking updated vs verbatim keys
    deduped_source: dict[str, str] = {}
    for item in raw_entries:
        deduped_source[item.key] = item.val

    compiled_entries: dict[str, str] = {}
    updated_count = 0
    preserved_names: list[str] = []

    for key in sorted(deduped_source):
        original_val = deduped_source[key]
        match = PM_FUEL_KEY_RE.fullmatch(key)
        if match is None:
            compiled_entries[key] = original_val
            preserved_names.append(key)
            continue

        prefix = match.group("prefix")
        pm_grade = match.group("grade")
        variant = match.group("variant")
        iso2 = prefix_map.get(prefix)
        if iso2 is None:
            compiled_entries[key] = original_val
            preserved_names.append(key)
            continue

        country = snapshot.countries.get(iso2)
        if country is None:
            compiled_entries[key] = original_val
            preserved_names.append(key)
            continue

        price = _resolve_grade_price(country, pm_grade, prefix=prefix)
        if price is None:
            compiled_entries[key] = original_val
            preserved_names.append(key)
            continue

        regime = classify_pm_format_regime(iso2, country.fuel.currency)
        compiled_entries[key] = format_pm_fuel_value(price, variant, regime)
        updated_count += 1

    rendered_bytes = _render_promods_localization_db(unit_name, compiled_entries)
    return ProModsFuelModuleResult(
        module_name=module_name,
        unit_name=unit_name,
        source_path=source_path,
        total_keys=len(compiled_entries),
        updated_keys=updated_count,
        preserved_keys=len(preserved_names),
        preserved_key_names=sorted(preserved_names),
        entries=compiled_entries,
        rendered_bytes=rendered_bytes,
    )


def _find_module_source_in_stack(
    stack: VfsStack,
    module_name: ProModsFuelModuleName,
    active_locales: list[str],
) -> tuple[str, bytes] | None:
    filename = f"local_module.{module_name}.sii"
    probe_locales = ["en_gb", *(lang for lang in active_locales if lang != "en_gb")]
    for lang in probe_locales:
        candidate = f"locale/{lang}/{filename}"
        entry = stack.resolve(candidate)
        if entry is None or entry.is_empty_stub:
            continue
        try:
            raw = stack.read_bytes(candidate)
        except (FileNotFoundError, ProtectedPayloadError, UnsupportedCompressionError):
            continue
        return candidate, raw
    return None


def compile_promods_fuel_locales(
    stack: VfsStack,
    locales: LocalesBaseline,
    snapshot: RealismSnapshot,
) -> CompiledProModsFuel:
    """Discover ProMods ``pm*_fuel`` modules in ``stack`` and emit across all 43 active locales."""
    active_locales = sorted(locales.active_locales)
    if not active_locales:
        raise ValueError("LocalesBaseline.active_locales must not be empty")
    if "fr_qc" in active_locales:
        raise ValueError("Deprecated locale 'fr_qc' must not be emitted (D-08)")
    for lang in active_locales:
        if _LOCALE_CODE_RE.fullmatch(lang) is None:
            raise ValueError(f"Invalid ETS2 locale directory code: {lang!r}")

    modules: dict[ProModsFuelModuleName, ProModsFuelModuleResult] = {}
    locale_files: dict[str, bytes] = {}

    for module_name in PM_FUEL_MODULES:
        found = _find_module_source_in_stack(stack, module_name, active_locales)
        if found is None:
            continue
        source_path, raw_bytes = found
        result = compile_promods_fuel_module(
            module_name,
            raw_bytes,
            snapshot,
            source_path=source_path,
        )
        modules[module_name] = result
        filename = f"local_module.{module_name}.sii"
        for lang in active_locales:
            locale_files[f"locale/{lang}/{filename}"] = result.rendered_bytes

    return CompiledProModsFuel(modules=modules, locale_files=locale_files)


__all__ = [
    "PM_EU_PREFIX_TO_ISO2",
    "PM_FUEL_KEY_RE",
    "PM_FUEL_MODULES",
    "PM_ME_PREFIX_TO_ISO2",
    "PM_MODULE_PREFIX_MAPS",
    "PM_PREFIX_TAX_MULTIPLIERS",
    "PM_TGS_PREFIX_TO_ISO2",
    "CompiledProModsFuel",
    "PmFormatRegime",
    "ProModsFuelModuleName",
    "ProModsFuelModuleResult",
    "classify_pm_format_regime",
    "compile_promods_fuel_locales",
    "compile_promods_fuel_module",
    "format_pm_fuel_value",
]
