# ETS2 Country Realism

## What This Is

A clean-room, open-source (**public GitHub repo**, `MIT` code / `CC BY 4.0` curated data) ETS2 `1.62+` country-realism data pipeline, mod compiler, and local map-combo composer written in Python `3.12+` (`uv`), maintained by **MissionWAR** (`ets2-country-realism` / package `ets2_realism` / CLI `ets2-realism`). Instead of manually merging incompatible Steam Workshop mods every week (such as *Updated WINTER speed limits* `3668352310` and *Real life fuel prices* `3249064596`), it collects verified real-world global fuel prices, FX rates, seasonal speed limits, DST timezones, mandatory daytime running light laws, and axle mass limits into one canonical snapshot — producing:

1. **Steam Workshop Vanilla + DLC Core Editions:** **Summer** and **Winter** (built automatically via CI from ETS2 `1.62.3.3s` clean baselines).
2. **Steam Workshop ProMods Companion Editions:** **Summer (ProMods Edition)** and **Winter (ProMods Edition)** covering **ProMods Europe + ProMods Middle East + ProMods Maghreb + ProMods The Great Steppe** (compiled locally from the user's installed ProMods `def` packages so zero proprietary ProMods assets or copied `.scs` files are ever redistributed in the public repo).
3. **Local Map Combo Auto-Composer (`ets2-realism compose-local`):** A CLI tool consuming CI's global `realism-snapshot-{summer|winter}.json` (`225` territories) across any user's `mod/` load order (*RusMap*, *Trans-Siberian Truckway*, *UMCF*, *Beyond Map*, *Project Japan Relocated*, *Java Road Revolution*, *Southeast Asia*, *Roads of Chunghwa*, *EAA Rescaled*, Africa mods, etc.) to output a conflict-free `zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs`.

## Core Value

One public, open-source, reproducible pipeline generating bug-free **Summer** and **Winter** ETS2 country realism mods and multi-currency gas-station totems — preserving map-mod geometry, zones, and regions cleanly across Vanilla, ProMods, and arbitrary global Map Combos.

## Current State (v1.0 Shipped — 2026-11-26)

- **Shipped Version:** `v1.0` (`tag: v1.0`, `24/24` V1 requirements satisfied, `5/5` phases verified & code-reviewed, `5/5` Nyquist validation docs compliant).
- **Codebase:** `73` source modules (`26,090` LOC) + `45` test modules (`21,978` LOC) passing strict `ruff`, `basedpyright`, `pytest`, Offline SCS Workshop Validator, and `ETS2R-INV-LICENSE-TAINT` gates.
- **Data Coverage:** `225` countries/territories (`151` currencies, `119` map-mod aliases), `36` SCS `1.62.3.3s` Vanilla+DLC baselines, `460` Zero-DDS fuel sign boards across all `43` active locales.
- **Operational Readiness:** Codebase, `README.md`, `LICENSE`, and all 3 GitHub Actions workflows (`ci.yml`, `phase-a-release.yml`, `osm-speed-audit.yml`) are ready for GitHub push, first live `workflow_dispatch` fuel/FX run, and initial manual Steam Workshop upload via **SCS Workshop Uploader (`AppID 421800`)**.
- **Archive:** [MILESTONES.md](MILESTONES.md), [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md), [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md), [v1.0-MILESTONE-AUDIT.md](v1.0-MILESTONE-AUDIT.md).

## Next Milestone Goals

- **Operational Launch (Post-v1.0):** Push repository to `MissionWAR/ets2-country-realism`, run the first live Friday / manual `Phase A Weekly Release` workflow to populate live `state/prices.lock.json` and `snapshots-latest`, verify in ETS2 `1.62.3.3s` `game.log.txt`, and publish initial Core & ProMods Workshop items via `AppID 421800`.
- **v1.1 Candidates:** Non-editable wheel packaging (`importlib.resources` for `pip`/`uv tool install`), SHA-pinned GitHub Actions, and concurrent Tier 2 HTTP fetching / modular CLI refactor.
- **v2.0 Candidates:** Phase B full-auto SteamCMD Workshop publishing (`PUB-V2-01`, `PUB-V2-02`) after Phase A semi-auto publishing is proven across consecutive weekly cycles.

## Locked Architecture & Scope Decisions

- **Clean Open-Source Rewrite:** Built from scratch in Python `3.12+` (`uv`, `src/ets2_realism/`, `MIT` / `CC BY 4.0`). Zero GPL dependency contamination and zero `3nK` decryption/copying.
- **Target Game Version:** **ETS2 `1.62.3.3s`** (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`). Uses fresh clean-room JSON baselines from `def.scs` (36 countries incl. 5-axle 60t `iceland.sui`) and `locale.scs` (43 active locales, 12 supported `@@tz_*@@` keys).
- **Workshop Distribution & ProMods IP Boundary (Option C):** Public CI generates Vanilla+DLC Core (`Summer` & `Winter`) plus global `realism-snapshot-{summer|winter}.json` with zero ProMods `.scs`/def files in Git; ProMods Editions (`EU + ME + MA + TGS`) compile locally from user-installed ProMods archives.
- **Map Combo Protection (`FieldOwnershipPolicy`):** Strict separation between realism overlays (`fuel_price`, `lights_mandatory`, `driving_tired_offence`, `speed_limits` `car`/`truck`/`bus`) and map-owned identity/geometry (`country_id`, `pos`, `regions[]`/`region_areas[]`, `train`/`tram`, `leftside_traffic`, `imperial_units`, `country_code` default), `max_of_map_and_real` axle weights, `patch_if_single_tz` seasonal DST shifting, explicit `AEM!`/`3nK`/encrypted-ZIP diagnostics + `--unpacked-defs`, and opt-in `--patch-hardcoded-totems`.
- **Option 4b Zero-DDS Fuel Totems:** Namespaced `@@fp_*_ets2r@@` `def/sign/board/*.sii` rewrites + synchronized `locale/<lang>/local_module.ets2r_fuel.sii` across all 43 active ETS2 `1.62` locales (zero `.dds`/`.tobj`), plus `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` in ProMods Edition.
- **Legally Clean 3-Tier Global Data Pipeline (`CC BY 4.0` Compatible):** Multi-provider FX (`Frankfurter v2`, `ECB`, `fawazahmed0`, `CBR`), Tier 1 open EU & Global government APIs, Tier 2 guarded national portals with per-country circuit breakers & `prices.lock.json`, Tier 3 curated baselines (`225` total territories), and an AST-quarantined monthly CI OSM (`CC BY-SA`) speed-limit drift audit that never writes into `CC BY 4.0` outputs.
- **Phase A Semi-Auto Publishing:** Friday `06:00 UTC` CI build, Offline SCS Validator (`00001`–`00010` + `WARN 00001`/`00002`, `276x162` `.jpg`, `mp_mod_optional: true`), canonical SHA-256 diff gate (`state/published.json`), rolling `snapshots-latest` release, and persistent Release PR for 1-click GUI Workshop upload with zero Steam secrets in CI.

## Context

- **Installed ETS2 baseline:** `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\def.scs` & `locale.scs` (HashFS v2, ETS2 `1.62.3.3s`).
- **User's local mod & combo directory:** `D:\ETS2Data\Euro Truck Simulator 2\mod` (audited 503 mods across ProMods EU/ME/TGS/MA, RusMap, TST, UMCF, GMC Beyond Fix, JRR, SEA, RoC, Project Japan Relocated, EAA Rescaled, SemEuropa).
- **Research synthesis:** Full technical forensics, license checks, and 503-mod census documented in [SUMMARY.md](research/SUMMARY.md).

## Constraints

- **Zero Engine / Validator Errors:** Generated packages must pass every SCS Workshop Uploader rule (`00001`–`00010`, `WARN 00001`/`00002`, UTF-8 no-BOM LF, POSIX `/`, `<=12`-char unit segments) and load in ETS2 `1.62` `game.log.txt` with zero `[unit]` / `[mods]` errors.
- **No Map Clobbering:** Never strip `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`/`tram` speed units, higher map axle limits, or `leftside_traffic`.
- **Convoy Compatibility:** Always set `mp_mod_optional: true` in `manifest.sii`.
- **Clean Provenance & Public License:** Public GitHub repo stays strictly free of ProMods `.scs`/def dumps, `CC BY-NC-ND` scrapers, `CC BY-SA` redistributed blobs, and GPL archive extractors.

---
*Updated: 2026-11-26 — v1.0 milestone shipped and archived.*
