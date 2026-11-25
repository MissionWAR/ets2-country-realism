# Phase 5: Global Tier 1/2/3 Coverage & Internal OSM Audit - Context

**Gathered:** 2026-11-25
**Status:** Ready for planning
**Scope:** Requirements `GLB-01`, `GLB-02`, `GLB-03`, `GLB-04` (Plans `05-01` through `05-04`)

<domain>
## Phase Boundary

Phase 5 scales the clean-room V2 data pipeline and global `realism-snapshot-{summer|winter}.json` contract from `76` Vanilla+ProMods territories to **`200+` global countries and territories** for `ets2v2 compose-local` map combos, while adding a strictly isolated internal CI OSM speed-limit drift audit with automated `CC BY 4.0` license-taint enforcement. Specifically, it delivers:
- **Non-EU Tier 1 Open Government Fuel Collectors (`GLB-01`):** Automated ingestion, currency/unit normalization, and regional aggregation for `US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM`, `JP METI`, and `KR Opinet`, wired into `ets2v2 fetch` with optional secret isolation and EU Core CI gate separation.
- **Tier 2 Guarded National Portal Scrapers (`GLB-02`):** Research-gated, stdlib-only HTML/XML/XLSX/JSON parsers for machine-readable national portals (`CH`, `MD`, `MK`, `RU`, `IL`, `JO`, `AE`, `ZA`, `KE`, `NG`, `ID`, and `SA`/`EG`/`IS` where cleanly accessible) wrapped in strict per-country fault-isolated circuit breakers with tier-aware staleness alerts and zero Friday CI breakage.
- **Tier 3 Global `200+` Territory & FX Expansion (`GLB-03`):** Full canonical expansion of `data/laws/countries/<iso2>.json`, `data/mappings/ets2_countries.json`, and `state/prices.lock.json` to `~215–225` territories (`~155+` ISO-4217 currencies via data-driven `data/mappings/currencies.json` and `data/curated/tier3_fuel_baselines.json`) while keeping `RealismSnapshot` frozen at `schema_version: 1` and Vanilla+DLC Core builds strictly scoped to `36` countries.
- **Internal CI OSM (`CC BY-SA`) Speed-Limit Drift Audit & `CC BY 4.0` Isolation (`GLB-04`):** Isolated `src/ets2v2/audit/` subpackage (`ets2v2 audit osm-speeds`) comparing `data/laws/` against `westnordost/osm-legal-default-speeds` (plus opt-in Overpass/Taginfo spot-checks) in a dedicated monthly `.github/workflows/osm-speed-audit.yml` workflow with zero Git writes, backed by AST DAG isolation walls and automated provenance/license-taint checks.

Out of scope for Phase 5 (explicitly deferred or prohibited):
- Full-auto SteamCMD Workshop publishing and hidden-item TOTP verification spike (**Future V2**, `PUB-V2-01`, `PUB-V2-02`).
- Expanding Vanilla+DLC Core Workshop packages beyond the `36` `vanilla_1_62: true` countries, or bumping `RealismSnapshot` beyond `schema_version: 1`.
- Scraping `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`), `MyLPG.eu`, paid `IEA`, or bundling any `CC BY-SA` / `ODbL` OSM data into `data/laws/`, `state/prices.lock.json`, `realism-snapshot-*.json`, or any mod package.

</domain>

<decisions>
## Implementation Decisions

### 1. Non-EU Tier 1 Collectors & API Key Isolation (`GLB-01`)
- **D-01 — Optional API Keys (`EIA_API_KEY`, `OPINET_API_KEY`) Mirroring `TANKERKOENIG_API_KEY`:** Treat `EIA_API_KEY` (`US EIA v2`) and `OPINET_API_KEY` (`KR Opinet`) as optional environment secrets matching Phase 3 `D-03`. When unset, mark the collector `skipped=True` (never failed) and retain the lockfile / Tier 3 seed cleanly so public forks, local runs, and offline tests work zero-secret out of the box. Wire both optional secrets into `.github/workflows/phase-a-release.yml`.
- **D-02 — Separate European Core vs Global Tier 1 CI Outage Gates:** Keep Friday CI's hard-fail gate strictly scoped to **European Core Tier 1** fuel feeds (`eu_tier1_feeds_succeeded == 0` fails `ets2v2 fetch` / CI). Isolate **Global Tier 1** feeds (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`) so non-EU upstream outages emit structured `warning` alerts and retain `state/prices.lock.json` values without blocking Friday Core Workshop builds — and conversely, a succeeding non-EU feed never masks a total European Tier 1 outage. — **Reversibility:** `moderate` — protects weekly Workshop releases from regional API turbulence while keeping European outage detection strict.
- **D-03 — Lightweight Ingestion Formats & Dependency Discipline:** Keep `pyproject.toml` lean — ingest all non-EU Tier 1 feeds via lightweight JSON, CSV, or `.xlsx` endpoints using existing `httpx`, `openpyxl`, and Python stdlib (`json`, `csv`, `io`, `zipfile`). Explicitly do **not** add `pandas`, `pyarrow`, or `xlrd` (`MY OpenDOSM` via JSON/CSV API `api.data.gov.my`, `JP METI` via `.xlsx`/CSV, `BR ANP` via Latin-1 `;`-delimited CSV, `AR` CSV, `CO` JSON/OData, `CL` JSON).
- **D-04 — Exact Unit Conversions & Outlier-Resistant Regional Aggregation:** Convert `US EIA` `USD/gallon` to `USD/L` using the exact NIST liquid gallon factor (`3.785411784` L/gal). Use official published national average rows wherever provided (`US EIA` national average, `JP METI` national average row, `MY OpenDOSM` national weekly price), and compute deterministic **median** across valid station/municipality rows for raw station-level feeds (`BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`) to reject erroneous station outliers cleanly, mapping regular retail grades (`diesel`, `petrol_95`, plus `petrol_98`/`e85`/`lpg` where published) into canonical `FuelGrade` keys.

### 2. Tier 2 Guarded National Portals, HTML Parsing & Staleness Cadence (`GLB-02`)
- **D-05 — Research-Gated Tier 2 National Portal Roster:** Target the structured Tier 2 national portals identified in `ROADMAP.md` and `FEATURES.md` (`CH` BFS/LIK, `MD` ANRE, `MK` ERC, `RU` Rosstat, `IL` MoE/CBS, `JO` MEMR, `AE` MOEI, `ZA` DMRE/CEF, `KE` EPRA, `NG` NBS, `ID` Pertamina/ESDM, plus `SA`/`EG`/`IS` where direct machine-readable HTML/JSON/XLSX endpoints exist). During Phase 5 research, verify live machine-readability and automatically classify any portal gated by Cloudflare/anti-bot challenges, JS-only SPA rendering, CAPTCHAs, or scanned PDFs cleanly into Tier 3 curated baselines rather than building brittle scrapers.
- **D-06 — Stdlib-Only HTML/XML Parsing (Zero New Runtime Dependencies):** Implement all Tier 2 HTML and XML scrapers using Python stdlib (`html.parser`, `xml.etree.ElementTree`, `re`) plus existing `openpyxl`/`csv` — adding **zero** new runtime dependencies (no `beautifulsoup4`, no `lxml`), keeping `uv.lock` lean, supply-chain minimal, and strict `basedpyright` clean.
- **D-07 — Strict Per-Country Circuit-Breaker Isolation & CLI Filter Flags:** Extend `RawFuelFeedResult.tier` to `Literal["tier1", "tier2", "fallback"]` and execute each Tier 2 portal inside an isolated per-country boundary catching HTTP `403`/`429`/timeouts, charset/decoding errors (`windows-1251`, Latin-1, UTF-8), and HTML selector drift. Emit structured `warning` alerts (`tier2_portal_outage`, `tier2_rate_limited`, `tier2_selector_drift`, `tier2_encoding_error`), retain last-known-good `state/prices.lock.json` prices (still enforcing `0.01–5.00 EUR/L` and `±25%` WoW guards on accepted quotes), and **never** fail Friday CI on Tier 2 errors. Expose CLI filter flags on `ets2v2 fetch` (e.g., `--no-global`, `--no-tier2`) for fast targeted runs.
- **D-08 — Tier-Aware Staleness Thresholds & Noise-Controlled Alert Summaries:** Replace the flat 14d/30d staleness split in `evaluate_lockfile_staleness()` with tier- and cadence-aware limits:
  - **14 days:** Weekly Tier 1 live feeds (EU & Global).
  - **45 days:** Monthly Tier 2 national portals (and **105 days** for quarterly portals such as `EG` FAPC).
  - **30 days:** Degraded Tier 1 fallback retention.
  - **180 days:** Tier 3 curated global baseline review cadence.
  Keep Core, Tier 1, and Tier 2 anomalies itemized in alerts while aggregating Tier 3 staleness/fallback entries into compact summary counts in `CHANGELOG_{SUMMER,WINTER}.md` and Friday PR/step summaries so `130+` Tier 3 territories never flood release notes.

### 3. Tier 3 Global `200+` Territory Expansion, FX Scaling & Changelog Scope (`GLB-03`)
- **D-09 — Full Canonical `200+` Territory Expansion (~215–225 Territories):** Expand `data/laws/countries/<iso2>.json`, `data/mappings/ets2_countries.json` (`vanilla_1_62: false`), and `state/prices.lock.json` from `76` to **~215–225 territories** covering all ~195 UN sovereign states plus ~20–30 inhabited ISO-3166-1 territories and ETS2 global map-combo regions (`TW`, `HK`, `MO`, `PR`, `GF`, `GP`, `MQ`, `RE`, `YT`, `NC`, `PF`, `CW`, `AW`, `BM`, `KY`, `VG`, `TC`, `FK`, `PM`, `SX`, `EH`, etc., ensuring 100% coverage of every ISO-2 referenced in `data/mappings/country_aliases.json` and global map combos *EAA*, *Beyond*, *SEA*, *RoC*, *Africa*, *Project Japan*, *JRR*, *7RM*, *C2C/ProMods Canada*). Every territory carries a complete canonical `CountryLawRecord` (IANA timezone, `speed_unit`, statutory Summer/Winter speed limits, DRL, axle mass limits, ISO-4217 currency) so `realism-snapshot-{summer|winter}.json` stays frozen at `schema_version: 1` with `200+` full `RealismSnapshotCountry` entries while Vanilla+DLC Core builds stay strictly at `36` countries. — **Reversibility:** `moderate` — cleanly fulfills `GLB-03` and powers offline `compose-local` worldwide without breaking `RealismSnapshot` v1.
- **D-10 — Externalized Data-Driven Currency/FX Metadata & Tier 3 Fuel Baselines:** Move global ISO-2 → currency mappings, FX sanity envelopes, reference FX rates, and Tier 3 curated EUR/L fuel baselines out of Python literals in `src/ets2v2/normalize/currencies.py` into clean-room, Pydantic-validated versioned JSON files under `data/` (`data/mappings/currencies.json` and `data/curated/tier3_fuel_baselines.json` with `verified_date` and clean-room provenance metadata), loaded by `ets2v2.normalize` while preserving backwards-compatible Python constant exports and all AST offline DAG isolation walls.
- **D-11 — Isolated Global FX Validation & Hard `0.01 EUR/L` Floor:** Scale FX coverage from `41` to `~155+` ISO-4217 currencies via `Frankfurter v2` + `ECB` + `fawazahmed0` + `CBR`, isolating all `~140+` non-Core global currencies under `is_extended=True` so exotic/hyperinflationary/non-convertible currency outages or divergences emit warnings and fall back to lockfile or curated reference FX without ever failing Friday Core CI (keeping the `16` Core European non-EUR currencies as required hard gates). Retain the hard `0.01–5.00 EUR/L` bounds in `CountryFuelLockEntry` — clamping and annotating any ultra-subsidized oil-producer states (`IR`, `VE`, etc. where domestic retail diesel falls below `€0.01/L`) at `0.010 EUR/L` so ETS2 `fuel_price` never underflows to `0.000`.
- **D-12 — Core-Focused Changelogs with Compact Global Snapshot Coverage Summary:** Keep `CHANGELOG_{SUMMER,WINTER}.md`'s detailed per-country fuel table scoped strictly to the **36 Core Vanilla+DLC countries** (matching Workshop Core scope), add a compact **Global Snapshot Coverage** summary block (total territories `200+`, live Tier 1 EU/Global counts, Tier 2 portal counts, Tier 3 curated count, and open-data attributions for all integrated Tier 1/Tier 2 sources), and keep Workshop `description.txt` concise and readable.

### 4. Internal CI OSM (`CC BY-SA`) Speed-Limit Drift Audit & `CC BY 4.0` Isolation Wall (`GLB-04`)
- **D-13 — `westnordost/osm-legal-default-speeds` Primary + Opt-In Overpass/Taginfo Spot-Checks:** Build the internal speed-limit drift auditor to compare `data/laws/countries/<iso2>.json` (`car`/`truck`/`bus` urban, local, expressway, and motorway limits) primarily against `westnordost/osm-legal-default-speeds` (OSM Wiki *Default speed limits* structured rules — fast, reliable across `200+` territories without Overpass rate-limit flakiness), plus an opt-in `--overpass` / `--taginfo` spot-check mode for targeted ISO-2 codes when maintainers request empirical highway `maxspeed` tag distributions.
- **D-14 — Dedicated Standalone Monthly Audit Workflow (Zero Git Writes + Rolling Maintainer Issue):** Run the OSM speed-limit drift audit in a dedicated standalone GitHub Actions workflow (`.github/workflows/osm-speed-audit.yml`, monthly schedule e.g. 1st Monday `07:00 UTC` + manual `workflow_dispatch`), completely decoupled from `phase-a-release.yml`. Never commit OSM data or audit outputs to Git; publish `osm_speed_drift_report.md` and `osm_speed_drift_report.json` as workflow artifacts + GitHub Step Summary, and open/update a single rolling maintainer GitHub Issue (e.g., labeled `osm-audit`) whenever unacknowledged drift is detected. — **Reversibility:** `easy` — strictly internal maintainer observability with zero release-path coupling.
- **D-15 — Clean-Room Intentional Statutory Deviation Allowlist:** Support `data/laws/speed_audit_allowlist.json` containing **zero OSM text** — strictly clean-room keys (`iso2`, `vehicle_class`, `lane_speed_class`, `field`, `statutory_rationale`, `verified_date`) recording verified intentional differences (ETS2 3-lane abstraction, seasonal Winter limits, or statutory reforms ahead of OSM Wiki). Separate allowlisted differences into an "Acknowledged Statutory Differences" section so only new/unacknowledged drift triggers maintainer review alerts.
- **D-16 — Isolated `src/ets2v2/audit/` Subpackage, AST DAG Wall & Automated License-Taint Gate:** Place the OSM drift auditor in a dedicated isolated subpackage `src/ets2v2/audit/` (exposed via `ets2v2 audit osm-speeds` and unlocked in `tests/test_cli_scaffold.py::test_active_phase_only_package_layout`). Enforce two hard automated gates in `pytest` and CI:
  1. **AST DAG Isolation Wall:** Extend `test_phase4_ast_dag_isolation_walls` (for Phase 5) to verify **zero** non-audit subpackages (`vfs`, `sii`, `baseline`, `registry`, `normalize`, `fetch`, `package`, `validate`, `merge`, `publish`) ever import `ets2v2.audit`.
  2. **Automated Provenance & License-Taint Gate:** Add a dedicated test & validator scan across `data/laws/`, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, generated `realism-snapshot-{summer|winter}.json`, and built Workshop/local mod packages verifying zero forbidden license/source markers (`CC BY-SA`, `ODbL`, `openstreetmap`, `osm-legal-default-speeds`, `GlobalPetrolPrices`, `CC BY-NC-ND`, `MyLPG`, `IEA`) ever enter any `CC BY 4.0` input or output artifact.

### Claude's Discretion
- Exact module decomposition inside `src/ets2v2/fetch/` (e.g. `global_tier1.py`, `tier2_portals.py`, `_html.py`), `src/ets2v2/audit/` (e.g. `models.py`, `osm_speeds.py`, `overpass.py`, `taint.py`), and `src/ets2v2/normalize/` while keeping all AST DAG isolation walls intact.
- Exact JSON schemas for `data/mappings/currencies.json`, `data/curated/tier3_fuel_baselines.json`, and `data/laws/speed_audit_allowlist.json`, plus any optional additive fields on `CountryFuelLockEntry` / `FetchRunReport` that preserve `PricesLockfile` `schema_version: 1` compatibility.
- Exact `ets2v2 fetch` filter flags (`--no-global`, `--no-tier2`, etc.) and `ets2v2 audit osm-speeds` CLI flags (`--iso2`, `--overpass`, `--taginfo`, `--out-md`, `--out-json`, `--allowlist`, `--timeout`).
- Exact country list (`~215–225` ISO-3166-1 territories) verified during Phase 5 research, ensuring 100% coverage of UN states, inhabited map-combo territories, and all ISO-2 targets in `data/mappings/country_aliases.json`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or executing Phase 5:**

### Project & Milestone Specs
- `.planning/PROJECT.md` — Core value, legally clean 3-tier global pipeline, and explicit license exclusions (`GlobalPetrolPrices.com`, `MyLPG.eu`, paid `IEA`, `CC BY-SA` OSM redistribution ban).
- `.planning/REQUIREMENTS.md` — Requirements `GLB-01`, `GLB-02`, `GLB-03`, `GLB-04` and Out-of-Scope exclusions.
- `.planning/ROADMAP.md` — Phase 5 goal, 4 success criteria, research flag (`gsd-phase-researcher` recommended), and plan breakdown (`05-01`..`05-04`).
- `.planning/STATE.md` — Locked decisions and operational dependencies (`EIA_API_KEY`, `OPINET_API_KEY`, `TANKERKOENIG_API_KEY`).
- `.planning/phases/03-open-european-fuel-fx-pipeline-zero-dds-totem-engine/03-CONTEXT.md` — Two-stage `fetch` vs offline `build` contract (`D-05`), circuit breaker (`D-06`), FX cross-validation (`D-07`), outage/staleness policy (`D-08`), frozen `RealismSnapshot` v1 (`D-13`), canonical grade keys (`D-14`), and changelog fuel/alert/attribution format (`D-16`).
- `.planning/phases/04-promods-companion-builder-local-map-combo-composer/04-CONTEXT.md` — `76`-territory expansion pattern (`D-01`), frozen `RealismSnapshot` v1 + `country_aliases.json` (`D-02`), rolling `snapshots-latest` release (`D-03`), and AST offline DAG isolation walls.

### Research & Codebase Maps
- `.planning/research/FEATURES.md` — Verified Tier 1 global APIs (`US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`), Tier 2 national portals (`CH`, `MD`, `MK`, `RU`, `IL`, `SA`, `JO`, `AE`, `EG`, `ZA`, `KE`, `NG`, `ID`), Tier 3 regions, and OSM `CC BY-SA 2.0` audit boundary.
- `.planning/research/SUMMARY.md` — Synthesized 3-tier open-data table, legal rejections, and Phase 5 research targets.
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/STRUCTURE.md` — Acyclic package DAG and offline/online boundary rules.

### Existing Code & Data Schemas
- `src/ets2v2/fetch/pipeline.py`, `src/ets2v2/fetch/models.py`, `src/ets2v2/fetch/national.py`, `src/ets2v2/fetch/ec_bulletin.py`, `src/ets2v2/fetch/fx.py`, `src/ets2v2/fetch/http.py` — Existing online fetch orchestrator, provider status models, secret redaction (`redact_url_secrets`), and retry-capable HTTP client.
- `src/ets2v2/normalize/currencies.py`, `src/ets2v2/normalize/fx.py`, `src/ets2v2/normalize/fuel.py`, `src/ets2v2/normalize/lockfile.py`, `src/ets2v2/normalize/models.py` — Currency/sanity-band registry, `is_extended=True` FX cross-validator, `0.01–5.00 EUR/L` & `±25%` WoW normalizer, `PricesLockfile` v1 I/O, and `evaluate_lockfile_staleness()`.
- `src/ets2v2/registry/models.py`, `src/ets2v2/registry/loader.py`, `src/ets2v2/registry/snapshot.py` — `CountryLawRecord`, `CountryMappingRegistry`, and frozen `schema_version: 1` `RealismSnapshot` builder.
- `data/mappings/ets2_countries.json`, `data/mappings/country_aliases.json`, `data/laws/countries/*.json`, `state/prices.lock.json` — Existing `76`-territory law registry, map-mod aliases, and committed price/FX lockfile.
- `src/ets2v2/publish/changelog.py`, `src/ets2v2/package/metadata.py`, `.github/workflows/phase-a-release.yml` — Changelog fuel table, alert/attribution rendering, Workshop `description.txt`, and Friday CI release pipeline.
- `tests/test_cli_scaffold.py` — Active package layout gate (`test_active_phase_only_package_layout`), dependency pin assertions (`test_pyproject_metadata_and_quality_gates`), and AST DAG isolation walls (`test_phase4_ast_dag_isolation_walls`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ets2v2/fetch/http.py` (`create_http_client`, `redact_url_secrets`, `DEFAULT_TIMEOUT_SECONDS`) — Reusable retry-safe `httpx.Client` factory and URL/query-string secret redactor (ready for `EIA_API_KEY` and `OPINET_API_KEY` query-parameter redaction).
- `src/ets2v2/normalize/fx.py` (`cross_validate_fx_rates(..., include_extended=True)`) — Already separates required Core European FX currencies from `is_extended=True` extended currencies with sanity envelopes, validator chains, and reference FX fallback; scales cleanly to `~155+` currencies once backed by `data/mappings/currencies.json`.
- `src/ets2v2/normalize/fuel.py` (`normalize_country_fuel_prices`, `compute_secondary_grade_prices`) — Already enforces hard `0.01–5.00 EUR/L` bounds, `±25%` WoW circuit breaker with `--allow-jump`, and canonical `FuelGrade` secondary spreads.
- `src/ets2v2/registry/snapshot.py` (`build_realism_snapshot`) — Already handles arbitrary `vanilla_1_62: false` territories dynamically (`imperial_units = law.speed_unit == "mph"`), injecting `state/prices.lock.json` prices into `schema_version: 1` snapshots without schema changes.
- `src/ets2v2/publish/changelog.py` (`_render_fuel_summary_table`) — Already filters the detailed per-country fuel table to `VANILLA_36_ISO2S` when `snapshot.countries` exceeds 36 countries, making the `200+` Global Snapshot Coverage summary block a clean additive extension.

### Established Patterns
- Frozen Pydantic v2 models (`ConfigDict(strict=True, frozen=True, extra="forbid")`), deterministic UTF-8 no-BOM LF sorted JSON, strict `basedpyright` (`strict` mode, Python `3.12`), `ruff` (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`), and 100% offline `pytest` (`uv run --offline pytest` using `httpx.MockTransport` fixtures).
- AST DAG isolation wall scanner (`tests/test_cli_scaffold.py::_scan_forbidden_imports`) — ready to extend for Phase 5's `audit/` subpackage wall.
- `CountryMappingEntry.country_id: int | None` (relaxed in Phase 4 for `vanilla_1_62: false`) — directly supports all `~215–225` global territories without inventing fake ETS2 numeric `country_id`s.

### Integration Points
- `data/mappings/currencies.json` & `data/curated/tier3_fuel_baselines.json` — New clean-room versioned data registries backing `src/ets2v2/normalize/` (`D-10`).
- `data/laws/countries/<iso2>.json`, `data/mappings/ets2_countries.json`, `data/laws/speed_audit_allowlist.json` — Expanded to `~215–225` canonical territories plus clean-room OSM audit allowlist (`D-09`, `D-15`).
- `src/ets2v2/fetch/` — Add non-EU Tier 1 collectors (`GLB-01`), Tier 2 guarded national portal scrapers (`GLB-02`), separate EU vs Global Tier 1 outage counters, and `--no-global` / `--no-tier2` CLI flags (`D-01`..`D-07`).
- `src/ets2v2/normalize/lockfile.py` & `src/ets2v2/publish/changelog.py` — Tier-aware staleness evaluation (`D-08`), compact Global Snapshot Coverage block, and expanded open-data attributions (`D-12`).
- `src/ets2v2/audit/` & `.github/workflows/osm-speed-audit.yml` — Isolated OSM speed-limit drift auditor (`D-13`..`D-16`), standalone monthly CI workflow, and provenance/license-taint gate (`D-16`).
- `.github/workflows/phase-a-release.yml` — Pass optional `EIA_API_KEY` and `OPINET_API_KEY` secrets to `ets2v2 fetch` (`D-01`) and update step summary counters for EU vs Global Tier 1 / Tier 2 feeds.

</code_context>

<specifics>
## Specific Ideas

- **Research targets for `gsd-phase-researcher`:**
  - Verify live request/response schemas, query parameters, auth headers/params, and unit/grade labels for all 8 non-EU Tier 1 endpoints (`US EIA v2` petroleum retail prices route, `BR ANP` weekly CSV URL/columns/Latin-1 encoding, `AR Energía` CKAN/CSV resource discovery, `CO SICOM` Socrata/datos.gov.co resource ID & columns, `CL CNE` v4/v3 API auth/public endpoints, `MY OpenDOSM` `api.data.gov.my/data-catalogue?id=fuelprice` JSON schema, `JP METI` weekly `.xlsx`/CSV discovery & national average row layout, and `KR Opinet` `avgAllPrice.do` JSON/XML response schema).
  - Probe live accessibility, charsets, and machine-readable structures for all candidate Tier 2 national portals (`CH` BFS/LIK, `MD` ANRE, `MK` ERC, `RU` Rosstat, `IL` MoE/CBS, `JO` MEMR, `AE` MOEI, `ZA` DMRE/CEF, `KE` EPRA, `NG` NBS, `ID` Pertamina/ESDM, `SA` Aramco, `EG` FAPC, `IS` Orkusetur) — explicitly classifying any Cloudflare/CAPTCHA/JS-only/scanned-PDF portals as Tier 3 per `D-05` with evidence.
  - Verify the exact `~215–225` territory ISO-3166-1 roster (every UN state + inhabited territories + all ISO-2 targets in `data/mappings/country_aliases.json` and global map combos), their `~155+` ISO-4217 currencies + Frankfurter v2 / `fawazahmed0` coverage + sanity envelopes (including any recent redenominations or currency pegs), and verify `westnordost/osm-legal-default-speeds` artifact/release structure + Overpass/Taginfo query templates for `GLB-04`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed strictly within Phase 5 boundaries. Full-auto SteamCMD Workshop publishing and the hidden-item TOTP spike remain deferred to V2 (`PUB-V2-01`, `PUB-V2-02`).

</deferred>

---

*Phase: 05-global-tier-1-2-3-coverage-internal-osm-audit*
*Context gathered: 2026-11-25*
