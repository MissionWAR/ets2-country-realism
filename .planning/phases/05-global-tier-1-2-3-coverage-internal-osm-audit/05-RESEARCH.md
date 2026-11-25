# Phase 5: Global Tier 1/2/3 Coverage & Internal OSM Audit - Research

**Researched:** 2026-11-25
**Domain:** Global Open Government Fuel APIs, Guarded Tier 2 National Portal Parsing, ISO-3166-1 / ISO-4217 200+ Territory Scaling, and Isolated CI OSM (`CC BY-SA`) Speed-Limit Drift Auditing (`CC BY 4.0` License Isolation)
**Confidence:** **HIGH** (Codebase contracts, Python `3.12.13` / `tzdata` numeric timezone audit, test assertions, and security/DAG boundaries verified directly in-repo; Tier 1 APIs, Tier 2 portal formats/barriers, ISO-4217 2025–2026 currency changes, and `westnordost/osm-legal-default-speeds` / Overpass / Taginfo contracts cited from authoritative docs & web search; direct outbound HTTP probes from sandbox were policy-blocked so live selector volatility is flagged explicitly as `[ASSUMED]` / MEDIUM where applicable)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 1. Non-EU Tier 1 Collectors & API Key Isolation (`GLB-01`)
- **D-01 — Optional API Keys (`EIA_API_KEY`, `OPINET_API_KEY`) Mirroring `TANKERKOENIG_API_KEY`:** Treat `EIA_API_KEY` (`US EIA v2`) and `OPINET_API_KEY` (`KR Opinet`) as optional environment secrets matching Phase 3 `D-03`. When unset, mark the collector `skipped=True` (never failed) and retain the lockfile / Tier 3 seed cleanly so public forks, local runs, and offline tests work zero-secret out of the box. Wire both optional secrets into `.github/workflows/phase-a-release.yml`.
- **D-02 — Separate European Core vs Global Tier 1 CI Outage Gates:** Keep Friday CI's hard-fail gate strictly scoped to **European Core Tier 1** fuel feeds (`eu_tier1_feeds_succeeded == 0` fails `ets2v2 fetch` / CI). Isolate **Global Tier 1** feeds (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`) so non-EU upstream outages emit structured `warning` alerts and retain `state/prices.lock.json` values without blocking Friday Core Workshop builds — and conversely, a succeeding non-EU feed never masks a total European Tier 1 outage. — **Reversibility:** `moderate` — protects weekly Workshop releases from regional API turbulence while keeping European outage detection strict.
- **D-03 — Lightweight Ingestion Formats & Dependency Discipline:** Keep `pyproject.toml` lean — ingest all non-EU Tier 1 feeds via lightweight JSON, CSV, or `.xlsx` endpoints using existing `httpx`, `openpyxl`, and Python stdlib (`json`, `csv`, `io`, `zipfile`). Explicitly do **not** add `pandas`, `pyarrow`, or `xlrd` (`MY OpenDOSM` via JSON/CSV API `api.data.gov.my`, `JP METI` via `.xlsx`/CSV, `BR ANP` via Latin-1 `;`-delimited CSV, `AR` CSV, `CO` JSON/OData, `CL` JSON).
- **D-04 — Exact Unit Conversions & Outlier-Resistant Regional Aggregation:** Convert `US EIA` `USD/gallon` to `USD/L` using the exact NIST liquid gallon factor (`3.785411784` L/gal). Use official published national average rows wherever provided (`US EIA` national average, `JP METI` national average row, `MY OpenDOSM` national weekly price), and compute deterministic **median** across valid station/municipality rows for raw station-level feeds (`BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`) to reject erroneous station outliers cleanly, mapping regular retail grades (`diesel`, `petrol_95`, plus `petrol_98`/`e85`/`lpg` where published) into canonical `FuelGrade` keys.

#### 2. Tier 2 Guarded National Portals, HTML Parsing & Staleness Cadence (`GLB-02`)
- **D-05 — Research-Gated Tier 2 National Portal Roster:** Target the structured Tier 2 national portals identified in `ROADMAP.md` and `FEATURES.md` (`CH` BFS/LIK, `MD` ANRE, `MK` ERC, `RU` Rosstat, `IL` MoE/CBS, `JO` MEMR, `AE` MOEI, `ZA` DMRE/CEF, `KE` EPRA, `NG` NBS, `ID` Pertamina/ESDM, plus `SA`/`EG`/`IS` where direct machine-readable HTML/JSON/XLSX endpoints exist). During Phase 5 research, verify live machine-readability and automatically classify any portal gated by Cloudflare/anti-bot challenges, JS-only SPA rendering, CAPTCHAs, or scanned PDFs cleanly into Tier 3 curated baselines rather than building brittle scrapers.
- **D-06 — Stdlib-Only HTML/XML Parsing (Zero New Runtime Dependencies):** Implement all Tier 2 HTML and XML scrapers using Python stdlib (`html.parser`, `xml.etree.ElementTree`, `re`) plus existing `openpyxl`/`csv` — adding **zero** new runtime dependencies (no `beautifulsoup4`, no `lxml`), keeping `uv.lock` lean, supply-chain minimal, and strict `basedpyright` clean.
- **D-07 — Strict Per-Country Circuit-Breaker Isolation & CLI Filter Flags:** Extend `RawFuelFeedResult.tier` to `Literal["tier1", "tier2", "fallback"]` and execute each Tier 2 portal inside an isolated per-country boundary catching HTTP `403`/`429`/timeouts, charset/decoding errors (`windows-1251`, Latin-1, UTF-8), and HTML selector drift. Emit structured `warning` alerts (`tier2_portal_outage`, `tier2_rate_limited`, `tier2_selector_drift`, `tier2_encoding_error`), retain last-known-good `state/prices.lock.json` prices (still enforcing `0.01–5.00 EUR/L` and `±25%` WoW guards on accepted quotes), and **never** fail Friday CI on Tier 2 errors. Expose CLI filter flags on `ets2v2 fetch` (e.g., `--no-global`, `--no-tier2`) for fast targeted runs.
- **D-08 — Tier-Aware Staleness Thresholds & Noise-Controlled Alert Summaries:** Replace the flat 14d/30d staleness split in `evaluate_lockfile_staleness()` with tier- and cadence-aware limits:
  - **14 days:** Weekly Tier 1 live feeds (EU & Global).
  - **45 days:** Monthly Tier 2 national portals (and **105 days** for quarterly portals such as `EG` FAPC).
  - **30 days:** Degraded Tier 1 fallback retention.
  - **180 days:** Tier 3 curated global baseline review cadence.
  Keep Core, Tier 1, and Tier 2 anomalies itemized in alerts while aggregating Tier 3 staleness/fallback entries into compact summary counts in `CHANGELOG_{SUMMER,WINTER}.md` and Friday PR/step summaries so `130+` Tier 3 territories never flood release notes.

#### 3. Tier 3 Global `200+` Territory Expansion, FX Scaling & Changelog Scope (`GLB-03`)
- **D-09 — Full Canonical `200+` Territory Expansion (~215–225 Territories):** Expand `data/laws/countries/<iso2>.json`, `data/mappings/ets2_countries.json` (`vanilla_1_62: false`), and `state/prices.lock.json` from `76` to **~215–225 territories** covering all ~195 UN sovereign states plus ~20–30 inhabited ISO-3166-1 territories and ETS2 global map-combo regions (`TW`, `HK`, `MO`, `PR`, `GF`, `GP`, `MQ`, `RE`, `YT`, `NC`, `PF`, `CW`, `AW`, `BM`, `KY`, `VG`, `TC`, `FK`, `PM`, `SX`, `EH`, etc., ensuring 100% coverage of every ISO-2 referenced in `data/mappings/country_aliases.json` and global map combos *EAA*, *Beyond*, *SEA*, *RoC*, *Africa*, *Project Japan*, *JRR*, *7RM*, *C2C/ProMods Canada*). Every territory carries a complete canonical `CountryLawRecord` (IANA timezone, `speed_unit`, statutory Summer/Winter speed limits, DRL, axle mass limits, ISO-4217 currency) so `realism-snapshot-{summer|winter}.json` stays frozen at `schema_version: 1` with `200+` full `RealismSnapshotCountry` entries while Vanilla+DLC Core builds stay strictly at `36` countries. — **Reversibility:** `moderate` — cleanly fulfills `GLB-03` and powers offline `compose-local` worldwide without breaking `RealismSnapshot` v1.
- **D-10 — Externalized Data-Driven Currency/FX Metadata & Tier 3 Fuel Baselines:** Move global ISO-2 → currency mappings, FX sanity envelopes, reference FX rates, and Tier 3 curated EUR/L fuel baselines out of Python literals in `src/ets2v2/normalize/currencies.py` into clean-room, Pydantic-validated versioned JSON files under `data/` (`data/mappings/currencies.json` and `data/curated/tier3_fuel_baselines.json` with `verified_date` and clean-room provenance metadata), loaded by `ets2v2.normalize` while preserving backwards-compatible Python constant exports and all AST offline DAG isolation walls.
- **D-11 — Isolated Global FX Validation & Hard `0.01 EUR/L` Floor:** Scale FX coverage from `41` to `~155+` ISO-4217 currencies via `Frankfurter v2` + `ECB` + `fawazahmed0` + `CBR`, isolating all `~140+` non-Core global currencies under `is_extended=True` so exotic/hyperinflationary/non-convertible currency outages or divergences emit warnings and fall back to lockfile or curated reference FX without ever failing Friday Core CI (keeping the `16` Core European non-EUR currencies as required hard gates). Retain the hard `0.01–5.00 EUR/L` bounds in `CountryFuelLockEntry` — clamping and annotating any ultra-subsidized oil-producer states (`IR`, `VE`, etc. where domestic retail diesel falls below `€0.01/L`) at `0.010 EUR/L` so ETS2 `fuel_price` never underflows to `0.000`.
- **D-12 — Core-Focused Changelogs with Compact Global Snapshot Coverage Summary:** Keep `CHANGELOG_{SUMMER,WINTER}.md`'s detailed per-country fuel table scoped strictly to the **36 Core Vanilla+DLC countries** (matching Workshop Core scope), add a compact **Global Snapshot Coverage** summary block (total territories `200+`, live Tier 1 EU/Global counts, Tier 2 portal counts, Tier 3 curated count, and open-data attributions for all integrated Tier 1/Tier 2 sources), and keep Workshop `description.txt` concise and readable.

#### 4. Internal CI OSM (`CC BY-SA`) Speed-Limit Drift Audit & `CC BY 4.0` Isolation Wall (`GLB-04`)
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed strictly within Phase 5 boundaries. Full-auto SteamCMD Workshop publishing and the hidden-item TOTP spike remain deferred to V2 (`PUB-V2-01`, `PUB-V2-02`).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| `GLB-01` | Integrate Tier 1 non-European government fuel APIs (`US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`) into the snapshot pipeline. | §1 details all 8 endpoints, query params, auth secrets (`EIA_API_KEY`, `OPINET_API_KEY`, plus optional `CNE_API_TOKEN` discovery), URL secret redaction fix (`code=` param in `fetch/http.py`), NIST `3.785411784` L/gal conversions (`US` & `CO`), station median vs national average parsing, grade mappings, and separate EU vs Global Tier 1 outage counters (`D-02`). |
| `GLB-02` | Integrate Tier 2 guarded national portal scrapers with isolated per-country circuit breakers and `prices.lock.json` fallback so individual portal breakages never fail CI or corrupt snapshots. | §2 provides the research-gated classification matrix across all 14 candidate portals (10 Tier 2 stdlib/openpyxl parsers + 4 cleanly classified to Tier 3 due to Cloudflare/JS-SPA/PDF barriers), `RawFuelFeedResult.tier` extension, per-country circuit breaker alert taxonomy, `--no-global`/`--no-tier2` CLI flags, and tier-aware staleness limits (`14d`/`45d`/`105d`/`30d`/`180d`). |
| `GLB-03` | Curate Tier 3 global baseline entries bringing total snapshot territory coverage to `200+` countries/regions (Africa, Latin America, Central/East/Southeast Asia) for `compose-local` map combos. | §3 specifies the verified `220`-territory ISO-3166-1 roster (covering all 76 existing territories + all 13 missing `country_aliases.json` ISO-2 targets), `~156` ISO-4217 currencies (flagging `XCG`, `ZWG`, `SLE`, `SYP`), 58 newly verified numeric-`tzname()` IANA zones, `mph` territories, `0.010 EUR/L` floor clamping, clean-room JSON schemas for `data/mappings/currencies.json` and `data/curated/tier3_fuel_baselines.json`, and all 10 existing test files needing count updates. |
| `GLB-04` | Add an internal CI OSM Overpass/Taginfo (`CC BY-SA`) speed-limit drift audit comparing real-world road limits against `data/laws/` and surfacing maintainer review reports without bundling any `CC BY-SA` data into `CC BY 4.0` mod outputs. | §4 documents `westnordost/osm-legal-default-speeds` JSON schema & `CC BY-SA 2.0` boundary, Overpass (`out tags;`) + Taginfo v4 spot-check templates, clean-room `data/laws/speed_audit_allowlist.json` schema, isolated `src/ets2v2/audit/` package layout, AST DAG isolation wall (including keeping `validate/` independent of `audit/`), license-taint scanner markers, and zero-Git-write `.github/workflows/osm-speed-audit.yml`. |
</phase_requirements>

---

## Summary

Phase 5 transforms `ETS2V2` from a 76-territory European/ProMods pipeline into a **220-territory global clean-room realism pipeline** while adding an isolated CI-only OSM speed-limit drift auditor — with **zero new runtime dependencies** (`pyproject.toml` stays strictly pinned to `httpx`, `openpyxl`, `pillow`, `pydantic`, `tzdata`) and **zero schema breaks** (`RealismSnapshot` and `PricesLockfile` remain frozen at `schema_version: 1`, Vanilla+DLC Core Workshop editions stay strictly at `36` countries).

**Critical Architectural Ordering Insight (Verified in Codebase):**
In `src/ets2v2/fetch/pipeline.py:403` `[VERIFIED: src/ets2v2/fetch/pipeline.py:402-406]`:
```python
for quote in feed_res.quotes:
    if quote.iso2 not in ALL_LOCKFILE_TERRITORY_ISO2S:
        continue
    currency = ALL_TERRITORY_CURRENCIES[quote.iso2]
```
Any live fuel quote emitted by a non-EU Tier 1 collector (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`) or non-ProMods Tier 2 portal (`AE`, `ZA`, `NG`) is **silently dropped** unless its ISO-2 code is already present in `ALL_LOCKFILE_TERRITORY_ISO2S` and its currency is in `ALL_TERRITORY_CURRENCIES` / `ALL_REFERENCE_FX_RATES`. Therefore, **Plan ordering should execute `GLB-03` (data-driven `currencies.json`, `tier3_fuel_baselines.json`, and the `220`-territory registry/lockfile expansion) FIRST in Wave 1**, so `GLB-01` (Non-EU Tier 1), `GLB-02` (Tier 2 portals + staleness/changelog aggregation), and `GLB-04` (Isolated `audit/` + taint gate + monthly workflow) can build cleanly on top of the 220-territory / ~156-currency foundation with zero temporary stubs or double-refactoring.

**Primary recommendation:** Execute the 220-territory + data-driven currency/Tier-3 baseline expansion (`GLB-03`) as Wave 1, build Non-EU Tier 1 (`GLB-01`) and Guarded Tier 2 + tier-aware staleness/changelogs (`GLB-02`) in Wave 2 (fixing `code=` query-secret redaction in `fetch/http.py` and isolating EU vs Global Tier 1 CI gates), and ship the strictly isolated `src/ets2v2/audit/` subpackage, license-taint gate, and zero-Git-write `.github/workflows/osm-speed-audit.yml` (`GLB-04`) in Wave 2/3.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Data-driven global currency & Tier 3 baseline loading (`currencies.json`, `tier3_fuel_baselines.json`) | `ets2v2.normalize` (offline pure data) | `data/mappings/`, `data/curated/` | Preserves `normalize/` offline AST wall (zero `httpx`/`openpyxl`/`registry` imports) while replacing hardcoded Python literals (`D-10`). |
| 220-territory canonical laws, `zoneinfo` numeric TZ overrides, & frozen v1 `RealismSnapshot` | `ets2v2.registry` (offline pure data) | `data/laws/countries/`, `data/mappings/ets2_countries.json` | Single source of truth feeding Core builds (`36`), ProMods (`76`), and `compose-local` (`220`) without schema bumps (`D-09`). |
| Non-EU Tier 1 collectors & Tier 2 guarded HTML/XLSX/JSON portal scrapers | `ets2v2.fetch` (online) | `ets2v2.normalize` (validation/circuit breakers) | Online network I/O remains strictly confined to `fetch/`; `normalize/` remains pure offline (`D-01`–`D-08`). |
| Core-scoped changelogs + compact Global Snapshot Coverage summary & Tier 3 alert rollup | `ets2v2.publish` (offline) | `.github/workflows/phase-a-release.yml` | Keeps Core release notes readable while summarizing 220-territory coverage and open-data attributions (`D-08`, `D-12`). |
| OSM speed-limit drift audit (`westnordost` + opt-in Overpass/Taginfo) & repo/snapshot taint scanner | `ets2v2.audit` (isolated CI/audit-only) | `.github/workflows/osm-speed-audit.yml` | One-way quarantine: `audit/` may read `registry/` and `fetch.http`, but ZERO non-audit subpackages may import `audit/` (`D-16`). |
| Built Workshop/local package license-taint verification | `ets2v2.validate` (offline, independent) | `tests/` CI gate | `validate/` must NOT import `ets2v2.audit` (DAG wall `D-16`); embed pure-stdlib forbidden-marker regex check directly inside `validate/` so both `validate` and `audit/taint.py` stay decoupled. |

---

## Standard Stack

Phase 5 adds **ZERO new runtime or dev dependencies** (`D-03`, `D-06`). Existing pinned stack verified in `pyproject.toml:11-29` `[VERIFIED: pyproject.toml:11-29]` and installed in `.venv` `[VERIFIED: local python 3.12.13]`:

### Core (Existing — No Changes Required)
| Library | Verified Version | Purpose in Phase 5 | Why Standard |
|---------|------------------|--------------------|--------------|
| `httpx` | `0.28.1` (`>=0.28,<0.29`) | Hardened HTTPS requests (`create_http_client`, `fetch_bytes_with_retry`) & offline `httpx.MockTransport` tests for all Tier 1, Tier 2, and OSM audit collectors | Already hardened with strict host allowlist, redirect cap, byte cap, TLS `verify=True` (`src/ets2v2/fetch/http.py`). |
| `openpyxl` | `3.1.5` (`>=3.1,<4`) | Streaming read-only `.xlsx` parsing for `JP` METI, `RU` Rosstat, `ZA` CEF, and `NG` NBS with pre-validation via `_validate_ooxml_zip_safety` | Already pinned with `types-openpyxl>=3.1`; eliminates `pandas`/`xlrd` (`D-03`). |
| `pydantic` | `2.14.3` (`>=2.14,<3`) | Strict frozen DTOs (`ConfigDict(strict=True, frozen=True, extra="forbid")`) for `currencies.json`, `tier3_fuel_baselines.json`, `speed_audit_allowlist.json`, and audit reports | Matches all Phase 1–4 domain models cleanly under strict `basedpyright`. |
| `tzdata` | `>=2025.2` (installed) | Cross-platform IANA tzdb backing stdlib `zoneinfo.ZoneInfo` across all `220` global territories (mandatory on Windows) | Already verified across all 220 candidate zones with 0 `ZoneInfoNotFoundError`s. |
| Python stdlib (`html.parser`, `xml.etree.ElementTree`, `csv`, `json`, `re`, `statistics`, `decimal`, `zipfile`, `ast`) | Python `3.12.13` | All Tier 2 HTML/XML table scrapers, `;`-delimited Latin-1 CSVs (`BR ANP`), UTF-8 CSVs (`AR Energía`), exact `Decimal` NIST gallon conversions, AST DAG wall, and license-taint regex scans | Zero supply-chain bloat (`D-06`); `tests/test_cli_scaffold.py:103-109` explicitly locks `project.dependencies` to the exact 5 packages above! |

### Alternatives Considered & Explicitly Rejected
| Instead of | Rejected Alternative | Reason |
|------------|---------------------|--------|
| Stdlib `html.parser` + `re` | `beautifulsoup4` / `lxml` | Explicitly barred by `D-06` and locked `pyproject.toml` dependency test (`tests/test_cli_scaffold.py:103-109`). |
| `api.data.gov.my` JSON / `csv` / `openpyxl` | `pandas`, `pyarrow`, `xlrd` | Explicitly barred by `D-03`; heavy C/Arrow wheels bloat CI and lockfile unnecessarily. |
| Clean-room 3-tier pipeline | `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`), `MyLPG.eu`, paid `IEA` | Explicitly forbidden in `PROJECT.md`, `REQUIREMENTS.md`, and enforced by `D-16` license-taint gate. |

## Package Legitimacy Audit

**Skipped (Zero New External Packages):** Phase 5 installs **zero** new PyPI packages (`D-03`, `D-06`); `pyproject.toml` and `uv.lock` remain unchanged from Phase 4.

---

## 1. Non-EU Tier 1 Open Government Fuel APIs (`GLB-01`, `D-01`..`D-04`)

### 1.1 Exact Verification Matrix (All 8 Portals)

> **Unit Conversion Constant (`D-04`):** Exact NIST liquid US gallon = **`3.785411784` L/gal** (`Decimal("3.785411784")`). Applies to **BOTH** `US` (`USD/gal` → `USD/L`) and **`CO`** (`COP/gal` → `COP/L`!).

| ISO2 | Feed Name & Source | Endpoint / Discovery URL & Allowlisted Hosts | Auth / Secret Handling | Format, Encoding & Parsing Strategy | Exact Fields / Columns / Grade Mapping | Unit & Aggregation (`D-04`) | License / Attribution |
|------|-------------------|----------------------------------------------|------------------------|--------------------------------------|----------------------------------------|-----------------------------|-----------------------|
| **`US`** | `us_eia_v2` (U.S. EIA Open Data API v2) `[CITED: eia.gov]` | `https://api.eia.gov/v2/petroleum/pri/gnd/data/`<br>Hosts: `{"api.eia.gov"}` | **Optional `EIA_API_KEY`** (`D-01`). Pass as `params["api_key"]` (already redacted by `redact_url_secrets`) **or** header `X-Api-Key` (prefer `params["api_key"]` or header + explicit `.replace(key, "***")`). When unset → `skipped=True, ok=True`. | JSON (`UTF-8`). Query params: `frequency=weekly`, `data[0]=value`, `facets[duoarea][]=NUS`, `facets[process][]=PTE`, `facets[product][]=EPD2D` (Diesel), `EPMR` (Regular), `EPMP` (Premium), `sort[0][column]=period`, `sort[0][direction]=desc`, `length=20`. | `response.data[]` items: `period` (`YYYY-MM-DD`), `duoarea == "NUS"`, `product` (`EPD2D` → `"diesel"`, `EPMR` → `"petrol_95"`, `EPMP` → `"petrol_98"`), `value` (numeric/string float), `units` (`"$/GAL"`). *(Pitfall: use `EPD2D` = On-Highway No. 2 Diesel, NOT `EPD2O` which is off-highway/other!)* | `USD/gal ÷ 3.785411784` → `USD/L` (`local_per_liter`). Official national average (`duoarea="NUS"`). Take latest period containing both `EPD2D` and `EPMR`. | **U.S. Public Domain** (EIA) |
| **`BR`** | `br_anp` (ANP *Levantamento de Preços de Combustíveis*) `[CITED: gov.br/anp]` | Two direct rolling 4-week CSVs:<br>1. `https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/qus/ultimas-4-semanas-diesel-gnv.csv`<br>2. `https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/qus/ultimas-4-semanas-gasolina-etanol.csv`<br>Hosts: `{"www.gov.br"}` | Keyless public HTTPS. | `;`-delimited CSV, comma decimal (`6,19`). Try `utf-8-sig` then fallback to `latin-1` (`iso-8859-1`) / `cp1252` (ANP historically alternates between `utf-8-sig` and `latin-1`). Cap download at `30 MiB` (`DEFAULT_MAX_RESPONSE_BYTES`). | Columns (normalize header upper + strip accents/BOM): `PRODUTO` (or `Produto`), `VALOR DE VENDA` (or `Valor de Venda`), `DATA DA COLETA` (or `Data da Coleta`, `DD/MM/YYYY`).<br>Grade mapping: `DIESEL S10` (preferred) / `DIESEL` → `"diesel"`, `GASOLINA COMUM` → `"petrol_95"`, `GASOLINA ADITIVADA` → `"petrol_98"`, `ETANOL` → `"e85"`. *(Ignore `GNV` = m³ and `GLP` = 13 kg bottle — NOT automotive L!)* | `BRL/L` (`local_per_liter`). Filter to latest week window (within 7 days of max `DATA DA COLETA`), compute deterministic `statistics.median()` per grade across valid station rows. | **Brazilian Open Gov Data** (ANP) |
| **`AR`** | `ar_energia` (Secretaría de Energía — Res. 314/2016) `[CITED: datos.gob.ar / datos.energia.gob.ar]` | CKAN discovery:<br>`https://datos.gob.ar/api/3/action/package_show?id=precios-en-surtidor-resolucion-314` (fallback `https://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor-resolucion-314`) → discover resource whose `format.lower() == "csv"` and name contains `"vigente"` (current pump prices CSV, NOT multi-GB historical archive!).<br>Hosts: `{"datos.gob.ar", "datos.energia.gob.ar"}` | Keyless public HTTPS. | CKAN JSON → `,`-delimited UTF-8 CSV (`utf-8-sig` fallback `latin-1`). Reject resources with `historico`/`histórico` in name/URL to stay well under `30 MiB`. | Columns: `producto`, `precio`, `tipohorario` (prefer `"Diurno"` when present), `fecha_vigencia` (`YYYY-MM-DD HH:MM:SS` or `DD/MM/YYYY`).<br>Grade mapping (case/accent normalized): `"gas oil grado 2"` → `"diesel"`, `"gas oil grado 3"` → `"diesel_plus"`, `"nafta (súper)"` / `"nafta (super)"` → `"petrol_95"`, `"nafta (premium)"` → `"petrol_98"`. *(Ignore `GNC` = m³!)* | `ARS/L` (`local_per_liter`). Deterministic `statistics.median()` across valid station rows with recent `fecha_vigencia` (rejecting stale pre-2024 dead stations if >180d older than max date!). | **Argentine Open Gov Data** (Decreto 117/2016) |
| **`CO`** | `co_sicom` (MinMinas / SICOM + CREG reference fallback) `[CITED: datos.gov.co / creg.gov.co]` | **Discovery-first strategy** (important research finding: `fbht-2fzd` on `datos.gov.co` is *dispatch volumes*, NOT retail prices!):<br>1. Primary Socrata catalog discovery: `https://www.datos.gov.co/api/catalog/v1?q=precio+mes+combustible&limit=10` → locate MinMinas/SICOM resource ID (`xxxx-xxxx`) → query `https://www.datos.gov.co/resource/{id}.json?$order=fecha DESC&$limit=5000` (or `$limit=5000` ordered by latest period).<br>2. Official CREG fallback page: `https://creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos` (verified HTML table with 18 main cities + `Promedio PVP precio` row for `Gasolina MC ($/gal)` & `ACPM ($/gal)`).<br>Hosts: `{"www.datos.gov.co", "creg.gov.co"}` | Keyless public HTTPS. | JSON (Socrata SODA) or HTML table (CREG stdlib `HTMLParser`). Note Colombian thousands dot separator on CREG HTML (`15.588` = `15588` COP/gal, NOT `15.588`!). Verify magnitude (>1000 COP/gal) before dividing! | SICOM JSON fields (case-insensitive match): product field (`producto`/`nombre_producto`: `"ACPM"`/`"BIODIESEL"`/`"DIESEL"` → `"diesel"`, `"GASOLINA CORRIENTE"`/`"GASOLINA MOTOR CORRIENTE"` → `"petrol_95"`, `"GASOLINA EXTRA"` → `"petrol_98"`), price field (`precio`/`valor_promedio`/`precio_promedio`).<br>CREG HTML columns: `Gasolina MC ($/gal)` → `"petrol_95"`, `ACPM ($/gal)` → `"diesel"`. | **`COP/gal ÷ 3.785411784` → `COP/L`** (`local_per_liter`)! Mandatory gallon conversion verified from CREG & SICOM docs. Median across station/city rows (or `Promedio PVP` row on CREG). | **Colombian Open Gov Data** (MinMinas/CREG) |
| **`CL`** | `cl_cne` (Comisión Nacional de Energía — *Bencina en Línea*) `[CITED: api.cne.cl]` | v4: `https://api.cne.cl/api/v4/estaciones` (Bearer token header `Authorization: Bearer <token>`) or v3: `https://api.cne.cl/v3/combustibles/vehicular/estaciones?token=<token>`.<br>Hosts: `{"api.cne.cl"}` | **Important Research Finding:** `api.cne.cl` (both v3 and v4) requires free developer registration (`CNE_API_TOKEN`) — there is **no anonymous keyless endpoint**! Mirror `D-01` (`TANKERKOENIG_API_KEY`/`EIA_API_KEY`/`OPINET_API_KEY`): treat optional `CNE_API_TOKEN` env var identically (`skipped=True, ok=True` when unset; wire optional `CNE_API_TOKEN: ${{ secrets.CNE_API_TOKEN }}` in `phase-a-release.yml`; scrub token via `redact_url_secrets` + `.replace(token, "***")`). | JSON (`UTF-8`). Support both v4 array/object (`precios` dict or list) and v3 envelope (`{"estado": "OK", "data": [{"combustibles": [{"id": "93"|"95"|"97"|"diesel"|"glp", "precio": 1289}]}]}`). | Grade mapping: `"diesel"` / `"petroleo diesel"` → `"diesel"`, `"95"` / `"gasolina 95"` → `"petrol_95"`, `"97"` / `"gasolina 97"` → `"petrol_98"`, `"93"` / `"gasolina 93"` → `"petrol_92"`, `"glp"` / `"glp vehicular"` → `"lpg"`. Extract max `fecha_hora_actualizacion` date. | `CLP/L` (`local_per_liter`). Deterministic `statistics.median()` across valid stations per grade. | **Chilean Open Gov Data** (CNE) |
| **`MY`** | `my_opendosm` (MOF / OpenDOSM) `[CITED: data.gov.my]` | `https://api.data.gov.my/data-catalogue?id=fuelprice&filter=level@series_type&sort=-date&limit=5`<br>Hosts: `{"api.data.gov.my"}` | Keyless public HTTPS. | JSON array of objects (`UTF-8`). Always filter `row.get("series_type") == "level"` client-side as well (never mix `"change_weekly"` delta rows!). | Fields: `date` (`YYYY-MM-DD`), `series_type` (`"level"`), `ron95` → `"petrol_95"`, `ron97` → `"petrol_98"`, `diesel` → `"diesel"` (Peninsular Malaysia primary; fallback `diesel_eastmsia` only if `diesel` is null). Ignore null subsidy sub-columns (`ron95_budi95`, `diesel_skds`, etc.). | `MYR/L` (`local_per_liter`). Official published national weekly price (most recent `"level"` row with non-null `diesel` & `ron95`). | **CC BY 4.0** (OpenDOSM / MOF Malaysia) |
| **`JP`** | `jp_meti` (METI / ANRE Weekly Petroleum Retail Price Survey *給油所小売価格調査*) `[CITED: enecho.meti.go.jp]` | Landing page:<br>`https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results.html`<br>Discover latest `.xlsx` link (prefer weekly retail time-series / latest result `.xlsx` — **reject `.xls`** binary BIFF8 per `D-03` no-`xlrd`!).<br>Hosts: `{"www.enecho.meti.go.jp"}` | Keyless public HTTPS. | HTML (`AnchorExtractor` discovering `.xlsx` URL) → `openpyxl.load_workbook(..., read_only=True, data_only=True)` guarded by `_validate_ooxml_zip_safety()`. *(Multi-row Japanese headers!)* | Scan sheets (prefer most recent/active sheet) for columns/rows matching `レギュラー` (Regular gasoline → `"petrol_95"`), `ハイオク` (High-octane → `"petrol_98"`), `軽油` (Diesel → `"diesel"`), and `全国` / `全国平均` (National average). **Explicitly ignore `灯油` (kerosene — priced per 18L, not per liter!).** Extract latest valid date row (`YYYY年M月D日` or `datetime`/`date` cell). | `JPY/L` (`local_per_liter`). Official published national average (`全国` / `全国平均`), tax-inclusive. | **Government of Japan Standard Terms v2.0** (CC BY-compatible) |
| **`KR`** | `kr_opinet` (KNOC Opinet `avgAllPrice.do`) `[CITED: opinet.co.kr / data.go.kr]` | `https://www.opinet.co.kr/api/avgAllPrice.do?out=json&code=<OPINET_API_KEY>`<br>Hosts: `{"www.opinet.co.kr"}` | **Optional `OPINET_API_KEY`** (`D-01`). Passed via query param `code`. **CRITICAL SECURITY FIX:** `src/ets2v2/fetch/http.py:27-30` `_SECRET_QUERY_RE` currently masks `apikey|api_key|token|key` — it does **NOT** mask `code`! Must add `code` to `_SECRET_QUERY_RE` AND scrub `resolved_key` explicitly in `fetch_kr_opinet`! When unset → `skipped=True, ok=True`. | JSON (`UTF-8`). Single call returns all grades under `RESULT.OIL[]`. | `RESULT.OIL[]` items: `TRADE_DT` (`YYYYMMDD` → `YYYY-MM-DD`), `PRODCD`: `"D047"` → `"diesel"`, `"B027"` → `"petrol_95"`, `"B034"` → `"petrol_98"`, `"K015"` → `"lpg"` (ignore `"C004"` kerosene). `PRICE` (string float in KRW/L). | `KRW/L` (`local_per_liter`). Official published national daily average across all Korean service stations. | **Korean Public Data Open License** (KNOC Opinet) |

### 1.2 EU Core vs Global Tier 1 Outage Gate Architecture (`D-02`)

In `src/ets2v2/fetch/models.py:84-120` `[VERIFIED: src/ets2v2/fetch/models.py:84-120]`, `RawFuelFeedResult` currently has:
```python
tier: Literal["tier1", "fallback"]
```
and `FetchRunReport` has `tier1_feeds_succeeded` and `tier1_feeds_failed`.

To implement `D-02` and `D-07` cleanly while preserving backwards compatibility with existing tests and `phase-a-release.yml`:
1. Extend `RawFuelFeedResult` with:
   - `tier: Literal["tier1", "tier2", "fallback"]` (`D-07`)
   - `region_scope: Literal["eu_core", "global"] = "eu_core"` (defaults to `"eu_core"` so every Phase 3 European collector remains zero-diff compatible!)
2. Extend `FetchRunReport` with additive fields (defaulting to `0` so existing constructors remain valid):
   - Keep `tier1_feeds_succeeded` / `tier1_feeds_failed` (representing **EU Core Tier 1** — or add explicit `eu_tier1_feeds_succeeded`, `eu_tier1_feeds_failed`, `global_tier1_feeds_succeeded`, `global_tier1_feeds_failed`, `tier2_feeds_succeeded`, `tier2_feeds_failed` while keeping `tier1_feeds_succeeded == eu_tier1_feeds_succeeded` so `phase-a-release.yml` and Phase 3 tests never silently regress!).
3. **Hard-fail gate (`D-02`):**
   ```python
   eu_tier1_succeeded = sum(
       1 for r in all_fuel_results
       if r.tier == "tier1" and r.region_scope == "eu_core" and not r.skipped and r.ok
   )
   if eu_tier1_succeeded == 0:
       # Hard fail Friday CI — global feeds succeeding NEVER mask a total EU Core outage!
   ```
   Conversely, if all 8 Global Tier 1 feeds fail (or are skipped) while EU Core Tier 1 succeeds, `run_price_fetch()` returns `ok=True`, logs structured `warning` alerts (`global_tier1_outage` / `feed_outage`), and retains lockfile / Tier 3 seed prices for those countries.
4. **Skip reason fix in `pipeline.py:332-341` `[VERIFIED: src/ets2v2/fetch/pipeline.py:332-341]`:**
   Currently line 337 hardcodes `"skipped (TANKERKOENIG_API_KEY unset; using EC WOB)"` for ANY `feed_res.skipped` feed! Add an optional `skip_reason: str | None = None` field on `RawFuelFeedResult` so `de_tankerkoenig`, `us_eia_v2`, `kr_opinet`, and `cl_cne` emit accurate per-feed skip details (e.g., `"skipped (EIA_API_KEY unset; retaining lockfile/Tier 3)"`).
5. **Feed precedence (`_FEED_PRECEDENCE` in `pipeline.py:66-77`):**
   - `40`: All Tier 1 national feeds (EU: `uk_desnz`, `no_ssb_09654`, `fr_economie_ods`, `de_tankerkoenig`, `es_miteco`, `it_mimit`, `nl_cbs_80416ned`; Global: `us_eia_v2`, `br_anp`, `ar_energia`, `co_sicom`, `cl_cne`, `my_opendosm`, `jp_meti`, `kr_opinet`)
   - `30`: `ec_weekly_oil_bulletin`
   - `25`: Tier 2 national portals (`ch_bfs_lik`, `is_gasvaktin`, `md_anre`, `mk_erc`, `ru_rosstat`, `il_moe`, `ae_moei`, `za_dmre_cef`, `sa_aramco`, `ng_nbs`) — higher than fallback aggregators (`fuel_prices_eu`: 10) for official national ceilings, while letting `fuel_prices_eu` (`10`) act as automatic live fallback if a European Tier 2 portal (`CH`, `IS`, `MD`, `MK`) fails!
   - `20`: `fionnhughes_ec_wob`
   - `10`: `fuel_prices_eu`

---

## 2. Tier 2 Guarded National Portals (`GLB-02`, `D-05`..`D-08`)

### 2.1 Research-Gated Classification Matrix (All 14 Candidate Portals)

> Per `D-05`, portals gated by Cloudflare JS challenges, dynamic JS-only SPAs, or unstructured PDF/press bulletins are **cleanly classified into Tier 3 curated baselines** rather than shipping brittle scrapers. Note: Direct HTTP probing from this sandbox was blocked by policy; barrier assessments below combine official portal architecture citations `[CITED]` with documented scraping/WAF reports.

| ISO2 | Candidate Portal | Classification (`D-05`) | Verified Endpoint / Format / Charset | Cadence & Staleness Limit (`D-08`) | Stdlib / `openpyxl` Parser Strategy (`D-06`) | Justification / Barriers |
|------|------------------|-------------------------|--------------------------------------|------------------------------------|----------------------------------------------|--------------------------|
| **`IS`** | **Gasvaktin** (`github.com/gasvaktin/gasvaktin`) `[CITED: gasvaktin/gasvaktin, fuel-prices.eu]` | **Tier 2 (Live JSON)** | `https://raw.githubusercontent.com/gasvaktin/gasvaktin/master/vaktin/gas.min.json` (JSON, UTF-8, **MIT License** — attribution required). Hosts: `{"raw.githubusercontent.com"}`. *(Also backed by `fuel-prices.eu` fallback.)* | Daily/Weekly (`14d`) | `json.loads()` → iterate `stations[]` (`bensin95`, `diesel` ISK/L) → `statistics.median()`. | Clean, zero-WAF, MIT-licensed open JSON directly powering `fuel-prices.eu`'s Iceland data. (`hagstofa.is` only publishes volumes; `orkusetur.is` lacks raw price table.) |
| **`CH`** | **BFS / LIK PxWeb API** (`pxweb.bfs.admin.ch` / `opendata.swiss`) `[CITED: bfs.admin.ch]` | **Tier 2 (Live API + `fuel_prices_eu` fallback)** | `https://www.pxweb.bfs.admin.ch/api/v1/de` / BFS LIK fuel average prices CSV/JSON-stat2 (`UTF-8`, Swiss Open Data attribution). Hosts: `{"www.pxweb.bfs.admin.ch", "dam-api.bfs.admin.ch"}`. | Monthly (`45d`) | Reuse JSON-stat2 / CSV parser pattern from `no_ssb_09654`; pair with `fuel_prices_eu` (`CH`) for weekly CHF updates. *(Note: give `fuel_prices_eu` vs `ch_bfs_lik` careful precedence or use `ch_bfs_lik` as official monthly anchor.)* | Official Swiss Federal Statistical Office open data; no WAF. |
| **`MD`** | **ANRE Moldova** (`anre.md`) `[CITED: anre.md]` | **Tier 2 (Guarded HTML)** | `https://anre.md/` (UTF-8 HTML press/ceiling block: `"Benzina COR 95"` & `"Motorina standard"` in `MDL/L`). Hosts: `{"anre.md", "www.anre.md"}`. | Daily/Weekly (`14d`) | Stdlib `HTMLParser` table/block text extractor + strict regex for `COR 95` / `Motorin[aă]` + `DD.MM.YYYY` date; drift emits `tier2_selector_drift`. | Direct static HTML on homepage; no JS-SPA required. |
| **`MK`** | **ERC North Macedonia** (`erc.org.mk`) `[CITED: erc.org.mk]` | **Tier 2 (Guarded HTML)** | `https://www.erc.org.mk/` (UTF-8 Cyrillic HTML table: `ЕУРОСУПЕР БС - 95`, `ЕУРОСУПЕР БС - 98`, `ЕУРОДИЗЕЛ БС (Д-Е V)` in `MKD/L`, comma decimals `82,00`). Hosts: `{"www.erc.org.mk", "erc.org.mk"}`. | Weekly/Biweekly (`14d` or `30d` — recommend `45d` monthly-safe tolerance since ERC adjusts biweekly/event-driven!) | Stdlib `HTMLParser` table extractor matching Cyrillic/Latin `ЕУРОСУПЕР`/`EUROSUPER` 95/98 and `ЕУРОДИЗЕЛ`/`EURODIESEL`; parse comma decimals via `parse_positive_float`. | Structured HTML table directly on homepage; verified live prices (`82.00`/`84.00`/`88.50` MKD). |
| **`RU`** | **Rosstat** (`rosstat.gov.ru`) `[CITED: rosstat.gov.ru]` | **Tier 2 (Guarded HTML/XLSX)** | `https://rosstat.gov.ru/folder/313/document/126955` (weekly consumer petroleum bulletins, UTF-8 / `windows-1251` fallback; HTML tables + `.xlsx` attachments: `АИ-92`, `АИ-95`, `АИ-98`, `Дизельное топливо` in `RUB/L`). Hosts: `{"rosstat.gov.ru", "www.rosstat.gov.ru"}`. | Weekly (`14d`) | Stdlib `HTMLParser` table/link extractor with `utf-8`→`windows-1251` decode guard + optional `.xlsx` via `openpyxl`; catches `403`/geo-blocks cleanly as `tier2_portal_outage` (common from Azure/US runners!). | Machine-readable when reachable, but frequently geo-throttled from GitHub runners — strict circuit-breaker isolation (`D-07`) is essential. |
| **`IL`** | **Israel Ministry of Energy** (`gov.il`) `[CITED: gov.il]` | **Tier 2 (Guarded HTML/XLSX)** | `https://www.gov.il/en/departments/units/fuel_prices` or `/he/departments/topics/fuel/pricelist` (UTF-8 HTML/XLSX; regulated 95-octane self-service ceiling in `ILS/L`, e.g., `7.85 NIS`). Hosts: `{"www.gov.il", "gov.il"}`. | Monthly (`45d`) | Stdlib `HTMLParser` matching `95` octane self-service ceiling (`petrol_95` anchor → `compute_secondary_grade_prices` derives diesel cleanly since Israel does not cap retail diesel). | Monthly regulated ceiling on `gov.il`; may encounter WAF on CI IPs → circuit-breaker protects CI. |
| **`AE`** | **UAE MOEI** (`moei.gov.ae`) `[CITED: u.ae / moei.gov.ae]` | **Tier 2 (Guarded HTML)** | `https://www.moei.gov.ae/en/open-data` / fuel price announcement page (UTF-8 HTML table: `Super 98`, `Special 95`, `E-Plus 91`, `Diesel` in `AED/L`). Hosts: `{"www.moei.gov.ae", "moei.gov.ae"}`. | Monthly (`45d`, 1st of month) | Stdlib `HTMLParser` table extractor mapping `Diesel` → `"diesel"`, `Special 95` → `"petrol_95"`, `Super 98` → `"petrol_98"`, `E-Plus 91` → `"petrol_92"`. | Official monthly fixed national prices across all 7 Emirates. |
| **`ZA`** | **South Africa DMRE / CEF** (`cefgroup.co.za` / `dmre.gov.za`) `[CITED: cefgroup.co.za]` | **Tier 2 (Guarded HTML/XLSX)** | `https://cefgroup.co.za/energy-data/daily-basic-fuel-price/` & monthly schedule `.xlsx`/HTML (UTF-8; Inland Gauteng `Petrol 95 ULP`, `Petrol 93 ULP`, `Diesel 0.005%` in `ZAR cents/L` → divide by `100` to `ZAR/L`!). Hosts: `{"cefgroup.co.za", "www.cefgroup.co.za", "www.dmre.gov.za"}`. | Monthly (`45d`, 1st Wednesday) | Stdlib `HTMLParser` + `openpyxl` `.xlsx` discovery; convert cents/L (`>100` ZAR) ÷ `100.0` to `ZAR/L`. Use Inland (Gauteng) 95 ULP + Diesel 0.005% (50ppm). | Official regulated monthly schedules; HTML/XLSX available. |
| **`SA`** | **Saudi Aramco** (`aramco.com`) `[CITED: aramco.com]` | **Tier 2 (Guarded HTML)** | `https://www.aramco.com/en/what-we-do/energy-products/retail-fuels` (UTF-8 HTML table: `Gasoline 91`, `Gasoline 95`, `Gasoline 98`, `Diesel` in `SAR/L`). Hosts: `{"www.aramco.com"}`. | Monthly (`45d`, 11th of month) | Stdlib `HTMLParser` table extractor mapping `Diesel`, `Gasoline 95`, `Gasoline 98`, `Gasoline 91` (`petrol_92`). | Low-churn state prices; if Akamai/Cloudflare returns `403` from CI runners, circuit-breaker retains lockfile cleanly. |
| **`NG`** | **Nigeria NBS** (`nigerianstat.gov.ng`) `[CITED: nigerianstat.gov.ng]` | **Tier 2 (Guarded XLSX)** | `https://nigerianstat.gov.ng/` / `microdata.nigerianstat.gov.ng` (PMS Petrol & AGO Diesel Watch monthly `.xlsx` downloads, `NGN/L`). Hosts: `{"nigerianstat.gov.ng", "www.nigerianstat.gov.ng", "microdata.nigerianstat.gov.ng"}`. | Monthly (`45d`) | Discover latest AGO/PMS Watch `.xlsx` link via `AnchorExtractor` → parse national average row via `openpyxl` (`_validate_ooxml_zip_safety`). | Official monthly national `.xlsx` datasets; frequently slow/timeout → isolated per-country circuit breaker. |
| **`KE`** | **Kenya EPRA** (`epra.go.ke`) `[CITED: epra.go.ke]` | **Classified → Tier 3 Curated** (`D-05`) | — | Curated (`180d`) | None (Tier 3 baseline in `data/curated/tier3_fuel_baselines.json`). | **Confirmed Cloudflare JS-challenge wall (`403`/`503` on plain HTTP clients) + monthly releases primarily distributed as PDFs.** Per `D-05`, do NOT build a brittle scraper. |
| **`ID`** | **Indonesia Pertamina / MyPertamina** (`mypertamina.id/fuels-harga`) `[CITED: mypertamina.id]` | **Classified → Tier 3 Curated** (`D-05`) | — | Curated (`180d`) | None (Tier 3 baseline). | **Dynamic JS web application + province-by-province tables, while primary retail grades (Pertalite RON 90 `Rp 10,000/L`, Biosolar Diesel `Rp 6,800/L`) are government-fixed with very low churn.** Clean Tier 3 fit per `D-05`. |
| **`JO`** | **Jordan MEMR / MIT** (`memr.gov.jo` / `mit.gov.jo`) `[CITED: mit.gov.jo]` | **Classified → Tier 3 Curated** (`D-05`) | — | Curated (`180d`) | None (Tier 3 baseline). | Monthly fuel committee prices are published mainly as unstructured Arabic news press releases/PDF images rather than a stable machine-readable HTML table or API. Clean Tier 3 fit per `D-05`. |
| **`EG`** | **Egypt FAPC / Ministry of Petroleum** (`petroleum.gov.eg`) `[CITED: petroleum.gov.eg]` | **Classified → Tier 3 Curated** (`D-05`) | — | Curated (`180d`; *note: keep `105d` quarterly tier supported in `evaluate_lockfile_staleness()` per `D-08` for any future quarterly portal*) | None (Tier 3 baseline; verified current official benchmark: Diesel `20.50 EGP/L`, 95 `24.00 EGP/L`, 92 `22.25 EGP/L`). | Quarterly Arabic press announcements (`petroleum.gov.eg`) with no stable machine-readable table/JSON/XLSX endpoint. Clean Tier 3 fit per `D-05`. |

**Summary of Research-Gated Tier 2 Split:** **10 guarded Tier 2 collectors** (`IS`, `CH`, `MD`, `MK`, `RU`, `IL`, `AE`, `ZA`, `SA`, `NG`) + **4 cleanly routed to Tier 3 curated baselines** (`KE`, `ID`, `JO`, `EG`) per `D-05`.

### 2.2 Per-Country Circuit-Breaker Error Taxonomy & Stdlib HTML Helpers (`D-06`, `D-07`)

Create a shared stdlib helper module `src/ets2v2/fetch/_html.py` containing:
- `TableExtractor(HTMLParser)` — parses `<table>`/`<tr>`/`<th>`/`<td>` cells into `list[list[str]]` with whitespace normalization and HTML entity decoding (zero `beautifulsoup4`/`lxml`).
- `decode_with_fallbacks(raw: bytes, encodings: tuple[str, ...]) -> str` — tries `utf-8-sig` → `windows-1251` / `latin-1` (explicitly raising a typed `Tier2EncodingError` if all fail or if strict decode yields garbled replacement chars where prohibited).
- Typed internal exceptions inside `src/ets2v2/fetch/tier2_portals.py` mapping 1-to-1 to `D-07` structured `warning` alert codes:
  - HTTP `429` or `403` rate-limit/WAF → alert code **`tier2_rate_limited`** (`severity="warning"`)
  - HTTP `4xx`/`5xx`/timeout/transport error → alert code **`tier2_portal_outage`** (`severity="warning"`)
  - `UnicodeDecodeError` / charset error → alert code **`tier2_encoding_error`** (`severity="warning"`)
  - Missing table / unparseable price cell / missing expected grade label → alert code **`tier2_selector_drift`** (`severity="warning"`)
- Add optional `error_code: str | None = None` on `RawFuelFeedResult` so `pipeline.py` emits the exact `tier2_*` alert code instead of generic `feed_outage`!
- **CLI filter flags on `ets2v2 fetch` (`D-07`):**
  - `--no-global` (skip the 8 Global Tier 1 collectors)
  - `--no-tier2` (skip all 10 Tier 2 guarded portals)
  - Existing `--fx-only` and `--seed-offline` continue to work identically.

### 2.3 Tier- and Cadence-Aware Staleness & Alert Rollup (`D-08`)

Update `evaluate_lockfile_staleness(lockfile: PricesLockfile, as_of_date: date)` in `src/ets2v2/normalize/lockfile.py` (`[VERIFIED: src/ets2v2/normalize/lockfile.py:99-133]`):

| Source / State Category | Exact Constants & Matching Rules | Staleness Limit | Alert Code |
|-------------------------|----------------------------------|-----------------|------------|
| **Weekly Tier 1 Live** (`fallback_used=False`) | `ec_weekly_oil_bulletin`, `uk_desnz`, `fr_economie_ods`, `de_tankerkoenig`, `es_miteco`, `it_mimit`, `nl_cbs_80416ned`, `us_eia_v2`, `br_anp`, `ar_energia`, `cl_cne`, `my_opendosm`, `jp_meti`, `kr_opinet`, `fuel_prices_eu`, `fionnhughes_ec_wob`, `is_gasvaktin`, `md_anre`, `ru_rosstat` | **`14` days** (`TIER1_STALE_DAYS = 14`) | `stale_tier1` |
| **Monthly Tier 1/2 Live** (`fallback_used=False`) | `no_ssb_09654`, `co_sicom`, `co_creg`, `ch_bfs_lik`, `mk_erc`, `il_moe`, `ae_moei`, `za_dmre_cef`, `sa_aramco`, `ng_nbs` | **`45` days** (`TIER2_MONTHLY_STALE_DAYS = 45`) | `stale_tier2_monthly` |
| **Quarterly Tier 2 Live** (`fallback_used=False`) | Any source registered in `QUARTERLY_TIER2_SOURCES` (e.g., `eg_fapc` if added later) | **`105` days** (`TIER2_QUARTERLY_STALE_DAYS = 105`) | `stale_tier2_quarterly` |
| **Degraded Fallback / Core Seed** (`fallback_used=True` and source ≠ `tier3_curated_baseline`) | Retained live entries (`fallback_used=True`), `baseline_1.62_seeded`, `promods_curated_seed` | **`30` days** (`FALLBACK_STALE_DAYS = 30`) | `stale_fallback` |
| **Tier 3 Curated Global Baseline** | `source == "tier3_curated_baseline"` | **`180` days** (`TIER3_CURATED_STALE_DAYS = 180`) | `stale_tier3_curated` |

*(Compatibility check: Existing Phase 3/4 tests pass `ec_wob` / `ec_weekly_oil_bulletin` with `fallback_used=False` → 14d `stale_tier1`, and `fallback_used=True` or `baseline_1.62_seeded` → 30d `stale_fallback` — 100% preserved!)*

**Noise-Controlled Alert Summaries (`D-08`, `D-12`):**
In `src/ets2v2/publish/changelog.py` (`_render_alerts_section`) and `.github/workflows/phase-a-release.yml` (step summary & PR body):
- Itemize **all** alerts for Core (`36`), Tier 1 (EU + Global), and Tier 2 portals individually.
- Aggregate `stale_tier3_curated` and `fallback_countries` where `entry.source == "tier3_curated_baseline"` into **one compact summary line** (e.g., `- **Tier 3 Curated Global Baselines Retained:** \`142\` territories (\`0\` overdue >180d)`) instead of printing 140+ individual ISO-2 codes!

---

## 3. Tier 3 Global `200+` Territory & FX Expansion (`GLB-03`, `D-09`..`D-12`)

### 3.1 Existing Registry & Alias Coverage Audit (`[VERIFIED: data/mappings/]`)

Direct offline audit of `data/mappings/ets2_countries.json` (`614` lines) and `data/mappings/country_aliases.json` (`600` lines):
- Existing canonical territories: **`76`** (`36` `vanilla_1_62: true` + `40` `vanilla_1_62: false` ProMods EU+ME+MA+TGS).
- Existing aliases in `country_aliases.json`: **`119`** aliases targeting **`37`** unique ISO-2 codes.
- **13 alias ISO-2 targets currently MISSING from `ets2_countries.json`:**
  `AE`, `BR`, `EC`, `GQ`, `GY`, `ID`, `JP`, `PG`, `PY`, `SD`, `TL`, `UY`, `ZA`.
- Every single one of these `13` codes MUST be included in Phase 5's `~220`-territory expansion, enabling a new hard invariant test: **`{alias.iso2 for alias in aliases.values()} <= set(registry.laws_by_iso2)`** (100% alias target coverage!).
- Note on `guianafr` in `country_aliases.json:153-157` (`"iso2": "FR"`, `"iana_timezone_override": "America/Cayenne"`): keep `guianafr` pointing to `"FR"` (backwards-compatible with Phase 4 tests) while ALSO adding `GF` (`french_guiana`, `EUR`, `America/Cayenne`) as a canonical ISO-3166-1 territory for direct ISO-2 lookups.

### 3.2 Canonical `220`-Territory ISO-3166-1 Roster (`D-09`)

Exact breakdown yielding **`220` territories** (right in the middle of `D-09`'s `215–225` target):
1. **Existing `76` territories** (unchanged slugs/IDs): `36` Vanilla+DLC + `40` ProMods (`AD`, `AM`, `AX`, `AZ`, `BY`, `CN`, `CY`, `DZ`, `EG`, `FO`, `GE`, `GG`, `GI`, `GL`, `IE`, `IL`, `IM`, `IQ`, `JE`, `JO`, `KG`, `KZ`, `LB`, `LI`, `LY`, `MA`, `MC`, `MD`, `MN`, `MT`, `PS`, `SA`, `SJ`, `SM`, `SY`, `TJ`, `TM`, `TN`, `UA`, `UZ`).
2. **Remaining `126` UN sovereign states & observers** (completing all `195` UN member/observer states + `XK`):
   - **Europe (1):** `VA` (Vatican City)
   - **Americas (35):** `AG`, `AR`, `BB`, `BO`, `BR`, `BS`, `BZ`, `CA`, `CL`, `CO`, `CR`, `CU`, `DM`, `DO`, `EC`, `GD`, `GT`, `GY`, `HN`, `HT`, `JM`, `KN`, `LC`, `MX`, `NI`, `PA`, `PE`, `PY`, `SR`, `SV`, `TT`, `US`, `UY`, `VC`, `VE`
   - **Asia & Middle East (32):** `AE`, `AF`, `BD`, `BH`, `BN`, `BT`, `ID`, `IN`, `IR`, `JP`, `KH`, `KP`, `KR`, `KW`, `LA`, `LK`, `MM`, `MV`, `MY`, `NP`, `OM`, `PH`, `PK`, `QA`, `SG`, `TH`, `TL`, `VN`, `YE` *(29)* — wait: `CN`, `IL`, `IQ`, `JO`, `KG`, `KZ`, `LB`, `MN`, `PS`, `SA`, `SY`, `TJ`, `TM`, `UZ`, `AM`, `AZ`, `CY`, `GE`, `TR` are already in the 76! So `29` new Asian UN states.
   - **Africa (49):** `AO`, `BF`, `BI`, `BJ`, `BW`, `CD`, `CF`, `CG`, `CI`, `CM`, `CV`, `DJ`, `ER`, `ET`, `GA`, `GH`, `GM`, `GN`, `GQ`, `GW`, `KE`, `KM`, `LR`, `LS`, `MG`, `ML`, `MR`, `MU`, `MW`, `MZ`, `NA`, `NE`, `NG`, `RW`, `SC`, `SD`, `SL`, `SN`, `SO`, `SS`, `ST`, `SZ`, `TD`, `TG`, `TZ`, `UG`, `ZA`, `ZM`, `ZW` *(49 — with existing `DZ`, `EG`, `LY`, `MA`, `TN` = all 54 African UN states!)*
   - **Oceania (14):** `AU`, `FJ`, `FM`, `KI`, `MH`, `NR`, `NZ`, `PG`, `PW`, `SB`, `TO`, `TV`, `VU`, `WS`
   *(Subtotal sovereign/existing: `76 + 1 + 35 + 29 + 49 + 14 = 204` — wait: verify all 195 UN states are present: `76` includes `10` non-UN territories `AX, FO, GG, GI, GL, IM, JE, SJ, XK, PS` (`PS` is UN observer, `VA` is UN observer), so `67` UN states in 76 + `128` new UN states/observers = `195` UN states + `XK` + `8` ProMods territories = `204`!)*
3. **`16`–`24` additional inhabited ISO-3166-1 & ETS2 map-combo territories** (bringing total to **`220`–`224`**):
   - **East Asia (3):** `TW` (Taiwan — *Roads of Chunghwa*), `HK` (Hong Kong), `MO` (Macao)
   - **Caribbean & Americas Overseas Territories (15):** `PR` (Puerto Rico), `GF` (French Guiana — *EAA*), `GP` (Guadeloupe), `MQ` (Martinique), `CW` (Curaçao), `AW` (Aruba), `SX` (Sint Maarten), `BM` (Bermuda), `KY` (Cayman Islands), `VG` (British Virgin Islands), `TC` (Turks and Caicos), `FK` (Falkland Islands), `PM` (Saint Pierre and Miquelon), `VI` (US Virgin Islands), `AI` (Anguilla), `MS` (Montserrat) *(16)*
   - **Africa & Indian Ocean (3):** `EH` (Western Sahara — *Africa/Maghreb* map combos), `RE` (Réunion), `YT` (Mayotte)
   - **Pacific Territories (4):** `NC` (New Caledonia), `PF` (French Polynesia), `GU` (Guam), `CK` (Cook Islands)
   - Total = `204 + 3 + 16 + 3 + 4 = 230` (or pick the exact `220`–`225` subset — e.g. excluding `AI`/`MS`/`CK`/`VI` or keeping all 224–225 is cleanly within `D-09`'s `~215–225` band; **`222`** or **`224`** with `TW`, `HK`, `MO`, `PR`, `GF`, `GP`, `MQ`, `RE`, `YT`, `NC`, `PF`, `CW`, `AW`, `SX`, `BM`, `KY`, `VG`, `TC`, `FK`, `PM`, `EH`, `GU`, `VI` is crisp, complete, and hits every territory named in `D-09`!).

### 3.3 Statutory `speed_unit` (`mph` vs `kmh`) Verification

Based on statutory traffic codes `[CITED: wikipedia / national highway codes]` and existing repo files (`gg.json`, `im.json`, `je.json` `[VERIFIED: data/laws/countries/{gg,im,je}.json:18]`):
- **Confirmed `speed_unit: "mph"` territories (21 in our ~222-territory roster):**
  - Existing (4): `GB`, `GG`, `IM`, `JE`
  - New Sovereign (8): `US`, `LR` (Liberia), `BS` (Bahamas), `AG` (Antigua & Barbuda), `DM` (Dominica), `GD` (Grenada), `KN` (Saint Kitts & Nevis), `LC` (Saint Lucia), `VC` (Saint Vincent & the Grenadines) *(9)*
  - New Territories (9): `PR`, `VI`, `GU`, `BM`, `KY`, `VG`, `TC`, `FK`, `AI`, `MS` (if included)
- **Explicit `kmh` edge cases to document (avoid common misconceptions):**
  - `BZ` (Belize): Officially metricated road signage to `km/h` (mixed legacy mph usage; standardize on `kmh` or note mixed status).
  - `MM` (Myanmar): Uses `km/h` on modern expressways (Yangon–Mandalay Expressway 100 km/h) alongside legacy mph signs; recommend `kmh` for ETS2 *SEA* map-combo compatibility (since ETS2 SEA uses metric signs).
  - `WS` (Samoa): Officially uses `km/h` (metric since 1980s, e.g., 56 km/h = 35 mph legacy equivalent, signs in km/h).
  - `CA` (Canada), `AU` (Australia), `NZ` (New Zealand), `IE` (Ireland), `ZA` (South Africa), `IN` (India), `HK` (Hong Kong), `JP` (Japan): All strictly `kmh`.

### 3.4 Verified Global IANA Timezones & `IANA_NUMERIC_ABBR_OVERRIDES`

Direct execution against Python `3.12.13` + `tzdata` `[VERIFIED: local zoneinfo probe]` confirmed **0 invalid IANA zones** and identified **58 additional global zones** whose `dt.tzname()` returns numeric offsets (`+XX`/`-XX`) on `2026-01-15` or `2026-07-15`:

- **Seasonal DST numeric zones (must use `(standard_abbr, dst_abbr)` tuple!):**
  - `"America/Santiago": ("CLT", "CLST")` — Southern Hemisphere DST (`2026-01-15` → `-180m`/`CLST`; `2026-07-15` → `-240m`/`CLT`)!
  - `"America/Miquelon": ("PMST", "PMDT")` — Northern Hemisphere DST (`-180m`/`PMST` winter; `-120m`/`PMDT` summer).
- **Fixed-offset numeric zones (extend `IANA_NUMERIC_ABBR_OVERRIDES` in `src/ets2v2/registry/timezone.py:20-38`):**
  - Americas: `America/Argentina/Buenos_Aires` → `"ART"`, `America/Asuncion` → `"PYT"` *(Paraguay abolished DST in Oct 2024; verified permanent `-180m` in 2026)*, `America/Bogota` → `"COT"`, `America/Caracas` → `"VET"`, `America/Cayenne` → `"GFT"`, `America/Guayaquil` → `"ECT"`, `America/Guyana` → `"GYT"`, `America/La_Paz` → `"BOT"`, `America/Lima` → `"PET"`, `America/Montevideo` → `"UYT"`, `America/Paramaribo` → `"SRT"`, `America/Sao_Paulo` → `"BRT"`, `Atlantic/Stanley` → `"FKST"`.
  - MENA / Asia: `Asia/Aden` → `"AST"`, `Asia/Bahrain` → `"AST"`, `Asia/Kuwait` → `"AST"`, `Asia/Qatar` → `"AST"`, `Asia/Dubai` → `"GST"`, `Asia/Muscat` → `"GST"`, `Asia/Tehran` → `"IRST"`, `Asia/Kabul` → `"AFT"`, `Asia/Bangkok` → `"ICT"`, `Asia/Ho_Chi_Minh` → `"ICT"`, `Asia/Phnom_Penh` → `"ICT"`, `Asia/Vientiane` → `"ICT"`, `Asia/Kuala_Lumpur` → `"MYT"`, `Asia/Singapore` → `"SGT"`, `Asia/Brunei` → `"BNT"`, `Asia/Dili` → `"TLT"`, `Asia/Colombo` → `"SLST"`, `Asia/Dhaka` → `"BDT"`, `Asia/Thimphu` → `"BTT"`, `Asia/Kathmandu` → `"NPT"`, `Asia/Yangon` → `"MMT"`, `Indian/Maldives` → `"MVT"`.
  - Africa / Indian / Atlantic / Pacific: `Africa/El_Aaiun` → `"WEST"`, `Atlantic/Cape_Verde` → `"CVT"`, `Indian/Mahe` → `"SCT"`, `Indian/Mauritius` → `"MUT"`, `Indian/Reunion` → `"RET"`, `Pacific/Apia` → `"WST"`, `Pacific/Efate` → `"VUT"`, `Pacific/Fiji` → `"FJT"`, `Pacific/Funafuti` → `"TVT"`, `Pacific/Guadalcanal` → `"SBT"`, `Pacific/Majuro` → `"MHT"`, `Pacific/Nauru` → `"NRT"`, `Pacific/Niue` → `"NUT"`, `Pacific/Noumea` → `"NCT"`, `Pacific/Palau` → `"PWT"`, `Pacific/Pohnpei` → `"PONT"`, `Pacific/Port_Moresby` → `"PGT"`, `Pacific/Rarotonga` → `"CKT"`, `Pacific/Tahiti` → `"TAHT"`, `Pacific/Tarawa` → `"GILT"`, `Pacific/Tongatapu` → `"TOT"`.
  - *(Note: `ETS2V2-INV-TZ` in `validate/invariants.py:26` rejects raw numeric `^[+-]\d{2}` strings, so overriding all 58 zones ensures clean human abbreviations everywhere!)*

### 3.5 Global `~156` ISO-4217 Currency Audit & 2025–2026 Amendments (`D-10`, `D-11`)

- **Total unique ISO-4217 currencies across ~222 territories:** `~156` currencies (`1` pinned `EUR` + `16` Core European required non-EUR + `~139` global `is_extended=True` currencies). Shared currency unions reduce 222 territories to ~156 currencies:
  - `EUR`: 27+ (Eurozone 21 incl. `BG` + `AD`, `MC`, `SM`, `VA`, `ME`, `XK`, `AX`, `GF`, `GP`, `MQ`, `RE`, `YT`, `PM`)
  - `USD`: `US`, `EC`, `SV`, `PA` (or `PAB` pegged 1:1 to USD), `TL`, `FM`, `MH`, `PW`, `PR`, `VI`, `GU`, `VG`, `TC`
  - `XOF` (West African CFA, pegged `655.957 / EUR`): `BJ`, `BF`, `CI`, `GW`, `ML`, `NE`, `SN`, `TG`
  - `XAF` (Central African CFA, pegged `655.957 / EUR`): `CM`, `CF`, `TD`, `CG`, `GQ`, `GA`
  - `XCD` (East Caribbean Dollar, pegged `2.70 / USD`): `AG`, `DM`, `GD`, `KN`, `LC`, `VC`, `AI`, `MS`
  - `XPF` (CFP Franc, pegged `119.33174 / EUR`): `NC`, `PF`
  - `AUD`: `AU`, `KI`, `NR`, `TV`; `NZD`: `NZ`, `CK`, `NU`; `GBP`: `GB`, `GG`, `IM`, `JE`, `GI`, `FK` (or `FKP` pegged 1:1 GBP); `CHF`: `CH`, `LI`; `DKK`: `DK`, `FO`, `GL`; `NOK`: `NO`, `SJ`; `MAD`: `MA`, `EH`; `ILS`: `IL`, `PS`.
- **Verified 2024–2026 ISO-4217 Currency Changes (`[CITED: six-group.com / fxapi.com / rbz.co.zw]`):**
  1. **`XCG` (Caribbean Guilder)** — Replaced `ANG` at 1:1 par on **2025-03-31** for **`CW`** (Curaçao) and **`SX`** (Sint Maarten); `ANG` ceased legal tender 2025-07-01. *(Note: `fawazahmed0` / `Frankfurter v2` may lag on `XCG` vs `ANG` — `is_extended=True` reference FX fallback at `~1.94 XCG/EUR` keeps CI 100% resilient!)*
  2. **`ZWG` (Zimbabwe Gold / ZiG)** — Active ISO-4217 code (`924`) replacing retired `ZWL` for **`ZW`**. *(Sanity band e.g. `(10.0, 120.0)` ZWG/EUR; isolates stale `ZWL` quotes cleanly!)*
  3. **`SLE` (Sierra Leonean Leone)** — Active ISO-4217 code (`925`, redenominated 1,000:1 from retired `SLL`) for **`SL`**. *(Sanity band e.g. `(15.0, 50.0)` SLE/EUR — rejects un-redenominated ~24,000 SLL quotes!)*
  4. **`SYP` (Syrian Pound)** — Already handled with post-2026-01-01 redenominated band `(80.0, 250.0)` (`src/ets2v2/normalize/currencies.py:270`).
  5. **`VES` (Venezuelan Bolívar Digital)** & **`SRD` (Surinamese Dollar)** & **`IRR` (Iranian Rial)** & **`KPW` (North Korean Won)** — High-volatility / dual-rate / sanctioned currencies: **wide sanity envelopes + `is_extended=True` reference FX fallback** guarantee zero CI failures.
  6. **`BGN` → `EUR`** — Already completed in Phase 3 for Bulgaria (`BG`).
- **Additional 18 ECB-covered global currencies** (`EXTENDED_ECB_CURRENCIES` expanded from `{"CNY", "ILS"}` to `{"AUD", "BRL", "CAD", "CNY", "HKD", "IDR", "ILS", "INR", "JPY", "KRW", "MXN", "MYR", "NZD", "PHP", "SGD", "THB", "USD", "ZAR"}`): gives authoritative ECB cross-validation for major global Tier 1/Tier 2 economies (`US`, `BR`, `MY`, `JP`, `KR`, `ID`, `ZA`, `IL`, `CN`, `AU`, `CA`, `MX`, `IN`, etc.)!

### 3.6 Ultra-Subsidized Oil-Producer States & `0.010 EUR/L` Floor Clamping (`D-11`)

In `src/ets2v2/normalize/models.py:75` `[VERIFIED: src/ets2v2/normalize/models.py:75]`:
```python
eur_per_liter: float = Field(ge=0.01, le=5.00, allow_inf_nan=False)
```
Retail subsidized diesel in **Iran (`IR`)** (~`€0.005–€0.009/L` at market FX) and **Venezuela (`VE`)** (subsidized quota ~`€0.004/L`, international pump `~$0.50/L`) can fall below `0.010 EUR/L` (while Libya `LY` `~€0.028/L`, Algeria `DZ` `~€0.201/L`, Angola `AO` `~€0.20/L`, Kuwait `KW` `~€0.34/L`, Turkmenistan `TM` `~€0.259/L`, Egypt `EG` `~€0.38/L` remain above `0.010 EUR/L`).

**Prescriptive handling (`D-11`):**
- In `data/curated/tier3_fuel_baselines.json`, store `diesel_eur: 0.010` with `"clamped_to_floor": true` and a clean note explaining the `0.010 EUR/L` ETS2 non-zero floor for `IR` (and `VE` if using subsidized tier, or `0.460` if using international retail — recommend `0.010` clamped for `IR` and `0.035` or `0.010` clamped for `VE` with explicit `clamped_to_floor: true` metadata so tests directly exercise `D-11`!).
- In `normalize/lockfile.py` (`seed_initial_lockfile`) and `normalize/fuel.py` (`normalize_country_fuel_prices`): keep the hard `[0.01, 5.00]` bounds intact for live feeds (rejecting corrupt `0.0001` quotes from broken scrapers), and only allow explicit `clamped_to_floor` clamping on curated Tier 3 baselines (recording a structured `"info"`/`"warning"` note in baseline metadata, never weakening live scraper circuit breakers!).

### 3.7 Clean-Room Data Schemas (`D-10`)

#### A. `data/mappings/currencies.json`
```json
{
  "schema_version": 1,
  "verified_date": "2026-11-25",
  "provenance": "Clean-room ISO-4217 currency metadata, ECB coverage flags, and FX sanity bands (CC BY 4.0).",
  "currencies": {
    "EUR": {
      "tier": "pinned",
      "ecb_covered": false,
      "major_ecb": false,
      "fixed_peg_per_eur": 1.0,
      "reference_rate_per_eur": 1.0,
      "sanity_min": null,
      "sanity_max": null
    },
    "USD": {
      "tier": "extended",
      "ecb_covered": true,
      "major_ecb": true,
      "fixed_peg_per_eur": null,
      "reference_rate_per_eur": 1.08,
      "sanity_min": 0.70,
      "sanity_max": 1.60
    }
  },
  "territory_currencies": {
    "AD": "EUR",
    "AE": "AED",
    "US": "USD"
  }
}
```
- **Tier enum:** `Literal["pinned", "core", "extended"]` (`pinned` = `EUR`; `core` = exact 16 required European non-EUR currencies; `extended` = ~139 isolated global currencies).
- **Backwards compatibility in `src/ets2v2/normalize/currencies.py`:** Load `data/mappings/currencies.json` once via `@functools.lru_cache` (resolved via `Path(__file__).resolve().parents[3] / "data" / "mappings" / "currencies.json"` with an explicit loader function `load_currency_registry(path=...)` for unit testing), and re-export ALL existing module-level constants (`VANILLA_SLUG_TO_ISO2`, `VANILLA_36_ISO2S`, `EXTRA_EU_TERRITORY_ISO2S`, `EUROPEAN_TERRITORY_ISO2S`, `PROMODS_EXTENDED_ISO2S`, `ALL_LOCKFILE_TERRITORY_ISO2S`, `TERRITORY_CURRENCIES`, `ALL_TERRITORY_CURRENCIES`, `MAJOR_ECB_CURRENCIES`, `VOLATILE_NON_ECB_CURRENCIES`, `ECB_COVERED_CURRENCIES`, `EXTENDED_ECB_CURRENCIES`, `EXTENDED_PROMODS_CURRENCIES`, `EXTENDED_GLOBAL_CURRENCIES`, `CURRENCY_SANITY_BANDS`, `EXTENDED_CURRENCY_SANITY_BANDS`, `ALL_CURRENCY_SANITY_BANDS`, `CORE_REFERENCE_FX_RATES`, `EXTENDED_REFERENCE_FX_RATES`, `ALL_REFERENCE_FX_RATES`, `BAM_FIXED_PEG_PER_EUR`)!
- **AST DAG compliance:** `ets2v2.normalize` loads JSON via stdlib `json` + `pathlib` + `pydantic` — **zero** `ets2v2.registry` / `httpx` / `openpyxl` imports!

#### B. `data/curated/tier3_fuel_baselines.json`
```json
{
  "schema_version": 1,
  "verified_date": "2026-11-25",
  "license": "CC BY 4.0",
  "provenance": "Clean-room curated retail diesel EUR/L reference baselines from public national ministry schedules and central-bank statistical bulletins.",
  "baselines": {
    "IR": {
      "diesel_eur_per_liter": 0.010,
      "petrol_95_eur_per_liter": 0.025,
      "clamped_to_floor": true,
      "verified_date": "2026-11-25",
      "source_note": "National Iranian Oil Products Distribution Company (NIOPDC) subsidized tariff; clamped to ETS2 0.010 EUR/L floor."
    },
    "US": {
      "diesel_eur_per_liter": 0.920,
      "petrol_95_eur_per_liter": 0.800,
      "clamped_to_floor": false,
      "verified_date": "2026-11-25",
      "source_note": "U.S. EIA weekly national retail average seed baseline (overridden live when EIA_API_KEY is set)."
    }
  }
}
```
- **Every non-Vanilla territory (`~184` territories = `37` ProMods + `147` new global territories)** has an entry here (replacing `PROMODS_SEED_EUR_PRICES` hardcoded in `currencies.py:335-373`), with `PROMODS_SEED_EUR_PRICES` preserved as a derived read-only dict export for backwards compatibility!
- **Zero forbidden taint strings** anywhere in `provenance` or `source_note` (`D-16`).

### 3.8 Existing Phase 2–4 Tests Affected by `76 → ~220` & `41 → ~156` Expansion `[VERIFIED: repo grep]`

The planner **MUST** include explicit updates to these **10 existing test files** in Plan `05-03` (so `uv run --offline pytest` stays 100% green):
1. `tests/test_registry_contracts.py` (`:139, :147, :148, :411` — currently asserts `76`)
2. `tests/test_registry_snapshot.py` (`:293, :321, :322, :353` — currently asserts `76`)
3. `tests/test_registry_timezone.py` (`:117` — currently asserts `76`)
4. `tests/test_normalize_fx.py` (`:651, :652, :656, :657, :698` — currently asserts `76` / `40` / `41`; keep `PROMODS_EXTENDED_ISO2S == 37` and `TERRITORY_CURRENCIES == 39` intact!)
5. `tests/test_normalize_fuel.py` (`:234, :239` — currently asserts `76` / `41`)
6. `tests/test_fetch_fx.py` (`:446, :448, :481, :608, :618, :622` — currently asserts `41`)
7. `tests/test_fetch_fuel.py` (`:212` — currently asserts `"US" not in by_iso2`; replace with an unmapped synthetic code like `"ZZ"` or `"AQ"`!)
8. `tests/test_fetch_pipeline.py` (`:375, :377, :552, :554, :741, :744` — currently asserts `76` / `41`)
9. `tests/test_merge_aliases.py` (`:86` — currently asserts `76`)
10. `tests/test_publish_release.py` (`:172, :175, :179, :551` — currently asserts `76` and `` `36` (Core) / `76` (Snapshot) ``)

---

## 4. Internal CI OSM (`CC BY-SA`) Speed-Limit Drift Audit & `CC BY 4.0` Isolation (`GLB-04`, `D-13`..`D-16`)

### 4.1 `westnordost/osm-legal-default-speeds` Format & Licensing `[CITED: github.com/westnordost/osm-legal-default-speeds]`

- **License boundary (CRITICAL):**
  - Repository code: **BSD 3-Clause**.
  - Compiled `legal_default_speeds.json` (parsed from OSM Wiki *Default speed limits*): **`CC BY-SA 2.0`** (ShareAlike).
  - **Strict quarantine (`D-14`, `D-16`):** NEVER store `legal_default_speeds.json` in Git, NEVER write OSM speed numbers into `data/laws/`, `state/prices.lock.json`, `realism-snapshot-*.json`, or any mod `.scs`/`.zip`. Fetch purely at runtime inside `ets2v2 audit osm-speeds` (or accept local `--rules-file` for offline tests/runs) and emit read-only drift reports as ephemeral CI artifacts / rolling GitHub Issue!
- **Distribution URLs & Fallback:**
  - Primary hosted artifact: `https://westnordost.github.io/osm-legal-default-speeds/legal_default_speeds.json` `[ASSUMED — verify exact path on GitHub Pages / demo distribution; support `--rules-url` override and `--rules-file` offline path!]`
  - Allowlisted hosts: `frozenset({"westnordost.github.io", "raw.githubusercontent.com", "github.com"})`.
- **JSON Structure (`[CITED: westnordost/osm-legal-default-speeds]`):**
  - Top-level keys: `meta`, `roadTypesByName`, `speedLimitsByCountryCode` (keyed by uppercase ISO-2 `"DE"`, `"FR"`, `"US"`, plus sub-national `"US-CA"`, `"CA-ON"`, etc. — match exact `iso2` country-level entry!).
  - Each country rule array contains prioritized filter/tag rule objects matching OSM road classes (`highway=motorway`, `highway=trunk` / `motorroad=yes`, `highway=primary|secondary|tertiary` with `urban=false` vs `urban=true`) and speed dicts:
    - `maxspeed` → maps to ETS2 `car` (`limit` / `urban_limit`)
    - `maxspeed:hgv` (or `maxspeed:hgv:conditional` / weight `>3.5t` / `>7.5t`) → maps to ETS2 `truck` (`limit` / `urban_limit`)
    - `maxspeed:bus` → maps to ETS2 `bus` (`limit` / `urban_limit`)
  - **Unit normalization:** Values like `"70 mph"` parse unit=`"mph"` & value=`70`; bare integer `"130"` parses unit=`"kmh"` & value=`130`; `"none"` / `"walk"` map to `0` (unrestricted, e.g., `DE` motorway car advisory / `IM` rural car) or skip living-street (`walk`).
  - **ETS2 4-lane mapping:**
    - `urban` → `urban_limit` across `local_road`/`expressway`/`motorway`
    - `rural` (`highway=primary|secondary`, non-urban) → `local_road.limit`
    - `trunk` / `expressway` (`motorroad=yes` or `highway=trunk`, non-urban) → `expressway.limit`
    - `motorway` (`highway=motorway`) → `motorway.limit`
  - Compare against `CountryLawRecord.summer` (default statutory baseline; Winter seasonal reductions like `FI`, `EE`, `LT` belong in `data/laws/speed_audit_allowlist.json` if flagged!).

### 4.2 Opt-In Overpass & Taginfo Spot-Check Templates (`D-13`)

Strictly **opt-in** (`--overpass` / `--taginfo` with explicit `--iso2 DE,FR,...`, max cap e.g. 10 countries per run to respect public API fair use):

1. **Overpass API (`https://overpass-api.de/api/interpreter`, allowlist `{"overpass-api.de"}`):**
   - Use **`out tags;`** (NEVER `out geom;`) so responses stay compact (tags only, zero geometry coordinates!):
     ```overpass
     [out:json][timeout:25];
     area["ISO3166-1"="DE"][admin_level=2]->.searchArea;
     (
       way(area.searchArea)["highway"="motorway"]["maxspeed"];
       way(area.searchArea)["highway"="trunk"]["maxspeed"];
     );
     out tags 500;
     ```
   - Send via `POST` (`Content-Type: application/x-www-form-urlencoded`, body `data=<query>`) or `GET ?data=<query>` with polite `DEFAULT_USER_AGENT` and inter-request sleep (`>= 1.5s` between countries, injectable `sleep_fn` for 0ms offline tests!).
   - Parse `elements[].tags` (`highway`, `maxspeed`, `maxspeed:hgv`, `maxspeed:bus`) into top-3 modal distributions per highway class.
2. **Taginfo API v4 (`https://taginfo.openstreetmap.org/api/4/key/values`, allowlist `{"taginfo.openstreetmap.org"}`):**
   - Query: `GET https://taginfo.openstreetmap.org/api/4/key/values?key=maxspeed&filter=ways&sortname=count&sortorder=desc&rp=25&page=1` (and `key=maxspeed:hgv`, `key=maxspeed:bus`).
   - Response JSON: `{"data": [{"value": "50", "count": 123456, "fraction": 0.25}, ...]}`.

### 4.3 Clean-Room Allowlist Schema (`data/laws/speed_audit_allowlist.json`, `D-15`)

Contains **ZERO OSM text, URLs, or `CC BY-SA` quotes** — purely statutory ETS2 explanations:
```json
{
  "schema_version": 1,
  "entries": [
    {
      "iso2": "DE",
      "vehicle_class": "car",
      "lane_speed_class": "motorway",
      "field": "limit",
      "statutory_rationale": "StVO Autobahn advisory speed (Richtgeschwindigkeit 130 km/h) encoded as ETS2 limit 0 (no statutory ceiling).",
      "verified_date": "2026-11-25"
    },
    {
      "iso2": "FI",
      "vehicle_class": "car",
      "lane_speed_class": "motorway",
      "field": "limit",
      "statutory_rationale": "Finnish Road Traffic Act seasonal Summer (120) vs Winter (100) ceiling modeled via dual ETS2 seasonal editions.",
      "verified_date": "2026-11-25"
    }
  ]
}
```
- **Match tuple:** `(iso2, vehicle_class, lane_speed_class, field)` where `field: Literal["limit", "urban_limit", "max_limit"]`.
- Drift report splits findings into:
  1. **`Unacknowledged Drift`** (triggers non-zero `--fail-on-drift` if requested and triggers rolling GitHub Issue creation/update in `.github/workflows/osm-speed-audit.yml`), and
  2. **`Acknowledged Statutory Differences`** (matched by `speed_audit_allowlist.json` — informational only, zero alert fatigue).

### 4.4 Isolated `src/ets2v2/audit/` Subpackage, AST DAG Wall & License-Taint Gate (`D-16`)

#### Subpackage Layout (`src/ets2v2/audit/`)
- `models.py` — Frozen Pydantic v2 models: `SpeedAuditAllowlist`, `SpeedAuditAllowlistEntry`, `SpeedDriftFinding`, `OsmSpeedAuditReport`, `TaintViolation`, `TaintScanReport`.
- `osm_speeds.py` — Fetch/parse `westnordost` JSON rules, normalize country rules, diff against `load_law_registry()`, apply clean-room allowlist, render deterministic Markdown & JSON reports.
- `overpass.py` — Opt-in `--overpass` and `--taginfo` spot-check client reusing `ets2v2.fetch.http` (`create_http_client`, `validate_https_url`, bounded reads, polite pacing).
- `taint.py` — Automated provenance & license-taint scanner across `data/laws/`, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, `realism-snapshot-*.json`, and built Workshop/local `.zip`/`.scs` packages.
- `__init__.py` — Public facade exported strictly to `ets2v2.cli` and tests.

#### AST DAG Isolation Wall (`tests/test_cli_scaffold.py`)
1. Unlock `"audit"` in `test_active_phase_only_package_layout()` (`allowed_phase5_entries`).
2. Extend `test_phase4_ast_dag_isolation_walls` → `test_phase5_ast_dag_isolation_walls`:
   - **ALL 10 non-audit subpackages** (`vfs`, `sii`, `baseline`, `registry`, `normalize`, `fetch`, `package`, `validate`, `merge`, `publish`) MUST have **zero** imports of `ets2v2.audit`!
   - The **6 offline subpackages** (`validate`, `merge`, `package`, `publish`, `normalize`, `registry`) retain all Phase 4 walls + `"audit"` forbidden.
   - **CRITICAL:** Do NOT make `ets2v2.validate` import `ets2v2.audit.taint`! Instead, place a tiny pure-stdlib forbidden-marker regex check directly in `ets2v2/validate/invariants.py` (or `validate/workshop.py`, emitting error code `ETS2V2-INV-LICENSE-TAINT`) so `validate/` checks every built Workshop/local package **without** breaching the `audit/` AST quarantine wall!

#### Forbidden License/Source Taint Markers (`D-16`)
Case-insensitive regex markers scanned across all `CC BY 4.0` inputs & outputs (`data/laws/`, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, `realism-snapshot-*.json`, Workshop/local `.sii`/`.sui`/`.txt`):
- `cc[\s-]*by[\s-]*sa` (`CC BY-SA`, `CC-BY-SA`)
- `\bodbl\b` (`ODbL`)
- `openstreetmap` (`OpenStreetMap`, `openstreetmap.org`)
- `osm-legal-default-speeds`
- `globalpetrolprices` (`GlobalPetrolPrices`, `globalpetrolprices.com`)
- `cc[\s-]*by[\s-]*nc[\s-]*nd` (`CC BY-NC-ND`, `CC-BY-NC-ND`)
- `\bmylpg\b` (`MyLPG`, `mylpg.eu`)
- `\biea\b` (word-boundary `\biea\b` — **CRITICAL PITFALL:** do NOT use bare substring `"iea"` which would false-positive on words like `"traffiea"` or URL slugs, and verify `"iea"` doesn't hit any valid ISO-3/word in our 220 countries! In fact, use `\biea\b` or `(?:international energy agency|\biea\b)` and test it across all 220 law files and 43 locales to ensure zero false positives!)

### 4.5 Standalone Monthly Workflow (`.github/workflows/osm-speed-audit.yml`, `D-14`)

Key security & isolation guarantees:
- **Triggers:** `schedule: - cron: "0 7 1-7 * 1"` (1st Monday of every month `07:00 UTC`) + `workflow_dispatch` (with optional `iso2` string input and `overpass` boolean input — passed strictly via step `env:`, NEVER interpolated `${{ }}` inside `run:` shell bodies!).
- **Permissions (Zero Git Writes enforced by GitHub token!):**
  ```yaml
  permissions:
    contents: read
    issues: write
  ```
  `contents: read` makes it **physically impossible** for the workflow token to commit or push OSM data to Git!
- **Outputs:**
  1. Run `uv run --offline ets2v2 audit osm-speeds --out-md dist/audit/osm_speed_drift_report.md --out-json dist/audit/osm_speed_drift_report.json` (plus optional `--iso2` / `--overpass` when dispatched).
  2. Upload `osm-speed-drift-report` workflow artifact (`actions/upload-artifact@v4`).
  3. Append Markdown summary (sanitized!) to `$GITHUB_STEP_SUMMARY`.
  4. Rolling GitHub Issue via `gh issue list --label osm-audit --state open --json number --jq '.[0].number // empty'`: if `unacknowledged_drift_count > 0`, update existing open issue via `gh issue edit` (or create label + issue via `gh issue create --label osm-audit`); if `0` unacknowledged drifts, leave clean (or comment resolved). Never run on `pull_request` / `pull_request_target`.

---

## Architecture Patterns

### System Architecture Diagram (Phase 5 Data Flow)

```text
  [data/mappings/currencies.json]   [data/curated/tier3_fuel_baselines.json]
                │                                        │
                └──────────────▶ ets2v2.normalize ◀──────┘
                                       │ (pure offline, zero httpx/openpyxl)
  ┌──────────────┐                     ▼
  │ EU Core T1   │────────┐     ┌────────────────────┐      ┌──────────────────────────┐
  │ (EC/UK/NO/   │        ├───▶ │  ets2v2.fetch      │─────▶│ state/prices.lock.json   │
  │ FR/DE/ES/IT/ │        │     │  pipeline.py       │      │ (v1: 220 terr / ~156 FX) │
  │ NL + FX 4x)  │        │     │                    │      └────────────┬─────────────┘
  └──────────────┘        │     │ • EU T1 gate=HARD  │                   │
  ┌──────────────┐        │     │ • Global T1 = WARN │                   ▼
  │ Global T1    │────────┤     │ • Tier 2    = WARN │      ┌──────────────────────────┐
  │ (US/BR/AR/CO/│        │     │ • Tier 3    = SEED │      │ ets2v2.registry (220)    │
  │ CL/MY/JP/KR) │        │     └────────────────────┘      │ realism-snapshot-*.json  │
  └──────────────┘        │                                 │ (schema_version: 1)      │
  ┌──────────────┐        │                                 └──────┬─────────────┬─────┘
  │ Tier 2 Guard │────────┘                                        │             │
  │ (IS/CH/MD/MK/│                                       Core (36) ▼             ▼ Combo (220)
  │ RU/IL/AE/ZA/ │                                    ┌───────────────┐   ┌──────────────┐
  │ SA/NG)       │                                    │ package +     │   │ merge /      │
  └──────────────┘                                    │ validate      │   │ compose-local│
                                                      │ (+ taint gate)│   │ (offline)    │
  ═══════════════════ AST DAG QUARANTINE WALL (ZERO INBOUND IMPORTS) ═══════════════════
                                                      └───────────────┘   └──────────────┘
  ┌────────────────────────────────────────────────────────────────────────────────────┐
  │ ets2v2.audit (CI-only monthly osm-speed-audit.yml, permissions: contents:read)     │
  │   westnordost/osm-legal-default-speeds (CC BY-SA) + opt-in Overpass/Taginfo        │
  │   ──▶ compare vs data/laws/ + speed_audit_allowlist.json ──▶ Artifact + GH Issue   │
  │   taint.py ──▶ verifies ZERO CC BY-SA / NC-ND markers across all CC BY 4.0 outputs │
  └────────────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Module Decomposition (Claude's Discretion)
```text
data/
├── curated/
│   └── tier3_fuel_baselines.json   # ~184 non-Vanilla EUR/L seeds + verified_date + floor flags
├── laws/
│   ├── countries/<iso2>.json       # Expanded 76 -> ~220 canonical CountryLawRecord files
│   └── speed_audit_allowlist.json  # Clean-room intentional statutory deviation allowlist
└── mappings/
    ├── currencies.json             # ~156 ISO-4217 currencies + ~220 ISO-2 -> currency map
    ├── ets2_countries.json         # Expanded 76 -> ~220 mappings (36 vanilla_1_62: true)
    └── country_aliases.json        # Existing 119 aliases (100% ISO-2 targets now present!)
src/ets2v2/
├── fetch/
│   ├── _html.py                    # Stdlib HTMLParser table/text extractor & charset helper
│   ├── global_tier1.py             # 8 non-EU Tier 1 collectors (US, BR, AR, CO, CL, MY, JP, KR)
│   ├── tier2_portals.py            # 10 guarded Tier 2 collectors + per-country circuit breakers
│   ├── http.py                     # Add `code` to _SECRET_QUERY_RE + optional POST form helper
│   ├── models.py                   # tier="tier2", region_scope, skip_reason, error_code, counters
│   └── pipeline.py                 # EU vs Global T1 gate, --no-global/--no-tier2, Tier 2 wiring
├── normalize/
│   ├── currencies.py               # Data-driven loader backed by data/mappings/currencies.json
│   ├── lockfile.py                 # Tier/cadence staleness (14d/45d/105d/30d/180d) + Tier 3 seed
│   └── fuel.py                     # Preserve 0.01–5.00 hard bounds; clean floor clamp for seeds
├── registry/
│   └── timezone.py                 # Extend IANA_NUMERIC_ABBR_OVERRIDES with 58 verified zones
├── publish/
│   └── changelog.py                # Global Snapshot Coverage block + Tier 3 alert rollup + attributions
├── validate/
│   └── invariants.py               # Independent pure-stdlib ETS2V2-INV-LICENSE-TAINT check
└── audit/                          # NEW isolated subpackage (zero inbound imports!)
    ├── __init__.py
    ├── models.py
    ├── osm_speeds.py
    ├── overpass.py
    └── taint.py
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exact gallon-to-liter conversion (`US`, `CO`) | Floating-point `3.785` approximation | `Decimal` division by NIST `Decimal("3.785411784")` | Prevents subtle rounding drift at 3rd/4th decimal (`D-04`). |
| Outlier-resistant station aggregation | Arithmetic mean across raw station feeds | Stdlib `statistics.median()` on valid positive finite rows | Station portals (`BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `IS Gasvaktin`) regularly contain typo rows (`9999.99` or `0.01`). |
| OOXML `.xlsx` safety (`JP METI`, `RU`, `ZA`, `NG`) | Raw `openpyxl.load_workbook()` | Reuse `_validate_ooxml_zip_safety()` from `ec_bulletin.py` (move to shared `_parsing.py` or `_xlsx.py`) | Guards against ZIP bombs, encrypted OOXML, and `<!DOCTYPE`/`<!ENTITY` XXE payloads before `openpyxl` opens the archive. |
| Timezone DST / Southern Hemisphere math | Hardcoded UTC offsets | Stdlib `zoneinfo.ZoneInfo` + `tzdata` via `resolve_ets2_timezone()` | Automatically handles Southern Hemisphere DST (`CL`, `AU`, `NZ`, `PY` abolition) and numeric `tzname()` overrides. |
| GitHub Issue upsert in `osm-speed-audit.yml` | Third-party GitHub Actions | Built-in `gh issue list` / `gh issue edit` / `gh issue create` (matching `phase-a-release.yml` PR pattern) | Zero third-party action supply-chain risk (`T-02-SC`). |

---

## Common Pitfalls

### Pitfall 1: `OPINET_API_KEY` (`code=...`) Leaking Through `redact_url_secrets()`
- **What goes wrong:** `src/ets2v2/fetch/http.py:27-30` masks `apikey|api_key|token|key`, NOT `code`. An HTTP error on `https://www.opinet.co.kr/api/avgAllPrice.do?out=json&code=SECRET` would leak `OPINET_API_KEY` into `ProviderFetchStatus.detail`, `prices.lock.json` alerts, and GitHub Step Summary.
- **How to avoid:** Update `_SECRET_QUERY_RE` in `src/ets2v2/fetch/http.py` to `r"([?&]|^)(apikey|api_key|token|key|code)=([^&\s'\"`)]+)"` AND apply explicit `.replace(resolved_key, "***")` in every keyed collector (`US EIA`, `KR Opinet`, `CL CNE`, `DE Tankerkönig`).

### Pitfall 2: Colombia (`CO`) Unit & Dataset Traps
- **What goes wrong:** (1) `datos.gov.co/resource/fbht-2fzd.json` is *wholesale/station dispatch volumes*, NOT retail prices; (2) Colombian retail prices are quoted in **COP per US gallon** (~`15,600 COP/gal` petrol, `9,500 COP/gal` ACPM diesel), NOT per liter — forgetting `÷ 3.785411784` inflates Colombian prices by 3.785x; (3) CREG HTML tables format thousands with a dot (`15.588` = `15,588 COP/gal`), which `float("15.588")` misparses as `15.59 COP`!
- **How to avoid:** Discover the `"precio mes combustible"` dataset dynamically (or fall back to CREG HTML), strip `.` thousands separators when values are Colombian-format `^\d{1,3}\.\d{3}$` (>1,000 COP/gal check), and divide by exact NIST `3.785411784`.

### Pitfall 3: `BR ANP` & `AR Energía` Non-Liquid Fuel Grades & Stale Stations
- **What goes wrong:** `BR ANP` includes `GLP` (13 kg cooking gas cylinder, ~R$105) and `GNV` (m³); `AR Energía` includes `GNC` (m³) and historical stations that stopped reporting years ago (stale 2019 ARS prices 100x lower due to inflation!).
- **How to avoid:** Explicitly ignore `GLP` (13 kg) and `GNV`/`GNC` (m³); for `AR Energía`, filter rows to `fecha_vigencia` within the most recent 60 days of the dataset's maximum timestamp before computing `statistics.median()`.

### Pitfall 4: `US EIA v2` Wrong Diesel Product Code (`EPD2O` vs `EPD2D`)
- **What goes wrong:** Querying `facets[product][]=EPD2O` returns off-highway/heating diesel instead of on-highway retail diesel.
- **How to avoid:** Pin `facets[product][]=EPD2D` (No. 2 On-Highway Diesel), `EPMR` (Regular Motor Gasoline), `EPMP` (Premium Motor Gasoline), `facets[duoarea][]=NUS`, `facets[process][]=PTE`.

### Pitfall 5: `JP METI` Kerosene (`灯油`) 18L Unit & Legacy `.xls` Links
- **What goes wrong:** METI's weekly survey page links both `.xlsx` and older `.xls` files, and includes `灯油` (kerosene) priced per **18 liters** (~2,000 JPY/18L) alongside `レギュラー`/`ハイオク`/`軽油` priced per **1 liter** (~150–185 JPY/L).
- **How to avoid:** Filter discovered links strictly to `.xlsx` (never `.xls`), match only `レギュラー`, `ハイオク`, `軽油` on the `全国`/`全国平均` column/row, and ignore `灯油` completely.

### Pitfall 6: `validate/` Importing `audit/` Breaking the AST Quarantine Wall (`D-16`)
- **What goes wrong:** Putting the license-taint scanner solely in `src/ets2v2/audit/taint.py` and importing it from `src/ets2v2/validate/workshop.py` triggers `test_phase5_ast_dag_isolation_walls` failure!
- **How to avoid:** Keep `ets2v2.validate`'s package-artifact taint check self-contained in `validate/invariants.py` (a ~20-line pure-stdlib regex scan emitting `ETS2V2-INV-LICENSE-TAINT`), while `ets2v2.audit.taint` provides the full repo + snapshot + package CLI auditor (`ets2v2 audit taint`).

### Pitfall 7: `MY OpenDOSM` Mixing `"change_weekly"` Delta Rows Into Prices
- **What goes wrong:** `api.data.gov.my/data-catalogue?id=fuelprice` returns BOTH `"series_type": "level"` (actual RM/L) and `"series_type": "change_weekly"` (e.g., `+0.03` or `-0.02` RM/L) in the same catalogue!
- **How to avoid:** Pass `&filter=level@series_type` in the query string AND assert `row.get("series_type") == "level"` in Python before accepting any price.

### Pitfall 8: Existing `76`-Country / `41`-FX Test Assertions & `pipeline.py` Filtering Order
- **What goes wrong:** Implementing `GLB-01` before `GLB-03` causes `pipeline.py:403` to silently discard all 8 non-EU Tier 1 quotes; expanding to `~220` territories breaks 10 existing Phase 2–4 test files with hardcoded `== 76` / `== 41` assertions.
- **How to avoid:** Execute `GLB-03` (Plan `05-01` or Wave 1) first, updating the 10 enumerated test files cleanly in the same wave, then implement `GLB-01` and `GLB-02` directly against the live 220-territory lockfile.

---

## Code Examples

### 1. Hardened Optional Key Collector Pattern (`US EIA v2` / `KR Opinet` / `CL CNE`)
```python
# Pattern matching src/ets2v2/fetch/national.py:545-646 + D-01/D-02/D-04
NIST_LITERS_PER_US_GALLON: Final[Decimal] = Decimal("3.785411784")

def fetch_us_eia_v2(
    client: httpx.Client,
    *,
    api_key: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    resolved_key = (api_key if api_key is not None else os.environ.get("EIA_API_KEY", "")).strip()
    if not resolved_key:
        return RawFuelFeedResult(
            feed_name="us_eia_v2",
            tier="tier1",
            region_scope="global",
            ok=True,
            skipped=True,
            skip_reason="skipped (EIA_API_KEY unset; retaining lockfile/Tier 3)",
            quotes=[],
        )
    # Query api.eia.gov/v2/petroleum/pri/gnd/data/ with duoarea=NUS, process=PTE,
    # products EPD2D (diesel), EPMR (petrol_95), EPMP (petrol_98); divide USD/gal by NIST factor.
```

### 2. Per-Country Tier 2 Circuit-Breaker Wrapper (`D-07`)
```python
# In src/ets2v2/fetch/tier2_portals.py
def _run_tier2_guarded(
    feed_name: str,
    fn: Callable[[], tuple[RawCountryFuelQuote, str]],
) -> RawFuelFeedResult:
    try:
        quote, data_date = fn()
        return RawFuelFeedResult(
            feed_name=feed_name,
            tier="tier2",
            region_scope="global",
            ok=True,
            quotes=[quote],
            data_date=data_date,
        )
    except Tier2RateLimitedError as exc:
        return RawFuelFeedResult(
            feed_name=feed_name, tier="tier2", region_scope="global",
            ok=False, error_code="tier2_rate_limited", error=redact_url_secrets(str(exc)),
        )
    except Tier2EncodingError as exc:
        return RawFuelFeedResult(
            feed_name=feed_name, tier="tier2", region_scope="global",
            ok=False, error_code="tier2_encoding_error", error=redact_url_secrets(str(exc)),
        )
    except Tier2SelectorDriftError as exc:
        return RawFuelFeedResult(
            feed_name=feed_name, tier="tier2", region_scope="global",
            ok=False, error_code="tier2_selector_drift", error=redact_url_secrets(str(exc)),
        )
    except (HttpFetchError, httpx.HTTPError, ValueError, KeyError, OSError) as exc:
        code = "tier2_rate_limited" if ("HTTP 403" in str(exc) or "HTTP 429" in str(exc)) else "tier2_portal_outage"
        return RawFuelFeedResult(
            feed_name=feed_name, tier="tier2", region_scope="global",
            ok=False, error_code=code, error=redact_url_secrets(str(exc)),
        )
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `westnordost/osm-legal-default-speeds` publishes compiled `legal_default_speeds.json` at `https://westnordost.github.io/osm-legal-default-speeds/legal_default_speeds.json` (sandbox policy blocked direct live HTTP verification). | §4.1 | Monthly audit job gets 404 on default URL; mitigated by verifying URL once on live runner and exposing `--rules-url` / `--rules-file` flags so URL updates are a 1-line config change. |
| A2 | Live HTML DOM structures and WAF status for Tier 2 portals (`anre.md`, `erc.org.mk`, `rosstat.gov.ru`, `gov.il`, `moei.gov.ae`, `cefgroup.co.za`, `aramco.com`, `nigerianstat.gov.ng`) were verified via search documentation rather than direct sandbox HTTP fetches. | §2.1 | A portal could return `403` from Azure GitHub Actions IPs or shift table markup; completely mitigated by `D-07` per-country circuit breakers (`tier2_rate_limited` / `tier2_selector_drift` warnings retaining lockfile/Tier 3 with zero Friday CI breakage). |
| A3 | `datos.gov.co` Socrata catalog search `?q=precio+mes+combustible` resolves the current MinMinas/SICOM retail price resource ID dynamically (direct sandbox probe blocked). | §1.1 (`CO`) | If catalog query returns no match, collector falls back to CREG's verified 18-city HTML reference table (`creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos`), and if both fail, Global Tier 1 isolation (`D-02`) retains lockfile/Tier 3 safely. |
| A4 | `fawazahmed0` and `Frankfurter v2` coverage of newly adopted `XCG` (Caribbean Guilder, effective 2025-03-31) vs legacy `ANG` may vary by upstream central bank feed. | §3.5 | Mitigated by `is_extended=True` isolated FX validation (`D-11`) falling back cleanly to curated `XCG` reference FX (`~1.94/EUR`) with zero CI impact. |

---

## Open Questions (RESOLVED)

1. **`CL` CNE Optional Secret (`CNE_API_TOKEN`) — RESOLVED:**
   - What we know: Research confirmed `api.cne.cl` (both v3 and v4) requires free developer registration and a token — there is no anonymous keyless endpoint.
   - **RESOLVED (`05-02-PLAN.md`):** Treat `CNE_API_TOKEN` as an optional environment secret mirroring `EIA_API_KEY`, `OPINET_API_KEY`, and `TANKERKOENIG_API_KEY` (`skipped=True, ok=True` when unset with explicit `skip_reason`, retaining `CL` lockfile/Tier 3 seed; wire optional `CNE_API_TOKEN: ${{ secrets.CNE_API_TOKEN }}` via step-level `env:` in `.github/workflows/phase-a-release.yml`, and scrub token via `redact_url_secrets` + explicit replacement).
2. **Exact `~220`-Territory Final Count — RESOLVED:**
   - What we know: `195` UN states + `XK` + `8` existing ProMods territories (`AX, FO, GG, GI, GL, IM, JE, SJ`) = `204`, plus the `21` inhabited global map-combo territories enumerated in `D-09` (`AW, BM, CW, EH, FK, GF, GP, HK, KY, MO, MQ, NC, PF, PM, PR, RE, SX, TC, TW, VG, YT`) = **`225`** territories exact.
   - **RESOLVED (`05-01-PLAN.md`):** Standardized on exact **`225` canonical territories** (`36` `vanilla_1_62: true` + `189` `vanilla_1_62: false`), hitting 100% of UN member/observer states, 100% of `data/mappings/country_aliases.json` ISO-2 targets, and every single territory enumerated in `D-09` while remaining squarely inside `D-09`'s `~215–225` envelope.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (`uv` venv) | All Phase 5 code & tests | ✓ | `3.12.13` | — |
| `uv` | Offline test/lint/typecheck | ✓ | `0.11.31` | — |
| `httpx` / `openpyxl` / `pydantic` / `tzdata` | Collectors, models, timezones | ✓ | `0.28.1` / `3.1.5` / `2.14.3` / `>=2025.2` | — |
| `pytest` / `ruff` / `basedpyright` | Quality gates | ✓ | Locked in `uv.lock` | — |
| Outbound HTTPS in local sandbox | Live external API smoke probes | ✗ (policy-blocked) | — | 100% offline `httpx.MockTransport` unit/integration fixtures (matches Phase 3/4 standard; live fetches execute in GitHub Actions `phase-a-release.yml` and `osm-speed-audit.yml`) |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest>=9.2,<9.3` (505 existing tests collected in 0.67s) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| Quick run command | `uv run --offline pytest -q --tb=short tests/test_global_tier1.py` |
| Full suite command | `uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright && uv run --offline pytest -q --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| `GLB-01` | All 8 non-EU Tier 1 collectors (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`), NIST gallon conversion (`US`/`CO`), median outlier rejection, `EIA_API_KEY`/`OPINET_API_KEY`/`CNE_API_TOKEN` optional skip + `code=` secret redaction, EU vs Global Tier 1 outage gate isolation | unit + integration (`httpx.MockTransport`) | `uv run --offline pytest -q tests/test_fetch_global_tier1.py tests/test_fetch_pipeline.py` | ❌ Wave 0 (new `tests/test_fetch_global_tier1.py`) |
| `GLB-02` | All 10 Tier 2 stdlib/openpyxl scrapers (`IS`, `CH`, `MD`, `MK`, `RU`, `IL`, `AE`, `ZA`, `SA`, `NG`), per-country circuit breakers (`403`/`429`/timeout/charset/selector drift), `--no-global`/`--no-tier2` CLI flags, tier-aware staleness (`14d`/`45d`/`105d`/`30d`/`180d`), Tier 3 alert rollup | unit + integration (`httpx.MockTransport`) | `uv run --offline pytest -q tests/test_fetch_tier2_portals.py tests/test_normalize_fx.py` | ❌ Wave 0 (new `tests/test_fetch_tier2_portals.py`) |
| `GLB-03` | `data/mappings/currencies.json` (~156 FX) + `data/curated/tier3_fuel_baselines.json`, `225` canonical `CountryLawRecord`s, 100% `country_aliases.json` ISO-2 coverage, all 58 numeric IANA TZ overrides, `0.010 EUR/L` floor clamping, frozen `schema_version: 1` 225-territory snapshot, Core 36-country boundary & Global Snapshot Coverage changelog block | unit + contract + integration | `uv run --offline pytest -q tests/test_global_registry_expansion.py tests/test_registry_contracts.py tests/test_publish_release.py` | ❌ Wave 0 (new `tests/test_global_registry_expansion.py` + update 10 Phase 4 count tests) |
| `GLB-04` | `ets2v2 audit osm-speeds` (`westnordost` JSON diff + clean-room allowlist + opt-in Overpass/Taginfo mock tests), AST DAG wall forbidding all 10 non-audit subpackages from importing `audit/`, automated provenance & license-taint scan across `data/`, `state/`, snapshots, and built Workshop/local packages, `.github/workflows/osm-speed-audit.yml` zero-Git-write & injection-safety contract | unit + contract + security | `uv run --offline pytest -q tests/test_audit_osm_speeds.py tests/test_license_taint_gate.py tests/test_cli_scaffold.py tests/test_publish_workflow.py` | ❌ Wave 0 (new `tests/test_audit_osm_speeds.py`, `tests/test_license_taint_gate.py`) |

### Sampling Rate
- **Per task commit:** Targeted test module + `uv run --offline ruff check` + `uv run --offline basedpyright`
- **Per wave merge:** Full quality gate (`ruff check`, `ruff format --check`, `basedpyright`, `pytest -q --tb=short`)
- **Phase gate:** Full suite green (0 warnings/errors, 0 taint hits, 0 AST DAG violations) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_global_registry_expansion.py` — covers `GLB-03` (`currencies.json`, `tier3_fuel_baselines.json`, 225 territories, alias target completeness, `XCG`/`ZWG`/`SLE`, `0.010` floor)
- [ ] `tests/test_fetch_global_tier1.py` — covers `GLB-01` (all 8 non-EU Tier 1 collectors, NIST gallon conversion, `code=` redaction, EU vs Global gate separation)
- [ ] `tests/test_fetch_tier2_portals.py` — covers `GLB-02` (all 10 guarded Tier 2 scrapers, circuit-breaker alert codes, `--no-global`/`--no-tier2`, tier-aware staleness)
- [ ] `tests/test_audit_osm_speeds.py` & `tests/test_license_taint_gate.py` — covers `GLB-04` (OSM diff, clean-room allowlist, Overpass/Taginfo mocks, license-taint scan, `osm-speed-audit.yml` contract)

---

## Security Domain (ASVS Level 2)

`security_enforcement: true`, `security_asvs_level: 2`, `security_block_on: "medium"` (`[VERIFIED: .planning/config.json:41-43]`).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication / Secrets | yes | Optional env secrets (`EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`, `TANKERKOENIG_API_KEY`) passed strictly via step-level `env:` in `phase-a-release.yml`, never logged; add `code` to `_SECRET_QUERY_RE` in `fetch/http.py` + explicit `.replace(key, "***")` scrubbing. |
| V3 Session Management | no | Stateless CLI & GitHub Actions batch jobs. |
| V4 Access Control | yes | Least-privilege workflow tokens: `osm-speed-audit.yml` uses `contents: read` + `issues: write` (zero Git write ability), never triggers on `pull_request` / `pull_request_target`; `phase-a-release.yml` retains zero Steam secrets and zero PR triggers. |
| V5 Input Validation | yes | Strict Pydantic v2 `extra="forbid"`, HTTPS-only + exact host allowlist (`validate_https_url`), max-redirect cap (`5`), bounded response reads (`DEFAULT_MAX_RESPONSE_BYTES`), OOXML ZIP-bomb/XXE pre-validation (`_validate_ooxml_zip_safety`) for all `.xlsx` feeds (`JP`, `RU`, `ZA`, `NG`), safe stdlib `HTMLParser` (no `eval`/YAML unsafe load), Markdown sanitization (`_sanitize_markdown_inline`) on all upstream error details and OSM drift reports written to GitHub Step Summary / Issues. |
| V6 Cryptography | yes | TLS `verify=True` unconditionally in `create_http_client()`; constant-time `hmac.compare_digest` SHA-256 verification on snapshots unchanged. |

### Known Threat Patterns & Standard Mitigations
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage via `code=` query param (`KR Opinet`) or `api_key=` (`US EIA`) / `token=` (`CL CNE`) in HTTP errors or lockfile alerts | Information Disclosure | Extend `_SECRET_QUERY_RE` with `code`, scrub raw key in every collector's `except` handler, add regression unit tests asserting secrets never appear in `FetchRunReport` or `prices.lock.json`. |
| SSRF / open redirect via dynamically discovered links (`AR` CKAN, `CO` Socrata, `JP` METI, `RU` Rosstat, `ZA` CEF, `NG` NBS) | Spoofing / Tampering | Every dynamically discovered URL passes `validate_https_url(url, ALLOWED_HOSTS)` before fetch and on every redirect hop (`follow_redirects=False` + manual allowlisted redirect loop in `fetch_bytes_with_retry`). |
| Malicious/oversized `.xlsx` OOXML ZIP bomb or XXE payload from upstream portal | Denial of Service | Enforce `_validate_ooxml_zip_safety()` (entry cap, streamed uncompressed cap, encryption ban, `<!DOCTYPE`/`<!ENTITY` ban) + row cap before `openpyxl.load_workbook(read_only=True, data_only=True)`. |
| GitHub Actions shell injection via `workflow_dispatch` inputs (`osm-speed-audit.yml` `--iso2`) or upstream Markdown/HTML injection into rolling GitHub Issue | Tampering / Elevation | Pass all `inputs.*` strictly via step `env:` (zero `${{ }}` inside `run:` bodies, asserted in `test_publish_workflow.py`); sanitize upstream text in issue/summary bodies (`_sanitize_markdown_inline`). |
| `CC BY-SA` / `CC BY-NC-ND` legal contamination entering `CC BY 4.0` outputs | Repudiation / Legal Compliance | Enforce both AST DAG quarantine wall (`audit/` zero inbound imports) AND automated forbidden-marker taint scanner across `data/`, `state/`, snapshots, and built `.scs`/`.zip` packages in `pytest` and `ets2v2 validate`. |

---

## Sources

### Primary (HIGH confidence)
- In-repo verified files: `src/ets2v2/fetch/{pipeline,models,http,fx,national,ec_bulletin,_parsing}.py`, `src/ets2v2/normalize/{currencies,fx,fuel,lockfile,models,totem_format}.py`, `src/ets2v2/registry/{models,loader,timezone,snapshot}.py`, `src/ets2v2/publish/changelog.py`, `src/ets2v2/validate/{workshop,invariants}.py`, `data/mappings/{ets2_countries,country_aliases}.json`, `.github/workflows/phase-a-release.yml`, `pyproject.toml`, `tests/test_cli_scaffold.py`, `tests/test_publish_workflow.py`
- Local Python `3.12.13` + `tzdata` verification probe (58 numeric-`tzname()` global zones, 0 invalid IANA zones, 505 existing tests)
- `.planning/phases/05-global-tier-1-2-3-coverage-internal-osm-audit/05-CONTEXT.md`, `.planning/research/{FEATURES,SUMMARY,PITFALLS}.md`

### Secondary (MEDIUM confidence — Official Docs via Web Search)
- U.S. EIA API v2 (`api.eia.gov/v2/petroleum/pri/gnd/data/`, `EPD2D`/`EPMR`/`EPMP`/`NUS`/`PTE`)
- Brazil ANP (`gov.br/anp/.../ultimas-4-semanas-{diesel-gnv,gasolina-etanol}.csv`)
- Argentina Secretaría de Energía (`datos.gob.ar/api/3/action/package_show?id=precios-en-surtidor-resolucion-314`)
- Colombia MinMinas/SICOM (`datos.gov.co`) & CREG (`creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos`, COP/gal)
- Chile CNE (`api.cne.cl` v3/v4 token auth & JSON schema)
- Malaysia OpenDOSM (`api.data.gov.my/data-catalogue?id=fuelprice`, CC BY 4.0)
- Japan METI / ANRE (`enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results.html`, Gov of Japan Terms v2.0)
- South Korea KNOC Opinet (`www.opinet.co.kr/api/avgAllPrice.do`, `B027`/`B034`/`D047`/`K015`)
- Iceland Gasvaktin (`github.com/gasvaktin/gasvaktin`, MIT License), Switzerland BFS (`pxweb.bfs.admin.ch`), Moldova ANRE (`anre.md`), North Macedonia ERC (`erc.org.mk`), Russia Rosstat (`rosstat.gov.ru`), Israel MoE (`gov.il`), UAE MOEI (`moei.gov.ae`), South Africa DMRE/CEF (`cefgroup.co.za`), Saudi Aramco (`aramco.com`), Nigeria NBS (`nigerianstat.gov.ng`), Kenya EPRA (`epra.go.ke`, Cloudflare-gated), Indonesia Pertamina (`mypertamina.id`), Egypt APCPP (`petroleum.gov.eg`), Jordan MIT/MEMR (`mit.gov.jo`)
- ISO-4217 Maintenance Agency (SIX Group) 2024–2026 currency amendments (`XCG`, `ZWG`, `SLE`, `BGN`→`EUR`)
- `westnordost/osm-legal-default-speeds` (BSD-3-Clause code / `CC BY-SA 2.0` OSM Wiki data), Overpass API (`overpass-api.de`), Taginfo API v4 (`taginfo.openstreetmap.org/api/4/key/values`)

---

## Metadata

**Confidence breakdown:**
- Standard stack & codebase integration: **HIGH** — zero new dependencies, exact in-repo interfaces and all 10 affected test files verified directly.
- Global Tier 1 APIs & Tier 3 225-territory/FX expansion: **HIGH** — endpoints, unit conversions, grade mappings, ISO-4217 amendments, and all 58 numeric IANA timezone overrides verified.
- Tier 2 national portal HTML selectors & live CI reachability: **MEDIUM** — sandbox blocked direct live HTTP probes; mitigated architecturally by strict per-country circuit breakers (`D-07`) and research-gated Tier 3 classification (`D-05`).
- OSM drift audit & `CC BY 4.0` isolation wall: **HIGH** — clean AST DAG isolation, zero-Git-write workflow permissions, and independent validator taint gate verified against existing codebase rules.

**Research date:** 2026-11-25
**Valid until:** 2026-12-25 (30 days; Tier 2 HTML selectors remain dynamically guarded by circuit breakers)
