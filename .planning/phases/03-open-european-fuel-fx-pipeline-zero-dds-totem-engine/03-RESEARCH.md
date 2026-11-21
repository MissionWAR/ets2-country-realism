# Phase 3: Open European Fuel/FX Pipeline & Zero-DDS Totem Engine - Research

**Researched:** 2026-11-21
**Domain:** Automated Open European/EEA Fuel & Multi-Provider FX Data Pipeline (`httpx` + `openpyxl` + Pydantic v2) and ETS2 `1.62.3.3s` Zero-DDS 43-Locale Roadside Fuel Totem Synthesis
**Confidence:** **HIGH**

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 — Non-EU Vanilla Countries (`AL`, `BA`, `CH`, `IS`, `ME`, `MK`, `RS`, `RU`, `TR`, `XK`):** Use `fuel-prices.eu` (`CC BY 4.0`) where covered for non-EU vanilla European countries, and seed any remaining uncovered non-EU vanilla entries from the ETS2 `1.62` baseline (`data/baselines/ets2_1.62_def/countries.json`) into `state/prices.lock.json` until Phase 5 adds dedicated Tier 2/3 national portal collectors. Convert baseline/fallback values cleanly through live FX so all 36 Vanilla+DLC countries have coherent EUR `.sui` and native-currency totem prices immediately.
- **D-02 — Missing Secondary Fuel Grades (`98`, `100`, `Diesel+`, `E85`, `LPG`, `92`, `MPO`):** Use live national multi-grade feeds (`FR` `prix-carburants.gouv.fr`, `DE` `Tankerkönig` when keyed, `ES` MITECO, `IT` MIMIT, `NL` CBS StatLine) and `EC Weekly Oil Bulletin` `LPG` directly wherever available. For any country/grade not directly published by a Tier 1 feed, compute deterministic secondary grades using documented per-grade market spread ratios over live `petrol_95` / `diesel` (e.g., `petrol_98 ≈ petrol_95 × 1.06`, `petrol_100 ≈ petrol_95 × 1.12`, `diesel_plus ≈ diesel × 1.07`, `e85 ≈ petrol_95 × 0.72`, `mpo ≈ diesel × 0.75`, `petrol_92 ≈ petrol_95 × 0.96`, `lpg ≈ petrol_95 × 0.48` — exact ratios verified during Phase 3 research) so all multi-grade totems track weekly swings realistically.
- **D-03 — Optional `TANKERKOENIG_API_KEY` for Germany (`DE`):** Treat Germany's `Tankerkönig` (`CC BY 4.0`) API key as optional enrichment. When `TANKERKOENIG_API_KEY` is present in environment / GitHub Actions Secrets, sample a deterministic fixed set of German stations/cities for live multi-grade (`E5`/`E10`/`Diesel`) averages; when unset, silently fall back to `EC Weekly Oil Bulletin` (`DE`) + documented grade spreads so local builds, tests, and public forks work zero-secret out of the box.
- **D-04 — `state/prices.lock.json` Tracks 39 European Territories (`36` Vanilla + `IE`/`CY`/`MT`):** Store all **39** European entries in `state/prices.lock.json` (`36` Vanilla+DLC countries plus `IE`, `CY`, and `MT` naturally returned by the EU-27 `EC Weekly Oil Bulletin`). This gives ETS2 `1.62`'s `gas_ie_*` fuel sign boards live official Irish EUR prices immediately and pre-warms `IE`/`CY`/`MT` for Phase 4 ProMods, while Core `def/country/*.sui` and `speed_limits.sii` remain strictly scoped to the **36** Vanilla+DLC countries. — **Reversibility:** `moderate` — cleanly bridges `1.62` `gas_ie_*` signs and Phase 4 ProMods without expanding Core `.sui` scope.
- **D-05 — Two-Stage Decoupled Flow (`fetch` vs offline `build`/`publish`):** Place the price lockfile at `state/prices.lock.json` beside `state/published.json`. Online `ets2v2 fetch` updates `state/prices.lock.json` (with FX cross-validation and circuit-breaker guards), while `ets2v2 build` and `ets2v2 publish release` remain **100% offline-deterministic**, reading `state/prices.lock.json` with zero network I/O. In `.github/workflows/phase-a-release.yml`, run the online `fetch` step before `publish release`, and commit updated `state/prices.lock.json` alongside `state/published.json` and `CHANGELOG_{SUMMER,WINTER}.md` inside the single persistent Release PR (`release/phase-a-weekly`). — **Reversibility:** `costly` — defines the offline/online boundary, PR CI reproducibility, and Friday Release PR artifact contract.
- **D-06 — Strict Price Circuit Breaker with Manual Shock Override:** Automatically reject and hold the last-known-good value in `state/prices.lock.json` (recording a structured alert) whenever a fetched price falls outside `0.01–5.00 EUR/L` equivalent **OR** changes by more than `±25%` week-over-week against the lockfile. Provide a manual CLI override flag (`--allow-jump <ISO2>`) on `ets2v2 fetch` so maintainers can explicitly accept genuine tax/currency shocks without weakening default protection against upstream unit-scaling bugs (e.g., EUR/1000L or pence-as-GBP).
- **D-07 — Tiered FX Cross-Validation & Currency-Split Guard (`DAT-01`):** Cross-validate primary `Frankfurter v2` rates against `ECB eurofxref-daily.xml` (for ECB currencies) and `fawazahmed0/exchange-api` / `CBR XML` (for non-ECB/regional currencies like `RUB`, `ALL`, `BAM`, `MKD`, `RSD`), accounting for ECB weekend/TARGET2 fixing lag. Enforce tiered divergence tolerances:
  - Warn at `>2%` divergence for major/ECB pairs (`GBP`, `CHF`, `CZK`, `DKK`, `HUF`, `ISK`, `NOK`, `PLN`, `RON`, `SEK`), and `>5%` for volatile/non-ECB pairs (`TRY`, `RUB`, `ALL`, `BAM`, `MKD`, `RSD`).
  - Reject & hold lockfile FX with an alert if divergence exceeds `10%` or fails currency-split sanity checks (e.g., inverted `EUR/X` vs `X/EUR` magnitude, non-positive/NaN rates, or `BG` not pinned to `EUR = 1.0`).
- **D-08 — Outage & Staleness Policy in Friday CI:**
  - **Partial upstream outage** (one or more feeds unreachable/failing while at least one Tier 1 fuel feed succeeds): warn loudly, retain `state/prices.lock.json` values for affected countries, record structured alerts, and proceed with the Friday build.
  - **Total upstream outage** (`0` live Tier 1 fuel feeds reachable during `ets2v2 fetch`): exit non-zero so Friday CI fails loudly and alerts the maintainer rather than silently no-oping on stale data.
  - **Staleness alerts:** Emit structured warnings in fetch output, changelogs, and Release PR summary when a Tier 1 country entry is older than **14 days**, or a fallback/seeded entry is older than **30 days**.
- **D-09 — Full Identifiable Single-Text Board Coverage (461 `1.62` Boards):** Rewrite every identifiable country/city + grade board among the **461** single-text fuel boards in `data/baselines/ets2_1.62_def/fuel_boards.json` (`373` `active_fp` + identifiable `47` `placeholder` + identifiable `41` `blank`) to namespaced `@@fp_<cc>_<grade>_ets2v2@@` tokens backed by `locale/<lang>/local_module.ets2v2_fuel.sii` across all **43** active ETS2 `1.62` locales (`fr_qc` excluded, `fr_ca` synced). Explicitly fix all known `1.62` / `3249064596` gaps:
  - Populate all `17` active unmapped boards (`gas_bi_*`, `gas_ie_*` via `IE` live EUR prices, `gas_ba_*_lpg`, `gas_dk_92`).
  - Restore `gas_is_ip1_98.sii` (blanked in `3249064596`) and fix vanilla `1.62`'s swapped `gas_is_yokull_95` / `gas_is_yokull_diesel` tokens.
  - Map city-named and placeholder/blank grade boards (e.g., `gas_dortmund_98`/`lpg` -> `DE`, `gas_al_apus_98`/`lpg` -> `AL`, `gas_ie_cloveroil_*` -> `IE`, `gas_bi_*_super*` -> `GB`).
  - Preserve intentionally empty structural spacer boards (such as `gas_empty`) untouched.
  - Keep `5` excluded multi-item highway signs untouched (`fi_oulu_95`, `fi_oulu_98`, `rs_fuel_01`, `ru_m_95`, `ru_m_98`).
- **D-10 — Authentic Native-Currency Pump Formatting Gated by `1.62` `.font` Verification:** Display native local currencies and real-world sub-unit pump conventions on totems, verified against ETS2 `1.62` `.font` glyph tables and `coords_*` bounding boxes during Phase 3 research:
  - **UK (`GB`):** Pence per litre with 1 decimal (e.g., `142.9` for £1.429).
  - **Eurozone & Tenth-Cent Markets (`DE`, `AT`, `FR`, `BE`, `ES`, `IT`, `NL`, `IE`, etc.):** EUR with `<sup>9</sup>` tenth-cent formatting where `1.62` Prism3D sign templates and board fonts support it cleanly, falling back deterministically to `3`-decimal (`1.789`) or `2`-decimal (`1.79`) on narrow or 7-segment boards that cannot render `<sup>` cleanly without clipping.
  - **Bulgaria (`BG`):** Post-2026 `EUR` (`2` decimals, e.g., `1.34`).
  - **High-Unit Integer Currencies (`HUF`, `ISK`, `ALL`, `RSD`):** Whole integers (e.g., `615`, `312`, `185`, `198`).
  - **Other National Currencies (`CHF`, `CZK`, `DKK`, `NOK`, `PLN`, `RON`, `SEK`, `BAM`, `MKD`, `RUB`, `TRY`):** Standard national pump precision (verified against `1.62` `fuel_price_strings.sui` widths during research).
- **D-11 — Uniform Dot (`.`) Decimal Separator:** Use `.` as the decimal separator across all generated totem strings to match roadside LED/7-segment displays and vanilla `1.62` `fuel_price_strings.sui`, avoiding missing-glyph boxes across all `6` ETS2 gas fonts.
- **D-12 — Hard Totem Invariants in Offline SCS Validator (`PUB-01` Extension):** Extend `src/ets2v2/validate/` (`validate workshop` and `validate local`) to enforce Phase 3 totem invariants as hard failures:
  - Zero `.dds` or `.tobj` files anywhere in the mod package (Zero-DDS guarantee).
  - Exact **43** active `locale/<lang>/local_module.ets2v2_fuel.sii` files matching `data/baselines/ets2_1.62_def/locales.json` (zero `fr_qc`, `fr_ca` present), all carrying identical sorted `key[]`/`val[]` sets with valid `fp_*_ets2v2` keys and non-empty values.
  - Every emitted `def/sign/board/*.sii` passes `validate_sii_hygiene()` (UTF-8 no-BOM LF, POSIX `/`, `<=12`-char `[a-z0-9_]` unit segments), preserves baseline `model_name: ""`, `font_face`, and `coords_*`, and resolves its `@@fp_*_ets2v2@@` token cleanly in `local_module.ets2v2_fuel.sii` (zero dangling/orphan tokens).
- **D-13 — Preserve Locked `RealismSnapshot` `schema_version: 1` (Provenance Separation):** Keep `RealismSnapshot` (`src/ets2v2/registry/snapshot.py`, locked as `one-way` in Phase 2 `D-11`) strictly at `schema_version: 1` with `extra="forbid"` (`currency`, `eur_per_liter`, `local_prices`, `source`). Store full operational provenance (FX provider rates, divergence metrics, `fetched_at` timestamps, fallback flags, staleness ages, and circuit-breaker alerts) inside `state/prices.lock.json` rather than bumping the snapshot schema. — **Reversibility:** `one-way` — preserves Phase 2 -> Phase 4 snapshot compatibility without breaking downstream consumers.
- **D-14 — Canonical Domain Grade Keys in `local_prices` & `state/prices.lock.json`:** Use clean, game-agnostic canonical fuel grade keys (`diesel`, `diesel_plus`, `petrol_95`, `petrol_98`, `petrol_100`, `petrol_92`, `e85`, `lpg`, `mpo`) inside both `RealismSnapshotFuel.local_prices` and `state/prices.lock.json`. Map ETS2's regional `fp_*` board/token aliases deterministically via a single adapter table (`natural95`/`unleaded` -> `petrol_95`, `super` -> `petrol_98`, `diesel5` -> `diesel_plus`, etc.) when emitting `@@fp_*_ets2v2@@` totems.
- **D-15 — 3-Decimal `eur_per_liter` Precision (`0.001 EUR/L`):** Round `eur_per_liter` (emitted as `country_data.fuel_price` in `.sui`) to **3 decimal places** (`0.001 EUR/L`, e.g., `1.642`), matching ETS2 `1.62` and `3249064596` conventions and maintaining tenth-cent consistency with roadside totems.
- **D-16 — Weekly Fuel Table, Open-Data Attribution & Alerts in Changelogs and `description.txt`:** Extend `CHANGELOG_SUMMER.md` and `CHANGELOG_WINTER.md` (`src/ets2v2/publish/changelog.py`) with:
  - A compact 36-country fuel price summary table (`ISO2`, `EUR/L` diesel, local diesel & 95 display values, source identifier, freshness/date).
  - A highlighted **Circuit-Breaker & Staleness Alerts** section whenever any country fell back to `state/prices.lock.json`, tripped a jump/bounds/FX guard, or exceeded staleness thresholds.
  - Explicit open-data attribution (`EC Weekly Oil Bulletin CC BY 4.0`, `fuel-prices.eu CC BY 4.0`, `UK DESNZ OGL v3`, `Norway SSB CC BY 4.0`, `France Licence Ouverte`, `Italy MIMIT IODL 2.0`, `Spain MITECO`, `Netherlands CBS`, `Germany Tankerkönig CC BY 4.0`, `Frankfurter v2 MIT`, `ECB`, `fawazahmed0 CC0`) in both `CHANGELOG_*.md` and Workshop `description.txt`.

### Claude's Discretion
- Exact Python subpackage layout for Phase 3 (`src/ets2v2/fetch/`, `src/ets2v2/normalize/`, and totem module placement under `src/ets2v2/package/` or `src/ets2v2/totems/`), updating `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` cleanly while keeping Phase 4's `merge/` blocked until Phase 4.
- Adding `httpx>=0.28,<0.29` and `openpyxl>=3.1,<4` (and updating `uv.lock` + `test_cli_scaffold.py` dependency checks) while preserving strictly permissive licensing (`MIT`/`BSD`/`Apache-2.0`/`PSF-2.0`).
- Exact `ets2v2 fetch` CLI flags (e.g., `--lock-path`, `--allow-jump`, `--fx-only`, `--json`, `--timeout`), internal HTTP retry/backoff settings, and deterministic German city coordinates for optional `Tankerkönig` sampling.
- Exact JSON key naming inside `state/prices.lock.json` and exact unit naming inside generated `def/sign/board/*.sii` and `local_module.ets2v2_fuel.sii` (within SCS `[a-z0-9_]{1,12}` segment rules).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed strictly within Phase 3 boundaries. ProMods `pm_*_fuel` totems and `compose-local` remain mapped to Phase 4 (`MAP-01`..`MAP-05`), and non-EU Tier 1/2/3 global collectors (`CH` BFS/LIK, `IS` Orkusetur, `MK` ERC, `RU` Rosstat, `US`/`BR`/`JP`/etc.) + CI OSM speed-limit drift audits remain mapped to Phase 5 (`GLB-01`..`GLB-04`).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **DAT-01** | Fetch and cross-validate FX exchange rates using `Frankfurter v2` (`MIT`, 219 currencies), `ECB` validator, `fawazahmed0` currency API (`CC0`), and `CBR` FX with deterministic country-currency mapping and currency-split sanity checks. | Section 3 locks exact endpoints/schemas (`Frankfurter v2` flat array vs v1 dict, `ECB` XML namespaces + RUB suspension, `fawazahmed0` jsDelivr/Pages lowercase JSON, `CBR` `windows-1251` comma-decimal XML), all 39 territory currency mappings (incl. `BG = EUR = 1.0`, `BAM = 1.95583` fixed peg), and tiered `2%/5%/10%` divergence + sanity formulas. |
| **DAT-02** | Collect Tier 1 open European & EEA government fuel data from `EC Weekly Oil Bulletin` (dynamic XLSX discovery + `FionnHughes`/`fuel-prices.eu` fallback), `UK DESNZ`, `NO SSB`, and multi-grade national APIs (`FR`, `DE`, `ES`, `IT`, `NL`). | Section 4 locks exact endpoints, Drupal/GOV.UK link discovery, column headers, unit scaling (`EUR/1000L` -> `/1000`, `pence/L` -> `/100`), `EL` -> `GR`, OpenDataSoft v2.1 `avg()` aggregation for `FR`, `MITECO` comma strings for `ES`, `MIMIT` line-1 comment + `isSelf=1` for `IT`, `CBS 80416ned` OData fields for `NL`, `SSB 09654` JSON-stat2 for `NO`, optional `Tankerkönig` 5-city sampling for `DE`, non-EU `fuel-prices.eu`/baseline seeding, and empirically grounded secondary-grade spreads. |
| **DAT-03** | Enforce circuit-breaker safety (`0.01–5.00 EUR/L` equivalent bounds and `±25%` change alerts) backed by `prices.lock.json` so stale or broken upstream endpoints safely fall back to last-known-good attributed values. | Section 6 defines the exact `state/prices.lock.json` (`schema_version: 1`) Pydantic v2 schema, `0.01–5.00 EUR/L` + `±25%` WoW guards with `--allow-jump <ISO2>`, partial vs total outage exit codes, 14d/30d staleness alerts, and zero-network offline `build`/`publish` coupling preserving locked `RealismSnapshot` v1 (`D-13`). |
| **TOT-01** | Implement Option 4b Zero-DDS gas-station totem updates using namespaced `@@fp_*_ets2v2@@` tokens in `def/sign/board/*.sii` and `locale/<lang>/local_module.ets2v2_fuel.sii` across all 43 active ETS2 `1.62` locales. | Section 5 uncovers the critical `fuel_boards.json` baseline schema gap (`width`, `height`, `font_size`, `text_halign`, `text_valign`, `font_color`, `font_opacity`, `line_spacing`, `letter_spacing`, `id`, `board_name`), specifies the clean-room extractor extension + re-extraction, and locks the exact `localization_db : .ets2v2_fuel` (`11` chars `<=12`) 43-locale synthesizer and Offline SCS Validator hard checks (`D-12`). |
| **TOT-02** | Render authentic multi-grade (`95`, `98`, `100`, `Diesel`, `Diesel+`, `E85`, `LPG`) prices in national currencies and sub-units (pence, eurocents, `<sup>9</sup>`, Bulgaria EUR transition) while fixing all 17 active and 69 placeholder/blank missing `1.62` sign boards (including `gas_bi_*`, `gas_ie_*`, `gas_ba_*_lpg`, `gas_dk_92`, `gas_is_ip1_98`). | Section 5 provides the exhaustive 461-board forensic audit (`460` identifiable boards -> `164` unique tokens across `37` countries, `1` untouched spacer `gas_empty`, `5` excluded highway signs), exact `base.scs` `.font` glyph tables & normalized widths for all `6` SDF gas fonts, exact 3-tier Eurozone `<sup>` / 3-dec / 2-dec width-budget routing (eliminating overflow on all `40` narrow boards), and per-country native currency formatting verified against `locale/fuel_price_strings.sui`. |
</phase_requirements>

---

## Summary

Direct inspection of ETS2 `1.62.3.3s` archives (`def.scs`, `locale.scs`, `base.scs`), the existing `src/ets2v2/` Phase 1–2 codebase, and live upstream open-data specifications establishes a crystal-clear, zero-guesswork blueprint for Phase 3. Every external FX and Tier 1 fuel feed uses clean permissive/open licenses (`MIT`, `CC0-1.0`, `CC BY 4.0`, `OGL v3.0`, `Licence Ouverte v2.0`, `IODL 2.0`), requires zero mandatory secrets (`TANKERKOENIG_API_KEY` is strictly optional), and fits cleanly into the two-stage online-`fetch` -> `state/prices.lock.json` -> offline-`build`/`publish` boundary (`D-05`).

**Two high-impact forensic discoveries emerged during this research that directly prevent execution-time failures:**
1. **`fuel_boards.json` Baseline Schema Must Be Extended Before Synthesizing `def/sign/board/*.sii`:** Direct inspection of raw ETS2 `1.62.3.3s` `def.scs:/def/sign/board/*.sii` files revealed that `src/ets2v2/sii/sign_board.py` currently parses `board_size`, `h_align`, and `v_align` (which do not exist in `1.62` sign templates — the real SCS attributes are `width`, `height`, `text_halign`, and `text_valign`) and omits `board_name`, `dynamic_attributes`, `font_size`, `font_color`, `font_opacity`, `line_spacing`, `letter_spacing`, `id`, `area_name`, `area_idx`, `z_order`, and `tag` `[VERIFIED: def.scs + src/ets2v2/sii/sign_board.py:84-156]`. Without preserving `font_size`, `font_color` (LED red/green/amber/white!), and `text_halign`, synthesized clean-room boards would render in wrong colors, sizes, and positions. Extending `sign_board.py`, `baseline/models.py`, and `baseline/extractor.py` and re-running `uv run ets2v2 baseline extract` solves this cleanly while keeping `data/baselines/ets2_1.62_def/fuel_boards.json` 100% clean-room JSON.
2. **Exact `.font` Glyph Tables & Width Budgets Prove `gas_empty` Is the Sole Spacer and 40 Narrow Boards Require 2-Decimal Fallback:** Direct extraction of all 6 `/font/sign/gas_*.font` files from `base.scs` proved that all 6 are modern SDF fonts (`1.43+`) containing **only** `' '`, `','`, `'.'`, `'0'`–`'9'` (plus `'-'` in `gas_sign_digit.font`) — **zero letters or currency symbols** — and that `gas_segment_7_standard.font` and `gas_sign_digit.font` are strictly **monospace** where `.` consumes a full digit cell `[VERIFIED: base.scs:/font/sign/gas_*.font]`. Checking exact rendered widths across all `461` single-text boards proved that **460** boards are identifiable fuel price boards across `37` countries (`36` Vanilla+DLC + `IE`), **1** board (`gas_empty`, uniquely having `font_size: 0` and `font_opacity: 0`) is a structural spacer, and **40** narrow Eurozone boards overflow on 5 characters (`1.789`) or `1.78<sup>9</sup>` and therefore route deterministically to compact 2-decimal tokens (`fp_<cc>_<grade>_c_ets2v2`).

**Primary recommendation:** Implement Phase 3 across 4 clean sequential plans: `03-01` (deps + `fetch/` FX & `normalize/` currency-split cross-validator), `03-02` (Tier 1 EU/EEA fuel collectors + `state/prices.lock.json` circuit breaker + `ets2v2 fetch` CLI), `03-03` (baseline `fuel_boards.json` rendering-attribute extension + Option 4b Zero-DDS totem compiler for all `460` boards & `43` locales + `validate/` hard invariants), and `03-04` (native-currency multi-grade formatter with `.font` width budgets, `builder.py`/`snapshot.py` lockfile integration, `changelog.py`/`description.txt` fuel table + alerts + attributions, and Friday `phase-a-release.yml` wiring).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| **Multi-Provider FX Fetching & Cross-Validation (`DAT-01`)** | Online CLI (`ets2v2 fetch` -> `src/ets2v2/fetch/fx.py`, `src/ets2v2/normalize/fx.py`) | Lockfile Persistence (`state/prices.lock.json`) | Isolates all external network I/O and FX cross-validation inside `fetch` so offline builds and PR CI never touch the network (`D-05`). |
| **Tier 1 European Fuel Ingestion & Secondary Spreads (`DAT-02`)** | Online CLI (`src/ets2v2/fetch/fuel_*.py`, `src/ets2v2/normalize/spreads.py`) | Lockfile Persistence (`state/prices.lock.json`) | Each upstream source lives in an isolated fault-tolerant collector; missing secondary grades are computed deterministically from verified live anchors (`D-02`). |
| **Circuit Breaker, Lockfile & Staleness Policy (`DAT-03`)** | Normalization / State Layer (`src/ets2v2/normalize/lockfile.py`, `state/prices.lock.json`) | Release Reporting (`src/ets2v2/publish/changelog.py`, Friday CI) | Enforces `0.01–5.00 EUR/L`, `±25%` WoW, FX `2%/5%/10%` guards, and `--allow-jump` before writing `state/prices.lock.json`; downstream offline consumers read validated lockfile state only. |
| **Snapshot v1 Fuel Injection (`D-13`, `D-14`, `D-15`)** | Registry Layer (`src/ets2v2/registry/snapshot.py`) | Lockfile Loader (`src/ets2v2/normalize/lockfile.py`) | Injects `3`-decimal `eur_per_liter`, numeric `local_prices` (canonical grade keys), and `source` into locked `schema_version: 1` `RealismSnapshot` (`extra="forbid"`) while keeping provenance/alerts in `prices.lock.json`. |
| **Zero-DDS Totem Compilation & Native Formatting (`TOT-01`, `TOT-02`)** | Package Compiler (`src/ets2v2/package/totems.py`, `src/ets2v2/package/builder.py`) | Baseline Metadata (`data/baselines/ets2_1.62_def/fuel_boards.json`, `locales.json`) | Deterministically synthesizes `460` `def/sign/board/*.sii` files and `43` identical `locale/<lang>/local_module.ets2v2_fuel.sii` files purely offline from `prices.lock.json` + baseline JSON. |
| **Hard Totem Invariant Validation (`D-12`)** | Offline Validator (`src/ets2v2/validate/workshop.py`, `src/ets2v2/validate/invariants.py`) | SII Parsers (`src/ets2v2/sii/sign_board.py`, `localization.py`, `hygiene.py`) | Independently parses built Workshop roots & local ZIPs to enforce zero `.dds`/`.tobj`, exact `43`-locale sync, SII hygiene, attribute preservation, and zero orphan/dangling `@@fp_*_ets2v2@@` tokens. |
| **Friday CI Orchestration, Changelogs & Release PR (`D-05`, `D-08`, `D-16`)** | Publish & CI Layer (`src/ets2v2/publish/release.py`, `changelog.py`, `.github/workflows/phase-a-release.yml`) | Package Metadata (`src/ets2v2/package/metadata.py`) | Runs online `ets2v2 fetch` before offline `ets2v2 publish release`, embeds 36-country fuel table + alerts + open-data attribution, and stages `state/prices.lock.json` in `release/phase-a-weekly`. |

---

## Standard Stack

### Core (Phase 3 Additions to Existing Phase 1–2 Stack)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **httpx** | `>=0.28,<0.29` (`0.28.1`) `[CITED: pypi.org/project/httpx]` | HTTP/1.1 & HTTP/2 client for FX and Tier 1 fuel collectors | Modern typed Python HTTP client with explicit timeouts, redirect controls, `MockTransport` for 100% offline deterministic `pytest` fixtures, and zero `requests`/`urllib3` quirks. |
| **openpyxl** | `>=3.1,<4` (`3.1.5`) `[CITED: pypi.org/project/openpyxl]` | Parsing EC Weekly Oil Bulletin `.xlsx` ("Prices with taxes") workbooks | Standard pure-Python OOXML `.xlsx` reader (`read_only=True, data_only=True`) with zero compiled C extensions on Windows/Linux. |
| **pydantic** *(already installed)* | `>=2.14,<3` `[VERIFIED: pyproject.toml:13]` | Strict frozen schemas for `PricesLockfile` (`schema_version: 1`) and `RealismSnapshot` v1 | Already enforces `ConfigDict(strict=True, frozen=True, extra="forbid")` across the repo. |
| **xml.etree.ElementTree / csv / html.parser / statistics / decimal** *(Python 3.12 stdlib)* | Python `3.12.13` `[VERIFIED: uv run python --version]` | Parsing ECB/CBR XML, UK DESNZ/MIMIT/FionnHughes CSV, EC/GOV.UK HTML anchor links, medians, and exact `ROUND_HALF_UP` price rounding | Zero extra third-party dependencies (`BeautifulSoup4`/`lxml` deferred until Phase 5 Tier 2 HTML scraping if needed). |

### Supporting (Existing Quality Gates)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest** + **pytest-cov** | `9.2.0` `[VERIFIED: uv run pytest --version]` | Unit, mocked-HTTP transport, circuit-breaker, totem rendering, and validator invariant tests | Every task commit (`uv run --offline pytest -q --tb=short`). |
| **ruff** | `0.17.5` `[VERIFIED: uv run ruff --version]` | Linting (`E, F, I, UP, B, SIM, RUF`) + formatting | Every task commit (`uv run --offline ruff check && uv run --offline ruff format --check`). |
| **basedpyright** | `1.40.2` `[VERIFIED: uv run basedpyright --version]` | Strict static type checking (`typeCheckingMode = "strict"`) | Every task commit (`uv run --offline basedpyright`). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx` | `requests` or stdlib `urllib.request` | `httpx` provides native `httpx.MockTransport` for clean offline transport-level testing, strict timeout objects (`httpx.Timeout`), and seamless HTTP/2 support; already selected in `.planning/research/STACK.md`. |
| Stdlib `html.parser` for EC/DESNZ link discovery | `beautifulsoup4` + `lxml` | Extracting `<a href="...xlsx">` / `<a href="...csv">` from 2 static government landing pages takes 15 lines of stdlib `HTMLParser` and avoids adding unnecessary dependencies in Phase 3 (`lxml` adds C-wheel surface). |
| `xml.etree.ElementTree` + strict size cap | `defusedxml` | ECB (`~3 KB`) and CBR (`~10 KB`) XML feeds are tiny, predictable central-bank documents; enforcing a strict byte-size cap (`<= 2 MB`) + rejecting `<!DOCTYPE`/`<!ENTITY` tokens before `ET.fromstring()` prevents XXE/billion-laughs without adding an extra dependency (and Python's Expat does not resolve external entities by default). |
| `Decimal` (`ROUND_HALF_UP`) for pump display | Binary `float` `round()` | Python's `round()` uses banker's rounding (`ROUND_HALF_EVEN`), which produces counter-intuitive pump prices (`1.785 -> 1.78` vs `1.79`). Using `Decimal(str(val)).quantize(..., rounding=ROUND_HALF_UP)` guarantees deterministic, intuitive pump rounding. |

**Installation:**
```bash
uv add "httpx>=0.28,<0.29" "openpyxl>=3.1,<4"
```
*(Update `tests/test_cli_scaffold.py::test_pyproject_metadata_and_quality_gates` and `test_uv_lock_contains_verified_packages` to include `httpx>=0.28,<0.29` and `openpyxl>=3.1,<4`, and unlock `fetch` and `normalize` in `test_active_phase_only_package_layout` while keeping `merge` blocked for Phase 4.)*

---

## Package Legitimacy Audit

> Audited via official PyPI documentation & dependency metadata (`gsd-tools.cjs` package-legitimacy CLI was not present in the local runtime path; versions and licenses verified against PyPI metadata `[CITED: pypi.org]`).

| Package | Registry | Version | License | Transitive Dependencies & Licenses | Verdict | Disposition |
|---------|----------|---------|---------|------------------------------------|---------|-------------|
| `httpx` | PyPI | `0.28.1` | `BSD-3-Clause` | `httpcore 1.0.9` (`BSD-3-Clause`), `anyio 4.x` (`MIT`), `h11 0.16.0` (`MIT`), `idna 3.x` (`BSD-3-Clause`), `sniffio 1.3.1` (`MIT OR Apache-2.0`), `certifi` (`MPL-2.0`) | `[OK]` (Well-established Encode OSS project; zero GPL/LGPL/AGPL) | Approved |
| `openpyxl` | PyPI | `3.1.5` | `MIT` | `et-xmlfile 2.0.0` (`MIT`) | `[OK]` (Well-established pure-Python OOXML library; zero GPL/LGPL/AGPL) | Approved |

**Packages removed due to `[SLOP]` verdict:** None.
**Packages flagged as suspicious `[SUS]`:** None.
*License note:* `certifi` (transitive dependency of `httpx`) is licensed under **`MPL-2.0`** (weak file-level permissive license, fully compatible with `MIT` / `CC BY 4.0` distribution and containing zero GPL/LGPL/AGPL copyleft obligations). Note that `pyproject.toml` already pins strictly permissive packages and `uv.lock` will lock exact hashes for every wheel/sdist.

---

## Deliverable 1: Multi-Provider FX Architecture (`DAT-01`, `D-07`)

### 1.1 Exact Live Endpoints, Schemas & Quirks

| Role | Provider | Exact Endpoint URL | Format & Exact Schema | Cadence & Quirks | License / Attribution |
|------|----------|-------------------|-----------------------|------------------|-----------------------|
| **Primary (all 17 currencies)** | **Frankfurter v2** | `GET https://api.frankfurter.dev/v2/rates?base=EUR` (or filter `&quotes=ALL,BAM,CHF,CZK,DKK,GBP,HUF,ISK,MKD,NOK,PLN,RON,RSD,RUB,SEK,TRY`) `[CITED: frankfurter.dev]` | **Flat JSON array** (breaking change vs v1 dict!): `[{"date": "2026-11-20", "base": "EUR", "quote": "GBP", "rate": 0.8342}, ...]` `[CITED: frankfurter.dev]`. Error schema: `{"status": 422, "message": "..."}`. | Daily business-day fixings blended from 108 central banks (219 currencies). Supports `?providers=ecb` to pin ECB specifically. Keyless; fair-use rate limit (1 single call per `fetch` run!). | **MIT** (`Frankfurter v2`) |
| **Validator (ECB currencies)** | **ECB Eurofxref Daily XML** | `GET https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` `[CITED: ecb.europa.eu]` | XML with namespaces `gesmes="http://www.gesmes.org/xml/2002-08-01"` and default `ns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"`. Structure: `<Cube><Cube time="YYYY-MM-DD"><Cube currency="GBP" rate="0.8342"/>...</Cube></Cube>`. | Published weekdays ~16:00 CET; frozen on weekends & TARGET2 holidays. **Covers 11 of our 16 non-EUR currencies** (`CHF`, `CZK`, `DKK`, `GBP`, `HUF`, `ISK`, `NOK`, `PLN`, `RON`, `SEK`, `TRY`). **`RUB` suspended since 2022-03-01** (`<Cube currency="RUB"/>` absent!). Never includes `ALL`, `BAM`, `MKD`, `RSD`. | **ECB Open Data** (attribution) |
| **Fallback / Non-ECB Validator** | **`fawazahmed0/exchange-api`** | Primary CDN: `GET https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/eur.json`<br>Mirror: `GET https://latest.currency-api.pages.dev/v1/currencies/eur.json` `[CITED: github.com/fawazahmed0/exchange-api]` | JSON object with **lowercase** currency keys: `{"date": "2026-11-20", "eur": {"gbp": 0.8342, "all": 98.5, "bam": 1.95583, "mkd": 61.5, "rsd": 117.1, "rub": 95.4, ...}}`. | Daily static CDN JSON (200+ currencies). Always normalize keys with `.upper()`. Zero rate limits; Cloudflare Pages mirror covers jsDelivr outages. | **CC0-1.0** (Public Domain) |
| **Regional RUB Cross-Validator** | **Central Bank of Russia (CBR) XML** | `GET https://www.cbr.ru/scripts/XML_daily.asp` `[CITED: cbr.ru]` | XML encoded in **`windows-1251`** (MUST decode `raw.decode("windows-1251")` BEFORE parsing or strip/convert encoding declaration!). `<ValCurs Date="DD.MM.YYYY"><Valute ID="R01239"><CharCode>EUR</CharCode><Nominal>1</Nominal><Value>90,3445</Value><VunitRate>90,3445</VunitRate></Valute>...</ValCurs>`. | Comma `,` decimal separator! `EUR` entry (`CharCode == "EUR"`, `ID="R01239"`) gives **RUB per 1 EUR** directly (`VunitRate` if present, else `Value / Nominal`). Note: `Nominal` may be `10`/`100`/`10000` for other currencies, so always divide `Value / Nominal` or use `VunitRate`. | Public Central Bank data (`CBR`) |

> **Critical Convention Verification:** All four providers yield **`1 EUR = X <CURRENCY>`** (units of local currency per 1 Euro):
> - `local_price = eur_per_liter * rate_per_eur`
> - `eur_per_liter = local_price / rate_per_eur`
> Never invert this direction; enforce directionality via the currency-split magnitude guard below.

### 1.2 Complete 39-Territory Currency Map (`36` Vanilla+DLC + `IE`, `CY`, `MT`)

Verified verbatim against `data/laws/countries/*.json` `[VERIFIED: data/laws/countries/*.json]` and `data/mappings/ets2_countries.json:1-294`:

| ISO-4217 | Territories (39 total) | FX Class | ECB Covered? | Validation Pair | Sanity Band (`1 EUR = X`) | Notes |
|----------|------------------------|----------|--------------|-----------------|---------------------------|-------|
| **`EUR`** | `AT`, `BE`, `BG`, `CY`*, `DE`, `EE`, `ES`, `FI`, `FR`, `GR`, `HR`, `IE`*, `IT`, `LT`, `LU`, `LV`, `ME`, `MT`*, `NL`, `PT`, `SI`, `SK`, `XK` (23 territories) | Pinned (`1.0`) | N/A | Hard invariant `rate == 1.0` | Exact `1.0` | `BG` adopted `EUR` on `2026-01-01` `[VERIFIED: data/laws/countries/bg.json]`; `ME` & `XK` use `EUR` unilaterally; `IE`/`CY`/`MT` are EU-27 EUR states (`D-04`). |
| **`GBP`** | `GB` (`uk`) | Major / ECB | Yes | Frankfurter v2 vs ECB (fallback `fawazahmed0`) | `0.60 – 1.25` | Warn `>2%`, reject `>10%`. **Unit trap:** UK DESNZ reports pence/L (`142.9`), NOT GBP/L (`1.429`)! |
| **`CHF`** | `CH` (`switzerland`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `0.70 – 1.40` | Warn `>2%`, reject `>10%`. |
| **`CZK`** | `CZ` (`czech`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `18.0 – 35.0` | Warn `>2%`, reject `>10%`. |
| **`DKK`** | `DK` (`denmark`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `7.00 – 7.90` | ERM II peg (`~7.46`). Warn `>2%`, reject `>10%`. |
| **`HUF`** | `HU` (`hungary`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `250.0 – 550.0` | Warn `>2%`, reject `>10%`. |
| **`ISK`** | `IS` (`iceland`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `100.0 – 250.0` | Warn `>2%`, reject `>10%`. |
| **`NOK`** | `NO` (`norway`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `7.5 – 16.0` | Warn `>2%`, reject `>10%`. |
| **`PLN`** | `PL` (`poland`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `3.2 – 6.0` | Warn `>2%`, reject `>10%`. |
| **`RON`** | `RO` (`romania`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `3.8 – 6.5` | Warn `>2%`, reject `>10%`. |
| **`SEK`** | `SE` (`sweden`) | Major / ECB | Yes | Frankfurter v2 vs ECB | `8.0 – 15.0` | Warn `>2%`, reject `>10%`. |
| **`TRY`** | `TR` (`turkey`) | Volatile / ECB | Yes | Frankfurter v2 vs ECB (fallback `fawazahmed0`) | `15.0 – 120.0` | **Volatile tier (`D-07`):** warn `>5%`, reject `>10%`. |
| **`RUB`** | `RU` (`russia`) | Volatile / Non-ECB | **No** (suspended) | Frankfurter v2 vs `CBR XML` & `fawazahmed0` | `40.0 – 250.0` | Warn `>5%`, reject `>10%`. CBR provides official EUR/RUB cross-rate. |
| **`ALL`** | `AL` (`albania`) | Volatile / Non-ECB | No | Frankfurter v2 vs `fawazahmed0` | `70.0 – 160.0` | Warn `>5%`, reject `>10%`. |
| **`BAM`** | `BA` (`bosnia`) | Fixed Peg / Non-ECB | No | Frankfurter v2 vs `fawazahmed0` + CBBH peg `1.95583` `[CITED: cbbh.ba]` | `1.90 – 2.01` | Legal currency-board peg **`1 EUR = 1.95583 BAM`**; if both APIs fail, peg `1.95583` is legally authoritative. Warn `>5%`, reject `>10%`. |
| **`MKD`** | `MK` (`macedonia`) | Volatile / Non-ECB | No | Frankfurter v2 vs `fawazahmed0` | `55.0 – 70.0` | De facto EUR peg (`~61.5`). Warn `>5%`, reject `>10%`. |
| **`RSD`** | `RS` (`serbia`) | Volatile / Non-ECB | No | Frankfurter v2 vs `fawazahmed0` | `95.0 – 145.0` | Managed float vs EUR (`~117.1`). Warn `>5%`, reject `>10%`. |

*`*` `IE`, `CY`, `MT` are stored in `state/prices.lock.json` (`D-04`) to feed ETS2 `1.62` `gas_ie_*` totems and pre-warm Phase 4 ProMods; they are NOT added to the 36 Vanilla+DLC `def/country/*.sui` Core files.*

### 1.3 Cross-Validation & Currency-Split Guard Math (`D-07`)

For each currency $c \neq \text{EUR}$:
1. **Provider resolution order:**
   - Primary: `Frankfurter v2` (`rate_primary`). If `Frankfurter v2` is unreachable or omits $c$, promote validator/fallback (`ECB` for ECB currencies, `CBR` for `RUB`, `fawazahmed0` for all others) to primary and record a `fx_primary_fallback` warning.
   - Validator: `ECB eurofxref-daily.xml` for ECB currencies (`GBP`, `CHF`, `CZK`, `DKK`, `HUF`, `ISK`, `NOK`, `PLN`, `RON`, `SEK`, `TRY`); `CBR XML` (primary validator) + `fawazahmed0` (secondary) for `RUB`; `fawazahmed0` (jsDelivr -> Cloudflare Pages mirror) for `ALL`, `BAM`, `MKD`, `RSD`.
2. **Sanity / Currency-Split Checks (Hard Reject -> Hold Lockfile):**
   - Reject if `not math.isfinite(rate)` or `rate <= 0`.
   - Reject if `rate` falls outside the currency's `[min_band, max_band]` sanity envelope above (immediately catches inverted `X/EUR` vs `EUR/X` bugs, e.g., `HUF = 0.0025` instead of `400.0`, or `GBP = 1.19` vs `0.84` when paired with validator check, or `100x` unit bugs).
   - Hard assert `country_currency["BG"] == "EUR"` and `rates["EUR"] == 1.0`.
3. **Relative Divergence Formula:**
   $$\text{divergence\_pct}(r_1, r_2) = \frac{|r_1 - r_2|}{\min(r_1, r_2)} \times 100$$
   - If `divergence_pct > 10.0`: **REJECT** fetched rate, retain previous `state/prices.lock.json` FX rate for $c$, emit structured `fx_divergence_rejected` alert.
   - Else if `c in MAJOR_ECB_CURRENCIES` (`GBP`, `CHF`, `CZK`, `DKK`, `HUF`, `ISK`, `NOK`, `PLN`, `RON`, `SEK`) and `divergence_pct > 2.0`: **ACCEPT** primary, emit structured `fx_divergence_warning` alert.
   - Else if `c in VOLATILE_NON_ECB_CURRENCIES` (`TRY`, `RUB`, `ALL`, `BAM`, `MKD`, `RSD`) and `divergence_pct > 5.0`: **ACCEPT** primary, emit structured `fx_divergence_warning` alert.
   - Weekend/TARGET2 lag note: On Saturday–Monday mornings before 16:00 CET, ECB XML reflects Friday's fixing while `fawazahmed0` may show weekend interbank drift; the `2%`/`5%` warn and `10%` reject bands naturally absorb Friday-to-Monday drift without false rejections.

---

## Deliverable 2: Tier 1 European/EEA Fuel Data Collectors (`DAT-02`, `D-01`..`D-04`)

### 2.1 Collector Priority & Source Matrix

| Priority / Scope | Source | Exact Endpoint & Discovery | Format, Columns & Exact Unit Scaling | Grades Supplied | Cadence & License |
|------------------|--------|---------------------------|--------------------------------------|-----------------|-------------------|
| **1. EU-27 Primary** | **EC Weekly Oil Bulletin** | Landing page: `https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en` `[CITED: energy.ec.europa.eu]`. Dynamically parse `<a href="...">` matching `"Prices with taxes"` / `Weekly_Oil_Bulletin` / `.xlsx` (Drupal UUID `/document/download/<uuid>_en` rotates!). | `.xlsx` (`openpyxl`, `read_only=True, data_only=True`). Match header row dynamically (NOT hardcoded column index!): find country ISO-2 code (`EL` -> **`GR`**!), `Euro-super 95` -> `petrol_95`, `Automotive gas oil` / `Gas oil` -> `diesel`, `LPG - motor fuel` / `LPG` -> `lpg`. **CRITICAL UNIT:** Reported in **`EUR per 1,000 litres`** -> **divide by `1000.0`**! Validate that latest row date is monotonic. | `diesel`, `petrol_95`, `lpg` (all **27** EU countries incl. `IE`, `CY`, `MT`, `BG` in EUR!) | Weekly (Thu ~17:00 CET; CI runs Fri `06:00 UTC`). **CC BY 4.0**. |
| **1b. EU-27 Fallback #1** | **`FionnHughes/eu-weekly-oil-bulletin`** | `GET https://huggingface.co/datasets/FionnHughes/eu-weekly-oil-bulletin/raw/main/eu_oil_bulletin.csv` `[CITED: huggingface.co/datasets/FionnHughes/eu-weekly-oil-bulletin]` | Tidy CSV (`date`, `geo`/`country`, `product`/`fuel`, `price`). Filter latest `date` per ISO-2 (`EL` -> `GR`), map `diesel`, `petrol_95`, `lpg`. Guard unit scale: if `price > 20.0` (EUR/1000L), divide by `1000.0`; else already `EUR/L`. | `diesel`, `petrol_95`, `lpg` (EU-27) | Weekly mirror. **CC BY 4.0**. |
| **1c. Pan-EU & Non-EU Bridge (`IS`, etc.)** | **`fuel-prices.eu`** | `GET https://www.fuel-prices.eu/board_now.php` `[CITED: fuel-prices.eu]` | JSON `{"ok": true, "ts": <unix_s>, "petrol": {"IS": 1.795, ...}, "diesel": {"IS": 1.820, ...}}` in **EUR/L** (tax-inclusive, 3 decimals). Server-side only (no CORS header). Covers live feeds (`AD`, `AT`, `DK`, `ES`, `FR`, `GB`, `GR`, `HR`, `IS`, `IT`, plus intermittent markets). | `diesel`, `petrol_95` | Live / 2-min cache. **CC BY 4.0** (credit `fuel-prices.eu`). |
| **2. UK Primary (`GB`)** | **UK DESNZ Weekly Road Fuel Prices** | Landing page: `https://www.gov.uk/government/statistical-data-sets/oil-and-petroleum-products-weekly-statistics` `[CITED: gov.uk]`. Dynamically discover CSV link (`Weekly road fuel prices` `.csv`) from `assets.publishing.service.gov.uk`. | CSV with columns `Date` (`DD/MM/YYYY` or ISO), `ULSP ... Pump price in pence/litre`, `ULSD ... Pump price in pence/litre`. **CRITICAL UNIT:** Reported in **pence/litre** (e.g., `142.9` -> `1.429 GBP/L` by `/100.0`, then `/ rate_GBP_per_EUR` for `eur_per_liter`). Take latest non-empty row. | `petrol_95` (`ULSP`), `diesel` (`ULSD`) | Weekly (Monday). **OGL v3.0**. |
| **3. Norway Primary (`NO`)** | **Norway SSB Table `09654`** | PxWebApi v2 GET: `https://data.ssb.no/api/pxwebapi/v2/tables/09654/data?lang=en&valueCodes[Tid]=top(3)` (inspect `/metadata?lang=en` or parse JSON-stat2 `dimension` labels dynamically so variable code renames never break parsing!) `[CITED: data.ssb.no]`. | JSON-stat2 (`dimension`, `id`, `size`, `value`). Match product labels containing `"95"` / `"gasoline"` / `"bensin"` -> `petrol_95` and `"diesel"` / `"autodiesel"` -> `diesel` (dutiable / `avgiftspliktig`), take latest non-null month (`YYYYM##`). Units: **`NOK/L`** (`eur_per_liter = nok / rate_NOK_per_EUR`). | `petrol_95`, `diesel` | Monthly (~10th of month). **CC BY 4.0 (NLOD)**. |
| **4. France Multi-Grade (`FR`)** | **France Ministère de l'Économie (OpenDataSoft v2.1)** | `GET https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records?select=avg(gazole_prix)%20as%20diesel,avg(sp95_prix)%20as%20petrol_95,avg(sp98_prix)%20as%20petrol_98,avg(e10_prix)%20as%20e10,avg(e85_prix)%20as%20e85,avg(gplc_prix)%20as%20lpg&limit=1` `[CITED: data.economie.gouv.fr]` | Single tiny JSON response (`{"total_count": 1, "results": [{"diesel": 1.68, "petrol_95": 1.79, "petrol_98": 1.88, "e10": 1.74, "e85": 0.89, "lpg": 0.99}]}`) in **EUR/L** directly (avoids downloading 20 MB instant XML with milli-EUR!). Prefer `sp95` if present else `e10` for `petrol_95`. | `diesel`, `petrol_95`, `petrol_98`, `e85`, `lpg` | Live / Hourly. **Licence Ouverte v2.0**. |
| **5. Germany Multi-Grade (`DE`, Optional Key)** | **Tankerkönig (MTS-K)** | `GET https://creativecommons.tankerkoenig.de/json/list.php?lat={lat}&lng={lng}&rad=15&sort=dist&type=all&apikey={TANKERKOENIG_API_KEY}` `[CITED: creativecommons.tankerkoenig.de]` | JSON `{"ok": true, "stations": [{"diesel": 1.659, "e5": 1.759, "e10": 1.699, "isOpen": true}, ...]}` in **EUR/L**. Only runs if `TANKERKOENIG_API_KEY` env var is non-empty (`D-03`). Query 5 deterministic German cities (`Berlin 52.52,13.405`, `Hamburg 53.551,9.994`, `Munich 48.135,11.582`, `Cologne 50.938,6.960`, `Frankfurt 50.111,8.682`), filter `isOpen` & `price > 0`, take `statistics.median` across collected open stations (`e5` -> `petrol_95`, `diesel` -> `diesel`). Check `ok == true` before parsing; if key unset or call fails, silently fall back to EC WOB (`DE`). | `diesel`, `petrol_95` (`e5`) | Live (5-min fair-use cap; CI runs 1x/week = 5 requests/week!). **CC BY 4.0**. |
| **6. Spain Multi-Grade (`ES`)** | **Spain MITECO REST API** | `GET https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/` with header `Accept: application/json` and explicit `User-Agent` `[CITED: sedeaplicaciones.minetur.gob.es]` | JSON `{"Fecha": "DD/MM/YYYY HH:MM:SS", "ListaEESSPrecio": [{...}]}` (~12,000 stations, ~20 MB gzipped). Exact string fields (comma decimal `"1,685"` -> replace `,` with `.`): `"Precio Gasoleo A"` -> `diesel`, `"Precio Gasoleo Premium"` -> `diesel_plus`, `"Precio Gasolina 95 E5"` -> `petrol_95`, `"Precio Gasolina 98 E5"` -> `petrol_98`, `"Precio Gases licuados del petróleo"` -> `lpg`. Aggregate via `statistics.median` over valid positive station prices (robust against outlier typo stations!). | `diesel`, `diesel_plus`, `petrol_95`, `petrol_98`, `lpg` | Live / Daily. Spanish Open Gov Data (`MITECO`). |
| **7. Italy Multi-Grade (`IT`)** | **Italy MIMIT Osservaprezzi CSV** | `GET https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv` `[CITED: mimit.gov.it]` | CSV (`~6–8 MB`). **CRITICAL QUIRK:** Line 1 is a timestamp banner (`Estrazione del YYYY-MM-DD HH:MM:SS`), Line 2 is the header (`idImpianto;descCarburante;prezzo;isSelf;dtComu` — detect `;` vs `,` delimiter dynamically!). Filter `isSelf == "1"` (self-service pump prices, matching EC WOB & standard totems). Normalize `descCarburante.strip().lower()`: `"benzina"` -> `petrol_95`, `"gasolio"` -> `diesel`, `"gpl"` -> `lpg`, `{"blue diesel", "hi-q diesel", "gasolio speciale", "gasolio special", "gasolio alpino", "gasolio plus", "diesel max", "diesel+", "excellium diesel", "supreme diesel"}` -> `diesel_plus`, `{"benzina speciale", "benzina special", "blu super", "v-power", "benzina 100 ottani", "hiq perform+"}` -> `petrol_98`. Aggregate via `statistics.median`. | `diesel`, `diesel_plus`, `petrol_95`, `petrol_98`, `lpg` | Daily (08:00 CET). **IODL 2.0**. |
| **8. Netherlands Multi-Grade (`NL`)** | **Netherlands CBS StatLine OData `80416ned`** | `GET https://opendata.cbs.nl/ODataApi/odata/80416ned/TypedDataSet?$orderby=Perioden%20desc&$top=5` `[CITED: opendata.cbs.nl]` | OData JSON `{"value": [{"Perioden": "2026JJ00" / "20261119", "BenzineEuro95_1": 1.985, "Diesel_2": 1.742, "Lpg_3": 0.895}, ...]}` in **EUR/L**. Filter rows whose `Perioden` matches daily pattern `^\d{8}$` (exclude annual `JJ00` / monthly `MM` summary rows if present!) and pick the latest row with non-null `BenzineEuro95_1` & `Diesel_2`. | `petrol_95`, `diesel`, `lpg` | Daily. **CC BY 4.0** (`CBS`). |

### 2.2 Merge Precedence for Multi-Grade Enrichment (`DAT-02`, `D-01`..`D-04`)

When merging multiple Tier 1 feeds for the same country:
1. **National Multi-Grade Feeds (`FR`, `DE` when keyed, `ES`, `IT`, `NL`)** overwrite/enrich `EC Weekly Oil Bulletin` for their published grades (so `FR`/`ES`/`IT`/`NL`/`DE` get daily live multi-grade prices including `diesel_plus`, `petrol_98`, `e85`, `lpg`). If a national feed fails or returns partial grades, `EC Weekly Oil Bulletin` (`diesel`, `petrol_95`, `lpg`) cleanly covers the missing grades without outage!
2. **`UK DESNZ`** is primary for `GB` (fallback: `fuel-prices.eu` `GB`).
3. **`Norway SSB 09654`** is primary for `NO` (note: SSB updates monthly; if `fuel-prices.eu` exposes live `NO`, cross-check or keep SSB as official `CC BY 4.0` primary anchor per `D-02`, falling back to `fuel-prices.eu` if SSB fails).
4. **Non-EU Vanilla Countries (`AL`, `BA`, `CH`, `IS`, `ME`, `MK`, `RS`, `RU`, `TR`, `XK` — 10 countries, per `D-01`):**
   - Check `fuel-prices.eu` (`board_now.php`) first: `IS` (Iceland) is actively covered live (`petrol` + `diesel` in EUR/L), and any other non-EU country returned in `board_now.php` (e.g., `CH` when active) is ingested automatically!
   - For the remaining uncovered non-EU vanilla countries (`AL`, `BA`, `CH` if absent, `ME`, `MK`, `RS`, `RU`, `TR`, `XK`), seed `eur_per_liter` (diesel) cleanly from `data/baselines/ets2_1.62_def/countries.json` (`fuel_price`), derive `petrol_95` from verified `1.62` `diesel/petrol` ratio (or `0.95` fallback), convert to local currency via live Phase 3 FX (`DAT-01`), and mark `source: "baseline_1.62_seeded"`, `fallback_used: true` so Phase 5 Tier 2/3 collectors can replace them seamlessly.

### 2.3 Verified Secondary-Grade Spread Ratios (`D-02`)

Cross-checking European retail market benchmarks (`EC WOB`, `TCS`, `Cargopedia`) `[CITED: tcs.ch, cargopedia.net]` against the empirical medians directly observed in ETS2 `1.62.3.3s` `locale/fuel_price_strings.sui` (`98/95` median `1.050` across 17 countries, `100/95` median `1.050–1.100`, `d+/d` median `1.051–1.099`, `mpo/d` = `0.800`, `e85/95` = `0.72–0.90`, `92/95` = `0.967`) `[VERIFIED: locale.scs:/locale/fuel_price_strings.sui]`, lock the following deterministic spread table for computing any grade not directly published by a Tier 1 feed:

| Canonical Grade | Anchor Grade | Multiplier | Basis |
|-----------------|--------------|------------|-------|
| `petrol_98` | `petrol_95` | `1.06` | Real EU 98-vs-95 premium (`+5%` to `+10%`; ETS2 `1.62` 17-country median `1.050`, D-02 `1.06`). |
| `petrol_100` | `petrol_95` | `1.12` | Real EU 100-octane racing/premium (`+10%` to `+15%`; D-02 `1.12`). |
| `diesel_plus` | `diesel` | `1.07` | Real EU premium diesel (`+5%` to `+12%`; ETS2 `1.62` `BA` `1.051` / `IT` `1.099`, D-02 `1.07`). |
| `petrol_92` | `petrol_95` | `0.96` | Real RU/DK 92-vs-95 discount (`-3%` to `-5%`; ETS2 `1.62` `DK` `0.967`, D-02 `0.96`). |
| `e85` | `petrol_95` | `0.72` | Real FR/SE bioethanol tax-advantaged discount (`~0.65–0.80` of 95; D-02 `0.72`). |
| `mpo` | `diesel` | `0.75` | Finnish light fuel oil (*Moottoripolttoöljy* / red agricultural diesel, `~0.75–0.80` of road diesel; D-02 `0.75`). |
| `lpg` | `petrol_95` | `0.48` | Real EU Autogas discount (`0.45–0.55` of 95; D-02 `0.48`, used only when EC WOB & national APIs omit `lpg`). |

> **Ordering Invariant:** Always populate live grades first (`EC WOB` `diesel`/`petrol_95`/`lpg` + national multi-grade overrides), and ONLY fill missing grades from the spread table above. Ensure `local_prices` stores **every canonical grade required by any board for that country** (and always at least `diesel` and `petrol_95`).

---

## Deliverable 3: ETS2 `1.62` Totem Forensics, Font Metrics & Complete 461-Board Classification (`TOT-01`, `TOT-02`, `D-09`..`D-12`)

### 3.1 Critical Baseline Gap Discovered in `def.scs` vs `fuel_boards.json`

Direct inspection of raw ETS2 `1.62.3.3s` `def.scs:/def/sign/board/*.sii` across all `461` boards revealed the exact canonical SII schema `[VERIFIED: def.scs:/def/sign/board/*.sii]`:

```text
SiiNunit
{
sign_board_template : _nameless.2.2a34.f3e0 {
 board_name: "gas de big diesel"
 width: &3fc00000
 height: &3f2b851f
 model_name: ""
 items: 1
 items[0]: _nameless.2.1160.beb0
 dynamic_attributes: 0
}

sign_template_text : _nameless.2.1160.beb0 {
 text: "@@fp_de_diesel_ets2v2@@"
 font_face: "/font/sign/gas_roadgeek_2005_mittelschrift.font"
 font_size: &3eb33333
 text_halign: center
 text_valign: center
 font_color: 200
 font_opacity: 1
 line_spacing: &3e4ccccd
 letter_spacing: 0
 id: 2435448831
 area_name: ""
 area_idx: nil
 coords_l: &3dd04570
 coords_r: &3fa1a08b
 coords_t: &3f0b9214
 coords_b: &3de4c050
 z_order: 1
 tag: ""
}

}
```

**Audit across ALL 461 boards in `def.scs` confirmed the exact closed set of attributes:**
- `sign_board_template` (6 attributes): `board_name` (str), `width` (float), `height` (float), `model_name` (`""`), `items` (`1` + `items[0]`), `dynamic_attributes` (`0`).
- `sign_template_text` (18 attributes): `text` (str), `font_face` (str), `font_size` (float), `text_halign` (`center` | `left` | `right`), `text_valign` (`center` | `bottom`), `font_color` (int | `nil` — e.g., `200`, `46330`, `65280`, `16777215`, `nil`), `font_opacity` (`0` | `1`), `line_spacing` (float), `letter_spacing` (float), `id` (uint32), `area_name` (`""`), `area_idx` (`nil`), `coords_l` (float), `coords_r` (float), `coords_t` (float), `coords_b` (float), `z_order` (`1`), `tag` (`""`).
- **Unit name segment compliance:** Verified across all `461` boards — **0** segments exceed 12 chars (`_nameless.x.xxxx.xxxx` has max segment length `9` `[VERIFIED: data/baselines/ets2_1.62_def/fuel_boards.json]`). Preserving the baseline `unit_name` and `slot.unit_name` guarantees 100% SCS unit-name compliance!
- **Required Phase 3 Plan 03-03 prerequisite:** Extend `SignBoardTemplate` & `SignTemplateTextSlot` (`src/ets2v2/sii/sign_board.py:16-156`) and `FuelBoardEntry` & `FuelBoardSlot` (`src/ets2v2/baseline/models.py:100-131`, `extractor.py:326-349`) to parse and persist these exact attributes (keeping `board_size` / `h_align` / `v_align` cleanly replaced or populated from `width`/`height`/`text_halign`/`text_valign` so all existing tests stay green), then re-run `uv run ets2v2 baseline extract` to update `data/baselines/ets2_1.62_def/fuel_boards.json` + `manifest.json` SHA-256s. **Clean-room rule preserved:** still 100% structured JSON metadata, zero raw `.sii` files under `data/`.

### 3.2 Exact `.font` Glyph Tables & Width Physics (All 6 Gas Fonts Verified from `base.scs`)

Direct inspection of `base.scs:/font/sign/gas_*.font` `[VERIFIED: base.scs]` confirmed all 6 gas fonts are **ETS2 `1.43+` SDF fonts** supporting runtime `<sup>` scaling, containing **ONLY digits `0–9`, space `' '`, comma `','`, dot `'.'`** (plus `'-'` in `gas_sign_digit.font`) — **zero letters or currency symbols**:

| Font File (`/font/sign/...`) | Boards | Type | `vert_span` | `scale_x` | Digit Adv | Dot Adv | `digit_w / fs` | `dot_w / fs` | Width `"1.79"` | Width `"1.78<sup>9</sup>"` | Width `"1.789"` |
|------------------------------|--------|------|-------------|-----------|-----------|---------|----------------|--------------|----------------|----------------------------|-----------------|
| `gas_karnivore_lite.font` | `213` | Proportional SDF | `28.586` | `0.9584` | `17.216` | `5.985` | `0.577` | `0.201` | `1.932·fs` | `2.307·fs` | `2.510·fs` |
| `gas_roadgeek_2005_mittelschrift.font` | `100` | Proportional SDF | `27.385` | `0.9231` | `16.380` | `8.814` | `0.552` | `0.297` | `1.954·fs` | `2.312·fs` | `2.506·fs` |
| `gas_segment_7_standard.font` | `61` | **Monospace 7-Seg SDF** | `29.429` | `0.5143` | `40.950` | `40.950` | `0.716` | `0.716` | `2.863·fs` | `3.328·fs` | `3.578·fs` |
| `gas_ds_digib.font` | `53` | Narrow-dot 7-Seg SDF | `26.772` | `0.4334` | `37.672` | `10.337` | `0.610` | `0.167` | `1.997·fs` | `2.393·fs` | `2.607·fs` |
| `gas_sign_digit.font` | `24` | **Monospace LED SDF** | `28.000` | `0.4444` | `36.818` | `36.818` | `0.584` | `0.584` | `2.338·fs` | `2.718·fs` | `2.922·fs` |
| `gas_fundamental_brigade_schwer.font` | `10` | Proportional SDF | `27.601` | `0.9576` | `20.301` | `6.353` | `0.704` | `0.220` | `2.333·fs` | `2.791·fs` | `3.038·fs` |

*Formula for rendered text width in board metres:*
$$W(\text{text}) = \left(n_{\text{digits}} \cdot d_w + n_{\text{sup}} \cdot 0.65 \cdot d_w + n_{\text{dots}} \cdot p_w\right) \cdot \text{font\_size} + (N_{\text{chars}} - 1) \cdot \text{letter\_spacing}$$
A string fits cleanly when $W(\text{text}) \le (\text{coords\_r} - \text{coords\_l}) \times 1.03$.

### 3.3 Exhaustive Classification of All 461 Single-Text Boards (`D-09`)

#### Summary Breakdown (`461` total in `data/baselines/ets2_1.62_def/fuel_boards.json`)
- **`373` `active_fp`** -> **ALL `373` rewritten** to `@@fp_<cc>_<grade>[_<variant>]_ets2v2@@` (fixing `6` keys missing from vanilla `locale.scs` + `13` name/token anomalies!).
- **`47` `placeholder`** -> **ALL `47` rewritten** (100% identifiable fuel boards; all have `font_opacity == 1.0` and valid `font_size > 0`).
- **`41` `blank`** -> **`40` rewritten** (all 40 have `font_opacity == 1.0` and valid `font_size > 0`!) + **`1` untouched structural spacer** (`gas_empty`, the **only** board in all `461` with `font_size == 0` and `font_opacity == 0`!).
- **`5` excluded multi-item highway signs** (`fi_oulu_95`, `fi_oulu_98`, `rs_fuel_01`, `ru_m_95`, `ru_m_98`) -> **untouched**.
- **Total emitted `def/sign/board/*.sii` files:** **`460`** across **`37` countries** (`36` Vanilla+DLC + `IE`), referencing **`164` unique tokens** in `locale/<lang>/local_module.ets2v2_fuel.sii`.

#### Deterministic Board-Name Classification Ruleset
1. Exclude structural spacer: `board_name == "gas_empty"` -> **SKIP** (do not emit).
2. Non-`gas_` legacy boards: `es_95_01` -> `(ES, petrol_95)`, `es_diesel_01` -> `(ES, diesel)`, `pt_95_01` -> `(PT, petrol_95)`, `pt_diesel_01` -> `(PT, diesel)`.
3. Standard `gas_<region>_<...>_<grade_suffix>` boards:
   - Region alias map: `"bi" -> "GB"` (British Isles rework), `"dortmund" -> "DE"`, all other 2-letter tokens -> `token.upper()` (yields exact ISO-2 across all 37 countries; note SCS typo `gas_no_tgq_98` still starts with `gas_no_` -> `NO`!).
   - Grade suffix map (`tokens[-1]`):
     - `"diesel"` -> `"diesel"`
     - `"95"`, `"unleaded"` -> `"petrol_95"`
     - `"98"`, `"97"`, `"super"` -> `"petrol_98"` *(Turkish `97` boards map to `petrol_98` just like vanilla `fp_tr_natural98`)*
     - `"100"` -> `"petrol_100"`
     - `"92"` -> `"petrol_92"`
     - `"85"`, `"e85"` -> `"e85"`
     - `"lpg"` -> `"lpg"`
     - `"mpo"` -> `"mpo"`
     - `"diesel5"`, `"dieselplus"`, `"superdiesel"`, `"superd"` -> `"diesel_plus"`

#### All 6 Vanilla `active_fp` Keys Missing from `1.62` `locale.scs` (Fixed by Phase 3)
1. `gas_hr_gryf_98` (vanilla `@@fp_hr_natural98@@` — missing in `locale.scs`!) -> `@@fp_hr_petrol_98_c_ets2v2@@`
2. `gas_lu_bnlx_98` (vanilla `@@fp_lu_natural98@@` — missing in `locale.scs`!) -> `@@fp_lu_petrol_98_ets2v2@@`
3. `gas_ie_pegi_95` (vanilla `@@fp_ie_natural95@@` — missing in `locale.scs`!) -> `@@fp_ie_petrol_95_ets2v2@@`
4. `gas_ie_pegi_diesel` (vanilla `@@fp_ie_diesel@@` — missing in `locale.scs`!) -> `@@fp_ie_diesel_ets2v2@@`
5. `gas_ie_primel_95` (vanilla `@@fp_ie_natural95@@` — missing in `locale.scs`!) -> `@@fp_ie_petrol_95_ets2v2@@`
6. `gas_ie_primel_diesel` (vanilla `@@fp_ie_diesel@@` — missing in `locale.scs`!) -> `@@fp_ie_diesel_ets2v2@@`

#### Vanilla `1.62` Name-vs-Token Bugs Fixed by Board-Name Classification
- `gas_is_yokull_95` (vanilla had `@@fp_is_diesel@@`!) -> **`(IS, petrol_95)`**
- `gas_is_yokull_diesel` (vanilla had `@@fp_is_natural95@@`!) -> **`(IS, diesel)`**
- `gas_ba_apus_lpg`, `gas_ba_bts_lpg` (vanilla had `@@fp_ba_diesel5@@`!) -> **`(BA, lpg)`** *(D-09 explicitly requires `gas_ba_*_lpg` populated with LPG!)*
- `gas_hr_bts_98` (vanilla had `@@fp_hr_natural100@@`) -> **`(HR, petrol_98)`**
- `gas_nl_gryf_98` (vanilla had `@@fp_nl_natural100@@`) -> **`(NL, petrol_98)`**
- `gas_is_ip1_98` (blanked in `3249064596`) -> **`(IS, petrol_98)`**

#### Complete Table of All `47` Placeholder Boards -> `(ISO2, Canonical Grade)`
| Board Name(s) | Count | Vanilla Text | Mapped `(ISO2, Grade)` |
|---------------|-------|--------------|------------------------|
| `gas_be_primel_98`, `gas_be_primel_100` | 2 | `00.00` | `(BE, petrol_98)`, `(BE, petrol_100)` |
| `gas_bi_beldon_super`, `gas_bi_beldon_superd` | 2 | `0.000` | `(GB, petrol_98)`, `(GB, diesel_plus)` |
| `gas_bi_pegi_98`, `gas_bi_pegi_100` | 2 | `00.00` | `(GB, petrol_98)`, `(GB, petrol_100)` |
| `gas_bi_primel_98`, `gas_bi_primel_100` | 2 | `00.00` | `(GB, petrol_98)`, `(GB, petrol_100)` |
| `gas_bi_sheltie_super`, `gas_bi_sheltie_superd` | 2 | `0.000` | `(GB, petrol_98)`, `(GB, diesel_plus)` |
| `gas_bi_victory_super`, `gas_bi_victory_superd` | 2 | `0.000` | `(GB, petrol_98)`, `(GB, diesel_plus)` |
| `gas_dk_primel_98`, `gas_dk_primel_100`, `gas_dk_primel_s_98`, `gas_dk_primel_s_100` | 4 | `00.00` | `(DK, petrol_98)`, `(DK, petrol_100)` |
| `gas_dk_tqg_85`, `gas_dk_tqg_98` | 2 | `00.00` | `(DK, e85)`, `(DK, petrol_98)` |
| `gas_dortmund_98`, `gas_dortmund_lpg` | 2 | `0.00` | `(DE, petrol_98)`, `(DE, lpg)` |
| `gas_fi_primel_mpo`, `gas_fi_primel_s_mpo`, `gas_fi_tqg_85` | 3 | `0.000` | `(FI, mpo)`, `(FI, e85)` |
| `gas_ie_cloveroil_{95,diesel,super,superd}` | 4 | `123.9` | `(IE, petrol_95/diesel/petrol_98/diesel_plus)` |
| `gas_ie_opetrol_{95,diesel,super,superd}` | 4 | `123.9` | `(IE, petrol_95/diesel/petrol_98/diesel_plus)` |
| `gas_ie_pegi_{98,100}`, `gas_ie_primel_{98,100}` | 4 | `00.00` | `(IE, petrol_98/petrol_100)` |
| `gas_is_skanfill_95`, `gas_is_skanfill_diesel` | 2 | `@@000.0@@`, `000.0` | `(IS, petrol_95)`, `(IS, diesel)` |
| `gas_lu_primel_{98,100}`, `gas_nl_primel_{98,100}` | 4 | `00.00` | `(LU/NL, petrol_98/petrol_100)` |
| `gas_no_primel_{98,100}`, `gas_no_primel_s_{98,100}`, `gas_no_tgq_98`, `gas_no_tqg_85` | 6 | `00.00` | `(NO, petrol_98/petrol_100/e85)` |

#### Complete Table of All `41` Blank Boards -> `(ISO2, Canonical Grade)` or Untouched Spacer
| Board Name(s) | Count | Mapped `(ISO2, Grade)` / Action |
|---------------|-------|---------------------------------|
| `gas_empty` | **1** | **UNTOUCHED STRUCTURAL SPACER** (`font_size: 0, font_opacity: 0`) |
| `gas_al_{apus,bts,gryf,nada}_{98,lpg}` | 8 | `(AL, petrol_98)` / `(AL, lpg)` |
| `gas_bg_{gryf,primel}_superdiesel` | 2 | `(BG, diesel_plus)` |
| `gas_ch_{gryf,pegi,pegi_s}_{98,lpg}` | 6 | `(CH, petrol_98)` / `(CH, lpg)` |
| `gas_de_{gryf,pegi,pegi_s}_{98,lpg}` | 6 | `(DE, petrol_98)` / `(DE, lpg)` |
| `gas_fr_pegi_s_lpg` | 1 | `(FR, lpg)` |
| `gas_hr_{apus,bts,nada}_lpg` | 3 | `(HR, lpg)` |
| `gas_me_{apus,gryf}_lpg` | 2 | `(ME, lpg)` |
| `gas_mk_{apus,bts}_lpg` | 2 | `(MK, lpg)` |
| `gas_rs_{apus,bts,nada,pegi,pegi_s}_lpg` | 5 | `(RS, lpg)` |
| `gas_si_nada_lpg` | 1 | `(SI, lpg)` |
| `gas_tr_{pegi,pegi_s}_dieselplus`, `gas_tr_primel_superdiesel` | 3 | `(TR, diesel_plus)` |
| `gas_xk_nada_lpg` | 1 | `(XK, lpg)` |

### 3.4 Native-Currency Totem Formatting Rules & Width-Budget Routing (`D-10`, `D-11`)

All formatting uses **dot (`.`) decimal separator** (`D-11`) and `Decimal(..., rounding=ROUND_HALF_UP)` with zero currency symbols:

| Country Group | Currencies | Standard Format (`fp_<cc>_<grade>_ets2v2`) | 7-Seg Wide Format (`_3_ets2v2`) | Narrow Fallback (`_c_ets2v2`) | Verified Fit Across All Boards |
|---------------|------------|-------------------------------------------|---------------------------------|-------------------------------|--------------------------------|
| **Eurozone Tenth-Cent (`17` countries):** `AT`, `BE`, `DE`, `EE`, `ES`, `FR`, `HR`, `IE`, `IT`, `LT`, `LU`, `LV`, `ME`, `NL`, `PT`, `SK`, `XK` | `EUR` | `1.78<sup>9</sup>` (`f"{whole}.{cents:02d}<sup>{tenth}</sup>"` from 3-decimal EUR) on wide non-7-seg boards (`136` boards) | `1.789` (`f"{val:.3f}"`) on `12` wide 7-seg boards (`es_*`, `pt_*`, `gas_at_enz_*`, `gas_de_enz_*`, `gas_ie_cloveroil_*`) | `1.79` (`f"{val:.2f}"`) on `40` narrow/tight boards (`gas_*_small_*`, `gas_de_gob_*`, `gas_dortmund_*`, `gas_fr_eco_*`, `gas_hr_gryf_*`, `gas_it_*`, `gas_lu_big_*`, `gas_sk_big_*`) | **188 / 188 (100%)** |
| **Eurozone Native 3-Decimal (`3` countries):** `FI`, `GR`, `SI` | `EUR` | `1.789` (`f"{val:.3f}"`, matches `1.62` `fuel_price_strings.sui`) | — | — | **54 / 54 (100%)** |
| **Bulgaria (`BG`, post-2026 EUR)** | `EUR` | `1.34` (`f"{val:.2f}"`, per `D-10`) | — | — | **14 / 14 (100%)** |
| **United Kingdom (`GB`)** | `GBP` (pence) | `142.9` (`f"{gbp * 100:.1f}"`, per `D-10`) | — | — | **24 / 24 (100%)** |
| **High-Unit Integer (`4` countries):** `AL`, `HU`, `IS`, `RS` | `ALL`, `HUF`, `ISK`, `RSD` | `185`, `615`, `312`, `198` (`f"{round(val):.0f}"`, per `D-10`) | — | — | **47 / 47 (100%)** |
| **Czechia (`CZ`)** | `CZK` | `38.90` (`f"{round(val, 1):.2f}"`, always ends `.X0` per SCS comment `[VERIFIED: locale.scs]`) | — | — | **4 / 4 (100%)** |
| **Romania (`RO`)** | `RON` | `7.45` if `< 10` else `10.1` (`X.XX` / `XX.X`, max 4 chars per SCS comment & `gas_ds_digib` width `[VERIFIED: locale.scs]`) | — | — | **6 / 6 (100%)** |
| **North Macedonia (`MK`)** | `MKD` | `79.50` if `< 100` else `103.4` (`XX.XX` / `XXX.X`, max 5 chars per SCS comment `[VERIFIED: locale.scs]`) | — | — | **8 / 8 (100%)** |
| **2-Decimal National (`8` countries):** `BA`, `CH`, `DK`, `NO`, `PL`, `RU`, `SE`, `TR` | `BAM`, `CHF`, `DKK`, `NOK`, `PLN`, `RUB`, `SEK`, `TRY` | `2.65`, `1.89`, `14.29`, `22.45`, `6.49`, `68.50`, `18.95`, `44.50` (`f"{val:.2f}"`) | — | — | **115 / 115 (100%)** |

*(Note: `CY` and `MT` are in `state/prices.lock.json` as EUR territories but have `0` vanilla `1.62` sign boards; they will feed Phase 4 ProMods `pm_fuel` automatically.)*

### 3.5 `locale/<lang>/local_module.ets2v2_fuel.sii` Format & SCS Unit Rules

Per SCS Modding Wiki (`units.md`) and ETS2 `1.62` `locale.scs` `[VERIFIED: locale.scs:/locale/en_gb/local.sii + src/ets2v2/sii/hygiene.py:71-115]`:
- Emitted at `locale/<lang>/local_module.ets2v2_fuel.sii` for **all 43** `active_locales` in `data/baselines/ets2_1.62_def/locales.json` (`bg_bg` .. `zh_tw`, including `fr_ca`, excluding dead `fr_qc`).
- Unit header: **`localization_db : .ets2v2_fuel`** (`ets2v2_fuel` is **11 chars** `<= 12`, strictly matching `[a-z0-9_]{1,12}`!). Note: `.localization` (12 chars) is also valid, but `.ets2v2_fuel` avoids any ambiguity and stays strictly unique per module!
- Entries: identical sorted `key[]` / `val[]` pairs (`164` pairs) across all 43 locale files, UTF-8 no-BOM, LF endings, validated by `validate_sii_hygiene(..., require_siinunit=True)` and `parse_localization_db()`.

```text
SiiNunit
{
localization_db : .ets2v2_fuel
{
	key[]: "fp_al_diesel_ets2v2"
	val[]: "185"
...
}
}
```

---

## Deliverable 4: Lockfile Schema, Snapshot v1 Compatibility & Integration Architecture (`D-05`, `D-06`, `D-08`, `D-13`..`D-16`)

### 4.1 Exact `state/prices.lock.json` (`schema_version: 1`) Schema

All models use `ConfigDict(strict=True, frozen=True, extra="forbid")` and serialize with `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`:

```python
CanonicalFuelGrade = Literal[
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

class FxRateLockEntry(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    rate_per_eur: float = Field(gt=0.0, allow_inf_nan=False)
    provider: str = Field(min_length=1)                  # e.g. "frankfurter_v2" | "pinned_eur" | "cbbh_peg"
    validator_provider: str | None = None                # e.g. "ecb_xml" | "cbr_xml" | "fawazahmed0"
    validator_rate_per_eur: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)
    divergence_pct: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    data_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    fetched_at: str = Field(min_length=1)                # ISO-8601 UTC timestamp
    fallback_used: bool = False

class CountryFuelLockEntry(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    eur_per_liter: float = Field(ge=0.01, le=5.00, allow_inf_nan=False)  # 3-decimal diesel (D-15)
    local_prices: dict[CanonicalFuelGrade, float]        # numeric native currency/L (GBP for GB, NOT pence!)
    derived_grades: list[CanonicalFuelGrade] = Field(default_factory=list)  # grades filled via D-02 spreads
    source: str = Field(min_length=1)                    # e.g. "ec_wob", "uk_desnz", "fr_economie", "baseline_1.62_seeded"
    license: str = Field(min_length=1)                   # e.g. "CC BY 4.0", "OGL v3.0", "Licence Ouverte v2.0"
    data_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    fetched_at: str = Field(min_length=1)
    fallback_used: bool = False

class LockAlert(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    severity: Literal["warning", "error"]
    code: str = Field(min_length=1)                      # e.g. "price_jump_rejected", "price_bounds_rejected", "fx_divergence_warning", "stale_tier1", "stale_fallback", "feed_outage"
    scope: str = Field(min_length=1)                     # ISO2 or currency code or feed name
    detail: str = Field(min_length=1)

class PricesLockfile(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    schema_version: Literal[1] = 1
    updated_at: str = Field(min_length=1)
    fx_rates: dict[str, FxRateLockEntry]                 # keyed by ISO-4217 ("ALL".."TRY", incl. "EUR")
    countries: dict[str, CountryFuelLockEntry]           # exact 39 European ISO-2 keys (36 Vanilla + IE, CY, MT)
    alerts: list[LockAlert] = Field(default_factory=list)
```

> **Clean `local_prices` Numeric Convention (`D-13`, `D-14`):** Store **standard native-currency per litre** as `float` in `local_prices` (e.g., `GB`: `1.429` GBP/L, `DE`: `1.789` EUR/L, `HU`: `615.0` HUF/L, `NO`: `22.45` NOK/L) — this matches `RealismSnapshotFuel.local_prices: dict[str, float]` `[VERIFIED: src/ets2v2/registry/snapshot.py:36]` with **zero schema bump** (`D-13`) and keeps downstream Phase 4 ProMods (`pm_fuel`, which needs pounds AND pence) cleanly decoupled! Display formatting (pence `×100` for UK totems, `<sup>9</sup>` for wide Eurozone totems, integers for HUF/ISK/ALL/RSD) happens deterministically at totem build time in `package/totems.py`!

### 4.2 Recommended Subpackage Layout & Existing Integration Points

```text
src/ets2v2/
├── fetch/                         # NEW (online-only HTTP collectors; unlocked in test_cli_scaffold.py)
│   ├── __init__.py
│   ├── http.py                    # Shared httpx.Client builder, User-Agent, retry/backoff, byte caps
│   ├── fx.py                      # Frankfurter v2, ECB XML, fawazahmed0 (jsDelivr+Pages), CBR XML
│   ├── ec_wob.py                  # EC Weekly Oil Bulletin dynamic XLSX + FionnHughes CSV + fuel-prices.eu
│   └── national.py                # UK DESNZ, NO SSB 09654, FR ODS v2.1, DE Tankerkönig (opt), ES MITECO, IT MIMIT, NL CBS
├── normalize/                     # NEW (pure deterministic offline validation, spreads & lockfile)
│   ├── __init__.py
│   ├── currencies.py              # 39-territory currency table, ECB/volatile tiers, BAM peg, sanity bands
│   ├── fx.py                      # Tiered 2%/5%/10% cross-validator & currency-split guard (DAT-01)
│   ├── spreads.py                 # Canonical grade spread calculator & non-EU baseline seeding (D-01, D-02)
│   └── lockfile.py                # PricesLockfile Pydantic models, circuit breaker (±25%, 0.01–5.00), staleness (14d/30d), I/O
├── package/
│   ├── totems.py                  # NEW: 460-board classifier, .font width-budget engine, 43-locale + board SII synthesizer
│   ├── builder.py                 # EXTEND: optional prices_lock_path -> pass to build_realism_snapshot + emit 460 boards & 43 locales
│   ├── metadata.py                # EXTEND: open-data attribution block in description.txt (D-16)
│   └── synthesize.py              # EXTEND: format 3-decimal fuel_price cleanly (D-15)
├── registry/
│   └── snapshot.py                # EXTEND: optional PricesLockfile injection into build_realism_snapshot() (schema_version=1 unchanged!)
├── sii/
│   └── sign_board.py              # EXTEND: parse full sign_board_template (6 attrs) + sign_template_text (18 attrs)
├── baseline/
│   ├── models.py                  # EXTEND: FuelBoardEntry & FuelBoardSlot rendering fields
│   └── extractor.py               # EXTEND: extract full sign board rendering fields into fuel_boards.json
├── validate/
│   ├── workshop.py                # EXTEND: reject .dds/.tobj (Zero-DDS!), parse def/sign/board/*.sii & locale/*/local_module.ets2v2_fuel.sii
│   └── invariants.py              # EXTEND: validate_totem_invariants() (43 locales, identical keys, 460 boards, zero dangling/orphan tokens, baseline attr preservation)
├── publish/
│   ├── changelog.py               # EXTEND: 36-country fuel table, Circuit-Breaker & Staleness Alerts section, open-data attributions (D-16)
│   └── release.py                 # EXTEND: accept prices_lock_path, load PricesLockfile offline, pass to build_core_edition & render_edition_changelog
└── cli.py                         # EXTEND: add `ets2v2 fetch` (`--lock-path`, `--allow-jump`, `--fx-only`, `--json`, `--timeout`), wire `--prices-lock` on `registry snapshot`, `package build`, `publish release`
```

### 4.3 Validator Extensions (`D-12` Hard Failures)

In `src/ets2v2/validate/workshop.py` and `src/ets2v2/validate/invariants.py`:
1. **Zero-DDS Guarantee:** Immediately emit error `ETS2V2-INV-ZERO-DDS` (or `00003`) if ANY entry inside the package ends with `.dds` or `.tobj`! (Currently `.dds` and `.tobj` are in `ALLOWED_SCS_ASSET_EXTENSIONS` `[VERIFIED: src/ets2v2/validate/workshop.py:82-83]`; add an explicit Zero-DDS check before/after extension dispatch.)
2. **Exact 43-Locale Sync (`ETS2V2-INV-TOTEM-LOCALE`):**
   - Collect all `locale/<lang>/local_module.ets2v2_fuel.sii` files.
   - Verify exact set equality against `baseline_locales.active_locales` (`43` locales, `fr_ca` present, `fr_qc` absent).
   - Verify every file passes `validate_sii_hygiene(..., require_siinunit=True)` and `parse_localization_db()`.
   - Verify every key matches `^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$`, has no duplicates, has non-empty value containing only allowed glyphs (`[0-9.]` and optional `<sup>[0-9]</sup>` — zero letters/currency symbols/commas!), and all 43 locale files have **byte-identical** sorted `(key, val)` pairs.
3. **Board-to-Token Integrity (`ETS2V2-INV-TOTEM-BOARD`):**
   - Parse every emitted `def/sign/board/*.sii` via `parse_sign_board()`.
   - Verify exact `460` identifiable boards emitted (`gas_empty` and the `5` excluded highway signs NOT emitted).
   - Verify baseline `model_name == ""`, `font_face`, `coords_l/r/t/b`, `width`, `height`, `font_size`, `font_color`, `font_opacity == 1.0`, `text_halign`, `text_valign` match `fuel_boards.json`.
   - Verify every board's `slot.localization_key` resolves in `local_module.ets2v2_fuel.sii` (zero dangling tokens) AND every key in `local_module.ets2v2_fuel.sii` is referenced by at least one emitted board (zero orphan tokens).

### 4.4 Friday CI Workflow Wiring (`.github/workflows/phase-a-release.yml`, `D-05`, `D-08`, `D-16`)

1. Keep existing offline quality gates (`ruff`, `basedpyright`, `pytest` — all `--offline`!).
2. Add online fetch step **before** `publish release`:
   ```yaml
   - name: Fetch live European fuel prices and FX rates
     env:
       TANKERKOENIG_API_KEY: ${{ secrets.TANKERKOENIG_API_KEY }}
     run: |
       set -euo pipefail
       uv run --offline ets2v2 fetch --lock-path state/prices.lock.json --json > dist/fetch_summary.json
   ```
   *(Note: `uv run --offline` keeps `uv` from re-resolving packages while allowing the Python script itself to make outbound HTTP requests!)*
   - On total Tier 1 fuel outage (`0` live Tier 1 feeds reachable), `ets2v2 fetch` exits non-zero (`1`), failing the workflow loudly (`D-08`).
   - On partial outage, `ets2v2 fetch` retains lockfile entries, records `LockAlert` warnings, writes `state/prices.lock.json`, and exits `0`.
3. Pass `--prices-lock state/prices.lock.json` to `uv run --offline ets2v2 publish release`.
4. Stage `state/prices.lock.json` alongside `state/published.json`, `CHANGELOG_SUMMER.md`, and `CHANGELOG_WINTER.md` in the persistent Release PR (`release/phase-a-weekly`) and include any `LockAlert` summary lines in the PR body!

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OOXML `.xlsx` ZIP/XML parsing | Custom `zipfile` + XML parser for EC Weekly Oil Bulletin | `openpyxl` (`read_only=True, data_only=True`) | EC `.xlsx` workbooks have shared-string tables, date serial numbers, merged headers, and style indices that hand-rolled XML parsers mishandle. |
| HTTP connection pooling, TLS, redirects, timeouts, mock transports | Raw `urllib.request` / `http.client` | `httpx.Client` + `httpx.MockTransport` | `httpx` gives structured `Timeout`, automatic gzip/deflate, clean redirect limits, and zero-monkeypatch offline test transport mocking. |
| Banker's rounding (`round()`) for prices | Built-in `round(float, 2)` | `decimal.Decimal` with `ROUND_HALF_UP` | Avoids IEEE-754 binary float drift (`1.785` rounding inconsistently) and ensures deterministic `eur_per_liter` & totem string output across platforms. |
| SII file parsing / hygiene validation | Regexes for `def/sign/board/*.sii` or `local_module.*.sii` | Existing `ets2v2.sii.{document,hygiene,sign_board,localization}` | Already handles IEEE-754 `&xxxxxxxx` floats, BOM/CRLF checks, 12-char unit segments, and POSIX path hygiene. |

---

## Common Pitfalls

### Pitfall 1: Treating `Frankfurter v2` Like v1 JSON
- **What goes wrong:** Expecting `{"base": "EUR", "rates": {"GBP": 0.83}}` (Frankfurter v1 schema) crashes with `TypeError` / `ValidationError` on `/v2/rates?base=EUR`, which returns a **flat JSON list** `[{"date": "...", "base": "EUR", "quote": "GBP", "rate": 0.83}, ...]` `[CITED: frankfurter.dev]`.
- **How to avoid:** Parse `/v2/rates?base=EUR` as `list[dict]` mapping `row["quote"].upper() -> float(row["rate"])`, and enforce explicit Pydantic validation on every row.

### Pitfall 2: Silent Unit-Scaling Bugs (`EUR/1000L` & `Pence/L`)
- **What goes wrong:** EC Weekly Oil Bulletin reports **`EUR per 1,000 litres`** (e.g., `1642.50`), and UK DESNZ reports **`pence per litre`** (e.g., `142.9`). Forgetting `/1000` or `/100` corrupts `.sui` and totem prices by `100x–1000x`.
- **How to avoid:** Convert at the collector boundary (`ec_wob.py` divides by `1000.0`; `uk_desnz` divides by `100.0` into `GBP/L`), AND enforce the `0.01–5.00 EUR/L` hard circuit breaker (`D-06`) as defense-in-depth!

### Pitfall 3: EC `EL` vs ISO `GR` and CBR `windows-1251` Comma Decimals
- **What goes wrong:** Dropping Greece because EC uses Eurostat code `EL` instead of `GR`; or failing UTF-8 decoding / `float("90,3445")` on CBR XML.
- **How to avoid:** Explicitly map `{"EL": "GR", "UK": "GB"}` in EC/mirror parsers; decode CBR bytes with `raw.decode("windows-1251")` and replace `","` with `"."` before `float()`.

### Pitfall 4: Synthesizing `def/sign/board/*.sii` Without `font_size`, `font_color`, `width`, `height`, `text_halign`
- **What goes wrong:** Generating minimal `sign_board_template`/`sign_template_text` units from the Phase 1 `fuel_boards.json` loses LED colors (`200`, `46330`, `65280`, `16777215`), font sizes, and alignments — breaking in-game visual fidelity on every single station.
- **How to avoid:** Extend `sign_board.py` + `baseline/{models,extractor}.py` first in Plan 03-03 and re-run `ets2v2 baseline extract` so all 24 exact SCS attributes are preserved verbatim in `fuel_boards.json` and emitted cleanly.

### Pitfall 5: Totem Overflow on 40 Narrow Eurozone / 7-Segment Boards or Currency Symbols in Gas Fonts
- **What goes wrong:** Emitting `"1.789"` or `"1.78<sup>9</sup>"` onto narrow `gas_segment_7_standard.font` / `gas_sign_digit.font` boards (`gas_dortmund_*`, `gas_it_ini_*`, `gas_*_small_*`) clips horizontally; emitting `"€"` or `"p"` renders missing-glyph boxes because all 6 `.font` files contain ONLY `' '`, `','`, `'.'`, `'0'`–`'9'` (plus `'-'`).
- **How to avoid:** Enforce exact `.font` width-budget routing (`_ets2v2` vs `_3_ets2v2` vs `_c_ets2v2`) and assert regex `^[0-9]+(?:\.[0-9]+)?(?:<sup>[0-9]</sup>)?$` in the Offline SCS Validator (`D-12`).

### Pitfall 6: `MIMIT` Line-1 Timestamp Banner & `CBS 80416ned` Aggregate Rows
- **What goes wrong:** Parsing `prezzo_alle_8.csv` with `csv.DictReader` starting at line 1 reads `Estrazione del ...` as the header and drops all rows; reading `CBS 80416ned` without filtering `Perioden` to daily `^\d{8}$` rows can pick annual `2026JJ00` rows instead of the latest daily observation.
- **How to avoid:** Strip/skip the `Estrazione del` banner line in `MIMIT` and sniff `;` vs `,`; filter `CBS` `Perioden` strictly to `^\d{8}$` (`YYYYMMDD`).

### Pitfall 7: Mutating `RealismSnapshot` v1 Schema or Leaking Network I/O into Offline CI
- **What goes wrong:** Adding `fetched_at` or `alerts` to `RealismSnapshotFuel` violates `D-13` (`one-way` locked `schema_version: 1`, `extra="forbid"`); calling real HTTP endpoints inside `pytest` breaks `uv run --offline pytest` in `.github/workflows/ci.yml`.
- **How to avoid:** Keep all provenance/alerts in `state/prices.lock.json` (`D-13`), inject only `(currency, eur_per_liter, local_prices, source)` into `RealismSnapshotFuel`, and test every collector exclusively via `httpx.MockTransport` fixtures.

---

## Code Examples

### Example 1: Clean-Room `def/sign/board/*.sii` Synthesizer Pattern
```python
# Preserves all 6 sign_board_template and 18 sign_template_text attributes verbatim from baseline
# while rewriting ONLY text to @@fp_<cc>_<grade>[_<variant>]_ets2v2@@
lines = [
    "SiiNunit",
    "{",
    f"sign_board_template : {board.unit_name} {{",
    f" board_name: {format_sii_string(board.board_name)}",
    f" width: {_format_sii_float(board.width)}",
    f" height: {_format_sii_float(board.height)}",
    ' model_name: ""',
    " items: 1",
    f" items[0]: {slot.unit_name}",
    f" dynamic_attributes: {board.dynamic_attributes}",
    "}",
    "",
    f"sign_template_text : {slot.unit_name} {{",
    f" text: {format_sii_string(f'@@{token_key}@@')}",
    f" font_face: {format_sii_string(slot.font_face)}",
    f" font_size: {_format_sii_float(slot.font_size)}",
    f" text_halign: {slot.text_halign}",
    f" text_valign: {slot.text_valign}",
    f" font_color: {'nil' if slot.font_color is None else slot.font_color}",
    f" font_opacity: {_format_sii_float(slot.font_opacity)}",
    f" line_spacing: {_format_sii_float(slot.line_spacing)}",
    f" letter_spacing: {_format_sii_float(slot.letter_spacing)}",
    f" id: {slot.text_id}",
    f" area_name: {format_sii_string(slot.area_name)}",
    f" area_idx: {'nil' if slot.area_idx is None else slot.area_idx}",
    f" coords_l: {_format_sii_float(slot.coords_l)}",
    f" coords_r: {_format_sii_float(slot.coords_r)}",
    f" coords_t: {_format_sii_float(slot.coords_t)}",
    f" coords_b: {_format_sii_float(slot.coords_b)}",
    f" z_order: {slot.z_order}",
    f" tag: {format_sii_string(slot.tag)}",
    "}",
    "",
    "}",
]
```

### Example 2: Offline `httpx.MockTransport` Collector Pattern
```python
def fetch_frankfurter_v2(client: httpx.Client) -> tuple[dict[str, float], str]:
    resp = client.get(
        "https://api.frankfurter.dev/v2/rates",
        params={"base": "EUR"},
    )
    resp.raise_for_status()
    rows = resp.json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("Frankfurter v2 returned empty or non-list payload")
    rates: dict[str, float] = {"EUR": 1.0}
    data_date = ""
    for row in rows:
        quote = str(row["quote"]).upper()
        rate = float(row["rate"])
        if not math.isfinite(rate) or rate <= 0.0:
            raise ValueError(f"Invalid Frankfurter v2 rate for {quote}: {rate!r}")
        rates[quote] = rate
        data_date = max(data_date, str(row["date"]))
    return rates, data_date
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Frankfurter v1 (`/v1/latest`, nested `rates` dict, ECB-only ~30 currencies) | Frankfurter v2 (`/v2/rates?base=EUR`, flat JSON array, 219 currencies from 108 central banks) | 2025–2026 | Covers all 17 European currencies (`ALL`, `BAM`, `MKD`, `RSD`, `RUB`, `TRY`, + ECB currencies) in a single keyless call. |
| France `PrixCarburants_instantane.xml.zip` (20 MB XML, milli-EUR integers) | `data.economie.gouv.fr` OpenDataSoft v2.1 `records?select=avg(...)` | 2024–2026 | Single `<1 KB` JSON aggregation returning EUR/L across all 6 French grades (`Gazole`, `SP95`, `SP98`, `E10`, `E85`, `GPLc`). |
| Bulgaria `BGN` (`1 EUR = 1.95583 BGN`) | Bulgaria `EUR` (`1.0`, post-2026 Eurozone accession) | `2026-01-01` | Bulgaria is priced directly in `EUR` inside EC WOB, `data/laws/countries/bg.json`, and ETS2 `1.62` `fuel_price_strings.sui`. |
| DDS texture baking for fuel totems | Option 4b Zero-DDS `def/sign/board/*.sii` + 43-locale `local_module.ets2v2_fuel.sii` | ETS2 `1.43+` SDF fonts / `1.62` | Zero binary texture churn, 100% crisp SDF scaling across all 43 locales including `<sup>9</sup>`. |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `data.economie.gouv.fr` ODS v2.1 `avg(gazole_prix)` aggregation returns `EUR/L` directly without milli-EUR scaling (as documented in ODS v2 dataset metadata) `[ASSUMED]` | Deliverable 2 (`FR`) | Low — guarded by `0.01–5.00 EUR/L` circuit breaker (`D-06`), and collector can normalize `/1000` only if raw value is in `[500, 5000]` milli-EUR band or log an error. |
| A2 | `fuel-prices.eu/board_now.php` live market list currently includes `IS` and may intermittently add/remove `CH` or `NO` `[ASSUMED]` | Deliverable 2 (Non-EU) | Low — collector reads whatever ISO-2 codes appear in `petrol`/`diesel` dynamically and falls back seamlessly to `baseline_1.62_seeded` / `prices.lock.json`. |
| A3 | ETS2 `1.62` Prism3D `<sup>` scaling factor in `sign_template_text` is approximately `0.60–0.65×` of base `font_size` (derived from SDF rendering convention; exact C++ engine constant is closed-source) `[ASSUMED]` | Deliverable 3 (Width Budget) | Low — `1.03` tolerance + conservative `0.65×` factor routes all `40` borderline narrow boards cleanly to 2-decimal fallback, leaving generous margin on all `136` wide boards. |
| A4 | Initial checked-in `state/prices.lock.json` seeded in Phase 3 before the first Friday live fetch can be bootstrapped offline from `data/baselines/ets2_1.62_def/countries.json` + reference FX rates (or one live maintainer `ets2v2 fetch` run) `[ASSUMED]` | Deliverable 4 | Low — offline bootstrap ensures `uv run --offline ets2v2 package build` and `pytest` pass immediately on clean checkouts; first Friday CI `ets2v2 fetch` refreshes all Tier 1 countries live. |

---

## Open Questions (RESOLVED)

1. **Initial Seed of `state/prices.lock.json` in Git — RESOLVED:**
   - What we know: `D-05` requires `ets2v2 build` and `ets2v2 publish release` to run 100% offline reading `state/prices.lock.json`, and `state/prices.lock.json` tracks 39 territories (`D-04`).
   - **RESOLVED:** Plan `03-02` Task 3 (`03-02-03`) implements deterministic offline bootstrap `ets2v2 fetch --seed-offline --lock-path state/prices.lock.json` (calling `seed_initial_lockfile()` from `data/baselines/ets2_1.62_def/countries.json` + reference FX + `IE`/`CY`/`MT` defaults with fixed deterministic `seed_date`/`updated_at` and no wall-clock staleness alerts) to commit the initial reproducible 39-territory `state/prices.lock.json`; scheduled Friday CI (`phase-a-release.yml`) and manual `ets2v2 fetch` refreshes update it live from Tier 1 European/EEA feeds.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | Dependency locking & task runner | ✓ | `0.11.31` | — |
| Python | Runtime (`>=3.12`) | ✓ | `3.12.13` | — |
| `pytest` | Offline test suite | ✓ | `9.2.0` | — |
| `ruff` | Linting & formatting | ✓ | `0.17.5` | — |
| `basedpyright` | Strict static type checking | ✓ | `1.40.2` | — |
| ETS2 `1.62.3.3s` (`def.scs`, `locale.scs`) | Re-extracting extended `fuel_boards.json` (Plan `03-03`) | ✓ | `1.62.3.3s` (`D:\SteamLibrary\...`) | Committed `data/baselines/ets2_1.62_def/*.json` once re-extracted |
| `httpx` + `openpyxl` | Phase 3 runtime dependencies | ✗ *(not yet in `pyproject.toml`)* | Target `0.28.1` + `3.1.5` | Installed in Plan `03-01` via `uv add` |
| `TANKERKOENIG_API_KEY` | Optional `DE` live station enrichment (`D-03`) | ✗ *(optional)* | — | Automatic keyless fallback to `EC Weekly Oil Bulletin` (`DE`) |

**Missing dependencies with no fallback:** None (only `uv add httpx openpyxl` in Plan `03-01`).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest 9.2.0` + `pytest-cov` `[VERIFIED: pyproject.toml:23-24]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["src"]`) `[VERIFIED: pyproject.toml:47-53]` |
| Quick run command | `uv run --offline pytest -q --tb=short -m "not local_ets2"` |
| Full suite command | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| `DAT-01` | Multi-provider FX fetchers (`Frankfurter v2`, `ECB XML`, `fawazahmed0`, `CBR` cp1251), 39-territory currency mapping (`BG=EUR`, `BAM=1.95583`), tiered `2%/5%/10%` divergence & currency-split guards | unit (mocked `httpx.MockTransport`) | `uv run --offline pytest tests/test_fetch_fx.py tests/test_normalize_fx.py -x` | ❌ Wave 0 (`03-01`) |
| `DAT-02` | Tier 1 collectors (`EC WOB` dynamic XLSX + `EL->GR` + `/1000`, `FionnHughes` CSV, `fuel-prices.eu`, `UK DESNZ` pence->GBP, `NO SSB 09654`, `FR` ODS v2.1, `DE` Tankerkönig opt-in/fallback, `ES` MITECO, `IT` MIMIT, `NL` CBS 80416ned) + secondary grade spreads | unit (mocked `httpx.MockTransport` + generated `.xlsx` fixture) | `uv run --offline pytest tests/test_fetch_fuel.py tests/test_normalize_spreads.py -x` | ❌ Wave 0 (`03-02`) |
| `DAT-03` | `state/prices.lock.json` schema, `0.01–5.00 EUR/L` bounds, `±25%` WoW guard, `--allow-jump <ISO2>`, partial vs total outage exit codes, 14d/30d staleness alerts | unit + CLI integration | `uv run --offline pytest tests/test_normalize_lockfile.py tests/test_cli_fetch.py -x` | ❌ Wave 0 (`03-02`) |
| `TOT-01` | Extended `fuel_boards.json` extraction, `460` clean-room `def/sign/board/*.sii` synthesis (`gas_empty` & 5 highway signs excluded), exact `43`-locale `local_module.ets2v2_fuel.sii` sync (`fr_ca` present, `fr_qc` absent), Zero-DDS & validator hard checks (`D-12`) | unit + integration | `uv run --offline pytest tests/test_totems_compiler.py tests/test_validate_totems.py -x` | ❌ Wave 0 (`03-03`) |
| `TOT-02` | Native-currency formatting (`GB` pence, `BG` EUR, `HUF`/`ISK`/`ALL`/`RSD` int, `CZ` `.X0`, `RO`/`MK` width, Eurozone `<sup>9</sup>` / 3-dec / 2-dec width routing on all 460 boards), `gas_is_yokull` swap fix, `gas_is_ip1_98` restore, `gas_ie_*`/`gas_bi_*`/`gas_ba_*_lpg`/`gas_dk_92`, snapshot v1 compatibility, changelog fuel table & CI workflow assertions | unit + end-to-end offline release | `uv run --offline pytest tests/test_totems_formatting.py tests/test_publish_release.py tests/test_publish_workflow.py -x` | ❌ Wave 0 (`03-04`, extends existing release/workflow tests) |

### Sampling Rate
- **Per task commit:** `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short -m "not local_ets2"`
- **Per wave merge:** Full suite including `@pytest.mark.local_ets2` (`uv run --offline pytest -q --tb=short`)
- **Phase gate:** Full suite green + `ets2v2 validate workshop` & `ets2v2 validate local` green on both Summer and Winter builds before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_fetch_fx.py`, `tests/test_normalize_fx.py` — covers `DAT-01` (`03-01`)
- [ ] `tests/test_fetch_fuel.py`, `tests/test_normalize_spreads.py`, `tests/test_normalize_lockfile.py`, `tests/test_cli_fetch.py` — covers `DAT-02`, `DAT-03` (`03-02`)
- [ ] `tests/test_totems_compiler.py`, `tests/test_validate_totems.py` — covers `TOT-01`, `D-12` (`03-03`)
- [ ] `tests/test_totems_formatting.py` + extensions to `tests/test_publish_release.py`, `tests/test_publish_workflow.py`, `tests/test_registry_snapshot.py`, `tests/test_baseline_contracts.py` — covers `TOT-02`, `D-13`..`D-16` (`03-04`)

---

## Security Domain

### Applicable ASVS Categories (ASVS Level 2 — `security_enforcement: true`)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| **V2 Authentication** | Minimal (`TANKERKOENIG_API_KEY` optional secret) | Read `TANKERKOENIG_API_KEY` strictly from environment (`os.environ.get`), NEVER log request URLs containing `apikey=` query params (mask `apikey=***` in all error/debug/alert strings!). |
| **V3 Session Management** | No | Stateless CLI tool with zero user sessions. |
| **V4 Access Control** | Yes (CI Workflow permissions & path containment) | Keep `ci.yml` at `contents: read`; keep `phase-a-release.yml` scoped to `schedule`/`workflow_dispatch` (never `pull_request_target`) so `TANKERKOENIG_API_KEY` secret is never exposed to forks; enforce `_ensure_contained()` on all written build/lockfile paths. |
| **V5 Input Validation** | **Yes (Critical — untrusted external HTTP/XLSX/XML/CSV inputs)** | Validate all fetched JSON/CSV/XML/XLSX via strict Pydantic v2 models (`allow_inf_nan=False`, finite bounds), enforce HTTPS-only allowlisted upstream hosts for dynamic link discovery (`energy.ec.europa.eu`, `assets.publishing.service.gov.uk`, `gov.uk` — preventing SSRF via malicious HTML `<a href>` redirects!), cap response body size (`<= 30 MB` for MITECO/XLSX, `<= 2 MB` for XML), reject `<!DOCTYPE`/`<!ENTITY` in XML before `ET.fromstring()`, and reject SII control chars/backslashes via `format_sii_string()`. |
| **V6 Cryptography** | Minimal | Enforce default TLS certificate verification (`verify=True` in `httpx.Client` — never disable TLS verification!). |

### Known Threat Patterns for Python Data Pipeline & Mod Compiler

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **SSRF / Open-Redirect via Dynamic HTML Link Discovery (`EC WOB`, `UK DESNZ`)** | Tampering / Information Disclosure | Resolve relative `href` via `urllib.parse.urljoin`, then assert `scheme == "https"` AND `hostname` is in explicit per-collector allowlist (`energy.ec.europa.eu`, `ec.europa.eu`, `assets.publishing.service.gov.uk`, `www.gov.uk`) before issuing the download GET. Disable cross-host unsafe redirects or re-validate final URL host. |
| **API Key Leakage in Logs / Alerts (`TANKERKOENIG_API_KEY`)** | Information Disclosure | Strip/redact query parameters from `httpx.HTTPStatusError` / `httpx.RequestError` messages before printing or recording into `state/prices.lock.json` `alerts[]`! |
| **XML Bomb / XXE on `ECB` & `CBR` XML** | Denial of Service / Information Disclosure | Cap XML response payload to `<= 2 MiB` and reject any payload containing `<!DOCTYPE` or `<!ENTITY` before passing to `xml.etree.ElementTree.fromstring()`. |
| **Zip Bomb / Malicious OOXML in `EC WOB` `.xlsx`** | Denial of Service | Cap downloaded `.xlsx` bytes (`<= 20 MiB`), open with `openpyxl.load_workbook(..., read_only=True, data_only=True)` and cap scanned row count (`<= 5000` rows). |
| **Upstream Price Poisoning / Unit-Scaling Corruption** | Tampering | Circuit breaker (`0.01–5.00 EUR/L`, `±25%` WoW without `--allow-jump`), tiered FX cross-validation (`2%/5%/10%`), and currency-split magnitude envelopes (`D-06`, `D-07`). |
| **SII Injection via Untrusted Localization Values** | Tampering | Format all totem values strictly from validated `Decimal` numbers matching `^[0-9]+(?:\.[0-9]+)?(?:<sup>[0-9]</sup>)?$`, emit via `format_sii_string()`, and re-parse in Offline SCS Validator (`D-12`). |

---

## Sources

### Primary (HIGH confidence)
- **ETS2 `1.62.3.3s` Local Game Archives** (`def.scs`, `locale.scs`, `base.scs`) — Direct read-only forensic inspection of all `461` `def/sign/board/*.sii` attribute schemas, `locale/fuel_price_strings.sui` (`99` keys + SCS formatting comments), `locale/en_gb/local.sii`, and all `6` `/font/sign/gas_*.font` SDF glyph tables & advance widths.
- **Repository Source & Baselines** — `data/baselines/ets2_1.62_def/{fuel_boards,locales,countries}.json`, `data/laws/countries/*.json`, `data/mappings/ets2_countries.json`, `src/ets2v2/{registry/snapshot,sii/sign_board,sii/localization,sii/hygiene,package/builder,package/synthesize,package/metadata,validate/workshop,validate/invariants,publish/release,publish/changelog,baseline/extractor,baseline/models,cli}.py`, `.github/workflows/{ci,phase-a-release}.yml`.
- **SCS Modding Wiki** (`.agents/skills/scs-modding-wiki/docs/engine/{units,mod_manager,fonts}.md`) — `SiiNunit`, `localization_db`, `<=12`-char unit segments, SDF font format.
- **Official FX & Government Open-Data Docs:**
  - Frankfurter v2 (`https://frankfurter.dev` — `/v2/rates` flat JSON array schema, MIT)
  - ECB Eurofxref (`https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`, RUB suspension notice 2022-03-01)
  - `fawazahmed0/exchange-api` (`https://github.com/fawazahmed0/exchange-api`, jsDelivr + Cloudflare Pages URLs, CC0-1.0)
  - CBR XML (`https://www.cbr.ru/scripts/XML_daily.asp`, `windows-1251`, `Valute`/`Nominal`/`Value`/`VunitRate`)
  - Central Bank of Bosnia and Herzegovina (`cbbh.ba` — `1 EUR = 1.95583 BAM` currency board peg)
  - EC Weekly Oil Bulletin (`https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en`, `Prices with taxes`, `1000 l`, `EL`, `LPG - motor fuel`, CC BY 4.0)
  - UK DESNZ (`https://www.gov.uk/government/statistical-data-sets/oil-and-petroleum-products-weekly-statistics`, `ULSP`/`ULSD` pence/litre, OGL v3.0)
  - Norway SSB PxWebApi v2 (`https://data.ssb.no/api/pxwebapi/v2/tables/09654`, JSON-stat2, CC BY 4.0)
  - France OpenDataSoft v2.1 (`https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records`, Licence Ouverte v2.0)
  - Germany Tankerkönig (`https://creativecommons.tankerkoenig.de/json/list.php`, CC BY 4.0)
  - Spain MITECO (`https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/`)
  - Italy MIMIT (`https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv`, IODL 2.0)
  - Netherlands CBS StatLine OData (`https://opendata.cbs.nl/ODataApi/odata/80416ned/TypedDataSet`, `BenzineEuro95_1`, `Diesel_2`, `Lpg_3`, `Perioden`, CC BY 4.0)

### Secondary (MEDIUM confidence)
- `FionnHughes/eu-weekly-oil-bulletin` (`https://huggingface.co/datasets/FionnHughes/eu-weekly-oil-bulletin`) — tidy CSV mirror of CC BY 4.0 EC Weekly Oil Bulletin.
- `fuel-prices.eu` (`https://www.fuel-prices.eu/board_now.php`) — CC BY 4.0 live pan-European EUR/L ticker JSON.
- PyPI package metadata (`httpx 0.28.1`, `openpyxl 3.1.5`, transitive dependency licenses).
- European retail fuel spread benchmarks (`tcs.ch`, `cargopedia.net` cross-checked against ETS2 `1.62` `fuel_price_strings.sui`).

---

## Metadata

**Confidence breakdown:**
- Standard stack & licensing: **HIGH** — `httpx 0.28.1` + `openpyxl 3.1.5` + transitive licenses verified against PyPI; toolchain verified locally.
- FX & Tier 1 fuel APIs: **HIGH** — Exact endpoints, response shapes, encodings, unit scaling (`EUR/1000L`, `pence/L`), and quirks verified against official documentation.
- Totem engine & `1.62` forensics: **HIGH** — All `461` boards, all `6` `.font` SDF glyph tables, and all `99` `fuel_price_strings.sui` conventions directly verified against local ETS2 `1.62.3.3s` archives.
- Lockfile, Snapshot v1 & Validator integration: **HIGH** — Directly verified against existing `src/ets2v2/` strict Pydantic v2 models and CI workflows.

**Research date:** 2026-11-21
**Valid until:** 2026-12-21 (30 days; upstream Drupal/GOV.UK landing links are discovered dynamically by design)
