"""100% offline tests for stdlib fetch/_html.py and guarded Tier 2 national portal scrapers."""

from __future__ import annotations

import json

import httpx
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
    IS_GASVAKTIN_URL,
    MD_ANRE_URL,
    MK_ERC_URL,
    Tier2RateLimitedError,
    Tier2SelectorDriftError,
    fetch_ae_moei,
    fetch_is_gasvaktin,
    fetch_md_anre,
    fetch_mk_erc,
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
