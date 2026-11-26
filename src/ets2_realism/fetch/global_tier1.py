"""Non-EU Tier 1 open government fuel price collectors (GLB-01: US, BR, AR, CO, CL, MY, JP, KR)."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final, cast
from urllib.parse import urljoin, urlsplit

import httpx
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from ets2_realism.fetch._html import extract_html_tables, extract_html_text
from ets2_realism.fetch._parsing import (
    AnchorExtractor,
    extract_iso_date,
    parse_positive_float,
    validate_ooxml_zip_safety,
)
from ets2_realism.fetch.http import (
    DEFAULT_MAX_RESPONSE_BYTES,
    HttpFetchError,
    fetch_bytes_with_retry,
    redact_url_secrets,
    validate_https_url,
)
from ets2_realism.fetch.models import RawCountryFuelQuote, RawFuelFeedResult
from ets2_realism.normalize.models import FuelGrade

NIST_LITERS_PER_US_GALLON: Final[Decimal] = Decimal("3.785411784")

# --- US EIA v2 ---
US_EIA_V2_URL: Final[str] = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
US_EIA_V2_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"api.eia.gov"})
_US_EIA_PRODUCT_MAP: Final[dict[str, FuelGrade]] = {
    "EPD2D": "diesel",
    "EPMR": "petrol_95",
    "EPMP": "petrol_98",
}

# --- BR ANP ---
BR_ANP_DIESEL_GNV_URL: Final[str] = (
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/"
    "shpc/qus/ultimas-4-semanas-diesel-gnv.csv"
)
BR_ANP_GASOLINA_ETANOL_URL: Final[str] = (
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/"
    "shpc/qus/ultimas-4-semanas-gasolina-etanol.csv"
)
BR_ANP_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.gov.br"})

# --- AR Energia ---
AR_ENERGIA_CKAN_PRIMARY_URL: Final[str] = (
    "https://datos.gob.ar/api/3/action/package_show?id=precios-en-surtidor-resolucion-314"
)
AR_ENERGIA_CKAN_FALLBACK_URL: Final[str] = (
    "https://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor-resolucion-314"
)
AR_ENERGIA_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"datos.gob.ar", "datos.energia.gob.ar"}
)

# --- CO SICOM / CREG ---
CO_SICOM_CATALOG_URL: Final[str] = (
    "https://www.datos.gov.co/api/catalog/v1?q=precio+mes+combustible&limit=10"
)
CO_CREG_FALLBACK_URL: Final[str] = (
    "https://creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos"
)
CO_SICOM_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.datos.gov.co"})
CO_CREG_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"creg.gov.co"})
_CO_SOCRATA_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$")
_CO_DOT_THOUSANDS_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}(?:\.\d{3})+(?:,\d+)?$")
_CO_VOLUME_DATASET_ID: Final[str] = "fbht-2fzd"

# --- CL CNE ---
CL_CNE_V4_URL: Final[str] = "https://api.cne.cl/api/v4/estaciones"
CL_CNE_V3_URL: Final[str] = "https://api.cne.cl/v3/combustibles/vehicular/estaciones"
CL_CNE_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"api.cne.cl"})

# --- MY OpenDOSM ---
MY_OPENDOSM_URL: Final[str] = "https://api.data.gov.my/data-catalogue"
MY_OPENDOSM_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"api.data.gov.my"})

# --- JP METI ---
JP_METI_LANDING_URL: Final[str] = (
    "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results.html"
)
JP_METI_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.enecho.meti.go.jp"})
JP_METI_MAX_XLSX_BYTES: Final[int] = 20_971_520  # 20 MiB
JP_METI_MAX_ROWS: Final[int] = 5000
_JP_KANJI_DATE_RE: Final[re.Pattern[str]] = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
_JP_REIWA_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"令和\s*(元|\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)
_JP_SLASH_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b")

# --- KR Opinet ---
KR_OPINET_URL: Final[str] = "https://www.opinet.co.kr/api/avgAllPrice.do"
KR_OPINET_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.opinet.co.kr"})
_KR_OPINET_PRODUCT_MAP: Final[dict[str, FuelGrade]] = {
    "D047": "diesel",
    "B027": "petrol_95",
    "B034": "petrol_98",
    "K015": "lpg",
}


def gallon_to_liter(price_per_gallon: float) -> float:
    """Convert a per-US-gallon price (USD/gal or COP/gal) to per-liter via exact NIST factor."""
    if not math.isfinite(price_per_gallon) or price_per_gallon <= 0.0:
        raise ValueError(f"price_per_gallon must be finite and positive, got {price_per_gallon!r}")
    return float(Decimal(str(price_per_gallon)) / NIST_LITERS_PER_US_GALLON)


def _scrub_secret(message: str, secret: str) -> str:
    cleaned = redact_url_secrets(message)
    if secret:
        cleaned = cleaned.replace(secret, "***")
    return cleaned


def _fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_ish = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_ish.strip().lower().split())


def _decode_csv_bytes(raw: bytes) -> str:
    if b"\x00" in raw:
        raise ValueError("CSV payload contains NUL bytes (binary/corrupt content)")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _parse_yyyymmdd_date(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        candidate = f"{cleaned[0:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return None
    return extract_iso_date(cleaned)


def _parse_jp_date(value: object) -> str | None:
    iso = extract_iso_date(value)
    if iso is not None:
        return iso
    if not isinstance(value, str):
        return None
    kanji = _JP_KANJI_DATE_RE.search(value)
    if kanji is not None:
        year_s, month_s, day_s = kanji.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s)).isoformat()
        except ValueError:
            return None
    reiwa = _JP_REIWA_DATE_RE.search(value)
    if reiwa is not None:
        era_s, month_s, day_s = reiwa.groups()
        era_year = 1 if era_s == "元" else int(era_s)
        if era_year >= 1:
            try:
                return date(2018 + era_year, int(month_s), int(day_s)).isoformat()
            except ValueError:
                return None
    slash = _JP_SLASH_DATE_RE.search(value)
    if slash is not None:
        year_s, month_s, day_s = slash.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s)).isoformat()
        except ValueError:
            return None
    return None


def _parse_colombian_cop_per_gallon(value: object) -> float | None:
    """Parse COP/gallon values, normalizing Colombian dot-thousands ('15.588' -> 15588.0)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) and num > 1000.0 else None
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace("\u00a0", "").replace(" ", "")
    cleaned = cleaned.replace("$", "").replace("COP", "").replace("cop", "")
    if not cleaned:
        return None
    if _CO_DOT_THOUSANDS_RE.match(cleaned):
        normalized = cleaned.replace(".", "").replace(",", ".")
        try:
            num = float(normalized)
        except ValueError:
            return None
        return num if math.isfinite(num) and num > 1000.0 else None
    num = parse_positive_float(cleaned)
    if num is None or num <= 1000.0:
        return None
    return num


def fetch_us_eia_v2(
    client: httpx.Client,
    *,
    api_key: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch U.S. EIA Open Data API v2 weekly national retail prices (optional EIA_API_KEY)."""
    resolved_key = (api_key if api_key is not None else os.environ.get("EIA_API_KEY", "")).strip()
    if not resolved_key:
        return RawFuelFeedResult(
            feed_name="us_eia_v2",
            tier="tier1",
            region_scope="global",
            ok=True,
            skipped=True,
            skip_reason="skipped (EIA_API_KEY unset; retaining lockfile/Tier 3)",
            quotes=[],
        )

    try:
        raw = fetch_bytes_with_retry(
            client,
            US_EIA_V2_URL,
            allowed_hosts=US_EIA_V2_ALLOWED_HOSTS,
            params=[
                ("api_key", resolved_key),
                ("frequency", "weekly"),
                ("data[0]", "value"),
                ("facets[duoarea][]", "NUS"),
                ("facets[process][]", "PTE"),
                ("facets[product][]", "EPD2D"),
                ("facets[product][]", "EPMR"),
                ("facets[product][]", "EPMP"),
                ("sort[0][column]", "period"),
                ("sort[0][direction]", "desc"),
                ("length", "20"),
            ],
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("US EIA v2 payload is not a JSON object")
        root = cast(dict[object, object], payload)
        resp_obj = root.get("response")
        if not isinstance(resp_obj, dict):
            raise ValueError("US EIA v2 payload missing 'response' object")
        data_rows = cast(dict[object, object], resp_obj).get("data")
        if not isinstance(data_rows, list) or not data_rows:
            raise ValueError("US EIA v2 payload missing non-empty 'response.data' list")

        by_period: dict[str, dict[FuelGrade, float]] = {}
        for item in cast(list[object], data_rows):
            if not isinstance(item, dict):
                continue
            row = cast(dict[object, object], item)
            if str(row.get("duoarea", "")).strip().upper() != "NUS":
                continue
            process_val = row.get("process")
            if process_val is not None and str(process_val).strip().upper() != "PTE":
                continue
            product_code = str(row.get("product", "")).strip().upper()
            grade = _US_EIA_PRODUCT_MAP.get(product_code)
            if grade is None:
                continue
            row_date = extract_iso_date(row.get("period"))
            if row_date is None:
                continue
            usd_per_gal = parse_positive_float(row.get("value"))
            if usd_per_gal is None:
                continue
            by_period.setdefault(row_date, {})[grade] = gallon_to_liter(usd_per_gal)

        complete_periods = [
            period
            for period, grades in by_period.items()
            if "diesel" in grades and "petrol_95" in grades
        ]
        if not complete_periods:
            raise ValueError("US EIA v2 yielded no period containing both EPD2D and EPMR prices")

        latest_date = max(complete_periods)
        quote = RawCountryFuelQuote(
            iso2="US",
            currency="USD",
            prices_by_grade=by_period[latest_date],
            unit_basis="local_per_liter",
            source="us_eia_v2",
            license="U.S. Public Domain (EIA)",
            data_date=latest_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="us_eia_v2",
            tier="tier1",
            region_scope="global",
            ok=False,
            skipped=False,
            quotes=[],
            error=_scrub_secret(str(exc), resolved_key),
        )

    return RawFuelFeedResult(
        feed_name="us_eia_v2",
        tier="tier1",
        region_scope="global",
        ok=True,
        skipped=False,
        quotes=[quote],
        data_date=latest_date,
    )


def fetch_br_anp(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Brazil ANP rolling 4-week retail CSVs and compute outlier-resilient medians."""
    try:
        parsed_rows: list[tuple[str, str, float]] = []
        for url in (BR_ANP_DIESEL_GNV_URL, BR_ANP_GASOLINA_ETANOL_URL):
            raw = fetch_bytes_with_retry(
                client,
                url,
                allowed_hosts=BR_ANP_ALLOWED_HOSTS,
                max_bytes=DEFAULT_MAX_RESPONSE_BYTES,
                sleep_fn=sleep_fn,
            )
            text = _decode_csv_bytes(raw)
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            if not reader.fieldnames:
                raise ValueError(f"BR ANP CSV missing header row: {url}")

            header_map = {_fold_text(name): name for name in reader.fieldnames if name}
            prod_col = header_map.get("produto")
            price_col = header_map.get("valor de venda")
            date_col = header_map.get("data da coleta")
            if not (prod_col and price_col and date_col):
                raise ValueError(
                    f"BR ANP CSV missing required columns; got {list(reader.fieldnames)}"
                )

            for row in reader:
                row_date = extract_iso_date(row.get(date_col, ""))
                if row_date is None:
                    continue
                prod_norm = _fold_text(str(row.get(prod_col, ""))).upper()
                if prod_norm in {"GLP", "GNV"}:
                    continue
                price = parse_positive_float(row.get(price_col, ""))
                if price is None:
                    continue
                parsed_rows.append((row_date, prod_norm, price))

        if not parsed_rows:
            raise ValueError("BR ANP CSVs yielded zero valid automotive fuel rows")

        max_date_str = max(item[0] for item in parsed_rows)
        max_date_obj = date.fromisoformat(max_date_str)

        diesel_s10: list[float] = []
        diesel_regular: list[float] = []
        petrol_95: list[float] = []
        petrol_98: list[float] = []
        e85: list[float] = []

        for row_date_str, prod_norm, price in parsed_rows:
            delta_days = (max_date_obj - date.fromisoformat(row_date_str)).days
            if delta_days < 0 or delta_days > 7:
                continue
            if prod_norm == "DIESEL S10":
                diesel_s10.append(price)
            elif prod_norm == "DIESEL":
                diesel_regular.append(price)
            elif prod_norm == "GASOLINA COMUM":
                petrol_95.append(price)
            elif prod_norm == "GASOLINA ADITIVADA":
                petrol_98.append(price)
            elif prod_norm == "ETANOL":
                e85.append(price)

        prices: dict[FuelGrade, float] = {}
        if diesel_s10:
            prices["diesel"] = statistics.median(diesel_s10)
        elif diesel_regular:
            prices["diesel"] = statistics.median(diesel_regular)
        if petrol_95:
            prices["petrol_95"] = statistics.median(petrol_95)
        if petrol_98:
            prices["petrol_98"] = statistics.median(petrol_98)
        if e85:
            prices["e85"] = statistics.median(e85)

        if "diesel" not in prices or "petrol_95" not in prices:
            raise ValueError("BR ANP yielded no valid recent diesel or petrol_95 prices")

        quote = RawCountryFuelQuote(
            iso2="BR",
            currency="BRL",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="br_anp",
            license="Brazilian Open Gov Data (ANP)",
            data_date=max_date_str,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        OSError,
        csv.Error,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="br_anp",
            tier="tier1",
            region_scope="global",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="br_anp",
        tier="tier1",
        region_scope="global",
        ok=True,
        quotes=[quote],
        data_date=max_date_str,
    )


def _discover_ar_energia_csv_url(ckan_payload: object) -> str:
    if not isinstance(ckan_payload, dict):
        raise ValueError("AR Energia CKAN payload is not a JSON object")
    root = cast(dict[object, object], ckan_payload)
    result = root.get("result")
    if not isinstance(result, dict):
        raise ValueError("AR Energia CKAN payload missing 'result' object")
    resources = cast(dict[object, object], result).get("resources")
    if not isinstance(resources, list):
        raise ValueError("AR Energia CKAN payload missing 'result.resources' list")

    for item in cast(list[object], resources):
        if not isinstance(item, dict):
            continue
        res = cast(dict[object, object], item)
        fmt = str(res.get("format", "")).strip().lower()
        name = _fold_text(str(res.get("name", "")))
        url = str(res.get("url", "")).strip()
        url_folded = _fold_text(url)
        if not url:
            continue
        if fmt != "csv" and not url_folded.endswith(".csv"):
            continue
        combined = f"{name} {url_folded}"
        if "historico" in combined:
            continue
        if "vigente" in combined:
            return validate_https_url(url, AR_ENERGIA_ALLOWED_HOSTS)

    raise ValueError("AR Energia CKAN package contained no valid 'vigente' CSV resource")


def _map_ar_energia_grade(product: str) -> FuelGrade | None:
    folded = _fold_text(product)
    if folded == "gnc" or "gnc" in folded.split():
        return None
    if "gas oil grado 2" in folded or "gasoil grado 2" in folded:
        return "diesel"
    if "gas oil grado 3" in folded or "gasoil grado 3" in folded:
        return "diesel_plus"
    if "nafta" in folded and "super" in folded:
        return "petrol_95"
    if "nafta" in folded and "premium" in folded:
        return "petrol_98"
    return None


def fetch_ar_energia(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Argentina Secretaria de Energia Res. 314 vigente CSV via CKAN discovery."""
    try:
        ckan_raw: bytes | None = None
        ckan_errors: list[str] = []
        for ckan_url in (AR_ENERGIA_CKAN_PRIMARY_URL, AR_ENERGIA_CKAN_FALLBACK_URL):
            try:
                ckan_raw = fetch_bytes_with_retry(
                    client,
                    ckan_url,
                    allowed_hosts=AR_ENERGIA_ALLOWED_HOSTS,
                    sleep_fn=sleep_fn,
                )
                break
            except (HttpFetchError, httpx.HTTPError, ValueError) as exc:
                ckan_errors.append(redact_url_secrets(str(exc)))
        if ckan_raw is None:
            raise ValueError(f"AR Energia CKAN discovery failed: {'; '.join(ckan_errors)}")

        ckan_payload: object = json.loads(ckan_raw.decode("utf-8"))
        csv_url = _discover_ar_energia_csv_url(ckan_payload)
        csv_raw = fetch_bytes_with_retry(
            client,
            csv_url,
            allowed_hosts=AR_ENERGIA_ALLOWED_HOSTS,
            max_bytes=DEFAULT_MAX_RESPONSE_BYTES,
            sleep_fn=sleep_fn,
        )
        text = _decode_csv_bytes(csv_raw)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("AR Energia CSV missing header row")

        header_map = {_fold_text(name): name for name in reader.fieldnames if name}
        prod_col = header_map.get("producto")
        price_col = header_map.get("precio")
        date_col = header_map.get("fecha_vigencia") or header_map.get("fecha")
        horario_col = header_map.get("tipohorario")
        if not (prod_col and price_col and date_col):
            raise ValueError(
                f"AR Energia CSV missing required columns; got {list(reader.fieldnames)}"
            )

        rows: list[tuple[str, FuelGrade, float, str]] = []
        for row in reader:
            grade = _map_ar_energia_grade(str(row.get(prod_col, "")))
            if grade is None:
                continue
            price = parse_positive_float(row.get(price_col, ""))
            if price is None:
                continue
            row_date = extract_iso_date(row.get(date_col, ""))
            if row_date is None:
                continue
            horario = _fold_text(str(row.get(horario_col, ""))) if horario_col else ""
            rows.append((row_date, grade, price, horario))

        if not rows:
            raise ValueError("AR Energia CSV yielded zero valid liquid fuel rows")

        max_date_str = max(item[0] for item in rows)
        max_date_obj = date.fromisoformat(max_date_str)

        diurno_samples: dict[FuelGrade, list[float]] = {}
        all_samples: dict[FuelGrade, list[float]] = {}
        for row_date_str, grade, price, horario in rows:
            delta_days = (max_date_obj - date.fromisoformat(row_date_str)).days
            if delta_days < 0 or delta_days > 60:
                continue
            all_samples.setdefault(grade, []).append(price)
            if horario == "diurno":
                diurno_samples.setdefault(grade, []).append(price)

        prices: dict[FuelGrade, float] = {}
        for grade, fallback_vals in all_samples.items():
            chosen = diurno_samples.get(grade) or fallback_vals
            if chosen:
                prices[grade] = statistics.median(chosen)

        if "diesel" not in prices or "petrol_95" not in prices:
            raise ValueError("AR Energia yielded no valid recent diesel or petrol_95 prices")

        quote = RawCountryFuelQuote(
            iso2="AR",
            currency="ARS",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="ar_energia",
            license="Argentine Open Gov Data (Decreto 117/2016)",
            data_date=max_date_str,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        OSError,
        csv.Error,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="ar_energia",
            tier="tier1",
            region_scope="global",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="ar_energia",
        tier="tier1",
        region_scope="global",
        ok=True,
        quotes=[quote],
        data_date=max_date_str,
    )


def discover_co_sicom_resource_url(catalog_payload: object) -> str:
    """Discover the MinMinas/SICOM retail price Socrata resource URL with SSRF allowlist."""
    if not isinstance(catalog_payload, dict):
        raise ValueError("CO SICOM catalog payload is not a JSON object")
    results = cast(dict[object, object], catalog_payload).get("results")
    if not isinstance(results, list):
        raise ValueError("CO SICOM catalog payload missing 'results' list")

    for item in cast(list[object], results):
        if not isinstance(item, dict):
            continue
        entry = cast(dict[object, object], item)
        permalink = entry.get("permalink") or entry.get("link")
        if isinstance(permalink, str) and permalink.strip():
            validate_https_url(permalink.strip(), CO_SICOM_ALLOWED_HOSTS)

        res_obj = entry.get("resource")
        if not isinstance(res_obj, dict):
            continue
        res = cast(dict[object, object], res_obj)
        res_id = str(res.get("id", "")).strip().lower()
        if not _CO_SOCRATA_ID_RE.match(res_id) or res_id == _CO_VOLUME_DATASET_ID:
            continue
        meta_text = _fold_text(f"{res.get('name', '')} {res.get('description', '')}")
        if "precio" not in meta_text and "combustible" not in meta_text:
            continue
        resource_url = f"https://www.datos.gov.co/resource/{res_id}.json?$limit=5000"
        return validate_https_url(resource_url, CO_SICOM_ALLOWED_HOSTS)

    raise ValueError("CO SICOM catalog search yielded no valid retail fuel price resource")


def _map_co_sicom_grade(product: str) -> FuelGrade | None:
    folded = _fold_text(product)
    if not folded:
        return None
    if "acpm" in folded or "biodiesel" in folded or "diesel" in folded:
        return "diesel"
    if "gasolina" in folded and "extra" in folded:
        return "petrol_98"
    if "gasolina" in folded and "corriente" in folded:
        return "petrol_95"
    return None


def _fetch_co_sicom_primary(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> tuple[RawCountryFuelQuote, str]:
    catalog_raw = fetch_bytes_with_retry(
        client,
        CO_SICOM_CATALOG_URL,
        allowed_hosts=CO_SICOM_ALLOWED_HOSTS,
        sleep_fn=sleep_fn,
    )
    catalog_payload: object = json.loads(catalog_raw.decode("utf-8"))
    resource_url = discover_co_sicom_resource_url(catalog_payload)
    soda_raw = fetch_bytes_with_retry(
        client,
        resource_url,
        allowed_hosts=CO_SICOM_ALLOWED_HOSTS,
        max_bytes=DEFAULT_MAX_RESPONSE_BYTES,
        sleep_fn=sleep_fn,
    )
    soda_payload: object = json.loads(soda_raw.decode("utf-8"))
    if not isinstance(soda_payload, list) or not soda_payload:
        raise ValueError("CO SICOM SODA response is not a non-empty JSON array")

    samples: dict[FuelGrade, list[float]] = {}
    dates: list[str] = []
    for item in cast(list[object], soda_payload):
        if not isinstance(item, dict):
            continue
        row = {_fold_text(str(k)): v for k, v in cast(dict[object, object], item).items()}
        prod_raw = (
            row.get("producto")
            or row.get("nombre_producto")
            or row.get("combustible")
            or row.get("tipo_combustible")
            or ""
        )
        grade = _map_co_sicom_grade(str(prod_raw))
        if grade is None:
            continue
        price_raw = (
            row.get("precio")
            or row.get("valor_promedio")
            or row.get("precio_promedio")
            or row.get("valor")
        )
        cop_per_gal = _parse_colombian_cop_per_gallon(price_raw)
        if cop_per_gal is None:
            continue
        samples.setdefault(grade, []).append(gallon_to_liter(cop_per_gal))

        for date_key in ("fecha", "fecha_precio", "periodo"):
            parsed_d = extract_iso_date(row.get(date_key))
            if parsed_d is not None:
                dates.append(parsed_d)
                break

    prices: dict[FuelGrade, float] = {
        grade: statistics.median(vals) for grade, vals in samples.items() if vals
    }
    if "diesel" not in prices or "petrol_95" not in prices:
        raise ValueError("CO SICOM SODA yielded no valid diesel or petrol_95 prices")

    data_date = max(dates) if dates else datetime.now(UTC).date().isoformat()
    quote = RawCountryFuelQuote(
        iso2="CO",
        currency="COP",
        prices_by_grade=prices,
        unit_basis="local_per_liter",
        source="co_sicom",
        license="Colombian Open Gov Data (MinMinas/CREG)",
        data_date=data_date,
    )
    return quote, data_date


def _fetch_co_creg_fallback(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> tuple[RawCountryFuelQuote, str]:
    raw_html = fetch_bytes_with_retry(
        client,
        CO_CREG_FALLBACK_URL,
        allowed_hosts=CO_CREG_ALLOWED_HOSTS,
        sleep_fn=sleep_fn,
    )
    html_text = raw_html.decode("utf-8", errors="replace")
    detected_date = extract_iso_date(" ".join(extract_html_text(html_text)))
    for table in extract_html_tables(html_text):
        gas_col: int | None = None
        acpm_col: int | None = None
        header_idx: int | None = None
        for r_idx, row in enumerate(table):
            cand_gas: int | None = None
            cand_acpm: int | None = None
            for c_idx, cell in enumerate(row):
                folded = _fold_text(cell)
                if "gasolina" in folded and cand_gas is None:
                    cand_gas = c_idx
                if ("acpm" in folded or "diesel" in folded) and cand_acpm is None:
                    cand_acpm = c_idx
            if cand_gas is not None and cand_acpm is not None:
                gas_col = cand_gas
                acpm_col = cand_acpm
                header_idx = r_idx
                break

        if header_idx is None or gas_col is None or acpm_col is None:
            continue

        promedio_prices: dict[FuelGrade, float] | None = None
        city_gas: list[float] = []
        city_acpm: list[float] = []
        for row in table[header_idx + 1 :]:
            if max(gas_col, acpm_col) >= len(row):
                continue
            gas_gal = _parse_colombian_cop_per_gallon(row[gas_col])
            acpm_gal = _parse_colombian_cop_per_gallon(row[acpm_col])
            if gas_gal is None or acpm_gal is None:
                continue
            row_label = _fold_text(row[0]) if row else ""
            if "promedio" in row_label:
                promedio_prices = {
                    "petrol_95": gallon_to_liter(gas_gal),
                    "diesel": gallon_to_liter(acpm_gal),
                }
            else:
                city_gas.append(gallon_to_liter(gas_gal))
                city_acpm.append(gallon_to_liter(acpm_gal))

        prices: dict[FuelGrade, float] | None = promedio_prices
        if prices is None and city_gas and city_acpm:
            prices = {
                "petrol_95": statistics.median(city_gas),
                "diesel": statistics.median(city_acpm),
            }
        if prices is not None:
            data_date = detected_date or datetime.now(UTC).date().isoformat()
            quote = RawCountryFuelQuote(
                iso2="CO",
                currency="COP",
                prices_by_grade=prices,
                unit_basis="local_per_liter",
                source="co_creg",
                license="Colombian Open Gov Data (MinMinas/CREG)",
                data_date=data_date,
            )
            return quote, data_date

    raise ValueError("CO CREG HTML contained no parseable Gasolina/ACPM table")


def fetch_co_sicom(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Colombia MinMinas/SICOM retail fuel prices with CREG HTML fallback (COP/gal -> L)."""
    errors: list[str] = []
    try:
        quote, data_date = _fetch_co_sicom_primary(client, sleep_fn=sleep_fn)
        return RawFuelFeedResult(
            feed_name="co_sicom",
            tier="tier1",
            region_scope="global",
            ok=True,
            quotes=[quote],
            data_date=data_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        errors.append(f"sicom: {redact_url_secrets(str(exc))}")

    try:
        quote, data_date = _fetch_co_creg_fallback(client, sleep_fn=sleep_fn)
        return RawFuelFeedResult(
            feed_name="co_sicom",
            tier="tier1",
            region_scope="global",
            ok=True,
            quotes=[quote],
            data_date=data_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
    ) as exc:
        errors.append(f"creg: {redact_url_secrets(str(exc))}")

    return RawFuelFeedResult(
        feed_name="co_sicom",
        tier="tier1",
        region_scope="global",
        ok=False,
        quotes=[],
        error="; ".join(errors),
    )


def _map_cl_cne_grade(raw_key: str) -> FuelGrade | None:
    folded = _fold_text(raw_key)
    if folded in {"diesel", "petroleo diesel", "di"} or "diesel" in folded:
        return "diesel"
    if folded in {"95", "gasolina 95"} or "95" in folded.split():
        return "petrol_95"
    if folded in {"97", "gasolina 97"} or "97" in folded.split():
        return "petrol_98"
    if folded in {"93", "gasolina 93"} or "93" in folded.split():
        return "petrol_92"
    if folded in {"glp", "glp vehicular"} or "glp" in folded.split():
        return "lpg"
    return None


def _parse_cl_cne_stations(payload: object) -> tuple[dict[FuelGrade, float], str]:
    stations_obj: object
    if isinstance(payload, list):
        stations_obj = cast(list[object], payload)
    elif isinstance(payload, dict):
        root = cast(dict[object, object], payload)
        estado = root.get("estado")
        if isinstance(estado, str) and estado.strip().upper() not in {"OK", "SUCCESS"}:
            raise ValueError(f"CL CNE API returned estado={estado!r}")
        stations_obj = root.get("data")
    else:
        raise ValueError("CL CNE payload is neither a JSON list nor object")

    if not isinstance(stations_obj, list) or not stations_obj:
        raise ValueError("CL CNE payload missing non-empty stations list")

    samples: dict[FuelGrade, list[float]] = {}
    dates: list[str] = []

    for item in cast(list[object], stations_obj):
        if not isinstance(item, dict):
            continue
        station = cast(dict[object, object], item)
        for d_key in ("fecha_hora_actualizacion", "fecha_actualizacion", "fecha"):
            parsed_d = extract_iso_date(station.get(d_key))
            if parsed_d is not None:
                dates.append(parsed_d)
                break

        precios = station.get("precios")
        if isinstance(precios, dict):
            for raw_k, raw_v in cast(dict[object, object], precios).items():
                grade = _map_cl_cne_grade(str(raw_k))
                if grade is None:
                    continue
                val_obj: object = (
                    cast(dict[object, object], raw_v).get("precio")
                    if isinstance(raw_v, dict)
                    else raw_v
                )
                price = parse_positive_float(val_obj)
                if price is not None:
                    samples.setdefault(grade, []).append(price)
        elif isinstance(precios, list):
            for entry in cast(list[object], precios):
                if not isinstance(entry, dict):
                    continue
                rec = cast(dict[object, object], entry)
                label = str(rec.get("tipo") or rec.get("id") or rec.get("nombre") or "")
                grade = _map_cl_cne_grade(label)
                if grade is None:
                    continue
                price = parse_positive_float(rec.get("precio"))
                if price is not None:
                    samples.setdefault(grade, []).append(price)

        combustibles = station.get("combustibles")
        if isinstance(combustibles, list):
            for entry in cast(list[object], combustibles):
                if not isinstance(entry, dict):
                    continue
                rec = cast(dict[object, object], entry)
                label = str(rec.get("id") or rec.get("tipo") or rec.get("nombre") or "")
                grade = _map_cl_cne_grade(label)
                if grade is None:
                    continue
                price = parse_positive_float(rec.get("precio"))
                if price is not None:
                    samples.setdefault(grade, []).append(price)

    prices: dict[FuelGrade, float] = {
        grade: statistics.median(vals) for grade, vals in samples.items() if vals
    }
    if "diesel" not in prices or "petrol_95" not in prices:
        raise ValueError("CL CNE yielded no valid diesel or petrol_95 station prices")

    data_date = max(dates) if dates else datetime.now(UTC).date().isoformat()
    return prices, data_date


def fetch_cl_cne(
    client: httpx.Client,
    *,
    api_token: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Chile CNE Bencina en Linea v4/v3 station medians (optional CNE_API_TOKEN)."""
    resolved_token = (
        api_token if api_token is not None else os.environ.get("CNE_API_TOKEN", "")
    ).strip()
    if not resolved_token:
        return RawFuelFeedResult(
            feed_name="cl_cne",
            tier="tier1",
            region_scope="global",
            ok=True,
            skipped=True,
            skip_reason="skipped (CNE_API_TOKEN unset; retaining lockfile/Tier 3)",
            quotes=[],
        )

    errors: list[str] = []
    attempts: tuple[tuple[str, dict[str, str] | None, dict[str, str] | None], ...] = (
        (CL_CNE_V4_URL, None, {"Authorization": f"Bearer {resolved_token}"}),
        (CL_CNE_V3_URL, {"token": resolved_token}, None),
    )
    for url, params, headers in attempts:
        try:
            raw = fetch_bytes_with_retry(
                client,
                url,
                allowed_hosts=CL_CNE_ALLOWED_HOSTS,
                params=params,
                headers=headers,
                max_bytes=DEFAULT_MAX_RESPONSE_BYTES,
                sleep_fn=sleep_fn,
            )
            payload: object = json.loads(raw.decode("utf-8"))
            prices, data_date = _parse_cl_cne_stations(payload)
            quote = RawCountryFuelQuote(
                iso2="CL",
                currency="CLP",
                prices_by_grade=prices,
                unit_basis="local_per_liter",
                source="cl_cne",
                license="Chilean Open Gov Data (CNE)",
                data_date=data_date,
            )
            return RawFuelFeedResult(
                feed_name="cl_cne",
                tier="tier1",
                region_scope="global",
                ok=True,
                skipped=False,
                quotes=[quote],
                data_date=data_date,
            )
        except (
            HttpFetchError,
            httpx.HTTPError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            errors.append(_scrub_secret(str(exc), resolved_token))

    return RawFuelFeedResult(
        feed_name="cl_cne",
        tier="tier1",
        region_scope="global",
        ok=False,
        skipped=False,
        quotes=[],
        error=_scrub_secret("; ".join(errors), resolved_token),
    )


def fetch_my_opendosm(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Malaysia OpenDOSM / MOF weekly national fuel prices (CC BY 4.0, keyless)."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            MY_OPENDOSM_URL,
            allowed_hosts=MY_OPENDOSM_ALLOWED_HOSTS,
            params={
                "id": "fuelprice",
                "filter": "level@series_type",
                "sort": "-date",
                "limit": "5",
            },
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, list) or not payload:
            raise ValueError("MY OpenDOSM payload is not a non-empty JSON array")

        best_date: str | None = None
        best_prices: dict[FuelGrade, float] | None = None
        for item in cast(list[object], payload):
            if not isinstance(item, dict):
                continue
            row = cast(dict[object, object], item)
            if row.get("series_type") != "level":
                continue
            row_date = extract_iso_date(row.get("date"))
            if row_date is None:
                continue
            ron95 = parse_positive_float(row.get("ron95"))
            diesel = parse_positive_float(row.get("diesel"))
            if diesel is None:
                diesel = parse_positive_float(row.get("diesel_eastmsia"))
            if ron95 is None or diesel is None:
                continue

            prices: dict[FuelGrade, float] = {
                "diesel": diesel,
                "petrol_95": ron95,
            }
            ron97 = parse_positive_float(row.get("ron97"))
            if ron97 is not None:
                prices["petrol_98"] = ron97

            if best_date is None or row_date > best_date:
                best_date = row_date
                best_prices = prices

        if best_date is None or best_prices is None:
            raise ValueError("MY OpenDOSM returned zero valid series_type='level' rows")

        quote = RawCountryFuelQuote(
            iso2="MY",
            currency="MYR",
            prices_by_grade=best_prices,
            unit_basis="local_per_liter",
            source="my_opendosm",
            license="CC BY 4.0 (OpenDOSM / MOF Malaysia)",
            data_date=best_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="my_opendosm",
            tier="tier1",
            region_scope="global",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="my_opendosm",
        tier="tier1",
        region_scope="global",
        ok=True,
        quotes=[quote],
        data_date=best_date,
    )


def discover_jp_meti_xlsx_url(
    html_text: str,
    base_url: str = JP_METI_LANDING_URL,
) -> str:
    """Discover the latest JP METI .xlsx link (explicitly rejecting .xls) under HTTPS allowlist."""
    parser = AnchorExtractor()
    parser.feed(html_text)
    parser.close()

    scored: list[tuple[int, str]] = []
    for href, text in parser.anchors:
        resolved = urljoin(base_url, href)
        path_lower = urlsplit(resolved).path.lower()
        # Explicitly reject legacy BIFF8 .xls files per D-03
        if not path_lower.endswith(".xlsx"):
            continue
        score = 5
        combined = f"{path_lower} {text}"
        if "結果" in combined or "results" in combined or "最新" in combined:
            score += 4
        if "xlsx" in path_lower:
            score += 2
        scored.append((score, resolved))

    if not scored:
        raise ValueError("JP METI landing page contained no .xlsx link (legacy .xls is rejected)")

    scored.sort(key=lambda item: item[0], reverse=True)
    return validate_https_url(scored[0][1], JP_METI_ALLOWED_HOSTS)


def _match_jp_meti_grade_header(text: str) -> FuelGrade | None:
    cleaned = "".join(text.split())
    if not cleaned or "灯油" in cleaned:
        return None
    if "レギュラー" in cleaned:
        return "petrol_95"
    if "ハイオク" in cleaned:
        return "petrol_98"
    if "軽油" in cleaned:
        return "diesel"
    return None


def parse_jp_meti_xlsx(
    raw_xlsx: bytes,
    *,
    max_rows: int = JP_METI_MAX_ROWS,
    default_date: str | None = None,
) -> tuple[RawCountryFuelQuote, str]:
    """Parse JP METI .xlsx national average row (ignoring 18L kerosene) with OOXML safety guard."""
    if len(raw_xlsx) > JP_METI_MAX_XLSX_BYTES:
        raise ValueError(
            f"JP METI .xlsx payload size {len(raw_xlsx)} exceeds max {JP_METI_MAX_XLSX_BYTES} bytes"
        )
    validate_ooxml_zip_safety(raw_xlsx)

    wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx), read_only=True, data_only=True)
    try:
        scanned_rows = 0
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            detected_date: str | None = None
            grade_cols: dict[FuelGrade, int] = {}
            headers_locked = False
            national_prices: dict[FuelGrade, float] | None = None
            latest_ts_date: str | None = None
            latest_ts_prices: dict[FuelGrade, float] | None = None
            sheet_is_national = "全国" in sheet_name

            for row in ws.iter_rows(values_only=True):
                scanned_rows += 1
                if scanned_rows > max_rows:
                    break

                # Scan cells for Japanese/ISO dates and multi-row grade headers (lock once found)
                row_date: str | None = None
                for idx, cell in enumerate(row):
                    if isinstance(cell, str):
                        if "全国" in cell:
                            sheet_is_national = True
                        if not headers_locked:
                            matched_grade = _match_jp_meti_grade_header(cell)
                            if matched_grade is not None:
                                grade_cols[matched_grade] = idx
                    maybe_date = _parse_jp_date(cell)
                    if maybe_date is not None:
                        row_date = maybe_date
                        if detected_date is None or maybe_date > detected_date:
                            detected_date = maybe_date

                if not headers_locked and "diesel" in grade_cols and "petrol_95" in grade_cols:
                    headers_locked = True

                if "diesel" not in grade_cols or "petrol_95" not in grade_cols:
                    continue

                # Check Layout A: row labeled 全国 / 全国平均
                row_label = ""
                for cell in row[:2]:
                    if isinstance(cell, str) and cell.strip():
                        row_label = "".join(cell.split())
                        break

                if "全国" in row_label:
                    extracted: dict[FuelGrade, float] = {}
                    for grade, col_idx in grade_cols.items():
                        if col_idx < len(row):
                            val = parse_positive_float(row[col_idx])
                            if val is not None:
                                extracted[grade] = val
                    if "diesel" in extracted and "petrol_95" in extracted:
                        national_prices = extracted
                        break

                # Check Layout B: national time-series row with explicit date
                if sheet_is_national and row_date is not None:
                    extracted_ts: dict[FuelGrade, float] = {}
                    for grade, col_idx in grade_cols.items():
                        if col_idx < len(row):
                            val = parse_positive_float(row[col_idx])
                            if val is not None:
                                extracted_ts[grade] = val
                    if (
                        "diesel" in extracted_ts
                        and "petrol_95" in extracted_ts
                        and (latest_ts_date is None or row_date > latest_ts_date)
                    ):
                        latest_ts_date = row_date
                        latest_ts_prices = extracted_ts

            chosen_prices = national_prices or latest_ts_prices
            if chosen_prices is not None:
                resolved_date = (
                    (detected_date if national_prices is not None else latest_ts_date)
                    or detected_date
                    or default_date
                    or datetime.now(UTC).date().isoformat()
                )
                quote = RawCountryFuelQuote(
                    iso2="JP",
                    currency="JPY",
                    prices_by_grade=chosen_prices,
                    unit_basis="local_per_liter",
                    source="jp_meti",
                    license="Government of Japan Standard Terms v2.0 (METI/ANRE)",
                    data_date=resolved_date,
                )
                return quote, resolved_date
    finally:
        wb.close()

    raise ValueError("JP METI .xlsx workbook contained no parseable national average fuel prices")


def fetch_jp_meti(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Discover and fetch the latest Japan METI weekly .xlsx survey (rejecting .xls)."""
    try:
        landing_raw = fetch_bytes_with_retry(
            client,
            JP_METI_LANDING_URL,
            allowed_hosts=JP_METI_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        landing_html = landing_raw.decode("utf-8", errors="replace")
        xlsx_url = discover_jp_meti_xlsx_url(landing_html, JP_METI_LANDING_URL)
        raw_xlsx = fetch_bytes_with_retry(
            client,
            xlsx_url,
            allowed_hosts=JP_METI_ALLOWED_HOSTS,
            max_bytes=JP_METI_MAX_XLSX_BYTES,
            sleep_fn=sleep_fn,
        )
        quote, data_date = parse_jp_meti_xlsx(raw_xlsx)
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        OSError,
        InvalidFileException,
        zipfile.BadZipFile,
        ET.ParseError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="jp_meti",
            tier="tier1",
            region_scope="global",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="jp_meti",
        tier="tier1",
        region_scope="global",
        ok=True,
        quotes=[quote],
        data_date=data_date,
    )


def fetch_kr_opinet(
    client: httpx.Client,
    *,
    api_key: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch South Korea KNOC Opinet daily national averages (optional OPINET_API_KEY)."""
    resolved_key = (
        api_key if api_key is not None else os.environ.get("OPINET_API_KEY", "")
    ).strip()
    if not resolved_key:
        return RawFuelFeedResult(
            feed_name="kr_opinet",
            tier="tier1",
            region_scope="global",
            ok=True,
            skipped=True,
            skip_reason="skipped (OPINET_API_KEY unset; retaining lockfile/Tier 3)",
            quotes=[],
        )

    try:
        raw = fetch_bytes_with_retry(
            client,
            KR_OPINET_URL,
            allowed_hosts=KR_OPINET_ALLOWED_HOSTS,
            params={"out": "json", "code": resolved_key},
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("KR Opinet payload is not a JSON object")
        root = cast(dict[object, object], payload)
        result_obj = root.get("RESULT")
        if not isinstance(result_obj, dict):
            raise ValueError("KR Opinet payload missing 'RESULT' object")
        oil_rows = cast(dict[object, object], result_obj).get("OIL")
        if not isinstance(oil_rows, list) or not oil_rows:
            raise ValueError("KR Opinet payload missing non-empty 'RESULT.OIL' list")

        prices: dict[FuelGrade, float] = {}
        dates: list[str] = []
        for item in cast(list[object], oil_rows):
            if not isinstance(item, dict):
                continue
            row = cast(dict[object, object], item)
            prodcd = str(row.get("PRODCD", "")).strip().upper()
            grade = _KR_OPINET_PRODUCT_MAP.get(prodcd)
            if grade is None:
                continue
            price = parse_positive_float(row.get("PRICE"))
            if price is None:
                continue
            prices[grade] = price
            parsed_date = _parse_yyyymmdd_date(row.get("TRADE_DT"))
            if parsed_date is not None:
                dates.append(parsed_date)

        if "diesel" not in prices or "petrol_95" not in prices:
            raise ValueError("KR Opinet response missing required D047 diesel or B027 petrol_95")
        if not dates:
            raise ValueError("KR Opinet response missing valid TRADE_DT date")

        data_date = max(dates)
        quote = RawCountryFuelQuote(
            iso2="KR",
            currency="KRW",
            prices_by_grade=prices,
            unit_basis="local_per_liter",
            source="kr_opinet",
            license="Korean Public Data Open License (KNOC Opinet)",
            data_date=data_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="kr_opinet",
            tier="tier1",
            region_scope="global",
            ok=False,
            skipped=False,
            quotes=[],
            error=_scrub_secret(str(exc), resolved_key),
        )

    return RawFuelFeedResult(
        feed_name="kr_opinet",
        tier="tier1",
        region_scope="global",
        ok=True,
        skipped=False,
        quotes=[quote],
        data_date=data_date,
    )


def fetch_all_global_tier1_feeds(
    client: httpx.Client,
    *,
    eia_api_key: str | None = None,
    opinet_api_key: str | None = None,
    cne_api_token: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> list[RawFuelFeedResult]:
    """Run all 8 non-EU Tier 1 open government fuel collectors in deterministic order."""
    return [
        fetch_us_eia_v2(client, api_key=eia_api_key, sleep_fn=sleep_fn),
        fetch_br_anp(client, sleep_fn=sleep_fn),
        fetch_ar_energia(client, sleep_fn=sleep_fn),
        fetch_co_sicom(client, sleep_fn=sleep_fn),
        fetch_cl_cne(client, api_token=cne_api_token, sleep_fn=sleep_fn),
        fetch_my_opendosm(client, sleep_fn=sleep_fn),
        fetch_jp_meti(client, sleep_fn=sleep_fn),
        fetch_kr_opinet(client, api_key=opinet_api_key, sleep_fn=sleep_fn),
    ]
