---
phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine
reviewed: 2026-11-16T19:05:01Z
depth: deep
files_reviewed: 38
files_reviewed_list:
  - .github/workflows/ci.yml
  - pyproject.toml
  - src/ets2v2/__init__.py
  - src/ets2v2/cli.py
  - src/ets2v2/baseline/__init__.py
  - src/ets2v2/baseline/extractor.py
  - src/ets2v2/baseline/models.py
  - src/ets2v2/sii/__init__.py
  - src/ets2v2/sii/country.py
  - src/ets2v2/sii/document.py
  - src/ets2v2/sii/hygiene.py
  - src/ets2v2/sii/lexer.py
  - src/ets2v2/sii/localization.py
  - src/ets2v2/sii/sign_board.py
  - src/ets2v2/sii/speed_limits.py
  - src/ets2v2/vfs/__init__.py
  - src/ets2v2/vfs/cityhash.py
  - src/ets2v2/vfs/dir_archive.py
  - src/ets2v2/vfs/hashfs.py
  - src/ets2v2/vfs/stack.py
  - src/ets2v2/vfs/types.py
  - src/ets2v2/vfs/zip_archive.py
  - tests/test_baseline_contracts.py
  - tests/test_baseline_extractor.py
  - tests/test_cli_scaffold.py
  - tests/test_sii_boards_locales.py
  - tests/test_sii_country.py
  - tests/test_sii_document.py
  - tests/test_sii_hygiene.py
  - tests/test_sii_speed_limits.py
  - tests/test_vfs_archives.py
  - tests/test_vfs_cityhash.py
  - tests/test_vfs_stack.py
  - data/baselines/ets2_1.62_def/countries.json
  - data/baselines/ets2_1.62_def/fuel_boards.json
  - data/baselines/ets2_1.62_def/locales.json
  - data/baselines/ets2_1.62_def/manifest.json
  - data/baselines/ets2_1.62_def/speed_limits.json
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: passed
---

# Phase 01: Code Review Report (Post-Fix Re-Review)

**Reviewed:** 2026-11-16T19:05:01Z (updated after `WR-11` fix)
**Depth:** deep
**Files Reviewed:** 38
**Status:** passed

## Summary

Deep post-fix re-review of Phase 1 (`01-vfs-1-62-baseline-extraction-structural-sii-engine`) across `src/ets2v2/`, `.github/workflows/ci.yml`, `pyproject.toml`, `tests/`, and `data/baselines/ets2_1.62_def/`, verifying every prior finding (`CR-01`..`CR-04`, `WR-01`..`WR-10`, `IN-01`..`IN-05`), inspecting all `git diff` changes, and auditing newly added code for regressions.

Note on reference docs: `~/.gemini/antigravity/gsd-core/references/necessity-review.md` and `~/.gemini/antigravity/gsd-core/references/cicd-review-patterns.md` remain unreadable due to sandbox path permission boundaries. Per review rules, `necessity:` is omitted from frontmatter, and CI/CD review fell back to the built-in pipeline checklist.

**Gate checks executed (read-only, post-fix):**
- `uv run ruff check --no-cache`: **PASS** (`All checks passed!`)
- `uv run ruff format --check --no-cache`: **PASS** (`31 files already formatted`)
- `uv run basedpyright`: **PASS** (`0 errors, 0 warnings, 0 notes`)
- `uv run pytest -p no:cacheprovider -k "not local_ets2"`: **PASS** (`113 passed, 2 deselected in 0.58s`)
- `uv run pytest -p no:cacheprovider -m local_ets2`: **PASS** (`2 passed, 113 deselected in 36.12s` — full 1.62.3.3s zero-diff baseline & 36-country surgical round-trip checks)

**Post-fix assessment:**
- **All 4 Critical blockers (`CR-01`..`CR-04`) are RESOLVED** and backed by dedicated regression tests: HashFS v2 table/entry caps (`64 MiB` / `128 MiB`), streaming ZIP decompression cap (`128 MiB`), `VfsStack` stub-inspection ceiling (`1 MiB`), fixed-array country parsing/replacement, single-line & shared-brace surgical edit boundaries, and control-character/newline escaping in `_format_sii_string`.
- **All 10 original Warnings (`WR-01`..`WR-06`, `WR-08`..`WR-10`, plus `WR-07` timeout + plan-scoped `@v4`/`@v5` waiver) and follow-up `WR-11` are RESOLVED** with regression tests verified across `tests/`.
- **4 of 5 Info findings (`IN-02`..`IN-05`) are RESOLVED; `IN-01` remains open (deferred)** as non-blocking complexity/function-length guidance.

## Narrative Findings (AI reviewer)

## Post-Fix Verification of Prior Findings

| ID | Original Finding | Post-Fix Status | Verification Evidence |
| --- | --- | --- | --- |
| `CR-01` | Unbounded decompression-bomb allocation in HashFS v1/v2, ZIP, and `VfsStack` | **RESOLVED** | `hashfs.py:31-32,50-67,145-182,418-443,481-504` (`MAX_V2_TABLE_BYTES`, `MAX_ENTRY_DECOMPRESSED_BYTES`, `_bounded_zlib_decompress`); `zip_archive.py:24-25,32-49,186-205` (`_read_zip_bounded`, `MAX_ZIP_ENTRY_BYTES`); `stack.py:25,275-299` (`MAX_STUB_INSPECT_BYTES`). Verified by `test_hashfs_v2_table_bomb_and_entry_decompression_caps`, `test_zip_archive_streaming_size_cap_and_multi_chunk_read` (`tests/test_vfs_archives.py:597-712`), and `test_vfs_stack_skips_stub_inspection_above_max_stub_inspect_bytes` (`tests/test_vfs_stack.py:288-318`). |
| `CR-02` | Fixed-array (`attr: N` + `attr[0..N-1]`) corrupts `parse_country_data` and leaves stale lines on patch | **RESOLVED** | `country.py:120-126` (`_ordered_array_values`); `document.py:297-404` (`replace_array_append` removes scalar count & `[0..N-1]` spans cleanly). Verified by `test_country_fixed_array_parse_and_patch_removes_stale_count_and_indices` (`tests/test_sii_country.py:229-269`) and `test_document_single_line_and_shared_brace_mutations_preserve_braces` (`tests/test_sii_document.py:261-280`). |
| `CR-03` | `replace_array_append`, `remove_attribute_line`, and empty-unit lane replacement corrupt braces on single-line blocks | **RESOLVED** (`WR-11` also resolved) | `document.py:138-167,180-286,335-404` (`_attribute_removal_bounds`, `_insert_lines_into_unit`, `same_line_close` handling); `speed_limits.py:180-248` (`_replace_unit_lane_region` delegates `not groups` to `doc.insert_lines` and guards `first_same_open`/`last_same_close`). Verified by `test_document_single_line_and_shared_brace_mutations_preserve_braces` (`tests/test_sii_document.py:233-280`) and `test_patch_speed_limits_single_line_and_shared_brace_units` (`tests/test_sii_speed_limits.py:228-269`). |
| `CR-04` | Newline / control-char injection via `_format_sii_string` | **RESOLVED** | `country.py:111-117` (`_format_sii_string` rejects `\` and `\x00` and escapes `"`, `\r`, `\n`, `\t`). Verified by `test_patch_country_data_escapes_newlines_tabs_quotes_and_rejects_backslash_nul` (`tests/test_sii_country.py:271-293`). |
| `WR-01` | Unclosed `(` in `_scan_rhs_value` swallows to EOF and produces out-of-range unit span | **RESOLVED** | `lexer.py:268-305,308-372,448` (`_looks_like_next_statement`, `unbalanced_paren` diagnostic, `min(close_brace_pos + 1, len(text))` span clamp). Verified by `test_scan_sii_structure_unclosed_paren_and_eof_unit_span_clamp` (`tests/test_sii_document.py:283-314`). |
| `WR-02` | Duplicate scalar precedence mismatch (`parse_country_data` last-wins vs `set_scalar` first-wins) | **RESOLVED** | `lexer.py:92-97` (`SiiUnitBlock.get_scalar` iterates `reversed(self.attributes)`). Verified by `test_document_duplicate_scalar_last_wins` (`tests/test_sii_document.py:316-323`) and `test_patch_country_data_duplicate_scalar_uses_last_wins` (`tests/test_sii_country.py:295-308`). |
| `WR-03` | `DirectoryArchive` misses Windows NTFS junctions in `os.walk`, and `get_meta()` skips re-containment check | **RESOLVED** | `dir_archive.py:21-24,70-99,129-145` (`_is_dir_junction`, escaping & cycle pruning via `visited_dirs`, `_is_within_root` re-check in `get_meta`). Verified by `test_directory_archive_junction_pruning_and_get_meta_containment` (`tests/test_vfs_archives.py:832-881`). |
| `WR-04` | Inconsistent `list_paths(prefixes=[])` contract and missing `not child_rec.is_dir` guard in HashFS walk | **RESOLVED** | `types.py:86-109` (`filter_paths_by_prefixes` returns `[]` for empty non-`None` sequence across `DirectoryArchive`/`ZipArchive`/`HashFs*`); `hashfs.py:228-229,303-309` (`and not child_rec.is_dir`). Verified by `test_list_paths_empty_prefixes_consistent_across_all_archives` and `test_hashfs_walk_skips_dir_records_listed_as_files_and_backwards_meta_ref` (`tests/test_vfs_archives.py:714-757,884-899`). |
| `WR-05` | `VfsStack.resolve()` does not refresh `meta.three_nk` and stores unused `_seeded_prefixes` | **RESOLVED** | `stack.py:164-175,275-299` (`del seeded_prefixes`, `_with_stub_status` refreshes `meta` via `entry.archive.get_meta`). Verified by `test_vfs_stack_resolve_refreshes_three_nk_meta_on_first_call` (`tests/test_vfs_stack.py:266-286`). |
| `WR-06` | CLI `baseline extract` misses `ProtectedPayloadError`/`UnsupportedCompressionError`, CWD-dependent `data/` guard, direct `def_arc.read_bytes` | **RESOLVED** | `cli.py:120-128` catches both exceptions; `extractor.py:216-220` anchors `data/` at `Path(__file__).resolve().parents[3] / "data"`; `extractor.py:315` reads boards via `def_stack.read_bytes(board_vfs)`. Verified by `tests/test_baseline_extractor.py:732-844`. |
| `WR-07` | CI workflow lacks `timeout-minutes` and uses mutable `@v4`/`@v5` tags | **RESOLVED (`timeout`) / WAIVED (`@v4`/`@v5`)** | `.github/workflows/ci.yml:16` adds `timeout-minutes: 15` (verified by `tests/test_cli_scaffold.py:150`). `actions/checkout@v4` and `astral-sh/setup-uv@v5` are intentionally retained under `permissions: contents: read` to satisfy `01-01-PLAN.md` `must_haves` (`contains: "astral-sh/setup-uv@v5"`) and `tests/test_cli_scaffold.py:151-152`. |
| `WR-08` | `_has_disallowed_backslash` false-positive on valid `\n`/`\t` UI strings ending in asset extensions | **RESOLVED** | `hygiene.py:118-145` validates escape sequences for non-path keys and restricts `_ASSET_EXT_RE` fallback to `key is None`. Verified by `test_validate_sii_hygiene_allows_valid_escapes_before_asset_ext_and_reports_col` (`tests/test_sii_hygiene.py:187-208`). |
| `WR-09` | Repeated utility logic across `vfs/` and `sii/` modules | **RESOLVED** | Shared helpers extracted to `vfs/types.py:86-191` (`matches_prefixes`, `filter_paths_by_prefixes`, `DiagnosticCollector`, `deduplicate_diagnostics`, `decode_vfs_text`, `record_3nk_if_present`) and `sii/lexer.py:134-153` (`parse_sii_bool`, `split_sii_tuple`). (`vfs/stack.py:29-83` `_strip_sii_comments` intentionally remains standalone so `vfs` has no import dependency on `sii`.) |
| `WR-10` | `ZipArchive` ignores strong-encryption bit `0x40` and retains stale diagnostics on duplicate normalized paths | **RESOLVED** | `zip_archive.py:28-29,125-140,157,169` (`_is_encrypted_zip_info` checks `0x41`; diagnostics emitted from deduplicated `self._entries`). Verified by `test_zip_archive_strong_encryption_0x40_and_duplicate_path_diagnostics` (`tests/test_vfs_archives.py:759-830`). |
| `IN-01` | Six core functions exceed 80–275 lines with high cyclomatic complexity | **OPEN (Deferred)** | Unchanged; remains a non-blocking maintainability suggestion (details below under `Info`). |
| `IN-02` | `_audit_dlc_archives` probes only `def/country.{dlc_stem}.sii` and `def/country/` | **RESOLVED** | `extractor.py:141-161` lists `["def", "base/def", "def/country", "base/def/country"]` and probes `dlc_stem.removeprefix("dlc_")`. Verified by `tests/test_baseline_extractor.py:786-844` and `local_ets2` zero-diff baseline verification. |
| `IN-03` | HashFS v2 `meta_cnt == 1` fallback overrides backwards metadata refs and misclassifies high flags | **RESOLVED** | `hashfs.py:553-607` restricts `meta_idx + 1` fallback to `payload_idx == 0 or payload_idx >= total_meta_words` and classifies non-`0x80`/`0x81` descriptors as `unsupported_metadata`. Verified by `tests/test_vfs_archives.py:900-976`. |
| `IN-04` | Attribute column hardcoded to `1` and mid-file ZWNBSP flagged as BOM in `hygiene.py` | **RESOLVED** | `hygiene.py:217-232,269` computes exact column via `_offset_to_line_col(..., attr.value_span.start)` and restricts `str` BOM check to `text.startswith("\ufeff")`. Verified by `tests/test_sii_hygiene.py:201-213`. |
| `IN-05` | Unreachable `else:` in `_open_archive_ctx` and unused `dir_path` param in `HashFsV1Archive._parse_dir_listing` | **RESOLVED** | `types.py:206-208` adds `__enter__`/`__exit__` to `VfsArchive`; `extractor.py:133-138` simplifies `_open_archive_ctx` to `contextlib.closing(...)`. `hashfs.py:390` intentionally retains `dir_path` parameter name to satisfy strict `basedpyright` override compatibility with `_BaseHashFsArchive._parse_dir_listing`. |

## Warnings

### WR-11: `_replace_attribute_line_with_lines` duplicates `unit.header_indent` when `same_close` anchor starts at line indent — **RESOLVED**

**File:** `src/ets2v2/sii/document.py:237-245`
**Resolution:** Fixed by slicing from `l_start` instead of `r_start` when `r_start <= kept_indent_end` (`tests/test_sii_document.py` indented shared-brace regression test added and passing).

## Info

### IN-01: Six core functions exceed 80–275 lines with high cyclomatic complexity

**File:** `src/ets2v2/sii/lexer.py:473-747`, `src/ets2v2/baseline/extractor.py:198-446`, `src/ets2v2/vfs/hashfs.py:223-311,445-607`, `src/ets2v2/sii/country.py:148-261`, `src/ets2v2/sii/hygiene.py:235-337`
**Issue:** `scan_sii_structure` (275 lines), `extract_baseline` (249 lines), `HashFsV2Archive._load_tables` (163 lines), `parse_country_data` (114 lines), `validate_sii_hygiene` (103 lines), and `_walk_with_parser` (89 lines) remain multi-responsibility functions.
**Fix:** Split into small single-purpose helpers (e.g., `_extract_countries_and_speeds`, `_discover_fuel_boards`, `_extract_locales` in `extractor.py`; `_parse_v2_entry_record` in `hashfs.py`).

---

_Reviewed: 2026-11-16T19:05:01Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
