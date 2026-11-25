# Project State

## Project Reference

See: [.planning/PROJECT.md](PROJECT.md) and [.planning/REQUIREMENTS.md](REQUIREMENTS.md) (updated 2026-11-16)

**Core value:** One public, open-source (`MIT` / `CC BY 4.0`), reproducible pipeline generating bug-free **Summer** and **Winter** ETS2 `1.62+` country realism mods and Zero-DDS multi-currency gas-station totems — preserving map-mod geometry, zones, and regions cleanly across Vanilla+DLC, ProMods (`EU + ME + MA + TGS`), and arbitrary global map combos via `ets2v2 compose-local`.
**Current focus:** Phase 4 complete, verified & code-reviewed (`04-VERIFICATION.md` `PASSED` `19/19`, `04-REVIEW.md` `resolved` `19/19`) — merged into `master` (`phase-04`), ready to start Phase 5 (Global Tier 1/2/3 Coverage & Internal OSM Audit)

## Current Position

Milestone: V1 (Phase A Semi-Auto Workshop & Local Map Combo Release)
Phase: 4 of 5 (ProMods Companion Builder & Local Map Combo Composer) — Complete, Verified & Reviewed
Plan: 4 of 4 in current phase (4/4 complete across 3 waves)
Status: Phase 4 merged into `master` and tagged `phase-04` (`04-01`..`04-04` complete, `04-VERIFICATION.md` `PASSED` `19/19` must-haves, `5/5` requirements `MAP-01`..`MAP-05`, `04-REVIEW.md` `resolved` `19/19` findings, **505 tests passing**, 0 ruff/basedpyright errors)
Last activity: 2026-11-25 — Resolved all 19 Phase 4 review findings and merged Phase 4 into `master` (`phase-04`)

Progress: [████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 17
- Average duration: ~28 min
- Total execution time: ~8.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. VFS, 1.62 Baseline & SII Engine | 4/4 | ~69 min | ~17 min |
| 2. Realism Registry, Core & Validator | 5/5 | ~68 min | ~14 min |
| 3. European Fuel/FX & Totems | 4/4 | ~116 min | ~29 min |
| 4. ProMods Companion & Combo Composer | 4/4 | ~227 min | ~57 min |
| 5. Global Tier 1/2/3 & OSM Audit | 0/4 | - | - |

## Accumulated Context

### Key Locked Decisions (2026-11-16 Post-Research Checkpoint)

- **Clean V2 Open-Source Rewrite:** Built from scratch in Python `3.12+` (`uv`, `src/ets2v2/`) under `MIT` / `CC BY 4.0`; legacy `d:\CODE\Ets2 Mod` is reference-only. Zero GPL dependency contamination (`TruckLib`/`Extractor`/`easy-scsmodmanager`) and zero `3nK` decryption/copying of reference mod `3668352310`.
- **Target Game Baseline:** ETS2 `1.62.3.3s` (`def.scs` 36 countries incl. 5-axle 60t `iceland.sui` + `457` `gas_*` signs; `locale.scs` 43 active locales + 12 `@@tz_*@@` keys). Plain `"CET"`/`"WET"`/`"AST"` emitted where `locale.scs` lacks keys.
- **Option C Distribution & ProMods IP Boundary:** Public CI builds Vanilla+DLC Core (`Summer` & `Winter`) plus `realism-snapshot-{summer|winter}.json` with zero ProMods `.scs`/def files stored in Git; ProMods Editions (`EU + ME + MA + TGS`) build locally from user-installed ProMods archives.
- **Map Combo Protection (`FieldOwnershipPolicy`):** Strict separation between realism overlays and map identity/geometry (`country_id`, `pos`, `regions[]`/`region_areas[]`, `train`/`tram`, `leftside_traffic`, `imperial_units`, `country_code` default). `max_of_map_and_real` axle mass limits; `patch_if_single_tz` seasonal DST shifting; explicit `AEM!`/encrypted-ZIP diagnostics + `--unpacked-defs`; opt-in `--patch-hardcoded-totems` for JRR/7RM.
- **Option 4b Zero-DDS Fuel Totems:** Namespaced `@@fp_*_ets2v2@@` `def/sign/board/*.sii` rewrites + synchronized `locale/<lang>/local_module.ets2v2_fuel.sii` across all 43 active `1.62` locales (excluding dead `fr_qc`, fixing `fr_ca`, populating all 17 active + 69 placeholder/blank `1.62` signs + `gas_is_ip1_98`), and `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` in ProMods Edition.
- **Legally Clean 3-Tier Data Pipeline:** `Frankfurter v2` + `ECB` + `fawazahmed0` + `CBR` FX; Tier 1 open gov APIs + Tier 2 guarded portals with `prices.lock.json` (`0.01–5.00 EUR/L`, `±25%` alert) + Tier 3 curated baselines (`200+` territories). Reject `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`), `MyLPG.eu`, paid `IEA`, and bundling `CC BY-SA` OSM data into `CC BY 4.0` outputs (OSM drift check is CI audit-only).
- **Phase A Semi-Auto Publishing:** Friday `06:00 UTC` CI build, Offline SCS Validator (`00001`–`00010` + `WARN 00001`/`00002`, `276x162` `.jpg`), canonical SHA-256 diff gate (`state/published.json`), and markdown changelogs with zero Steam secrets in CI.

### Open Operational Dependencies

- **Phase 1 (`VFS-02`):** Local ETS2 `1.62.3.3s` installation at `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\` (`def.scs`, `locale.scs`) required on maintainer machine to extract deterministic baseline fixtures into `data/baselines/ets2_1.62_def/`.
- **Phase 2 (`PUB-03`):** Optional manual upload verification via `SCS Workshop Uploader` (`AppID 421800`, currently not installed on local workstation) when verifying generated Phase A artifacts on Steam Workshop.
- **Phases 3 & 5 (`DAT-02`, `GLB-01`):** Optional free API keys for enhanced multi-grade / non-EU sources (`Tankerkönig` CC BY 4.0 key for DE, `US EIA` v2 key, `KR Opinet` key) if live fetching beyond keyless sources is enabled in CI.
- **Phase 4 (`MAP-01`, `MAP-03`):** Local `D:\ETS2Data\Euro Truck Simulator 2\mod` directory containing `promods-eu-def-v284.scs`, `promods-me-defmap-v284.scs`, `promods-ma-defmap-v104.scs`, `promods-tgs-defmap-v170.scs`, and user combo archives needed for local ProMods and `compose-local` validation.

### Deferred V2 Backlog

- **PUB-V2-01:** GitHub Actions full-auto `steamcmd +workshop_build_item` publishing with inline post-self-update 30s TOTP (`STEAM_SHARED_SECRET`) and isolated Summer/Winter matrix jobs.
- **PUB-V2-02:** Multi-day hidden-item (`visibility: 2`) Workshop verification spike validating TOTP resilience, metadata preservation, `1.62+` `game.log.txt` loading, and `AppID 421800` re-adoption after clearing `mod_items_data.sii`.

### Pending Todos

None yet.

### Blockers/Concerns

None blocking Phase 4 closeout or Phase 5 planning.

## Session Continuity

Last session: 2026-11-25
Stopped at: Phase 4 executed, verified, code-reviewed, merged into `master`, and tagged `phase-04`
Resume file: .planning/phases/04-promods-companion-builder-local-map-combo-composer/04-REVIEW.md
Next action: Run `/gsd-discuss-phase 5` to start Phase 5 (Global Tier 1/2/3 Coverage & Internal OSM Audit)
