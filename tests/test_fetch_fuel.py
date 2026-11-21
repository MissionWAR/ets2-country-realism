"""100% offline httpx.MockTransport + in-memory openpyxl tests for Tier 1 fuel collectors."""

from __future__ import annotations

import io
from datetime import date

import httpx
import openpyxl
import pytest

from ets2v2.fetch.ec_bulletin import (
    EC_WOB_LANDING_URL,
    FIONNHUGHES_CSV_URL,
    FUEL_PRICES_EU_URL,
    discover_ec_wob_xlsx_url,
    fetch_ec_weekly_oil_bulletin,
    fetch_fionnhughes_fallback,
    fetch_fuel_prices_eu,
    parse_ec_wob_xlsx,
)
from ets2v2.fetch.http import create_http_client

_EU27_SAMPLE_ROWS: list[tuple[str, float, float, float | None]] = [
    ("AT", 1598.0, 1572.0, 910.0),
    ("BE", 1654.0, 1680.0, 745.0),
    ("BG", 1295.0, 1310.0, 620.0),
    ("CY", 1450.0, 1510.0, None),
    ("CZ", 1465.0, 1480.0, 690.0),
    ("DE", 1742.0, 1642.5, 995.0),
    ("DK", 1915.0, 1785.0, None),
    ("EE", 1620.0, 1580.0, 780.0),
    ("EL", 1812.0, 1594.0, 890.0),  # Eurostat EL -> ISO GR
    ("ES", 1580.0, 1495.0, 940.0),
    ("FI", 1790.0, 1715.0, None),
    ("FR", 1765.0, 1675.0, 990.0),
    ("HR", 1520.0, 1480.0, 810.0),
    ("HU", 1530.0, 1550.0, 820.0),
    ("IE", 1775.0, 1735.0, 960.0),
    ("IT", 1810.0, 1710.0, 740.0),
    ("LT", 1510.0, 1490.0, 710.0),
    ("LU", 1525.0, 1460.0, 730.0),
    ("LV", 1585.0, 1555.0, 760.0),
    ("MT", 1340.0, 1210.0, None),
    ("NL", 1960.0, 1745.0, 885.0),
    ("PL", 1435.0, 1455.0, 680.0),
    ("PT", 1730.0, 1615.0, 870.0),
    ("RO", 1460.0, 1495.0, 720.0),
    ("SE", 1575.0, 1630.0, None),
    ("SI", 1515.0, 1535.0, 830.0),
    ("SK", 1560.0, 1505.0, 740.0),
]


def _build_ec_wob_xlsx_bytes(*, extra_padding_rows: int = 0) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Prices with taxes"
    ws.append(["Weekly Oil Bulletin — Consumer prices with taxes"])
    ws.append(["Prices in force on", date(2026, 11, 16)])
    ws.append(["Country", "Euro-super 95", "Automotive gas oil", "LPG - motor fuel"])
    for code, p95, diesel, lpg in _EU27_SAMPLE_ROWS:
        ws.append([code, p95, diesel, lpg])
    ws.append(["EU27", 1690.0, 1610.0, 840.0])  # Summary row must be ignored
    for idx in range(extra_padding_rows):
        ws.append([f"NOTE_{idx}", None, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_discover_ec_wob_xlsx_url_resolves_relative_and_blocks_ssrf() -> None:
    good_html = (
        "<html><body>"
        '<a href="/document/download/abc123_en'
        '?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx">'
        "Prices with taxes (XLSX)</a>"
        "</body></html>"
    )
    resolved = discover_ec_wob_xlsx_url(good_html, EC_WOB_LANDING_URL)
    assert resolved == (
        "https://energy.ec.europa.eu/document/download/abc123_en"
        "?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx"
    )

    evil_html = (
        "<html><body>"
        '<a href="https://evil.example/prices.xlsx">Prices with taxes (XLSX)</a>'
        "</body></html>"
    )
    with pytest.raises(ValueError, match="allowlist"):
        discover_ec_wob_xlsx_url(evil_html, EC_WOB_LANDING_URL)

    http_html = (
        "<html><body>"
        '<a href="http://energy.ec.europa.eu/document/download/abc123_en">'
        "Prices with taxes</a>"
        "</body></html>"
    )
    with pytest.raises(ValueError, match="HTTPS"):
        discover_ec_wob_xlsx_url(http_html, EC_WOB_LANDING_URL)


def test_parse_and_fetch_ec_weekly_oil_bulletin_covers_eu27_el_to_gr_and_size_cap() -> None:
    xlsx_bytes = _build_ec_wob_xlsx_bytes()
    quotes, data_date = parse_ec_wob_xlsx(xlsx_bytes)
    assert data_date == "2026-11-16"
    by_iso2 = {q.iso2: q for q in quotes}
    assert len(by_iso2) == 27
    assert "EL" not in by_iso2
    assert "GR" in by_iso2
    assert by_iso2["GR"].prices_by_grade["petrol_95"] == pytest.approx(1.812)
    assert by_iso2["GR"].prices_by_grade["diesel"] == pytest.approx(1.594)
    assert by_iso2["GR"].prices_by_grade["lpg"] == pytest.approx(0.890)
    assert by_iso2["DE"].prices_by_grade["diesel"] == pytest.approx(1.6425)
    assert by_iso2["IE"].prices_by_grade["diesel"] == pytest.approx(1.735)
    assert by_iso2["CY"].prices_by_grade["diesel"] == pytest.approx(1.510)
    assert by_iso2["MT"].prices_by_grade["diesel"] == pytest.approx(1.210)
    assert by_iso2["BG"].currency == "EUR"
    assert by_iso2["BG"].unit_basis == "eur_per_liter"
    assert "lpg" not in by_iso2["MT"].prices_by_grade

    # Oversized .xlsx byte cap rejection (> 20 MiB)
    with pytest.raises(ValueError, match=r"20971520|max"):
        parse_ec_wob_xlsx(b"x" * (20_971_520 + 1))

    # Full end-to-end mocked HTTP fetch (landing HTML -> Drupal .xlsx download)
    xlsx_download_url = (
        "https://energy.ec.europa.eu/document/download/7f8a9b_en"
        "?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx"
    )
    landing_html = (
        '<html><body><a href="/document/download/7f8a9b_en'
        '?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx">'
        "Weekly Oil Bulletin - Prices with taxes</a></body></html>"
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == EC_WOB_LANDING_URL:
            return httpx.Response(200, text=landing_html)
        if url == xlsx_download_url:
            return httpx.Response(200, content=xlsx_bytes)
        return httpx.Response(404, text=f"unexpected: {url}")

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_ec_weekly_oil_bulletin(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.tier == "tier1"
    assert result.feed_name == "ec_weekly_oil_bulletin"
    assert result.data_date == "2026-11-16"
    assert len(result.quotes) == 27


def test_fetch_fionnhughes_fallback_parses_latest_date_el_to_gr_and_unit_scaling() -> None:
    csv_text = (
        "date,geo,product,price\n"
        "2026-11-09,EL,Euro-super 95,1790.0\n"
        "2026-11-16,EL,Euro-super 95,1815.0\n"
        "2026-11-16,EL,Automotive gas oil,1595.0\n"
        "2026-11-16,EL,LPG - motor fuel,885.0\n"
        "2026-11-16,DE,Euro-super 95,1.742\n"
        "2026-11-16,DE,Automotive gas oil,1.645\n"
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == FIONNHUGHES_CSV_URL:
            return httpx.Response(200, text=csv_text)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_fionnhughes_fallback(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.tier == "fallback"
    by_iso2 = {q.iso2: q for q in result.quotes}
    assert by_iso2["GR"].data_date == "2026-11-16"
    assert by_iso2["GR"].prices_by_grade["petrol_95"] == pytest.approx(1.815)
    assert by_iso2["GR"].prices_by_grade["diesel"] == pytest.approx(1.595)
    assert by_iso2["GR"].prices_by_grade["lpg"] == pytest.approx(0.885)
    assert by_iso2["DE"].prices_by_grade["diesel"] == pytest.approx(1.645)


def test_fetch_fuel_prices_eu_parses_is_live_eur_and_rejects_ok_false() -> None:
    payload = {
        "ok": True,
        "ts": 1795154400,  # 2026-11-20 UTC
        "petrol": {"IS": 1.812, "UK": 1.695, "AD": 1.410},
        "diesel": {"IS": 1.845, "UK": 1.740, "AD": 1.350},
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == FUEL_PRICES_EU_URL:
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_fuel_prices_eu(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.tier == "fallback"
    by_iso2 = {q.iso2: q for q in result.quotes}
    assert "IS" in by_iso2
    assert "GB" in by_iso2
    assert "AD" not in by_iso2  # Outside 39 European territories
    assert by_iso2["IS"].prices_by_grade["petrol_95"] == pytest.approx(1.812)
    assert by_iso2["IS"].prices_by_grade["diesel"] == pytest.approx(1.845)
    assert by_iso2["IS"].unit_basis == "eur_per_liter"

    # ok: false must fail cleanly
    fail_transport = httpx.MockTransport(
        lambda _req: httpx.Response(200, json={"ok": False, "error": "rate_limited"})
    )
    with create_http_client(transport=fail_transport) as client:
        failed = fetch_fuel_prices_eu(client, sleep_fn=lambda _: None)
    assert failed.ok is False
    assert failed.error is not None
