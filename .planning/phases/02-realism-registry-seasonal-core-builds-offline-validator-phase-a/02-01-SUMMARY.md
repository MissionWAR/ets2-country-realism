---
phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
plan: "01"
subsystem: registry
tags: [pydantic, tzdata, pillow, laws, mappings, sim-01, cli]

requires:
  - phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine
    provides: "ETS2 1.62.3.3s baseline JSON contracts (CountriesBaseline, SpeedLimitsBaseline) and CLI foundation"
provides:
  - "Locked Phase 2 runtime dependencies (tzdata==2026.6, pillow==13.0.0) in pyproject.toml and uv.lock"
  - "Strict frozen Pydantic v2 registry schemas (src/ets2v2/registry/models.py) and baseline cross-validating loader (src/ets2v2/registry/loader.py)"
  - "CLI command ets2v2 registry validate"
  - "Canonical 36-country ETS2 slug mapping (data/mappings/ets2_countries.json) and 36 per-country statutory law JSON files (data/laws/countries/<iso2>.json)"
affects: [02-02, 02-03, 02-04, 02-05, phase-3, phase-4, phase-5]

tech-stack:
  added: [tzdata==2026.6, pillow==13.0.0]
  patterns: [strict frozen pydantic v2 JSON models, canonical sorted UTF-8 LF JSON serialization, acyclic layer-5 registry DAG]

key-files:
  created:
    - src/ets2v2/registry/__init__.py
    - src/ets2v2/registry/models.py
    - src/ets2v2/registry/loader.py
    - data/mappings/ets2_countries.json
    - data/laws/countries/al.json
    - data/laws/countries/is.json
    - tests/test_registry_schema.py
    - tests/test_registry_contracts.py
  modified:
    - pyproject.toml
    - uv.lock
    - tests/test_cli_scaffold.py
    - src/ets2v2/cli.py

key-decisions:
  - "Locked tzdata==2026.6 and pillow==13.0.0 alongside pydantic==2.14.3 with zero YAML dependencies (D-01)."
  - "Encoded all 36 Vanilla+DLC countries strictly under data/laws/countries/<iso2>.json with Bulgaria currency set to EUR and zero ProMods/non-vanilla entries (D-02)."

patterns-established:
  - "Active-phase boundary guard in tests/test_cli_scaffold.py unlocks Phase 2 subpackages (registry, package, validate, publish) while keeping Phase 3-5 directories (fetch, normalize, merge) blocked."
  - "All registry JSON files serialize through serialize_registry_json_bytes() enforcing UTF-8 no-BOM, LF, indent=2, sort_keys=True, and trailing newline."

requirements-completed: [SIM-01]

duration: 15min
completed: 2026-11-19
---

# Phase 2 Plan 01: Realism Registry, Dependencies & 36-Country Law Matrix Summary

**Locked `tzdata==2026.6` and `pillow==13.0.0`, implemented the strict Pydantic v2 `ets2v2.registry` schema/loader and `ets2v2 registry validate` CLI, and authored all 36 canonical Vanilla+DLC statutory law files.**

## Accomplishments
- Added `pillow>=12,<14` (`13.0.0`) and `tzdata>=2025.2` (`2026.6`) to `pyproject.toml` and `uv.lock`, updating `tests/test_cli_scaffold.py` to unlock Phase 2 subpackages while blocking deferred Phase 3-5 directories.
- Built `src/ets2v2/registry/{models.py,loader.py,__init__.py}` enforcing `ConfigDict(strict=True, frozen=True, extra="forbid")`, JSON-mode `model_validate_json()`, monotonic axle validation (`10_000..150_000`), non-downgrading baseline cross-checks, and `ets2v2 registry validate`.
- Authored `data/mappings/ets2_countries.json` and all 36 `data/laws/countries/<iso2>.json` files encoding seasonal speed drops (`FI`, `EE`, `LT`), seasonal DRL (`HR`), statutory DRL fixes (`CH`, `NL`, `AL`, `TR`), speed fixes (`AT`, `HU`, `IS`, `LT`, `TR`), UK imperial `mph`, `BG`/`RO`/`TR` `slow_road` + `uncommon` flags, `RO`/`SE` `max_limit`, and non-downgraded axle ladders (`IS` 5-element 60t, `FI` 10-element 105t).
- Verified red-first TDD transitions and full green verification across `tests/test_registry_schema.py`, `tests/test_registry_contracts.py`, and the full repository suite (`127 passed`).

## Deviations from Plan
- The Plan `02-01` executor subagent stalled in `waiting_for_dependents` after Task 2's full test suite finished (`127 passed`); the orchestrator verified the passing gates, committed Task 2, and generated this summary.

## Verification
- `uv lock --check --offline`: exit 0 (`Resolved 19 packages`)
- `uv run --offline ets2v2 registry validate`: exit 0 (`Registry validation passed (36 countries).`)
- `uv run --offline ruff check`: exit 0 (`All checks passed!`)
- `uv run --offline ruff format --check`: exit 0 (`36 files already formatted`)
- `uv run --offline basedpyright`: exit 0 (`0 errors, 0 warnings, 0 notes`)
- `uv run --offline pytest -q --tb=short`: exit 0 (`127 passed`)

---
*Phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a*
*Completed: 2026-11-19*
