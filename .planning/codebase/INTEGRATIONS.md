# External Integrations

**Analysis Date:** 2026-11-26

## APIs & External Services

All outbound HTTP integrations route through the hardened `httpx.Client` helpers in `src/ets2_realism/fetch/http.py` enforcing HTTPS-only port `443`, unconditional TLS verification (`verify=True`), per-provider exact host allowlists across up to `5` redirect hops, bounded streaming byte caps (`30 MiB` default, `50 MiB` for ES MITECO, `20 MiB` for `.xlsx`, `2 MiB` for XML), OOXML ZIP-bomb caps (`256` entries / `64 MiB` uncompressed in `src/ets2_realism/fetch/_parsing.py`), XXE/DOCTYPE/ENTITY rejection (`parse_xml_safe()`), bounded retries (`2` retries on `429`/`500`/`502`/`503`/`504`), and automatic URL secret redaction (`redact_url_secrets()`).

**Multi-Provider Foreign Exchange (4 Providers — `src/ets2_realism/fetch/fx.py`, `src/ets2_realism/normalize/fx.py`):**
- **Frankfurter v2** (`https://api.frankfurter.dev/v2/rates?base=EUR`, `MIT`, primary EUR base feed)
  - SDK/Client: `httpx` via `fetch_frankfurter_v2()`
  - Auth: None (keyless)
- **European Central Bank Daily XML** (`https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`, secondary cross-validator)
  - SDK/Client: `httpx` + `parse_xml_safe()` via `fetch_ecb_daily_xml()`
  - Auth: None (keyless)
- **fawazahmed0 Currency API** (jsDelivr primary `https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/eur.json` + Cloudflare Pages mirror `https://latest.currency-api.pages.dev/v1/currencies/eur.json`, `CC0 1.0`, extended global currency coverage across `151` ISO-4217 currencies)
  - SDK/Client: `httpx` via `fetch_fawazahmed0_eur()`
  - Auth: None (keyless)
- **Central Bank of Russia Daily XML** (`https://www.cbr.ru/scripts/XML_daily.asp`, `windows-1251`, EUR->RUB cross-check)
  - SDK/Client: `httpx` + `parse_xml_safe()` via `fetch_cbr_daily_xml()`
  - Auth: None (keyless)

**Tier 1 European & EEA Open Fuel Feeds (10 Collectors — `src/ets2_realism/fetch/ec_bulletin.py`, `src/ets2_realism/fetch/national.py`):**
- **EC Weekly Oil Bulletin** (`https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en` -> dynamic `"Prices with taxes"` `.xlsx` link discovery on `energy.ec.europa.eu` / `ec.europa.eu`, `CC BY 4.0`, EU-27)
  - SDK/Client: `httpx` + `openpyxl` via `fetch_ec_weekly_oil_bulletin()`
  - Auth: None (keyless)
- **FionnHughes EC WOB Mirror** (`https://huggingface.co/datasets/FionnHughes/eu-weekly-oil-bulletin/raw/main/eu_oil_bulletin.csv`, `CC BY 4.0`, conditional fallback when EC WOB fails or returns `<27` states)
  - SDK/Client: `httpx` + stdlib `csv` via `fetch_fionnhughes_fallback()`
  - Auth: None (keyless)
- **fuel-prices.eu** (`https://www.fuel-prices.eu/board_now.php`, `CC BY 4.0`, live EUR/L European & non-EU fallback/primary for non-EU vanilla/ProMods territories)
  - SDK/Client: `httpx` via `fetch_fuel_prices_eu()`
  - Auth: None (keyless)
- **UK DESNZ Weekly Road Fuel** (`https://www.gov.uk/government/statistical-data-sets/oil-and-petroleum-products-weekly-statistics` -> dynamic CSV on `assets.publishing.service.gov.uk`, `OGL v3.0`, pence/L -> GBP/L)
  - SDK/Client: `httpx` + stdlib `csv` via `fetch_uk_desnz()`
  - Auth: None (keyless)
- **Norway SSB Table `09654`** (`https://data.ssb.no/api/pxwebapi/v2/tables/09654/data?lang=en&valueCodes[Tid]=top(3)`, `CC BY 4.0 (NLOD)`, JSON-stat2, NOK/L)
  - SDK/Client: `httpx` via `fetch_no_ssb_09654()`
  - Auth: None (keyless)
- **France Ministère de l'Économie (OpenDataSoft v2.1)** (`https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records?...`, `Licence Ouverte v2.0`, multi-grade `diesel`, `petrol_95`, `petrol_98`, `e85`, `lpg`)
  - SDK/Client: `httpx` via `fetch_fr_economie()`
  - Auth: None (keyless)
- **Germany Tankerkönig** (`https://creativecommons.tankerkoenig.de/json/list.php`, `CC BY 4.0`, 5-city median)
  - SDK/Client: `httpx` via `fetch_de_tankerkoenig()`
  - Auth: Optional `TANKERKOENIG_API_KEY` (silently skips to EC WOB when unset)
- **Spain MITECO EstacionesTerrestres** (`https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/`, Spanish Open Gov Data, `50 MiB` cap, multi-grade medians)
  - SDK/Client: `httpx` via `fetch_es_miteco()`
  - Auth: None (keyless)
- **Italy MIMIT Osservaprezzi** (`https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv`, `IODL 2.0`, self-service multi-grade medians)
  - SDK/Client: `httpx` + stdlib `csv` via `fetch_it_mimit()`
  - Auth: None (keyless)
- **Netherlands CBS StatLine OData `80416ned`** (`https://opendata.cbs.nl/ODataApi/odata/80416ned/TypedDataSet?$orderby=Perioden%20desc&$top=5`, `CC BY 4.0 (CBS)`)
  - SDK/Client: `httpx` via `fetch_nl_cbs_80416ned()`
  - Auth: None (keyless)

**Tier 1 Global Non-EU Government Fuel APIs (8 Collectors — `src/ets2_realism/fetch/global_tier1.py`):**
- **US EIA Open Data API v2** (`https://api.eia.gov/v2/petroleum/pri/gnd/data/`, U.S. Public Domain, exact NIST `3.785411784` L/gal)
  - SDK/Client: `httpx` via `fetch_us_eia_v2()`
  - Auth: Optional `EIA_API_KEY` (silently skips to lockfile/Tier 3 when unset)
- **Brazil ANP** (`https://www.gov.br/anp/.../ultimas-4-semanas-{diesel-gnv,gasolina-etanol}.csv`, Brazilian Open Gov Data)
  - SDK/Client: `httpx` + stdlib `csv` via `fetch_br_anp()`
  - Auth: None (keyless)
- **Argentina Secretaría de Energía (CKAN)** (`https://datos.gob.ar/api/3/action/package_show?id=precios-en-surtidor-resolucion-314` + `datos.energia.gob.ar` fallback -> dynamic `vigente` CSV, Decreto 117/2016)
  - SDK/Client: `httpx` + stdlib `csv` via `fetch_ar_energia()`
  - Auth: None (keyless)
- **Colombia MinMinas/SICOM & CREG** (`https://www.datos.gov.co/api/catalog/v1?q=precio+mes+combustible&limit=10` -> Socrata SODA `/resource/<id>.json` with `https://creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos` HTML fallback, COP/gal -> L)
  - SDK/Client: `httpx` + stdlib `html.parser` via `fetch_co_sicom()`
  - Auth: None (keyless)
- **Chile CNE Bencina en Línea** (`https://api.cne.cl/api/v4/estaciones` Bearer + `https://api.cne.cl/v3/combustibles/vehicular/estaciones` fallback, Chilean Open Gov Data)
  - SDK/Client: `httpx` via `fetch_cl_cne()`
  - Auth: Optional `CNE_API_TOKEN` (silently skips to lockfile/Tier 3 when unset)
- **Malaysia OpenDOSM / MOF** (`https://api.data.gov.my/data-catalogue?id=fuelprice&filter=level@series_type...`, `CC BY 4.0`)
  - SDK/Client: `httpx` via `fetch_my_opendosm()`
  - Auth: None (keyless)
- **Japan METI Weekly Petroleum Survey** (`https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results.html` -> `.xlsx` discovery, explicitly rejecting legacy `.xls`, Government of Japan Standard Terms v2.0)
  - SDK/Client: `httpx` + `openpyxl` via `fetch_jp_meti()`
  - Auth: None (keyless)
- **South Korea KNOC Opinet** (`https://www.opinet.co.kr/api/avgAllPrice.do`, Korean Public Data Open License)
  - SDK/Client: `httpx` via `fetch_kr_opinet()`
  - Auth: Optional `OPINET_API_KEY` (silently skips to lockfile/Tier 3 when unset)

**Tier 2 Guarded National Fuel Portals (10 Fault-Isolated Collectors — `src/ets2_realism/fetch/tier2_portals.py`):**
- Executed individually inside `_run_tier2_guarded()` circuit breakers classifying `tier2_rate_limited`, `tier2_encoding_error`, `tier2_selector_drift`, and `tier2_portal_outage` without failing the fetch pipeline:
  - **Iceland Gasvaktin** (`https://raw.githubusercontent.com/gasvaktin/gasvaktin/master/vaktin/gas.min.json`, `MIT`)
  - **Switzerland BFS / LIK** (`https://www.pxweb.bfs.admin.ch/api/v1/de/px-x-0501000000_105/px-x-0501000000_105.px`, allowlisted `www.pxweb.bfs.admin.ch`, `dam-api.bfs.admin.ch`, JSON-stat2/CSV)
  - **Moldova ANRE** (`https://anre.md/`, HTML)
  - **North Macedonia ERC** (`https://www.erc.org.mk/`, HTML UTF-8/`windows-1251`)
  - **Russia Rosstat** (`https://rosstat.gov.ru/folder/313/document/126955`, HTML/`.xlsx`, UTF-8/`windows-1251`)
  - **Israel Ministry of Energy** (`https://www.gov.il/en/departments/units/fuel_prices`, HTML)
  - **UAE MOEI** (`https://www.moei.gov.ae/en/open-data`, HTML)
  - **South Africa DMRE / CEF** (`https://cefgroup.co.za/energy-data/daily-basic-fuel-price/`, allowlisted `cefgroup.co.za`, `www.dmre.gov.za`, HTML/`.xlsx`, cents/L -> ZAR/L)
  - **Saudi Aramco** (`https://www.aramco.com/en/what-we-do/energy-products/retail-fuels`, HTML)
  - **Nigeria NBS** (`https://nigerianstat.gov.ng/`, allowlisted `nigerianstat.gov.ng`, `microdata.nigerianstat.gov.ng`, HTML -> AGO/PMS Watch `.xlsx`)

**Quarantined CI-Only Speed-Limit Drift Audit Sources (`src/ets2_realism/audit/`):**
- **westnordost/osm-legal-default-speeds** (`https://westnordost.github.io/osm-legal-default-speeds/legal_default_speeds.json`, allowed hosts `westnordost.github.io`, `raw.githubusercontent.com`, `github.com`)
  - SDK/Client: `httpx` via `run_osm_speed_audit()` (`src/ets2_realism/audit/osm_speeds.py`)
  - Auth: None (keyless)
- **OSM Overpass API (Opt-in `--overpass`)** (`https://overpass-api.de/api/interpreter`, strict tags-only `out tags 500;` POST query, capped at `<= 10` ISO-2 codes with `1.5s` polite throttle)
  - SDK/Client: `httpx` via `fetch_overpass_speed_spot_checks()` (`src/ets2_realism/audit/overpass.py`)
  - Auth: None (keyless)
- **OSM Taginfo API v4 (Opt-in `--taginfo`)** (`https://taginfo.openstreetmap.org/api/4/key/values`, `maxspeed`, `maxspeed:hgv`, `maxspeed:bus` distributions, `0.5s` throttle)
  - SDK/Client: `httpx` via `fetch_taginfo_maxspeed_distributions()` (`src/ets2_realism/audit/overpass.py`)
  - Auth: None (keyless)
- **Strict Licensing Firewall (`src/ets2_realism/audit/taint.py`):** Audit outputs are strictly read-only CI maintainer advisories and never write to `data/` or release packages. `ets2-realism audit taint` and `check_license_taint_bytes()` (`src/ets2_realism/validate/invariants.py`) reject `CC BY-SA`, `ODbL`, `OpenStreetMap`, `osm-legal-default-speeds`, `GlobalPetrolPrices`, `CC BY-NC-ND`, `MyLPG`, and `IEA` markers across `data/`, `state/`, snapshots, and compiled `.zip`/`.scs`/Workshop packages.

**Offline Documentation Mirror:**
- **SCS Modding Wiki Offline Mirror** (`.agents/skills/scs-modding-wiki/SKILL.md`, `index.json`, `sources.json`, `162` pages under `docs/`) - Local documentation reference for SCS `.sii`/`.sui` formats, Workshop Uploader validation codes, and archive formats.

## Data Storage

**Databases:**
- None (pure local filesystem + deterministic sorted UTF-8 no-BOM LF JSON artifacts).

**File Storage & Clean-Room Repository Registries:**
- `data/baselines/ets2_1.62_def/` - Clean-room extracted ETS2 `1.62.3.3` JSON baselines (`manifest.json`, `countries.json` with `36` Vanilla+DLC countries, `speed_limits.json`, `fuel_boards.json` with `461` single-text boards + `5` excluded multi-item boards, `locales.json` with `43` active locales, `12` `tz_*` keys, and `99` `fp_*` keys). Raw `.sii`/`.sui` files are strictly prohibited under `data/` (`verify_baseline_bundle()` in `src/ets2_realism/baseline/extractor.py`).
- `data/laws/countries/*.json` - `225` canonical per-country statutory law JSON files (`CC BY 4.0`) + `data/laws/speed_audit_allowlist.json` (`11` documented statutory deviation entries).
- `data/curated/tier3_fuel_baselines.json` - `186` Tier 3 curated global fuel baselines (`CC BY 4.0`, verified `2026-11-25`, `180`-day staleness alert threshold).
- `data/mappings/` - `ets2_countries.json` (`225` territories), `country_aliases.json` (`119` map-mod slug/prefix aliases), and `currencies.json` (`151` ISO-4217 currencies with ECB flags & sanity bands mapped across `225` territories).
- `state/prices.lock.json` - Canonical circuit-breaker FX (`151` currencies) and fuel price (`225` territories) lockfile (`0.01–5.00 EUR/L` bounds, `±25%` WoW jump guard, `14d`/`30d`/`45d`/`105d`/`180d` staleness thresholds in `src/ets2_realism/normalize/lockfile.py`).
- `state/published.json` - Canonical payload SHA-256 diff-gate ledger (`src/ets2_realism/publish/ledger.py`) preventing no-op Workshop updates.
- `assets/icons/` - Checked-in clean-room `276x162` RGB JPEG icons (`summer.jpg`, `winter.jpg`, `promods_summer.jpg`, `promods_winter.jpg`).

**Local ETS2, ProMods & Map-Combo Archive Integrations (Never Tracked in Git):**
- **ETS2 `1.62.3.3s` Game Directory:** Resolved via `--game-dir` > `ETS2_GAME_DIR` > `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2` (`src/ets2_realism/baseline/extractor.py`). Reads HashFS v2 `version.scs`, `def.scs` (`66066` entries), `locale.scs` (`521` entries via `seeded_prefixes=("locale",)`), and audits `107` `dlc_*.scs` archives. When `--game-dir` is omitted in `package promods` or `compose-local`, `BaselineVirtualArchive` (`src/ets2_realism/merge/load_order.py`) synthesizes Vanilla 1.62 defs in-memory from `data/baselines/ets2_1.62_def/`.
- **ProMods Local Mod Directory:** Resolved via `--mod-dir` > `ETS2_MOD_DIR` > `D:\ETS2Data\Euro Truck Simulator 2\mod` (Windows fallback `~/Documents/Euro Truck Simulator 2/mod`; Linux `~/.local/share/Euro Truck Simulator 2/mod`) in `src/ets2_realism/merge/promods_discovery.py`. Version-agnostically discovers ProMods EU, TGS, ME, and MA `def`/`defmap` and `assets` `.scs`/`.zip` archives in official stacking order (`Vanilla < EU < TGS < ME < MA`) and compiles standalone ProMods Editions + `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` across all 43 locales. `assert_out_dir_not_tracked()` (`src/ets2_realism/merge/promods_builder.py`) refuses writing ProMods/combo outputs into tracked repository directories.
- **Steam Workshop `227300` & Arbitrary Map Combos (`ets2-realism compose-local`):** Resolved via `--workshop-dir` > `ETS2_WORKSHOP_DIR` > sibling `steamapps/workshop/content/227300` > platform Steam defaults (`src/ets2_realism/merge/load_order.py`). Discovers active load order from ETS2 `game.log.txt`, plaintext `profile.sii` (refusing `ScsC`-encrypted profiles), or `--modlist`; auto-excludes prior managed packages (`# ets2-realism:managed-package`); substitutes protected `AEM!`/`3nK`/encrypted-ZIP archives via `--unpacked-defs`; optionally rewrites verified JRR/7RM numeric fuel boards via `--patch-hardcoded-totems` (`src/ets2_realism/merge/hardcoded_totems.py`); and emits validated `zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs` (`src/ets2_realism/merge/compose.py`).

**Caching:**
- In-memory VFS index and empty-stub cache inside `VfsStack` (`src/ets2_realism/vfs/stack.py`).
- GitHub Actions `uv` dependency cache (`enable-cache: true` in `.github/workflows/*.yml`).
- Persistent on-disk last-known-good price cache in `state/prices.lock.json`.

## Authentication & Identity

**Auth Provider:**
- None (CLI and GitHub Actions workflows only; no user accounts or OAuth flows).
- **GitHub Actions Permissions:**
  - `.github/workflows/ci.yml`: `permissions: contents: read`.
  - `.github/workflows/phase-a-release.yml`: `permissions: contents: write, pull-requests: write` using default `GITHUB_TOKEN` (`gh release`, `gh pr`).
  - `.github/workflows/osm-speed-audit.yml`: `permissions: contents: read, issues: write` using default `GITHUB_TOKEN` (`gh issue`, `gh label`).
- **Steam Workshop Publishing (Phase A Semi-Auto):** Stores **zero Steam credentials** in GitHub Actions. Maintainers download the validated `phase-a-release-bundle` artifact (`dist/workshop/{summer,winter}/`) and upload manually via **SCS Workshop Uploader** (`AppID 421800`). Full-auto `steamcmd` + TOTP (`STEAM_SHARED_SECRET`) remains deferred to V2 (`PUB-V2-01`).

## Monitoring & Observability

**Error Tracking:**
- No external error-tracking SaaS. Structured frozen Pydantic reports and diagnostics cover every subsystem:
  - `ArchiveDiagnostic` (`src/ets2_realism/vfs/types.py`) and `ProtectedArchiveDiagnostic` (`src/ets2_realism/merge/load_order.py`).
  - `SiiDiagnostic` (`src/ets2_realism/sii/hygiene.py`).
  - `LockAlert` and `FetchRunReport` (`src/ets2_realism/normalize/models.py`, `src/ets2_realism/fetch/models.py`) published to `$GITHUB_STEP_SUMMARY` and the weekly Release PR body (`.github/workflows/phase-a-release.yml`).
  - `ValidationReport` implementing Offline SCS Workshop Validator (`00001`–`00010`, `WARN 00001`/`00002`, and `core`/`promods`/`combo` realism invariants in `src/ets2_realism/validate/`).
  - `OsmSpeedAuditReport` and `TaintScanReport` (`src/ets2_realism/audit/models.py`), with automated rolling GitHub Issue (`osm-audit` label, capped at `58,000` chars via `truncate_markdown_for_github_issue()`) on unacknowledged speed-limit drift (`.github/workflows/osm-speed-audit.yml`).

**Logs:**
- Standard stdout/stderr console output and `--json` machine-readable output in `src/ets2_realism/cli.py`, plus GitHub Actions job logs and step summaries.

## CI/CD & Deployment

**Hosting:**
- GitHub Repository (`https://github.com/MissionWAR/ets2-country-realism`), GitHub Releases (`snapshots-latest` rolling release serving `realism-snapshot-{summer,winter}.json` and `SHA256SUMS.txt`), and Steam Workshop (ETS2 `AppID 227300`, uploaded manually via `SCS Workshop Uploader` `AppID 421800`).

**CI Pipeline:**
- **`.github/workflows/ci.yml`** (`push` on `master`/`main`, all `pull_request`): `ubuntu-latest`, `timeout-minutes: 15`, runs `uv sync --locked`, `ruff check`, `ruff format --check`, `basedpyright`, and `pytest` (auto-skipping `@pytest.mark.local_ets2` and `@pytest.mark.local_promods` tests offline).
- **`.github/workflows/phase-a-release.yml`** (`schedule: "0 6 * * 5"` Friday `06:00 UTC` + `workflow_dispatch` with `force_run`): `ubuntu-latest`, `timeout-minutes: 20`, runs offline quality gates -> `ets2-realism fetch` -> sanitized alert summary -> `ets2-realism publish release` (diff-gated via `state/published.json`) -> explicit `validate workshop`/`local` -> `registry snapshot-verify` -> uploads `phase-a-release-bundle` artifact -> updates rolling `snapshots-latest` GitHub Release -> creates/updates persistent `release/phase-a-weekly` PR staging `state/published.json`, `state/prices.lock.json`, and `CHANGELOG_{SUMMER,WINTER}.md`.
- **`.github/workflows/osm-speed-audit.yml`** (`schedule: "0 7 1-7 * 1"` first Monday `07:00 UTC` + `workflow_dispatch` with `iso2` and `overpass`): `ubuntu-latest`, `timeout-minutes: 15`, runs `ets2-realism audit osm-speeds` read-only -> uploads `osm-speed-drift-report` artifact -> publishes step summary -> upserts or auto-closes the rolling `osm-audit` GitHub Issue.

## Environment Configuration

**Required env vars:**
- None strictly required for offline CI, testing, or keyless live fetching.

**Optional env vars & GitHub Actions Secrets:**
- `TANKERKOENIG_API_KEY` - Optional free API key for Germany 5-city live medians (`.github/workflows/phase-a-release.yml`, `src/ets2_realism/fetch/national.py`).
- `EIA_API_KEY` - Optional free API key for US EIA v2 weekly retail fuel prices (`.github/workflows/phase-a-release.yml`, `src/ets2_realism/fetch/global_tier1.py`).
- `OPINET_API_KEY` - Optional free API key for South Korea KNOC Opinet daily averages (`.github/workflows/phase-a-release.yml`, `src/ets2_realism/fetch/global_tier1.py`).
- `CNE_API_TOKEN` - Optional API token for Chile CNE Bencina en Línea station medians (`.github/workflows/phase-a-release.yml`, `src/ets2_realism/fetch/global_tier1.py`).
- `ETS2_GAME_DIR`, `ETS2_MOD_DIR`, `ETS2_WORKSHOP_DIR` - Optional local workstation filesystem overrides for ETS2 installation, local `mod/` folder, and Steam Workshop `227300` content folder.

**Secrets location:**
- GitHub Actions repository secrets (for optional fuel API keys) and ephemeral `GITHUB_TOKEN`. Zero `.env` files or Steam secrets exist in the repository or CI.

## Webhooks & Callbacks

**Incoming:**
- None (CLI invocations, GitHub push/PR events, cron schedules, and manual `workflow_dispatch` only).

**Outgoing:**
- Outbound HTTPS `GET` (and form-encoded `POST` for opt-in Overpass queries) from `src/ets2_realism/fetch/` and `src/ets2_realism/audit/`, plus GitHub REST/CLI operations (`gh release`, `gh pr`, `gh issue`, `gh label`) from `.github/workflows/phase-a-release.yml` and `.github/workflows/osm-speed-audit.yml`.

---

*Integration audit: 2026-11-26*
