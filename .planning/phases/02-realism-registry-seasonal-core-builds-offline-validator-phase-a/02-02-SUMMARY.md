---
phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
plan: "02"
subsystem: registry
tags: [zoneinfo, tzdata, dst, snapshot, schema-v1, sim-02, cli]

requires:
  - phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
    provides: "36-country law registry, CountryMappingRegistry, and locked tzdata==2026.6 dependency (02-01)"
provides:
  - "Pure stdlib zoneinfo + tzdata seasonal DST resolver (src/ets2v2/registry/timezone.py) with numeric tzname overrides and 12-key @@tz_*@@ whitelist"
  - "Locked D-11 one-way schema_version=1 JSON contracts for realism-snapshot-{summer,winter}.json and state/published.json"
  - "Deterministic RealismSnapshot models, builder, serializer (src/ets2v2/registry/snapshot.py), and CLI command ets2v2 registry snapshot"
affects: [02-03, 02-04, 02-05, phase-3, phase-4, phase-5]

tech-stack:
  added: []
  patterns: [stdlib zoneinfo+tzdata seasonal anchor resolution, 12-key @@tz_*@@ whitelist filtering, locked schema_version=1 canonical snapshot JSON]

key-files:
  created:
    - src/ets2v2/registry/timezone.py
    - src/ets2v2/registry/snapshot.py
    - tests/test_registry_timezone.py
    - tests/test_registry_snapshot.py
  modified:
    - src/ets2v2/registry/__init__.py
    - src/ets2v2/cli.py

key-decisions:
  - "D-11 One-Way Schema Lock (approve-v1): Locked schema_version=1 JSON contracts for realism-snapshot-{summer,winter}.json and state/published.json with zero wall-clock timestamps and reserved fuel.{currency,eur_per_liter,local_prices,source} structure for Phase 3-5."
  - "Applied explicit IANA_NUMERIC_ABBR_OVERRIDES (Europe/Istanbul->TRT, Asia/Amman->AST, Asia/Damascus->AST) prior to 12-key @@tz_*@@ whitelist matching so CET/WET/AST emit plain strings and never unsupported @@tz_cet@@/@@tz_wet@@ tokens."

patterns-established:
  - "assert_leftside_traffic_immutable() enforces baseline leftside_traffic preservation (true only for uk among 36 Vanilla+DLC countries)."
  - "serialize_snapshot_bytes() guarantees deterministic UTF-8 no-BOM LF sorted JSON output across platforms."

requirements-completed: [SIM-02]

duration: 12min
completed: 2026-11-19
---

# Phase 2 Plan 02: Seasonal Timezone Resolver, D-11 Schema Lock & Realism Snapshot Summary

**Implemented dynamic `zoneinfo`+`tzdata` Summer/Winter DST resolution across all 36 countries (plus MENA permanent-UTC+3 edge cases), locked the `one-way` D-11 `schema_version=1` snapshot/ledger contracts, and wired deterministic `ets2v2 registry snapshot` generation.**

## Accomplishments
- Implemented `src/ets2v2/registry/timezone.py` with `resolve_season_anchor_date()`, `resolve_ets2_timezone()`, `IANA_NUMERIC_ABBR_OVERRIDES`, `ResolvedTimezone`, and `assert_leftside_traffic_immutable()`.
- Verified exact July 15 (Summer) parity across all 36 countries against ETS2 `1.62.3.3s` `countries.json`, exact January 15 (Winter) offsets/names (`24` CET `+60/"CET"`, `7` EET `+120/"@@tz_eet@@"`, `PT` `0/"WET"`, `GB`/`IS` `0/"@@tz_gmt@@"`, `RU` `+180/"@@tz_msk@@"` + Kaliningrad `+120/"@@tz_eet@@"`, `TR` `+180/"@@tz_trt@@"`), and `Asia/Amman`/`Asia/Damascus` permanent `+180/"AST"` (`is_dst=False`).
- Completed Task 2 blocking decision checkpoint: maintainer approved `approve-v1` locking both `realism-snapshot-{summer,winter}.json` (`schema_version=1`) and `state/published.json` (`schema_version=1`).
- Implemented `src/ets2v2/registry/snapshot.py` (`RealismSnapshotFuel`, `RealismSnapshotCountry`, `RealismSnapshot`, `build_realism_snapshot`, `serialize_snapshot_bytes`, `write_realism_snapshot`) and wired `ets2v2 registry snapshot` (`--season`, `--date`, `--anchor-year`, `--out`).

## Deviations from Plan
- The Plan `02-02` subagent stalled in `waiting_for_dependents` after running full-repo `pytest` (`149 passed in 70.63s` exceeded the 10s sync wait cap); the orchestrator re-verified all gates, wrote this summary, and committed the changes. Subsequent wave subagents are scoped strictly to fast targeted test suites (<5s) so no subagent command backgrounds.

## Verification
- `uv run --offline ruff check`: exit 0 (`All checks passed!`)
- `uv run --offline ruff format --check`: exit 0 (`40 files already formatted`)
- `uv run --offline basedpyright`: exit 0 (`0 errors, 0 warnings, 0 notes`)
- `uv run --offline pytest tests/test_registry_*.py -q --tb=short`: exit 0 (`33 passed in 0.43s`)
- Full repository `pytest`: `149 passed`

---
*Phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a*
*Completed: 2026-11-19*
