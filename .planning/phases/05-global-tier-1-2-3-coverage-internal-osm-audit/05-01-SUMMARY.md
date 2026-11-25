---
phase: 05-global-tier-1-2-3-coverage-internal-osm-audit
plan: "01"
subsystem: global-registry-normalize-lockfile
tags: [pydantic-v2, iso-4217, iso-3166-1, tier3-baselines, fx-isolation, timezone-overrides, realism-snapshot-v1, clean-room]
dependency_graph:
  requires:
    - "04-01 (76-territory ProMods registry, country_aliases.json, FX CI isolation, and locked RealismSnapshot v1)"
    - "04-04 (compose-local orchestrator and hardcoded numeric totem patcher)"
  provides:
    - "Clean-room schema_version=1 data/mappings/currencies.json (151 active ISO-4217 currencies incl. XCG/ZWG/SLE/SYP, 18 extended ECB currencies, exact 225 ISO-2 territory mappings) and data/curated/tier3_fuel_baselines.json (186 non-Vanilla EUR/L baselines with verified_date and clamped_to_floor metadata for IR/VE)"
    - "Data-driven Pydantic v2 loaders in src/ets2v2/normalize/currencies.py preserving all Phase 3/4 constant exports and all 6 offline AST DAG isolation walls"
    - "Global FX cross-validation isolating 134 extended global currencies under is_extended=True while keeping 16 Core European non-EUR currencies strictly hard-gated and default include_extended=False at 17 Core currencies"
    - "225 canonical CountryLawRecord JSON files under data/laws/countries/ (36 vanilla_1_62=true + 189 vanilla_1_62=false) and data/mappings/ets2_countries.json achieving 100% coverage of all country_aliases.json ISO-2 targets (closing all 13 Phase 4 gaps)"
    - "75 verified IANA_NUMERIC_ABBR_OVERRIDES (+58 global zones incl. seasonal tuples America/Santiago and America/Miquelon) eliminating numeric TZ strings across all 225 territories in Summer & Winter"
    - "Committed 225-territory / 151-FX state/prices.lock.json (schema_version=1) with IR/VE floor-clamped at 0.010 EUR/L while Vanilla+DLC Core Workshop builds remain strictly at 36 countries / 579 files"
  affects:
    - "05-02 (Non-EU Tier 1 live fuel collectors flowing directly into ALL_LOCKFILE_TERRITORY_ISO2S & ALL_TERRITORY_CURRENCIES without quote drops)"
    - "05-03 (Tier 2 guarded national portal scrapers, 5-tier staleness evaluation, and Global Snapshot Coverage changelogs)"
    - "05-04 (Isolated src/ets2v2/audit/ OSM speed-limit drift auditor and CC BY 4.0 license-taint gate across all 225 law files, registries, and lockfile)"
tech-stack:
  added: []
  patterns:
    - "Data-driven @functools.lru_cache frozen Pydantic v2 JSON loaders in Layer 5 normalize/ using pure stdlib pathlib/json + pydantic (zero registry/httpx/openpyxl imports)"
    - "Shared SEEDED_LOCKFILE_SOURCES constant uniting baseline_1.62_seeded, promods_curated_seed, and tier3_curated_baseline across normalize/fuel.py, normalize/lockfile.py, and fetch/pipeline.py"
    - "Explicit clamped_to_floor=true metadata at 0.010 EUR/L solely on curated Tier 3 baselines (IR/VE) while preserving hard [0.01, 5.00] EUR/L bounds on all live fuel feeds"
key-files:
  created:
    - data/mappings/currencies.json
    - data/curated/tier3_fuel_baselines.json
    - tests/test_global_registry_expansion.py
    - "data/laws/countries/*.json (149 new canonical global CountryLawRecord files; 225 total)"
  modified:
    - src/ets2v2/normalize/currencies.py
    - src/ets2v2/normalize/fx.py
    - src/ets2v2/normalize/fuel.py
    - src/ets2v2/normalize/lockfile.py
    - src/ets2v2/normalize/totem_format.py
    - src/ets2v2/normalize/__init__.py
    - src/ets2v2/registry/timezone.py
    - src/ets2v2/fetch/pipeline.py
    - data/mappings/ets2_countries.json
    - state/prices.lock.json
    - tests/test_compose_local.py
    - tests/test_fetch_fuel.py
    - tests/test_fetch_fx.py
    - tests/test_fetch_pipeline.py
    - tests/test_hardcoded_totems.py
    - tests/test_merge_aliases.py
    - tests/test_normalize_fuel.py
    - tests/test_normalize_fx.py
    - tests/test_publish_release.py
    - tests/test_registry_contracts.py
    - tests/test_registry_snapshot.py
    - tests/test_registry_timezone.py
decisions:
  - "Enforced exact currency bijection in data/mappings/currencies.json: all 225 canonical territories map cleanly to 151 unique active ISO-4217 currencies (1 pinned EUR + 16 Core European required + 134 Extended Global, incl. 18 EXTENDED_ECB_CURRENCIES and post-2025/2026 XCG, ZWG, SLE, SYP) with zero unreferenced orphan currencies."
  - "Preserved promods_curated_seed provenance on the 37 ProMods extended territories and assigned tier3_curated_baseline (CC BY 4.0) to the 149 new global territories, exporting shared SEEDED_LOCKFILE_SOURCES from normalize/fuel.py so first live Tier 1/2 transitions and weekly FX repricing work uniformly."
  - "Preserved promods_reference_fx fallback provider naming on the 24 ProMods extended currencies and introduced global_reference_fx for the 110 additional extended global currencies."
metrics:
  duration: "95m"
  completed: "2026-11-25"
status: complete
actuals:
  tokens: 267940
  tasks: 3
  commits: 3
plan_head_before: c8f851d3e04b2f46199a0d0d913f941775279184
plan_head_after: a7b8a262516d3eaafd393600ae7155878ab67cce
---

# Phase 5 Plan 01: Global 225-Territory & 151-Currency Registry Foundation Summary

Externalized global ISO-4217 currency/FX metadata (`data/mappings/currencies.json`, **151** active currencies, **18** extended ECB currencies, **225** territory mappings) and clean-room Tier 3 EUR/L fuel baselines (`data/curated/tier3_fuel_baselines.json`, **186** baselines with `IR`/`VE` floor-clamped at `0.010 EUR/L`) into frozen Pydantic v2-validated JSON registries, expanded `data/laws/countries/`, `data/mappings/ets2_countries.json`, and `state/prices.lock.json` from `76` to **`225`** canonical territories (`36` `vanilla_1_62: true` + `189` `vanilla_1_62: false`, achieving 100% `country_aliases.json` ISO-2 coverage) with **`+58`** verified global `IANA_NUMERIC_ABBR_OVERRIDES` (`75` total), isolated all `134` non-Core global currencies under `is_extended=True`, kept `RealismSnapshot` frozen at `schema_version: 1` and Vanilla+DLC Core builds strictly at `36` countries (`579` Workshop files), and updated all impacted Phase 2–4 regression suites to green.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Build clean-room `data/mappings/currencies.json` & `data/curated/tier3_fuel_baselines.json` with Pydantic-validated data-driven normalize loaders, extended FX isolation, and `0.010 EUR/L` floor support | `602001e` | `data/mappings/currencies.json`, `data/curated/tier3_fuel_baselines.json`, `src/ets2v2/normalize/{currencies,fx,fuel,lockfile,totem_format,__init__}.py`, `src/ets2v2/fetch/pipeline.py`, `tests/test_global_registry_expansion.py` |
| 2 | Add `58` global `IANA_NUMERIC_ABBR_OVERRIDES`, expand `data/laws/countries/` & `data/mappings/ets2_countries.json` to `225` canonical territories (100% alias target coverage), and regenerate `225`-territory `state/prices.lock.json` | `e594204` | `src/ets2v2/registry/timezone.py`, `data/mappings/ets2_countries.json`, `data/laws/countries/*.json` (149 new), `state/prices.lock.json`, `tests/test_global_registry_expansion.py` |
| 3 | Update all impacted Phase 2–4 regression test suites (`11` planned + `tests/test_compose_local.py`) to the `225`-territory / `151`-FX global baseline | `a7b8a26` | `tests/test_{compose_local,fetch_fuel,fetch_fx,fetch_pipeline,hardcoded_totems,merge_aliases,normalize_fuel,normalize_fx,publish_release,registry_contracts,registry_snapshot,registry_timezone}.py` |

## Achieved Counts

- **Canonical territories:** `225` (`36` `vanilla_1_62: true` + `189` `vanilla_1_62: false` = all `195` UN member/observer states + `XK` + `8` ProMods territories + `21` inhabited global map-combo territories)
- **ISO-4217 currencies:** `151` (`1` pinned `EUR` + `16` Core European required + `134` Extended Global, incl. `18` `EXTENDED_ECB_CURRENCIES`, `XCG`, `ZWG`, `SLE`, and post-2026 redenominated `SYP`)
- **Tier 3 curated fuel baselines:** `186` (`37` ProMods + `149` new global; `IR` & `VE` explicitly clamped and annotated at `0.010 EUR/L`)
- **Global IANA numeric TZ overrides:** `75` total (`17` existing + `58` new global overrides, incl. seasonal tuples `America/Santiago` and `America/Miquelon`; `0` numeric or `UTC±` fallback TZ strings across all `225` territories in both Summer & Winter)
- **`country_aliases.json` ISO-2 target coverage:** `100%` (`37/37` unique targets covered, closing all `13` previously missing targets: `AE`, `BR`, `EC`, `GQ`, `GY`, `ID`, `JP`, `PG`, `PY`, `SD`, `TL`, `UY`, `ZA`)
- **Core Vanilla+DLC Workshop boundary:** Strictly `36` countries / `579` Workshop files (`RealismSnapshot` frozen at `schema_version: 1`)
- **Runtime dependencies:** Strictly locked at `5` (`pyproject.toml` and `uv.lock` untouched)

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `107 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, Python `3.12`)
- `uv run --offline ets2v2 registry validate`: `Registry validation passed (225 countries).`
- `uv run --offline ets2v2 registry snapshot --season summer --prices-lock state/prices.lock.json --out <scratch>/snap_summer.json`: `schema_version: 1`, `225 countries`
- `uv run --offline ets2v2 package build --edition summer --out-dir <scratch>/core_verify`: `579 files`, `36` country `.sui` files
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **526 passed, 4 deselected** (zero failures across all Phase 1–5 offline suites)

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-05-01** | `load_currency_registry()` and `load_tier3_fuel_baselines()` enforce UTF-8 no-BOM LF hygiene, strict frozen `ConfigDict(strict=True, frozen=True, extra="forbid")` Pydantic v2 models, `allow_inf_nan=False`, sanity band containment on `reference_rate_per_eur`, `[0.01, 5.00]` EUR/L bounds, and clean-room taint-free assertions across all `225` law files, `ets2_countries.json`, `currencies.json`, and `tier3_fuel_baselines.json`. |
| **T-05-02** | All `134` non-Core global currencies are isolated under `is_extended=True` with explicit post-redenomination sanity envelopes (`XCG`, `ZWG`, `SLE`, `SYP`), falling back cleanly via `fx_reference_fallback` warnings while missing Core European currencies (e.g., `PLN`) still hard-fail (`ok=False`). |
| **T-05-03** | Hard `[0.01, 5.00]` EUR/L bounds remain strictly enforced on live `normalize_country_fuel_prices()` inputs, while ultra-subsidized `IR` and `VE` are explicitly clamped and annotated (`clamped_to_floor: true`, `0.010 EUR/L`) solely in `data/curated/tier3_fuel_baselines.json`. |
| **T-05-04** | `src/ets2v2/normalize/currencies.py` loads JSON purely via stdlib `pathlib` + `functools.lru_cache` + `pydantic`; all 6 AST-enforced offline DAG walls pass in `tests/test_cli_scaffold.py`. |
| **T-05-SC** | Zero new runtime dependencies added (`pyproject.toml` and `uv.lock` unchanged). |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug / Estimate Refinement] Exact `151` unique active ISO-4217 currencies across the `225` territories (vs `~156` pre-deduplication research estimate)**
- **Found during:** Task 1
- **Issue:** Deduplicating all `14` shared currency unions (`EUR`, `USD`, `GBP`, `AUD`, `NZD`, `DKK`, `NOK`, `CHF`, `MAD`, `ILS`, `XOF`, `XAF`, `XCD`, `XPF`) plus shared `XCG` (`CW`/`SX`) and post-2026 `BG -> EUR` across the exact `225`-territory roster yields exactly `151` unique active ISO-4217 currencies (`1` pinned `EUR` + `16` Core European + `134` Extended Global).
- **Fix:** Kept an exact 1:1 bijection (`set(territory_currencies.values()) == set(currencies.keys())`) in `data/mappings/currencies.json` rather than padding with unreferenced orphan currencies, and updated assertions accordingly.
- **Files modified:** `data/mappings/currencies.json`, `tests/test_global_registry_expansion.py`
- **Commit:** `602001e`

**2. [Rule 3 - Blocking Issue] Updated 2 additional assertions in `tests/test_compose_local.py` and unmapped TZ zones in `tests/test_registry_timezone.py`**
- **Found during:** Task 3 full offline `pytest` verification
- **Issue:** (a) `tests/test_compose_local.py` (12th test file, beyond the 11 listed in Task 3) asserted Phase 4's absence of `BR` (`alagoas.sui`/`brasil.sui` unmatched) and `ID` (`indo_gas_totem_01a.sii` skipped); (b) `tests/test_registry_timezone.py::test_unmapped_numeric_tzname_deterministic_utc_fallback` previously used `Asia/Dubai`, `Asia/Tehran`, and `America/Sao_Paulo`, which are now explicitly mapped in `IANA_NUMERIC_ABBR_OVERRIDES`.
- **Fix:** Updated `tests/test_compose_local.py` to assert `alagoas.sui` & `brasil.sui` now patch cleanly with Brazil realism (`BRT`, `-180m`, `0.99 EUR/L`, `80000 kg` axles preserved, zero Albania clobber) and `indo_gas_totem_01a.sii` patches alongside `kz_gas_totem_95.sii` (`hardcoded_totems_patched == 2`); updated `test_registry_timezone.py` to test genuinely unmapped numeric IANA zones (`Asia/Srednekolymsk`, `Pacific/Marquesas`, `America/Punta_Arenas`).
- **Files modified:** `tests/test_compose_local.py`, `tests/test_registry_timezone.py`
- **Commit:** `a7b8a26`

## Known Stubs

None — all `225` territories, `151` currencies, `186` Tier 3 fuel baselines, `75` numeric TZ overrides, and committed `state/prices.lock.json` are fully wired and validated.

## Handoff Notes for Plan 05-02

- All 8 non-EU Tier 1 target territories (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`) and their currencies (`USD`, `BRL`, `ARS`, `COP`, `CLP`, `MYR`, `JPY`, `KRW` — 6 of which are already ECB-cross-validated in `EXTENDED_ECB_CURRENCIES`) are live in `ALL_LOCKFILE_TERRITORY_ISO2S`, `ALL_TERRITORY_CURRENCIES`, and `state/prices.lock.json`.
- `SEEDED_LOCKFILE_SOURCES` in `src/ets2v2/normalize/fuel.py` already exempts first live transitions from `tier3_curated_baseline` against false `>25%` WoW rejections while keeping hard `[0.01, 5.00]` EUR/L bounds strictly enforced.
- Plan `05-02` can proceed directly with `code=` query-param redaction in `src/ets2v2/fetch/http.py`, shared `validate_ooxml_zip_safety()` promotion, the 8 non-EU Tier 1 collectors, EU Core vs Global Tier 1 CI outage gate separation (`D-02`), and `--no-global` CLI wiring.

## Self-Check: PASSED

- All created and modified files exist on disk (`225` JSON files under `data/laws/countries/`, `0` `.sii`/`.sui` files under `data/`, clean working tree).
- All three task commits (`602001e`, `e594204`, `a7b8a26`) are verified ancestors of `HEAD` with zero accidental deletions.
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, `ets2v2 registry validate`, `ets2v2 registry snapshot`, `ets2v2 package build`, and `526`-test offline `pytest`) passed with zero errors.
