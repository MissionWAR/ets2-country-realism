---
phase: 02
slug: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
status: complete
nyquist_compliant: true
tdd_mode: true
granularity: fine
wave_0_complete: true
---

# Phase 2 — Nyquist Validation Strategy

**Goal:** Enforce test-first (RED -> GREEN -> REFACTOR) verification, strict static typing (`basedpyright` strict), lint/format hygiene (`ruff`), deterministic cross-platform builds, full SCS Workshop offline validation (`00001`–`00010` + `WARN 00001`/`00002` + `1.62` realism invariants), and canonical SHA-256 diff-gate contracts across every task in Phase 2 (`02-01` through `02-05`).

---

## 1. Test Infrastructure & Shared Quality Gates

- **Framework:** `pytest>=9.2,<9.3` with `pytest-cov>=6,<8`, `testpaths = ["tests"]`, `pythonpath = ["src"]`, `--strict-markers`.
- **Runtime Dependencies Added in Wave 1 (`02-01-01`):** `tzdata>=2025.2` (`Apache-2.0`, verified `[OK]`) and `pillow>=12,<14` (`MIT-CMU`, verified `[OK]`), locked once online via `uv lock && uv sync --locked` so every subsequent task runs strictly offline (`--offline`).
- **Static & Test Gates (executed at every wave completion and in `.github/workflows/ci.yml`):**
  - `uv run --offline ruff check`
  - `uv run --offline ruff format --check`
  - `uv run --offline basedpyright` (`typeCheckingMode = "strict"`)
  - `uv run --offline pytest -q --tb=short`
- **CI Independence:** 100% of Phase 2 tests are CI-safe and require zero proprietary ETS2 game archives (`def.scs`/`locale.scs`), compiling purely from committed `data/baselines/ets2_1.62_def/*.json`, `data/laws/countries/<iso2>.json`, `data/mappings/ets2_countries.json`, and `assets/icons/{summer,winter}.jpg` (D-04, D-07).

---

## 2. Wave-by-Wave Sampling & Gate Schedule

| Wave | Plan(s) | Parallelism | Gate Executed After Wave |
|------|---------|-------------|--------------------------|
| **Wave 1** | `02-01` | Sequential root (locks `tzdata`+`pillow`, updates scaffold & registry) | `uv run --offline ets2v2 registry validate && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_cli_scaffold.py tests/test_baseline_contracts.py tests/test_registry_schema.py tests/test_registry_contracts.py -x` |
| **Wave 2** | `02-02` | Sequential (`SIM-02` timezone + `D-11` one-way schema decision checkpoint) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_registry_*.py -x` |
| **Wave 3** | `02-03` | Sequential (`SIM-03` clean-room synthesis, icons, dual packager) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_package_*.py tests/test_cli_scaffold.py -x` |
| **Wave 4** | `02-04` | Sequential (`PUB-01` independent Offline SCS Validator & `1.62` invariants) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_validate_*.py -x` |
| **Wave 5** | `02-05` | Sequential (`PUB-02`, `PUB-03` diff ledger, changelogs, Friday Phase A CI) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short` |

*Note on wave ordering:* Every plan extends `src/ets2v2/cli.py` and builds end-to-end verification atop the previous layer (e.g., `02-04` runs positive/mutation validation on real `02-03`-compiled Summer & Winter bundles while enforcing strict zero-import runtime DAG isolation of `src/ets2v2/validate/` from `ets2v2.package`), guaranteeing zero `files_modified` collisions in every wave.

---

## 3. Per-Task Verification Map

| Task ID | Plan | Wave | Req(s) | TDD / Mode | Test File(s) | Automated Verify Command | Failure Signal (`<fails_when>`) | Status |
|---------|------|------|--------|------------|--------------|--------------------------|---------------------------------|--------|
| `02-01-01` | `02-01` | 1 | `SIM-01` | `tracer` (RED -> GREEN, `costly` D-01) | `tests/test_cli_scaffold.py`, `tests/test_registry_schema.py` | `uv lock && uv sync --locked && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_cli_scaffold.py tests/test_registry_schema.py -x` | `tzdata`/`pillow` fail lock/sync, scaffold boundary fails, strict Pydantic models accept invalid inputs, or `registry validate` CLI fails | pass |
| `02-01-02` | `02-01` | 1 | `SIM-01` | `auto` (`tdd="true"`) | `tests/test_registry_contracts.py`, `tests/test_baseline_contracts.py` | `uv run --offline ets2v2 registry validate && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_cli_scaffold.py tests/test_baseline_contracts.py tests/test_registry_schema.py tests/test_registry_contracts.py -x` | Any of 36 law JSONs fails schema/baseline parity, misses statutory speed/DRL/axle rule, adds non-vanilla entries or raw `.sii`/`.sui` under `data/` | pass |
| `02-02-01` | `02-02` | 2 | `SIM-02` | `tracer` (RED -> GREEN) | `tests/test_registry_timezone.py` | `uv run --offline ruff check src/ets2v2/registry tests/test_registry_timezone.py && uv run --offline ruff format --check src/ets2v2/registry tests/test_registry_timezone.py && uv run --offline basedpyright src/ets2v2/registry tests/test_registry_timezone.py && uv run --offline pytest tests/test_registry_timezone.py -x` | Wrong Summer/Winter offsets, invalid `@@tz_cet@@`/`@@tz_wet@@`, numeric `+03` leak on `TR`/`JO`/`SY`, Windows `tzdata` lookup error, or `leftside_traffic` guard failure | pass |
| `02-02-02` | `02-02` | 2 | `SIM-02` | `checkpoint:decision` (`one-way` D-11) | N/A (human decision gate) | Human approval of `realism-snapshot-{summer,winter}.json` v1 and `state/published.json` v1 schemas | Maintainer requests schema changes before locking v1 models | pass (`approve-v1`) |
| `02-02-03` | `02-02` | 2 | `SIM-02` | `auto` (`tdd="true"`, `one-way` D-11) | `tests/test_registry_snapshot.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_registry_timezone.py tests/test_registry_snapshot.py tests/test_registry_schema.py tests/test_registry_contracts.py -x` | Snapshot deviates from locked v1 schema, non-deterministic JSON bytes, or `--date` override failure | pass |
| `02-03-01` | `02-03` | 3 | `SIM-03` | `tracer` (RED -> GREEN, `costly` D-04) | `tests/test_package_synthesize.py` | `uv run --offline ruff check src/ets2v2/package tests/test_package_synthesize.py && uv run --offline ruff format --check src/ets2v2/package tests/test_package_synthesize.py && uv run --offline basedpyright src/ets2v2/package tests/test_package_synthesize.py && uv run --offline pytest tests/test_package_synthesize.py -x` | Synthesized `.sui`/`speed_limits.sii` fails `validate_sii_hygiene()`, drops `regions[]`/`secondary_time_zone*`/`train`/`tram`/`slow_road`/quoting, mutates `fuel_price`, or fails parse round-trip | pass |
| `02-03-02` | `02-03` | 3 | `SIM-03` | `auto` (`tdd="true"`) | `tests/test_package_icons_metadata.py` | `uv run --offline ruff check src/ets2v2/package scripts/generate_icons.py tests/test_package_icons_metadata.py && uv run --offline ruff format --check src/ets2v2/package scripts/generate_icons.py tests/test_package_icons_metadata.py && uv run --offline basedpyright src/ets2v2/package tests/test_package_icons_metadata.py && uv run --offline pytest tests/test_package_icons_metadata.py -x` | Icons fail `276x162`/JPEG/EXIF/ICC/`<1 MiB` checks, `scripts/generate_icons.py` has lint/format issues, Workshop `manifest.sii` leaks `display_name`/`compatible_versions[]`, or `description.txt` embeds volatile dates | pass |
| `02-03-03` | `02-03` | 3 | `SIM-03` | `auto` (`tdd="true"`) | `tests/test_package_builder.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_package_synthesize.py tests/test_package_icons_metadata.py tests/test_package_builder.py tests/test_cli_scaffold.py -x` | Wrong 76-file Workshop tree, `universal.zip` beside `universal/`, `def/country.sii` emitted, non-deterministic ZIP hash, or `ZipArchive` mount failure | pass |
| `02-04-01` | `02-04` | 4 | `PUB-01` | `tracer` (RED -> GREEN) | `tests/test_validate_workshop.py` | `uv run --offline ruff check src/ets2v2/validate src/ets2v2/cli.py tests/test_validate_workshop.py && uv run --offline ruff format --check src/ets2v2/validate src/ets2v2/cli.py tests/test_validate_workshop.py && uv run --offline basedpyright src/ets2v2/validate src/ets2v2/cli.py tests/test_validate_workshop.py && uv run --offline pytest tests/test_validate_workshop.py tests/test_cli_scaffold.py -x` | `ets2v2.validate` imports `ets2v2.package`, positive Summer/Winter validation fails, or `validate workshop`/`local` CLI fails | pass |
| `02-04-02` | `02-04` | 4 | `PUB-01` | `auto` (`tdd="true"`) | `tests/test_validate_workshop.py` | `uv run --offline ruff check src/ets2v2/validate tests/test_validate_workshop.py && uv run --offline ruff format --check src/ets2v2/validate tests/test_validate_workshop.py && uv run --offline basedpyright src/ets2v2/validate tests/test_validate_workshop.py && uv run --offline pytest tests/test_validate_workshop.py -x` | Any SCS `00001`–`00010` or `WARN 00001`/`00002` negative fixture passes or clean builds fail falsely | pass |
| `02-04-03` | `02-04` | 4 | `PUB-01` | `auto` (`tdd="true"`) | `tests/test_validate_invariants.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_validate_workshop.py tests/test_validate_invariants.py -x` | Any `1.62` realism regression (`Estonia`, `leftside_traffic`, `regions[]`, `iceland` 60t/80, `train`/`tram`, `@@tz_cet@@`) passes validator | pass |
| `02-05-01` | `02-05` | 5 | `PUB-02` | `tracer` (RED -> GREEN) | `tests/test_publish_ledger.py` | `uv run --offline ruff check src/ets2v2/publish tests/test_publish_ledger.py && uv run --offline ruff format --check src/ets2v2/publish tests/test_publish_ledger.py && uv run --offline basedpyright src/ets2v2/publish tests/test_publish_ledger.py && uv run --offline pytest tests/test_publish_ledger.py -x` | `package_version` change mutates canonical SHA-256, single-byte payload change missed, ISO-week/hotfix bumping fails, or `PublishedLedger` schema fails | pass |
| `02-05-02` | `02-05` | 5 | `PUB-02`, `PUB-03` | `auto` (`tdd="true"`) | `tests/test_publish_release.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_publish_ledger.py tests/test_publish_release.py -x` | No-op run bumps ledger, single-edition edit triggers both editions, validation error fails to block ledger update, or `publish release` CLI fails | pass |
| `02-05-03` | `02-05` | 5 | `PUB-03` | `auto` (`tdd="true"`, `costly` D-10) | `tests/test_publish_workflow.py` + full suite | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short` | `phase-a-release.yml` fails cron/dispatch/permission/no-secret/injection-safety checks, `ci.yml` regresses, or any Phase 1/2 test fails | pass |

---

## 4. Requirement Coverage Matrix

| Requirement | Owning Plan(s) & Tasks | Key Invariants Verified |
|-------------|------------------------|-------------------------|
| **SIM-01** | `02-01` (`02-01-01`, `02-01-02`) | Strictly 36 Vanilla+DLC `data/laws/countries/<iso2>.json` + `data/mappings/ets2_countries.json`; `ConfigDict(strict=True, frozen=True, extra="forbid")`; seasonal speed drops (`FI`, `EE`, `LT`), seasonal DRL (`HR`), statutory DRL fixes (`NL`, `CH`, `AL`, `TR`, `RO`), statutory speed fixes (`AT`, `HU`, `IS` 80 km/h, `LT`, `TR`), UK `mph`, zero axle downgrades (`IS` 5-axle 60t, `FI` 10-axle 105t), zero raw `.sii`/`.sui` under `data/` |
| **SIM-02** | `02-02` (`02-02-01`, `02-02-02`, `02-02-03`) | Stdlib `zoneinfo` + `tzdata` on July 15 / January 15 (+ `--date` override); numeric `tzname()` normalization (`Europe/Istanbul -> @@tz_trt@@`, `Asia/Amman`/`Asia/Damascus -> AST`); exact 12-key `@@tz_*@@` whitelist from `locales.json`; plain `"CET"`/`"WET"`/`"AST"` elsewhere; Russia Kaliningrad secondary TZ preserved; `leftside_traffic` immutability guard; locked `schema_version: 1` `realism-snapshot-{summer,winter}.json` |
| **SIM-03** | `02-03` (`02-03-01`, `02-03-02`, `02-03-03`) | Pure clean-room synthesis of all 36 `.sui` and 36 `speed_limits.sii` without `def.scs`; zero `def/country.sii`; `1.62` `fuel_price`, `regions[]`, `secondary_time_zone*`, `train`/`tram`, `slow_road`, `iso_country_code_quoted` preserved; checked-in clean-room `276x162` EXIF/ICC-stripped `assets/icons/{summer,winter}.jpg`; dual `dist/workshop/{summer,winter}/` (no `universal.zip` beside `universal/`, Workshop `manifest.sii` omitting `display_name`/`compatible_versions[]`) + deterministic `dist/local/ETS2V2_Core_{Summer,Winter}.zip` |
| **PUB-01** | `02-04` (`02-04-01`, `02-04-02`, `02-04-03`) | Strict zero-import independence of `ets2v2.validate` from `ets2v2.package`; hard enforcement of all SCS codes `00001`–`00010` and `WARN 00001`/`00002` across Workshop roots & local ZIPs (raw `ZipInfo.filename` traversal/`\` checks, `276x162` JPEG `< 1 MiB` + `MAX_IMAGE_PIXELS` bomb cap, UTF-8 LF `< 1 MiB` `description.txt`, `validate_sii_hygiene()`, `<=12`-char unit segments, `<=2` valid categories, zero `3nK`, zero ZIP-as-`.scs`); full `1.62` realism invariant enforcement |
| **PUB-02** | `02-05` (`02-05-01`, `02-05-02`) | Length-prefixed canonical payload SHA-256 normalizing `manifest.sii` `package_version` to `"__CANONICAL__"`; independent `summer`/`winter` tracking in `state/published.json` (`schema_version: 1`); ISO-week `1.62-YYYY.WW` (`.2`/`.3` hotfix) bumping strictly on canonical content change; clean no-op exit when unchanged; deterministic `CHANGELOG_SUMMER.md` and `CHANGELOG_WINTER.md` |
| **PUB-03** | `02-05` (`02-05-02`, `02-05-03`) | `.github/workflows/phase-a-release.yml` scheduled Friday `06:00 UTC` (`0 6 * * 5`) + `workflow_dispatch` (`force_run` boolean via `env:`); zero Steam secrets; least-privilege `contents: write` + `pull-requests: write` isolated from read-only `ci.yml`; hard offline validation before upload; `actions/upload-artifact@v4` uploading Summer/Winter bundles, v1 snapshots, and changelogs; single persistent Release PR (`release/phase-a-weekly`) via built-in `gh` CLI |

---

## 5. CI vs Local Verification Policy

1. **GitHub Actions CI (`ubuntu-latest` via `.github/workflows/ci.yml` and `.github/workflows/phase-a-release.yml`):**
   - Every Phase 2 unit, contract, synthesizer, packager, validator, diff-ledger, and workflow test runs unconditionally in CI with `uv sync --locked` and zero proprietary ETS2 archives.
   - `.github/workflows/ci.yml` remains strictly read-only (`contents: read`) on `push`/`pull_request`; `.github/workflows/phase-a-release.yml` executes only on Friday `06:00 UTC` schedule or manual `workflow_dispatch`.
2. **Local Maintainer Workstation (Windows `pwsh`):**
   - After Plan `02-01` Task 1 locks `tzdata>=2025.2` and `pillow>=12,<14` into `uv.lock`, every local verification runs offline via `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short`.
   - **End-of-phase optional manual spot checks (`human_verify_mode: end-of-phase`):**
     - Run `uv run --offline ets2v2 publish release --out-dir dist --changelogs-dir build/changelogs` and inspect `dist/workshop/{summer,winter}/`, `dist/local/ETS2V2_Core_{Summer,Winter}.zip`, and `dist/snapshots/realism-snapshot-{summer,winter}.json`.
     - Optionally drop `dist/local/ETS2V2_Core_Summer.zip` or `ETS2V2_Core_Winter.zip` into ETS2 `1.62.3.3s` `mod/` (or load `dist/workshop/{summer,winter}/` in `SCS Workshop Uploader` `AppID 421800` when installed) and verify zero warnings in `game.log.txt`.
