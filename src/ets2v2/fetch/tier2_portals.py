"""Guarded Tier 2 national fuel portal scrapers with per-country circuit breakers (GLB-02)."""

from __future__ import annotations

import csv
import json
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Final, cast

import httpx
from openpyxl.utils.exceptions import InvalidFileException

from ets2v2.fetch._html import (
    Tier2EncodingError,
    decode_with_fallbacks,
    extract_html_tables,
    extract_html_text,
)
from ets2v2.fetch._parsing import extract_iso_date, parse_positive_float
from ets2v2.fetch.http import (
    HttpFetchError,
    fetch_bytes_with_retry,
    redact_url_secrets,
)
from ets2v2.fetch.models import RawCountryFuelQuote, RawFuelFeedResult
from ets2v2.normalize.models import FuelGrade

# --- IS Gasvaktin (MIT open JSON) ---
IS_GASVAKTIN_URL: Final[str] = (
    "https://raw.githubusercontent.com/gasvaktin/gasvaktin/master/vaktin/gas.min.json"
)
IS_GASVAKTIN_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"raw.githubusercontent.com"})

# --- MD ANRE ---
MD_ANRE_URL: Final[str] = "https://anre.md/"
MD_ANRE_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"anre.md", "www.anre.md"})

# --- MK ERC ---
MK_ERC_URL: Final[str] = "https://www.erc.org.mk/"
MK_ERC_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.erc.org.mk", "erc.org.mk"})

# --- AE MOEI ---
AE_MOEI_URL: Final[str] = "https://www.moei.gov.ae/en/open-data"
AE_MOEI_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.moei.gov.ae", "moei.gov.ae"})

_HTTP_RATE_LIMIT_RE: Final[re.Pattern[str]] = re.compile(r"\bHTTP\s+(?:403|429)\b")
_ISO_PREFIX_DATE_RE: Final[re.Pattern[str]] = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_DMY_DOT_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_NUM_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\d+(?:[.,]\d+)?")
_MONTH_YEAR_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{4})\b",
    flags=re.IGNORECASE,
)
_MONTH_MAP: Final[dict[str, int]] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


class Tier2RateLimitedError(RuntimeError):
    """Raised when a Tier 2 national portal returns HTTP 403/429 WAF or rate-limit responses."""


class Tier2SelectorDriftError(ValueError):
    """Raised when a Tier 2 portal markup/schema drifts and expected price selectors are absent."""


def _fold_ascii(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.strip().lower().split())


def _extract_portal_date(text: str) -> str | None:
    iso = extract_iso_date(text)
    if iso is not None:
        return iso
    iso_prefix = _ISO_PREFIX_DATE_RE.search(text)
    if iso_prefix is not None:
        try:
            return date.fromisoformat(iso_prefix.group(1)).isoformat()
        except ValueError:
            pass
    dot_match = _DMY_DOT_DATE_RE.search(text)
    if dot_match is not None:
        day_s, month_s, year_s = dot_match.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s)).isoformat()
        except ValueError:
            pass
    month_match = _MONTH_YEAR_RE.search(text)
    if month_match is not None:
        month_name, year_s = month_match.groups()
        month_num = _MONTH_MAP.get(month_name.lower())
        if month_num is not None:
            try:
                return date(int(year_s), month_num, 1).isoformat()
            except ValueError:
                pass
    return None


def _extract_first_price(cell: str) -> float | None:
    direct = parse_positive_float(cell)
    if direct is not None:
        return direct
    for match in _NUM_TOKEN_RE.finditer(cell):
        val = parse_positive_float(match.group(0))
        if val is not None:
            return val
    return None


def _run_tier2_guarded(
    feed_name: str,
    fn: Callable[[], tuple[list[RawCountryFuelQuote], str | None]],
) -> RawFuelFeedResult:
    """Execute one Tier 2 portal collector inside a strict fault-isolated circuit breaker (D-07)."""
    try:
        quotes, data_date = fn()
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=True,
            quotes=quotes,
            data_date=data_date,
        )
    except Tier2RateLimitedError as exc:
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=False,
            error_code="tier2_rate_limited",
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )
    except (Tier2EncodingError, UnicodeDecodeError) as exc:
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=False,
            error_code="tier2_encoding_error",
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )
    except Tier2SelectorDriftError as exc:
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=False,
            error_code="tier2_selector_drift",
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )
    except httpx.HTTPStatusError as exc:
        code = (
            "tier2_rate_limited"
            if exc.response.status_code in {403, 429}
            else "tier2_portal_outage"
        )
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=False,
            error_code=code,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )
    except HttpFetchError as exc:
        msg = redact_url_secrets(str(exc))
        code = "tier2_rate_limited" if _HTTP_RATE_LIMIT_RE.search(msg) else "tier2_portal_outage"
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=False,
            error_code=code,
            quotes=[],
            error=msg,
        )
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        OSError,
        csv.Error,
        InvalidFileException,
        zipfile.BadZipFile,
        ET.ParseError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=False,
            error_code="tier2_portal_outage",
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )


def fetch_is_gasvaktin(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Iceland Gasvaktin open JSON (MIT License) median station retail prices in ISK/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            IS_GASVAKTIN_URL,
            allowed_hosts=IS_GASVAKTIN_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        text = decode_with_fallbacks(raw, encodings=("utf-8-sig",))
        payload: object = json.loads(text)
        if not isinstance(payload, dict):
            raise Tier2SelectorDriftError("Gasvaktin JSON root is not an object")
        obj = cast(dict[object, object], payload)
        raw_stations = obj.get("stations")
        if not isinstance(raw_stations, list):
            raise Tier2SelectorDriftError("Gasvaktin JSON missing 'stations' list")

        petrol_vals: list[float] = []
        diesel_vals: list[float] = []
        for item in cast(list[object], raw_stations):
            if not isinstance(item, dict):
                continue
            station = cast(dict[object, object], item)
            p95 = parse_positive_float(station.get("bensin95"))
            if p95 is not None:
                petrol_vals.append(p95)
            dsl = parse_positive_float(station.get("diesel"))
            if dsl is not None:
                diesel_vals.append(dsl)

        prices: dict[FuelGrade, float] = {}
        if petrol_vals:
            prices["petrol_95"] = float(statistics.median(petrol_vals))
        if diesel_vals:
            prices["diesel"] = float(statistics.median(diesel_vals))
        if not prices:
            raise Tier2SelectorDriftError(
                "Gasvaktin JSON contained no valid positive bensin95/diesel prices"
            )

        raw_ts_changes = obj.get("timestampPriceChanges")
        raw_ts_check = obj.get("timestampPriceCheck")
        data_date = (
            (_extract_portal_date(raw_ts_changes) if isinstance(raw_ts_changes, str) else None)
            or (_extract_portal_date(raw_ts_check) if isinstance(raw_ts_check, str) else None)
            or datetime.now(UTC).date().isoformat()
        )
        quote = RawCountryFuelQuote(
            iso2="IS",
            currency="ISK",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="is_gasvaktin",
            license="MIT License (Gasvaktin)",
            data_date=data_date,
        )
        return [quote], data_date

    return _run_tier2_guarded("is_gasvaktin", _run)


def fetch_md_anre(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Moldova ANRE HTML retail fuel ceiling prices (Benzina COR 95 / Motorina) in MDL/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            MD_ANRE_URL,
            allowed_hosts=MD_ANRE_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        html = decode_with_fallbacks(raw, encodings=("utf-8-sig",))
        tables = extract_html_tables(html)
        blocks = extract_html_text(html)

        prices: dict[FuelGrade, float] = {}
        for table in tables:
            for row in table:
                if len(row) < 2:
                    continue
                label = _fold_ascii(row[0])
                val = _extract_first_price(row[1])
                if val is None:
                    continue
                if ("cor 95" in label or ("benzina" in label and "95" in label)) and (
                    "petrol_95" not in prices
                ):
                    prices["petrol_95"] = val
                elif "motorin" in label and "diesel" not in prices:
                    prices["diesel"] = val

        # Fallback to text blocks if ANRE switches from <table> to <div> cards
        if "petrol_95" not in prices or "diesel" not in prices:
            for block in blocks:
                folded = _fold_ascii(block)
                if "petrol_95" not in prices and (
                    "cor 95" in folded or ("benzina" in folded and "95" in folded)
                ):
                    after = re.sub(r".*?95\b", "", folded, count=1)
                    val = _extract_first_price(after)
                    if val is not None:
                        prices["petrol_95"] = val
                elif "diesel" not in prices and "motorin" in folded:
                    after = re.sub(r".*?motorin\w*", "", folded, count=1)
                    val = _extract_first_price(after)
                    if val is not None:
                        prices["diesel"] = val

        if "diesel" not in prices and "petrol_95" not in prices:
            raise Tier2SelectorDriftError(
                "ANRE Moldova HTML missing Benzina COR 95 / Motorina ceiling prices"
            )

        full_text = "\n".join(blocks)
        data_date = _extract_portal_date(full_text) or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="MD",
            currency="MDL",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="md_anre",
            license="ANRE Moldova public tariff",
            data_date=data_date,
        )
        return [quote], data_date

    return _run_tier2_guarded("md_anre", _run)


def fetch_mk_erc(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch North Macedonia ERC HTML table (Cyrillic/Latin grades, comma decimals) in MKD/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            MK_ERC_URL,
            allowed_hosts=MK_ERC_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        html = decode_with_fallbacks(raw, encodings=("utf-8-sig", "windows-1251"))
        tables = extract_html_tables(html)
        blocks = extract_html_text(html)

        prices: dict[FuelGrade, float] = {}
        for table in tables:
            for row in table:
                if len(row) < 2:
                    continue
                label_raw = row[0].strip().lower()
                label_ascii = _fold_ascii(row[0])
                price_val: float | None = None
                for cell in row[1:]:
                    parsed = _extract_first_price(cell)
                    if parsed is not None:
                        price_val = parsed
                        break
                if price_val is None:
                    continue

                is_super = "еуросупер" in label_raw or "eurosuper" in label_ascii
                is_diesel = "еуродизел" in label_raw or "eurodiesel" in label_ascii
                if is_super and "95" in label_raw and "petrol_95" not in prices:
                    prices["petrol_95"] = price_val
                elif is_super and "98" in label_raw and "petrol_98" not in prices:
                    prices["petrol_98"] = price_val
                elif is_diesel and "diesel" not in prices:
                    prices["diesel"] = price_val

        if "diesel" not in prices and "petrol_95" not in prices:
            raise Tier2SelectorDriftError(
                "ERC North Macedonia HTML missing ЕУРОСУПЕР/ЕУРОДИЗЕЛ price rows"
            )

        data_date = _extract_portal_date("\n".join(blocks)) or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="MK",
            currency="MKD",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="mk_erc",
            license="ERC North Macedonia public tariff",
            data_date=data_date,
        )
        return [quote], data_date

    return _run_tier2_guarded("mk_erc", _run)


def fetch_ae_moei(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch UAE MOEI monthly regulated retail fuel prices HTML table in AED/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            AE_MOEI_URL,
            allowed_hosts=AE_MOEI_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        html = decode_with_fallbacks(raw, encodings=("utf-8-sig",))
        tables = extract_html_tables(html)
        blocks = extract_html_text(html)

        prices: dict[FuelGrade, float] = {}
        for table in tables:
            for row in table:
                if len(row) < 2:
                    continue
                label = _fold_ascii(row[0])
                price_val: float | None = None
                for cell in row[1:]:
                    parsed = _extract_first_price(cell)
                    if parsed is not None:
                        price_val = parsed
                        break
                if price_val is None:
                    continue

                if "diesel" in label and "diesel" not in prices:
                    prices["diesel"] = price_val
                elif "special" in label and "95" in label and "petrol_95" not in prices:
                    prices["petrol_95"] = price_val
                elif "super" in label and "98" in label and "petrol_98" not in prices:
                    prices["petrol_98"] = price_val
                elif (
                    ("e-plus" in label or "e plus" in label)
                    and "91" in label
                    and ("petrol_92" not in prices)
                ):
                    prices["petrol_92"] = price_val

        if "diesel" not in prices and "petrol_95" not in prices:
            raise Tier2SelectorDriftError(
                "UAE MOEI HTML table missing expected Diesel / Special 95 rows"
            )

        data_date = _extract_portal_date("\n".join(blocks)) or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="AE",
            currency="AED",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="ae_moei",
            license="UAE MOEI open data",
            data_date=data_date,
        )
        return [quote], data_date

    return _run_tier2_guarded("ae_moei", _run)
