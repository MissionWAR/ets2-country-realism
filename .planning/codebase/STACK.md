# Technology Stack

**Analysis Date:** 2026-11-26

## Languages

**Primary:**
- Python `>=3.12` (verified `3.12.13` locally on Windows `AMD64`; `"3.12"` across `.github/workflows/ci.yml`, `.github/workflows/phase-a-release.yml`, and `.github/workflows/osm-speed-audit.yml`) - All production modules (`src/ets2_realism/`), helper scripts (`scripts/generate_icons.py`), and test suites (`tests/`). Use `from __future__ import annotations`, PEP 604 `X | Y` unions, `collections.abc` abstractions, and strict type annotations across every module.

**Secondary:**
- TOML - Package metadata, linter/type-checker/pytest configuration (`pyproject.toml`), and deterministic lockfile (`uv.lock`).
- JSON - Clean-room extracted ETS2 `1.62.3.3` baselines (`data/baselines/ets2_1.62_def/*.json`), `225` per-country statutory law records (`data/laws/countries/*.json`), clean-room audit allowlist (`data/laws/speed_audit_allowlist.json`), `186` Tier 3 curated global fuel baselines (`data/curated/tier3_fuel_baselines.json`), global mappings (`data/mappings/{ets2_countries,country_aliases,currencies}.json`), release/price state files (`state/{prices.lock,published}.json`), and GSD configuration (`.planning/config.json`).
- YAML - GitHub Actions CI, weekly release, and monthly OSM drift audit pipelines (`.github/workflows/{ci,phase-a-release,osm-speed-audit}.yml`).
- SCS SII / SUI (`SiiNunit` containers and headerless `.sui` fragments) - Game definition, localization (`local_module.*.sii`), sign board (`def/sign/board/*.sii`), speed-limit (`def/country/*/speed_limits.sii`), and mod packaging (`versions.sii`, `manifest.sii`) formats parsed, validated, synthesized, and surgically rewritten by `src/ets2_realism/sii/`, `src/ets2_realism/package/`, and `src/ets2_realism/merge/`.

## Runtime

**Environment:**
- CPython `3.12.13` locally on Windows (`win_amd64`) and Python `3.12` on GitHub Actions `ubuntu-latest`.
- Declared constraint: `requires-python = ">=3.12"` in `pyproject.toml` and `uv.lock`.

**Package Manager:**
- `uv` (`0.11.31` verified locally; provisioned via `astral-sh/setup-uv@v5` with `enable-cache: true` across `.github/workflows/*.yml`).
- Lockfile: `uv.lock` present (lock `version = 1`, `revision = 3`, `28` resolved packages). Always install and run via `uv sync --locked` and `uv run` (or `uv run --offline` for local/offline runs).
- Build backend: `hatchling>=1.27,<2` (`build-backend = "hatchling.build"` in `pyproject.toml`), targeting `[tool.hatch.build.targets.wheel] packages = ["src/ets2_realism"]` (`ets2-country-realism == 0.1.0`) with PEP 561 marker `src/ets2_realism/py.typed`.

## Frameworks

**Core:**
- `pydantic` `2.14.3` (`>=2.14,<3` in `pyproject.toml`) - Strict immutable (`ConfigDict(strict=True, frozen=True, extra="forbid")`) schemas for VFS diagnostics, SII models, baselines, law registries, v1 realism snapshots, price lockfiles, validation reports, compose reports, and audit outputs across `src/ets2_realism/`.
- Python stdlib `argparse` (`src/ets2_realism/cli.py`) - Unified CLI entrypoint `[project.scripts] ets2-realism = "ets2_realism.cli:main"` exposing `vfs inspect`, `baseline extract`, `registry {validate,snapshot,snapshot-verify}`, `package {icons,promods-icons,build,promods}`, `validate {workshop,local}`, `publish release`, `fetch`, `compose-local`, and `audit {osm-speeds,taint}`.

**Testing:**
- `pytest` `9.2.0` (`>=9.2,<9.3` in `pyproject.toml`) - Test runner (`45` test modules under `tests/`) configured under `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = ["-ra", "--strict-markers"]`, markers `local_ets2` and `local_promods`).
- `pytest-cov` `7.1.0` (`>=6,<8` in `pyproject.toml`, backed by `coverage` `7.17.3` in `uv.lock`) - Coverage reporting plugin.

**Build/Dev:**
- `ruff` `0.17.5` (`>=0.16` in `pyproject.toml`) - Combined linter and formatter (`uv run --offline ruff check`, `uv run --offline ruff format --check`) configured in `[tool.ruff]` and `[tool.ruff.lint]`.
- `basedpyright` `1.40.2` (`>=1.40,<2` in `pyproject.toml`, backed by `nodejs-wheel-binaries` `24.19.0` in `uv.lock`) - Strict static type checker (`typeCheckingMode = "strict"`) across `src` and `tests`, paired with `types-openpyxl` `3.1.5.20261017`.
- `scripts/generate_icons.py` - Thin reproducible wrapper invoking `generate_all_icons()` and `generate_promods_icons()` (`src/ets2_realism/package/icons.py`) to regenerate checked-in `276x162` JPEG Workshop icons under `assets/icons/`.

## Key Dependencies

**Critical:**
- `pydantic` `2.14.3` (transitives in `uv.lock`: `pydantic-core` `2.50.4`, `annotated-types` `0.8.0`, `typing-extensions` `4.16.0`, `typing-inspection` `0.4.5`) - Enforces strict model typing, frozen value objects, and deterministic JSON serialization/validation.
- `httpx` `0.28.1` (`>=0.28,<0.29`; transitives: `httpcore` `1.0.9`, `h11` `0.16.0`, `anyio` `4.16.0`, `certifi` `2026.11.20`, `idna` `3.20`) - Hardened synchronous HTTPS client in `src/ets2_realism/fetch/http.py` with unconditional TLS verification (`verify=True`), exact host allowlists on initial requests and redirects, bounded streaming response caps, exponential backoff retries, and secret redaction.
- `openpyxl` `3.1.5` (`>=3.1,<4`; transitive: `et-xmlfile` `2.0.0`) - Read-only OOXML `.xlsx` parsing (`read_only=True, data_only=True`) in `src/ets2_realism/fetch/ec_bulletin.py`, `src/ets2_realism/fetch/global_tier1.py` (Japan METI, rejecting legacy `.xls`), and `src/ets2_realism/fetch/tier2_portals.py` (Rosstat, DMRE/CEF, Nigeria NBS), guarded by `validate_ooxml_zip_safety()` (`src/ets2_realism/fetch/_parsing.py`).
- `pillow` `13.0.0` (`>=12,<14`) - Used strictly for deterministic `276x162` RGB baseline JPEG Workshop icon generation (`src/ets2_realism/package/icons.py`) and offline Workshop icon validation (`src/ets2_realism/validate/workshop.py`). Explicitly prohibited for `.dds`/`.tobj` totem baking (totems use Option 4b Zero-DDS localization).
- `tzdata` `2026.6` (`>=2025.2`) - Cross-platform IANA timezone database required by Python stdlib `zoneinfo.ZoneInfo` on Windows for seasonal Summer (`Jul 15`) / Winter (`Jan 15`) UTC offset and DST derivation (`src/ets2_realism/registry/timezone.py`).

**Infrastructure (Python 3.12 Standard Library Primitives):**
- `struct`, `zlib`, `zipfile` (`src/ets2_realism/vfs/cityhash.py`, `src/ets2_realism/vfs/hashfs.py`, `src/ets2_realism/vfs/zip_archive.py`, `src/ets2_realism/package/builder.py`) - Clean-room MIT Google CityHash64 1.0.3 path hashing, HashFS v1 (`SCS#\x01`) & v2 (`SCS#\x02`, method `CITY`) archive readers, bounded ZIP readers (`MAX_V2_TABLE_BYTES = 64 MiB`, `MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB`), and byte-deterministic DEFLATE ZIP packaging (`1980-01-01 00:00:00`, Unix mode `0o100644`, level 6).
- `html.parser`, `csv`, `xml.etree.ElementTree`, `decimal`, `statistics`, `unicodedata` (`src/ets2_realism/fetch/_html.py`, `src/ets2_realism/fetch/_parsing.py`, `src/ets2_realism/fetch/http.py`, `src/ets2_realism/normalize/`) - Stdlib-only HTML table/anchor/text parsing (zero `beautifulsoup4`/`lxml` dependency), XXE-hardened XML parsing (`parse_xml_safe()` rejecting `DOCTYPE`/`ENTITY` with 2 MiB cap), and exact `Decimal` `ROUND_HALF_UP` FX/gallon-to-liter (`3.785411784` NIST factor) arithmetic.
- `zoneinfo`, `datetime`, `hashlib`, `tempfile`, `os`, `pathlib`, `re`, `json` - Seasonal DST resolution, SHA-256 content diff-gating and `SHA256SUMS.txt` verification, atomic file writes (`os.replace()`), POSIX VFS path canonicalization, linear structural SII lexing/rewriting, and symlink containment checks.

**Licensing & Dependency Hygiene:**
- Repository code license is `MIT` (`pyproject.toml`); clean-room registries, baselines, and curated data use `CC BY 4.0`.
- All `28` locked packages in `uv.lock` use permissive licenses (`MIT`, `BSD`, `Apache-2.0`, `PSF-2.0`, `HPND`). Copyleft GPL SCS archive extractors (`TruckLib`, `Extractor`, `easy-scsmodmanager`), C-wheel `cityhash`, `beautifulsoup4`/`lxml`, and `CC BY-SA` / `ODbL` / `CC BY-NC-ND` data sources are excluded and enforced by `ets2-realism audit taint` (`src/ets2_realism/audit/taint.py`).

## Configuration

**Environment:**
- No `.env` files exist in the repository; all optional runtime overrides and API keys are read directly via `os.environ.get()`.
- Local path overrides:
  - `ETS2_GAME_DIR` - Overrides local ETS2 `1.62.3.3s` install path (`src/ets2_realism/baseline/extractor.py`).
  - `ETS2_MOD_DIR` - Overrides local ETS2 `mod/` directory for ProMods and combo discovery (`src/ets2_realism/merge/promods_discovery.py`).
  - `ETS2_WORKSHOP_DIR` - Overrides local Steam Workshop `227300` content path (`src/ets2_realism/merge/load_order.py`).
- Optional live-fetch API credentials (silent keyless fallback when unset):
  - `TANKERKOENIG_API_KEY` (`src/ets2_realism/fetch/national.py`)
  - `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN` (`src/ets2_realism/fetch/global_tier1.py`)

**Build:**
- `pyproject.toml`:
  - `[tool.ruff]`: `target-version = "py312"`, `line-length = 100`, `src = ["src", "tests"]`, `extend-exclude = [".planning", ".agents"]`, `[tool.ruff.lint] select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`.
  - `[tool.basedpyright]`: `pythonVersion = "3.12"`, `typeCheckingMode = "strict"`, `include = ["src", "tests"]`, `venvPath = "."`, `venv = ".venv"`.
  - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = ["-ra", "--strict-markers"]`, markers `local_ets2` and `local_promods`.
- `.gitattributes` - Enforces `* text=auto eol=lf`, `fixtures/** -text`, and binary handling for `*.scs`, `*.dds`, `*.jpg`, `*.png`.
- `.gitignore` - Excludes `.venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`, `build/`, `dist/`, `out/`, `raw/`, `vendor/`, `.DS_Store`, `Thumbs.db`, `*.tmp`, `*.bak`.
- `.planning/config.json` - Configures GSD quality gates (`build_command`, `test_command`) and binds agent skills to the vendored SCS Modding Wiki mirror at `.agents/skills/scs-modding-wiki/SKILL.md` (`162` official docs pages).

## Platform Requirements

**Development:**
- Cross-platform Windows (`D:\CODE\Ets2 Mod V2`) or Linux host with `uv` (`>=0.11.31`) and Python `>=3.12`. All VFS and SII paths canonicalize to POSIX `/` with UTF-8 no-BOM LF hygiene regardless of host OS (`src/ets2_realism/vfs/types.py`, `src/ets2_realism/sii/hygiene.py`).
- Local ETS2 `1.62.3.3s` archives (`version.scs`, `def.scs`, `locale.scs`, `dlc_*.scs`) are required only for `ets2-realism baseline extract` and `@pytest.mark.local_ets2` tests.
- Local ProMods archives (`promods-{eu,me,ma,tgs}-*.scs`) and/or user map combos are required only for `ets2-realism package promods`, `ets2-realism compose-local`, and `@pytest.mark.local_promods` tests.

**Production:**
- GitHub Actions `ubuntu-latest` runners executing:
  - `.github/workflows/ci.yml` (offline quality gates & unit/contract tests).
  - `.github/workflows/phase-a-release.yml` (weekly Friday `06:00 UTC` online FX/fuel fetch, diff-gated Core Summer/Winter build, Offline SCS Workshop Validator, v1 snapshot publishing to `snapshots-latest` GitHub Release, and persistent `release/phase-a-weekly` PR for manual `SCS Workshop Uploader` `AppID 421800` handoff).
  - `.github/workflows/osm-speed-audit.yml` (monthly read-only OSM speed-limit drift advisory reporting via artifact + rolling `osm-audit` GitHub Issue).

---

*Stack analysis: 2026-11-26*
