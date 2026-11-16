# Coding Conventions

**Analysis Date:** 2026-11-16

## Naming Patterns

**Files & Packages:**
- Use lowercase `snake_case.py` module names under `src/ets2v2/` (`src/ets2v2/cli.py`, `src/ets2v2/vfs/dir_archive.py`, `src/ets2v2/sii/speed_limits.py`, `src/ets2v2/baseline/extractor.py`).
- Include the PEP 561 `src/ets2v2/py.typed` marker so downstream type checkers recognize package typing.
- Name test modules `tests/test_<subsystem>_<topic>.py` (`tests/test_vfs_cityhash.py`, `tests/test_sii_document.py`, `tests/test_baseline_contracts.py`).

**Functions & Methods:**
- Use `snake_case` verb-first names for public functions (`open_archive`, `normalize_vfs_path`, `parse_country_data`, `patch_speed_limits`, `extract_baseline`).
- Prefix module-private helpers and internal methods with a single leading underscore (`_bounded_zlib_decompress`, `_format_sii_string`, `_scan_rhs_value`, `_extract_lane_groups`, `_ensure_index`).

**Variables & Constants:**
- Use `snake_case` for local variables, dataclass attributes, and Pydantic model fields.
- Use `UPPER_SNAKE_CASE` for exported module constants (`DEFAULT_SEEDED_PREFIXES`, `MAX_V2_TABLE_BYTES`, `MAX_ENTRY_DECOMPRESSED_BYTES`, `MAX_ZIP_ENTRY_BYTES`, `MAX_STUB_INSPECT_BYTES`, `DEFAULT_ETS2_GAME_DIR`, `EXTRACTOR_SCHEMA_VERSION`).
- Prefix private constants and compiled regexes with an underscore (`_MASK64`, `_V1_HEADER_STRUCT`, `_IDENT_RE`, `_PATH_ATTR_KEYS`, `_FUEL_BOARD_PREFIXES`).

**Types, Classes & Aliases:**
- Use `PascalCase` for classes, protocols, Pydantic models, dataclasses, exceptions, and `Literal` type aliases (`VfsArchive`, `VfsStack`, `SiiDocument`, `CountryDataModel`, `BaselineManifest`, `DiagnosticKind`, `CompressionKind`, `BoardClassification`, `CommandHandler`).
- Prefix internal-only classes with an underscore (`_BaseHashFsArchive`, `_HashFsRecord`, `_OpenUnit`, `_LaneSpanGroup`).

**SCS Engine Token Naming:**
- Enforce `[a-z0-9_]{1,12}` on every dot-separated unit name segment (`validate_unit_name_segments` in `src/ets2v2/sii/hygiene.py`, derived from `.agents/skills/scs-modding-wiki/docs/engine/units.md`).
- Prefix file-scoped/anonymous units with `.` (e.g., `.speed_limit.car` in `src/ets2v2/sii/speed_limits.py`).

## Code Style

**Formatting (`ruff format`):**
- Enforced in `.github/workflows/ci.yml` (`uv run ruff format --check`) and `.planning/config.json` (`workflow.build_command`).
- Configure `line-length = 100` in `pyproject.toml` under `[tool.ruff]`, 4-space indentation, double quotes, and LF (`\n`) line endings.

**Linting (`ruff check`):**
- Configured in `pyproject.toml`:
  ```toml
  [tool.ruff]
  target-version = "py312"
  line-length = 100
  src = ["src", "tests"]
  extend-exclude = [".planning", ".agents"]

  [tool.ruff.lint]
  select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
  ```
- Maintain zero `# noqa` suppression comments across `src/` and `tests/`.

**Strict Static Typing (`basedpyright`):**
- Configured in `pyproject.toml` with `pythonVersion = "3.12"`, `typeCheckingMode = "strict"`, `include = ["src", "tests"]`, `venvPath = "."`, `venv = ".venv"`.
- Start every module (except minimal `src/ets2v2/__init__.py`) with `from __future__ import annotations`.
- Annotate every function and test signature explicitly, including `-> None` return types and `-> Self` on `__enter__` context methods (`src/ets2v2/vfs/types.py`).
- Accept `collections.abc` abstract interfaces (`Sequence`, `Iterable`, `Mapping`, `Callable`) for function inputs while returning concrete parameterized containers (`list[str]`, `dict[str, Path]`, `tuple[int, int]`).
- Narrow `Any` values from `struct.unpack_from`, `tomllib.loads`, `argparse.Namespace`, or JSON payloads via explicit `cast(...)` (`src/ets2v2/cli.py`, `src/ets2v2/vfs/hashfs.py`) or typed validation helpers (`_as_table`, `_as_str_list` in `tests/test_cli_scaffold.py`). Never use `# type: ignore` or `# pyright: ignore`.

## Data Models (Pydantic v2 vs Frozen Dataclasses)

**Use Frozen Pydantic v2 Models for Schemas & Domain DTOs:**
- Define JSON-serialized metadata, boundary diagnostics, and parsed ETS2 domain models as `pydantic.BaseModel` subclasses with `model_config = ConfigDict(frozen=True)` and `Field(default_factory=...)` for mutable defaults (`src/ets2v2/baseline/models.py`, `src/ets2v2/vfs/types.py`, `src/ets2v2/sii/country.py`, `src/ets2v2/sii/speed_limits.py`, `src/ets2v2/sii/sign_board.py`, `src/ets2v2/sii/localization.py`):
  ```python
  class CountryDataPatch(BaseModel):
      """Surgical overlay patch for realism-owned ``country_data`` fields."""

      model_config = ConfigDict(frozen=True)

      fuel_price: float | None = None
      mass_limit_per_axle_count: list[int] | None = None
  ```
- Perform immutable updates via `.model_copy(update=...)`, deserialize via `.model_validate_json(...)`, and serialize via `.model_dump(mode="json")` (`src/ets2v2/baseline/extractor.py`, `src/ets2v2/vfs/types.py`).

**Use Frozen Dataclasses for High-Volume Internal Value Objects:**
- Use `@dataclass(frozen=True)` or `@dataclass(frozen=True, slots=True)` for non-JSON structural records where allocation overhead matters: lexer spans (`SiiSpan`, `SiiUnitBlock`, `SiiAttributeSpan` in `src/ets2v2/sii/lexer.py`), hygiene diagnostics (`SiiDiagnostic` in `src/ets2v2/sii/hygiene.py`), HashFS records (`_HashFsRecord` in `src/ets2v2/vfs/hashfs.py`), and VFS stack entries (`VfsLayer`, `EffectiveVfsEntry` in `src/ets2v2/vfs/stack.py`, mutated via `dataclasses.replace(...)`).
- Restrict mutable `@dataclass` strictly to private, function-local accumulators (`_OpenUnit` in `src/ets2v2/sii/lexer.py`, `_LaneSpanGroup` in `src/ets2v2/sii/speed_limits.py`).

## Import Organization

**Order (enforced by Ruff `I`):**
1. `from __future__ import annotations`
2. Standard library imports (alphabetical)
3. Third-party imports (`pydantic`, `pytest`)
4. First-party `ets2v2.*` imports

**Import Rules:**
- Use absolute imports (`from ets2v2.vfs.types import normalize_vfs_path`) across all `src/` and `tests/` modules; avoid relative imports (`from .foo import bar`).
- Export public package APIs explicitly via `__all__` in `src/ets2v2/__init__.py`, `src/ets2v2/vfs/__init__.py`, `src/ets2v2/sii/__init__.py`, `src/ets2v2/baseline/__init__.py`, and `src/ets2v2/sii/document.py`.
- Use explicit re-export syntax (`from ets2v2.vfs.types import detect_3nk as detect_3nk` in `src/ets2v2/vfs/hashfs.py`) when re-exporting symbols under strict `basedpyright`.

## File Hygiene & SCS SII/SUI Rules

**Repository-Wide UTF-8 No-BOM & LF Hygiene:**
- `.gitattributes` enforces `* text=auto eol=lf` (`fixtures/** -text`; `*.scs`, `*.dds`, `*.jpg`, `*.png` marked `binary`).
- Commit all Python modules, tests, baseline JSONs, `.github/workflows/ci.yml`, and configs strictly as UTF-8 without BOM (`\xef\xbb\xbf`) and `\n` (LF) line endings. `tests/test_cli_scaffold.py` and `tests/test_baseline_contracts.py` fail CI if BOM or `\r` appears in `.github/workflows/ci.yml` or `data/baselines/ets2_1.62_def/*.json`.

**SII/SUI Runtime Normalization & Surgical Editing (`src/ets2v2/sii/`):**
- Normalize BOM (`\xef\xbb\xbf` / leading `\ufeff`) and `\r\n`/`\r` to LF on every read and write via `normalize_sii_bytes` and `serialize_sii_text` in `src/ets2v2/sii/hygiene.py`. Reject invalid UTF-8 bytes or lone surrogates by raising `SiiEncodingError`.
- Clean LF no-BOM files round-trip with zero byte diff on pass 1; BOM/CRLF inputs normalize on pass 1 and produce zero byte diff on pass 2+.
- Validate `@include` directives at column `0`, POSIX `/` separators (reject `\` and `..` in `@include` and `_PATH_ATTR_KEYS` while allowing valid `\"`, `\\`, `\n`, `\r`, `\t` escapes in UI text strings), balanced braces, and `[a-z0-9_]{1,12}` unit segments via `validate_sii_hygiene` (`src/ets2v2/sii/hygiene.py`).
- Edit `.sii`/`.sui` files exclusively through span-preserving splices in `SiiDocument` (`src/ets2v2/sii/document.py`), `patch_country_data` (`src/ets2v2/sii/country.py`), and `patch_speed_limits` (`src/ets2v2/sii/speed_limits.py`) — preserving comments (`#`, `//`, `/* */`), original `iso_country_code` quoting (`isl` vs `"bih"`), `regions[]`/`region_areas[]`, `secondary_time_zone*`, and `train`/`tram` blocks verbatim. Never apply global regex text replacement.
- Escape `"`, `\r`, `\n`, `\t` and reject `\` and `\x00` in `_format_sii_string` (`src/ets2v2/sii/country.py`).

**SCS Modding Wiki Reference Usage (`.agents/skills/scs-modding-wiki/`):**
- Consult `.agents/skills/scs-modding-wiki/SKILL.md` and `docs/` (`engine/units.md`, `engine/formats.md`, `engine/mod_manager.md`, `tools/scs_workshop_uploader/validation_errors_and_solutions_for_them.md`) before implementing SII unit parsers, `manifest.sii`/`versions.sii` emitters, or Workshop validators, and cite `index.json` source URLs when answering SCS engine/format questions.

## Error Handling

**Exception vs Diagnostic Split:**
- Raise typed domain exceptions (`ProtectedPayloadError`, `UnsupportedCompressionError`, `SiiEncodingError`) or standard exceptions (`FileNotFoundError`, `NotADirectoryError`, `IsADirectoryError`, `ValueError`, `KeyError`) when callers request missing paths, unsafe traversal (`..` / NUL bytes), malformed inputs, or payload reads on protected entries.
- Accumulate non-fatal inspection issues via `DiagnosticCollector` (`src/ets2v2/vfs/types.py`) emitting `ArchiveDiagnostic` (`three_nk_obfuscated`, `aem_protected`, `unknown_magic`, `encrypted_zip`, `unsupported_compression`, `unsupported_metadata`, `corrupt_archive`, `path_traversal`) and `ProtectedArchiveStub` (`src/ets2v2/vfs/hashfs.py`) without crashing archive enumeration.
- Return structural/hygiene issues from `scan_sii_structure` (`src/ets2v2/sii/lexer.py`) and `validate_sii_hygiene` (`src/ets2v2/sii/hygiene.py`) as immutable diagnostic lists rather than aborting scans mid-file.
- Catch operational errors at the CLI boundary (`src/ets2v2/cli.py`) to print `error: ...` to `sys.stderr` and return POSIX exit status `1`.

**Resource & Decompression Bounds:**
- Enforce hard size caps on untrusted archives (`MAX_V2_TABLE_BYTES = 64 MiB` and `MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB` in `src/ets2v2/vfs/hashfs.py`; `MAX_ZIP_ENTRY_BYTES = 128 MiB` in `src/ets2v2/vfs/zip_archive.py`; `MAX_STUB_INSPECT_BYTES = 1 MiB` in `src/ets2v2/vfs/stack.py`).

## Logging

- Do not import `logging` or call `print()` inside library modules (`src/ets2v2/{vfs,sii,baseline}/`); return structured models or diagnostic lists instead.
- Route all user-facing console summaries (`--json` or plain text) to `sys.stdout` and diagnostics/errors to `sys.stderr` exclusively in `src/ets2v2/cli.py`.

## Comments

- Write single-line `"""..."""` docstrings on modules, public classes, methods, and exported functions using double backticks (````symbol````) for code references.
- Add inline `#` comments only to explain non-obvious invariants, engine quirks, or security/DAG boundaries (e.g., `# Look ahead past trailing whitespace/comments to detect unit block '{'.` in `src/ets2v2/sii/lexer.py`, `# Retained for call-site compatibility; layers own their seeds.` in `src/ets2v2/vfs/stack.py`).

## Function Design

- Validate preconditions early and return immediately on empty inputs (`if not lines: return`).
- Use keyword-only parameters (`*`) for behavioral flags (`allow_empty`, `require_siinunit`, `seeded_prefixes`, `raw_cache_dir`, `enabled_dlcs`).
- Keep new functions concise and single-purpose; avoid growing existing long orchestrators noted in `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-REVIEW.md` (`IN-01`: `scan_sii_structure`, `extract_baseline`, `HashFsV2Archive._load_tables`, `parse_country_data`, `validate_sii_hygiene`, `_walk_with_parser`).

## Module Design & Acyclic Module DAG

**Strict Acyclic Dependency Hierarchy (`src/ets2v2/`):**
- Keep the package import graph strictly acyclic and maintain complete decoupling between `vfs` and `sii`:
  - **Layer 0 (Leaf Primitives):** `src/ets2v2/__init__.py`, `src/ets2v2/vfs/types.py`, `src/ets2v2/sii/lexer.py` (zero internal `ets2v2` imports).
  - **Layer 1 (Core Primitives):** `src/ets2v2/vfs/{cityhash,dir_archive,zip_archive}.py` -> `vfs.types`; `src/ets2v2/sii/hygiene.py` -> `sii.lexer`.
  - **Layer 2 (Containers & Document Engine):** `src/ets2v2/vfs/hashfs.py` -> `vfs.{cityhash,dir_archive,types,zip_archive}`; `src/ets2v2/vfs/stack.py` -> `vfs.{hashfs,types}` (`stack.py` implements `_strip_sii_comments` locally so `vfs` never imports `sii`); `src/ets2v2/sii/document.py` -> `sii.{hygiene,lexer}`.
  - **Layer 3 (Format Adapters):** `src/ets2v2/sii/{country,localization,sign_board,speed_limits}.py` -> `sii.{document,lexer}`.
  - **Layer 4 (Baseline Pipeline):** `src/ets2v2/baseline/models.py` -> `sii.speed_limits`; `src/ets2v2/baseline/extractor.py` -> `baseline.models`, `vfs`, `sii`.
  - **Layer 5 (CLI Orchestrator):** `src/ets2v2/cli.py` -> `ets2v2`, `ets2v2.baseline`, `ets2v2.vfs`.
- Scaffold only active-phase subpackages; never create empty placeholder directories for deferred phases (`fetch/`, `normalize/`, `merge/`, `validate/`, `package/`) until their phase begins (`test_active_phase_only_package_layout` in `tests/test_cli_scaffold.py`).
- Produce deterministic JSON via `json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"` with zero timestamps (`_serialize_model_bytes` in `src/ets2v2/baseline/extractor.py`).

## Clean-Room IP & License Compliance

- **Permissive MIT Provenance:** `pyproject.toml` declares `license = "MIT"`, and `uv.lock` contains only permissive dependencies (`MIT`, `BSD`, `Apache-2.0`, `PSF-2.0`). Never add GPL/LGPL/AGPL dependencies or port code from GPL SCS tools (`TruckLib`, `Extractor`, `easy-scsmodmanager`). `src/ets2v2/vfs/cityhash.py` implements Google CityHash64 1.0.3 (MIT) cleanly in pure Python.
- **Zero Decryption & Zero Raw Game Assets in Git:** Never implement `3nK\x01` XOR decryption or `AEM!` cracking — only detect headers (`detect_3nk`, `open_archive`, `ZipArchive`) and emit `ArchiveDiagnostic`. Never commit raw `.scs` archives, ProMods `def` dumps, or extracted `.sii`/`.sui` files under `data/` (`test_no_raw_scs_files_committed_under_data` in `tests/test_baseline_contracts.py` and the CWD-independent `repo_data_dir` guard in `src/ets2v2/baseline/extractor.py`). Dump optional raw files only to gitignored `build/`/`raw/` or explicit `--raw-cache-dir` outside `data/` and `--out-dir`.
- **Upstream Data Licensing (`.planning/PROJECT.md`):** Use only `CC BY 4.0`-compatible data sources for future collectors (`Frankfurter v2`, `ECB`, `fawazahmed0/exchange-api`, Tier 1 open government fuel APIs); exclude `CC BY-NC-ND` scrapers (`GlobalPetrolPrices.com`), `MyLPG.eu`, paid `IEA`, and redistributed `CC BY-SA` OSM Wiki data.

---

*Convention analysis: 2026-11-16*
