# Phase 5: Global Tier 1/2/3 Coverage & Internal OSM Audit - Pattern Map

**Mapped:** 2026-11-25
**Phase Scope:** `GLB-01`, `GLB-02`, `GLB-03`, `GLB-04` (Plans `05-01` through `05-04`)
**Recommended Execution Wave Ordering:** **Wave 1 (`05-03` / `GLB-03`)** -> **Wave 2 (`05-01` / `GLB-01`)** -> **Wave 3 (`05-02` / `GLB-02` & `05-04` / `GLB-04`, or `05-02` Wave 3 / `05-04` Wave 4 to avoid concurrent `cli.py` edits)** — `src/ets2v2/fetch/pipeline.py:403` drops quotes for any ISO-2 absent from `ALL_LOCKFILE_TERRITORY_ISO2S`, so the `225`-territory / `~156`-FX foundation (`05-03`) MUST land first.
**Files analyzed:** 44 planned new/modified files (8 new Python modules across `src/ets2v2/fetch/` and `src/ets2v2/audit/`, 16 modified Python modules across `normalize/`, `registry/`, `fetch/`, `validate/`, `publish/`, `cli.py`, 5 data/state artifacts, 2 GitHub Actions workflows, 13 new/updated test files)
**Analogs found:** 41 / 44 (3 net-new modules introduce capabilities with no direct Phase 1–4 analog — stdlib HTML table/charset extraction in `fetch/_html.py`, `westnordost/osm-legal-default-speeds` + Overpass/Taginfo speed-limit drift diffing in `audit/osm_speeds.py` & `audit/overpass.py` — while strictly replicating Phase 1–4 Pydantic v2, `fetch/http.py`, `httpx.MockTransport`, determinism, and CLI/test conventions)

---

## 1. Proposed Phase 5 Package & Module Layout

### Subpackage Alignment (`src/ets2v2/`)

Per `05-CONTEXT.md` (`D-16`), Phase 5 introduces one strictly quarantined subpackage **`audit/`** under `src/ets2v2/` — unlocked in `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` (`allowed_phase5_entries`).

**Layering Decision (`audit/` as Layer 7C — ONLINE-ONLY CI/AUDIT QUARANTINE, strictly zero inbound imports from all 10 non-audit subpackages):**
1. **`normalize/` (Layer 5 — 100% OFFLINE)** loads clean-room `data/mappings/currencies.json` and `data/curated/tier3_fuel_baselines.json` purely via stdlib `json`, `pathlib`, `functools.lru_cache`, and `pydantic` — **zero** `registry/`, `fetch/`, `audit/`, `httpx`, or `openpyxl` imports (`D-10`).
2. **`fetch/` (Layer 7A — ONLINE ONLY)** absorbs `global_tier1.py` (`GLB-01`), `tier2_portals.py` (`GLB-02`), and stdlib `_html.py` (`D-06`), promotes `_validate_ooxml_zip_safety` to shared `_parsing.py`, adds `code` query-param redaction + form-POST support in `http.py`, and isolates EU Core vs Global Tier 1 outage gates in `pipeline.py` (`D-02`). `fetch/` NEVER imports `audit/`.
3. **`audit/` (Layer 7C — ONLINE-ONLY CI/AUDIT QUARANTINE)** sits parallel to `package/` (Layer 7B) and strictly **above** `fetch.http` (Layer 7A, reusing `create_http_client`, `validate_https_url`, `fetch_bytes_with_retry`, `post_form_bytes_with_retry`, `redact_url_secrets`), `registry/` (Layer 6, `load_law_registry`, `load_realism_snapshot`), `normalize/` (Layer 5, `load_prices_lockfile`), and `vfs/` (Layer 2, `open_archive`, `ZipArchive`, `DirectoryArchive` for package scanning). **`audit/` is imported ONLY by `cli.py` (Layer 10) and `tests/` — ZERO of the 10 non-audit subpackages may ever import `ets2v2.audit` (`D-16`).**
4. **`validate/` (Layer 8 — 100% OFFLINE, STRICTLY INDEPENDENT OF `audit/`)** NEVER imports `audit/` (nor `package/`, `merge/`, `normalize/`, `fetch/`, `publish/`, `httpx`, `openpyxl`). Instead, `validate/invariants.py` embeds a tiny pure-stdlib `check_license_taint_bytes()` check emitting `ETS2V2-INV-LICENSE-TAINT`, invoked on every decoded `.sii`/`.sui`/`.txt` member in `validate/workshop.py` so every built Workshop/local/ProMods/combo package is automatically taint-checked without breaching the `audit/` quarantine wall!

```text
src/ets2v2/
├── __init__.py                   # Existing — __version__ = "0.1.0"
├── py.typed                      # Existing — PEP 561 marker
├── cli.py                        # Modified (05-02, 05-04) — add `--no-global`, `--no-tier2` on `fetch`;
│                                 #   add `ets2v2 audit osm-speeds` and `ets2v2 audit taint`
├── vfs/                          # Existing (Phase 1, Layers 0-2) — unchanged; zero audit imports
├── sii/                          # Existing (Phase 1, Layers 0-3) — unchanged; zero audit imports
├── baseline/                     # Existing (Phase 1, Layer 4) — unchanged; zero audit imports
├── normalize/                    # Modified (Layer 5 — 100% OFFLINE, zero registry/fetch/audit/httpx/openpyxl)
│   ├── __init__.py               # Modified (05-03, 05-02) — export new currency/baseline loaders & staleness consts
│   ├── models.py                 # Existing (or additive clean-room schema models for currencies/baselines)
│   ├── currencies.py             # Modified (05-03) — Pydantic-validated JSON loaders for
│   │                             #   data/mappings/currencies.json & data/curated/tier3_fuel_baselines.json
│   │                             #   preserving ALL Phase 3/4 module-level constant exports (D-10)
│   ├── fx.py                     # Modified (05-03) — expand EXTENDED_ECB_CURRENCIES (2 -> 18) &
│   │                             #   _OPTIONAL_EXTENDED_CURRENCIES (24 -> ~139) with is_extended=True (D-11)
│   ├── fuel.py                   # Modified (05-03) — include TIER3_CURATED_BASELINE_SOURCE in _SEEDED_SOURCES
│   │                             #   while preserving strict [0.01, 5.00] EUR/L bounds on all live feeds
│   ├── lockfile.py               # Modified (05-03, 05-02) — seed 225 territories from tier3_fuel_baselines.json
│   │                             #   with 0.010 EUR/L floor support (05-03); tier/cadence-aware staleness
│   │                             #   14d / 45d / 105d / 30d / 180d in evaluate_lockfile_staleness() (05-02)
│   └── totem_format.py           # Modified (05-03) — optional global integer/3-dec currency formatting sets
│                                 #   (JPY/KRW/IDR/VND/CLP/COP/PYG/UGX/TZS/RWF/XOF/XAF; KWD/BHD/OMR)
├── registry/                     # Modified (Layer 6 — 100% OFFLINE, zero fetch/audit/package/validate/merge/publish)
│   ├── timezone.py               # Modified (05-03) — add 58 verified global IANA_NUMERIC_ABBR_OVERRIDES
│   │                             #   (incl. seasonal tuples America/Santiago & America/Miquelon)
│   └── (models, loader, snapshot) # Existing — schema_version: 1 frozen (D-09); zero schema changes!
├── fetch/                        # Modified (Layer 7A — ONLINE ONLY, imported ONLY by cli.py & audit/overpass+osm)
│   ├── __init__.py               # Modified (05-01, 05-02) — export global Tier 1 & Tier 2 symbols (RUF022 sorted)
│   ├── http.py                   # Modified (05-01, 05-04) — add `code` to _SECRET_QUERY_RE (KR Opinet fix!);
│   │                             #   add bounded post_form_bytes_with_retry() for opt-in Overpass POST
│   ├── _parsing.py               # Modified (05-01) — promote validate_ooxml_zip_safety() from ec_bulletin.py
│   │                             #   for shared OOXML ZIP-bomb/XXE safety across EC WOB, JP, RU, ZA, NG
│   ├── _html.py                  # NEW (05-02) — stdlib-only TableExtractor(HTMLParser), text/block helpers,
│   │                             #   decode_with_fallbacks() (UTF-8 / windows-1251 / Latin-1) (D-06)
│   ├── models.py                 # Modified (05-01, 05-02) — RawFuelFeedResult: tier Literal["tier1","tier2","fallback"],
│   │                             #   region_scope Literal["eu_core","global"]="eu_core", skip_reason, error_code;
│   │                             #   FetchRunReport additive eu_tier1/global_tier1/tier2 counters (D-02, D-07)
│   ├── ec_bulletin.py            # Modified (05-01) — import shared validate_ooxml_zip_safety from _parsing.py
│   ├── national.py               # Modified (05-01) — set skip_reason on de_tankerkoenig
│   ├── global_tier1.py           # NEW (05-01) — 8 non-EU Tier 1 collectors (US EIA, BR ANP, AR Energía,
│   │                             #   CO SICOM/CREG, CL CNE, MY OpenDOSM, JP METI, KR Opinet) + orchestrator
│   ├── tier2_portals.py          # NEW (05-02) — 10 guarded Tier 2 collectors (IS, CH, MD, MK, RU, IL, AE, ZA,
│   │                             #   SA, NG) + _run_tier2_guarded() per-country circuit breaker (D-05..D-07)
│   └── pipeline.py               # Modified (05-01, 05-02) — wire Global Tier 1 + Tier 2, separate EU Core vs
│                                 #   Global Tier 1 outage gate, feed precedence, include_global/include_tier2
├── package/                      # Existing (Layer 7B — 100% OFFLINE) — unchanged; Core strictly 36 countries
├── audit/                        # NEW (Phase 5, Layer 7C — ONLINE-ONLY QUARANTINE, ZERO INBOUND IMPORTS!)
│   ├── __init__.py               # Public __all__ facade (sorted alphabetically, RUF022)
│   ├── models.py                 # Strict frozen Pydantic v2 DTOs: SpeedAuditAllowlist, SpeedAuditAllowlistEntry,
│   │                             #   SpeedDriftFinding, OsmSpeedAuditReport, OverpassSpotCheck,
│   │                             #   TaginfoDistribution, TaintViolation, TaintScanReport
│   ├── osm_speeds.py             # westnordost/osm-legal-default-speeds parser + data/laws/ diff + clean-room
│   │                             #   allowlist splitter + sanitized Markdown/JSON report renderer (D-13, D-15)
│   ├── overpass.py               # Opt-in Overpass (`out tags;`) & Taginfo v4 spot-check client reusing
│   │                             #   ets2v2.fetch.http with polite sleep_fn pacing & country cap (D-13)
│   └── taint.py                  # Full provenance & license-taint scanner across data/, state/, snapshots,
│                                 #   and built Workshop/local .zip/.scs packages (D-16)
├── validate/                     # Modified (Layer 8 — 100% OFFLINE, validate ⊥ audit ⊥ package ⊥ merge ⊥ fetch)
│   ├── invariants.py             # Modified (05-04) — add self-contained pure-stdlib check_license_taint_bytes()
│   │                             #   emitting ETS2V2-INV-LICENSE-TAINT (zero ets2v2.audit import!)
│   └── workshop.py               # Modified (05-04) — invoke check_license_taint_bytes() on every decoded
│                                 #   .sii/.sui/.txt file across core/promods/combo profiles
├── merge/                        # Existing (Layer 9A — 100% OFFLINE) — unchanged; benefits from 225 territories
└── publish/                      # Modified (Layer 9B — 100% OFFLINE)
    └── changelog.py              # Modified (05-02) — add compact Global Snapshot Coverage summary block,
                                  #   Tier 3 staleness/fallback rollup, and Global Tier 1/2 attributions (D-08, D-12)
```

### Complete Acyclic Module DAG Verification (Layers 0–10)

Phase 5 preserves a strictly bottom-up **11-layer DAG (Layers 0–10)** with **zero cycles** and **seven hard AST-enforced isolation walls**:

```text
Layer 10: ets2v2.cli
            ├──► ets2v2.vfs, ets2v2.baseline                    (Phase 1)
            ├──► ets2v2.registry, ets2v2.package,
            │    ets2v2.validate, ets2v2.publish                (Phase 2)
            ├──► ets2v2.normalize, ets2v2.fetch                 (Phase 3 + Phase 5 GLB-01/02)
            ├──► ets2v2.merge                                   (Phase 4)
            └──► ets2v2.audit                                   (Phase 5 GLB-04 — ONLY cli.py & tests!)

Layer 9A: ets2v2.merge    [OFFLINE — merge ⊥ fetch ⊥ publish ⊥ audit, zero httpx/openpyxl]
Layer 9B: ets2v2.publish  [OFFLINE — publish ⊥ fetch ⊥ merge ⊥ audit, zero httpx/openpyxl]
Layer 8:  ets2v2.validate [OFFLINE — validate ⊥ audit ⊥ package ⊥ merge ⊥ normalize ⊥ fetch ⊥ publish]

Layer 7C: ets2v2.audit    {models, osm_speeds, overpass, taint} [ONLINE-ONLY CI/AUDIT QUARANTINE]
            └──► ets2v2.fetch.http (only), ets2v2.registry.{models, loader, snapshot},
                 ets2v2.normalize.{models, lockfile}, ets2v2.vfs.{hashfs, zip_archive, dir_archive, types},
                 httpx, pydantic, stdlib
            *** ZERO of the 10 non-audit subpackages may EVER import ets2v2.audit! ***

Layer 7B: ets2v2.package  [OFFLINE — package ⊥ merge ⊥ validate ⊥ fetch ⊥ publish ⊥ audit]
Layer 7A: ets2v2.fetch    {models, http, _parsing, _html, fx,   [ONLINE ONLY — fetch ⊥ audit]
                           ec_bulletin, national, global_tier1,
                           tier2_portals, pipeline}
            └──► httpx, openpyxl, ets2v2.baseline.models, ets2v2.normalize.*

Layer 6:  ets2v2.registry [OFFLINE — registry ⊥ package ⊥ merge ⊥ validate ⊥ fetch ⊥ publish ⊥ audit]
Layer 5:  ets2v2.normalize [OFFLINE — pure domain + stdlib JSON loaders for data/{mappings,curated}]
Layer 4:  ets2v2.baseline  (Phase 1 — unchanged; zero audit imports)
Layer 3:  ets2v2.sii.{country, speed_limits, sign_board, localization} (zero audit imports)
Layer 2:  ets2v2.vfs.{hashfs, stack}  |  ets2v2.sii.document           (zero audit imports)
Layer 1:  ets2v2.vfs.{cityhash, dir_archive, zip_archive} | ets2v2.sii.hygiene
Layer 0:  ets2v2.__init__ | ets2v2.vfs.types | ets2v2.sii.lexer
```

**Seven Mandatory AST-Enforced Isolation Walls (`tests/test_cli_scaffold.py:271-293` & `tests/test_validate_workshop.py:88-136`):**
1. **`validate` wall:** NEVER imports `package`, `merge`, `normalize`, `fetch`, `publish`, **`audit`**, `httpx`, or `openpyxl`.
2. **`merge` wall:** NEVER imports `fetch`, `publish`, **`audit`**, `httpx`, or `openpyxl`.
3. **`package` wall:** NEVER imports `fetch`, `merge`, `validate`, `publish`, **`audit`**, `httpx`, or `openpyxl`.
4. **`publish` wall:** NEVER imports `fetch`, `merge`, **`audit`**, `httpx`, or `openpyxl`.
5. **`normalize` wall:** NEVER imports `fetch`, `registry`, `package`, `validate`, `merge`, `publish`, **`audit`**, `httpx`, or `openpyxl`.
6. **`registry` wall:** NEVER imports `fetch`, `package`, `validate`, `merge`, `publish`, **`audit`**, `httpx`, or `openpyxl`.
7. **Global `audit` Quarantine Wall (NEW — `D-16`):** ALL 10 non-audit subpackages (`vfs`, `sii`, `baseline`, `normalize`, `registry`, `fetch`, `package`, `validate`, `merge`, `publish`) MUST have **zero** imports of `ets2v2.audit`! (And `audit/` itself NEVER imports `package`, `merge`, `publish`, `validate`, or `openpyxl`.)

### Non-Python Repository Artifacts Added / Modified in Phase 5

| Path | Plan (Wave) | Committed? | Format / Hygiene Contract |
|---|---|---|---|
| `data/mappings/currencies.json` | `05-03` (W1) | Yes | Canonical sorted UTF-8 no-BOM LF JSON (`schema_version: 1`): `~156` ISO-4217 currencies (`pinned`/`core`/`extended`, ECB flags, sanity envelopes, reference rates) + `225` ISO-2 -> currency map (`D-10`, `D-11`) |
| `data/curated/tier3_fuel_baselines.json` | `05-03` (W1) | Yes | Canonical sorted UTF-8 no-BOM LF JSON (`schema_version: 1`, `license: "CC BY 4.0"`): `~186` non-Vanilla EUR/L baselines with `verified_date`, `clamped_to_floor`, and zero taint markers (`D-10`, `D-11`, `D-16`) |
| `data/laws/countries/<iso2>.json` | `05-03` (W1) | Yes | Expanded from `76` to **`225`** canonical sorted UTF-8 no-BOM LF `CountryLawRecord` files covering all 195 UN states + `XK` + ProMods + 21 global map-combo territories (`D-09`); zero `.sii`/`.sui` under `data/` |
| `data/mappings/ets2_countries.json` | `05-03` (W1) | Yes | Expanded from `76` to **`225`** sorted entries: exact `36` `vanilla_1_62: true` (non-null `country_id`) + `189` `vanilla_1_62: false` (`country_id: null`) covering 100% of `country_aliases.json` targets (`D-09`) |
| `state/prices.lock.json` | `05-03` (W1) | Yes | Canonical sorted UTF-8 no-BOM LF `PricesLockfile` (`schema_version: 1`) expanded to `225` territories / `~156` FX rates; `IR`/`VE` floor-clamped at `0.010 EUR/L` (`D-09`, `D-11`) |
| `data/laws/speed_audit_allowlist.json` | `05-04` (W3/4) | Yes | Clean-room sorted UTF-8 no-BOM LF JSON (`schema_version: 1`) recording intentional statutory/ETS2 deviations with **zero OSM text/URLs** (`D-15`, `D-16`) |
| `.github/workflows/phase-a-release.yml` | `05-01` (W2) & `05-02` (W3) | Yes | UTF-8 no-BOM LF; wire optional `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN` via step `env:`; add EU vs Global Tier 1 / Tier 2 counters & Tier 3 alert rollup in step summary + PR body; zero `${{` inside `run:` (`D-01`, `D-02`, `D-08`) |
| `.github/workflows/osm-speed-audit.yml` | `05-04` (W3/4) | Yes | Standalone monthly workflow (`cron: "0 7 1-7 * 1"` + `workflow_dispatch`), `permissions: contents: read, issues: write` (zero Git writes), artifact upload, sanitized Step Summary, rolling `osm-audit` GitHub Issue, zero `${{` inside `run:` (`D-14`) |
| `dist/audit/osm_speed_drift_report.{md,json}` | `05-04` (W3/4) | **No** | Ephemeral CI artifact under gitignored `dist/`; NEVER committed to Git (`D-14`, `D-16`) |

---

## 2. File Classification & File-to-Analog Mapping Table

All analog paths below are git-tracked source files verified via `git ls-files`.

### Wave 1 — Plan `05-03` (`GLB-03`: Global `225`-Territory & `~156`-FX Foundation)

| Plan | New / Modified File | Role | Data Flow | Closest Tracked Analog | Match Quality | Key Patterns to Replicate |
|---|---|---|---|---|---|---|
| `05-03` | `data/mappings/currencies.json` | data / config | file-I/O | `data/mappings/country_aliases.json` | exact | Canonical sorted UTF-8 no-BOM LF JSON (`schema_version: 1`, `verified_date`, `provenance`) |
| `05-03` | `data/curated/tier3_fuel_baselines.json` | data / config | file-I/O | `data/mappings/country_aliases.json` | exact | Canonical sorted UTF-8 no-BOM LF JSON (`schema_version: 1`, `license: "CC BY 4.0"`, `clamped_to_floor`) |
| `05-03` | `src/ets2v2/normalize/currencies.py` | service / loader | file-I/O + transform | `src/ets2v2/normalize/currencies.py` (in-place) & `registry/loader.py:30-47` | exact | Strict frozen Pydantic v2 models (`CurrencyRegistry`, `Tier3FuelBaselineRegistry`) loaded via `@functools.lru_cache` from `data/`; re-export ALL Phase 3/4 constants intact; zero `registry`/`httpx`/`openpyxl` imports |
| `05-03` | `src/ets2v2/normalize/fx.py` | service / domain | transform | `src/ets2v2/normalize/fx.py` (in-place) | exact | Expand `EXTENDED_ECB_CURRENCIES` (18 global ECB currencies) & `_OPTIONAL_EXTENDED_CURRENCIES` (`EXTENDED_GLOBAL_CURRENCIES`, ~139 currencies) under `is_extended=True`; keep 16 Core non-EUR hard-gated (`D-11`) |
| `05-03` | `src/ets2v2/normalize/fuel.py` | service / domain | transform | `src/ets2v2/normalize/fuel.py` (in-place) | exact | Add `TIER3_CURATED_BASELINE_SOURCE` (`"tier3_curated_baseline"`) to `_SEEDED_SOURCES` (lines 45-47) so first live Tier 1/2 transition skips false WoW rejection while keeping hard `[0.01, 5.00]` bounds intact |
| `05-03` | `src/ets2v2/normalize/lockfile.py` | service / state | file-I/O + transform | `src/ets2v2/normalize/lockfile.py` (in-place) | exact | Seed all `225` territories & `~156` FX rates from `load_currency_registry()` + `load_tier3_fuel_baselines()`, honoring `0.010 EUR/L` floor clamping (`D-11`) and `TIER3_CURATED_BASELINE_SOURCE` |
| `05-03` | `src/ets2v2/normalize/totem_format.py` | utility / domain | transform | `src/ets2v2/normalize/totem_format.py` (in-place) | exact | Extend `EXTENDED_INTEGER_CURRENCY_ISO2S` (e.g., `JP`, `KR`, `ID`, `VN`, `CL`, `CO`, `PY`, `UG`, `TZ`, `RW`, `IR`, `KH`, `LA`, `MM`) & `THREE_DEC_NATIONAL_ISO2S` (`KW`, `BH`, `OM`) for clean global pump display |
| `05-03` | `src/ets2v2/normalize/__init__.py` | barrel / facade | n/a | `src/ets2v2/normalize/__init__.py` (in-place) | exact | Export new loaders/models/constants in alphabetically sorted `__all__` (`RUF022`) |
| `05-03` | `src/ets2v2/registry/timezone.py` | utility / domain | transform | `src/ets2v2/registry/timezone.py` (in-place) | exact | Add all `58` verified global `IANA_NUMERIC_ABBR_OVERRIDES` (alphabetically sorted), using `(std, dst)` tuples for `"America/Santiago"` and `"America/Miquelon"` |
| `05-03` | `data/laws/countries/*.json`, `data/mappings/ets2_countries.json`, `state/prices.lock.json` | data / state | file-I/O | Existing `data/laws/countries/de.json`, `data/mappings/ets2_countries.json`, `state/prices.lock.json` | exact | Expand `76 -> 225` canonical records via `serialize_registry_json_bytes()` / `serialize_lockfile_bytes()`; `36` `vanilla_1_62: true`, `189` `vanilla_1_62: false`; 100% coverage of `country_aliases.json` ISO-2 targets |
| `05-03` | `tests/test_global_registry_expansion.py` | test / contract | contract | `tests/test_registry_contracts.py` & `tests/test_country_aliases.py` | exact | Verify `225` territories, `~156` FX, `currencies.json`/`tier3_fuel_baselines.json` schemas, `XCG`/`ZWG`/`SLE`, `0.010` floor clamp, 100% alias target coverage, zero numeric TZ strings |
| `05-03` | **10 existing count-asserting test files** (see §5 table) | test / regression | contract | Existing files (in-place) | exact | Update hardcoded `76` / `41` / `40` / `"US" not in by_iso2` assertions cleanly to dynamic or `225` / `~156` counts |

### Wave 2 — Plan `05-01` (`GLB-01`: Non-EU Tier 1 Open Government Fuel Collectors)

| Plan | New / Modified File | Role | Data Flow | Closest Tracked Analog | Match Quality | Key Patterns to Replicate |
|---|---|---|---|---|---|---|
| `05-01` | `src/ets2v2/fetch/http.py` | utility / transport | request-response | `src/ets2v2/fetch/http.py` (in-place) | exact | Add `code` to `_SECRET_QUERY_RE` (line 28) for `KR Opinet` key redaction; preserve `validate_https_url`, redirect cap, byte cap, TLS `verify=True` |
| `05-01` | `src/ets2v2/fetch/_parsing.py` & `ec_bulletin.py` | utility / parser | transform | `src/ets2v2/fetch/ec_bulletin.py:182-219` & `_parsing.py` | exact | Promote `_validate_ooxml_zip_safety` -> `validate_ooxml_zip_safety` in `_parsing.py` (with configurable entry/uncompressed caps) and reuse in `ec_bulletin.py`, `global_tier1.py` (`JP`), and `tier2_portals.py` (`RU`, `ZA`, `NG`) |
| `05-01` | `src/ets2v2/fetch/models.py` | model / DTO | transform | `src/ets2v2/fetch/models.py` (in-place) | exact | Extend `RawFuelFeedResult`: `tier: Literal["tier1", "tier2", "fallback"]`, `region_scope: Literal["eu_core", "global"] = "eu_core"`, `skip_reason: str | None = None`, `error_code: str | None = None`; extend `FetchRunReport` with additive `eu_tier1_*`, `global_tier1_*`, `tier2_*` counters (`default=0`) |
| `05-01` | `src/ets2v2/fetch/national.py` | service / collector | request-response | `src/ets2v2/fetch/national.py` (in-place) | exact | Populate explicit `skip_reason="skipped (TANKERKOENIG_API_KEY unset; using EC WOB)"` on `fetch_de_tankerkoenig` |
| `05-01` | `src/ets2v2/fetch/global_tier1.py` | service / collector | request-response + transform | `src/ets2v2/fetch/national.py:545-722` & `ec_bulletin.py:253-409` | exact | 8 isolated collectors (`us_eia_v2`, `br_anp`, `ar_energia`, `co_sicom`, `cl_cne`, `my_opendosm`, `jp_meti`, `kr_opinet`) + `fetch_all_global_tier1_feeds()`: optional env keys (`EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`) with `_scrub()`, `Decimal("3.785411784")` gallon conversion (`US`, `CO`), `statistics.median()` for station feeds (`BR`, `AR`, `CO`, `CL`), `validate_ooxml_zip_safety` + `openpyxl` (`JP`) |
| `05-01` | `src/ets2v2/fetch/pipeline.py` & `__init__.py` | service / orchestrator | batch | `src/ets2v2/fetch/pipeline.py` (in-place) | exact | Wire `fetch_all_global_tier1_feeds()`, add `include_global: bool = True`, add all 8 feeds at `_FEED_PRECEDENCE = 40`, separate EU Core (`eu_tier1_feeds_succeeded == 0` hard-fail) vs Global Tier 1 (`warning` alert only, `D-02`), honor `feed_res.skip_reason`, preserve `tier3_curated_baseline` FX-repricing on fallback |
| `05-01` | `.github/workflows/phase-a-release.yml` | CI workflow | batch | `.github/workflows/phase-a-release.yml:49-92` | exact | Pass optional `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN` via step `env:` on `ets2v2 fetch`; emit EU Core vs Global Tier 1 counters in Step Summary; zero `${{` inside `run:` |
| `05-01` | `tests/test_fetch_global_tier1.py` | test / unit + integration | integration | `tests/test_fetch_fuel.py` & `tests/test_fetch_pipeline.py` | exact | 100% offline `httpx.MockTransport` + in-memory `openpyxl` tests for all 8 collectors, NIST gallon math, outlier median, optional key skip & `code=` secret non-leakage, EU vs Global gate separation |

### Wave 3 — Plan `05-02` (`GLB-02`: Tier 2 Guarded National Portals, Staleness & Changelog Rollup)

| Plan | New / Modified File | Role | Data Flow | Closest Tracked Analog | Match Quality | Key Patterns to Replicate |
|---|---|---|---|---|---|---|
| `05-02` | `src/ets2v2/fetch/_html.py` | utility / parser | transform | `src/ets2v2/fetch/_parsing.py:15-43` | role-match | Stdlib-only `TableExtractor(HTMLParser)`, `TextExtractor(HTMLParser)`, `decode_with_fallbacks(raw, encodings)` raising typed `Tier2EncodingError` — zero `beautifulsoup4`/`lxml` (`D-06`) |
| `05-02` | `src/ets2v2/fetch/tier2_portals.py` | service / collector | request-response + transform | `src/ets2v2/fetch/national.py` & `ec_bulletin.py` | exact | 10 guarded Tier 2 collectors (`is_gasvaktin`, `ch_bfs_lik`, `md_anre`, `mk_erc`, `ru_rosstat`, `il_moe`, `ae_moei`, `za_dmre_cef`, `sa_aramco`, `ng_nbs`) wrapped in `_run_tier2_guarded()` mapping errors to `tier2_rate_limited`, `tier2_portal_outage`, `tier2_encoding_error`, `tier2_selector_drift` (`D-05`, `D-07`) |
| `05-02` | `src/ets2v2/fetch/pipeline.py` & `cli.py` | orchestrator + CLI | batch + request-response | `src/ets2v2/fetch/pipeline.py:313-392` & `cli.py:637-694, 1407-1455` | exact | Wire `fetch_all_tier2_portals()`, `include_tier2: bool = True`, `_FEED_PRECEDENCE = 25` for Tier 2 (above `fuel_prices_eu: 10`), emit `feed_res.error_code or "feed_outage"`, add `--no-global` and `--no-tier2` CLI flags (`D-07`) |
| `05-02` | `src/ets2v2/normalize/lockfile.py` | service / state | transform | `src/ets2v2/normalize/lockfile.py:34-54, 99-133` | exact | Tier- and cadence-aware `evaluate_lockfile_staleness()`: `14d` (`stale_tier1`), `45d` (`stale_tier2_monthly`), `105d` (`stale_tier2_quarterly`), `30d` (`stale_fallback`), `180d` (`stale_tier3_curated`) (`D-08`) |
| `05-02` | `src/ets2v2/publish/changelog.py` & `.github/workflows/phase-a-release.yml` | renderer + CI | transform | `src/ets2v2/publish/changelog.py:78-111, 332-347` | exact | Keep per-country table strictly Core 36; add **Global Snapshot Coverage** summary block + expanded Tier 1/Tier 2 attributions (`D-12`); aggregate Tier 3 staleness/fallback into compact summary counts in changelog, Step Summary, and PR body (`D-08`) |
| `05-02` | `tests/test_fetch_tier2_portals.py` | test / unit + integration | integration | `tests/test_fetch_fuel.py`, `tests/test_normalize_fuel.py`, `tests/test_publish_release.py` | exact | Offline `httpx.MockTransport` tests for all 10 Tier 2 portals, `403`/`429`/timeout/`windows-1251`/selector-drift circuit breakers, `--no-global`/`--no-tier2` CLI flags, 5-tier staleness limits, and Tier 3 alert rollup |

### Wave 3/4 — Plan `05-04` (`GLB-04`: Isolated `audit/` Subpackage, License-Taint Gate & Monthly OSM Workflow)

| Plan | New / Modified File | Role | Data Flow | Closest Tracked Analog | Match Quality | Key Patterns to Replicate |
|---|---|---|---|---|---|---|
| `05-04` | `src/ets2v2/fetch/http.py` | utility / transport | request-response | `src/ets2v2/fetch/http.py:105-178` | exact | Add `post_form_bytes_with_retry()` (mirroring `fetch_bytes_with_retry` with `data=...`, `validate_https_url`, bounded reads, retries, and secret redaction) for opt-in Overpass `POST` queries |
| `05-04` | `data/laws/speed_audit_allowlist.json` | data / config | file-I/O | `data/mappings/country_aliases.json` | exact | Clean-room sorted UTF-8 no-BOM LF JSON (`schema_version: 1`) with `iso2`, `vehicle_class`, `lane_speed_class`, `field`, `statutory_rationale`, `verified_date` — **zero OSM text** (`D-15`) |
| `05-04` | `src/ets2v2/audit/__init__.py` | barrel / facade | n/a | `src/ets2v2/merge/__init__.py` & `package/__init__.py` | exact | `from __future__ import annotations`, absolute imports, alphabetically sorted `__all__` (`RUF022`) |
| `05-04` | `src/ets2v2/audit/models.py` | model / DTO | transform | `src/ets2v2/validate/models.py` & `fetch/models.py` | exact | Strict frozen Pydantic v2 models (`ConfigDict(strict=True, frozen=True, extra="forbid")`) for allowlist, drift findings, Overpass/Taginfo spot-checks, audit report, and taint report |
| `05-04` | `src/ets2v2/audit/osm_speeds.py` | service / auditor | request-response + transform | `src/ets2v2/publish/changelog.py:16-23` & `registry/loader.py:30-47` | partial | Fetch/load `westnordost/osm-legal-default-speeds` JSON (`--rules-url` / `--rules-file`), normalize country rules vs `load_law_registry()`, split into `Unacknowledged Drift` vs `Acknowledged Statutory Differences` via clean-room allowlist, render deterministic sanitized Markdown + sorted JSON (`D-13`, `D-15`) |
| `05-04` | `src/ets2v2/audit/overpass.py` | service / client | request-response | `src/ets2v2/fetch/national.py` & `fetch/http.py` | partial | Opt-in `--overpass` (`out tags 500;`, allowlist `{"overpass-api.de"}`, `<=10` ISO-2 cap, injectable `sleep_fn` >=1.5s) and `--taginfo` (`taginfo.openstreetmap.org/api/4/key/values`) spot-check client (`D-13`) |
| `05-04` | `src/ets2v2/audit/taint.py` | service / scanner | file-I/O + transform | `src/ets2v2/registry/loader.py:49-62` & `validate/workshop.py` | role-match | Scan `data/laws/`, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, `realism-snapshot-*.json`, and built `.zip`/`.scs`/Workshop dirs against the 8 compiled `D-16` forbidden license/source regexes |
| `05-04` | `src/ets2v2/validate/invariants.py` & `validate/workshop.py` | service / validator | transform | `src/ets2v2/validate/workshop.py:289-319` & `invariants.py` | exact | Add self-contained pure-stdlib `check_license_taint_bytes()` emitting `ETS2V2-INV-LICENSE-TAINT` in `invariants.py` and call it on every decoded `.sii`/`.sui`/`.txt` file in `workshop.py` — **ZERO `ets2v2.audit` import!** (`D-16`) |
| `05-04` | `src/ets2v2/cli.py` | CLI entrypoint | request-response | `src/ets2v2/cli.py:510-550, 1250-1300` | exact | Wire `ets2v2 audit osm-speeds` (`--iso2`, `--overpass`, `--taginfo`, `--rules-url`, `--rules-file`, `--allowlist`, `--out-md`, `--out-json`, `--timeout`, `--fail-on-drift`, `--json`) and `ets2v2 audit taint` (`--repo-root`, `--snapshot`, `--package`, `--json`) |
| `05-04` | `.github/workflows/osm-speed-audit.yml` | CI workflow | batch | `.github/workflows/phase-a-release.yml` | exact | Monthly schedule `0 7 1-7 * 1` + `workflow_dispatch`, `permissions: contents: read, issues: write`, zero PR triggers, zero `${{` inside `run:`, artifact upload, sanitized `$GITHUB_STEP_SUMMARY`, rolling `osm-audit` issue upsert via `gh issue` (`D-14`) |
| `05-04` | `tests/test_cli_scaffold.py` & `tests/test_validate_workshop.py` | test / contract | contract | Existing files (in-place) | exact | Unlock `"audit"` in `test_active_phase_only_package_layout`; enforce `test_phase5_ast_dag_isolation_walls` (6 offline walls + all 10 non-audit subpackages blocking `"audit"`); add `"audit"` to `validate`'s forbidden list in `test_validate_workshop.py:93` |
| `05-04` | `tests/test_audit_osm_speeds.py`, `tests/test_license_taint_gate.py`, `tests/test_publish_workflow.py` | test / security + contract | integration | `tests/test_fetch_fuel.py`, `tests/test_validate_invariants.py`, `tests/test_publish_workflow.py` | exact | Mock `westnordost` JSON + Overpass + Taginfo + allowlist tests; live repo/snapshot/package taint gate + false-positive checks (`\biea\b`) + synthetic tainted package rejection; `osm-speed-audit.yml` zero-Git-write & injection-safety contract |

---

## 3. Concrete Pattern Assignments (Code to Copy From)

### Pattern A — Data-Driven Currency & Tier 3 Baseline Registries + 58 Global TZ Overrides (`05-03` / Wave 1)

**Analogs:** `src/ets2v2/normalize/currencies.py:1-373`, `src/ets2v2/normalize/fx.py:36-39, 197-221`, `src/ets2v2/normalize/lockfile.py:34-54, 136-228`, `src/ets2v2/registry/timezone.py:20-38`

**1. Data-driven Pydantic loader in `src/ets2v2/normalize/currencies.py` (`D-10`, zero `registry`/`httpx`/`openpyxl` imports):**
```python
# src/ets2v2/normalize/currencies.py (Layer 5 — 100% offline, pure stdlib + pydantic)
import functools
from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_REPO_DATA_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "data"
DEFAULT_CURRENCIES_JSON_PATH: Final[Path] = _REPO_DATA_DIR / "mappings" / "currencies.json"
DEFAULT_TIER3_BASELINES_JSON_PATH: Final[Path] = (
    _REPO_DATA_DIR / "curated" / "tier3_fuel_baselines.json"
)
TIER3_CURATED_BASELINE_SOURCE: Final[str] = "tier3_curated_baseline"
TIER3_CURATED_BASELINE_LICENSE: Final[str] = "CC BY 4.0"


class CurrencyMetadataEntry(BaseModel):
    """Canonical clean-room ISO-4217 currency entry in data/mappings/currencies.json."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    tier: Literal["pinned", "core", "extended"]
    ecb_covered: bool
    major_ecb: bool
    fixed_peg_per_eur: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)
    reference_rate_per_eur: float = Field(gt=0.0, allow_inf_nan=False)
    sanity_min: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)
    sanity_max: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _validate_sanity_band(self) -> CurrencyMetadataEntry:
        if self.tier == "pinned":
            if self.sanity_min is not None or self.sanity_max is not None:
                raise ValueError("Pinned currency must not specify sanity_min/sanity_max")
            return self
        if self.sanity_min is None or self.sanity_max is None:
            raise ValueError("Non-pinned currency requires both sanity_min and sanity_max")
        if self.sanity_min >= self.sanity_max:
            raise ValueError("sanity_min must be strictly less than sanity_max")
        if not (self.sanity_min <= self.reference_rate_per_eur <= self.sanity_max):
            raise ValueError("reference_rate_per_eur must fall inside [sanity_min, sanity_max]")
        return self


class CurrencyRegistry(BaseModel):
    """Top-level data/mappings/currencies.json schema (D-10)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    verified_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    provenance: str = Field(min_length=1)
    currencies: dict[str, CurrencyMetadataEntry]
    territory_currencies: dict[str, str]

    @field_validator("verified_date")
    @classmethod
    def _check_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value


@functools.lru_cache(maxsize=4)
def load_currency_registry(path: Path = DEFAULT_CURRENCIES_JSON_PATH) -> CurrencyRegistry:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise ValueError(f"currencies.json must be UTF-8 no-BOM LF: {path}")
    return CurrencyRegistry.model_validate_json(raw.decode("utf-8"))
```
- **Backwards-compatible constant derivation (`D-10`):** Load once at module import (`_DEFAULT_CURRENCY_REG = load_currency_registry()`, `_DEFAULT_TIER3_REG = load_tier3_fuel_baselines()`) and populate ALL existing Phase 3/4 exports verbatim (`VANILLA_SLUG_TO_ISO2` [36], `VANILLA_36_ISO2S` [36], `EXTRA_EU_TERRITORY_ISO2S` [3], `EUROPEAN_TERRITORY_ISO2S` [39], `PROMODS_EXTENDED_ISO2S` [37], `ALL_LOCKFILE_TERRITORY_ISO2S` [225], `TERRITORY_CURRENCIES` [39], `ALL_TERRITORY_CURRENCIES` [225], `MAJOR_ECB_CURRENCIES` [10], `VOLATILE_NON_ECB_CURRENCIES` [6], `ECB_COVERED_CURRENCIES` [11], `EXTENDED_ECB_CURRENCIES` [18], `EXTENDED_PROMODS_CURRENCIES` [24], `EXTENDED_GLOBAL_CURRENCIES` [~139], `CURRENCY_SANITY_BANDS` [16], `EXTENDED_CURRENCY_SANITY_BANDS` [~139], `ALL_CURRENCY_SANITY_BANDS` [~155], `CORE_REFERENCE_FX_RATES` [17], `EXTENDED_REFERENCE_FX_RATES` [~139], `ALL_REFERENCE_FX_RATES` [~156], `BAM_FIXED_PEG_PER_EUR`, `PROMODS_SEED_EUR_PRICES` [37]).
- **Key `normalize/fx.py` update (lines 37, 202):** Change `_OPTIONAL_EXTENDED_CURRENCIES = tuple(sorted(EXTENDED_GLOBAL_CURRENCIES))` so `cross_validate_fx_rates(..., include_extended=True)` validates all ~139 global currencies under `is_extended=True` with `"global_reference_fx"` (or `"promods_reference_fx"` for ProMods subset) reference fallback — keeping `include_extended=False` (used by Phase 3 unit tests) strictly at 17 Core European currencies!

**2. `0.010 EUR/L` floor clamping on Tier 3 seeds (`src/ets2v2/normalize/lockfile.py:182-221`, `D-11`):**
- In `Tier3FuelBaselineEntry`, validate `diesel_eur_per_liter: float = Field(ge=0.01, le=5.00, allow_inf_nan=False)`, `petrol_95_eur_per_liter: float = Field(ge=0.01, le=5.00, allow_inf_nan=False)`, `clamped_to_floor: bool = False`, `verified_date`, `source_note`.
- In `seed_initial_lockfile()` (`lockfile.py:183-203`), check `baseline_eur_by_iso2` (36 Vanilla) -> `EXTRA_EU_SEED_EUR_PRICES` (`CY`, `IE`, `MT`) -> `tier3_baselines.baselines[iso2]` (for all remaining `186` non-Vanilla territories, using `source=PROMODS_CURATED_SEED_SOURCE` or `TIER3_CURATED_BASELINE_SOURCE` — recommend `TIER3_CURATED_BASELINE_SOURCE = "tier3_curated_baseline"` for the new global territories and keeping `PROMODS_CURATED_SEED_SOURCE` for the 37 ProMods territories OR using `TIER3_CURATED_BASELINE_SOURCE` uniformly for Tier 3 territories while keeping `PROMODS_CURATED_SEED_SOURCE` exported and recognized in `_SEEDED_SOURCES`!).

**3. 58 Global Numeric-`tzname()` Overrides (`src/ets2v2/registry/timezone.py:20-38`):**
- Copy exact tuple/string pattern of `"America/Nuuk": ("WGT", "WGST")` and `"Asia/Riyadh": "AST"`:
  - Seasonal DST tuples: `"America/Santiago": ("CLT", "CLST")`, `"America/Miquelon": ("PMST", "PMDT")`.
  - Fixed-offset strings: all 56 remaining zones enumerated in `05-RESEARCH.md` §3.4 (sorted alphabetically by IANA key).

---

### Pattern B — `code=` Secret Redaction, Shared OOXML Safety, Non-EU Tier 1 Collectors & EU-Core Outage Gate (`05-01` / Wave 2)

**Analogs:** `src/ets2v2/fetch/http.py:27-48`, `src/ets2v2/fetch/ec_bulletin.py:182-219`, `src/ets2v2/fetch/national.py:545-722`, `src/ets2v2/fetch/models.py:84-120`, `src/ets2v2/fetch/pipeline.py:331-392`

**1. Mandatory `code=` query-secret redaction fix (`src/ets2v2/fetch/http.py:27-30`):**
```python
_SECRET_QUERY_RE: Final[re.Pattern[str]] = re.compile(
    r"([?&]|^)(apikey|api_key|token|key|code)=([^&\s'\"`)]+)",
    flags=re.IGNORECASE,
)
```
- **Why critical:** `KR Opinet` passes `OPINET_API_KEY` via `?out=json&code=<SECRET>`. Adding `code` to `_SECRET_QUERY_RE` PLUS a per-collector `_scrub(msg)` (`redact_url_secrets(msg).replace(resolved_key, "***")`, copied directly from `national.py:564-565`) guarantees zero secret leakage in errors, alerts, lockfiles, or GitHub Step Summaries!

**2. Additive `RawFuelFeedResult` & `FetchRunReport` fields (`src/ets2v2/fetch/models.py:84-120`, `D-02`, `D-07`):**
```python
class RawFuelFeedResult(BaseModel):
    """Isolated fetch outcome for one upstream fuel feed collector."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    feed_name: str = Field(min_length=1)
    tier: Literal["tier1", "tier2", "fallback"]
    region_scope: Literal["eu_core", "global"] = "eu_core"
    ok: bool
    skipped: bool = False
    skip_reason: str | None = None
    error_code: str | None = None
    quotes: list[RawCountryFuelQuote] = Field(default_factory=list)
    error: str | None = None
    data_date: str | None = None


class FetchRunReport(BaseModel):
    """Machine-readable report emitted by ``ets2v2 fetch`` (supports ``--json``)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ok: bool
    fx_only: bool
    dry_run: bool
    lock_path: Path
    tier1_feeds_succeeded: int = Field(ge=0)
    tier1_feeds_failed: int = Field(ge=0)
    eu_tier1_feeds_succeeded: int = Field(default=0, ge=0)
    eu_tier1_feeds_failed: int = Field(default=0, ge=0)
    global_tier1_feeds_succeeded: int = Field(default=0, ge=0)
    global_tier1_feeds_failed: int = Field(default=0, ge=0)
    tier2_feeds_succeeded: int = Field(default=0, ge=0)
    tier2_feeds_failed: int = Field(default=0, ge=0)
    countries_updated: int = Field(ge=0)
    countries_fallback: int = Field(ge=0)
    fx_currencies_validated: int = Field(ge=0)
    alerts: list[LockAlert] = Field(default_factory=list)
    provider_statuses: list[ProviderFetchStatus] = Field(default_factory=list)
```
- **Backwards compatibility:** Keeping `tier1_feeds_succeeded == eu_tier1_feeds_succeeded` and `tier1_feeds_failed == eu_tier1_feeds_failed` ensures every Phase 3/4 test and `phase-a-release.yml` assertion remains valid while exposing explicit `eu_tier1_*`, `global_tier1_*`, and `tier2_*` breakdowns!

**3. Exact NIST gallon conversion & optional-key collector pattern (`src/ets2v2/fetch/global_tier1.py`, copying `national.py:545-646`):**
```python
from decimal import Decimal
import statistics

NIST_LITERS_PER_US_GALLON: Final[Decimal] = Decimal("3.785411784")


def gallon_to_liter(price_per_gallon: float) -> float:
    """Convert USD/gal or COP/gal to native currency/L via exact NIST factor (D-04)."""
    return float(Decimal(str(price_per_gallon)) / NIST_LITERS_PER_US_GALLON)
```
- Apply `gallon_to_liter()` to **BOTH** `US EIA v2` (`EPD2D`/`EPMR`/`EPMP` with `duoarea=NUS`, `process=PTE`) AND **`CO` SICOM/CREG** (remember Colombian thousands-dot normalization `15.588` -> `15588 COP/gal` when `^\d{1,3}\.\d{3}$`!).
- Use `statistics.median()` across valid station rows for `BR ANP` (ignore `GLP`/`GNV`), `AR Energía` (reject `"historico"` CSVs, ignore `GNC`, filter `fecha_vigencia` within 60d of max date), `CO SICOM`, and `CL CNE`.
- Use official national rows for `US EIA` (`duoarea="NUS"`), `MY OpenDOSM` (filter `series_type == "level"` strictly!), `JP METI` (`.xlsx` only via shared `validate_ooxml_zip_safety()`, match `全国`/`全国平均` + `レギュラー`/`ハイオク`/`軽油`, strictly ignore `灯油` 18L kerosene!), and `KR Opinet` (`RESULT.OIL[]`: `D047`->`diesel`, `B027`->`petrol_95`, `B034`->`petrol_98`, `K015`->`lpg`, ignore `C004`).
- Optional secrets (`EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`): return `RawFuelFeedResult(feed_name=..., tier="tier1", region_scope="global", ok=True, skipped=True, skip_reason=..., quotes=[])` when unset (`D-01`).

**4. Separate EU Core vs Global Tier 1 outage gate (`src/ets2v2/fetch/pipeline.py:331-392`, `D-02`):**
```python
    for feed_res in all_fuel_results:
        if feed_res.skipped:
            provider_statuses.append(
                ProviderFetchStatus(
                    provider=feed_res.feed_name,
                    ok=True,
                    detail=feed_res.skip_reason or "skipped (optional API key unset)",
                    data_date=feed_res.data_date,
                )
            )
            continue
        ...
        if not feed_res.ok:
            default_code = (
                "global_tier1_outage"
                if (feed_res.tier == "tier1" and feed_res.region_scope == "global")
                else "feed_outage"
            )
            alerts.append(
                LockAlert(
                    severity="warning",
                    code=feed_res.error_code or default_code,
                    scope=feed_res.feed_name,
                    detail=redact_url_secrets(feed_res.error or "fuel feed fetch failed"),
                )
            )

    eu_tier1_succeeded = sum(
        1
        for r in all_fuel_results
        if r.tier == "tier1" and r.region_scope == "eu_core" and not r.skipped and r.ok
    )
    eu_tier1_failed = sum(
        1
        for r in all_fuel_results
        if r.tier == "tier1" and r.region_scope == "eu_core" and not r.skipped and not r.ok
    )
    if eu_tier1_succeeded == 0:
        # Hard fail Friday CI — succeeding Global Tier 1 or Tier 2 feeds NEVER mask an EU Core outage!
        ...
```
- **Preserve Tier 3 seed repricing in `pipeline.py:518`:** Extend the seed-repricing check from `{BASELINE_SEEDED_SOURCE, PROMODS_CURATED_SEED_SOURCE}` to `{BASELINE_SEEDED_SOURCE, PROMODS_CURATED_SEED_SOURCE, TIER3_CURATED_BASELINE_SOURCE}` so weekly FX updates reprice Tier 3 local pump prices cleanly while preserving `data_date`!

---

### Pattern C — Stdlib HTML/Charset Helpers, Per-Country Tier 2 Circuit Breakers, Tier-Aware Staleness & Changelog Rollup (`05-02` / Wave 3)

**Analogs:** `src/ets2v2/fetch/_parsing.py:15-43`, `src/ets2v2/normalize/lockfile.py:99-133`, `src/ets2v2/publish/changelog.py:32-111, 332-347`, `src/ets2v2/cli.py:637-694, 1407-1455`

**1. Stdlib-only `src/ets2v2/fetch/_html.py` (`D-06`, zero `beautifulsoup4`/`lxml`):**
```python
from __future__ import annotations

from html.parser import HTMLParser


class Tier2EncodingError(ValueError):
    """Raised when a Tier 2 portal response cannot be decoded cleanly under allowed charsets."""


class TableExtractor(HTMLParser):
    """Stdlib HTMLParser collecting all HTML <table> rows as list[list[list[str]]]."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_parts: list[str] = []
    ...


def decode_with_fallbacks(
    raw: bytes,
    encodings: tuple[str, ...] = ("utf-8-sig", "windows-1251", "latin-1"),
) -> str:
    """Decode bytes strictly across ordered charsets; raise Tier2EncodingError if all fail."""
    for enc in encodings:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise Tier2EncodingError(f"Failed to decode response with encodings {encodings!r}")
```

**2. Per-country circuit breaker wrapper (`src/ets2v2/fetch/tier2_portals.py`, `D-07`):**
- Use `_run_tier2_guarded(feed_name, fn)` catching `Tier2RateLimitedError` (`tier2_rate_limited`), `Tier2EncodingError` (`tier2_encoding_error`), `Tier2SelectorDriftError` (`tier2_selector_drift`), and `(HttpFetchError, httpx.HTTPError, ValueError, KeyError, OSError, InvalidFileException, zipfile.BadZipFile, ET.ParseError)` (inspecting `"HTTP 403"` / `"HTTP 429"` -> `tier2_rate_limited`, else `tier2_portal_outage`).
- Always returns `RawFuelFeedResult(feed_name=..., tier="tier2", region_scope="global", ok=False, error_code=..., error=redact_url_secrets(str(exc)))` — **NEVER** raises out of a Tier 2 collector and **NEVER** contributes to `eu_tier1_feeds_succeeded`!
- Precedence in `pipeline.py`: Tier 1 (`40`) > `ec_weekly_oil_bulletin` (`30`) > Tier 2 portals (`25`) > `fionnhughes_ec_wob` (`20`) > `fuel_prices_eu` (`10`) — so if `MD`, `MK`, `CH`, or `IS` Tier 2 portal fails, `fuel_prices_eu` (`10`) still serves as live fallback automatically!

**3. Tier- and cadence-aware staleness (`src/ets2v2/normalize/lockfile.py:34-54, 99-133`, `D-08`):**
```python
TIER1_STALE_DAYS: Final[int] = 14
TIER2_MONTHLY_STALE_DAYS: Final[int] = 45
TIER2_QUARTERLY_STALE_DAYS: Final[int] = 105
FALLBACK_STALE_DAYS: Final[int] = 30
TIER3_CURATED_STALE_DAYS: Final[int] = 180

MONTHLY_LIVE_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "no_ssb_09654",
        "co_sicom",
        "co_creg",
        "ch_bfs_lik",
        "mk_erc",
        "il_moe",
        "ae_moei",
        "za_dmre_cef",
        "sa_aramco",
        "ng_nbs",
    }
)
QUARTERLY_TIER2_SOURCES: Final[frozenset[str]] = frozenset({"eg_fapc"})
```
- Dispatch order inside `evaluate_lockfile_staleness()` for each sorted `iso2`:
  1. `entry.source == TIER3_CURATED_BASELINE_SOURCE` -> limit `180d`, alert code `"stale_tier3_curated"`.
  2. `entry.fallback_used or entry.source in _SEEDED_SOURCES` (`baseline_1.62_seeded`, `promods_curated_seed`) -> limit `30d`, alert code `"stale_fallback"`.
  3. `entry.source in QUARTERLY_TIER2_SOURCES` -> limit `105d`, alert code `"stale_tier2_quarterly"`.
  4. `entry.source in MONTHLY_LIVE_SOURCES` -> limit `45d`, alert code `"stale_tier2_monthly"`.
  5. Default (weekly live Tier 1 / daily Tier 2) -> limit `14d`, alert code `"stale_tier1"`.
- **100% backwards-compatible** with all Phase 3/4 staleness unit tests!

**4. Noise-controlled Tier 3 rollup & Global Snapshot Coverage (`src/ets2v2/publish/changelog.py:78-111, 332-347`, `D-08`, `D-12`):**
- In `_render_alerts_section()`:
  - Itemize every non-`stale_tier3_curated` alert individually (using `_sanitize_markdown_inline`).
  - Aggregate `stale_tier3_curated` alerts and `fallback_countries` where `entry.source == TIER3_CURATED_BASELINE_SOURCE` into **one compact summary line** (`- **Tier 3 Curated Global Baselines Retained:** \`{count}\` territories (\`{stale_count}\` overdue >180d)`), while still itemizing Core/Tier 1/Tier 2 fallback countries!
  - Aggregate extended fallback FX rates concisely when `len(fallback_fx) > 20` (itemize Core non-EUR fallback FX + summary count for extended global FX) so 100+ exotic FX fallbacks never flood Markdown!
- Add `_render_global_coverage_section(snapshot, prices_lock)` right before `## Attribution & Licensing` showing total territories (`225`), Core Vanilla+DLC (`36`), live Tier 1 EU/Global counts, Tier 2 portal count, and Tier 3 curated count, plus expand `## Attribution & Licensing` with all integrated Tier 1 & Tier 2 open-data attributions (`U.S. EIA`, `Brazil ANP`, `Argentina Energía`, `Colombia MinMinas/CREG`, `Chile CNE`, `Malaysia OpenDOSM CC BY 4.0`, `Japan METI`, `Korea KNOC Opinet`, `Iceland Gasvaktin MIT`, `Switzerland BFS`, etc.).
- Mirror the same Tier 3 rollup in `.github/workflows/phase-a-release.yml` Step Summary & PR body embedded Python scripts (preserving `def _sanitize(` in both snippets per `tests/test_publish_workflow.py:210-212`!).

---

### Pattern D — Isolated `src/ets2v2/audit/`, Independent `validate/` License-Taint Gate & Monthly OSM Workflow (`05-04` / Wave 3–4)

**Analogs:** `src/ets2v2/fetch/http.py:105-178`, `src/ets2v2/validate/invariants.py:25-45`, `src/ets2v2/validate/workshop.py:289-319, 967-1050`, `.github/workflows/phase-a-release.yml`, `tests/test_cli_scaffold.py:64-89, 271-293`, `tests/test_validate_workshop.py:88-136`

**1. Independent Pure-Stdlib License-Taint Check in `src/ets2v2/validate/invariants.py` (ZERO `ets2v2.audit` import — `D-16`):**
```python
# src/ets2v2/validate/invariants.py (Layer 8 — strictly independent of ets2v2.audit!)
FORBIDDEN_LICENSE_TAINT_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("CC BY-SA", re.compile(r"cc[\s-]*by[\s-]*sa", re.IGNORECASE)),
    ("ODbL", re.compile(r"\bodbl\b", re.IGNORECASE)),
    ("OpenStreetMap", re.compile(r"openstreetmap", re.IGNORECASE)),
    ("osm-legal-default-speeds", re.compile(r"osm-legal-default-speeds", re.IGNORECASE)),
    ("GlobalPetrolPrices", re.compile(r"globalpetrolprices", re.IGNORECASE)),
    ("CC BY-NC-ND", re.compile(r"cc[\s-]*by[\s-]*nc[\s-]*nd", re.IGNORECASE)),
    ("MyLPG", re.compile(r"\bmylpg\b", re.IGNORECASE)),
    ("IEA", re.compile(r"(?:international\s+energy\s+agency|\biea\b)", re.IGNORECASE)),
)


def check_license_taint_bytes(
    raw: bytes,
    rel_path: str,
    collector: ValidationCollector,
) -> None:
    """Reject any CC BY-SA / ODbL / CC BY-NC-ND / forbidden source markers in CC BY 4.0 packages."""
    text = raw.decode("utf-8", errors="replace")
    for label, pattern in FORBIDDEN_LICENSE_TAINT_PATTERNS:
        if pattern.search(text) is not None:
            collector.error(
                "ETS2V2-INV-LICENSE-TAINT",
                rel_path,
                f"Forbidden non-CC-BY-4.0 license/source marker {label!r} detected in package text",
            )
```
- Invoke `check_license_taint_bytes(raw, display_path, collector)` in `src/ets2v2/validate/workshop.py` on `versions.sii`, `manifest.sii`, every `.txt` description, and every `.sii`/`.sui` member inside `_validate_package_contents()` — covering all 3 profiles (`core`, `promods`, `combo`) automatically!
- Mirror the exact same 8 compiled patterns in `src/ets2v2/audit/taint.py` for scanning `data/laws/`, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, `realism-snapshot-*.json`, and arbitrary built `.zip`/`.scs`/Workshop dirs via `ets2v2 audit taint`.

**2. Clean-Room Allowlist & Drift Audit in `src/ets2v2/audit/` (`D-13`, `D-15`):**
- `data/laws/speed_audit_allowlist.json` validated by frozen `SpeedAuditAllowlist` (`ConfigDict(strict=True, frozen=True, extra="forbid")`), keyed by `(iso2, vehicle_class, lane_speed_class, field)` where `field: Literal["limit", "urban_limit", "max_limit"]`.
- `osm_speeds.py` loads `westnordost/osm-legal-default-speeds` JSON via `--rules-file` (100% offline test path) or `fetch_bytes_with_retry(..., allowed_hosts=frozenset({"westnordost.github.io", "raw.githubusercontent.com", "github.com"}))`, compares `car`/`truck`/`bus` urban/local/expressway/motorway limits against `load_law_registry()` summer baseline, splits findings into `unacknowledged_drifts` vs `acknowledged_differences`, and renders sanitized Markdown (`_sanitize_markdown_inline`) + sorted UTF-8 no-BOM LF JSON.
- `overpass.py` implements opt-in `--overpass` (`POST` via `post_form_bytes_with_retry()` to `https://overpass-api.de/api/interpreter`, `out tags 500;`, cap `<= 10` ISO-2 codes, polite `sleep_fn(1.5)` between requests) and `--taginfo` (`GET` to `https://taginfo.openstreetmap.org/api/4/key/values`).

**3. Standalone Zero-Git-Write Workflow (`.github/workflows/osm-speed-audit.yml`, `D-14`):**
```yaml
name: Monthly OSM Speed-Limit Drift Audit

on:
  schedule:
    - cron: "0 7 1-7 * 1"
  workflow_dispatch:
    inputs:
      iso2:
        description: "Optional comma-separated ISO-2 country codes to audit (default: all)"
        required: false
        type: string
        default: ""
      overpass:
        description: "Run opt-in Overpass spot-checks (requires <=10 ISO-2 codes)"
        required: false
        type: boolean
        default: false

permissions:
  contents: read
  issues: write

concurrency:
  group: osm-speed-audit
  cancel-in-progress: false
```
- **Security invariants (asserted in `tests/test_publish_workflow.py`):**
  - `contents: read` (NEVER `contents: write` — physically blocks Git commits/pushes of OSM data!).
  - Zero `pull_request` or `pull_request_target` triggers.
  - Pass `AUDIT_ISO2: ${{ inputs.iso2 }}`, `AUDIT_OVERPASS: ${{ inputs.overpass }}`, `GH_TOKEN: ${{ github.token }}` strictly via step/job `env:` — **ZERO `${{` inside `run:` shell bodies**!
  - Sanitize report text before writing `$GITHUB_STEP_SUMMARY` or rolling `osm-audit` GitHub Issue via `gh issue list` / `gh issue edit` / `gh issue create`.

**4. Phase 5 AST DAG Wall & Active Layout Updates (`tests/test_cli_scaffold.py` & `tests/test_validate_workshop.py`):**
```python
# tests/test_cli_scaffold.py:64-89
allowed_phase5_entries = {
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
    "merge",
    "publish",
    "audit",
}

# tests/test_cli_scaffold.py:271-293 -> test_phase5_ast_dag_isolation_walls()
wall_specs: dict[str, frozenset[str]] = {
    "validate": frozenset({"package", "merge", "normalize", "fetch", "publish", "audit"}),
    "merge": frozenset({"fetch", "publish", "audit"}),
    "package": frozenset({"fetch", "merge", "validate", "publish", "audit"}),
    "publish": frozenset({"fetch", "merge", "audit"}),
    "normalize": frozenset({"fetch", "registry", "package", "validate", "merge", "publish", "audit"}),
    "registry": frozenset({"fetch", "package", "validate", "merge", "publish", "audit"}),
}
# Plus universal audit quarantine across ALL 10 non-audit subpackages:
all_non_audit_subpkgs = (
    "vfs", "sii", "baseline", "normalize", "registry",
    "fetch", "package", "validate", "merge", "publish",
)
for subpkg in all_non_audit_subpkgs:
    violations = _scan_forbidden_imports(
        src_root / subpkg,
        forbidden_roots=frozenset(),
        forbidden_ets2v2_subpackages=frozenset({"audit"}),
    )
    assert violations == [], f"Audit quarantine breach in {subpkg}/: {violations}"
```
- **ALSO update `tests/test_validate_workshop.py:93`** to add `"audit"` to `forbidden_subpkgs = ("package", "merge", "normalize", "fetch", "publish", "audit")`!

---

## 4. Shared Cross-Cutting Patterns

### 4.1 Strict Frozen Pydantic v2 Models
**Source:** `src/ets2v2/normalize/models.py:47-129`, `src/ets2v2/fetch/models.py:23-120`
**Apply to:** `normalize/currencies.py`, `fetch/models.py`, `audit/models.py`
- Every DTO uses `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`.
- Calendar dates validated via `Field(pattern=r"^\d{4}-\d{2}-\d{2}$")` + `@field_validator` calling `date.fromisoformat(value)`.
- Floats validated with `allow_inf_nan=False`.

### 4.2 Deterministic UTF-8 No-BOM LF Sorted JSON Serialization
**Source:** `src/ets2v2/normalize/lockfile.py:56-96`, `src/ets2v2/registry/loader.py:30-47`
**Apply to:** `data/mappings/currencies.json`, `data/curated/tier3_fuel_baselines.json`, `data/laws/countries/*.json`, `data/laws/speed_audit_allowlist.json`, `audit/osm_speeds.py` (`--out-json`), `audit/taint.py`
```python
payload: object = model.model_dump(mode="json")
raw = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
```
- Atomic writes use `tempfile.NamedTemporaryFile(dir=path.parent, delete=False)` + `os.replace(tmp_path, path)` (copied from `lockfile.py:75-96`).

### 4.3 Hardened HTTPS Transport & Offline `httpx.MockTransport` Testing
**Source:** `src/ets2v2/fetch/http.py:50-178`, `tests/test_fetch_fuel.py:59-120`, `tests/test_fetch_pipeline.py:1-90`
**Apply to:** `fetch/global_tier1.py`, `fetch/tier2_portals.py`, `audit/osm_speeds.py`, `audit/overpass.py`, and all new fetch/audit test suites
- Every collector accepts `(client: httpx.Client, *, sleep_fn: Callable[[float], None] | None = None)` and routes every request (and dynamically discovered link!) through `fetch_bytes_with_retry(..., allowed_hosts=...)` or `post_form_bytes_with_retry(..., allowed_hosts=...)`.
- Every unit/integration test builds `client = create_http_client(transport=httpx.MockTransport(handler))` with `sleep_fn=lambda _s: None` so `uv run --offline pytest` completes in <1s with zero real network calls.
- Every `.xlsx` parser (`JP METI`, `RU Rosstat`, `ZA CEF`, `NG NBS`) calls shared `validate_ooxml_zip_safety(raw_xlsx)` before `openpyxl.load_workbook(io.BytesIO(raw_xlsx), read_only=True, data_only=True)` and enforces row caps (`_MAX_ROWS`).

### 4.4 CLI `argparse` + Strict `basedpyright` `cast(...)` + `--json` Pattern
**Source:** `src/ets2v2/cli.py:637-694, 1407-1455`
**Apply to:** `cli.py` (`fetch --no-global --no-tier2`, `audit osm-speeds`, `audit taint`)
- `cast(...)` every `argparse.Namespace` attribute; annotate `payload: object = report.model_dump(mode="json")` before `json.dumps(...)`; return POSIX `0`/`1`; pass errors through `redact_url_secrets()` on `sys.stderr`.
- Zero `print()` or `logging` inside library modules (`normalize/`, `registry/`, `fetch/`, `validate/`, `publish/`, `audit/`).
- `ruff` (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`, `line-length = 100`, zero `# noqa`) and `basedpyright` (`strict`, Python `3.12`, zero `# type: ignore`) across both `src/` and `tests/`.

---

## 5. Existing Tests Impacted by Phase 5 Counts, Layout & AST Walls (Exact Line Map)

The planner **MUST** schedule every existing test file update in the exact plan that changes the underlying count or contract so every wave finishes 100% green:

### A. 10 Existing Test Files Affected by `76 -> 225` Territories & `41 -> ~156` FX Rates (Update in Plan `05-03` / Wave 1)

| File | Verified Line Numbers | Current Phase 4 Assertion | Required Plan `05-03` Update |
|---|---|---|---|
| `tests/test_registry_contracts.py` | `:139, :147, :148, :153, :411` | `== 76`, `len(promods_entries) == 40`, `"76 countries"` | Update to `225` total (`36` `vanilla_1_62=True`, `189` `vanilla_1_62=False`); add 100% `country_aliases.json` ISO-2 target coverage assertion |
| `tests/test_registry_snapshot.py` | `:293, :321, :322, :353` | `== 76` | Update to `225` (or `len(ALL_LOCKFILE_TERRITORY_ISO2S)`) while keeping `schema_version == 1` |
| `tests/test_registry_timezone.py` | `:117` | `assert len(registry.laws_by_iso2) == 76` | Update to `225`; verifies all 225 territories resolve non-numeric TZ strings in Summer & Winter! |
| `tests/test_normalize_fx.py` | `:651, :652, :656, :657, :698` | `== 76`, `== 40`, `== 41` | Update to `len(ALL_LOCKFILE_TERRITORY_ISO2S) == 225`, `len(ALL_CURRENCY_SANITY_BANDS) == len(ALL_REFERENCE_FX_RATES) - 1` (`~155`), `len(res.rates) == len(ALL_REFERENCE_FX_RATES)` (`~156`); **preserve `:111` (`39`), `:112` (`39`), `:650` (`37`) unchanged!** |
| `tests/test_normalize_fuel.py` | `:234, :239` | `len(lock_a.countries) == 76`, `len(lock_a.fx_rates) == 41` | Update to `225` and `len(ALL_REFERENCE_FX_RATES)` (`~156`) |
| `tests/test_fetch_fx.py` | `:446, :448, :481, :608, :618, :622` | `== 41` | Update to `len(ALL_REFERENCE_FX_RATES)` (`~156`) |
| `tests/test_fetch_fuel.py` | `:212` | `assert "US" not in by_iso2` | `"US"` is now a canonical territory in `ALL_LOCKFILE_TERRITORY_ISO2S`! Replace `"US"` in that test's unmapped-code fixture with a synthetic unmapped code (`"ZZ"` or `"AQ"`) |
| `tests/test_fetch_pipeline.py` | `:375, :377, :552, :554, :741, :744` | `== 76`, `== 41` | Update to `225` and `len(ALL_REFERENCE_FX_RATES)` (`~156`) |
| `tests/test_merge_aliases.py` | `:86` | `assert len(phase4_snapshot.countries) == 76` | Update to `225` |
| `tests/test_publish_release.py` | `:172, :175, :179, :551` | `== 76`, `` `36` (Core) / `76` (Snapshot) `` | Update to `225` and `` `36` (Core) / `225` (Snapshot) `` (keeping Core Workshop files strictly 36 countries / 579 files!) |

### B. 3 Structural / Security Test Files Updated in Plans `05-01`, `05-02`, and `05-04`

| File | Plan | Verified Line Numbers | Required Update |
|---|---|---|---|
| `tests/test_cli_scaffold.py` | `05-04` | `:70-88`, `:271-293` | Unlock `"audit"` in `test_active_phase_only_package_layout`; upgrade `test_phase4_ast_dag_isolation_walls` -> `test_phase5_ast_dag_isolation_walls` enforcing all 6 offline walls + universal `audit` quarantine across all 10 non-audit subpackages. **Keep `:103-109` exact 5-dependency pin UNCHANGED!** |
| `tests/test_validate_workshop.py` | `05-04` | `:88-136` | Add `"audit"` to `forbidden_subpkgs` in `test_validate_package_has_zero_imports_from_ets2v2_package()`; add test verifying tainted `.txt`/`.sii` emits `ETS2V2-INV-LICENSE-TAINT` |
| `tests/test_publish_workflow.py` | `05-01`, `05-02`, `05-04` | `:187-219`, new tests | Assert `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN` passed via step `env:` (`05-01`); assert `osm-speed-audit.yml` has `contents: read`, `issues: write`, zero `pull_request*`, zero `${{` in `run:`, valid compiled Python snippets, and rolling `gh issue` logic (`05-04`) |

---

## 6. Phase 5 Regression Trap Checklist

1. **TRAP 1 — Dependency Pin Lock (`tests/test_cli_scaffold.py:103-109`):** `pyproject.toml` dependencies are explicitly asserted equal to `["httpx>=0.28,<0.29", "openpyxl>=3.1,<4", "pillow>=12,<14", "pydantic>=2.14,<3", "tzdata>=2025.2"]`. Adding `beautifulsoup4`, `lxml`, `pandas`, or `xlrd` immediately fails CI (`D-03`, `D-06`).
2. **TRAP 2 — `OPINET_API_KEY` (`code=`) Secret Leak (`src/ets2v2/fetch/http.py:27-30`):** `_SECRET_QUERY_RE` currently omits `code`. Update it in Plan `05-01` BEFORE implementing `fetch_kr_opinet`, and test explicitly that a failing request URL never leaks `code=SECRET` into `FetchRunReport` or `state/prices.lock.json`.
3. **TRAP 3 — `pipeline.py:337` Hardcoded Tankerkönig Skip String:** Currently every `feed_res.skipped` feed logs `"skipped (TANKERKOENIG_API_KEY unset; using EC WOB)"`! Add `skip_reason: str | None = None` on `RawFuelFeedResult` in Plan `05-01` so `EIA`, `Opinet`, `CNE`, and `Tankerkönig` report accurate skip details.
4. **TRAP 4 — `test_fetch_pipeline.py` Mock Transport Must Handle New Global Tier 1 & Tier 2 URLs Cleanly:** Existing Phase 3/4 pipeline tests (`tests/test_fetch_pipeline.py`) pass a `MockTransport` that only stubs EU FX + EU fuel URLs (returning `404` or `500` for unmapped URLs!). Because Global Tier 1 (`D-02`) and Tier 2 (`D-07`) are strictly fault-isolated, `404`s on those new URLs will NOT fail `run_price_fetch()` — **HOWEVER**, check whether any Phase 3/4 pipeline test asserts `len(report.alerts) == 0` or exact `len(report.provider_statuses)`! Either pass `include_global=False, include_tier2=False` in legacy EU-only tests OR account for the new warning statuses cleanly in `tests/test_fetch_pipeline.py` during Plans `05-01` and `05-02`.
5. **TRAP 5 — `validate/` Importing `audit/` Breaches `D-16` AST Wall:** NEVER import `ets2v2.audit.taint` from `ets2v2.validate`. Keep `check_license_taint_bytes()` self-contained in `validate/invariants.py`.
6. **TRAP 6 — `\biea\b` Taint Regex False Positives:** NEVER use bare substring `"iea"`. Use word-boundary `(?:international\s+energy\s+agency|\biea\b)` and verify zero false positives across all `225` `data/laws/countries/*.json`, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, snapshots, and built 43-locale packages.
7. **TRAP 7 — `tests/test_package_icons_metadata.py:173-202` Volatile Date Regex:** Keep `description.txt` concise (`D-12`) with zero `YYYY-MM-DD` or `1.62-YYYY.WW` strings; put the detailed Global Snapshot Coverage block & full Tier 1/2 attributions in `CHANGELOG_{SUMMER,WINTER}.md`.
8. **TRAP 8 — `tests/test_publish_workflow.py:210-212` (`def _sanitize(` count >= 2 & zero `${{` inside `run:`):** Preserve `def _sanitize(` in both Step Summary and PR body scripts in `phase-a-release.yml`, and enforce zero `${{` inside `run:` across both `phase-a-release.yml` and `osm-speed-audit.yml`.

---

## 7. No Analog Found

Files introducing net-new Phase 5 capabilities with no direct Phase 1–4 analog (planner should combine `05-CONTEXT.md` + `05-RESEARCH.md` specifications with Patterns A–D and §4 shared conventions above):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/ets2v2/fetch/_html.py` | utility / parser | transform | First stdlib `HTMLParser` `<table>` cell extractor & multi-charset (`utf-8-sig`/`windows-1251`/`latin-1`) decoder in the repo (Phase 3 only had `AnchorExtractor` for `<a>` links) |
| `src/ets2v2/audit/osm_speeds.py` | service / auditor | request-response + transform | First `westnordost/osm-legal-default-speeds` rule normalizer, `data/laws/` statutory speed-limit diff engine, and clean-room allowlist splitter in the repo |
| `src/ets2v2/audit/overpass.py` | service / client | request-response | First Overpass (`out tags 500;` form-POST) and Taginfo v4 (`key/values`) empirical tag-distribution client in the repo |

---

## Metadata

**Analog search scope:** `src/ets2v2/{vfs,sii,baseline,normalize,registry,fetch,package,validate,merge,publish,cli.py}`, `tests/`, `.github/workflows/`, `data/`, `pyproject.toml`
**Files scanned:** 36 tracked source, config, workflow, and test files
**Pattern extraction date:** 2026-11-25
