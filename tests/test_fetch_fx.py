"""100% offline MockTransport tests for ets2_realism.fetch.{http,fx} and CLI tracer."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ets2_realism.cli import main
from ets2_realism.fetch import (
    CBR_DAILY_XML_URL,
    ECB_DAILY_XML_URL,
    FAWAZ_CLOUDFLARE_URL,
    FAWAZ_JSDELIVR_URL,
    FRANKFURTER_V2_URL,
    HttpFetchError,
    create_http_client,
    fetch_all_fx_quotes,
    fetch_bytes_with_retry,
    fetch_cbr_daily_xml,
    fetch_ecb_daily_xml,
    fetch_fawazahmed0_eur,
    fetch_frankfurter_v2,
    parse_xml_safe,
    redact_url_secrets,
    run_fx_only_fetch,
    validate_https_url,
)
from ets2_realism.normalize import (
    ALL_REFERENCE_FX_RATES,
    ECB_COVERED_CURRENCIES,
    FxProviderQuote,
    cross_validate_fx_rates,
    load_prices_lockfile,
)

_SAMPLE_RATES: dict[str, float] = {
    "ALL": 98.5,
    "BAM": 1.95583,
    "CHF": 0.94,
    "CZK": 25.2,
    "DKK": 7.46,
    "GBP": 0.84,
    "HUF": 400.0,
    "ISK": 148.0,
    "MKD": 61.5,
    "NOK": 11.7,
    "PLN": 4.30,
    "RON": 4.97,
    "RSD": 117.1,
    "RUB": 95.0,
    "SEK": 11.4,
    "TRY": 36.5,
}


def _frankfurter_v2_payload() -> list[dict[str, object]]:
    return [
        {"date": "2026-11-20", "base": "EUR", "quote": ccy, "rate": rate}
        for ccy, rate in sorted(_SAMPLE_RATES.items())
    ]


def _ecb_daily_xml_bytes(*, include_rub: bool = False) -> bytes:
    cubes: list[str] = []
    for ccy in sorted(ECB_COVERED_CURRENCIES):
        cubes.append(f'<Cube currency="{ccy}" rate="{_SAMPLE_RATES[ccy]}"/>')
    if include_rub:
        cubes.append(f'<Cube currency="RUB" rate="{_SAMPLE_RATES["RUB"]}"/>')
    body = "\n        ".join(cubes)
    xml_text = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" '
        'xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">\n'
        "  <Cube>\n"
        '    <Cube time="2026-11-20">\n'
        f"        {body}\n"
        "    </Cube>\n"
        "  </Cube>\n"
        "</gesmes:Envelope>\n"
    )
    return xml_text.encode("utf-8")


def _fawaz_payload() -> dict[str, object]:
    return {
        "date": "2026-11-20",
        "eur": {ccy.lower(): rate for ccy, rate in _SAMPLE_RATES.items()},
    }


def _cbr_daily_xml_bytes(*, with_vunit_rate: bool = True) -> bytes:
    if with_vunit_rate:
        eur_block = (
            '  <Valute ID="R01239">\n'
            "    <NumCode>978</NumCode>\n"
            "    <CharCode>EUR</CharCode>\n"
            "    <Nominal>1</Nominal>\n"
            "    <Name>Евро</Name>\n"
            "    <Value>95,1234</Value>\n"
            "    <VunitRate>95,1234</VunitRate>\n"
            "  </Valute>\n"
        )
    else:
        # Exercise Value / Nominal fallback when VunitRate is omitted and Nominal > 1
        eur_block = (
            '  <Valute ID="R01239">\n'
            "    <NumCode>978</NumCode>\n"
            "    <CharCode>EUR</CharCode>\n"
            "    <Nominal>10</Nominal>\n"
            "    <Name>Евро</Name>\n"
            "    <Value>951,2340</Value>\n"
            "  </Valute>\n"
        )
    xml_text = (
        '<?xml version="1.0" encoding="windows-1251"?>\n'
        '<ValCurs Date="20.11.2026" name="Foreign Currency Market">\n'
        f"{eur_block}"
        "</ValCurs>\n"
    )
    return xml_text.encode("windows-1251")


def _all_providers_transport(
    *,
    fail_frankfurter: bool = False,
    fail_ecb: bool = False,
    fail_jsdelivr: bool = False,
    fail_cloudflare: bool = False,
    fail_cbr: bool = False,
) -> httpx.MockTransport:
    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://api.frankfurter.dev/v2/rates"):
            if fail_frankfurter:
                return httpx.Response(503, text="Frankfurter unavailable")
            return httpx.Response(200, json=_frankfurter_v2_payload())
        if url == ECB_DAILY_XML_URL:
            if fail_ecb:
                return httpx.Response(503, text="ECB unavailable")
            return httpx.Response(
                200,
                content=_ecb_daily_xml_bytes(include_rub=False),
                headers={"content-type": "application/xml"},
            )
        if url == FAWAZ_JSDELIVR_URL:
            if fail_jsdelivr:
                return httpx.Response(503, text="jsDelivr unavailable")
            return httpx.Response(200, json=_fawaz_payload())
        if url == FAWAZ_CLOUDFLARE_URL:
            if fail_cloudflare:
                return httpx.Response(503, text="Cloudflare mirror unavailable")
            return httpx.Response(200, json=_fawaz_payload())
        if url == CBR_DAILY_XML_URL:
            if fail_cbr:
                return httpx.Response(503, text="CBR unavailable")
            return httpx.Response(
                200,
                content=_cbr_daily_xml_bytes(with_vunit_rate=True),
                headers={"content-type": "application/xml; charset=windows-1251"},
            )
        return httpx.Response(404, text=f"unexpected url: {url}")

    return httpx.MockTransport(_handler)


def test_validate_https_url_ssrf_guard() -> None:
    allowed = frozenset({"api.frankfurter.dev", "www.ecb.europa.eu"})
    assert validate_https_url(FRANKFURTER_V2_URL, allowed) == FRANKFURTER_V2_URL
    assert validate_https_url(ECB_DAILY_XML_URL, allowed) == ECB_DAILY_XML_URL

    with pytest.raises(ValueError, match="HTTPS"):
        validate_https_url("http://api.frankfurter.dev/v2/rates", allowed)
    with pytest.raises(ValueError, match="HTTPS"):
        validate_https_url("file:///etc/passwd", allowed)
    with pytest.raises(ValueError, match="allowlist"):
        validate_https_url("https://evil.example.com/v2/rates", allowed)
    with pytest.raises(ValueError, match="credentials"):
        validate_https_url("https://user:pass@api.frankfurter.dev/v2/rates", allowed)


def test_redact_url_secrets_masks_query_credentials() -> None:
    raw = (
        "Client error for url 'https://creativecommons.tankerkoenig.de/json/list.php"
        "?lat=52.5&apikey=secret123&token=tok_xyz&key=k999'"
    )
    redacted = redact_url_secrets(raw)
    assert "secret123" not in redacted
    assert "tok_xyz" not in redacted
    assert "k999" not in redacted
    assert "apikey=***" in redacted
    assert "token=***" in redacted
    assert "key=***" in redacted
    assert "lat=52.5" in redacted


def test_fetch_bytes_with_retry_retries_transient_blocks_redirects_and_caps_size() -> None:
    attempts = 0

    def _retry_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, text="busy")
        if attempts == 2:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, content=b"ok-bytes")

    sleeps: list[float] = []
    with create_http_client(transport=httpx.MockTransport(_retry_handler)) as client:
        data = fetch_bytes_with_retry(
            client,
            "https://api.frankfurter.dev/v2/rates",
            allowed_hosts=frozenset({"api.frankfurter.dev"}),
            max_retries=2,
            sleep_fn=sleeps.append,
        )
    assert data == b"ok-bytes"
    assert attempts == 3
    assert len(sleeps) == 2

    # Oversized body cap rejection
    def _big_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2048)

    with (
        create_http_client(transport=httpx.MockTransport(_big_handler)) as client,
        pytest.raises(ValueError, match="max_bytes"),
    ):
        fetch_bytes_with_retry(
            client,
            "https://api.frankfurter.dev/v2/rates",
            allowed_hosts=frozenset({"api.frankfurter.dev"}),
            max_bytes=1024,
            sleep_fn=lambda _: None,
        )

    # Disallowed cross-host redirect SSRF guard
    def _redirect_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://169.254.169.254/latest/meta-data"})

    with (
        create_http_client(transport=httpx.MockTransport(_redirect_handler)) as client,
        pytest.raises(ValueError, match="allowlist"),
    ):
        fetch_bytes_with_retry(
            client,
            "https://api.frankfurter.dev/v2/rates",
            allowed_hosts=frozenset({"api.frankfurter.dev"}),
            sleep_fn=lambda _: None,
        )

    # Secret redaction on 401/403 HTTP error
    def _auth_fail_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    with (
        create_http_client(transport=httpx.MockTransport(_auth_fail_handler)) as client,
        pytest.raises(HttpFetchError) as exc_info,
    ):
        fetch_bytes_with_retry(
            client,
            "https://api.frankfurter.dev/v2/rates",
            allowed_hosts=frozenset({"api.frankfurter.dev"}),
            params={"apikey": "super_secret_token_999"},
            max_retries=0,
            sleep_fn=lambda _: None,
        )
    assert "super_secret_token_999" not in str(exc_info.value)


def test_parse_xml_safe_rejects_xxe_and_oversized_payloads() -> None:
    xxe_payload = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b"<root>&xxe;</root>"
    )
    with pytest.raises(ValueError, match=r"DOCTYPE|ENTITY"):
        parse_xml_safe(xxe_payload)

    entity_payload = b"<root><!ENTITY lol 'lol'></root>"
    with pytest.raises(ValueError, match=r"DOCTYPE|ENTITY"):
        parse_xml_safe(entity_payload)

    oversized = b"<root>" + (b"a" * 3_000_000) + b"</root>"
    with pytest.raises(ValueError, match="exceeds"):
        parse_xml_safe(oversized, max_bytes=2_097_152)


def test_fetch_frankfurter_v2_parses_flat_array_and_rejects_v1_dict() -> None:
    with create_http_client(transport=_all_providers_transport()) as client:
        quote = fetch_frankfurter_v2(client, sleep_fn=lambda _: None)
    assert quote.provider == "frankfurter_v2"
    assert quote.data_date == "2026-11-20"
    assert quote.rates["GBP"] == pytest.approx(0.84)
    assert quote.rates["BAM"] == pytest.approx(1.95583)

    # Reject legacy Frankfurter v1 dict schema
    v1_transport = httpx.MockTransport(
        lambda _req: httpx.Response(
            200,
            json={"base": "EUR", "date": "2026-11-20", "rates": {"GBP": 0.84}},
        )
    )
    with (
        create_http_client(transport=v1_transport) as client,
        pytest.raises(ValueError, match="flat JSON array"),
    ):
        fetch_frankfurter_v2(client, sleep_fn=lambda _: None)


def test_fetch_ecb_daily_xml_handles_suspended_rub_cleanly() -> None:
    with create_http_client(transport=_all_providers_transport()) as client:
        quote = fetch_ecb_daily_xml(client, sleep_fn=lambda _: None)
    assert quote.provider == "ecb_xml"
    assert quote.data_date == "2026-11-20"
    assert "RUB" not in quote.rates
    assert set(quote.rates) == set(ECB_COVERED_CURRENCIES)
    assert quote.rates["PLN"] == pytest.approx(4.30)


def test_fetch_fawazahmed0_primary_and_cloudflare_mirror_fallback() -> None:
    with create_http_client(transport=_all_providers_transport()) as client:
        quote = fetch_fawazahmed0_eur(client, sleep_fn=lambda _: None)
    assert quote.provider == "fawazahmed0"
    assert quote.rates["ALL"] == pytest.approx(98.5)
    assert quote.rates["RSD"] == pytest.approx(117.1)

    # jsDelivr 503 -> automatic Cloudflare Pages mirror fallback
    with create_http_client(transport=_all_providers_transport(fail_jsdelivr=True)) as client:
        quote_mirror = fetch_fawazahmed0_eur(client, sleep_fn=lambda _: None)
    assert quote_mirror.provider == "fawazahmed0"
    assert quote_mirror.rates["MKD"] == pytest.approx(61.5)


def test_fetch_cbr_daily_xml_windows_1251_and_nominal_division() -> None:
    with create_http_client(transport=_all_providers_transport()) as client:
        quote = fetch_cbr_daily_xml(client, sleep_fn=lambda _: None)
    assert quote.provider == "cbr_xml"
    assert quote.data_date == "2026-11-20"
    assert quote.rates["RUB"] == pytest.approx(95.1234)

    # Without VunitRate, divides Value / Nominal (951,2340 / 10 = 95.1234)
    nominal_transport = httpx.MockTransport(
        lambda _req: httpx.Response(200, content=_cbr_daily_xml_bytes(with_vunit_rate=False))
    )
    with create_http_client(transport=nominal_transport) as client:
        quote_nom = fetch_cbr_daily_xml(client, sleep_fn=lambda _: None)
    assert quote_nom.rates["RUB"] == pytest.approx(95.1234)


def test_fetch_all_fx_quotes_partial_outage_and_cross_validation() -> None:
    # Simulate CBR outage while Frankfurter + ECB + fawazahmed0 succeed
    with create_http_client(transport=_all_providers_transport(fail_cbr=True)) as client:
        bundle = fetch_all_fx_quotes(client, sleep_fn=lambda _: None)
    statuses = {s.provider: s for s in bundle.statuses}
    assert statuses["frankfurter_v2"].ok is True
    assert statuses["ecb_xml"].ok is True
    assert statuses["fawazahmed0"].ok is True
    assert statuses["cbr_xml"].ok is False

    provider_quotes = {
        name: FxProviderQuote(provider=q.provider, data_date=q.data_date, rates=q.rates)
        for name, q in bundle.quotes.items()
    }
    validated = cross_validate_fx_rates(
        provider_quotes,
        previous_fx=None,
        fetched_at="2026-11-20T06:00:00Z",
    )
    assert validated.ok is True
    assert len(validated.rates) == 17
    assert validated.rates["RUB"].validator_provider == "fawazahmed0"


def test_fetch_all_fx_quotes_preserves_extended_promods_currencies() -> None:
    def _extended_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://api.frankfurter.dev/v2/rates"):
            rows = [
                {"date": "2026-11-20", "base": "EUR", "quote": c, "rate": r}
                for c, r in sorted(
                    {**_SAMPLE_RATES, "CNY": 7.85, "ILS": 4.00, "KZT": 540.0}.items()
                )
            ]
            return httpx.Response(200, json=rows)
        if url == ECB_DAILY_XML_URL:
            cubes = "\n".join(
                f'        <Cube currency="{c}" rate="{r}"/>'
                for c, r in sorted(
                    {
                        **{k: _SAMPLE_RATES[k] for k in ECB_COVERED_CURRENCIES},
                        "CNY": 7.86,
                        "ILS": 4.01,
                    }.items()
                )
            )
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" '
                'xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">\n'
                f'  <Cube><Cube time="2026-11-20">\n{cubes}\n  </Cube></Cube>\n'
                "</gesmes:Envelope>\n"
            )
            return httpx.Response(200, content=xml.encode("utf-8"))
        if url in {FAWAZ_JSDELIVR_URL, FAWAZ_CLOUDFLARE_URL}:
            rates = {
                c.lower(): r
                for c, r in {**_SAMPLE_RATES, "CNY": 7.85, "ILS": 4.00, "KZT": 540.0}.items()
            }
            return httpx.Response(200, json={"date": "2026-11-20", "eur": rates})
        if url == CBR_DAILY_XML_URL:
            return httpx.Response(200, content=_cbr_daily_xml_bytes())
        return httpx.Response(404)

    with create_http_client(transport=httpx.MockTransport(_extended_handler)) as client:
        bundle = fetch_all_fx_quotes(client, sleep_fn=lambda _: None)

    assert bundle.quotes["frankfurter_v2"].rates["CNY"] == pytest.approx(7.85)
    assert bundle.quotes["frankfurter_v2"].rates["ILS"] == pytest.approx(4.00)
    assert bundle.quotes["frankfurter_v2"].rates["KZT"] == pytest.approx(540.0)
    assert bundle.quotes["ecb_xml"].rates["CNY"] == pytest.approx(7.86)
    assert bundle.quotes["ecb_xml"].rates["ILS"] == pytest.approx(4.01)
    assert bundle.quotes["fawazahmed0"].rates["KZT"] == pytest.approx(540.0)


def test_run_fx_only_fetch_and_cli_tracer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lock_path = tmp_path / "prices.lock.json"

    # Direct write_lock=True check
    report = run_fx_only_fetch(
        lock_path=lock_path,
        write_lock=True,
        transport=_all_providers_transport(),
        fetched_at="2026-11-20T06:00:00Z",
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.fx_only is True
    assert report.dry_run is False
    assert report.fx_currencies_validated == len(ALL_REFERENCE_FX_RATES)
    loaded = load_prices_lockfile(lock_path)
    assert len(loaded.fx_rates) == len(ALL_REFERENCE_FX_RATES)
    assert loaded.fx_rates["EUR"].rate_per_eur == 1.0

    # End-to-end CLI tracer: ets2-realism fetch --fx-only --dry-run --json
    import ets2_realism.fetch.fx as fetch_fx_module

    orig_create = fetch_fx_module.create_http_client

    def _patched_create(
        *, timeout: float = 20.0, transport: httpx.BaseTransport | None = None
    ) -> httpx.Client:
        return orig_create(timeout=timeout, transport=transport or _all_providers_transport())

    monkeypatch.setattr(fetch_fx_module, "create_http_client", _patched_create)

    dry_lock = tmp_path / "dry.lock.json"
    exit_code = main(
        [
            "fetch",
            "--fx-only",
            "--dry-run",
            "--json",
            "--lock-path",
            str(dry_lock),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert not dry_lock.exists()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["fx_only"] is True
    assert payload["dry_run"] is True
    assert payload["fx_currencies_validated"] == len(ALL_REFERENCE_FX_RATES)

    # Total FX outage with no prior lockfile exits non-zero
    def _patched_outage_create(
        *, timeout: float = 20.0, transport: httpx.BaseTransport | None = None
    ) -> httpx.Client:
        return orig_create(
            timeout=timeout,
            transport=transport
            or _all_providers_transport(
                fail_frankfurter=True,
                fail_ecb=True,
                fail_jsdelivr=True,
                fail_cloudflare=True,
                fail_cbr=True,
            ),
        )

    import ets2_realism.fetch.http as fetch_http_module

    def _noop_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(fetch_fx_module, "create_http_client", _patched_outage_create)
    monkeypatch.setattr(fetch_http_module.time, "sleep", _noop_sleep)
    fail_code = main(
        [
            "fetch",
            "--fx-only",
            "--dry-run",
            "--json",
            "--lock-path",
            str(dry_lock),
        ]
    )
    fail_captured = capsys.readouterr()
    assert fail_code == 1
    fail_payload = json.loads(fail_captured.out)
    assert fail_payload["ok"] is False


def test_http_port_guard_decoding_error_redaction_bom_xml_and_timeout_bounds(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    allowed = frozenset({"api.frankfurter.dev"})
    assert (
        validate_https_url("https://api.frankfurter.dev:443/v2/rates", allowed)
        == "https://api.frankfurter.dev:443/v2/rates"
    )
    with pytest.raises(ValueError, match="port"):
        validate_https_url("https://api.frankfurter.dev:8443/v2/rates", allowed)

    # Non-retryable httpx.DecodingError / StreamError wrapped in HttpFetchError with redacted secret
    def _bad_gzip_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError(
            f"corrupt gzip stream for {request.url}",
            request=request,
        )

    with (
        create_http_client(transport=httpx.MockTransport(_bad_gzip_handler)) as client,
        pytest.raises(HttpFetchError) as dec_exc,
    ):
        fetch_bytes_with_retry(
            client,
            "https://api.frankfurter.dev/v2/rates",
            allowed_hosts=allowed,
            params={"apikey": "very_secret_gzip_key"},
            max_retries=2,
            sleep_fn=lambda _: None,
        )
    assert "very_secret_gzip_key" not in str(dec_exc.value)
    assert "apikey=***" in str(dec_exc.value)

    def _stream_err_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.StreamClosed()

    with (
        create_http_client(transport=httpx.MockTransport(_stream_err_handler)) as client,
        pytest.raises(HttpFetchError),
    ):
        fetch_bytes_with_retry(
            client,
            "https://api.frankfurter.dev/v2/rates",
            allowed_hosts=allowed,
            max_retries=0,
            sleep_fn=lambda _: None,
        )

    # UTF-8 BOM-prefixed XML parses cleanly (LO-03)
    bom_xml = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><root><item>ok</item></root>'
    root = parse_xml_safe(bom_xml)
    assert root.tag == "root"

    # Invalid timeout rejected in create_http_client() and CLI _handle_fetch() (LO-05)
    for bad_timeout in (0.0, -2.5, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="timeout"):
            create_http_client(timeout=bad_timeout)

    for bad_arg in ("0", "-1", "nan", "inf"):
        code = main(["fetch", "--fx-only", "--dry-run", "--timeout", bad_arg])
        err_cap = capsys.readouterr()
        assert code == 1
        assert "--timeout" in err_cap.err

    # CLI _handle_fetch() redacts secrets in caught exception messages on stderr
    def _boom_fetch(*_args: object, **_kwargs: object) -> object:
        raise ValueError("failure for https://example.test/?apikey=cli_secret_999")

    monkeypatch.setattr("ets2_realism.cli.run_price_fetch", _boom_fetch)
    err_code = main(["fetch", "--fx-only", "--dry-run"])
    err_cap = capsys.readouterr()
    assert err_code == 1
    assert "cli_secret_999" not in err_cap.err
    assert "apikey=***" in err_cap.err


def test_hi03_fx_only_fetch_preserves_all_extended_global_currencies(tmp_path: Path) -> None:
    """HI-03 regression: fetch --fx-only preserves all global FX currencies in lockfile."""
    from ets2_realism.normalize.currencies import EXTENDED_PROMODS_CURRENCIES

    repo_lock = Path(__file__).resolve().parent.parent / "state" / "prices.lock.json"
    lock_copy = tmp_path / "prices.lock.json"
    lock_copy.write_bytes(repo_lock.read_bytes())

    before = load_prices_lockfile(lock_copy)
    assert len(before.fx_rates) == len(ALL_REFERENCE_FX_RATES)

    report = run_fx_only_fetch(
        lock_path=lock_copy,
        write_lock=True,
        transport=_all_providers_transport(),
        fetched_at="2026-11-25T06:00:00Z",
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.fx_currencies_validated == len(ALL_REFERENCE_FX_RATES)

    after = load_prices_lockfile(lock_copy)
    assert set(after.fx_rates.keys()) == set(ALL_REFERENCE_FX_RATES.keys())
    assert len(after.fx_rates) == len(ALL_REFERENCE_FX_RATES)
    for ext_ccy in EXTENDED_PROMODS_CURRENCIES:
        assert ext_ccy in after.fx_rates
        assert after.fx_rates[ext_ccy].rate_per_eur > 0.0


def test_http_retry_and_max_bytes_bounds_validation_lo02() -> None:
    """LO-02: Negative max_retries and non-positive max_bytes raise ValueError cleanly."""
    from ets2_realism.fetch.http import post_form_bytes_with_retry

    allowed = frozenset({"api.frankfurter.dev"})
    with create_http_client(transport=httpx.MockTransport(lambda _r: httpx.Response(200))) as c:
        with pytest.raises(ValueError, match="max_retries"):
            fetch_bytes_with_retry(
                c, "https://api.frankfurter.dev/v2/rates", allowed_hosts=allowed, max_retries=-1
            )
        with pytest.raises(ValueError, match="max_bytes"):
            fetch_bytes_with_retry(
                c, "https://api.frankfurter.dev/v2/rates", allowed_hosts=allowed, max_bytes=0
            )
        with pytest.raises(ValueError, match="max_retries"):
            post_form_bytes_with_retry(
                c,
                "https://api.frankfurter.dev/v2/rates",
                allowed_hosts=allowed,
                data={"k": "v"},
                max_retries=-2,
            )
        with pytest.raises(ValueError, match="max_bytes"):
            post_form_bytes_with_retry(
                c,
                "https://api.frankfurter.dev/v2/rates",
                allowed_hosts=allowed,
                data={"k": "v"},
                max_bytes=-10,
            )
