# Project Research Summary: ETS2 World Country Realism Generator (V2)

**Project:** ETS2 World Country Realism Generator (V2)
**Target Game Baseline:** Euro Truck Simulator 2 `1.62.3.3s` (`version.scs`: `"1.62.3.3"`, rev. `7173c707daa0`)
**Synthesized:** 2026-11-15 (from `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md`, and `PROJECT.md`)
**Overall Confidence:** **HIGH** (backed by direct binary inspection of ETS2 `1.62.3.3s` archives, Steam Workshop mods `3668352310`/`3249064596`/`3668351598`/`1820303287`/`3002586900`, a 503-mod local map-combo census, live SCS Modding Wiki verification, and Windows `zoneinfo`/`tzdata` testing; minor Tier 2/3 portal stability caveats rated MEDIUM)

---

## 1. Executive Summary & ETS2 1.62.3.3s Verified Baseline

**ETS2 World Country Realism Generator (V2)** is a clean-room, open-source Python 3.12+ data pipeline and mod compiler that generates **conflict-free Summer and Winter Steam Workshop editions** (plus an optional ProMods companion addon and a local map-combo auto-composer) from a single canonical dataset. Rather than copying or merging fragile third-party Workshop archives every week, V2 extracts fresh base definitions directly from ETS2 `1.62.3.3s`, collects real-world fuel prices and FX rates through a legally clean 3-tier pipeline, applies statutory seasonal rules (`speed_limits.sii`, DST `time_zone`, `lights_mandatory`, axle weights), updates roadside gas-station totems via **zero-DDS localization overrides**, and validates every package offline against SCS Workshop Uploader rules (`00001`–`00010` & `WARN 00001`/`00002`) before publishing.

Direct read-only binary inspection of all **96 `.scs` archives** in ETS2 `1.62.3.3s` (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`) established the exact vanilla baseline:
- **`def.scs` (HashFS v2, `CITY`):** Sole base source for `def/country.sii` (**36** `@include` entries), `def/country/*.sui` (`36` files, `20` distinct `country_data` attributes), `def/country/*/speed_limits.sii` (`36` files containing `car`, `truck`, `bus`, `train`, and `tram` speed classes), and `def/sign/board/*.sii` (**457** `gas_*` boards / **555** total fuel boards across ~12.9k board templates, **373** of which currently reference `@@fp_*@@` tokens).
- **1.62 Deltas vs V1 `1.60.1.7`:** All **36/36** `fuel_price` values and **14/36** `speed_limits.sii` files changed (`czech`, `france`, `germany`, `iceland`, `italy`, `latvia`, `luxembourg`, `montenegro`, `poland`, `romania`, `slovenia`, `sweden`, `switzerland`, `uk`). ETS2 1.62 also wired `iceland.sui` (`country_id: 26`) with a **5-element `mass_limit_per_axle_count[]`** (`[18000, 29000, 38000, 46000, 60000]` = 60t), expanded British Isles/Ireland `gas_bi_*` and `gas_ie_*` fuel totems, and reflects **Bulgaria's 2026-01-01 Euro adoption** in `locale.scs` (`fp_bg_natural95: "1.67"` EUR even though `economy_data.sii` keeps legacy `BGN*`). Vanilla `regions[]` / `region_areas[]` exist on `bosnia`, `finland`, `norway`, `spain` (plus `sweden` regional flags).
- **`dlc_*.scs` Footprint:** **Zero** DLC archives contain `def/country.*.sii`, `def/country/*.sui`, `speed_limits.sii`, or `def/sign/board/*`. Only 9 DLCs (`dlc_balt`, `dlc_fr`, `dlc_iberia`, `dlc_it`, `dlc_north`, plus 4 truck DLCs) carry `def/country/<country>/traffic.<dlc>.sii`.
- **`locale.scs` (565 entries, omits `/` root — must walk via seeded `/locale`):** Defines **43** active locales (`bg_bg`..`zh_tw`), **99** `fp_*` keys in `/locale/fuel_price_strings.sui`, and **only 12 `tz_*` keys** in `localization.sui` (`tz_bst`, `tz_cdt`, `tz_cest`, `tz_eet`, `tz_eest`, `tz_gmt`, `tz_msk`, `tz_mst`, `tz_mdt`, `tz_pdt`, `tz_trt`, `tz_west`).

### Why `3249064596` and `3668352310` Cannot Simply Be Merged or Copied

Forensic unpacking of both reference Workshop mods confirmed critical defects that disqualify direct merging or template copying:

| Mod / File | Confirmed Defects & Engine Hazards Observed on Disk | V2 Clean-Room Fix |
|---|---|---|
| **`3249064596`** (`estonia.sui`) | `name: "@@tz_eest@@i"` from blind `"est"` regex replacement | Field-level SII/SUI attribute rewriter; assert `name` immutable |
| **`3249064596`** (`armenia.sui`) | `leftside_traffic: true` (flips Armenia to left-hand drive) | Never copy third-party `.sui`s; assert `leftside_traffic` immutable |
| **`3249064596`** (`libya.sui`, `libya1.sui`) | Duplicate `country_id: 120` collision (`0.020` vs `0.024`) | Enforce unique `country_id` & unit names across VFS in validator |
| **`3249064596`** (`locale/fr_ca/`, `fr_qc`) | Missing `local_module.kworey_fuel_ets.sii` in `fr_ca`, stale `pm_*` key counts, ships dead `fr_qc` (44 locales vs 1.62's 43) | Single canonical locale generator syncing all **43** active 1.62 locales |
| **`3249064596`** (`iceland.sui`, `greece.sui`, `latvia.sui`, `svalbard.sui`, `sanmarino.sui`) | Reverts 1.62 `iceland.sui` 5-axle 60t to stale 4-axle 40t; `greece` 40t vs 44t; wrong `latvia` `pos`; `svalbard` (`2.573`) & `sanmarino` (`1.46`) stale prices | Extract fresh `1.62.3.3s` baseline; `max_of_map_and_real` axle policy; live/enclave-consistent pricing |
| **`3249064596`** (`uk.sui`, `russia.sui`, `kazakhstan.sui`) | Monolithic 75-`.sui` dump deletes ProMods UK `regions[]` (`scotland`/`wales`), truncates TST `russia.sui` (`15` vs `27` TZs) and RusMap/TST `48t` axles, reverts UMCF `kazakhstan.sui` `ALMT` (`360`) & 5 `AQTT` rects | Isolate Vanilla+DLC Core (`36` countries) from ProMods Addon & `compose-local`; field-ownership preservation |
| **`3249064596`** (`jordan.sui`, `syria.sui` + EU) | Hardcodes `jordan`/`syria` to `180` + `"@@tz_eest@@"` (both abolished DST in Oct 2022 → permanent `UTC+3` `AST`); hardcodes EU to winter offsets | Derive Summer & Winter offsets from IANA `zoneinfo` + `tzdata` |
| **`3249064596`** (`def/sign/board/*.sii`) | Misses **86 of 457** `gas_*` boards in 1.62 (**17** active `@@fp_*@@` boards: `10 gas_bi_*`, `4 gas_ie_*`, `2 gas_ba_*_lpg`, `1 gas_dk_92`; **38** numeric placeholders `"0.00"`/`"00.00"`/`"0.000"`/`"123.9"`; **31** blank `" "` boards) and blanks `gas_is_ip1_98.sii` | Dynamic discovery from `def.scs:/def/sign/board/` + populate `fp_ie_*` and all active/placeholder boards |
| **`3668352310`** (`speed_limits.sii`) | All 36 `speed_limits.sii` files are **`3nK\x01`-encrypted** (`32/36` differ from 1.62), breaking Workshop Uploader SII validation and obscuring 1.62 `bus`/`train`/`tram` units | Zero `3nK` cracking/copying; emit plaintext UTF-8 `SiiNunit` merging `car`/`truck`/`bus` while preserving `train`/`tram` |
| **`3668352310`** (`@@tz_cet@@`/`@@tz_wet@@` & `@@tz_*@@`) | **`@@tz_cet@@` and `@@tz_wet@@` DO NOT EXIST in `locale.scs`** (using them renders literal `"@@tz_cet@@"`). `3668352310` replaces *all* `@@tz_*@@` tokens with hardcoded English strings (`"EET"`, `"GMT"`, `"MSK"`), breaking localization | Preserve `@@tz_*@@` tokens for the 12 supported keys (`@@tz_cest@@`, `@@tz_eet@@`, `@@tz_gmt@@`, `@@tz_msk@@`, etc.) and emit plain strings (`"CET"`, `"WET"`, `"AST"`, etc.) only where `locale.scs` lacks a token |
| **`3668352310`** (`_vtd/*.sui`, `lights_mandatory`, `country_code`) | Injects `@include "_vtd/<country>.sui"` (`247` custom boxes) while stripping vanilla `regions[]` (`bosnia`/`finland`/`norway`/`spain`/`sweden`), wrongly sets `lights_mandatory: true` on `albania` & `turkey` (though right on `netherlands: false` & `switzerland: true`), and forces `FIN`/`RUS` codes | Preserve vanilla `regions[]`/`region_areas[]` verbatim, apply verified statutory `lights_mandatory`, and keep vanilla ISO `country_code`s by default |

---

## 2. Recommended Technology Stack & Clean-Room Architecture

V2 replaces V1's flat monolithic scripts (`update_fuel.py` 1,632 LOC, `update_limits.py` 1,508 LOC) and Windows-only manual `scs_extractor.exe` workflow with a modular, cross-platform `src/` layout package (`ets2-world-realism`, CLI entrypoint `ets2v2`).

### Core Stack (`pyproject.toml` Baseline)

| Layer | Technology / Version | Purpose & Key Architectural Constraint |
|---|---|---|
| **Runtime & Packaging** | **Python `>=3.12`** (`3.12.13`) + **`uv`** (`0.11.31+`) + `src/ets2v2/` layout | Reproducible `uv.lock`, Windows & Linux CI parity (`astral-sh/setup-uv@v5`). |
| **Modeling & Validation** | **`pydantic>=2.14,<3`** | Strict typed schemas (`eur_per_liter` vs `local_display_price`, axle limits, `[a-z0-9_]{1,12}` SII tokens, Summer/Winter speed overrides). |
| **HTTP & Spreadsheet Ingestion** | **`httpx>=0.28,<0.29`** + **`openpyxl>=3.1,<4`** (+ `beautifulsoup4`/`lxml` deferred to Tier 2 HTML parsers) | Async-ready HTTP/2 fetching with timeouts/retries; EC Weekly Oil Bulletin `.xlsx` header/country-code parsing (`EL` → `GR`). |
| **Timezone Derivation** | **Stdlib `zoneinfo`** + **`tzdata`** (PyPI) | **Critical Windows requirement:** `ZoneInfo("Europe/Berlin")` raises `ZoneInfoNotFoundError` on Windows without `tzdata`. Computes Summer/Winter DST offsets automatically. |
| **Workshop Icon Tooling** | **`pillow>=12,<14`** | **Strictly scoped to `276x162` `.jpg` Workshop icon validation/generation.** Confirmed **NO-GO for `.dds`** (lacks mipmaps & sRGB DXGI 72/78/88/91 support); fuel totems require **zero DDS**. |
| **Quality & CI Gates** | **`pytest>=9.2,<9.3`** (`pytest-cov`), **`ruff>=0.16`**, **`basedpyright>=1.40,<2`** | Static type checking (`ty` `0.0.x` skipped as beta), byte-level round-trip SII tests, invariant assertions, and Offline SCS Validator checks. |

### Clean-Room Binary & Text Components

1. **Clean-Room Pure-Python HashFS v1/v2 + `3nK` Reader (`src/ets2v2/vfs/`):** Implemented directly from documented HashFS v1/v2 binary layouts, stdlib `struct` + `zlib`, and a ~100-line pure-Python **MIT Google CityHash64** implementation (avoiding GPL copyleft contamination from `sk-zk/TruckLib`/`Extractor` or `Switch-Bros/easy-scsmodmanager`, avoiding `clickhouse-cityhash` C-wheel build failures on Windows, and eliminating Windows-only `scs_extractor.exe` in CI). Also natively reads ZIPs and unpacked directories while simulating ETS2 VFS load order (`base/`, `dlc_*/`, `.sui`/`.sii`, empty stub suppression).
2. **Surgical Comment/Order-Preserving SII/SUI Engine (`src/ets2v2/sii/` & `merge/`):** Parses `country_data`, `country_speed_limit`, `sign_board_template`, and `localization_db` blocks structurally without stripping vanilla `#`/`//`/`/* */` comments, `regions[]`, `region_areas[]`, `secondary_time_zone*`, or `train`/`tram` speed units. Enforces column-0 `@include` rules, UTF-8 without BOM, and `\n` (LF) line endings.
3. **Zero-DDS Dual-Tier Fuel Totem Engine:** Modifies only `def/sign/board/*.sii` (`model_name: ""`) + `locale/<lang>/*.sii` across all **43** ETS2 1.62 locales — zero `.dds`/`.tobj` binaries. *(Open design choice for Decision Matrix: patching `/locale/fuel_price_strings.sui` + only the 17+86 unmapped/placeholder vanilla boards vs rewriting all 375–457 vanilla boards to `@@fp_*_ets2v2@@` + `local_module.ets2v2_fuel.sii`.)*
4. **Cross-Platform Packaging (`src/ets2v2/package/`):** Uses Python stdlib `zipfile` (with normalized `1980-01-01` timestamps for reproducible SHA-256) or clean unpacked `universal/` directories (`universal.zip` / `universal/`), which Steam Workshop explicitly accepts (while **forbidding** ZIP-renamed-`.scs` per Error `00003` and requiring no Windows `scs_packer.exe` when shipping zero binary meshes/textures).

---

## 3. Map Combo Scaling Analysis & Tradeoffs

A direct census of **503 user mods** in `D:\ETS2Data\Euro Truck Simulator 2\mod` identified **86 mods** modifying `def/country*`, `speed_limits.sii`, or fuel boards across **6 structural edge cases** that break naive generators:

1. **`.sii` Fragment Extensions:** *Southeast Asia* (`country.sea.sii`), *Roads of Chunghwa* (`country.taiwan.sii`), *Project Japan Relocated* (`japan.sii` + 38 prefecture `.sii`s), and *GMC Beyond Fix* include **`.sii` files** (not `.sui`) inside `def/country/` without `SiiNunit` wrappers.
2. **`base/` Mount Prefix & Total Overhauls:** *EAA Rescaled* places defs under `base/def/country.eaa.sii` (raising Brazil's axle mass up to **80,000 kg / 7 axles**), while *eaa_map_semeuropa_v1* removes Europe entirely using an empty `def/country.sii`.
3. **Empty `SiiNunit { }` Combo Suppression Stubs:** *UMCF* (`country.7rm2.sii`, `country.kz.rtc.sii`), *gmc.beyond.fix* (`country.beyond.sii`), and *SemEuropa* suppress lower-priority maps by shadowing their exact `def/country.<infix>.sii` path with an empty `SiiNunit { }` file.
4. **Multi-Timezone & Sub-National Territory Schemas:** *RusMap* (`9` TZs, `48t` 6-axle), *Trans-Siberian Truckway* (**27** secondary TZs on Russia, `48t`), *UMCF* Kazakhstan (`ALMT` `360`, Cyrillic name, `5` active `AQTT` rects), and *JRR* (`indo_b`, `indo_th`, `indo_tm` sharing `cc="ID"` + hardcoded numeric totems like `indo_gas_totem_01a.sii`).
5. **Protected / Encrypted Archives (`12` total):** **6** `AEM!` headers (`ProjectJapan model1`, `ProjectRussia 5.7.1a`, `Altai 1.7.2`, `M12 Vostok`, `nnmap130`, `rfex`), **3** `Bad magic`, and **3** encrypted ZIPs (`Beyond_by_TerraMaps_1`, `Beyond_by_TerraMaps_5`, `161HybridPlus2` — though central directory paths remain inspectable and plain-ZIP GMC fix packs above them expose active overrides).
6. **Strict ETS2 Engine Rules:** Un-included `.sui`/`speed_limits.sii` files are inert; adding duplicate `country_data : country.data.<name>` via a new `def/country.realism.sii` causes fatal `[unit]` errors; `speed_limits.sii` uses file-scoped `.speed_limit.*` units requiring exact path replacement (not `.infix.sii`); `def/country.custom.sii` is deprecated; and **no `mod_<id>/` conditional directory exists** (`dlc_<id>/` applies only to official SCS DLCs).

### Architectural Options Comparison

| Criterion | Option A: Static Presets (50+ Combo Packs) | Option B: Pure Local CLI Auto-Merger Only | Option C (**Recommended**): Field-Ownership Registry + Clean Workshop Core/PM + Local Composer |
|---|---|---|---|
| **Workshop & Convoy UX** | Fragile; $O(2^k)$ combinatorial preset explosion | Poor; locks out ~90% of casual Workshop & Convoy users | **Best:** 1-click Subscribe for Vanilla+DLC Core (`Summer`/`Winter`) + optional ProMods Addon (`mp_mod_optional: true`) |
| **Arbitrary Map Combos** (`RusMap`, `TST`, `UMCF`, `Beyond`, `JRR`, `SEA`, `RoC`, `PJ`, `EAA`, `Africa`) | Broken; breaks on every map update | Optimal for power users | **Best:** `ets2v2 compose-local` scans user's `mod/` + load order using CI's `realism-snapshot-{season}.json` (~200+ countries) to emit `zz_ETS2V2_ComboPatch_{Summer\|Winter}.scs` |
| **Zero-Clobber Safety** | Low; manual merges drift | High | **Schema-enforced Field-Ownership Contract:** realism owns `fuel_price`, `lights_mandatory`, `driving_tired_offence`, road `speed_limits` (`car`/`truck`/`bus`), conditional single-TZ `time_zone`, and `max_of_map_and_real` axles; maps own `country_id`, `pos`, `regions[]`, `secondary_time_zone*`, `train`/`tram` |
| **Encrypted / `AEM!` Mods** | Fails unless author manually extracts every mod | Needs fallback or `--unpacked-defs` | Reads unencrypted GMC fix packs above encrypted bases + reports exact unreadable `AEM!`/encrypted archives clearly with optional `--unpacked-defs` / external `Extractor` hook |

---

## 4. Global Data Collection Automation Tiers & Legal/Reliability Constraints

### FX Currency Conversion (Required for `.sui` `fuel_price` in EUR/L)
ETS2 `country_data.fuel_price` is strictly **EUR/L diesel**, whereas station totems (`fp_*`) display **native local pump currencies and conventions** (pence `197.0` vs GBP `1.97`, eurocents `252.5` vs EUR `2.53`, `<sup>9</sup>` tenth-cents, integer ALL/ISK/HUF). V2 separates `eur_per_liter` and `local_display_price` as distinct typed fields powered by:
- **Primary:** **Frankfurter v2** (`MIT` License, **219** currencies from 108 central banks, solves CIS/Balkans/MENA/Africa/LatAm/Asia in one keyless call).
- **Secondary / Validator:** **ECB `eurofxref-daily.xml`** (~30 currencies; note `RUB` suspended Mar 2022, CIS/MENA/Balkans absent, freezes weekends/TARGET2 holidays).
- **Tertiary / Regional Fallbacks:** **`fawazahmed0/exchange-api`** (`CC0 1.0` CDN JSON) + **CBR XML** (`RUB`/`BYN`/`KZT`/`UZS` cross-check).

### 3-Tier Fuel Collection Pipeline

| Tier | Scope & Sources | Cadence & Format | License / Reliability Guardrails |
|---|---|---|---|
| **Tier 1 (Automated Open APIs)** | **EU27:** EC Weekly Oil Bulletin (+ `FionnHughes` & `fuel-prices.eu` `CC BY 4.0` fallbacks). **UK:** DESNZ Weekly Road Fuel (`OGL v3`). **NO:** SSB Table `09654` (`CC BY 4.0`). **Multi-Grade Totems (`95`/`98`/`100`/`E85`/`Diesel+`/`LPG`):** `FR` `prix-carburants.gouv.fr` (*Licence Ouverte*), `DE` `Tankerkönig` (`CC BY 4.0`), `ES` MITECO, `IT` MIMIT (*IODL 2.0*), `NL` CBS StatLine. **Global Tier 1:** `US` EIA v2 (`Public Domain`), `BR` ANP (`dados.gov.br`), `AR` Energía, `CO` SICOM, `CL` CNE, `MY` OpenDOSM (`CC BY 4.0`), `JP` METI (`.xlsx`, JP Gov Terms v2), `KR` KNOC Opinet. | Weekly/Daily JSON, CSV, Parquet, XLSX. Schedule EC fetch **Friday `06:00 UTC`** (safely after Thu ~17:00 CET publish); discover Drupal XLSX link dynamically; map `EL`→`GR`. | Highest reliability & clean open-source licensing. |
| **Tier 2 (Guarded National Portals)** | `CH` BFS/LIK + `fuel-prices.eu`; `MD` ANRE (`anre.md`); `MK` ERC (`erc.org.mk`); `RU` Rosstat + CBR; `AZ`/`BY` state tariffs; `IS` Orkusetur/`fuel-prices.eu`; `ID` Pertamina/ESDM; `IL` MoE/CBS; `SA` Aramco / `JO` MEMR / `AE` MOEI / `EG` FAPC; `ZA` DMRE / `KE` EPRA / `NG` NBS. | Scheduled HTML/XLSX parsers with structural selector guards. | **Circuit-breaker resilience:** on `403`/`429`/selector drift, retain last-good rate in `prices.lock.json` with staleness warnings; enforce `€0.01–€5.00/L` range & `±25%` WoW jump alerts. |
| **Tier 3 (Curated Community Baselines)** | Remaining Balkans, Ukraine, Caucasus/Central Asia (`GE`/`AM`/`KZ`/`UZ`/`TM`), `TR` (or Tier 2 EPDK), Maghreb (`MA`/`TN`/`DZ`/`LY`), Levant/Iraq (`SY`/`IQ`/`LB`), `PE`/`TW`. | Versioned repo dataset with manual/PR verification & staleness age alerts. | Prevents brittle CI failures on Cloudflare-walled or low-churn state-fixed markets. |

### Non-Fuel Attributes & Explicit Legal/Ethical Rejections
- **Timezones, Speeds, Lights & Axles:** Compute Summer/Winter `time_zone` & `time_zone_name` via `zoneinfo` + `tzdata` (updating Jordan & Syria to permanent `UTC+3` `AST` and Greenland to `America/Nuuk`, preserving only the 12 supported `@@tz_*@@` tokens). Maintain statutory road-code YAML for seasonal car/truck/bus speed limits (Finland, Estonia, Lithuania, Sweden, fixing Iceland 80 km/h heavy truck limit & avoiding Spain truck anomalies), `lights_mandatory` (fixing `NL`/`CH`/`AL`/`TR`), and EU Directive `96/53/EC` + `ITF/OECD` axle limits.
- **Explicitly REJECTED (Do Not Build/Use):**
  1. **`GlobalPetrolPrices.com`:** Enforces **`CC BY-NC-ND 3.0`** (incompatible with open-source CC BY 4.0 derivatives) + anti-automation TOS + Cloudflare `403` on GitHub Actions runners. *(Note: `ARCHITECTURE.md`'s high-level diagram included `GlobalPetrolPrices` casually; synthesized architecture formally strikes it in favor of Tier 1/2/3.)*
  2. **`MyLPG.eu`:** No public API; TOS prohibits scraping.
  3. **Paid `IEA Energy Prices`:** Commercial subscription barrier.
  4. **Cracking/copying `3668352310` `3nK` files:** Legally/ethically toxic and inherits stale/wrong rules.
  5. **Direct ingestion of `westnordost/osm-legal-default-speeds` / OSM Wiki (`CC BY-SA 2.0`) into `CC BY 4.0` outputs:** ShareAlike license taint; permitted **exclusively as an internal CI drift-audit detector** comparing against curated statutory rules.

---

## 5. Workshop Packaging & Publishing Progression (Phase A -> Phase B)

`SCS Workshop Uploader` (`AppID 421800`) has **no CLI or batch mode** (and neither `421800`, `steamcmd`, nor `scs_packer.exe` is installed locally), while `steamcmd +workshop_build_item` performs **zero SCS validation**. V2 therefore decouples SCS validation from Steam upload in two disciplined phases:

1. **Phase A — Semi-Automatic Packaging & Offline Validation (Zero Stored Secrets):**
   - Builds dual completely isolated Workshop roots: `dist/workshop/summer/` and `dist/workshop/winter/` (`versions.sii` with **strictly one** `package_version_info : .universal` + `universal/` directory or normalized-epoch `universal.zip`).
   - Runs a strict **Offline SCS Validator** enforcing all SCS Wiki rules: `00001`–`00010` and `WARN 00001`/`00002` (omit `compatible_versions[]` and `display_name` from Workshop `manifest.sii`; enforce `mp_mod_optional: true`; `<=2` valid categories; `<=12`-char `[a-z0-9_]` unit segments; `276x162` `.jpg` `<1 MB`; UTF-8 no-BOM LF `.txt`/`.sii`/`.sui` `<1 MB`; POSIX `/` paths only; no extraneous root files; no ZIP-renamed-`.scs`; zero `3nK`; `regions[]` & `bus`/`train`/`tram` invariants).
   - **Canonical Payload SHA-256 Diff Gate (`state/published.json`):** Hashes sorted `(relative_path, normalized_bytes)` excluding build timestamps/volatile metadata so identical upstream weeks exit `no-op` with zero subscriber update spam.
   - Emits `CHANGELOG_SUMMER.md` / `CHANGELOG_WINTER.md` + release artifacts on Friday `06:00 UTC` for 1-minute manual upload via SCS Workshop Uploader GUI.

2. **Phase B — Full-Automatic SteamCMD Publishing (Gated by Verification Spike):**
   - **Mandatory Pre-Flight Verification Spike (`visibility: 2` hidden test item):** Must prove across 2+ consecutive days on `ubuntu-latest` that: (1) generating 30s TOTP from `STEAM_SHARED_SECRET` *immediately after* `steamcmd` self-updates avoids `Invalid Login Auth Code` (`game-ci/steam-deploy#56` `config.vdf` token rot); (2) omitting `title`/`description`/`previewfile`/`visibility` in `manifest.vdf` preserves Steam Community metadata/tags; (3) ETS2 `1.62.3.3s` mounts the Workshop item cleanly with zero `game.log.txt` `[unit]`/`[mods]` errors; and (4) SCS Workshop Uploader (`421800`) still adopts/updates the item after clearing `mod_items_data.sii`.
   - **Production Isolation & Security:** Must use **separate GitHub Actions matrix jobs (`summer`, `winter`)** with distinct `stagingPath`s (never sequential `m00nl1ght-dev/steam-workshop-deploy` runs, whose `rsync` lacks `--delete` and leaks Summer files into Winter!), dedicated unrestricted (`$5+` spent) Steam account owning ETS2 `227300`, `steam-workshop-prod` Environment approval, pinned 40-char action SHAs / Docker digests, `pull_request` trigger ban, and sanitized log output (`GHSA-mj96-mh85-r574`).

---

## 6. Implications for Roadmap & Research Flags

Based on technical dependencies, risk reduction, and MVP-to-global scaling, research points to a **6-phase roadmap**:

| Phase | Scope & Deliverables | Key Pitfalls Mitigated | Research Flag |
|---|---|---|---|
| **1. Clean-Room VFS, Baseline Extractor & Surgical SII Engine** | `uv` + `src/ets2v2/` scaffold; MIT/stdlib HashFS v1/v2 + `3nK` reader; ETS2 `1.62.3.3s` `def.scs`/`locale.scs` schema/manifest extractor; comment/region-preserving SII/SUI & `speed_limits.sii` parser/rewriter; invariant test fixtures. | Avoids `3249064596` regex corruption (`estonia`/`armenia`), `3nK` copying, GPL taint, `bus`/`train`/`tram` & `regions[]` loss, Windows `tzdata` absence. | **Standard patterns** (formats and schemas already byte-verified; skip `--research-phase`). |
| **2. Canonical Realism Registry, Seasonal Laws & Dual Core Workshop Builds (Phase A)** | Unified single-source country laws (`speed_limits`, `lights_mandatory`, `axles`, `zoneinfo`+`tzdata` DST); isolated `dist/workshop/{summer,winter}/` builder for the 36 Vanilla+DLC countries; Offline SCS Validator (`00001`–`00010` + `WARN 00001`/`00002`); SHA-256 diff gate + Phase A GitHub Actions CI & changelogs. | Eliminates Summer/Winter drift, `@@tz_cet@@`/`@@tz_wet@@` UI bugs, Workshop Uploader errors (`00001`–`00010`, `WARN 00001`/`00002`), and no-op subscriber spam. | **Standard patterns** (all SCS rules & 36-country baselines verified). |
| **3. Tier 1 Automated Fuel, FX & 43-Locale Totem Engine** | Frankfurter v2 + ECB + `fawazahmed0` FX; EC Weekly Oil Bulletin (+ `FionnHughes` / `fuel-prices.eu` fallbacks), UK DESNZ, NO SSB, FR/DE/ES/IT/NL multi-grade APIs; `prices.lock.json` circuit-breaker + `±25%` bounds; zero-DDS 43-locale totem patching (incl. `17+` active unmapped `gas_*` signs, `gas_is_ip1_98`, `fp_ie_*`, placeholder boards). | Fixes Friday `06:00 UTC` schedule drift, `EL`→`GR`, ECB `RUB`/CIS gaps, EUR vs local totem currency confusion, `fr_ca`/`fr_qc` locale desync, and DDS baking trap. | **Targeted research / spike (`--research-phase`)** for national API schema quirks (`Tankerkönig` key, MIMIT CSV, EC link scraping) & totem font width / `<sup>9</sup>` formatting rules. |
| **4. ProMods Companion Addon & `ets2v2 compose-local` Dynamic Map Combo Engine** | Optional ProMods `EU+ME+TGS+MA` companion package (`pm_*_fuel` totems + `scotland`/`wales` preservation) AND `ets2v2 compose-local` CLI consuming `realism-snapshot-{season}.json` across user `mod/` + load order (`.sui`/`.sii`, `base/`, empty stubs, `max_of_map_and_real`, `patch_if_single_tz`, `AEM!`/encrypted ZIP diagnostics). | Prevents $O(2^k)$ combo preset explosion, duplicate `country.data.*` crashes, RusMap/TST/UMCF/EAA geometry clobbering, and silent `AEM!` failures. | **Needs `--research-phase`** to verify ProMods pinned baseline sourcing, `profile.sii`/`game.log.txt` active-load-order parsing across Steam/local mods, and JRR hardcoded totem opt-in rules. |
| **5. Global Tier 2/3 Expansion & OSM Drift Guard** | Global Tier 1 APIs (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`); guarded Tier 2 national scrapers (`MD`, `MK`, `RU`, `AZ`, `BY`, `IS`, `ID`, `IL`, `GCC`, `ZA`, `KE`, `NG`); Tier 3 curated baselines (`200+` territories); internal OSM/Wikidata `CC BY-SA` speed drift-audit CI job. | Prevents Cloudflare `403` CI crashes (`GlobalPetrolPrices` rejected), `CC BY-SA` license contamination, and stale third-world fuel rates. | **Needs `--research-phase`** per Tier 2 national portal HTML selector, encoding (`windows-1251`/Latin-1), and `Opinet` key workflow. |
| **6. Phase B Full-Auto SteamCMD Workshop Publishing** | Dedicated publisher account + mandatory hidden-item (`visibility: 2`) verification spike (multi-day TOTP auth, metadata preservation, `1.62.3.3s` `game.log.txt` check, `421800` re-adoption after clearing `mod_items_data.sii`) → matrix `summer`/`winter` production deploy workflow. | Prevents `config.vdf` token rot (`#56`), `rsync` Summer/Winter cross-contamination, TOTP 30s self-update races, and `GHSA-mj96-mh85-r574` credential leaks. | **Hands-on verification spike mandatory** (practical Steamworks/SteamCMD validation rather than doc lookup). |

---

## 7. Confidence Assessment & Gaps to Address

| Area | Confidence | Verified Basis & Remaining Gaps |
|---|---|---|
| **Technology Stack & SII/HashFS Tooling** | **HIGH** | Local Python `3.12.13` / `uv 0.11.31` toolchain and HashFS v1/v2 + `3nK` binary parsing verified directly against 96 game `.scs` files and Workshop archives. |
| **ETS2 `1.62.3.3s` & Reference Mod Forensics** | **HIGH** | All 36 vanilla countries, 373–555 fuel boards, 43 locales, 12 `tz_*` tokens, and all bugs in `3249064596`/`3668352310` verified byte-for-byte on disk. |
| **Map Combo Architecture (Option C)** | **HIGH** | Backed by empirical 503-mod census (`86` country mods, 6 edge cases). **Gap:** Exact load-order parser strategy (`game.log.txt` vs decrypted `profile.sii` vs explicit modlist file) and ProMods def baseline acquisition method need Phase 4 planning resolution. |
| **Global Data Sources & Licensing** | **HIGH (Tier 1) / MEDIUM (Tier 2–3)** | Licenses (`CC BY 4.0`, `OGL v3`, `MIT`, `CC0`, `PD`) and FX feeds verified live. **Gap:** Individual Tier 2 portal HTML selectors (`anre.md`, `erc.org.mk`, `rosstat`, `aramco`, `dmre`) and optional free API keys (`Tankerkönig`, `EIA`, `Opinet`) need Phase 3/5 integration validation. |
| **Workshop Automation (Phase A -> B)** | **HIGH (Rules) / MEDIUM (Account Ops)** | SCS error codes `00001`–`00010`, `WARN 00001`/`00002`, `config.vdf` rot, and `rsync` bug verified in source/docs. **Gap:** Dedicated `$5+` unrestricted Steam publisher account ownership & live TOTP spike on `ubuntu-latest` remain untested until Phase 6. |

---

## 8. Explicit Decision Matrix for the User Checkpoint

Before locking `REQUIREMENTS.md` and `ROADMAP.md`, please confirm or override the following 6 concrete architectural & data-collection decisions:

| # | Decision Topic | Recommended Default (Synthesized) | Alternatives Available | Impact on Requirements & Roadmap |
|---|---|---|---|---|
| **1** | **Map Combo Distribution Model (Open Q1)** | **Option C:** Strict **Vanilla+DLC Core** (`Summer` & `Winter`, `36` countries) on Steam Workshop + **optional ProMods Addon** + **`ets2v2 compose-local` CLI** consuming CI `realism-snapshot-{season}.json` (~200+ countries) for arbitrary combos (`RusMap`, `TST`, `UMCF`, `Beyond`, `JRR`, `SEA`, `RoC`, `PJ`, `EAA`, `Africa`). | **A:** Static Workshop presets per combo (`50+` packs). **B:** Local CLI only (no Workshop editions). | Locks Phase 2 (Core Workshop), Phase 4 (ProMods + `compose-local`), and drops multi-combo Workshop preset maintenance. |
| **2** | **ProMods Addon Packaging & Baseline Sourcing** | Ship ProMods `EU+ME+TGS+MA` (`pm_*_fuel` totems + merged `.sui`/`speed_limits.sii`) as a **pair of seasonal Workshop companion addons** (`Summer` & `Winter`) — generated cleanly at build/user-supplied ProMods def path without illegally redistributing raw ProMods map assets. | Single ProMods addon (or skip ProMods on Workshop and handle ProMods solely via `compose-local`). | Determines whether Phase 4 targets 2 additional Workshop listings + how ProMods defs are pinned/sourced in CI. |
| **3** | **`compose-local` Conflict & Protected-Archive Policies** | Default to **`max_of_map_and_real`** for axle weights (`60t` IS, `48t` RU, `80t` BR, `105t` FI), **`patch_if_single_tz`** for multi-TZ countries (preserving TST 27-TZ Russia & UMCF 5-TZ KZ), **warn clearly + support `--unpacked-defs` / external `Extractor` hook** on `AEM!`/encrypted ZIPs, and keep hardcoded numeric totems (`JRR`/`7RM`) opt-in (`--patch-hardcoded-totems`). | Always overwrite axles/TZs unconditionally; or silently skip unreadable `AEM!` mods. | Defines CLI flags, safety invariants, and error UX in Phase 4. |
| **4** | **Vanilla Totem Override Footprint & `country_code` Policy** | **Option 4a (Low-conflict):** Patch `/locale/fuel_price_strings.sui` + **only** the `17+` unmapped/placeholder/blank `def/sign/board/*.sii` boards (leaving the other ~353 working vanilla boards untouched to minimize sign-mod conflicts), and **preserve vanilla ISO codes** (`"GB"`, `"FI"`, `"RU"`) by default with an optional plate-code flag. | **Option 4b (`3249064596`-style):** Rewrite all ~375–457 `def/sign/board/*.sii` to custom `@@fp_*_ets2v2@@` + `local_module.ets2v2_fuel.sii` for full multi-grade/font customization (`<sup>9</sup>`, pence). | Directly shapes Phase 3's totem emitter scope and mod-compatibility guarantees. *(Note: multi-grade formatting customization favors 4b if font widths require custom tokens.)* |
| **5** | **Global Data Licensing & Sources (Open Q2)** | **Approve 3-Tier Open Pipeline:** Tier 1 (`CC BY 4.0` / `OGL v3` / `PD` / `CC0`) + Frankfurter v2/ECB/fawazahmed0 FX + Tier 2 guarded national portals + Tier 3 curated community baselines; **explicitly reject** `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`), `MyLPG.eu`, paid IEA, `3nK` cracking, and direct redistribution of OSM `CC BY-SA` tables (CI audit-only). | Accept non-commercial restrictions (breaks open-source mod licensing) or drop non-EU Tier 2/3 automation (manual global updates only). | Locks Phase 3 & Phase 5 data sources, `LICENSE`/attribution obligations, and CI fallback architecture. |
| **6** | **Workshop Publishing Progression & Account Security** | **Phase A Semi-Auto first** (zero CI Steam secrets, Offline SCS Validator `00001`–`00010` + `WARN 00001`/`00002`, SHA-256 diff gate, GitHub Artifacts + changelogs), graduating to **Phase B SteamCMD + inline 30s TOTP** on isolated matrix jobs **only after passing the hidden-item (`visibility: 2`) spike** using a dedicated unrestricted (`$5+` spent) Steam publisher account owning `227300`. | Stay Phase A forever (no Steam credentials in CI); or test Phase B directly on maintainer's primary Steam account. | Defines Phase 2 CI outputs and Phase 6 gating criteria / Steam account prep. |

---

## 9. Aggregated Sources

- **Direct Local Binary & Mod Forensics (2026-11-15):**
  - ETS2 `1.62.3.3s` (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\`): all 96 `.scs` archives including `version.scs`, `def.scs`, `locale.scs`, `economy_data.sii`, `dlc_*.scs`, and `game.log.txt`.
  - Installed Workshop mods (`D:\SteamLibrary\steamapps\workshop\content\227300\`): `3249064596` (*Real life fuel prices*), `3668352310` (*Updated WINTER speed limits*), `3668351598`, `1820303287`, `3002586900`.
  - 503-mod local census (`D:\ETS2Data\Euro Truck Simulator 2\mod`): `Country_Speed_Fuel_Merge.scs`, ProMods EU/ME/TGS/MA, RusMap, TST, ROEX, UMCF, GMC Beyond Fix, JRR, SE Asia, RoC, Project Japan Relocated, EAA Rescaled, SemEuropa, plus 12 `AEM!` / `Bad magic` / encrypted ZIP archives.
  - Legacy V1 repository (`D:\CODE\Ets2 Mod\`): `pyproject.toml`, `docs/DDS-SPIKE-VERDICT.md`, `docs/SCS-REFERENCE-VERDICT.md`, `tools/`.
- **SCS Software Official Documentation & Tooling Specs:**
  - Local mirror `.agents/skills/scs-modding-wiki/` & live `modding.scssoft.com` (`SCS_Workshop_Uploader/Changelog` `oldid=5814`, `Validation_errors_and_solutions_for_them` `oldid=5757`, `Warning_and_error_codes`, `Units` `oldid=5765`, `Game_data` `oldid=5754`, `Game_Archive_Packer` `oldid=5720`, `Mod_manager`, `versions.sii`, `Special:RecentChanges` through `2026-11-15`).
  - SCS Forums (`t=342966`, `t=347407`, `t=246228`, `t=276948`), `TheLazyTomcat/3nK_Transcode`, `sk-zk/TruckLib` & `Extractor` / `Switch-Bros/easy-scsmodmanager` (format verification only; GPL not copied).
- **Data Feeds, Licenses & Statutory Authorities:**
  - FX: Frankfurter v2 (`frankfurter.dev`, MIT), ECB `eurofxref-daily.xml`, `fawazahmed0/exchange-api` (CC0 1.0), CBR `XML_daily.asp`.
  - Fuel (Tier 1/2/3): EC Weekly Oil Bulletin (`CC BY 4.0`) + `FionnHughes`/`the-Hull` mirrors + `fuel-prices.eu` (`CC BY 4.0`), UK DESNZ (`OGL v3`), Norway SSB `09654` (`CC BY 4.0`), FR `prix-carburants.gouv.fr` (*Licence Ouverte*), DE Tankerkönig (`CC BY 4.0`), ES MITECO, IT MIMIT (*IODL 2.0*), NL CBS, US EIA (`PD`), BR ANP, AR Energía, CO SICOM, CL CNE, MY OpenDOSM (`CC BY 4.0`), JP METI, KR Opinet, CH BFS/LIK, MD ANRE, MK ERC, RU Rosstat, plus `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`, rejected) & `MyLPG.eu` (TOS-restricted, rejected) & IEA (commercial, rejected).
  - Rules & Timezones: Python `zoneinfo` + `tzdata`, Bulgaria EUR adoption (2026-01-01), Jordan/Syria permanent UTC+3, EU Directive `96/53/EC` & ITF/OECD axle weights, EC Road Safety / SWOV `lights_mandatory`, `westnordost/osm-legal-default-speeds` (`CC BY-SA 2.0`, CI audit-only).
- **Steam Workshop CI/CD & Security References:**
  - `m00nl1ght-dev/steam-workshop-deploy@v4` (`action.yml`, `steam_deploy.sh`), `game-ci/steam-deploy#56` & `duty_guvnor@743bf12` (`config.vdf` rot vs TOTP), `GHSA-mj96-mh85-r574`, Steamworks `ISteamUGC` / `workshop_build_item` documentation.
