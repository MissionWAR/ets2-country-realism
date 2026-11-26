# Coding Conventions

**Analysis Date:** 2026-11-26

## Naming Patterns

**Files & Packages:**
- Use lowercase `snake_case.py` module names under `src/ets2_realism/` (`src/ets2_realism/cli.py`, `src/ets2_realism/vfs/dir_archive.py`, `src/ets2_realism/sii/speed_limits.py`, `src/ets2_realism/fetch/ec_bulletin.py`, `src/ets2_realism/merge/promods_builder.py`, `src/ets2_realism/audit/osm_speeds.py`).
- Prefix internal helper modules with a leading underscore when they are not part of a subpackage's public surface (`src/ets2_realism/fetch/_html.py`, `src/ets2_realism/fetch/_parsing.py`).
- Keep the PEP 561 `src/ets2_realism/py.typed` marker intact so downstream type checkers recognize package typing.
- Keep standalone regeneration wrappers minimal under `scripts/` (`scripts/generate_icons.py`).
- Name test modules `tests/test_<subsystem>_<topic>.py` (`tests/test_vfs_cityhash.py`, `tests/test_fetch_tier2_portals.py`, `tests/test_validate_workshop.py`, `tests/test_audit_osm_speeds.py`).

**Functions & Methods:**
- Use `snake_case` verb-first names for public functions (`open_archive`, `normalize_vfs_path`, `parse_country_data`, `patch_speed_limits`, `extract_baseline`, `load_law_registry`, `build_core_editions`, `validate_workshop_package`, `compose_local`, `run_phase_a_release`, `scan_repo_and_artifacts_for_taint`).
- Prefix module-private helpers, CLI handlers, and internal methods with a single leading underscore (`_bounded_zlib_decompress`, `_format_sii_string`, `_read_bounded_response`, `_scan_text_bytes`, `_handle_compose_local`).

**Variables & Constants:**
- Use `snake_case` for local variables, dataclass attributes, and Pydantic model fields.
- Annotate module constants with `typing.Final[...]` (`424` constants across `src/ets2_realism/`) and use `UPPER_SNAKE_CASE` for exported constants (`DEFAULT_SEEDED_PREFIXES`, `MAX_ENTRY_DECOMPRESSED_BYTES`, `ZIP_FIXED_TIMESTAMP`, `FORBIDDEN_LICENSE_TAINT_PATTERNS`, `DEFAULT_TIMEOUT_SECONDS`, `TIER1_STALE_DAYS`).
- Prefix private constants and compiled regexes with an underscore (`_MASK64`, `_V1_HEADER_STRUCT`, `_IDENT_RE`, `_SECRET_QUERY_RE`, `_XML_FORBIDDEN_DECL_RE`, `_SCANNABLE_TEXT_SUFFIXES`).

**Types, Classes & Aliases:**
- Use `PascalCase` for classes, protocols, Pydantic models, dataclasses, exceptions, and `Literal` type aliases (`VfsArchive`, `VfsStack`, `SiiDocument`, `CountryLawRecord`, `PricesLockfile`, `RealismSnapshot`, `ValidationReport`, `FieldOwnershipPolicy`, `Season`, `RoadVehicleClass`, `ValidationSeverity`, `PackageProfile`, `CommandHandler`).
- Prefix internal-only classes with an underscore (`_BaseHashFsArchive`, `_HashFsRecord`, `_OpenUnit`, `_LaneSpanGroup`, `_TableFrame`, `_FuelCandidate`, `_StagedEdition`).

**SCS Engine Token & Unit Naming:**
- Enforce `[a-z0-9_]{1,12}` on every dot-separated unit name segment (`validate_unit_name_segments` in `src/ets2_realism/sii/hygiene.py`, verified against `.agents/skills/scs-modding-wiki/docs/engine/units.md` and SCS Workshop error `00007` in `src/ets2_realism/validate/workshop.py`).
- Prefix file-scoped/anonymous units with `.` (e.g., `.speed_limit.car` in `src/ets2_realism/sii/speed_limits.py`).
- Name generated fuel-price localization tokens strictly `^fp_[a-z]{2}_[a-z0-9_]+_ets2r$` (`_TOTEM_TOKEN_KEY_RE` in `src/ets2_realism/validate/invariants.py`).

## Code Style

**Formatting (`ruff format`):**
- Enforced in `.github/workflows/ci.yml`, `.github/workflows/phase-a-release.yml`, and `.planning/config.json` (`workflow.build_command`: `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright`).
- Configure `line-length = 100` in `pyproject.toml` under `[tool.ruff]`, 4-space indentation, double quotes, and LF (`\n`) line endings.

**Linting (`ruff check`):**
- Configured in `pyproject.toml` (`ruff>=0.16`, locked `0.17.5`):
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
- Configured in `pyproject.toml` (`basedpyright>=1.40,<2`, locked `1.40.2`, with `types-openpyxl>=3.1`):
  ```toml
  [tool.basedpyright]
  pythonVersion = "3.12"
  typeCheckingMode = "strict"
  include = ["src", "tests"]
  venvPath = "."
  venv = ".venv"
  ```
- Start every module under `src/ets2_realism/` (except minimal `src/ets2_realism/__init__.py`) and `tests/` with `from __future__ import annotations`.
- Annotate every function, method, fixture, and test signature explicitly, including `-> None` return types and `-> Self` on context manager `__enter__` methods (`src/ets2_realism/vfs/types.py`).
- Accept `collections.abc` abstract interfaces (`Sequence`, `Iterable`, `Mapping`, `Callable`) for function inputs while returning concrete parameterized containers (`list[str]`, `dict[str, Path]`, `tuple[int, int]`).
- Narrow `Any` values from `struct.unpack_from`, `tomllib.loads`, `argparse.Namespace`, `openpyxl`, or JSON payloads via explicit `cast(...)` (`src/ets2_realism/cli.py`, `src/ets2_realism/vfs/hashfs.py`) or typed validation helpers (`_as_table`, `_as_str_list` in `tests/test_cli_scaffold.py`).
- Maintain zero `# type: ignore` or `# pyright: ignore` comments in `src/ets2_realism/`. In `tests/`, avoid suppressions except when wrapping stdlib overloaded methods like `pathlib.Path.open` during monkeypatching (`tests/test_validate_workshop.py:546` is the sole suppression in the repository).

## Data Models (Pydantic v2 vs Frozen Dataclasses)

**Use Strict Frozen Pydantic v2 Models for New Schemas & Domain DTOs:**
- Define all new JSON-serialized schemas, config registries, snapshots, reports, and boundary DTOs as `pydantic.BaseModel` subclasses with `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")` (`69` models across `audit/`, `fetch/`, `merge/`, `normalize/`, `package/`, `publish/`, `registry/`, `validate/`):
  ```python
  class ValidationIssue(BaseModel):
      """Single SCS Workshop or ETS2 1.62 realism validation finding."""

      model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

      code: str
      severity: ValidationSeverity
      path: str | None = None
      detail: str
  ```
- Legacy Phase 1 models (`20` models in `src/ets2_realism/baseline/models.py`, `src/ets2_realism/sii/{country,localization,sign_board,speed_limits}.py`, and `src/ets2_realism/vfs/types.py`) use `ConfigDict(frozen=True)`; keep them immutable and use `Field(default_factory=...)` for mutable defaults.
- Enforce domain invariants declaratively with `Field(ge=..., le=..., pattern=..., min_length=...)`, `@field_validator`, and `@model_validator(mode="after")` (`src/ets2_realism/registry/models.py`, `src/ets2_realism/normalize/models.py`, `src/ets2_realism/publish/release.py`).
- Perform immutable updates via `.model_copy(update=...)`, deserialize via `.model_validate_json(...)`, and serialize via `.model_dump(mode="json")`.

**Use Frozen Dataclasses for High-Volume Internal Value Objects:**
- Use `@dataclass(frozen=True)` or `@dataclass(frozen=True, slots=True)` for non-JSON structural records where allocation overhead matters: lexer spans (`SiiSpan`, `SiiUnitBlock`, `SiiAttributeSpan`, `SiiIncludeSpan`, `SiiScanResult` in `src/ets2_realism/sii/lexer.py`), hygiene diagnostics (`SiiDiagnostic` in `src/ets2_realism/sii/hygiene.py`), HashFS records (`_HashFsRecord` in `src/ets2_realism/vfs/hashfs.py`), VFS layers (`VfsLayer`, `EffectiveVfsEntry` in `src/ets2_realism/vfs/stack.py`), scanned map countries (`ScannedMapCountry` in `src/ets2_realism/merge/scanner.py`), fuel candidates (`_FuelCandidate` in `src/ets2_realism/fetch/pipeline.py`), and staged release bundles (`_StagedEdition` in `src/ets2_realism/publish/release.py`).
- Restrict mutable `@dataclass` strictly to private function-local accumulators (`_OpenUnit` in `src/ets2_realism/sii/lexer.py`, `_LaneSpanGroup` in `src/ets2_realism/sii/speed_limits.py`, `_TableFrame` in `src/ets2_realism/fetch/_html.py`) and non-JSON VFS composite containers (`ComboVfsBuildResult` in `src/ets2_realism/merge/load_order.py`, `ComboScanResult` in `src/ets2_realism/merge/scanner.py`).

**Use `decimal.Decimal` for Currency, FX & Fuel Rounding:**
- Perform exact decimal arithmetic and rounding with `decimal.Decimal` in currency/FX normalization, fuel price calculations, and totem formatting (`src/ets2_realism/normalize/{fuel,fx,totem_format}.py`, `src/ets2_realism/fetch/{global_tier1,pipeline}.py`, `src/ets2_realism/merge/{hardcoded_totems,promods_fuel}.py`) to avoid IEEE-754 float drift across platforms.

## Import Organization

**Order (enforced by Ruff `I`):**
1. `from __future__ import annotations`
2. Standard library imports (alphabetical)
3. Third-party imports (`httpx`, `openpyxl`, `PIL`, `pydantic`, `pytest`)
4. First-party `ets2_realism.*` imports

**Import Rules:**
- Use absolute imports (`from ets2_realism.vfs.types import normalize_vfs_path`) across all `src/` and `tests/` modules; maintain zero relative imports (`from .foo import bar`).
- Export public package APIs explicitly via `__all__` in `src/ets2_realism/__init__.py`, all 11 subpackage `__init__.py` files, `src/ets2_realism/sii/document.py`, and all `src/ets2_realism/merge/*.py` modules (`22` modules total).
- Use explicit re-export syntax (`from ets2_realism.vfs.types import detect_3nk as detect_3nk` in `src/ets2_realism/vfs/hashfs.py`) when re-exporting symbols under strict `basedpyright`.

## File Hygiene, Determinism & SCS SII/SUI Rules

**Repository-Wide UTF-8 No-BOM & LF Hygiene:**
- `.gitattributes` enforces `* text=auto eol=lf` (`fixtures/** -text`; `*.scs`, `*.dds`, `*.jpg`, `*.png` marked `binary`).
- Commit all Python modules, tests, JSON registries/baselines/lockfiles, Markdown changelogs, and `.github/workflows/*.yml` strictly as UTF-8 without BOM (`\xef\xbb\xbf`) and `\n` (LF) line endings. Loaders (`load_prices_lockfile` in `src/ets2_realism/normalize/lockfile.py`, `load_law_registry` and `load_country_aliases` in `src/ets2_realism/registry/loader.py`) and tests (`tests/test_cli_scaffold.py`, `tests/test_baseline_contracts.py`, `tests/test_publish_workflow.py`, `tests/test_country_aliases.py`) reject BOM and `\r` outright.

**Deterministic Serialization & Atomic File Writes:**
- Emit canonical JSON via `json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"` with zero wall-clock timestamps inside canonical hashes (`src/ets2_realism/baseline/extractor.py`, `src/ets2_realism/normalize/lockfile.py`, `src/ets2_realism/registry/snapshot.py`, `src/ets2_realism/publish/ledger.py`).
- Build reproducible ZIP/`.scs` archives using fixed ZIP metadata constants (`ZIP_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)`, `ZIP_UNIX_SYSTEM = 3`, `ZIP_FILE_EXTERNAL_ATTR = 0o100644 << 16`, `ZIP_COMPRESS_LEVEL = 6`) and sorted relative paths (`src/ets2_realism/package/builder.py`, `src/ets2_realism/merge/promods_builder.py`, `src/ets2_realism/merge/compose.py`).
- Write persistent JSON state and generated reports atomically via `tempfile.NamedTemporaryFile(dir=path.parent, delete=False)` + `os.replace(tmp_path, path)` with `contextlib.suppress(OSError)` temp cleanup on `BaseException` (`src/ets2_realism/normalize/lockfile.py`, `src/ets2_realism/merge/compose.py`, `src/ets2_realism/merge/promods_builder.py`, `src/ets2_realism/cli.py`).

**SII/SUI Runtime Normalization & Surgical Editing (`src/ets2_realism/sii/`):**
- Normalize BOM (`\xef\xbb\xbf` / leading `\ufeff`) and `\r\n`/`\r` to LF on every read and write via `normalize_sii_bytes` and `serialize_sii_text` (`src/ets2_realism/sii/hygiene.py`). Reject invalid UTF-8 bytes or lone surrogates by raising `SiiEncodingError`.
- Edit `.sii`/`.sui` files exclusively through span-preserving splices in `SiiDocument` (`src/ets2_realism/sii/document.py`), `patch_country_data` (`src/ets2_realism/sii/country.py`), `patch_speed_limits` (`src/ets2_realism/sii/speed_limits.py`), and `FieldOwnershipPolicy` (`src/ets2_realism/merge/policy.py`) — preserving comments (`#`, `//`, `/* */`), original `iso_country_code` quoting (`isl` vs `"bih"`), `regions[]`/`region_areas[]`, `secondary_time_zone*`, and `train`/`tram` blocks verbatim. Never apply global regex replacement to `.sii`/`.sui` payloads.
- Validate `@include` directives at column `0`, POSIX `/` separators (rejecting `\` and `..`), balanced braces, and `[a-z0-9_]{1,12}` unit segments via `validate_sii_hygiene` (`src/ets2_realism/sii/hygiene.py`).
- Consult `.agents/skills/scs-modding-wiki/SKILL.md` and `docs/` (`engine/units.md`, `engine/formats.md`, `engine/mod_manager.md`, `tools/scs_workshop_uploader/validation_errors_and_solutions_for_them.md`) before modifying SII unit parsers, `manifest.sii`/`versions.sii` emitters, or Workshop validation rules.

## Error Handling & Security Hardening

**Exception vs Collector/Diagnostic Split:**
- Raise typed domain exceptions (`8` custom classes) or standard exceptions (`FileNotFoundError`, `ValueError`, `KeyError`) on fatal preconditions, traversal attempts, encoding errors, or transport failures:
  - VFS: `ProtectedPayloadError`, `UnsupportedCompressionError` (`src/ets2_realism/vfs/types.py`)
  - SII: `SiiEncodingError` (`src/ets2_realism/sii/hygiene.py`)
  - Fetch: `HttpFetchError` (`src/ets2_realism/fetch/http.py`), `Tier2EncodingError` (`src/ets2_realism/fetch/_html.py`), `Tier2RateLimitedError`, `Tier2SelectorDriftError` (`src/ets2_realism/fetch/tier2_portals.py`)
  - Merge: `EncryptedProfileError` (`src/ets2_realism/merge/load_order.py`)
- Accumulate non-fatal archive, hygiene, validation, and lockfile alerts via structured collectors/lists instead of aborting scans mid-run:
  - `DiagnosticCollector` -> `ArchiveDiagnostic` (`src/ets2_realism/vfs/types.py`)
  - `ValidationCollector` -> `ValidationReport` where **any** error OR warning sets `ok=False` (`src/ets2_realism/validate/models.py`)
  - `SiiDiagnostic` / `SiiLexDiagnostic` (`src/ets2_realism/sii/{hygiene,lexer}.py`)
  - `LockAlert` (`src/ets2_realism/normalize/models.py`) and `ScanDiagnostic` (`src/ets2_realism/merge/scanner.py`)
- Catch operational errors (`OSError`, `ValueError`, `ValidationError`, `HttpFetchError`, `ProtectedPayloadError`, `UnsupportedCompressionError`) at the CLI boundary (`src/ets2_realism/cli.py`), redact any URL secrets with `redact_url_secrets`, print `error: ...` to `sys.stderr`, and return POSIX exit status `1`.

**Resource Caps, Path Containment & Network Hardening:**
- Enforce hard byte ceilings on untrusted inputs: `MAX_V2_TABLE_BYTES = 64 MiB` and `MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB` (`src/ets2_realism/vfs/hashfs.py`), `MAX_ZIP_ENTRY_BYTES = 128 MiB` (`src/ets2_realism/vfs/zip_archive.py`), `MAX_STUB_INSPECT_BYTES = 1 MiB` (`src/ets2_realism/vfs/stack.py`), `MAX_TAINT_TEXT_BYTES = 64 MiB` (`src/ets2_realism/audit/taint.py`), `DEFAULT_MAX_RESPONSE_BYTES = 30 MiB` and `DEFAULT_MAX_XML_BYTES = 2 MiB` (`src/ets2_realism/fetch/http.py`).
- Enforce path containment (`validate_rel_path` and `ensure_contained` in `src/ets2_realism/package/builder.py`; `normalize_vfs_path` in `src/ets2_realism/vfs/types.py`; tracked-repo output guards in `src/ets2_realism/baseline/extractor.py`, `src/ets2_realism/merge/promods_builder.py`, and `src/ets2_realism/merge/compose.py`).
- Route all outbound HTTP requests through `create_http_client`, `fetch_bytes_with_retry`, or `post_form_bytes_with_retry` (`src/ets2_realism/fetch/http.py`): enforce `verify=True`, `follow_redirects=False` with per-hop allowlist re-validation, HTTPS port `443` only, query-secret masking (`redact_url_secrets`), and XXE-safe XML parsing (`parse_xml_safe` rejecting `DOCTYPE`/`ENTITY`).

## Logging

- Never import `logging` or call `print()` inside library subpackages (`src/ets2_realism/{vfs,sii,baseline,normalize,registry,fetch,package,validate,merge,publish,audit}/`); return structured Pydantic models or diagnostic collections instead.
- Route all console output (`--json` or plain-text summaries to `sys.stdout`, `error: ...` to `sys.stderr`) exclusively through the `16` `_handle_*` subcommand functions in `src/ets2_realism/cli.py`.

## Comments

- Write single-line `"""..."""` docstrings on modules, public classes, methods, and exported functions using double backticks (````symbol````) for code references.
- Add inline `#` comments only to explain non-obvious invariants, engine quirks, decision IDs (`D-09`, `D-13`, `D-16`), threat IDs (`T-02-13`, `T-03-02`), or DAG boundaries.

## Function Design

- Validate preconditions early and return immediately on empty inputs.
- Use keyword-only parameters (`*`) for behavioral flags, optional paths, and injectable dependencies (`laws_dir`, `mappings_path`, `baseline_dir`, `prices_lock_path`, `client`, `sleep_fn`, `dry_run`, `force`, `profile`).
- Keep functions single-purpose and pure where possible; inject HTTP clients (`httpx.Client`) and clocks/dates (`as_of_date`, `build_date`, `sleep_fn`) rather than reading global wall-clock or network state inside core logic.

## Module Design & AST-Enforced Acyclic DAG

**Strict Acyclic Package Dependency Hierarchy (`src/ets2_realism/`):**
- Maintain the 11-subpackage DAG verified automatically by `test_phase5_ast_dag_isolation_walls` (`tests/test_cli_scaffold.py`) and `test_validate_package_has_zero_imports_from_ets2r_package` (`tests/test_validate_workshop.py`):
  - **Leaf Primitives:** `vfs/` and `sii/` (zero cross-imports between `vfs` and `sii`; `vfs/stack.py` strips SII comments locally).
  - **Baseline Layer:** `baseline/` -> `vfs`, `sii`.
  - **Offline Normalization & Registry:** `normalize/` -> `baseline`; `registry/` -> `baseline`, `normalize`.
  - **Offline Packaging & Independent Validation:** `package/` -> `baseline`, `normalize`, `registry`, `sii`, `vfs`; `validate/` -> `baseline`, `sii`, `vfs` (strictly isolated from `package`, `merge`, `normalize`, `fetch`, `publish`, `audit`).
  - **Offline Composition & Release Orchestration:** `merge/` -> `baseline`, `normalize`, `package`, `registry`, `sii`, `validate`, `vfs`; `publish/` -> `baseline`, `normalize`, `package`, `registry`, `sii`, `validate`, `vfs`.
  - **Online Fetch Layer:** `fetch/` -> `baseline`, `normalize` (sole production subpackage using `httpx` and `openpyxl` for live price feeds).
  - **Quarantined Internal Audit Layer:** `audit/` -> `fetch`, `registry`, `vfs`.
  - **CLI Orchestrator:** `src/ets2_realism/cli.py` -> wires all 11 subpackages.
- **Six Offline Isolation Walls:** `validate/`, `merge/`, `package/`, `publish/`, `normalize/`, and `registry/` must never import `httpx`, `openpyxl`, `ets2_realism.fetch`, or `ets2_realism.audit`.
- **Audit Quarantine Wall (D-16):** Zero of the 10 non-audit subpackages may import `ets2_realism.audit`, and `audit/` must never import `package`, `merge`, `publish`, `validate`, or `openpyxl`.

## Clean-Room IP & License Hygiene

- **MIT Clean-Room Provenance:** `pyproject.toml` declares `license = "MIT"` and `uv.lock` contains only permissive dependencies (`MIT`, `BSD`, `Apache-2.0`, `PSF-2.0`). Never add GPL/LGPL/AGPL dependencies or port code from GPL SCS tools (`TruckLib`, `Extractor`, `easy-scsmodmanager`). `src/ets2_realism/vfs/cityhash.py` implements Google CityHash64 1.0.3 (MIT) cleanly in pure Python.
- **Zero Decryption & Zero Raw Game Assets in Git:** Never decrypt `3nK\x01`, `AEM!`, `ScsC` encrypted profiles, or encrypted ZIP entries (`0x01`/`0x40`) — detect headers and emit diagnostics or raise typed errors (`ProtectedPayloadError`, `EncryptedProfileError`). Never commit raw `.scs` archives, ProMods `def` dumps, or extracted `.sii`/`.sui` files under `data/`.
- **Automated CC BY 4.0 License-Taint Gate (D-16 / GLB-04):** Keep all committed registries (`data/laws/`, `data/curated/`, `data/mappings/`), `state/prices.lock.json`, `CHANGELOG_*.md`, generated snapshots, and built `.scs`/`.zip`/Workshop packages free of the 8 forbidden license/source markers (`CC BY-SA`, `ODbL`, `OpenStreetMap`, `osm-legal-default-speeds`, `GlobalPetrolPrices`, `CC BY-NC-ND`, `MyLPG`, `IEA`). Both `src/ets2_realism/audit/taint.py` and `src/ets2_realism/validate/invariants.py` maintain synchronized independent copies of `FORBIDDEN_LICENSE_TAINT_PATTERNS` (preserving the DAG wall between `validate/` and `audit/`), verified by `tests/test_license_taint_gate.py`.
- **Internal-Only OSM Advisory Quarantine:** `src/ets2_realism/audit/osm_speeds.py` and `.github/workflows/osm-speed-audit.yml` are strictly read-only maintainer advisory tools; never auto-apply OSM values into `data/laws/` or release artifacts.

---

*Convention analysis: 2026-11-26*
