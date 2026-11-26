"""Phase A release orchestrator composing registry, packaging, validation, diff-gate & logs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ets2_realism.baseline.models import (
    BaselineManifest,
    CountriesBaseline,
    LocalesBaseline,
)
from ets2_realism.normalize.lockfile import load_prices_lockfile
from ets2_realism.normalize.models import PricesLockfile
from ets2_realism.package.builder import BuiltEditionPaths, build_core_edition
from ets2_realism.package.metadata import DEFAULT_AUTHOR
from ets2_realism.publish.changelog import render_edition_changelog
from ets2_realism.publish.ledger import (
    PublishedEditionState,
    PublishedLedger,
    compute_workshop_canonical_sha256,
    load_published_ledger,
    resolve_next_package_version,
    write_published_ledger,
)
from ets2_realism.registry.loader import load_law_registry
from ets2_realism.registry.models import Season
from ets2_realism.registry.snapshot import (
    RealismSnapshot,
    build_realism_snapshot,
    serialize_snapshot_bytes,
    verify_snapshot_file,
    write_realism_snapshot,
    write_sha256sums,
)
from ets2_realism.registry.timezone import DEFAULT_ANCHOR_YEAR
from ets2_realism.validate.models import ValidationReport
from ets2_realism.validate.workshop import validate_local_zip, validate_workshop_package

_EDITIONS: Final[tuple[Season, ...]] = ("summer", "winter")
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
_ISO_DATE_PATTERN: Final[str] = r"^\d{4}-\d{2}-\d{2}$"


class EditionReleaseResult(BaseModel):
    """Structured Phase A release outcome for a single seasonal edition."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    edition: Season
    changed: bool
    snapshot_changed: bool = False
    package_version: str = Field(min_length=1)
    previous_package_version: str | None
    payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    snapshot_sha256: str = Field(pattern=_SHA256_PATTERN)
    workshop_dir: Path
    local_zip_path: Path
    snapshot_path: Path
    changelog_path: Path | None
    validation_ok: bool


class PhaseAReleaseSummary(BaseModel):
    """Structured release summary written to ``dist/release_summary.json``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    build_date: str = Field(pattern=_ISO_DATE_PATTERN)
    force_run: bool
    any_changed: bool
    snapshots_changed: bool = False
    summer_changed: bool
    winter_changed: bool
    changed_editions: list[Season]
    editions: dict[Season, EditionReleaseResult]


@dataclass(frozen=True)
class _StagedEdition:
    edition: Season
    snapshot: RealismSnapshot
    snapshot_sha256: str
    snapshot_changed: bool
    built: BuiltEditionPaths
    canonical_sha256: str
    package_version: str
    changed: bool
    previous_state: PublishedEditionState | None


def _derive_game_version_prefix(game_version: str) -> str:
    parts = game_version.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else "1.62"


def _format_validation_failures(
    edition: Season,
    label: str,
    report: ValidationReport,
) -> list[str]:
    failures: list[str] = []
    for issue in report.issues:
        loc = f" [{issue.path}]" if issue.path else ""
        failures.append(
            f"{edition}/{label} {issue.severity.upper()} {issue.code}{loc}: {issue.detail}"
        )
    return failures


def _serialize_summary_bytes(summary: PhaseAReleaseSummary) -> bytes:
    payload: object = summary.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def run_phase_a_release(
    *,
    state_path: Path = Path("state/published.json"),
    prices_lock_path: Path = Path("state/prices.lock.json"),
    prices_lock: PricesLockfile | None = None,
    out_dir: Path = Path("dist"),
    changelogs_dir: Path = Path("."),
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    icons_dir: Path = Path("assets/icons"),
    build_date: date | None = None,
    author: str = DEFAULT_AUTHOR,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    write_state: bool = False,
    force_run: bool = False,
    previous_snapshots: Mapping[Season, RealismSnapshot] | None = None,
) -> PhaseAReleaseSummary:
    """Run the full Phase A build -> validate -> diff-gate -> snapshot -> changelog pipeline."""
    effective_build_date = build_date if build_date is not None else datetime.now(UTC).date()
    resolved_lock = (
        prices_lock if prices_lock is not None else load_prices_lockfile(prices_lock_path)
    )

    registry = load_law_registry(laws_dir, mappings_path)
    bl_countries = CountriesBaseline.model_validate_json(
        (baseline_dir / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (baseline_dir / "locales.json").read_text("utf-8")
    )
    manifest_json = baseline_dir / "manifest.json"
    if manifest_json.is_file():
        bl_manifest = BaselineManifest.model_validate_json(manifest_json.read_text("utf-8"))
        game_version = bl_manifest.game_version
    else:
        game_version = registry.mappings.baseline_game_version
    game_version_prefix = _derive_game_version_prefix(game_version)

    existing_ledger = (
        load_published_ledger(state_path) if state_path.exists() else PublishedLedger()
    )

    iso_year, iso_week, _ = effective_build_date.isocalendar()
    default_week_version = f"{game_version_prefix}-{iso_year}.{iso_week:02d}"

    staged_editions: dict[Season, _StagedEdition] = {}
    validation_errors: list[str] = []

    for edition in _EDITIONS:
        snapshot = build_realism_snapshot(
            registry,
            bl_countries,
            bl_locales,
            edition,
            anchor_year=anchor_year,
            baseline_game_version=game_version,
            prices_lock=resolved_lock,
        )
        snapshot_bytes = serialize_snapshot_bytes(snapshot)
        snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()

        prev_state = existing_ledger.editions.get(edition)
        initial_version = (
            prev_state.package_version if prev_state is not None else default_week_version
        )

        built = build_core_edition(
            edition,
            out_dir,
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            baseline_dir=baseline_dir,
            icons_dir=icons_dir,
            prices_lock=resolved_lock,
            package_version=initial_version,
            author=author,
            anchor_year=anchor_year,
        )
        canonical_sha256 = compute_workshop_canonical_sha256(built.workshop_dir)
        final_version, changed = resolve_next_package_version(
            prev_state,
            canonical_sha256,
            effective_build_date,
            game_version_prefix=game_version_prefix,
        )

        if final_version != built.package_version:
            built = build_core_edition(
                edition,
                out_dir,
                laws_dir=laws_dir,
                mappings_path=mappings_path,
                baseline_dir=baseline_dir,
                icons_dir=icons_dir,
                prices_lock=resolved_lock,
                package_version=final_version,
                author=author,
                anchor_year=anchor_year,
            )
            restamped_sha256 = compute_workshop_canonical_sha256(built.workshop_dir)
            if restamped_sha256 != canonical_sha256:
                raise ValueError(
                    f"Canonical SHA-256 drifted after re-stamping {edition} package_version "
                    f"({canonical_sha256} != {restamped_sha256})"
                )

        workshop_report = validate_workshop_package(built.workshop_dir, baseline_dir=baseline_dir)
        if not workshop_report.ok:
            validation_errors.extend(
                _format_validation_failures(edition, "workshop", workshop_report)
            )

        local_report = validate_local_zip(built.local_zip_path, baseline_dir=baseline_dir)
        if not local_report.ok:
            validation_errors.extend(_format_validation_failures(edition, "local", local_report))

        snapshot_changed = prev_state is None or prev_state.snapshot_sha256 != snapshot_sha256
        staged_editions[edition] = _StagedEdition(
            edition=edition,
            snapshot=snapshot,
            snapshot_sha256=snapshot_sha256,
            snapshot_changed=snapshot_changed,
            built=built,
            canonical_sha256=canonical_sha256,
            package_version=final_version,
            changed=changed,
            previous_state=prev_state,
        )

    # Hard validation gate BEFORE mutating state/published.json, changelogs, or summary (T-02-15)
    if validation_errors:
        joined_errors = "\n".join(validation_errors)
        raise ValueError(f"Offline SCS validation failed before release emission:\n{joined_errors}")

    snapshots_dir = out_dir / "snapshots"
    edition_results: dict[Season, EditionReleaseResult] = {}
    new_ledger_editions: dict[Season, PublishedEditionState] = {}
    changed_editions: list[Season] = []

    for edition in _EDITIONS:
        staged = staged_editions[edition]
        snapshot_path = snapshots_dir / f"realism-snapshot-{edition}.json"
        write_realism_snapshot(staged.snapshot, snapshot_path)

        changelog_path: Path | None = None
        if staged.changed or force_run:
            prev_snap = previous_snapshots.get(edition) if previous_snapshots is not None else None
            changelog_bytes = render_edition_changelog(
                edition,
                staged.package_version,
                staged.canonical_sha256,
                staged.snapshot_sha256,
                staged.snapshot,
                file_count=staged.built.workshop_file_count,
                previous_state=staged.previous_state,
                previous_snapshot=prev_snap,
                prices_lock=resolved_lock,
            )
            changelog_path = changelogs_dir / f"CHANGELOG_{edition.upper()}.md"
            changelog_path.parent.mkdir(parents=True, exist_ok=True)
            changelog_path.write_bytes(changelog_bytes)

        if staged.changed:
            changed_editions.append(edition)
            new_ledger_editions[edition] = PublishedEditionState(
                anchor_date=staged.snapshot.anchor_date,
                baseline_game_version=staged.snapshot.baseline_game_version,
                country_count=len(bl_countries.countries),
                file_count=staged.built.workshop_file_count,
                package_version=staged.package_version,
                payload_sha256=staged.canonical_sha256,
                snapshot_sha256=staged.snapshot_sha256,
            )
        elif staged.previous_state is not None:
            if staged.snapshot_changed:
                # Non-Core ProMods snapshot data changed without changing 36-country Core payload:
                # advance snapshot_sha256 without bumping Core package_version (MD-06).
                new_ledger_editions[edition] = staged.previous_state.model_copy(
                    update={"snapshot_sha256": staged.snapshot_sha256}
                )
            else:
                new_ledger_editions[edition] = staged.previous_state

        edition_results[edition] = EditionReleaseResult(
            edition=edition,
            changed=staged.changed,
            snapshot_changed=staged.snapshot_changed,
            package_version=staged.package_version,
            previous_package_version=(
                staged.previous_state.package_version if staged.previous_state is not None else None
            ),
            payload_sha256=staged.canonical_sha256,
            snapshot_sha256=staged.snapshot_sha256,
            workshop_dir=staged.built.workshop_dir,
            local_zip_path=staged.built.local_zip_path,
            snapshot_path=snapshot_path,
            changelog_path=changelog_path,
            validation_ok=True,
        )

    snapshot_paths = [
        snapshots_dir / "realism-snapshot-summer.json",
        snapshots_dir / "realism-snapshot-winter.json",
    ]
    checksums_path = snapshots_dir / "SHA256SUMS.txt"
    write_sha256sums(snapshot_paths, checksums_path)

    for edition in _EDITIONS:
        written_snapshot_path = snapshots_dir / f"realism-snapshot-{edition}.json"
        verification = verify_snapshot_file(
            written_snapshot_path,
            checksums_path=checksums_path,
            expected_edition=edition,
        )
        if not verification.ok or not verification.checksum_verified:
            joined = "; ".join(verification.issues)
            raise ValueError(f"Emitted {edition} realism snapshot failed verification: {joined}")

    any_changed = bool(changed_editions)
    snapshots_changed = any(res.snapshot_changed for res in edition_results.values())
    if write_state and (any_changed or snapshots_changed):
        write_published_ledger(PublishedLedger(editions=new_ledger_editions), state_path)

    summary = PhaseAReleaseSummary(
        build_date=effective_build_date.isoformat(),
        force_run=force_run,
        any_changed=any_changed,
        snapshots_changed=snapshots_changed,
        summer_changed=edition_results["summer"].changed,
        winter_changed=edition_results["winter"].changed,
        changed_editions=changed_editions,
        editions=edition_results,
    )

    summary_path = out_dir / "release_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_bytes(_serialize_summary_bytes(summary))
    return summary
