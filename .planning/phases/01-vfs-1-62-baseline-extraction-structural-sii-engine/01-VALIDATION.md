---
phase: 01
slug: 01-vfs-1-62-baseline-extraction-structural-sii-engine
status: ready
nyquist_compliant: true
tdd_mode: true
granularity: fine
wave_0_complete: true
---

# Phase 1 — Nyquist Validation Strategy

**Goal:** Enforce test-first (RED -> GREEN -> REFACTOR) verification, strict static typing (`basedpyright` strict), lint/format hygiene (`ruff`), and deterministic clean-room baseline contracts across every task in Phase 1 (`01-01` through `01-04`).

---

## 1. Test Infrastructure & Shared Quality Gates

- **Framework:** `pytest>=9.2,<9.3` with `pytest-cov>=6,<8`, `testpaths = ["tests"]`, `pythonpath = ["src"]`, `--strict-markers`.
- **Static Gates (executed at every wave completion and in `.github/workflows/ci.yml`):**
  - `uv sync --locked`
  - `uv run ruff check`
  - `uv run ruff format --check`
  - `uv run basedpyright` (`typeCheckingMode = "strict"`)
  - `uv run pytest`
- **Custom Marker:** `@pytest.mark.local_ets2` — runs live verification against installed ETS2 `1.62.3.3s` archives (`def.scs`, `locale.scs`, `version.scs`); automatically skipped via `pytest.mark.skipif` on CI runners lacking proprietary game archives.

---

## 2. Wave-by-Wave Sampling & Gate Schedule

| Wave | Plan(s) | Parallelism | Gate Executed After Wave |
|------|---------|-------------|--------------------------|
| **Wave 1** | `01-01` | Sequential root | `uv sync --locked && uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run pytest tests/test_cli_scaffold.py` |
| **Wave 2** | `01-02`, `01-04` | Parallel (`files_modified` strictly disjoint) | `uv run pytest tests/test_vfs_*.py tests/test_sii_*.py && uv run ruff check && uv run ruff format --check && uv run basedpyright` |
| **Wave 3** | `01-03` | Sequential integration | `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def --check && uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright` |

---

## 3. Per-Task Verification Map

| Task ID | Plan | Wave | Req(s) | TDD / Mode | Test File(s) | Automated Verify Command | Failure Signal (`<fails_when>`) | Status |
|---------|------|------|--------|------------|--------------|--------------------------|---------------------------------|--------|
| `01-01-01` | `01-01` | 1 | `VFS-01`, `VFS-02`, `SII-01`, `SII-02` | `tracer` (RED -> GREEN) | `tests/test_cli_scaffold.py` | `uv run --no-project --python 3.12 python -c "import pathlib, sys, tomllib; data = tomllib.loads(pathlib.Path('pyproject.toml').read_text('utf-8')); assert data['project']['scripts']['ets2v2'] == 'ets2v2.cli:main'; assert 'hatchling>=1.27,<2' in data['build-system']['requires']; assert 'pytest-cov>=6,<8' in data['dependency-groups']['dev']; sys.path.insert(0, 'src'); from ets2v2.cli import main; assert main(['--version']) == 0"` | Invalid TOML, missing script/bounds, or CLI tracer import/exit failure | pending |
| `01-01-02` | `01-01` | 1 | `VFS-01`, `VFS-02`, `SII-01`, `SII-02` | `auto` (`tdd="true"`) | `tests/test_cli_scaffold.py` | `uv sync --locked && uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run pytest tests/test_cli_scaffold.py -x` | `uv.lock` drift, CI workflow assertion fail, or ruff/basedpyright/pytest error | pending |
| `01-02-01` | `01-02` | 2 | `VFS-01` | `tracer` (RED -> GREEN) | `tests/test_vfs_cityhash.py`, `tests/test_vfs_archives.py` | `uv run pytest tests/test_vfs_cityhash.py tests/test_vfs_archives.py -k "cityhash or hashfs or 3nk" -x && uv run ruff check src/ets2v2/vfs tests/test_vfs_cityhash.py tests/test_vfs_archives.py && uv run basedpyright src/ets2v2/vfs/cityhash.py src/ets2v2/vfs/types.py src/ets2v2/vfs/hashfs.py tests/test_vfs_cityhash.py tests/test_vfs_archives.py` | CityHash64 1.0.3 vector/salt mismatch, HashFS v1/v2 or non-`0x80`/`0x81` skip failure, or `3nK` diagnostic failure | pending |
| `01-02-02` | `01-02` | 2 | `VFS-01` | `auto` (`tdd="true"`) | `tests/test_vfs_archives.py` | `uv run pytest tests/test_vfs_archives.py -x && uv run ruff check src/ets2v2/vfs tests/test_vfs_archives.py && uv run basedpyright src/ets2v2/vfs tests/test_vfs_archives.py` | ZIP, encrypted ZIP central-dir, directory traversal, `AEM!`, unknown magic, or unsupported compression failure | pending |
| `01-02-03` | `01-02` | 2 | `VFS-01` | `auto` (`tdd="true"`) | `tests/test_vfs_stack.py` | `uv run pytest tests/test_vfs_cityhash.py tests/test_vfs_archives.py tests/test_vfs_stack.py -x && uv run ruff check src/ets2v2/vfs tests/test_vfs_*.py && uv run ruff format --check src/ets2v2/vfs tests/test_vfs_*.py && uv run basedpyright src/ets2v2/vfs tests/test_vfs_*.py` | `VfsStack` layer priority, `base/` normalization, or empty `SiiNunit {}` stub shadowing failure | pending |
| `01-04-01` | `01-04` | 2 | `SII-01`, `SII-02` | `tracer` (RED -> GREEN) | `tests/test_sii_hygiene.py`, `tests/test_sii_document.py` | `uv run pytest tests/test_sii_hygiene.py tests/test_sii_document.py -x && uv run ruff check src/ets2v2/sii tests/test_sii_hygiene.py tests/test_sii_document.py && uv run basedpyright src/ets2v2/sii/hygiene.py src/ets2v2/sii/lexer.py src/ets2v2/sii/document.py tests/test_sii_hygiene.py tests/test_sii_document.py` | BOM/CRLF normalization, idempotency, `@include` col-0 / `[a-z0-9_]{1,12}` hygiene, or span edit failure | pending |
| `01-04-02` | `01-04` | 2 | `SII-01`, `SII-02` | `auto` (`tdd="true"`) | `tests/test_sii_country.py`, `tests/test_sii_speed_limits.py` | `uv run pytest tests/test_sii_country.py tests/test_sii_speed_limits.py -x && uv run ruff check src/ets2v2/sii tests/test_sii_country.py tests/test_sii_speed_limits.py && uv run basedpyright src/ets2v2/sii/country.py src/ets2v2/sii/speed_limits.py tests/test_sii_country.py tests/test_sii_speed_limits.py` | Country/speed-limit surgical patch failure or `regions[]`/`secondary_time_zone*`/`train`/`tram`/quoting mutation | pending |
| `01-04-03` | `01-04` | 2 | `SII-01` | `auto` (`tdd="true"`) | `tests/test_sii_boards_locales.py` | `uv run pytest tests/test_sii_*.py -x && uv run ruff check src/ets2v2/sii tests/test_sii_*.py && uv run ruff format --check src/ets2v2/sii tests/test_sii_*.py && uv run basedpyright src/ets2v2/sii tests/test_sii_*.py` | `sign_board_template` (`&hex` float/`nil`/`items[i]`) or `localization_db` parse failure | pending |
| `01-03-01` | `01-03` | 3 | `VFS-02` | `tracer` (RED -> GREEN) | `tests/test_baseline_extractor.py` | `uv run pytest tests/test_cli_scaffold.py tests/test_baseline_extractor.py -x && uv run ruff check src/ets2v2/baseline src/ets2v2/cli.py tests/test_baseline_extractor.py && uv run basedpyright src/ets2v2/baseline src/ets2v2/cli.py tests/test_baseline_extractor.py` | Synthetic HashFS v2 extraction, `fi_oulu_95` exclusion, `tz_`/`fp_` filtering, or CLI subcommand failure | pending |
| `01-03-02` | `01-03` | 3 | `VFS-02` | `auto` (`tdd="true"`, RED gate) | `tests/test_baseline_contracts.py` | `uv run ruff check tests/test_baseline_contracts.py && uv run ruff format --check tests/test_baseline_contracts.py && uv run basedpyright tests/test_baseline_contracts.py && uv run python -c "import subprocess; r = subprocess.run(['uv', 'run', 'pytest', 'tests/test_baseline_contracts.py', '-k', 'not local_ets2']); assert r.returncode != 0, 'Expected RED before baseline JSON extraction'"` | Test file has lint/type errors or fails to report RED prior to JSON baseline extraction | pending |
| `01-03-03` | `01-03` | 3 | `VFS-02` | `auto` (GREEN gate) | `tests/test_baseline_contracts.py` + full suite | `uv run ets2v2 baseline extract --out-dir data/baselines/ets2_1.62_def --check && uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright` | `--check` drift, raw `.sui`/`.sii` files under `data/`, or any pytest/ruff/basedpyright failure | pending |

---

## 4. Requirement Coverage Matrix

| Requirement | Owning Tasks | Key Invariants Verified |
|-------------|--------------|-------------------------|
| **VFS-01** | `01-01-01`, `01-01-02`, `01-02-01`, `01-02-02`, `01-02-03` | CityHash64 1.0.3 (`k3=0xc949d7c7509e6557`, `b""->k2`), HashFS v1/v2 (`version.scs` small tables, `locale.scs` seeded walk, deduplicated dirs, non-`0x80`/`0x81` skip), ZIP/dir readers, `VfsStack` (`base/`, empty `SiiNunit {}` shadowing), safe `3nK`/`AEM!`/unknown/encrypted-ZIP/unsupported-compression diagnostics |
| **VFS-02** | `01-01-01`, `01-01-02`, `01-03-01`, `01-03-02`, `01-03-03` | Deterministic extraction of `1.62.3.3s` into `data/baselines/ets2_1.62_def/*.json`: `36` countries, `36` speed limits, `461` fuel boards (`373` `@@fp_*@@` + `88` placeholders; highway signs excluded), `43` locales (`fr_qc` absent), `12` `tz_*`, `99` `fp_*`, zero raw `.sui`/`.sii` committed, `0` diff on `--check` |
| **SII-01** | `01-01-01`, `01-01-02`, `01-04-01`, `01-04-02`, `01-04-03` | Structural lexer/document engine (`SiiNunit` + headerless `.sui`/`.sii`, inline/next-line `{`, `#`/`//`/`/* */`, `@include`, `attr[]` & `attr[i]`, `&hex` float, `nil`); surgical edits preserving comments, `regions[]`, `secondary_time_zone*`, `train`/`tram`, `isl`/`"bih"` quoting, and inserting missing keys before `}` or trailing `@include` |
| **SII-02** | `01-01-01`, `01-01-02`, `01-04-01`, `01-04-02` | UTF-8 no-BOM + LF (`\n`) normalization on pass 1, zero byte diff on pass 2+ idempotent writes, POSIX `/` path validation (no `\` or `..`), column-0 `@include`, `[a-z0-9_]{1,12}` unit segment validation |

---

## 5. CI vs Local Verification Policy (`@pytest.mark.local_ets2` & Manual Checks)

1. **CI Runners (`ubuntu-latest` via `.github/workflows/ci.yml`):**
   - Proprietary ETS2 game archives (`def.scs`, `locale.scs`, `version.scs`) are **never** present on GitHub Actions runners.
   - All unit, synthetic binary HashFS v1/v2, ZIP, directory, SII/SUI round-trip, synthetic baseline extractor, and committed `data/baselines/ets2_1.62_def/*.json` contract tests run unconditionally in CI.
   - `@pytest.mark.local_ets2` tests automatically skip cleanly when `resolve_game_dir()` finds no local `def.scs`/`locale.scs`.
2. **Local Maintainer Workstation (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2` or `ETS2_GAME_DIR`):**
   - Running `uv run pytest` locally executes both CI-safe suites **and** `@pytest.mark.local_ets2` live-archive verification (verifying exact `0`-diff regeneration against `def.scs`/`locale.scs` and byte-preserving surgical round-trips across all 36 real `1.62.3.3s` country and speed-limit files in memory).
   - **Manual-only spot check (optional end-of-phase confirmation):** Inspect `uv run ets2v2 vfs inspect "D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\def.scs" --prefix def/country` and `git status` to confirm no temporary cache artifacts leaked outside gitignored `build/`.
