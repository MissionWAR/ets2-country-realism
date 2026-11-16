# Codebase Concerns

**Analysis Date:** 2026-11-16

## Tech Debt

### `IN-01` Oversized Multi-Responsibility Core Functions (Deferred from Phase 1 Review)

**Issue:** Six core functions flagged in `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-REVIEW.md` (`IN-01`) exceed 80–275 lines and combine I/O, state transitions, validation, and assembly in single scopes:
- `scan_sii_structure` in `src/ets2v2/sii/lexer.py:473-747` (275 lines): mixes brace tracking, `@include` parsing, `SiiNunit` detection, identifier/array lexing, unit-header lookahead, attribute span creation, and EOF diagnostics.
- `extract_baseline` in `src/ets2v2/baseline/extractor.py:198-446` (249 lines): combines path/cache validation, `version.sii`, `def/country.sii`, 36 country/speed-limit parses, ~12.9k sign-board scans, `locale.scs` walking, DLC auditing, and manifest hashing.
- `HashFsV2Archive._load_tables` in `src/ets2v2/vfs/hashfs.py:445-607` (163 lines): combines binary header decoding, table size bounds checking, zlib decompression, metadata word unpacking, and multi-descriptor selection.
- `parse_country_data` in `src/ets2v2/sii/country.py:148-261` (114 lines): manually extracts and coerces all 20 known scalar, tuple, and array attributes inline.
- `validate_sii_hygiene` in `src/ets2v2/sii/hygiene.py:235-337` (103 lines): mixes BOM/UTF-8 decoding, line-ending checks, structural scan delegation, `@include` validation, unit naming checks, and attribute path checks.
- `_BaseHashFsArchive._walk_with_parser` in `src/ets2v2/vfs/hashfs.py:223-311` (89 lines): couples prefix/root/seeded fallback resolution, BFS directory traversal, unsafe entry rejection, and diagnostic path rewriting.
**Impact:** High cyclomatic complexity raises regression risk when Phase 2–4 extend the parser (`sign_board.py`/`localization.py` write modes, `profile.sii`/load-order scanning, or additional SII unit classes) and lowers unit-level testability of individual branches.
**Fix approach:** Extract focused single-purpose helpers before extending these modules — e.g., `_scan_statement` / `_open_or_emit_unit` in `src/ets2v2/sii/lexer.py`, `_extract_countries_and_speeds` / `_discover_fuel_boards` / `_extract_locales` in `src/ets2v2/baseline/extractor.py`, and `_parse_v2_entry_record` in `src/ets2v2/vfs/hashfs.py`.

### Mutable CI Action Tags (`WR-07` vs `01-01-PLAN.md` Constraint)

**Issue:** `.github/workflows/ci.yml:16` adds `timeout-minutes: 15` under `permissions: contents: read` (`ci.yml:10-11`), resolving the timeout half of `WR-07`. However, `.github/workflows/ci.yml:19,22` still pins `actions/checkout@v4` and `astral-sh/setup-uv@v5` by mutable major tag rather than immutable 40-character commit SHAs.
**Reason retained:** `01-01-PLAN.md` `must_haves.artifacts` (`.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-01-PLAN.md:54`) requires `contains: "astral-sh/setup-uv@v5"`, and `tests/test_cli_scaffold.py:151-152` fails CI if `"actions/checkout@v4"` or `"astral-sh/setup-uv@v5"` strings are replaced.
**Impact:** Mutable upstream tags remain a supply-chain drift risk once workflows gain release artifact permissions (Phase 2 Phase A) or credentials (deferred Phase B). Current Phase 1 exposure is mitigated by `permissions: contents: read`, zero CI secrets, and `uv sync --locked` against `uv.lock`.
**Fix approach:** Keep `.github/workflows/ci.yml` tag assertions only as long as `01-01` contract tests require them, and pin all actions and container images by immutable 40-char commit SHA / digest in new Phase 2+ release workflows (`.planning/research/PITFALLS.md:62,207`) or update `tests/test_cli_scaffold.py:151-152` together with `ci.yml` in Phase 2.

### Active-Phase Layout & Dependency Coupling in `tests/test_cli_scaffold.py`

**Issue:** `test_active_phase_only_package_layout()` (`tests/test_cli_scaffold.py:63-74`) and `test_pyproject_metadata_and_quality_gates()` (`tests/test_cli_scaffold.py:76-116`) hardcode the exact Phase 1 package allowlist (`{"__init__.py", "py.typed", "cli.py", "vfs", "sii", "baseline"}`), forbid `{"fetch", "normalize", "merge", "validate", "package"}`, and assert `dependencies == ["pydantic>=2.14,<3"]`.
**Impact:** Intentional Phase 2–5 additions (`tzdata`, `pillow`, `httpx`, `openpyxl`, and new subpackages) will fail `tests/test_cli_scaffold.py` until that test file is updated in lockstep.
**Fix approach:** Update `tests/test_cli_scaffold.py` at the start of each phase's Wave 1 plan to admit only that phase's newly activated subpackages and verified dependencies.

### Compatibility & Residual VFS/SII Ergonomics

**Issue:** Minor interface/implementation shortcuts exist in Phase 1 modules:
- `VfsStack.__init__` (`src/ets2v2/vfs/stack.py:164-171`) accepts `seeded_prefixes` only to delete it (`del seeded_prefixes`) because `VfsArchive` layers own their own seed prefixes.
- `ZipArchive._load_central_directory()` (`src/ets2v2/vfs/zip_archive.py:125`) silently overwrites `self._entries[norm] = info` when a ZIP central directory contains duplicate normalized paths instead of recording a diagnostic for duplicate entries.
- `src/ets2v2/sii/sign_board.py` and `src/ets2v2/sii/localization.py` are strictly read-only parsers; Phase 3 totem generation requires surgical emitters/writers that do not yet exist.
- `src/ets2v2/vfs/` is strictly read-only; Phase 2 (`universal.zip`) and Phase 4 (`zz_ETS2V2_ComboPatch_*.scs`) require a deterministic ZIP packager (normalized timestamps, zero `.scs`-named Workshop ZIPs).
**Fix approach:** Deprecate `seeded_prefixes` on `VfsStack.__init__` when refactoring Phase 4 `compose-local`, add optional duplicate-entry diagnostics in `ZipArchive`, and build dedicated Phase 2/3 write adapters rather than mutating read models.

## Known Bugs

All Critical (`CR-01`..`CR-04`) and Warning (`WR-01`..`WR-11`) defects identified in `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-REVIEW.md` and `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-VERIFICATION.md` are resolved and covered by regression tests (`115/115` passing locally; `113/113` passing in CI-safe mode). Two behavioral edge cases remain in current Phase 1 code:

### `SiiDocument.diagnostics` Masks Raw BOM/CRLF Hygiene Errors

- **Symptoms:** Constructing a `SiiDocument` from raw bytes or text containing a leading UTF-8 BOM (`\xef\xbb\xbf`) or `\r\n`/`\r` line endings and inspecting `doc.diagnostics` returns zero `utf8_bom` or `non_lf_line_ending` diagnostics.
- **Files:** `src/ets2v2/sii/document.py:44-50,72-74`
- **Trigger:** `SiiDocument.parse()` strips leading BOM and normalizes `\r\n`/`\r` to `\n` before storing `self._text`, and `doc.diagnostics` calls `validate_sii_hygiene(self._text)` on the already-normalized string.
- **Workaround:** Offline validators in Phase 2 (`PUB-01`) must pass raw unparsed file bytes directly to `validate_sii_hygiene(raw_bytes)` rather than relying on `SiiDocument.parse(raw_bytes).diagnostics`.

### `extract_baseline` Repo `data/` Guard Assumes Editable Source Layout

- **Symptoms:** The CWD-independent guard preventing `--raw-cache-dir` writes inside `data/` anchors on `Path(__file__).resolve().parents[3] / "data"` (`src/ets2v2/baseline/extractor.py:217`).
- **Files:** `src/ets2v2/baseline/extractor.py:215-219`, `src/ets2v2/cli.py:101-113`
- **Trigger:** If `ets2v2` is installed into `site-packages` as a non-editable wheel instead of running from the repo checkout (`uv run`), `parents[3]` resolves inside `site-packages` rather than the repository's `data/` directory.
- **Workaround:** `cli.py:101-113` separately blocks `--raw-cache-dir` overlapping `--out-dir`; keep repo CI/local runs editable via `uv run`, and resolve repo root via marker discovery (`pyproject.toml`) if non-editable distribution is ever supported.

## Security Considerations

### Protected & Obfuscated Containers (`3nK`, `AEM!`, Encrypted ZIPs, Unknown Compression)

- **Boundary:** Untrusted third-party `.scs`/`.zip` archives and mod trees read by `src/ets2v2/vfs/`.
- **Current mitigation:**
  - **`3nK\x01` payloads:** `detect_3nk()` (`src/ets2v2/vfs/types.py:33-35`) matches magic bytes only; `decode_vfs_text()` (`types.py:168-174`) raises `ProtectedPayloadError`; `record_3nk_if_present()` (`types.py:177-190`) emits `three_nk_obfuscated` diagnostics. Zero XOR keytables or decryption code exist in `src/ets2v2/`.
  - **`AEM!` & unknown archive magic:** `open_archive()` (`src/ets2v2/vfs/hashfs.py:736-796`) isolates `b"AEM!"`, `<4`-byte files, truncated `SCS#`, unsupported HashFS versions, and unrecognized headers behind `ProtectedArchiveStub`, raising `ProtectedPayloadError` on any `read_bytes()`/`read_text()` call.
  - **Encrypted ZIP entries:** `ZipArchive` (`src/ets2v2/vfs/zip_archive.py:28-30,127-140,169-175`) checks `flag_bits & 0x41` (both standard PKZIP `0x01` and strong encryption `0x40`), surfaces central-directory paths without decryption, emits post-dedup `encrypted_zip` diagnostics, and raises `ProtectedPayloadError` on `read_bytes()`.
  - **Compression whitelist:** Only `"none"` and `"zlib"` (`deflate`) are implemented (`src/ets2v2/vfs/hashfs.py:576-586`, `src/ets2v2/vfs/zip_archive.py:91-96`); other methods emit `unsupported_compression` and raise `UnsupportedCompressionError`.
- **Gap / nuance:** `three_nk` detection occurs lazily upon reading payload bytes (`read_bytes()` or `VfsStack._with_stub_status()` for `.sii`/`.sui` `<= 1 MiB` during `resolve()`). Files `> 1 MiB` or non-`.sii`/`.sui` entries do not populate `VfsEntryMeta.three_nk` via `get_meta()` alone until `read_bytes()` runs.

### Bounded Decompression & Memory Exhaustion Guards

- **Boundary:** Maliciously crafted HashFS v1/v2 headers, zlib bombs, spoofed ZIP `file_size` headers, or oversized `.sii`/`.sui` stubs.
- **Current mitigation:**
  - `HashFsV2Archive` caps entry and metadata tables at `MAX_V2_TABLE_BYTES = 64 MiB` (`64 * 1024 * 1024`, `src/ets2v2/vfs/hashfs.py:31,421-434,481-493`) and decodes zlib streams via `_bounded_zlib_decompress(..., expected_size + 1)` (`hashfs.py:50-67`).
  - Both `HashFsV1Archive`/`HashFsV2Archive` (`MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB`, `hashfs.py:32,145-181`) and `ZipArchive` (`MAX_ZIP_ENTRY_BYTES = 128 MiB`, chunked `_ZIP_READ_CHUNK_BYTES = 65536` streaming in `_read_zip_bounded`, `src/ets2v2/vfs/zip_archive.py:24-49`) bound per-entry allocations regardless of spoofed headers.
  - `VfsStack._with_stub_status()` (`src/ets2v2/vfs/stack.py:25,287`) enforces `MAX_STUB_INSPECT_BYTES = 1 MiB` before reading `.sii`/`.sui` payloads for `SiiNunit {}` stub checks.
  - `sign_board.py:128-146` looks up `items[i]` by unit name rather than preallocating from `items: N`, defeating untrusted count-based memory DoS.
- **Residual gap:** `DirectoryArchive.read_bytes()` (`src/ets2v2/vfs/dir_archive.py:173`) calls `resolved.read_bytes()` with no size cap. Calling `DirectoryArchive.read_bytes()` directly on large unpacked binary assets (`.pmg`/`.dds`) loads the entire file into RAM. Enforce an explicit `MAX_ENTRY_DECOMPRESSED_BYTES` guard in `DirectoryArchive.read_bytes()` before Phase 4 scans arbitrary user `mod/` trees.

### Path Traversal, Symlink & Windows NTFS Junction Guards

- **Boundary:** Archive entry paths, directory symlinks/junctions, and `--raw-cache-dir` file writes.
- **Current mitigation:**
  - `normalize_vfs_path()` (`src/ets2v2/vfs/types.py:63-83`) rejects `\x00` NUL bytes and `..` segments and canonicalizes `\` and `/` identically on Windows and Linux.
  - `HashFs*._walk_with_parser()` (`src/ets2v2/vfs/hashfs.py:238-257,274-302`) rejects unsafe directory names (`""`, `.`, `..`, `/`, `\`, `\x00`) with `path_traversal` diagnostics and deduplicates `visited_dir_hashes` + `visited_dir_paths` to break cyclic directory links.
  - `ZipArchive._load_central_directory()` (`src/ets2v2/vfs/zip_archive.py:113-121`) catches traversal errors and logs `path_traversal`.
  - `DirectoryArchive` (`src/ets2v2/vfs/dir_archive.py:21-24,60-124,134-141,164-171`) prunes escaping symlinks and Windows NTFS junctions (`_is_dir_junction`), detects junction cycles via `visited_dirs`, and re-verifies `_is_within_root()` on every `get_meta()` and `read_bytes()`.
  - `_write_raw_cache_entry()` (`src/ets2v2/baseline/extractor.py:103-111`) validates `resolved_dest.is_relative_to(resolved_root)` before creating parent directories or writing files.

### SII Injection & Hygiene Enforcement

- **Boundary:** Values written into `.sui`/`.sii` templates and downstream ETS2/Workshop output files.
- **Current mitigation:** `_format_sii_string()` (`src/ets2v2/sii/country.py:111-117`) rejects `\` and `\x00` and escapes `"`, `\r`, `\n`, `\t`. `validate_sii_hygiene()` (`src/ets2v2/sii/hygiene.py:235-337`) enforces strict UTF-8 (no `latin1` fallback), BOM-free header, LF line endings, column-0 `@include`, POSIX `/` paths without `..`, balanced braces, and `[a-z0-9_]{1,12}` unit segments.

### Raw `.sii`/`.sui` Copyright & License Provenance Boundaries

- **Boundary:** Proprietary ETS2 `def.scs`/`locale.scs` text, ProMods assets, and non-open third-party sources vs public MIT/`CC BY 4.0` repository.
- **Current mitigation:**
  - `data/baselines/ets2_1.62_def/` stores only clean-room Pydantic JSON schemas (`manifest.json`, `countries.json`, `speed_limits.json`, `fuel_boards.json`, `locales.json`).
  - `verify_baseline_bundle()` (`src/ets2v2/baseline/extractor.py:471-477`) and `test_no_raw_scs_files_committed_under_data` (`tests/test_baseline_contracts.py:83-89`) fail if any `.sii` or `.sui` exists under `data/`.
  - `uv.lock` contains 17 packages with `MIT`, `BSD`, `Apache-2.0`, and `PSF-2.0` licenses only (`01-VERIFICATION.md:145`), avoiding GPL (`TruckLib`/`Extractor`/`easy-scsmodmanager`).
- **Ongoing Phase 3–5 risks:** Future collectors must enforce hard rejections documented in `.planning/REQUIREMENTS.md:60-67` (`GlobalPetrolPrices.com` `CC BY-NC-ND 3.0`, `MyLPG.eu`, paid `IEA`, `3nK` cracking, ProMods `.scs`/`.sui` git commits, and any `CC BY-SA` OSM Overpass/Taginfo data leaking into `CC BY 4.0` snapshots or mods).

## Performance Bottlenecks

### Eager Full-Archive Indexing in `VfsStack._ensure_index()`

- **Problem:** First call to `VfsStack.resolve()`, `exists()`, or `list_paths()` triggers `_ensure_index()` (`src/ets2v2/vfs/stack.py:240-273`), which calls `layer.archive.list_paths()` (unfiltered `prefixes=None`) and `layer.archive.get_meta(raw_path)` across **every file in every mounted layer**.
- **Files:** `src/ets2v2/vfs/stack.py:240-273,318-322`
- **Cause:** `HashFs*` `list_paths(None)` performs a BFS walk hashing every directory and child entry in pure Python (`cityhash64` in `src/ets2v2/vfs/cityhash.py:139-192`). For ETS2 `def.scs` (`66,066` entries in `data/baselines/ets2_1.62_def/manifest.json:5`), walking and metadata-boxing tens of thousands of unrelated `.tobj`/`.mat`/`.pmd` entries dominates startup time. Notice `_audit_dlc_archives()` (`src/ets2v2/baseline/extractor.py:141-161`) originally took ~244s across 107 local `dlc_*.scs` archives until narrowed to `list_paths(["def", "base/def", "def/country", "base/def/country"])` (~0.94s, `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-03-SUMMARY.md:40`).
- **Improvement path:** Add optional `index_prefixes: Sequence[str] | None` to `VfsStack` (defaulting to `("def", "base/def", "locale", "base/locale")` or caller-supplied prefixes in `compose-local`) and skip `get_meta()` until an entry is actually queried, cutting Phase 4 load-order indexing across 86–503 mod archives by orders of magnitude.

### Full `12,942`-Board Decompression Scan in `extract_baseline`

- **Problem:** `extract_baseline()` (`src/ets2v2/baseline/extractor.py:304-317`) calls `def_stack.read_bytes(board_vfs)` on all `12,942` `def/sign/board/*.sii` entries inside `def.scs` to check `b"@@fp_" not in raw_board` even when `board_name` is not a fuel keyword.
- **Files:** `src/ets2v2/baseline/extractor.py:304-317`
- **Cause:** 19+ boards lacking `gas_` filename prefixes still contain `@@fp_*@@` tokens, requiring payload inspection during baseline refresh; `def_stack.read_bytes()` also runs `resolve()` + `is_empty_sii_stub()` (`stack.py:275-299`) on each board, making full `local_ets2` verification take `36.12s` (`01-REVIEW.md:71`).
- **Improvement path:** Acceptable for infrequent local baseline extraction (`data/baselines/ets2_1.62_def/fuel_boards.json` isolates CI from this cost), but Phase 2–4 build loops must consume `fuel_boards.json` rather than re-scanning `def.scs`.

### Repeated Full-Document Re-Scans During Chained SII Edits

- **Problem:** Every call to `SiiDocument.set_scalar()`, `update_attribute_value()`, `remove_attribute_line()`, or `insert_lines_after_attribute()` calls `replace_span()` -> `_refresh()` -> full `scan_sii_structure(self._text)` (`src/ets2v2/sii/document.py:112-136`). `_patch_unit_lanes_in_place()` (`src/ets2v2/sii/speed_limits.py:152-178`) mutates lane attributes one field at a time inside nested loops (`N lanes * 4 fields`), re-scanning the entire `speed_limits.sii` on every field.
- **Files:** `src/ets2v2/sii/document.py:112-136,249-258`, `src/ets2v2/sii/speed_limits.py:152-178`
- **Cause:** Sequential span mutations invalidate downstream offsets unless batched in reverse order (`_apply_reverse_edits`).
- **Improvement path:** Negligible on 1–5 KB `.sui`/`speed_limits.sii` files, but if Phase 3/4 generates or edits large `local_module.*.sii` files (hundreds of `key[]`/`val[]` entries), batch edits via `_apply_reverse_edits()` or emit sorted localization modules directly.

## Fragile Areas

### `VfsStack` Un-Normalized `dlc_<id>/` Scope vs User Mod Packs

- **Files:** `src/ets2v2/vfs/stack.py:100-123`
- **Why fragile:** `classify_mount_path()` strips `base/` unconditionally (`mount_scope="base"`) and scopes `dlc_<id>/` unless `enabled_dlcs` is explicitly passed (`VfsStack(..., enabled_dlcs=...)`). Notice `extract_baseline()` (`src/ets2v2/baseline/extractor.py:231`) creates `def_stack` over `def.scs` only without mounting `dlc_*.scs` into `def_stack` (DLCs are audited separately in `_audit_dlc_archives`), and `cli.py` `vfs inspect` does not yet expose an `--enable-dlc` flag. If future ETS2 `1.63+` DLCs ever ship `country_data` inside `dlc_<id>/def/country/`, callers must pass `enabled_dlcs` explicitly.
- **Safe modification:** Keep `enabled_dlcs` opt-in so non-DLC mods cannot accidentally spoof `dlc_*` flattening, and document `enabled_dlcs` requirement for Phase 4 combo resolution when inspecting DLC-scoped overrides.
- **Test coverage:** Tested in `tests/test_vfs_stack.py`, untested in `cli.py` (`vfs inspect`).

### `SiiDocument` Interleaved & Non-Contiguous Array Updates

- **Files:** `src/ets2v2/sii/document.py:298-405`, `src/ets2v2/sii/speed_limits.py:80-107,180-248`
- **Why fragile:** `replace_array_append()` rejects interleaved attributes (lines `319-326,378-382`) because `speed_limits.sii` interleaves `lane_speed_class[]`, `limit[]`, `urban_limit[]`, `max_limit[]`, and `uncommon[]` (`speed_limits.py` handles this separately via `_extract_lane_groups`). Additionally, `_extract_lane_groups()` rejects duplicate `limit[]`/`urban_limit[]`/`max_limit[]`/`uncommon[]` within one lane (`speed_limits.py:102-103`) and raises if a lane field precedes `lane_speed_class[]` (`98-101`). Malformed third-party map-mod `speed_limits.sii` files with trailing orphan lane attributes or comments placed mid-lane block could trigger `ValueError` during Phase 4 `compose-local` unless handled with per-file error reporting.
- **Safe modification:** Wrap `parse_speed_limits`/`patch_speed_limits` calls in `compose-local` with file-scoped diagnostics so one malformed third-party `speed_limits.sii` reports a clear diagnostic instead of aborting an entire 100-mod combo merge.
- **Test coverage:** Interleaved rejection errors in `document.py:323,380` and orphan/duplicate lane errors in `speed_limits.py:77,99,103` are currently uncovered by tests.

### `sign_board_template` Discovery Filter Coupling

- **Files:** `src/ets2v2/baseline/extractor.py:49-55,75-91,304-354`, `src/ets2v2/sii/sign_board.py:59-66`
- **Why fragile:** `extract_baseline` relies on `_FUEL_BOARD_PREFIXES` (`gas_`, `es_95_`, `es_diesel_`, `pt_95_`, `pt_diesel_`), `_is_fuel_keyword_name()`, `b"@@fp_" in raw_board`, and `is_single_text_fuel_candidate` (`model_name == ""`, `items_count == 1`, `child_types == ["sign_template_text"]`). Any future ETS2 patch introducing fuel boards with non-matching filenames and non-`@@fp_` placeholder text (e.g., `"0.00"` in a differently named board) will not be discovered automatically.
- **Safe modification:** Keep `excluded_fuel_keyword_boards` and `total_sign_boards` monitored in `manifest.json` whenever refreshing baselines against ETS2 `1.63+`.

### Unpacked `SiiNunit` Nested Units / Malformed Map-Mod Quirks

- **Files:** `src/ets2v2/sii/lexer.py:649-675`, `src/ets2v2/sii/hygiene.py:118-145`
- **Why fragile:** `scan_sii_structure` enters a unit block only when `active_unit is None` (`lexer.py:650`), assuming standard SCS non-nested unit definitions. Furthermore, `DEFAULT_ETS2_GAME_DIR = Path(r"D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2")` (`src/ets2v2/baseline/extractor.py:46`) hardcodes a single Windows path as the default fallback when `--game-dir` and `ETS2_GAME_DIR` are unset, which will always fail with `FileNotFoundError` on Linux or non-default Steam library drives unless explicitly configured.

## Scaling Limits

### Archive Count, Memory, and Format Ceilings

- **HashFS table & entry ceilings:**
  - `MAX_V2_TABLE_BYTES = 64 MiB` (`src/ets2v2/vfs/hashfs.py:31`): Assumes HashFS v2 `entry_table` (`entry_count * 16 B`, up to ~4.19M entries) and `metadata_table` (`metadata_count * 4 B`, up to ~16.7M words) fit within 64 MiB each and are loaded completely into `_records: dict[int, _HashFsRecord]`. ETS2 `1.62.3.3s` `def.scs` has `66,066` entries (~1 MB table), well within bounds, while massive multi-GB `base.scs` / map-asset archives could approach table/memory limits if opened whole.
  - `MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB` (`hashfs.py:32`) and `MAX_ZIP_ENTRY_BYTES = 128 MiB` (`src/ets2v2/vfs/zip_archive.py:24`): Single entries `> 128 MiB` raise `ValueError` / diagnostic `corrupt_archive`.
  - `MAX_STUB_INSPECT_BYTES = 1 MiB` (`src/ets2v2/vfs/stack.py:25`): `.sii`/`.sui` files `> 1 MiB` skip empty-stub detection (`is_empty_stub=False`) during `VfsStack.resolve()`.
- **Map-combo scale (`Phase 4` target):**
  - Local census verified `503` installed user mods (`86` touching `def/country*`, `speed_limits.sii`, or fuel boards, including `12` protected `AEM!`/`Bad magic`/encrypted ZIP archives; `.planning/research/ARCHITECTURE.md:41,54`). Current `VfsStack` eager full-tree indexing does not scale cleanly to scanning 503 full archives without prefix scoping.
- **Global coverage scale (`Phase 5` target):**
  - Baseline currently tracks `36` countries, `461` fuel boards (`373` `active_fp`, `88` placeholder/blank, `5` excluded highway signs), `43` locales, `12` `tz_*` keys, and `99` `fp_*` keys (`data/baselines/ets2_1.62_def/manifest.json`). Phase 5 scales snapshots to `200+` global countries/territories across Tier 1/2/3 pipelines (`.planning/ROADMAP.md:88-96`).
- **HashFS compression evolution (`ETS2 1.63+`):**
  - `HashFsV2Archive` handles compression nibbles `0` (stored) and `1` (zlib) only (`src/ets2v2/vfs/hashfs.py:576-586`). If SCS adopts Zstandard/GDeflate on `def.scs` or `locale.scs` in a future ETS2 update, `extract_baseline` will fail with `UnsupportedCompressionError` until extended.

## Dependencies at Risk

### Phase 1 Runtime & Dev Toolchain (`pyproject.toml`, `uv.lock`)

- **Current dependency footprint:** Minimal locked graph (`17` packages total in `uv.lock`, `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-VERIFICATION.md:97`): runtime `pydantic>=2.14,<3` (`2.14.3`), build backend `hatchling>=1.27,<2` (`1.33.0`), dev `basedpyright>=1.40,<2` (`1.40.2`), `pytest>=9.2,<9.3` (`9.2.0`), `pytest-cov>=6,<8` (`7.1.0`), `ruff>=0.16` (`0.17.5`).
- **Risk notes:**
  - `ruff` (`0.17.5`) checks markdown code snippets unless excluded (`extend-exclude = [".planning", ".agents"]` in `pyproject.toml:33`), which required an explicit exclusion for `.planning/research/ARCHITECTURE.md` (`01-01-SUMMARY.md:54`).
  - No GPL dependencies exist (`MIT`, `BSD`, `Apache-2.0`, `PSF-2.0` only).

### Planned External Dependencies & Upstream Data Feeds (Phases 2–5)

- **Windows `zoneinfo` dependency (`Phase 2`):** Python stdlib `zoneinfo` fails on Windows (`ZoneInfoNotFoundError`) without `tzdata` on PyPI (`.planning/research/SUMMARY.md:51`). `tzdata` is not yet in `pyproject.toml`.
- **Workshop Icon Validation (`Phase 2`):** `pillow>=12,<14` is needed exclusively for `276x162` JPEG validation/generation (`.planning/research/STACK.md:43,149`), strictly excluded from `.dds` texture generation.
- **Network APIs & Fragile Scrapers (`Phases 3 & 5`):**
  - `httpx` and `openpyxl` (and `beautifulsoup4`/`lxml` for Phase 5 Tier 2 portals) are not yet added to `pyproject.toml`.
  - EC Weekly Oil Bulletin uses Drupal dynamic XLSX links, `EL` instead of `GR` for Greece, and EUR/1,000 L units, and shifts around EU holidays (`.planning/research/PITFALLS.md:130`).
  - ECB `eurofxref-daily.xml` omits `RUB` and ~15–20+ non-Eurozone/CIS/MENA/Balkan currencies and freezes on weekends/TARGET2 holidays (`PITFALLS.md:116-119`).
  - Optional API keys required for full automated multi-grade/non-EU coverage: DE `Tankerkönig`, `US EIA v2`, `KR Opinet` (`.planning/STATE.md:53`).
  - Tier 2 national HTML portals (`anre.md`, `erc.org.mk`, `rosstat`, `dmre`, `epra`, etc.) risk HTTP `403`/`429`, `windows-1251`/Latin-1 charset issues, and selector drift, requiring `prices.lock.json` circuit-breakers (`ROADMAP.md:94`).
- **Missing Local SCS & Steam Tooling (`Phase 2` / `Phase B`):**
  - `SCS Workshop Uploader` (`AppID 421800`), `steamcmd`, `scs_extractor.exe`, and `scs_packer.exe` are not installed on the local workstation (`.planning/research/PITFALLS.md:12`). Phase A manual upload verification requires installing `AppID 421800` on Windows; full-auto SteamCMD (`PUB-V2-01`, `PUB-V2-02`) is deferred to V2 due to `config.vdf` token rot (`#56`), `GHSA-mj96-mh85-r574`, and `m00nl1ght-dev/steam-workshop-deploy` cross-edition `rsync` leaks (`.planning/research/PITFALLS.md:23-63`).

## Missing Critical Features (Phase 2–5 Integration Dependencies)

Phase 1 delivers the VFS, baseline extraction, and SII foundations (`VFS-01`, `VFS-02`, `SII-01`, `SII-02`) but intentionally omits all downstream compilation, validation, fetching, and packaging layers (`.planning/ROADMAP.md:38-102`):

1. **Phase 2 (`SIM-01`..`03`, `PUB-01`..`03`) — Realism Registry, Core Compiler, Offline SCS Validator & Phase A Release Gate:**
   - Depends on Phase 1 `data/baselines/ets2_1.62_def/*.json` and `src/ets2v2/sii/{country,speed_limits,hygiene,document}.py`.
   - Missing pieces: `data/laws/` & `data/mappings/` Pydantic registry, `zoneinfo` + `tzdata` seasonal DST engine respecting the 12 supported `@@tz_*@@` tokens (`locales.json`), read/write ZIP Workshop packager (`versions.sii`, `manifest.sii`, `276x162` `.jpg` icon, `mp_mod_optional: true`, no `display_name`/`compatible_versions[]`, no ZIP-as-`.scs`), Offline SCS Validator (`00001`–`00010` + `WARN 00001`/`00002`, raw-byte hygiene check), `state/published.json` SHA-256 no-op gate, and Friday `06:00 UTC` Phase A workflow.
2. **Phase 3 (`DAT-01`..`03`, `TOT-01`..`02`) — Multi-Provider FX/Fuel Pipeline & Zero-DDS Totem Writers:**
   - Depends on Phase 1 `data/baselines/ets2_1.62_def/fuel_boards.json` (`461` boards), `locales.json` (`43` locales), and Phase 2 core compiler/validator.
   - Missing pieces: `httpx` + `openpyxl` collectors (`Frankfurter v2`, `ECB`, `fawazahmed0`, `CBR`, `EC Weekly Oil Bulletin`, `UK DESNZ`, `NO SSB`, `FR`/`DE`/`ES`/`IT`/`NL`), `prices.lock.json` (`0.01–5.00 EUR/L`, `±25%` alerts), writable `sign_board_template` & `localization_db` emitters (`@@fp_*_ets2v2@@` + `locale/<lang>/local_module.ets2v2_fuel.sii` for all 43 locales), and repair of the 17 active unmapped + 69 placeholder/blank `1.62` signs.
3. **Phase 4 (`MAP-01`..`05`) — ProMods Companion & `ets2v2 compose-local`:**
   - Depends on Phase 1 `src/ets2v2/vfs/` (`VfsStack`, `base/`, empty `{}` stubs, `AEM!`/encrypted ZIP diagnostics), `src/ets2v2/sii/` surgical writers, and Phase 3 `realism-snapshot-{summer|winter}.json`.
   - Missing pieces: local ProMods archives (`promods-eu-def-v284.scs`, `promods-me-defmap-v284.scs`, `promods-ma-defmap-v104.scs`, `promods-tgs-defmap-v170.scs`), `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` emitters, active load-order parser (`profile.sii` / `game.log.txt`), `FieldOwnershipPolicy` (`max_of_map_and_real`, `patch_if_single_tz`), `--unpacked-defs` fallback for `12` local `AEM!`/encrypted mods, opt-in `--patch-hardcoded-totems` (JRR/7RM), and `VfsStack` prefix-scoped indexing.
4. **Phase 5 (`GLB-01`..`04`) — Global Tier 1/2/3 Expansion & OSM Drift Audit:**
   - Depends on Phase 3 snapshot/circuit-breaker architecture and Phase 4 global alias mappings (`200+` territories).
   - Missing pieces: non-EU Tier 1 collectors (`US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`), per-country Tier 2 scrapers, Tier 3 curated baselines, and CI-only OSM (`CC BY-SA`) drift audit with provenance isolation checks guaranteeing zero `CC BY-SA` contamination in `CC BY 4.0` artifacts.

## Test Coverage Gaps

Executing the CI-safe suite with coverage (`uv run --offline --no-sync pytest -p no:cacheprovider -k "not local_ets2" --cov=ets2v2 --cov-report=term-missing`) achieves **91% overall statement coverage (2,578 / 2,831 statements; 253 missed across 113 CI-safe tests)**, while the `2` `@pytest.mark.local_ets2` tests in `tests/test_baseline_contracts.py` skip automatically on CI runners lacking local ETS2 `1.62.3.3s` archives.

### Unenforced CI Coverage & Platform Gaps

- **No coverage gate in CI:** `.github/workflows/ci.yml:40` runs `uv run pytest` without `--cov` or `--cov-fail-under`, even though `pytest-cov` is a declared dev dependency (`pyproject.toml:22`).
- **Windows-only & live-archive test skips on CI:** NTFS junction pruning (`src/ets2v2/vfs/dir_archive.py:21-24,82-97`) and `@pytest.mark.local_ets2` tests (`tests/test_baseline_contracts.py:235-321`) only execute meaningfully on Windows hosts with local ETS2 `1.62.3.3s` archives.

### Module-Level Coverage Gaps (Verified via `pytest-cov`)

- **`src/ets2v2/vfs/dir_archive.py` — 78% (25 missed / 116 statements):**
  - Untested paths: missing/non-directory constructor errors (`34, 36`), broken/unreadable symlinks in `_is_within_root` (`63-64`), intra-archive NTFS junction cycle skipping (`94-97`), non-file/unsafe-path skips in `_scan_tree` (`106-113, 116-122`), and post-scan root-escape / missing-file checks in `get_meta` and `read_bytes` (`133, 144-145, 163, 166-171`).
  - Priority: **High** before Phase 4 `compose-local` traverses untrusted user `mod/` trees and `--unpacked-defs` directories.
- **`src/ets2v2/vfs/hashfs.py` — 86% (56 missed / 405 statements):**
  - Untested paths: truncated HashFS v1/v2 headers (`339-344, 450-455`), invalid magic/version/hash method (`351-357, 472-478`), table offset past EOF (`362-367, 499-504`), `_read_slice` bounds & zero-length reads (`123, 125`), uncompressed entry cap errors (`174-179`), `_decode_table` empty/raw-fallback/corrupt branches (`420, 422-427, 438-443, 522`), out-of-bounds metadata spans & truncated `0x80`/`0x81` blocks (`537-542, 560-565`), truncated v2 directory listings (`611-625, 632-637`), `ProtectedArchiveStub` context/validation branches (`661, 665, 669, 689-690, 704`), and `<6`-byte `SCS#` header stub (`755`).
  - Priority: **Medium-High** (corrupt-archive fault-injection coverage before scanning diverse community `.scs` mods in Phase 4).
- **`src/ets2v2/sii/lexer.py` — 86% (61 missed / 449 statements):**
  - Untested paths: malformed-input diagnostic paths (`unterminated_comment` `252-261, 393-402`, `unterminated_string` `228-229, 327-328, 544-545`, `malformed_include` `567-575`, `unexpected_token` `590-601`, `syntax_error` missing `:` `625-636`, stray `{`/`}` `unbalanced_brace` `499-508, 522-533`), `_looks_like_next_statement` comment skipping (`277-286, 291-304`), multi-line tuple `line_span` (`688-690`), and `parse_sii_bool`/`split_sii_tuple` error cases (`141, 148, 151`).
  - Priority: **Medium-High** (Phase 2 Offline SCS Validator and Phase 4 third-party mod parsing rely directly on these diagnostics).
- **`src/ets2v2/sii/document.py` — 87% (32 missed / 249 statements):**
  - Untested paths: `_resolve_unit` `KeyError` (`123`), `replace_span` invalid bounds (`128`), `insert_lines_after_attribute` on same-line `}` or no-trailing-newline EOF (`153-158, 165-166`), `_attribute_removal_bounds` without trailing newline (`215-217`), `same_open` / `same_open and same_close` in `_replace_attribute_line_with_lines` (`232-236`), empty `replace_array_append` on absent key or clearing fixed arrays (`310, 386-390`), and interleaved array `ValueError` guards (`323, 380`).
  - Priority: **Medium**.
- **`src/ets2v2/cli.py` (91%), `src/ets2v2/sii/hygiene.py` (94%), `src/ets2v2/baseline/extractor.py` (95%):**
  - Untested paths: `cli.py` non-JSON `vfs inspect` diagnostics/truncation output (`42-44, 86, 88-91`) and default help/exit fallback (`264, 272-273`); `hygiene.py` `invalid_utf8` raw-bytes diagnostic (`257-266`) and trailing backslash escape edge (`130, 133`); `extractor.py` `verify_baseline_bundle` failure branches (`467, 477, 485-486, 490, 492, 505-506`) and `_write_raw_cache_entry` root-escape check (`109`).
  - Priority: **Medium** (`verify_baseline_bundle` negative tests and `hygiene.py` `invalid_utf8` are directly relevant to Phase 2 validator verification).

---

*Concerns audit: 2026-11-16*
