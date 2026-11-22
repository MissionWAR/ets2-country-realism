"""39-territory European currency registry, FX validation tiers, BAM peg, and sanity bands."""

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

# D-07 tiered FX divergence classes:
# - Major / ECB pairs: warn at >2% divergence, reject at >10%
# - Volatile / non-ECB pairs: warn at >5% divergence, reject at >10%
MAJOR_ECB_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"GBP", "CHF", "CZK", "DKK", "HUF", "ISK", "NOK", "PLN", "RON", "SEK"}
)
VOLATILE_NON_ECB_CURRENCIES: Final[frozenset[str]] = frozenset(
    {"TRY", "RUB", "ALL", "BAM", "MKD", "RSD"}
)
ECB_COVERED_CURRENCIES: Final[frozenset[str]] = MAJOR_ECB_CURRENCIES | frozenset({"TRY"})

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
