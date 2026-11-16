---
phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine
plan: "03"
subsystem: baseline
tags: [baseline, ets2-1.62, pydantic, sha256, cli, vfs, sii, tdd, basedpyright, ruff]

requires:
  - "01-01"
  - "01-02"
  - "01-04"
provides:
  - "Clean-room Pydantic v2 schemas for ETS2 1.62.3.3s baseline metadata (ets2v2.baseline.models)"
  - "Deterministic extractor, canonical UTF-8 no-BOM LF JSON writer, SHA-256 verifier, and optional raw-cache exporter (ets2v2.baseline.extractor)"
  - "CLI subcommands `ets2v2 vfs inspect` and `ets2v2 baseline extract` (ets2v2.cli)"
  - "Clean-room ETS2 1.62.3.3s JSON baseline bundle under data/baselines/ets2_1.62_def/ (manifest, countries, speed_limits, fuel_boards, locales)"
  - "CI-safe synthetic HashFS v2 extractor tests and committed 1.62 baseline + @pytest.mark.local_ets2 round-trip contract tests"
affects: [phase-2, phase-3, phase-4]

tech-stack:
  added: []
  patterns: [clean-room JSON baseline boundary, deterministic sorted canonical JSON + SHA-256 manifest, targeted HashFS prefix DLC audit, whitespace-tolerant @@fp_*@@ slot classification]

key-files:
  created:
    - src/ets2v2/baseline/__init__.py
    - src/ets2v2/baseline/models.py
    - src/ets2v2/baseline/extractor.py
    - data/baselines/ets2_1.62_def/manifest.json
    - data/baselines/ets2_1.62_def/countries.json
    - data/baselines/ets2_1.62_def/speed_limits.json
    - data/baselines/ets2_1.62_def/fuel_boards.json
    - data/baselines/ets2_1.62_def/locales.json
    - tests/test_baseline_extractor.py
    - tests/test_baseline_contracts.py
  modified:
    - src/ets2v2/cli.py

key-decisions:
  - "Normalized trailing whitespace when classifying @@fp_*@@ slot text in extractor.py so gas_ba_apus_lpg ('@@fp_ba_diesel5@@ ') resolves to fp_key='fp_ba_diesel5' while preserving the verbatim slot text and classifying @@000.0@@ (gas_is_skanfill_95) as placeholder (yielding exact 373 active_fp + 88 placeholder/blank = 461)."
  - "Scoped DLC archive country auditing (_audit_dlc_archives) via targeted list_paths(['def/country', 'base/def/country']) plus direct def/country*.sii existence checks, reducing full 107-DLC extraction runtime from ~244s to ~0.94s with identical counts."
  - "Enforced raw-cache isolation: write_baseline_bundle emits strictly clean-room Pydantic JSON files, raw .sii/.sui dumps are accepted only in explicit --raw-cache-dir outside repo data/ and --out-dir, and test_baseline_contracts.py enforces zero .sii/.sui files under data/."

patterns-established:
  - "All baseline JSON outputs serialize via json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + '\\n' using write_bytes() to guarantee UTF-8 no-BOM LF across Windows and Linux."
  - "Live proprietary archive checks use @pytest.mark.local_ets2 with skipif when resolve_game_dir() archives are absent, keeping CI fast and self-contained."

requirements-completed: [VFS-02]

actuals:
  tokens: 137519
  tasks: 3
  commits: 0  # Coordinator handles git commit and STATE/ROADMAP/VALIDATION updates

duration: 33min
completed: 2026-11-16
---

# Phase 1 Plan 03: ETS2 1.62.3.3s Baseline Extraction & CLI Subcommands Summary

**Implemented clean-room Pydantic v2 baseline schemas, deterministic `ets2v2` extractor/verifier, `vfs inspect` + `baseline extract` CLI subcommands, CI-safe + `@pytest.mark.local_ets2` test suites, and extracted the verified ETS2 `1.62.3.3s` baseline JSONs (`36` countries, `36` speed limits, `461` fuel boards, `43` locales, `12` `tz_*` keys, `99` `fp_*` keys).**

## Accomplishments
- **Task 1 (`tracer`, Red -> Green):** Wrote red-first synthetic HashFS v2 tests in `tests/test_baseline_extractor.py`, verified RED (`ModuleNotFoundError: No module named 'ets2v2.baseline'`), then implemented `src/ets2v2/baseline/{models.py,extractor.py,__init__.py}` and updated `src/ets2v2/cli.py` with `ets2v2 vfs inspect` and `ets2v2 baseline extract` (`--game-dir`, `--out-dir`, `--raw-cache-dir`, `--check`). Verified all 12 tests across `test_cli_scaffold.py` and `test_baseline_extractor.py` pass under `ruff check`, `ruff format --check`, and `basedpyright` strict.
- **Task 2 (`tdd="true"`, Red Gate):** Authored `tests/test_baseline_contracts.py` prior to extracting `data/baselines/ets2_1.62_def/*.json`. Verified `ruff check`, `ruff format --check`, and `basedpyright` passed cleanly and `pytest tests/test_baseline_contracts.py -k "not local_ets2"` failed RED (`6 failed`) because the baseline JSONs did not yet exist.
- **Task 3 (Extraction & Full Green Verification):** Executed `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def` against `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`, verified `--check` passed with 0 byte diff, exercised `uv run ets2v2 vfs inspect "...\version.scs"`, verified zero `.sii`/`.sui` files under `data/` and `tests/`, and verified the full test, lint, format, and type-check suite passed GREEN.

## Verified `data/baselines/ets2_1.62_def/manifest.json` Counts
- `application`: `"eut2"`
- `game_version`: `"1.62.3.3"`
- `extractor_schema_version`: `1`
- `def_entry_count`: `66066`
- `locale_entry_count`: `521`
- `country_count`: `36`
- `speed_limit_count`: `36`
- `total_sign_boards`: `12942`
- `fuel_board_count`: `461` (`active_fp_board_count`: `373`, `placeholder_or_blank_board_count`: `88`)
- `excluded_fuel_keyword_boards`: `["fi_oulu_95", "fi_oulu_98", "rs_fuel_01", "ru_m_95", "ru_m_98"]`
- `locale_count`: `43` (`fr_qc` absent, `fr_ca` present)
- `tz_key_count`: `12`
- `fp_key_count`: `99`
- `file_sha256s`:
  - `countries.json`: `b238d259d83005f0cf9052c2f4ed9f5367ffeec742ebcd9b933115efcd068901`
  - `fuel_boards.json`: `ad27cc852e1d9496231c1c840ddad8c76af466fa1b0d793e2aa368a03a0b8db8`
  - `locales.json`: `964e8480f37a8cf1b64bee78663bd1e0937ff75311b46ce830e8ef25467a42aa`
  - `speed_limits.json`: `3330297366affcbd318b14143f05baa4613b9fb63cd2022a72f0f9632de3be52`

## Deviations from Plan
- **Auto-fixed empirical edge case in slot classification (`gas_ba_apus_lpg`):** Real ETS2 `1.62.3.3s` `def/sign/board/gas_ba_apus_lpg.sii` stores `text: "@@fp_ba_diesel5@@ "` with a trailing space (and `gas_is_skanfill_95.sii` stores `text: "@@000.0@@"`). Normalized surrounding whitespace and required `fp_` prefix in `_extract_fp_key()` so `gas_ba_apus_lpg` classifies as `active_fp` (`373` total) while `gas_is_skanfill_95` classifies as `placeholder` (`88` placeholder/blank total) without mutating raw slot text.
- **Auto-fixed DLC audit performance (`_audit_dlc_archives`):** Initial full-archive directory walk across 107 local `dlc_*.scs` files took ~244s; scoped `_audit_dlc_archives` to `list_paths(["def/country", "base/def/country"])` plus explicit `def/country*.sii` existence checks, cutting extraction runtime to ~1-2s with identical results.
- Git commits and `STATE.md`/`ROADMAP.md`/`01-VALIDATION.md` updates deferred to coordinator per execution instructions.

## Known Stubs
- None (`TODO`/`FIXME`/`XXX`/`HACK` scan across all owned Python modules returned zero matches).

## Verification
- `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def`: exit 0
- `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def --check`: exit 0 (0 byte diff)
- `uv run ets2v2 vfs inspect "D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\version.scs"`: exit 0 (`1` entry: `version.sii`)
- `uv run pytest`: `97 passed in 59.19s` (95 CI-safe + 2 `@pytest.mark.local_ets2` live-archive tests incl. all 36 `1.62.3.3s` SII surgical round-trips)
- `uv run pytest -k "not local_ets2"`: `95 passed, 2 deselected in 0.62s` (CI subset)
- `uv run ruff check`: `All checks passed!`
- `uv run ruff format --check`: `31 files already formatted`
- `uv run basedpyright`: `0 errors, 0 warnings, 0 notes`
- Verified all 11 owned files and `01-03-SUMMARY.md` use UTF-8 without BOM and LF (`\n`) line endings, with zero `.sii`/`.sui` files under `data/` or `tests/`.

## Self-Check: PASSED

---
*Phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine*
*Completed: 2026-11-16*
