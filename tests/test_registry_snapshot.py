"""Unit, contract, determinism, and CLI tests for schema_version=1 realism snapshots."""

from __future__ import annotations

import json
import pathlib
from datetime import date
from typing import cast

import pytest
from pydantic import ValidationError

from ets2v2.baseline.models import CountriesBaseline, LocalesBaseline
from ets2v2.cli import main
from ets2v2.registry import load_law_registry
from ets2v2.registry.snapshot import (
    RealismSnapshot,
    RealismSnapshotCountry,
    RealismSnapshotFuel,
    build_realism_snapshot,
    serialize_snapshot_bytes,
    write_realism_snapshot,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"

EXPECTED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {"schema_version", "edition", "anchor_date", "baseline_game_version", "countries"}
)
EXPECTED_COUNTRY_KEYS: frozenset[str] = frozenset(
    {
        "iso2",
        "iso3",
        "ets2_slug",
        "iana_timezone",
        "time_zone",
        "time_zone_name",
        "observes_dst",
        "lights_mandatory",
        "driving_tired_offence",
        "imperial_units",
        "mass_limit_per_axle_count",
        "speed_limits",
        "fuel",
    }
)
EXPECTED_FUEL_KEYS: frozenset[str] = frozenset(
    {"currency", "eur_per_liter", "local_prices", "source"}
)


def _load_inputs() -> tuple[CountriesBaseline, LocalesBaseline]:
    countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    return countries, locales


def test_build_summer_and_winter_snapshots_against_committed_data() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()
    bl_by_slug = {c.slug: c for c in bl_countries.countries}

    summer = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")
    winter = build_realism_snapshot(registry, bl_countries, bl_locales, "winter")

    assert summer.schema_version == 1
    assert winter.schema_version == 1
    assert summer.edition == "summer"
    assert winter.edition == "winter"
    assert summer.anchor_date == "2026-07-15"
    assert winter.anchor_date == "2026-01-15"
    assert summer.baseline_game_version == "1.62.3.3"
    assert winter.baseline_game_version == "1.62.3.3"

    assert len(summer.countries) == 36
    assert len(winter.countries) == 36
    assert list(summer.countries.keys()) == sorted(summer.countries.keys())
    assert set(summer.countries.keys()) == set(winter.countries.keys())

    # Croatia seasonal DRL (Nov 1 - Mar 31 only)
    assert summer.countries["HR"].lights_mandatory is False
    assert winter.countries["HR"].lights_mandatory is True

    # Finland, Estonia, Lithuania seasonal car speed differences
    assert [lane.limit for lane in summer.countries["FI"].speed_limits["car"]] == [80, 100, 120]
    assert [lane.limit for lane in winter.countries["FI"].speed_limits["car"]] == [80, 80, 100]
    assert [lane.limit for lane in summer.countries["EE"].speed_limits["car"]] == [90, 110, 110]
    assert [lane.limit for lane in winter.countries["EE"].speed_limits["car"]] == [90, 90, 90]
    assert [lane.limit for lane in summer.countries["LT"].speed_limits["car"]] == [90, 120, 130]
    assert [lane.limit for lane in winter.countries["LT"].speed_limits["car"]] == [90, 110, 110]

    # Iceland heavy truck 80 km/h limit and 5-element 60t axle ladder
    iceland = summer.countries["IS"]
    assert [lane.limit for lane in iceland.speed_limits["truck"]] == [80, 80, 80]
    assert iceland.mass_limit_per_axle_count == [18000, 29000, 38000, 46000, 60000]

    # Seasonal timezone transitions embedded per country
    assert summer.countries["DE"].time_zone == 120
    assert summer.countries["DE"].time_zone_name == "@@tz_cest@@"
    assert summer.countries["DE"].observes_dst is True
    assert winter.countries["DE"].time_zone == 60
    assert winter.countries["DE"].time_zone_name == "CET"
    assert winter.countries["DE"].observes_dst is True

    assert summer.countries["PT"].time_zone == 60
    assert summer.countries["PT"].time_zone_name == "@@tz_west@@"
    assert winter.countries["PT"].time_zone == 0
    assert winter.countries["PT"].time_zone_name == "WET"

    assert summer.countries["TR"].time_zone == 180
    assert summer.countries["TR"].time_zone_name == "@@tz_trt@@"
    assert summer.countries["TR"].observes_dst is False
    assert winter.countries["TR"].time_zone == 180
    assert winter.countries["TR"].time_zone_name == "@@tz_trt@@"

    # UK imperial units and baseline 1.62 fuel price preservation across all 36 countries (D-05)
    for iso2, country in summer.countries.items():
        assert isinstance(country, RealismSnapshotCountry)
        assert isinstance(country.fuel, RealismSnapshotFuel)
        bl = bl_by_slug[country.ets2_slug]
        assert country.imperial_units is (iso2 == "GB")
        assert country.fuel.source == "baseline_1.62"
        assert country.fuel.local_prices == {}
        assert country.fuel.eur_per_liter == bl.fuel_price
        assert winter.countries[iso2].fuel == country.fuel


def test_serialize_snapshot_bytes_is_deterministic_canonical_and_round_trips(
    tmp_path: pathlib.Path,
) -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()

    snap_a = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")
    snap_b = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")

    bytes_a = serialize_snapshot_bytes(snap_a)
    bytes_b = serialize_snapshot_bytes(snap_b)
    assert bytes_a == bytes_b
    assert not bytes_a.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in bytes_a
    assert bytes_a.endswith(b"\n")

    # Verify locked D-11 v1 JSON keys exactly (no stray fields or wall-clock timestamps)
    raw_obj = cast(dict[str, object], json.loads(bytes_a.decode("utf-8")))
    assert set(raw_obj.keys()) == EXPECTED_TOP_LEVEL_KEYS
    raw_countries = cast(dict[str, dict[str, object]], raw_obj["countries"])
    assert len(raw_countries) == 36
    sample_country = raw_countries["DE"]
    assert set(sample_country.keys()) == EXPECTED_COUNTRY_KEYS
    sample_fuel = cast(dict[str, object], sample_country["fuel"])
    assert set(sample_fuel.keys()) == EXPECTED_FUEL_KEYS

    # Strict Pydantic JSON round-trip
    restored = RealismSnapshot.model_validate_json(bytes_a.decode("utf-8"))
    assert restored == snap_a

    # write_realism_snapshot creates parent dirs and writes identical bytes
    out_file = tmp_path / "nested" / "realism-snapshot-summer.json"
    written = write_realism_snapshot(snap_a, out_file)
    assert written == bytes_a
    assert out_file.read_bytes() == bytes_a


def test_snapshot_schema_enforces_locked_v1_and_forbids_missing_fuel_price() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()

    snap = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        "winter",
        override_date=date(2026, 7, 15),
    )
    assert snap.edition == "winter"
    assert snap.anchor_date == "2026-07-15"
    assert snap.countries["DE"].time_zone == 120
    assert snap.countries["DE"].time_zone_name == "@@tz_cest@@"

    raw_payload = cast(
        dict[str, object], json.loads(serialize_snapshot_bytes(snap).decode("utf-8"))
    )
    raw_payload["schema_version"] = 2
    with pytest.raises(ValidationError):
        RealismSnapshot.model_validate_json(json.dumps(raw_payload))

    raw_payload["schema_version"] = 1
    raw_payload["generated_at"] = "2026-11-19T00:00:00Z"
    with pytest.raises(ValidationError):
        RealismSnapshot.model_validate_json(json.dumps(raw_payload))

    # Missing baseline fuel_price must fail loudly
    corrupted_countries = [
        c.model_copy(update={"fuel_price": None}) if c.slug == "germany" else c
        for c in bl_countries.countries
    ]
    with pytest.raises(ValueError, match="fuel_price"):
        build_realism_snapshot(
            registry,
            CountriesBaseline(countries=corrupted_countries),
            bl_locales,
            "summer",
        )


def test_cli_registry_snapshot_winter_date_override_and_invalid_date(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    winter_out = tmp_path / "realism-snapshot-winter.json"
    exit_code = main(
        [
            "registry",
            "snapshot",
            "--season",
            "winter",
            "--out",
            str(winter_out),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "36 countries" in captured.out
    assert winter_out.is_file()

    loaded_winter = RealismSnapshot.model_validate_json(winter_out.read_text("utf-8"))
    assert loaded_winter.schema_version == 1
    assert loaded_winter.edition == "winter"
    assert loaded_winter.anchor_date == "2026-01-15"
    assert loaded_winter.countries["HR"].lights_mandatory is True
    assert loaded_winter.countries["DE"].time_zone == 60
    assert loaded_winter.countries["DE"].time_zone_name == "CET"

    # Explicit --date override (D-03)
    override_out = tmp_path / "realism-snapshot-override.json"
    exit_override = main(
        [
            "registry",
            "snapshot",
            "--season",
            "winter",
            "--date",
            "2026-07-15",
            "--out",
            str(override_out),
        ]
    )
    _ = capsys.readouterr()
    assert exit_override == 0
    loaded_override = RealismSnapshot.model_validate_json(override_out.read_text("utf-8"))
    assert loaded_override.anchor_date == "2026-07-15"
    assert loaded_override.countries["DE"].time_zone == 120
    assert loaded_override.countries["DE"].time_zone_name == "@@tz_cest@@"

    # Invalid --date returns exit code 1 with stderr diagnostic
    bad_out = tmp_path / "should-not-exist.json"
    exit_bad = main(
        [
            "registry",
            "snapshot",
            "--season",
            "summer",
            "--date",
            "not-a-date",
            "--out",
            str(bad_out),
        ]
    )
    bad_captured = capsys.readouterr()
    assert exit_bad == 1
    assert "error:" in bad_captured.err
    assert not bad_out.exists()


def test_build_realism_snapshot_with_prices_lock_emits_76_territories_and_preserves_v1(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ets2v2.normalize.lockfile import seed_initial_lockfile, write_prices_lockfile
    from ets2v2.normalize.models import CANONICAL_FUEL_GRADES

    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()
    lock = seed_initial_lockfile(bl_countries)
    assert len(lock.countries) == 76
    assert {"IE", "CY", "MT", "KZ", "UZ", "JO", "SY", "MA", "GL"} <= set(lock.countries.keys())

    # Override DE with an exact 3-decimal EUR/L and live national source to verify injection
    de_live = lock.countries["DE"].model_copy(
        update={
            "eur_per_liter": 1.659,
            "source": "de_tankerkoenig",
            "fallback_used": False,
        }
    )
    custom_lock = lock.model_copy(update={"countries": {**lock.countries, "DE": de_live}})

    snap = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        "summer",
        prices_lock=custom_lock,
    )
    snap_winter = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        "winter",
        prices_lock=custom_lock,
    )
    assert snap.schema_version == 1
    assert len(snap.countries) == 76
    assert len(snap_winter.countries) == 76
    assert {"IE", "CY", "MT", "KZ", "UZ", "JO", "SY", "GL", "GG", "GI", "IM", "JE"} <= set(
        snap.countries.keys()
    )

    # imperial_units derived strictly for non-vanilla territories (D-02)
    imperial_iso2s = {iso2 for iso2, c in snap.countries.items() if c.imperial_units}
    assert imperial_iso2s == {"GB", "GG", "IM", "JE"}
    assert snap.countries["GI"].imperial_units is False

    # ProMods seasonal timezones resolved accurately via zoneinfo + overrides
    assert snap.countries["GL"].time_zone_name == "WGST"
    assert snap_winter.countries["GL"].time_zone_name == "WGT"
    assert snap.countries["UZ"].time_zone == 300
    assert snap.countries["UZ"].time_zone_name == "UZT"
    assert snap.countries["KZ"].time_zone == 300
    assert snap.countries["KZ"].time_zone_name == "AQTT"
    assert snap.countries["JO"].time_zone == 180
    assert snap.countries["JO"].time_zone_name == "AST"
    assert snap.countries["SY"].time_zone == 180
    assert snap.countries["SY"].time_zone_name == "AST"

    assert snap.countries["DE"].fuel.eur_per_liter == 1.659
    assert snap.countries["DE"].fuel.source == "de_tankerkoenig"
    assert snap.countries["DE"].fuel.currency == "EUR"
    assert set(snap.countries["DE"].fuel.local_prices.keys()) == set(CANONICAL_FUEL_GRADES)

    # Verify locked schema_version=1 JSON keys (extra="forbid" D-02)
    raw_obj = cast(dict[str, object], json.loads(serialize_snapshot_bytes(snap).decode("utf-8")))
    assert set(raw_obj.keys()) == EXPECTED_TOP_LEVEL_KEYS
    raw_countries = cast(dict[str, dict[str, object]], raw_obj["countries"])
    assert len(raw_countries) == 76
    assert set(raw_countries["DE"].keys()) == EXPECTED_COUNTRY_KEYS
    assert set(raw_countries["KZ"].keys()) == EXPECTED_COUNTRY_KEYS
    assert set(cast(dict[str, object], raw_countries["DE"]["fuel"]).keys()) == EXPECTED_FUEL_KEYS

    # CLI: ets2v2 registry snapshot --prices-lock ...
    lock_file = tmp_path / "prices.lock.json"
    write_prices_lockfile(custom_lock, lock_file)
    snap_out = tmp_path / "snap-with-prices.json"
    exit_code = main(
        [
            "registry",
            "snapshot",
            "--season",
            "summer",
            "--prices-lock",
            str(lock_file),
            "--out",
            str(snap_out),
        ]
    )
    _ = capsys.readouterr()
    assert exit_code == 0
    restored = RealismSnapshot.model_validate_json(snap_out.read_text("utf-8"))
    assert restored == snap


def test_timezone_overrides_cover_promods_numeric_zones_and_seasonal_nuuk() -> None:
    from ets2v2.registry.timezone import resolve_ets2_timezone

    _, bl_locales = _load_inputs()
    tz_keys = bl_locales.tz_keys

    nuuk_winter = resolve_ets2_timezone("America/Nuuk", date(2026, 1, 15), tz_keys)
    nuuk_summer = resolve_ets2_timezone("America/Nuuk", date(2026, 7, 15), tz_keys)
    assert nuuk_winter.abbreviation == "WGT"
    assert nuuk_winter.ets2_time_zone_name == "WGT"
    assert nuuk_winter.offset_minutes == -120
    assert nuuk_winter.is_dst is False
    assert nuuk_winter.observes_dst is True
    assert nuuk_summer.abbreviation == "WGST"
    assert nuuk_summer.ets2_time_zone_name == "WGST"
    assert nuuk_summer.offset_minutes == -60
    assert nuuk_summer.is_dst is True

    uz = resolve_ets2_timezone("Asia/Tashkent", date(2026, 7, 15), tz_keys)
    assert uz.offset_minutes == 300
    assert uz.ets2_time_zone_name == "UZT"

    kz = resolve_ets2_timezone("Asia/Almaty", date(2026, 7, 15), tz_keys)
    assert kz.offset_minutes == 300
    assert kz.ets2_time_zone_name == "AQTT"

    for zone in ("Asia/Baghdad", "Asia/Riyadh", "Asia/Amman", "Asia/Damascus"):
        resolved = resolve_ets2_timezone(zone, date(2026, 7, 15), tz_keys)
        assert resolved.offset_minutes == 180
        assert resolved.ets2_time_zone_name == "AST"

    ma = resolve_ets2_timezone("Africa/Casablanca", date(2026, 7, 15), tz_keys)
    assert ma.offset_minutes == 60
    assert ma.ets2_time_zone_name == "@@tz_west@@"


def test_sha256sums_verify_snapshot_file_and_sibling_auto_verification(
    tmp_path: pathlib.Path,
) -> None:
    from ets2v2.registry.snapshot import (
        load_realism_snapshot,
        parse_sha256sums,
        render_sha256sums,
        verify_snapshot_file,
        write_sha256sums,
    )

    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries, bl_locales = _load_inputs()

    summer = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")
    winter = build_realism_snapshot(registry, bl_countries, bl_locales, "winter")

    snap_dir = tmp_path / "snapshots"
    summer_path = snap_dir / "realism-snapshot-summer.json"
    winter_path = snap_dir / "realism-snapshot-winter.json"
    write_realism_snapshot(summer, summer_path)
    write_realism_snapshot(winter, winter_path)

    assert load_realism_snapshot(summer_path) == summer

    sums_path = snap_dir / "SHA256SUMS.txt"
    rendered = render_sha256sums([winter_path, summer_path])
    written = write_sha256sums([winter_path, summer_path], sums_path)
    assert rendered == written
    assert not written.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in written
    lines = written.decode("utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("  realism-snapshot-summer.json")
    assert lines[1].endswith("  realism-snapshot-winter.json")

    parsed = parse_sha256sums(sums_path)
    assert set(parsed.keys()) == {
        "realism-snapshot-summer.json",
        "realism-snapshot-winter.json",
    }

    # Explicit checksums verification succeeds
    res_explicit = verify_snapshot_file(
        summer_path,
        checksums_path=sums_path,
        expected_edition="summer",
    )
    assert res_explicit.ok is True
    assert res_explicit.checksum_verified is True
    assert res_explicit.schema_version == 1
    assert res_explicit.edition == "summer"
    assert res_explicit.issues == []

    # Sibling SHA256SUMS.txt auto-verification when checksums_path=None (D-04)
    res_sibling = verify_snapshot_file(summer_path, expected_edition="summer")
    assert res_sibling.ok is True
    assert res_sibling.checksum_verified is True

    # Edition mismatch fails loudly
    res_wrong_ed = verify_snapshot_file(summer_path, expected_edition="winter")
    assert res_wrong_ed.ok is False
    assert any("edition" in issue.lower() for issue in res_wrong_ed.issues)

    # Tampered snapshot fails sibling auto-verification loudly
    original_bytes = summer_path.read_bytes()
    summer_path.write_bytes(original_bytes.replace(b'"2026-07-15"', b'"2026-07-16"'))
    res_tampered = verify_snapshot_file(summer_path)
    assert res_tampered.ok is False
    assert res_tampered.checksum_verified is False
    assert any(
        "sha-256" in issue.lower() or "mismatch" in issue.lower() for issue in res_tampered.issues
    )
    summer_path.write_bytes(original_bytes)

    # Missing entry in checksums fails loudly
    other_sums = tmp_path / "other_sums.txt"
    write_sha256sums([winter_path], other_sums)
    res_missing_entry = verify_snapshot_file(summer_path, checksums_path=other_sums)
    assert res_missing_entry.ok is False
    assert any("not found" in issue.lower() for issue in res_missing_entry.issues)

    # Reject BOM, CRLF, and schema_version=2
    no_sibling_dir = tmp_path / "isolated"
    no_sibling_dir.mkdir()
    bom_snap = no_sibling_dir / "bom.json"
    bom_snap.write_bytes(b"\xef\xbb\xbf" + original_bytes)
    assert verify_snapshot_file(bom_snap).ok is False

    crlf_snap = no_sibling_dir / "crlf.json"
    crlf_snap.write_bytes(original_bytes.replace(b"\n", b"\r\n"))
    assert verify_snapshot_file(crlf_snap).ok is False

    v2_snap = no_sibling_dir / "v2.json"
    v2_snap.write_bytes(original_bytes.replace(b'"schema_version": 1', b'"schema_version": 2'))
    assert verify_snapshot_file(v2_snap).ok is False

    # parse_sha256sums rejects path separators, BOM, CRLF, and duplicate filenames
    bad_sep = tmp_path / "bad_sep.txt"
    bad_sep.write_bytes(f"{'a' * 64}  ../evil.json\n".encode())
    with pytest.raises(ValueError):
        parse_sha256sums(bad_sep)

    bad_dup = tmp_path / "bad_dup.txt"
    bad_dup.write_bytes(f"{'a' * 64}  snap.json\n{'b' * 64}  snap.json\n".encode())
    with pytest.raises(ValueError, match="Duplicate"):
        parse_sha256sums(bad_dup)


def test_load_or_build_snapshot_and_cli_snapshot_verify(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ets2v2.registry.snapshot import load_or_build_snapshot, write_sha256sums

    # Offline repo checkout fallback (snapshot_path=None)
    fallback_snap = load_or_build_snapshot(
        "summer",
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        prices_lock_path=REPO_ROOT / "state" / "prices.lock.json",
    )
    assert fallback_snap.schema_version == 1
    assert fallback_snap.edition == "summer"

    # Explicit snapshot + sibling SHA256SUMS.txt auto-verification
    snap_dir = tmp_path / "snaps"
    snap_path = snap_dir / "realism-snapshot-summer.json"
    sums_path = snap_dir / "SHA256SUMS.txt"
    write_realism_snapshot(fallback_snap, snap_path)
    write_sha256sums([snap_path], sums_path)

    loaded_explicit = load_or_build_snapshot(
        "summer",
        snapshot_path=snap_path,
        checksums_path=sums_path,
    )
    assert loaded_explicit == fallback_snap

    loaded_sibling = load_or_build_snapshot("summer", snapshot_path=snap_path)
    assert loaded_sibling == fallback_snap

    # CLI tracer: ets2v2 registry snapshot-verify -> exit 0 with JSON output
    exit_ok = main(
        [
            "registry",
            "snapshot-verify",
            str(snap_path),
            "--checksums",
            str(sums_path),
            "--expected-edition",
            "summer",
            "--json",
        ]
    )
    out_ok = capsys.readouterr()
    assert exit_ok == 0
    report_ok = cast(dict[str, object], json.loads(out_ok.out))
    assert report_ok["ok"] is True
    assert report_ok["checksum_verified"] is True
    assert report_ok["schema_version"] == 1
    assert report_ok["edition"] == "summer"

    # Tampered snapshot -> load_or_build_snapshot raises ValueError & CLI exits 1
    snap_path.write_bytes(snap_path.read_bytes().replace(b'"2026-07-15"', b'"2026-07-16"'))
    with pytest.raises(ValueError, match="verification failed"):
        load_or_build_snapshot("summer", snapshot_path=snap_path)

    exit_bad = main(
        [
            "registry",
            "snapshot-verify",
            str(snap_path),
            "--checksums",
            str(sums_path),
            "--expected-edition",
            "summer",
            "--json",
        ]
    )
    out_bad = capsys.readouterr()
    assert exit_bad == 1
    report_bad = cast(dict[str, object], json.loads(out_bad.out))
    assert report_bad["ok"] is False
    assert report_bad["checksum_verified"] is False
