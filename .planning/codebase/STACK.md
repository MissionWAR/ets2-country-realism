# Technology Stack

**Analysis Date:** 2026-11-16

## Languages

**Primary:**
- Python `>=3.12` (verified `3.12.13` in local `.venv`, `"3.12"` in `.github/workflows/ci.yml`) - All production modules (`src/ets2v2/`) and tests (`tests/`). Use `from __future__ import annotations`, PEP 604 `X | Y` unions, `collections.abc` abstractions, and strict type annotations across every module.

**Secondary:**
- TOML - Package configuration (`pyproject.toml`) and deterministic dependency lockfile (`uv.lock`).
- JSON - Clean-room extracted game baselines (`data/baselines/ets2_1.62_def/*.json`) and GSD orchestration config (`.planning/config.json`).
- YAML - GitHub Actions CI pipeline definition (`.github/workflows/ci.yml`).
- SCS SII / SUI (`SiiNunit` and headerless `.sui`/`.sii` fragments) - Domain asset format parsed, inspected, and surgically rewritten by `src/ets2v2/sii/`.

## Runtime

**Environment:**
- CPython `3.12.13` locally on Windows (`win_amd64`) and Python `3.12` on GitHub Actions `ubuntu-latest` (`.github/workflows/ci.yml`).
- Declared constraint: `requires-python = ">=3.12"` in `pyproject.toml` and `uv.lock`.

**Package Manager & Build System:**
- `uv` (`0.11.31` verified locally; provisioned via `astral-sh/setup-uv@v5` in `.github/workflows/ci.yml`).
- Lockfile: `uv.lock` present (lock `version = 1`, `revision = 3`, `17` resolved packages). Always install and run via `uv sync --locked` and `uv run`.
- Build backend: `hatchling>=1.27,<2` (`build-backend = "hatchling.build"` in `pyproject.toml`), targeting `[tool.hatch.build.targets.wheel] packages = ["src/ets2v2"]` with editable local metadata (`ets2-world-realism == 0.1.0`) and PEP 561 marker `src/ets2v2/py.typed`.

## Frameworks

**Core Modeling & CLI:**
- `pydantic` `2.14.3` (`>=2.14,<3` in `pyproject.toml`) - Strict immutable (`ConfigDict(frozen=True)`) domain and baseline schemas in `src/ets2v2/vfs/types.py`, `src/ets2v2/sii/country.py`, `src/ets2v2/sii/speed_limits.py`, `src/ets2v2/sii/sign_board.py`, `src/ets2v2/sii/localization.py`, and `src/ets2v2/baseline/models.py`.
- Python stdlib `argparse` (`src/ets2v2/cli.py`) - CLI parser exposed via `[project.scripts]` entrypoint `ets2v2 = "ets2v2.cli:main"` (`ets2v2 vfs inspect`, `ets2v2 baseline extract`).

**Testing:**
- `pytest` `9.2.0` (`>=9.2,<9.3` in `pyproject.toml`) - Test runner configured under `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = ["-ra", "--strict-markers"]`, marker `local_ets2`).
- `pytest-cov` `7.1.0` (`>=6,<8` in `pyproject.toml`, backed by `coverage` `7.17.3` in `uv.lock`) - Coverage plugin available in the dev dependency group.

**Linting, Formatting & Static Analysis:**
- `ruff` `0.17.5` (`>=0.16` in `pyproject.toml`) - Combined linter and formatter (`ruff check`, `ruff format --check`) configured in `[tool.ruff]` and `[tool.ruff.lint]`.
- `basedpyright` `1.40.2` (`>=1.40,<2` in `pyproject.toml`, backed by `nodejs-wheel-binaries` `24.19.0` in `uv.lock`) - Strict static type checker configured in `[tool.basedpyright]` (`typeCheckingMode = "strict"`).

## Key Dependencies

**Critical Runtime Dependencies (Implemented — Phase 1):**
- `pydantic` `2.14.3` (transitives in `uv.lock`: `pydantic-core` `2.50.4`, `annotated-types` `0.8.0`, `typing-extensions` `4.16.0`, `typing-inspection` `0.4.5`) - Enforces field typing, frozen models, and deterministic JSON serialization/validation (`model_dump(mode="json")`, `model_validate_json()`).
- Python 3.12 Standard Library Primitives (zero C-extension or GPL dependencies):
  - `struct`, `zlib`, `zipfile` (`src/ets2v2/vfs/cityhash.py`, `src/ets2v2/vfs/hashfs.py`, `src/ets2v2/vfs/zip_archive.py`) - Clean-room MIT Google CityHash64 1.0.3 path hashing, HashFS v1/v2 container parsing, and bounded ZIP reading (`MAX_V2_TABLE_BYTES = 64 MiB`, `MAX_ENTRY_DECOMPRESSED_BYTES = 128 MiB`, `MAX_ZIP_ENTRY_BYTES = 128 MiB`).
  - `os`, `pathlib` (`src/ets2v2/vfs/dir_archive.py`, `src/ets2v2/vfs/types.py`, `src/ets2v2/baseline/extractor.py`) - Cross-platform POSIX VFS path normalization (`normalize_vfs_path()`) and symlink/NTFS-junction containment checks.
  - `re`, `dataclasses`, `bisect`, `math` (`src/ets2v2/sii/lexer.py`, `src/ets2v2/sii/document.py`, `src/ets2v2/sii/hygiene.py`, `src/ets2v2/sii/country.py`) - Linear structural SII/SUI scanner (`O(n)`), span-preserving surgical mutations, IEEE-754 `&hex` float decoding, and SCS hygiene assertions.
  - `json`, `hashlib`, `contextlib` (`src/ets2v2/baseline/extractor.py`, `src/ets2v2/cli.py`) - Deterministic UTF-8 no-BOM LF JSON serialization and SHA-256 verification.

**Dev / Quality Gate Dependencies (Locked in `uv.lock`):**
- `basedpyright` `1.40.2` - Strict type verification across `src` and `tests`.
- `ruff` `0.17.5` - Style and lint enforcement (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`).
- `pytest` `9.2.0` (transitives: `iniconfig` `2.3.1`, `packaging` `26.3`, `pluggy` `1.7.0`, `pygments` `2.21.0`, `colorama` `0.4.6` on `win32`) & `pytest-cov` `7.1.0` - Unit, contract, and `@pytest.mark.local_ets2` live-archive verification.

**Licensing Compliance:**
- Repository package license is `MIT` (`pyproject.toml`). All `17` locked packages in `uv.lock` use permissive licenses (`MIT`, `BSD`, `Apache-2.0`, `PSF-2.0`); copyleft GPL archive extractors (`TruckLib`, `easy-scsmodmanager`) and `cityhash` C-wheel packages are explicitly excluded (`.planning/research/STACK.md`).

**Planned Downstream Dependencies (Not Yet in `pyproject.toml` / `uv.lock`; Phases 2–5):**
- `zoneinfo` (stdlib) + `tzdata` (PyPI, required on Windows) - Planned in Phase 2 (`SIM-02`) for seasonal Summer/Winter DST UTC offset derivation (`.planning/ROADMAP.md`, `.planning/research/SUMMARY.md`).
- `pillow` (`>=12,<14`) - Planned in Phase 2 (`SIM-03`, `PUB-01`) strictly for `276x162` `.jpg` Workshop icon validation/generation; explicitly prohibited for `.dds` totem baking (`.planning/research/STACK.md`).
- `httpx` (`>=0.28,<0.29`) and `openpyxl` (`>=3.1,<4`) - Planned in Phases 3 and 5 (`DAT-01`, `DAT-02`, `GLB-01`) for FX APIs and EC Weekly Oil Bulletin `.xlsx` parsing (`.planning/research/STACK.md`).
- `beautifulsoup4` + `lxml` - Conditionally deferred to Phase 5 (`GLB-02`) only if Tier 2 guarded portals require HTML scraping (`.planning/research/STACK.md`).

## Configuration

**Package, Tooling & Test Configuration (`pyproject.toml`):**
- `[tool.ruff]`: `target-version = "py312"`, `line-length = 100`, `src = ["src", "tests"]`, `extend-exclude = [".planning", ".agents"]`, `[tool.ruff.lint] select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`.
- `[tool.basedpyright]`: `pythonVersion = "3.12"`, `typeCheckingMode = "strict"`, `include = ["src", "tests"]`, `venvPath = "."`, `venv = ".venv"`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["src"]`, `addopts = ["-ra", "--strict-markers"]`, `markers = ["local_ets2: tests requiring local ETS2 1.62.3.3s archives"]`.

**Repository Line-Ending & Ignore Rules:**
- `.gitattributes` enforces `* text=auto eol=lf` (`fixtures/** -text`, binary treatment for `*.scs`, `*.dds`, `*.jpg`, `*.png`).
- `.gitignore` excludes `.venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`, `build/`, `dist/`, `out/`, `raw/`, `vendor/`, `.DS_Store`, `Thumbs.db`, `*.tmp`, `*.bak`.

**Planning & Skill Configuration (`.planning/config.json`, `.agents/`):**
- `.planning/config.json` configures `project_code: "ETS2V2"`, `model_profile: "quality"`, `granularity: "fine"`, `git.branching_strategy: "phase"`, `workflow.tdd_mode: true`, `workflow.security_enforcement: true` (`security_asvs_level: 2`), `workflow.build_command` (`"uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright"`), and `workflow.test_command` (`"uv run --offline pytest -q --tb=short"`).
- `.planning/config.json` binds `agent_skills` to the vendored SCS Modding Wiki knowledge base at `.agents/skills/scs-modding-wiki/SKILL.md` (backed by `index.json`, `sources.json`, and 162 markdown reference pages under `.agents/skills/scs-modding-wiki/docs/`).

**Environment Variables:**
- `ETS2_GAME_DIR` - Optional override for the local ETS2 `1.62.3.3s` install directory in `resolve_game_dir()` (`src/ets2v2/baseline/extractor.py`). No `.env` files exist in the repository.

## Platform Requirements

**Development:**
- Cross-platform Windows (`D:\CODE\Ets2 Mod V2`) or Linux host with `uv` (`>=0.11.31`) and Python `>=3.12`. All VFS and SII paths canonicalize to POSIX `/` regardless of host OS (`src/ets2v2/vfs/types.py`, `src/ets2v2/sii/hygiene.py`).
- A local ETS2 `1.62.3.3s` Steam installation (`version.scs`, `def.scs`, `locale.scs`, `dlc_*.scs`) is required only when running `ets2v2 baseline extract` (`src/ets2v2/cli.py`) or the `@pytest.mark.local_ets2` tests (`tests/test_baseline_contracts.py`).
- Keep `src/ets2v2/` scoped strictly to active implemented subsystems (`vfs`, `sii`, `baseline`, `cli.py`); `tests/test_cli_scaffold.py` explicitly rejects premature placeholder packages (`fetch`, `normalize`, `merge`, `validate`, `package`).

**Production / CI:**
- GitHub Actions `ubuntu-latest` (`.github/workflows/ci.yml`) running `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run basedpyright`, and `uv run pytest` offline against committed clean-room JSON baselines under `data/baselines/ets2_1.62_def/` with zero external binaries or Steam/ETS2 installs required.

---

*Stack analysis: 2026-11-16*
