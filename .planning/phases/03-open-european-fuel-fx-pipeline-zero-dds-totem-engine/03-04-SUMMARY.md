---
phase: 03-open-european-fuel-fx-pipeline-zero-dds-totem-engine
plan: "04"
subsystem: zero-dds-totem-engine-validator-release
tags: [sdf-fonts, totem-formatting, zero-dds, offline-validator, d-12, d-16, changelogs, friday-ci]
dependency_graph:
  requires:
    - "03-03 (24-attribute fuel_boards.json refresh, 460-board classifier, Option 4b Zero-DDS compiler & Core package builder)"
    - "03-02 (committed 39-territory state/prices.lock.json, Tier 1 collectors, circuit breaker & RealismSnapshot v1 injection)"
  provides:
    - "6-font ETS2 1.62 SDF glyph & width-budget physics and Decimal ROUND_HALF_UP native-currency pump formatter (ets2v2.normalize.totem_format) routing all 460 boards cleanly across 164 unique tokens (136 sup / 12 3-dec / 40 compact)"
    - "Package-isolated Offline SCS Validator D-12 hard gates: ETS2V2-INV-ZERO-DDS, ETS2V2-INV-LOCALE-SYNC (exact 43 active locales, fr_ca present, fr_qc rejected), and ETS2V2-INV-TOTEM-BOARDS (exact 460 boards, attribute preservation, zero dangling/orphan tokens, D-09 regression checks)"
    - "D-16 open-data attributions in Workshop description.txt (zero volatile dates/versions) and Markdown CHANGELOG_{SUMMER,WINTER}.md (36-country fuel summary table, highlighted Circuit-Breaker & Staleness Alerts, full open-data licensing)"
    - "Offline Phase A release orchestrator (publish/release.py + CLI --prices-lock) and Friday 06:00 UTC two-stage workflow (.github/workflows/phase-a-release.yml) running online ets2v2 fetch (optional TANKERKOENIG_API_KEY via step env) before offline publish release and staging state/prices.lock.json in release/phase-a-weekly"
  affects:
    - "Phase 4 (ProMods Companion Editions reusing ets2v2.normalize.totem_format SDF width physics and validate/invariants patterns)"
    - "Phase 5 (Global Tier 1/2/3 fuel collectors feeding state/prices.lock.json into the same offline publish release & Friday CI pipeline)"
tech-stack:
  added: []
  patterns:
    - "Deterministic worst-case probe strings ('1.88<sup>9</sup>', '1.889') in resolve_totem_token_and_value() so Eurozone 3-tier token variant assignment depends strictly on board geometry & font and never flaps week-to-week"
    - "Carry-safe Decimal ROUND_HALF_UP national pump formatting handling boundary transitions cleanly (1.7996 -> 1.80<sup>0</sup>, RO 9.996 -> 10.0, MK 99.996 -> 100.0, GB pence 142.9, BG EUR 1.34, HUF/ISK/ALL/RSD integers, CZ .X0)"
    - "Strict AST-enforced Layer 8 validator isolation (ets2v2.validate imports zero symbols from package/, normalize/, fetch/, httpx, or openpyxl)"
    - "Zero-expression-interpolation GitHub Actions workflow steps (TANKERKOENIG_API_KEY strictly via step env:, embedded Python PR body generator compiled in tests)"
key-files:
  created:
    - src/ets2v2/normalize/totem_format.py
    - tests/test_totem_formatting.py
  modified:
    - src/ets2v2/normalize/__init__.py
    - src/ets2v2/package/totems.py
    - src/ets2v2/validate/invariants.py
    - src/ets2v2/validate/workshop.py
    - src/ets2v2/validate/__init__.py
    - src/ets2v2/package/metadata.py
    - src/ets2v2/publish/changelog.py
    - src/ets2v2/publish/release.py
    - src/ets2v2/cli.py
    - .github/workflows/phase-a-release.yml
    - tests/test_totem_compiler.py
    - tests/test_validate_invariants.py
    - tests/test_validate_workshop.py
    - tests/test_package_icons_metadata.py
    - tests/test_publish_release.py
    - tests/test_publish_workflow.py
decisions:
  - "Evaluated Eurozone 3-tier width routing against deterministic worst-case probe strings ('1.88<sup>9</sup>' and '1.889') rather than weekly fluctuating prices so board-to-token assignments remain permanently stable across releases."
  - "Removed .dds and .tobj from ALLOWED_SCS_ASSET_EXTENSIONS and checked FORBIDDEN_TOTEM_EXTENSIONS unconditionally before extension allowlist checks so Zero-DDS violations always emit the dedicated ETS2V2-INV-ZERO-DDS error code with or without baseline_dir."
  - "Stripped <sup>/</sup> tags in Markdown changelog fuel tables to clean 3-decimal ASCII while preserving full native currency conventions (UK pence, BG EUR, integer ISK/HUF/ALL/RSD, CZ .X0, RO/MK width-bounded) and omitting the Circuit-Breaker & Staleness Alerts section when a lockfile has zero alerts and zero fallback entries."
  - "Passed TANKERKOENIG_API_KEY strictly via step-level env: in .github/workflows/phase-a-release.yml and generated Release PR alerts via an inline Python heredoc reading dist/fetch_summary.json so zero GitHub Actions expressions appear inside any run: block."
metrics:
  duration: "35m"
  completed: "2026-11-22"
status: complete
actuals:
  tokens: 25820
  tasks: 3
  commits: 3
plan_head_before: db0fc88f05c0bad8d740b300d71ac2755420b0e6
plan_head_after: eed3c0fe755ca7a772e5fe23dc3ebae4d9094a90
---

# Phase 3 Plan 04: 6-Font SDF Native-Currency Totem Formatter, D-12 Validator Gates, D-16 Changelogs & Friday CI Summary

Implemented `ets2v2.normalize.totem_format` encoding all 6 verified ETS2 `1.62` gas `.font` SDF glyph and width-budget ratios and wired `resolve_totem_token_and_value()` as the default resolver in `package/totems.py` (routing all `460` identifiable boards across `164` unique tokens with `136` `<sup>9</sup>`, `12` wide 7-seg `_3_ets2v2`, `40` narrow `_c_ets2v2`, UK pence `142.9`, Bulgaria post-2026 EUR `2`-dec, integer `HUF`/`ISK`/`ALL`/`RSD`, `CZ` `.X0`, `RO`/`MK` width-bounded precision, `FI`/`GR`/`SI` `3`-dec, and `460/460` verified zero-overflow compliance); extended the strictly package-isolated Offline SCS Validator (`validate/{workshop,invariants}.py`) with hard `D-12` gates (`ETS2V2-INV-ZERO-DDS`, `ETS2V2-INV-LOCALE-SYNC`, `ETS2V2-INV-TOTEM-BOARDS`); and completed end-to-end `D-16` open-data attributions in `description.txt` and `CHANGELOG_{SUMMER,WINTER}.md` (36-country fuel summary table + Circuit-Breaker & Staleness Alerts), offline `state/prices.lock.json` wiring in `publish/release.py` and `ets2v2 publish release --prices-lock`, and two-stage Friday CI fetch + persistent Release PR staging in `.github/workflows/phase-a-release.yml`.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Build 6-font SDF width-budget & native-currency totem formatter (`totem_format.py`) and wire into `package/totems.py` | `e68b3eb` | `src/ets2v2/normalize/{totem_format,__init__}.py`, `src/ets2v2/package/totems.py`, `tests/{test_totem_formatting,test_totem_compiler}.py` |
| 2 | Extend Offline SCS Validator with hard D-12 totem invariants (`ETS2V2-INV-ZERO-DDS`, `ETS2V2-INV-LOCALE-SYNC`, `ETS2V2-INV-TOTEM-BOARDS`) under strict zero-import isolation | `6924fa4` | `src/ets2v2/validate/{invariants,workshop,__init__}.py`, `tests/{test_validate_invariants,test_validate_workshop}.py` |
| 3 | Wire D-16 description/changelog fuel tables & alerts, offline `release.py` lockfile flow, and Friday CI `phase-a-release.yml` fetch+PR staging | `eed3c0f` | `src/ets2v2/package/metadata.py`, `src/ets2v2/publish/{changelog,release}.py`, `src/ets2v2/cli.py`, `.github/workflows/phase-a-release.yml`, `tests/{test_package_icons_metadata,test_publish_release,test_publish_workflow}.py` |

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `85 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline pytest -q --tb=short`: **365 passed, 1 warning** (including both `@pytest.mark.local_ets2` tests, all 4 AST DAG isolation walls intact, all 460-board SDF width-budget & D-12 fault-injection tests, and workflow injection-safety + Python snippet compilation checks).
- End-to-end offline release & validator check (`uv run --offline ets2v2 publish release --prices-lock state/prices.lock.json --write-state`):
  - Summer Workshop root: **579 files** — `ets2v2 validate workshop` passed (`0 errors, 0 warnings`); Local ZIP: **578 entries** — `ets2v2 validate local` passed (`0 errors, 0 warnings`).
  - Winter Workshop root: **579 files** — `ets2v2 validate workshop` passed (`0 errors, 0 warnings`); Local ZIP: **578 entries** — `ets2v2 validate local` passed (`0 errors, 0 warnings`).

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-03-15** | All pump strings formatted strictly from validated `Decimal` values matching `^[0-9]+(?:\.[0-9]+)?(?:<sup>[0-9]</sup>)?$`, verified against all 6 SDF font metrics & width budgets in `normalize/totem_format.py`, and independently re-audited in `validate/invariants.py`. |
| **T-03-16** | `.github/workflows/phase-a-release.yml` triggers strictly on `schedule` and `workflow_dispatch`, passes `TANKERKOENIG_API_KEY` exclusively via step-level `env:` with zero `${{` inside any `run:` block, and `.github/workflows/ci.yml` remains read-only without `ets2v2 fetch`. Enforced by `tests/test_publish_workflow.py`. |
| **T-03-17** | `ETS2V2-INV-ZERO-DDS` unconditionally rejects `.dds` and `.tobj` files in Workshop roots and local ZIPs before extension allowlist checks; AST isolation tests confirm `validate/` has zero imports from `package/`, `normalize/`, `fetch/`, `httpx`, or `openpyxl`. |
| **T-03-18** | `publish/release.py` executes the full Offline SCS Validator (including Zero-DDS, 43-locale sync, and 460-board integrity) as a hard gate before mutating `state/published.json` or changelogs, and surfaces all circuit-breaker & staleness alerts in Markdown changelogs and Release PR bodies. |
| **T-03-SC** | Zero new third-party dependencies added in `03-04`. |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. All 460 identifiable `1.62` fuel boards, 164 width-safe native-currency tokens, 43 synchronized active locale modules, D-12 validator gates, D-16 changelogs/descriptions, offline release orchestration, and Friday CI fetch+PR staging are fully implemented and verified end-to-end.

## Self-Check: PASSED

- All 18 created/modified files exist on disk (`src/ets2v2/normalize/{totem_format,__init__}.py`, `src/ets2v2/package/{totems,metadata}.py`, `src/ets2v2/validate/{invariants,workshop,__init__}.py`, `src/ets2v2/publish/{changelog,release}.py`, `src/ets2v2/cli.py`, `.github/workflows/phase-a-release.yml`, `tests/{test_totem_formatting,test_totem_compiler,test_validate_invariants,test_validate_workshop,test_package_icons_metadata,test_publish_release,test_publish_workflow}.py`).
- All 3 task commits (`e68b3eb`, `6924fa4`, `eed3c0f`) are verified ancestors of `HEAD` (`git rev-list --count db0fc88f..eed3c0fe == 3`).
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, full `pytest` 365 passed, and end-to-end `ets2v2 publish release` + `validate workshop`/`validate local` on 579-file Summer & Winter builds) passed with zero errors.
