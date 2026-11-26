"""Non-EU Tier 1 open government fuel price collectors (GLB-01: US, BR, AR, CO, CL, MY, JP, KR)."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Final, cast

import httpx

from ets2v2.fetch._parsing import extract_iso_date, parse_positive_float
from ets2v2.fetch.http import (
    HttpFetchError,
    fetch_bytes_with_retry,
    redact_url_secrets,
)
from ets2v2.fetch.models import RawCountryFuelQuote, RawFuelFeedResult
from ets2v2.normalize.models import FuelGrade

NIST_LITERS_PER_US_GALLON: Final[Decimal] = Decimal("3.785411784")

US_EIA_V2_URL: Final[str] = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
US_EIA_V2_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"api.eia.gov"})
_US_EIA_PRODUCT_MAP: Final[dict[str, FuelGrade]] = {
    "EPD2D": "diesel",
    "EPMR": "petrol_95",
    "EPMP": "petrol_98",
}

MY_OPENDOSM_URL: Final[str] = "https://api.data.gov.my/data-catalogue"
MY_OPENDOSM_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"api.data.gov.my"})

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
