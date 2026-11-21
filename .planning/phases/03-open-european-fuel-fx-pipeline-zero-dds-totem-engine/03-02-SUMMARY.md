---
phase: 03-open-european-fuel-fx-pipeline-zero-dds-totem-engine
plan: "02"
subsystem: data-pipeline-fuel
tags: [fuel-collectors, ec-wob, openpyxl, circuit-breaker, prices-lock, snapshot-v1, ssrf, secret-redaction]
dependency_graph:
  requires:
    - "03-01 (hardened httpx transport, 4 FX providers, 39-territory currency map, PricesLockfile v1, AST DAG walls)"
    - "02-01 (locked schema_version=1 RealismSnapshot & 36-country law registry)"
  provides:
    - "Pure offline ets2v2.normalize.fuel bounds (0.01-5.00 EUR/L), +/-25% WoW circuit breaker with --allow-jump override, D-02 secondary-grade spreads, and EL->GR/UK->GB aliases"
    - "Deterministic 39-territory offline baseline seeder seed_initial_lockfile() and committed canonical state/prices.lock.json"
    - "Tier 1 European & EEA fuel collectors (EC Weekly Oil Bulletin dynamic Drupal .xlsx + FionnHughes & fuel-prices.eu fallbacks, UK DESNZ, NO SSB 09654, FR ODS v2.1, DE optional Tankerkoenig, ES MITECO, IT MIMIT, NL CBS 80416ned)"
    - "Full run_price_fetch() orchestrator & ets2v2 fetch CLI enforcing D-08 outage and 14d/30d staleness policies"
    - "Optional prices_lock injection in build_realism_snapshot() and ets2v2 registry snapshot --prices-lock preserving locked schema_version=1"
  affects:
    - "03-03 (Zero-DDS totem engine reading committed state/prices.lock.json offline)"
    - "03-04 (package builder/changelog fuel table, alerts, attributions, and Friday CI fetch wiring)"
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth unit conversion (EUR/1000L -> /1000, pence/L -> /100) paired with non-bypassable 0.01-5.00 EUR/L hard bounds and +/-25% WoW circuit breaker"
    - "Dynamic stdlib HTMLParser link discovery validated against per-collector HTTPS host allowlists (T-03-06)"
    - "OOXML read_only=True, data_only=True parsing with <=20 MiB byte cap and <=5000 row scan cap (T-03-08)"
    - "Double-scrubbed secret redaction (redact_url_secrets + literal key replacement) for optional TANKERKOENIG_API_KEY (T-03-07)"
    - "Atomic temp-file + os.replace() canonical lockfile persistence"
key-files:
  created:
    - src/ets2v2/normalize/fuel.py
    - src/ets2v2/fetch/ec_bulletin.py
    - src/ets2v2/fetch/national.py
    - src/ets2v2/fetch/pipeline.py
    - state/prices.lock.json
    - tests/test_normalize_fuel.py
    - tests/test_fetch_fuel.py
    - tests/test_fetch_pipeline.py
  modified:
    - src/ets2v2/normalize/__init__.py
    - src/ets2v2/normalize/lockfile.py
    - src/ets2v2/fetch/__init__.py
    - src/ets2v2/registry/snapshot.py
    - src/ets2v2/cli.py
    - tests/test_registry_snapshot.py
decisions:
  - "Exempted initial baseline_1.62_seeded bootstrap entries from the +/-25% week-over-week jump check inside normalize_country_fuel_prices() (while preserving unconditional 0.01-5.00 EUR/L hard bounds) so the first live Friday CI fetch transitions smoothly from ETS2 1.62's 2022 peak diesel prices to 2026 Tier 1 prices without false WoW rejections."
  - "Computed 3-decimal ROUND_HALF_UP diesel eur_per_liter from the unrounded live diesel local price before 4-decimal local_prices quantization so sub-basis-point rounding boundaries (e.g. 1.7855 -> 1.786) remain exact."
  - "Delegated run_price_fetch(..., fx_only=True) directly to run_fx_only_fetch() to preserve 100% backwards compatibility with Plan 03-01 CLI tracer tests and FX-only workflows."
  - "Upgraded write_prices_lockfile() to atomic sibling-temp write + os.replace() so interrupted runs never leave truncated state/prices.lock.json files on disk."
metrics:
  duration: "19m"
  completed: "2026-11-21"
status: complete
actuals:
  tokens: 48172
  tasks: 3
  commits: 3
plan_head_before: 3b9e0513d3c9d330da9a16c4913062e91ee98bc8
plan_head_after: 753400cc786fda499640373f002aa90bf4663dd5
---

# Phase 3 Plan 02: Tier 1 European Fuel Collectors, Circuit Breaker & Seeded `prices.lock.json` Summary

Built the pure offline fuel bounds/circuit-breaker & D-02 secondary-grade spread normalizer, all 10 fault-isolated European/EEA fuel collectors (`EC Weekly Oil Bulletin` dynamic Drupal `.xlsx`, `FionnHughes` CSV & `fuel-prices.eu` CC BY 4.0 fallbacks, `UK DESNZ`, `NO SSB 09654`, `FR` ODS v2.1, optional `DE` `Tankerkönig`, `ES` MITECO, `IT` MIMIT, `NL` CBS `80416ned`), the `run_price_fetch()` orchestrator & `ets2v2 fetch` CLI, committed the deterministic 39-territory `state/prices.lock.json`, and wired optional `prices_lock` injection into locked `schema_version=1` `build_realism_snapshot()`.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Build offline fuel circuit-breaker/spread normalizer, 39-territory baseline seeder, and EC Weekly Oil Bulletin + CC BY 4.0 fallback collectors | `406d8a8` | `src/ets2v2/normalize/{fuel,lockfile,__init__}.py`, `src/ets2v2/fetch/ec_bulletin.py`, `tests/test_normalize_fuel.py`, `tests/test_fetch_fuel.py` |
| 2 | Build Tier 1 national multi-grade fuel collectors (`UK DESNZ`, `NO SSB 09654`, `FR`, `DE` optional `Tankerkönig`, `ES` MITECO, `IT` MIMIT, `NL` CBS) | `e7aed09` | `src/ets2v2/fetch/{national,__init__}.py`, `tests/test_fetch_fuel.py` |
| 3 | Wire `run_price_fetch()` pipeline, full `ets2v2 fetch` CLI, committed 39-territory `state/prices.lock.json`, and `RealismSnapshot` v1 price injection | `753400c` | `src/ets2v2/fetch/{pipeline,__init__}.py`, `src/ets2v2/registry/snapshot.py`, `src/ets2v2/cli.py`, `state/prices.lock.json`, `tests/test_fetch_pipeline.py`, `tests/test_registry_snapshot.py` |

## Verification Results

- `uv run --offline ets2v2 fetch --seed-offline --lock-path state/prices.lock.json --dry-run --json`: exited `0` (`ok: true`, `countries_fallback: 39`, `fx_currencies_validated: 17`, `alerts: []`)
- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `80 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2"`: **312 passed, 2 deselected** (100% offline via `httpx.MockTransport` and in-memory `openpyxl.Workbook`, including all 4 AST DAG isolation walls in `tests/test_cli_scaffold.py` and all existing Phase 2 snapshot tests)

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-03-06** | `discover_ec_wob_xlsx_url()` and `discover_uk_desnz_csv_url()` resolve relative `<a href>` with `urljoin()` and enforce `validate_https_url()` against strict per-collector HTTPS allowlists (`energy.ec.europa.eu`/`ec.europa.eu`; `www.gov.uk`/`assets.publishing.service.gov.uk`), rejecting HTTP and off-domain links. Verified in `tests/test_fetch_fuel.py`. |
| **T-03-07** | `fetch_de_tankerkoenig()` reads `TANKERKOENIG_API_KEY` from arg/env only, passes via `httpx` params, scrubs all error messages with `redact_url_secrets()` + literal key replacement, and never writes secrets to `FetchRunReport` or `state/prices.lock.json`. Verified with negative assertions in `tests/test_fetch_fuel.py` and `tests/test_fetch_pipeline.py`. |
| **T-03-08** | `parse_ec_wob_xlsx()` enforces `<= 20 MiB` (`20_971_520` bytes) cap before opening, uses `openpyxl.load_workbook(..., read_only=True, data_only=True)`, caps scanned rows at `<= 5000`, and closes the workbook in a `finally` block. Verified in `tests/test_fetch_fuel.py`. |
| **T-03-09** | `EUR/1000L` (`/1000`) and `pence/L` (`/100`) scaling occurs at collector boundaries; `normalize_country_fuel_prices()` enforces non-bypassable `[0.01, 5.00]` EUR/L hard bounds + `±25%` WoW circuit breaker; `DE`, `ES`, and `IT` aggregate station prices via outlier-resilient `statistics.median`. Verified in `tests/test_normalize_fuel.py` and `tests/test_fetch_fuel.py`. |
| **T-03-10** | `run_price_fetch()` returns `ok=False` (CLI exit `1`) without overwriting `state/prices.lock.json` when `0` Tier 1 fuel feeds succeed (`total_tier1_outage`), retains lockfile entries with `feed_outage` alerts on partial outages (`ok=True`, exit `0`), and appends `stale_tier1` (`>14d`) / `stale_fallback` (`>30d`) alerts. Verified in `tests/test_fetch_pipeline.py`. |
| **T-03-11** | `build_realism_snapshot(..., prices_lock=...)` preserves locked `schema_version: 1` (`extra="forbid"`), validates `lock_entry.currency == law.currency`, keeps `IE`/`CY`/`MT` strictly excluded from 36-country Core snapshots, and leaves all Phase 2 `prices_lock=None` tests untouched. Verified in `tests/test_registry_snapshot.py`. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserve exact pre-quantization precision when computing 3-decimal `eur_per_liter`**
- **Found during:** Task 1 (`test_normalize_country_fuel_prices_uses_3dp_round_half_up_for_eur_per_liter`)
- **Issue:** Quantizing `live_local_prices["diesel"]` to 4 decimals before dividing by `rate_per_eur` shifted `1.49982 / 0.84 = 1.7855` to `1.785476...` (`1.785` instead of `1.786`).
- **Fix:** Compute `diesel_eur` from `live_local_prices.get("diesel", full_local_prices["diesel"]) / rate` before 4-decimal local price rounding.
- **Files modified:** `src/ets2v2/normalize/fuel.py`
- **Commit:** `406d8a8`

**2. [Rule 1 - Bug] Allow initial `baseline_1.62_seeded` bootstrap entries to transition cleanly to live Tier 1 prices**
- **Found during:** Task 3 (`test_run_price_fetch_outage_and_staleness_policies_d08`)
- **Issue:** ETS2 `1.62` `countries.json` stores 2022 peak diesel prices (e.g. `IT = 2.228 EUR/L`), which differ by `> 25%` from realistic 2026 Tier 1 prices (`IT = 1.710 EUR/L`, `lpg = 0.740`), causing the WoW circuit breaker to reject initial live updates against `baseline_1.62_seeded`.
- **Fix:** Skip the `±25%` WoW comparison when `previous_entry.source == "baseline_1.62_seeded"` while keeping the `[0.01, 5.00]` EUR/L hard bounds unconditionally active on every fetch and retaining full `±25%` WoW protection on all live-to-live transitions.
- **Files modified:** `src/ets2v2/normalize/fuel.py`
- **Commit:** `753400c`

## Known Stubs

None. All 10 European/EEA collectors, the full `run_price_fetch()` pipeline, the `ets2v2 fetch` CLI, the committed 39-territory `state/prices.lock.json`, and `build_realism_snapshot(..., prices_lock=...)` are fully wired and verified offline.

## Self-Check: PASSED

- All 14 created/modified files (`src/ets2v2/normalize/{fuel,lockfile,__init__}.py`, `src/ets2v2/fetch/{ec_bulletin,national,pipeline,__init__}.py`, `src/ets2v2/registry/snapshot.py`, `src/ets2v2/cli.py`, `state/prices.lock.json`, `tests/{test_normalize_fuel,test_fetch_fuel,test_fetch_pipeline,test_registry_snapshot}.py`) exist on disk and are tracked cleanly in git.
- All 3 task commits (`406d8a8`, `e7aed09`, `753400c`) are verified ancestors of `HEAD`.
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, `pytest -q --tb=short -m "not local_ets2"`) passed with 0 errors and 312 tests passing.
