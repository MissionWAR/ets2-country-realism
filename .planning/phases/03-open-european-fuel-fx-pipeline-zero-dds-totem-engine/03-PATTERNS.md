# Phase 3: Open European Fuel/FX Pipeline & Zero-DDS Totem Engine - Pattern Map

**Mapped:** 2026-11-21
**Phase Scope:** `DAT-01`, `DAT-02`, `DAT-03`, `TOT-01`, `TOT-02` (Plans `03-01` through `03-04`)
**Files analyzed:** 35 planned new/modified files (13 new source modules, 8 modified source modules, 1 new committed state lockfile, 2 config/workflow files, 11 new/updated test modules)
**Analogs found:** 32 / 35 (3 new modules introduce Phase 3 HTTP/XLSX transport capabilities — `httpx` client/transport, `openpyxl` workbook parsing, and multi-endpoint national HTTP collectors — with no direct Phase 1/2 network library analog, while strictly replicating Phase 1/2 typing, Pydantic, determinism, and CLI/test conventions)

---

## 1. Proposed Phase 3 Package & Module Layout

### Subpackage Alignment (`src/ets2v2/`)

Per `03-CONTEXT.md` (lines 71, 123), Phase 3 unlocks **`fetch/`** and **`normalize/`** under `src/ets2v2/` while keeping Phase 4's **`merge/`** strictly blocked in `tests/test_cli_scaffold.py::test_active_phase_only_package_layout`.

**Totem Engine Placement Decision (`package/totems.py` + `normalize/totem_format.py` vs a top-level `totems/` package):**
Split totem responsibilities across the two existing/unlocked architectural domains rather than creating an unplanned top-level `src/ets2v2/totems/` package:
1. **`src/ets2v2/normalize/totem_format.py` (Layer 5 — pure offline domain rules):** Houses the canonical grade alias adapter (`natural95`/`unleaded` -> `petrol_95`, `super` -> `petrol_98`, `diesel5` -> `diesel_plus`, etc. per `D-14`), the deterministic `461`-board classification table (`D-09`: `373` `active_fp` + identifiable `47` `placeholder` + identifiable `41` `blank`, fixing the `17` unmapped boards, `gas_is_ip1_98`, `gas_is_yokull` swap, and leaving `gas_empty` structural spacers + `5` multi-item highway signs untouched), and native-currency pump price formatting (`D-10`, `D-11`: UK pence `142.9`, `BG` `EUR`, integer currencies `HUF`/`ISK`/`ALL`/`RSD`, `<sup>9</sup>` tenth-cent vs `3`-dec/`2`-dec fallback gated by board font/width, uniform `.` decimal separator). Reused directly by Phase 4 ProMods `pm_*_fuel` totems without pulling in Vanilla packaging.
2. **`src/ets2v2/package/totems.py` (Layer 7B — offline SII emitter):** Synthesizes clean-room `def/sign/board/*.sii` overrides and all `43` synchronized `locale/<lang>/local_module.ets2v2_fuel.sii` files from `FuelBoardsBaseline` + `LocalesBaseline` + `PricesLockfile` + `normalize.totem_format`, validated through `validate_sii_hygiene()`.

**Why this placement is optimal:**
- Matches `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` (`fetch/` + `normalize/` unlocked, zero unplanned top-level packages, `merge/` still blocked).
- Automatically preserves the strict `validate ⊥ package` AST isolation boundary (`tests/test_validate_workshop.py:87-120`) — all SII mod-file emitters (`synthesize.py`, `totems.py`, `metadata.py`, `icons.py`, `builder.py`) stay in `package/`, while `validate/` inspects built artifacts independently using `ets2v2.sii.{sign_board,localization,hygiene}` and `ets2v2.baseline.models`.
- Keeps `package/`, `validate/`, `publish/`, and `normalize/` **100% offline** with zero `httpx` or `openpyxl` imports anywhere outside `fetch/`.

```text
src/ets2v2/
├── __init__.py                   # Existing — __version__ = "0.1.0"
├── py.typed                      # Existing — PEP 561 marker
├── cli.py                        # Modified (03-01..03-04) — add `ets2v2 fetch` & `--prices-lock` flags
├── vfs/                          # Existing (Phase 1, Layers 0-2) — unchanged
├── sii/                          # Existing (Phase 1, Layers 0-3) — unchanged (sign_board & localization reused)
├── baseline/                     # Existing (Phase 1, Layer 4) — unchanged (FuelBoardsBaseline & LocalesBaseline reused)
├── normalize/                    # NEW (Phase 3, Layer 5 — 100% offline pure domain & lockfile)
│   ├── __init__.py               # Public __all__ facade (sorted alphabetically, RUF022)
│   ├── models.py                 # Strict frozen Pydantic v2 models: FuelGrade, FxRateRecord, CountryFuelLockEntry,
│   │                             #   PriceAlert, PricesLockfile (state/prices.lock.json schema_version=1)
│   ├── lockfile.py               # Offline loader, deterministic JSON serializer, baseline seeder (D-01/D-04),
│   │                             #   and 14d/30d staleness evaluator (D-08)
│   ├── fx.py                     # Pure FX cross-validator (tiered >2%/>5% warn, >10% reject, inversion/split guard,
│   │                             #   BG pinned EUR=1.0, 3-decimal eur_per_liter rounding per D-07/D-15)
│   ├── fuel.py                   # Pure price normalizer (0.01-5.00 EUR/L bounds, ±25% WoW circuit breaker +
│   │                             #   --allow-jump override, secondary-grade spread ratios, EL->GR per D-02/D-06/D-14)
│   └── totem_format.py           # Canonical fp_* alias adapter, 461-board country/grade resolver (D-09),
│                                 #   and native-currency / <sup>9</sup> / font-width pump formatter (D-10/D-11)
├── registry/                     # Modified (Layer 6 — offline statutory laws & locked v1 snapshot)
│   ├── __init__.py               # Existing — unchanged
│   ├── models.py                 # Existing — unchanged
│   ├── loader.py                 # Existing — unchanged
│   ├── timezone.py               # Existing — unchanged
│   └── snapshot.py               # Modified (03-02) — optional `prices_lock: PricesLockfile | None = None`
│                                 #   injecting live RealismSnapshotFuel while locking schema_version=1 (D-13)
├── fetch/                        # NEW (Phase 3, Layer 7A — ONLY online/HTTP & XLSX subpackage)
│   ├── __init__.py               # Public __all__ facade
│   ├── models.py                 # Strict frozen DTOs: RawFxQuoteSet, RawFuelFeedResult, FetchRunReport
│   ├── http.py                   # httpx.Client factory (timeouts, User-Agent, retry/backoff, MockTransport hook)
│   ├── fx.py                     # Online FX collectors: Frankfurter v2, ECB eurofxref-daily.xml, fawazahmed0, CBR XML
│   ├── ec_bulletin.py            # EC Weekly Oil Bulletin dynamic Drupal .xlsx discovery + openpyxl parser (EL->GR,
│   │                             #   EU-27 incl. IE/CY/MT, LPG) + FionnHughes/fuel-prices.eu CC BY 4.0 fallback
│   ├── national.py               # Tier 1 national collectors: UK DESNZ, NO SSB 09654, FR, DE (optional Tankerkönig),
│   │                             #   ES MITECO, IT MIMIT, NL CBS StatLine
│   └── pipeline.py               # `run_price_fetch()` orchestrator: fetch -> FX cross-validate -> fuel normalize ->
│                                 #   circuit-breaker/staleness/outage policy (D-06..D-08) -> write state/prices.lock.json
├── package/                      # Modified (Layer 7B — 100% offline Core mod compiler, package ⊥ fetch)
│   ├── __init__.py               # Modified (03-03) — export totem synthesizer symbols
│   ├── synthesize.py             # Existing — unchanged (already formats resolved.fuel.eur_per_liter)
│   ├── totems.py                 # NEW (03-03/03-04) — Option 4b Zero-DDS emitter for def/sign/board/*.sii and
│   │                             #   all 43 locale/<lang>/local_module.ets2v2_fuel.sii files (TOT-01/TOT-02)
│   ├── metadata.py               # Modified (03-04) — extend render_description_txt() with D-16 open-data attribution
│   ├── icons.py                  # Existing — unchanged
│   └── builder.py                # Modified (03-03) — load state/prices.lock.json, pass into build_realism_snapshot(),
│                                 #   emit totem boards + 43 locale modules into Workshop root & local ZIP
├── validate/                     # Modified (Layer 8 — 100% offline validator, validate ⊥ package ⊥ fetch ⊥ normalize)
│   ├── __init__.py               # Modified (03-04) — export validate_totem_invariants & Zero-DDS constants
│   ├── models.py                 # Existing — unchanged
│   ├── invariants.py             # Modified (03-04) — add validate_totem_invariants() (Zero-DDS, 43-locale parity,
│   │                             #   board geometry/font preservation, token resolution, 5 highway signs untouched)
│   └── workshop.py               # Modified (03-04) — hard-reject .dds/.tobj (Zero-DDS), parse def/sign/board/*.sii
│                                 #   & locale/<lang>/local_module.ets2v2_fuel.sii, load FuelBoardsBaseline
└── publish/                      # Modified (Layer 9 — 100% offline release orchestrator, publish ⊥ fetch)
    ├── __init__.py               # Existing — unchanged
    ├── ledger.py                 # Existing — unchanged (canonical SHA-256 automatically hashes new totem/locale files)
    ├── changelog.py              # Modified (03-04) — add 36-country fuel table, Circuit-Breaker & Staleness Alerts,
    │                             #   and D-16 open-data attribution block
    └── release.py                # Modified (03-04) — accept prices_lock_path, pass PricesLockfile into snapshot,
                                  #   builder, and changelog renderer
```

### Complete Acyclic Module DAG Verification (Layers 0–10)

Phase 3 extends Phase 2's DAG to **11 strictly bottom-up layers (Layers 0–10)** with **zero upward or lateral cycles** and **four hard isolation walls**:

```text
Layer 10: ets2v2.cli
            ├──► ets2v2.vfs, ets2v2.baseline                    (Phase 1)
            ├──► ets2v2.registry, ets2v2.package,
            │    ets2v2.validate, ets2v2.publish                (Phase 2)
            └──► ets2v2.normalize, ets2v2.fetch                 (Phase 3)

Layer 9:  ets2v2.publish  {ledger, changelog, release}          [OFFLINE — zero fetch/httpx/openpyxl]
            └──► ets2v2.baseline.models, ets2v2.normalize.{models, lockfile},
                 ets2v2.registry.*, ets2v2.package.*, ets2v2.validate.*,
                 ets2v2.sii.document, ets2v2.vfs.types

Layer 8:  ets2v2.validate {models, invariants, workshop}        [OFFLINE — validate ⊥ package ⊥ fetch ⊥ normalize]
            └──► ets2v2.vfs {zip_archive, dir_archive, types},
                 ets2v2.sii {hygiene, document, country, speed_limits,
                             sign_board, localization, lexer},
                 ets2v2.baseline.models {CountriesBaseline, SpeedLimitsBaseline,
                                         FuelBoardsBaseline, LocalesBaseline},
                 PIL

Layer 7A: ets2v2.fetch    {models, http, fx, ec_bulletin,       [ONLINE ONLY — imported ONLY by cli.py]
                           national, pipeline}
            └──► httpx, openpyxl, ets2v2.baseline.models,
                 ets2v2.registry.{models, loader}, ets2v2.normalize.*

Layer 7B: ets2v2.package  {synthesize, totems, metadata,        [OFFLINE — package ⊥ fetch, zero httpx/openpyxl]
                           icons, builder}
            └──► ets2v2.sii {hygiene, country, speed_limits, lexer},
                 ets2v2.baseline.models, ets2v2.normalize.{models, lockfile, totem_format},
                 ets2v2.registry.*, ets2v2.vfs.types, PIL

Layer 6:  ets2v2.registry {models, timezone, loader, snapshot}  [OFFLINE]
            └──► ets2v2.baseline.models, ets2v2.sii.speed_limits,
                 ets2v2.normalize.models (snapshot.py only), stdlib zoneinfo (tzdata)

Layer 5:  ets2v2.normalize {models, lockfile, fx, fuel,         [OFFLINE — pure domain, zero httpx/openpyxl]
                            totem_format}
            └──► ets2v2.baseline.models, pydantic, stdlib (json, math, datetime, re, pathlib)

Layer 4:  ets2v2.baseline {models, extractor}                   (Phase 1 — unchanged)
            └──► ets2v2.vfs, ets2v2.sii

Layer 3:  ets2v2.sii.{country, speed_limits, sign_board, localization}   (Phase 1 — unchanged)
Layer 2:  ets2v2.vfs.{hashfs, stack}  |  ets2v2.sii.document             (Phase 1 — vfs ⊥ sii)
Layer 1:  ets2v2.vfs.{cityhash, dir_archive, zip_archive} | ets2v2.sii.hygiene
Layer 0:  ets2v2.__init__ | ets2v2.vfs.types | ets2v2.sii.lexer
```

**Four Mandatory AST-Enforced Isolation Walls (verify in `tests/test_validate_workshop.py` and `tests/test_fetch_pipeline.py`):**
1. **`validate ⊥ package` (existing):** `src/ets2v2/validate/` NEVER imports `ets2v2.package`.
2. **`validate ⊥ fetch` (new):** `src/ets2v2/validate/` NEVER imports `ets2v2.fetch`, `httpx`, or `openpyxl` (and does not need `ets2v2.normalize` either).
3. **`package ⊥ fetch` & `publish ⊥ fetch` (new):** `src/ets2v2/package/` and `src/ets2v2/publish/` NEVER import `ets2v2.fetch`, `httpx`, or `openpyxl` — guarantees `D-05` 100% offline-deterministic builds and releases.
4. **`normalize ⊥ fetch` (new):** `src/ets2v2/normalize/` NEVER imports `ets2v2.fetch`, `httpx`, or `openpyxl` — keeps all FX validation, circuit-breaker math, lockfile I/O, and totem formatting purely offline and testable without HTTP stubs.

### Active-Phase Layout Gate Update (`tests/test_cli_scaffold.py:63-85`)

Plan `03-01` (Wave 1) updates `test_active_phase_only_package_layout()` to unlock `fetch` and `normalize` while keeping Phase 4's `merge` blocked:

```python
def test_active_phase_only_package_layout() -> None:
    pkg_root = REPO_ROOT / "src" / "ets2v2"
    assert pkg_root.is_dir()

    entries = {entry.name for entry in pkg_root.iterdir() if entry.name != "__pycache__"}
    deferred_phase_dirs = {"merge"}
    allowed_phase3_entries = {
        "__init__.py",
        "py.typed",
        "cli.py",
        "vfs",
        "sii",
        "baseline",
        "normalize",
        "registry",
        "fetch",
        "package",
        "validate",
        "publish",
    }

    assert entries.isdisjoint(deferred_phase_dirs)
    assert entries <= allowed_phase3_entries
    assert {"__init__.py", "py.typed", "cli.py"} <= entries
```

### Non-Python Repository Artifacts Added / Modified in Phase 3

| Path | Plan | Committed? | Format / Hygiene Contract |
|---|---|---|---|
| `pyproject.toml` & `uv.lock` | `03-01` | Yes | Add permissive runtime deps `httpx>=0.28,<0.29`, `openpyxl>=3.1,<4` (and `types-openpyxl` in `[dependency-groups].dev` for strict `basedpyright`); run `uv lock` |
| `state/prices.lock.json` | `03-02` | Yes | UTF-8 no-BOM LF, `indent=2`, `sort_keys=True`, `ensure_ascii=False` + `\n`; tracks all **39** European territories (`36` Vanilla+DLC + `IE`, `CY`, `MT` per `D-04`), FX rates, provider provenance, timestamps, and circuit-breaker alerts (`D-05`, `D-13`) |
| `.github/workflows/phase-a-release.yml` | `03-04` | Yes | UTF-8 no-BOM LF; add online `ets2v2 fetch` step (with step-level `env: TANKERKOENIG_API_KEY`) BEFORE offline `ets2v2 publish release`; stage `state/prices.lock.json` in persistent `release/phase-a-weekly` PR (`D-03`, `D-05`, `D-08`) |
| `dist/workshop/{summer,winter}/` & `dist/local/*.zip` | `03-03` | **No** | Gitignored under `dist/`; now include `def/sign/board/*.sii` and 43 `locale/<lang>/local_module.ets2v2_fuel.sii` files |

---

## 2. File Classification & File-to-Analog Mapping Table

All analog paths below are verified git-tracked via `git ls-files`.

| Plan | New / Modified File | Role | Data Flow | Closest Tracked Phase 1/2 Analog | Match Quality | Key Patterns to Replicate |
|---|---|---|---|---|---|---|
| `03-01` | `pyproject.toml` & `uv.lock` | config | n/a | `pyproject.toml` (in-place) | exact | Add `httpx>=0.28,<0.29`, `openpyxl>=3.1,<4` to sorted `project.dependencies`, `types-openpyxl` to `[dependency-groups].dev`; keep `ruff`/`basedpyright` strict configs untouched |
| `03-01` | `tests/test_cli_scaffold.py` | test / contract | contract | `tests/test_cli_scaffold.py` (in-place) | exact | Update `test_active_phase_only_package_layout` (`fetch`/`normalize` unlocked, `merge` blocked), `test_pyproject_metadata_and_quality_gates`, `test_uv_lock_contains_verified_packages`, add `test_phase3_runtime_distribution_metadata` |
| `03-01` | `src/ets2v2/normalize/__init__.py` | barrel / facade | n/a | `src/ets2v2/registry/__init__.py` | exact | `from __future__ import annotations`, absolute imports, alphabetically sorted `__all__` (`RUF022`) |
| `03-01` | `src/ets2v2/normalize/models.py` | model / schema | transform | `src/ets2v2/registry/models.py` & `publish/ledger.py` | exact | `ConfigDict(strict=True, frozen=True, extra="forbid")`, `Literal` type aliases (`FuelGrade`, `AlertSeverity`, `AlertKind`), `Field(pattern=..., ge=..., allow_inf_nan=False)` |
| `03-01` | `src/ets2v2/normalize/lockfile.py` | service / state | file-I/O | `src/ets2v2/publish/ledger.py` & `registry/loader.py` | exact | BOM/LF raw-byte checks before `model_validate_json()`, canonical `json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`, baseline seeding (`D-01`/`D-04`), 14d/30d staleness checks (`D-08`) |
| `03-01` | `src/ets2v2/normalize/fx.py` | utility / domain | transform | `src/ets2v2/registry/timezone.py` | exact | Pure stateless functions, frozen Pydantic result models, `Final` tolerance constants (`0.02`, `0.05`, `0.10`), `BG` pinned `EUR=1.0`, currency-split & inversion guards, 3-dec `eur_per_liter` rounding (`D-07`, `D-15`) |
| `03-01` | `src/ets2v2/fetch/__init__.py` | barrel / facade | n/a | `src/ets2v2/publish/__init__.py` | exact | `from __future__ import annotations`, absolute imports, alphabetically sorted `__all__` (`RUF022`) |
| `03-01` | `src/ets2v2/fetch/models.py` | model / DTO | transform | `src/ets2v2/validate/models.py` | exact | Strict frozen Pydantic v2 DTOs for raw provider quotes, feed statuses, and structured `FetchRunReport` (`--json` ready) |
| `03-01` | `src/ets2v2/fetch/http.py` | utility / transport | request-response | *No direct analog* (new `httpx` capability) | partial | Context-managed `httpx.Client` builder accepting optional `transport: httpx.BaseTransport \| None` for offline `MockTransport` testing; explicit `timeout`, `User-Agent`, bounded retries on `429`/`5xx`, zero `print()`/`logging` |
| `03-01` | `src/ets2v2/fetch/fx.py` | service / collector | request-response | `src/ets2v2/fetch/http.py` + `sii/lexer.py` | role-match | Multi-provider fetchers (`Frankfurter v2` JSON, `ECB eurofxref-daily.xml`, `fawazahmed0` JSON, `CBR` XML via `xml.etree.ElementTree`) catching `httpx.HTTPError`/parse errors into structured provider diagnostics without crashing fallback chain |
| `03-01` | `tests/test_normalize_fx.py` | test / unit | unit | `tests/test_registry_timezone.py` | exact | Parametrized `>2%`/`>5%`/`>10%` divergence matrix, inverted-rate rejection, `BG: EUR=1.0`, NaN/zero/negative guard, 3-decimal `eur_per_liter` precision |
| `03-01` | `tests/test_fetch_fx.py` | test / integration | request-response | `tests/test_baseline_extractor.py` | role-match | 100% offline `httpx.MockTransport` fixtures covering Frankfurter v2, ECB XML, fawazahmed0, CBR XML, weekend fixing lag, and provider outage fallback |
| `03-02` | `src/ets2v2/normalize/fuel.py` | service / domain | transform | `src/ets2v2/registry/loader.py` & `timezone.py` | role-match | Pure bounds (`0.01–5.00 EUR/L`), `±25%` WoW circuit breaker with `--allow-jump <ISO2>` set (`D-06`), documented secondary-grade spread derivation (`D-02`), canonical 9-grade keys (`D-14`), `EL`->`GR` normalization |
| `03-02` | `src/ets2v2/fetch/ec_bulletin.py` | service / collector | request-response + transform | *No direct analog* (new `openpyxl` parser) | partial | Dynamic Drupal `.xlsx` link discovery + `openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)` parser (`EU-27` incl. `EL`->`GR`, `IE`/`CY`/`MT`, `LPG`) + `FionnHughes`/`fuel-prices.eu` `CC BY 4.0` fallback |
| `03-02` | `src/ets2v2/fetch/national.py` | service / collector | request-response + transform | *No direct analog* (multi-portal HTTP parsers) | partial | Isolated Tier 1 national collectors (`UK DESNZ`, `NO SSB 09654`, `FR`, `DE` optional `TANKERKOENIG_API_KEY`, `ES MITECO`, `IT MIMIT`, `NL CBS`) returning structured per-feed results so any single failure isolates cleanly |
| `03-02` | `src/ets2v2/fetch/pipeline.py` | service / orchestrator | batch | `src/ets2v2/publish/release.py` | exact | Composes FX fetch -> Tier 1 fuel collectors -> `normalize.fuel` circuit breaker -> `D-01` non-EU seeding -> `D-08` outage/staleness policy -> atomic `write_prices_lockfile()`; returns frozen `FetchRunReport` |
| `03-02` | `state/prices.lock.json` | state / lockfile | file-I/O | `state/published.json` | exact | Committed canonical sorted UTF-8 no-BOM LF JSON tracking 39 territories (`36` Vanilla+DLC + `IE`, `CY`, `MT`), live/seeded FX + canonical grade prices + provenance + alerts |
| `03-02` | `src/ets2v2/registry/snapshot.py` | model / serializer | transform | `src/ets2v2/registry/snapshot.py` (in-place) | exact | Add keyword-only `prices_lock: PricesLockfile \| None = None` to `build_realism_snapshot()`; preserve `schema_version: Literal[1] = 1` & exact 4 `RealismSnapshotFuel` keys (`D-13`, `D-14`, `D-15`) |
| `03-02` | `tests/test_normalize_fuel.py` | test / unit | unit | `tests/test_registry_schema.py` & `test_publish_ledger.py` | exact | Parametrized `0.01–5.00 EUR/L` bounds, `±25%` jump rejection vs `--allow-jump`, secondary-grade spread ratios, `EL`->`GR`, 39-territory lockfile round-trip & staleness `14d`/`30d` alerts |
| `03-02` | `tests/test_fetch_pipeline.py` | test / integration | request-response + batch | `tests/test_publish_release.py` | exact | Offline `httpx.MockTransport` + in-memory `openpyxl.Workbook` fixtures testing full pipeline, optional `TANKERKOENIG_API_KEY` on/off (`D-03`), partial outage retain vs total `0`-feed outage failure (`D-08`), AST offline-wall checks |
| `03-02` | `tests/test_registry_snapshot.py` | test / contract | contract | `tests/test_registry_snapshot.py` (in-place) | exact | Keep existing `prices_lock=None` tests intact; add live `PricesLockfile` injection tests asserting `schema_version == 1`, exact 4 fuel keys, 3-decimal `eur_per_liter`, and canonical `local_prices` |
| `03-03` | `src/ets2v2/normalize/totem_format.py` | utility / domain | transform | `src/ets2v2/registry/timezone.py` & `sii/sign_board.py` | role-match | Canonical `fp_*` alias map (`D-14`), deterministic `461`-board classification (`D-09`: `active_fp` + `placeholder` + `blank`, `17` unmapped, `gas_is_ip1_98`, `gas_is_yokull` swap, skipping `gas_empty` + `5` highway signs), native currency & `<sup>9</sup>` width-gated formatter (`D-10`, `D-11`) |
| `03-03` | `src/ets2v2/package/totems.py` | service / compiler | transform | `src/ets2v2/package/synthesize.py` | exact | Clean-room `def/sign/board/*.sii` & 43-locale `locale/<lang>/local_module.ets2v2_fuel.sii` emitters using `format_sii_string()`, `serialize_sii_text()`, `validate_sii_hygiene(..., require_siinunit=True)` (`TOT-01`, `TOT-02`) |
| `03-03` | `src/ets2v2/package/__init__.py` | barrel / facade | n/a | `src/ets2v2/package/__init__.py` (in-place) | exact | Re-export `package.totems` public APIs in alphabetically sorted `__all__` |
| `03-03` | `src/ets2v2/package/builder.py` | service / packager | file-I/O | `src/ets2v2/package/builder.py` (in-place) | exact | Accept `prices_lock_path: Path = Path("state/prices.lock.json")`, load `FuelBoardsBaseline` & `PricesLockfile`, inject prices into `build_realism_snapshot()`, emit `def/sign/board/*.sii` + 43 `locale/<lang>/local_module.ets2v2_fuel.sii` into `shared_payloads` |
| `03-03` | `tests/test_totem_engine.py` | test / unit + integration | unit | `tests/test_package_synthesize.py` & `test_sii_boards_locales.py` | exact | Round-trip every emitted board via `parse_sign_board()` & every locale module via `parse_localization_db()`, verify all 43 locales (`fr_ca` yes, `fr_qc` no), `17` unmapped boards, `gas_is_ip1_98`, `gas_is_yokull` swap, `gas_empty` & `5` highway signs omitted, native currency & `<sup>9</sup>` formatting |
| `03-03` | `tests/test_package_builder.py` | test / integration | integration | `tests/test_package_builder.py` (in-place) | exact | Update hardcoded `76`/`75` file counts to `76 + N_boards + 43` / `75 + N_boards + 43`, verify `def/sign/board/*.sii` & 43 `locale/*/local_module.ets2v2_fuel.sii` inside both Workshop root & local ZIP, assert zero `.dds`/`.tobj` |
| `03-04` | `src/ets2v2/validate/invariants.py` | service / validator | transform | `src/ets2v2/validate/invariants.py` (in-place) | exact | Add `validate_totem_invariants()` enforcing `D-12`: Zero-DDS, exact 43 active locales (`fr_qc` absent), identical sorted `key[]`/`val[]` sets (`^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$`), non-empty values, baseline `model_name`/`font_face`/`coords_*` preservation, zero dangling/orphan tokens, `5` highway signs & `gas_empty` untouched |
| `03-04` | `src/ets2v2/validate/workshop.py` | service / validator | file-I/O | `src/ets2v2/validate/workshop.py` (in-place) | exact | Reject `.dds`/`.tobj` hard (`ETS2V2-INV-ZERO-DDS`), load `FuelBoardsBaseline` in `_load_optional_baselines()`, parse `def/sign/board/*.sii` via `parse_sign_board()` & `locale/<lang>/local_module.ets2v2_fuel.sii` via `parse_localization_db()`, invoke `validate_totem_invariants()` |
| `03-04` | `src/ets2v2/validate/__init__.py` | barrel / facade | n/a | `src/ets2v2/validate/__init__.py` (in-place) | exact | Re-export `validate_totem_invariants` & `FORBIDDEN_TOTEM_EXTENSIONS` in sorted `__all__` |
| `03-04` | `src/ets2v2/package/metadata.py` | utility / emitter | transform | `src/ets2v2/package/metadata.py` (in-place) | exact | Extend `render_description_txt()` with all `D-16` open-data source attributions while preserving zero volatile dates/versions |
| `03-04` | `src/ets2v2/publish/changelog.py` | service / renderer | transform | `src/ets2v2/publish/changelog.py` (in-place) | exact | Add compact 36-country fuel table, highlighted **Circuit-Breaker & Staleness Alerts** section (when `prices_lock` has alerts), and `D-16` open-data attribution block |
| `03-04` | `src/ets2v2/publish/release.py` | service / orchestrator | batch | `src/ets2v2/publish/release.py` (in-place) | exact | Thread `prices_lock_path: Path = Path("state/prices.lock.json")` into `build_realism_snapshot()`, `build_core_edition()`, and `render_edition_changelog()` — staying 100% offline |
| `03-04` | `src/ets2v2/cli.py` | CLI entrypoint | request-response | `src/ets2v2/cli.py` (in-place) | exact | Register `ets2v2 fetch` (`--lock-path`, `--allow-jump`, `--fx-only`, `--timeout`, `--dry-run`, `--json`) + add `--prices-lock` flag to `registry snapshot`, `package build`, `publish release` |
| `03-04` | `.github/workflows/phase-a-release.yml` | CI workflow | batch | `.github/workflows/phase-a-release.yml` (in-place) | exact | Add online `uv run ets2v2 fetch` step (with step-level `env: TANKERKOENIG_API_KEY: ${{ secrets.TANKERKOENIG_API_KEY }}`) BEFORE offline `uv run --offline ets2v2 publish release`; stage `state/prices.lock.json` in persistent Release PR |
| `03-04` | `tests/test_validate_invariants.py` & `test_validate_workshop.py` | test / unit + integration | unit | `tests/test_validate_invariants.py` & `test_validate_workshop.py` (in-place) | exact | Add fault-injection tests for `.dds`/`.tobj` rejection, missing locale / stray `fr_qc`, mismatched `key[]`/`val[]`, dangling `@@fp_*_ets2v2@@` token, drifted `font_face`/`coords_*`, rewritten highway sign; extend AST isolation checks (`validate`/`package`/`publish`/`normalize` zero `fetch`/`httpx`/`openpyxl`) |
| `03-04` | `tests/test_package_icons_metadata.py`, `test_publish_release.py`, `test_publish_workflow.py` | test / contract | contract | Existing files (in-place) | exact | Verify `D-16` attributions in `description.txt` & changelogs, 36-country fuel table, circuit-breaker alert block, and `phase-a-release.yml` `ets2v2 fetch` + `TANKERKOENIG_API_KEY` step-`env` + `state/prices.lock.json` staging |

---

## 3. Concrete Pattern Assignments (Code to Copy From)

### Pattern A — Strict Frozen Pydantic v2 Models (`03-01`, `03-02`, `03-03`)

**Analog:** `src/ets2v2/registry/models.py:21-31`, `src/ets2v2/registry/snapshot.py:29-38`, `src/ets2v2/publish/ledger.py:24-45`

```python
from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

FuelGrade = Literal[
    "diesel",
    "diesel_plus",
    "petrol_95",
    "petrol_98",
    "petrol_100",
    "petrol_92",
    "e85",
    "lpg",
    "mpo",
]

_ISO_DATE_PATTERN: Final[str] = r"^\d{4}-\d{2}-\d{2}$"


class CountryFuelLockEntry(BaseModel):
    """Canonical locked fuel price record for one European territory in ``state/prices.lock.json``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    eur_per_liter: float = Field(gt=0.0, allow_inf_nan=False)
    local_prices: dict[FuelGrade, float] = Field(default_factory=dict)
    source: str = Field(min_length=1)
    fetched_at: str = Field(pattern=_ISO_DATE_PATTERN)
    is_fallback: bool = False
```

**Conventions to preserve:**
- Always use `ConfigDict(strict=True, frozen=True, extra="forbid")` on every Phase 3 Pydantic schema.
- Always set `allow_inf_nan=False` on float price/FX fields (mirrors `src/ets2v2/registry/snapshot.py:35`).
- Deserialize JSON strictly with `Model.model_validate_json(raw.decode("utf-8"))` — never `Model.model_validate(json.loads(...))` under `strict=True` (tuple/literal/container coercion breaks).
- Immutable updates strictly via `.model_copy(update={...})`.

---

### Pattern B — Deterministic Canonical Lockfile Persistence (`03-01`, `03-02`)

**Analog:** `src/ets2v2/publish/ledger.py:148-172` & `src/ets2v2/registry/loader.py:29-46`

```python
def serialize_lockfile_bytes(lockfile: PricesLockfile) -> bytes:
    """Serialize ``PricesLockfile`` to canonical UTF-8 no-BOM LF sorted JSON bytes."""
    payload: object = lockfile.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def load_prices_lockfile(path: Path) -> PricesLockfile:
    """Load and strictly validate a ``state/prices.lock.json`` v1 lockfile."""
    if not path.is_file():
        raise FileNotFoundError(f"Prices lockfile does not exist: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"Prices lockfile must not contain a UTF-8 BOM: {path}")
    if b"\r" in raw:
        raise ValueError(f"Prices lockfile must use LF line endings only: {path}")
    return PricesLockfile.model_validate_json(raw.decode("utf-8"))


def write_prices_lockfile(lockfile: PricesLockfile, path: Path) -> bytes:
    """Write ``PricesLockfile`` deterministically to ``path`` and return serialized bytes."""
    raw = serialize_lockfile_bytes(lockfile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw
```

**Apply to:** `src/ets2v2/normalize/lockfile.py` (`state/prices.lock.json`). Note the explicit `payload: object = ...` annotation preventing `basedpyright` `reportUnknownVariableType`.

---

### Pattern C — Offline `httpx.MockTransport` Client & Testing Pattern (`03-01`, `03-02`)

**Constraint:** `.github/workflows/ci.yml:40` and `.github/workflows/phase-a-release.yml:47` run `uv run --offline pytest -q --tb=short`. Every Phase 3 fetch test **MUST** inject `httpx.MockTransport` (zero live sockets).

**Production client factory (`src/ets2v2/fetch/http.py`):**
```python
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Final

import httpx

DEFAULT_TIMEOUT_SECONDS: Final[float] = 20.0
DEFAULT_MAX_RETRIES: Final[int] = 2
DEFAULT_USER_AGENT: Final[str] = (
    "ets2-world-realism/0.1.0 (+https://github.com/ets2-world-realism; clean-room open-data fetch)"
)
_RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})


def create_http_client(
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    """Create a configured synchronous ``httpx.Client`` supporting injected mock transports."""
    return httpx.Client(
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": DEFAULT_USER_AGENT},
        follow_redirects=True,
        transport=transport,
    )


def fetch_bytes_with_retry(
    client: httpx.Client,
    url: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = 0.5,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bytes:
    """Perform a bounded GET request retrying transient network/429/5xx failures."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.get(url)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < max_retries:
                sleep_fn(backoff_seconds * (2**attempt))
                continue
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < max_retries:
                sleep_fn(backoff_seconds * (2**attempt))
                continue
            raise
    assert last_exc is not None
    raise last_exc
```

**Offline test pattern (`tests/test_fetch_fx.py`, `tests/test_fetch_pipeline.py`):**
```python
def _mock_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "frankfurter" in url:
        return httpx.Response(200, json={"base": "EUR", "date": "2026-11-20", "rates": {"GBP": 0.84}})
    if "eurofxref-daily.xml" in url:
        return httpx.Response(200, content=_SAMPLE_ECB_XML, headers={"content-type": "application/xml"})
    return httpx.Response(404, text="not found")

transport = httpx.MockTransport(_mock_handler)
with create_http_client(transport=transport) as client:
    quotes = fetch_all_fx_quotes(client)
```

**In-memory `openpyxl` fixture pattern (zero binary `.xlsx` blobs committed to `tests/`):**
```python
import io
import openpyxl

def _build_ec_bulletin_xlsx_bytes(rows: list[list[object]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

---

### Pattern D — Clean-Room Option 4b Totem Board & 43-Locale Module Synthesis (`03-03`, `03-04`)

**Analog:** `src/ets2v2/package/synthesize.py:20-102` & `src/ets2v2/sii/sign_board.py:16-66` & `src/ets2v2/sii/localization.py:13-57`

**Reuse directly from `src/ets2v2/package/synthesize.py`:**
- `format_sii_string()` (lines 20–27) — safely escapes `"`, `\r`, `\n`, `\t` and rejects `\` and `\x00`. Verified safe for `<sup>9</sup>` HTML micro-tags (`"1.78<sup>9</sup>"` passes both `format_sii_string()` and `validate_sii_hygiene()` with zero diagnostics).
- `_format_float()` convention (lines 60–69) — finite float formatting without scientific notation.
- `serialize_sii_text()` + `validate_sii_hygiene(raw, require_siinunit=True)` (`src/ets2v2/sii/hygiene.py:61, 235`).

**Generated `def/sign/board/<board_name>.sii` shape (preserving baseline `model_name: ""`, `board_size`, `font_face`, `coords_*`, `h_align`, `v_align`):**
```text
SiiNunit
{
sign_board_template : _nameless.7c8.5900
{
	model_name: ""
	items: 1
	items[0]: _nameless.7ce.f090
}

sign_template_text : _nameless.7ce.f090
{
	font_face: "/font/sign/gas_segment_7_standard.font"
	coords_l: 0
	coords_r: 1.5
	coords_t: 0.6
	coords_b: 0
	text: "@@fp_es_natural95_ets2v2@@"
}
}
```
> **Unit-name segment rule (`src/ets2v2/sii/hygiene.py:71-115`):** Every dot-separated segment MUST match `[a-z0-9_]{1,12}`.
> - Preserving baseline `board.unit_name` / `board.slot.unit_name` (`_nameless.7c8.5900`) or using file-scoped `.board` / `.text0` passes `validate_unit_name_segments()`.
> - For `locale/<lang>/local_module.ets2v2_fuel.sii`, use **`localization_db : .ets2v2.fuel`** (`ets2v2` = 6 chars, `fuel` = 4 chars). **NEVER** use a >12-char single segment like `.ets2v2_fuel_prices` (18 chars -> fails `unit_segment_too_long` / SCS `00007`)!

**Generated `locale/<lang>/local_module.ets2v2_fuel.sii` shape (identical across all 43 active locales from `locales.json`, `fr_qc` excluded, `fr_ca` included):**
```text
SiiNunit
{
localization_db : .ets2v2.fuel
{
	key[]: "fp_al_diesel_ets2v2"
	val[]: "185"
	key[]: "fp_de_natural95_ets2v2"
	val[]: "1.78<sup>9</sup>"
	key[]: "fp_gb_diesel_ets2v2"
	val[]: "142.9"
}
}
```
- Emit `(key, val)` pairs sorted lexicographically by `key` so all 43 locale files are byte-identical and 100% deterministic across runs.
- Assert `validate_sii_hygiene(raw, require_siinunit=True) == []` on every synthesized board and locale file inside `package/totems.py` before returning bytes (mirroring `_assert_hygiene()` at `src/ets2v2/package/synthesize.py:97-101`).

---

### Pattern E — Package-Independent Offline Totem Validator (`03-04`)

**Analog:** `src/ets2v2/validate/workshop.py:177-191, 912-1056` & `src/ets2v2/validate/invariants.py:323-410`

**Reuse directly (zero `package/` or `fetch/` imports):**
- `ets2v2.sii.sign_board.parse_sign_board` (`src/ets2v2/sii/sign_board.py:108-156`)
- `ets2v2.sii.localization.parse_localization_db` (`src/ets2v2/sii/localization.py:45-57`)
- `ets2v2.baseline.models.FuelBoardsBaseline` & `LocalesBaseline` (`src/ets2v2/baseline/models.py:133-150`)
- `ets2v2.validate.models.ValidationCollector` (`src/ets2v2/validate/models.py:38-89`)

**Exact validation wiring in `src/ets2v2/validate/workshop.py`:**
1. **Zero-DDS hard gate (`D-12`):** Reject `.dds` and `.tobj` files anywhere inside Core packages before extension allowlist check:
   ```python
   FORBIDDEN_TOTEM_EXTENSIONS: Final[frozenset[str]] = frozenset({".dds", ".tobj"})
   ```
   Emit `collector.error("ETS2V2-INV-ZERO-DDS", display_path, f"Zero-DDS policy forbids {suffix!r} texture/object assets in Core packages")`!
2. **Board & Locale collection inside `_validate_package_contents()`:**
   - Match `_SIGN_BOARD_RE = re.compile(r"^def/sign/board/([a-z0-9_]+)\.sii$")` -> parse with `parse_sign_board(raw)`, emit `00008` on parse error, collect into `sign_boards: dict[str, SignBoardTemplate]`.
   - Match `_FUEL_LOCALE_RE = re.compile(r"^locale/([a-z]{2}_[a-z]{2})/local_module\.ets2v2_fuel\.sii$")` -> parse with `parse_localization_db(raw)`, emit `00008` on parse error, collect into `fuel_locales: dict[str, list[LocalizationEntry]]`.
3. **Invariant checks in `src/ets2v2/validate/invariants.py::validate_totem_invariants()`:**
   - `ETS2V2-INV-TOTEM-LOCALES`: Exact `43` locales matching `set(baseline_locales.active_locales)` (`"fr_qc"` explicitly absent, `"fr_ca"` present); zero duplicate keys; every key matches `^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$`; every value non-empty; sorted key order and identical `(key, val)` list across all 43 locales.
   - `ETS2V2-INV-TOTEM-BOARDS`: Every emitted board exists in `baseline_fuel_boards.boards` (and is NOT in `baseline_fuel_boards.excluded_fuel_keyword_boards` and NOT a structural spacer like `gas_empty`); `is_single_text_fuel_candidate is True`; `model_name == ""`; `font_face`, `coords_l/r/t/b` (within `_FLOAT_TOL`), `h_align`, `v_align` match baseline verbatim.
   - `ETS2V2-INV-TOTEM-TOKENS`: Every emitted board's `text_slots[0].localization_key` is non-None, ends with `"_ets2v2"`, and resolves cleanly in `local_module.ets2v2_fuel.sii` (zero dangling tokens, zero orphan keys unused by any board if strict orphan checking is enabled).

---

### Pattern F — CLI Subcommand Registration & `--json` Output (`03-01`..`03-04`)

**Analog:** `src/ets2v2/cli.py:397-476, 802-901`

```python
def _handle_fetch(args: argparse.Namespace) -> int:
    lock_path = cast(Path, args.lock_path)
    allow_jumps = cast(list[str] | None, args.allow_jump) or []
    fx_only = cast(bool, args.fx_only)
    timeout = cast(float, args.timeout)
    dry_run = cast(bool, args.dry_run)
    laws_dir = cast(Path, args.laws_dir)
    mappings_path = cast(Path, args.mappings)
    baseline_dir = cast(Path, args.baseline_dir)
    as_json = cast(bool, args.json)

    try:
        report = run_price_fetch(
            lock_path=lock_path,
            laws_dir=laws_dir,
            mappings_path=mappings_path,
            baseline_dir=baseline_dir,
            allow_jump_iso2=frozenset(code.upper() for code in allow_jumps),
            fx_only=fx_only,
            timeout=timeout,
            write_lock=not dry_run,
        )
    except (FileNotFoundError, OSError, ValueError, ValidationError) as exc:
        print(f"error: price fetch failed: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = report.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if report.ok else 1

    # Human-readable stdout + alert summary to stderr
    ...
    return 0 if report.ok else 1
```

**Conventions:**
- Every attribute read from `argparse.Namespace` MUST use `cast(...)` (`cli.py:55-58, 398-411`).
- Zero `print()` or `logging` inside `fetch/`, `normalize/`, `package/`, `validate/`, `publish/`.
- `--allow-jump` uses `action="append", default=None` (matching `--prefix` at `cli.py:517-522`) so maintainers can override multiple ISO2 codes (`--allow-jump DE --allow-jump PL`).
- Total upstream outage (`0` live Tier 1 fuel feeds reachable, `D-08`) sets `report.ok = False` and exits with POSIX status `1`.

---

### Pattern G — Two-Stage Online/Offline Friday Release Workflow (`03-04`)

**Analog:** `.github/workflows/phase-a-release.yml:41-140`

```yaml
      - name: Fetch live European FX & Tier 1 fuel prices into state/prices.lock.json
        env:
          TANKERKOENIG_API_KEY: ${{ secrets.TANKERKOENIG_API_KEY }}
        run: |
          set -euo pipefail
          uv run ets2v2 fetch --lock-path state/prices.lock.json --json > dist/fetch_summary.json

      - name: Run Phase A diff-gated release build
        id: release
        run: |
          set -euo pipefail
          args=(
            --state state/published.json
            --prices-lock state/prices.lock.json
            --out-dir dist
            --changelogs-dir .
            --write-state
          )
          if [ "${FORCE_RUN:-false}" = "true" ]; then
            args+=(--force)
          fi
          uv run --offline ets2v2 publish release "${args[@]}"
```

And in the persistent Release PR staging loop (`.github/workflows/phase-a-release.yml:112-114`):
```yaml
          for f in state/published.json state/prices.lock.json CHANGELOG_SUMMER.md CHANGELOG_WINTER.md; do
            if [ -f "$f" ]; then git add "$f"; fi
          done
```

**CRITICAL SECURITY RULE (enforced by `tests/test_publish_workflow.py:151-157`):**
- Pass `TANKERKOENIG_API_KEY` **exclusively** via step-level `env:` — **NEVER** put `${{ ... }}` inside any `run:` block!
- Keep `uv run --offline` on quality gates, `publish release`, and `validate workshop`/`validate local` so only the single explicit `ets2v2 fetch` step touches the network (`D-05`).
- Keep `.github/workflows/ci.yml` untouched (read-only `permissions: contents: read`, 100% offline `pytest`).

---

## 4. Exact Reusable Phase 1 & 2 APIs & Signatures

Phase 3 modules **MUST reuse** these existing symbols directly rather than duplicating parsing, hygiene, snapshot, or synthesis helpers.

### `ets2v2.baseline.models` (`src/ets2v2/baseline/models.py`)

| Symbol | Line | Exact Fields / Contract | Phase 3 Consumers |
|---|---|---|---|
| `BaselineCountry` | `:38` | `slug`, `iso_country_code`, `fuel_price: float \| None`, ... | `normalize.lockfile` (D-01 non-EU baseline seeding), `registry.snapshot` |
| `CountriesBaseline` | `:71` | `countries: list[BaselineCountry]` | `fetch.pipeline`, `normalize.lockfile`, `registry.snapshot` |
| `FuelBoardSlot` | `:100` | `slot_index: int`, `unit_name: str`, `font_face: str \| None`, `coords_l/r/t/b: float \| None`, `h_align: str \| None`, `v_align: str \| None`, `text: str \| None` | `normalize.totem_format`, `package.totems`, `validate.invariants` |
| `FuelBoardEntry` | `:117` | `board_name: str`, `vfs_path: str`, `unit_name: str`, `model_name: str`, `board_size: tuple[float, float] \| None`, `items_count: int`, `classification: Literal["active_fp", "placeholder", "blank"]`, `fp_key: str \| None`, `slot: FuelBoardSlot` | `normalize.totem_format`, `package.totems`, `validate.invariants` |
| `FuelBoardsBaseline` | `:133` | `total_sign_boards: int`, `excluded_fuel_keyword_boards: list[str]` (the 5 highway signs), `boards: list[FuelBoardEntry]` (461 single-text boards) | `package.builder`, `package.totems`, `validate.workshop`, `validate.invariants` |
| `LocalesBaseline` | `:143` | `active_locales: list[str]` (exact 43 locales, `fr_ca` in, `fr_qc` out), `tz_keys: list[str]` (12), `fp_keys: list[str]` (99) | `package.totems`, `validate.workshop`, `validate.invariants` |

### `ets2v2.sii` (`src/ets2v2/sii/sign_board.py`, `localization.py`, `hygiene.py`)

| Symbol | Location | Exact Signature | Phase 3 Consumers |
|---|---|---|---|
| `SignTemplateTextSlot` | `sign_board.py:16` | Frozen Pydantic model + `.localization_key -> str \| None` property (`:33`) | `validate.invariants`, `tests/test_totem_engine.py` |
| `SignBoardTemplate` | `sign_board.py:45` | Frozen Pydantic model + `.is_single_text_fuel_candidate -> bool` property (`:59`) | `validate.workshop`, `validate.invariants`, `tests/test_totem_engine.py` |
| `parse_sign_board` | `sign_board.py:108` | `(source: str \| bytes) -> SignBoardTemplate` | `validate.workshop`, `tests/test_totem_engine.py` |
| `LocalizationEntry` | `localization.py:13` | `key: str`, `val: str` | `validate.workshop`, `validate.invariants`, `tests/test_totem_engine.py` |
| `parse_localization_db` | `localization.py:45` | `(source: str \| bytes) -> list[LocalizationEntry]` | `validate.workshop`, `tests/test_totem_engine.py` |
| `serialize_sii_text` | `hygiene.py:61` | `(text: str) -> bytes` (UTF-8 no-BOM LF) | `package.totems`, `package.metadata` |
| `validate_unit_name_segments` | `hygiene.py:71` | `(unit_name: str, *, line: int = 1, column: int = 1) -> list[SiiDiagnostic]` | `package.totems`, `validate.workshop` |
| `validate_sii_hygiene` | `hygiene.py:235` | `(source: str \| bytes, *, require_siinunit: bool = False) -> list[SiiDiagnostic]` | `package.totems`, `validate.workshop` |

### `ets2v2.registry`, `ets2v2.package`, `ets2v2.publish`

| Symbol | Location | Exact Signature / Contract | Phase 3 Integration |
|---|---|---|---|
| `RealismSnapshotFuel` | `registry/snapshot.py:29` | **LOCKED `schema_version: 1` (`D-13`):** `currency: str`, `eur_per_liter: float`, `local_prices: dict[str, float]`, `source: str` (`extra="forbid"`) | Populated from `PricesLockfile` with 3-dec `eur_per_liter` (`D-15`) and canonical grade keys (`D-14`) |
| `build_realism_snapshot` | `registry/snapshot.py:72` | Add keyword-only `prices_lock: PricesLockfile \| None = None` | Default `None` keeps `baseline_1.62`; live lockfile fills `RealismSnapshotFuel` |
| `format_sii_string` | `package/synthesize.py:20` | `(value: str) -> str` (rejects `\` & `\x00`) | Reused in `package/totems.py` for quoting board `text`/`font_face` and locale `key[]`/`val[]` |
| `_format_fuel_price` | `package/synthesize.py:51` | `(value: float) -> str` (strips trailing zeros cleanly) | Already emits `resolved.fuel.eur_per_liter` at `synthesize.py:129` |
| `_diff_country` | `publish/changelog.py:31` | Lines 60–82 already diff `fuel.eur_per_liter`, `fuel.currency`, `fuel.source`, and `fuel.local_prices`! | Keep intact; add 36-country table, Circuit-Breaker Alerts section, and `D-16` attributions |
| `compute_workshop_canonical_sha256` | `publish/ledger.py:65` | Recursively hashes ALL files under `workshop_dir` (ignoring only `package_version`) | Automatically detects weekly fuel price / totem / locale changes with zero edits needed to `ledger.py`! |

---

## 5. Key Integration Points, Regression Traps & Typing/CI Guardrails

### Regression Trap Checklist (Existing Tests & Code Impacted by Phase 3)

Every item below was verified directly against the current repository source and test suite:

1. **TRAP 1 — Hardcoded `76` / `75` Core File Counts (`tests/test_package_builder.py:64, 78, 104, 131, 196`):**
   - Phase 2 asserts `info.workshop_file_count == 76`, `len(workshop_files) == 76`, `len(infos) == 75`, `len(listed) == 75`, and `built.workshop_file_count == 76` (1 `versions.sii` + 1 `manifest.sii` + 1 `mod_icon.jpg` + 1 `description.txt` + 36 `.sui` + 36 `speed_limits.sii`).
   - Once Plan `03-03` emits `N_boards` `def/sign/board/*.sii` overrides plus `43` `locale/<lang>/local_module.ets2v2_fuel.sii` modules into `shared_payloads`, Workshop file count becomes **`76 + N_boards + 43`** and Local ZIP entry count becomes **`75 + N_boards + 43`**.
   - **Action:** Plan `03-03` MUST update all five count assertions in `tests/test_package_builder.py` (preferring an explicit breakdown formula `76 + expected_board_count + 43` and asserting exact board & locale paths) and verify `def/sign/board/*.sii` and `locale/*/local_module.ets2v2_fuel.sii` mount cleanly in `ZipArchive` and `VfsStack`.

2. **TRAP 2 — `RealismSnapshot` `schema_version: 1` Lock & Backwards-Compatible Default (`src/ets2v2/registry/snapshot.py:29-138` & `tests/test_registry_snapshot.py:50-52, 129-132`):**
   - `tests/test_registry_snapshot.py:50-52` asserts `EXPECTED_FUEL_KEYS == {"currency", "eur_per_liter", "local_prices", "source"}` and lines `191-198` assert `schema_version: 2` and extra keys fail with `ValidationError`. **NEVER** add provenance fields (`fetched_at`, `fx_rate`, `alerts`, `is_fallback`) to `RealismSnapshot` or `RealismSnapshotFuel` (`D-13`) — keep all operational provenance strictly in `state/prices.lock.json`.
   - `tests/test_registry_snapshot.py:129-132` calls `build_realism_snapshot(registry, bl_countries, bl_locales, "summer")` **without** `prices_lock` and asserts `country.fuel.source == "baseline_1.62"`, `country.fuel.local_prices == {}`, and `country.fuel.eur_per_liter == bl.fuel_price`.
   - **Action:** Make `prices_lock: PricesLockfile | None = None` an optional keyword-only argument on `build_realism_snapshot()`. When `None`, preserve exact Phase 2 `baseline_1.62` behavior; when supplied (default inside `package/builder.py` and `publish/release.py`), populate `eur_per_liter=round(entry.eur_per_liter, 3)` (`D-15`), `local_prices=dict(entry.local_prices)` (`D-14`), `currency=entry.currency`, and `source=entry.source`.
   - Note also `tests/test_registry_snapshot.py:214-262` (`ets2v2 registry snapshot` CLI test): if CLI `--prices-lock` defaults to `Path("state/prices.lock.json")` and loads it when present (or accepts `--no-prices-lock`), verify `test_cli_registry_snapshot_winter_date_override_and_invalid_date` stays green (it checks `schema_version`, `edition`, `anchor_date`, `HR.lights_mandatory`, `DE.time_zone`, `DE.time_zone_name`).

3. **TRAP 3 — `ALLOWED_SCS_ASSET_EXTENSIONS` Currently Permits `.dds` & `.tobj` (`src/ets2v2/validate/workshop.py:76-98`):**
   - Lines `82–83` of `src/ets2v2/validate/workshop.py` currently include `".dds"` and `".tobj"` in `ALLOWED_SCS_ASSET_EXTENSIONS`!
   - Under `D-12` ("Zero `.dds` or `.tobj` files anywhere in the mod package (Zero-DDS guarantee)"), the Offline SCS Validator MUST fail hard if any `.dds` or `.tobj` appears in a Core Workshop directory or local ZIP.
   - **Action:** Plan `03-04` MUST check `FORBIDDEN_TOTEM_EXTENSIONS = frozenset({".dds", ".tobj"})` **before** the `ALLOWED_SCS_ASSET_EXTENSIONS` check (or remove them from Core allowlist and emit a dedicated `ETS2V2-INV-ZERO-DDS` error) and add explicit fault-injection tests in `tests/test_validate_workshop.py` / `tests/test_validate_invariants.py`.
   - **Secondary trap in `tests/test_validate_workshop.py:244-737`:** Existing SCS `00001`–`00010` fault-injection tests call `validate_workshop_package(ws)` **without** `baseline_dir`. Ensure Zero-DDS and SII hygiene/parse checks run unconditionally, while baseline-comparison totem checks (43-locale parity against `locales.json`, baseline `font_face`/`coords_*` parity against `fuel_boards.json`) run when `baseline_dir is not None` — matching how `validate_core_realism_invariants()` is gated at `workshop.py:1237, 1290, 1376`.

4. **TRAP 4 — `description.txt` Zero-Volatile-Token Regex (`tests/test_package_icons_metadata.py:179-181`):**
   - `test_render_description_txt_hygiene_attribution_and_no_volatile_tokens` explicitly enforces:
     ```python
     assert re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text) is None
     assert re.search(r"1\.62-\d{4}\.\d{2}", text) is None
     ```
   - **Action:** When adding the `D-16` open-data attribution block to `render_description_txt()` (`src/ets2v2/package/metadata.py:78-121`), include all required source/license names (`EC Weekly Oil Bulletin CC BY 4.0`, `fuel-prices.eu CC BY 4.0`, `UK DESNZ OGL v3`, `Norway SSB CC BY 4.0`, `France Licence Ouverte`, `Italy MIMIT IODL 2.0`, `Spain MITECO`, `Netherlands CBS`, `Germany Tankerkönig CC BY 4.0`, `Frankfurter v2 MIT`, `ECB`, `fawazahmed0 CC0`) **without** embedding any ISO date (`YYYY-MM-DD`) or `1.62-YYYY.WW` version string!

5. **TRAP 5 — Zero `${{` Inside Workflow `run:` Shell Bodies (`tests/test_publish_workflow.py:151-157`):**
   - `test_phase_a_workflow_injection_safety_and_job_level_force_run` extracts every `run:` block in `.github/workflows/phase-a-release.yml` and fails if `"${{"` appears anywhere inside a `run:` script!
   - **Action:** Wire `TANKERKOENIG_API_KEY` via step-level `env: TANKERKOENIG_API_KEY: ${{ secrets.TANKERKOENIG_API_KEY }}` (mirroring `GH_TOKEN: ${{ github.token }}` at line 105). Preserve `'if [ -f "$f" ]; then git add "$f"; fi'` (asserted at `tests/test_publish_workflow.py:104`) when adding `state/prices.lock.json` to the staged files list. Ensure `dist/` exists (`mkdir -p dist`) before redirecting `--json > dist/fetch_summary.json`!

6. **TRAP 6 — `tests/test_cli_scaffold.py` Exact Dependency List & Layout Guards (`lines 63-157`):**
   - Line `68`: `deferred_phase_dirs = {"fetch", "normalize", "merge"}` -> must become `{"merge"}` and unlock `"fetch"`, `"normalize"`.
   - Lines `99–103`: `sorted(_as_str_list(project["dependencies"])) == [...]` -> exact list equality! Must become:
     ```python
     [
         "httpx>=0.28,<0.29",
         "openpyxl>=3.1,<4",
         "pillow>=12,<14",
         "pydantic>=2.14,<3",
         "tzdata>=2025.2",
     ]
     ```
   - Lines `148–157`: extend `expected` set in `test_uv_lock_contains_verified_packages()` with `"httpx"` and `"openpyxl"`.

7. **TRAP 7 — `tests/test_publish_release.py` Backwards-Compatible Changelog & Release Defaults (`lines 52-261, 366-405`):**
   - `test_render_edition_changelog_initial_and_diff` and `test_changelog_diff_renders_max_limit_uncommon_currency_and_local_prices` call `render_edition_changelog(...)` without `prices_lock`. Make `prices_lock: PricesLockfile | None = None` optional (keyword-only) so all existing calls remain valid, render the 36-country fuel table from `snapshot.countries` (augmented with freshness dates from `prices_lock` when provided), and render the **Circuit-Breaker & Staleness Alerts** section whenever `prices_lock` has active alerts (`D-16`).
   - `test_single_edition_winter_change_keeps_summer_untouched` mutates only `hr.json` winter DRL; because `state/prices.lock.json` is constant across both runs, Summer's canonical SHA-256 (including all totems & 43 locale files) stays identical -> `summer_changed is False` remains valid!
   - `tests/test_publish_ledger.py:43, 224` uses synthetic `file_count=76` inside `_sample_edition_state()` unit helper — unaffected by real build counts, keep passing.

8. **TRAP 8 — `data/` Clean-Room Guard (`tests/test_baseline_contracts.py:83-89` & `tests/test_registry_contracts.py:141-144`):**
   - Both tests recursively scan `data/` and fail if any `.sii` or `.sui` file exists under `data/`. `state/prices.lock.json` lives under `state/`, and any Phase 3 lookup data committed under `data/` (if any) MUST be canonical sorted UTF-8 no-BOM LF `.json` only.

### `basedpyright` (`strict`) & `ruff` Phase 3 Pitfalls

`pyproject.toml` enforces `basedpyright` in `strict` mode (`pythonVersion = "3.12"`, zero `# type: ignore` / `# pyright: ignore`) and `ruff` (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`, `line-length = 100`, zero `# noqa`) across **both `src/` and `tests/`**:

1. **`openpyxl` Stubs under Strict `basedpyright` (`reportMissingTypeStubs`):**
   - `openpyxl` does not ship `py.typed`. Importing `openpyxl` under `typeCheckingMode = "strict"` fails with `reportMissingTypeStubs` unless **`types-openpyxl`** (Apache-2.0 typeshed stubs) is added to `[dependency-groups].dev` in `pyproject.toml` (and locked in `uv.lock`)!
   - Narrow every `openpyxl` worksheet cell value (`cell.value`) carefully: check `isinstance(val, (int, float)) and not isinstance(val, bool)` before numeric conversion (in Python, `isinstance(True, int)` is `True`!).
   - `wb.active` is typed as `Worksheet | None` — narrow with `if ws is None: raise ValueError(...)`.
2. **`xml.etree.ElementTree` Typing (`ECB` & `CBR` XML):**
   - `ET.fromstring(raw)` returns `ET.Element`; `.attrib.get(...)` and `.find(...)` / `.findtext(...)` return `str | None` / `ET.Element | None`. Narrow every nullable lookup explicitly before `.strip()` or `float(...)`.
   - Use `xml.etree.ElementTree` safely (no external entity expansion; stdlib `ElementTree` expat does not load external DTDs/entities by default, and reject oversized responses before parsing).
3. **`httpx` Typing:**
   - `httpx` ships `py.typed`. Type `MockTransport` handlers explicitly as `def _handler(request: httpx.Request) -> httpx.Response:`.
   - `response.json()` returns `Any` — narrow immediately via `cast(dict[str, object], response.json())` or validate straight through a strict Pydantic `BaseModel.model_validate_json(response.content)`! Using `model_validate_json(response.content)` directly avoids untyped `dict` traversal altogether.
4. **Ruff Compliance (`I`, `B905`, `B904`, `SIM117`, `RUF022`, `RUF012`):**
   - Absolute imports only (`from ets2v2.normalize.models import PricesLockfile`), never relative imports.
   - Always `zip(..., strict=True)` (`B905`), `raise ... from exc` (`B904`), combined `with (a, b):` (`SIM117`), alphabetically sorted `__all__` in `normalize/__init__.py` and `fetch/__init__.py` (`RUF022`), `Final[...]` on module constants.

---

## 6. No Analog Found

Files introducing net-new Phase 3 external I/O libraries with no direct Phase 1/2 analog (planner should follow `03-RESEARCH.md` endpoint/workbook contracts while copying Pattern A/B/C/F typing & testing discipline above):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/ets2v2/fetch/http.py` | utility / transport | request-response | First `httpx` HTTP client & `MockTransport` abstraction in the repo (Phases 1–2 were 100% offline) |
| `src/ets2v2/fetch/ec_bulletin.py` | service / collector | request-response + transform | First Drupal HTML `.xlsx` link discovery + `openpyxl` spreadsheet parser in the repo |
| `src/ets2v2/fetch/national.py` | service / collector | request-response + transform | First multi-format national government API adapters (JSON/CSV/OData/ZIP-XML across `UK`/`NO`/`FR`/`DE`/`ES`/`IT`/`NL`) |

---

## Metadata

**Analog search scope:** `src/ets2v2/`, `tests/`, `state/`, `data/baselines/ets2_1.62_def/`, `.github/workflows/`, `pyproject.toml`
**Files scanned:** 31 tracked source, config, workflow, baseline, and test files (all verified git-tracked via `git ls-files`)
**Pattern extraction date:** 2026-11-21
