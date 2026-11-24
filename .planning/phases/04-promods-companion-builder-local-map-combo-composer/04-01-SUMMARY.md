---
phase: 04-promods-companion-builder-local-map-combo-composer
plan: "01"
subsystem: registry-snapshot-ci
tags: [pydantic-v2, promods, country-aliases, realism-snapshot-v1, sha256sums, fx-isolation, ast-dag, github-releases]
dependency_graph:
  requires:
    - "02-01 (locked schema_version=1 RealismSnapshot & 36-country law registry)"
    - "03-02 (39-territory prices.lock.json & Tier 1 European fuel/FX pipeline)"
    - "03-04 (Phase A diff-gated release orchestrator & phase-a-release.yml workflow)"
  provides:
    - "Unlocked src/ets2v2/merge/ Layer 9A subpackage scaffold with all 6 AST-enforced offline DAG isolation walls and local_promods pytest marker"
    - "76-territory canonical law registry (36 Vanilla+DLC vanilla_1_62=true + 40 ProMods EU+ME+MA+TGS v1.71 vanilla_1_62=false) with null-allowed non-vanilla country_id and zero .sii/.sui files under data/"
    - "Bundled canonical data/mappings/country_aliases.json (119 aliases covering ProMods, GMC Beyond/UMCF/RIW, JRR 3-TZ Indonesia, SemEuropa 27 Brazilian state collision shields, SEA/Africa, and 47 Project Japan prefectures)"
    - "Extended 76-territory / 41-FX-currency normalize & fetch pipeline with CI isolation for 24 exotic ProMods currencies (incl. post-2026 redenominated SYP 80-250 sanity band)"
    - "Frozen schema_version=1 RealismSnapshot with non-vanilla imperial_units derivation, SHA256SUMS.txt emitter/parser, constant-time verify_snapshot_file(), load_or_build_snapshot() repo fallback, ets2v2 registry snapshot-verify CLI, and rolling snapshots-latest GitHub Release workflow step"
  affects:
    - "04-02 (ProMods Companion Builder consuming 76-territory v1 snapshot, load_or_build_snapshot(), and src/ets2v2/merge/)"
    - "04-03 (load-order parsers and VfsStack country scanner consuming CountryAliasRegistry & country_aliases.json)"
    - "04-04 (compose-local orchestrator consuming 76-territory v1 snapshot, aliases, and offline verification)"
tech-stack:
  added: []
  patterns:
    - "6 AST-enforced offline DAG isolation walls across validate, merge, package, publish, normalize, and registry"
    - "Strict frozen Pydantic v2 CountryAliasEntry/CountryAliasRegistry with ZoneInfo validation on optional iana_timezone_override"
    - "Dual-tier FX cross-validation isolating 24 optional extended ProMods currencies from the 16 required Core European non-EUR currencies"
    - "Constant-time hmac.compare_digest SHA-256 verification with sibling SHA256SUMS.txt auto-discovery"
key-files:
  created:
    - src/ets2v2/merge/__init__.py
    - data/mappings/country_aliases.json
    - tests/test_country_aliases.py
    - data/laws/countries/ad.json
    - data/laws/countries/am.json
    - data/laws/countries/ax.json
    - data/laws/countries/az.json
    - data/laws/countries/by.json
    - data/laws/countries/cn.json
    - data/laws/countries/cy.json
    - data/laws/countries/dz.json
    - data/laws/countries/eg.json
    - data/laws/countries/fo.json
    - data/laws/countries/ge.json
    - data/laws/countries/gg.json
    - data/laws/countries/gi.json
    - data/laws/countries/gl.json
    - data/laws/countries/ie.json
    - data/laws/countries/il.json
    - data/laws/countries/im.json
    - data/laws/countries/iq.json
    - data/laws/countries/je.json
    - data/laws/countries/jo.json
    - data/laws/countries/kg.json
    - data/laws/countries/kz.json
    - data/laws/countries/lb.json
    - data/laws/countries/li.json
    - data/laws/countries/ly.json
    - data/laws/countries/ma.json
    - data/laws/countries/mc.json
    - data/laws/countries/md.json
    - data/laws/countries/mn.json
    - data/laws/countries/mt.json
    - data/laws/countries/ps.json
    - data/laws/countries/sa.json
    - data/laws/countries/sj.json
    - data/laws/countries/sm.json
    - data/laws/countries/sy.json
    - data/laws/countries/tj.json
    - data/laws/countries/tm.json
    - data/laws/countries/tn.json
    - data/laws/countries/ua.json
    - data/laws/countries/uz.json
  modified:
    - pyproject.toml
    - src/ets2v2/registry/models.py
    - src/ets2v2/registry/loader.py
    - src/ets2v2/registry/timezone.py
    - src/ets2v2/registry/snapshot.py
    - src/ets2v2/registry/__init__.py
    - src/ets2v2/normalize/currencies.py
    - src/ets2v2/normalize/fx.py
    - src/ets2v2/normalize/fuel.py
    - src/ets2v2/normalize/lockfile.py
    - src/ets2v2/normalize/__init__.py
    - src/ets2v2/fetch/ec_bulletin.py
    - src/ets2v2/fetch/pipeline.py
    - src/ets2v2/publish/changelog.py
    - src/ets2v2/publish/release.py
    - src/ets2v2/cli.py
    - .github/workflows/phase-a-release.yml
    - data/mappings/ets2_countries.json
    - state/prices.lock.json
    - tests/test_cli_scaffold.py
    - tests/test_validate_workshop.py
    - tests/test_registry_schema.py
    - tests/test_registry_contracts.py
    - tests/test_registry_snapshot.py
    - tests/test_registry_timezone.py
    - tests/test_normalize_fx.py
    - tests/test_normalize_fuel.py
    - tests/test_fetch_fx.py
    - tests/test_fetch_fuel.py
    - tests/test_fetch_pipeline.py
    - tests/test_totem_formatting.py
    - tests/test_publish_release.py
    - tests/test_publish_workflow.py
decisions:
  - "Placed CORE_REFERENCE_FX_RATES, EXTENDED_REFERENCE_FX_RATES, ALL_REFERENCE_FX_RATES, and PROMODS_SEED_EUR_PRICES in ets2v2.normalize.currencies so normalize.fx and normalize.lockfile share reference FX tables cleanly with zero circular imports while preserving REFERENCE_FX_RATES in normalize.lockfile for backwards compatibility."
  - "Extended normalize/fuel.py (ALL_TERRITORY_CURRENCIES lookup and promods_curated_seed bootstrap exemption) and fetch/ec_bulletin.py (ALL_LOCKFILE_TERRITORY_ISO2S filter) so live fuel-prices.eu quotes for ProMods EU territories such as AD (Andorra) flow cleanly through run_price_fetch()."
  - "Scoped Core changelog fuel summary tables to VANILLA_36_ISO2S (keeping ## 36-Country Fuel Price Summary crisp) while recording 36 (Core) / 76 (Snapshot) in Release Summary and keeping PublishedEditionState.country_count at 36 for Core Workshop packages."
metrics:
  duration: "70m"
  completed: "2026-11-24"
status: complete
actuals:
  tokens: 93720
  tasks: 3
  commits: 3
plan_head_before: 12545cdb791cddade066b7647ea419118fc269e9
plan_head_after: acf8dbc808b8a1d7158413df244c77a1bd56ffd0
---

# Phase 4 Plan 01: Merge Scaffold, 76-Territory ProMods Registry, Country Aliases, FX CI Isolation & `snapshots-latest` Distribution Summary

Unlocked `src/ets2v2/merge/` with all 6 AST-enforced offline DAG isolation walls, expanded the canonical law registry, country mappings, currency/FX/lockfile pipeline, and frozen `schema_version: 1` `RealismSnapshot` to all **76** Vanilla + ProMods `EU + ME + MA + TGS v1.71` territories (`36` Vanilla+DLC + `40` ProMods), bundled `data/mappings/country_aliases.json` (`119` entries), added air-gapped `SHA256SUMS.txt` verification via `ets2v2 registry snapshot-verify` + `load_or_build_snapshot()`, and wired verified rolling `snapshots-latest` GitHub Release uploads into `.github/workflows/phase-a-release.yml`.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Unlock `src/ets2v2/merge/` with 6 AST DAG walls, relax `CountryMappingEntry`, add `CountryAliasRegistry` + `country_aliases.json`, and expand `registry/timezone/snapshot` v1 + `snapshot-verify` CLI | `7acfa3f` | `pyproject.toml`, `src/ets2v2/merge/__init__.py`, `src/ets2v2/registry/{models,loader,timezone,snapshot,__init__}.py`, `src/ets2v2/cli.py`, `data/mappings/country_aliases.json`, `tests/test_{cli_scaffold,validate_workshop,country_aliases,registry_schema,registry_snapshot}.py` |
| 2 | Populate 40 ProMods `EU+ME+MA+TGS` statutory law files (76 total), expand currency/FX CI isolation, preserve ProMods entries in `fetch/pipeline.py`, and seed 76-territory `state/prices.lock.json` | `37572e7` | `data/laws/countries/*.json` (40 new), `data/mappings/ets2_countries.json`, `state/prices.lock.json`, `src/ets2v2/normalize/{currencies,fx,fuel,lockfile,__init__}.py`, `src/ets2v2/fetch/{ec_bulletin,pipeline}.py`, `tests/test_{registry_contracts,registry_snapshot,normalize_fx,fetch_fx,fetch_pipeline}.py` |
| 3 | Keep Core changelogs scoped cleanly to 36 Core countries, emit `dist/snapshots/SHA256SUMS.txt` in `release.py`, and publish rolling `snapshots-latest` release in `phase-a-release.yml` | `acf8dbc` | `src/ets2v2/publish/{changelog,release}.py`, `.github/workflows/phase-a-release.yml`, `tests/test_{publish_release,publish_workflow,fetch_fuel,normalize_fuel,registry_timezone,totem_formatting}.py` |

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `88 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline ets2v2 registry validate`: `Registry validation passed (76 countries).`
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **400 passed, 2 deselected** (zero failures across all Phase 1–4 offline unit, contract, workflow, and integration suites)
- Clean-room audit: `76` canonical JSON files under `data/laws/countries/`, `0` `.sii`/`.sui` files under `data/`, zero new external packages added (`pyproject.toml` dependencies and `uv.lock` untouched).

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-04-01** | `load_realism_snapshot()`, `parse_sha256sums()`, and `verify_snapshot_file()` enforce UTF-8 no-BOM LF hygiene, strict `RealismSnapshot` `schema_version=1` + `extra="forbid"` + `allow_inf_nan=False`, reject path separators / `.` / `..` / duplicate entries in `SHA256SUMS.txt`, and compare digests with `hmac.compare_digest()` (including automatic sibling `SHA256SUMS.txt` verification). Verified in `tests/test_registry_snapshot.py` and `tests/test_publish_release.py`. |
| **T-04-02** | `.github/workflows/phase-a-release.yml` gates rolling `snapshots-latest` release upload strictly on `schedule` or `refs/heads/master`, verifies both snapshots via `ets2v2 registry snapshot-verify` before release publication, passes `GH_TOKEN: ${{ github.token }}` strictly via step-level `env:`, and contains zero `${{` expressions inside any `run:` block. Verified in `tests/test_publish_workflow.py`. |
| **T-04-03** | `EXTENDED_CURRENCY_SANITY_BANDS` enforces `SYP: (80.0, 250.0)` rejecting un-redenominated `14,000` quotes, and `cross_validate_fx_rates(..., include_extended=True)` isolates all 24 extended ProMods currencies from the 16 required Core European currencies so exotic FX outages fall back via `fx_reference_fallback` warning without failing Friday CI. Verified in `tests/test_normalize_fx.py` and `tests/test_fetch_pipeline.py`. |
| **T-04-04** | Both `tests/test_cli_scaffold.py` and `tests/test_validate_workshop.py` AST-enforce all 6 offline DAG isolation walls (`validate`, `merge`, `package`, `publish`, `normalize`, `registry`) and `tests/test_registry_contracts.py` enforces zero `.sii`/`.sui` files under `data/`. |
| **T-04-SC** | Zero new external PyPI dependencies installed (`pyproject.toml` dependencies and `uv.lock` unchanged). |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Extended `normalize/fuel.py` and `fetch/ec_bulletin.py` to 76 territories**
- **Found during:** Task 2
- **Issue:** `normalize_country_fuel_prices()` in `src/ets2v2/normalize/fuel.py` looked up `TERRITORY_CURRENCIES` (39 territories) and only exempted `BASELINE_SEEDED_SOURCE` from bootstrap WoW checks, and `fetch_fuel_prices_eu()` in `src/ets2v2/fetch/ec_bulletin.py` filtered quotes against `EUROPEAN_TERRITORY_ISO2S` (39 territories), which would have rejected live `AD` (Andorra) quotes from `fuel-prices.eu`.
- **Fix:** Switched `normalize/fuel.py` to `ALL_TERRITORY_CURRENCIES` + `{BASELINE_SEEDED_SOURCE, PROMODS_CURATED_SEED_SOURCE}` and `fetch/ec_bulletin.py` to `ALL_LOCKFILE_TERRITORY_ISO2S`.
- **Files modified:** `src/ets2v2/normalize/fuel.py`, `src/ets2v2/fetch/ec_bulletin.py`
- **Commit:** `37572e7`

**2. [Rule 3 - Blocking Issue] Updated 4 legacy Phase 2/3 regression tests hardcoded to 36/39 territories or unmapped `Asia/Tbilisi`**
- **Found during:** Task 3 full-suite pytest verification
- **Issue:** Four additional existing tests outside Task 2's explicit list failed once the repo expanded to 76 territories and mapped `Asia/Tbilisi -> GET`: `tests/test_fetch_fuel.py` (`assert "AD" not in by_iso2`), `tests/test_normalize_fuel.py` (39-territory `seed_initial_lockfile()` assertion), `tests/test_registry_timezone.py` (`len(registry.laws_by_iso2) == 36` and `Asia/Tbilisi` unmapped fallback), and `tests/test_totem_formatting.py` (`TERRITORY_CURRENCIES[iso2]` lookup over 76-territory `prices.lock.json`).
- **Fix:** Updated `test_fetch_fuel.py` to assert `"AD" in by_iso2` and `"US" not in by_iso2`, `test_normalize_fuel.py` to assert 76 territories / 41 FX rates, `test_registry_timezone.py` to partition 36 Vanilla checks on `vanilla_1_62` and use unmapped `Asia/Dubai` (`+240`, `UTC+4`), and `test_totem_formatting.py` to use `ALL_TERRITORY_CURRENCIES` / `ALL_CURRENCY_SANITY_BANDS`.
- **Files modified:** `tests/test_fetch_fuel.py`, `tests/test_normalize_fuel.py`, `tests/test_registry_timezone.py`, `tests/test_totem_formatting.py`
- **Commit:** `acf8dbc`

## Known Stubs

None — `src/ets2v2/merge/__init__.py` is intentionally unlocked as an empty Layer 9A package scaffold for Plans `04-02`–`04-04` per Plan `04-01` Task 1 spec.

## Self-Check: PASSED

- All created and modified files exist on disk and are tracked cleanly in git.
- All three task commits (`7acfa3f`, `37572e7`, `acf8dbc`) are verified ancestors of `HEAD`.
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, `ets2v2 registry validate`, and 400-test offline `pytest`) passed with zero errors.
