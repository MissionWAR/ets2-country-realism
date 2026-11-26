# Project State

## Project Reference

See: [.planning/PROJECT.md](PROJECT.md) and [.planning/MILESTONES.md](MILESTONES.md) (v1.0 shipped 2026-11-26)

**Core value:** One public, open-source (`MIT` / `CC BY 4.0`), reproducible pipeline generating bug-free **Summer** and **Winter** ETS2 `1.62+` country realism mods and Zero-DDS multi-currency gas-station totems — preserving map-mod geometry, zones, and regions cleanly across Vanilla+DLC, ProMods (`EU + ME + MA + TGS`), and arbitrary global map combos via `ets2-realism compose-local`.
**Current focus:** Milestone `v1.0` shipped, archived, and tagged on `master`. Ready for GitHub repository publishing, first live Friday / manual Phase A workflow run, local ETS2 `1.62.3.3s` in-game verification, or starting the next milestone via `/gsd-new-milestone`.

## Current Position

Milestone: v1.0 — SHIPPED & ARCHIVED (`2026-11-26`, tag `v1.0`)
Phase: 5 of 5 complete (archived in `.planning/milestones/v1.0-ROADMAP.md`)
Plan: 21 of 21 complete (`24/24` V1 requirements archived in `.planning/milestones/v1.0-REQUIREMENTS.md`)
Status: Milestone v1.0 complete; awaiting next milestone (`/gsd-new-milestone`)
Last activity: 2026-11-26 — Archived v1.0 milestone, updated `PROJECT.md`/`ROADMAP.md`/`MILESTONES.md`, deleted active `REQUIREMENTS.md` for next milestone, and created git tag `v1.0`

Progress: [██████████] 100%

## Performance Metrics (v1.0)

**Velocity:**
- Total plans completed: 21
- Average duration: ~29 min
- Total execution time: ~10.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. VFS, 1.62 Baseline & SII Engine | 4/4 | ~69 min | ~17 min |
| 2. Realism Registry, Core & Validator | 5/5 | ~68 min | ~14 min |
| 3. European Fuel/FX & Totems | 4/4 | ~116 min | ~29 min |
| 4. ProMods Companion & Combo Composer | 4/4 | ~227 min | ~57 min |
| 5. Global Tier 1/2/3 & OSM Audit | 4/4 | ~140 min | ~35 min |

## Accumulated Context

### Key Shipped Decisions (v1.0)

- **Public Identity:** Distribution `ets2-country-realism`, package `ets2_realism`, CLI `ets2-realism`, author `MissionWAR`, `MIT` code / `CC BY 4.0` curated data.
- **Target Game Baseline:** ETS2 `1.62.3.3s` (`36` countries, `43` active locales, `12` `@@tz_*@@` keys, `460` fuel sign boards).
- **Option C Distribution & ProMods IP Boundary:** Public CI builds Vanilla+DLC Core (`Summer` & `Winter`) + `225`-territory `realism-snapshot-{summer|winter}.json` with zero ProMods files in Git; ProMods Editions (`EU + ME + MA + TGS`) build locally from user-installed ProMods archives.
- **Map Combo Protection (`FieldOwnershipPolicy`):** Preserves map identity/geometry, `max_of_map_and_real` axles, `patch_if_single_tz` seasonal DST, explicit `AEM!`/`3nK` diagnostics + `--unpacked-defs`, opt-in `--patch-hardcoded-totems`.
- **Option 4b Zero-DDS Totems:** Namespaced `@@fp_*_ets2r@@` boards + synchronized `locale/<lang>/local_module.ets2r_fuel.sii` across all `43` active locales (zero `.dds`/`.tobj`).
- **3-Tier Global Pipeline & Quarantine:** Multi-provider FX + Tier 1 EU/Global + Tier 2 guarded portals + Tier 3 curated baselines (`225` territories); OSM (`CC BY-SA`) speed audit strictly AST-quarantined under `src/ets2_realism/audit/` and enforced by `ETS2R-INV-LICENSE-TAINT`.

### Pending Operational Steps (User Action)

- Push `master` and `v1.0` tag to GitHub (`MissionWAR/ets2-country-realism`).
- Optionally add free API keys (`TANKERKOENIG_API_KEY`, `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`) to GitHub Actions Secrets.
- Trigger first `Phase A Weekly Release` workflow run on GitHub Actions to fetch live prices and publish `snapshots-latest`.
- Upload Core & ProMods packages to Steam Workshop via **SCS Workshop Uploader (`AppID 421800`)** and verify in ETS2 `1.62.3.3s` `game.log.txt`.

### Deferred Backlog (Next Milestone Candidates)

- **v1.1:** Non-editable wheel packaging (`importlib.resources`), SHA-pinned GitHub Actions, concurrent Tier 2 fetching.
- **v2.0:** `PUB-V2-01` & `PUB-V2-02` (full-auto GitHub Actions `steamcmd` Steam Workshop publishing).

## Session Continuity

Last session: 2026-11-26
Stopped at: Milestone v1.0 archived and tagged (`v1.0`) on `master`
Resume file: .planning/MILESTONES.md
Next action: Publish to GitHub / run first live cycle, or run `/gsd-new-milestone` to begin v1.1 / v2.0
