"""100% offline httpx.MockTransport + in-memory openpyxl tests for non-EU Tier 1 fuel collectors."""

from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from pathlib import Path

import httpx
import openpyxl
import pytest

from ets2v2.fetch._parsing import extract_iso_date, validate_ooxml_zip_safety
from ets2v2.fetch.global_tier1 import (
    AR_ENERGIA_CKAN_FALLBACK_URL,
    AR_ENERGIA_CKAN_PRIMARY_URL,
    BR_ANP_DIESEL_GNV_URL,
    BR_ANP_GASOLINA_ETANOL_URL,
    CL_CNE_V3_URL,
    CL_CNE_V4_URL,
    CO_CREG_FALLBACK_URL,
    CO_SICOM_CATALOG_URL,
    JP_METI_LANDING_URL,
    KR_OPINET_URL,
    MY_OPENDOSM_URL,
    NIST_LITERS_PER_US_GALLON,
    US_EIA_V2_URL,
    discover_co_sicom_resource_url,
    discover_jp_meti_xlsx_url,
    fetch_all_global_tier1_feeds,
    fetch_ar_energia,
    fetch_br_anp,
    fetch_cl_cne,
    fetch_co_sicom,
    fetch_jp_meti,
    fetch_kr_opinet,
    fetch_my_opendosm,
    fetch_us_eia_v2,
    gallon_to_liter,
    parse_jp_meti_xlsx,
)
from ets2v2.fetch.http import (
    create_http_client,
    fetch_bytes_with_retry,
    redact_url_secrets,
)
from ets2v2.fetch.models import FetchRunReport, RawFuelFeedResult
from ets2v2.fetch.national import fetch_de_tankerkoenig


def _build_minimal_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["A", "B"])
    ws.append([1, 2])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_redact_url_secrets_masks_code_and_existing_params() -> None:
    url = (
        "https://www.opinet.co.kr/api/avgAllPrice.do?out=json&code=OPINET_SUPER_SECRET_999"
        "&api_key=EIA_KEY_123&apikey=TK_KEY_456&token=CNE_TOK_789&KEY=ALT_KEY"
    )
    redacted = redact_url_secrets(url)
    assert "OPINET_SUPER_SECRET_999" not in redacted
    assert "EIA_KEY_123" not in redacted
    assert "TK_KEY_456" not in redacted
    assert "CNE_TOK_789" not in redacted
    assert "ALT_KEY" not in redacted
    assert "code=***" in redacted
    assert "api_key=***" in redacted
    assert "apikey=***" in redacted
    assert "token=***" in redacted
    assert "KEY=***" in redacted
    assert "out=json" in redacted

    # Upper-case CODE= at start of string also masked
    assert redact_url_secrets("CODE=SECRET_XYZ&foo=bar") == "CODE=***&foo=bar"


def test_fetch_bytes_with_retry_accepts_repeated_sequence_query_params() -> None:
    seen_params: list[tuple[str, str]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen_params.extend(request.url.params.multi_items())
        return httpx.Response(200, content=b'{"ok":true}')

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        body = fetch_bytes_with_retry(
            client,
            US_EIA_V2_URL,
            allowed_hosts=frozenset({"api.eia.gov"}),
            params=[
                ("frequency", "weekly"),
                ("facets[product][]", "EPD2D"),
                ("facets[product][]", "EPMR"),
                ("facets[product][]", "EPMP"),
            ],
            sleep_fn=lambda _: None,
        )

    assert body == b'{"ok":true}'
    assert ("facets[product][]", "EPD2D") in seen_params
    assert ("facets[product][]", "EPMR") in seen_params
    assert ("facets[product][]", "EPMP") in seen_params


def test_validate_ooxml_zip_safety_guards_encryption_xxe_and_bombs() -> None:
    # Valid minimal workbook passes cleanly
    validate_ooxml_zip_safety(_build_minimal_xlsx_bytes())

    # XXE DOCTYPE / ENTITY rejection
    xxe_buf = io.BytesIO()
    with zipfile.ZipFile(xxe_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "xl/workbook.xml",
            b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            b"<workbook/>",
        )
    with pytest.raises(ValueError, match=r"DOCTYPE|ENTITY"):
        validate_ooxml_zip_safety(xxe_buf.getvalue())

    # Oversized uncompressed member rejection
    bomb_buf = io.BytesIO()
    with zipfile.ZipFile(bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sheet1.xml", b"A" * 4096)
    with pytest.raises(ValueError, match=r"uncompressed|exceeds"):
        validate_ooxml_zip_safety(bomb_buf.getvalue(), max_uncompressed_bytes=1024)

    # Too many entries rejection
    many_buf = io.BytesIO()
    with zipfile.ZipFile(many_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx in range(5):
            zf.writestr(f"xl/s{idx}.xml", b"<x/>")
    with pytest.raises(ValueError, match=r"entry count|cap"):
        validate_ooxml_zip_safety(many_buf.getvalue(), max_entries=3)

    # Encrypted entry rejection (bit 0 flag set in central directory / local header)
    enc_buf = io.BytesIO()
    with zipfile.ZipFile(enc_buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("xl/workbook.xml", b"<workbook/>")
    raw_enc = bytearray(enc_buf.getvalue())
    # Patch general purpose bit flag in local header (offset 6) and central dir
    raw_enc[6] |= 0x01
    cd_idx = raw_enc.find(b"PK\x01\x02")
    assert cd_idx != -1
    raw_enc[cd_idx + 8] |= 0x01
    with pytest.raises(ValueError, match="Encrypted"):
        validate_ooxml_zip_safety(bytes(raw_enc))


def test_fetch_models_additive_fields_and_tankerkoenig_skip_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = RawFuelFeedResult(
        feed_name="tier2_probe",
        tier="tier2",
        region_scope="global",
        ok=False,
        skipped=False,
        skip_reason=None,
        error_code="tier2_selector_drift",
        error="missing table",
    )
    assert res.tier == "tier2"
    assert res.region_scope == "global"
    assert res.error_code == "tier2_selector_drift"

    report = FetchRunReport(
        ok=True,
        fx_only=False,
        dry_run=True,
        lock_path=Path("state/prices.lock.json"),
        tier1_feeds_succeeded=5,
        tier1_feeds_failed=0,
        eu_tier1_feeds_succeeded=5,
        eu_tier1_feeds_failed=0,
        global_tier1_feeds_succeeded=3,
        global_tier1_feeds_failed=1,
        tier2_feeds_succeeded=0,
        tier2_feeds_failed=0,
        countries_updated=10,
        countries_fallback=2,
        fx_currencies_validated=151,
    )
    assert report.eu_tier1_feeds_succeeded == 5
    assert report.global_tier1_feeds_succeeded == 3
    assert report.global_tier1_feeds_failed == 1
    assert report.tier2_feeds_succeeded == 0

    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(500))
    ) as client:
        tk = fetch_de_tankerkoenig(client)
    assert tk.ok is True
    assert tk.skipped is True
    assert tk.region_scope == "eu_core"
    assert tk.skip_reason == "skipped (TANKERKOENIG_API_KEY unset; using EC WOB)"


def test_nist_gallon_to_liter_exact_conversion() -> None:
    expected = Decimal("3.785411784")
    assert expected == NIST_LITERS_PER_US_GALLON
    assert gallon_to_liter(3.785411784) == pytest.approx(1.0, rel=1e-12)
    assert gallon_to_liter(3.785411784 * 2.0) == pytest.approx(2.0, rel=1e-12)
    with pytest.raises(ValueError, match=r"positive|finite"):
        gallon_to_liter(0.0)
    with pytest.raises(ValueError, match=r"positive|finite"):
        gallon_to_liter(-1.0)


def test_fetch_us_eia_v2_skip_happy_path_and_secret_scrubbing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Key unset -> silent skip
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(500))
    ) as client:
        skipped = fetch_us_eia_v2(client, sleep_fn=lambda _: None)
    assert skipped.ok is True
    assert skipped.skipped is True
    assert skipped.region_scope == "global"
    assert skipped.skip_reason is not None
    assert "EIA_API_KEY" in skipped.skip_reason
    assert skipped.quotes == []

    # 2. Valid EIA v2 response with EPD2D, EPMR, EPMP, plus ignored EPD2O and incomplete newer row
    seen_params: list[tuple[str, str]] = []
    eia_payload = {
        "response": {
            "data": [
                # Incomplete latest period (only EPD2O off-highway + EPMR, missing EPD2D)
                {
                    "period": "2026-11-23",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPD2O",
                    "value": "9.999",
                    "units": "$/GAL",
                },
                {
                    "period": "2026-11-23",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPMR",
                    "value": "3.200",
                    "units": "$/GAL",
                },
                # Complete period 2026-11-16
                {
                    "period": "2026-11-16",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPD2D",
                    "value": "3.785411784",
                    "units": "$/GAL",
                },
                {
                    "period": "2026-11-16",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPD2O",
                    "value": "8.888",
                    "units": "$/GAL",
                },
                {
                    "period": "2026-11-16",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPMR",
                    "value": "3.4068706056",
                    "units": "$/GAL",
                },
                {
                    "period": "2026-11-16",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPMP",
                    "value": "4.1639529624",
                    "units": "$/GAL",
                },
                # Older period should not win
                {
                    "period": "2026-11-09",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPD2D",
                    "value": "4.500",
                    "units": "$/GAL",
                },
                {
                    "period": "2026-11-09",
                    "duoarea": "NUS",
                    "process": "PTE",
                    "product": "EPMR",
                    "value": "3.800",
                    "units": "$/GAL",
                },
            ]
        }
    }

    def _ok_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(US_EIA_V2_URL)
        seen_params.extend(request.url.params.multi_items())
        return httpx.Response(200, json=eia_payload)

    with create_http_client(transport=httpx.MockTransport(_ok_handler)) as client:
        res = fetch_us_eia_v2(client, api_key="EIA_TEST_SECRET_ABC", sleep_fn=lambda _: None)

    assert res.ok is True
    assert res.skipped is False
    assert res.tier == "tier1"
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-16"
    assert len(res.quotes) == 1
    quote = res.quotes[0]
    assert quote.iso2 == "US"
    assert quote.currency == "USD"
    assert quote.unit_basis == "local_per_liter"
    assert quote.source == "us_eia_v2"
    assert quote.prices_by_grade["diesel"] == pytest.approx(1.0, rel=1e-9)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(0.9, rel=1e-9)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(1.1, rel=1e-9)
    assert ("facets[duoarea][]", "NUS") in seen_params
    assert ("facets[process][]", "PTE") in seen_params
    assert ("facets[product][]", "EPD2D") in seen_params
    assert ("facets[product][]", "EPMR") in seen_params
    assert ("facets[product][]", "EPMP") in seen_params

    # 3. HTTP 500 error MUST scrub EIA_API_KEY
    secret = "EIA_ULTRA_SECRET_XYZ123"
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(500, text=f"err {secret}"))
    ) as client:
        failed = fetch_us_eia_v2(client, api_key=secret, sleep_fn=lambda _: None)
    assert failed.ok is False
    assert failed.region_scope == "global"
    assert failed.error is not None
    assert secret not in failed.error
    assert "api_key=***" in failed.error


def test_fetch_my_opendosm_filters_change_weekly_and_falls_back_eastmsia() -> None:
    payload = [
        # Newer delta row MUST be rejected client-side even if upstream returns it
        {
            "date": "2026-11-26",
            "series_type": "change_weekly",
            "ron95": 0.03,
            "ron97": -0.02,
            "diesel": 0.05,
        },
        # Valid level row
        {
            "date": "2026-11-19",
            "series_type": "level",
            "ron95": 2.05,
            "ron97": 3.19,
            "diesel": 2.95,
            "diesel_eastmsia": 2.15,
            "ron95_budi95": None,
        },
    ]

    def _handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(MY_OPENDOSM_URL)
        assert request.url.params.get("id") == "fuelprice"
        assert request.url.params.get("filter") == "level@series_type"
        return httpx.Response(200, json=payload)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        res = fetch_my_opendosm(client, sleep_fn=lambda _: None)

    assert res.ok is True
    assert res.tier == "tier1"
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-19"
    assert len(res.quotes) == 1
    quote = res.quotes[0]
    assert quote.iso2 == "MY"
    assert quote.currency == "MYR"
    assert quote.unit_basis == "local_per_liter"
    assert quote.license == "CC BY 4.0 (OpenDOSM / MOF Malaysia)"
    assert quote.prices_by_grade["diesel"] == pytest.approx(2.95)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(2.05)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(3.19)

    # Null diesel falls back to diesel_eastmsia cleanly
    fallback_payload = [
        {
            "date": "2026-11-19",
            "series_type": "level",
            "ron95": 2.05,
            "ron97": None,
            "diesel": None,
            "diesel_eastmsia": 2.15,
        }
    ]
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(200, json=fallback_payload))
    ) as client:
        res_fb = fetch_my_opendosm(client, sleep_fn=lambda _: None)
    assert res_fb.ok is True
    assert res_fb.quotes[0].prices_by_grade["diesel"] == pytest.approx(2.15)
    assert "petrol_98" not in res_fb.quotes[0].prices_by_grade


def test_fetch_kr_opinet_skip_mapping_ignores_c004_and_scrubs_code_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Key unset -> silent skip
    monkeypatch.delenv("OPINET_API_KEY", raising=False)
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(500))
    ) as client:
        skipped = fetch_kr_opinet(client, sleep_fn=lambda _: None)
    assert skipped.ok is True
    assert skipped.skipped is True
    assert skipped.region_scope == "global"
    assert skipped.skip_reason is not None
    assert "OPINET_API_KEY" in skipped.skip_reason
    assert skipped.quotes == []

    # 2. Happy path mapping D047, B027, B034, K015 while ignoring C004 (kerosene)
    opinet_payload = {
        "RESULT": {
            "OIL": [
                {
                    "TRADE_DT": "20261120",
                    "PRODCD": "B034",
                    "PRODNM": "고급휘발유",
                    "PRICE": "1912.50",
                },
                {
                    "TRADE_DT": "20261120",
                    "PRODCD": "B027",
                    "PRODNM": "휘발유",
                    "PRICE": "1654.20",
                },
                {
                    "TRADE_DT": "20261120",
                    "PRODCD": "D047",
                    "PRODNM": "자동차용경유",
                    "PRICE": "1518.80",
                },
                {
                    "TRADE_DT": "20261120",
                    "PRODCD": "C004",
                    "PRODNM": "실내등유",
                    "PRICE": "1340.00",
                },
                {
                    "TRADE_DT": "20261120",
                    "PRODCD": "K015",
                    "PRODNM": "자동차용부탄",
                    "PRICE": "1012.40",
                },
            ]
        }
    }

    def _ok_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(KR_OPINET_URL)
        assert request.url.params.get("out") == "json"
        assert request.url.params.get("code") == "OPINET_VALID_KEY"
        return httpx.Response(200, json=opinet_payload)

    with create_http_client(transport=httpx.MockTransport(_ok_handler)) as client:
        res = fetch_kr_opinet(client, api_key="OPINET_VALID_KEY", sleep_fn=lambda _: None)

    assert res.ok is True
    assert res.skipped is False
    assert res.tier == "tier1"
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-20"
    assert len(res.quotes) == 1
    quote = res.quotes[0]
    assert quote.iso2 == "KR"
    assert quote.currency == "KRW"
    assert quote.unit_basis == "local_per_liter"
    assert quote.prices_by_grade == {
        "diesel": pytest.approx(1518.80),
        "petrol_95": pytest.approx(1654.20),
        "petrol_98": pytest.approx(1912.50),
        "lpg": pytest.approx(1012.40),
    }

    # 3. HTTP 500 error & transport timeout MUST NEVER leak OPINET_API_KEY
    secret = "OPINET_TOP_SECRET_7777"
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(500, text="server fail"))
    ) as client:
        failed_500 = fetch_kr_opinet(client, api_key=secret, sleep_fn=lambda _: None)
    assert failed_500.ok is False
    assert failed_500.error is not None
    assert secret not in failed_500.error
    assert "code=***" in failed_500.error

    def _timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"Timed out requesting {request.url}")

    with create_http_client(transport=httpx.MockTransport(_timeout_handler)) as client:
        failed_to = fetch_kr_opinet(client, api_key=secret, sleep_fn=lambda _: None)
    assert failed_to.ok is False
    assert failed_to.error is not None
    assert secret not in failed_to.error


def _build_jp_meti_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "全国平均価格"
    ws.append(["石油製品価格調査 (給油所小売価格調査)"])
    ws.append(["調査日", "2026年11月16日"])
    ws.append(["都道府県", "ガソリン (円/L)", "", "軽油 (円/L)", "灯油 (円/18L)"])
    ws.append(["", "レギュラー", "ハイオク", "軽油", "灯油 (店頭)"])
    ws.append(["全国平均", 174.8, 185.6, 154.2, 2110.0])
    ws.append(["北海道", 173.1, 184.0, 152.9, 2090.0])
    ws.append(["東京都", 176.2, 187.1, 155.5, 2180.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_fetch_br_anp_latin1_median_outliers_and_excludes_glp_gnv() -> None:
    # Latin-1 encoded semicolon CSVs with comma decimals, outliers, old week rows, and GLP/GNV
    diesel_csv = (
        "Região - Sigla;Estado - Sigla;Produto;Data da Coleta;Valor de Venda;Unidade de Medida\n"
        "SE;SP;DIESEL S10;18/11/2026;6,15;R$ / litro\n"
        "SE;RJ;DIESEL S10;19/11/2026;6,25;R$ / litro\n"
        "S;PR;DIESEL S10;19/11/2026;999,99;R$ / litro\n"  # typo outlier rejected by median
        "N;AM;DIESEL S10;19/11/2026;0,01;R$ / litro\n"  # typo outlier rejected by median
        "SE;MG;DIESEL S10;20/11/2026;6,20;R$ / litro\n"
        "SE;SP;DIESEL S10;01/11/2026;4,50;R$ / litro\n"  # >7 days older than max date -> excluded
        "SE;SP;DIESEL;19/11/2026;5,95;R$ / litro\n"  # S10 preferred over generic DIESEL
        "SE;SP;GNV;19/11/2026;4,80;R$ / m³\n"  # must be ignored
        "SE;SP;GLP;19/11/2026;105,00;R$ / 13 kg\n"  # must be ignored
    ).encode("latin-1")

    gasolina_csv = (
        "Região - Sigla;Estado - Sigla;Produto;Data da Coleta;Valor de Venda;Unidade de Medida\n"
        "SE;SP;GASOLINA COMUM;18/11/2026;6,05;R$ / litro\n"
        "SE;RJ;GASOLINA COMUM;19/11/2026;6,15;R$ / litro\n"
        "SE;MG;GASOLINA COMUM;20/11/2026;999,99;R$ / litro\n"
        "SE;SP;GASOLINA ADITIVADA;19/11/2026;6,35;R$ / litro\n"
        "SE;RJ;GASOLINA ADITIVADA;20/11/2026;6,45;R$ / litro\n"
        "SE;SP;ETANOL;19/11/2026;4,10;R$ / litro\n"
        "SE;RJ;ETANOL;20/11/2026;4,20;R$ / litro\n"
    ).encode("latin-1")

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == BR_ANP_DIESEL_GNV_URL:
            return httpx.Response(200, content=diesel_csv)
        if url == BR_ANP_GASOLINA_ETANOL_URL:
            return httpx.Response(200, content=gasolina_csv)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        res = fetch_br_anp(client, sleep_fn=lambda _: None)

    assert res.ok is True
    assert res.tier == "tier1"
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-20"
    assert len(res.quotes) == 1
    quote = res.quotes[0]
    assert quote.iso2 == "BR"
    assert quote.currency == "BRL"
    assert quote.unit_basis == "local_per_liter"
    assert quote.prices_by_grade["diesel"] == pytest.approx(6.20)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(6.15)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(6.40)
    assert quote.prices_by_grade["e85"] == pytest.approx(4.15)
    assert "lpg" not in quote.prices_by_grade


def test_fetch_ar_energia_rejects_historico_filters_stale_stations_and_ignores_gnc() -> None:
    vigente_url = "https://datos.energia.gob.ar/dataset/abc/precios-en-surtidor-vigentes.csv"
    historico_url = "https://datos.energia.gob.ar/dataset/abc/precios-en-surtidor-historico.csv"
    ckan_payload = {
        "success": True,
        "result": {
            "resources": [
                {
                    "name": "Precios en surtidor historico (Res. 314)",
                    "format": "CSV",
                    "url": historico_url,
                },
                {
                    "name": "Precios vigentes en surtidor (Res. 314)",
                    "format": "CSV",
                    "url": vigente_url,
                },
            ]
        },
    }
    csv_text = (
        "producto,precio,tipohorario,fecha_vigencia\n"
        # Stale 2019 dead stations must be filtered out (>60d older than max date)
        "Gas Oil Grado 2,42.50,Diurno,2019-06-15 10:00:00\n"
        "Nafta (súper),45.00,Diurno,2019-06-15 10:00:00\n"
        # Recent valid Diurno rows + outlier
        "Gas Oil Grado 2,1180.0,Diurno,2026-11-18 08:00:00\n"
        "Gas Oil Grado 2,1200.0,Diurno,2026-11-19 08:00:00\n"
        "Gas Oil Grado 2,99999.0,Diurno,2026-11-19 09:00:00\n"
        "Gas Oil Grado 2,1350.0,Nocturno,2026-11-19 23:00:00\n"
        "Gas Oil Grado 3,1420.0,Diurno,2026-11-19 08:00:00\n"
        "Nafta (súper),1120.0,Diurno,2026-11-18 08:00:00\n"
        "Nafta (super),1140.0,Diurno,2026-11-19 08:00:00\n"
        "Nafta (super),1160.0,Diurno,2026-11-19 10:00:00\n"
        "Nafta (premium),1380.0,Diurno,2026-11-19 08:00:00\n"
        "GNC,540.0,Diurno,2026-11-19 08:00:00\n"  # must be ignored
    )

    seen_urls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        seen_urls.append(url)
        if url == AR_ENERGIA_CKAN_PRIMARY_URL:
            return httpx.Response(503)  # Exercise fallback to datos.energia.gob.ar
        if url == AR_ENERGIA_CKAN_FALLBACK_URL:
            return httpx.Response(200, json=ckan_payload)
        if url == vigente_url:
            return httpx.Response(200, text=csv_text)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        res = fetch_ar_energia(client, sleep_fn=lambda _: None)

    assert historico_url not in seen_urls
    assert res.ok is True
    assert res.tier == "tier1"
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-19"
    quote = res.quotes[0]
    assert quote.iso2 == "AR"
    assert quote.currency == "ARS"
    assert quote.prices_by_grade["diesel"] == pytest.approx(1200.0)
    assert quote.prices_by_grade["diesel_plus"] == pytest.approx(1420.0)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(1140.0)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(1380.0)
    assert "lpg" not in quote.prices_by_grade


def test_fetch_co_sicom_primary_soda_creg_fallback_and_ssrf_guard() -> None:
    # 1. Primary Socrata discovery skipping dispatch-volume fbht-2fzd
    catalog_payload = {
        "results": [
            {
                "resource": {
                    "id": "fbht-2fzd",
                    "name": "Volumen combustible despachado SICOM",
                },
                "permalink": "https://www.datos.gov.co/d/fbht-2fzd",
            },
            {
                "resource": {
                    "id": "ab12-cd34",
                    "name": "Precio mes combustible retail SICOM",
                },
                "permalink": "https://www.datos.gov.co/d/ab12-cd34",
            },
        ]
    }
    soda_rows = [
        {"producto": "BIODIESEL", "precio": "9540", "fecha": "2026-11-15"},
        {"producto": "ACPM", "precio": "9500", "fecha": "2026-11-15"},
        {"producto": "ACPM", "precio": "9580", "fecha": "2026-11-15"},
        {"producto": "GASOLINA CORRIENTE", "precio": "15588", "fecha": "2026-11-15"},
        {"producto": "GASOLINA MOTOR CORRIENTE", "precio": "15600", "fecha": "2026-11-15"},
        {"producto": "GASOLINA EXTRA", "precio": "21200", "fecha": "2026-11-15"},
    ]

    def _primary_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == CO_SICOM_CATALOG_URL:
            return httpx.Response(200, json=catalog_payload)
        if url.startswith("https://www.datos.gov.co/resource/ab12-cd34.json"):
            return httpx.Response(200, json=soda_rows)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_primary_handler)) as client:
        res = fetch_co_sicom(client, sleep_fn=lambda _: None)

    assert res.ok is True
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-15"
    quote = res.quotes[0]
    assert quote.iso2 == "CO"
    assert quote.currency == "COP"
    assert quote.source == "co_sicom"
    assert quote.prices_by_grade["diesel"] == pytest.approx(gallon_to_liter(9540.0), rel=1e-9)
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(gallon_to_liter(15594.0), rel=1e-9)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(gallon_to_liter(21200.0), rel=1e-9)

    # 2. Fallback to CREG HTML with Colombian dot-thousands (15.588 and 9.540 COP/gal)
    creg_html = (
        "<html><body><p>Actualizado: 2026-11-16</p>"
        "<table>"
        "<tr><th>Ciudad</th><th>Gasolina MC ($/gal)</th><th>ACPM ($/gal)</th></tr>"
        "<tr><td>Bogotá</td><td>15.800</td><td>9.700</td></tr>"
        "<tr><td>Medellín</td><td>15.700</td><td>9.650</td></tr>"
        "<tr><td>Promedio PVP precio</td><td>15.588</td><td>9.540</td></tr>"
        "</table></body></html>"
    )

    def _creg_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == CO_SICOM_CATALOG_URL:
            return httpx.Response(503)
        if url == CO_CREG_FALLBACK_URL:
            return httpx.Response(200, text=creg_html)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_creg_handler)) as client:
        res_creg = fetch_co_sicom(client, sleep_fn=lambda _: None)

    assert res_creg.ok is True
    assert res_creg.data_date == "2026-11-16"
    q_creg = res_creg.quotes[0]
    assert q_creg.source == "co_creg"
    assert q_creg.prices_by_grade["petrol_95"] == pytest.approx(gallon_to_liter(15588.0), rel=1e-9)
    assert q_creg.prices_by_grade["diesel"] == pytest.approx(gallon_to_liter(9540.0), rel=1e-9)

    # 3. SSRF rejection of off-host catalog link
    evil_catalog: dict[object, object] = {
        "results": [
            {
                "resource": {"id": "ab12-cd34", "name": "Precio mes combustible"},
                "permalink": "https://evil.example/d/ab12-cd34",
            }
        ]
    }
    with pytest.raises(ValueError, match=r"allowlist|host"):
        discover_co_sicom_resource_url(evil_catalog)


def test_fetch_cl_cne_skip_v4_v3_median_and_secret_scrubbing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Token unset -> silent skip
    monkeypatch.delenv("CNE_API_TOKEN", raising=False)
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(500))
    ) as client:
        skipped = fetch_cl_cne(client, sleep_fn=lambda _: None)
    assert skipped.ok is True
    assert skipped.skipped is True
    assert skipped.region_scope == "global"
    assert skipped.skip_reason is not None
    assert "CNE_API_TOKEN" in skipped.skip_reason

    # 2. v4 Bearer schema happy path
    v4_payload = [
        {
            "fecha_hora_actualizacion": "2026-11-18 12:00:00",
            "precios": {
                "diesel": 1020,
                "93": 1240,
                "95": 1280,
                "97": 1340,
                "glp": 610,
            },
        },
        {
            "fecha_hora_actualizacion": "2026-11-19 15:30:00",
            "precios": {
                "diesel": 1040,
                "93": 1260,
                "95": 1300,
                "97": 1360,
                "glp": 630,
            },
        },
        {
            "fecha_hora_actualizacion": "2026-11-19 16:00:00",
            "precios": {
                "diesel": 99999,  # typo outlier rejected by median
                "93": 1250,
                "95": 1290,
                "97": 1350,
            },
        },
    ]

    def _v4_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == CL_CNE_V4_URL:
            assert request.headers.get("authorization") == "Bearer CNE_SECRET_V4"
            return httpx.Response(200, json=v4_payload)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_v4_handler)) as client:
        res_v4 = fetch_cl_cne(client, api_token="CNE_SECRET_V4", sleep_fn=lambda _: None)

    assert res_v4.ok is True
    assert res_v4.data_date == "2026-11-19"
    q_v4 = res_v4.quotes[0]
    assert q_v4.iso2 == "CL"
    assert q_v4.currency == "CLP"
    assert q_v4.prices_by_grade["diesel"] == pytest.approx(1040.0)
    assert q_v4.prices_by_grade["petrol_92"] == pytest.approx(1250.0)
    assert q_v4.prices_by_grade["petrol_95"] == pytest.approx(1290.0)
    assert q_v4.prices_by_grade["petrol_98"] == pytest.approx(1350.0)
    assert q_v4.prices_by_grade["lpg"] == pytest.approx(620.0)

    # 3. v3 fallback schema when v4 returns 404
    v3_payload = {
        "estado": "OK",
        "data": [
            {
                "fecha_hora_actualizacion": "2026-11-19 10:00:00",
                "combustibles": [
                    {"id": "diesel", "precio": 1035},
                    {"id": "95", "precio": 1289},
                    {"id": "97", "precio": 1349},
                    {"id": "93", "precio": 1249},
                    {"id": "glp", "precio": 615},
                ],
            }
        ],
    }

    def _v3_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == CL_CNE_V4_URL:
            return httpx.Response(404)
        if url.startswith(CL_CNE_V3_URL):
            assert request.url.params.get("token") == "CNE_SECRET_V3"
            return httpx.Response(200, json=v3_payload)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_v3_handler)) as client:
        res_v3 = fetch_cl_cne(client, api_token="CNE_SECRET_V3", sleep_fn=lambda _: None)

    assert res_v3.ok is True
    assert res_v3.quotes[0].prices_by_grade["diesel"] == pytest.approx(1035.0)
    assert res_v3.quotes[0].prices_by_grade["petrol_95"] == pytest.approx(1289.0)

    # 4. Error scrubbing when both v4 and v3 fail
    secret = "CNE_TOP_SECRET_555"
    with create_http_client(
        transport=httpx.MockTransport(lambda _req: httpx.Response(500, text=f"bad {secret}"))
    ) as client:
        failed = fetch_cl_cne(client, api_token=secret, sleep_fn=lambda _: None)
    assert failed.ok is False
    assert failed.error is not None
    assert secret not in failed.error


def test_fetch_jp_meti_rejects_xls_ignores_kerosene_and_blocks_xxe() -> None:
    xlsx_bytes = _build_jp_meti_xlsx_bytes()

    # Discovery selects .xlsx and rejects .xls
    html = (
        "<html><body>"
        '<a href="/statistics/petroleum_and_lpgas/pl007/results_legacy.xls">旧形式 (.xls)</a>'
        '<a href="/statistics/petroleum_and_lpgas/pl007/results_20261116.xlsx">'
        "最新調査結果 (.xlsx)</a>"
        "</body></html>"
    )
    resolved = discover_jp_meti_xlsx_url(html, JP_METI_LANDING_URL)
    assert resolved == (
        "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results_20261116.xlsx"
    )

    # Only .xls link -> must fail cleanly
    with pytest.raises(ValueError, match=r"\.xlsx"):
        discover_jp_meti_xlsx_url(
            '<a href="/statistics/petroleum_and_lpgas/pl007/old.xls">Legacy</a>',
            JP_METI_LANDING_URL,
        )

    # Off-host .xlsx link -> SSRF rejection
    with pytest.raises(ValueError, match="allowlist"):
        discover_jp_meti_xlsx_url(
            '<a href="https://evil.example/meti.xlsx">Latest</a>',
            JP_METI_LANDING_URL,
        )

    # Direct workbook parse verifies national average & kerosene exclusion
    quote, data_date = parse_jp_meti_xlsx(xlsx_bytes)
    assert data_date == "2026-11-16"
    assert quote.iso2 == "JP"
    assert quote.currency == "JPY"
    assert quote.prices_by_grade == {
        "petrol_95": pytest.approx(174.8),
        "petrol_98": pytest.approx(185.6),
        "diesel": pytest.approx(154.2),
    }

    # End-to-end mocked HTTP fetch
    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == JP_METI_LANDING_URL:
            return httpx.Response(200, text=html)
        if url == resolved:
            return httpx.Response(200, content=xlsx_bytes)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        res = fetch_jp_meti(client, sleep_fn=lambda _: None)

    assert res.ok is True
    assert res.tier == "tier1"
    assert res.region_scope == "global"
    assert res.data_date == "2026-11-16"
    assert res.quotes[0].prices_by_grade["diesel"] == pytest.approx(154.2)

    # OOXML XXE payload inside METI .xlsx MUST be rejected
    xxe_buf = io.BytesIO()
    with zipfile.ZipFile(xxe_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", b"<!DOCTYPE x [<!ENTITY a 'b'>]><workbook/>")
    with pytest.raises(ValueError, match=r"DOCTYPE|ENTITY"):
        parse_jp_meti_xlsx(xxe_buf.getvalue())


def test_fetch_all_global_tier1_feeds_returns_8_isolated_results_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("OPINET_API_KEY", raising=False)
    monkeypatch.delenv("CNE_API_TOKEN", raising=False)

    # Only MY OpenDOSM succeeds; all other keyless feeds return 500 -> must NOT abort
    my_payload = [
        {
            "date": "2026-11-19",
            "series_type": "level",
            "ron95": 2.05,
            "ron97": 3.19,
            "diesel": 2.95,
        }
    ]

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(MY_OPENDOSM_URL):
            return httpx.Response(200, json=my_payload)
        return httpx.Response(500)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        results = fetch_all_global_tier1_feeds(client, sleep_fn=lambda _: None)

    assert [r.feed_name for r in results] == [
        "us_eia_v2",
        "br_anp",
        "ar_energia",
        "co_sicom",
        "cl_cne",
        "my_opendosm",
        "jp_meti",
        "kr_opinet",
    ]
    assert all(r.tier == "tier1" and r.region_scope == "global" for r in results)
    by_name = {r.feed_name: r for r in results}
    assert by_name["us_eia_v2"].skipped is True
    assert by_name["cl_cne"].skipped is True
    assert by_name["kr_opinet"].skipped is True
    assert by_name["my_opendosm"].ok is True
    assert by_name["br_anp"].ok is False
    assert by_name["ar_energia"].ok is False
    assert by_name["co_sicom"].ok is False
    assert by_name["jp_meti"].ok is False


def _build_corrupt_deflate_xlsx() -> bytes:
    """Create a valid ZIP header whose compressed member bytes trigger zlib.error on inflate."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", b"<workbook>" + b"A" * 256 + b"</workbook>")
    raw = bytearray(buf.getvalue())
    # Local file header ends at 30 + filename_len + extra_len
    name_len = int.from_bytes(raw[26:28], "little")
    extra_len = int.from_bytes(raw[28:30], "little")
    data_offset = 30 + name_len + extra_len
    # 0x06 sets deflate BTYPE=11 (reserved/invalid), reliably raising zlib.error
    raw[data_offset] = 0x06
    return bytes(raw)


def test_ooxml_safety_catches_corrupt_deflate_and_utf16_doctype_hi02() -> None:
    """HI-02: Corrupt deflate streams raise ValueError (not zlib.error) & UTF-16 XXE is blocked."""
    corrupt_zip = _build_corrupt_deflate_xlsx()
    with pytest.raises(ValueError, match="OOXML"):
        validate_ooxml_zip_safety(corrupt_zip)

    # Also isolated cleanly inside fetch_jp_meti without crashing pipeline
    xlsx_url = (
        "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/corrupt_20261116.xlsx"
    )

    def _jp_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == JP_METI_LANDING_URL:
            return httpx.Response(200, text=f'<a href="{xlsx_url}">Weekly .xlsx</a>')
        if str(request.url) == xlsx_url:
            return httpx.Response(200, content=corrupt_zip)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_jp_handler)) as client:
        jp_res = fetch_jp_meti(client, sleep_fn=lambda _: None)
    assert jp_res.ok is False
    assert jp_res.error is not None

    # UTF-16LE and UTF-16BE DOCTYPE/ENTITY payloads (both .xml and extensionless XML member)
    xml_payload = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE foo [<!ENTITY x "a">]><wb/>'
    for encoding, member_name in (
        ("utf-16", "xl/workbook.xml"),
        ("utf-16-le", "xl/workbook.xml"),
        ("utf-16-be", "xl/workbook.xml"),
        ("utf-16", "xl/custom_part"),
    ):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(member_name, xml_payload.encode(encoding))
        with pytest.raises(ValueError, match=r"DOCTYPE|ENTITY"):
            validate_ooxml_zip_safety(buf.getvalue())


def test_extract_iso_date_handles_t_separated_iso8601_timestamps_hi04() -> None:
    """HI-04: ISO-8601 T-separated timestamps extract real dates across CO, AR, and CL."""
    assert extract_iso_date("2026-11-20T00:00:00.000") == "2026-11-20"
    assert extract_iso_date("2026-11-20T15:00:00Z") == "2026-11-20"
    assert extract_iso_date("2026-11-20T15:00:00-05:00") == "2026-11-20"
    # Embedded digits must NOT falsely match
    assert extract_iso_date("92026-11-201") is None

    # 1. CO SICOM Socrata SODA floating timestamp format ("YYYY-MM-DDT00:00:00.000")
    def _co_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == CO_SICOM_CATALOG_URL:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "resource": {
                                "id": "ab12-cd34",
                                "name": "Precios de combustibles SICOM",
                            },
                            "permalink": "https://www.datos.gov.co/d/ab12-cd34",
                        }
                    ]
                },
            )
        if url.startswith("https://www.datos.gov.co/resource/ab12-cd34.json"):
            return httpx.Response(
                200,
                json=[
                    {
                        "producto": "GASOLINA MOTOR CORRIENTE",
                        "precio": "15900",
                        "fecha_precio": "2026-11-18T00:00:00.000",
                    },
                    {
                        "producto": "BIODIESEL EXTRA",
                        "precio": "10400",
                        "fecha_precio": "2026-11-18T00:00:00.000",
                    },
                ],
            )
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_co_handler)) as client:
        co_res = fetch_co_sicom(client, sleep_fn=lambda _: None)
    assert co_res.ok is True
    assert co_res.data_date == "2026-11-18"

    # 2. AR Energia CSV with T-separated ISO-8601 fecha_vigencia
    ar_csv_url = "https://datos.energia.gob.ar/dataset/precios-en-surtidor/precios_2026.csv"
    ar_csv = (
        "producto,precio,fecha_vigencia\n"
        "Nafta (súper) entre 92 y 95 Ron,1150.0,2026-11-17T08:00:00Z\n"
        "Gas Oil Grado 2,1180.0,2026-11-17T08:00:00Z\n"
    )

    def _ar_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == AR_ENERGIA_CKAN_PRIMARY_URL:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "resources": [
                            {"format": "CSV", "name": "Precios vigentes", "url": ar_csv_url}
                        ]
                    },
                },
            )
        if url == ar_csv_url:
            return httpx.Response(200, content=ar_csv.encode("utf-8"))
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_ar_handler)) as client:
        ar_res = fetch_ar_energia(client, sleep_fn=lambda _: None)
    assert ar_res.ok is True
    assert ar_res.data_date == "2026-11-17"

    # 3. CL CNE v4 JSON with T-separated ISO-8601 fecha_hora_actualizacion
    def _cl_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == CL_CNE_V4_URL:
            return httpx.Response(
                200,
                json=[
                    {
                        "fecha_hora_actualizacion": "2026-11-16T14:30:00Z",
                        "precios": {
                            "95": {"precio": 1280.0},
                            "DI": {"precio": 1020.0},
                        },
                    }
                ],
            )
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_cl_handler)) as client:
        cl_res = fetch_cl_cne(client, api_token="dummy-token", sleep_fn=lambda _: None)
    assert cl_res.ok is True
    assert cl_res.data_date == "2026-11-16"


def test_co_creg_ignores_script_dates_and_handles_nested_tables_md07() -> None:
    """MD-07: CO CREG uses shared _html.py (ignores <script> dates, handles nested tables)."""
    creg_html = (
        "<html><head><script>var oldDate = '1999-01-01';</script></head><body>"
        "<p>Actualizado: 2026-11-19</p>"
        "<table><tr><td>Wrapper</td><td><table><tr><td>Nested</td></tr></table></td></tr></table>"
        "<table><tr><th>Ciudad</th><th>Gasolina MC</th><th>ACPM</th></tr>"
        "<tr><td>Promedio Nacional</td><td>15.600</td><td>9.550</td></tr>"
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == CO_SICOM_CATALOG_URL:
            return httpx.Response(503)
        if str(request.url) == CO_CREG_FALLBACK_URL:
            return httpx.Response(200, text=creg_html)
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_handler)) as client:
        res = fetch_co_sicom(client, sleep_fn=lambda _: None)
    assert res.ok is True
    assert res.data_date == "2026-11-19"
    assert res.quotes[0].source == "co_creg"
    assert res.quotes[0].prices_by_grade["diesel"] == pytest.approx(gallon_to_liter(9550.0))


def test_jp_meti_locks_headers_prefers_layout_a_date_and_parses_reiwa_md08_in03() -> None:
    """MD-08 & IN-03: JP METI locks grade headers, prefers Layout A date, and parses Reiwa era."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "全国平均価格"
    ws.append(["調査日", "令和8年11月16日"])
    ws.append(["都道府県", "レギュラー", "ハイオク", "軽油"])
    # Earlier dated row (older date) before 全国平均 must NOT override Layout A date
    ws.append(["2026-11-09", 170.0, 180.0, 150.0])
    # Footnote/annotation row mentioning 軽油 in col 0 must NOT corrupt locked grade_cols!
    ws.append(["※軽油は税込価格", "", "", ""])
    ws.append(["全国平均", 175.2, 186.0, 154.9])
    buf = io.BytesIO()
    wb.save(buf)

    quote, data_date = parse_jp_meti_xlsx(buf.getvalue())
    assert data_date == "2026-11-16"
    assert quote.prices_by_grade["petrol_95"] == pytest.approx(175.2)
    assert quote.prices_by_grade["petrol_98"] == pytest.approx(186.0)
    assert quote.prices_by_grade["diesel"] == pytest.approx(154.9)

    # Also verify Reiwa 元年 (year 1 -> 2019) via parse_jp_meti_xlsx and NUL CSV via fetch_br_anp
    wb2 = openpyxl.Workbook()
    ws2 = wb2.active
    assert ws2 is not None
    ws2.append(["調査日", "令和元年5月1日"])
    ws2.append(["都道府県", "レギュラー", "軽油"])
    ws2.append(["全国平均", 150.0, 130.0])
    buf2 = io.BytesIO()
    wb2.save(buf2)
    _, reiwa1_date = parse_jp_meti_xlsx(buf2.getvalue())
    assert reiwa1_date == "2019-05-01"

    def _nul_csv_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"a;b\x00c\n")

    with create_http_client(transport=httpx.MockTransport(_nul_csv_handler)) as client:
        br_nul = fetch_br_anp(client, sleep_fn=lambda _: None)
    assert br_nul.ok is False
    assert br_nul.error is not None
    assert "NUL" in br_nul.error
