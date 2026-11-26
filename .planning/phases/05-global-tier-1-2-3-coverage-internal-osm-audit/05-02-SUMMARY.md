---
phase: 05-global-tier-1-2-3-coverage-internal-osm-audit
plan: "02"
subsystem: global-tier1-fuel-collectors
tags: [tier1-global, httpx, openpyxl, secret-redaction, ooxml-safety, nist-gallon, eu-core-gate, ci-workflow]
dependency_graph:
  requires:
    - "05-01 (225-territory & 151-FX global registry foundation, SEEDED_LOCKFILE_SOURCES, committed state/prices.lock.json)"
  provides:
    - "Hardened query-parameter `code=` secret redaction in `src/ets2v2/fetch/http.py` and `Sequence[tuple[str, str]]` query parameter support in `fetch_bytes_with_retry()`"
    - "Shared OOXML ZIP-bomb/encryption/XXE safety validator `validate_ooxml_zip_safety()` in `src/ets2v2/fetch/_parsing.py` reused across EC WOB, JP METI, and upcoming Tier 2 XLSX feeds"
    - "Additive `RawFuelFeedResult` (`tier='tier2'`, `region_scope`, `skip_reason`, `error_code`) and `FetchRunReport` (`eu_tier1_feeds_*`, `global_tier1_feeds_*`, `tier2_feeds_*`) DTO extensions in `src/ets2v2/fetch/models.py`"
    - "All 8 non-EU Tier 1 open government fuel collectors (`us_eia_v2`, `br_anp`, `ar_energia`, `co_sicom`/CREG fallback, `cl_cne`, `my_opendosm`, `jp_meti`, `kr_opinet`) and `fetch_all_global_tier1_feeds()` in `src/ets2v2/fetch/global_tier1.py`"
    - "Strict EU Core hard-fail (`eu_tier1_feeds_succeeded == 0`) vs Global Tier 1 warning-only (`global_tier1_outage`) outage gate separation in `src/ets2v2/fetch/pipeline.py`, `--no-global` CLI flag, and optional `EIA_API_KEY`/`OPINET_API_KEY`/`CNE_API_TOKEN` step-level env wiring in `.github/workflows/phase-a-release.yml`"
  affects:
    - "05-03 (Tier 2 guarded national portal scrapers can directly reuse `validate_ooxml_zip_safety()`, `RawFuelFeedResult(tier='tier2', error_code=...)`, `FetchRunReport.tier2_feeds_*`, and `pipeline.py` error_code propagation)"
    - "05-04 (Isolated `src/ets2v2/audit/` and license-taint gate across all 225 territories and open-data attributions)"
tech-stack:
  added: []
  patterns:
    - "Exact NIST `Decimal('3.785411784')` gallon-to-liter conversion (`gallon_to_liter`) applied uniformly to both `US EIA v2` and `CO SICOM`/`CREG`"
    - "Deterministic `statistics.median()` station aggregation rejecting typo outliers (`BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`) alongside official national average rows (`US`, `MY`, `JP`, `KR`)"
    - "Optional secret silent-skip (`ok=True, skipped=True`, accurate per-feed `skip_reason`) plus dual secret scrubbing (`redact_url_secrets()` + `_scrub_secret()`) across `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`, and `TANKERKOENIG_API_KEY`"
    - "Strict EU Core vs Global Tier 1 CI outage gate partitioning keeping Friday Core Workshop releases resilient to regional non-EU API turbulence while preventing global success from masking EU Core outages"
key-files:
  created:
    - src/ets2v2/fetch/global_tier1.py
    - tests/test_fetch_global_tier1.py
  modified:
    - src/ets2v2/fetch/http.py
    - src/ets2v2/fetch/_parsing.py
    - src/ets2v2/fetch/ec_bulletin.py
    - src/ets2v2/fetch/models.py
    - src/ets2v2/fetch/national.py
    - src/ets2v2/fetch/pipeline.py
    - src/ets2v2/fetch/__init__.py
    - src/ets2v2/cli.py
    - .github/workflows/phase-a-release.yml
    - tests/test_fetch_pipeline.py
    - tests/test_publish_workflow.py
decisions:
  - "Converted `Sequence[tuple[str, str]]` query parameters to `tuple[tuple[str, str], ...]` inside `fetch_bytes_with_retry()` so repeated EIA v2 `facets[product][]` keys satisfy `httpx`'s covariant `QueryParamTypes` under strict `basedpyright` without weakening the public parameter annotation."
  - "Kept `FetchRunReport.tier1_feeds_succeeded` and `tier1_feeds_failed` mirrored to `eu_tier1_feeds_succeeded` and `eu_tier1_feeds_failed` for 100% backwards compatibility with Phase 3/4 consumers while exposing separate `global_tier1_feeds_*` and `tier2_feeds_*` counters."
  - "Exposed `co_creg` alongside `co_sicom` at `_FEED_PRECEDENCE = 40` in `pipeline.py` so CREG HTML fallback quotes retain full Tier 1 precedence when `datos.gov.co` SODA discovery is unavailable."
metrics:
  duration: "25m active execution"
  completed: "2026-11-26"
status: complete
actuals:
  tokens: 35770
  tasks: 3
  commits: 3
plan_head_before: 3fab26b008d4289c6a9b18cbf9b709c7ca7dc5ac
plan_head_after: 271a30dde74c9f3c79fcbc5a115a7a63b33c972d
---

# Phase 5 Plan 02: Non-EU Tier 1 Open Government Fuel Collectors Summary

Hardened `src/ets2v2/fetch/http.py` to mask `code=` query secrets and accept repeated `Sequence[tuple[str, str]]` query parameters, promoted `validate_ooxml_zip_safety()` to `src/ets2v2/fetch/_parsing.py`, extended `RawFuelFeedResult` and `FetchRunReport` with additive `tier="tier2"`, `region_scope`, `skip_reason`, `error_code`, and EU/Global/Tier2 counters, implemented all **8 non-EU Tier 1 open government fuel collectors** (`US EIA v2`, `BR ANP`, `AR Energía`, `CO SICOM`/CREG, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`) using zero new runtime dependencies, wired Global Tier 1 into `run_price_fetch()` with strict EU Core hard-fail vs Global warning-only outage gate isolation (`D-02`) and `--no-global` CLI filtering, and exposed optional `EIA_API_KEY`, `OPINET_API_KEY`, and `CNE_API_TOKEN` via step-level `env:` in `.github/workflows/phase-a-release.yml`.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Harden `fetch/http.py` (`code=` secret redaction & sequence params), share `validate_ooxml_zip_safety` in `_parsing.py`, extend `fetch/models.py`, and build tracer collectors (`US EIA v2`, `MY OpenDOSM`, `KR Opinet`) | `6407b37` | `src/ets2v2/fetch/{http,_parsing,ec_bulletin,models,national,global_tier1}.py`, `tests/test_fetch_global_tier1.py` |
| 2 | Expand `fetch/global_tier1.py` with `BR ANP`, `AR Energía`, `CO SICOM`/CREG, `CL CNE`, `JP METI`, and `fetch_all_global_tier1_feeds()` | `1f7c2d9` | `src/ets2v2/fetch/global_tier1.py`, `tests/test_fetch_global_tier1.py` |
| 3 | Wire Global Tier 1 into `fetch/pipeline.py` with EU Core vs Global outage gate isolation (`D-02`), expose `--no-global` CLI flag, and wire optional secrets in `phase-a-release.yml` | `271a30d` | `src/ets2v2/fetch/{pipeline,__init__}.py`, `src/ets2v2/cli.py`, `.github/workflows/phase-a-release.yml`, `tests/test_{fetch_pipeline,publish_workflow}.py` |

## Achieved Coverage & Contracts

- **Non-EU Tier 1 collectors (8/8):** `us_eia_v2` (`US`, optional `EIA_API_KEY`, `EPD2D`/`EPMR`/`EPMP` ignoring `EPD2O`, NIST `USD/gal -> USD/L`), `br_anp` (`BR`, dual Latin-1/CP1252/UTF-8 `;`-CSV medians excluding `GLP`/`GNV` and `>7d` rows), `ar_energia` (`AR`, CKAN `vigente` discovery rejecting `historico`, filtering `>60d` stale stations, preferring `Diurno`, excluding `GNC`), `co_sicom` (`CO`, Socrata discovery skipping dispatch-volume `fbht-2fzd` + CREG HTML table fallback with dot-thousands `15.588` normalization and NIST `COP/gal -> COP/L`), `cl_cne` (`CL`, optional `CNE_API_TOKEN`, v4 Bearer + v3 token fallback station medians), `my_opendosm` (`MY`, keyless `CC BY 4.0`, client-side `series_type == "level"` rejecting `change_weekly`, `diesel_eastmsia` fallback), `jp_meti` (`JP`, `.xlsx`-only discovery rejecting `.xls`, shared `validate_ooxml_zip_safety()`, national average `全国`/`全国平均` ignoring 18L `灯油`), `kr_opinet` (`KR`, optional `OPINET_API_KEY`, `D047`/`B027`/`B034`/`K015` ignoring `C004` kerosene, `TRADE_DT` normalization).
- **EU Core vs Global Tier 1 Outage Gate (`D-02`):** `eu_tier1_feeds_succeeded == 0` hard-fails `run_price_fetch()` (`ok=False`) even when Global Tier 1 feeds succeed; conversely, a total 8/8 Global Tier 1 outage emits `warning` alerts (`global_tier1_outage`), retains lockfile/Tier 3 baselines, and returns `ok=True`.
- **CLI & Workflow (`D-01`, `D-07`):** `ets2v2 fetch --no-global` skips all 8 Global Tier 1 feeds cleanly; `.github/workflows/phase-a-release.yml` passes `EIA_API_KEY`, `OPINET_API_KEY`, and `CNE_API_TOKEN` strictly via step-level `env:`, renders EU Core vs Global Tier 1 Step Summary counters, preserves `def _sanitize(` (`>= 2`), and contains zero `${{` inside `run:` blocks while `.github/workflows/ci.yml` remains strictly read-only with zero API secrets.
- **Runtime dependencies:** Strictly locked at `5` (`pyproject.toml` and `uv.lock` untouched).

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `109 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, Python `3.12`)
- `uv run --offline ets2v2 fetch --seed-offline --no-global --lock-path <tmp>/ets2v2_0502_verify.lock.json --dry-run --json`: exit `0`, `ok: true`, `countries_fallback: 225`, `fx_currencies_validated: 151`, additive `eu_tier1_feeds_*`, `global_tier1_feeds_*`, and `tier2_feeds_*` fields emitted
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **545 passed, 4 deselected** (+19 new tests: `14` in `tests/test_fetch_global_tier1.py`, `4` in `tests/test_fetch_pipeline.py`, `1` in `tests/test_publish_workflow.py`)

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-05-05** | `_SECRET_QUERY_RE` in `src/ets2v2/fetch/http.py` redacts `code=` (case-insensitive) alongside `apikey`/`api_key`/`token`/`key`; every keyed collector (`us_eia_v2`, `kr_opinet`, `cl_cne`, `de_tankerkoenig`) applies `_scrub_secret()` / `.replace(key, "***")`; unit and pipeline tests assert zero raw secret leakage on HTTP 500, timeout, and lockfile writes; `phase-a-release.yml` passes secrets strictly via step-level `env:`. |
| **T-05-06** | Every initial request, discovered CKAN/Socrata/METI link, and redirect hop runs through `fetch_bytes_with_retry()` + `validate_https_url()` with exact per-collector HTTPS host allowlists (`api.eia.gov`, `www.gov.br`, `datos.gob.ar`/`datos.energia.gob.ar`, `www.datos.gov.co`/`creg.gov.co`, `api.cne.cl`, `api.data.gov.my`, `www.enecho.meti.go.jp`, `www.opinet.co.kr`). |
| **T-05-07** | `DEFAULT_MAX_RESPONSE_BYTES` (30 MiB) caps CSV/JSON reads; `AR Energía` rejects `"historico"` resources; `JP METI` rejects `.xls` links, enforces 20 MiB + 5000-row caps, and validates every `.xlsx` via shared `validate_ooxml_zip_safety()` (entry count, uncompressed byte budget, encryption ban, `<!DOCTYPE`/`<!ENTITY` XXE ban) before `openpyxl.load_workbook(read_only=True, data_only=True)`. |
| **T-05-08** | Exact NIST `Decimal("3.785411784")` division applied on `US` & `CO`, Colombian dot-thousands normalized (`> 1000 COP/gal` guard), non-automotive fuels (`GLP`, `GNV`, `GNC`, `C004`, `灯油`) and `MY` `change_weekly` delta rows excluded, and `statistics.median()` applied across station-level feeds. |
| **T-05-09** | `eu_tier1_feeds_succeeded == 0` hard-fail strictly isolated from `global_tier1_feeds_*` warning-only `global_tier1_outage` alerts; `phase-a-release.yml` preserves zero `${{` inside `run:` and `def _sanitize(` in both Step Summary and PR body scripts. |
| **T-05-SC** | Zero new runtime dependencies added (`pyproject.toml` and `uv.lock` unchanged). |

## Deviations from Plan

None — plan executed as written. One minor strict-typing implementation detail (`Rule 3` inline): `fetch_bytes_with_retry()` converts non-mapping `Sequence[tuple[str, str]]` query params to `tuple[tuple[str, str], ...]` before calling `httpx.Client.stream()` so `basedpyright` strict satisfies `httpx`'s covariant `QueryParamTypes` signature.

## Known Stubs

None — all 8 non-EU Tier 1 collectors, shared OOXML safety validation, `code=` secret redaction, EU vs Global outage gate isolation, `--no-global` CLI flag, and workflow wiring are fully implemented and verified offline.

## Handoff Notes for Plan 05-03

- `src/ets2v2/fetch/_parsing.py` already exports `validate_ooxml_zip_safety()` ready for Tier 2 `.xlsx` portals (`RU Rosstat`, `ZA CEF`, `NG NBS`).
- `RawFuelFeedResult` already supports `tier="tier2"`, `region_scope="global"`, `skip_reason`, and `error_code`, and `FetchRunReport` / `pipeline.py` already compute and propagate `tier2_feeds_succeeded`, `tier2_feeds_failed`, and `feed_res.error_code` into `LockAlert.code`.
- Plan `05-03` can add `src/ets2v2/fetch/_html.py`, `src/ets2v2/fetch/tier2_portals.py`, `--no-tier2` CLI wiring, 5-tier staleness thresholds in `normalize/lockfile.py`, and compact Tier 3 alert rollups + Global Snapshot Coverage blocks in `publish/changelog.py` and `.github/workflows/phase-a-release.yml` directly on top of these seams.

## Self-Check: PASSED

- All created and modified files exist on disk (`src/ets2v2/fetch/global_tier1.py`, `tests/test_fetch_global_tier1.py`, plus all 11 modified source/workflow/test files; `pyproject.toml` and `uv.lock` unchanged).
- All three task commits (`6407b37`, `1f7c2d9`, `271a30d`) are verified ancestors of `HEAD` with zero accidental deletions.
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, offline `ets2v2 fetch --seed-offline --no-global --dry-run --json`, and `545`-test offline `pytest`) passed with zero errors.
