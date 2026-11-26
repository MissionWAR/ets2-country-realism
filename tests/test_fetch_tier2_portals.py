"""100% offline tests for stdlib fetch/_html.py and guarded Tier 2 national portal scrapers."""

from __future__ import annotations

import io
import json
import zipfile

import httpx
import openpyxl
import pytest

from ets2v2.fetch._html import (
    TableExtractor,
    TextExtractor,
    Tier2EncodingError,
    decode_with_fallbacks,
    extract_html_tables,
    extract_html_text,
)
from ets2v2.fetch.http import create_http_client
from ets2v2.fetch.tier2_portals import (
    AE_MOEI_URL,
    CH_BFS_LIK_URL,
    IL_MOE_URL,
    IS_GASVAKTIN_URL,
    MD_ANRE_URL,
    MK_ERC_URL,
    NG_NBS_URL,
    RU_ROSSTAT_URL,
    SA_ARAMCO_URL,
    TIER2_PORTAL_FEED_NAMES,
    ZA_DMRE_CEF_URL,
    Tier2RateLimitedError,
    Tier2SelectorDriftError,
    fetch_ae_moei,
    fetch_all_tier2_portals,
    fetch_ch_bfs_lik,
    fetch_il_moe,
    fetch_is_gasvaktin,
    fetch_md_anre,
    fetch_mk_erc,
    fetch_ng_nbs,
    fetch_ru_rosstat,
    fetch_sa_aramco,
    fetch_za_dmre_cef,
)


def _no_sleep(_seconds: float) -> None:
    return None


def _mock_client(handler: httpx.MockTransport) -> httpx.Client:
    return create_http_client(transport=handler)


# ---------------------------------------------------------------------------
# Stdlib _html.py tests (D-06)
# ---------------------------------------------------------------------------


def test_extract_html_tables_strips_script_style_and_decodes_entities() -> None:
    html = """
    <html>
      <head>
        <style>table { color: red; } td { padding: 4px; }</style>
        <script>var hidden = "<table><tr><td>fake</td></tr></table>";</script>
      </head>
      <body>
        <table>
          <thead>
            <tr><th>Fuel&nbsp;Grade</th><th>Price &amp; Unit</th></tr>
          </thead>
          <tbody>
            <tr><td>Special&nbsp;&nbsp;95</td><td>2.63<br/>AED/L</td></tr>
            <tr><td>Diesel</td><td>2.74&nbsp;AED</td></tr>
          </tbody>
        </table>
        <table>
          <tr><td>Outer</td><td><table><tr><td>Inner&nbsp;Cell</td></tr></table></td></tr>
        </table>
      </body>
    </html>
    """
    tables = extract_html_tables(html)
    assert len(tables) == 3
    assert tables[0] == [
        ["Fuel Grade", "Price & Unit"],
        ["Special 95", "2.63 AED/L"],
        ["Diesel", "2.74 AED"],
    ]
    assert ["Inner Cell"] in tables[1]
    assert tables[2][0][0] == "Outer"

    # Direct TableExtractor usage matches helper
    parser = TableExtractor()
    parser.feed("<table><tr><td>A</td><td>B</td></tr></table>")
    parser.close()
    assert parser.tables == [[["A", "B"]]]


def test_extract_html_text_ignores_scripts_and_normalizes_blocks() -> None:
    html = """
    <html>
      <body>
        <style>.x { display: none; }</style>
        <script>console.log('ignored');</script>
        <h1>Fuel Prices</h1>
        <p>Benzina COR 95:   24,18&nbsp;lei/L</p>
        <div>Motorina standard: 21,05 lei/L</div>
      </body>
    </html>
    """
    blocks = extract_html_text(html)
    assert blocks == [
        "Fuel Prices",
        "Benzina COR 95: 24,18 lei/L",
        "Motorina standard: 21,05 lei/L",
    ]

    extractor = TextExtractor()
    extractor.feed("<p>Hello&nbsp;World</p>")
    extractor.close()
    assert extractor.blocks == ["Hello World"]


def test_decode_with_fallbacks_utf8_cp1251_and_error() -> None:
    cyrillic_line = "Дизельное топливо: 67,50"
    utf8_bom = b"\xef\xbb\xbf" + cyrillic_line.encode("utf-8")
    assert decode_with_fallbacks(utf8_bom) == cyrillic_line

    cp1251 = cyrillic_line.encode("windows-1251")
    assert decode_with_fallbacks(cp1251) == cyrillic_line

    with pytest.raises(Tier2EncodingError):
        decode_with_fallbacks(cp1251, encodings=("utf-8",))

    with pytest.raises(Tier2EncodingError):
        decode_with_fallbacks(b"\x98\xff", encodings=("utf-8-sig", "windows-1251"))


# ---------------------------------------------------------------------------
# Circuit-breaker taxonomy tests (D-07)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (403, "tier2_rate_limited"),
        (429, "tier2_rate_limited"),
        (503, "tier2_portal_outage"),
        (404, "tier2_portal_outage"),
    ],
)
def test_tier2_circuit_breaker_http_status_mapping(
    status_code: int,
    expected_code: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request, text="blocked or unavailable")

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_ae_moei(client, sleep_fn=_no_sleep)

    assert res.ok is False
    assert res.tier == "tier2"
    assert res.region_scope == "global"
    assert res.error_code == expected_code
    assert res.quotes == []


def test_tier2_circuit_breaker_timeout_encoding_and_selector_drift() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with _mock_client(httpx.MockTransport(timeout_handler)) as client:
        timeout_res = fetch_md_anre(client, sleep_fn=_no_sleep)
    assert timeout_res.ok is False
    assert timeout_res.tier == "tier2"
    assert timeout_res.error_code == "tier2_portal_outage"

    def bad_charset_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=b"\x98\xff\xfeinvalid")

    with _mock_client(httpx.MockTransport(bad_charset_handler)) as client:
        enc_res = fetch_ae_moei(client, sleep_fn=_no_sleep)
    assert enc_res.ok is False
    assert enc_res.tier == "tier2"
    assert enc_res.error_code == "tier2_encoding_error"

    def drift_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            text="<html><body><p>Portal redesigned with no fuel table</p></body></html>",
        )

    with _mock_client(httpx.MockTransport(drift_handler)) as client:
        drift_res = fetch_ae_moei(client, sleep_fn=_no_sleep)
    assert drift_res.ok is False
    assert drift_res.tier == "tier2"
    assert drift_res.error_code == "tier2_selector_drift"

    # Typed exception classes exist and inherit cleanly
    assert issubclass(Tier2RateLimitedError, RuntimeError)
    assert issubclass(Tier2SelectorDriftError, ValueError)


# ---------------------------------------------------------------------------
# Tracer Tier 2 collectors: IS Gasvaktin, MD ANRE, MK ERC, AE MOEI
# ---------------------------------------------------------------------------


def test_fetch_is_gasvaktin_median_and_drift() -> None:
    payload = {
        "timestampPriceChanges": "2026-11-24T08:00:00.000",
        "stations": [
            {"key": "st1", "bensin95": 309.5, "diesel": 318.0},
            {"key": "st2", "bensin95": 312.0, "diesel": 321.5},
            {"key": "st3", "bensin95": 999.0, "diesel": 320.0},  # outlier
            {"key": "st4", "bensin95": None, "diesel": -5.0},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == IS_GASVAKTIN_URL
        return httpx.Response(200, request=request, text=json.dumps(payload))

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_is_gasvaktin(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.tier == "tier2"
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-24"
    assert len(res.quotes) == 1
    q = res.quotes[0]
    assert q.iso2 == "IS"
    assert q.currency == "ISK"
    assert q.source == "is_gasvaktin"
    assert "MIT" in q.license
    assert q.prices_by_grade["petrol_95"] == pytest.approx(312.0)
    assert q.prices_by_grade["diesel"] == pytest.approx(320.0)

    def drift_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text='{"stations": []}')

    with _mock_client(httpx.MockTransport(drift_handler)) as client:
        drift = fetch_is_gasvaktin(client, sleep_fn=_no_sleep)
    assert drift.ok is False
    assert drift.error_code == "tier2_selector_drift"


def test_fetch_md_anre_html_and_drift() -> None:
    html = """
    <html><body>
      <div class="price-box">
        <h3>Prețuri maximale de comercializare cu amănuntul (25.11.2026)</h3>
        <table>
          <tr><td>Benzina COR 95</td><td>24,18 lei/L</td></tr>
          <tr><td>Motorina standard</td><td>21,05 lei/L</td></tr>
        </table>
      </div>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == MD_ANRE_URL
        return httpx.Response(200, request=request, text=html)

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_md_anre(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.tier == "tier2"
    assert res.data_date == "2026-11-25"
    assert len(res.quotes) == 1
    q = res.quotes[0]
    assert q.iso2 == "MD"
    assert q.currency == "MDL"
    assert q.source == "md_anre"
    assert q.prices_by_grade["petrol_95"] == pytest.approx(24.18)
    assert q.prices_by_grade["diesel"] == pytest.approx(21.05)

    def drift_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text="<html><body>Empty page</body></html>")

    with _mock_client(httpx.MockTransport(drift_handler)) as client:
        drift = fetch_md_anre(client, sleep_fn=_no_sleep)
    assert drift.ok is False
    assert drift.error_code == "tier2_selector_drift"


def test_fetch_mk_erc_cyrillic_and_latin_html() -> None:
    html = """
    <html><body>
      <h2>Малопродажни цени на нафтени деривати од 24.11.2026</h2>
      <table>
        <tr><th>Дериват</th><th>Цена (ден/л)</th></tr>
        <tr><td>ЕУРОСУПЕР БС - 95</td><td>82,00</td></tr>
        <tr><td>ЕУРОСУПЕР БС - 98</td><td>84,50</td></tr>
        <tr><td>ЕУРОДИЗЕЛ БС (Д-\u0415 V)</td><td>76,50</td></tr>
      </table>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == MK_ERC_URL
        return httpx.Response(200, request=request, text=html)

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_mk_erc(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.tier == "tier2"
    assert res.data_date == "2026-11-24"
    q = res.quotes[0]
    assert q.iso2 == "MK"
    assert q.currency == "MKD"
    assert q.source == "mk_erc"
    assert q.prices_by_grade["petrol_95"] == pytest.approx(82.00)
    assert q.prices_by_grade["petrol_98"] == pytest.approx(84.50)
    assert q.prices_by_grade["diesel"] == pytest.approx(76.50)


def test_fetch_ae_moei_html_table() -> None:
    html = """
    <html><body>
      <h2>UAE Fuel Prices - November 2026 (effective 2026-11-01)</h2>
      <table>
        <tr><th>Fuel Type</th><th>Price (AED/L)</th></tr>
        <tr><td>Super 98</td><td>2.74</td></tr>
        <tr><td>Special 95</td><td>2.63</td></tr>
        <tr><td>E-Plus 91</td><td>2.55</td></tr>
        <tr><td>Diesel</td><td>2.67</td></tr>
      </table>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == AE_MOEI_URL
        return httpx.Response(200, request=request, text=html)

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_ae_moei(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.tier == "tier2"
    assert res.data_date == "2026-11-01"
    q = res.quotes[0]
    assert q.iso2 == "AE"
    assert q.currency == "AED"
    assert q.source == "ae_moei"
    assert q.prices_by_grade["petrol_98"] == pytest.approx(2.74)
    assert q.prices_by_grade["petrol_95"] == pytest.approx(2.63)
    assert q.prices_by_grade["petrol_92"] == pytest.approx(2.55)
    assert q.prices_by_grade["diesel"] == pytest.approx(2.67)


# ---------------------------------------------------------------------------
# Remaining 6 guarded Tier 2 collectors: CH, RU, IL, ZA, SA, NG
# ---------------------------------------------------------------------------


def _build_xlsx(rows: list[list[object]], *, title: str = "Sheet1") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = title
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_xxe_xlsx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "boom">]><workbook/>',
        )
    return buf.getvalue()


def test_fetch_ch_bfs_lik_json_stat2_and_csv() -> None:
    json_stat2 = {
        "id": ["Treibstoff", "Monat"],
        "size": [3, 2],
        "dimension": {
            "Treibstoff": {
                "category": {
                    "index": {"b95": 0, "b98": 1, "dsl": 2},
                    "label": {"b95": "Bleifrei 95", "b98": "Bleifrei 98", "dsl": "Diesel"},
                }
            },
            "Monat": {
                "category": {
                    "index": {"2026M10": 0, "2026M11": 1},
                    "label": {"2026M10": "2026M10", "2026M11": "2026M11"},
                }
            },
        },
        "value": [1.78, 1.81, 1.89, 1.92, 1.86, 1.89],
    }

    def json_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == CH_BFS_LIK_URL
        return httpx.Response(200, request=request, text=json.dumps(json_stat2))

    with _mock_client(httpx.MockTransport(json_handler)) as client:
        res = fetch_ch_bfs_lik(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.tier == "tier2"
    assert res.data_date == "2026-11-01"
    q = res.quotes[0]
    assert q.iso2 == "CH"
    assert q.currency == "CHF"
    assert q.source == "ch_bfs_lik"
    assert q.prices_by_grade["petrol_95"] == pytest.approx(1.81)
    assert q.prices_by_grade["petrol_98"] == pytest.approx(1.92)
    assert q.prices_by_grade["diesel"] == pytest.approx(1.89)

    csv_url = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/12345/master"
    csv_body = "Monat;Bleifrei 95;Diesel\n2026-10;1.77;1.85\n2026-11;1.82;1.91\n"

    def csv_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == csv_url
        return httpx.Response(200, request=request, text=csv_body)

    with _mock_client(httpx.MockTransport(csv_handler)) as client:
        res_csv = fetch_ch_bfs_lik(client, url=csv_url, sleep_fn=_no_sleep)

    assert res_csv.ok is True
    assert res_csv.data_date == "2026-11-01"
    assert res_csv.quotes[0].prices_by_grade["petrol_95"] == pytest.approx(1.82)
    assert res_csv.quotes[0].prices_by_grade["diesel"] == pytest.approx(1.91)


def test_fetch_ru_rosstat_cp1251_html_xlsx_xxe_guard_and_403() -> None:
    html_text = (
        "<html><body>"
        "<p>Средние потребительские цены на 18.11.2026</p>"
        "<table>"
        "<tr><th>Вид топлива</th><th>Цена, \u0440\u0443\u0431./л</th></tr>"
        "<tr><td>Дизельное топливо</td><td>67,85</td></tr>"
        "<tr><td>Бензин автомобильный марки АИ-92</td><td>54,20</td></tr>"
        "<tr><td>Бензин автомобильный марки АИ-95</td><td>59,60</td></tr>"
        "<tr><td>Бензин автомобильный марки АИ-98</td><td>78,40</td></tr>"
        "</table></body></html>"
    )
    cp1251_bytes = html_text.encode("windows-1251")

    def cp1251_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == RU_ROSSTAT_URL
        return httpx.Response(200, request=request, content=cp1251_bytes)

    with _mock_client(httpx.MockTransport(cp1251_handler)) as client:
        res = fetch_ru_rosstat(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.tier == "tier2"
    assert res.data_date == "2026-11-18"
    q = res.quotes[0]
    assert q.iso2 == "RU"
    assert q.currency == "RUB"
    assert q.source == "ru_rosstat"
    assert q.prices_by_grade["diesel"] == pytest.approx(67.85)
    assert q.prices_by_grade["petrol_92"] == pytest.approx(54.20)
    assert q.prices_by_grade["petrol_95"] == pytest.approx(59.60)
    assert q.prices_by_grade["petrol_98"] == pytest.approx(78.40)

    # XLSX fallback path with valid workbook
    xlsx_url = "https://rosstat.gov.ru/storage/mediabank/fuel_weekly_20261118.xlsx"
    xlsx_bytes = _build_xlsx(
        [
            ["Цены на нефтепродукты на 18.11.2026"],
            ["Вид топлива", "Средняя по РФ (\u0440\u0443\u0431./л)"],
            ["Дизельное топливо", 68.10],
            ["Автомобильный бензин марки АИ-95", 60.05],
        ]
    )

    def xlsx_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == RU_ROSSTAT_URL:
            return httpx.Response(
                200,
                request=request,
                text='<a href="/storage/mediabank/fuel_weekly_20261118.xlsx">XLSX</a>',
            )
        assert str(request.url) == xlsx_url
        return httpx.Response(200, request=request, content=xlsx_bytes)

    with _mock_client(httpx.MockTransport(xlsx_handler)) as client:
        res_xlsx = fetch_ru_rosstat(client, sleep_fn=_no_sleep)

    assert res_xlsx.ok is True
    assert res_xlsx.quotes[0].prices_by_grade["diesel"] == pytest.approx(68.10)
    assert res_xlsx.quotes[0].prices_by_grade["petrol_95"] == pytest.approx(60.05)

    # OOXML XXE attack blocked cleanly via validate_ooxml_zip_safety()
    xxe_bytes = _build_xxe_xlsx()

    def xxe_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == RU_ROSSTAT_URL:
            return httpx.Response(
                200,
                request=request,
                text='<a href="/storage/mediabank/fuel_weekly_20261118.xlsx">XLSX</a>',
            )
        return httpx.Response(200, request=request, content=xxe_bytes)

    with _mock_client(httpx.MockTransport(xxe_handler)) as client:
        res_xxe = fetch_ru_rosstat(client, sleep_fn=_no_sleep)
    assert res_xxe.ok is False
    assert res_xxe.error_code == "tier2_portal_outage"

    # Geo-block HTTP 403 -> tier2_rate_limited
    def geo_403_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request, text="geo blocked")

    with _mock_client(httpx.MockTransport(geo_403_handler)) as client:
        res_403 = fetch_ru_rosstat(client, sleep_fn=_no_sleep)
    assert res_403.ok is False
    assert res_403.error_code == "tier2_rate_limited"


def test_fetch_il_moe_regulated_95_ceiling_anchor() -> None:
    html = """
    <html><body>
      <h1>Maximum Fuel Prices - November 2026</h1>
      <table>
        <tr><th>Fuel Type</th><th>Self-Service Ceiling (NIS/L)</th></tr>
        <tr><td>Unleaded 95 Octane (Self-Service)</td><td>7.45</td></tr>
      </table>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == IL_MOE_URL
        return httpx.Response(200, request=request, text=html)

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_il_moe(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.tier == "tier2"
    assert res.data_date == "2026-11-01"
    q = res.quotes[0]
    assert q.iso2 == "IL"
    assert q.currency == "ILS"
    assert q.source == "il_moe"
    assert q.prices_by_grade == {"petrol_95": pytest.approx(7.45)}


def test_fetch_za_dmre_cef_cents_conversion_html_and_xlsx() -> None:
    html = """
    <html><body>
      <h2>South Africa Monthly Fuel Price Schedule (effective 2026-11-04)</h2>
      <table>
        <tr><th>Grade</th><th>Coast (c/L)</th><th>Inland / Gauteng (c/L)</th></tr>
        <tr><td>Petrol 95 ULP</td><td>2265.0</td><td>2345.0</td></tr>
        <tr><td>Petrol 93 ULP</td><td>2230.0</td><td>2310.0</td></tr>
        <tr><td>Diesel 0.005% (50ppm)</td><td>2025.0</td><td>2105.0</td></tr>
      </table>
    </body></html>
    """

    def html_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ZA_DMRE_CEF_URL
        return httpx.Response(200, request=request, text=html)

    with _mock_client(httpx.MockTransport(html_handler)) as client:
        res = fetch_za_dmre_cef(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.data_date == "2026-11-04"
    q = res.quotes[0]
    assert q.iso2 == "ZA"
    assert q.currency == "ZAR"
    assert q.source == "za_dmre_cef"
    assert q.prices_by_grade["petrol_95"] == pytest.approx(23.45)
    assert q.prices_by_grade["petrol_92"] == pytest.approx(23.10)
    assert q.prices_by_grade["diesel"] == pytest.approx(21.05)

    # XLSX fallback path
    xlsx_url = "https://www.dmre.gov.za/LinkClick/fuel_schedule_202611.xlsx"
    xlsx_bytes = _build_xlsx(
        [
            ["DMRE Fuel Price Schedule", "2026-11-04"],
            ["Product", "Coastal", "Gauteng Inland"],
            ["Petrol 95 ULP", 2250.0, 2330.0],
            ["Diesel 0.005%", 2010.0, 2090.0],
        ]
    )

    def xlsx_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == ZA_DMRE_CEF_URL:
            return httpx.Response(
                200,
                request=request,
                text=f'<a href="{xlsx_url}">Download Fuel Schedule XLSX</a>',
            )
        assert str(request.url) == xlsx_url
        return httpx.Response(200, request=request, content=xlsx_bytes)

    with _mock_client(httpx.MockTransport(xlsx_handler)) as client:
        res_xlsx = fetch_za_dmre_cef(client, sleep_fn=_no_sleep)
    assert res_xlsx.ok is True
    assert res_xlsx.quotes[0].prices_by_grade["petrol_95"] == pytest.approx(23.30)
    assert res_xlsx.quotes[0].prices_by_grade["diesel"] == pytest.approx(20.90)


def test_fetch_sa_aramco_html_and_waf_403() -> None:
    html = """
    <html><body>
      <h2>Retail Fuel Prices - November 2026</h2>
      <table>
        <tr><th>Product</th><th>Price (SAR/Liter)</th></tr>
        <tr><td>Gasoline 91</td><td>2.18</td></tr>
        <tr><td>Gasoline 95</td><td>2.33</td></tr>
        <tr><td>Gasoline 98</td><td>2.88</td></tr>
        <tr><td>Diesel</td><td>1.15</td></tr>
      </table>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == SA_ARAMCO_URL
        return httpx.Response(200, request=request, text=html)

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_sa_aramco(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.data_date == "2026-11-01"
    q = res.quotes[0]
    assert q.iso2 == "SA"
    assert q.currency == "SAR"
    assert q.source == "sa_aramco"
    assert q.prices_by_grade["petrol_92"] == pytest.approx(2.18)
    assert q.prices_by_grade["petrol_95"] == pytest.approx(2.33)
    assert q.prices_by_grade["petrol_98"] == pytest.approx(2.88)
    assert q.prices_by_grade["diesel"] == pytest.approx(1.15)

    def waf_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request, text="Akamai WAF")

    with _mock_client(httpx.MockTransport(waf_handler)) as client:
        res_403 = fetch_sa_aramco(client, sleep_fn=_no_sleep)
    assert res_403.ok is False
    assert res_403.error_code == "tier2_rate_limited"


def test_fetch_ng_nbs_xlsx_discovery_and_national_average() -> None:
    ago_url = "https://nigerianstat.gov.ng/downloads/ago_diesel_watch_nov2026.xlsx"
    pms_url = "https://nigerianstat.gov.ng/downloads/pms_petrol_watch_nov2026.xlsx"
    ago_xlsx = _build_xlsx(
        [
            ["Automotive Gas Oil (Diesel) Price Watch", "2026-11-01"],
            ["State", "Oct-2026", "Nov-2026"],
            ["Lagos", 1390.0, 1410.0],
            ["National Average", 1405.0, 1425.5],
        ]
    )
    pms_xlsx = _build_xlsx(
        [
            ["Premium Motor Spirit (Petrol) Price Watch", "2026-11-01"],
            ["State", "Oct-2026", "Nov-2026"],
            ["Lagos", 1010.0, 1030.0],
            ["National Average", 1020.0, 1045.25],
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == NG_NBS_URL:
            return httpx.Response(
                200,
                request=request,
                text=(
                    '<a href="/downloads/ago_diesel_watch_nov2026.xlsx">AGO Diesel Watch</a>'
                    '<a href="/downloads/pms_petrol_watch_nov2026.xlsx">PMS Petrol Watch</a>'
                ),
            )
        if url == ago_url:
            return httpx.Response(200, request=request, content=ago_xlsx)
        if url == pms_url:
            return httpx.Response(200, request=request, content=pms_xlsx)
        return httpx.Response(404, request=request)

    with _mock_client(httpx.MockTransport(handler)) as client:
        res = fetch_ng_nbs(client, sleep_fn=_no_sleep)

    assert res.ok is True
    assert res.data_date == "2026-11-01"
    q = res.quotes[0]
    assert q.iso2 == "NG"
    assert q.currency == "NGN"
    assert q.source == "ng_nbs"
    assert q.prices_by_grade["diesel"] == pytest.approx(1425.5)
    assert q.prices_by_grade["petrol_95"] == pytest.approx(1045.25)


def test_fetch_all_tier2_portals_exact_10_feeds_and_excludes_tier3_waf_portals() -> None:
    def fail_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request, text="down")

    with _mock_client(httpx.MockTransport(fail_handler)) as client:
        results = fetch_all_tier2_portals(client, sleep_fn=_no_sleep)

    assert len(results) == 10
    feed_names = {r.feed_name for r in results}
    expected_10 = {
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
    assert feed_names == expected_10
    assert frozenset(expected_10) == TIER2_PORTAL_FEED_NAMES
    # KE, ID, JO, EG are cleanly classified as Tier 3 per D-05 (zero scrapers!)
    for excluded in ("ke_epra", "id_pertamina", "jo_memr", "eg_fapc"):
        assert excluded not in feed_names
    assert all(r.tier == "tier2" and r.region_scope == "global" and not r.ok for r in results)


def test_tier2_corrupt_deflate_and_utf16_xxe_isolated_by_circuit_breaker_hi02() -> None:
    """HI-02: Corrupt deflate stream (zlib.error) and UTF-16 XXE never crash Tier 2 guarded run."""
    ago_url = "https://nigerianstat.gov.ng/downloads/ago_diesel_watch_nov2026.xlsx"
    pms_url = "https://nigerianstat.gov.ng/downloads/pms_petrol_watch_nov2026.xlsx"

    # Build corrupt deflate archive
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", b"<workbook>" + b"Z" * 256 + b"</workbook>")
    raw = bytearray(buf.getvalue())
    offset = 30 + int.from_bytes(raw[26:28], "little") + int.from_bytes(raw[28:30], "little")
    raw[offset] = 0x06
    corrupt_zip = bytes(raw)

    def _corrupt_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == NG_NBS_URL:
            return httpx.Response(
                200,
                request=request,
                text=(
                    f'<a href="{ago_url}">AGO Diesel Watch</a>'
                    f'<a href="{pms_url}">PMS Petrol Watch</a>'
                ),
            )
        if url in {ago_url, pms_url}:
            return httpx.Response(200, request=request, content=corrupt_zip)
        return httpx.Response(404, request=request)

    with _mock_client(httpx.MockTransport(_corrupt_handler)) as client:
        res_corrupt = fetch_ng_nbs(client, sleep_fn=_no_sleep)
    assert res_corrupt.ok is False
    assert res_corrupt.error is not None

    # Build UTF-16 XXE workbook
    xxe_buf = io.BytesIO()
    with zipfile.ZipFile(xxe_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE a [<!ENTITY b "c">]><wb/>'.encode(
                "utf-16"
            ),
        )
    utf16_xxe = xxe_buf.getvalue()

    def _xxe_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == NG_NBS_URL:
            return httpx.Response(
                200,
                request=request,
                text=(
                    f'<a href="{ago_url}">AGO Diesel Watch</a>'
                    f'<a href="{pms_url}">PMS Petrol Watch</a>'
                ),
            )
        if url in {ago_url, pms_url}:
            return httpx.Response(200, request=request, content=utf16_xxe)
        return httpx.Response(404, request=request)

    with _mock_client(httpx.MockTransport(_xxe_handler)) as client:
        res_xxe = fetch_ng_nbs(client, sleep_fn=_no_sleep)
    assert res_xxe.ok is False
    assert res_xxe.error is not None
    assert "DOCTYPE" in res_xxe.error or "ENTITY" in res_xxe.error


def test_table_extractor_flushes_unclosed_table_on_close_md07() -> None:
    """MD-07: TableExtractor.close() flushes unclosed <table>/<tr>/<td> frames."""
    unclosed = "<table><tr><td>Diesel</td><td>2.67</td></tr>"
    assert extract_html_tables(unclosed) == [[["Diesel", "2.67"]]]
    nested_unclosed = "<table><tr><td>Outer</td></tr><table><tr><td>Inner</td><td>1.99</td></tr>"
    tables = extract_html_tables(nested_unclosed)
    assert [["Inner", "1.99"]] in tables
    assert [["Outer"]] in tables
