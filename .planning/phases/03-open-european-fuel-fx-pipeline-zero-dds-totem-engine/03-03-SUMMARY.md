---
phase: 03-open-european-fuel-fx-pipeline-zero-dds-totem-engine
plan: "03"
subsystem: zero-dds-totem-engine
tags: [sign-board, fuel-boards, totem-catalog, option-4b, zero-dds, 43-locales, prices-lock, core-builder]
dependency_graph:
  requires:
    - "03-02 (committed 39-territory state/prices.lock.json and RealismSnapshot v1 prices_lock injection)"
    - "01-03 (ETS2 1.62.3.3s baseline extractor & SII hygiene/sign_board/localization parsers)"
  provides:
    - "Full 24-attribute ETS2 1.62 sign_board_template (6 attrs) + sign_template_text (18 attrs) parser and re-extracted clean-room data/baselines/ets2_1.62_def/{fuel_boards,manifest}.json"
    - "Pure offline ets2v2.normalize.totem_catalog classifying all 461 1.62 boards into 460 identifiable boards across 37 countries (36 Vanilla+DLC + IE) while verifying gas_empty as the sole font_size==0/font_opacity==0 spacer"
    - "Option 4b Zero-DDS compiler ets2v2.package.totems emitting 460 attribute-preserving def/sign/board/*.sii files and 43 byte-identical locale/<lang>/local_module.ets2v2_fuel.sii modules (localization_db : .ets2v2_fuel) with pluggable TotemTokenResolver Protocol"
    - "Core Summer/Winter package builder & CLI wired offline to state/prices.lock.json producing 579-file Workshop roots and 578-entry deterministic local ZIPs with zero .dds/.tobj assets"
  affects:
    - "03-04 (6-font SDF width-budget / <sup>9</sup> / UK-pence / integer-currency TotemTokenResolver, Offline SCS Validator hard totem invariants, D-16 changelog/description attributions, and Friday CI fetch wiring)"
    - "Phase 4 (ProMods pm_*_fuel totems reusing ets2v2.normalize.totem_catalog grade adapters and ets2v2.package.totems patterns)"
tech-stack:
  added: []
  patterns:
    - "Optional None-defaulted fields on SignBoardTemplate/SignTemplateTextSlot and FuelBoardEntry/FuelBoardSlot preserving 100% Phase 1 synthetic fixture compatibility while persisting all 24 real ETS2 1.62 rendering attributes"
    - "Pluggable TotemTokenResolver Protocol decoupling 460-board SII synthesis from Plan 03-04's 6-font SDF width-budget display formatter"
    - "9-decimal finite float serialization preserving float32 coordinates/sizes without scientific notation and round-tripping cleanly through parse_sign_board()"
    - "Uniform dot-decimal Decimal(ROUND_HALF_UP) default formatting and single-payload byte-identical replication across all 43 active ETS2 1.62 locales"
key-files:
  created:
    - src/ets2v2/normalize/totem_catalog.py
    - src/ets2v2/package/totems.py
    - tests/test_totem_compiler.py
  modified:
    - src/ets2v2/sii/sign_board.py
    - src/ets2v2/baseline/models.py
    - src/ets2v2/baseline/extractor.py
    - data/baselines/ets2_1.62_def/fuel_boards.json
    - data/baselines/ets2_1.62_def/manifest.json
    - src/ets2v2/normalize/__init__.py
    - src/ets2v2/package/__init__.py
    - src/ets2v2/package/builder.py
    - src/ets2v2/cli.py
    - tests/test_sii_boards_locales.py
    - tests/test_baseline_contracts.py
    - tests/test_package_builder.py
decisions:
  - "Preserved legacy optional fields (board_size, h_align, v_align) alongside the 16 newly captured real ETS2 1.62 attributes so every Phase 1 synthetic test fixture remains green without schema churn."
  - "Formatted board float attributes with 9-decimal trimmed finite decimals (no scientific notation) so float32 IEEE-754 hex values extracted from def.scs round-trip faithfully through parse_sign_board() within 1e-7."
  - "Enforced fail-loud validation on structural spacers (gas_empty must have font_size == 0.0 and font_opacity == 0.0), excluded multi-item highway signs, deprecated fr_qc locales, conflicting token values, and unknown board names."
  - "Exposed TotemTokenResolver Protocol in src/ets2v2/package/totems.py with a clean dot-decimal Decimal ROUND_HALF_UP default so Plan 03-04 can plug in the full 6-font SDF width-budget / <sup>9</sup> formatter with zero duplication."
metrics:
  duration: "46m"
  completed: "2026-11-21"
status: complete
actuals:
  tokens: 171510
  tasks: 2
  commits: 2
plan_head_before: 257737dcb55d65ab6e195c4965e3951014dc514b
plan_head_after: 0953fe5ca2512313eaac7747d8836e93240d7251
---

# Phase 3 Plan 03: 24-Attribute `fuel_boards.json` Refresh & Option 4b Zero-DDS 43-Locale Totem Engine Summary

Extended `ets2v2.sii.sign_board` and the clean-room `1.62` baseline extractor to capture all 24 ETS2 `1.62` sign board rendering attributes (`6` `sign_board_template` + `18` `sign_template_text`) and refreshed `data/baselines/ets2_1.62_def/{fuel_boards,manifest}.json` directly from local ETS2 `1.62.3.3s` `def.scs`; implemented the exhaustive 460-board classifier (`ets2v2.normalize.totem_catalog`) fixing all `D-09` missing/swapped/blank/placeholder boards across 37 countries (`36` Vanilla+DLC + `IE`) while skipping `gas_empty` and 5 highway signs; built the Option 4b Zero-DDS SII compiler (`ets2v2.package.totems`) emitting 460 attribute-preserving `def/sign/board/*.sii` files and 43 byte-identical `locale/<lang>/local_module.ets2v2_fuel.sii` modules (`localization_db : .ets2v2_fuel`); and wired offline `state/prices.lock.json` loading plus all 503 totem/locale payloads into `build_core_edition()` (`579` Workshop files / `578` local ZIP entries) and `ets2v2 package build --prices-lock`.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Extend `sign_board.py` & baseline extractor with all 24 ETS2 `1.62` rendering attributes and re-extract `fuel_boards.json` | `2ef6dd2` | `src/ets2v2/sii/sign_board.py`, `src/ets2v2/baseline/{models,extractor}.py`, `data/baselines/ets2_1.62_def/{fuel_boards,manifest}.json`, `tests/{test_sii_boards_locales,test_baseline_contracts}.py` |
| 2 | Build 460-board totem classifier, Option 4b Zero-DDS 43-locale compiler, and wire totems + `prices.lock.json` into Core package builder | `0953fe5` | `src/ets2v2/normalize/{totem_catalog,__init__}.py`, `src/ets2v2/package/{totems,__init__,builder}.py`, `src/ets2v2/cli.py`, `tests/{test_totem_compiler,test_package_builder}.py` |

## Verification Results

- `uv run --offline ets2v2 baseline extract --check --out-dir data/baselines/ets2_1.62_def`: exited `0` (`Baseline check passed (eut2 1.62.3.3): 36 countries, 36 speed limits, 461 fuel boards (373 active fp), 43 locales, 12 tz keys, 99 fp keys.`); only `fuel_boards.json` and `manifest.json` changed under `data/baselines/ets2_1.62_def/`, with zero raw `.sii`/`.sui` files under `data/`.
- `uv run --offline pytest tests/test_sii_boards_locales.py tests/test_baseline_extractor.py tests/test_baseline_contracts.py -x`: **19 passed** (including both `@pytest.mark.local_ets2` round-trip & zero-diff baseline tests).
- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `83 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2"`: **317 passed, 2 deselected** (all 4 AST DAG isolation walls intact, all 460 board SII round-trips verbatim, all 43 locales byte-identical with `fr_ca` present & `fr_qc` absent, Workshop/local validator and Phase A release suites 100% green).

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-03-12** | Clean-room JSON-only persistence in `data/baselines/ets2_1.62_def/fuel_boards.json` with exact SHA-256 verification (`baseline extract --check`) and zero raw `.sii`/`.sui` files under `data/` (`test_no_raw_scs_files_committed_under_data`). |
| **T-03-13** | Every synthesized string passes `format_sii_string()` (rejecting `\` and `\x00`), locale unit uses `.ets2v2_fuel` (`11 <= 12` chars), every token enforces `^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$`, comma decimals are rejected, and every emitted board/locale file passes `validate_sii_hygiene(..., require_siinunit=True)`. Verified in `tests/test_totem_compiler.py`. |
| **T-03-14** | `classify_fuel_board()` skips only `gas_empty` after verifying `font_size == 0.0 and font_opacity == 0.0`, rejects any excluded highway sign injected into `boards`, and raises `ValueError` on unknown board names. Verified in `tests/test_totem_compiler.py`. |
| **T-03-SC** | Zero new third-party dependencies added in `03-03`. |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. All 460 identifiable `1.62` fuel boards, 43 synchronized locale modules, offline `state/prices.lock.json` loading, and Core Summer/Winter dual-target packaging (`579` Workshop files / `578` local ZIP entries) are wired end-to-end; `TotemTokenResolver` provides a clean default dot-decimal resolver and typed hook for Plan `03-04`'s 6-font SDF width-budget / `<sup>9</sup>` formatter.

## Self-Check: PASSED

- All 15 created/modified files exist on disk (`src/ets2v2/sii/sign_board.py`, `src/ets2v2/baseline/{models,extractor}.py`, `data/baselines/ets2_1.62_def/{fuel_boards,manifest}.json`, `src/ets2v2/normalize/{totem_catalog,__init__}.py`, `src/ets2v2/package/{totems,__init__,builder}.py`, `src/ets2v2/cli.py`, `tests/{test_sii_boards_locales,test_baseline_contracts,test_totem_compiler,test_package_builder}.py`).
- Both task commits (`2ef6dd2`, `0953fe5`) are verified ancestors of `HEAD` (`git rev-list --count 257737d..0953fe5 == 2`).
- All quality gates (`baseline extract --check`, `ruff check`, `ruff format --check`, `basedpyright`, `pytest` offline 317 passed + `local_ets2` 2 passed) passed cleanly.
