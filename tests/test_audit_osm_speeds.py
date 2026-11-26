"""Offline tests for post_form_bytes_with_retry, OSM speed drift audit, Overpass/Taginfo & CLI."""

from __future__ import annotations

import json
import pathlib
from typing import cast

import httpx
import pytest
from pydantic import ValidationError

from ets2v2.audit import (
    DEFAULT_WESTNORDOST_RULES_URL,
    MAX_OVERPASS_ISO2S,
    OsmSpeedAuditReport,
    SpeedAuditAllowlist,
    fetch_overpass_speed_spot_checks,
    fetch_taginfo_maxspeed_distributions,
    load_speed_audit_allowlist,
    render_osm_speed_drift_markdown,
    run_osm_speed_audit,
)
from ets2v2.audit.overpass import build_overpass_speed_query
from ets2v2.audit.taint import scan_repo_and_artifacts_for_taint
from ets2v2.cli import main
from ets2v2.fetch.http import (
    HttpFetchError,
    create_http_client,
    post_form_bytes_with_retry,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
ALLOWLIST_PATH = LAWS_DIR / "speed_audit_allowlist.json"


def _sample_westnordost_payload() -> dict[str, object]:
    """Realistic offline mock of westnordost/osm-legal-default-speeds JSON."""
    return {
        "meta": {"source": "mock-test-fixture"},
        "speedLimitsByCountryCode": {
            # DE: motorway car "130" (advisory) vs law 0 -> allowlisted!
            # DE: local_road/motorway truck & bus match cleanly
            "DE": [
                {
                    "name": "urban",
                    "filter": "urban=true",
                    "tags": {"maxspeed": "50", "maxspeed:hgv": "50", "maxspeed:bus": "50"},
                },
                {
                    "name": "rural",
                    "filter": "urban=false",
                    "tags": {"maxspeed": "100", "maxspeed:hgv": "60", "maxspeed:bus": "80"},
                },
                {
                    "name": "motorway",
                    "filter": "highway=motorway",
                    "tags": {"maxspeed": "130", "maxspeed:hgv": "80", "maxspeed:bus": "100"},
                },
            ],
            # FR: exact match on urban, rural, expressway, motorway
            "FR": [
                {
                    "name": "urban",
                    "filter": "urban=true",
                    "tags": {"maxspeed": "50", "maxspeed:hgv": "50", "maxspeed:bus": "50"},
                },
                {
                    "name": "rural",
                    "filter": "urban=false",
                    "tags": {"maxspeed": "80", "maxspeed:hgv": "80", "maxspeed:bus": "80"},
                },
                {
                    "name": "trunk",
                    "filter": "motorroad=yes",
                    "tags": {"maxspeed": "110", "maxspeed:hgv": "80", "maxspeed:bus": "90"},
                },
                {
                    "name": "motorway",
                    "filter": "highway=motorway",
                    "tags": {"maxspeed": "130", "maxspeed:hgv": "90", "maxspeed:bus": "100"},
                },
            ],
            # US: mph values matching us.json (35 / 55 / 65 / 70 car; 65 truck motorway)
            # Sub-national US-CA must be ignored when comparing country-level US
            "US": [
                {
                    "name": "urban",
                    "filter": "urban=true",
                    "tags": {"maxspeed": "35 mph", "maxspeed:hgv": "35 mph"},
                },
                {
                    "name": "rural",
                    "filter": "urban=false",
                    "tags": {"maxspeed": "55 mph", "maxspeed:hgv": "55 mph"},
                },
                {
                    "name": "trunk",
                    "filter": "highway=trunk",
                    "tags": {"maxspeed": "65 mph", "maxspeed:hgv": "65 mph"},
                },
                {
                    "name": "motorway",
                    "filter": "highway=motorway",
                    "tags": {"maxspeed": "70 mph", "maxspeed:hgv": "65 mph"},
                },
                {
                    "name": "living_street",
                    "filter": "highway=living_street",
                    "tags": {"maxspeed": "walk"},
                },
            ],
            "US-CA": [
                {
                    "name": "motorway",
                    "filter": "highway=motorway",
                    "tags": {"maxspeed": "65 mph", "maxspeed:hgv": "55 mph"},
                },
            ],
            # PL: intentional synthetic mismatch on motorway car (130 vs 140 in pl.json)
            # plus injected HTML/backtick payload in raw value to verify Markdown sanitization
            "PL": [
                {
                    "name": "urban",
                    "filter": "urban=true",
                    "tags": {"maxspeed": "50"},
                },
                {
                    "name": "motorway",
                    "filter": "highway=motorway",
                    "tags": {"maxspeed": "130 @ (<script>`evil`</script>)"},
                },
            ],
        },
    }


def test_post_form_bytes_with_retry_allowlist_retries_cap_and_redaction() -> None:
    """post_form_bytes_with_retry enforces HTTPS allowlist, retries 429/503, byte cap & scrub."""
    calls: list[str] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(429, text="rate limited")
        if len(calls) == 2:
            return httpx.Response(503, text="busy")
        if "oversized" in str(request.url):
            return httpx.Response(200, content=b"x" * 2048)
        if "secretfail" in str(request.url):
            return httpx.Response(400, text="bad request")
        return httpx.Response(200, content=b'{"ok":true}')

    client = create_http_client(transport=httpx.MockTransport(handler))
    try:
        allowed = frozenset({"overpass-api.de"})
        raw = post_form_bytes_with_retry(
            client,
            "https://overpass-api.de/api/interpreter",
            allowed_hosts=allowed,
            data={"data": "[out:json];out tags 1;"},
            sleep_fn=sleeps.append,
        )
        assert raw == b'{"ok":true}'
        assert len(calls) == 3
        assert len(sleeps) == 2

        # Disallowed host rejected before transport
        with pytest.raises(ValueError, match="allowlist"):
            post_form_bytes_with_retry(
                client,
                "https://evil.example/api/interpreter",
                allowed_hosts=allowed,
                data={"data": "test"},
                sleep_fn=lambda _s: None,
            )

        # Plain HTTP rejected
        with pytest.raises(ValueError, match="HTTPS"):
            post_form_bytes_with_retry(
                client,
                "http://overpass-api.de/api/interpreter",
                allowed_hosts=allowed,
                data={"data": "test"},
                sleep_fn=lambda _s: None,
            )

        # Byte cap enforced
        with pytest.raises(ValueError, match="max_bytes"):
            post_form_bytes_with_retry(
                client,
                "https://overpass-api.de/api/oversized",
                allowed_hosts=allowed,
                data={"data": "test"},
                max_bytes=512,
                sleep_fn=lambda _s: None,
            )

        # Secret query parameters redacted on HTTP errors
        with pytest.raises(HttpFetchError) as exc_info:
            post_form_bytes_with_retry(
                client,
                "https://overpass-api.de/api/secretfail?api_key=TOPSECRET123&code=HIDE456",
                allowed_hosts=allowed,
                data={"data": "test"},
                sleep_fn=lambda _s: None,
            )
        err_msg = str(exc_info.value)
        assert "TOPSECRET123" not in err_msg
        assert "HIDE456" not in err_msg
        assert "api_key=***" in err_msg
        assert "code=***" in err_msg
    finally:
        client.close()


def test_committed_speed_audit_allowlist_schema_hygiene_and_zero_taint(
    tmp_path: pathlib.Path,
) -> None:
    """data/laws/speed_audit_allowlist.json is canonical UTF-8 no-BOM LF JSON with zero taint."""
    assert ALLOWLIST_PATH.is_file(), "data/laws/speed_audit_allowlist.json must exist"
    raw = ALLOWLIST_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw

    allowlist = load_speed_audit_allowlist(ALLOWLIST_PATH)
    assert isinstance(allowlist, SpeedAuditAllowlist)
    assert allowlist.schema_version == 1
    assert len(allowlist.entries) >= 5

    # Must contain DE Autobahn car motorway limit allowlist entry
    keys = {entry.match_key() for entry in allowlist.entries}
    assert ("DE", "car", "motorway", "limit") in keys
    assert ("FI", "car", "motorway", "limit") in keys
    assert ("IM", "car", "local_road", "limit") in keys

    # Verify zero taint markers on allowlist via repo taint scanner
    taint_report = scan_repo_and_artifacts_for_taint(REPO_ROOT)
    assert taint_report.ok is True, taint_report.violations

    # Negative schema checks: extra field & invalid field value rejected
    bad_extra = tmp_path / "bad_extra.json"
    bad_extra.write_bytes(
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "entries": [
                        {
                            "iso2": "DE",
                            "vehicle_class": "car",
                            "lane_speed_class": "motorway",
                            "field": "limit",
                            "statutory_rationale": "Test",
                            "verified_date": "2026-11-25",
                            "osm_quote": "forbidden extra field",
                        }
                    ],
                }
            )
            + "\n"
        ).encode("utf-8")
    )
    with pytest.raises(ValidationError):
        load_speed_audit_allowlist(bad_extra)

    bad_field = tmp_path / "bad_field.json"
    bad_field.write_bytes(
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "entries": [
                        {
                            "iso2": "DE",
                            "vehicle_class": "car",
                            "lane_speed_class": "motorway",
                            "field": "invalid_field",
                            "statutory_rationale": "Test",
                            "verified_date": "2026-11-25",
                        }
                    ],
                }
            )
            + "\n"
        ).encode("utf-8")
    )
    with pytest.raises(ValidationError):
        load_speed_audit_allowlist(bad_field)


def test_run_osm_speed_audit_splits_allowlist_and_sanitizes_markdown(
    tmp_path: pathlib.Path,
) -> None:
    """run_osm_speed_audit compares rules vs data/laws/, splits allowlist, and sanitizes MD."""
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(_sample_westnordost_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = run_osm_speed_audit(
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        allowlist_path=ALLOWLIST_PATH,
        rules_file=rules_path,
        iso2_filter=["DE", "FR", "US", "PL"],
    )
    assert isinstance(report, OsmSpeedAuditReport)
    assert report.countries_checked == 4
    assert report.countries_matched_in_osm == 4
    assert report.countries_missing_in_osm == []

    # DE car motorway limit (law=0 vs osm=130) is allowlisted -> acknowledged_differences
    ack_keys = {
        (f.iso2, f.vehicle_class, f.lane_speed_class, f.field)
        for f in report.acknowledged_differences
    }
    assert ("DE", "car", "motorway", "limit") in ack_keys
    assert report.acknowledged_difference_count == len(report.acknowledged_differences)

    # FR & US match cleanly -> zero unacknowledged findings for FR/US
    unack_keys = {
        (f.iso2, f.vehicle_class, f.lane_speed_class, f.field) for f in report.unacknowledged_drifts
    }
    assert ("PL", "car", "motorway", "limit") in unack_keys
    assert all(f.iso2 not in {"FR", "US"} for f in report.unacknowledged_drifts)
    assert report.unacknowledged_drift_count == len(report.unacknowledged_drifts)

    # Markdown report neutralizes injected <script> & backticks
    md = render_osm_speed_drift_markdown(report)
    assert "## Unacknowledged Drift" in md
    assert "## Acknowledged Statutory Differences" in md
    assert "<script>" not in md
    assert "&lt;script&gt;" in md
    assert "`evil`" not in md
    assert "\r" not in md

    # Online rules-url path works via MockTransport and enforces host allowlist
    payload_bytes = json.dumps(_sample_westnordost_payload()).encode("utf-8")

    def rules_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == DEFAULT_WESTNORDOST_RULES_URL
        return httpx.Response(200, content=payload_bytes)

    client = create_http_client(transport=httpx.MockTransport(rules_handler))
    try:
        online_report = run_osm_speed_audit(
            laws_dir=LAWS_DIR,
            mappings_path=MAPPINGS_PATH,
            allowlist_path=ALLOWLIST_PATH,
            rules_url=DEFAULT_WESTNORDOST_RULES_URL,
            iso2_filter=["FR", "US"],
            client=client,
            sleep_fn=lambda _s: None,
        )
        assert online_report.unacknowledged_drift_count == 0
    finally:
        client.close()


def test_overpass_and_taginfo_spot_checks_security_and_modal_counts() -> None:
    """Overpass enforces ^[A-Z]{2}$, <=10 cap, out tags 500;, sleep pacing, and handles 429."""
    # Reject Overpass QL injection and >10 ISO-2 cap
    with pytest.raises(ValueError, match="ISO-2"):
        build_overpass_speed_query('DE"];node;out;//')
    with pytest.raises(ValueError, match="ISO-2"):
        build_overpass_speed_query("de")

    query_de = build_overpass_speed_query("DE")
    assert "out tags 500;" in query_de
    assert "out geom" not in query_de
    assert 'area["ISO3166-1"="DE"][admin_level=2]' in query_de

    seen_queries: list[str] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "overpass-api.de" in url:
            body_text = request.content.decode("utf-8")
            seen_queries.append(body_text)
            if "FR" in body_text:
                return httpx.Response(429, text="Too Many Requests")
            return httpx.Response(
                200,
                json={
                    "elements": [
                        {
                            "type": "way",
                            "id": 1,
                            "tags": {
                                "highway": "motorway",
                                "maxspeed": "none",
                                "maxspeed:hgv": "80",
                                "maxspeed:bus": "100",
                            },
                        },
                        {
                            "type": "way",
                            "id": 2,
                            "tags": {
                                "highway": "motorway",
                                "maxspeed": "none",
                                "maxspeed:hgv": "80",
                            },
                        },
                        {
                            "type": "way",
                            "id": 3,
                            "tags": {
                                "highway": "motorway",
                                "maxspeed": "120",
                                "maxspeed:hgv": "80",
                            },
                        },
                        {
                            "type": "way",
                            "id": 4,
                            "tags": {
                                "highway": "trunk",
                                "maxspeed": "100",
                            },
                        },
                    ]
                },
            )
        if "taginfo.openstreetmap.org" in url:
            key_param = request.url.params.get("key", "maxspeed")
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"value": "50", "count": 500000, "fraction": 0.42},
                        {
                            "value": "80" if "hgv" in key_param else "100",
                            "count": 120000,
                            "fraction": 0.12,
                        },
                    ]
                },
            )
        return httpx.Response(404)

    client = create_http_client(transport=httpx.MockTransport(handler))
    try:
        # Exceeding MAX_OVERPASS_ISO2S (10) raises ValueError
        too_many = [f"{chr(65 + i)}{chr(65 + i)}" for i in range(MAX_OVERPASS_ISO2S + 1)]
        with pytest.raises(ValueError, match="at most"):
            fetch_overpass_speed_spot_checks(client, too_many, sleep_fn=lambda _s: None)

        spots = fetch_overpass_speed_spot_checks(
            client,
            ["DE", "FR"],
            sleep_fn=sleeps.append,
        )
        assert len(spots) == 2
        by_iso2 = {s.iso2: s for s in spots}
        assert by_iso2["DE"].ok is True
        assert by_iso2["DE"].ways_sampled == 4
        assert by_iso2["DE"].top_maxspeed_by_highway["motorway"][0].value == "none"
        assert by_iso2["DE"].top_maxspeed_by_highway["motorway"][0].count == 2
        assert by_iso2["DE"].top_maxspeed_hgv_by_highway["motorway"][0].value == "80"
        assert by_iso2["DE"].top_maxspeed_hgv_by_highway["motorway"][0].count == 3
        assert by_iso2["FR"].ok is False
        assert by_iso2["FR"].error is not None
        assert "429" in by_iso2["FR"].error
        # Polite sleep between countries
        assert any(s >= 1.5 for s in sleeps)
        assert all("out+geom" not in q and "out%20geom" not in q for q in seen_queries)

        dists = fetch_taginfo_maxspeed_distributions(client, sleep_fn=lambda _s: None)
        assert [d.key for d in dists] == ["maxspeed", "maxspeed:hgv", "maxspeed:bus"]
        assert all(d.ok is True for d in dists)
        assert dists[0].values[0].value == "50"
        assert dists[1].values[1].value == "80"
    finally:
        client.close()


def test_cli_audit_osm_speeds_and_taint_end_to_end(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ets2v2 audit osm-speeds & audit taint CLI work end-to-end offline."""
    # Help on bare `audit`
    rc_help = main(["audit"])
    help_out = capsys.readouterr()
    assert rc_help == 0
    assert "osm-speeds" in help_out.out
    assert "taint" in help_out.out

    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(_sample_westnordost_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_md = tmp_path / "drift.md"
    out_json = tmp_path / "drift.json"

    # Without --fail-on-drift -> exit 0 even with PL drift
    rc_ok = main(
        [
            "audit",
            "osm-speeds",
            "--iso2",
            "DE,FR,US,PL",
            "--rules-file",
            str(rules_path),
            "--allowlist",
            str(ALLOWLIST_PATH),
            "--laws-dir",
            str(LAWS_DIR),
            "--mappings",
            str(MAPPINGS_PATH),
            "--out-md",
            str(out_md),
            "--out-json",
            str(out_json),
            "--json",
        ]
    )
    cap_ok = capsys.readouterr()
    assert rc_ok == 0, cap_ok.err
    payload = cast(dict[str, object], json.loads(cap_ok.out))
    assert payload["countries_checked"] == 4
    assert cast(int, payload["unacknowledged_drift_count"]) >= 1
    assert cast(int, payload["acknowledged_difference_count"]) >= 1
    assert out_md.is_file()
    assert out_json.is_file()
    md_bytes = out_md.read_bytes()
    json_bytes = out_json.read_bytes()
    assert not md_bytes.startswith(b"\xef\xbb\xbf") and b"\r" not in md_bytes
    assert not json_bytes.startswith(b"\xef\xbb\xbf") and b"\r" not in json_bytes

    # With --fail-on-drift -> exit 1 when unacknowledged drift exists
    rc_fail = main(
        [
            "audit",
            "osm-speeds",
            "--iso2",
            "PL",
            "--rules-file",
            str(rules_path),
            "--allowlist",
            str(ALLOWLIST_PATH),
            "--laws-dir",
            str(LAWS_DIR),
            "--mappings",
            str(MAPPINGS_PATH),
            "--fail-on-drift",
        ]
    )
    _ = capsys.readouterr()
    assert rc_fail == 1

    # `ets2v2 audit taint --json` exits 0 with zero violations on clean repo
    rc_taint = main(["audit", "taint", "--repo-root", str(REPO_ROOT), "--json"])
    cap_taint = capsys.readouterr()
    assert rc_taint == 0, cap_taint.err
    taint_payload = cast(dict[str, object], json.loads(cap_taint.out))
    assert taint_payload["ok"] is True
    assert taint_payload["violation_count"] == 0
    assert taint_payload["violations"] == []
