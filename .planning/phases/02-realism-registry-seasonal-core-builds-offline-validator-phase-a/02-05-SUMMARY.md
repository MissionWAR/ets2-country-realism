---
phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
plan: "05"
subsystem: publish
tags: [sha256, ledger, changelog, release, github-actions, pub-02, pub-03, cli]

requires:
  - phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
    provides: "Locked D-11 schema_version=1 snapshot/ledger contracts (02-02), dual Core packager (02-03), and Offline SCS Workshop Validator (02-04)"
provides:
  - "Canonical payload SHA-256 hasher excluding package_version, ISO-week version resolver, and state/published.json loader/writer (src/ets2v2/publish/ledger.py)"
  - "Deterministic UTF-8 no-BOM LF Markdown changelog renderer (src/ets2v2/publish/changelog.py)"
  - "Phase A release orchestrator composing registry -> package -> validate -> diff-gate -> snapshot -> changelog (src/ets2v2/publish/release.py) and ets2v2 publish release CLI"
  - "Committed initial schema_version=1 state/published.json ledger (empty editions map)"
  - "Phase A Friday 06:00 UTC persistent-PR GitHub Actions workflow (.github/workflows/phase-a-release.yml) with zero Steam secrets"
affects: [phase-3, phase-4, phase-5]

tech-stack:
  added: []
  patterns: [canonical SHA-256 content hashing with SiiDocument sentinel substitution, pre-mutation validation gate, persistent Release PR GitHub Actions workflow]

key-files:
  created:
    - src/ets2v2/publish/__init__.py
    - src/ets2v2/publish/ledger.py
    - src/ets2v2/publish/changelog.py
    - src/ets2v2/publish/release.py
    - state/published.json
    - .github/workflows/phase-a-release.yml
    - tests/test_publish_ledger.py
    - tests/test_publish_release.py
    - tests/test_publish_workflow.py
  modified:
    - src/ets2v2/cli.py

key-decisions:
  - "Canonical SHA-256 hashing substitutes universal/manifest.sii package_version with '__CANONICAL__' via SiiDocument and length-prefixes every sorted POSIX file frame so weekly ISO-week bumps never cause false-positive diffs."
  - "state/published.json initializes with schema_version=1 and empty editions={} so the first Friday 06:00 UTC CI run generates the initial Release PR cleanly and advances state only upon maintainer merge."
  - "Isolated contents:write and pull-requests:write strictly inside phase-a-release.yml while keeping ci.yml read-only and keeping zero Steam secrets anywhere in workflows."

patterns-established:
  - "Hard validation gate in run_phase_a_release() verifies both Workshop trees and both local ZIPs before mutating state/published.json, snapshots, or changelogs."
  - "GitHub Actions workflow_dispatch inputs pass strictly through env: (FORCE_RUN) to prevent shell injection."

requirements-completed: [PUB-02, PUB-03]

duration: 14min
completed: 2026-11-20
---

# Phase 2 Plan 05: Canonical SHA-256 Diff Gate, Changelogs & Phase A CI Release Pipeline Summary

**Implemented canonical payload SHA-256 diff gating (`state/published.json`), deterministic Summer/Winter Markdown changelogs, the `ets2v2 publish release` orchestrator, and the Friday `06:00 UTC` persistent-PR GitHub Actions workflow with zero Steam secrets.**

## Accomplishments
- Implemented `src/ets2v2/publish/ledger.py` (`CANONICAL_VERSION_SENTINEL`, `PublishedEditionState`, `PublishedLedger`, `compute_workshop_canonical_sha256`, `resolve_next_package_version`, `load_published_ledger`, `write_published_ledger`) matching the locked D-11 `schema_version=1` ledger contract.
- Implemented `src/ets2v2/publish/changelog.py` (`render_edition_changelog`) emitting deterministic UTF-8 no-BOM LF Markdown changelogs (`CHANGELOG_SUMMER.md`, `CHANGELOG_WINTER.md`).
- Implemented `src/ets2v2/publish/release.py` (`EditionReleaseResult`, `PhaseAReleaseSummary`, `run_phase_a_release`) and wired `ets2v2 publish release` into `src/ets2v2/cli.py`, enforcing independent per-edition diff gating and hard Offline SCS Validation prior to any state or artifact emission.
- Committed initial `state/published.json` (`{"editions": {}, "schema_version": 1}`) and `.github/workflows/phase-a-release.yml` (`cron: "0 6 * * 5"`, `workflow_dispatch` with `env.FORCE_RUN`, `gh pr list`/`edit`/`create` against `release/phase-a-weekly` as `github-actions[bot]`, zero Steam secrets).
- Added comprehensive TDD test suites (`tests/test_publish_ledger.py`, `tests/test_publish_release.py`, `tests/test_publish_workflow.py`) and verified the full repository test suite (`232 passed`).

## Deviations from Plan
- The Plan `02-05` subagent stalled after `pytest` took `23.11s` (>10s async backgrounding threshold); the orchestrator verified all lint/type gates and the full 232-test suite, wrote this summary, and committed Plan `02-05`.

## Verification
- `uv run --offline ruff check`: exit 0 (`All checks passed!`)
- `uv run --offline ruff format --check`: exit 0 (`62 files already formatted`)
- `uv run --offline basedpyright`: exit 0 (`0 errors, 0 warnings, 0 notes`)
- `uv run --offline pytest -q --tb=short`: exit 0 (`232 passed in 96.81s`)

---
*Phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a*
*Completed: 2026-11-20*
