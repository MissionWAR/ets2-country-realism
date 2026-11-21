"""100% offline integration tests for run_price_fetch(), outage/staleness policy, CLI & lockfile."""

from __future__ import annotations

import io
import json
import pathlib
from datetime import UTC, date, datetime

import httpx
import openpyxl
import pytest

from ets2v2.baseline.models import CountriesBaseline
from ets2v2.cli import main
from ets2v2.fetch.ec_bulletin import (
    EC_WOB_LANDING_URL,
    FIONNHUGHES_CSV_URL,
    FUEL_PRICES_EU_URL,
)
from ets2v2.fetch.fx import (
    CBR_DAILY_XML_URL,
    ECB_DAILY_XML_URL,
    FAWAZ_CLOUDFLARE_URL,
    FAWAZ_JSDELIVR_URL,
)
from ets2v2.fetch.national import (
    DE_TANKERKOENIG_URL,
    ES_MITECO_URL,
    FR_ECONOMIE_URL,
    IT_MIMIT_URL,
    NL_CBS_80416NED_URL,
    NO_SSB_09654_URL,
    UK_DESNZ_LANDING_URL,
)
from ets2v2.fetch.pipeline import run_price_fetch
from ets2v2.normalize.currencies import (
    ECB_COVERED_CURRENCIES,
    EUROPEAN_TERRITORY_ISO2S,
    TERRITORY_CURRENCIES,
)
from ets2v2.normalize.lockfile import (
    BASELINE_SEEDED_SOURCE,
    load_prices_lockfile,
    seed_initial_lockfile,
    write_prices_lockfile,
)
from ets2v2.normalize.models import CANONICAL_FUEL_GRADES

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
COMMITTED_LOCK_PATH = REPO_ROOT / "state" / "prices.lock.json"

_RATES: dict[str, float] = {
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

_EU27_ROWS: list[tuple[str, float, float, float | None]] = [
    ("AT", 1600.0, 1580.0, 910.0),
    ("BE", 1650.0, 1680.0, 745.0),
    ("BG", 1300.0, 1310.0, 620.0),
    ("CY", 1450.0, 1510.0, None),
    ("CZ", 1465.0, 1480.0, 690.0),
    ("DE", 1740.0, 1640.0, 995.0),
    ("DK", 1915.0, 1785.0, None),
    ("EE", 1620.0, 1580.0, 780.0),
    ("EL", 1810.0, 1595.0, 890.0),
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


def _make_ec_xlsx(
    *,
    de_diesel_per_1000l: float = 1640.0,
    obs_date: date = date(2026, 11, 16),
) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Prices with taxes"
    ws.append(["Weekly Oil Bulletin"])
    ws.append(["Date", obs_date])
    ws.append(["Country", "Euro-super 95", "Automotive gas oil", "LPG - motor fuel"])
    for code, p95, diesel, lpg in _EU27_ROWS:
        d_val = de_diesel_per_1000l if code == "DE" else diesel
        ws.append([code, p95, d_val, lpg])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_ecb_xml() -> bytes:
    cubes = "\n".join(
        f'<Cube currency="{c}" rate="{_RATES[c]}"/>' for c in sorted(ECB_COVERED_CURRENCIES)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" '
        'xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">'
        f'<Cube><Cube time="2026-11-20">{cubes}</Cube></Cube>'
        "</gesmes:Envelope>"
    ).encode()


def _make_cbr_xml() -> bytes:
    return (
        '<?xml version="1.0" encoding="windows-1251"?>\n'
        '<ValCurs Date="20.11.2026">'
        '<Valute ID="R01239"><CharCode>EUR</CharCode><Nominal>1</Nominal>'
        "<Value>95,0000</Value><VunitRate>95,0000</VunitRate></Valute>"
        "</ValCurs>"
    ).encode("windows-1251")


def _pipeline_transport(
    *,
    fail_all_tier1: bool = False,
    fail_it: bool = False,
    fail_ec_wob: bool = False,
    de_diesel_per_1000l: float = 1640.0,
    ec_obs_date: date = date(2026, 11, 16),
) -> httpx.MockTransport:
    ec_xlsx_url = (
        "https://energy.ec.europa.eu/document/download/test_uuid_en"
        "?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx"
    )
    uk_csv_url = "https://assets.publishing.service.gov.uk/media/test/weekly_road_fuel_prices.csv"
    xlsx_bytes = _make_ec_xlsx(de_diesel_per_1000l=de_diesel_per_1000l, obs_date=ec_obs_date)

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # FX endpoints
        if url.startswith("https://api.frankfurter.dev/v2/rates"):
            return httpx.Response(
                200,
                json=[
                    {"date": "2026-11-20", "base": "EUR", "quote": c, "rate": r}
                    for c, r in sorted(_RATES.items())
                ],
            )
        if url == ECB_DAILY_XML_URL:
            return httpx.Response(200, content=_make_ecb_xml())
        if url in {FAWAZ_JSDELIVR_URL, FAWAZ_CLOUDFLARE_URL}:
            return httpx.Response(
                200,
                json={"date": "2026-11-20", "eur": {c.lower(): r for c, r in _RATES.items()}},
            )
        if url == CBR_DAILY_XML_URL:
            return httpx.Response(200, content=_make_cbr_xml())

        # Fuel endpoints
        if url == EC_WOB_LANDING_URL:
            if fail_all_tier1 or fail_ec_wob:
                return httpx.Response(503, text="ec wob down")
            return httpx.Response(
                200,
                text=(
                    '<a href="/document/download/test_uuid_en'
                    '?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx">'
                    "Prices with taxes</a>"
                ),
            )
        if url == ec_xlsx_url:
            if fail_all_tier1 or fail_ec_wob:
                return httpx.Response(503)
            return httpx.Response(200, content=xlsx_bytes)
        if url == FIONNHUGHES_CSV_URL:
            if fail_all_tier1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                text=(
                    "date,geo,product,price\n"
                    "2026-11-16,EL,Euro-super 95,1810.0\n"
                    "2026-11-16,EL,Automotive gas oil,1595.0\n"
                ),
            )
        if url == FUEL_PRICES_EU_URL:
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "ts": 1795154400,
                    "petrol": {"IS": 1.810},
                    "diesel": {"IS": 1.840},
                },
            )
        if url == UK_DESNZ_LANDING_URL:
            if fail_all_tier1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                text=f'<a href="{uk_csv_url}">Weekly road fuel prices (CSV)</a>',
            )
        if url == uk_csv_url:
            if fail_all_tier1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                text=(
                    "Date,ULSP: Pump price in pence/litre,ULSD: Pump price in pence/litre\n"
                    "16/11/2026,138.4,142.9\n"
                ),
            )
        if url == NO_SSB_09654_URL:
            if fail_all_tier1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "id": ["Drivstoff", "Tid"],
                    "size": [2, 1],
                    "dimension": {
                        "Drivstoff": {
                            "category": {
                                "index": {"01": 0, "02": 1},
                                "label": {"01": "Gasoline 95", "02": "Auto diesel"},
                            }
                        },
                        "Tid": {
                            "category": {
                                "index": {"2026M11": 0},
                                "label": {"2026M11": "2026M11"},
                            }
                        },
                    },
                    "value": [21.85, 20.95],
                },
            )
        if url == FR_ECONOMIE_URL:
            if fail_all_tier1:
                return httpx.Response(503)
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
        if url.startswith(DE_TANKERKOENIG_URL):
            if fail_all_tier1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "stations": [{"diesel": 1.659, "e5": 1.759, "isOpen": True}],
                },
            )
        if url == ES_MITECO_URL:
            if fail_all_tier1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "Fecha": "20/11/2026 07:00:00",
                    "ListaEESSPrecio": [
                        {
                            "Precio Gasoleo A": "1,499",
                            "Precio Gasoleo Premium": "1,609",
                            "Precio Gasolina 95 E5": "1,579",
                            "Precio Gasolina 98 E5": "1,729",
                            "Precio Gases licuados del petróleo": "0,949",
                        }
                    ],
                },
            )
        if url == IT_MIMIT_URL:
            if fail_all_tier1 or fail_it:
                return httpx.Response(503, text="mimit down")
            return httpx.Response(
                200,
                text=(
                    "Estrazione del 2026-11-20 08:00:00\n"
                    "idImpianto;descCarburante;prezzo;isSelf;dtComu\n"
                    "1;Gasolio;1.709;1;20/11/2026\n"
                    "1;Benzina;1.809;1;20/11/2026\n"
                    "1;GPL;0.739;1;20/11/2026\n"
                    "1;Blue Diesel;1.849;1;20/11/2026\n"
                    "1;Blu Super;1.959;1;20/11/2026\n"
                ),
            )
        if url == NL_CBS_80416NED_URL:
            if fail_all_tier1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "Perioden": "20261119",
                            "BenzineEuro95_1": 1.985,
                            "Diesel_2": 1.742,
                            "Lpg_3": 0.895,
                        }
                    ]
                },
            )
        return httpx.Response(404, text=f"unexpected url: {url}")

    return httpx.MockTransport(_handler)


def test_run_price_fetch_full_39_territory_merge_precedence_and_keyless_vs_keyed_de(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    # Keyless run: DE falls back silently to EC WOB and is excluded from Tier 1 tallies
    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.tier1_feeds_succeeded == 7  # EC WOB + UK + NO + FR + ES + IT + NL (DE skipped)
    assert report.tier1_feeds_failed == 0

    loaded = load_prices_lockfile(lock_path)
    assert len(loaded.countries) == 39
    assert set(loaded.countries.keys()) == set(EUROPEAN_TERRITORY_ISO2S)

    # National multi-grade overrides EC WOB
    assert loaded.countries["FR"].source == "fr_economie_ods"
    assert loaded.countries["FR"].local_prices["e85"] == pytest.approx(0.889)
    assert loaded.countries["ES"].source == "es_miteco"
    assert loaded.countries["ES"].local_prices["diesel_plus"] == pytest.approx(1.609)
    assert loaded.countries["IT"].source == "it_mimit"
    assert loaded.countries["NL"].source == "nl_cbs_80416ned"
    assert loaded.countries["GB"].source == "uk_desnz"
    assert loaded.countries["GB"].eur_per_liter == pytest.approx(1.701)  # 1.429 / 0.84
    assert loaded.countries["NO"].source == "no_ssb_09654"
    # Keyless DE uses EC WOB
    assert loaded.countries["DE"].source == "ec_weekly_oil_bulletin"
    assert loaded.countries["DE"].eur_per_liter == pytest.approx(1.640)
    # EC WOB EU-27 incl. EL->GR, IE, CY, MT, BG (EUR)
    assert loaded.countries["GR"].source == "ec_weekly_oil_bulletin"
    assert loaded.countries["BG"].currency == "EUR"
    assert loaded.countries["IE"].source == "ec_weekly_oil_bulletin"
    assert loaded.countries["CY"].source == "ec_weekly_oil_bulletin"
    assert loaded.countries["MT"].source == "ec_weekly_oil_bulletin"
    # fuel-prices.eu live non-EU IS
    assert loaded.countries["IS"].source == "fuel_prices_eu"
    assert loaded.countries["IS"].eur_per_liter == pytest.approx(1.840)
    # Uncovered non-EU seeded from 1.62 baseline converted via live FX
    for non_eu in ("AL", "BA", "CH", "ME", "MK", "RS", "RU", "TR", "XK"):
        assert loaded.countries[non_eu].source == BASELINE_SEEDED_SOURCE
        assert loaded.countries[non_eu].fallback_used is True

    # Keyed DE Tankerkoenig overrides DE diesel/petrol_95 while keeping EC WOB LPG
    report_keyed = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(),
        tankerkoenig_api_key="tk-test-key-xyz",
        now_utc=datetime(2026, 11, 20, 6, 5, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report_keyed.ok is True
    assert report_keyed.tier1_feeds_succeeded == 8
    loaded_keyed = load_prices_lockfile(lock_path)
    assert loaded_keyed.countries["DE"].source == "de_tankerkoenig"
    assert loaded_keyed.countries["DE"].eur_per_liter == pytest.approx(1.659)
    assert loaded_keyed.countries["DE"].local_prices["lpg"] == pytest.approx(0.995)
    assert "tk-test-key-xyz" not in lock_path.read_text("utf-8")


def test_run_price_fetch_circuit_breaker_and_allow_jump_cli_override(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    # Initial healthy fetch (DE diesel = 1.640 EUR/L)
    run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(de_diesel_per_1000l=1640.0),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )

    # Next week DE jumps +35% to 2.214 -> rejected & held without --allow-jump DE
    report_blocked = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(de_diesel_per_1000l=2214.0),
        now_utc=datetime(2026, 11, 27, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report_blocked.ok is True
    assert any(a.code == "price_jump_rejected" and a.scope == "DE" for a in report_blocked.alerts)
    assert load_prices_lockfile(lock_path).countries["DE"].eur_per_liter == pytest.approx(1.640)

    # CLI with --allow-jump DE --allow-jump PL --json accepts DE jump
    import ets2v2.fetch.pipeline as pipeline_mod

    orig_create = pipeline_mod.create_http_client

    def _patched_create(
        *, timeout: float = 20.0, transport: httpx.BaseTransport | None = None
    ) -> httpx.Client:
        return orig_create(
            timeout=timeout,
            transport=transport or _pipeline_transport(de_diesel_per_1000l=2214.0),
        )

    monkeypatch.setattr(pipeline_mod, "create_http_client", _patched_create)
    exit_code = main(
        [
            "fetch",
            "--lock-path",
            str(lock_path),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--allow-jump",
            "DE",
            "--allow-jump",
            "PL",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    cli_payload = json.loads(captured.out)
    assert cli_payload["ok"] is True
    assert load_prices_lockfile(lock_path).countries["DE"].eur_per_liter == pytest.approx(2.214)


def test_run_price_fetch_outage_and_staleness_policies_d08(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    # Seed initial lockfile with an old date so staleness alerts fire cleanly
    bl = CountriesBaseline.model_validate_json((BASELINE_DIR / "countries.json").read_text("utf-8"))
    old_seed = seed_initial_lockfile(bl, seed_date="2026-09-01", updated_at="2026-09-01T06:00:00Z")
    write_prices_lockfile(old_seed, lock_path)

    # Partial outage (IT MIMIT down while EC WOB + other Tier 1 succeed) -> ok=True, exit 0
    partial = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(fail_it=True, ec_obs_date=date(2026, 11, 1)),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert partial.ok is True
    assert partial.tier1_feeds_succeeded >= 1
    assert partial.tier1_feeds_failed == 1
    assert any(a.code == "feed_outage" and a.scope == "it_mimit" for a in partial.alerts)
    # IT fell back cleanly to EC WOB!
    loaded_partial = load_prices_lockfile(lock_path)
    assert loaded_partial.countries["IT"].source == "ec_weekly_oil_bulletin"
    # Staleness alerts: ec_obs_date 2026-11-01 is 19 days old (>14d stale_tier1)
    # and seeded non-EU from 2026-09-01 is 80 days old (>30d stale_fallback)
    assert any(a.code == "stale_tier1" for a in partial.alerts)
    assert any(a.code == "stale_fallback" for a in partial.alerts)

    # Total upstream outage (0 Tier 1 fuel feeds succeed) -> ok=False (exit 1), lockfile preserved
    before_bytes = lock_path.read_bytes()
    total = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(fail_all_tier1=True),
        now_utc=datetime(2026, 11, 20, 7, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert total.ok is False
    assert total.tier1_feeds_succeeded == 0
    assert any(a.code == "total_tier1_outage" and a.severity == "error" for a in total.alerts)
    assert lock_path.read_bytes() == before_bytes


def test_committed_state_prices_lockfile_contract() -> None:
    assert COMMITTED_LOCK_PATH.is_file(), "state/prices.lock.json must be committed"
    raw = COMMITTED_LOCK_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    text = raw.decode("utf-8")
    assert "TANKERKOENIG" not in text
    assert "apikey=" not in text.lower()

    lock = load_prices_lockfile(COMMITTED_LOCK_PATH)
    assert lock.schema_version == 1
    assert len(lock.countries) == 39
    assert set(lock.countries.keys()) == set(EUROPEAN_TERRITORY_ISO2S)
    assert lock.countries["BG"].currency == "EUR"
    assert lock.fx_rates["EUR"].rate_per_eur == 1.0
    for iso2, entry in lock.countries.items():
        assert entry.currency == TERRITORY_CURRENCIES[iso2]
        assert set(entry.local_prices.keys()) == set(CANONICAL_FUEL_GRADES)
