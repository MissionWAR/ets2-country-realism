"""100% offline integration tests for run_price_fetch(), outage/staleness policy, CLI & lockfile."""

from __future__ import annotations

import io
import json
import pathlib
from datetime import UTC, date, datetime

import httpx
import openpyxl
import pytest

from ets2_realism.baseline.models import CountriesBaseline
from ets2_realism.cli import main
from ets2_realism.fetch.ec_bulletin import (
    EC_WOB_LANDING_URL,
    FIONNHUGHES_CSV_URL,
    FUEL_PRICES_EU_URL,
)
from ets2_realism.fetch.fx import (
    CBR_DAILY_XML_URL,
    ECB_DAILY_XML_URL,
    FAWAZ_CLOUDFLARE_URL,
    FAWAZ_JSDELIVR_URL,
)
from ets2_realism.fetch.global_tier1 import (
    AR_ENERGIA_CKAN_PRIMARY_URL,
    BR_ANP_DIESEL_GNV_URL,
    BR_ANP_GASOLINA_ETANOL_URL,
    CL_CNE_V4_URL,
    CO_SICOM_CATALOG_URL,
    JP_METI_LANDING_URL,
    KR_OPINET_URL,
    MY_OPENDOSM_URL,
    US_EIA_V2_URL,
    gallon_to_liter,
)
from ets2_realism.fetch.national import (
    DE_TANKERKOENIG_URL,
    ES_MITECO_URL,
    FR_ECONOMIE_URL,
    IT_MIMIT_URL,
    NL_CBS_80416NED_URL,
    NO_SSB_09654_URL,
    UK_DESNZ_LANDING_URL,
)
from ets2_realism.fetch.pipeline import run_price_fetch
from ets2_realism.fetch.tier2_portals import (
    AE_MOEI_URL,
    CH_BFS_LIK_URL,
    IL_MOE_URL,
    IS_GASVAKTIN_URL,
    MD_ANRE_URL,
    MK_ERC_URL,
    NG_NBS_URL,
    RU_ROSSTAT_URL,
    SA_ARAMCO_URL,
    ZA_DMRE_CEF_URL,
)
from ets2_realism.normalize.currencies import (
    ALL_LOCKFILE_TERRITORY_ISO2S,
    ALL_REFERENCE_FX_RATES,
    ALL_TERRITORY_CURRENCIES,
    ECB_COVERED_CURRENCIES,
)
from ets2_realism.normalize.lockfile import (
    BASELINE_SEEDED_SOURCE,
    PROMODS_CURATED_SEED_SOURCE,
    load_prices_lockfile,
    seed_initial_lockfile,
    write_prices_lockfile,
)
from ets2_realism.normalize.models import CANONICAL_FUEL_GRADES

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
    de_lpg_per_1000l: float | None = 995.0,
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
        l_val = de_lpg_per_1000l if code == "DE" else lpg
        ws.append([code, p95, d_val, l_val])
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
    de_lpg_per_1000l: float | None = 995.0,
    de_tankerkoenig_diesel: float = 1.659,
    ec_obs_date: date = date(2026, 11, 16),
) -> httpx.MockTransport:
    ec_xlsx_url = (
        "https://energy.ec.europa.eu/document/download/test_uuid_en"
        "?filename=Weekly_Oil_Bulletin_Prices_with_taxes.xlsx"
    )
    uk_csv_url = "https://assets.publishing.service.gov.uk/media/test/weekly_road_fuel_prices.csv"
    xlsx_bytes = _make_ec_xlsx(
        de_diesel_per_1000l=de_diesel_per_1000l,
        de_lpg_per_1000l=de_lpg_per_1000l,
        obs_date=ec_obs_date,
    )

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
                    "stations": [{"diesel": de_tankerkoenig_diesel, "e5": 1.759, "isOpen": True}],
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
        include_global=False,
        include_tier2=False,
        transport=_pipeline_transport(),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.tier1_feeds_succeeded == 7  # EC WOB + UK + NO + FR + ES + IT + NL (DE skipped)
    assert report.tier1_feeds_failed == 0

    loaded = load_prices_lockfile(lock_path)
    assert len(loaded.countries) == 225
    assert set(loaded.countries.keys()) == set(ALL_LOCKFILE_TERRITORY_ISO2S)
    assert len(loaded.fx_rates) == len(ALL_REFERENCE_FX_RATES)

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
        include_global=False,
        include_tier2=False,
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
    import ets2_realism.fetch.pipeline as pipeline_mod

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
    assert len(lock.countries) == 225
    assert set(lock.countries.keys()) == set(ALL_LOCKFILE_TERRITORY_ISO2S)
    assert len(lock.fx_rates) == len(ALL_REFERENCE_FX_RATES)
    assert lock.countries["BG"].currency == "EUR"
    assert lock.fx_rates["EUR"].rate_per_eur == 1.0
    for iso2, entry in lock.countries.items():
        assert entry.currency == ALL_TERRITORY_CURRENCIES[iso2]
        assert set(entry.local_prices.keys()) == set(CANONICAL_FUEL_GRADES)


def test_run_price_fetch_isolates_corrupt_supplemental_grade_and_falls_back_to_live_ec_wob(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    # Initial healthy lockfile (DE diesel = 1.640 from EC WOB)
    init = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(de_diesel_per_1000l=1640.0),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert init.ok is True

    # Scenario 1 (HI-03): Corrupt EC WOB lpg (99.0 EUR/L) must NOT poison valid de_tankerkoenig
    res_supp = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(
            de_diesel_per_1000l=1645.0,
            de_lpg_per_1000l=99_000.0,  # 99.0 EUR/L -> corrupt!
            de_tankerkoenig_diesel=1.659,
        ),
        tankerkoenig_api_key="tk-test-key",
        now_utc=datetime(2026, 11, 21, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res_supp.ok is True
    loaded_supp = load_prices_lockfile(lock_path)
    assert loaded_supp.countries["DE"].source == "de_tankerkoenig"
    assert loaded_supp.countries["DE"].eur_per_liter == pytest.approx(1.659)
    assert "lpg" in loaded_supp.countries["DE"].derived_grades
    assert loaded_supp.countries["DE"].local_prices["lpg"] == pytest.approx(1.759 * 0.48, abs=1e-3)
    assert any(a.code == "supplemental_grade_rejected" and a.scope == "DE" for a in res_supp.alerts)

    # Scenario 2 (HI-03): Rejected Tier 1 national feed (de_tankerkoenig >25% jump) falls back
    # to healthy live EC WOB (diesel = 1.670) instead of stale previous entry (1.659)!
    res_fb = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(
            de_diesel_per_1000l=1670.0,
            de_lpg_per_1000l=985.0,
            de_tankerkoenig_diesel=3.500,  # >25% jump -> rejected
        ),
        tankerkoenig_api_key="tk-test-key",
        now_utc=datetime(2026, 11, 22, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res_fb.ok is True
    loaded_fb = load_prices_lockfile(lock_path)
    assert loaded_fb.countries["DE"].source == "ec_weekly_oil_bulletin"
    assert loaded_fb.countries["DE"].eur_per_liter == pytest.approx(1.670)
    assert loaded_fb.countries["DE"].fallback_used is False
    assert any(a.code == "price_jump_rejected" and a.scope == "DE" for a in res_fb.alerts)


def test_run_price_fetch_anchorless_quote_retains_previous_live_entry(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ets2_realism.fetch.models import RawCountryFuelQuote, RawFuelFeedResult

    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    # Initial healthy live fetch (IS = 1.840 from fuel_prices_eu)
    run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert load_prices_lockfile(lock_path).countries["IS"].source == "fuel_prices_eu"

    # Next run: fuel_prices_eu returns an anchorless quote for IS (only lpg, no diesel/petrol_95)
    def _anchorless_feed(
        _client: httpx.Client,
        *,
        sleep_fn: object = None,
    ) -> RawFuelFeedResult:
        _ = sleep_fn
        return RawFuelFeedResult(
            feed_name="fuel_prices_eu",
            tier="fallback",
            ok=True,
            quotes=[
                RawCountryFuelQuote(
                    iso2="IS",
                    currency="EUR",
                    prices_by_grade={"lpg": 0.99},
                    unit_basis="eur_per_liter",
                    source="fuel_prices_eu",
                    license="CC BY 4.0",
                    data_date="2026-11-21",
                )
            ],
            data_date="2026-11-21",
        )

    monkeypatch.setattr("ets2_realism.fetch.pipeline.fetch_fuel_prices_eu", _anchorless_feed)
    res = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=_pipeline_transport(),
        now_utc=datetime(2026, 11, 21, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res.ok is True
    loaded = load_prices_lockfile(lock_path)
    # Retain previous live fuel_prices_eu entry (1.840), NOT overwrite with baseline_1.62_seeded
    assert loaded.countries["IS"].source == "fuel_prices_eu"
    assert loaded.countries["IS"].eur_per_liter == pytest.approx(1.840)
    assert loaded.countries["IS"].fallback_used is True
    assert any(a.code == "price_anchor_missing" and a.scope == "IS" for a in res.alerts)


def test_run_price_fetch_preserves_76_territories_and_reprices_promods_with_live_fx(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    bl = CountriesBaseline.model_validate_json((BASELINE_DIR / "countries.json").read_text("utf-8"))
    seeded = seed_initial_lockfile(bl, seed_date="2026-11-15", updated_at="2026-11-15T06:00:00Z")
    write_prices_lockfile(seeded, lock_path)

    base_transport = _pipeline_transport()
    live_extended_rates = {**_RATES, "KZT": 560.0, "JOD": 0.80, "UAH": 48.0}

    def _extended_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://api.frankfurter.dev/v2/rates"):
            return httpx.Response(
                200,
                json=[
                    {"date": "2026-11-20", "base": "EUR", "quote": c, "rate": r}
                    for c, r in sorted(live_extended_rates.items())
                ],
            )
        if url in {FAWAZ_JSDELIVR_URL, FAWAZ_CLOUDFLARE_URL}:
            return httpx.Response(
                200,
                json={
                    "date": "2026-11-20",
                    "eur": {c.lower(): r for c, r in live_extended_rates.items()},
                },
            )
        if url == FUEL_PRICES_EU_URL:
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "ts": 1795154400,
                    "petrol": {"IS": 1.810, "AD": 1.495},
                    "diesel": {"IS": 1.840, "AD": 1.460},
                },
            )
        return base_transport.handle_request(request)

    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=httpx.MockTransport(_extended_handler),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.fx_currencies_validated == len(ALL_REFERENCE_FX_RATES)

    loaded = load_prices_lockfile(lock_path)
    assert len(loaded.countries) == 225
    assert set(loaded.countries.keys()) == set(ALL_LOCKFILE_TERRITORY_ISO2S)

    # Live fuel-prices.eu AD quote accepted cleanly and NOT marked fallback (IN-02)
    assert loaded.countries["AD"].source == "fuel_prices_eu"
    assert loaded.countries["AD"].eur_per_liter == pytest.approx(1.460)
    assert loaded.countries["AD"].fallback_used is False

    # Curated ProMods entries preserved & local_prices dynamically recalculated with live FX
    for iso2, expected_rate in (("KZ", 560.0), ("JO", 0.80), ("UA", 48.0)):
        entry = loaded.countries[iso2]
        assert entry.source == PROMODS_CURATED_SEED_SOURCE
        assert entry.data_date == "2026-11-15"
        assert entry.fallback_used is True
        expected_local_diesel = round(entry.eur_per_liter * expected_rate, 4)
        assert entry.local_prices["diesel"] == pytest.approx(expected_local_diesel, abs=1e-3)


def test_in02_non_eu_promods_live_fuel_prices_eu_not_marked_fallback(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IN-02 regression: fresh fuel_prices_eu quotes for non-EU ProMods territories are primary."""
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"
    bl = CountriesBaseline.model_validate_json((BASELINE_DIR / "countries.json").read_text("utf-8"))
    seeded = seed_initial_lockfile(bl, seed_date="2026-11-15", updated_at="2026-11-15T06:00:00Z")
    write_prices_lockfile(seeded, lock_path)

    base_transport = _pipeline_transport(fail_ec_wob=True)

    def _handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == FUEL_PRICES_EU_URL:
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "ts": 1795154400,
                    "petrol": {"IS": 1.810, "UA": 1.350, "MD": 1.310, "AD": 1.495, "CY": 1.450},
                    "diesel": {"IS": 1.840, "UA": 1.320, "MD": 1.280, "AD": 1.460, "CY": 1.510},
                },
            )
        return base_transport.handle_request(request)

    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        transport=httpx.MockTransport(_handler),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    loaded = load_prices_lockfile(lock_path)
    for non_eu_iso2 in ("IS", "UA", "MD", "AD"):
        assert loaded.countries[non_eu_iso2].source == "fuel_prices_eu"
        assert loaded.countries[non_eu_iso2].fallback_used is False
    # EU-27 member (CY) falling back to fuel_prices_eu when EC WOB is down IS marked fallback
    assert loaded.countries["CY"].source == "fuel_prices_eu"
    assert loaded.countries["CY"].fallback_used is True


def _make_jp_meti_pipeline_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "全国平均価格"
    ws.append(["調査日", "2026年11月16日"])
    ws.append(["都道府県", "レギュラー", "ハイオク", "軽油", "灯油"])
    ws.append(["全国平均", 174.8, 185.6, 154.2, 2110.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _global_pipeline_transport(
    *,
    fail_all_eu_tier1: bool = False,
    fail_all_global_tier1: bool = False,
    succeed_only_my_jp: bool = False,
) -> httpx.MockTransport:
    base = _pipeline_transport(fail_all_tier1=fail_all_eu_tier1)
    global_rates = {
        **_RATES,
        "USD": 1.08,
        "BRL": 6.20,
        "ARS": 1080.0,
        "COP": 4700.0,
        "CLP": 1020.0,
        "MYR": 4.80,
        "JPY": 165.0,
        "KRW": 1500.0,
    }
    ar_csv_url = "https://datos.energia.gob.ar/dataset/abc/precios-en-surtidor-vigentes.csv"
    jp_xlsx_url = (
        "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results_20261116.xlsx"
    )
    jp_xlsx_bytes = _make_jp_meti_pipeline_xlsx()

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # Extended FX rates covering all 8 global Tier 1 currencies
        if url.startswith("https://api.frankfurter.dev/v2/rates"):
            return httpx.Response(
                200,
                json=[
                    {"date": "2026-11-20", "base": "EUR", "quote": c, "rate": r}
                    for c, r in sorted(global_rates.items())
                ],
            )
        if url in {FAWAZ_JSDELIVR_URL, FAWAZ_CLOUDFLARE_URL}:
            return httpx.Response(
                200,
                json={
                    "date": "2026-11-20",
                    "eur": {c.lower(): r for c, r in global_rates.items()},
                },
            )

        # MY OpenDOSM & JP METI (checked before fail_all_global_tier1 if succeed_only_my_jp)
        if url.startswith(MY_OPENDOSM_URL):
            if fail_all_global_tier1 and not succeed_only_my_jp:
                return httpx.Response(500, text="my down")
            return httpx.Response(
                200,
                json=[
                    {
                        "date": "2026-11-19",
                        "series_type": "level",
                        "ron95": 2.05,
                        "ron97": 3.19,
                        "diesel": 2.95,
                    }
                ],
            )
        if url == JP_METI_LANDING_URL:
            if fail_all_global_tier1 and not succeed_only_my_jp:
                return httpx.Response(500, text="jp down")
            return httpx.Response(
                200,
                text=(
                    '<a href="/statistics/petroleum_and_lpgas/pl007/results_20261116.xlsx">XLSX</a>'
                ),
            )
        if url == jp_xlsx_url:
            if fail_all_global_tier1 and not succeed_only_my_jp:
                return httpx.Response(500, text="jp xlsx down")
            return httpx.Response(200, content=jp_xlsx_bytes)

        if fail_all_global_tier1 or succeed_only_my_jp:
            global_prefixes = (
                US_EIA_V2_URL,
                BR_ANP_DIESEL_GNV_URL,
                BR_ANP_GASOLINA_ETANOL_URL,
                AR_ENERGIA_CKAN_PRIMARY_URL,
                "https://datos.energia.gob.ar/",
                CO_SICOM_CATALOG_URL,
                "https://creg.gov.co/",
                CL_CNE_V4_URL,
                "https://api.cne.cl/",
                KR_OPINET_URL,
            )
            if any(url.startswith(prefix) for prefix in global_prefixes):
                return httpx.Response(500, text="global upstream down")

        # Remaining 6 global Tier 1 endpoints
        if url.startswith(US_EIA_V2_URL):
            return httpx.Response(
                200,
                json={
                    "response": {
                        "data": [
                            {
                                "period": "2026-11-16",
                                "duoarea": "NUS",
                                "process": "PTE",
                                "product": "EPD2D",
                                "value": "3.785411784",
                            },
                            {
                                "period": "2026-11-16",
                                "duoarea": "NUS",
                                "process": "PTE",
                                "product": "EPMR",
                                "value": "3.4068706056",
                            },
                            {
                                "period": "2026-11-16",
                                "duoarea": "NUS",
                                "process": "PTE",
                                "product": "EPMP",
                                "value": "4.1639529624",
                            },
                        ]
                    }
                },
            )
        if url == BR_ANP_DIESEL_GNV_URL:
            return httpx.Response(
                200,
                content=(
                    "Produto;Data da Coleta;Valor de Venda\nDIESEL S10;19/11/2026;6,20\n"
                ).encode("latin-1"),
            )
        if url == BR_ANP_GASOLINA_ETANOL_URL:
            return httpx.Response(
                200,
                content=(
                    "Produto;Data da Coleta;Valor de Venda\n"
                    "GASOLINA COMUM;19/11/2026;6,10\n"
                    "ETANOL;19/11/2026;4,15\n"
                ).encode("latin-1"),
            )
        if url == AR_ENERGIA_CKAN_PRIMARY_URL:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "resources": [
                            {"name": "Precios vigentes", "format": "CSV", "url": ar_csv_url}
                        ]
                    },
                },
            )
        if url == ar_csv_url:
            return httpx.Response(
                200,
                text=(
                    "producto,precio,tipohorario,fecha_vigencia\n"
                    "Gas Oil Grado 2,1188.0,Diurno,2026-11-19 08:00:00\n"
                    "Nafta (super),1134.0,Diurno,2026-11-19 08:00:00\n"
                ),
            )
        if url == CO_SICOM_CATALOG_URL:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "resource": {
                                "id": "ab12-cd34",
                                "name": "Precio mes combustible SICOM",
                            }
                        }
                    ]
                },
            )
        if url.startswith("https://www.datos.gov.co/resource/ab12-cd34.json"):
            return httpx.Response(
                200,
                json=[
                    {"producto": "ACPM", "precio": "9540", "fecha": "2026-11-15"},
                    {"producto": "GASOLINA CORRIENTE", "precio": "15588", "fecha": "2026-11-15"},
                ],
            )
        if url == CL_CNE_V4_URL:
            return httpx.Response(
                200,
                json=[
                    {
                        "fecha_hora_actualizacion": "2026-11-19 10:00:00",
                        "precios": {"diesel": 1040, "95": 1290, "97": 1350, "93": 1250},
                    }
                ],
            )
        if url.startswith(KR_OPINET_URL):
            return httpx.Response(
                200,
                json={
                    "RESULT": {
                        "OIL": [
                            {"TRADE_DT": "20261120", "PRODCD": "D047", "PRICE": "1518.0"},
                            {"TRADE_DT": "20261120", "PRODCD": "B027", "PRICE": "1654.0"},
                            {"TRADE_DT": "20261120", "PRODCD": "B034", "PRICE": "1912.0"},
                            {"TRADE_DT": "20261120", "PRODCD": "K015", "PRICE": "1012.0"},
                        ]
                    }
                },
            )

        return base.handle_request(request)

    return httpx.MockTransport(_handler)


def test_run_price_fetch_updates_all_8_global_tier1_economies_live(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=True,
        eia_api_key="eia-secret-live",
        opinet_api_key="opinet-secret-live",
        cne_api_token="cne-secret-live",
        transport=_global_pipeline_transport(),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.eu_tier1_feeds_succeeded == 7
    assert report.tier1_feeds_succeeded == 7
    assert report.eu_tier1_feeds_failed == 0
    assert report.global_tier1_feeds_succeeded == 8
    assert report.global_tier1_feeds_failed == 0

    raw_lock = lock_path.read_text("utf-8")
    assert "eia-secret-live" not in raw_lock
    assert "opinet-secret-live" not in raw_lock
    assert "cne-secret-live" not in raw_lock

    loaded = load_prices_lockfile(lock_path)
    expected_sources = {
        "US": "us_eia_v2",
        "BR": "br_anp",
        "AR": "ar_energia",
        "CO": "co_sicom",
        "CL": "cl_cne",
        "MY": "my_opendosm",
        "JP": "jp_meti",
        "KR": "kr_opinet",
    }
    for iso2, src in expected_sources.items():
        entry = loaded.countries[iso2]
        assert entry.source == src
        assert entry.fallback_used is False

    # Verify exact US & CO NIST gallon conversion flowed cleanly into local_prices & eur_per_liter
    assert loaded.countries["US"].local_prices["diesel"] == pytest.approx(1.0, abs=1e-4)
    assert loaded.countries["US"].eur_per_liter == pytest.approx(1.0 / 1.08, abs=1e-3)
    assert loaded.countries["CO"].local_prices["diesel"] == pytest.approx(
        gallon_to_liter(9540.0), abs=1e-3
    )


def test_run_price_fetch_d02_global_tier1_outage_warns_only_and_retains_lockfile(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    bl = CountriesBaseline.model_validate_json((BASELINE_DIR / "countries.json").read_text("utf-8"))
    seeded = seed_initial_lockfile(bl, seed_date="2026-11-15", updated_at="2026-11-15T06:00:00Z")
    write_prices_lockfile(seeded, lock_path)

    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=True,
        eia_api_key="eia-outage-secret",
        opinet_api_key="opinet-outage-secret",
        cne_api_token="cne-outage-secret",
        transport=_global_pipeline_transport(fail_all_global_tier1=True),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.eu_tier1_feeds_succeeded == 7
    assert report.global_tier1_feeds_succeeded == 0
    assert report.global_tier1_feeds_failed == 8

    outage_alerts = [a for a in report.alerts if a.code == "global_tier1_outage"]
    assert len(outage_alerts) == 8
    assert all(a.severity == "warning" for a in outage_alerts)

    # Zero secret leakage in alerts or lockfile
    raw_lock = lock_path.read_text("utf-8")
    assert "eia-outage-secret" not in raw_lock
    assert "opinet-outage-secret" not in raw_lock
    assert "cne-outage-secret" not in raw_lock

    loaded = load_prices_lockfile(lock_path)
    for iso2 in ("US", "BR", "AR", "CO", "CL", "MY", "JP", "KR"):
        assert loaded.countries[iso2].eur_per_liter == pytest.approx(
            seeded.countries[iso2].eur_per_liter
        )
        assert loaded.countries[iso2].fallback_used is True


def test_run_price_fetch_d02_global_success_never_masks_eu_core_outage(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("OPINET_API_KEY", raising=False)
    monkeypatch.delenv("CNE_API_TOKEN", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    bl = CountriesBaseline.model_validate_json((BASELINE_DIR / "countries.json").read_text("utf-8"))
    seeded = seed_initial_lockfile(bl, seed_date="2026-11-15", updated_at="2026-11-15T06:00:00Z")
    write_prices_lockfile(seeded, lock_path)
    before_bytes = lock_path.read_bytes()

    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=True,
        transport=_global_pipeline_transport(fail_all_eu_tier1=True, succeed_only_my_jp=True),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is False
    assert report.eu_tier1_feeds_succeeded == 0
    assert report.tier1_feeds_succeeded == 0
    assert report.global_tier1_feeds_succeeded == 2  # MY + JP succeeded
    assert any(a.code == "total_tier1_outage" and a.severity == "error" for a in report.alerts)
    assert lock_path.read_bytes() == before_bytes


def test_run_price_fetch_keyless_skip_reasons_are_feed_specific_and_no_global_cli(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("OPINET_API_KEY", raising=False)
    monkeypatch.delenv("CNE_API_TOKEN", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=True,
        transport=_global_pipeline_transport(),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.global_tier1_feeds_succeeded == 5  # BR, AR, CO, MY, JP
    assert report.global_tier1_feeds_failed == 0

    status_by_provider = {s.provider: s for s in report.provider_statuses}
    assert status_by_provider["de_tankerkoenig"].detail is not None
    assert "TANKERKOENIG_API_KEY" in status_by_provider["de_tankerkoenig"].detail
    assert status_by_provider["us_eia_v2"].detail is not None
    assert "EIA_API_KEY" in status_by_provider["us_eia_v2"].detail
    assert "TANKERKOENIG" not in status_by_provider["us_eia_v2"].detail
    assert status_by_provider["kr_opinet"].detail is not None
    assert "OPINET_API_KEY" in status_by_provider["kr_opinet"].detail
    assert "TANKERKOENIG" not in status_by_provider["kr_opinet"].detail
    assert status_by_provider["cl_cne"].detail is not None
    assert "CNE_API_TOKEN" in status_by_provider["cl_cne"].detail
    assert "TANKERKOENIG" not in status_by_provider["cl_cne"].detail

    # CLI --no-global skips all 8 Global Tier 1 feeds cleanly
    import ets2_realism.fetch.pipeline as pipeline_mod

    orig_create = pipeline_mod.create_http_client

    def _patched_create(
        *, timeout: float = 20.0, transport: httpx.BaseTransport | None = None
    ) -> httpx.Client:
        return orig_create(timeout=timeout, transport=transport or _pipeline_transport())

    monkeypatch.setattr(pipeline_mod, "create_http_client", _patched_create)
    exit_code = main(
        [
            "fetch",
            "--no-global",
            "--lock-path",
            str(lock_path),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--dry-run",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    cli_payload = json.loads(captured.out)
    assert cli_payload["ok"] is True
    assert cli_payload["eu_tier1_feeds_succeeded"] == 7
    assert cli_payload["global_tier1_feeds_succeeded"] == 0
    assert cli_payload["global_tier1_feeds_failed"] == 0
    providers = {s["provider"] for s in cli_payload["provider_statuses"]}
    assert "us_eia_v2" not in providers
    assert "my_opendosm" not in providers
    assert "kr_opinet" not in providers


def test_run_price_fetch_tier2_all_10_failing_warns_only_and_falls_back_to_fuel_prices_eu(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"
    bl = CountriesBaseline.model_validate_json((BASELINE_DIR / "countries.json").read_text("utf-8"))
    seeded = seed_initial_lockfile(bl, seed_date="2026-11-15", updated_at="2026-11-15T06:00:00Z")
    write_prices_lockfile(seeded, lock_path)

    base = _pipeline_transport()

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == FUEL_PRICES_EU_URL:
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "ts": 1795154400,
                    "petrol": {"IS": 1.810, "CH": 1.920, "MD": 1.300, "MK": 1.330},
                    "diesel": {"IS": 1.840, "CH": 1.990, "MD": 1.240, "MK": 1.250},
                },
            )
        if url == RU_ROSSTAT_URL:
            return httpx.Response(403, request=request, text="geo blocked")
        if url == SA_ARAMCO_URL:
            return httpx.Response(429, request=request, text="rate limited")
        if url == AE_MOEI_URL:
            return httpx.Response(200, request=request, content=b"\x98\xff\xfebad")
        if url == MD_ANRE_URL:
            return httpx.Response(200, request=request, text="<html><body>No table</body></html>")
        if url == NG_NBS_URL:
            raise httpx.ReadTimeout("nbs timeout", request=request)
        if url in {
            IS_GASVAKTIN_URL,
            CH_BFS_LIK_URL,
            MK_ERC_URL,
            IL_MOE_URL,
            ZA_DMRE_CEF_URL,
        }:
            return httpx.Response(503, request=request, text="portal down")
        return base.handle_request(request)

    report = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=False,
        include_tier2=True,
        transport=httpx.MockTransport(_handler),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert report.ok is True
    assert report.tier2_feeds_succeeded == 0
    assert report.tier2_feeds_failed == 10

    alert_by_scope = {a.scope: a for a in report.alerts}
    assert alert_by_scope["ru_rosstat"].code == "tier2_rate_limited"
    assert alert_by_scope["sa_aramco"].code == "tier2_rate_limited"
    assert alert_by_scope["ae_moei"].code == "tier2_encoding_error"
    assert alert_by_scope["md_anre"].code == "tier2_selector_drift"
    assert alert_by_scope["ng_nbs"].code == "tier2_portal_outage"
    assert all(a.severity == "warning" for a in report.alerts if a.code.startswith("tier2_"))

    loaded = load_prices_lockfile(lock_path)
    # European Tier 2 portals automatically fell back to live fuel_prices_eu (precedence 10)
    for eu_t2 in ("IS", "CH", "MD", "MK"):
        assert loaded.countries[eu_t2].source == "fuel_prices_eu"
        assert loaded.countries[eu_t2].fallback_used is False
    # Non-EU Tier 2 portals cleanly retained lockfile/Tier 3 baseline
    for non_eu_t2 in ("AE", "ZA", "SA", "NG", "IL", "RU"):
        assert loaded.countries[non_eu_t2].eur_per_liter == pytest.approx(
            seeded.countries[non_eu_t2].eur_per_liter
        )
        assert loaded.countries[non_eu_t2].fallback_used is True


def test_run_price_fetch_tier2_live_updates_and_bounds_wow_guards(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    base = _pipeline_transport()
    t2_rates = {
        **_RATES,
        "AED": 3.96,
        "ZAR": 19.80,
        "SAR": 4.05,
        "ILS": 4.00,
    }

    def _make_handler(*, ae_diesel_aed: float = 2.67) -> httpx.MockTransport:
        def _handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.startswith("https://api.frankfurter.dev/v2/rates"):
                return httpx.Response(
                    200,
                    json=[
                        {"date": "2026-11-20", "base": "EUR", "quote": c, "rate": r}
                        for c, r in sorted(t2_rates.items())
                    ],
                )
            if url in {FAWAZ_JSDELIVR_URL, FAWAZ_CLOUDFLARE_URL}:
                return httpx.Response(
                    200,
                    json={
                        "date": "2026-11-20",
                        "eur": {c.lower(): r for c, r in t2_rates.items()},
                    },
                )
            if url == AE_MOEI_URL:
                return httpx.Response(
                    200,
                    text=(
                        "<html><body><p>2026-11-01</p><table>"
                        f"<tr><td>Diesel</td><td>{ae_diesel_aed}</td></tr>"
                        "<tr><td>Special 95</td><td>2.63</td></tr>"
                        "</table></body></html>"
                    ),
                )
            if url == ZA_DMRE_CEF_URL:
                return httpx.Response(
                    200,
                    text=(
                        "<html><body><p>2026-11-04</p><table>"
                        "<tr><th>Grade</th><th>Inland (c/L)</th></tr>"
                        "<tr><td>Petrol 95 ULP</td><td>2345.0</td></tr>"
                        "<tr><td>Diesel 0.005%</td><td>2105.0</td></tr>"
                        "</table></body></html>"
                    ),
                )
            if url == SA_ARAMCO_URL:
                return httpx.Response(
                    200,
                    text=(
                        "<html><body><p>2026-11-11</p><table>"
                        "<tr><td>Diesel</td><td>1.15</td></tr>"
                        "<tr><td>Gasoline 95</td><td>2.33</td></tr>"
                        "</table></body></html>"
                    ),
                )
            if url == IL_MOE_URL:
                return httpx.Response(
                    200,
                    text=(
                        "<html><body><p>2026-11-01</p><table>"
                        "<tr><td>Unleaded 95 Octane (Self-Service)</td><td>7.45</td></tr>"
                        "</table></body></html>"
                    ),
                )
            return base.handle_request(request)

        return httpx.MockTransport(_handler)

    # First live run: AE, ZA, SA, IL update cleanly (IL derives diesel from petrol_95 anchor)
    res1 = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=False,
        include_tier2=True,
        transport=_make_handler(ae_diesel_aed=2.67),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res1.ok is True
    assert res1.tier2_feeds_succeeded == 4
    loaded1 = load_prices_lockfile(lock_path)
    assert loaded1.countries["AE"].source == "ae_moei"
    assert loaded1.countries["AE"].fallback_used is False
    assert loaded1.countries["AE"].local_prices["diesel"] == pytest.approx(2.67)
    assert loaded1.countries["ZA"].source == "za_dmre_cef"
    assert loaded1.countries["ZA"].local_prices["diesel"] == pytest.approx(21.05)
    assert loaded1.countries["SA"].source == "sa_aramco"
    assert loaded1.countries["SA"].local_prices["diesel"] == pytest.approx(1.15)
    assert loaded1.countries["IL"].source == "il_moe"
    assert loaded1.countries["IL"].fallback_used is False
    assert loaded1.countries["IL"].local_prices["petrol_95"] == pytest.approx(7.45)
    assert "diesel" in loaded1.countries["IL"].derived_grades

    # Corrupt out-of-bounds (< 0.01 EUR/L) quote from AE is rejected
    res_oob = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=False,
        include_tier2=True,
        transport=_make_handler(ae_diesel_aed=0.001),
        now_utc=datetime(2026, 11, 21, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res_oob.ok is True
    assert any(a.code == "price_bounds_rejected" and a.scope == "AE" for a in res_oob.alerts)
    assert load_prices_lockfile(lock_path).countries["AE"].local_prices["diesel"] == pytest.approx(
        2.67
    )

    # Corrupt +80% WoW jump from AE is rejected by +/-25% circuit breaker
    res_jump = run_price_fetch(
        lock_path=lock_path,
        baseline_dir=BASELINE_DIR,
        write_lock=True,
        include_global=False,
        include_tier2=True,
        transport=_make_handler(ae_diesel_aed=4.80),
        now_utc=datetime(2026, 11, 22, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res_jump.ok is True
    assert any(a.code == "price_jump_rejected" and a.scope == "AE" for a in res_jump.alerts)
    assert load_prices_lockfile(lock_path).countries["AE"].local_prices["diesel"] == pytest.approx(
        2.67
    )


def test_cli_no_tier2_flag_skips_all_tier2_portals(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    lock_path = tmp_path / "prices.lock.json"

    import ets2_realism.fetch.pipeline as pipeline_mod

    orig_create = pipeline_mod.create_http_client

    def _patched_create(
        *, timeout: float = 20.0, transport: httpx.BaseTransport | None = None
    ) -> httpx.Client:
        return orig_create(timeout=timeout, transport=transport or _pipeline_transport())

    monkeypatch.setattr(pipeline_mod, "create_http_client", _patched_create)
    exit_code = main(
        [
            "fetch",
            "--no-global",
            "--no-tier2",
            "--lock-path",
            str(lock_path),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--dry-run",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["tier2_feeds_succeeded"] == 0
    assert payload["tier2_feeds_failed"] == 0
    providers = {s["provider"] for s in payload["provider_statuses"]}
    assert "ae_moei" not in providers
    assert "is_gasvaktin" not in providers
    assert "za_dmre_cef" not in providers


def test_run_price_fetch_preserves_curated_tier3_petrol_and_verified_date_hi01(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HI-01: Repricing/bootstrapping Tier 3 territories must preserve curated petrol_95 & date."""
    from ets2_realism.normalize.currencies import load_tier3_fuel_baselines
    from ets2_realism.normalize.fuel import round_local_price

    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("OPINET_API_KEY", raising=False)
    baselines = load_tier3_fuel_baselines().baselines

    # 1. Repricing an existing committed lockfile preserves exact curated diesel & petrol_95
    reprice_lock = tmp_path / "reprice.lock.json"
    reprice_lock.write_bytes(COMMITTED_LOCK_PATH.read_bytes())
    res_reprice = run_price_fetch(
        lock_path=reprice_lock,
        baseline_dir=BASELINE_DIR,
        include_global=False,
        include_tier2=False,
        write_lock=True,
        transport=_pipeline_transport(),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res_reprice.ok is True
    after_reprice = load_prices_lockfile(reprice_lock)
    for iso2 in ("IR", "VE", "US", "BN", "CA", "CG"):
        t3 = baselines[iso2]
        entry = after_reprice.countries[iso2]
        rate = after_reprice.fx_rates[entry.currency].rate_per_eur
        assert entry.eur_per_liter == pytest.approx(t3.diesel_eur_per_liter)
        assert entry.local_prices["petrol_95"] == pytest.approx(
            round_local_price(t3.petrol_95_eur_per_liter * rate)
        )
    # US and CA remain petrol-cheaper-than-diesel (never inverted by * 1.03)
    assert (
        after_reprice.countries["US"].local_prices["petrol_95"]
        < after_reprice.countries["US"].local_prices["diesel"]
    )
    assert (
        after_reprice.countries["CA"].local_prices["petrol_95"]
        < after_reprice.countries["CA"].local_prices["diesel"]
    )

    # 2. Bootstrapping a fresh lockfile preserves exact curated petrol_95 & verified_date
    fresh_lock = tmp_path / "fresh.lock.json"
    res_fresh = run_price_fetch(
        lock_path=fresh_lock,
        baseline_dir=BASELINE_DIR,
        include_global=False,
        include_tier2=False,
        write_lock=True,
        transport=_pipeline_transport(),
        now_utc=datetime(2026, 11, 20, 6, 0, 0, tzinfo=UTC),
        sleep_fn=lambda _: None,
    )
    assert res_fresh.ok is True
    after_fresh = load_prices_lockfile(fresh_lock)
    for iso2 in ("IR", "VE", "US", "BN"):
        t3 = baselines[iso2]
        entry = after_fresh.countries[iso2]
        rate = after_fresh.fx_rates[entry.currency].rate_per_eur
        assert entry.data_date == t3.verified_date
        assert entry.local_prices["petrol_95"] == pytest.approx(
            round_local_price(t3.petrol_95_eur_per_liter * rate)
        )


def test_cli_fetch_human_output_includes_global_tier1_and_tier2_counts_in02(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """IN-02: Human-readable fetch stdout includes global_tier1= and tier2= counters."""
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    import ets2_realism.fetch.pipeline as pipeline_mod

    orig_create = pipeline_mod.create_http_client

    def _patched_create(
        *, timeout: float = 20.0, transport: httpx.BaseTransport | None = None
    ) -> httpx.Client:
        return orig_create(timeout=timeout, transport=transport or _pipeline_transport())

    monkeypatch.setattr(pipeline_mod, "create_http_client", _patched_create)
    rc = main(
        [
            "fetch",
            "--no-global",
            "--no-tier2",
            "--lock-path",
            str(tmp_path / "prices.lock.json"),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--dry-run",
        ]
    )
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    assert "global_tier1=" in cap.out
    assert "tier2=" in cap.out
