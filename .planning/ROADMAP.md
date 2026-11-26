# Roadmap: ETS2 World Country Realism Generator (V2)

## Overview

ETS2 World Country Realism Generator (V2) (`ETS2V2`) is an open-source (`MIT` / `CC BY 4.0`), clean-room Python `3.12+` (`uv`) pipeline and mod compiler for **Euro Truck Simulator 2 `1.62.3.3s`+**. Across five cohesive V1 phases, the project builds a pure-Python HashFS/SII foundation, validates seasonal Vanilla+DLC Core Workshop editions (`Summer` & `Winter`) under Phase A semi-auto CI, wires legally clean European fuel/FX feeds into a 43-locale Zero-DDS totem system, extends realism safely to ProMods (`EU + ME + MA + TGS`) and arbitrary user map combos via `ets2v2 compose-local`, and scales to `200+` global territories with an isolated OSM drift audit. Full-auto SteamCMD Workshop publishing (`PUB-V2-01`, `PUB-V2-02`) is explicitly deferred to a future V2 milestone.

## Phases

**Phase Numbering:**
- Integer phases (`1`, `2`, `3`, `4`, `5`): Planned V1 milestone work
- Decimal phases (`2.1`, `2.2`): Urgent insertions (created via `/gsd-phase --insert`)

- [x] **Phase 1: VFS, 1.62 Baseline Extraction & Structural SII Engine** - Clean-room HashFS v1/v2 + ZIP + unpacked VFS reader, `1.62.3.3s` baseline extraction, and comment/region-preserving surgical SII/SUI engine. (completed 2026-11-16)
- [x] **Phase 2: Realism Registry, Seasonal Core Builds & Offline Validator (Phase A)** - Canonical seasonal country laws, `zoneinfo`+`tzdata` DST derivation, dual 36-country Vanilla+DLC Core builds, Offline SCS Validator, SHA-256 diff gate, and Friday CI release pipeline. (completed 2026-11-20)
- [x] **Phase 3: Open European Fuel/FX Pipeline & Zero-DDS Totem Engine** - Multi-provider FX cross-validation, Tier 1 EU/EEA fuel APIs with `prices.lock.json` circuit breakers, and Option 4b Zero-DDS 43-locale fuel totems covering all active and placeholder `1.62` signs. (completed 2026-11-22)
- [x] **Phase 4: ProMods Companion Builder & Local Map Combo Composer** - Versioned `realism-snapshot-{summer|winter}.json` contract, local ProMods `EU+ME+MA+TGS` builder, and `ets2v2 compose-local` with `FieldOwnershipPolicy` map-combo protection. (completed 2026-11-25)
- [x] **Phase 5: Global Tier 1/2/3 Coverage & Internal OSM Audit** - Non-EU Tier 1 government APIs, Tier 2 guarded portals with isolated circuit breakers, Tier 3 curated baselines (`200+` territories), and CI-only OSM (`CC BY-SA`) speed-limit drift reporting. (completed 2026-11-26)

## Phase Details

### Phase 1: VFS, 1.62 Baseline Extraction & Structural SII Engine
**Goal**: Developers and build pipelines can cleanly inspect ETS2 `1.62.3.3s` and mod archives cross-platform, extract canonical baseline metadata, and surgically edit country and speed-limit SII/SUI files without corrupting comments, regions, or unrelated engine blocks.
**Depends on**: Nothing (first phase)
**Requirements**: VFS-01, VFS-02, SII-01, SII-02
**Research**: Covered by `.planning/research/` (`STACK.md`, `ARCHITECTURE.md`, `SUMMARY.md`) — HashFS v1/v2 binary structures, `3nK` magic-byte detection, `1.62.3.3s` archive manifests (`def.scs` / `locale.scs`), and SII/SUI unit conventions are verified on disk; `gsd-phase-researcher` not required (standard implementation from verified specs).
**Success Criteria** (what must be TRUE):
  1. Reading a directory of HashFS v1, HashFS v2, standard `.zip`/`.scs`, and unpacked mod trees resolves VFS paths identically on Windows and Linux while cleanly reporting `3nK`, `AEM!`, or encrypted ZIP archives without attempting decryption or crashing.
  2. Extracting ETS2 `1.62.3.3s` `def.scs` and `locale.scs` produces deterministic, version-controlled baseline schemas and fixtures under `data/baselines/ets2_1.62_def/` covering all 36 country definitions, 36 `speed_limits.sii` files, `def/sign/board/*.sii` fuel boards, and all 43 active locales.
  3. Surgically updating `fuel_price`, `time_zone`, `time_zone_name`, `lights_mandatory`, `mass_limit_per_axle_count[]`, and `car`/`truck`/`bus` speed limits preserves comments (`#`, `//`, `/* */`), `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`, and `tram` blocks verbatim.
  4. Every serialized `.sii`/`.sui` output passes strict SCS hygiene assertions (UTF-8 without BOM, `\n` LF endings, POSIX `/` internal paths, column-0 `@include`, valid unit scoping) and produces zero byte diff on idempotent round-trip writes.
**Plans**: 4 plans
Plans:
- [x] `01-01-PLAN.md` — Project package scaffold (`pyproject.toml`, `uv.lock`, `src/ets2v2/` structure, `ruff` + `basedpyright` + `pytest` gates, Day-1 CI)
- [x] `01-02-PLAN.md` — Clean-room HashFS v1/v2 (`CityHash64` MIT + `zlib`), ZIP, and unpacked VFS reader/overlay with safe `3nK`/`AEM!`/encrypted-ZIP detection (`VFS-01`)
- [x] `01-03-PLAN.md` — ETS2 `1.62.3.3s` `def.scs` & `locale.scs` baseline extractor generating deterministic `data/baselines/ets2_1.62_def/` schemas and CLI wiring (`VFS-02`)
- [x] `01-04-PLAN.md` — Structural SII/SUI & `speed_limits.sii` parser, surgical field rewriter, and UTF-8/LF/POSIX round-trip verification suite (`SII-01`, `SII-02`)

### Phase 2: Realism Registry, Seasonal Core Builds & Offline Validator (Phase A)
**Goal**: Players and maintainers obtain verified, Workshop-compliant Summer and Winter Vanilla+DLC Core mods (`36` countries) compiled from one canonical source of truth, backed by an Offline SCS Validator and automated Friday Phase A release artifacts.
**Depends on**: Phase 1
**Requirements**: SIM-01, SIM-02, SIM-03, PUB-01, PUB-02, PUB-03
**Research**: Covered by `.planning/research/` (`FEATURES.md`, `PITFALLS.md`, `SUMMARY.md`) — all 36 country deltas vs `3249064596`/`3668352310`, the 12 supported `@@tz_*@@` localization keys, SCS error codes `00001`–`00010` + `WARN 00001`/`00002`, and Phase A GitHub Actions structure are verified; `gsd-phase-researcher` optional for minor national speed/DRL statute double-checks during planning.
**Success Criteria** (what must be TRUE):
  1. Compiling `Summer` and `Winter` editions from `data/laws/` and `data/mappings/` resolves all known reference-mod regressions (Estonia `name: "Eesti"`, Armenia `leftside_traffic: false`, Iceland 5-axle 60t + 80 km/h heavy truck, Jordan/Syria permanent `UTC+3` `AST`, NL/CH/AL/TR `lights_mandatory`, and vanilla `regions[]` preservation).
  2. Seasonal timezone calculation via stdlib `zoneinfo` + `tzdata` emits accurate Summer/Winter integer minute offsets and emits `@@tz_*@@` tokens strictly for the 12 keys present in `1.62` `locale.scs` while emitting plain `"CET"`, `"WET"`, `"AST"` strings elsewhere.
  3. Dual Vanilla+DLC Core builds (`dist/workshop/summer/` and `dist/workshop/winter/`) pass the Offline SCS Validator with zero `00001`–`00010` errors and zero `WARN 00001`/`00002` warnings (valid `versions.sii`, `manifest.sii` with `mp_mod_optional: true`, `276x162` `.jpg` icon, no `display_name`/`compatible_versions[]`, no ZIP-as-`.scs`).
  4. Running a build with unchanged canonical content triggers the `state/published.json` SHA-256 no-op gate without bumping or emitting redundant updates, while material changes output Summer/Winter release bundles and markdown changelogs on Friday `06:00 UTC` CI without storing Steam secrets.
**Plans**: 5 plans
Plans:
- [x] `02-01-PLAN.md` — Runtime deps (`tzdata`, `pillow`), active-phase scaffold update, canonical 36-country realism registry (`data/laws/countries/<iso2>.json`, `data/mappings/ets2_countries.json`), Pydantic v2 models & loader (`SIM-01`)
- [x] `02-02-PLAN.md` — Dynamic `zoneinfo` + `tzdata` seasonal DST offset & `@@tz_*@@`/plain-abbreviation resolver (with numeric `tzname()` overrides + `Asia/Amman`/`Asia/Damascus` tests), `one-way` D-11 schema lock checkpoint, and `realism-snapshot` v1 contract (`SIM-02`)
- [x] `02-03-PLAN.md` — Clean-room `.sui`/`speed_limits.sii` synthesis, checked-in `276x162` `.jpg` icons (`assets/icons/{summer,winter}.jpg`), and dual 36-country Vanilla+DLC Core packager (`dist/workshop/{summer,winter}/` & `dist/local/*.zip`) (`SIM-03`)
- [x] `02-04-PLAN.md` — Offline SCS Workshop Validator enforcing `00001`–`00010`, `WARN 00001`/`00002`, unit token limits, raw ZIP hygiene, and `1.62` realism invariants (`PUB-01`)
- [x] `02-05-PLAN.md` — Canonical SHA-256 diff ledger (`state/published.json`), Markdown changelog generator, `realism-snapshot` release emission, and Phase A Friday `06:00 UTC` persistent-PR GitHub Actions workflow (`PUB-02`, `PUB-03`)

### Phase 3: Open European Fuel/FX Pipeline & Zero-DDS Totem Engine
**Goal**: Core Summer and Winter editions automatically reflect live weekly European/EEA diesel and multi-grade pump prices converted cleanly between EUR/L (`fuel_price`) and authentic local-currency roadside totems across all 43 ETS2 `1.62` locales with zero DDS texture baking.
**Depends on**: Phase 2
**Requirements**: DAT-01, DAT-02, DAT-03, TOT-01, TOT-02
**Research**: **`gsd-phase-researcher` recommended** — verify live schema/auth behavior for national multi-grade APIs (`FR` `prix-carburants.gouv.fr`, `DE` Tankerkönig key flow, `ES` MITECO, `IT` MIMIT CSV, `NL` CBS OData), EC Weekly Oil Bulletin dynamic link discovery, and character-width/font glyph rules (`<sup>9</sup>`, integer vs decimal) across the 17 active + 69 placeholder/blank `1.62` `def/sign/board/*.sii` templates.
**Success Criteria** (what must be TRUE):
  1. Multi-source FX collection (`Frankfurter v2`, `ECB`, `fawazahmed0`, `CBR`) converts national currencies into validated `eur_per_liter` values alongside separate `local_display_price` values, respecting Bulgaria's `EUR` adoption and failing loudly on currency-split mismatches.
  2. Tier 1 collectors ingest live weekly/daily EU27 + EEA + UK fuel prices (`EC Weekly Oil Bulletin` dynamic XLSX + `FionnHughes`/`fuel-prices.eu` fallback, `UK DESNZ`, `NO SSB`, and `FR`/`DE`/`ES`/`IT`/`NL` multi-grade feeds) while falling back safely to `prices.lock.json` on upstream outages and enforcing `0.01–5.00 EUR/L` bounds plus `±25%` change alerts.
  3. All 43 active ETS2 `1.62` locales (with dead `fr_qc` excluded and `fr_ca` fully synchronized) receive consistent `locale/<lang>/local_module.ets2v2_fuel.sii` modules backing namespaced `@@fp_*_ets2v2@@` `def/sign/board/*.sii` rewrites with zero `.dds`/`.tobj` files generated.
  4. Roadside totems display authentic multi-grade (`95`, `98`, `100`, `Diesel`, `Diesel+`, `E85`, `LPG`) native-currency formats (UK pence vs GBP, NL eurocents vs EUR, `<sup>9</sup>` tenth-cents, Bulgaria `EUR`) and populate all 17 active unmapped `1.62` signs (`gas_bi_*`, `gas_ie_*`, `gas_ba_*_lpg`, `gas_dk_92`), `gas_is_ip1_98`, and the 69 placeholder/blank boards without Offline SCS Validator errors.
**Plans**: 4 plans
Plans:
- [x] `03-01-PLAN.md` — Phase 3 runtime deps (`httpx`, `openpyxl`, `types-openpyxl`), 4 AST offline DAG isolation walls, pure `ets2v2.normalize` 39-territory FX cross-validator & `PricesLockfile` v1, and hardened `ets2v2.fetch` FX providers (`Frankfurter v2`, `ECB`, `fawazahmed0`, `CBR`) (`DAT-01`)
- [x] `03-02-PLAN.md` — Tier 1 EU/EEA fuel collectors (`EC Weekly Oil Bulletin` dynamic XLSX + `FionnHughes`/`fuel-prices.eu`, `UK DESNZ`, `NO SSB 09654`, `FR`/`DE`/`ES`/`IT`/`NL`), `0.01–5.00 EUR/L` & `±25%` WoW circuit breakers, committed 39-territory `state/prices.lock.json`, and locked `RealismSnapshot` v1 price injection (`DAT-02`, `DAT-03`)
- [x] `03-03-PLAN.md` — Extended 24-attribute `1.62` sign board parser & refreshed `fuel_boards.json`, deterministic 460-board classifier (`37` countries, fixing all `17` active unmapped + `47` placeholder + `40` blank boards, `gas_is_ip1_98`, `gas_is_yokull` swap), and Option 4b Zero-DDS 43-locale totem compiler wired into Summer/Winter Core builds (`TOT-01`)
- [x] `03-04-PLAN.md` — 6-font SDF native-currency formatter (`<sup>9</sup>`, `_3_ets2v2`, `_c_ets2v2`, UK pence, BG `EUR`, integer currencies), hard Offline SCS Validator `D-12` invariants (`ETS2V2-INV-ZERO-DDS`, `ETS2V2-INV-LOCALE-SYNC`, `ETS2V2-INV-TOTEM-BOARDS`), `D-16` fuel tables/alerts/attributions, and Friday CI `fetch` + Release PR wiring (`TOT-02`)

### Phase 4: ProMods Companion Builder & Local Map Combo Composer
**Goal**: ProMods players receive locally built Summer and Winter ProMods Editions (`EU + ME + MA + TGS`), and multi-map combo users can run `ets2v2 compose-local` offline against CI snapshots to generate a conflict-free `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` preserving every map's geometry, regions, axles, and multi-timezone zones.
**Depends on**: Phase 3
**Requirements**: MAP-01, MAP-02, MAP-03, MAP-04, MAP-05
**Research**: **`gsd-phase-researcher` recommended** — verify exact local ProMods package contents (`promods-eu-def-v284.scs`, `promods-me-defmap-v284.scs`, `promods-ma-defmap-v104.scs`, `promods-tgs-defmap-v170.scs`) country IDs and `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` schemas on disk, active load-order extraction strategy (`profile.sii` / `game.log.txt` / explicit list), and JRR/7RM numeric totem board signatures for `--patch-hardcoded-totems`.
**Success Criteria** (what must be TRUE):
  1. Running the local ProMods Companion Builder against installed `EU + ME + MA + TGS` ProMods archives produces validated `Summer (ProMods Edition)` and `Winter (ProMods Edition)` packages (including `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` totems and preserved UK `scotland`/`wales` regions) while keeping zero ProMods files tracked in the Git repository.
  2. CI exports versioned `realism-snapshot-{summer|winter}.json` artifacts consumed offline by both the ProMods Companion Builder and `ets2v2 compose-local` with zero network access required at compose time.
  3. Running `ets2v2 compose-local` against a local `mod/` load order resolves `.sui` and `.sii` fragments (`SEA`, `RoC`, `Project Japan`), `base/` mount prefixes (`EAA`), empty `SiiNunit { }` suppression stubs (`UMCF`, `gmc.beyond.fix`, `SemEuropa`), and sub-national country aliases into a single `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs`.
  4. `FieldOwnershipPolicy` preserves higher map axle limits (`max_of_map_and_real`: EAA `80t`, Iceland `60t`, RusMap/TST `48t`, Finland `105t`), skips timezone overrides on multi-TZ definitions (`patch_if_single_tz`: TST `27`-TZ Russia, UMCF `5`-TZ Kazakhstan, EAA Brazil), emits clear diagnostics + `--unpacked-defs` fallback on `AEM!`/encrypted ZIPs, and leaves hardcoded numeric totems (`JRR`/`7RM`) untouched unless `--patch-hardcoded-totems` is passed.
**Plans**: 4 plans
Plans:
- [x] `04-01-PLAN.md` — Unlock `merge/` with 6 AST DAG walls, 76-territory ProMods `EU+ME+MA+TGS v1.71` law registry + `country_aliases.json` + 76-territory `prices.lock.json` & FX isolation, frozen `RealismSnapshot` v1 + `SHA256SUMS.txt` + `ets2v2 registry snapshot-verify`, and rolling `snapshots-latest` GitHub Release (`MAP-02`)
- [x] `04-02-PLAN.md` — Local ProMods Companion Builder (`EU+ME+MA+TGS` `def`/`defmap` + `assets` discovery, dynamic 43-locale `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` `_v0`–`_v4` updater, clean-room ProMods icons, profile-parameterized Offline SCS Validator, `ets2v2 package promods`, zero Git ProMods assets) (`MAP-01`)
- [x] `04-03-PLAN.md` — `ets2v2 compose-local` multi-source load-order resolver (`--game-log`, plaintext `--profile` + `ScsC` guard + Workshop `227300`, `--modlist`, D-10 self-exclusion, smart `--unpacked-defs`), `VfsStack` combo country scanner (headerless `.sui`/`.sii`, `base/`, empty `SiiNunit {}` stubs, protected diagnostics), and 3-tier `country_aliases.json` resolver (`MAP-03`)
- [x] `04-04-PLAN.md` — `FieldOwnershipPolicy` merge guardrails (`max_of_map_and_real` axles, `patch_if_single_tz`, custom-lane preservation, `imperial_units` parity guard), opt-in `--patch-hardcoded-totems` (JRR/7RM), pre-write validated `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` emitter, and `ets2v2 compose-local` CLI (`MAP-04`, `MAP-05`)

### Phase 5: Global Tier 1/2/3 Coverage & Internal OSM Audit
**Goal**: Global map-combo snapshots cover `200+` countries and territories cleanly via Tier 1 non-EU open APIs, fault-isolated Tier 2 national portals, and Tier 3 curated baselines, while an internal CI audit surfaces statutory speed-limit drift against OSM without polluting `CC BY 4.0` outputs.
**Depends on**: Phase 4
**Requirements**: GLB-01, GLB-02, GLB-03, GLB-04
**Research**: **`gsd-phase-researcher` recommended** — verify live API request/auth contracts for non-EU Tier 1 portals (`US EIA v2`, `KR Opinet`, `JP METI` Excel tables, `BR ANP` Latin-1 CSV, `MY OpenDOSM` Parquet/JSON), Tier 2 portal HTML selectors/charsets (`anre.md`, `erc.org.mk`, `rosstat`, `dmre`, `epra`), and `westnordost/osm-legal-default-speeds` / Overpass audit diff pipeline.
**Success Criteria** (what must be TRUE):
  1. Tier 1 non-EU collectors (`US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`) fetch, currency-convert, and record live regional prices into `realism-snapshot-{summer|winter}.json` with source provenance metadata.
  2. Tier 2 guarded portal parsers apply per-country isolated circuit breakers so HTTP `403`/`429`, encoding errors, or HTML selector drift retain `prices.lock.json` last-known-good rates with staleness alerts rather than failing CI builds or corrupting snapshots.
  3. Combined Tier 1, Tier 2, and curated Tier 3 baselines bring `realism-snapshot-{summer|winter}.json` coverage to `200+` global countries and territories across Africa, Latin America, MENA, and Central/East/Southeast Asia for `compose-local`.
  4. An internal CI OSM Overpass/Taginfo (`CC BY-SA`) speed-limit drift audit generates maintainer review reports highlighting mismatches against `data/laws/`, while automated provenance checks verify zero `CC BY-SA` data enters any `CC BY 4.0` mod or snapshot artifact.
**Plans**: 4 plans
Plans:
- [x] `05-01-PLAN.md` — Global `225`-territory & `151`-currency foundation (`currencies.json`, `tier3_fuel_baselines.json`, `225` canonical laws/mappings/lockfile, `58` global TZ overrides, `18` ECB + `134` isolated FX, `0.010 EUR/L` floor clamping, frozen v1 snapshot, 12 updated Phase 2-4 tests) (`GLB-03`)
- [x] `05-02-PLAN.md` — Non-EU Tier 1 open government fuel collectors (`US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`/CREG, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`), `code=` secret redaction, shared OOXML safety, EU Core vs Global Tier 1 outage gate separation, `--no-global`, and optional Friday CI secrets (`GLB-01`)
- [x] `05-03-PLAN.md` — Research-gated Tier 2 national portal scrapers (`IS`, `CH`, `MD`, `MK`, `RU`, `IL`, `AE`, `ZA`, `SA`, `NG`; `KE`/`ID`/`JO`/`EG` in Tier 3), stdlib `fetch/_html.py`, per-country circuit breakers, `--no-tier2`, 5-tier staleness (`14d`/`45d`/`105d`/`30d`/`180d`), noise-controlled Tier 3 rollups & Global Snapshot Coverage changelogs (`GLB-02`)
- [x] `05-04-PLAN.md` — Quarantined `src/ets2v2/audit/` subpackage + Phase 5 universal AST DAG quarantine walls, clean-room `speed_audit_allowlist.json`, `ets2v2 audit {osm-speeds,taint}` (`westnordost` + opt-in Overpass/Taginfo), independent `ETS2V2-INV-LICENSE-TAINT` validator gate, full repo/snapshot/package taint gate, and standalone monthly zero-Git-write `.github/workflows/osm-speed-audit.yml` (`GLB-04`)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. VFS, 1.62 Baseline Extraction & Structural SII Engine | 4/4 | Complete | 2026-11-16 |
| 2. Realism Registry, Core & Validator | 5/5 | Complete | 2026-11-20 |
| 3. European Fuel/FX & Totems | 4/4 | Complete | 2026-11-22 |
| 4. ProMods Companion & Combo Composer | 4/4 | Complete | 2026-11-25 |
| 5. Global Tier 1/2/3 & OSM Audit | 4/4 | Complete | 2026-11-26 |

## Future Milestone Scope (V2 — Deferred)

Deferred out of V1 until Phase A Semi-Auto publishing (`Phase 2`) is proven across consecutive weekly Friday cycles:

- **PUB-V2-01**: Full-auto GitHub Actions `steamcmd +workshop_build_item` publishing using inline post-self-update 30-second TOTP (`STEAM_SHARED_SECRET`), dedicated unrestricted (`$5+`) Steam publisher account owning `227300`, `steam-workshop-prod` Environment approval, isolated matrix jobs (`summer`, `winter`), and sanitized logging (`GHSA-mj96-mh85-r574`).
- **PUB-V2-02**: Multi-day hidden-item (`visibility: 2`) Workshop verification spike proving zero `config.vdf` token rot (`#56`), Workshop metadata preservation, clean ETS2 `1.62+` `game.log.txt` loading, and SCS Workshop Uploader (`421800`) re-adoption after clearing `mod_items_data.sii`.
