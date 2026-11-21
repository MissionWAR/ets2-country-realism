"""EC Weekly Oil Bulletin dynamic .xlsx collector plus FionnHughes & fuel-prices.eu fallbacks."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from typing import Final, cast
from urllib.parse import urljoin

import httpx
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from ets2v2.fetch.http import (
    HttpFetchError,
    fetch_bytes_with_retry,
    redact_url_secrets,
    validate_https_url,
)
from ets2v2.fetch.models import RawCountryFuelQuote, RawFuelFeedResult
from ets2v2.normalize.currencies import EUROPEAN_TERRITORY_ISO2S
from ets2v2.normalize.fuel import normalize_iso2_alias
from ets2v2.normalize.models import FuelGrade

EC_WOB_LANDING_URL: Final[str] = (
    "https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en"
)
EC_WOB_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"energy.ec.europa.eu", "ec.europa.eu"})
EC_WOB_MAX_XLSX_BYTES: Final[int] = 20_971_520  # 20 MiB (T-03-08)
EC_WOB_MAX_ROWS: Final[int] = 5000  # T-03-08

FIONNHUGHES_CSV_URL: Final[str] = (
    "https://huggingface.co/datasets/FionnHughes/eu-weekly-oil-bulletin/raw/main/eu_oil_bulletin.csv"
)
FIONNHUGHES_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"huggingface.co", "cdn-lfs.hf.co", "cdn-lfs.huggingface.co", "cdn-lfs-us-1.huggingface.co"}
)

FUEL_PRICES_EU_URL: Final[str] = "https://www.fuel-prices.eu/board_now.php"
FUEL_PRICES_EU_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.fuel-prices.eu"})

_EU27_ISO2S: Final[frozenset[str]] = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
    }
)

_EU_COUNTRY_NAMES_TO_ISO2: Final[dict[str, str]] = {
    "austria": "AT",
    "belgium": "BE",
    "bulgaria": "BG",
    "croatia": "HR",
    "cyprus": "CY",
    "czech republic": "CZ",
    "czechia": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "greece": "GR",
    "hungary": "HU",
    "ireland": "IE",
    "italy": "IT",
    "latvia": "LV",
    "lithuania": "LT",
    "luxembourg": "LU",
    "malta": "MT",
    "netherlands": "NL",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "slovakia": "SK",
    "slovenia": "SI",
    "spain": "ES",
    "sweden": "SE",
}

_ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DMY_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


class _AnchorExtractor(HTMLParser):
    """Minimal stdlib HTMLParser extracting ``(href, link_text)`` pairs from ``<a>`` tags."""

    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for attr_name, attr_val in attrs:
            if attr_name.lower() == "href" and attr_val:
                self._current_href = attr_val.strip()
                self._text_parts = []
                break

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href is not None:
            text = " ".join("".join(self._text_parts).split())
            self.anchors.append((self._current_href, text))
            self._current_href = None
            self._text_parts = []


def discover_ec_wob_xlsx_url(
    html_text: str,
    base_url: str = EC_WOB_LANDING_URL,
) -> str:
    """Discover the EC Weekly Oil Bulletin 'Prices with taxes' .xlsx URL under HTTPS allowlist."""
    parser = _AnchorExtractor()
    parser.feed(html_text)
    parser.close()

    scored: list[tuple[int, str]] = []
    for href, text in parser.anchors:
        combined_lower = f"{href} {text}".lower()
        href_lower = href.lower()
        text_lower = text.lower()

        is_download_candidate = (
            ".xlsx" in href_lower
            or "/document/download/" in href_lower
            or "weekly_oil_bulletin" in href_lower
            or "prices with taxes" in text_lower
        )
        if not is_download_candidate:
            continue

        score = 0
        if "prices with taxes" in text_lower or "prices_with_taxes" in href_lower:
            score += 10
        if "without taxes" in combined_lower or "net price" in combined_lower:
            score -= 8
        if ".xlsx" in href_lower:
            score += 5
        if "/document/download/" in href_lower:
            score += 4
        if "weekly" in combined_lower or "bulletin" in combined_lower:
            score += 2
        if score > 0:
            scored.append((score, href))

    if not scored:
        raise ValueError("Could not discover EC Weekly Oil Bulletin 'Prices with taxes' .xlsx link")

    scored.sort(key=lambda item: item[0], reverse=True)
    best_href = scored[0][1]
    resolved = urljoin(base_url, best_href)
    return validate_https_url(resolved, EC_WOB_ALLOWED_HOSTS)


def _extract_iso_date(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        return None
    iso_match = _ISO_DATE_RE.search(value)
    if iso_match is not None:
        return iso_match.group(1)
    dmy_match = _DMY_DATE_RE.search(value)
    if dmy_match is not None:
        day_s, month_s, year_s = dmy_match.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s)).isoformat()
        except ValueError:
            return None
    return None


def _parse_positive_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) and num > 0.0 else None
    if isinstance(value, str):
        cleaned = value.strip().replace("\u00a0", "").replace(" ", "")
        if not cleaned or cleaned in {"-", "N/A", "n/a", "NA", ".."}:
            return None
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
        try:
            num = float(cleaned)
        except ValueError:
            return None
        return num if math.isfinite(num) and num > 0.0 else None
    return None


def _resolve_eu_iso2(cell_value: object) -> str | None:
    if not isinstance(cell_value, str):
        return None
    raw = cell_value.strip()
    if not raw:
        return None
    if len(raw) == 2 and raw.isascii() and raw.isalpha():
        iso2 = normalize_iso2_alias(raw)
        return iso2 if iso2 in _EU27_ISO2S else None
    # Strip footnote markers such as "Greece (1)" or "DE*"
    base = re.sub(r"\s*\([^)]*\)\s*$", "", raw).rstrip("* ").strip()
    if len(base) == 2 and base.isascii() and base.isalpha():
        iso2 = normalize_iso2_alias(base)
        return iso2 if iso2 in _EU27_ISO2S else None
    return _EU_COUNTRY_NAMES_TO_ISO2.get(base.lower())


def _match_ec_grade_header(text: str) -> FuelGrade | None:
    lower = " ".join(text.lower().split())
    if not lower:
        return None
    if "heating" in lower or "heavy fuel" in lower:
        return None
    if "euro-super" in lower or "euro super" in lower or "super 95" in lower or "95" in lower:
        return "petrol_95"
    if "automotive gas oil" in lower or "gas oil" in lower or "diesel" in lower:
        return "diesel"
    if "lpg" in lower:
        return "lpg"
    return None


def parse_ec_wob_xlsx(
    raw_xlsx: bytes,
    *,
    max_rows: int = EC_WOB_MAX_ROWS,
    default_date: str | None = None,
) -> tuple[list[RawCountryFuelQuote], str]:
    """Parse an EC Weekly Oil Bulletin .xlsx workbook (EUR/1000L -> EUR/L, EL->GR, capped rows)."""
    if len(raw_xlsx) > EC_WOB_MAX_XLSX_BYTES:
        raise ValueError(
            f"EC WOB .xlsx payload size {len(raw_xlsx)} exceeds max {EC_WOB_MAX_XLSX_BYTES} bytes"
        )

    wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx), read_only=True, data_only=True)
    try:
        sheet_names = list(wb.sheetnames)
        # Prefer sheets mentioning "price" / "tax"
        ordered_sheets = sorted(
            sheet_names,
            key=lambda name: (
                0 if ("price" in name.lower() and "without" not in name.lower()) else 1
            ),
        )

        scanned_rows = 0
        for sheet_name in ordered_sheets:
            ws = wb[sheet_name]
            detected_date: str | None = None
            country_col: int | None = None
            grade_cols: dict[FuelGrade, int] = {}
            quotes_by_iso2: dict[str, dict[FuelGrade, float]] = {}

            for row in ws.iter_rows(values_only=True):
                scanned_rows += 1
                if scanned_rows > max_rows:
                    break

                if country_col is None:
                    # Scan preamble rows for date and header columns
                    for cell in row:
                        if detected_date is None:
                            maybe_date = _extract_iso_date(cell)
                            if maybe_date is not None:
                                detected_date = maybe_date

                    candidate_grades: dict[FuelGrade, int] = {}
                    candidate_country_col: int | None = None
                    for idx, cell in enumerate(row):
                        if not isinstance(cell, str):
                            continue
                        cell_lower = " ".join(cell.lower().split())
                        if candidate_country_col is None and (
                            "country" in cell_lower
                            or "member state" in cell_lower
                            or cell_lower in {"iso", "code", "geo", "ms"}
                        ):
                            candidate_country_col = idx
                        matched_grade = _match_ec_grade_header(cell)
                        if matched_grade is not None and matched_grade not in candidate_grades:
                            candidate_grades[matched_grade] = idx

                    if "diesel" in candidate_grades and "petrol_95" in candidate_grades:
                        country_col = (
                            candidate_country_col if candidate_country_col is not None else 0
                        )
                        grade_cols = candidate_grades
                    continue

                if country_col >= len(row):
                    continue
                iso2 = _resolve_eu_iso2(row[country_col])
                if iso2 is None:
                    continue

                prices: dict[FuelGrade, float] = {}
                for grade, col_idx in grade_cols.items():
                    if col_idx >= len(row):
                        continue
                    num = _parse_positive_float(row[col_idx])
                    if num is not None:
                        prices[grade] = num / 1000.0
                if prices:
                    quotes_by_iso2[iso2] = prices

            if quotes_by_iso2:
                resolved_date = (
                    detected_date or default_date or datetime.now(UTC).date().isoformat()
                )
                quotes = [
                    RawCountryFuelQuote(
                        iso2=iso2,
                        currency="EUR",
                        prices_by_grade=quotes_by_iso2[iso2],
                        unit_basis="eur_per_liter",
                        source="ec_weekly_oil_bulletin",
                        license="CC BY 4.0",
                        data_date=resolved_date,
                    )
                    for iso2 in sorted(quotes_by_iso2)
                ]
                return quotes, resolved_date
    finally:
        wb.close()

    raise ValueError("EC Weekly Oil Bulletin workbook contained no parseable EU-27 fuel price rows")


def fetch_ec_weekly_oil_bulletin(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Discover and fetch the latest EC Weekly Oil Bulletin .xlsx with strict SSRF & OOXML caps."""
    try:
        landing_bytes = fetch_bytes_with_retry(
            client,
            EC_WOB_LANDING_URL,
            allowed_hosts=EC_WOB_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        landing_html = landing_bytes.decode("utf-8", errors="replace")
        xlsx_url = discover_ec_wob_xlsx_url(landing_html, EC_WOB_LANDING_URL)
        raw_xlsx = fetch_bytes_with_retry(
            client,
            xlsx_url,
            allowed_hosts=EC_WOB_ALLOWED_HOSTS,
            max_bytes=EC_WOB_MAX_XLSX_BYTES,
            sleep_fn=sleep_fn,
        )
        quotes, data_date = parse_ec_wob_xlsx(raw_xlsx)
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        OSError,
        InvalidFileException,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="ec_weekly_oil_bulletin",
            tier="tier1",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="ec_weekly_oil_bulletin",
        tier="tier1",
        ok=True,
        quotes=quotes,
        data_date=data_date,
    )


def fetch_fionnhughes_fallback(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch FionnHughes CC BY 4.0 tidy CSV mirror of EC Weekly Oil Bulletin."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            FIONNHUGHES_CSV_URL,
            allowed_hosts=FIONNHUGHES_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("FionnHughes CSV is missing header row")

        field_map = {name.strip().lower(): name for name in reader.fieldnames if name}
        date_col = field_map.get("date") or field_map.get("week") or field_map.get("period")
        geo_col = (
            field_map.get("geo")
            or field_map.get("country")
            or field_map.get("country_code")
            or field_map.get("iso2")
        )
        product_col = (
            field_map.get("product") or field_map.get("fuel") or field_map.get("fuel_type")
        )
        price_col = (
            field_map.get("price")
            or field_map.get("value")
            or field_map.get("price_with_tax")
            or field_map.get("eur_per_1000l")
            or field_map.get("eur_per_liter")
        )
        if not (date_col and geo_col and product_col and price_col):
            raise ValueError(
                f"FionnHughes CSV missing expected columns; got {list(reader.fieldnames)}"
            )

        # Track latest date per (iso2, grade)
        latest: dict[str, tuple[str, dict[FuelGrade, float]]] = {}
        for row in reader:
            row_date = _extract_iso_date(row.get(date_col, ""))
            if row_date is None:
                continue
            iso2 = _resolve_eu_iso2(row.get(geo_col, ""))
            if iso2 is None:
                continue
            grade = _match_ec_grade_header(str(row.get(product_col, "")))
            if grade is None:
                continue
            raw_price = _parse_positive_float(row.get(price_col, ""))
            if raw_price is None:
                continue
            eur_per_liter = raw_price / 1000.0 if raw_price > 20.0 else raw_price

            prev = latest.get(iso2)
            if prev is None or row_date > prev[0]:
                latest[iso2] = (row_date, {grade: eur_per_liter})
            elif row_date == prev[0]:
                prev[1][grade] = eur_per_liter

        if not latest:
            raise ValueError("FionnHughes CSV yielded zero EU-27 fuel quotes")

        overall_date = max(entry[0] for entry in latest.values())
        quotes = [
            RawCountryFuelQuote(
                iso2=iso2,
                currency="EUR",
                prices_by_grade=latest[iso2][1],
                unit_basis="eur_per_liter",
                source="fionnhughes_ec_wob",
                license="CC BY 4.0",
                data_date=latest[iso2][0],
            )
            for iso2 in sorted(latest)
        ]
    except (HttpFetchError, httpx.HTTPError, ValueError, KeyError, OSError) as exc:
        return RawFuelFeedResult(
            feed_name="fionnhughes_ec_wob",
            tier="fallback",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="fionnhughes_ec_wob",
        tier="fallback",
        ok=True,
        quotes=quotes,
        data_date=overall_date,
    )


def fetch_fuel_prices_eu(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch ``fuel-prices.eu/board_now.php`` CC BY 4.0 live EUR/L feed (covering IS & non-EU)."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            FUEL_PRICES_EU_URL,
            allowed_hosts=FUEL_PRICES_EU_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("fuel-prices.eu payload is not a JSON object")
        obj = cast(dict[object, object], payload)
        if obj.get("ok") is not True:
            raise ValueError(f"fuel-prices.eu returned ok={obj.get('ok')!r}")

        ts_val = obj.get("ts")
        if isinstance(ts_val, (int, float)) and not isinstance(ts_val, bool) and ts_val > 0:
            data_date = datetime.fromtimestamp(float(ts_val), tz=UTC).date().isoformat()
        else:
            data_date = datetime.now(UTC).date().isoformat()

        by_iso2: dict[str, dict[FuelGrade, float]] = {}
        grade_sections: tuple[tuple[str, FuelGrade], ...] = (
            ("petrol", "petrol_95"),
            ("diesel", "diesel"),
        )
        for json_key, grade in grade_sections:
            section = obj.get(json_key)
            if not isinstance(section, dict):
                continue
            section_map = cast(dict[object, object], section)
            for raw_code, raw_val in section_map.items():
                if not isinstance(raw_code, str):
                    continue
                iso2 = normalize_iso2_alias(raw_code)
                if iso2 not in EUROPEAN_TERRITORY_ISO2S:
                    continue
                price = _parse_positive_float(raw_val)
                if price is None:
                    continue
                by_iso2.setdefault(iso2, {})[grade] = price

        if not by_iso2:
            raise ValueError("fuel-prices.eu returned zero European territory fuel quotes")

        quotes = [
            RawCountryFuelQuote(
                iso2=iso2,
                currency="EUR",
                prices_by_grade=by_iso2[iso2],
                unit_basis="eur_per_liter",
                source="fuel_prices_eu",
                license="CC BY 4.0",
                data_date=data_date,
            )
            for iso2 in sorted(by_iso2)
        ]
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="fuel_prices_eu",
            tier="fallback",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="fuel_prices_eu",
        tier="fallback",
        ok=True,
        quotes=quotes,
        data_date=data_date,
    )
