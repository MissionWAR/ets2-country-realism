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
from ets2v2.registry.snapshot import RealismSnapshot, build_realism_snapshot

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

    # Validate v1 snapshot schema cleanly
    summer_snap = RealismSnapshot.model_validate_json(
        (out_dir / "snapshots" / "realism-snapshot-summer.json").read_text("utf-8")
    )
    assert summer_snap.schema_version == 1
    assert len(summer_snap.countries) == 36

    state_bytes_after_run1 = state_path.read_bytes()
    ledger_after_run1 = load_published_ledger(state_path)
    assert ledger_after_run1.editions["summer"].package_version == "1.62-2026.47"
    assert ledger_after_run1.editions["winter"].package_version == "1.62-2026.47"

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
