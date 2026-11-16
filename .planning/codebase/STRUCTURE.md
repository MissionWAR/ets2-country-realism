# Codebase Structure

**Analysis Date:** 2026-11-16

## Directory Layout

```text
d:\CODE\Ets2 Mod V2\
├── .agents/                          # Project-local agent skills (vendored SCS Modding Wiki)
│   └── skills/
│       └── scs-modding-wiki/         # SKILL.md, index.json, sources.json, 163 mirrored wiki docs
├── .github/
│   └── workflows/
│       └── ci.yml                    # Day-1 CI: ruff check/format, basedpyright strict, pytest
├── .planning/                        # GSD project metadata, research, plans, and codebase maps
│   ├── codebase/                     # ARCHITECTURE.md, STRUCTURE.md (generated codebase analysis)
│   ├── intel/                        # Refresh metadata (.last-refresh.json)
│   ├── phases/
│   │   └── 01-vfs-1-62-baseline-extraction-structural-sii-engine/
│   ├── research/                     # Pre-implementation research docs (STACK, ARCHITECTURE, etc.)
│   ├── config.json                   # GSD workflow, model, and skill bindings
│   ├── PROJECT.md                    # Core project scope and locked architectural decisions
│   ├── REQUIREMENTS.md               # Traceable V1/V2 requirements matrix
│   ├── ROADMAP.md                    # 5-phase V1 milestone roadmap and plan tracker
│   └── STATE.md                      # Live execution position and metrics
├── data/
│   └── baselines/
│       └── ets2_1.62_def/            # Deterministic clean-room ETS2 1.62.3.3s JSON baseline
│           ├── countries.json        # 36 base country_data schemas
│           ├── fuel_boards.json      # 461 fuel totem boards + 5 excluded highway signs
│           ├── locales.json          # 43 active locales, 12 tz_* keys, 99 fp_* keys
│           ├── manifest.json         # Version counts, DLC audit (107 DLCs), file SHA-256 digests
│           └── speed_limits.json     # 36 country speed_limits.sii schemas (incl. train/tram)
├── src/
│   └── ets2v2/                       # Installable Python 3.12+ package (`ets2-world-realism`)
│       ├── __init__.py               # Package docstring and __version__ = "0.1.0"
│       ├── cli.py                    # CLI entrypoint (`ets2v2` console script)
│       ├── py.typed                  # PEP 561 typed-package marker
│       ├── baseline/                 # ETS2 1.62 baseline Pydantic models & extractor
│       │   ├── __init__.py
│       │   ├── extractor.py
│       │   └── models.py
│       ├── sii/                      # Structural SII/SUI lexer, hygiene, surgical editor & adapters
│       │   ├── __init__.py
│       │   ├── country.py
│       │   ├── document.py
│       │   ├── hygiene.py
│       │   ├── lexer.py
│       │   ├── localization.py
│       │   ├── sign_board.py
│       │   └── speed_limits.py
│       └── vfs/                      # Clean-room HashFS v1/v2, ZIP, directory & VfsStack overlay
│           ├── __init__.py
│           ├── cityhash.py
│           ├── dir_archive.py
│           ├── hashfs.py
│           ├── stack.py
│           ├── types.py
│           └── zip_archive.py
├── tests/                            # Pytest suite (113 CI-safe + 2 @pytest.mark.local_ets2)
│   ├── test_baseline_contracts.py
│   ├── test_baseline_extractor.py
│   ├── test_cli_scaffold.py
│   ├── test_sii_boards_locales.py
│   ├── test_sii_country.py
│   ├── test_sii_document.py
│   ├── test_sii_hygiene.py
│   ├── test_sii_speed_limits.py
│   ├── test_vfs_archives.py
│   ├── test_vfs_cityhash.py
│   └── test_vfs_stack.py
├── .gitattributes                    # Enforces LF line endings and binary markers (.scs, .dds, .jpg, .png)
├── .gitignore                        # Excludes .venv/, build/, dist/, out/, raw/, vendor/, caches
├── pyproject.toml                    # Hatchling build, dependencies, Ruff, Basedpyright, Pytest config
└── uv.lock                           # Locked 17-package reproducible dependency graph
```

## Directory Purposes

**`src/ets2v2/`:**
- Purpose: Root Python package containing only active Phase 1 subsystems (`cli.py`, `vfs/`, `sii/`, `baseline/`).
- Contains: Typed modules (`py.typed`), Pydantic v2 schemas, pure-Python VFS/SII engines, and CLI orchestration.
- Key files: `src/ets2v2/__init__.py`, `src/ets2v2/cli.py`, `src/ets2v2/py.typed`.

**`src/ets2v2/vfs/`:**
- Purpose: Cross-platform read-only SCS virtual filesystem abstraction.
- Contains: MIT pure-Python `CityHash64` 1.0.3 (`cityhash.py`), protocol/diagnostic types (`types.py`), HashFS v1/v2 & magic dispatcher (`hashfs.py`), ZIP/ZIP-`.scs` reader (`zip_archive.py`), root-contained directory reader (`dir_archive.py`), and priority overlay stack (`stack.py`).
- Key files: `src/ets2v2/vfs/__init__.py`, `src/ets2v2/vfs/types.py`, `src/ets2v2/vfs/cityhash.py`, `src/ets2v2/vfs/hashfs.py`, `src/ets2v2/vfs/zip_archive.py`, `src/ets2v2/vfs/dir_archive.py`, `src/ets2v2/vfs/stack.py`.

**`src/ets2v2/sii/`:**
- Purpose: String/comment-aware structural scanner, hygiene checker, and span-preserving surgical SII/SUI editor plus ETS2 format adapters.
- Contains: Linear lexer (`lexer.py`), UTF-8/LF/path/unit-segment validator (`hygiene.py`), surgical editor (`document.py`), read+patch adapters (`country.py`, `speed_limits.py`), and read-only parsers (`sign_board.py`, `localization.py`).
- Key files: `src/ets2v2/sii/__init__.py`, `src/ets2v2/sii/lexer.py`, `src/ets2v2/sii/hygiene.py`, `src/ets2v2/sii/document.py`, `src/ets2v2/sii/country.py`, `src/ets2v2/sii/speed_limits.py`, `src/ets2v2/sii/sign_board.py`, `src/ets2v2/sii/localization.py`.

**`src/ets2v2/baseline/`:**
- Purpose: Clean-room ETS2 `1.62.3.3s` metadata extraction, JSON serialization, and SHA-256 verification.
- Contains: Frozen Pydantic baseline schemas (`models.py`) and extraction/verification pipeline (`extractor.py`).
- Key files: `src/ets2v2/baseline/__init__.py`, `src/ets2v2/baseline/models.py`, `src/ets2v2/baseline/extractor.py`.

**`data/baselines/ets2_1.62_def/`:**
- Purpose: Version-controlled clean-room JSON fixture snapshot extracted from ETS2 `1.62.3.3s` (`version.scs`, `def.scs`, `locale.scs`, and audited `dlc_*.scs`).
- Contains: Five deterministic UTF-8 no-BOM LF JSON files (`countries.json`, `speed_limits.json`, `fuel_boards.json`, `locales.json`, `manifest.json`). Zero `.sii`/`.sui` files are permitted here.

**`tests/`:**
- Purpose: Automated TDD and contract verification suite mirroring `src/ets2v2/` subsystems.
- Contains: Synthetic/in-memory unit tests (CI-safe) plus `@pytest.mark.local_ets2` live-archive verification in `tests/test_baseline_contracts.py` and scaffold/layout guards in `tests/test_cli_scaffold.py`.

**`.github/workflows/`:**
- Purpose: Automated CI quality gate execution.
- Key files: `.github/workflows/ci.yml` (`ruff check`, `ruff format --check`, `basedpyright`, `pytest`).

## Key File Locations

**Entry Points:**
- `src/ets2v2/cli.py`: `ets2v2` CLI (`build_parser()`, `main()`, `vfs inspect`, `baseline extract`).
- `src/ets2v2/__init__.py`: Package version export (`__version__ = "0.1.0"`).

**Configuration:**
- `pyproject.toml`: Build system (`hatchling`), runtime/dev dependency bounds, `ets2v2` script, `ruff` (`line-length = 100`, `E/F/I/UP/B/SIM/RUF`), `basedpyright` (`strict`, Python `3.12`), and `pytest` (`testpaths = ["tests"]`, `pythonpath = ["src"]`, `local_ets2` marker).
- `uv.lock`: Exact locked dependency versions (`pydantic==2.14.3`, `basedpyright==1.40.2`, `pytest==9.2.0`, `pytest-cov==7.1.0`, `ruff==0.17.5`).
- `.gitattributes` / `.gitignore`: LF text enforcement, binary patterns, and gitignored output/cache directories (`build/`, `dist/`, `out/`, `raw/`, `vendor/`).
- `.github/workflows/ci.yml`: GitHub Actions CI definition.

**Core Logic:**
- `src/ets2v2/vfs/hashfs.py` & `src/ets2v2/vfs/stack.py`: Archive dispatching and multi-layer VFS overlay resolution.
- `src/ets2v2/sii/lexer.py` & `src/ets2v2/sii/document.py`: Structural SII/SUI scanner and surgical span editor.
- `src/ets2v2/sii/country.py` & `src/ets2v2/sii/speed_limits.py`: Surgical ETS2 country and speed-limit round-trip adapters.
- `src/ets2v2/baseline/extractor.py` & `src/ets2v2/baseline/models.py`: Clean-room baseline schema models and deterministic extractor/verifier.

**Testing:**
- `tests/test_cli_scaffold.py`: CLI smoke tests, pyproject/CI validation, and `test_active_phase_only_package_layout()` boundary check.
- `tests/test_vfs_cityhash.py`, `tests/test_vfs_archives.py`, `tests/test_vfs_stack.py`: CityHash64, HashFS v1/v2, ZIP, Directory, protection stubs, and `VfsStack` overlay tests.
- `tests/test_sii_hygiene.py`, `tests/test_sii_document.py`, `tests/test_sii_country.py`, `tests/test_sii_speed_limits.py`, `tests/test_sii_boards_locales.py`: SII lexer, hygiene, surgical mutation, country, speed-limit, sign-board, and localization tests.
- `tests/test_baseline_extractor.py` & `tests/test_baseline_contracts.py`: Synthetic extractor tests, committed `1.62` baseline invariants, zero-raw-SCS check, and `@pytest.mark.local_ets2` 36-country live round-trip checks.

## Naming Conventions

**Files & Packages:**
- Lowercase `snake_case.py` for Python modules (`dir_archive.py`, `speed_limits.py`, `sign_board.py`).
- Short lowercase subsystem package names (`vfs/`, `sii/`, `baseline/`).
- Test modules mirror subsystem prefix: `tests/test_<subsystem>_<area>.py` (`test_vfs_stack.py`, `test_sii_country.py`, `test_baseline_contracts.py`).
- Clean-room JSON baselines use lowercase `snake_case.json` (`countries.json`, `fuel_boards.json`, `locales.json`, `manifest.json`, `speed_limits.json`).

**Code Symbols:**
- `PascalCase` for Pydantic models, dataclasses, protocols, and exceptions (`VfsArchive`, `VfsStack`, `SiiDocument`, `BaselineBundle`, `ProtectedPayloadError`, `SiiEncodingError`).
- `snake_case` for functions, methods, and fields; leading underscore (`_helper_name`) for module-private helpers and internal dataclasses (`_OpenUnit`, `_HashFsRecord`, `_LaneSpanGroup`).
- `UPPER_SNAKE_CASE` for module constants and compiled regexes (`DEFAULT_SEEDED_PREFIXES`, `MAX_V2_TABLE_BYTES`, `EXTRACTOR_SCHEMA_VERSION`, `_UNIT_SEGMENT_CHARS_RE`).
- Explicit `__all__` export lists in every subpackage `__init__.py`.

**SCS Mod Assets & Hygiene:**
- POSIX `/` separators only; no `..` parent traversal; UTF-8 without BOM; LF (`\n`) line endings.
- Unit name segments strictly match `[a-z0-9_]{1,12}` separated by `.` (`validate_unit_name_segments()` in `src/ets2v2/sii/hygiene.py`).

## Where to Add New Code (Phases 2–5 Placement Guide)

**Important Pre-Condition (Active-Phase Guard):**
`tests/test_cli_scaffold.py::test_active_phase_only_package_layout` (`lines 63–74`) explicitly enforces that `src/ets2v2/` contains only `{"__init__.py", "py.typed", "cli.py", "vfs", "sii", "baseline"}` and rejects `{"fetch", "normalize", "merge", "validate", "package"}` during Phase 1. When starting each new phase, update `allowed_phase*_entries` / `deferred_phase_dirs` in `tests/test_cli_scaffold.py` deliberately alongside introducing that phase's package(s).

**Phase 2 — Realism Registry, Seasonal Core Builds & Offline Validator:**
- **Canonical data files:** Place YAML/JSON country speed, DRL, axle, and alias registries under `data/laws/` and `data/mappings/`; place the release SHA-256 diff ledger at `state/published.json`.
- **DST & registry normalization:** Add `src/ets2v2/normalize/` for canonical registry loading and stdlib `zoneinfo` + `tzdata` seasonal DST computation (`@@tz_*@@` vs plain `"CET"`/`"WET"`/`"AST"`).
- **Mod compilation:** Add `src/ets2v2/merge/` for seasonal `country_data` + `speed_limits.sii` generation built over `ets2v2.sii` surgical editors (`patch_country_data()`, `patch_speed_limits()`).
- **Offline SCS Validator:** Add `src/ets2v2/validate/` wrapping `ets2v2.sii.hygiene.validate_sii_hygiene()` and adding Workshop checks (`00001`–`00010`, `WARN 00001`/`00002`, `276x162` `.jpg` icon, `manifest.sii`/`versions.sii` constraints, no ZIP-as-`.scs` errors).
- **Packaging & CI:** Add `src/ets2v2/package/` for staging `dist/workshop/{summer,winter}/` (`universal/` and `universal.zip`), wire build/validate CLI commands in `src/ets2v2/cli.py`, add Phase A Friday release workflow in `.github/workflows/`, and add tests in `tests/test_validate_*.py`, `tests/test_merge_*.py`, `tests/test_package_*.py`.

**Phase 3 — Open European Fuel/FX Pipeline & Zero-DDS Totems:**
- **Source configs & circuit-breaker state:** Add `data/sources.yaml` (FX/fuel endpoint configs), `prices.lock.json` (last-known-good fallback store), and `data/mappings/fuel_sign_boards.yaml`.
- **Collectors & FX conversion:** Add `src/ets2v2/fetch/` (`Frankfurter v2`, `ECB`, `fawazahmed0`, `CBR` FX validators; Tier 1 EU/EEA collectors with `0.01–5.00 EUR/L` and `±25%` circuit-breaker guards) and extend `src/ets2v2/normalize/` for `eur_per_liter` vs `local_display_price` conversion.
- **Zero-DDS totem engine:** Extend `src/ets2v2/sii/sign_board.py` and `src/ets2v2/sii/localization.py` with write/patch helpers if surgical board mutation is needed, and implement Option 4b `@@fp_*_ets2v2@@` `def/sign/board/*.sii` + 43-locale `locale/<lang>/local_module.ets2v2_fuel.sii` compilation in `src/ets2v2/merge/`.

**Phase 4 — ProMods Companion & Local Map Combo Composer:**
- **Alias & ProMods schemas:** Populate `data/mappings/country_aliases.yaml` and `data/mappings/pm_totem_keys.yaml` (keeping zero ProMods `.scs` or extracted `.sii`/`.sui` files in Git).
- **Snapshot & `FieldOwnershipPolicy`:** Extend `src/ets2v2/normalize/` to emit/validate `realism-snapshot-{summer|winter}.json`; extend `src/ets2v2/merge/` with `FieldOwnershipPolicy` (`max_of_map_and_real`, `patch_if_single_tz`), ProMods `EU + ME + MA + TGS` companion builder (`local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii`), and load-order scanner over `ets2v2.vfs.VfsStack` (handling `.sui`/`.sii` fragments, `base/`, `empty_stub_paths()`, `AEM!`/encrypted-ZIP diagnostics, `--unpacked-defs`, and `--patch-hardcoded-totems`).
- **CLI:** Add `compose-local` (and ProMods build subcommand) in `src/ets2v2/cli.py`, emitting `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` via `src/ets2v2/package/`.

**Phase 5 — Global Tier 1/2/3 Coverage & Internal OSM Audit:**
- **Global collectors & baselines:** Extend `src/ets2v2/fetch/` with non-EU Tier 1 collectors and isolated per-country Tier 2 scrapers; expand `data/laws/` Tier 3 coverage to `200+` territories.
- **Isolated OSM audit:** Place the CI-only OSM Overpass/Taginfo (`CC BY-SA`) speed-limit drift audit in an isolated audit module/script and dedicated CI check asserting zero `CC BY-SA` data provenance enters `CC BY 4.0` snapshot or mod outputs.

**Utilities & Shared Helpers:**
- VFS container/path/diagnostic utilities belong in `src/ets2v2/vfs/types.py`.
- SII scalar/tuple/span helpers belong in `src/ets2v2/sii/lexer.py`; encoding/path/unit hygiene checks belong in `src/ets2v2/sii/hygiene.py`.

## Special Directories

**`data/baselines/` (`data/baselines/ets2_1.62_def/`):**
- Purpose: Holds deterministic clean-room JSON metadata extracted from ETS2 `1.62.3.3s` archives (`countries.json`, `speed_limits.json`, `fuel_boards.json`, `locales.json`, `manifest.json`).
- Generated: Extracted via `ets2v2 baseline extract` (only regenerates on game updates or extractor schema bumps; verified zero-diff via `--check`).
- Committed: Yes. Enforced free of raw `.sii`/`.sui` files by `tests/test_baseline_contracts.py` and `src/ets2v2/baseline/extractor.py` (`--raw-cache-dir` is forbidden inside `data/`).

**`.planning/`:**
- Purpose: Stores project specifications (`PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`), workflow settings (`config.json`), pre-phase research (`.planning/research/`), phase execution/review/verification artifacts (`.planning/phases/01-*/`), codebase maps (`.planning/codebase/`), and intel timestamps (`.planning/intel/`).
- Generated: Maintained by GSD planning/execution workflows (`commit_docs: true` in `.planning/config.json`).
- Committed: Yes. Excluded from Ruff markdown formatting checks via `extend-exclude = [".planning", ".agents"]` in `pyproject.toml`.

**`.agents/` (`skills/scs-modding-wiki/`):**
- Purpose: Houses vendored project skill `scs-modding-wiki` (`SKILL.md`, `index.json`, `sources.json`, `crawl_report.md`, and 163 mirrored official SCS Modding Wiki pages across `docs/engine/` and `docs/tools/`), wired to GSD agents via `agent_skills` in `.planning/config.json`.
- Generated: Pre-vendored offline documentation snapshot (read-only reference).
- Committed: Yes. Excluded from Ruff checks via `pyproject.toml`.

**Gitignored Staging/Cache Directories (`.gitignore`):**
- `build/`, `dist/`, `out/`, `raw/`, `vendor/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`: Local virtualenvs, tool caches, optional `--raw-cache-dir` extracts, and generated build/Workshop/combo outputs. Never committed to Git.

---

*Structure analysis: 2026-11-16*
