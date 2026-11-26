---
phase: 04
slug: 04-promods-companion-builder-local-map-combo-composer
status: verified
nyquist_compliant: true
tdd_mode: true
granularity: fine
wave_0_complete: true
---

# Phase 4 — Nyquist Validation Strategy

**Goal:** Enforce test-first (`RED -> GREEN -> REFACTOR`) verification, strict static typing (`basedpyright` strict), lint/format hygiene (`ruff`), zero new runtime dependencies, **6 AST-enforced offline DAG isolation walls** (`validate`, `merge`, `package`, `publish`, `normalize`, `registry`), clean-room Git IP boundaries (zero ProMods `.scs`/`.sii`/`.sui` files in Git), `RealismSnapshot` v1 + `SHA256SUMS.txt` verification, local ProMods Companion (`EU + ME + MA + TGS`) packaging, `ets2-realism compose-local` multi-source load-order & `FieldOwnershipPolicy` guardrails, protected archive diagnostics (`AEM!`/`3nK`/encrypted ZIP), and opt-in `--patch-hardcoded-totems` across every plan in Phase 4 (`04-01` through `04-04`).

---

## 1. Test Infrastructure & Shared Quality Gates

- **Framework:** `pytest>=9.2,<9.3` with `pytest-cov>=6,<8`, `testpaths = ["tests"]`, `pythonpath = ["src"]`, `--strict-markers` (`local_promods` marker registered in `pyproject.toml`).
- **Zero New Dependencies (`T-04-SC`):** `pyproject.toml` and `uv.lock` remain strictly unchanged from Phase 3 (`httpx`, `openpyxl`, `pillow`, `pydantic`, `tzdata`).
- **Static & Test Gates (executed at every task/wave completion and in `.github/workflows/ci.yml`):**
  - `uv run --offline ruff check`
  - `uv run --offline ruff format --check`
  - `uv run --offline basedpyright` (`typeCheckingMode = "strict"`, Python `3.12`)
  - `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"` (CI-safe offline synthetic suites; `@pytest.mark.local_promods` verified on maintainer workstation against real ProMods + 340-mod combo)

---

## 2. Wave-by-Wave Sampling & Gate Schedule

| Wave | Plan(s) | Requirement(s) | Parallelism | Gate Executed After Wave |
|------|---------|----------------|-------------|--------------------------|
| **Wave 1** | `04-01` | `MAP-02` | Sequential foundation (unlock `merge/`, 6 AST DAG walls, 76-territory ProMods registry, `country_aliases.json`, frozen `RealismSnapshot` v1 + `SHA256SUMS.txt`, `registry snapshot-verify`, rolling `snapshots-latest` CI release) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_cli_scaffold.py tests/test_country_aliases.py tests/test_registry_schema.py tests/test_registry_contracts.py tests/test_registry_snapshot.py tests/test_normalize_fx.py tests/test_fetch_pipeline.py tests/test_publish_workflow.py -x` |
| **Wave 2** | `04-02` | `MAP-01` | Sequential (local ProMods `EU+ME+MA+TGS` discovery, dynamic 43-locale `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` compiler, ProMods icons, `profile="promods"` Offline SCS Validator, `assert_out_dir_not_tracked()` guard, `package promods` CLI) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_promods_discovery.py tests/test_promods_fuel.py tests/test_promods_builder.py tests/test_package_icons_metadata.py tests/test_validate_workshop.py tests/test_validate_invariants.py -m "not local_promods" -x` |
| **Wave 3** | `04-03` | `MAP-03`, `MAP-05` | Sequential (`load_order.py` multi-source `--profile`/`--game-log`/`--modlist` + `ScsC` refusal + Workshop `227300` + self-exclusion + `--unpacked-defs` + protected diagnostics; `scanner.py` `.sui`/`.sii`/`base/`/empty-stub walker; 3-tier `aliases.py`) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_merge_load_order.py tests/test_merge_scanner.py tests/test_merge_aliases.py -x` |
| **Wave 4** | `04-04` | `MAP-03`, `MAP-04`, `MAP-05` | Sequential (`FieldOwnershipPolicy` `max_of_map_and_real` axles + `patch_if_single_tz` + `imperial_units` parity; opt-in `hardcoded_totems.py` for JRR/7RM; pre-write `profile="combo"` validated `compose.py` + `ets2-realism compose-local` CLI) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_merge_policy.py tests/test_hardcoded_totems.py tests/test_compose_local.py tests/test_cli_scaffold.py -m "not local_promods" -x` |

---

## 3. Per-Plan Verification Map

| Plan | Wave | Req(s) | Threat Ref(s) | Test File(s) | Automated Verify Command | Status |
|------|------|--------|---------------|--------------|--------------------------|--------|
| `04-01` | 1 | `MAP-02` | `T-04-01`, `T-04-02`, `T-04-03`, `T-04-04`, `T-04-SC` | `tests/test_cli_scaffold.py`, `tests/test_country_aliases.py`, `tests/test_registry_schema.py`, `tests/test_registry_contracts.py`, `tests/test_registry_snapshot.py`, `tests/test_normalize_fx.py`, `tests/test_fetch_pipeline.py`, `tests/test_publish_workflow.py` | `uv run --offline pytest tests/test_cli_scaffold.py tests/test_country_aliases.py tests/test_registry_snapshot.py tests/test_publish_workflow.py -x` | passed |
| `04-02` | 2 | `MAP-01` | `T-04-05`, `T-04-06`, `T-04-07`, `T-04-08` | `tests/test_promods_discovery.py`, `tests/test_promods_fuel.py`, `tests/test_promods_builder.py`, `tests/test_package_icons_metadata.py`, `tests/test_validate_workshop.py`, `tests/test_validate_invariants.py` | `uv run --offline pytest tests/test_promods_discovery.py tests/test_promods_fuel.py tests/test_promods_builder.py -m "not local_promods" -x` | passed |
| `04-03` | 3 | `MAP-03`, `MAP-05` | `T-04-09`, `T-04-10`, `T-04-11`, `T-04-12` | `tests/test_merge_load_order.py`, `tests/test_merge_scanner.py`, `tests/test_merge_aliases.py` | `uv run --offline pytest tests/test_merge_load_order.py tests/test_merge_scanner.py tests/test_merge_aliases.py -x` | passed |
| `04-04` | 4 | `MAP-03`, `MAP-04`, `MAP-05` | `T-04-13`, `T-04-14`, `T-04-15`, `T-04-16` | `tests/test_merge_policy.py`, `tests/test_hardcoded_totems.py`, `tests/test_compose_local.py`, `tests/test_cli_scaffold.py` | `uv run --offline pytest tests/test_merge_policy.py tests/test_hardcoded_totems.py tests/test_compose_local.py -m "not local_promods" -x` | passed |

---

## 4. Requirement Coverage & Audit Sign-Off

- [x] **`MAP-01`:** Local ProMods Companion Builder (`EU+ME+MA+TGS`), dynamic 43-locale `pm*_fuel` modules, checked-in `276x162` `assets/icons/promods_{summer,winter}.jpg`, `profile="promods"` Offline SCS Validator, zero ProMods files tracked in Git, and external-CWD-safe `assert_out_dir_not_tracked()` guard (`test_assert_out_dir_not_tracked_allows_non_repo_external_cwd`).
- [x] **`MAP-02`:** Frozen `schema_version=1` `RealismSnapshot` + `SHA256SUMS.txt` + `ets2-realism registry snapshot-verify` + offline `load_or_build_snapshot()` + rolling `snapshots-latest` GitHub Release.
- [x] **`MAP-03`:** Multi-source load-order resolver (`--profile` w/ `ScsC` guard, `--game-log`, `--modlist`, Workshop `227300`, automatic managed-package self-exclusion), `VfsStack` combo country scanner (`.sui`/`.sii`/`base/`/empty stubs), and 3-tier `country_aliases.json` resolver (`37/37` ISO-2 targets covered).
- [x] **`MAP-04`:** `FieldOwnershipPolicy` (`max_of_map_and_real` axles, `patch_if_single_tz`, `imperial_units` parity guard, custom lane & `train`/`tram` preservation).
- [x] **`MAP-05`:** Protected archive detection (`AEM!`/`3nK`/encrypted ZIP) with `--unpacked-defs` & `--strict-protected`, plus opt-in `--patch-hardcoded-totems` (JRR/7RM).
