---
phase: 05-global-tier-1-2-3-coverage-internal-osm-audit
plan: "04"
subsystem: osm-speed-audit-license-quarantine
tags: [osm-audit, cc-by-sa-quarantine, license-taint, ast-dag-wall, overpass, taginfo, github-actions, clean-room]
dependency_graph:
  requires:
    - "05-01 (225-territory canonical data/laws/countries/*.json, data/mappings/currencies.json, data/curated/tier3_fuel_baselines.json, and state/prices.lock.json)"
    - "05-03 (Finalized Phase 5 Tier 2 national portals, 5-tier staleness, and clean-room open-data attributions)"
  provides:
    - "Strictly quarantined Layer 7C `src/ets2v2/audit/` subpackage (`models`, `osm_speeds`, `overpass`, `taint`) unlocked behind the universal Phase 5 AST DAG quarantine wall across all 10 non-audit subpackages (`D-16`)"
    - "Self-contained pure-stdlib `FORBIDDEN_LICENSE_TAINT_PATTERNS` & `check_license_taint_bytes()` emitting `ETS2V2-INV-LICENSE-TAINT` inside `src/ets2v2/validate/invariants.py` (ZERO `ets2v2.audit` import) wired into `src/ets2v2/validate/workshop.py` across `core`, `promods`, and `combo` profiles (`D-16`)"
    - "Automated repo/snapshot/package license-taint gate (`src/ets2v2/audit/taint.py` + `tests/test_license_taint_gate.py`) verifying zero forbidden markers across all `225` law files, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, generated Summer/Winter snapshots, and built Core Workshop/local packages (`D-16`)"
    - "Clean-room canonical `data/laws/speed_audit_allowlist.json` (`schema_version: 1`, 11 statutory entries, zero OSM text/URLs) (`D-15`)"
    - "Hardened `post_form_bytes_with_retry()` in `src/ets2v2/fetch/http.py`, `westnordost/osm-legal-default-speeds` drift auditor (`src/ets2v2/audit/osm_speeds.py`), opt-in tags-only Overpass (`out tags 500;`, `<= 10` ISO-2 cap, `^[A-Z]{2}$` validation, polite `sleep_fn`) & Taginfo v4 spot-check client (`src/ets2v2/audit/overpass.py`), and `ets2v2 audit {osm-speeds,taint}` CLI subcommands (`D-13`, `D-15`)"
    - "Standalone monthly zero-Git-write `.github/workflows/osm-speed-audit.yml` (`cron: '0 7 1-7 * 1'` + `workflow_dispatch`, `permissions: { contents: read, issues: write }`, zero `${{` inside `run:`, artifact upload, sanitized Step Summary, rolling `osm-audit` issue upsert) (`D-14`)"
  affects:
    - "Phase 5 verification & UAT (`GLB-01`..`GLB-04` complete; zero new runtime dependencies; all 7 AST DAG isolation walls and automated `CC BY 4.0` taint gates enforced in CI)"
tech-stack:
  added: []
  patterns:
    - "One-way Layer 7C `ets2v2.audit` quarantine enforced via AST import scanning across all 10 non-audit subpackages (`vfs`, `sii`, `baseline`, `normalize`, `registry`, `fetch`, `package`, `validate`, `merge`, `publish`) plus outbound `audit/` ban on `package`/`merge`/`publish`/`validate`/`openpyxl` (`D-16`)"
    - "Decoupled pure-stdlib `ETS2V2-INV-LICENSE-TAINT` package check in `validate/invariants.py` mirroring the exact 8 `D-16` markers (with word-boundary `(?:international\\s+energy\\s+agency|\\biea\\b)`) without importing `ets2v2.audit`"
    - "Hardened form-encoded `post_form_bytes_with_retry()` reusing `validate_https_url()`, `_read_bounded_response()`, retryable status backoff, and `redact_url_secrets()` for opt-in Overpass QL spot-checks"
    - "Least-privilege zero-Git-write monthly audit workflow (`contents: read`, `issues: write`, env-only inputs, built-in `gh issue` CLI) physically preventing `CC BY-SA` / `ODbL` data from entering Git history (`D-14`)"
key-files:
  created:
    - src/ets2v2/audit/__init__.py
    - src/ets2v2/audit/models.py
    - src/ets2v2/audit/osm_speeds.py
    - src/ets2v2/audit/overpass.py
    - src/ets2v2/audit/taint.py
    - data/laws/speed_audit_allowlist.json
    - .github/workflows/osm-speed-audit.yml
    - tests/test_audit_osm_speeds.py
    - tests/test_license_taint_gate.py
  modified:
    - src/ets2v2/fetch/http.py
    - src/ets2v2/fetch/__init__.py
    - src/ets2v2/validate/invariants.py
    - src/ets2v2/validate/workshop.py
    - src/ets2v2/validate/__init__.py
    - src/ets2v2/cli.py
    - tests/test_cli_scaffold.py
    - tests/test_validate_workshop.py
    - tests/test_publish_workflow.py
decisions:
  - "Duplicated the 8 compiled `D-16` forbidden license/source regexes independently in `validate/invariants.py` (pure stdlib) and `audit/taint.py`—asserting label parity in `tests/test_license_taint_gate.py`—so `ets2v2.validate` audits every packaged `.sii`/`.sui`/`.txt` across `core`/`promods`/`combo` profiles with zero `ets2v2.audit` import."
  - "Compared `westnordost/osm-legal-default-speeds` urban defaults against ETS2 `local_road.urban_limit` (while comparing rural/trunk/motorway against `local_road`/`expressway`/`motorway` `.limit`) so motorway urban-section speed encodings do not generate false drift noise."
  - "Enforced `post_form_bytes_with_retry()` to follow only POST-preserving redirects (`307`/`308`) within `allowed_hosts` and reject non-POST-preserving `301`/`302`/`303` redirects cleanly."
metrics:
  duration: "135m wall-clock (incl. ~95m Windows sandbox full pytest & workshop validation I/O)"
  completed: "2026-11-26"
status: complete
actuals:
  tokens: 30788
  tasks: 3
  commits: 3
plan_head_before: dd5a4336e2e8568f40cf3cd3a3c149bcfe8e535d
plan_head_after: 0de3c4f9170bdddbc462e921156398c59f57aca0
---

# Phase 5 Plan 04: Quarantined OSM Speed-Limit Drift Audit, License-Taint Gate & Monthly Workflow Summary

Unlocked the strictly quarantined Layer 7C **`src/ets2v2/audit/` subpackage** behind the universal Phase 5 AST DAG quarantine wall across all `10` non-audit subpackages (`D-16`), embedded an independent pure-stdlib **`ETS2V2-INV-LICENSE-TAINT`** check inside `src/ets2v2/validate/invariants.py` wired into `src/ets2v2/validate/workshop.py` across `core`, `promods`, and `combo` profiles with zero `ets2v2.audit` import, verified **0 taint violations** across all `225` committed law files, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, `data/laws/speed_audit_allowlist.json`, generated Summer/Winter `225`-territory snapshots, and built Core Workshop/local packages (`tests/test_license_taint_gate.py`), implemented clean-room `data/laws/speed_audit_allowlist.json` (`D-15`), `post_form_bytes_with_retry()` in `src/ets2v2/fetch/http.py`, `westnordost/osm-legal-default-speeds` speed-limit drift auditing + opt-in Overpass (`out tags 500;`, `<= 10` ISO-2 cap) & Taginfo v4 spot-checks (`src/ets2v2/audit/{osm_speeds,overpass}.py`, `D-13`), wired `ets2v2 audit {osm-speeds,taint}` into `src/ets2v2/cli.py`, and shipped the standalone monthly zero-Git-write **`.github/workflows/osm-speed-audit.yml`** workflow (`permissions: { contents: read, issues: write }`, zero `${{` inside `run:`, artifact upload, sanitized Step Summary, and single rolling `osm-audit` maintainer issue upsert per `D-14`).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Unlock `src/ets2v2/audit/` with Phase 5 AST DAG quarantine walls, add independent `ETS2V2-INV-LICENSE-TAINT` validator gate, and build `audit/{models,taint}.py` + `test_license_taint_gate.py` | `835f4ec` | `src/ets2v2/audit/{__init__,models,taint}.py`, `src/ets2v2/validate/{invariants,workshop,__init__}.py`, `tests/test_{cli_scaffold,validate_workshop,license_taint_gate}.py` |
| 2 | Build clean-room `data/laws/speed_audit_allowlist.json`, `post_form_bytes_with_retry()` in `fetch/http.py`, and `audit/{osm_speeds,overpass}.py` + `ets2v2 audit` CLI | `a6fa08a` | `src/ets2v2/fetch/{http,__init__}.py`, `data/laws/speed_audit_allowlist.json`, `src/ets2v2/audit/{osm_speeds,overpass,__init__}.py`, `src/ets2v2/cli.py`, `tests/test_audit_osm_speeds.py` |
| 3 | Ship standalone monthly zero-Git-write `.github/workflows/osm-speed-audit.yml` (`D-14`) and run complete Phase 5 verification & security audit | `0de3c4f` | `.github/workflows/osm-speed-audit.yml`, `tests/test_publish_workflow.py` |

## Achieved Coverage & Contracts

- **Universal Phase 5 AST DAG Quarantine Wall (`D-16`):** `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` unlocks `"audit"` while `test_phase5_ast_dag_isolation_walls` (and `tests/test_validate_workshop.py`) enforces all 6 offline walls (`validate`, `merge`, `package`, `publish`, `normalize`, `registry`) PLUS universal `audit` quarantine across all `10` non-audit subpackages (`vfs`, `sii`, `baseline`, `normalize`, `registry`, `fetch`, `package`, `validate`, `merge`, `publish`) and outbound restrictions on `audit/` (`package`, `merge`, `publish`, `validate`, `openpyxl`).
- **Independent Validator & Repo License-Taint Gate (`D-16`):** `validate/invariants.py` implements self-contained pure-stdlib `FORBIDDEN_LICENSE_TAINT_PATTERNS` and `check_license_taint_bytes()` emitting `ETS2V2-INV-LICENSE-TAINT` across `versions.sii`, `manifest.sii`, `.txt` descriptions, and every `.sii`/`.sui` member for `core`, `promods`, and `combo` profiles with zero `ets2v2.audit` import; `audit/taint.py` + `tests/test_license_taint_gate.py` confirm **0 violations** across all `231` committed repo data/lockfile artifacts (`225` law files + `speed_audit_allowlist.json` + `tier3_fuel_baselines.json` + `3` mappings + `state/prices.lock.json`), `2` generated Summer/Winter `225`-territory snapshots, and `4` built Core Workshop/local packages (`2,542+` scanned text files total) while rejecting all 8 synthetic markers (`CC BY-SA`, `ODbL`, `OpenStreetMap`, `osm-legal-default-speeds`, `GlobalPetrolPrices`, `CC BY-NC-ND`, `MyLPG`, `IEA`) with zero word-boundary false positives (`traffiea`, `caribbean`, `U.S. EIA`, etc.).
- **Clean-Room Allowlist & OSM Drift Auditor (`D-13`, `D-15`):** `data/laws/speed_audit_allowlist.json` validates under strict frozen `SpeedAuditAllowlist` (`schema_version: 1`, 11 clean-room statutory entries for `DE`, `EE`, `FI`, `IM`, `LT` with zero OSM text/URLs). `ets2v2 audit osm-speeds` compares `data/laws/` against `westnordost/osm-legal-default-speeds` (offline `--rules-file` or HTTPS allowlisted `--rules-url`), splits findings into `Unacknowledged Drift` vs `Acknowledged Statutory Differences`, supports opt-in `--overpass` (`POST` via `post_form_bytes_with_retry()`, `out tags 500;`, `^[A-Z]{2}$` validation, `<= 10` ISO-2 cap, polite `sleep_fn`) and `--taginfo` (`taginfo.openstreetmap.org/api/4/key/values`), and emits sanitized deterministic UTF-8 no-BOM LF Markdown (`--out-md`) + sorted JSON (`--out-json`).
- **Standalone Monthly Zero-Git-Write Workflow (`D-14`):** `.github/workflows/osm-speed-audit.yml` runs on 1st Monday `07:00 UTC` (`cron: "0 7 1-7 * 1"`) + `workflow_dispatch` (`iso2`, `overpass`), enforces `permissions: { contents: read, issues: write }` (physically preventing Git commits/pushes), forbids `pull_request*` triggers, passes `AUDIT_ISO2`/`AUDIT_OVERPASS`/`GH_TOKEN` strictly via `env:` with zero `${{` inside `run:`, uploads `osm-speed-drift-report` artifacts via `actions/upload-artifact@v4`, publishes a sanitized `$GITHUB_STEP_SUMMARY`, and upserts a single rolling `osm-audit` GitHub Issue via built-in `gh issue` CLI only when `unacknowledged_drift_count > 0`.
- **Zero New Dependencies (`D-03`, `D-06`):** `pyproject.toml` and `uv.lock` remain strictly untouched at the exact 5 runtime packages (`httpx`, `openpyxl`, `pillow`, `pydantic`, `tzdata`).

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `119 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, Python `3.12`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **602 passed, 4 deselected** (+26 new tests: `18` in `tests/test_license_taint_gate.py`, `5` in `tests/test_audit_osm_speeds.py`, `1` in `tests/test_validate_workshop.py`, `2` in `tests/test_publish_workflow.py`)
- `uv run --offline ets2v2 audit taint --json`: exit `0`, `ok: true`, `files_scanned: 231`, `violation_count: 0`, `violations: []`
- `uv run --offline ets2v2 audit osm-speeds --iso2 DE,FR,PL --rules-file <tmp>/sample_rules.json --out-md <tmp>/drift.md --out-json <tmp>/drift.json --json`: exit `0`, `countries_checked: 3`, `countries_matched_in_osm: 3`, `acknowledged_difference_count: 1` (`DE`), `unacknowledged_drift_count: 1` (`PL`)

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-05-14** | Dual automated `CC BY 4.0` barriers: Phase 5 AST DAG quarantine wall across all `10` non-audit subpackages (`tests/test_cli_scaffold.py`, `tests/test_validate_workshop.py`) + independent `ETS2V2-INV-LICENSE-TAINT` check in `validate/invariants.py` and full repo/snapshot/package taint gate (`tests/test_license_taint_gate.py`, `ets2v2 audit taint`). |
| **T-05-15** | `.github/workflows/osm-speed-audit.yml` enforces `permissions: { contents: read, issues: write }`, zero `pull_request*` triggers, zero `git add`/`commit`/`push`, env-only inputs (`AUDIT_ISO2`, `AUDIT_OVERPASS`, `GH_TOKEN`), and zero `${{` inside `run:`, all asserted in `tests/test_publish_workflow.py`. |
| **T-05-16** | `audit/overpass.py` validates every ISO-2 code against `^[A-Z]{2}$` before Overpass QL interpolation, caps opt-in runs at `MAX_OVERPASS_ISO2S = 10`, emits tags-only `out tags 500;` (never `out geom;`), enforces polite `>= 1.5s` `sleep_fn` pacing, and routes through `post_form_bytes_with_retry()` with exact allowlist `{"overpass-api.de"}`. |
| **T-05-17** | `audit/osm_speeds.py` enforces `WESTNORDOST_ALLOWED_HOSTS` (`{"westnordost.github.io", "raw.githubusercontent.com", "github.com"}`), bounded reads (`DEFAULT_MAX_RESPONSE_BYTES`), and `_sanitize_markdown_inline()` (neutralizing backticks, angle brackets, newlines, and table pipes) across all rendered Markdown reports, Step Summaries, and rolling issues. |
| **T-05-18** | `data/laws/speed_audit_allowlist.json` validated under strict `extra="forbid"` `SpeedAuditAllowlist` schema and automatically scanned by `tests/test_license_taint_gate.py` & `ets2v2 audit taint` with zero taint violations. |
| **T-05-SC** | Zero new PyPI runtime packages added (`pyproject.toml` and `uv.lock` unchanged); `.github/workflows/osm-speed-audit.yml` uses only first-party pinned actions (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/upload-artifact@v4`) and built-in `gh issue` CLI. |

## Deviations from Plan

None — plan executed as written.

## Known Stubs

None — all `src/ets2v2/audit/` modules, `fetch/http.py` `post_form_bytes_with_retry()`, independent `validate/` `ETS2V2-INV-LICENSE-TAINT` gate, clean-room `data/laws/speed_audit_allowlist.json`, `ets2v2 audit {osm-speeds,taint}` CLI subcommands, and `.github/workflows/osm-speed-audit.yml` are fully implemented and verified offline.

## Notes for Phase 5 Verification

- All 4 Phase 5 plans (`05-01`..`05-04`) covering `GLB-01`, `GLB-02`, `GLB-03`, and `GLB-04` are now complete on branch `gsd/phase-05-global-tier-1-2-3-coverage-internal-osm-audit`.
- Offline CI suite stands at **602 passed, 4 deselected** with `0` ruff lint/format issues, `0` strict `basedpyright` errors, `0` AST DAG violations, and `0` license-taint violations (`231` repo files scanned).
- End-of-phase workstation verification (`human_verify_mode: end-of-phase`) may optionally run the 4 workstation-local tests (`@pytest.mark.local_ets2` and `@pytest.mark.local_promods`) and a manual `workflow_dispatch` on `.github/workflows/osm-speed-audit.yml` after pushing.

## Self-Check: PASSED

- All 9 created files (`src/ets2v2/audit/{__init__,models,osm_speeds,overpass,taint}.py`, `data/laws/speed_audit_allowlist.json`, `.github/workflows/osm-speed-audit.yml`, `tests/test_{audit_osm_speeds,license_taint_gate}.py`) and all 9 modified files exist on disk; `pyproject.toml` and `uv.lock` are untouched.
- All three task commits (`835f4ec`, `a6fa08a`, `0de3c4f`) are verified ancestors of `HEAD` with zero accidental deletions and zero TODO/FIXME/placeholder stubs.
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, `602`-test offline `pytest`, `ets2v2 audit taint --json`, and offline `ets2v2 audit osm-speeds` smoke check) passed with zero errors.
