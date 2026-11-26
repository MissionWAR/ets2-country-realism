---
phase: 05-global-tier-1-2-3-coverage-internal-osm-audit
plan: "03"
subsystem: tier2-portals-staleness-changelog
tags: [tier2-portals, html-parser, circuit-breaker, staleness, changelog, global-coverage, ci-workflow]
dependency_graph:
  requires:
    - "05-01 (225-territory & 151-FX global registry foundation, TIER3_CURATED_BASELINE_SOURCE)"
    - "05-02 (shared validate_ooxml_zip_safety(), RawFuelFeedResult tier='tier2'/error_code, FetchRunReport tier2_feeds_*, pipeline error_code propagation)"
  provides:
    - "Stdlib-only HTML table/text extractors (`TableExtractor`, `TextExtractor`, `extract_html_tables`, `extract_html_text`) and multi-charset fallback decoder (`decode_with_fallbacks`, `Tier2EncodingError`) in `src/ets2v2/fetch/_html.py` with zero new runtime dependencies"
    - "All 10 research-gated Tier 2 national portal scrapers (`is_gasvaktin`, `ch_bfs_lik`, `md_anre`, `mk_erc`, `ru_rosstat`, `il_moe`, `ae_moei`, `za_dmre_cef`, `sa_aramco`, `ng_nbs`) wrapped in per-country `_run_tier2_guarded()` circuit breakers (`tier2_rate_limited`, `tier2_portal_outage`, `tier2_encoding_error`, `tier2_selector_drift`) in `src/ets2v2/fetch/tier2_portals.py`, while `KE`/`ID`/`JO`/`EG` stay cleanly classified as Tier 3"
    - "Pipeline Tier 2 wiring at `_FEED_PRECEDENCE = 25` (strictly above `fuel_prices_eu: 10` for automatic EU fallback) and `--no-tier2` CLI flag on `ets2v2 fetch`"
    - "5-tier cadence-aware `evaluate_lockfile_staleness()` (`14d` `stale_tier1`, `45d` `stale_tier2_monthly`, `105d` `stale_tier2_quarterly`, `30d` `stale_fallback`, `180d` `stale_tier3_curated`) in `src/ets2v2/normalize/lockfile.py`"
    - "Core-36 fuel table, compact `## Global Snapshot Coverage` block, noise-controlled Tier 3 staleness/fallback and extended-FX rollups, and expanded Global Tier 1 & Tier 2 open-data attributions across `src/ets2v2/publish/changelog.py` and `.github/workflows/phase-a-release.yml`"
  affects:
    - "05-04 (Isolated `src/ets2v2/audit/` subpackage, monthly OSM speed-limit drift audit, and automated `CC BY 4.0` license-taint gate across all finalized Phase 5 sources, data, snapshots, and changelogs)"
tech-stack:
  added: []
  patterns:
    - "Pure-stdlib streaming `html.parser.HTMLParser` nested table/text extraction (`src/ets2v2/fetch/_html.py`) rejecting `<script>`/`<style>` noise without `beautifulsoup4` or `lxml` (`D-06`)"
    - "Strict per-country fault-isolated circuit breaker (`_run_tier2_guarded()`) mapping every HTTP 403/429, timeout/5xx, charset failure, or selector drift to structured `warning`-only `tier2_*` alerts with zero Friday CI breakage (`D-07`)"
    - "Precedence-25 Tier 2 placement enabling automatic live `fuel_prices_eu` (`10`) fallback for European Tier 2 portals (`IS`, `CH`, `MD`, `MK`) while retaining lockfile/Tier 3 baselines for non-EU portals"
    - "5-tier cadence-aware staleness (`14d`/`45d`/`105d`/`30d`/`180d`) plus compact Tier 3 alert/fallback rollups keeping `CHANGELOG_{SUMMER,WINTER}.md` and GitHub Step Summary/PR body free of 140+ Tier 3 noise rows (`D-08`, `D-12`)"
key-files:
  created:
    - src/ets2v2/fetch/_html.py
    - src/ets2v2/fetch/tier2_portals.py
    - tests/test_fetch_tier2_portals.py
  modified:
    - src/ets2v2/fetch/pipeline.py
    - src/ets2v2/fetch/__init__.py
    - src/ets2v2/cli.py
    - src/ets2v2/normalize/lockfile.py
    - src/ets2v2/normalize/__init__.py
    - src/ets2v2/publish/changelog.py
    - .github/workflows/phase-a-release.yml
    - tests/test_fetch_pipeline.py
    - tests/test_normalize_fuel.py
    - tests/test_publish_release.py
    - tests/test_publish_workflow.py
decisions:
  - "Used a frame stack in `TableExtractor(HTMLParser)` so nested `<table>` layouts extract both inner and outer tables deterministically while ignoring `<script>`/`<style>` content and normalizing `<br>` tags and HTML character entities."
  - "Applied strict ordered charset lists per portal (`('utf-8-sig',)` for UTF-8 portals and `('utf-8-sig', 'windows-1251')` for Cyrillic portals `RU`/`MK`, while keeping `decode_with_fallbacks()` default at `('utf-8-sig', 'windows-1251', 'latin-1')`) so corrupt binary payloads reliably raise `Tier2EncodingError` -> `tier2_encoding_error` rather than silently decoding as Latin-1."
  - "Kept source-tier classification constants (`_EU_TIER1_SOURCES`, `_GLOBAL_TIER1_SOURCES`, `_TIER2_PORTAL_SOURCES`) local to `src/ets2v2/publish/changelog.py` so `ets2v2.publish` maintains zero imports from `ets2v2.fetch` under the AST offline DAG isolation wall."
metrics:
  duration: "65m active execution (incl. 46m full pytest suite)"
  completed: "2026-11-26"
status: complete
actuals:
  tokens: 34259
  tasks: 3
  commits: 3
plan_head_before: 970fbf6a95b3f7438a5967e9bc2666d22ebdcf58
plan_head_after: 993b6816db8ea75742f08c40a2f8e1e232364776
---

# Phase 5 Plan 03: Tier 2 Guarded National Portals, 5-Tier Staleness & Changelog Rollups Summary

Built stdlib-only HTML table/text extractors and multi-charset decoding in `src/ets2v2/fetch/_html.py` (zero new dependencies per `D-06`), implemented all **10 research-gated Tier 2 national portal scrapers** (`IS` Gasvaktin MIT JSON, `CH` BFS/LIK PxWeb/CSV, `MD` ANRE HTML, `MK` ERC Cyrillic/Latin HTML, `RU` Rosstat UTF-8/`windows-1251` HTML/XLSX, `IL` MoE regulated 95 ceiling, `AE` MOEI monthly HTML, `ZA` DMRE/CEF cents/L->ZAR/L HTML/XLSX, `SA` Aramco HTML, `NG` NBS AGO/PMS XLSX) inside strict per-country `_run_tier2_guarded()` circuit breakers in `src/ets2v2/fetch/tier2_portals.py` while cleanly leaving Cloudflare/JS-SPA/PDF-gated `KE`/`ID`/`JO`/`EG` in Tier 3 (`D-05`, `D-07`), wired Tier 2 into `fetch/pipeline.py` at `_FEED_PRECEDENCE = 25` with `--no-tier2` CLI support, upgraded `evaluate_lockfile_staleness()` to the 5-tier `14d`/`45d`/`105d`/`30d`/`180d` cadence schedule (`D-08`), and added compact **Global Snapshot Coverage**, noise-controlled Tier 3 & extended-FX alert rollups, and expanded open-data attributions across `src/ets2v2/publish/changelog.py` and `.github/workflows/phase-a-release.yml` (`D-08`, `D-12`).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Build stdlib-only `fetch/_html.py` and tracer Tier 2 guarded collectors (`IS`, `MD`, `MK`, `AE`) with `_run_tier2_guarded()` circuit breaker | `3ab0523` | `src/ets2v2/fetch/{_html,tier2_portals}.py`, `tests/test_fetch_tier2_portals.py` |
| 2 | Expand `tier2_portals.py` with remaining 6 guarded collectors (`CH`, `RU`, `IL`, `ZA`, `SA`, `NG`), wire into `fetch/pipeline.py` at precedence `25`, and expose `--no-tier2` CLI flag | `83157de` | `src/ets2v2/fetch/{tier2_portals,pipeline,__init__}.py`, `src/ets2v2/cli.py`, `tests/test_fetch_{tier2_portals,pipeline}.py` |
| 3 | Implement 5-tier `evaluate_lockfile_staleness()` (`D-08`), noise-controlled Tier 3 rollups & Global Snapshot Coverage in `publish/changelog.py` (`D-08`, `D-12`), and Friday CI summary updates | `993b681` | `src/ets2v2/normalize/{lockfile,__init__}.py`, `src/ets2v2/publish/changelog.py`, `.github/workflows/phase-a-release.yml`, `tests/test_{normalize_fuel,publish_release,publish_workflow}.py` |

## Achieved Coverage & Contracts

- **Stdlib-only HTML/charset parsing (`D-06`):** `src/ets2v2/fetch/_html.py` provides `TableExtractor(HTMLParser)`, `TextExtractor(HTMLParser)`, `extract_html_tables()`, `extract_html_text()`, `decode_with_fallbacks()`, and `Tier2EncodingError` using pure Python stdlib with zero third-party parser dependencies (`pyproject.toml` and `uv.lock` remain strictly locked at 5 runtime packages).
- **Research-gated Tier 2 national portal roster (`D-05`, `D-07`):** Exact 10 isolated collectors (`is_gasvaktin`, `ch_bfs_lik`, `md_anre`, `mk_erc`, `ru_rosstat`, `il_moe`, `ae_moei`, `za_dmre_cef`, `sa_aramco`, `ng_nbs`) wrapped in `_run_tier2_guarded()` mapping every failure deterministically to `tier2_rate_limited` (`403`/`429`), `tier2_encoding_error`, `tier2_selector_drift`, or `tier2_portal_outage` warning alerts; `KE`, `ID`, `JO`, and `EG` remain cleanly classified in Tier 3.
- **Precedence & Circuit-Breaker Safety (`D-07`):** All 10 Tier 2 feeds sit at `_FEED_PRECEDENCE = 25` (above `fuel_prices_eu: 10`), so European Tier 2 failures (`IS`/`CH`/`MD`/`MK`) automatically fall back to live `fuel_prices_eu`, non-EU Tier 2 failures retain lockfile/Tier 3 baselines, accepted quotes still pass `[0.01, 5.00]` EUR/L & `±25%` WoW guards (`IL`'s regulated `petrol_95`-only ceiling cleanly derives `diesel`), Tier 2 outages never fail Friday CI, and `ets2v2 fetch --no-tier2` skips all 10 portals.
- **5-Tier Cadence-Aware Staleness (`D-08`):** `evaluate_lockfile_staleness()` enforces `14d` weekly live Tier 1 (`stale_tier1`), `45d` monthly live Tier 1/2 (`stale_tier2_monthly`), `105d` quarterly Tier 2 (`stale_tier2_quarterly`), `30d` degraded fallback/Core+ProMods seed (`stale_fallback`), and `180d` Tier 3 curated global baseline (`stale_tier3_curated`), while remaining 100% compatible with Phase 3/4 tests.
- **Changelog & Friday CI Rollups (`D-08`, `D-12`):** `CHANGELOG_{SUMMER,WINTER}.md` keeps `## 36-Country Fuel Price Summary` at exactly 36 Core Vanilla+DLC rows, adds `## Global Snapshot Coverage` (`225` territories + tier breakdown) right before `## Attribution & Licensing`, expands open-data attributions for all integrated Global Tier 1 & Tier 2 sources, rolls up `stale_tier3_curated` + Tier 3 curated fallbacks into one compact summary line (and summarizes >20 extended FX fallbacks cleanly), and mirrors Tier 2 counters + `stale_tier3_curated` rollups in `.github/workflows/phase-a-release.yml` Step Summary & PR body (preserving `def _sanitize(` >= 2 and zero `${{` inside `run:`).

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `112 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, Python `3.12`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **576 passed, 4 deselected** (+31 new tests: `19` in `tests/test_fetch_tier2_portals.py`, `3` in `tests/test_fetch_pipeline.py`, `7` in `tests/test_normalize_fuel.py`, `1` in `tests/test_publish_release.py`, `1` in `tests/test_publish_workflow.py`)
- `uv run --offline ets2v2 fetch --seed-offline --no-global --no-tier2 --lock-path <tmp>/prices.lock.json --dry-run --json`: exit `0`, `ok: true`, `countries_fallback: 225`, `fx_currencies_validated: 151`, `tier2_feeds_succeeded: 0`, `tier2_feeds_failed: 0`
- `uv run --offline ets2v2 publish release --state <tmp>/published.json --prices-lock state/prices.lock.json --out-dir <tmp>/dist --changelogs-dir <tmp>/cl --force --json`: exit `0`, `validation_ok: true` for both Summer & Winter editions, generating validated bundles, `225`-territory v1 snapshots, and changelogs with Core-36 fuel table, Global Snapshot Coverage, Tier 3 rollup, and expanded attributions

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-05-10** | Stdlib `HTMLParser` (`src/ets2v2/fetch/_html.py`) with non-backtracking regexes, strict `decode_with_fallbacks()` raising `Tier2EncodingError`, and per-country `_run_tier2_guarded()` mapping `403`/`429`, timeouts, charset errors, and selector drift to warning-only `tier2_*` alerts with zero CI breakage. |
| **T-05-11** | Exact per-portal HTTPS host allowlists enforced via `fetch_bytes_with_retry()` and `validate_https_url()` on all initial URLs, redirects, and discovered `.xlsx` links (`RU`, `ZA`, `NG`), with `TIER2_MAX_XLSX_BYTES` (20 MiB), `TIER2_MAX_XLSX_ROWS` (5000), and shared `validate_ooxml_zip_safety()` blocking XXE/ZIP bombs before `openpyxl`. |
| **T-05-12** | Explicit `ZA` ZAR cents/L (`> 100.0`) ÷ `100.0` conversion, `parse_positive_float()` validation, and mandatory `[0.01, 5.00]` EUR/L + `±25%` WoW guards verified in pipeline tests rejecting corrupt `<0.01 EUR/L` and `+80%` WoW Tier 2 quotes. |
| **T-05-13** | All alert strings sanitized through `_sanitize_markdown_inline()` (`changelog.py`) and `def _sanitize(` (`>= 2` in `phase-a-release.yml`), Tier 3 staleness/fallback aggregated into compact summary lines, and zero `${{` inside any `run:` block. |
| **T-05-SC** | Zero new runtime dependencies added (`pyproject.toml` and `uv.lock` unchanged; 5-package pin verified in `tests/test_cli_scaffold.py`). |

## Deviations from Plan

None — plan executed as written. One small inline fix during Task 1 TDD (`Rule 1` inline): `fetch/_parsing.py`'s `extract_iso_date()` uses `\b(\d{4}-\d{2}-\d{2})\b` which does not match ISO timestamps joined with `T` (`2026-11-24T08:00:00.000` in Gasvaktin JSON); `_extract_portal_date()` in `tier2_portals.py` added a non-digit boundary regex `(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)` so ISO-8601 timestamps parse cleanly alongside `DD.MM.YYYY` and `Month YYYY` portal dates.

## Known Stubs

None — all 10 Tier 2 national portal scrapers, stdlib HTML/charset helpers, pipeline precedence & `--no-tier2` wiring, 5-tier staleness evaluation, and changelog/workflow rollups are fully implemented and verified offline.

## Handoff Notes for Plan 05-04

- All Phase 5 online fuel collectors (EU Tier 1, Global Tier 1, and Tier 2 guarded portals) and open-data changelog attributions are now finalized and verified zero-taint (`U.S. EIA`, no forbidden markers), ready for Plan `05-04`'s isolated `src/ets2v2/audit/` subpackage, universal Phase 5 AST DAG quarantine wall, independent `validate/` `ETS2V2-INV-LICENSE-TAINT` check, and automated repo/snapshot/package taint gate.
- `tests/test_cli_scaffold.py` still reflects Phase 4's package layout and AST walls (intentionally untouched in `05-03`); Plan `05-04` will unlock `"audit"` and enforce the universal Phase 5 AST DAG quarantine across all 10 non-audit subpackages.

## Self-Check: PASSED

- All 3 created files (`src/ets2v2/fetch/_html.py`, `src/ets2v2/fetch/tier2_portals.py`, `tests/test_fetch_tier2_portals.py`) and all 11 modified files exist on disk; `pyproject.toml` and `uv.lock` are untouched.
- All three task commits (`3ab0523`, `83157de`, `993b681`) are verified ancestors of `HEAD` with zero accidental deletions.
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, offline CLI `fetch --seed-offline --no-global --no-tier2` & `publish release`, and `576`-test offline `pytest`) passed with zero errors.
