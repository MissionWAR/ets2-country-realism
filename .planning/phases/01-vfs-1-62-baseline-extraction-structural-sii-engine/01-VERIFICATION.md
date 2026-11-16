---
phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine
verified: 2026-11-16T19:03:00Z
status: passed
score: 16/16 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 16/16
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 1: VFS, 1.62 Baseline Extraction & Structural SII Engine Verification Report

**Phase Goal:** Developers and build pipelines can cleanly inspect ETS2 `1.62.3.3s` and mod archives cross-platform, extract canonical baseline metadata, and surgically edit country and speed-limit SII/SUI files without corrupting comments, regions, or unrelated engine blocks.
**Verified:** 2026-11-16T19:03:00Z
**Status:** passed
**Re-verification:** Yes — post-review-fix closeout

## Goal Achievement

### Requirements Verdict Matrix

| Requirement | Plans | Verdict | Key Codebase Evidence |
| ----------- | ----- | ------- | --------------------- |
| `VFS-01` | `01-01`, `01-02` | **PASS** | Pure-Python MIT `CityHash64` 1.0.3 (`src/ets2v2/vfs/cityhash.py`); shared VFS helpers & `VfsArchive` context protocol (`src/ets2v2/vfs/types.py`); bounded `HashFsV1Archive`, `HashFsV2Archive`, `ProtectedArchiveStub`, `open_archive()` (`src/ets2v2/vfs/hashfs.py`); chunk-bounded `ZipArchive` with `0x41` encryption flags and post-dedup diagnostics (`src/ets2v2/vfs/zip_archive.py`); junction-pruned & `get_meta()` containment-checked `DirectoryArchive` (`src/ets2v2/vfs/dir_archive.py`); `VfsStack` with `MAX_STUB_INSPECT_BYTES` cap & refreshed `three_nk` meta (`src/ets2v2/vfs/stack.py`). All 58 VFS tests pass; live `def.scs`, `locale.scs`, and `version.scs` inspection succeeds with zero diagnostics. |
| `VFS-02` | `01-01`, `01-03` | **PASS** | Clean-room Pydantic schemas (`src/ets2v2/baseline/models.py`), deterministic extractor/verifier with CWD-independent `data/` cache guard, `def_stack` board reads, and `dlc_` prefix-stripped DLC audit (`src/ets2v2/baseline/extractor.py`), CLI `ets2v2 baseline extract` catching `ProtectedPayloadError`/`UnsupportedCompressionError` (`src/ets2v2/cli.py`), and 5 committed JSONs under `data/baselines/ets2_1.62_def/` (`36` countries, `36` speed limits, `461` fuel boards, `43` locales, `12` `tz_*`, `99` `fp_*`). Zero `.sii`/`.sui` files under `data/`; `--check` exits 0 with 0 byte diff. |
| `SII-01` | `01-01`, `01-04` | **PASS** | Structural O(n) scanner with `unbalanced_paren` recovery, EOF span clamping, and last-wins `get_scalar()` (`src/ets2v2/sii/lexer.py`); span-preserving surgical `SiiDocument` handling single-line/shared-brace mutations and fixed arrays (`src/ets2v2/sii/document.py`); `country_data` + `country.sii` adapter with fixed-array `attr[i]` parsing and newline/control-char escaping (`src/ets2v2/sii/country.py`); interleaved `country_speed_limit` editor with shared-brace safety (`src/ets2v2/sii/speed_limits.py`); read-only `sign_board_template` (`src/ets2v2/sii/sign_board.py`) and `localization_db` (`src/ets2v2/sii/localization.py`). All 35 SII unit tests and both `@pytest.mark.local_ets2` live `1.62.3.3s` tests (including all 36 country/speed-limit surgical round-trips) pass verbatim. |
| `SII-02` | `01-01`, `01-04` | **PASS** | Strict UTF-8 no-BOM + LF (`\n`) normalization (`normalize_sii_bytes`, `serialize_sii_text`) and hygiene validation (`validate_sii_hygiene`: index-0 BOM check, column-0 `@include`, POSIX `/` no `..` paths, escape-aware `_has_disallowed_backslash`, accurate `value_span` column reporting, balanced braces, `[a-z0-9_]{1,12}` unit segments) in `src/ets2v2/sii/hygiene.py`. Pass-2+ byte-exact idempotency verified in unit tests and across all 36 live `1.62.3.3s` files (`test_baseline_contracts.py`). |

### ROADMAP Success Criteria Verdict Matrix

| # | Success Criterion | Verdict | Verified Evidence |
| - | ----------------- | ------- | ----------------- |
| 1 | Reading a directory of HashFS v1, HashFS v2, standard `.zip`/`.scs`, and unpacked mod trees resolves VFS paths identically on Windows and Linux while cleanly reporting `3nK`, `AEM!`, or encrypted ZIP archives without attempting decryption or crashing. | **PASS** | `normalize_vfs_path()` canonicalizes `\` and `/` identically; `open_archive()` dispatches directories, `PK` ZIPs, `SCS#\x01`, `SCS#\x02`, `AEM!`, and unknown magic; `VfsStack` handles layered priority, `base/` normalization, `dlc_<id>/` scoping, and bounded empty `SiiNunit {}` shadowing (`MAX_STUB_INSPECT_BYTES = 1 MiB`). `detect_3nk()` (`b"3nK\x01"`), `aem_protected`, `encrypted_zip` (`flag_bits & 0x41` with central-dir filename listing and post-dedup diagnostics), `unsupported_compression`, `unsupported_metadata`, and `unknown_magic` emit `ArchiveDiagnostic` records and raise `ProtectedPayloadError`/`UnsupportedCompressionError` on decode/read without decryption logic (`tests/test_vfs_*.py`: 58 passed). |
| 2 | Extracting ETS2 `1.62.3.3s` `def.scs` and `locale.scs` produces deterministic, version-controlled baseline schemas and fixtures under `data/baselines/ets2_1.62_def/` covering all 36 country definitions, 36 `speed_limits.sii` files, `def/sign/board/*.sii` fuel boards, and all 43 active locales. | **PASS** | `data/baselines/ets2_1.62_def/` contains 5 deterministic JSONs (`manifest.json`, `countries.json`, `speed_limits.json`, `fuel_boards.json`, `locales.json`) with matching SHA-256 digests (`file_sha256s`), `country_count=36`, `speed_limit_count=36`, `fuel_board_count=461` (`373` `active_fp` + `88` `placeholder`/`blank`, excluding `5` multi-item highway signs), `locale_count=43` (`fr_qc` excluded, `fr_ca` present), `tz_key_count=12`, `fp_key_count=99`. `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def --check` exits 0 with zero diff; zero raw `.sii`/`.sui` files exist under `data/`. |
| 3 | Surgically updating `fuel_price`, `time_zone`, `time_zone_name`, `lights_mandatory`, `mass_limit_per_axle_count[]`, and `car`/`truck`/`bus` speed limits preserves comments (`#`, `//`, `/* */`), `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`, and `tram` blocks verbatim. | **PASS** | `patch_country_data()` and `patch_speed_limits()` splice only targeted value spans / insertion points via `SiiDocument` (supporting both append `[]` and fixed `attr: N` + `attr[i]` arrays, single-line/shared-brace blocks, and escaped `time_zone_name` strings). Verified by synthetic tests (`tests/test_sii_document.py`, `tests/test_sii_country.py`, `tests/test_sii_speed_limits.py`: 20 passed) and `@pytest.mark.local_ets2` live-archive round-trips across all 36 real `1.62.3.3s` countries and `speed_limits.sii` files (`tests/test_baseline_contracts.py`: 8 passed). |
| 4 | Every serialized `.sii`/`.sui` output passes strict SCS hygiene assertions (UTF-8 without BOM, `\n` LF endings, POSIX `/` internal paths, column-0 `@include`, valid unit scoping) and produces zero byte diff on idempotent round-trip writes. | **PASS** | `serialize_sii_text()` enforces UTF-8 no-BOM and `\n` LF on pass 1; `validate_sii_hygiene()` enforces UTF-8, index-0 BOM rejection, LF, column-0 `@include`, POSIX `/` no `..` paths (without false-positiving on valid UI escapes), balanced braces, and `[a-z0-9_]{1,12}` unit segments. Pass-1 clean round-trips, pass-2 BOM/CRLF normalization idempotency, and live `1.62.3.3s` round-trip idempotency verified (`tests/test_sii_hygiene.py`: 10 passed; `tests/test_baseline_contracts.py`: 8 passed). |

### Observable Truths (`01-01` through `01-04` `must_haves`)

| # | Plan | Truth | Status | Evidence |
| - | ---- | ----- | ------ | -------- |
| 1 | `01-01` | Python 3.12+ package `ets2v2` installs reproducibly via `uv sync --locked` with minimal Phase 1 dependencies (`pydantic>=2.14,<3` runtime; `basedpyright>=1.40,<2`, `ruff>=0.16`, `pytest>=9.2,<9.3`, `pytest-cov>=6,<8` dev). | ✓ VERIFIED | `pyproject.toml` lines 9-24 declare exact bounds; `uv lock --check --offline` and `uv sync --locked --offline --dry-run` exit 0 (`Resolved 17 packages`, `Checked 17 packages`, `Would make no changes`). |
| 2 | `01-01` | Only active Phase 1 entries exist under `src/ets2v2/` (`__init__.py`, `py.typed`, `cli.py`, plus `vfs`, `sii`, `baseline` in Waves 2-3), with zero deferred Phases 2-5 placeholder packages (`fetch`, `normalize`, `merge`, `validate`, `package`). | ✓ VERIFIED | Direct directory scan of `src/ets2v2/` returned exact set `['__init__.py', 'baseline', 'cli.py', 'py.typed', 'sii', 'vfs']`; `deferred_present: []`; `test_active_phase_only_package_layout` passed. |
| 3 | `01-01` | Running `ets2v2 --version` and `ets2v2 --help` executes cleanly with exit code 0. | ✓ VERIFIED | `uv run ets2v2 --version` printed `ets2v2 0.1.0` (exit 0); `uv run ets2v2 --help` printed CLI help (`vfs`, `baseline`) (exit 0); `test_cli_version` and `test_cli_help` passed. |
| 4 | `01-01` | All quality gates (`ruff check`, `ruff format --check`, `basedpyright` strict, `pytest`) pass locally and in `.github/workflows/ci.yml` on `ubuntu-latest`. | ✓ VERIFIED | `.github/workflows/ci.yml` runs all 4 gates on `ubuntu-latest` with `permissions: contents: read`, `timeout-minutes: 15`, `actions/checkout@v4`, and `astral-sh/setup-uv@v5`; local `ruff check --no-cache`, `ruff format --check --no-cache` (`31 files`), `basedpyright` (`0 errors, 0 warnings, 0 notes`), and `pytest` (`115 passed`) all exit 0. |
| 5 | `01-02` | Clean-room pure-Python `CityHash64` 1.0.3 (`k3=0xc949d7c7509e6557`, `b''->k2`) computes exact SCS HashFS path hashes across all length buckets (`0`, `<=16`, `17..32`, `33..64`, `>64`) and salts without C extensions or GPL code. | ✓ VERIFIED | `src/ets2v2/vfs/cityhash.py` implements 1.0.3 constants (`K0`–`K3`) and 64-bit masked arithmetic in pure Python + `struct`; 25 tests in `tests/test_vfs_cityhash.py` pass; live `def.scs` (`66,066` entries) and `locale.scs` (`521` entries) resolve via `hash_vfs_path()`. |
| 6 | `01-02` | `HashFsV1Archive`, `HashFsV2Archive` (zlib-compressed small entry/meta tables, bounds-checked skipping of non-`0x80`/`0x81` metadata kinds, deduplicated seeded walking for stripped-root archives like `locale.scs`), `ZipArchive`, and `DirectoryArchive` resolve canonical POSIX paths identically on Windows and Linux. | ✓ VERIFIED | Implemented in `src/ets2v2/vfs/{hashfs,zip_archive,dir_archive,types}.py` with decompression caps (`MAX_V2_TABLE_BYTES`, `MAX_ENTRY_DECOMPRESSED_BYTES`, `MAX_ZIP_ENTRY_BYTES`), consistent `list_paths(prefixes)` contracts, backwards metadata-ref preservation, NTFS junction pruning + `get_meta()` containment checks; `tests/test_vfs_archives.py` (`15 passed`) + live `def.scs`/`locale.scs`/`version.scs` pass. |
| 7 | `01-02` | Multi-layer `VfsStack` enforces priority-ordered overlay resolution, normalizes `base/` mount prefixes into canonical VFS paths, and preserves empty `SiiNunit {}` stub shadowing semantics. | ✓ VERIFIED | Implemented in `src/ets2v2/vfs/stack.py` (`classify_mount_path`, `is_empty_sii_stub`, `VfsStack.resolve/empty_stub_paths`, `MAX_STUB_INSPECT_BYTES = 1 MiB`, `three_nk` meta refresh); `dlc_<id>/` remains scoped under `"dlc:<id>"` unless enabled; 18 tests in `tests/test_vfs_stack.py` pass. |
| 8 | `01-02` | Protected and non-standard containers/payloads (`3nK\x01` payloads, `AEM!` headers, unknown archive magic, password-encrypted ZIP flag `0x1` with central-directory filename inspection, unsupported HashFS v2 compression nibbles) emit structured `ArchiveDiagnostic` records without decrypting or crashing. | ✓ VERIFIED | `detect_3nk()` inspects magic bytes only; `open_archive()` emits `ProtectedArchiveStub` (`aem_protected`, `unknown_magic`, `corrupt_archive`); `ZipArchive` inspects `flag_bits & 0x41` central-directory names with post-dedup diagnostics while raising `ProtectedPayloadError` on read; `HashFsV2Archive` records `unsupported_compression`/`unsupported_metadata` and raises `UnsupportedCompressionError`. Zero XOR/keytable/decryption code exists in `src/`. |
| 9 | `01-03` | `ets2v2 baseline extract` reads ETS2 `1.62.3.3s` `version.scs`, `def.scs`, and stripped-root `locale.scs` cleanly via `src/ets2v2/vfs/` and `src/ets2v2/sii/` without external executables. | ✓ VERIFIED | `src/ets2v2/baseline/extractor.py` uses `open_archive()`, `VfsStack`, `HashFsV2Archive.walk(["locale"])`, and `ets2v2.sii` parsers; verified directly via `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def --check` (exit 0). |
| 10 | `01-03` | Deterministic clean-room JSON schemas under `data/baselines/ets2_1.62_def/` capture all 36 countries, 36 speed limits, 461 fuel totem boards (373 `@@fp_*@@` + 88 placeholder/blank with `model_name == ''` and `items == 1`, excluding multi-item highway signs like `fi_oulu_95`), 43 active locales (excluding dead `fr_qc`), 12 `@@tz_*@@` keys (`key.startswith('tz_')`), and 99 `fp_*` keys (`key.startswith('fp_')`). | ✓ VERIFIED | Inspected all 5 JSON files directly: 36 countries (`iceland` 5-axle `[18000, 29000, 38000, 46000, 60000]`), 36 speed limits, 461 fuel boards (`373` `active_fp` + `88` `placeholder`/`blank`), `5` excluded highway signs (`fi_oulu_95`, `fi_oulu_98`, `rs_fuel_01`, `ru_m_95`, `ru_m_98`), 43 locales (`fr_qc` absent, `fr_ca` present), 12 `tz_*` keys, 99 `fp_*` keys, and 107 DLCs audited with matching SHA-256s in `manifest.json`. |
| 11 | `01-03` | Zero verbatim raw SCS `.sui`/`.sii` files are committed under `data/baselines/ets2_1.62_def/` (raw cache is strictly optional under gitignored `build/`). | ✓ VERIFIED | Recursive scan under `data/` returned `[]`; `extractor.py` anchors the `data/` rejection against `Path(__file__).resolve().parents[3] / "data"` independently of CWD; `cli.py` rejects overlapping `--raw-cache-dir` and `--out-dir`; `test_no_raw_scs_files_committed_under_data` and `test_raw_cache_dir_guard_cwd_independent_and_base_mount_boards_and_dlc_audit` passed. |
| 12 | `01-03` | Re-running extraction produces zero byte diff on all 5 committed JSON files, and all committed JSON schemas validate cleanly in CI without requiring local ETS2 archives. | ✓ VERIFIED | `ets2v2 baseline extract --check` passed against real `1.62.3.3s` archives; `uv run pytest -p no:cacheprovider -k "not local_ets2"` passed 113 CI-safe tests (`2 deselected`) in `0.59s`. |
| 13 | `01-04` | Shared structural SII/SUI lexer and span-preserving document engine handles both `SiiNunit { ... }` wrappers and headerless `.sui`/`.sii` fragments, inline `{` and next-line `{`, `#`, `//`, and `/* */` comments, column-0 `@include` directives, `attr[]` append arrays, and `attr: N` / `attr[i]` fixed arrays. | ✓ VERIFIED | Verified in `src/ets2v2/sii/{lexer,document}.py` (including unclosed `(` recovery, EOF unit span clamping, and shared-brace/fixed-array handling) and `tests/test_sii_{hygiene,document}.py` (`19 passed`). |
| 14 | `01-04` | Surgical editing of `country_data` and `country_speed_limit` updates only targeted scalar/array attributes (preserving inline comments, original `iso_country_code` quoting style such as `isl` vs `"bih"`, `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`, `tram`, and blank lines verbatim) and inserts absent attributes cleanly before the closing `}` or trailing `@include`. | ✓ VERIFIED | Verified in `src/ets2v2/sii/{document,country,speed_limits}.py`, `tests/test_sii_{document,country,speed_limits}.py` (`20 passed`, incl. fixed-array parsing/patching, newline/tab/quote escaping, duplicate scalar last-wins, and shared-brace speed-limit edits), and `@pytest.mark.local_ets2` live 36-country round-trips (`tests/test_baseline_contracts.py`). |
| 15 | `01-04` | Read-only `sign_board_template` (handling `&hex` IEEE754 floats, `nil`, `items: N` / `items[i]`) and `localization_db` (`key[]`/`val[]`) adapters cleanly feed Phase 1 baseline extraction. | ✓ VERIFIED | Verified in `src/ets2v2/sii/{sign_board,localization}.py`, `tests/test_sii_boards_locales.py` (`5 passed`), and live extraction across `12,942` `def/sign/board/*.sii` files and `43` locale databases. |
| 16 | `01-04` | Every serialized output enforces UTF-8 without BOM and `\n` (LF) line endings on pass 1, validates POSIX `/` internal paths, column-0 `@include` rules, and `[a-z0-9_]{1,12}` unit segments, and achieves zero byte diff on idempotent round-trip writes. | ✓ VERIFIED | Verified in `src/ets2v2/sii/hygiene.py`, `tests/test_sii_hygiene.py` (`10 passed`), and zero-diff pass-2+ checks across all 36 `1.62.3.3s` country and speed-limit pairs in `tests/test_baseline_contracts.py`. |

**Score:** 16/16 truths verified (0 behavior-unverified)

### Post-Review Fix Verification (`01-REVIEW.md` Closeout)

All actionable defects flagged in `01-REVIEW.md` were directly inspected in source and verified by new regression tests (`97` -> `115` total tests; `95` -> `113` CI-safe tests):

| Review ID | Scope & Fix Verified | Verification Evidence |
| --------- | -------------------- | --------------------- |
| `CR-01` | Bounded zlib table/payload decompression (`MAX_V2_TABLE_BYTES = 64 MiB`, `MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB` in `hashfs.py`), chunk-bounded ZIP streaming (`MAX_ZIP_ENTRY_BYTES = 128 MiB` in `zip_archive.py`), and `MAX_STUB_INSPECT_BYTES = 1 MiB` guard in `stack.py`. | `test_hashfs_v2_table_bomb_and_entry_decompression_caps`, `test_zip_archive_streaming_size_cap_and_multi_chunk_read`, `test_vfs_stack_skips_stub_inspection_above_max_stub_inspect_bytes` |
| `CR-02` | `_ordered_array_values()` prioritizes indexed `attr[i]` over scalar length `attr: N`, and `SiiDocument.replace_array_append()` removes/replaces fixed-array count + indexed spans cleanly. | `test_country_fixed_array_parse_and_patch_removes_stale_count_and_indices` |
| `CR-03` | `SiiDocument._attribute_removal_bounds()`, `_replace_attribute_line_with_lines()`, `insert_lines_after_attribute()`, `replace_array_append()`, and `speed_limits._replace_unit_lane_region()` preserve shared `{` and `}` on single-line / shared-brace units. | `test_document_single_line_and_shared_brace_mutations_preserve_braces`, `test_patch_speed_limits_single_line_and_shared_brace_units` |
| `CR-04` | `_format_sii_string()` rejects `\` / `\x00` and escapes `"`, `\r`, `\n`, `\t` in `time_zone_name`. | `test_patch_country_data_escapes_newlines_tabs_quotes_and_rejects_backslash_nul` |
| `WR-01` | `_scan_rhs_value()` tracks `paren_positions` with `_looks_like_next_statement()` recovery + `unbalanced_paren` diagnostic; `_close_open_unit()` clamps `span.end` to `len(text)`. | `test_scan_sii_structure_unclosed_paren_and_eof_unit_span_clamp` |
| `WR-02` | `SiiUnitBlock.get_scalar()` uses last-wins semantics matching `parse_country_data._scalar_raw()` and `SiiDocument.set_scalar()`. | `test_document_duplicate_scalar_last_wins`, `test_patch_country_data_duplicate_scalar_uses_last_wins` |
| `WR-03` | `DirectoryArchive` prunes escaping NTFS junctions (`_is_dir_junction`) during `os.walk` and re-verifies `_is_within_root()` in `get_meta()`. | `test_directory_archive_junction_pruning_and_get_meta_containment` |
| `WR-04` | Unified `filter_paths_by_prefixes()` contract (`prefixes=[]` -> `[]` across all `VfsArchive` readers) and added `not child_rec.is_dir` check for file entries in HashFS `_walk_with_parser()`. | `test_list_paths_empty_prefixes_consistent_across_all_archives`, `test_hashfs_walk_skips_dir_records_listed_as_files_and_backwards_meta_ref` |
| `WR-05` | `VfsStack._with_stub_status()` refreshes `meta` from `archive.get_meta()` after `read_bytes()` (and on cache hit) and drops unused `_seeded_prefixes`. | `test_vfs_stack_resolve_refreshes_three_nk_meta_on_first_call`, `test_vfs_stack_skips_stub_inspection_above_max_stub_inspect_bytes` |
| `WR-06` | `cli.py` catches `ProtectedPayloadError` and `UnsupportedCompressionError`; `extractor.py` anchors `data/` check via `Path(__file__).resolve().parents[3] / "data"` and reads boards via `def_stack.read_bytes()`. | `test_cli_baseline_extract_handles_protected_and_unsupported_archives`, `test_raw_cache_dir_guard_cwd_independent_and_base_mount_boards_and_dlc_audit` |
| `WR-07` | `.github/workflows/ci.yml` adds `timeout-minutes: 15`; `actions/checkout@v4` and `astral-sh/setup-uv@v5` remain pinned by major tag per `01-01-PLAN.md` and `tests/test_cli_scaffold.py`. | `test_ci_workflow_configuration` |
| `WR-08` | `_has_disallowed_backslash()` parses valid escapes (`\"`, `\\`, `\n`, `\r`, `\t`) without false-positiving on UI strings ending in asset extensions. | `test_validate_sii_hygiene_allows_valid_escapes_before_asset_ext_and_reports_col` |
| `WR-09` | Extracted shared helpers into `vfs/types.py` (`DiagnosticCollector`, `deduplicate_diagnostics`, `filter_paths_by_prefixes`, `decode_vfs_text`, `record_3nk_if_present`) and `sii/lexer.py` (`parse_sii_bool`, `split_sii_tuple`). | Verified directly in `src/ets2v2/vfs/types.py`, `src/ets2v2/sii/lexer.py`, and full passing suite |
| `WR-10` | `ZipArchive` checks `flag_bits & 0x41` (standard + strong encryption) and emits `encrypted_zip`/`unsupported_compression` diagnostics post-deduplication over `self._entries`. | `test_zip_archive_strong_encryption_0x40_and_duplicate_path_diagnostics` |
| `IN-02`–`IN-05` | `_audit_dlc_archives` checks `def`/`base/def` and `dlc_stem.removeprefix("dlc_")`; HashFS v2 preserves valid backwards metadata pointers and reports non-`0x80`/`0x81` as `unsupported_metadata`; `hygiene.py` reports exact column from `value_span.start` and checks `text.startswith("\ufeff")`; `VfsArchive` defines `__enter__`/`__exit__` and `extractor.py` uses `contextlib.closing`. | `test_raw_cache_dir_guard_cwd_independent_and_base_mount_boards_and_dlc_audit`, `test_hashfs_walk_skips_dir_records_listed_as_files_and_backwards_meta_ref`, `test_validate_sii_hygiene_allows_valid_escapes_before_asset_ext_and_reports_col` |

### Advisory (New Scope, Unevidenced)

None — all `01-REVIEW.md` Critical (`CR-01`..`CR-04`), Warning (`WR-01`..`WR-10`), and actionable Info (`IN-02`..`IN-05`) findings were verified fixed with deterministic tests. Note for record keeping only: `.github/workflows/ci.yml` retains `actions/checkout@v4` and `astral-sh/setup-uv@v5` tags to satisfy `01-01-PLAN.md` and `tests/test_cli_scaffold.py` (with `timeout-minutes: 15` added), and `IN-01` (function-length note) is non-blocking.

### Required Artifacts

| Artifact | Plan | Status | Verified Details |
| -------- | ---- | ------ | ---------------- |
| `pyproject.toml` | `01-01` | ✓ VERIFIED | PEP 621/639 `hatchling>=1.27,<2`, Python `>=3.12`, `license="MIT"`, `pydantic>=2.14,<3`, `ets2v2 = "ets2v2.cli:main"`, strict `basedpyright`, `ruff`, `pytest`. |
| `uv.lock` | `01-01` | ✓ VERIFIED | 17 resolved packages (`pydantic==2.14.3`, `basedpyright==1.40.2`, `pytest==9.2.0`, `pytest-cov==7.1.0`, `ruff==0.17.5`), zero GPL packages. |
| `.github/workflows/ci.yml` | `01-01` | ✓ VERIFIED | `ubuntu-latest`, `permissions: contents: read`, `timeout-minutes: 15`, `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `uv sync --locked`, `ruff check`, `ruff format --check`, `basedpyright`, `pytest`. |
| `src/ets2v2/__init__.py`, `py.typed`, `cli.py` | `01-01`, `01-03` | ✓ VERIFIED | Exports `__version__ = "0.1.0"`, PEP 561 marker, `build_parser`, `main`, `vfs inspect`, `baseline extract`. |
| `src/ets2v2/vfs/{__init__,cityhash,types,hashfs,zip_archive,dir_archive,stack}.py` | `01-02` | ✓ VERIFIED | All 7 modules present, substantive (no stubs), exported via `ets2v2.vfs.__all__`. |
| `src/ets2v2/sii/{__init__,hygiene,lexer,document,country,speed_limits,sign_board,localization}.py` | `01-04` | ✓ VERIFIED | All 8 modules present, substantive (no stubs), exported via `ets2v2.sii.__all__`. |
| `src/ets2v2/baseline/{__init__,models,extractor}.py` | `01-03` | ✓ VERIFIED | All 3 modules present, substantive (no stubs), exported via `ets2v2.baseline.__all__`. |
| `data/baselines/ets2_1.62_def/{manifest,countries,speed_limits,fuel_boards,locales}.json` | `01-03` | ✓ VERIFIED | All 5 deterministic clean-room JSON files present, SHA-256 verified, UTF-8 no-BOM LF. |
| `tests/test_{cli_scaffold,vfs_cityhash,vfs_archives,vfs_stack,sii_hygiene,sii_document,sii_country,sii_speed_limits,sii_boards_locales,baseline_extractor,baseline_contracts}.py` | `01-01`..`01-04` | ✓ VERIFIED | All 11 test modules present and passing (`113 passed` CI-safe; `115 passed` total incl. 2 `@pytest.mark.local_ets2`). |

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| `pyproject.toml` | `src/ets2v2/cli.py` | `ets2v2 = "ets2v2.cli:main"` console script | ✓ WIRED |
| `.github/workflows/ci.yml` | `pyproject.toml` | `uv sync --locked`, `ruff`, `basedpyright`, `pytest` steps | ✓ WIRED |
| `src/ets2v2/vfs/hashfs.py` | `src/ets2v2/vfs/cityhash.py` | `hash_vfs_path()` in HashFS v1/v2 lookup and walk | ✓ WIRED |
| `src/ets2v2/vfs/stack.py` | `src/ets2v2/vfs/hashfs.py` | `open_archive()` and `DEFAULT_SEEDED_PREFIXES` in `VfsStack` | ✓ WIRED |
| `src/ets2v2/vfs/zip_archive.py` | `src/ets2v2/vfs/types.py` | `ArchiveDiagnostic` and `ProtectedPayloadError` on encrypted ZIP `flag_bits & 0x41` | ✓ WIRED |
| `src/ets2v2/sii/document.py` | `src/ets2v2/sii/lexer.py` | `scan_sii_structure()` span indexing and re-scanning | ✓ WIRED |
| `src/ets2v2/sii/country.py` | `src/ets2v2/sii/document.py` | `SiiDocument` surgical scalar/array patching and serialization | ✓ WIRED |
| `src/ets2v2/sii/speed_limits.py` | `src/ets2v2/sii/document.py` | `SiiDocument` unit-scoped interleaved lane patching | ✓ WIRED |
| `src/ets2v2/baseline/extractor.py` | `src/ets2v2/vfs/hashfs.py` | `open_archive()` and `HashFsV2Archive.walk(["locale"])` | ✓ WIRED |
| `src/ets2v2/baseline/extractor.py` | `src/ets2v2/sii/country.py` | `parse_country_includes()` and `parse_country_data()` | ✓ WIRED |
| `src/ets2v2/baseline/extractor.py` | `src/ets2v2/sii/sign_board.py` | `parse_sign_board()` filtering `is_single_text_fuel_candidate` | ✓ WIRED |
| `src/ets2v2/cli.py` | `src/ets2v2/baseline/extractor.py` | `baseline extract` calling `extract_baseline`, `write_baseline_bundle`, `verify_baseline_bundle` | ✓ WIRED |

### Behavioral Spot-Checks & Fresh Re-Verification Runs

| Check | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| Lockfile / sync check | `uv lock --check --offline && uv sync --locked --offline --dry-run` | `Resolved 17 packages`, `Checked 17 packages`, `Would make no changes` (exit 0) | ✓ PASS |
| Ruff lint | `uv run ruff check --no-cache` | `All checks passed!` (exit 0) | ✓ PASS |
| Ruff format | `uv run ruff format --check --no-cache` | `31 files already formatted` (exit 0) | ✓ PASS |
| Type check (strict) | `uv run basedpyright` | `0 errors, 0 warnings, 0 notes` (exit 0) | ✓ PASS |
| CI-safe test suite | `uv run pytest -p no:cacheprovider -k "not local_ets2"` | `113 passed, 2 deselected in 0.59s` (exit 0) | ✓ PASS |
| Full local test suite | `uv run pytest -p no:cacheprovider` | `115 passed in 36.45s` (exit 0, incl. 2 `@pytest.mark.local_ets2` live tests) | ✓ PASS |
| Baseline zero-diff check | `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def --check` | `Baseline check passed (eut2 1.62.3.3): 36 countries, 36 speed limits, 461 fuel boards (373 active fp), 43 locales, 12 tz keys, 99 fp keys.` (exit 0) | ✓ PASS |
| CLI version & help | `uv run ets2v2 --version && uv run ets2v2 --help` | `ets2v2 0.1.0` and usage with `vfs`, `baseline` (exit 0) | ✓ PASS |
| Live VFS archive inspect | `uv run ets2v2 vfs inspect "D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\version.scs" --json && uv run ets2v2 vfs inspect "D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\def.scs" --prefix def/country --limit 10` | `version.scs` (`hashfs_v2`, 1 entry `version.sii`, 0 diagnostics); `def.scs` (`hashfs_v2`, 186 entries under `def/country`) (exit 0) | ✓ PASS |

### Hygiene, Anti-Pattern & Policy Audit

| Audit Check | Scope | Result | Status |
| ----------- | ----- | ------ | ------ |
| Stub / debt markers (`TBD`, `FIXME`, `XXX`, `TODO`, `HACK`) | `src/**/*.py` | Zero matches across all `src/` Python modules | ✓ PASS |
| Deferred placeholder packages (`fetch`, `normalize`, `merge`, `validate`, `package`) | `src/ets2v2/` | None present (`['__init__.py', 'baseline', 'cli.py', 'py.typed', 'sii', 'vfs']`) | ✓ PASS |
| Raw `.sii`/`.sui` leaks | `data/` | `[]` — zero `.sii` or `.sui` files under `data/` | ✓ PASS |
| UTF-8 no-BOM & LF (`\n`) endings | `src/`, `tests/`, `data/`, `.github/`, root configs + `.planning/` phase/root docs | All `42` workspace code/test/data/CI/root config files and `01-VERIFICATION.md` have `bom=False`, `crlf=False`, and valid UTF-8 (within `.planning/`, only pre-existing `.planning/research/ARCHITECTURE.md` has CRLF) | ✓ PASS |
| Dependency licensing | All 17 packages in `uv.lock` | `MIT`, `BSD-2-Clause`/`BSD`, `Apache-2.0`, `PSF-2.0` only — zero GPL/LGPL/AGPL dependencies | ✓ PASS |
| `3nK` decryption exclusion | `src/ets2v2/` | Only `detect_3nk()` (`b"3nK\x01"`) diagnostic reporting exists; zero XOR keytables or decryption logic | ✓ PASS |

### Closeout Bookkeeping Verification

- `.planning/ROADMAP.md`: Phase 1 marked `[x]`, all 4 plans (`01-01-PLAN.md`..`01-04-PLAN.md`) marked `[x]`, and Progress table records `4/4 | Complete | 2026-11-16`.
- `.planning/STATE.md`: Phase 1 marked `4 of 4 in current phase`, `Phase 1 complete (verified & reviewed; ready for Phase 2 planning)`, `115/115 tests passing`, Progress `[██████████] 100%`.
- `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-VALIDATION.md`: All 11 Wave 1–3 tasks (`01-01-01`..`01-04-03`) marked `passed`.
- *(Note: `.planning/REQUIREMENTS.md` traceability rows for `VFS-01`, `VFS-02`, `SII-01`, `SII-02` still show `[ ]` / `Pending` if the coordinator updates requirement checkboxes at milestone/phase closeout.)*

### Human Verification Required

None — all Phase 1 requirements (`VFS-01`, `VFS-02`, `SII-01`, `SII-02`) and Success Criteria (`1`–`4`) are deterministically verified by passing automated checks (`115/115` tests, `113/113` CI-safe) and live ETS2 `1.62.3.3s` archive verification.

### Gaps Summary

No codebase or Phase 1 closeout gaps found.

---

_Verified: 2026-11-16T19:03:00Z_
_Verifier: the agent (gsd-verifier)_
