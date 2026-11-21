# Phase 3: Open European Fuel/FX Pipeline & Zero-DDS Totem Engine - Context

**Gathered:** 2026-11-21
**Status:** Ready for planning
**Scope:** Requirements `DAT-01`, `DAT-02`, `DAT-03`, `TOT-01`, `TOT-02` (Plans `03-01` through `03-04`)

<domain>
## Phase Boundary

Phase 3 wires live, legally clean European/EEA fuel prices and multi-provider FX conversion into the Summer and Winter Vanilla+DLC Core build pipeline and adds the **Option 4b Zero-DDS 43-locale fuel totem engine**. Specifically, it delivers:
- Multi-provider FX fetching & cross-validation (`Frankfurter v2` primary, `ECB eurofxref-daily.xml` validator, `fawazahmed0/exchange-api` & `CBR XML` fallbacks) converting native pump currencies cleanly into typed `eur_per_liter` and `local_display_price` models (`DAT-01`).
- Tier 1 open European & EEA fuel ingestion (`EC Weekly Oil Bulletin` dynamic `.xlsx` discovery + `FionnHughes`/`fuel-prices.eu` `CC BY 4.0` fallbacks, `UK DESNZ` `OGL v3`, `NO SSB` Table `09654`, and national multi-grade APIs `FR`/`DE`/`ES`/`IT`/`NL`) backed by `state/prices.lock.json` circuit-breaker guards (`DAT-02`, `DAT-03`).
- Option 4b Zero-DDS roadside fuel totems emitting namespaced `@@fp_*_ets2v2@@` `def/sign/board/*.sii` overrides across all identifiable single-text `1.62` fuel boards and synchronized `locale/<lang>/local_module.ets2v2_fuel.sii` modules across all **43** active ETS2 `1.62` locales, validated by the Offline SCS Validator (`TOT-01`, `TOT-02`).

Out of scope for Phase 3 (explicitly deferred to later phases):
- ProMods Companion Editions (`EU + ME + MA + TGS`, `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii`) and `ets2v2 compose-local` map-combo composer (**Phase 4**).
- Non-EU Tier 1 global APIs (`US EIA`, `BR ANP`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`), Tier 2 guarded national portal scrapers (`CH` BFS/LIK, `IS` Orkusetur, `MD` ANRE, `MK` ERC, `RU` Rosstat, etc.), Tier 3 `200+` global baselines, and CI-only OSM `CC BY-SA` speed-limit drift audits (**Phase 5**).
- Full-auto SteamCMD Workshop publishing (**Future V2**).

</domain>

<decisions>
## Implementation Decisions

### 1. Non-EU Vanilla Coverage, Secondary Fuel Grades & API Keys (`DAT-02`)
- **D-01 — Non-EU Vanilla Countries (`AL`, `BA`, `CH`, `IS`, `ME`, `MK`, `RS`, `RU`, `TR`, `XK`):** Use `fuel-prices.eu` (`CC BY 4.0`) where covered for non-EU vanilla European countries, and seed any remaining uncovered non-EU vanilla entries from the ETS2 `1.62` baseline (`data/baselines/ets2_1.62_def/countries.json`) into `state/prices.lock.json` until Phase 5 adds dedicated Tier 2/3 national portal collectors. Convert baseline/fallback values cleanly through live FX so all 36 Vanilla+DLC countries have coherent EUR `.sui` and native-currency totem prices immediately.
- **D-02 — Missing Secondary Fuel Grades (`98`, `100`, `Diesel+`, `E85`, `LPG`, `92`, `MPO`):** Use live national multi-grade feeds (`FR` `prix-carburants.gouv.fr`, `DE` `Tankerkönig` when keyed, `ES` MITECO, `IT` MIMIT, `NL` CBS StatLine) and `EC Weekly Oil Bulletin` `LPG` directly wherever available. For any country/grade not directly published by a Tier 1 feed, compute deterministic secondary grades using documented per-grade market spread ratios over live `petrol_95` / `diesel` (e.g., `petrol_98 ≈ petrol_95 × 1.06`, `petrol_100 ≈ petrol_95 × 1.12`, `diesel_plus ≈ diesel × 1.07`, `e85 ≈ petrol_95 × 0.72`, `mpo ≈ diesel × 0.75`, `petrol_92 ≈ petrol_95 × 0.96`, `lpg ≈ petrol_95 × 0.48` — exact ratios verified during Phase 3 research) so all multi-grade totems track weekly swings realistically.
- **D-03 — Optional `TANKERKOENIG_API_KEY` for Germany (`DE`):** Treat Germany's `Tankerkönig` (`CC BY 4.0`) API key as optional enrichment. When `TANKERKOENIG_API_KEY` is present in environment / GitHub Actions Secrets, sample a deterministic fixed set of German stations/cities for live multi-grade (`E5`/`E10`/`Diesel`) averages; when unset, silently fall back to `EC Weekly Oil Bulletin` (`DE`) + documented grade spreads so local builds, tests, and public forks work zero-secret out of the box.
- **D-04 — `state/prices.lock.json` Tracks 39 European Territories (`36` Vanilla + `IE`/`CY`/`MT`):** Store all **39** European entries in `state/prices.lock.json` (`36` Vanilla+DLC countries plus `IE`, `CY`, and `MT` naturally returned by the EU-27 `EC Weekly Oil Bulletin`). This gives ETS2 `1.62`'s `gas_ie_*` fuel sign boards live official Irish EUR prices immediately and pre-warms `IE`/`CY`/`MT` for Phase 4 ProMods, while Core `def/country/*.sui` and `speed_limits.sii` remain strictly scoped to the **36** Vanilla+DLC countries. — **Reversibility:** `moderate` — cleanly bridges `1.62` `gas_ie_*` signs and Phase 4 ProMods without expanding Core `.sui` scope.

### 2. Circuit Breaker, `state/prices.lock.json` Lifecycle & Friday CI Wiring (`DAT-01`, `DAT-03`)
- **D-05 — Two-Stage Decoupled Flow (`fetch` vs offline `build`/`publish`):** Place the price lockfile at `state/prices.lock.json` beside `state/published.json`. Online `ets2v2 fetch` updates `state/prices.lock.json` (with FX cross-validation and circuit-breaker guards), while `ets2v2 build` and `ets2v2 publish release` remain **100% offline-deterministic**, reading `state/prices.lock.json` with zero network I/O. In `.github/workflows/phase-a-release.yml`, run the online `fetch` step before `publish release`, and commit updated `state/prices.lock.json` alongside `state/published.json` and `CHANGELOG_{SUMMER,WINTER}.md` inside the single persistent Release PR (`release/phase-a-weekly`). — **Reversibility:** `costly` — defines the offline/online boundary, PR CI reproducibility, and Friday Release PR artifact contract.
- **D-06 — Strict Price Circuit Breaker with Manual Shock Override:** Automatically reject and hold the last-known-good value in `state/prices.lock.json` (recording a structured alert) whenever a fetched price falls outside `0.01–5.00 EUR/L` equivalent **OR** changes by more than `±25%` week-over-week against the lockfile. Provide a manual CLI override flag (`--allow-jump <ISO2>`) on `ets2v2 fetch` so maintainers can explicitly accept genuine tax/currency shocks without weakening default protection against upstream unit-scaling bugs (e.g., EUR/1000L or pence-as-GBP).
- **D-07 — Tiered FX Cross-Validation & Currency-Split Guard (`DAT-01`):** Cross-validate primary `Frankfurter v2` rates against `ECB eurofxref-daily.xml` (for ECB currencies) and `fawazahmed0/exchange-api` / `CBR XML` (for non-ECB/regional currencies like `RUB`, `ALL`, `BAM`, `MKD`, `RSD`), accounting for ECB weekend/TARGET2 fixing lag. Enforce tiered divergence tolerances:
  - Warn at `>2%` divergence for major/ECB pairs (`GBP`, `CHF`, `CZK`, `DKK`, `HUF`, `ISK`, `NOK`, `PLN`, `RON`, `SEK`), and `>5%` for volatile/non-ECB pairs (`TRY`, `RUB`, `ALL`, `BAM`, `MKD`, `RSD`).
  - Reject & hold lockfile FX with an alert if divergence exceeds `10%` or fails currency-split sanity checks (e.g., inverted `EUR/X` vs `X/EUR` magnitude, non-positive/NaN rates, or `BG` not pinned to `EUR = 1.0`).
- **D-08 — Outage & Staleness Policy in Friday CI:**
  - **Partial upstream outage** (one or more feeds unreachable/failing while at least one Tier 1 fuel feed succeeds): warn loudly, retain `state/prices.lock.json` values for affected countries, record structured alerts, and proceed with the Friday build.
  - **Total upstream outage** (`0` live Tier 1 fuel feeds reachable during `ets2v2 fetch`): exit non-zero so Friday CI fails loudly and alerts the maintainer rather than silently no-oping on stale data.
  - **Staleness alerts:** Emit structured warnings in fetch output, changelogs, and Release PR summary when a Tier 1 country entry is older than **14 days**, or a fallback/seeded entry is older than **30 days**.

### 3. Zero-DDS Totem Engine, Native Currency Formatting & Validator Invariants (`TOT-01`, `TOT-02`)
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

### 4. Snapshot v1 Compatibility, `.sui` Precision & Weekly Changelogs (`DAT-01`, `DAT-03`)
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or executing Phase 3:**

### Project & Milestone Specs
- `.planning/PROJECT.md` — Core value, Option 4b Zero-DDS mandate, legally clean 3-tier pipeline, and explicit source rejections (`GlobalPetrolPrices.com`, `MyLPG.eu`, paid `IEA`).
- `.planning/REQUIREMENTS.md` — Requirements `DAT-01`, `DAT-02`, `DAT-03`, `TOT-01`, `TOT-02` and Out-of-Scope exclusions.
- `.planning/ROADMAP.md` — Phase 3 goal, 4 success criteria, research flag (`gsd-phase-researcher` recommended), and plan breakdown (`03-01`..`03-04`).
- `.planning/STATE.md` — Locked decisions and operational dependencies (`Tankerkönig` optional key).
- `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-CONTEXT.md` — Clean-room JSON-only `data/` boundary, SII hygiene, and `fuel_boards.json` extraction rules.
- `.planning/phases/02-realism-registry-seasonal-core-builds-offline-validator-phase-a/02-CONTEXT.md` — Phase 2 `D-04`..`D-11` contracts (clean-room synthesis, Workshop layout, Offline SCS Validator, persistent Release PR, locked `schema_version: 1` `RealismSnapshot`).

### Research & Codebase Maps
- `.planning/research/FEATURES.md` — Verified `1.62` `fuel_price_strings.sui` / `def/sign/board/*.sii` forensics, `3249064596` totem bugs (`fr_ca`/`fr_qc`, 86 missed boards, `gas_is_ip1_98`, `gas_is_yokull` swap), FX APIs, and Tier 1 European fuel APIs.
- `.planning/research/STACK.md` — Pinned Phase 3 runtime dependencies (`httpx>=0.28,<0.29`, `openpyxl>=3.1,<4`), strict `basedpyright`/`ruff`/`pytest` gates.
- `.planning/research/PITFALLS.md` — SCS encoding/BOM/LF/`<=12`-char unit token rules, `EL`->`GR` EC mapping, ECB `RUB`/weekend caveats, and Zero-DDS constraints.
- `.planning/research/SUMMARY.md` — Synthesized Tier 1 data source table and Phase 3 research flags.
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/STACK.md` — Acyclic package DAG, offline CI vs online fetch isolation, and clean-room boundaries.

### Existing Code & Baseline Data
- `data/baselines/ets2_1.62_def/fuel_boards.json` — `461` extracted single-text fuel boards (`373` `active_fp`, `47` `placeholder`, `41` `blank`, `6` gas `.font` faces) plus `5` excluded multi-item highway signs.
- `data/baselines/ets2_1.62_def/locales.json` — Exact `43` active ETS2 `1.62` locales (`fr_qc` excluded, `fr_ca` included), `12` `tz_*` keys, and `99` vanilla `fp_*` keys.
- `data/baselines/ets2_1.62_def/countries.json` — Baseline `1.62` `fuel_price` values for seeding uncovered non-EU vanilla countries.
- `data/laws/countries/<iso2>.json` & `data/mappings/ets2_countries.json` — Canonical 36-country currency codes (including `BG: EUR`) and slug mappings.
- `src/ets2v2/registry/snapshot.py` — Locked `schema_version: 1` `RealismSnapshot` and `RealismSnapshotFuel` models.
- `src/ets2v2/package/builder.py`, `src/ets2v2/package/synthesize.py`, `src/ets2v2/package/metadata.py` — Core Summer/Winter build pipeline, `.sui` emitter, and `description.txt` generator.
- `src/ets2v2/validate/workshop.py` & `src/ets2v2/validate/invariants.py` — Offline SCS Workshop Validator and `1.62` invariant auditor to extend with Phase 3 totem checks.
- `src/ets2v2/publish/release.py`, `src/ets2v2/publish/changelog.py`, `.github/workflows/phase-a-release.yml` — Phase A release orchestrator, changelog renderer, and Friday `06:00 UTC` persistent-PR CI workflow.
- `.agents/skills/scs-modding-wiki/docs/engine/units.md` & `.agents/skills/scs-modding-wiki/docs/engine/mod_manager.md` — SCS `SiiNunit`, `localization_db`, `sign_board_template`, and `<=12`-char unit segment rules.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ets2v2/sii/hygiene.py` (`validate_sii_hygiene`, `serialize_sii_text`, `validate_unit_name_segments`) — Ready to validate every generated `def/sign/board/*.sii` and `locale/<lang>/local_module.ets2v2_fuel.sii`.
- `src/ets2v2/sii/sign_board.py` (`SignBoardTemplate`, `SignTemplateTextSlot`, `parse_sign_board`) & `src/ets2v2/sii/localization.py` (`LocalizationEntry`, `parse_localization_db`) — Existing read-only parsers that the Offline SCS Validator (`PUB-01`) can call directly to parse and verify emitted totem boards and localization modules.
- `src/ets2v2/package/synthesize.py` (`format_sii_string`, `_format_fuel_price`) — Existing safe SII string/float formatters rejecting backslashes/NULs and formatting `fuel_price` cleanly.
- `src/ets2v2/publish/changelog.py` (`_diff_country`, `render_edition_changelog`) — Already diffs `RealismSnapshotFuel` (`eur_per_liter`, `currency`, `source`, `local_prices`); ready to extend with the 36-country fuel table, attribution block, and circuit-breaker alert section.

### Established Patterns
- Frozen Pydantic v2 models (`ConfigDict(strict=True, frozen=True, extra="forbid")`) + deterministic UTF-8 no-BOM LF sorted JSON (`json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`).
- Strict `basedpyright` (`strict` mode, Python `3.12`) + `ruff` (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`) + offline `pytest` (`uv run --offline pytest` in `ci.yml` — all network tests MUST use mocked HTTP transports / fixtures so PR CI stays 100% offline).
- `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` gates active subpackages under `src/ets2v2/` (Phase 3 unlocks `fetch/` and `normalize/` while keeping Phase 4's `merge/` blocked).

### Integration Points
- `pyproject.toml` & `uv.lock` — Add `httpx>=0.28,<0.29` and `openpyxl>=3.1,<4`.
- `state/prices.lock.json` — New committed canonical price/FX lockfile seeded in Phase 3 and updated by Friday CI inside the persistent Release PR.
- `src/ets2v2/registry/snapshot.py` & `src/ets2v2/package/builder.py` — Inject loaded `state/prices.lock.json` prices into `build_realism_snapshot()` and emit `def/sign/board/*.sii` + `locale/<lang>/local_module.ets2v2_fuel.sii` inside `build_core_edition()`.
- `src/ets2v2/validate/workshop.py` & `invariants.py` — Enforce Zero-DDS, 43-locale sync, and board-to-token cross-reference invariants.
- `.github/workflows/phase-a-release.yml` — Run `ets2v2 fetch` (with optional `TANKERKOENIG_API_KEY` secret) before `ets2v2 publish release`, and stage `state/prices.lock.json` in the persistent Release PR.

</code_context>

<specifics>
## Specific Ideas

- **Research targets for `gsd-phase-researcher`:**
  - Verify live endpoint contracts, pagination/compression, and auth/header quirks for `Frankfurter v2`, `ECB eurofxref-daily.xml`, `fawazahmed0/exchange-api`, `CBR XML`, `EC Weekly Oil Bulletin` dynamic Drupal `.xlsx` discovery (incl. `EL`->`GR` mapping), `FionnHughes`/`fuel-prices.eu`, `UK DESNZ`, `NO SSB` Table `09654`, and `FR`/`DE`/`ES`/`IT`/`NL` multi-grade feeds.
  - Inspect actual ETS2 `1.62.3.3s` `locale.scs` (`locale/fuel_price_strings.sui`), `def.scs` `.font` glyph metrics, and all `88` placeholder/blank boards in `data/baselines/ets2_1.62_def/fuel_boards.json` to lock exact per-board `<sup>9</sup>` support, width budgets, and country/grade classification rules (confirming which boards are structural spacers like `gas_empty`).
  - Document realistic European secondary-grade market spread ratios (`98`/`100`/`Diesel+`/`E85`/`LPG`/`92`/`MPO`) backed by verified European retail fuel benchmarks.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed strictly within Phase 3 boundaries. ProMods `pm_*_fuel` totems and `compose-local` remain mapped to Phase 4 (`MAP-01`..`MAP-05`), and non-EU Tier 1/2/3 global collectors (`CH` BFS/LIK, `IS` Orkusetur, `MK` ERC, `RU` Rosstat, `US`/`BR`/`JP`/etc.) + CI OSM speed-limit drift audits remain mapped to Phase 5 (`GLB-01`..`GLB-04`).

</deferred>

---

*Phase: 03-open-european-fuel-fx-pipeline-zero-dds-totem-engine*
*Context gathered: 2026-11-21*
