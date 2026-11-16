---
phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine
plan: "01"
subsystem: infra
tags: [python, uv, hatchling, pydantic, ruff, basedpyright, pytest, github-actions]

requires: []
provides:
  - "Clean-room Python 3.12+ package scaffold under src/ets2v2/ with hatchling build backend"
  - "Locked uv.lock dependency graph (pydantic 2.14.3, basedpyright 1.40.2, ruff 0.17.5, pytest 9.2.0, pytest-cov 7.1.0)"
  - "CLI entrypoint ets2v2 (ets2v2.cli:main, build_parser)"
  - "Day-1 CI workflow (.github/workflows/ci.yml) mirroring ruff, basedpyright strict, and pytest"
affects: [01-02, 01-03, 01-04, phase-2, phase-3, phase-4, phase-5]

tech-stack:
  added: [hatchling==1.33.0, pydantic==2.14.3, basedpyright==1.40.2, pytest==9.2.0, pytest-cov==7.1.0, ruff==0.17.5]
  patterns: [active-phase-only scaffolding, strict basedpyright typing, ruff E/F/I/UP/B/SIM/RUF, UTF-8 no-BOM LF hygiene]

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - src/ets2v2/__init__.py
    - src/ets2v2/py.typed
    - src/ets2v2/cli.py
    - tests/test_cli_scaffold.py
    - .github/workflows/ci.yml
  modified: []

key-decisions:
  - "Added extend-exclude = [\".planning\", \".agents\"] under [tool.ruff] in pyproject.toml so `uv run ruff format --check` excludes planning/skills markdown snippets without altering CI arguments."

patterns-established:
  - "Active-phase boundary guard in tests/test_cli_scaffold.py prevents premature Phase 2-5 subpackage creation."

requirements-completed: [VFS-01, VFS-02, SII-01, SII-02]

duration: 7min
completed: 2026-11-16
---

# Phase 1 Plan 01: Package Scaffold, Quality Gates & Day-1 CI Summary

**Python 3.12+ (`uv` + `hatchling`) package `ets2-world-realism` scaffolded with strict `basedpyright`, `ruff`, `pytest`, deterministic `uv.lock`, and Day-1 GitHub Actions CI.**

## Accomplishments
- Created PEP 621/639 `pyproject.toml` with `hatchling>=1.27,<2`, `requires-python = ">=3.12"`, runtime `pydantic>=2.14,<3`, and dev gates (`basedpyright>=1.40,<2`, `pytest>=9.2,<9.3`, `pytest-cov>=6,<8`, `ruff>=0.16`).
- Created active-phase-only `src/ets2v2/` entrypoint modules (`__init__.py`, `py.typed`, `cli.py`) exposing `ets2v2 --version` (`0.1.0`) and `--help`.
- Generated deterministic `uv.lock` resolving 17 packages (`pydantic==2.14.3`, `basedpyright==1.40.2`, `pytest==9.2.0`, `pytest-cov==7.1.0`, `ruff==0.17.5`) and synced `.venv`.
- Added `.github/workflows/ci.yml` (`ubuntu-latest`, `permissions: contents: read`, `astral-sh/setup-uv@v5`, `uv sync --locked`, `ruff check`, `ruff format --check`, `basedpyright`, `pytest`).
- Verified red-first TDD transitions and full green pass (`9 passed` in `tests/test_cli_scaffold.py`, `0` ruff errors, `0` basedpyright errors).

## Deviations from Plan
- Added `extend-exclude = [".planning", ".agents"]` to `[tool.ruff]` in `pyproject.toml` after `uv run ruff format --check` flagged `.planning/research/ARCHITECTURE.md` (Ruff `0.17.5` checks `.md` code blocks unless excluded).

## Verification
- `uv lock --check --offline`: exit 0 (`Resolved 17 packages`)
- `uv sync --locked --offline`: exit 0
- `uv run ruff check`: exit 0 (`All checks passed!`)
- `uv run ruff format --check`: exit 0 (`3 files already formatted`)
- `uv run basedpyright`: exit 0 (`0 errors, 0 warnings, 0 notes`)
- `uv run pytest tests/test_cli_scaffold.py -x`: exit 0 (`9 passed`)
- `uv run ets2v2 --version`: exit 0 (`ets2v2 0.1.0`)

---
*Phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine*
*Completed: 2026-11-16*
