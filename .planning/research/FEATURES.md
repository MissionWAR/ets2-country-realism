# Feature Landscape & Global Real-World Data Sources

**Domain:** ETS2 1.62 Realistic Fuel Prices, Pump Totems, Seasonal Country Rules (Summer/Winter Speed Limits, Timezones, DRL, Axle Mass Limits), and Automated Global Data Pipeline  
**Researched:** 2026-11-15  
**Overall Confidence:** **HIGH** (Reference mods & ETS2 1.62 base archives forensically verified byte-for-byte on disk; global official APIs/licenses verified live; minor Tier 2/3 portal stability caveats noted as MEDIUM)

---

## Executive Summary

Direct forensic inspection of ETS2 **1.62** (`def.scs`, `locale.scs`, `dlc_*.scs`), **`3249064596\universal.scs`** (*Real life fuel prices* by `kworey`), and **`3668352310\universal.scs`** (*Updated WINTER speed limits* by `neuhr`) establishes the exact technical baseline, feature parity target, and defect list for `Ets2 Mod V2`:

1. **Neither reference mod bakes DDS textures.** All roadside fuel totems operate exclusively through text template `.sii` overrides under `/def/sign/board/` paired with `/locale/fuel_price_strings.sui` or `locale/<lang>/local_module.<id>.sii`.
2. **ETS2 1.62 introduced breaking baseline changes** over 1.60/older releases: `def/country.sii` now includes **36** countries (wiring `iceland.sui` with a 5-element `mass_limit_per_axle_count[]` up to 60,000 kg), `def/sign/board/` expanded to **457** `gas_*` templates (including new British Isles `gas_bi_*` and Ireland `gas_ie_*` rework boards), and Bulgaria adopted the **Euro (`EUR`)** on 2026-01-01 (even though ETS2 1.62 `economy_data.sii` still carries legacy `BGN*`).
3. **Both reference mods carry concrete, fixable defects** — from corrupted country names (`estonia.sui`: `"@@tz_eest@@i"`), backwards traffic (`armenia.sui`: `leftside_traffic: true`), duplicate IDs (`libya`/`libya1` both `120`), missing/stale `locale/fr_ca/` modules, and 86 unmapped `gas_*` boards in `3249064596`, to wrong `lights_mandatory` overrides and `3nK`-obfuscated `speed_limits.sii` in `3668352310`.
4. **Legally clean automated global collection is achievable via a 3-Tier pipeline:** **CC BY 4.0 / CC0 / OGL / Public Domain** official APIs cover EU27, UK, Norway, Brazil, Argentina, Colombia, Malaysia, US, and global FX (**Tier 1**, 219+ currencies via `Frankfurter v2` + `ECB` + `fawazahmed0/exchange-api`), while **Tier 2** guarded scrapers and **Tier 3** curated community baselines cover the remaining Balkans, CIS, Middle East, Africa, and Asia — **strictly avoiding** non-open-source aggregators such as `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`, anti-automation TOS) and `MyLPG.eu` (no public API, scraping prohibited).

---

## 1. Reference Mod Forensics & ETS2 1.62 Baseline

### 1.1 `3249064596` (*Real life fuel prices*, HashFS v2, 628 files) — **HIGH confidence**

- **Coverage (75 `def/country/*.sui` files):**
  - **36 Vanilla + DLC countries** matching ETS2 1.62 `def/country.sii` (`albania` through `uk`, including `iceland.sui`).
  - **39 Map-Mod countries:**
    - *ProMods Europe & Dependencies (23):* `aland`, `andorra`, `armenia`, `azerbaijan`, `belarus`, `can_islands`, `cyprus`, `faroe`, `georgia`, `gibraltar`, `greenland`, `guernsey`, `iom`, `ireland`, `jersey`, `liecht`, `malta`, `moldova`, `monaco`, `nireland`, `sanmarino`, `svalbard`, `ukraine`.
    - *ProMods Middle East (8):* `egypt`, `iraq`, `israel`, `jordan`, `lebanon`, `saudia`, `syria`, `westbank`.
    - *ProMods The Great Steppe (3):* `kazakhstan`, `turkmenistan`, `uzbekistan`.
    - *Maghreb / North Africa (5):* `morocco`, `tunisia` (documented in `description.txt`), plus legacy/unlisted `algeria`, `libya`, `libya1`.
  - **Multi-zone `russia.sui`:** Defines **15** `secondary_time_zone*` bounding boxes covering Kaliningrad (`@@tz_eet@@` / `+120`), Samara (`SAMT` `+240`), Yekaterinburg (`YEKT` `+300`), Moscow (`@@tz_msk@@` `+180`), Omsk (`OMST` `+360`), and Krasnoyarsk (`KRAT` `+420`) for RusMap / PM-TGS / SibirMap / Volga / Altai compatibility.
- **How `fuel_price` in `.sui` works:**
  - Verified against `def.scs` 1.62 `def/economy_data.sii` (`currency_code[]: "EUR"`, `currency_ratio[]: 1`) and cross-checked against all 70 countries in `3249064596/description.txt`: **`fuel_price` is ALWAYS EUR per litre of standard retail diesel (inclusive of VAT/excise)**. Example exact matches: Germany `2.259`, Albania `2.290` (`208 lek`), UK `2.361` (`£1.97`), Poland `1.766` (`7.76 zł`), Kazakhstan `0.727` (`T 363`).
- **How Fuel Price Totems Work (Zero DDS Baking):**
  - **Vanilla 1.62 mechanism:** In `locale.scs`, every `locale/<lang>/local.sii` executes `@include "/locale/common.sui"`, which includes `/locale/fuel_price_strings.sui` (368 lines, **99 keys** covering **36** countries `al`..`xk`). Roadside sign templates in `def/sign/board/*.sii` simply render `text: "@@fp_<cc>_<grade>@@"`.
  - **`3249064596` mechanism:** Ships **0 textures** and overrides **375** files under `def/sign/board/*.sii` (`371 gas_*` + `es_95_01.sii`, `es_diesel_01.sii`, `pt_95_01.sii`, `pt_diesel_01.sii`) plus **4 localization modules** across `locale/<lang>/`:
    - `local_module.kworey_fuel_ets.sii`: **103 keys**, **36 countries**, **11 grades** (`diesel`, `diesel5`, `diesel_plus`, `e85`, `mpo`, `natural92`, `natural95`, `natural98`, `natural100`, `super`, `unleaded`). Renames 353 vanilla tokens (`@@fp_*@@` → `@@fp_*_kwo@@`) to avoid collision, and populates 16 hardcoded-zero/blank vanilla signs (`0.00`, `00.00`, `0.000`, `" "`), while swapping back `gas_is_yokull_95` and `gas_is_yokull_diesel` (which vanilla 1.62 swapped).
    - `local_module.pm_fuel.sii`: **1,001 keys**, **56 ProMods Europe countries**, **20 grade/format suffixes** (including `_v0`..`_v4`, `<sup>9</sup>` tenth-cent formatting, `lpg`, `e85`, `adblue`, `biogas`, `electric`, `diesel_colour`).
    - `local_module.pm_me_fuel.sii`: **84 keys**, **8 countries** (`eg`, `irq`, `isr`, `jor`, `ksa`, `lbn`, `ps`, `syr`), **3 grades** (`diesel`, `lpg`, `natural95`).
    - `local_module.pm_tgs_fuel.sii`: **48 keys**, **3 countries** (`kz`, `tm`, `uz`), **7 grades**.
  - **Totem Currency Display Rules:** Totems display **native local currency and local pump convention**, NOT EUR everywhere:
    - Non-EUR national currencies on totems: `AL` (ALL lek int), `BA` (BAM), `CH` (CHF), `CZ` (CZK), `DK` (DKK), `HU` (HUF int/dec), `IS` (ISK), `MK` (MKD), `NO` (NOK), `PL` (PLN), `RO` (RON), `RS` (RSD), `RU` (RUB), `SE` (SEK), `TR` (TRY). *Note:* Bulgaria (`BG`) switched to `EUR` on 2026-01-01 (`1.90` on totem = €1.90).
    - Sub-unit quirks in `3249064596`: UK base `kworey_fuel_ets` displays **pence** (`fp_gb_diesel_kwo = "197.0"`) while `pm_fuel` displays **pounds** (`"1.97"`) and vanilla 1.62 `fuel_price_strings.sui` uses pounds (`"1.993"`); Netherlands base uses **eurocents** (`"252.5"`) while `pm_fuel` (`"2.53"`) and vanilla 1.62 (`"2.51"`) use euros. Sign template font bounding boxes dictate digit/decimal formatting.

#### Confirmed Bugs in `3249064596` (Must Fix in V2)

| # | Location | Observed Defect in `3249064596` | Vanilla 1.62 / Ground Truth |
|---|----------|--------------------------------|-----------------------------|
| 1 | `def/country/estonia.sui` | `name: "@@tz_eest@@i"` (blind search-replace corrupted `"Eest"`) | `name: "Eesti"` |
| 2 | `def/country/armenia.sui` | `leftside_traffic: true` | `leftside_traffic: false` (right-hand traffic) |
| 3 | `def/country/libya.sui` & `libya1.sui` | Duplicate `country_id: 120` collision (`0.020` vs `0.024`) | Unique `country_id` or remove dead duplicate `libya1.sui` |
| 4 | `locale/fr_ca/` | Missing `local_module.kworey_fuel_ets.sii`; stale `pm_fuel` (847 vs 1001 keys), `pm_me_fuel` (111 vs 84), `pm_tgs_fuel` (30 vs 48); ships dead `fr_qc` (ETS2 1.62 has **43** locales, not 44) | All **43** active ETS2 1.62 locales synced identically |
| 5 | `def/country/svalbard.sui` | `fuel_price: 2.573` (copied mainland Norway), contradicting `description.txt` (`€2.725`) | Real Svalbard is tax-free Norway (cheaper than mainland, not identical/higher) |
| 6 | `def/country/iceland.sui` | Stale 4-element `mass_limit_per_axle_count[]` `[18000, 26000, 36000, 40000]` | ETS2 1.62 `dlc_iceland` baseline uses 5 elements `[18000, 29000, 38000, 46000, 60000]` |
| 7 | `def/country/latvia.sui` | `pos: (49500, 0, -39000)` | ETS2 1.62: `pos: (49500, 0, -38000)` |
| 8 | `def/sign/board/*.sii` | Misses **86** of 457 `gas_*` boards in 1.62 (**17** active `@@fp_*@@` boards: `10 gas_bi_*`, `4 gas_ie_*`, `2 gas_ba_*_lpg`, `1 gas_dk_92`; **38** `"0.00"`/`"00.00"`/`"0.000"`/`"123.9"` placeholders incl. `gas_ie_cloveroil_*`, `gas_ie_opetrol_*`, `gas_bi_*_super*`, `gas_no_primel_*`, `gas_dk_primel_*`; **31** blank `" "` boards mostly `*_lpg`); **explicitly blanks** `gas_is_ip1_98.sii` (`" "`) despite vanilla `@@fp_is_natural98@@` | Populate all active `@@fp_*@@` boards (incl. `fp_ie_*` which vanilla `locale.scs` omitted!), restore `gas_is_ip1_98.sii`, and map `0.00`/`00.00`/`000`/`123.9` placeholders where fuel grades exist |
| 9 | `def/country/sanmarino.sui` | `fuel_price: 1.46` (stale 2-decimal vs Italy `2.239`) | Tracks Italian enclave pump prices (~€2.2+ diesel, minor tax delta) |
| 10 | `jordan.sui`, `syria.sui` + EU DST | Hardcodes winter timezones everywhere; keeps `jordan.sui`/`syria.sui` on `tz=180` with `tzn="@@tz_eest@@"` | Jordan & Syria abolished DST in Oct 2022 → permanent `UTC+3` (`AST` / `180`), not EEST; EU needs Summer & Winter builds |
| 11 | `uk.sui`, `nireland.sui` | Overrides `country_code: "UK"` | Vanilla 1.62 is `"GB"`; make `UK` override explicitly documented or configurable |

---

### 1.2 `3668352310` (*Updated WINTER speed limits*, HashFS v1, 112 files) — **HIGH confidence**

- **Coverage:** **36** vanilla+DLC countries (`albania` through `uk`, matching 1.62 `def/country.sii`). Also bundles `pre144info.scs` + `versions.sii` as an informational guard for pre-1.44 compatibility.
- **Exact Summer (`def.scs` 1.62) vs Winter (`3668352310`) Differences:**
  - **`time_zone` & `time_zone_name`:** Switches all DST-observing countries from Summer (`CEST` 120, `EEST` 180, `WEST` 60, `BST` 60) to Winter Standard Time (`CET` 60, `EET` 120, `WET` 0, `GMT` 0), plus Russia Kaliningrad `KALT` (120). **CRITICAL ENGINE DETAIL:** `locale.scs` 1.62 (`localization.sui`) ONLY defines 12 `tz_*` keys (`tz_bst`, `tz_cdt`, `tz_cest`, `tz_eet`, `tz_eest`, `tz_gmt`, `tz_msk`, `tz_mst`, `tz_mdt`, `tz_pdt`, `tz_trt`, `tz_west`). **`@@tz_cet@@` and `@@tz_wet@@` DO NOT EXIST in vanilla `locale.scs`.** Using `"CET"` and `"WET"` as plain quoted strings (as both `3249064596` and `3668352310` do) avoids literal `"@@tz_cet@@"` rendering bugs in UI.
  - **`lights_mandatory` (4 differences vs `def.scs` 1.62):**
    - `netherlands`: `false` in `3668352310` vs `true` in 1.62 → **Reference mod is RIGHT**, daytime headlights are NOT legally mandatory for cars/trucks in normal visibility in the Netherlands (SWOV / European Commission).
    - `switzerland`: `true` in `3668352310` vs `false` in 1.62 → **Reference mod is RIGHT**, Switzerland mandates DRL / dipped headlights year-round since 2014.
    - `albania`: `true` in `3668352310` vs `false` in 1.62 → **Vanilla 1.62 is RIGHT**, Albania only requires lights at night, in tunnels, and in poor daytime visibility.
    - `turkey`: `true` in `3668352310` vs `false` in 1.62 → **Vanilla 1.62 is RIGHT**, general clear-daytime mandatory dipped lights do not apply to all vehicles in Turkey.
  - **`mass_limit_per_axle_count[]`:** Zero differences between `3668352310` and `def.scs` 1.62 across all 36 countries.
  - **`country_code` overrides:** `finland.sui` (`"FIN"` vs `"FI"`) and `russia.sui` (`"RUS"` vs `"RU"`). V2 should **keep vanilla ISO/game codes** (`"FI"`, `"RU"`, `"GB"`) by default unless explicitly needed for license plate mods.
  - **`_vtd/*.sui`:** Moves city bounding-box `regions[]` / `region_areas[]` (`_worldmap`, `_berlin`, etc.) into `@include "_vtd/<country>.sui"` while preserving vanilla `regions[]` on `bosnia`, `finland`, `norway`, `spain`, and `sweden`. V2 does not need `_vtd`, **but MUST preserve all 5 vanilla `regions[]` / `region_areas[]` definitions**.
  - **`speed_limits.sii` encoding:** All 36 files inside `3668352310` use SCS's **`3nK\x01` encrypted SII format** (`b'3nK\x01'`), not plaintext. **V2 will NOT crack or copy `3nK` blobs**; all Summer and Winter speed limits will be built cleanly from verified statutory sources (with known vanilla 1.62 discrepancies audited, e.g., Iceland heavy-truck 80 km/h limit vs vanilla 1.62 `90/90/90`).

---

## 2. Global Real-World Data Source Evaluation

> **Open-Source Licensing Rule (`PROJECT.md` = CC BY 4.0):**
> Reject any source carrying **NC / ND** restrictions (`CC BY-NC-ND 3.0`), anti-scraping Terms of Service, or **ShareAlike (`CC BY-SA`)** taint if redistributed in derivative data files without isolating or keeping separate.

### 2.1 FX Currency Conversion APIs (Required for `.sui` `fuel_price` in EUR/L)

| Candidate | Coverage | Cadence | License / TOS | Key / Rate Limit | Verdict & Fallback Role | Confidence |
|-----------|----------|---------|---------------|------------------|-------------------------|------------|
| **Frankfurter v2** (`api.frankfurter.dev/v1/...` or v2) | **219 currencies** + 39 assets from **108 central banks** & official providers | Daily business-day fixings (cached locally) | **MIT License** (open source, self-hostable; free for commercial use) | None; no quota (fair-use rate limit) | **PRIMARY FX:** Solves *all* non-ECB currencies (ALL, BAM, RSD, MKD, RUB, BYN, UAH, AMD, GEL, AZN, KZT, UZS, TMT, EGP, SAR, JOD, IQD, LBP, SYP, MAD, TND, DZD) in one keyless REST JSON/CSV call. | **HIGH** |
| **ECB Eurofxref** (`ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`) | ~30 major currencies (`GBP`, `CZK`, `DKK`, `HUF`, `PLN`, `RON`, `SEK`, `CHF`, `ISK`, `NOK`, `TRY`, `ILS`, `BRL`, `IDR`, `JPY`, etc.) | Daily ~16:00 CET | **ECB Free Use / Open Data** (attribution) | None | **SECONDARY / VALIDATOR:** Direct official XML authoritative check for ECB currencies; misses CIS/Balkans/MENA. | **HIGH** |
| **`fawazahmed0/exchange-api`** (jsDelivr CDN + GitHub mirror) | 200–300+ currencies | Daily | **CC0 1.0** (Public Domain) | None (CDN-backed) | **TERTIARY FALLBACK:** Zero-cost static JSON fallback if `api.frankfurter.dev` times out. | **HIGH** |
| **CBR XML** (`cbr.ru/scripts/XML_daily.asp`, `windows-1251` XML) | Official Central Bank of Russia rates vs RUB | Daily | Public Central Bank data | None | **REGIONAL VALIDATOR:** Backup check for RUB/BYN/KZT/UZS cross-rates if needed. | **MEDIUM** |

---

### 2.2 Fuel Price Sources by Region

#### A. EU27 + UK + EEA/EFTA (Tier 1 Primary Automation)

| Source | Coverage | Cadence | License / TOS | Access & Fragility | Verdict | Confidence |
|--------|----------|---------|---------------|--------------------|---------|------------|
| **EC Weekly Oil Bulletin** (`energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en`) | **EU27** (incl. Bulgaria in EUR from 2026) — Diesel, Euro-super 95, Heating Oil, LPG w/ & w/o taxes | Weekly (Monday survey, published Wed/Thu) | **CC BY 4.0** (Commission Decision 2011/833/EU) | `.xlsx` (`Prices with taxes`, `2005 onwards`). **Medium fragility:** Drupal UUID `/document/download/<uuid>_en` links can rotate; parser must scrape the bulletin landing page anchor cleanly rather than hardcoding UUIDs. | **PRIMARY EU27 SOURCE** | **HIGH** |
| **`FionnHughes/eu-weekly-oil-bulletin`** (Hugging Face) & **`the-Hull/weekly_oil_bulletin`** (GitHub) | EU27 (+ UK historical) tidy CSV/Parquet/JSON | Weekly mirror | Open-source mirrors of CC BY 4.0 EC data | Zero scraping; flat ISO-2 columns (`petrol_95`, `diesel`, `lpg`) | **FALLBACK #1** when EC `.xlsx` schema or UUID breaks | **HIGH** |
| **`fuel-prices.eu/api/docs`** (`GET /live/board_now.php`) | Pan-European (`AD`, `AT`, `CH`, `DK`, `ES`, `FR`, `GB`, `GR`, `HR`, `IS`, `IT`, `NO`, etc.) | Weekly/Live | **CC BY 4.0** (aggregations; upstream gov OGL/CC-BY) | Keyless JSON, `<500B` summary; non-commercial-abusive threshold (>300 req/10m logged) | **FALLBACK #2 & MICROSTATE/NON-EU EUROPE BRIDGE** (`AD`, `CH`, `IS`, `NO`) | **HIGH** |
| **UK DESNZ Weekly Road Fuel Prices** (`gov.uk/.../weekly-road-fuel-prices`) | UK (ULSP 95 + ULSD Diesel pump averages in GBP/pence) | Weekly (Monday) | **Open Government Licence v3.0 (OGL v3)** | Direct CSV/XLSX download; optional **UK Fuel Finder API** (OAuth2 client credentials, live forecourt feeds) | **PRIMARY UK SOURCE** | **HIGH** |
| **Norway SSB Table `09654`** (`data.ssb.no/api/pxwebapi/v2/.../table/09654`) | Norway (95 octane, Diesel in NOK/L) | Monthly (fallback/verify vs `fuel-prices.eu`/Drivkraft) | **CC BY 4.0** (NLOD) | Keyless PxWebApi v2 JSON-stat2 / CSV | **OFFICIAL NO ANCHOR** (monthly lag; pair with `fuel-prices.eu` for weekly delta) | **HIGH** |
| **National Daily Station Open APIs** (France `prix-carburants.gouv.fr` *Licence Ouverte*; Germany `Tankerkönig` *CC BY 4.0* key; Spain MITECO REST; Italy MIMIT CSV *IODL 2.0*; Netherlands CBS StatLine OData) | FR, DE, ES, IT, NL (plus E85, SP98, 100, LPG, Diesel+) | Daily / 10-min | **CC BY 4.0 / Licence Ouverte / IODL 2.0** | Direct open JSON/XML/CSV/OData | **MULTI-GRADE TOTEM UPGRADE:** EC Bulletin only tracks `95` + `Diesel` + `LPG`. National APIs supply **real SP98, Ultimate/Diesel+, E85** for totems instead of naive percentage multipliers! | **HIGH** |
| **Eurostat SDMX API** (`ec.europa.eu/eurostat/api/dissemination/...`) | EU household electricity/gas (`nrg_pc_204`/`202`), semi-annual | Semi-annual | **CC BY 4.0** | No motor-fuel weekly advantage over EC Weekly Oil Bulletin | **REJECT for weekly fuel** (too slow; EC Oil Bulletin is authoritative) | **HIGH** |

#### B. Non-EU Europe, Balkans, Switzerland, Turkey, Russia & CIS

| Country / Region | Recommended Primary Source | Access / Cadence / License | Fallback / Fragility Notes | Confidence |
|------------------|---------------------------|----------------------------|----------------------------|------------|
| **Switzerland** | **BFS/LIK** (`data.bfs.admin.ch` / `opendata.swiss`) + `fuel-prices.eu` | Official CPI average Petrol 95 & Diesel in CHF; Swiss Open Data (attribution) | BFS LIK is **monthly**; `fuel-prices.eu` gives live/weekly CHF parity | **HIGH** |
| **Moldova** | **ANRE Moldova** (`anre.md` e-Carburanți) | Official **daily** capped max prices (RON 95 & Diesel in MDL); public HTML table | Fragility: HTML structure changes require selector guard (Tier 2) | **MEDIUM** |
| **North Macedonia** | **ERC** (`erc.org.mk`) | Official weekly/biweekly Monday max decisions (`EUROSUPER BS-95/98`, `EURODIESEL`, MKD) | Public HTML/PDF notices (Tier 2); well-structured table | **MEDIUM** |
| **Russia** | **Rosstat** (`rosstat.gov.ru`) + **CBR XML** (`cbr.ru/scripts/XML_daily.asp`) | Official weekly consumer AI-92/AI-95/AI-98/Diesel averages (RUB) in XLSX/CSV | Fragility: Periodic URL changes / export-ban reporting shifts (Tier 2); keep `cbr-xml-daily.ru` / Frankfurter for RUB→EUR | **MEDIUM** |
| **Azerbaijan & Belarus** | **Tariff Council** (`tariff.gov.az` / `stat.gov.az`) & **Belneftekhim** (`belneftekhim.by`) | State-fixed national pump tariffs (AZN & BYN); low churn, event-driven updates | Tier 2/3 hybrid — prices change infrequently by state decree | **MEDIUM** |
| **Iceland** | `fuel-prices.eu` (CC BY 4.0) / **Orkusetur / FÍB** | Weekly/live ISK/L prices cross-checked via Frankfurter ISK→EUR | Resolves stale `gas_is_ip1_98` & `gas_is_yokull` gaps | **MEDIUM** |
| **Albania, Bosnia, Montenegro, Serbia, Kosovo, Ukraine, Georgia, Armenia, Kazakhstan, Uzbekistan, Turkmenistan, Turkey** | National portals (**EPDK/station lists TR**, **Ukraine MinEcon/Ukrstat**, **KZ Bureau of National Stats**, **GE Geostat**, **AM Armstat**, **UZ Stat.uz**) + Tier 3 curated baseline | Mix of Tier 2 parsers (HTML/bulletin scrapers) and Tier 3 curated weekly/monthly verified overrides | **Explicitly REJECTED:** `MyLPG.eu` (no public API, TOS forbids scraping), `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`), `Fuelo` commercial API without license check (only consider if written open-data permission obtained; per-station scraping fragile) | **MEDIUM** |

#### C. Global Expansion Regions (Middle East, Africa, East/SE Asia, South America, North America)

| Region / Country | Primary Source | Format / Cadence | License / TOS | Tier | Confidence |
|------------------|----------------|------------------|---------------|------|------------|
| **USA** | **US EIA API v2** (`api.eia.gov`) | REST JSON, Weekly (Monday) | **Public Domain** (free API key) | **Tier 1** | **HIGH** |
| **Brazil** | **ANP** (*Levantamento de Preços de Combustíveis*, `dados.gov.br` / `gov.br/anp`) | Weekly CSV (`;`-delimited, Latin-1) | **Open Gov Data / CC0-equivalent** (attribution) | **Tier 1** | **HIGH** |
| **Argentina** | **Secretaría de Energía** (`datos.energia.gob.ar` *Precios en Surtidor*) | Hourly/Daily CSV | Argentine Open Gov Data (Decreto 117/2016) | **Tier 1** | **HIGH** |
| **Colombia** | **MinEnergía / SICOM** via `datos.gov.co` | Monthly OData v2/v4, JSON, CSV | Colombian Open Data | **Tier 1** | **HIGH** |
| **Chile** | **CNE** (`api.cne.cl` / `energiaabierta.cl` *Bencina en Línea*) | Live/Weekly JSON API, CSV/XLS | Chilean Open Data | **Tier 1** | **HIGH** |
| **Malaysia** | **MOF / OpenDOSM** (`api.data.gov.my/data-catalogue?id=fuelprice` & `storage.data.gov.my/commodities/fuelprice.parquet`) | Weekly (Wed) keyless JSON / CSV / Parquet | **CC BY 4.0** (explicit!) | **Tier 1** | **HIGH** |
| **Japan** | **METI / ANRE** (`enecho.meti.go.jp` Weekly Oil Survey *給油所小売価格調査*) | Weekly (Wed) `.xlsx`/`.xls`/CSV (Regular/Hi-Octane/Diesel, all 47 prefectures) | **Government of Japan Standard Terms v2.0** (CC BY-compatible) | **Tier 1/2** (Excel parser) | **HIGH** |
| **South Korea** | **KNOC Opinet API** (`opinet.co.kr` / `data.go.kr`) | Daily JSON/XML (free 1,500 calls/day with key) | Korean Public Data Portal Open License | **Tier 1** (with key) | **HIGH** |
| **Indonesia** | **PT Pertamina** (`pertamina.com`) & **Kementerian ESDM** | Subsidized Pertalite/Biosolar fixed nationwide (Rp 10,000 / Rp 6,800); monthly non-subsidized reviews | Official Public Gov/SOE announcements | **Tier 2/3** (low churn on subsidized Diesel/90) | **HIGH** |
| **Israel** | **Ministry of Energy** (`gov.il/en/departments/units/fuel_prices`) | Monthly regulated 95-octane; **CBS API** (`api.cbs.gov.il`) | Israeli Gov Open Data | **Tier 2** (no dedicated Diesel cap; pair regulated 95 + CBS) | **MEDIUM** |
| **Saudi Arabia, Jordan, UAE, Egypt** | **Aramco** (11th monthly), **Jordan MEMR** (monthly committee), **UAE MOEI** (1st monthly), **Egypt FAPC** (quarterly) | Official monthly/quarterly HTML/press tables in SAR, JOD, AED, EGP | Official Government / SOE public schedules | **Tier 2** (date-scheduled HTML parsers) | **MEDIUM** |
| **South Africa, Kenya, Nigeria** | **DMRE/CEF** (`dmre.gov.za` / `cefgroup.co.za`, 1st Wed monthly), **Kenya EPRA** (`epra.go.ke`, 15th monthly), **Nigeria NBS** (`nigerianstat.gov.ng` PMS/AGO Watch) | Monthly official tables / microdata downloads | Official National Gov portals | **Tier 2** | **MEDIUM** |
| **Syria, Iraq, Lebanon, Libya, Algeria, Tunisia, Morocco, Peru, Taiwan** | State tariffs (`Naftal` DZ, Tunisia Ministry, Lebanon Energy) / **Osinergmin Facilito** PE / **CPC** TW / Curated baselines | Low-churn state fixed (DZ/LY/IQ/SY) or scraper-hardened portals | **IEA Energy Prices** explicitly **REJECTED** (commercial paid subscription) | **Tier 3** (plus optional Tier 2 for `cpc.com.tw`) | **MEDIUM** |

---

### 2.3 Speed Limits, Timezones, Daytime Lights & Axle Mass Limits Sources

| Attribute | Primary Automated / Authoritative Source | License / Mechanism | Pitfalls & Recommendations | Confidence |
|-----------|------------------------------------------|---------------------|----------------------------|------------|
| **Timezones (`time_zone`, `time_zone_name`)** | **Python stdlib `zoneinfo` + PyPI `tzdata` (IANA tzdb)** | **PSF / Public Domain tzdb**; computes both Summer (`2026-07-15`) and Winter (`2026-01-15`) offsets in minutes & zone abbreviations automatically per country/region | **CRITICAL WINDOWS PITFALL (Tested!):** On Windows, Python `ZoneInfo("Europe/Berlin")` **raises `ZoneInfoNotFoundError`** without `tzdata` installed! Pin `tzdata` in `pyproject.toml`. Also map `"CET"` / `"WET"` as plain strings (NOT `@@tz_cet@@`), while keeping `@@tz_cest@@`, `@@tz_eet@@`, `@@tz_eest@@`, `@@tz_west@@`, `@@tz_gmt@@`, `@@tz_bst@@`, `@@tz_msk@@`, `@@tz_trt@@` supported by `locale.scs`. Update Jordan & Syria to permanent `UTC+3` (`AST` / `180`) and Greenland to `America/Nuuk` (`UTC-2` Winter / `UTC-1` Summer). | **HIGH** |
| **Speed Limits (Summer & Winter)** | **Primary:** Verified national road codes curated in versioned repo JSON/CSV, audited against **OSM Wiki `Default speed limits`** (`westnordost/osm-legal-default-speeds` & `stadiamaps/osm-default-speeds` parsers) & **EU CARE/ERSO / national transport ministries** | **CRITICAL LICENSE GATE:** `westnordost` code is BSD-3-Clause, **but the OSM Wiki table data is `CC BY-SA 2.0`**! Redistributing scraped OSM Wiki JSON inside a `CC BY 4.0` mod triggers ShareAlike incompatibility. Use OSM/Wikidata (`P3086`) **only as an automated diff/drift detector**, never copy raw CC BY-SA blobs verbatim into CC BY 4.0 distribution files. | **Real-world seasonal deltas verified:** **Finland** drops 120→100 km/h (cars) & 100→80 km/h (rural cars), heavy trucks stay 80 km/h; **Lithuania** drops motorways 130→110 km/h (Nov–Mar); **Estonia** rolls back 110–120 summer roads to 90 km/h winter; **Sweden** drops seasonal 100/110 corridors to 80/90; **Spain** has NO blanket seasonal truck reduction (fix V1 `truck_motorway 100` anomaly!). Fix ETS2 1.62 **Iceland** heavy-truck limit (`90→80 km/h` per Icelandic Traffic Act). | **HIGH** |
| **EC `Going Abroad` & UNECE** | `transport.ec.europa.eu` Going Abroad + UNECE 1968 Vienna Convention | No bulk API on `Going Abroad` (UI only); UNECE delegates numeric limits to Member States | Useful for manual human audit checks, **not viable as a primary automated scraper**. | **HIGH** |
| **Mandatory Daytime Lights (`lights_mandatory`)** | Curated statutory table verified via **EC Road Safety / SWOV / national road acts** | Statutory factual boolean (`true`/`false`) | Fixes BOTH vanilla 1.62 bugs (`netherlands: true → false`, `switzerland: false → true`) AND `3668352310` over-reach (`albania: true → false`, `turkey: true → false`). | **HIGH** |
| **Axle Mass Limits (`mass_limit_per_axle_count[]`)** | **EU Directive 96/53/EC** (amended `(EU) 2015/719`) + **ITF/OECD *Permissible Maximum Weights of Lorries in Europe*** | Public EU legislation & ITF-OECD reference tables | Preserves ETS2 1.62 `iceland.sui` 5-element `[18000, 29000, 38000, 46000, 60000]` and `sweden` / `finland` Nordic high-capacity limits without regressions. | **HIGH** |

---

## 3. Feature Landscape

### Table Stakes (Parity With Reference Mods + Bug-Free 1.62 Baseline)

| Feature | Why Expected | Complexity | Notes / Targets |
|---------|--------------|------------|-----------------|
| **Dual Seasonal Workshop Editions (Summer & Winter)** | Players run seasonal weather/daylight mods (`Frosty Winter`, `Real Life Day & Night`) and cannot edit `.sui` DST/speed files manually | Low | Auto-generated from ONE unified database + target date/season flag; DST offsets derived via `zoneinfo` + `tzdata` |
| **Live Fuel Prices (`fuel_price` in EUR/L diesel)** | Core expectation matching `3249064596` across all 36 vanilla+DLC + 39 ProMods/Maghreb countries | Med | Weekly updates from Tier 1 APIs + Tier 2/3 fallbacks; sanity bounds (`€0.01–€5.00/L`, max ±25% week-over-week delta alert) |
| **Dynamic Roadside Fuel Totems (`def/sign/board/*.sii` + locale strings)** | Seeing pump signs match dashboard/F7 fuel price is the signature immersion feature of `3249064596` | Med | Zero DDS textures! Override `/locale/fuel_price_strings.sui` + targeted `def/sign/board/*.sii` fixes + `local_module.*.sii` for ProMods across **all 43 ETS2 1.62 locales** (fixing `fr_ca`!) |
| **Multi-Grade Totem Fuel Prices (`95`, `98`, `100`, `Diesel`, `Diesel+`, `LPG`, `E85`, `MPO`)** | Real stations show unleaded + diesel + premium/LPG side by side | Med | Real grades directly from EC Weekly Oil Bulletin (`95`, `Diesel`, `LPG`) + national open APIs (FR/DE/ES/IT/NL/NO/TR) + curated ratios where only Diesel/95 exists |
| **Complete 1.62 Base + `iceland.sui` Compatibility** | ETS2 1.62 added `iceland.sui`, 5-axle Icelandic weights, and `gas_bi_*`/`gas_ie_*` sign boards | Low | Preserves `regions[]`/`region_areas[]` (`bosnia`, `finland`, `norway`, `spain`, `sweden`), `pos`, `mass_limit_per_axle_count[]`, `mp_mod_optional: true` |
| **All Reference Mod Bug Fixes** | Must strictly beat `3249064596` + `3668352310` on correctness | Low | Fix Estonia `name`, Armenia `leftside_traffic`, Libya duplicate ID 120, `fr_ca` sync, San Marino & Svalbard diesel prices, Iceland 80 km/h truck limit, Jordan/Syria `UTC+3` AST, NL/CH/AL/TR `lights_mandatory`, and all 17+ unmapped 1.62 `gas_*` boards |

### Differentiators (High-Value Advantages Over `3249064596` & `3668352310`)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Fully Auditable, Open-Source (CC BY 4.0) 3-Tier Data Pipeline** | Unlike opaque/manual/NC-ND mods, every country's price, FX rate, timestamp, and provenance URL is tracked in CI with zero `CC BY-NC-ND` or `3nK` black boxes | Med | Automated weekly GitHub Actions PRs with anomaly diff report & fallback chain |
| **Automatic ETS2 1.62 Asset Drift Guard** | Automatically compares generated `/def/country/*.sui` and `/def/sign/board/*.sii` against ETS2 `def.scs` / `locale.scs` hashes so future game patches never break `mass_limit`, `regions[]`, or new `gas_*` signs silently | Low | Pure-Python HashFS v1/v2 reader validates 0 orphan keys, 0 missing locales, 0 syntax issues in CI |
| **True Native-Unit Totem Formatting Engine** | Handles pence (`197.0`) vs pounds (`1.97`), eurocents (`252.5`) vs euros (`2.53`), `<sup>9</sup>` tenth-cent boards, Bulgaria post-2026 `EUR`, and 7-segment board character widths automatically | Med | Per-board format ruleset derived from font/width metadata in `def.scs` |
| **Global Regional Readiness Beyond Europe** | Extends cleanly to Brazil (ANP), Argentina, Chile, Colombia, US (EIA), Japan (METI), Malaysia (`data.gov.my`), Korea (Opinet), South Africa (DMRE), GCC/MENA with zero architectural changes | Low | Same country registry schema handles any ISO-3166/map-mod territory (`ProMods`, `EAA`, `JRR`, `C2C`) |
| **Clean Non-Intrusive Defaults** | Avoids unrequested `country_code` breaking rewrites (`UK`/`FIN`/`RUS`) and `_vtd` clutter; keeps vanilla `def/country.sii` / `dlc_*.scs` clean | Low | Modular generation cleanly separates optional overlays if users want `UK` plates |

### Anti-Features (Explicitly Do NOT Build)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|--------------------|
| **DDS Texture Baking for Fuel Totems** | Proved non-viable in prior SPIKE (`Pillow` lacks mipmaps/DXGI sRGB support; 0 in-game effect) and completely unnecessary because SCS already drives signs via localization strings | Edit `def/sign/board/*.sii` placeholder signs + `locale/*.sii`/`sui` strings only |
| **Scraping `GlobalPetrolPrices.com` or `MyLPG.eu`** | **Legal & Reliability Blocker:** `GlobalPetrolPrices.com` enforces **`CC BY-NC-ND 3.0`** (incompatible with open-source CC BY 4.0 & derivative transforms) + manual/anti-automation TOS; `MyLPG.eu` prohibits scraping and offers no API | Use **EC Oil Bulletin + `fuel-prices.eu` (`CC BY 4.0`) + official Tier 1/2 national portals + Tier 3 curated baselines** |
| **Decrypting or Copying `3668352310` `3nK` Files** | Bypassing author obfuscation (`3nK\x01`) is legally/ethically toxic and risks copying stale/incorrect rules (`albania`/`turkey` `lights_mandatory`) | Derive Summer/Winter speed limits & lights cleanly from statutory road codes, verified EU/national law, and OSM audit diffs |
| **Ingesting `westnordost/osm-legal-default-speeds` Directly Into CC BY 4.0 Outputs** | OSM Wiki `Default speed limits` table carries **`CC BY-SA 2.0`** ShareAlike, which legally conflicts with distributing a CC BY 4.0 dataset | Use `osm-legal-default-speeds` strictly as an **internal automated CI audit/drift signal** against curated statutory road-code rules |
| **Shipping Live FX or Fuel Fetching Inside an In-Game Plugin/DLL** | Violates pure-`.scs` `mp_mod_optional: true` Convoy safety, breaks Linux/macOS/Steam Deck compatibility, and fails offline | Run all fetching offline in Python CI/build pipeline; output static versioned `.scs` packages |
| **Bundling Legacy Deleted Locales (`fr_qc`) or Stale `3nK`/Encryption** | Adds dead weight and breaks parity with ETS2 1.62's **43** active locales; causes silent mismatches (like `3249064596`'s broken `fr_ca`) | Generate all 43 ETS2 1.62 locales from a single canonical generator step |

---

## 4. Feature Dependencies & Recommended Phasing

```text
HashFS v1/v2 Reader & ETS2 1.62 Baseline Extractor (def.scs + locale.scs)
   ├──▶ Country Registry + Static/Statutory Rules (Speed Limits, Lights, Axles, ZoneInfo+tzdata)
   ├──▶ Tier 1/2/3 Fuel Collectors + Frankfurter/ECB FX Converter + Sanity/Circuit Breakers
   │       └──▶ Unified Canonical Country Snapshot (JSON/CSV with Provenance & Confidence)
   │               ├──▶ Summer & Winter .sui + speed_limits.sii Generator (36 Base + 39 Map-Mod)
   │               └──▶ Totem Localization + 18-86 Placeholder def/sign/board/*.sii Generator (43 Locales)
   └──▶ Automated Cross-Check Validator (vs 1.62 def.scs/locale.scs, syntax, key coverage, price bounds)
           └──▶ Dual Summer / Winter .scs Packager (Workshop-ready ZIP/HashFS)
```

### MVP -> Full Scope Recommendation
1. **MVP Core (Phase 1–2):** Baseline extractor against ETS2 1.62 (`def.scs`/`locale.scs`) + `zoneinfo`/`tzdata` DST derivation + bug-fixed static/seasonal `speed_limits.sii`, `lights_mandatory`, and `mass_limit_per_axle_count[]` for the **36 base+DLC countries**, packaged into validated **Summer** and **Winter** `.scs` editions.
2. **Tier 1 Automated Fuel + Totems (Phase 3–4):** Wire **EC Weekly Oil Bulletin** (+ `FionnHughes` & `fuel-prices.eu` `CC BY 4.0` fallbacks), **UK DESNZ**, **Norway SSB**, **Frankfurter v2 + ECB** FX, and national multi-grade APIs (`FR`/`DE`/`ES`/`IT`/`NL`) to drive all 36 base countries + full **43-locale** fuel totems (including fixing all 17 unmapped 1.62 `gas_bi_*`/`gas_ie_*`/`gas_ba_*`/`gas_dk_92` boards and `gas_is_ip1_98`).
3. **Global Tier 2/3 & Map-Mod Expansion (Phase 5):** Add the **39 ProMods/Maghreb countries**, **Tier 2** national parsers (`MD` ANRE, `MK` ERC, `RU` Rosstat+CBR, `JP` METI, `BR` ANP, `MY` `data.gov.my`, `CO`/`AR`/`CL`/`US`/`KR`/`ZA`/`IL`/GCC), and **Tier 3** curated community baselines with staleness alerts and placeholder-board completion (`00.00`/`123.9`/`*_lpg`).

---

## Sources

- **Direct Game & Reference Archive Inspections (on-disk HashFS v1/v2):**
  - ETS2 1.62 `def.scs`, `locale.scs` (`locale/fuel_price_strings.sui`, `locale/common.sui`, `locale/en_gb/localization.sui`), `dlc_*.scs`
  - Steam Workshop `3249064596\universal.scs` (*Real life fuel prices* by `kworey`)
  - Steam Workshop `3668352310\universal.scs` (*Updated WINTER speed limits* by `neuhr`, incl. `versions.sii`, `pre144info.scs`)
- **Fuel, Energy & FX Official APIs & Datasets:**
  - EC Weekly Oil Bulletin (`https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en`, CC BY 4.0) & mirrors (`FionnHughes/eu-weekly-oil-bulletin`, `the-Hull/weekly_oil_bulletin`)
  - `fuel-prices.eu/api/docs` (CC BY 4.0), `developers.fuelo.net`, `globalpetrolprices.com/terms_conditions.php` (`CC BY-NC-ND 3.0`), `mylpg.eu`
  - Frankfurter v2 (`https://frankfurter.dev`, MIT), ECB `eurofxref-daily.xml`, `fawazahmed0/exchange-api` (CC0 1.0), CBR `cbr.ru/scripts/XML_daily.asp`
  - UK DESNZ (`gov.uk/.../weekly-road-fuel-prices`, OGL v3) & UK Fuel Finder, Norway SSB Table `09654` (`data.ssb.no/api/pxwebapi/v2`), Switzerland BFS/LIK (`data.bfs.admin.ch` / `opendata.swiss`), Germany Tankerkönig (`CC BY 4.0`), France `prix-carburants.gouv.fr` (*Licence Ouverte*), Spain MITECO, Italy MIMIT (*IODL 2.0*), Netherlands CBS StatLine OData
  - Moldova ANRE (`anre.md`), North Macedonia ERC (`erc.org.mk`), Russia Rosstat (`rosstat.gov.ru`), Israel Ministry of Energy (`gov.il`), Jordan MEMR, Saudi Aramco, UAE MOEI, Egypt FAPC, South Africa DMRE/CEF (`dmre.gov.za`), Kenya EPRA (`epra.go.ke`), Nigeria NBS (`nigerianstat.gov.ng`)
  - Brazil ANP (`dados.gov.br`), Argentina `datos.energia.gob.ar`, Chile CNE (`cne.cl`), Colombia `datos.gov.co`, Peru Osinergmin (`Facilito`), US EIA API v2 (Public Domain), Japan METI/ANRE (`enecho.meti.go.jp`), Malaysia OpenDOSM (`api.data.gov.my`, CC BY 4.0), South Korea Opinet (`opinet.co.kr` / `data.go.kr`), Indonesia Pertamina / ESDM, IEA (`iea.org`, subscription)
- **Speed Limits, Timezones, Lights, Eurozone & Axle Weights:**
  - `westnordost/osm-legal-default-speeds` & OSM Wiki `Default speed limits` (`CC BY-SA 2.0`), Wikidata `P3086`, EC Going Abroad (`transport.ec.europa.eu`), UNECE 1968 Vienna Convention
  - EU Directive `96/53/EC` & ITF/OECD *Permissible Maximum Weights of Lorries in Europe* (`itf-oecd.org`)
  - Bulgaria Eurozone adoption (2026-01-01, `1 EUR = 1.95583 BGN`), Jordan/Syria permanent UTC+3 (Oct 2022), Greenland `America/Nuuk` UTC-2/UTC-1, Python `zoneinfo` + `tzdata` verification on Windows.
