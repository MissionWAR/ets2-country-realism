"""100% offline httpx.MockTransport + in-memory openpyxl tests for Tier 1 fuel collectors."""

from __future__ import annotations

import io
import zipfile
from datetime import date

import httpx
import openpyxl
import pytest

from ets2v2.fetch._parsing import extract_iso_date, parse_positive_float
from ets2v2.fetch.ec_bulletin import (
    EC_WOB_LANDING_URL,
    EC_WOB_MAX_UNCOMPRESSED_BYTES,
    EC_WOB_MAX_ZIP_ENTRIES,
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


def test_fetch_uk_desnz_discovers_csv_blocks_ssrf_and_converts_pence_to_gbp() -> None:
    from ets2v2.fetch.national import (
        UK_DESNZ_LANDING_URL,
        discover_uk_desnz_csv_url,
        fetch_uk_desnz,
    )

    csv_url = "https://assets.publishing.service.gov.uk/media/abc123/weekly_road_fuel_prices.csv"
    good_html = f'<html><body><a href="{csv_url}">Weekly road fuel prices (CSV)</a></body></html>'
    assert discover_uk_desnz_csv_url(good_html, UK_DESNZ_LANDING_URL) == csv_url

    with pytest.raises(ValueError, match="allowlist"):
        discover_uk_desnz_csv_url(
            '<a href="https://evil.example/weekly_road_fuel_prices.csv">'
            "Weekly road fuel prices</a>",
            UK_DESNZ_LANDING_URL,
        )

    csv_body = (
        "Date,ULSP: Pump price in pence/litre,ULSD: Pump price in pence/litre\n"
        "09/11/2026,137.5,141.8\n"
        "16/11/2026,138.4,142.9\n"
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == UK_DESNZ_LANDING_URL:
            return httpx.Response(200, text=good_html)
        if url == csv_url:
            return httpx.Response(200, text=csv_body)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_uk_desnz(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.tier == "tier1"
    assert result.data_date == "2026-11-16"
    assert len(result.quotes) == 1
    quote = result.quotes[0]
    assert quote.iso2 == "GB"
    assert quote.currency == "GBP"
    assert quote.unit_basis == "local_per_liter"
    assert quote.license == "OGL v3.0"
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(1.384)
    assert quote.prices_by_grade["diesel"] == pytest.approx(1.429)


def test_fetch_no_ssb_09654_parses_json_stat2_latest_non_null_month() -> None:
    from ets2v2.fetch.national import NO_SSB_09654_URL, fetch_no_ssb_09654

    json_stat2 = {
        "id": ["Drivstoff", "ContentsCode", "Tid"],
        "size": [2, 1, 3],
        "dimension": {
            "Drivstoff": {
                "category": {
                    "index": {"01": 0, "02": 1},
                    "label": {
                        "01": "Unleaded gasoline 95 octane",
                        "02": "Auto diesel (dutiable)",
                    },
                }
            },
            "ContentsCode": {
                "category": {
                    "index": {"Pris": 0},
                    "label": {"Pris": "Average retail price (NOK/l)"},
                }
            },
            "Tid": {
                "category": {
                    "index": {"2026M08": 0, "2026M09": 1, "2026M10": 2},
                    "label": {"2026M08": "2026M08", "2026M09": "2026M09", "2026M10": "2026M10"},
                }
            },
        },
        # Row-major: Drivstoff=01 (M08=21.10, M09=21.85, M10=None),
        # Drivstoff=02 (M08=20.20, M09=20.95, M10=None)
        "value": [21.10, 21.85, None, 20.20, 20.95, None],
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == NO_SSB_09654_URL:
            return httpx.Response(200, json=json_stat2)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_no_ssb_09654(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.tier == "tier1"
    assert result.data_date == "2026-09-01"
    quote = result.quotes[0]
    assert quote.iso2 == "NO"
    assert quote.currency == "NOK"
    assert quote.unit_basis == "local_per_liter"
    assert quote.license == "CC BY 4.0 (NLOD)"
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(21.85)
    assert quote.prices_by_grade["diesel"] == pytest.approx(20.95)


def test_fetch_fr_economie_parses_multigrade_and_e10_fallback() -> None:
    from ets2v2.fetch.national import fetch_fr_economie

    def _handler_full(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "results": [
                    {
                        "diesel": 1.682,
                        "petrol_95": 1.789,
                        "petrol_98": 1.879,
                        "e10": 1.745,
                        "e85": 0.889,
                        "lpg": 0.995,
                    }
                ],
            },
        )

    with create_http_client(transport=httpx.MockTransport(_handler_full)) as client:
        res = fetch_fr_economie(client, sleep_fn=lambda _: None)

    assert res.ok is True
    quote = res.quotes[0]
    assert quote.iso2 == "FR"
    assert quote.license == "Licence Ouverte v2.0"
    assert quote.prices_by_grade["diesel"] == pytest.approx(1.682)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(1.789)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(1.879)
    assert quote.prices_by_grade["e85"] == pytest.approx(0.889)
    assert quote.prices_by_grade["lpg"] == pytest.approx(0.995)

    # When sp95 is null, fall back to e10 for petrol_95
    def _handler_e10(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "results": [
                    {
                        "diesel": 1682.0,  # Guard milli-EUR scaling
                        "petrol_95": None,
                        "e10": 1.745,
                    }
                ],
            },
        )

    with create_http_client(transport=httpx.MockTransport(_handler_e10)) as client:
        res_e10 = fetch_fr_economie(client, sleep_fn=lambda _: None)

    assert res_e10.ok is True
    assert res_e10.quotes[0].prices_by_grade["diesel"] == pytest.approx(1.682)
    assert res_e10.quotes[0].prices_by_grade["petrol_95"] == pytest.approx(1.745)


def test_fetch_de_tankerkoenig_keyless_skip_keyed_median_and_secret_redaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ets2v2.fetch.national import TANKERKOENIG_CITIES, fetch_de_tankerkoenig

    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)

    # Keyless mode MUST issue zero HTTP requests and return ok=True, skipped=True
    def _must_not_call(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP call must not be made when TANKERKOENIG_API_KEY is unset")

    with create_http_client(transport=httpx.MockTransport(_must_not_call)) as client:
        skipped = fetch_de_tankerkoenig(client, sleep_fn=lambda _: None)

    assert skipped.ok is True
    assert skipped.skipped is True
    assert skipped.quotes == []
    assert skipped.feed_name == "de_tankerkoenig"

    # Keyed mode: 5 deterministic cities median over open stations only
    secret_key = "tk-super-secret-live-key-987654"
    calls: list[str] = []

    def _keyed_handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.url.params.get("apikey") == secret_key
        return httpx.Response(
            200,
            json={
                "ok": True,
                "stations": [
                    {"diesel": 1.639, "e5": 1.749, "e10": 1.689, "isOpen": True},
                    {"diesel": 1.659, "e5": 1.769, "e10": 1.709, "isOpen": True},
                    {"diesel": 9.999, "e5": 9.999, "isOpen": False},  # Closed -> ignored
                ],
            },
        )

    with create_http_client(transport=httpx.MockTransport(_keyed_handler)) as client:
        keyed = fetch_de_tankerkoenig(client, api_key=secret_key, sleep_fn=lambda _: None)

    assert len(calls) == len(TANKERKOENIG_CITIES) == 5
    assert keyed.ok is True
    assert keyed.skipped is False
    quote = keyed.quotes[0]
    assert quote.iso2 == "DE"
    assert quote.prices_by_grade["diesel"] == pytest.approx(1.649)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(1.759)

    # HTTP 401/500 MUST NEVER leak TANKERKOENIG_API_KEY in RawFuelFeedResult.error (T-03-07)
    def _fail_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"unauthorized for key {secret_key}")

    with create_http_client(transport=httpx.MockTransport(_fail_handler)) as client:
        errored = fetch_de_tankerkoenig(client, api_key=secret_key, sleep_fn=lambda _: None)

    assert errored.ok is False
    assert errored.skipped is False
    assert errored.error is not None
    assert secret_key not in errored.error


def test_fetch_es_miteco_comma_decimal_median_resilient_to_outliers() -> None:
    from ets2v2.fetch.national import ES_MITECO_URL, fetch_es_miteco

    payload = {
        "Fecha": "20/11/2026 07:30:00",
        "ListaEESSPrecio": [
            {
                "Precio Gasoleo A": "1,489",
                "Precio Gasoleo Premium": "1,599",
                "Precio Gasolina 95 E5": "1,569",
                "Precio Gasolina 98 E5": "1,719",
                "Precio Gases licuados del petróleo": "0,939",
            },
            {
                "Precio Gasoleo A": "1,499",
                "Precio Gasoleo Premium": "1,609",
                "Precio Gasolina 95 E5": "1,579",
                "Precio Gasolina 98 E5": "1,729",
                "Precio Gases licuados del petróleo": "0,949",
            },
            {
                # Typo outlier station defeated by median
                "Precio Gasoleo A": "99,990",
                "Precio Gasoleo Premium": "",
                "Precio Gasolina 95 E5": "1,589",
                "Precio Gasolina 98 E5": "1,739",
                "Precio Gases licuados del petróleo": "0,959",
            },
        ],
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == ES_MITECO_URL:
            assert request.headers.get("accept") == "application/json"
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_es_miteco(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.data_date == "2026-11-20"
    quote = result.quotes[0]
    assert quote.iso2 == "ES"
    assert quote.license == "Spanish Open Gov Data (MITECO)"
    assert quote.prices_by_grade["diesel"] == pytest.approx(1.499)
    assert quote.prices_by_grade["diesel_plus"] == pytest.approx(1.604)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(1.579)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(1.729)
    assert quote.prices_by_grade["lpg"] == pytest.approx(0.949)


def test_fetch_it_mimit_strips_banner_sniffs_delimiter_and_filters_isself() -> None:
    from ets2v2.fetch.national import IT_MIMIT_URL, fetch_it_mimit

    csv_text = (
        "Estrazione del 2026-11-20 08:00:00\n"
        "idImpianto;descCarburante;prezzo;isSelf;dtComu\n"
        "1001;Gasolio;1.699;1;20/11/2026 07:00:00\n"
        "1002;Gasolio;1.719;1;20/11/2026 07:00:00\n"
        "1003;Gasolio;2.099;0;20/11/2026 07:00:00\n"  # Attended (isSelf=0) -> ignored
        "1001;Benzina;1.799;1;20/11/2026 07:00:00\n"
        "1002;Benzina;1.819;1;20/11/2026 07:00:00\n"
        "1001;GPL;0.739;1;20/11/2026 07:00:00\n"
        "1001;Blue Diesel;1.849;1;20/11/2026 07:00:00\n"
        "1001;Blu Super;1.959;1;20/11/2026 07:00:00\n"
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == IT_MIMIT_URL:
            return httpx.Response(200, text=csv_text)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_it_mimit(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.data_date == "2026-11-20"
    quote = result.quotes[0]
    assert quote.iso2 == "IT"
    assert quote.license == "IODL 2.0"
    assert quote.prices_by_grade["diesel"] == pytest.approx(1.709)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(1.809)
    assert quote.prices_by_grade["lpg"] == pytest.approx(0.739)
    assert quote.prices_by_grade["diesel_plus"] == pytest.approx(1.849)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(1.959)


def test_fetch_nl_cbs_80416ned_filters_daily_perioden_and_rejects_annual_rows() -> None:
    from ets2v2.fetch.national import NL_CBS_80416NED_URL, fetch_nl_cbs_80416ned

    odata_payload = {
        "value": [
            {
                "Perioden": "2026JJ00",  # Annual summary row MUST be rejected
                "BenzineEuro95_1": 9.999,
                "Diesel_2": 9.999,
                "Lpg_3": 9.999,
            },
            {
                "Perioden": "2026MM11",  # Monthly summary row MUST be rejected
                "BenzineEuro95_1": 8.888,
                "Diesel_2": 8.888,
                "Lpg_3": 8.888,
            },
            {
                "Perioden": "20261119",
                "BenzineEuro95_1": 1.985,
                "Diesel_2": 1.742,
                "Lpg_3": 0.895,
            },
            {
                "Perioden": "20261118",
                "BenzineEuro95_1": 1.970,
                "Diesel_2": 1.730,
                "Lpg_3": 0.890,
            },
        ]
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == NL_CBS_80416NED_URL:
            return httpx.Response(200, json=odata_payload)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        result = fetch_nl_cbs_80416ned(client, sleep_fn=lambda _: None)

    assert result.ok is True
    assert result.data_date == "2026-11-19"
    quote = result.quotes[0]
    assert quote.iso2 == "NL"
    assert quote.license == "CC BY 4.0 (CBS)"
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(1.985)
    assert quote.prices_by_grade["diesel"] == pytest.approx(1.742)
    assert quote.prices_by_grade["lpg"] == pytest.approx(0.895)


def test_shared_parsing_mixed_european_english_separators_and_calendar_dates() -> None:
    assert parse_positive_float("1.750,50") == pytest.approx(1750.5)
    assert parse_positive_float("1,750.50") == pytest.approx(1750.5)
    assert parse_positive_float("1,489") == pytest.approx(1.489)
    assert parse_positive_float("1.234.567") == pytest.approx(1234567.0)
    assert parse_positive_float("1,234,567") == pytest.approx(1234567.0)
    assert parse_positive_float("1 750,50") == pytest.approx(1750.5)
    assert parse_positive_float("-") is None
    assert parse_positive_float(True) is None

    assert extract_iso_date("2026-11-20") == "2026-11-20"
    assert extract_iso_date("20/11/2026 08:00:00") == "2026-11-20"
    assert extract_iso_date("2026-99-01") is None
    assert extract_iso_date("31/02/2026") is None


def test_parse_ec_wob_xlsx_blocks_zip_bomb_entry_cap_and_doctype_xxe() -> None:
    # 1. High-ratio ZIP bomb (> 64 MiB uncompressed in a tiny compressed .xlsx)
    bomb_buf = io.BytesIO()
    with zipfile.ZipFile(bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "xl/sharedStrings.xml",
            b"<sst>" + (b" " * (EC_WOB_MAX_UNCOMPRESSED_BYTES + 1024)) + b"</sst>",
        )
    bomb_bytes = bomb_buf.getvalue()
    assert len(bomb_bytes) < 1_000_000  # tiny compressed archive well under 20 MiB cap
    with pytest.raises(ValueError, match="uncompressed"):
        parse_ec_wob_xlsx(bomb_bytes)

    # 2. OOXML member containing <!DOCTYPE / <!ENTITY declaration
    xxe_buf = io.BytesIO()
    with zipfile.ZipFile(xxe_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "xl/workbook.xml",
            b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            b"<workbook/>",
        )
    with pytest.raises(ValueError, match="DOCTYPE/ENTITY"):
        parse_ec_wob_xlsx(xxe_buf.getvalue())

    # 3. Excess ZIP entry count (> EC_WOB_MAX_ZIP_ENTRIES)
    many_buf = io.BytesIO()
    with zipfile.ZipFile(many_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(EC_WOB_MAX_ZIP_ENTRIES + 5):
            zf.writestr(f"xl/sheet_{i}.xml", b"<x/>")
    with pytest.raises(ValueError, match="entry count"):
        parse_ec_wob_xlsx(many_buf.getvalue())


def test_ec_wob_rejects_ex_tax_only_landing_page_and_worksheet() -> None:
    ex_tax_html = (
        "<html><body>"
        '<a href="/document/download/abc123_en'
        '?filename=Weekly_Oil_Bulletin_Prices_without_taxes.xlsx">'
        "Weekly Oil Bulletin - Prices without taxes (XLSX)</a>"
        '<a href="/document/download/def456_en'
        '?filename=Weekly_Oil_Bulletin_Net_Price.xlsx">'
        "Weekly Oil Bulletin - Net price excl. duties</a>"
        "</body></html>"
    )
    with pytest.raises(ValueError, match="Could not discover"):
        discover_ec_wob_xlsx_url(ex_tax_html, EC_WOB_LANDING_URL)

    # Workbook with only a "Prices without taxes" sheet must be rejected
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Prices without taxes"
    ws.append(["Country", "Euro-super 95", "Automotive gas oil"])
    ws.append(["DE", 820.0, 810.0])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="no parseable"):
        parse_ec_wob_xlsx(buf.getvalue())


def test_collectors_fault_isolate_html_for_xlsx_millisecond_ts_and_nul_csv() -> None:
    from ets2v2.fetch.national import (
        IT_MIMIT_URL,
        UK_DESNZ_LANDING_URL,
        fetch_it_mimit,
        fetch_uk_desnz,
    )

    # 1. HTTP 200 HTML maintenance page on EC WOB .xlsx download -> ok=False (not BadZipFile crash)
    xlsx_url = (
        "https://energy.ec.europa.eu/document/download/maint_en"
        "?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx"
    )
    landing_html = f'<a href="{xlsx_url}">Prices with taxes</a>'

    def _ec_html_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == EC_WOB_LANDING_URL:
            return httpx.Response(200, text=landing_html)
        return httpx.Response(200, text="<html><body>503 Maintenance</body></html>")

    with create_http_client(transport=httpx.MockTransport(_ec_html_handler)) as client:
        ec_res = fetch_ec_weekly_oil_bulletin(client, sleep_fn=lambda _: None)
    assert ec_res.ok is False
    assert ec_res.error is not None

    # 2. fuel-prices.eu millisecond timestamp normalizes cleanly; absurd/overflow ts -> ok=False
    ms_transport = httpx.MockTransport(
        lambda _req: httpx.Response(
            200,
            json={
                "ok": True,
                "ts": 1763618400000,  # 2025-11-20 in milliseconds
                "petrol": {"IS": 1.812},
                "diesel": {"IS": 1.845},
            },
        )
    )
    with create_http_client(transport=ms_transport) as client:
        ms_res = fetch_fuel_prices_eu(client, sleep_fn=lambda _: None)
    assert ms_res.ok is True
    assert ms_res.data_date == "2025-11-20"

    overflow_transport = httpx.MockTransport(
        lambda _req: httpx.Response(
            200,
            json={
                "ok": True,
                "ts": 9e18,
                "petrol": {"IS": 1.812},
                "diesel": {"IS": 1.845},
            },
        )
    )
    with create_http_client(transport=overflow_transport) as client:
        ov_res = fetch_fuel_prices_eu(client, sleep_fn=lambda _: None)
    assert ov_res.ok is False
    assert ov_res.error is not None

    # 3. NUL-byte CSV -> ok=False (not uncaught csv.Error) across UK DESNZ, IT MIMIT, FionnHughes
    uk_csv_url = "https://assets.publishing.service.gov.uk/media/bad/weekly_road_fuel_prices.csv"

    def _uk_nul_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == UK_DESNZ_LANDING_URL:
            return httpx.Response(200, text=f'<a href="{uk_csv_url}">Weekly road fuel CSV</a>')
        return httpx.Response(200, content=b"Date,ULSP,ULSD\n16/11/2026,\x00138.4,142.9\n")

    with create_http_client(transport=httpx.MockTransport(_uk_nul_handler)) as client:
        uk_res = fetch_uk_desnz(client, sleep_fn=lambda _: None)
    assert uk_res.ok is False

    it_nul_transport = httpx.MockTransport(
        lambda _req: httpx.Response(
            200,
            content=(
                b"Estrazione del 2026-11-20\nid;descCarburante;prezzo;isSelf\n1;Gasolio;\x00;1\n"
            ),
        )
    )
    with create_http_client(transport=it_nul_transport) as client:
        it_res = fetch_it_mimit(client, sleep_fn=lambda _: None)
    assert it_res.ok is False
    assert IT_MIMIT_URL.startswith("https://")

    fh_nul_transport = httpx.MockTransport(
        lambda _req: httpx.Response(
            200,
            content=b"date,geo,product,price\n2026-11-16,DE,Diesel,\x001640\n",
        )
    )
    with create_http_client(transport=fh_nul_transport) as client:
        fh_res = fetch_fionnhughes_fallback(client, sleep_fn=lambda _: None)
    assert fh_res.ok is False


def test_fetch_no_ssb_09654_resolves_multi_metric_contentscode_and_rejects_extra_dim() -> None:
    from ets2v2.fetch.national import NO_SSB_09654_URL, fetch_no_ssb_09654

    # ContentsCode has 2 series: idx 0 = Percent change, idx 1 = Average retail price
    multi_contents = {
        "id": ["Drivstoff", "ContentsCode", "Tid"],
        "size": [2, 2, 1],
        "dimension": {
            "Drivstoff": {
                "category": {
                    "index": {"01": 0, "02": 1},
                    "label": {
                        "01": "Unleaded gasoline 95 octane",
                        "02": "Auto diesel (dutiable)",
                    },
                }
            },
            "ContentsCode": {
                "category": {
                    "index": {"Endring": 0, "Pris": 1},
                    "label": {
                        "Endring": "Monthly percent change",
                        "Pris": "Average retail price (NOK/l)",
                    },
                }
            },
            "Tid": {
                "category": {
                    "index": {"2026M10": 0},
                    "label": {"2026M10": "2026M10"},
                }
            },
        },
        # [p95/Endring, p95/Pris, diesel/Endring, diesel/Pris]
        "value": [1.5, 22.10, 0.8, 21.30],
    }

    with create_http_client(
        transport=httpx.MockTransport(
            lambda req: (
                httpx.Response(200, json=multi_contents)
                if str(req.url) == NO_SSB_09654_URL
                else httpx.Response(404)
            )
        )
    ) as client:
        res = fetch_no_ssb_09654(client, sleep_fn=lambda _: None)

    assert res.ok is True
    assert res.quotes[0].prices_by_grade["petrol_95"] == pytest.approx(22.10)
    assert res.quotes[0].prices_by_grade["diesel"] == pytest.approx(21.30)

    # Unexpected multi-valued non-ContentsCode dimension -> ok=False
    bad_dim: dict[str, object] = {
        "id": ["Drivstoff", "Region", "Tid"],
        "size": [2, 2, 1],
        "dimension": {
            "Drivstoff": {
                "category": {
                    "index": {"01": 0, "02": 1},
                    "label": {
                        "01": "Unleaded gasoline 95 octane",
                        "02": "Auto diesel (dutiable)",
                    },
                }
            },
            "Region": {"category": {"index": {"01": 0, "02": 1}, "label": {"01": "A", "02": "B"}}},
            "Tid": {
                "category": {
                    "index": {"2026M10": 0},
                    "label": {"2026M10": "2026M10"},
                }
            },
        },
        "value": [1.5, 22.10, 0.8, 21.30],
    }
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(200, json=bad_dim))
    ) as client:
        bad_res = fetch_no_ssb_09654(client, sleep_fn=lambda _: None)
    assert bad_res.ok is False
    assert bad_res.error is not None and "multi-valued" in bad_res.error
