# Phase 1: VFS, 1.62 Baseline Extraction & Structural SII Engine - Context

**Gathered:** 2026-11-16
**Status:** Ready for planning
**Scope:** Requirements `VFS-01`, `VFS-02`, `SII-01`, `SII-02` (Plans `01-01` through `01-04`)

<domain>
## Phase Boundary

Phase 1 establishes the foundational Python `3.12+` (`uv`) package (`ets2v2`), a clean-room cross-platform VFS reader and overlay engine (`HashFS v1`, `HashFS v2`, `.zip`/`.scs`, unpacked directories), deterministic metadata/schema extraction from ETS2 `1.62.3.3s` (`def.scs` & `locale.scs`), and a comment/region-preserving surgical SII/SUI parser and serializer.

Out of scope for Phase 1 (explicitly deferred to later phases):
- Country realism rule datasets (`data/laws/`, `data/mappings/`), `zoneinfo`/`tzdata` DST calculation, Workshop packaging (`manifest.sii`, `versions.sii`, `276x162` `.jpg`), Offline SCS Validator, and SHA-256 release ledger (**Phase 2**).
- Live FX/fuel fetching, `prices.lock.json`, and Option 4b 43-locale totem writers (**Phase 3**).
- ProMods Companion Builder and `ets2v2 compose-local` load-order orchestration (**Phase 4**).
- Non-EU Tier 1/2/3 collectors and OSM drift audit (**Phase 5**).

</domain>

<decisions>
## Implementation Decisions

### 1. Package Layout, Build Backend & Quality Gates (`01-01`)
- **Active-Phase Scaffolding Only:** Scaffold only active Phase 1 packages under `src/ets2v2/` (`__init__.py`, `cli.py`, `vfs/`, `sii/`, `baseline/`). Do **not** create empty placeholder directories for later phases (`fetch/`, `normalize/`, `merge/`, `validate/`, `package/`) until their respective phases begin.
- **Build & Toolchain:** Use `pyproject.toml` with `hatchling` build backend, `requires-python = ">=3.12"`, console script `ets2v2 = "ets2v2.cli:main"`, and committed `uv.lock`.
- **Dependencies:** Core runtime dependencies per `STACK.md` (`pydantic>=2.14,<3`, plus Phase 1 stdlib `struct`, `zlib`, `zipfile`, `pathlib`, `json`; defer `httpx`/`openpyxl`/`pillow` until needed or include only if locked in baseline `pyproject.toml` — check `STACK.md` minimal Phase 1 vs full baseline). Dev gates: `basedpyright>=1.40,<2`, `ruff>=0.16`, `pytest>=9.2,<9.3`, `pytest-cov>=5,<7`.
- **Strict Type Checking:** Configure `basedpyright` in **`strict`** mode from day one alongside `ruff` lint/format checks (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`).
- **Day-1 CI Workflow:** Include `.github/workflows/ci.yml` in `01-01` running on PR/push (`ubuntu-latest`, `astral-sh/setup-uv@v5`) to execute `uv sync --locked`, `ruff check`, `ruff format --check`, `basedpyright`, and `pytest`.

### 2. VFS Container Readers, Multi-Layer Overlay & Protected Formats (`01-02`, `VFS-01`)
- **Full `VfsArchive` + `VfsStack` in Phase 1:** Build both uniform single-container readers (`HashFsV1Archive`, `HashFsV2Archive`, `ZipArchive`, `DirectoryArchive`) and the multi-layer `VfsStack` overlay engine in Phase 1:
  - Cross-platform POSIX forward-slash path normalization (`/def/...` or `def/...` consistently canonicalized on Windows and Linux).
  - Priority-ordered layer resolution (higher-priority layer wins per canonical path).
  - `base/` mount-prefix normalization (resolving both `def/...` and `base/def/...` into the canonical VFS view).
  - Seeded prefix walking for HashFS v2 archives like `locale.scs` that omit a root `/` directory listing (seeding known prefixes such as `locale`, `def`, `base`, or caller-provided prefixes).
  - Empty `SiiNunit { }` path shadowing semantics preserved cleanly in the overlay model.
- **Clean-Room HashFS Implementation:** Implement HashFS v1 and HashFS v2 purely from documented binary layouts using stdlib `struct` + `zlib` and a clean-room ~100-line pure-Python MIT `CityHash64` implementation. Zero GPL code (`TruckLib`, `Extractor`, `easy-scsmodmanager`) and zero C-extension build dependencies.
- **Strict Detect-and-Report Policy (`3nK`, `AEM!`, Encrypted ZIP, Unsupported Compression):**
  - Never implement `3nK` XOR decryption or copy `3nK`-decoded third-party blobs. Detect `b"3nK\x01"` headers on `.sii`/`.sui` payloads and record/return a typed protected-file diagnostic cleanly.
  - Detect `AEM!` headers, unknown/bad archive magic bytes, and password-encrypted ZIP entries (flag bit `0x1` — still inspecting unencrypted ZIP central-directory path names when available) and emit structured `ArchiveDiagnostic` warnings/records without crashing.
  - Support uncompressed and `zlib` (`deflate`) entries only; if a third-party HashFS v2 entry uses `zstd`, `gdeflate`, or an unknown compression code, record an explicit unsupported-compression diagnostic cleanly rather than adding extra decompression dependencies or crashing.

### 3. ETS2 `1.62.3.3s` Baseline Extraction & Public Repo Copyright Boundary (`01-03`, `VFS-02`)
- **Clean-Room JSON Schemas Only in Git:** Commit **only** deterministic, clean-room structured JSON metadata/schemas under `data/baselines/ets2_1.62_def/` (`manifest.json`, `countries.json`, `speed_limits.json`, `fuel_boards.json`, `locales.json`). Never commit verbatim raw SCS `.sui`/`.sii` files from `def.scs` or `locale.scs` to the public repository.
- **Optional Local Raw Cache for Byte-Exact Testing:** Support an optional gitignored local extraction/cache directory (e.g., under `build/` or explicit `--game-dir` / `ETS2_GAME_DIR`) when running locally against `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\` so maintainers can verify byte-preserving surgical edits against real `1.62.3.3s` files, while CI builds and unit tests remain 100% self-contained using JSON schemas and clean-room synthetic `.sui`/`.sii` test fixtures.
- **Dynamic Fuel Board Discovery & Slot Metadata:** Discover all fuel/gas boards dynamically from `def/sign/board/*.sii` (covering both `@@fp_*@@` boards and fuel/gas filename/placeholder patterns — ~457–555 boards across active, unmapped, numeric-placeholder, and blank fuel signs, excluding ~12.4k non-fuel highway signs). Capture full `sign_board_template` / `sign_template_text` slot metadata (`coords_*`, `font_face`, alignment, text slot index/value) inside `fuel_boards.json` so Phase 3 CI can generate Option 4b board overrides cleanly without `def.scs` on CI runners.
- **Locale & Baseline Coverage:** Extract all **36** Vanilla+DLC country definitions (incl. 5-axle 60t `iceland.sui`, `regions[]`/`region_areas[]`, quoting conventions), all **36** `speed_limits.sii` definitions (`car`/`truck`/`bus`/`train`/`tram`), and all **43** active `locale.scs` locales (explicitly excluding dead `fr_qc`), the **12** `@@tz_*@@` keys, and the **99** vanilla `fp_*` keys.

### 4. Structural SII/SUI Parser, Surgical Editor & Hygiene Engine (`01-04`, `SII-01`, `SII-02`)
- **Shared SII/SUI Parser Scope in `src/ets2v2/sii/`:** Implement a single shared structural lexer/document model supporting both `SiiNunit { ... }` files and headerless `.sui`/`.sii` `@include` fragments, `#`/`//`/`/* */` comments, column-0 `@include` tracking, `attr[]` append arrays, and indexed `attr: N` / `attr[0]: ...` arrays:
  - **Read + Surgical Edit adapters:** `country_data` (`.sui` / fragment `.sii`) and `country_speed_limit` (`speed_limits.sii` preserving `train`, `tram`, and untouched blocks/fields).
  - **Read-only models:** `sign_board_template` (`def/sign/board/*.sii`) and `localization_db` (`locale/*.sui`/`*.sii`), consumed directly by `01-03` baseline extraction (write/override emitters deferred to Phase 3).
- **Hygiene Normalization vs Round-Trip Idempotency (`SII-02`):** Normalize UTF-8 BOM (`\xef\xbb\xbf`) -> no-BOM and `\r\n`/`\r` -> `\n` (LF) on **every** write so all emitted files strictly obey SCS hygiene from the first output. Clean LF no-BOM inputs round-trip with zero byte diff on pass 1; BOM/CRLF inputs normalize on pass 1 and produce zero byte diff on pass 2+. Validate POSIX `/` internal paths, column-0 `@include` rules, and `[a-z0-9_]{1,12}` unit name segments.
- **Surgical Mutation Policy (`SII-01`):**
  - Preserve all untouched attributes, blank lines, formatting, `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`, `tram`, and comments (`#`, `//`, `/* */`) verbatim; preserve original quoting style on untouched fields such as `iso_country_code` (`fra` vs `"mne"`).
  - When updating an existing scalar attribute (`fuel_price`, `lights_mandatory`, `time_zone`, `time_zone_name`, `driving_tired_offence`), preserve trailing inline `#` or `//` comments on that line.
  - When inserting an attribute absent from the original block (e.g., adding `lights_mandatory` to a `country_data` unit), detect the block's indentation and insert cleanly immediately before the unit's closing `}` (or before any trailing `@include` inside the block if present).
  - When updating array attributes (`mass_limit_per_axle_count[]`, `limit[]`, `urban_limit[]`, `max_limit[]`), replace the existing contiguous array block in-place at its original position — supporting array length changes (e.g., 4-axle to 5-axle expansion) cleanly without disturbing surrounding comments.

### Agent's Discretion
- Exact CLI subcommand names and flags under `ets2v2` for Phase 1 (e.g., `ets2v2 baseline extract` / `ets2v2 vfs inspect` with `--game-dir` / `ETS2_GAME_DIR` fallback to standard Windows Steam path `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`).
- Internal AST/token span data structures in `src/ets2v2/sii/`, JSON schema field naming inside `data/baselines/ets2_1.62_def/`, and exact `ruff` rule exclusions if any clash with Pydantic/CLI typing conventions.
- Synthetic/clean-room fixture filenames and test organization under `tests/fixtures/`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or executing Phase 1:**
- `.planning/PROJECT.md` — Core value, license rules, and locked post-research baseline decisions.
- `.planning/REQUIREMENTS.md` — Requirements `VFS-01`, `VFS-02`, `SII-01`, `SII-02` and Out-of-Scope exclusions.
- `.planning/ROADMAP.md` — Phase 1 goal, 4 success criteria, and plan breakdown (`01-01`..`01-04`).
- `.planning/research/STACK.md` — Python `3.12` / `uv` versions, HashFS v1/v2, `3nK` detection specs, `1.62.3.3s` baseline counts, and `basedpyright`/`ruff`/`pytest` tooling.
- `.planning/research/ARCHITECTURE.md` — Field-Ownership Contract, ETS2 engine rules (`.sui` vs `.sii` fragments, `base/` mounts, empty `{}` suppression stubs, file-scoped `.speed_limit.*`), and `1.62.3.3s` archive findings.
- `.planning/research/PITFALLS.md` — SCS encoding/BOM/LF/`<=12`-char unit token rules, `iso_country_code` quoting notes, and `3249064596`/`3668352310` anti-patterns to test against.
- `.agents/skills/scs-modding-wiki/docs/engine/units.md` — Official `SiiNunit` syntax, comment types, column-0 `@include` rules, and `attr[]` / `attr[i]` array formats.
- `.agents/skills/scs-modding-wiki/docs/engine/formats.md` — Official `.sii`, `.sui`, `.scs`, `.zip` format specs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.agents/skills/scs-modding-wiki/` — Local mirror of SCS official documentation (`units.md`, `formats.md`, `game_data.md`, `mod_manager.md`, `validation_errors_and_solutions_for_them.md`).
- `.gitattributes` and `.gitignore` — Already configured in repo root (`* text=auto eol=lf`, `fixtures/** -text`, `*.scs binary`, `build/`/`dist/` gitignored).

### Established Patterns
- Greenfield repository (`d:\CODE\Ets2 Mod V2`) with no existing Python source files yet (`01-01` creates `pyproject.toml`, `uv.lock`, `src/ets2v2/`, `tests/`, and `.github/workflows/ci.yml`).
- Local environment verified: `uv 0.11.31` installed; `.venv` not yet created.

### Integration Points
- Phase 2 consumes `data/baselines/ets2_1.62_def/*.json` (clean-room JSON baseline) and `src/ets2v2/sii/` to synthesize and validate Summer & Winter Vanilla+DLC Core mods in CI without `def.scs`.
- Phase 4 consumes `src/ets2v2/vfs/` (`VfsStack`, `base/` normalization, `AEM!`/encrypted ZIP diagnostics, empty `{}` shadowing) and `src/ets2v2/sii/` surgical rewriting inside `ets2v2 compose-local`.

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed strictly within Phase 1 boundaries. All downstream Phase 2–5 requirements remain mapped in `.planning/ROADMAP.md`.

</deferred>

---
*Phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine*
*Context gathered: 2026-11-16*
