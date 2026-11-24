"""Integration tests for Phase A changelog rendering, release orchestration, and CLI wiring."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from ets2v2.baseline.models import CountriesBaseline, LocalesBaseline
from ets2v2.cli import main
from ets2v2.normalize.lockfile import load_prices_lockfile, write_prices_lockfile
from ets2v2.normalize.models import LockAlert
from ets2v2.publish.changelog import render_edition_changelog
from ets2v2.publish.ledger import (
    PublishedLedger,
    load_published_ledger,
    write_published_ledger,
)
from ets2v2.publish.release import (
    PhaseAReleaseSummary,
    run_phase_a_release,
)
from ets2v2.registry.loader import load_law_registry
from ets2v2.registry.snapshot import (
    RealismSnapshot,
    build_realism_snapshot,
    verify_snapshot_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
ICONS_DIR = REPO_ROOT / "assets" / "icons"
COMMITTED_STATE_PATH = REPO_ROOT / "state" / "published.json"


def _copy_laws_tree(dst_laws: Path) -> None:
    shutil.copytree(LAWS_DIR, dst_laws)


def test_committed_state_published_json_parses_cleanly() -> None:
    assert COMMITTED_STATE_PATH.is_file(), "state/published.json must be committed"
    raw = COMMITTED_STATE_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")

    ledger = load_published_ledger(COMMITTED_STATE_PATH)
    assert ledger.schema_version == 1
    assert ledger.editions == {}


def test_render_edition_changelog_initial_and_diff() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    snap_summer = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")
    snap_winter = build_realism_snapshot(registry, bl_countries, bl_locales, "winter")

    initial_bytes = render_edition_changelog(
        "summer",
        "1.62-2026.47",
        "a" * 64,
        "b" * 64,
        snap_summer,
    )
    assert not initial_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in initial_bytes
    assert initial_bytes.endswith(b"\n")
    initial_text = initial_bytes.decode("utf-8")
    assert "Summer" in initial_text
    assert "1.62-2026.47" in initial_text
    assert "MIT" in initial_text
    assert "CC BY 4.0" in initial_text
    assert "a" * 64 in initial_text

    # Deterministic repeat rendering
    assert (
        render_edition_changelog("summer", "1.62-2026.47", "a" * 64, "b" * 64, snap_summer)
        == initial_bytes
    )

    # Structured diff when previous_snapshot is provided
    diff_bytes = render_edition_changelog(
        "winter",
        "1.62-2026.48",
        "c" * 64,
        "d" * 64,
        snap_winter,
        previous_snapshot=snap_summer,
    )
    diff_text = diff_bytes.decode("utf-8")
    assert "HR" in diff_text  # Croatia seasonal lights_mandatory diff
    assert "FI" in diff_text  # Finland seasonal speed limit diff
    assert "DE" in diff_text  # Germany seasonal DST offset/name diff


def test_phase_a_release_initial_run_and_noop_across_weeks(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "published.json"
    out_dir = tmp_path / "dist"
    changelogs_dir = tmp_path / "changelogs"
    write_published_ledger(PublishedLedger(), state_path)

    # Run 1: empty ledger -> builds & validates both editions, writes snapshots, changelogs, state
    summary_1 = run_phase_a_release(
        state_path=state_path,
        out_dir=out_dir,
        changelogs_dir=changelogs_dir,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        build_date=date(2026, 11, 20),  # 2026-W47
        write_state=True,
    )
    assert isinstance(summary_1, PhaseAReleaseSummary)
    assert summary_1.any_changed is True
    assert summary_1.summer_changed is True
    assert summary_1.winter_changed is True
    assert summary_1.changed_editions == ["summer", "winter"]
    assert summary_1.editions["summer"].package_version == "1.62-2026.47"
    assert summary_1.editions["winter"].package_version == "1.62-2026.47"
    assert summary_1.editions["summer"].validation_ok is True
    assert summary_1.editions["winter"].validation_ok is True

    assert (out_dir / "workshop" / "summer" / "versions.sii").is_file()
    assert (out_dir / "workshop" / "winter" / "versions.sii").is_file()
    assert (out_dir / "local" / "ETS2V2_Core_Summer.zip").is_file()
    assert (out_dir / "local" / "ETS2V2_Core_Winter.zip").is_file()
    assert (out_dir / "snapshots" / "realism-snapshot-summer.json").is_file()
    assert (out_dir / "snapshots" / "realism-snapshot-winter.json").is_file()
    assert (changelogs_dir / "CHANGELOG_SUMMER.md").is_file()
    assert (changelogs_dir / "CHANGELOG_WINTER.md").is_file()
    assert (out_dir / "release_summary.json").is_file()

    # Validate v1 snapshot schema (76 territories) and SHA256SUMS.txt integrity cleanly
    summer_snap_path = out_dir / "snapshots" / "realism-snapshot-summer.json"
    winter_snap_path = out_dir / "snapshots" / "realism-snapshot-winter.json"
    checksums_path = out_dir / "snapshots" / "SHA256SUMS.txt"
    assert checksums_path.is_file()

    sums_raw = checksums_path.read_bytes()
    assert not sums_raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in sums_raw
    assert sums_raw.endswith(b"\n")
    sums_lines = sums_raw.decode("utf-8").splitlines()
    assert len(sums_lines) == 2
    assert sums_lines[0].endswith("  realism-snapshot-summer.json")
    assert sums_lines[1].endswith("  realism-snapshot-winter.json")

    summer_verify = verify_snapshot_file(
        summer_snap_path,
        checksums_path=checksums_path,
        expected_edition="summer",
    )
    winter_verify = verify_snapshot_file(
        winter_snap_path,
        checksums_path=checksums_path,
        expected_edition="winter",
    )
    assert summer_verify.ok is True
    assert summer_verify.checksum_verified is True
    assert summer_verify.country_count == 76
    assert winter_verify.ok is True
    assert winter_verify.checksum_verified is True
    assert winter_verify.country_count == 76

    summer_snap = RealismSnapshot.model_validate_json(summer_snap_path.read_text("utf-8"))
    assert summer_snap.schema_version == 1
    assert len(summer_snap.countries) == 76

    state_bytes_after_run1 = state_path.read_bytes()
    ledger_after_run1 = load_published_ledger(state_path)
    assert ledger_after_run1.editions["summer"].package_version == "1.62-2026.47"
    assert ledger_after_run1.editions["winter"].package_version == "1.62-2026.47"
    assert ledger_after_run1.editions["summer"].country_count == 36
    assert ledger_after_run1.editions["winter"].country_count == 36

    # Run 2: exact same data on a LATER ISO week (+14 days -> 2026-W49) -> clean NO-OP!
    summary_2 = run_phase_a_release(
        state_path=state_path,
        out_dir=out_dir,
        changelogs_dir=changelogs_dir,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        build_date=date(2026, 12, 4),  # 2026-W49
        write_state=True,
    )
    assert summary_2.any_changed is False
    assert summary_2.summer_changed is False
    assert summary_2.winter_changed is False
    assert summary_2.changed_editions == []
    assert summary_2.editions["summer"].package_version == "1.62-2026.47"
    assert summary_2.editions["winter"].package_version == "1.62-2026.47"
    assert state_path.read_bytes() == state_bytes_after_run1

    # Run 3: force_run=True on unchanged tree emits bundles/snapshots/changelogs
    # WITHOUT artificially mutating package_version or state/published.json
    forced_changelogs_dir = tmp_path / "forced_changelogs"
    summary_3 = run_phase_a_release(
        state_path=state_path,
        out_dir=out_dir,
        changelogs_dir=forced_changelogs_dir,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        build_date=date(2026, 12, 4),
        write_state=True,
        force_run=True,
    )
    assert summary_3.force_run is True
    assert summary_3.any_changed is False
    assert summary_3.editions["summer"].package_version == "1.62-2026.47"
    assert summary_3.editions["winter"].package_version == "1.62-2026.47"
    assert (forced_changelogs_dir / "CHANGELOG_SUMMER.md").is_file()
    assert (forced_changelogs_dir / "CHANGELOG_WINTER.md").is_file()
    assert state_path.read_bytes() == state_bytes_after_run1
    forced_summer_md = (forced_changelogs_dir / "CHANGELOG_SUMMER.md").read_text("utf-8")
    assert "**Previous Version:** unchanged (forced rebuild)" in forced_summer_md
    assert "**Previous Version:** `1.62-2026.47`" not in forced_summer_md


def test_single_edition_winter_change_keeps_summer_untouched(tmp_path: Path) -> None:
    laws_copy = tmp_path / "laws"
    _copy_laws_tree(laws_copy)
    state_path = tmp_path / "state" / "published.json"
    out_dir = tmp_path / "dist"
    changelogs_dir = tmp_path / "changelogs"
    write_published_ledger(PublishedLedger(), state_path)

    # Initial release on 2026-W47
    first = run_phase_a_release(
        state_path=state_path,
        out_dir=out_dir,
        changelogs_dir=changelogs_dir,
        laws_dir=laws_copy,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        build_date=date(2026, 11, 20),
        write_state=True,
    )
    assert first.any_changed is True
    initial_ledger = load_published_ledger(state_path)

    # Mutate ONLY Croatia's winter rule (winter.lights_mandatory -> False)
    hr_path = laws_copy / "countries" / "hr.json"
    hr_data = cast(dict[str, object], json.loads(hr_path.read_text("utf-8")))
    winter_block = cast(dict[str, object], hr_data["winter"])
    assert winter_block["lights_mandatory"] is True
    winter_block["lights_mandatory"] = False
    hr_path.write_text(
        json.dumps(hr_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Next week release on 2026-W48 -> ONLY winter updates, summer stays untouched!
    second_changelogs = tmp_path / "changelogs_run2"
    second = run_phase_a_release(
        state_path=state_path,
        out_dir=out_dir,
        changelogs_dir=second_changelogs,
        laws_dir=laws_copy,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        build_date=date(2026, 11, 27),
        write_state=True,
    )
    assert second.any_changed is True
    assert second.summer_changed is False
    assert second.winter_changed is True
    assert second.changed_editions == ["winter"]
    assert second.editions["summer"].package_version == "1.62-2026.47"
    assert second.editions["winter"].package_version == "1.62-2026.48"
    assert not (second_changelogs / "CHANGELOG_SUMMER.md").exists()
    assert (second_changelogs / "CHANGELOG_WINTER.md").is_file()

    updated_ledger = load_published_ledger(state_path)
    assert updated_ledger.editions["summer"] == initial_ledger.editions["summer"]
    assert updated_ledger.editions["winter"].package_version == "1.62-2026.48"
    assert (
        updated_ledger.editions["winter"].payload_sha256
        != initial_ledger.editions["winter"].payload_sha256
    )


def test_validation_failure_aborts_before_mutating_state(tmp_path: Path) -> None:
    icons_copy = tmp_path / "icons"
    shutil.copytree(ICONS_DIR, icons_copy)
    # Corrupt winter.jpg with truncated JPEG bytes so Offline SCS Validator fails with 00004
    (icons_copy / "winter.jpg").write_bytes(b"\xff\xd8\xff\xe0corrupt-truncated")

    state_path = tmp_path / "state" / "published.json"
    out_dir = tmp_path / "dist"
    changelogs_dir = tmp_path / "changelogs"
    original_state_bytes = write_published_ledger(PublishedLedger(), state_path)

    with pytest.raises(ValueError, match="00004"):
        run_phase_a_release(
            state_path=state_path,
            out_dir=out_dir,
            changelogs_dir=changelogs_dir,
            laws_dir=LAWS_DIR,
            mappings_path=MAPPINGS_PATH,
            baseline_dir=BASELINE_DIR,
            icons_dir=icons_copy,
            build_date=date(2026, 11, 20),
            write_state=True,
        )

    assert state_path.read_bytes() == original_state_bytes
    assert not (out_dir / "release_summary.json").exists()
    assert not (changelogs_dir / "CHANGELOG_SUMMER.md").exists()
    assert not (changelogs_dir / "CHANGELOG_WINTER.md").exists()


def test_cli_publish_release_end_to_end_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / "state" / "published.json"
    out_dir = tmp_path / "dist"
    changelogs_dir = tmp_path / "changelogs"
    write_published_ledger(PublishedLedger(), state_path)

    exit_code = main(
        [
            "publish",
            "release",
            "--state",
            str(state_path),
            "--out-dir",
            str(out_dir),
            "--changelogs-dir",
            str(changelogs_dir),
            "--laws-dir",
            str(LAWS_DIR),
            "--mappings",
            str(MAPPINGS_PATH),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--icons-dir",
            str(ICONS_DIR),
            "--build-date",
            "2026-11-20",
            "--write-state",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err

    parsed = PhaseAReleaseSummary.model_validate_json(captured.out)
    assert parsed.any_changed is True
    assert parsed.changed_editions == ["summer", "winter"]
    assert parsed.editions["summer"].package_version == "1.62-2026.47"

    # Second CLI invocation on later date -> clean exit 0 no-op
    exit_code_2 = main(
        [
            "publish",
            "release",
            "--state",
            str(state_path),
            "--out-dir",
            str(out_dir),
            "--changelogs-dir",
            str(changelogs_dir),
            "--laws-dir",
            str(LAWS_DIR),
            "--mappings",
            str(MAPPINGS_PATH),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--icons-dir",
            str(ICONS_DIR),
            "--build-date",
            "2026-12-04",
            "--write-state",
            "--json",
        ]
    )
    captured_2 = capsys.readouterr()
    assert exit_code_2 == 0, captured_2.err
    parsed_2 = PhaseAReleaseSummary.model_validate_json(captured_2.out)
    assert parsed_2.any_changed is False
    assert parsed_2.changed_editions == []


def test_changelog_diff_renders_max_limit_uncommon_currency_and_local_prices() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    snap_prev = build_realism_snapshot(registry, bl_countries, bl_locales, "summer")

    prev_ro = snap_prev.countries["RO"]
    mut_truck_lanes = [
        lane.model_copy(update={"max_limit": 100, "uncommon": True})
        if lane.lane_speed_class == "motorway"
        else lane
        for lane in prev_ro.speed_limits["truck"]
    ]
    mut_ro = prev_ro.model_copy(
        update={
            "speed_limits": {**prev_ro.speed_limits, "truck": mut_truck_lanes},
            "fuel": prev_ro.fuel.model_copy(
                update={"currency": "EUR", "local_prices": {"diesel": 7.45}}
            ),
        }
    )
    snap_curr = snap_prev.model_copy(update={"countries": {**snap_prev.countries, "RO": mut_ro}})

    rendered = render_edition_changelog(
        "summer",
        "1.62-2026.48",
        "e" * 64,
        "f" * 64,
        snap_curr,
        previous_snapshot=snap_prev,
    ).decode("utf-8")
    assert "[max=100]" in rendered
    assert "[uncommon=true]" in rendered
    assert "[RON]" in rendered and "[EUR]" in rendered
    assert "local_prices(diesel: None -> 7.45)" in rendered


def test_cli_publish_release_previous_snapshots_dir_and_registry_validate_error_guard(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wire --previous-snapshots-dir with winter snapshot vs summer build to force structured diff
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    prev_snaps_dir = tmp_path / "prev_snaps"
    prev_snaps_dir.mkdir()
    winter_snap = build_realism_snapshot(registry, bl_countries, bl_locales, "winter")
    (prev_snaps_dir / "realism-snapshot-summer.json").write_text(
        winter_snap.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    state_path = tmp_path / "state" / "published.json"
    out_dir = tmp_path / "dist"
    changelogs_dir = tmp_path / "changelogs"
    write_published_ledger(PublishedLedger(), state_path)

    exit_code = main(
        [
            "publish",
            "release",
            "--state",
            str(state_path),
            "--out-dir",
            str(out_dir),
            "--changelogs-dir",
            str(changelogs_dir),
            "--laws-dir",
            str(LAWS_DIR),
            "--mappings",
            str(MAPPINGS_PATH),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--icons-dir",
            str(ICONS_DIR),
            "--build-date",
            "2026-11-20",
            "--previous-snapshots-dir",
            str(prev_snaps_dir),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    summer_md = (changelogs_dir / "CHANGELOG_SUMMER.md").read_text("utf-8")
    assert "## Changes Since Previous Snapshot" in summer_md
    assert "HR" in summer_md

    # LO-05: _handle_registry_validate catches unexpected OSError cleanly
    def _boom(*_args: object, **_kwargs: object) -> list[str]:
        raise PermissionError("Simulated permission error")

    monkeypatch.setattr("ets2v2.cli.validate_law_registry", _boom)
    exit_err = main(["registry", "validate", "--json"])
    err_out = capsys.readouterr()
    assert exit_err == 1
    payload = cast(dict[str, object], json.loads(err_out.out))
    assert payload["ok"] is False
    assert payload["issue_count"] == 1


def test_changelog_d16_fuel_table_alerts_and_open_data_attributions() -> None:
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    base_lock = load_prices_lockfile(REPO_ROOT / "state" / "prices.lock.json")

    # 1. Clean live lock (no alerts, no fallback) omits alerts but renders 36-country fuel table
    clean_lock = base_lock.model_copy(
        update={
            "alerts": [],
            "countries": {
                iso2: entry.model_copy(update={"fallback_used": False})
                for iso2, entry in base_lock.countries.items()
            },
            "fx_rates": {
                ccy: fx.model_copy(update={"fallback_used": False})
                for ccy, fx in base_lock.fx_rates.items()
            },
        }
    )
    snap_clean = build_realism_snapshot(
        registry, bl_countries, bl_locales, "summer", prices_lock=clean_lock
    )
    clean_md = render_edition_changelog(
        "summer",
        "1.62-2026.47",
        "a" * 64,
        "b" * 64,
        snap_clean,
        prices_lock=clean_lock,
    ).decode("utf-8")

    assert "## 36-Country Fuel Price Summary" in clean_md
    assert "- **Countries Covered:** `36` (Core) / `76` (Snapshot)" in clean_md
    assert "| `KZ` |" not in clean_md
    assert "| ISO2 | Currency | EUR/L Diesel | Local Diesel | Local 95 | Source | Freshness |" in (
        clean_md
    )
    assert "| `GB` | GBP (p/L) |" in clean_md
    assert "| `HU` | HUF |" in clean_md
    assert "| `DE` | EUR |" in clean_md
    assert "## Circuit-Breaker & Staleness Alerts" not in clean_md
    for iso2 in ("DE", "GB", "BG", "IS"):
        assert f"| `{iso2}` |" in clean_md
    # Verify GB pence formatting & IS integer formatting in table (no raw <sup> tags in Markdown)
    assert "<sup>" not in clean_md
    for attribution in (
        "EC Weekly Oil Bulletin CC BY 4.0",
        "fuel-prices.eu CC BY 4.0",
        "UK DESNZ OGL v3",
        "Norway SSB CC BY 4.0",
        "France Licence Ouverte",
        "Italy MIMIT IODL 2.0",
        "Spain MITECO",
        "Netherlands CBS",
        "Germany Tankerkönig CC BY 4.0",
        "Frankfurter v2 MIT",
        "ECB",
        "fawazahmed0 CC0",
    ):
        assert attribution in clean_md, f"Missing D-16 attribution in changelog: {attribution!r}"

    # 2. Lock with circuit-breaker & staleness alerts highlights Alerts section and sanitizes MD
    evil_detail = "Bad feed\n## Injected Heading\n`backtick` <script>x</script> " + ("A" * 300)
    alerted_lock = clean_lock.model_copy(
        update={
            "alerts": [
                LockAlert(
                    severity="warning",
                    code="price_jump_rejected",
                    scope="DE",
                    detail="Diesel jumped +32.0% WoW; retained previous lockfile value.",
                ),
                LockAlert(
                    severity="warning",
                    code="stale_tier1",
                    scope="NO",
                    detail=evil_detail,
                ),
            ]
        }
    )
    alerted_md = render_edition_changelog(
        "summer",
        "1.62-2026.47",
        "a" * 64,
        "b" * 64,
        snap_clean,
        prices_lock=alerted_lock,
    ).decode("utf-8")
    assert "## Circuit-Breaker & Staleness Alerts" in alerted_md
    assert "price_jump_rejected" in alerted_md
    assert "stale_tier1" in alerted_md
    assert "\n## Injected Heading" not in alerted_md
    assert "<script>" not in alerted_md
    assert "&lt;script&gt;x&lt;/script&gt;" in alerted_md
    stale_line = next(line for line in alerted_md.splitlines() if "stale_tier1" in line)
    detail_part = stale_line.split(":** ", 1)[1]
    assert "`" not in detail_part
    assert len(detail_part) <= 240


def test_phase_a_release_prices_lock_mutation_bumps_both_editions_and_cli_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_lock = load_prices_lockfile(REPO_ROOT / "state" / "prices.lock.json")
    lock_path = tmp_path / "state" / "prices.lock.json"
    write_prices_lockfile(base_lock, lock_path)

    state_path = tmp_path / "state" / "published.json"
    out_dir = tmp_path / "dist"
    changelogs_dir = tmp_path / "changelogs"
    write_published_ledger(PublishedLedger(), state_path)

    # Initial CLI run with --prices-lock
    exit_1 = main(
        [
            "publish",
            "release",
            "--state",
            str(state_path),
            "--prices-lock",
            str(lock_path),
            "--out-dir",
            str(out_dir),
            "--changelogs-dir",
            str(changelogs_dir),
            "--laws-dir",
            str(LAWS_DIR),
            "--mappings",
            str(MAPPINGS_PATH),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--icons-dir",
            str(ICONS_DIR),
            "--build-date",
            "2026-11-20",
            "--write-state",
            "--json",
        ]
    )
    cap_1 = capsys.readouterr()
    assert exit_1 == 0, cap_1.err
    res_1 = PhaseAReleaseSummary.model_validate_json(cap_1.out)
    assert res_1.any_changed is True
    assert res_1.changed_editions == ["summer", "winter"]
    assert res_1.editions["summer"].validation_ok is True
    assert res_1.editions["winter"].validation_ok is True

    # Confirm 579 Workshop files (incl. 460 boards + 43 locales) and D-16 changelog content
    summer_ws_files = [p for p in (out_dir / "workshop" / "summer").rglob("*") if p.is_file()]
    assert len(summer_ws_files) == 579
    assert not any(p.suffix.lower() in {".dds", ".tobj"} for p in summer_ws_files)
    summer_md = (changelogs_dir / "CHANGELOG_SUMMER.md").read_text("utf-8")
    assert "## 36-Country Fuel Price Summary" in summer_md
    assert "EC Weekly Oil Bulletin CC BY 4.0" in summer_md

    # Mutate DE diesel price in prices.lock.json -> bumps BOTH editions cleanly next week
    de_old = base_lock.countries["DE"]
    de_new = de_old.model_copy(
        update={
            "eur_per_liter": round(de_old.eur_per_liter + 0.05, 3),
            "local_prices": {
                **de_old.local_prices,
                "diesel": round(de_old.local_prices["diesel"] + 0.05, 4),
            },
        }
    )
    updated_lock = base_lock.model_copy(update={"countries": {**base_lock.countries, "DE": de_new}})
    write_prices_lockfile(updated_lock, lock_path)

    res_2 = run_phase_a_release(
        state_path=state_path,
        prices_lock_path=lock_path,
        out_dir=out_dir,
        changelogs_dir=changelogs_dir,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        build_date=date(2026, 11, 27),
        write_state=True,
    )
    assert res_2.any_changed is True
    assert res_2.summer_changed is True
    assert res_2.winter_changed is True
    assert res_2.editions["summer"].package_version == "1.62-2026.48"
    assert res_2.editions["winter"].package_version == "1.62-2026.48"
