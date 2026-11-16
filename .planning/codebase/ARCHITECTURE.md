<!-- refreshed: 2026-11-16 -->
# Architecture

**Analysis Date:** 2026-11-16

## System Overview

`ets2v2` (`ets2-world-realism`) is a clean-room Python `3.12+` toolkit and data/build pipeline for Euro Truck Simulator 2 (`1.62.3.3s`+). Phase 1 implements the read-only VFS layer, the span-preserving structural SII/SUI engine, the clean-room ETS2 `1.62` baseline extractor, and the `ets2v2` CLI entrypoint. Phases 2–5 will layer seasonal realism registries, live FX/fuel collectors, Zero-DDS fuel totems, Offline SCS Workshop validation, a local ProMods companion builder, and `ets2v2 compose-local` on top of this core.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLI Layer (`src/ets2v2/cli.py`)                 │
│     `ets2v2 vfs inspect`          │       `ets2v2 baseline extract`     │
└──────────────────┬────────────────┴───────────────────┬─────────────────┘
                   │                                    │
                   │                                    ▼
                   │               ┌──────────────────────────────────────┐
                   │               │  Baseline Pipeline (`baseline/`)     │
                   │               │  `extract_baseline()`                │
                   │               │  `write_baseline_bundle()`           │
                   │               │  `verify_baseline_bundle()`          │
                   │               └────────┬────────────────────┬────────┘
                   │                        │                    │
                   ▼                        ▼                    ▼
┌─────────────────────────────────────────────┐  ┌────────────────────────┐
│         VFS Subsystem (`vfs/`)              │  │  SII Engine (`sii/`)   │
│  `VfsStack` overlay + `base/`/`dlc_` rules  │  │  `lexer` -> `hygiene`  │
│  `open_archive()` -> `HashFsV1Archive`,     │  │  -> `SiiDocument`      │
│  `HashFsV2Archive`, `ZipArchive`,           │  │  -> `country`,         │
│  `DirectoryArchive`, `ProtectedArchiveStub` │  │  `speed_limits`,       │
│  Pure-Python MIT `CityHash64` 1.0.3         │  │  `sign_board`,         │
│                                             │  │  `localization`        │
└──────────────────┬──────────────────────────┘  └───────────┬────────────┘
                   │                                         │
                   ▼                                         ▼
┌─────────────────────────────────────────────┐  ┌────────────────────────┐
│   ETS2 Game Archives / User Mod Trees       │  │ Clean-Room Baseline    │
│   `version.scs`, `def.scs`, `locale.scs`,   │  │ JSON Store             │
│   `dlc_*.scs`, `.zip`/`.scs`, unpacked dirs │  │ `data/baselines/.../`  │
└─────────────────────────────────────────────┘  └────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Package Root | Exposes `__version__` (`0.1.0`) and PEP 561 typing marker | `src/ets2v2/__init__.py`, `src/ets2v2/py.typed` |
| CLI Entrypoint | Parses subcommands (`vfs inspect`, `baseline extract`), checks path args, catches VFS/baseline errors, prints text/JSON | `src/ets2v2/cli.py` |
| VFS Contracts & Helpers | Defines `VfsArchive` protocol, `ArchiveDiagnostic`, `VfsEntryMeta`, `normalize_vfs_path()`, `DiagnosticCollector`, `detect_3nk()`, and typed exceptions | `src/ets2v2/vfs/types.py` |
| HashFS Path Hasher | Computes Google `CityHash64` 1.0.3 digests and salted VFS path hashes in pure Python | `src/ets2v2/vfs/cityhash.py` |
| HashFS Container Readers | Implements `HashFsV1Archive`, `HashFsV2Archive`, `ProtectedArchiveStub`, bounded zlib decompression, and `open_archive()` magic dispatch | `src/ets2v2/vfs/hashfs.py` |
| ZIP Container Reader | Reads standard `.zip`/`.scs` containers, inspects encrypted (`flag_bits & 0x41`) central-directory headers, streams bounded reads | `src/ets2v2/vfs/zip_archive.py` |
| Directory Reader | Reads unpacked mod trees with root containment (`Path.resolve().is_relative_to()`) and symlink/NTFS-junction pruning | `src/ets2v2/vfs/dir_archive.py` |
| Multi-Layer VFS Overlay | Resolves priority-ordered `VfsStack` layers, normalizes `base/`, scopes `dlc_<id>/`, detects empty `SiiNunit {}` stubs, deduplicates diagnostics | `src/ets2v2/vfs/stack.py` |
| Structural SII Scanner | Performs single-pass $O(n)$ string- and comment-aware scanning into spans (`SiiUnitBlock`, `SiiAttributeSpan`, `SiiIncludeSpan`) and `&hex` float parsing | `src/ets2v2/sii/lexer.py` |
| SCS SII Hygiene | Normalizes UTF-8 no-BOM + LF bytes and validates `@include` col-0 placement, POSIX `/` paths, brace balance, and `[a-z0-9_]{1,12}` unit segments | `src/ets2v2/sii/hygiene.py` |
| Surgical SII Editor | Provides span-preserving `SiiDocument` mutations (`set_scalar`, `replace_array_append`, `insert_lines`, `_apply_reverse_edits`) with immediate re-scan | `src/ets2v2/sii/document.py` |
| Country SII/SUI Adapter | Parses `@include` lists and `country_data` blocks into `CountryDataModel`; applies surgical `CountryDataPatch` edits | `src/ets2v2/sii/country.py` |
| Speed Limits Adapter | Groups interleaved `lane_speed_class[]` blocks into `SpeedLimitsFile` and patches targeted `car`/`truck`/`bus` classes without altering `train`/`tram` | `src/ets2v2/sii/speed_limits.py` |
| Sign Board Parser | Parses `sign_board_template` + linked `sign_template_text` child slots (`parse_sign_board`) for fuel totem classification | `src/ets2v2/sii/sign_board.py` |
| Localization DB Parser | Parses `localization_db` units and headerless `.sui` `key[]`/`val[]` pairs into `LocalizationEntry` lists | `src/ets2v2/sii/localization.py` |
| Baseline Schemas | Defines frozen Pydantic v2 schemas (`BaselineBundle`, `BaselineManifest`, `BaselineCountry`, `BaselineSpeedLimit`, `FuelBoardsBaseline`, `LocalesBaseline`) | `src/ets2v2/baseline/models.py` |
| Baseline Pipeline | Extracts deterministic clean-room metadata from ETS2 `version.scs`, `def.scs`, `locale.scs`, and `dlc_*.scs`; writes and SHA-256-verifies JSONs | `src/ets2v2/baseline/extractor.py` |

## Pattern Overview

**Overall:** Acyclic layered toolkit (`cli` -> `baseline` -> `vfs` | `sii`) built around immutable Pydantic/dataclass value models, read-only container adapters, and span-indexed surgical text rewriting.

**Key Characteristics:**
- **Strict subsystem decoupling:** `ets2v2.vfs` and `ets2v2.sii` share zero imports with each other (`src/ets2v2/vfs/stack.py` keeps its own minimal `_strip_sii_comments()` helper for `is_empty_sii_stub()` rather than importing `ets2v2.sii.lexer`). Only `ets2v2.baseline` and `ets2v2.cli` compose them.
- **Span-preserving editing over AST serialization:** `SiiDocument` never deserializes an entire `.sii`/`.sui` file into a lossy dict and re-prints it. Instead, `scan_sii_structure()` records half-open `SiiSpan` ranges (`[start, end)`), and edits splice only targeted value spans or insertion points before immediately re-scanning.
- **Detect-and-report container safety:** Protected, obfuscated, or malformed containers (`3nK\x01`, `AEM!`, password-encrypted ZIPs, unknown magic, unsupported HashFS v2 compression/metadata) emit structured `ArchiveDiagnostic` records and raise typed errors on payload reads without decryption or keytables.
- **Deterministic canonical persistence:** `write_baseline_bundle()` serializes Pydantic models with `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`, omitting timestamps and recording SHA-256 digests in `data/baselines/ets2_1.62_def/manifest.json`.

## Layers

### Layer 1: CLI Entrypoint (`ets2v2.cli`)
- **Purpose:** Expose subcommands (`vfs inspect`, `baseline extract`), validate filesystem arguments, map internal exceptions to stderr messages and POSIX exit codes, and format text or JSON output.
- **Location:** `src/ets2v2/cli.py`
- **Contains:** `argparse` parser builder (`build_parser()`), command dispatch (`main()`), and subcommand handlers (`_handle_vfs_inspect()`, `_handle_baseline_extract()`).
- **Depends on:** `ets2v2.__version__`, `ets2v2.baseline`, `ets2v2.vfs` (`VfsStack`, `DEFAULT_SEEDED_PREFIXES`, `ProtectedPayloadError`, `UnsupportedCompressionError`).
- **Used by:** End users and CI via console script `ets2v2 = "ets2v2.cli:main"` (`pyproject.toml`).

### Layer 2: Domain Pipeline (`ets2v2.baseline`)
- **Purpose:** Coordinate VFS reading and SII parsing to extract, serialize, and byte-verify clean-room ETS2 `1.62.3.3s` baseline metadata.
- **Location:** `src/ets2v2/baseline/` (`__init__.py`, `models.py`, `extractor.py`)
- **Contains:** Frozen Pydantic v2 baseline schemas (`BaselineBundle`, `BaselineManifest`, etc.) and deterministic extraction/verification pipeline (`extract_baseline()`, `write_baseline_bundle()`, `verify_baseline_bundle()`).
- **Depends on:** `ets2v2.vfs` (`open_archive`, `VfsStack`, `VfsLayer`, `HashFsV2Archive`, `normalize_vfs_path`, `DEFAULT_SEEDED_PREFIXES`) and `ets2v2.sii` (`SiiDocument`, `parse_country_includes`, `parse_country_data`, `parse_speed_limits`, `parse_sign_board`, `parse_localization_db`, `VehicleSpeedLimitBlock`, `unquote_sii_string`).
- **Used by:** `src/ets2v2/cli.py`, contract tests (`tests/test_baseline_contracts.py`), and upcoming Phase 2–4 build/validation engines.

### Layer 3A: Virtual Filesystem (`ets2v2.vfs`)
- **Purpose:** Read HashFS v1 (`SCS#\x01`), HashFS v2 (`SCS#\x02`), ZIP/ZIP-wrapped `.scs`, and unpacked directory trees uniformly across Windows and Linux, simulating ETS2 overlay priority, `base/` flattening, `dlc_<id>/` scoping, and empty `SiiNunit {}` stub shadowing.
- **Location:** `src/ets2v2/vfs/` (`types.py`, `cityhash.py`, `dir_archive.py`, `zip_archive.py`, `hashfs.py`, `stack.py`, `__init__.py`)
- **Internal DAG:** `types.py` -> `cityhash.py` -> `dir_archive.py` / `zip_archive.py` -> `hashfs.py` -> `stack.py` -> `__init__.py`.
- **Depends on:** Python stdlib (`struct`, `zlib`, `zipfile`, `os`, `pathlib`, `collections`) and `pydantic`. Zero dependencies on `sii` or `baseline`.
- **Used by:** `src/ets2v2/cli.py`, `src/ets2v2/baseline/extractor.py`, and future Phase 4 `compose-local` load-order scanning.

### Layer 3B: Structural SII/SUI Engine (`ets2v2.sii`)
- **Purpose:** Lex, validate, parse, and surgically edit SCS `.sii` (`SiiNunit { ... }`) and `.sui` (headerless `@include` fragments) files while preserving comments, whitespace, indentation, quoting conventions, `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`, and `tram` blocks verbatim.
- **Location:** `src/ets2v2/sii/` (`lexer.py`, `hygiene.py`, `document.py`, `country.py`, `speed_limits.py`, `sign_board.py`, `localization.py`, `__init__.py`)
- **Internal DAG:** `lexer.py` -> `hygiene.py` -> `document.py` -> `{country.py, speed_limits.py, sign_board.py, localization.py}` -> `__init__.py`.
- **Depends on:** Python stdlib (`re`, `struct`, `bisect`, `dataclasses`, `math`) and `pydantic`. Zero dependencies on `vfs` or `baseline`.
- **Used by:** `src/ets2v2/baseline/extractor.py` and future Phase 2–4 country, speed-limit, totem, and manifest generators.

## Data Flow

### Flow 1: `ets2v2 vfs inspect`

1. `main()` (`src/ets2v2/cli.py:255`) parses `paths`, `--prefix`, `--limit`, `--json` and invokes `_handle_vfs_inspect()` (`src/ets2v2/cli.py:28`).
2. `_handle_vfs_inspect()` verifies every input path exists, then calls `VfsStack.from_paths(raw_paths, seeded_prefixes=seeds)` (`src/ets2v2/vfs/stack.py:185`).
3. `VfsStack.from_paths()` assigns increasing priority indices (`0..N-1`) and dispatches each path through `open_archive()` (`src/ets2v2/vfs/hashfs.py:707`), inspecting magic bytes to construct `DirectoryArchive`, `ZipArchive` (`PK`), `HashFsV1Archive` (`SCS#\x01`), `HashFsV2Archive` (`SCS#\x02`), or `ProtectedArchiveStub` (`AEM!`, unknown/truncated magic).
4. Inside `with stack:`, `stack.list_paths()` triggers `_ensure_index()` (`src/ets2v2/vfs/stack.py:240`), walking every archive, normalizing `base/` prefixes and `dlc_<id>/` mounts via `classify_mount_path()`, and computing a winning `EffectiveVfsEntry` per canonical POSIX path ordered by `(layer.priority, mount_seq, _intra_layer_rank(mount_scope))`.
5. `stack.diagnostics()` (`src/ets2v2/vfs/stack.py:345`) aggregates deduplicated `ArchiveDiagnostic` records across layers; `_handle_vfs_inspect()` prints either structured JSON or human-readable layer summaries, sample paths, and diagnostics.

### Flow 2: `ets2v2 baseline extract` (and `--check`)

1. `_handle_baseline_extract()` (`src/ets2v2/cli.py:95`) rejects overlapping `--raw-cache-dir` and `--out-dir` paths, then calls `extract_baseline(game_dir, raw_cache_dir=...)` (`src/ets2v2/baseline/extractor.py:198`).
2. `resolve_game_dir()` selects `game_dir` > `ETS2_GAME_DIR` > `DEFAULT_ETS2_GAME_DIR` (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`). `extract_baseline()` verifies `--raw-cache-dir` is outside `<repo>/data` (anchored via `Path(__file__).resolve().parents[3] / "data"`).
3. Opens `version.scs`, `def.scs`, and `locale.scs` using `_open_archive_ctx()` (`contextlib.closing(open_archive(...))`), using `seeded_prefixes=("locale",)` for stripped-root `locale.scs`.
4. Reads `version.sii` via `SiiDocument.parse()` to extract `game_version` (`1.62.3.3`) and `application` (`eut2`).
5. Wraps `def.scs` in a single-layer `VfsStack`, reads `def/country.sii`, parses `@include` paths via `parse_country_includes()`, and iterates all 36 countries—parsing `def/country/<slug>.sui` (`parse_country_data()`) and `def/country/<slug>/speed_limits.sii` (`parse_speed_limits()`).
6. Scans `def/sign/board/*.sii` (`12,942` boards total), filters fuel-board candidates via prefix/keyword/@@fp_ matching, parses each candidate with `parse_sign_board()`, selects single-text-slot boards with `model_name == ""` (`461` total: `373` `active_fp` + `88` `placeholder`/`blank`, excluding `5` multi-item highway signs), and records `FuelBoardEntry` models.
7. Walks `locale.scs` explicitly seeded at `"locale"`, discovers all `43` active `locale/<lang>/localization.sui` files, parses `tz_*` keys (`12`) via `parse_localization_db()`, and reads `locale/fuel_price_strings.sui` for `fp_*` keys (`99`).
8. Audits all `dlc_*.scs` files (`_audit_dlc_archives()`), computes deterministic SHA-256 digests over serialized `countries.json`, `speed_limits.json`, `fuel_boards.json`, and `locales.json`, and returns a frozen `BaselineBundle`.
9. With `--check`, `verify_baseline_bundle()` verifies zero `.sii`/`.sui` files in `out_dir`, UTF-8 no-BOM LF hygiene, byte-for-byte payload equality, and matching `manifest.json` SHA-256s. Otherwise `write_baseline_bundle()` writes all 5 JSON files to `data/baselines/ets2_1.62_def/`.

### Flow 3: Surgical SII/SUI Round-Trips

```text
raw bytes / str
   │
   ▼  normalize_sii_bytes() — strip leading UTF-8 BOM, normalize CRLF/CR -> LF
LF-normalized str
   │
   ▼  scan_sii_structure() — single-pass O(n) scan -> SiiScanResult (units, attrs, @includes)
SiiDocument
   ├──► patch_country_data(source, CountryDataPatch)
   │      ├─ scalars (`fuel_price`, `lights_mandatory`, `time_zone`, `time_zone_name`)
   │      │    -> SiiDocument.set_scalar() -> replace value_span in place OR insert before `}`/@include
   │      └─ `mass_limit_per_axle_count[]`
   │           -> SiiDocument.replace_array_append() -> reverse-sorted span edits (handles [] and attr: N / attr[i])
   │
   └──► patch_speed_limits(source, updates)
          ├─ unchanged lane_speed_class sequence -> _patch_unit_lanes_in_place() (preserves comments/blanks)
          └─ reordered/added lanes -> _replace_unit_lane_region() (rewrites targeted unit's lanes only; train/tram untouched)
   │
   ▼  SiiDocument.render() / serialize_sii_text() + validate_sii_hygiene()
UTF-8 no-BOM, LF bytes (pass 2+ produces zero byte diff)
```

## Key Abstractions

### `VfsArchive` (`src/ets2v2/vfs/types.py`)
- **Purpose:** Read-only contract unifying HashFS v1, HashFS v2, ZIP/ZIP-`.scs`, unpacked directories, and protected container stubs behind uniform existence, metadata, listing, and byte/text read methods.
- **Examples:** `HashFsV1Archive`, `HashFsV2Archive`, `ProtectedArchiveStub` (`src/ets2v2/vfs/hashfs.py`), `ZipArchive` (`src/ets2v2/vfs/zip_archive.py`), `DirectoryArchive` (`src/ets2v2/vfs/dir_archive.py`).
- **Pattern:** `@runtime_checkable Protocol` supporting optional `with open_archive(...)` context management (`__enter__`/`__exit__`) to keep file handles open across batched reads while defaulting to lazy per-read opening so Windows file locks are not held unnecessarily.

### `VfsStack` (`src/ets2v2/vfs/stack.py`)
- **Purpose:** Models ETS2's Mod Manager overlay precedence and mount-prefix rules (`base/` vs root vs `dlc_<id>/`), exposing winning `EffectiveVfsEntry` provenance (`layer_name`, `priority`, `mount_scope`, `raw_path`, `is_empty_stub`) and aggregated diagnostics.
- **Pattern:** Lazy invalidation index (`_dirty` flag + `_ensure_index()`), deterministic precedence tuple `(layer.priority, seq, _intra_layer_rank(mount_scope))` where `base/` ranks `0` and `root` ranks `1` within the same layer, and bounded stub inspection (`MAX_STUB_INSPECT_BYTES = 1 MiB`) checking `is_empty_sii_stub()` for combo suppression stubs (`SiiNunit { }`).

### `SiiDocument` (`src/ets2v2/sii/document.py`)
- **Purpose:** Span-preserving mutable editor over normalized SII/SUI text supporting both wrapped `SiiNunit { ... }` documents and headerless `.sui` fragments.
- **Pattern:** Immediate re-index-on-splice (`replace_span()`) paired with identity-checked unit lookup (`_resolve_unit()` matching `index` + `(class_name, unit_name)`) and `_apply_reverse_edits()` (descending offset order) so multi-attribute array edits never suffer stale byte/char offsets. Handles single-line and shared-brace blocks (`country_data : .empty { }`), trailing `@include` placement, duplicate scalars (last-wins matching SCS engine), and mixed `attr[]` / `attr: N`+`attr[i]` arrays.

### `BaselineBundle` (`src/ets2v2/baseline/models.py`)
- **Purpose:** Frozen Pydantic v2 snapshot bundling `BaselineManifest`, `CountriesBaseline`, `SpeedLimitsBaseline`, `FuelBoardsBaseline`, and `LocalesBaseline` as the clean-room contract between Phase 1 extraction and Phases 2–4 build/validation/merge pipelines.
- **Pattern:** Immutable value models (`ConfigDict(frozen=True)`) with deterministic sorted JSON output and per-file SHA-256 verification (`file_sha256s`).

## Entry Points

- **Console script (`ets2v2`):** Declared in `pyproject.toml` (`ets2v2 = "ets2v2.cli:main"`), implemented in `src/ets2v2/cli.py`. Dispatches `vfs inspect` and `baseline extract`.
- **Library facades:** Package `__all__` exports in `src/ets2v2/vfs/__init__.py`, `src/ets2v2/sii/__init__.py`, and `src/ets2v2/baseline/__init__.py`.
- **CI entrypoint:** `.github/workflows/ci.yml` running `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run basedpyright`, and `uv run pytest` on `ubuntu-latest`.

## Clean-Room & Licensing Boundaries

- **Permissive dependency tree:** `pyproject.toml` and `uv.lock` resolve 17 packages using permissive licenses (`MIT`, `BSD`, `Apache-2.0`, `PSF-2.0`) with zero GPL/LGPL/AGPL dependencies (`CityHash64` 1.0.3 in `src/ets2v2/vfs/cityhash.py` is implemented clean-room in pure Python).
- **Zero decryption / cracking logic:** `src/ets2v2/` contains zero XOR keytables, cipher routines, or `3nK`/`AEM!` decryptors. `detect_3nk()` inspects the 4-byte `b"3nK\x01"` header solely to emit `three_nk_obfuscated` diagnostics and raise `ProtectedPayloadError` on text decoding; `open_archive()` wraps `AEM!` headers in `ProtectedArchiveStub`; `ZipArchive` checks `flag_bits & 0x41` to inspect filenames and refuse decryption.
- **Raw SCS isolation (`data/` boundary):** `data/baselines/ets2_1.62_def/` stores only structured Pydantic JSON schemas. `extract_baseline()` rejects any `--raw-cache-dir` inside `<repo>/data` independently of working directory, `cli.py` rejects overlapping `--raw-cache-dir` / `--out-dir`, and `tests/test_baseline_contracts.py::test_no_raw_scs_files_committed_under_data` fails CI if any `.sii` or `.sui` file enters `data/`.
- **ProMods & external data IP boundaries (from `.planning/PROJECT.md` & `.planning/REQUIREMENTS.md`):** Zero proprietary ProMods `.scs`/def dumps in Git (Phase 4 builds locally from user-installed archives); zero `CC BY-NC-ND 3.0` (`GlobalPetrolPrices.com`) or `MyLPG.eu` scraping; zero `CC BY-SA` OSM data bundled into `CC BY 4.0` outputs; zero Pillow DDS texture baking (Option 4b Zero-DDS locale tokens only).
- **Active-phase layout guard:** `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` enforces that `src/ets2v2/` contains only active phase modules (`__init__.py`, `py.typed`, `cli.py`, `vfs`, `sii`, `baseline`) and rejects deferred Phase 2–5 placeholder directories (`fetch`, `normalize`, `merge`, `validate`, `package`) until each phase is formally introduced.

## Architectural Constraints

- **Threading / I/O:** Single-threaded synchronous I/O. Archives avoid holding OS file descriptors between calls unless explicitly opened with `with archive:` or `with VfsStack.from_paths(...):`, preventing Windows file-locking issues.
- **Memory & decompression bounds:** `HashFsV2Archive` caps entry/metadata table allocations at `MAX_V2_TABLE_BYTES = 64 MiB` and individual payloads at `MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB` via `_bounded_zlib_decompress()`; `ZipArchive` streams reads in `64 KiB` chunks capped at `MAX_ZIP_ENTRY_BYTES = 128 MiB`; `VfsStack` caps empty-stub inspection at `MAX_STUB_INSPECT_BYTES = 1 MiB`; `parse_sign_board()` resolves `items[i]` via dictionary lookup over parsed units rather than preallocating from `items: N`.
- **Cross-platform path canonicalization:** All VFS paths pass through `normalize_vfs_path()` (converting `\` to `/`, stripping empty/`.` segments, rejecting NUL bytes and `..`). `DirectoryArchive` verifies `Path.resolve().is_relative_to(root.resolve())` during tree walk (including NTFS junctions via `_is_dir_junction()`), `get_meta()`, and `read_bytes()`.
- **Strict static typing:** `pyproject.toml` configures `basedpyright` in `strict` mode (`pythonVersion = "3.12"`) across both `src/` and `tests/`, backed by `src/ets2v2/py.typed`.

## Anti-Patterns

### Naive Substring / Regex Mutation on SII Files

**What happens:** Replacing timezone tokens or attributes via regex/string search across raw `.sui` text (as seen in reference mod `3249064596`, which turned Estonia's `name: "Eesti"` into `"@@tz_eest@@i"`).
**Why it's wrong:** Corrupts unrelated string literals, comments, quoting style (`isl` vs `"bih"`), `regions[]`/`region_areas[]`, and `secondary_time_zone*`.
**Do this instead:** Parse via `SiiDocument.parse()` (`src/ets2v2/sii/document.py`) and mutate only verified attribute spans through `patch_country_data()` (`src/ets2v2/sii/country.py`) or `patch_speed_limits()` (`src/ets2v2/sii/speed_limits.py`).

### Assuming `.sui`-Only Paths or Stripping Un-Included Map Files

**What happens:** Assuming all country definitions live at `def/country/*.sui` or shipping global `def/country.ets2v2.sii` / `def/country.custom.sii` registration files in Core mods.
**Why it's wrong:** Map mods use `.sii` fragments (`SEA`, `RoC`, `Project Japan`), `base/` mount prefixes (`EAA`), and empty `SiiNunit { }` stubs (`UMCF`, `SemEuropa`); shipping competing `def/country*.sii` files causes `<ERROR> [unit] The unit name 'country.data.<x>' is already taken` or invokes deprecated `/custom/country.sii` loading (documented in `.agents/skills/scs-modding-wiki/docs/engine/units.md` and `.planning/research/ARCHITECTURE.md`).
**Do this instead:** Resolve active includes through `VfsStack` + `parse_country_includes()` (`src/ets2v2/sii/country.py`), respecting empty `SiiNunit { }` stub suppression (`VfsStack.empty_stub_paths()`), and keep Core mods strictly scoped to the `36` vanilla paths.

### Dropping Rail Blocks or Using Non-Column-0 `@include`

**What happens:** Rewriting an entire `speed_limits.sii` file without preserving `train`/`tram` units, indenting `@include`, or emitting `\` / `..` / `>12`-char unit tokens.
**Why it's wrong:** Breaks SCS engine parsing and fails SCS Workshop Uploader rules (`.agents/skills/scs-modding-wiki/docs/engine/units.md`, `src/ets2v2/sii/hygiene.py`).
**Do this instead:** Patch only `car`/`truck`/`bus` via `patch_speed_limits()` and validate every output with `validate_sii_hygiene()` and `serialize_sii_text()`.

## Error Handling

**Strategy:** Fail-loudly with typed domain exceptions when callers attempt unsupported or corrupt operations, while collecting non-fatal per-archive or per-file anomalies into immutable diagnostic models for inspection and reporting.

**Patterns:**
- **VFS diagnostics vs read exceptions:** Unreadable or protected containers (`AEM!`, truncated/corrupt headers, encrypted ZIP entries `flag_bits & 0x41`, unsupported HashFS v2 compression/metadata, traversal attempts) record `ArchiveDiagnostic` objects (`src/ets2v2/vfs/types.py`) during open/walk without crashing stack inspection. Calling `read_bytes()` or `read_text()` on protected or `3nK\x01` entries raises `ProtectedPayloadError`, and unsupported compression raises `UnsupportedCompressionError`.
- **SII hygiene & encoding errors:** `normalize_sii_bytes()` and `serialize_sii_text()` raise `SiiEncodingError` on invalid UTF-8 surrogates/bytes; `validate_sii_hygiene()` collects line- and column-indexed `SiiDiagnostic` items (`utf8_bom`, `non_lf_line_ending`, `include_not_column_0`, `path_backslash`, `path_parent_traversal`, `unit_segment_too_long`, `unbalanced_brace`, `unbalanced_paren`, etc.); `parse_country_includes()` converts blocking diagnostics into `ValueError`.
- **CLI exit codes:** `_handle_vfs_inspect()` and `_handle_baseline_extract()` catch `(FileNotFoundError, OSError, ValueError, ProtectedPayloadError, UnsupportedCompressionError)`, write concise messages to `sys.stderr`, and return exit code `1`; `--check` mismatches return `1` after printing every issue.

## Cross-Cutting Concerns

- **File Encoding & Line Endings:** Every source, test, config, CI, and generated JSON/SII/SUI file uses UTF-8 without BOM and LF (`\n`), reinforced by `.gitattributes` (`* text=auto eol=lf`), `serialize_sii_text()`, and `write_baseline_bundle()`.
- **SCS Unit & Path Hygiene:** `validate_sii_hygiene()` (`src/ets2v2/sii/hygiene.py`) acts as the single reusable hygiene gate across SII parsing, baseline extraction, and future Phase 2–4 Workshop validation.
- **CI-Safe vs Local Game Testing:** Tests requiring proprietary ETS2 `1.62.3.3s` archives are marked `@pytest.mark.local_ets2` with `skipif(not _has_local_ets2())` (`tests/test_baseline_contracts.py`), allowing `uv run pytest` (`113` CI-safe tests in `<1s` on `ubuntu-latest`) and full `115`-test local verification when `def.scs`/`locale.scs` are present.

---

*Architecture analysis: 2026-11-16*
