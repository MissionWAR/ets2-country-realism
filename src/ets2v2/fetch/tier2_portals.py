"""Guarded Tier 2 national fuel portal scrapers with per-country circuit breakers (GLB-02)."""

from __future__ import annotations

import csv
import io
import json
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Final, cast
from urllib.parse import urljoin, urlsplit

import httpx
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from ets2v2.fetch._html import (
    Tier2EncodingError,
    decode_with_fallbacks,
    extract_html_tables,
    extract_html_text,
)
from ets2v2.fetch._parsing import (
    AnchorExtractor,
    extract_iso_date,
    parse_positive_float,
    validate_ooxml_zip_safety,
)
from ets2v2.fetch.http import (
    HttpFetchError,
    fetch_bytes_with_retry,
    redact_url_secrets,
    validate_https_url,
)
from ets2v2.fetch.models import RawCountryFuelQuote, RawFuelFeedResult
from ets2v2.normalize.models import FuelGrade

TIER2_MAX_XLSX_BYTES: Final[int] = 20_971_520  # 20 MiB cap for national portal .xlsx attachments
TIER2_MAX_XLSX_ROWS: Final[int] = 5000

# --- IS Gasvaktin (MIT open JSON) ---
IS_GASVAKTIN_URL: Final[str] = (
    "https://raw.githubusercontent.com/gasvaktin/gasvaktin/master/vaktin/gas.min.json"
)
IS_GASVAKTIN_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"raw.githubusercontent.com"})

# --- CH BFS / LIK (PxWeb JSON-stat2 or CSV) ---
CH_BFS_LIK_URL: Final[str] = (
    "https://www.pxweb.bfs.admin.ch/api/v1/de/px-x-0501000000_105/px-x-0501000000_105.px"
)
CH_BFS_LIK_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"www.pxweb.bfs.admin.ch", "dam-api.bfs.admin.ch"}
)

# --- MD ANRE ---
MD_ANRE_URL: Final[str] = "https://anre.md/"
MD_ANRE_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"anre.md", "www.anre.md"})

# --- MK ERC ---
MK_ERC_URL: Final[str] = "https://www.erc.org.mk/"
MK_ERC_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.erc.org.mk", "erc.org.mk"})

# --- RU Rosstat ---
RU_ROSSTAT_URL: Final[str] = "https://rosstat.gov.ru/folder/313/document/126955"
RU_ROSSTAT_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"rosstat.gov.ru", "www.rosstat.gov.ru"}
)

# --- IL Ministry of Energy ---
IL_MOE_URL: Final[str] = "https://www.gov.il/en/departments/units/fuel_prices"
IL_MOE_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.gov.il", "gov.il"})

# --- AE MOEI ---
AE_MOEI_URL: Final[str] = "https://www.moei.gov.ae/en/open-data"
AE_MOEI_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.moei.gov.ae", "moei.gov.ae"})

# --- ZA DMRE / CEF ---
ZA_DMRE_CEF_URL: Final[str] = "https://cefgroup.co.za/energy-data/daily-basic-fuel-price/"
ZA_DMRE_CEF_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"cefgroup.co.za", "www.cefgroup.co.za", "www.dmre.gov.za"}
)

# --- SA Saudi Aramco ---
SA_ARAMCO_URL: Final[str] = "https://www.aramco.com/en/what-we-do/energy-products/retail-fuels"
SA_ARAMCO_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.aramco.com"})

# --- NG Nigeria NBS ---
NG_NBS_URL: Final[str] = "https://nigerianstat.gov.ng/"
NG_NBS_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"nigerianstat.gov.ng", "www.nigerianstat.gov.ng", "microdata.nigerianstat.gov.ng"}
)

TIER2_PORTAL_FEED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "is_gasvaktin",
        "ch_bfs_lik",
        "md_anre",
        "mk_erc",
        "ru_rosstat",
        "il_moe",
        "ae_moei",
        "za_dmre_cef",
        "sa_aramco",
        "ng_nbs",
    }
)

_HTTP_RATE_LIMIT_RE: Final[re.Pattern[str]] = re.compile(r"\bHTTP\s+(?:403|429)\b")
_DMY_DOT_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_PXWEB_MONTH_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4})[Mm-](\d{2})$")
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


def _discover_xlsx_links(
    html_text: str,
    base_url: str,
    allowed_hosts: frozenset[str],
) -> list[tuple[str, str]]:
    parser = AnchorExtractor()
    parser.feed(html_text)
    parser.close()
    links: list[tuple[str, str]] = []
    for href, link_text in parser.anchors:
        resolved = urljoin(base_url, href)
        path_lower = urlsplit(resolved).path.lower()
        if not path_lower.endswith(".xlsx"):
            continue
        try:
            validated = validate_https_url(resolved, allowed_hosts)
        except ValueError:
            continue
        links.append((validated, link_text))
    return links


def _iter_xlsx_rows(raw_xlsx: bytes) -> list[list[object]]:
    validate_ooxml_zip_safety(raw_xlsx)
    wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx), read_only=True, data_only=True)
    rows: list[list[object]] = []
    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows(values_only=True):
                if len(rows) >= TIER2_MAX_XLSX_ROWS:
                    break
                if any(cell is not None for cell in row):
                    rows.append(list(row))
            if len(rows) >= TIER2_MAX_XLSX_ROWS:
                break
    finally:
        wb.close()
    return rows


# ---------------------------------------------------------------------------
# 1. IS Gasvaktin (MIT open JSON)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 2. CH BFS / LIK (PxWeb JSON-stat2 or CSV)
# ---------------------------------------------------------------------------


def _json_stat2_index_map(cat_dict: dict[object, object]) -> dict[str, int]:
    raw_index = cat_dict.get("index")
    result: dict[str, int] = {}
    if isinstance(raw_index, dict):
        for k, v in cast(dict[object, object], raw_index).items():
            if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool):
                result[k] = v
    elif isinstance(raw_index, list):
        for idx, item in enumerate(cast(list[object], raw_index)):
            if isinstance(item, str):
                result[item] = idx
    return result


def _json_stat2_label_map(cat_dict: dict[object, object]) -> dict[str, str]:
    raw_label = cat_dict.get("label")
    result: dict[str, str] = {}
    if isinstance(raw_label, dict):
        for k, v in cast(dict[object, object], raw_label).items():
            if isinstance(k, str) and isinstance(v, str):
                result[k] = v
    return result


def _parse_ch_month_key(raw_key: str) -> str | None:
    cleaned = raw_key.strip()
    m = _PXWEB_MONTH_RE.match(cleaned)
    if m is not None:
        year_s, month_s = m.groups()
        try:
            return date(int(year_s), int(month_s), 1).isoformat()
        except ValueError:
            return None
    return _extract_portal_date(cleaned)


def _match_ch_grade(label: str) -> FuelGrade | None:
    folded = _fold_ascii(label)
    if "diesel" in folded:
        return "diesel"
    if "bleifrei" in folded or "benzin" in folded or "essence" in folded or "gasoline" in folded:
        if "98" in folded:
            return "petrol_98"
        if "95" in folded:
            return "petrol_95"
    return None


def _parse_ch_json_stat2(obj: dict[object, object]) -> tuple[dict[FuelGrade, float], str]:
    raw_ids = obj.get("id")
    raw_sizes = obj.get("size")
    raw_dims = obj.get("dimension")
    raw_values = obj.get("value")
    if (
        not isinstance(raw_ids, list)
        or not isinstance(raw_sizes, list)
        or not isinstance(raw_dims, dict)
    ):
        raise Tier2SelectorDriftError("CH BFS JSON-stat2 missing id/size/dimension fields")

    dim_ids = [str(item) for item in cast(list[object], raw_ids)]
    sizes = [int(str(item)) for item in cast(list[object], raw_sizes)]
    if len(dim_ids) != len(sizes) or not dim_ids:
        raise Tier2SelectorDriftError("CH BFS JSON-stat2 id/size mismatch")

    dims = cast(dict[object, object], raw_dims)
    strides: list[int] = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    def _get_val(flat_idx: int) -> float | None:
        if isinstance(raw_values, list):
            vals = cast(list[object], raw_values)
            if 0 <= flat_idx < len(vals):
                return parse_positive_float(vals[flat_idx])
            return None
        if isinstance(raw_values, dict):
            return parse_positive_float(cast(dict[object, object], raw_values).get(str(flat_idx)))
        return None

    time_dim_pos: int | None = None
    time_entries: list[tuple[str, int]] = []
    product_dim_pos: int | None = None
    product_positions: dict[FuelGrade, int] = {}

    for dim_pos, dim_name in enumerate(dim_ids):
        dim_obj = dims.get(dim_name)
        if not isinstance(dim_obj, dict):
            continue
        cat_obj = cast(dict[object, object], dim_obj).get("category")
        if not isinstance(cat_obj, dict):
            continue
        cat = cast(dict[object, object], cat_obj)
        index_map = _json_stat2_index_map(cat)
        label_map = _json_stat2_label_map(cat)

        matched_times: list[tuple[str, int]] = []
        for key, pos in index_map.items():
            iso_month = _parse_ch_month_key(key)
            if iso_month is not None:
                matched_times.append((iso_month, pos))
        if matched_times:
            time_dim_pos = dim_pos
            time_entries = sorted(matched_times, key=lambda item: item[0], reverse=True)
            continue

        matched_grades: dict[FuelGrade, int] = {}
        for key, pos in index_map.items():
            grade = _match_ch_grade(label_map.get(key, key))
            if grade is not None and grade not in matched_grades:
                matched_grades[grade] = pos
        if matched_grades:
            product_dim_pos = dim_pos
            product_positions = matched_grades

    if time_dim_pos is None or product_dim_pos is None or not product_positions:
        raise Tier2SelectorDriftError("CH BFS JSON-stat2 missing recognizable time/fuel dimensions")

    for iso_month, t_pos in time_entries:
        prices: dict[FuelGrade, float] = {}
        for grade, p_pos in product_positions.items():
            flat_idx = t_pos * strides[time_dim_pos] + p_pos * strides[product_dim_pos]
            val = _get_val(flat_idx)
            if val is not None:
                prices[grade] = val
        if "diesel" in prices or "petrol_95" in prices:
            return prices, iso_month

    raise Tier2SelectorDriftError("CH BFS JSON-stat2 contained no populated monthly fuel prices")


def _parse_ch_csv(text: str) -> tuple[dict[FuelGrade, float], str]:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise Tier2SelectorDriftError("CH BFS CSV missing header row")

    date_col: str | None = None
    grade_cols: dict[FuelGrade, str] = {}
    for col in reader.fieldnames:
        if not col:
            continue
        folded = _fold_ascii(col)
        if date_col is None and any(tok in folded for tok in ("monat", "date", "datum", "mois")):
            date_col = col
            continue
        grade = _match_ch_grade(col)
        if grade is not None and grade not in grade_cols:
            grade_cols[grade] = col

    if date_col is None or not grade_cols:
        raise Tier2SelectorDriftError("CH BFS CSV missing recognizable Monat/Fuel columns")

    best_date = ""
    best_prices: dict[FuelGrade, float] = {}
    for row in reader:
        iso_month = _parse_ch_month_key(str(row.get(date_col, "")))
        if iso_month is None:
            continue
        row_prices: dict[FuelGrade, float] = {}
        for grade, col in grade_cols.items():
            val = parse_positive_float(row.get(col))
            if val is not None:
                row_prices[grade] = val
        if ("diesel" in row_prices or "petrol_95" in row_prices) and iso_month >= best_date:
            best_date = iso_month
            best_prices = row_prices

    if not best_date or not best_prices:
        raise Tier2SelectorDriftError("CH BFS CSV contained no valid dated fuel price rows")
    return best_prices, best_date


def fetch_ch_bfs_lik(
    client: httpx.Client,
    *,
    url: str = CH_BFS_LIK_URL,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Switzerland BFS/LIK monthly fuel prices (PxWeb JSON-stat2 or CSV) in CHF/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            url,
            allowed_hosts=CH_BFS_LIK_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        text = decode_with_fallbacks(raw, encodings=("utf-8-sig",))
        stripped = text.lstrip()
        if stripped.startswith("{"):
            payload: object = json.loads(text)
            if not isinstance(payload, dict):
                raise Tier2SelectorDriftError("CH BFS JSON root is not an object")
            prices, data_date = _parse_ch_json_stat2(cast(dict[object, object], payload))
        else:
            prices, data_date = _parse_ch_csv(text)

        quote = RawCountryFuelQuote(
            iso2="CH",
            currency="CHF",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="ch_bfs_lik",
            license="Swiss Open Data (BFS/LIK)",
            data_date=data_date,
        )
        return [quote], data_date

    return _run_tier2_guarded("ch_bfs_lik", _run)


# ---------------------------------------------------------------------------
# 3. MD ANRE
# ---------------------------------------------------------------------------


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

        data_date = _extract_portal_date("\n".join(blocks)) or datetime.now(UTC).date().isoformat()
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


# ---------------------------------------------------------------------------
# 4. MK ERC
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 5. RU Rosstat (UTF-8 / windows-1251 HTML or .xlsx)
# ---------------------------------------------------------------------------


def _match_ru_grade(label: str) -> FuelGrade | None:
    lower = " ".join(label.strip().lower().split())
    if "дизель" in lower or "diesel" in lower:
        return "diesel"
    if "\u0430\u0438-95" in lower or "\u0430\u0438 95" in lower or "ai-95" in lower:
        return "petrol_95"
    if "\u0430\u0438-98" in lower or "\u0430\u0438 98" in lower or "ai-98" in lower:
        return "petrol_98"
    if "\u0430\u0438-92" in lower or "\u0430\u0438 92" in lower or "ai-92" in lower:
        return "petrol_92"
    return None


def _extract_ru_prices_from_rows(rows: list[list[str]]) -> dict[FuelGrade, float]:
    prices: dict[FuelGrade, float] = {}
    for row in rows:
        if len(row) < 2:
            continue
        grade = _match_ru_grade(row[0])
        if grade is None or grade in prices:
            continue
        for cell in row[1:]:
            val = _extract_first_price(cell)
            if val is not None:
                prices[grade] = val
                break
    return prices


def fetch_ru_rosstat(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Russia Rosstat weekly consumer fuel prices (UTF-8/windows-1251 HTML or .xlsx)."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            RU_ROSSTAT_URL,
            allowed_hosts=RU_ROSSTAT_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        html = decode_with_fallbacks(raw, encodings=("utf-8-sig", "windows-1251"))
        tables = extract_html_tables(html)
        blocks = extract_html_text(html)

        prices: dict[FuelGrade, float] = {}
        for table in tables:
            found = _extract_ru_prices_from_rows(table)
            for grade, val in found.items():
                prices.setdefault(grade, val)

        data_date = _extract_portal_date("\n".join(blocks))

        if "diesel" not in prices and "petrol_95" not in prices:
            xlsx_links = _discover_xlsx_links(html, RU_ROSSTAT_URL, RU_ROSSTAT_ALLOWED_HOSTS)
            if xlsx_links:
                xlsx_url = xlsx_links[0][0]
                xlsx_raw = fetch_bytes_with_retry(
                    client,
                    xlsx_url,
                    allowed_hosts=RU_ROSSTAT_ALLOWED_HOSTS,
                    max_bytes=TIER2_MAX_XLSX_BYTES,
                    sleep_fn=sleep_fn,
                )
                xlsx_rows = _iter_xlsx_rows(xlsx_raw)
                str_rows = [[str(c) if c is not None else "" for c in row] for row in xlsx_rows]
                prices = _extract_ru_prices_from_rows(str_rows)
                if data_date is None:
                    for row in xlsx_rows[:10]:
                        for cell in row:
                            candidate_date = (
                                extract_iso_date(cell)
                                if not isinstance(cell, str)
                                else _extract_portal_date(cell)
                            )
                            if candidate_date is not None:
                                data_date = candidate_date
                                break
                        if data_date is not None:
                            break

        if "diesel" not in prices and "petrol_95" not in prices:
            raise Tier2SelectorDriftError(
                "Rosstat HTML/XLSX missing expected diesel / AI-95 price rows"
            )

        resolved_date = data_date or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="RU",
            currency="RUB",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="ru_rosstat",
            license="Rosstat public bulletin",
            data_date=resolved_date,
        )
        return [quote], resolved_date

    return _run_tier2_guarded("ru_rosstat", _run)


# ---------------------------------------------------------------------------
# 6. IL Ministry of Energy (regulated 95-octane self-service ceiling)
# ---------------------------------------------------------------------------


def fetch_il_moe(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Israel Ministry of Energy regulated 95-octane self-service ceiling in ILS/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            IL_MOE_URL,
            allowed_hosts=IL_MOE_ALLOWED_HOSTS,
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
                label_ascii = _fold_ascii(row[0])
                label_raw = row[0]
                price_val: float | None = None
                for cell in row[1:]:
                    parsed = _extract_first_price(cell)
                    if parsed is not None:
                        price_val = parsed
                        break
                if price_val is None:
                    continue

                is_95 = (
                    "95" in label_ascii
                    and any(
                        tok in label_ascii
                        for tok in ("octane", "unleaded", "petrol", "gasoline", "self")
                    )
                ) or ("95" in label_raw and "בנזין" in label_raw)
                if is_95 and "petrol_95" not in prices:
                    prices["petrol_95"] = price_val
                elif "diesel" in label_ascii and "diesel" not in prices:
                    prices["diesel"] = price_val

        if "petrol_95" not in prices:
            for block in blocks:
                folded = _fold_ascii(block)
                if "95" in folded and any(
                    tok in folded for tok in ("octane", "unleaded", "self-service", "nis", "ils")
                ):
                    after = re.sub(r".*?95\b", "", folded, count=1)
                    val = _extract_first_price(after)
                    if val is not None:
                        prices["petrol_95"] = val
                        break

        if "petrol_95" not in prices and "diesel" not in prices:
            raise Tier2SelectorDriftError(
                "Israel MoE HTML missing regulated 95-octane self-service ceiling price"
            )

        data_date = _extract_portal_date("\n".join(blocks)) or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="IL",
            currency="ILS",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="il_moe",
            license="Israel Ministry of Energy public tariff",
            data_date=data_date,
        )
        return [quote], data_date

    return _run_tier2_guarded("il_moe", _run)


# ---------------------------------------------------------------------------
# 7. AE MOEI
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 8. ZA DMRE / CEF (Inland Gauteng cents/L -> ZAR/L HTML or .xlsx)
# ---------------------------------------------------------------------------


def _normalize_za_cents_to_zar(raw_val: float) -> float:
    return raw_val / 100.0 if raw_val > 100.0 else raw_val


def _extract_za_prices_from_matrix(rows: list[list[str]]) -> dict[FuelGrade, float]:
    inland_col_idx: int | None = None
    prices: dict[FuelGrade, float] = {}
    has_50ppm_diesel = False

    for row in rows:
        if len(row) < 2:
            continue
        folded_cells = [_fold_ascii(cell) for cell in row]
        # Detect Inland / Gauteng header column
        if inland_col_idx is None:
            for col_i, cell_f in enumerate(folded_cells[1:], start=1):
                if "inland" in cell_f or "gauteng" in cell_f:
                    inland_col_idx = col_i
                    break

        label = folded_cells[0]
        target_val: float | None = None
        if inland_col_idx is not None and inland_col_idx < len(row):
            target_val = _extract_first_price(row[inland_col_idx])
        if target_val is None:
            for cell in row[1:]:
                parsed = _extract_first_price(cell)
                if parsed is not None:
                    target_val = parsed
                    break
        if target_val is None:
            continue

        zar_val = _normalize_za_cents_to_zar(target_val)
        if ("petrol" in label or "ulp" in label) and "95" in label and "petrol_95" not in prices:
            prices["petrol_95"] = zar_val
        elif ("petrol" in label or "ulp" in label) and "93" in label and "petrol_92" not in prices:
            prices["petrol_92"] = zar_val
        elif "diesel" in label:
            is_50ppm = "0.005" in label or "50ppm" in label or "50 ppm" in label
            if is_50ppm:
                prices["diesel"] = zar_val
                has_50ppm_diesel = True
            elif not has_50ppm_diesel and "diesel" not in prices:
                prices["diesel"] = zar_val

    return prices


def fetch_za_dmre_cef(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch South Africa DMRE/CEF monthly Inland Gauteng fuel prices (cents/L -> ZAR/L)."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            ZA_DMRE_CEF_URL,
            allowed_hosts=ZA_DMRE_CEF_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        html = decode_with_fallbacks(raw, encodings=("utf-8-sig",))
        tables = extract_html_tables(html)
        blocks = extract_html_text(html)

        prices: dict[FuelGrade, float] = {}
        for table in tables:
            found = _extract_za_prices_from_matrix(table)
            for grade, val in found.items():
                prices.setdefault(grade, val)

        data_date = _extract_portal_date("\n".join(blocks))

        if "diesel" not in prices and "petrol_95" not in prices:
            xlsx_links = _discover_xlsx_links(html, ZA_DMRE_CEF_URL, ZA_DMRE_CEF_ALLOWED_HOSTS)
            if xlsx_links:
                xlsx_raw = fetch_bytes_with_retry(
                    client,
                    xlsx_links[0][0],
                    allowed_hosts=ZA_DMRE_CEF_ALLOWED_HOSTS,
                    max_bytes=TIER2_MAX_XLSX_BYTES,
                    sleep_fn=sleep_fn,
                )
                xlsx_rows = _iter_xlsx_rows(xlsx_raw)
                str_rows = [[str(c) if c is not None else "" for c in row] for row in xlsx_rows]
                prices = _extract_za_prices_from_matrix(str_rows)
                if data_date is None:
                    for row in xlsx_rows[:10]:
                        for cell in row:
                            candidate_date = (
                                extract_iso_date(cell)
                                if not isinstance(cell, str)
                                else _extract_portal_date(cell)
                            )
                            if candidate_date is not None:
                                data_date = candidate_date
                                break
                        if data_date is not None:
                            break

        if "diesel" not in prices and "petrol_95" not in prices:
            raise Tier2SelectorDriftError(
                "South Africa DMRE/CEF HTML/XLSX missing Petrol 95 ULP / Diesel 0.005% rows"
            )

        resolved_date = data_date or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="ZA",
            currency="ZAR",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="za_dmre_cef",
            license="South Africa DMRE/CEF public tariff",
            data_date=resolved_date,
        )
        return [quote], resolved_date

    return _run_tier2_guarded("za_dmre_cef", _run)


# ---------------------------------------------------------------------------
# 9. SA Saudi Aramco
# ---------------------------------------------------------------------------


def fetch_sa_aramco(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Saudi Aramco monthly retail fuel price schedule HTML table in SAR/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            SA_ARAMCO_URL,
            allowed_hosts=SA_ARAMCO_ALLOWED_HOSTS,
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
                elif (
                    ("gasoline" in label or "octane" in label)
                    and "95" in label
                    and ("petrol_95" not in prices)
                ):
                    prices["petrol_95"] = price_val
                elif (
                    ("gasoline" in label or "octane" in label)
                    and "98" in label
                    and ("petrol_98" not in prices)
                ):
                    prices["petrol_98"] = price_val
                elif (
                    ("gasoline" in label or "octane" in label)
                    and "91" in label
                    and ("petrol_92" not in prices)
                ):
                    prices["petrol_92"] = price_val

        if "diesel" not in prices and "petrol_95" not in prices:
            raise Tier2SelectorDriftError(
                "Saudi Aramco HTML table missing expected Diesel / Gasoline 95 rows"
            )

        data_date = _extract_portal_date("\n".join(blocks)) or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="SA",
            currency="SAR",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="sa_aramco",
            license="Saudi Aramco public retail schedule",
            data_date=data_date,
        )
        return [quote], data_date

    return _run_tier2_guarded("sa_aramco", _run)


# ---------------------------------------------------------------------------
# 10. NG Nigeria NBS (AGO Diesel & PMS Petrol Watch .xlsx)
# ---------------------------------------------------------------------------


def _parse_ng_nbs_national_average(
    xlsx_rows: list[list[object]],
) -> tuple[float | None, str | None]:
    found_date: str | None = None
    for row in xlsx_rows[:10]:
        for cell in row:
            candidate = (
                extract_iso_date(cell) if not isinstance(cell, str) else _extract_portal_date(cell)
            )
            if candidate is not None:
                found_date = candidate
                break
        if found_date is not None:
            break

    for row in xlsx_rows:
        if len(row) < 2:
            continue
        label = _fold_ascii(str(row[0] or ""))
        if "national" in label or label in {"nigeria", "average", "all states"}:
            # Prefer rightmost numeric column (latest month in NBS Watch spreadsheets)
            latest_val: float | None = None
            for cell in row[1:]:
                parsed = (
                    parse_positive_float(cell)
                    if not isinstance(cell, str)
                    else _extract_first_price(cell)
                )
                if parsed is not None:
                    latest_val = parsed
            if latest_val is not None:
                return latest_val, found_date
    return None, found_date


def fetch_ng_nbs(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Nigeria NBS monthly AGO Diesel & PMS Petrol Watch .xlsx national averages in NGN/L."""

    def _run() -> tuple[list[RawCountryFuelQuote], str | None]:
        raw = fetch_bytes_with_retry(
            client,
            NG_NBS_URL,
            allowed_hosts=NG_NBS_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        html = decode_with_fallbacks(raw, encodings=("utf-8-sig",))
        xlsx_links = _discover_xlsx_links(html, NG_NBS_URL, NG_NBS_ALLOWED_HOSTS)
        if not xlsx_links:
            raise Tier2SelectorDriftError("Nigeria NBS page missing AGO/PMS Watch .xlsx links")

        ago_url: str | None = None
        pms_url: str | None = None
        for link_url, link_text in xlsx_links:
            haystack = _fold_ascii(f"{link_url} {link_text}")
            if ago_url is None and ("ago" in haystack or "diesel" in haystack):
                ago_url = link_url
            if pms_url is None and ("pms" in haystack or "petrol" in haystack):
                pms_url = link_url

        if ago_url is None and pms_url is None:
            raise Tier2SelectorDriftError(
                "Nigeria NBS .xlsx links did not match AGO Diesel or PMS Petrol Watch"
            )

        prices: dict[FuelGrade, float] = {}
        best_date: str | None = None

        targets: tuple[tuple[FuelGrade, str | None], ...] = (
            ("diesel", ago_url),
            ("petrol_95", pms_url),
        )
        for grade, target_url in targets:
            if target_url is None:
                continue
            xlsx_raw = fetch_bytes_with_retry(
                client,
                target_url,
                allowed_hosts=NG_NBS_ALLOWED_HOSTS,
                max_bytes=TIER2_MAX_XLSX_BYTES,
                sleep_fn=sleep_fn,
            )
            xlsx_rows = _iter_xlsx_rows(xlsx_raw)
            val, sheet_date = _parse_ng_nbs_national_average(xlsx_rows)
            if val is not None:
                prices[grade] = val
            if sheet_date is not None and (best_date is None or sheet_date > best_date):
                best_date = sheet_date

        if "diesel" not in prices and "petrol_95" not in prices:
            raise Tier2SelectorDriftError(
                "Nigeria NBS .xlsx workbooks missing National Average AGO/PMS values"
            )

        resolved_date = best_date or datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="NG",
            currency="NGN",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="ng_nbs",
            license="Nigeria NBS open statistics",
            data_date=resolved_date,
        )
        return [quote], resolved_date

    return _run_tier2_guarded("ng_nbs", _run)


def fetch_all_tier2_portals(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> list[RawFuelFeedResult]:
    """Run all 10 research-gated Tier 2 national portal scrapers in strict per-country isolation."""
    return [
        fetch_is_gasvaktin(client, sleep_fn=sleep_fn),
        fetch_ch_bfs_lik(client, sleep_fn=sleep_fn),
        fetch_md_anre(client, sleep_fn=sleep_fn),
        fetch_mk_erc(client, sleep_fn=sleep_fn),
        fetch_ru_rosstat(client, sleep_fn=sleep_fn),
        fetch_il_moe(client, sleep_fn=sleep_fn),
        fetch_ae_moei(client, sleep_fn=sleep_fn),
        fetch_za_dmre_cef(client, sleep_fn=sleep_fn),
        fetch_sa_aramco(client, sleep_fn=sleep_fn),
        fetch_ng_nbs(client, sleep_fn=sleep_fn),
    ]
