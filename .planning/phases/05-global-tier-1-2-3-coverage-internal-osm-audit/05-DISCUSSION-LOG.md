# Phase 5: Global Tier 1/2/3 Coverage & Internal OSM Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-25
**Phase:** 05-Global Tier 1/2/3 Coverage & Internal OSM Audit
**Areas discussed:** Non-EU Tier 1 Collectors & API Key Isolation; Tier 2 Guarded Portals, HTML Parsing & Staleness Cadence; Tier 3 Global 200+ Territories, FX Scaling & Changelog Scope; Internal CI OSM Speed-Limit Drift Audit & CC BY 4.0 Wall

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Non-EU Tier 1 Collectors & API Key Isolation (`GLB-01`) | Optional keys (`EIA_API_KEY`, `OPINET_API_KEY`), lightweight formats (JSON/CSV/`openpyxl` vs Parquet), unit/regional aggregation, and European vs Global CI outage gates | ✓ |
| Tier 2 Guarded Portals, HTML Parsing & Staleness Cadence (`GLB-02`) | Research-gated Tier 2 national portal roster, stdlib HTML parsing vs `beautifulsoup4`, per-country circuit breakers, and tier-aware staleness thresholds | ✓ |
| Tier 3 Global 200+ Territories, FX Scaling & Changelog Scope (`GLB-03`) | Territory roster (`~215–225`), moving seed/FX tables from Python dicts to JSON data files, global exotic FX isolation & `0.01 EUR/L` floor, and keeping Core changelogs readable | ✓ |
| Internal CI OSM Speed-Limit Drift Audit & CC BY 4.0 Wall (`GLB-04`) | Audit source (`osm-legal-default-speeds` vs Overpass/Taginfo), standalone CI workflow & reporting UX, intentional deviation allowlist, and AST + provenance license-taint gates | ✓ |

**User's choice:** Discuss all 4 areas in sequence.

---

## Area 1: Non-EU Tier 1 Collectors & API Key Isolation (`GLB-01`)

### Question 1: Optional API keys (`EIA_API_KEY` for US EIA v2, `OPINET_API_KEY` for KR Opinet)

| Option | Description | Selected |
|--------|-------------|----------|
| Optional secrets mirroring `TANKERKOENIG_API_KEY` | Skip cleanly when unset, retain lockfile/seed, inject in Friday CI secrets | ✓ |
| Try keyless public CSV/HTML fallbacks for US/KR when API keys are unset | Attempt unauthenticated fallback scraping for US/KR when keys are absent | |
| Require `EIA_API_KEY` and `OPINET_API_KEY` in Friday CI | Fail CI if either secret is missing | |

**User's choice:** Optional secrets mirroring `TANKERKOENIG_API_KEY` — skip cleanly when unset, retain lockfile/seed, inject in Friday CI secrets.

### Question 2: Interaction between non-EU Tier 1 feed outages and Friday CI's hard-fail gate

| Option | Description | Selected |
|--------|-------------|----------|
| Separate EU Core vs Global Tier 1 gates | EU Tier 1 total outage fails CI; Global Tier 1 outages warn and retain lockfile without blocking Core Workshop builds | ✓ |
| Shared Tier 1 gate | Succeed as long as at least one EU or Global Tier 1 feed succeeds | |
| Strict all-Tier-1 gate | Fail Friday CI if either EU or Global Tier 1 has zero live successes | |

**User's choice:** Separate EU Core vs Global Tier 1 gates.

### Question 3: Ingestion format and dependency policy for non-EU Tier 1 collectors

| Option | Description | Selected |
|--------|-------------|----------|
| Keep dependencies lightweight | Use JSON/CSV/XLSX via existing `httpx` + `openpyxl` + stdlib (no `pandas`/`pyarrow`/`xlrd`) | ✓ |
| Add `xlrd` for legacy JP METI `.xls` files | Add `xlrd` if `.xlsx` isn't available, still avoid `pandas`/`pyarrow` | |
| Add `pyarrow`/`pandas` | Support Parquet and arbitrary spreadsheet formats | |

**User's choice:** Keep dependencies lightweight — JSON/CSV/XLSX via existing `httpx` + `openpyxl` + stdlib.

### Question 4: Non-EU unit conversions and regional/station-level feed aggregation

| Option | Description | Selected |
|--------|-------------|----------|
| Exact US gallon conversion (`3.785411784` L/gal), official national average row where published, and outlier-resistant median for raw station/municipality CSVs (`AR`/`BR`/`CL`/`CO`) | Accurate NIST unit conversion + median robustness against bad station outliers | ✓ |
| Arithmetic mean across all station/municipality rows for raw CSVs | Simple average across raw rows | |
| Drop station-level CSV feeds if no pre-aggregated national summary endpoint exists | Skip station-level open datasets | |

**User's choice:** Exact US gallon conversion (`3.785411784` L/gal), official national average row where published, and outlier-resistant median for raw station/municipality CSVs (`AR`/`BR`/`CL`/`CO`).

---

## Area 2: Tier 2 Guarded Portals, HTML Parsing & Staleness Cadence (`GLB-02`)

### Question 1: Scoping the Tier 2 national portal roster during Phase 5 research and implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Research-gated full Tier 2 roster | Implement clean scrapers for every machine-readable HTML/XLSX/JSON portal (`CH`, `MD`, `MK`, `RU`, `IL`, `JO`, `AE`, `ZA`, `KE`, `NG`, `ID`, `SA`, `EG`, `IS`) and classify any Cloudflare/CAPTCHA/PDF-only portal cleanly as Tier 3 during research | ✓ |
| Small 5-portal Tier 2 starter set only | Only scrape `MD`, `MK`, `RU`, `ZA`, `KE`; leave the rest in Tier 3 | |
| Force scrapers for every named portal | Scrape all named portals even if PDF parsing or headless browser dependencies are required | |

**User's choice:** Research-gated full Tier 2 roster.

### Question 2: HTML parsing dependency for Tier 2 scrapers

| Option | Description | Selected |
|--------|-------------|----------|
| Stdlib-only (`html.parser` + `xml.etree.ElementTree` + regex) | Zero new runtime deps, strict `basedpyright` clean, minimal attack surface | ✓ |
| Add `beautifulsoup4` (MIT, pure Python) | CSS selector parsing without `lxml` | |
| Add `beautifulsoup4` + `lxml` (BSD C-extension) | Full HTML/XML C parser | |

**User's choice:** Stdlib-only (`html.parser` + `xml.etree.ElementTree` + regex).

### Question 3: Tier 2 per-country circuit breaker behavior on HTTP 403/429, encoding errors, or HTML selector drift

| Option | Description | Selected |
|--------|-------------|----------|
| Strict per-country `try/except` isolation with `tier="tier2"`, structured warning codes, lockfile retention, zero CI failure on Tier 2 errors, plus CLI filter flags (`--no-global` / `--no-tier2`) | Full fault isolation with actionable observability and zero CI disruption | ✓ |
| Fail Friday CI if more than half of Tier 2 portals fail in one run | Aggregate Tier 2 outage threshold fails CI | |
| Auto-disable failing Tier 2 portals in `state/prices.lock.json` until manually re-enabled | Stateful circuit-breaker lockout in lockfile | |

**User's choice:** Strict per-country `try/except` isolation with `tier="tier2"`, structured warning codes, lockfile retention, zero CI failure on Tier 2 errors, plus CLI filter flags.

### Question 4: Staleness thresholds and alert summaries at `200+` territories

| Option | Description | Selected |
|--------|-------------|----------|
| Tier-aware staleness thresholds (`14d` weekly Tier 1, `45d` monthly / `105d` quarterly Tier 2, `30d` degraded Tier 1 fallback, `180d` Tier 3 review cadence) with compact aggregated Tier 3 counts in changelogs/PRs | Matches real portal cadences and avoids 150+ noisy weekly alerts | ✓ |
| Keep flat `14d` Tier 1 and `30d` fallback/Tier 3 thresholds across all `200+` territories | Uniform thresholds across all tiers | |
| Disable staleness alerts entirely for Tier 2 and Tier 3 territories | No age tracking for Tier 2/3 | |

**User's choice:** Tier-aware staleness thresholds with compact aggregated Tier 3 counts in changelogs/PRs.

---

## Area 3: Tier 3 Global `200+` Territories, FX Scaling & Changelog Scope (`GLB-03`)

### Question 1: Global territory roster and registry completeness

| Option | Description | Selected |
|--------|-------------|----------|
| Full canonical expansion (`~215–225` territories: all ~195 UN states + ~20–30 inhabited ISO/map-combo territories like `TW`/`HK`/`MO`/`PR`/`GF`/`RE`/`CW`) with complete `CountryLawRecord` + `ets2_countries.json` + `prices.lock.json` entries | Complete `200+` global snapshot coverage for `compose-local` | ✓ |
| Minimal `200`-territory expansion (195 UN states + 5 territories) with complete law records | Bare-minimum `200` count | |
| Expand `prices.lock.json` to `200+` fuel entries only while leaving `data/laws/` at `76` territories | Fuel-only expansion without global laws | |

**User's choice:** Full canonical expansion (`~215–225` territories) with complete `CountryLawRecord` + `ets2_countries.json` + `prices.lock.json` entries.

### Question 2: Storage location for expanded global currency/FX metadata and Tier 3 curated fuel baselines

| Option | Description | Selected |
|--------|-------------|----------|
| Externalize into clean-room versioned JSON data files (`data/mappings/currencies.json` + `data/curated/tier3_fuel_baselines.json`) loaded by `ets2v2.normalize` | Clean data/code separation, readable PR diffs, Pydantic validated | ✓ |
| Keep all `215+` territories, `~155+` currencies, and Tier 3 seed prices hardcoded in Python dicts inside `src/ets2v2/normalize/currencies.py` | Single large Python literal file | |

**User's choice:** Externalize into clean-room versioned JSON data files (`data/mappings/currencies.json` + `data/curated/tier3_fuel_baselines.json`).

### Question 3: Exotic global FX currencies and ultra-subsidized (`<0.01 EUR/L`) fuel states

| Option | Description | Selected |
|--------|-------------|----------|
| Isolate all `~140+` non-Core global FX currencies with `is_extended=True` (warn + fallback, never block Friday Core CI) and keep the hard `0.01 EUR/L` floor (clamping sub-cent subsidized states like `IR`/`VE` at `0.010 EUR/L`) | Protects Core CI and prevents `0.000` free-fuel underflow in ETS2 | ✓ |
| Isolate non-Core global FX, but lower `MIN_EUR_PER_LITER` from `0.01` to `0.001 EUR/L` | Allow sub-cent prices directly | |
| Require live FX validation for all `~155` global currencies in Friday CI | Hard CI gate on exotic currencies | |

**User's choice:** Isolate all `~140+` non-Core global FX currencies with `is_extended=True` and keep the hard `0.01 EUR/L` floor.

### Question 4: Displaying `200+` global territories in `CHANGELOG_{SUMMER,WINTER}.md` and Workshop `description.txt`

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `CHANGELOG_{SUMMER,WINTER}.md` detailed fuel table at `36` Core countries, add a compact Global Snapshot Coverage summary (counts by Tier 1/2/3 + attributions), and keep Workshop `description.txt` concise | Keeps Workshop release notes readable while surfacing global pipeline coverage | ✓ |
| Expand the Markdown fuel table in `CHANGELOG_{SUMMER,WINTER}.md` to list all `200+` countries every week | Full `200+`-row weekly table | |

**User's choice:** Keep `CHANGELOG_{SUMMER,WINTER}.md` detailed fuel table at `36` Core countries + compact Global Snapshot Coverage summary + concise `description.txt`.

---

## Area 4: Internal CI OSM Speed-Limit Drift Audit & `CC BY 4.0` Wall (`GLB-04`)

### Question 1: OSM data source strategy for internal speed-limit drift audit

| Option | Description | Selected |
|--------|-------------|----------|
| Primary comparison against `westnordost/osm-legal-default-speeds` (OSM Wiki statutory defaults, fast & reliable across `200+` countries) + opt-in `--overpass` / `--taginfo` spot-check mode for targeted countries | Reliable global audit without Overpass rate-limit flakiness, plus empirical spot-check support | ✓ |
| Primary `westnordost/osm-legal-default-speeds` only (no Overpass/Taginfo querying) | Wiki defaults only | |
| Query live OSM Overpass API across all `200+` countries on every CI audit run | High-latency empirical queries across all countries | |

**User's choice:** Primary comparison against `westnordost/osm-legal-default-speeds` + opt-in `--overpass` / `--taginfo` spot-check mode.

### Question 2: CI workflow cadence and notification UX for OSM drift audit

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated standalone workflow (`.github/workflows/osm-speed-audit.yml`, monthly + `workflow_dispatch`) publishing Markdown/JSON report artifact + GitHub Step Summary + rolling maintainer Issue when unacknowledged drift is found (zero Git commits) | Decoupled from releases, zero Git OSM taint, actionable maintainer review | ✓ |
| Dedicated standalone workflow publishing workflow artifact + GitHub Step Summary only (no GitHub Issues) | Artifact/summary only | |
| Run the OSM audit inside Friday `phase-a-release.yml` alongside releases | Coupled to weekly release workflow | |

**User's choice:** Dedicated standalone workflow publishing Markdown/JSON report artifact + GitHub Step Summary + rolling maintainer Issue (zero Git commits).

### Question 3: Clean-room allowlist for already-verified intentional statutory/ETS2 differences

| Option | Description | Selected |
|--------|-------------|----------|
| Clean-room `data/laws/speed_audit_allowlist.json` (stores only our ISO2/lane/field + statutory rationale, zero OSM text) separating acknowledged intentional differences from new drift | Eliminates recurring false-positive noise while staying 100% free of OSM `CC BY-SA` text | ✓ |
| No allowlist — report every raw mismatch between `data/laws/` and OSM on every run | Raw diff every run | |

**User's choice:** Clean-room `data/laws/speed_audit_allowlist.json` (zero OSM text).

### Question 4: Code structure and automated `CC BY 4.0` provenance isolation enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Isolated `src/ets2v2/audit/` subpackage (`ets2v2 audit osm-speeds`) + AST DAG wall banning all other subpackages from importing `audit/` + automated `pytest`/validator license-taint scan blocking `CC BY-SA`/`ODbL`/OSM/`GlobalPetrolPrices`/`MyLPG`/`IEA` from all `CC BY 4.0` inputs & outputs | First-class typed CLI tool with compile-time/test-time architectural and provenance enforcement | ✓ |
| Standalone `scripts/osm_speed_audit.py` outside `src/ets2v2/` with a CI grep check only | Loose external script | |

**User's choice:** Isolated `src/ets2v2/audit/` subpackage + AST DAG wall + automated `pytest`/validator license-taint scan.

---

*Phase: 05-global-tier-1-2-3-coverage-internal-osm-audit*
*Discussion logged: 2026-11-25*
