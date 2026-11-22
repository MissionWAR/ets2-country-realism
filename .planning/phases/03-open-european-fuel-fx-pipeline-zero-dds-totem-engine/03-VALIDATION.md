---
phase: 03
slug: 03-open-european-fuel-fx-pipeline-zero-dds-totem-engine
status: verified
nyquist_compliant: true
tdd_mode: true
granularity: fine
wave_0_complete: true
---

# Phase 3 — Nyquist Validation Strategy

**Goal:** Enforce test-first (`RED -> GREEN -> REFACTOR`) verification, strict static typing (`basedpyright` strict), lint/format hygiene (`ruff`), 4 AST-enforced offline DAG isolation walls, 100% offline mocked-HTTP (`httpx.MockTransport`) & in-memory OOXML (`openpyxl`) test coverage, hardened ASVS Level 2 security controls (SSRF allowlists, XXE rejection, OOXML caps, secret redaction, CI injection safety), full Option 4b Zero-DDS 43-locale / 460-board totem verification, and hard Offline SCS Validator invariants (`D-12`) across every task in Phase 3 (`03-01` through `03-04`).

---

## 1. Test Infrastructure & Shared Quality Gates

- **Framework:** `pytest>=9.2,<9.3` with `pytest-cov>=6,<8`, `testpaths = ["tests"]`, `pythonpath = ["src"]`, `--strict-markers`.
- **Dependencies Added in Wave 1 (`03-01-01`):** `httpx>=0.28,<0.29` (`BSD-3-Clause`, verified `[OK]`), `openpyxl>=3.1,<4` (`MIT`, verified `[OK]`), and dev typing stub `types-openpyxl>=3.1` (`Apache-2.0`, official typeshed), locked once online via `uv lock && uv sync --locked` so every subsequent command runs strictly offline (`--offline`).
- **Static & Test Gates (executed at every task/wave completion and in `.github/workflows/ci.yml`):**
  - `uv run --offline ruff check`
  - `uv run --offline ruff format --check`
  - `uv run --offline basedpyright` (`typeCheckingMode = "strict"`)
  - `uv run --offline pytest -q --tb=short -m "not local_ets2"` (per task commit; full suite incl. `@pytest.mark.local_ets2` per wave merge)
- **CI Offline Independence (`D-05`):** 100% of Phase 3 unit and integration tests run offline with zero live sockets using `httpx.MockTransport` and in-memory `openpyxl.Workbook` fixtures, plus committed `state/prices.lock.json` and `data/baselines/ets2_1.62_def/fuel_boards.json`. Only Plan `03-03` Task 1 (`ets2v2 baseline extract`) requires local ETS2 `1.62.3.3s` `def.scs` once on the maintainer workstation to refresh committed `fuel_boards.json` + `manifest.json`.

---

## 2. Wave-by-Wave Sampling & Gate Schedule

| Wave | Plan(s) | Parallelism | Gate Executed After Wave |
|------|---------|-------------|--------------------------|
| **Wave 1** | `03-01` | Sequential root (locks `httpx`+`openpyxl`+`types-openpyxl`, enforces 4 AST isolation walls, builds `normalize/` & `fetch/fx`) | `uv lock && uv sync --locked && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_cli_scaffold.py tests/test_normalize_fx.py tests/test_fetch_fx.py -x` |
| **Wave 2** | `03-02` | Sequential (`DAT-02`/`DAT-03` Tier 1 fuel collectors, circuit breakers, `ets2v2 fetch`, committed `state/prices.lock.json`, `snapshot.py` v1 injection) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_normalize_fuel.py tests/test_fetch_fuel.py tests/test_fetch_pipeline.py tests/test_registry_snapshot.py tests/test_cli_scaffold.py -x` |
| **Wave 3** | `03-03` | Sequential (`TOT-01` extended `fuel_boards.json` extraction, 460-board classifier, Option 4b Zero-DDS 43-locale compiler, `builder.py` wiring) | `uv run --offline ets2v2 baseline extract --check --out-dir data/baselines/ets2_1.62_def && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_sii_boards_locales.py tests/test_baseline_extractor.py tests/test_baseline_contracts.py tests/test_totem_compiler.py tests/test_package_builder.py tests/test_cli_scaffold.py -x` |
| **Wave 4** | `03-04` | Sequential (`TOT-02` 6-font SDF native-currency formatter, hard `D-12` validator invariants, `D-16` changelogs/metadata, Friday CI workflow) | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short` |

*Note on wave ordering:* Strictly sequential 4-wave ordering eliminates all `files_modified` collisions (`src/ets2v2/cli.py`, `src/ets2v2/normalize/__init__.py`, `src/ets2v2/fetch/__init__.py`, `src/ets2v2/package/totems.py`) and lets each wave verify end-to-end against the real outputs of the preceding layer.

---

## 3. Per-Task Verification Map

| Task ID | Plan | Wave | Req(s) | Threat Ref(s) | TDD / Mode | Test File(s) | Automated Verify Command | Failure Signal (`<fails_when>`) | Status |
|---------|------|------|--------|---------------|------------|--------------|--------------------------|---------------------------------|--------|
| `03-01-01` | `03-01` | 1 | `DAT-01` | `T-03-03`, `T-03-05`, `T-03-SC` | `tracer` (RED -> GREEN, `costly` D-05/D-13) | `tests/test_cli_scaffold.py`, `tests/test_normalize_fx.py` | `uv lock && uv sync --locked && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_cli_scaffold.py tests/test_normalize_fx.py -x` | `httpx`/`openpyxl`/`types-openpyxl` fail lock/sync, any of 4 AST isolation walls fail, 39-territory currency map misses `BG=EUR` or `IE`/`CY`/`MT`, FX validator accepts inverted or `>10%` divergent rates, or staleness checks fail | verified |
| `03-01-02` | `03-01` | 1 | `DAT-01` | `T-03-01`, `T-03-02`, `T-03-04` | `auto` (`tdd="true"`) | `tests/test_fetch_fx.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_cli_scaffold.py tests/test_normalize_fx.py tests/test_fetch_fx.py -x` | Frankfurter v2 flat JSON, ECB XML without RUB, fawazahmed0 mirror fallback, or CBR `windows-1251`/comma parser fails; SSRF/XXE/secret-redaction guards fail; or `ets2v2 fetch --fx-only` fails | verified |
| `03-02-01` | `03-02` | 2 | `DAT-02`, `DAT-03` | `T-03-06`, `T-03-08`, `T-03-09` | `tracer` (RED -> GREEN) | `tests/test_normalize_fuel.py`, `tests/test_fetch_fuel.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_normalize_fuel.py tests/test_fetch_fuel.py -x` | `0.01–5.00 EUR/L` or `±25%` WoW circuit breaker fails, D-02 secondary spreads deviate, EC WOB SSRF/OOXML cap or `/1000` / `EL->GR` parsing fails, or 39-territory baseline seed is incomplete | verified |
| `03-02-02` | `03-02` | 2 | `DAT-02` | `T-03-06`, `T-03-07`, `T-03-09` | `auto` (`tdd="true"`) | `tests/test_fetch_fuel.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_fetch_fuel.py -x` | Any of the 7 national collectors (`UK DESNZ`, `NO SSB 09654`, `FR`, `DE` Tankerkönig, `ES` MITECO, `IT` MIMIT, `NL` CBS) mishandles unit scaling, comma decimals, banner/isSelf, daily Perioden, SSRF allowlist, keyless DE fallback, or leaks `TANKERKOENIG_API_KEY` | verified |
| `03-02-03` | `03-02` | 2 | `DAT-02`, `DAT-03` | `T-03-10`, `T-03-11` | `auto` (`tdd="true"`) | `tests/test_fetch_pipeline.py`, `tests/test_registry_snapshot.py` | `uv run --offline ets2v2 fetch --seed-offline --lock-path state/prices.lock.json --dry-run --json && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_normalize_fuel.py tests/test_fetch_fuel.py tests/test_fetch_pipeline.py tests/test_registry_snapshot.py tests/test_cli_scaffold.py -x` | Pipeline outage exit codes (`D-08`) or merge precedence fail, committed `state/prices.lock.json` misses any of 39 territories, or `RealismSnapshot` v1 breaks `extra="forbid"` or leaks `IE`/`CY`/`MT` | verified |
| `03-03-01` | `03-03` | 3 | `TOT-01` | `T-03-12` | `tracer` (RED -> GREEN) | `tests/test_sii_boards_locales.py`, `tests/test_baseline_extractor.py`, `tests/test_baseline_contracts.py` | `uv run --offline ets2v2 baseline extract --check --out-dir data/baselines/ets2_1.62_def && uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_sii_boards_locales.py tests/test_baseline_extractor.py tests/test_baseline_contracts.py -x` | Any of the 24 `1.62` sign board attributes is dropped, `fuel_boards.json`/`manifest.json` SHA-256 fails verify, `gas_empty` is not unique `font_size==0`/`font_opacity==0`, or raw `.sii`/`.sui` appears under `data/` | verified |
| `03-03-02` | `03-03` | 3 | `TOT-01` | `T-03-13`, `T-03-14` | `auto` (`tdd="true"`) | `tests/test_totem_compiler.py`, `tests/test_package_builder.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_totem_compiler.py tests/test_package_builder.py tests/test_cli_scaffold.py -x` | Fewer than 460 boards classified, `gas_empty` or 5 highway signs emitted, any D-09 board fix fails, `fr_qc` leaks or `!= 43` locales, `.dds`/`.tobj` emitted, or `579`/`578` builder file counts fail | verified |
| `03-04-01` | `03-04` | 4 | `TOT-02` | `T-03-15` | `tracer` (RED -> GREEN) | `tests/test_totem_formatting.py`, `tests/test_totem_compiler.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_totem_formatting.py tests/test_totem_compiler.py tests/test_package_builder.py -x` | Any of 460 boards overflows width budget or uses unsupported glyphs, Eurozone routing diverges from `136` `<sup>9</sup>` / `12` `_3_ets2v2` / `40` `_c_ets2v2` (`164` tokens), or `GB` pence / `BG` EUR / `HUF`/`ISK`/`ALL`/`RSD` / `CZ` / `RO` / `MK` formats fail | verified |
| `03-04-02` | `03-04` | 4 | `TOT-02` | `T-03-15`, `T-03-17` | `auto` (`tdd="true"`) | `tests/test_validate_workshop.py`, `tests/test_validate_invariants.py` | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest tests/test_validate_workshop.py tests/test_validate_invariants.py tests/test_cli_scaffold.py -x` | `.dds`/`.tobj` escapes `ETS2V2-INV-ZERO-DDS`, any 43-locale/460-board/glyph/orphan/dangling/attribute fault-injection passes, positive Summer/Winter builds fail validation, or `validate/` imports `package`/`normalize`/`fetch` | verified |
| `03-04-03` | `03-04` | 4 | `TOT-02` | `T-03-16`, `T-03-18` | `auto` (`tdd="true"`, `costly` D-05/D-08) | `tests/test_package_icons_metadata.py`, `tests/test_publish_release.py`, `tests/test_publish_workflow.py` + full suite | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short -m "not local_ets2"` | `description.txt` misses D-16 attribution or leaks volatile dates, changelogs omit 36-country table or alerts, offline release breaks diff gate, `phase-a-release.yml` injects `${{` in `run:` or misses `fetch`/`prices.lock.json`, or any Phase 1–3 test fails | verified |

---

## 4. Requirement & Locked-Decision Coverage Matrix

| Requirement | Locked Decisions | Owning Plan(s) & Tasks | Key Invariants Verified |
|-------------|------------------|------------------------|-------------------------|
| **DAT-01** | `D-04`, `D-05`, `D-07`, `D-13`, `D-14`, `D-15` | `03-01` (`03-01-01`, `03-01-02`) | `Frankfurter v2` flat JSON array, `ECB` XML (suspended `RUB` handled), `fawazahmed0` jsDelivr + Cloudflare Pages mirror, `CBR` `windows-1251`/comma XML; 39-territory currency map (`BG=EUR=1.0`, `ME`/`XK=EUR`, `BAM=1.95583`); tiered `>2%`/`>5%` warn & `>10%` reject-and-hold; currency-split magnitude envelopes; 3-decimal `ROUND_HALF_UP` `eur_per_liter` separated from `local_display_price`; 4 AST offline DAG isolation walls |
| **DAT-02** | `D-01`, `D-02`, `D-03`, `D-04`, `D-14` | `03-02` (`03-02-01`, `03-02-02`, `03-02-03`) | `EC Weekly Oil Bulletin` dynamic Drupal HTML discovery (SSRF allowlist) + `openpyxl` `/1000` + `EL->GR` + EU-27 incl. `IE`/`CY`/`MT` & `LPG`; `FionnHughes` CSV & `fuel-prices.eu` (`IS`/non-EU) `CC BY 4.0` fallbacks; `UK DESNZ` pence/L->GBP/L; `NO SSB 09654`; `FR` ODS v2.1; optional `DE` `Tankerkönig` 5-city median with silent keyless fallback & secret redaction; `ES` MITECO; `IT` MIMIT; `NL` CBS `80416ned`; `1.62` baseline seeding for uncovered non-EU vanilla entries; verified D-02 secondary-grade spread table |
| **DAT-03** | `D-05`, `D-06`, `D-08`, `D-13`, `D-15` | `03-02` (`03-02-01`, `03-02-03`), `03-04` (`03-04-03`) | `state/prices.lock.json` (`schema_version: 1`, 39 territories, canonical sorted UTF-8 no-BOM LF JSON); `0.01–5.00 EUR/L` bounds & `±25%` WoW circuit breaker with `--allow-jump <ISO2>`; partial outage warn+retain vs total `0`-Tier-1-feed exit `1`; `>14d` Tier 1 & `>30d` fallback staleness alerts; locked `RealismSnapshot` v1 (`extra="forbid"`) compatibility |
| **TOT-01** | `D-04`, `D-09`, `D-11`, `D-14` | `03-03` (`03-03-01`, `03-03-02`) | Extended `sign_board.py` & refreshed `data/baselines/ets2_1.62_def/fuel_boards.json` capturing all 24 ETS2 `1.62` attributes; deterministic 460-board classification across 37 countries (`gas_empty` spacer & 5 multi-item highway signs untouched); all 17 active unmapped + 47 placeholder + 40 blank boards + `gas_is_ip1_98` + `gas_is_yokull` swap fixed; Option 4b Zero-DDS `def/sign/board/*.sii` & 43 byte-identical `locale/<lang>/local_module.ets2v2_fuel.sii` (`localization_db : .ets2v2_fuel`, `fr_ca` yes, `fr_qc` no) wired into Summer & Winter Core builds (`579` Workshop files / `578` local ZIP entries) |
| **TOT-02** | `D-03`, `D-05`, `D-08`, `D-10`, `D-11`, `D-12`, `D-16` | `03-04` (`03-04-01`, `03-04-02`, `03-04-03`) | 6-font SDF glyph & width-budget physics (`460/460` fit, `164` unique tokens, `136` `<sup>9</sup>` / `12` `_3_ets2v2` / `40` `_c_ets2v2`, UK pence `142.9`, BG `EUR`, integer `HUF`/`ISK`/`ALL`/`RSD`, `CZ` `.X0`, `RO`/`MK` widths, dot `.` separator); hard `D-12` validator invariants (`ETS2V2-INV-ZERO-DDS`, `ETS2V2-INV-LOCALE-SYNC`, `ETS2V2-INV-TOTEM-BOARDS`) with strict zero-import isolation; D-16 36-country fuel table, Circuit-Breaker & Staleness Alerts, and open-data attributions in `CHANGELOG_*.md` and `description.txt`; Friday `phase-a-release.yml` online `fetch` + step-`env` `TANKERKOENIG_API_KEY` + `state/prices.lock.json` Release PR staging |

---

## 5. CI vs Local Verification Policy

1. **GitHub Actions CI (`ubuntu-latest` via `.github/workflows/ci.yml` and `.github/workflows/phase-a-release.yml`):**
   - `.github/workflows/ci.yml` remains strictly read-only (`permissions: contents: read`) and runs `uv run --offline pytest -q --tb=short` (zero live network requests; all Phase 3 fetch tests use `httpx.MockTransport` and in-memory `openpyxl.Workbook`).
   - `.github/workflows/phase-a-release.yml` runs online `ets2v2 fetch` ONLY on Friday `06:00 UTC` schedule or manual `workflow_dispatch` (passing optional `TANKERKOENIG_API_KEY` strictly via step-level `env:`), followed by 100% offline `ets2v2 publish release` and `ets2v2 validate workshop`/`local`, staging `state/prices.lock.json` alongside `state/published.json` and `CHANGELOG_{SUMMER,WINTER}.md` in `release/phase-a-weekly`.
2. **Local Maintainer Workstation (Windows `pwsh`):**
   - After Plan `03-01` Task 1 locks `httpx`, `openpyxl`, and `types-openpyxl` into `uv.lock`, every quality and test command runs offline (`--offline`).
   - Plan `03-03` Task 1 re-extracts `data/baselines/ets2_1.62_def/fuel_boards.json` + `manifest.json` from local ETS2 `1.62.3.3s` `def.scs` and verifies `@pytest.mark.local_ets2` passes with zero byte diff.
   - **End-of-phase optional manual spot checks (`human_verify_mode: end-of-phase`):**
     - Optionally run one live `uv run --offline ets2v2 fetch --lock-path state/prices.lock.json --dry-run --json` to observe live Friday upstream endpoints (`EC WOB`, `Frankfurter v2`, `ECB`, `UK DESNZ`, `NO SSB`, `FR`/`ES`/`IT`/`NL`).
     - Run `uv run --offline ets2v2 publish release --out-dir dist --changelogs-dir build/changelogs` and optionally drop `dist/local/ETS2V2_Core_Summer.zip` into ETS2 `1.62.3.3s` `mod/` to visually spot-check roadside gas totems (`DE` `<sup>9</sup>`, `GB` pence, `IE` EUR, `BG` EUR, `IS` Yokull/IP1, `BA` LPG) and confirm zero warnings in `game.log.txt`.
