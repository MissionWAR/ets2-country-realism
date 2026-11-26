"""100% offline httpx.MockTransport + in-memory openpyxl tests for non-EU Tier 1 fuel collectors."""

from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from pathlib import Path

import httpx
import openpyxl
import pytest

from ets2v2.fetch._parsing import validate_ooxml_zip_safety
from ets2v2.fetch.global_tier1 import (
    KR_OPINET_URL,
    MY_OPENDOSM_URL,
    NIST_LITERS_PER_US_GALLON,
    US_EIA_V2_URL,
    fetch_kr_opinet,
    fetch_my_opendosm,
    fetch_us_eia_v2,
    gallon_to_liter,
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
