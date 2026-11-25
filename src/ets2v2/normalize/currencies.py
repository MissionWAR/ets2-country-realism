"""39-territory European + 37 ProMods (76 total) currency registry, FX tiers, and sanity bands."""

from __future__ import annotations

from typing import Final

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
ALL_LOCKFILE_TERRITORY_ISO2S: Final[frozenset[str]] = (
    EUROPEAN_TERRITORY_ISO2S | PROMODS_EXTENDED_ISO2S
)

# Canonical 39-territory ISO-2 -> ISO-4217 mapping (36 Vanilla+DLC + IE, CY, MT per D-04).
# Bulgaria (BG) adopted EUR on 2026-01-01; Montenegro (ME) and Kosovo (XK) use EUR unilaterally.
TERRITORY_CURRENCIES: Final[dict[str, str]] = {
    "AL": "ALL",
    "AT": "EUR",
    "BA": "BAM",
    "BE": "EUR",
    "BG": "EUR",
    "CH": "CHF",
    "CY": "EUR",
    "CZ": "CZK",
    "DE": "EUR",
    "DK": "DKK",
    "EE": "EUR",
    "ES": "EUR",
    "FI": "EUR",
    "FR": "EUR",
    "GB": "GBP",
    "GR": "EUR",
    "HR": "EUR",
    "HU": "HUF",
    "IE": "EUR",
    "IS": "ISK",
    "IT": "EUR",
    "LT": "EUR",
    "LU": "EUR",
    "LV": "EUR",
    "ME": "EUR",
    "MK": "MKD",
    "MT": "EUR",
    "NL": "EUR",
    "NO": "NOK",
    "PL": "PLN",
    "PT": "EUR",
    "RO": "RON",
    "RS": "RSD",
    "RU": "RUB",
    "SE": "SEK",
    "SI": "EUR",
    "SK": "EUR",
    "TR": "TRY",
    "XK": "EUR",
}

_PROMODS_EXTENDED_TERRITORY_CURRENCIES: Final[dict[str, str]] = {
    "AD": "EUR",
    "AM": "AMD",
    "AX": "EUR",
    "AZ": "AZN",
    "BY": "BYN",
    "CN": "CNY",
    "DZ": "DZD",
    "EG": "EGP",
    "FO": "DKK",
    "GE": "GEL",
    "GG": "GBP",
    "GI": "GBP",
    "GL": "DKK",
    "IL": "ILS",
    "IM": "GBP",
    "IQ": "IQD",
    "JE": "GBP",
    "JO": "JOD",
    "KG": "KGS",
    "KZ": "KZT",
    "LB": "LBP",
    "LI": "CHF",
    "LY": "LYD",
    "MA": "MAD",
    "MC": "EUR",
    "MD": "MDL",
    "MN": "MNT",
    "PS": "ILS",
    "SA": "SAR",
    "SJ": "NOK",
    "SM": "EUR",
    "SY": "SYP",
    "TJ": "TJS",
    "TM": "TMT",
    "TN": "TND",
    "UA": "UAH",
    "UZ": "UZS",
}

ALL_TERRITORY_CURRENCIES: Final[dict[str, str]] = dict(
    sorted({**TERRITORY_CURRENCIES, **_PROMODS_EXTENDED_TERRITORY_CURRENCIES}.items())
)

# D-07 tiered FX divergence classes for the 16 required Core European non-EUR currencies:
# - Major / ECB pairs: warn at >2% divergence, reject at >10%
# - Volatile / non-ECB pairs: warn at >5% divergence, reject at >10%
MAJOR_ECB_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"GBP", "CHF", "CZK", "DKK", "HUF", "ISK", "NOK", "PLN", "RON", "SEK"}
)
VOLATILE_NON_ECB_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"TRY", "RUB", "ALL", "BAM", "MKD", "RSD"}
)
ECB_COVERED_CURRENCIES: Final[frozenset[str]] = MAJOR_ECB_CURRENCIES | frozenset({"TRY"})

# 24 extended ProMods EU+ME+MA+TGS currencies (isolated from required Core European CI gate).
EXTENDED_ECB_CURRENCIES: Final[frozenset[str]] = frozenset({"CNY", "ILS"})
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

# Central Bank of Bosnia and Herzegovina (CBBH) legal currency-board peg: 1 EUR = 1.95583 BAM.
BAM_FIXED_PEG_PER_EUR: Final[float] = 1.95583

# Sanity magnitude envelopes (1 EUR = X <CURRENCY>) guarding against inverted X/EUR or 100x bugs.
CURRENCY_SANITY_BANDS: Final[dict[str, tuple[float, float]]] = {
    "ALL": (70.0, 160.0),
    "BAM": (1.90, 2.01),
    "CHF": (0.70, 1.40),
    "CZK": (18.0, 35.0),
    "DKK": (7.00, 7.90),
    "GBP": (0.60, 1.25),
    "HUF": (250.0, 550.0),
    "ISK": (100.0, 250.0),
    "MKD": (55.0, 70.0),
    "NOK": (7.5, 16.0),
    "PLN": (3.2, 6.0),
    "RON": (3.8, 6.5),
    "RSD": (95.0, 145.0),
    "RUB": (40.0, 250.0),
    "SEK": (8.0, 15.0),
    "TRY": (15.0, 120.0),
}

# Post-2026-01-01 redenominated SYP (1 new SYP = 100 old SYP) rejects old ~14,000 quotes (T-04-03).
EXTENDED_CURRENCY_SANITY_BANDS: Final[dict[str, tuple[float, float]]] = {
    "AMD": (250.0, 700.0),
    "AZN": (1.2, 2.8),
    "BYN": (2.0, 6.0),
    "CNY": (5.0, 12.0),
    "DZD": (100.0, 220.0),
    "EGP": (25.0, 100.0),
    "GEL": (2.0, 4.5),
    "ILS": (2.5, 6.0),
    "IQD": (900.0, 2200.0),
    "JOD": (0.55, 1.10),
    "KGS": (65.0, 140.0),
    "KZT": (350.0, 800.0),
    "LBP": (60000.0, 150000.0),
    "LYD": (3.5, 8.0),
    "MAD": (8.5, 13.5),
    "MDL": (14.0, 26.0),
    "MNT": (2500.0, 5500.0),
    "SAR": (3.0, 5.2),
    "SYP": (80.0, 250.0),
    "TJS": (8.0, 18.0),
    "TMT": (2.5, 6.0),
    "TND": (2.5, 4.5),
    "UAH": (30.0, 75.0),
    "UZS": (9000.0, 22000.0),
}

ALL_CURRENCY_SANITY_BANDS: Final[dict[str, tuple[float, float]]] = dict(
    sorted({**CURRENCY_SANITY_BANDS, **EXTENDED_CURRENCY_SANITY_BANDS}.items())
)

# Deterministic reference FX rates (1 EUR = X <CURRENCY>) for offline seed & exotic fallback.
CORE_REFERENCE_FX_RATES: Final[dict[str, float]] = {
    "ALL": 98.5,
    "BAM": BAM_FIXED_PEG_PER_EUR,
    "CHF": 0.94,
    "CZK": 25.2,
    "DKK": 7.46,
    "EUR": 1.0,
    "GBP": 0.84,
    "HUF": 400.0,
    "ISK": 148.0,
    "MKD": 61.5,
    "NOK": 11.7,
    "PLN": 4.30,
    "RON": 4.97,
    "RSD": 117.1,
    "RUB": 95.0,
    "SEK": 11.4,
    "TRY": 36.5,
}

EXTENDED_REFERENCE_FX_RATES: Final[dict[str, float]] = {
    "AMD": 420.0,
    "AZN": 1.85,
    "BYN": 3.55,
    "CNY": 7.85,
    "DZD": 146.0,
    "EGP": 53.0,
    "GEL": 2.95,
    "ILS": 4.00,
    "IQD": 1420.0,
    "JOD": 0.77,
    "KGS": 94.0,
    "KZT": 535.0,
    "LBP": 97000.0,
    "LYD": 5.25,
    "MAD": 10.80,
    "MDL": 19.40,
    "MNT": 3700.0,
    "SAR": 4.08,
    "SYP": 140.0,
    "TJS": 11.60,
    "TMT": 3.80,
    "TND": 3.38,
    "UAH": 45.0,
    "UZS": 13900.0,
}

ALL_REFERENCE_FX_RATES: Final[dict[str, float]] = dict(
    sorted({**CORE_REFERENCE_FX_RATES, **EXTENDED_REFERENCE_FX_RATES}.items())
)

# Curated EUR/L diesel seed anchors for the 37 additional ProMods EU+ME+MA+TGS territories (D-01).
PROMODS_SEED_EUR_PRICES: Final[dict[str, float]] = {
    "AD": 1.490,
    "AM": 1.380,
    "AX": 1.880,
    "AZ": 0.590,
    "BY": 0.760,
    "CN": 1.020,
    "DZ": 0.201,
    "EG": 0.348,
    "FO": 1.950,
    "GE": 1.120,
    "GG": 1.850,
    "GI": 1.560,
    "GL": 0.810,
    "IL": 1.920,
    "IM": 1.850,
    "IQ": 0.239,
    "JE": 1.850,
    "JO": 1.151,
    "KG": 0.850,
    "KZ": 0.650,
    "LB": 1.257,
    "LI": 1.940,
    "LY": 0.028,
    "MA": 1.280,
    "MC": 1.850,
    "MD": 1.280,
    "MN": 0.980,
    "PS": 1.920,
    "SA": 0.433,
    "SJ": 1.650,
    "SM": 1.780,
    "SY": 1.094,
    "TJ": 1.100,
    "TM": 0.259,
    "TN": 0.661,
    "UA": 1.320,
    "UZ": 1.050,
}
