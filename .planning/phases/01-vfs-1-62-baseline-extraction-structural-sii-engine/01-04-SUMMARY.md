---
phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine
plan: "04"
subsystem: sii
status: complete
tags: [sii, sui, lexer, hygiene, surgical-editor, pydantic, tdd, basedpyright, ruff]

requires:
  - "01-01"
provides:
  - "SCS SII/SUI hygiene validator and UTF-8 no-BOM / LF normalization engine (ets2v2.sii.hygiene)"
  - "Single-pass O(n) string- and comment-aware SII/SUI structural scanner and IEEE754 &hex float parser (ets2v2.sii.lexer)"
  - "Span-preserving surgical SiiDocument editor with absent-key insertion and contiguous attr[] replacement (ets2v2.sii.document)"
  - "Surgical country.sii @include and country_data read + patch adapter preserving regions, quoting, secondary TZs, and comments (ets2v2.sii.country)"
  - "Interleaved per-lane country_speed_limit reader and surgical road-class editor preserving train/tram blocks verbatim (ets2v2.sii.speed_limits)"
  - "Read-only sign_board_template (&hex, nil, items[i]) and localization_db (key[]/val[]) adapters (ets2v2.sii.sign_board, ets2v2.sii.localization)"
affects: [01-03, phase-2, phase-3, phase-4]

tech-stack:
  added: []
  patterns: [single-pass linear O(n) scanner, span-preserving surgical splice + re-index, UTF-8 no-BOM pass-1 normalization, pass-2 zero-byte-diff idempotency, strict Pydantic v2 frozen models]

key-files:
  created:
    - src/ets2v2/sii/__init__.py
    - src/ets2v2/sii/hygiene.py
    - src/ets2v2/sii/lexer.py
    - src/ets2v2/sii/document.py
    - src/ets2v2/sii/country.py
    - src/ets2v2/sii/speed_limits.py
    - src/ets2v2/sii/sign_board.py
    - src/ets2v2/sii/localization.py
    - tests/test_sii_hygiene.py
    - tests/test_sii_document.py
    - tests/test_sii_country.py
    - tests/test_sii_speed_limits.py
    - tests/test_sii_boards_locales.py
  modified: []

key-decisions:
  - "Designed SiiDocument edits to splice targeted character spans and immediately re-scan normalized text while resolving SiiUnitBlock references by index+(class_name, unit_name), eliminating stale-offset hazards across chained scalar/array mutations."
  - "Separated lexer.py (stdlib only) from hygiene.py (imports lexer) and document.py (imports lexer + hygiene) to form an acyclic dependency DAG."
  - "Implemented dual-mode lane patching in speed_limits.py: matching lane_speed_class sequences update/insert/remove individual fields in-place preserving inline comments and blank lines, while added/reordered lanes rewrite only the targeted vehicle unit's lane region without touching train/tram."

patterns-established:
  - "Surgical SII/SUI editing touches only target value spans or insertion points (before closing } or trailing @include), preventing Estonia substring corruption and regions[]/secondary_time_zone* stripping."
  - "sign_board_template parsing resolves items[i] via O(1) unit-name lookup over parsed units rather than preallocating from items: N, preventing memory DoS on malformed counts."

requirements-completed: [SII-01, SII-02]

actuals:
  tokens: 27781
  tasks: 3
  commits: 0  # Coordinator commits after parallel Wave 2 verification

duration: 14min
completed: 2026-11-16
---

# Phase 1 Plan 04: Structural SII/SUI Lexer, Surgical Editor, Hygiene & Adapters Summary

**Implemented clean-room SII/SUI structural scanner, UTF-8 no-BOM/LF hygiene validator, span-preserving surgical `SiiDocument` editor, `country_data` + `country_speed_limit` read/patch adapters, and read-only `sign_board_template` + `localization_db` parsers.**

## Accomplishments
- **Task 1 (Tracer, Red -> Green):** Built `hygiene.py` (`SiiEncodingError`, `SiiDiagnostic`, `normalize_sii_bytes`, `serialize_sii_text`, `validate_sii_hygiene`), `lexer.py` (`SiiSpan`, `parse_sii_float`, `scan_sii_structure`), and `document.py` (`SiiDocument`, `SiiUnitBlock`, `SiiAttributeSpan`, `SiiIncludeSpan`). Verified strict UTF-8 BOM/CRLF pass-1 normalization, pass-2 zero-byte-diff idempotency, column-0 `@include` enforcement, POSIX `/` + `..` path checks, `[a-z0-9_]{1,12}` unit segment validation, `#`/`//`/`/* */` comment and quoted-string awareness, inline/next-line `{`, absent-attribute insertion before `}` or trailing `@include`, and contiguous `attr[]` expansion/shrinking.
- **Task 2 (TDD, Red -> Green):** Built `country.py` (`CountryDataModel`, `CountryDataPatch`, `parse_country_includes`, `parse_country_data`, `patch_country_data`) covering all 20 observed ETS2 1.62 `country_data` attributes + `iso_country_code_quoted` + `extra_attributes`, and `speed_limits.py` (`LaneSpeedRule`, `VehicleSpeedLimitBlock`, `SpeedLimitsFile`, `parse_speed_limits`, `patch_speed_limits`) grouping interleaved per-lane arrays (`lane_speed_class[]`, `limit[]`, `urban_limit[]`, `max_limit[]`, `uncommon[]`) while keeping `train`/`tram` blocks, inline comments, `regions[]`, `region_areas[]`, `secondary_time_zone*`, and `"Eesti"` intact.
- **Task 3 (TDD, Red -> Green):** Built `sign_board.py` (`SignBoardTemplate`, `SignTemplateTextSlot`, `parse_sign_board`) handling IEEE754 `&hex` floats, `nil`, `items: N` / `items[i]` child linking, fuel-board candidate identification (`model_name == ""` and `items_count == 1`), and multi-item highway signs; built `localization.py` (`LocalizationEntry`, `parse_localization_db`) for headerless `.sui` and wrapped `localization_db` files; exported the public API in `src/ets2v2/sii/__init__.py`.

## Deviations from Plan
- None — plan executed as specified (commits deferred to Wave 2 coordinator per parallel execution rules).

## Known Stubs
- None (stub scan across all `src/ets2v2/sii/*.py` files reported clean).

## Verification
- `uv run pytest -p no:cacheprovider tests/test_cli_scaffold.py tests/test_sii_*.py -v`: `36 passed` (27 SII tests + 9 scaffold tests)
- `uv run ruff check --no-cache src/ets2v2/sii tests/test_sii_*.py`: `All checks passed!`
- `uv run ruff format --check --no-cache src/ets2v2/sii tests/test_sii_*.py`: `13 files already formatted`
- `uv run basedpyright src/ets2v2/sii tests/test_sii_*.py`: `0 errors, 0 warnings, 0 notes`
- All 13 owned files and `01-04-SUMMARY.md` verified UTF-8 without BOM and LF (`\n`) line endings.

## Self-Check: PASSED

---
*Phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine*
*Completed: 2026-11-16*
