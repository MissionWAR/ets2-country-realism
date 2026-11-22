"""Multi-provider online FX fetchers (Frankfurter v2, ECB XML, fawazahmed0, CBR XML)."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

import httpx

from ets2v2.fetch.http import (
    DEFAULT_MAX_XML_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    HttpFetchError,
    create_http_client,
    fetch_bytes_with_retry,
    parse_xml_safe,
    redact_url_secrets,
)
from ets2v2.fetch.models import (
    FetchRunReport,
    FxFetchBundle,
    ProviderFetchStatus,
    RawFxProviderQuote,
)
from ets2v2.normalize.fx import (
    CBR_FX_PROVIDER,
    ECB_FX_PROVIDER,
    FAWAZ_FX_PROVIDER,
    PRIMARY_FX_PROVIDER,
    FxProviderQuote,
    cross_validate_fx_rates,
)
from ets2v2.normalize.lockfile import load_prices_lockfile, write_prices_lockfile
from ets2v2.normalize.models import FxRateLockEntry, LockAlert, PricesLockfile

FRANKFURTER_V2_URL: Final[str] = "https://api.frankfurter.dev/v2/rates?base=EUR"
ECB_DAILY_XML_URL: Final[str] = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
FAWAZ_JSDELIVR_URL: Final[str] = (
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/eur.json"
)
FAWAZ_CLOUDFLARE_URL: Final[str] = "https://latest.currency-api.pages.dev/v1/currencies/eur.json"
CBR_DAILY_XML_URL: Final[str] = "https://www.cbr.ru/scripts/XML_daily.asp"

_FRANKFURTER_HOSTS: Final[frozenset[str]] = frozenset({"api.frankfurter.dev"})
_ECB_HOSTS: Final[frozenset[str]] = frozenset({"www.ecb.europa.eu"})
_FAWAZ_JSDELIVR_HOSTS: Final[frozenset[str]] = frozenset({"cdn.jsdelivr.net"})
_FAWAZ_CLOUDFLARE_HOSTS: Final[frozenset[str]] = frozenset({"latest.currency-api.pages.dev"})
_CBR_HOSTS: Final[frozenset[str]] = frozenset({"www.cbr.ru"})


def _parse_positive_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Expected numeric rate for {label}, got {type(value).__name__}")
    rate = float(value)
    if not math.isfinite(rate) or rate <= 0.0:
        raise ValueError(f"Invalid non-positive or non-finite rate for {label}: {rate!r}")
    return rate


def _local_xml_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def fetch_frankfurter_v2(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFxProviderQuote:
    """Fetch and parse Frankfurter v2 flat JSON array (``[{"date","base","quote","rate"}]``)."""
    raw = fetch_bytes_with_retry(
        client,
        FRANKFURTER_V2_URL,
        allowed_hosts=_FRANKFURTER_HOSTS,
        sleep_fn=sleep_fn,
    )
    payload: object = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Expected non-empty Frankfurter v2 flat JSON array")
    rows = cast(list[object], payload)

    rates: dict[str, float] = {}
    latest_date = ""
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("Expected JSON object elements in Frankfurter v2 array")
        row = cast(dict[object, object], item)
        base_val = row.get("base")
        if base_val != "EUR":
            raise ValueError(f"Unexpected Frankfurter v2 base currency: {base_val!r}")
        quote_val = row.get("quote")
        date_val = row.get("date")
        if not isinstance(quote_val, str) or not quote_val.strip():
            raise ValueError(f"Invalid Frankfurter v2 quote code: {quote_val!r}")
        if not isinstance(date_val, str) or len(date_val) != 10:
            raise ValueError(f"Invalid Frankfurter v2 date: {date_val!r}")
        code = quote_val.strip().upper()
        rate = _parse_positive_number(row.get("rate"), label=f"frankfurter_v2:{code}")
        rates[code] = rate
        if date_val > latest_date:
            latest_date = date_val

    if not rates or not latest_date:
        raise ValueError("Frankfurter v2 response contained no usable FX rates")
    return RawFxProviderQuote(provider=PRIMARY_FX_PROVIDER, data_date=latest_date, rates=rates)


def fetch_ecb_daily_xml(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFxProviderQuote:
    """Fetch and parse ECB ``eurofxref-daily.xml`` (gracefully handles suspended RUB)."""
    raw = fetch_bytes_with_retry(
        client,
        ECB_DAILY_XML_URL,
        allowed_hosts=_ECB_HOSTS,
        max_bytes=DEFAULT_MAX_XML_BYTES,
        sleep_fn=sleep_fn,
    )
    root = parse_xml_safe(raw, encoding="utf-8", max_bytes=DEFAULT_MAX_XML_BYTES)

    time_cube: ET.Element | None = None
    for elem in root.iter():
        if _local_xml_tag(elem.tag) == "Cube" and "time" in elem.attrib:
            time_cube = elem
            break
    if time_cube is None:
        raise ValueError("ECB XML missing dated <Cube time='...'> element")

    data_date = time_cube.attrib["time"].strip()
    rates: dict[str, float] = {}
    for child in time_cube:
        if _local_xml_tag(child.tag) != "Cube":
            continue
        currency = child.attrib.get("currency", "").strip().upper()
        rate_str = child.attrib.get("rate", "").strip()
        if not currency or not rate_str:
            continue
        rate = float(rate_str)
        if not math.isfinite(rate) or rate <= 0.0:
            raise ValueError(f"Invalid ECB XML rate for {currency}: {rate_str!r}")
        rates[currency] = rate

    if not rates:
        raise ValueError("ECB XML contained zero currency rates")
    return RawFxProviderQuote(provider=ECB_FX_PROVIDER, data_date=data_date, rates=rates)


def _parse_fawazahmed0_payload(raw: bytes) -> RawFxProviderQuote:
    payload: object = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object from fawazahmed0 currency API")
    payload_dict = cast(dict[object, object], payload)
    date_val = payload_dict.get("date")
    eur_map = payload_dict.get("eur")
    if not isinstance(date_val, str) or len(date_val) != 10:
        raise ValueError(f"Invalid date field in fawazahmed0 response: {date_val!r}")
    if not isinstance(eur_map, dict) or not eur_map:
        raise ValueError("Missing or empty 'eur' object in fawazahmed0 response")
    eur_entries = cast(dict[object, object], eur_map)

    rates: dict[str, float] = {}
    for key_obj, val_obj in eur_entries.items():
        if not isinstance(key_obj, str):
            continue
        code = key_obj.strip().upper()
        if len(code) != 3 or not code.isascii() or not code.isalpha():
            continue
        if isinstance(val_obj, bool) or not isinstance(val_obj, (int, float)):
            continue
        rate = float(val_obj)
        if math.isfinite(rate) and rate > 0.0:
            rates[code] = rate

    if not rates:
        raise ValueError("fawazahmed0 response contained zero valid 3-letter currency rates")
    return RawFxProviderQuote(provider=FAWAZ_FX_PROVIDER, data_date=date_val, rates=rates)


def fetch_fawazahmed0_eur(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFxProviderQuote:
    """Fetch ``fawazahmed0`` EUR rates via jsDelivr with Cloudflare Pages mirror fallback."""
    primary_error: Exception | None = None
    try:
        raw_primary = fetch_bytes_with_retry(
            client,
            FAWAZ_JSDELIVR_URL,
            allowed_hosts=_FAWAZ_JSDELIVR_HOSTS,
            sleep_fn=sleep_fn,
        )
        return _parse_fawazahmed0_payload(raw_primary)
    except (HttpFetchError, httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        primary_error = exc

    try:
        raw_mirror = fetch_bytes_with_retry(
            client,
            FAWAZ_CLOUDFLARE_URL,
            allowed_hosts=_FAWAZ_CLOUDFLARE_HOSTS,
            sleep_fn=sleep_fn,
        )
        return _parse_fawazahmed0_payload(raw_mirror)
    except (HttpFetchError, httpx.HTTPError, ValueError, json.JSONDecodeError) as mirror_exc:
        raise HttpFetchError(
            redact_url_secrets(
                f"fawazahmed0 primary ({primary_error}) and mirror ({mirror_exc}) both failed"
            )
        ) from None


def _parse_cbr_decimal(raw_text: str, *, label: str) -> float:
    cleaned = raw_text.strip().replace(",", ".")
    val = float(cleaned)
    if not math.isfinite(val) or val <= 0.0:
        raise ValueError(f"Invalid CBR numeric field {label}: {raw_text!r}")
    return val


def _parse_cbr_date(raw_date: str) -> str:
    parts = raw_date.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid CBR ValCurs Date attribute: {raw_date!r}")
    day_s, month_s, year_s = parts
    parsed = datetime(int(year_s), int(month_s), int(day_s), tzinfo=UTC).date()
    return parsed.isoformat()


def fetch_cbr_daily_xml(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFxProviderQuote:
    """Fetch and parse Central Bank of Russia XML (``windows-1251``, comma decimals, EUR->RUB)."""
    raw = fetch_bytes_with_retry(
        client,
        CBR_DAILY_XML_URL,
        allowed_hosts=_CBR_HOSTS,
        max_bytes=DEFAULT_MAX_XML_BYTES,
        sleep_fn=sleep_fn,
    )
    root = parse_xml_safe(raw, encoding="windows-1251", max_bytes=DEFAULT_MAX_XML_BYTES)
    raw_date = root.attrib.get("Date", "")
    iso_date = _parse_cbr_date(raw_date)

    for valute in root.findall("Valute"):
        char_code = (valute.findtext("CharCode") or "").strip().upper()
        if char_code != "EUR":
            continue
        vunit_text = (valute.findtext("VunitRate") or "").strip()
        if vunit_text:
            rub_per_eur = _parse_cbr_decimal(vunit_text, label="VunitRate")
        else:
            value_text = (valute.findtext("Value") or "").strip()
            nominal_text = (valute.findtext("Nominal") or "1").strip()
            value_num = _parse_cbr_decimal(value_text, label="Value")
            nominal_num = _parse_cbr_decimal(nominal_text, label="Nominal")
            rub_per_eur = value_num / nominal_num
        return RawFxProviderQuote(
            provider=CBR_FX_PROVIDER,
            data_date=iso_date,
            rates={"RUB": rub_per_eur},
        )

    raise ValueError("CBR XML response did not contain a CharCode='EUR' Valute entry")


def fetch_all_fx_quotes(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> FxFetchBundle:
    """Invoke all 4 FX providers with isolated error handling so single outages never abort."""
    fetchers: tuple[tuple[str, Callable[[httpx.Client], RawFxProviderQuote]], ...] = (
        (PRIMARY_FX_PROVIDER, lambda c: fetch_frankfurter_v2(c, sleep_fn=sleep_fn)),
        (ECB_FX_PROVIDER, lambda c: fetch_ecb_daily_xml(c, sleep_fn=sleep_fn)),
        (FAWAZ_FX_PROVIDER, lambda c: fetch_fawazahmed0_eur(c, sleep_fn=sleep_fn)),
        (CBR_FX_PROVIDER, lambda c: fetch_cbr_daily_xml(c, sleep_fn=sleep_fn)),
    )

    quotes: dict[str, RawFxProviderQuote] = {}
    statuses: list[ProviderFetchStatus] = []
    for provider_name, fn in fetchers:
        try:
            quote = fn(client)
        except (
            HttpFetchError,
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            ET.ParseError,
            json.JSONDecodeError,
        ) as exc:
            statuses.append(
                ProviderFetchStatus(
                    provider=provider_name,
                    ok=False,
                    detail=redact_url_secrets(str(exc)),
                )
            )
            continue

        quotes[provider_name] = quote
        statuses.append(
            ProviderFetchStatus(
                provider=provider_name,
                ok=True,
                data_date=quote.data_date,
            )
        )

    return FxFetchBundle(quotes=quotes, statuses=statuses)


def run_fx_only_fetch(
    *,
    lock_path: Path,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    write_lock: bool = False,
    transport: httpx.BaseTransport | None = None,
    fetched_at: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> FetchRunReport:
    """Run online multi-provider FX fetch + D-07 cross-validation (``ets2v2 fetch --fx-only``)."""
    existing_lock: PricesLockfile | None = None
    previous_fx: dict[str, FxRateLockEntry] | None = None
    if lock_path.is_file():
        existing_lock = load_prices_lockfile(lock_path)
        previous_fx = dict(existing_lock.fx_rates)

    now_iso = fetched_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    with create_http_client(timeout=timeout, transport=transport) as client:
        bundle = fetch_all_fx_quotes(client, sleep_fn=sleep_fn)

    provider_quotes: dict[str, FxProviderQuote] = {
        name: FxProviderQuote(
            provider=quote.provider,
            data_date=quote.data_date,
            rates=dict(quote.rates),
        )
        for name, quote in bundle.quotes.items()
    }
    validation = cross_validate_fx_rates(
        provider_quotes,
        previous_fx=previous_fx,
        fetched_at=now_iso,
    )

    alerts: list[LockAlert] = []
    for status in bundle.statuses:
        if not status.ok:
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="fx_provider_outage",
                    scope=status.provider,
                    detail=redact_url_secrets(status.detail or "provider fetch failed"),
                )
            )
    alerts.extend(validation.alerts)

    if write_lock and validation.ok:
        updated_lock = (
            existing_lock.model_copy(
                update={
                    "updated_at": now_iso,
                    "fx_rates": validation.rates,
                    "alerts": alerts,
                }
            )
            if existing_lock is not None
            else PricesLockfile(
                schema_version=1,
                updated_at=now_iso,
                fx_rates=validation.rates,
                countries={},
                alerts=alerts,
            )
        )
        write_prices_lockfile(updated_lock, lock_path)

    return FetchRunReport(
        ok=validation.ok,
        fx_only=True,
        dry_run=not write_lock,
        lock_path=lock_path,
        tier1_feeds_succeeded=0,
        tier1_feeds_failed=0,
        countries_updated=0,
        countries_fallback=0,
        fx_currencies_validated=len(validation.rates),
        alerts=alerts,
        provider_statuses=bundle.statuses,
    )
