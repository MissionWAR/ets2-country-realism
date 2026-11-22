---
phase: 03-open-european-fuel-fx-pipeline-zero-dds-totem-engine
plan: "01"
subsystem: data-pipeline-fx
tags: [httpx, openpyxl, pydantic-v2, fx, cross-validation, ssrf, xxe, ast-dag, offline-boundary]
dependency_graph:
  requires:
    - "02-01 (locked schema_version=1 RealismSnapshot & 36-country law registry)"
    - "02-04 (deterministic canonical JSON ledger conventions in state/)"
  provides:
    - "Locked Phase 3 runtime deps (httpx>=0.28,<0.29, openpyxl>=3.1,<4) and dev stub (types-openpyxl>=3.1)"
    - "4 AST-enforced offline DAG isolation walls in tests/test_cli_scaffold.py"
    - "Pure offline ets2v2.normalize package: 39-territory currency registry, PricesLockfile v1, tiered 2%/5%/10% FX cross-validation, 3-decimal EUR/L conversion, and 14d/30d staleness evaluator"
    - "Hardened online ets2v2.fetch package: SSRF/XXE/secret-redacting HTTP transport, 4 FX providers (Frankfurter v2, ECB XML, fawazahmed0 with mirror fallback, CBR windows-1251 XML), and ets2v2 fetch --fx-only CLI"
  affects:
    - "03-02 (Tier 1 European fuel collectors, circuit breaker, and seeded state/prices.lock.json)"
    - "03-03 (Zero-DDS totem engine reading PricesLockfile v1 offline)"
    - "03-04 (snapshot v1 fuel injection, changelog alerts/tables, and Friday CI)"
tech-stack:
  added:
    - "httpx==0.28.1 (BSD-3-Clause)"
    - "openpyxl==3.1.5 (MIT)"
    - "types-openpyxl==3.1.5.20261017 (Apache-2.0)"
  patterns:
    - "Strict frozen Pydantic v2 models (ConfigDict(strict=True, frozen=True, extra='forbid')) with allow_inf_nan=False"
    - "Decimal ROUND_HALF_UP 3-decimal eur_per_liter conversion separated from numeric local_display_price"
    - "Hardened httpx.Client (verify=True, follow_redirects=False with per-hop allowlist validation, bounded streaming byte caps, secret query redaction, and DOCTYPE/ENTITY XML rejection)"
    - "100% offline httpx.MockTransport testing with zero live network sockets"
key-files:
  created:
    - src/ets2v2/normalize/__init__.py
    - src/ets2v2/normalize/models.py
    - src/ets2v2/normalize/currencies.py
    - src/ets2v2/normalize/lockfile.py
    - src/ets2v2/normalize/fx.py
    - src/ets2v2/fetch/__init__.py
    - src/ets2v2/fetch/models.py
    - src/ets2v2/fetch/http.py
    - src/ets2v2/fetch/fx.py
    - tests/test_normalize_fx.py
    - tests/test_fetch_fx.py
  modified:
    - pyproject.toml
    - uv.lock
    - tests/test_cli_scaffold.py
    - src/ets2v2/cli.py
decisions:
  - "Exposed FxProviderQuote in ets2v2.normalize.fx without inf/nan field rejection so cross_validate_fx_rates() handles untrusted NaN/Inf/inverted quotes per-currency and retains previous lockfile entries cleanly without aborting other currencies."
  - "Disabled automatic httpx redirects (follow_redirects=False) inside create_http_client() and implemented explicit bounded redirect-hop resolution in fetch_bytes_with_retry() so every Location hop is re-validated against validate_https_url(next_url, allowed_hosts) (T-03-01)."
  - "Used sleep_fn: Callable[[float], None] | None = None (resolving time.sleep at call time rather than function-definition time) so retry backoff tests execute instantaneously when monkeypatching time.sleep."
metrics:
  duration: "16m"
  completed: "2026-11-21"
status: complete
actuals:
  tokens: 28794
  tasks: 2
  commits: 2
plan_head_before: 8ee6950f532f2a9140d0916a5e2906e39db693fd
plan_head_after: 71dc666ac94bb6e8221157533d4e3b73f0be4d53
---

# Phase 3 Plan 01: Multi-Provider FX Pipeline, Offline Normalize Engine & AST DAG Walls Summary

Locked Phase 3 dependencies (`httpx==0.28.1`, `openpyxl==3.1.5`, `types-openpyxl==3.1.5.20261017`), enforced all 4 offline AST DAG isolation walls, built the pure offline `ets2v2.normalize` 39-territory currency/lockfile/FX cross-validation engine, and wired hardened multi-provider online FX fetchers (`Frankfurter v2`, `ECB XML`, `fawazahmed0` jsDelivr+Pages, `CBR` `windows-1251` XML) through `ets2v2 fetch --fx-only`.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Lock Phase 3 dependencies, enforce 4 AST DAG isolation walls, and build offline normalize models, 39-territory currency map, lockfile I/O, and FX cross-validator | `6ccc212` | `pyproject.toml`, `uv.lock`, `tests/test_cli_scaffold.py`, `src/ets2v2/normalize/{__init__,models,currencies,lockfile,fx}.py`, `tests/test_normalize_fx.py` |
| 2 | Build hardened HTTP transport, multi-provider FX fetchers (Frankfurter v2, ECB, fawazahmed0, CBR), and `ets2v2 fetch --fx-only` CLI tracer | `71dc666` | `src/ets2v2/fetch/{__init__,models,http,fx}.py`, `src/ets2v2/cli.py`, `tests/test_fetch_fx.py` |

## Verification Results

- `uv sync --locked`: exited `0` (28 packages verified, `uv.lock` unmodified)
- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `73 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2"`: **287 passed, 2 deselected** (including 12 scaffold/AST-wall tests, 28 `test_normalize_fx.py` tests, and 10 offline `httpx.MockTransport` `test_fetch_fx.py` tests)

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-03-01** | `validate_https_url()` rejects non-HTTPS schemes, embedded credentials, and non-allowlisted hosts on both initial URLs and every `3xx` redirect `Location` target; `create_http_client()` unconditionally sets `verify=True`. Verified in `tests/test_fetch_fx.py`. |
| **T-03-02** | `parse_xml_safe()` enforces `<= 2 MiB` raw byte cap and rejects `<!DOCTYPE` / `<!ENTITY` case-insensitively before `ET.fromstring()`. Verified in `tests/test_fetch_fx.py`. |
| **T-03-03** | `cross_validate_fx_rates()` enforces `BG == EUR == 1.0`, `CURRENCY_SANITY_BANDS`, `finite > 0` checks, tiered `>2%`/`>5%` divergence warnings, `>10%` reject-and-hold lockfile retention, and legal `BAM = 1.95583` CBBH peg fallback. Verified in `tests/test_normalize_fx.py`. |
| **T-03-04** | `redact_url_secrets()` masks `apikey`, `api_key`, `token`, and `key` query values across `HttpFetchError`, `ProviderFetchStatus.detail`, and `LockAlert.detail`. Verified in `tests/test_fetch_fx.py`. |
| **T-03-05** | `test_phase3_ast_dag_isolation_walls()` AST-scans `src/ets2v2/{validate,package,publish,normalize}/` verifying zero imports of `ets2v2.fetch`, `httpx`, or `openpyxl`, plus strict `validate ⊥ package/normalize` and `normalize ⊥ registry/package/validate/publish` walls. |
| **T-03-SC** | `httpx==0.28.1`, `openpyxl==3.1.5`, and `types-openpyxl==3.1.5.20261017` locked with SHA-256 hashes in `uv.lock` and verified via `importlib.metadata` in `tests/test_cli_scaffold.py`. |

## Deviations from Plan

None - plan executed cleanly as written. Minor engineering refinement: `fetch_bytes_with_retry()` resolves `time.sleep` dynamically at call time (`sleep_fn=None`) rather than binding `time.sleep` at function definition time so test suites monkeypatching `time.sleep` incur zero real sleep overhead.

## Known Stubs

None. Note that `ets2v2 fetch` without `--fx-only` explicitly returns exit code `1` with an informative stderr message until Plan `03-02` wires the full Tier 1 European fuel pipeline into the same subcommand (per Plan `03-01` Task 2 action spec).

## Self-Check: PASSED

- All 15 created/modified files exist on disk and are tracked cleanly in git.
- Both task commits (`6ccc212`, `71dc666`) are verified ancestors of `HEAD`.
- All quality gates (`uv sync --locked`, `ruff check`, `ruff format --check`, `basedpyright`, `pytest -m "not local_ets2"`) passed with zero errors.
