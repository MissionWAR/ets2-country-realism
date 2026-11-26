# Requirements: ETS2 World Country Realism Generator (V2)

**Defined:** 2026-11-16
**Core Value:** Open-source (`MIT` / `CC BY 4.0`), automated seasonal country realism (`Summer` & `Winter`) for Euro Truck Simulator 2 `1.62+` covering Vanilla+DLC, ProMods (`EU + ME + MA + TGS`), and arbitrary multi-map combos via local `compose-local` patching—with zero ProMods assets in the public repo and zero DDS texture baking.

## V1 Requirements

Requirements for the V1 release (Phases 1–5), targeting Phase A Semi-Auto Steam Workshop publishing.

### Virtual Filesystem & Structural SII Engine

- [x] **VFS-01**: Read HashFS v1/v2 archives, standard `.scs`/`.zip` packages, and unpacked mod directories across Windows and Linux paths cleanly, while safely detecting and reporting `3nK`-obfuscated or `AEM!`/encrypted ZIP archives without attempting to crack them.
- [x] **VFS-02**: Extract ETS2 `1.62.3.3s` baseline metadata from `def.scs` and `locale.scs` (36 Vanilla+DLC country definitions, `speed_limits.sii`, `sign/board/*.sii`, and all 43 active locales) into deterministic schemas/fixtures under `data/baselines/ets2_1.62_def/`.
- [x] **SII-01**: Parse and surgically edit ETS2 `.sii`/`.sui` country files and `speed_limits.sii` while preserving comments, formatting, `regions[]`, `secondary_time_zone_area[]`, `secondary_time_zone[]`, `train`, `tram`, and unrelated attributes untouched.
- [x] **SII-02**: Enforce strict SCS SII serialization hygiene on every generated file: UTF-8 without BOM, LF (`\n`) line endings, POSIX `/` internal paths, valid unit scoping, and idempotent round-trip output.

### Realism Registry, Seasonal Builds & Offline Validator (Phase A)

- [x] **SIM-01**: Maintain a canonical ISO country/territory realism registry (`data/laws/`, `data/mappings/`) supporting `Summer` and `Winter` speed-limit and DRL policies while fixing all known bugs from reference mods (`3249064596`, `3668352310`).
- [x] **SIM-02**: Compute accurate seasonal UTC offsets and abbreviations dynamically from stdlib `zoneinfo` + `tzdata`, emitting valid ETS2 integer minutes and plain strings (e.g., `"CET"`, `"WET"`) while respecting ETS2's 12 supported `@@tz_*@@` keys.
- [x] **SIM-03**: Package dual **Vanilla+DLC Core** mods (`Summer` and `Winter`) covering all 36 SCS countries with complete Workshop metadata (`manifest.sii`, description, `276x162` `.jpg` mod icon) built purely from open-source repository assets.
- [x] **PUB-01**: Run an Offline SCS Workshop Validator covering SCS validation error checks `00001`–`00010` and warnings `WARN 00001`/`00002` (encoding, icon dimensions/JPEG format, manifest integrity, unit/board references) before releasing any artifact.
- [x] **PUB-02**: Gate releases via a canonical SHA-256 hash ledger (`state/published.json`) comparing normalized package content against previously published state to prevent empty/no-op uploads and emit clean diffs.
- [x] **PUB-03**: Provide a Phase A Semi-Auto GitHub Actions CI & release workflow (scheduled Fridays aligned with the EC Weekly Oil Bulletin release plus manual dispatch) outputting validated `Summer` and `Winter` bundles, markdown changelogs, and `realism-snapshot-{summer|winter}.json` without storing Steam secrets.

### Open European Fuel/FX Pipeline & Zero-DDS Totem Engine

- [x] **DAT-01**: Fetch and cross-validate FX exchange rates using `Frankfurter v2` (`MIT`, 219 currencies), `ECB` validator, `fawazahmed0` currency API (`CC0`), and `CBR` FX with deterministic country-currency mapping and currency-split sanity checks.
- [x] **DAT-02**: Collect Tier 1 open European & EEA government fuel data from `EC Weekly Oil Bulletin` (dynamic XLSX discovery + `FionnHughes`/`fuel-prices.eu` fallback), `UK DESNZ`, `NO SSB`, and multi-grade national APIs (`FR`, `DE`, `ES`, `IT`, `NL`).
- [x] **DAT-03**: Enforce circuit-breaker safety (`0.01–5.00 EUR/L` equivalent bounds and `±25%` change alerts) backed by `prices.lock.json` so stale or broken upstream endpoints safely fall back to last-known-good attributed values.
- [x] **TOT-01**: Implement Option 4b Zero-DDS gas-station totem updates using namespaced `@@fp_*_ets2v2@@` tokens in `def/sign/board/*.sii` and `locale/<lang>/local_module.ets2v2_fuel.sii` across all 43 active ETS2 `1.62` locales.
- [x] **TOT-02**: Render authentic multi-grade (`95`, `98`, `100`, `Diesel`, `Diesel+`, `E85`, `LPG`) prices in national currencies and sub-units (pence, eurocents, `<sup>9</sup>`, Bulgaria EUR transition) while fixing all 17 active and 69 placeholder/blank missing `1.62` sign boards (including `gas_bi_*`, `gas_ie_*`, `gas_ba_*_lpg`, `gas_dk_92`, `gas_is_ip1_98`).

### ProMods Companion & Local Map Combo Composer

- [x] **MAP-01**: Provide a local **ProMods Companion Builder** producing `Summer (ProMods Edition)` and `Winter (ProMods Edition)` from the maintainer's installed ProMods `def` packages (`promods-eu-def-v284.scs`, `promods-me-defmap-v284.scs`, `promods-ma-defmap-v104.scs`, `promods-tgs-defmap-v170.scs`), including `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` totems, without ever storing ProMods files in the public GitHub repository.
- [x] **MAP-02**: Define and export versioned `realism-snapshot-{summer|winter}.json` artifacts decoupling online price/law ingestion from offline local patch generation.
- [x] **MAP-03**: Implement `ets2v2 compose-local` to scan the user's local `mod/` folder and active load order (*RusMap*, *TST*, *UMCF*, *Beyond*, *JRR*, *SEA*, *RoC*, *Project Japan Relocated*, *EAA Rescaled*, Africa mods) across `.sui`, `.sii` fragments, `base/` paths, and empty `SiiNunit {}` stubs to generate `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs`.
- [x] **MAP-04**: Apply `FieldOwnershipPolicy` merge guardrails in `compose-local`: `max_of_map_and_real` axle weights (preserving EAA 80t, Iceland 60t, RusMap/TST 48t, FI 105t) and `patch_if_single_tz` timezone patching (preserving TST 27-TZ Russia, UMCF Kazakhstan `ALMT`/`AQTT`, EAA Brazil).
- [x] **MAP-05**: Detect `AEM!`/encrypted ZIP archives (`12` identified locally) with clear user diagnostics and `--unpacked-defs` override support, plus opt-in `--patch-hardcoded-totems` support for JRR/7RM numeric gas signs.

### Global Tier 1/2/3 Data Expansion & Internal OSM Audit

- [x] **GLB-01**: Integrate Tier 1 non-European government fuel APIs (`US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`) into the snapshot pipeline.
- [x] **GLB-02**: Integrate Tier 2 guarded national portal scrapers with isolated per-country circuit breakers and `prices.lock.json` fallback so individual portal breakages never fail CI or corrupt snapshots.
- [x] **GLB-03**: Curate Tier 3 global baseline entries bringing total snapshot territory coverage to `200+` countries/regions (Africa, Latin America, Central/East/Southeast Asia) for `compose-local` map combos.
- [x] **GLB-04**: Add an internal CI OSM Overpass/Taginfo (`CC BY-SA`) speed-limit drift audit comparing real-world road limits against `data/laws/` and surfacing maintainer review reports without bundling any `CC BY-SA` data into `CC BY 4.0` mod outputs.

## V2 Requirements (Deferred)

Deferred to a future post-V1 milestone once Phase A Semi-Auto publishing is battle-tested.

- **PUB-V2-01**: GitHub Actions full-auto `steamcmd` Steam Workshop publishing using inline post-self-update 30s TOTP (`STEAM_SHARED_SECRET`) without `config.vdf` credential rot.
- **PUB-V2-02**: Hidden-item (`visibility: 2`) Workshop verification spike validating multi-item matrix updates without partial upload corruption or missing-delete sync bugs.

## Out of Scope

Explicit boundaries preserving open-source licensing (`MIT` / `CC BY 4.0`) and maintenance sanity:

| Exclusion | Reason |
|-----------|--------|
| DDS gas-station price texture baking | Option 4b locale tokens + `def/sign/board/*.sii` cover all 43 locales cleanly with zero binary texture churn |
| `GlobalPetrolPrices.com` scraping | `CC BY-NC-ND 3.0` non-commercial / no-derivatives license conflicts with `CC BY 4.0` mod packs |
| `MyLPG.eu` scraping or paid `IEA` feeds | Anti-open/paid Terms of Service incompatible with an open-source automated CI pipeline |
| Cracking or copying `3nK` blobs from `3668352310` | Clean-room authoring from official SCS `1.62` baselines avoids obfuscated third-party assets |
| Storing proprietary ProMods `.scs` or extracted `def/` files in Git | Violates ProMods no-reupload EULA; ProMods Editions are built locally from the maintainer's own `mod/` folder |
| Uploading unvalidated `.scs` mods or bypassing SCS validation rules | Must satisfy SCS Validator codes `00001`–`00010` and `WARN 00001`/`00002` cleanly |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VFS-01 | Phase 1 | Complete |
| VFS-02 | Phase 1 | Complete |
| SII-01 | Phase 1 | Complete |
| SII-02 | Phase 1 | Complete |
| SIM-01 | Phase 2 | Complete |
| SIM-02 | Phase 2 | Complete |
| SIM-03 | Phase 2 | Complete |
| PUB-01 | Phase 2 | Complete |
| PUB-02 | Phase 2 | Complete |
| PUB-03 | Phase 2 | Complete |
| DAT-01 | Phase 3 | Complete |
| DAT-02 | Phase 3 | Complete |
| DAT-03 | Phase 3 | Complete |
| TOT-01 | Phase 3 | Complete |
| TOT-02 | Phase 3 | Complete |
| MAP-01 | Phase 4 | Complete |
| MAP-02 | Phase 4 | Complete |
| MAP-03 | Phase 4 | Complete |
| MAP-04 | Phase 4 | Complete |
| MAP-05 | Phase 4 | Complete |
| GLB-01 | Phase 5 | Complete |
| GLB-02 | Phase 5 | Complete |
| GLB-03 | Phase 5 | Complete |
| GLB-04 | Phase 5 | Complete |

**Coverage:**
- V1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0 ✓

---
*Requirements defined: 2026-11-16*
*Last updated: 2026-11-26 after Phase 5 verification & code review (`GLB-01`..`GLB-04` verified; all 24/24 V1 requirements complete)*
