"""Data-driven 225-territory global currency registry, FX tiers, sanity bands, and Tier 3 seeds."""

from __future__ import annotations

import functools
import re
from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_REPO_DATA_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "data"
DEFAULT_CURRENCIES_JSON_PATH: Final[Path] = _REPO_DATA_DIR / "mappings" / "currencies.json"
DEFAULT_TIER3_BASELINES_JSON_PATH: Final[Path] = (
    _REPO_DATA_DIR / "curated" / "tier3_fuel_baselines.json"
)
TIER3_CURATED_BASELINE_SOURCE: Final[str] = "tier3_curated_baseline"
TIER3_CURATED_BASELINE_LICENSE: Final[str] = "CC BY 4.0"

_ISO2_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2}$")
_ISO4217_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{3}$")


class CurrencyMetadataEntry(BaseModel):
    """Canonical clean-room ISO-4217 currency entry in ``data/mappings/currencies.json``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    tier: Literal["pinned", "core", "extended"]
    ecb_covered: bool
    major_ecb: bool
    fixed_peg_per_eur: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)
    reference_rate_per_eur: float = Field(gt=0.0, allow_inf_nan=False)
    sanity_min: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)
    sanity_max: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _validate_sanity_band(self) -> CurrencyMetadataEntry:
        if self.tier == "pinned":
            if self.sanity_min is not None or self.sanity_max is not None:
                raise ValueError("Pinned currency must not specify sanity_min/sanity_max")
            return self
        if self.sanity_min is None or self.sanity_max is None:
            raise ValueError("Non-pinned currency requires both sanity_min and sanity_max")
        if self.sanity_min >= self.sanity_max:
            raise ValueError("sanity_min must be strictly less than sanity_max")
        if not (self.sanity_min <= self.reference_rate_per_eur <= self.sanity_max):
            raise ValueError("reference_rate_per_eur must fall inside [sanity_min, sanity_max]")
        return self


class CurrencyRegistry(BaseModel):
    """Top-level ``data/mappings/currencies.json`` schema (D-10)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    verified_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    provenance: str = Field(min_length=1)
    currencies: dict[str, CurrencyMetadataEntry]
    territory_currencies: dict[str, str]

    @field_validator("verified_date")
    @classmethod
    def _validate_verified_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _validate_cross_references(self) -> CurrencyRegistry:
        for code in self.currencies:
            if _ISO4217_RE.fullmatch(code) is None:
                raise ValueError(f"Invalid ISO-4217 currency code {code!r}")
        eur_meta = self.currencies.get("EUR")
        if eur_meta is None or eur_meta.tier != "pinned" or eur_meta.reference_rate_per_eur != 1.0:
            raise ValueError("currencies.json must pin EUR with tier='pinned' and rate=1.0")
        for iso2, code in self.territory_currencies.items():
            if _ISO2_RE.fullmatch(iso2) is None:
                raise ValueError(f"Invalid ISO-2 territory code {iso2!r}")
            if code not in self.currencies:
                raise ValueError(
                    f"Territory {iso2!r} references unknown ISO-4217 currency {code!r}"
                )
        return self


class Tier3FuelBaselineEntry(BaseModel):
    """Curated EUR/L retail fuel baseline entry in ``data/curated/tier3_fuel_baselines.json``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    diesel_eur_per_liter: float = Field(ge=0.01, le=5.00, allow_inf_nan=False)
    petrol_95_eur_per_liter: float = Field(ge=0.01, le=5.00, allow_inf_nan=False)
    clamped_to_floor: bool = False
    verified_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_note: str = Field(min_length=1)

    @field_validator("verified_date")
    @classmethod
    def _validate_verified_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _validate_floor_clamp(self) -> Tier3FuelBaselineEntry:
        if self.clamped_to_floor and self.diesel_eur_per_liter != 0.01:
            raise ValueError(
                "clamped_to_floor=True entries must clamp diesel_eur_per_liter to exactly 0.01"
            )
        return self


class Tier3FuelBaselineRegistry(BaseModel):
    """Top-level ``data/curated/tier3_fuel_baselines.json`` schema (D-10, D-11)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    verified_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    license: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    baselines: dict[str, Tier3FuelBaselineEntry]

    @field_validator("verified_date")
    @classmethod
    def _validate_verified_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _validate_iso2_keys(self) -> Tier3FuelBaselineRegistry:
        for iso2 in self.baselines:
            if _ISO2_RE.fullmatch(iso2) is None:
                raise ValueError(f"Invalid ISO-2 key in tier3_fuel_baselines.json: {iso2!r}")
        return self


def _read_clean_json_text(path: Path, *, label: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label} registry file: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{label} must be UTF-8 without BOM: {path}")
    if b"\r" in raw:
        raise ValueError(f"{label} must use LF line endings only: {path}")
    return raw.decode("utf-8")


@functools.lru_cache(maxsize=8)
def load_currency_registry(path: Path = DEFAULT_CURRENCIES_JSON_PATH) -> CurrencyRegistry:
    """Strictly load and validate ``data/mappings/currencies.json`` (cached, 100% offline)."""
    text = _read_clean_json_text(path, label="currencies.json")
    return CurrencyRegistry.model_validate_json(text)


@functools.lru_cache(maxsize=8)
def load_tier3_fuel_baselines(
    path: Path = DEFAULT_TIER3_BASELINES_JSON_PATH,
) -> Tier3FuelBaselineRegistry:
    """Strictly load and validate ``data/curated/tier3_fuel_baselines.json`` (cached, offline)."""
    text = _read_clean_json_text(path, label="tier3_fuel_baselines.json")
    return Tier3FuelBaselineRegistry.model_validate_json(text)


_DEFAULT_CURRENCY_REG: Final[CurrencyRegistry] = load_currency_registry()
_DEFAULT_TIER3_REG: Final[Tier3FuelBaselineRegistry] = load_tier3_fuel_baselines()

# All 36 Vanilla+DLC ETS2 1.62 country slugs -> ISO-2 codes (Layer 5 isolated from registry).
VANILLA_SLUG_TO_ISO2: Final[dict[str, str]] = {
    "albania": "AL",
    "austria": "AT",
    "belgium": "BE",
    "bosnia": "BA",
    "bulgaria": "BG",
    "croatia": "HR",
    "czech": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "greece": "GR",
    "hungary": "HU",
    "iceland": "IS",
    "italy": "IT",
    "kosovo": "XK",
    "latvia": "LV",
    "lithuania": "LT",
    "luxembourg": "LU",
    "macedonia": "MK",
    "montenegro": "ME",
    "netherlands": "NL",
    "norway": "NO",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "russia": "RU",
    "serbia": "RS",
    "slovakia": "SK",
    "slovenia": "SI",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "turkey": "TR",
    "uk": "GB",
}

VANILLA_36_ISO2S: Final[frozenset[str]] = frozenset(VANILLA_SLUG_TO_ISO2.values())
EXTRA_EU_TERRITORY_ISO2S: Final[frozenset[str]] = frozenset({"IE", "CY", "MT"})
EUROPEAN_TERRITORY_ISO2S: Final[frozenset[str]] = VANILLA_36_ISO2S | EXTRA_EU_TERRITORY_ISO2S

# Additional 37 ProMods EU+ME+MA+TGS v1.71 territories (40 ProMods minus IE/CY/MT already above).
PROMODS_EXTENDED_ISO2S: Final[frozenset[str]] = frozenset(
    {
        "AD",
        "AM",
        "AX",
        "AZ",
        "BY",
        "CN",
        "DZ",
        "EG",
        "FO",
        "GE",
        "GG",
        "GI",
        "GL",
        "IL",
        "IM",
        "IQ",
        "JE",
        "JO",
        "KG",
        "KZ",
        "LB",
        "LI",
        "LY",
        "MA",
        "MC",
        "MD",
        "MN",
        "PS",
        "SA",
        "SJ",
        "SM",
        "SY",
        "TJ",
        "TM",
        "TN",
        "UA",
        "UZ",
    }
)

# All 225 canonical global territories backed by data/mappings/currencies.json (D-09, D-10).
ALL_LOCKFILE_TERRITORY_ISO2S: Final[frozenset[str]] = frozenset(
    _DEFAULT_CURRENCY_REG.territory_currencies.keys()
)

# Canonical 39-territory European ISO-2 -> ISO-4217 mapping (36 Vanilla+DLC + IE, CY, MT per D-04).
TERRITORY_CURRENCIES: Final[dict[str, str]] = {
    iso2: _DEFAULT_CURRENCY_REG.territory_currencies[iso2]
    for iso2 in sorted(EUROPEAN_TERRITORY_ISO2S)
}

ALL_TERRITORY_CURRENCIES: Final[dict[str, str]] = dict(
    sorted(_DEFAULT_CURRENCY_REG.territory_currencies.items())
)

# D-07 tiered FX divergence classes for the 16 required Core European non-EUR currencies.
MAJOR_ECB_CURRENCIES: Final[frozenset[str]] = frozenset(
    code
    for code, meta in _DEFAULT_CURRENCY_REG.currencies.items()
    if meta.tier == "core" and meta.major_ecb
)
VOLATILE_NON_ECB_CURRENCIES: Final[frozenset[str]] = frozenset(
    code
    for code, meta in _DEFAULT_CURRENCY_REG.currencies.items()
    if meta.tier == "core" and not meta.major_ecb
)
ECB_COVERED_CURRENCIES: Final[frozenset[str]] = frozenset(
    code
    for code, meta in _DEFAULT_CURRENCY_REG.currencies.items()
    if meta.tier == "core" and meta.ecb_covered
)

# 18 ECB-covered extended global currencies (AUD..ZAR) + ProMods 24 + full global extended set.
EXTENDED_ECB_CURRENCIES: Final[frozenset[str]] = frozenset(
    code
    for code, meta in _DEFAULT_CURRENCY_REG.currencies.items()
    if meta.tier == "extended" and meta.ecb_covered
)
EXTENDED_PROMODS_CURRENCIES: Final[frozenset[str]] = frozenset(
    {
        "AMD",
        "AZN",
        "BYN",
        "CNY",
        "DZD",
        "EGP",
        "GEL",
        "ILS",
        "IQD",
        "JOD",
        "KGS",
        "KZT",
        "LBP",
        "LYD",
        "MAD",
        "MDL",
        "MNT",
        "SAR",
        "SYP",
        "TJS",
        "TMT",
        "TND",
        "UAH",
        "UZS",
    }
)
EXTENDED_GLOBAL_CURRENCIES: Final[frozenset[str]] = frozenset(
    code for code, meta in _DEFAULT_CURRENCY_REG.currencies.items() if meta.tier == "extended"
)


def _extract_bam_peg(registry: CurrencyRegistry) -> float:
    peg = registry.currencies["BAM"].fixed_peg_per_eur
    if peg is None:
        raise ValueError("BAM entry in currencies.json must define fixed_peg_per_eur")
    return peg


def _extract_sanity_band(meta: CurrencyMetadataEntry) -> tuple[float, float]:
    if meta.sanity_min is None or meta.sanity_max is None:
        raise ValueError("Non-pinned currency entry is missing sanity bounds")
    return (meta.sanity_min, meta.sanity_max)


# Central Bank of Bosnia and Herzegovina (CBBH) legal currency-board peg: 1 EUR = 1.95583 BAM.
BAM_FIXED_PEG_PER_EUR: Final[float] = _extract_bam_peg(_DEFAULT_CURRENCY_REG)

# Sanity magnitude envelopes (1 EUR = X <CURRENCY>) guarding against inverted X/EUR or 100x bugs.
CURRENCY_SANITY_BANDS: Final[dict[str, tuple[float, float]]] = {
    code: _extract_sanity_band(meta)
    for code, meta in sorted(_DEFAULT_CURRENCY_REG.currencies.items())
    if meta.tier == "core"
}

EXTENDED_CURRENCY_SANITY_BANDS: Final[dict[str, tuple[float, float]]] = {
    code: _extract_sanity_band(meta)
    for code, meta in sorted(_DEFAULT_CURRENCY_REG.currencies.items())
    if meta.tier == "extended"
}

ALL_CURRENCY_SANITY_BANDS: Final[dict[str, tuple[float, float]]] = dict(
    sorted({**CURRENCY_SANITY_BANDS, **EXTENDED_CURRENCY_SANITY_BANDS}.items())
)

# Deterministic reference FX rates (1 EUR = X <CURRENCY>) for offline seed & exotic fallback.
CORE_REFERENCE_FX_RATES: Final[dict[str, float]] = {
    code: meta.reference_rate_per_eur
    for code, meta in sorted(_DEFAULT_CURRENCY_REG.currencies.items())
    if meta.tier in {"pinned", "core"}
}

EXTENDED_REFERENCE_FX_RATES: Final[dict[str, float]] = {
    code: meta.reference_rate_per_eur
    for code, meta in sorted(_DEFAULT_CURRENCY_REG.currencies.items())
    if meta.tier == "extended"
}

ALL_REFERENCE_FX_RATES: Final[dict[str, float]] = dict(
    sorted({**CORE_REFERENCE_FX_RATES, **EXTENDED_REFERENCE_FX_RATES}.items())
)

# Curated EUR/L diesel seed anchors for the 37 additional ProMods EU+ME+MA+TGS territories.
PROMODS_SEED_EUR_PRICES: Final[dict[str, float]] = {
    iso2: _DEFAULT_TIER3_REG.baselines[iso2].diesel_eur_per_liter
    for iso2 in sorted(PROMODS_EXTENDED_ISO2S)
}
