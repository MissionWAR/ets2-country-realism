# ETS2 World Country Realism Generator (V2)

## What This Is

An open-source ETS2 mod generator and data-collection pipeline (starting fresh from scratch for **ETS2 1.62**) that produces **two conflict-free Steam Workshop editions** from a single repository: **Summer Edition** and **Winter Edition**. Instead of manually merging incompatible Steam Workshop mods every week (such as *Updated WINTER speed limits* `3668352310` and *Real life fuel prices* `3249064596`), the pipeline gathers real-world country data (fuel prices, seasonal speed limits, `_vtd` variable truck zones, timezones, mandatory daytime lights, axle mass limits, country codes) and compiles clean, validated ETS2 game files including gas-station price totem signs.

## Core Value

One open-source, reproducible pipeline generating clean Summer and Winter ETS2 country realism mods — eliminating `def/country/*.sui` conflicts while scaling cleanly across Europe and global Map Combos.

## Current Baseline & Scope Decisions

### Locked Decisions (2026-11-15)
- **Clean V2 Architecture:** Built from scratch in `d:\CODE\Ets2 Mod V2` (legacy V1 repo in `d:\CODE\Ets2 Mod` is reference-only for proven ideas like EC Oil Bulletin parsing; `.agents/skills/scs-modding-wiki` is installed locally).
- **Target Game Version:** **ETS2 1.62** (`1.62.3.3s` installed on disk at `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`).
- **Dual Workshop Editions:** One repository builds two separate mod packages/editions: **Summer** and **Winter**.
- **Feature Parity & Improvements:**
  - `def/country/*.sui` realism fields (`fuel_price`, `time_zone`, `time_zone_name`, `secondary_time_zone*`, `lights_mandatory`, `mass_limit_per_axle_count`, `country_code`) preserving SCS `regions[]` / `region_areas[]`.
  - Per-country `speed_limits.sii` + `_vtd` variable/regional speed-limit overrides (modeled after/improving upon `3668352310`).
  - Fuel price totem sign updates (`locale/*/local_module.*.sii` and related station signs, modeled after/improving upon `3249064596`).
- **Publishing Strategy:** **Semi-automatic** Workshop packaging & validation first (local/CI builds ready for upload, zero stored Steam secrets initially), progressing to **Full-automatic** Steam Workshop publishing once safety, bot/account isolation, and SCS-format validation are proven.

### Open Architecture Questions (To Be Decided After `.planning/research/` Review)
1. **Map Combo & Global Country Scaling:** How to support Vanilla+DLCs AND large GMC-style Map Combos (ProMods, RusMap, UMCF, Beyond Map, Africa mods, Project Japan, Java Road Revolution, Mapa EAA, Southeast Asia, Roads of Chungvua) without maintaining an unmanageable proliferation of brittle presets.
2. **Global Automated Data Collection:** What durable, open-source / public automated sources exist for fuel prices and speed limits beyond EU27+UK (Middle East, CIS, Africa, Asia, South America), and how automated scraping vs. curated fallback tables should be structured.

## Context

- **Installed ETS2 baseline:** `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\def.scs` (HashFS v2, ETS2 `1.62.3.3s`).
- **Local reference Workshop mods:**
  - `3668352310` (*Updated WINTER speed limits*): `D:\SteamLibrary\steamapps\workshop\content\227300\3668352310\universal.scs` (HashFS v1).
  - `3249064596` (*Real life fuel prices*): `D:\SteamLibrary\steamapps\workshop\content\227300\3249064596\universal.scs` (HashFS v2).
- **User's temporary merged mod:** `D:\ETS2Data\Euro Truck Simulator 2\mod\Country_Speed_Fuel_Merge.scs` (75 `.sui` files combining `3668352310`, `3249064596`, ProMods, RusMap, and UMCF winners while fixing bugs in `3249064596` such as `armenia` `leftside_traffic: true` and `estonia` `@@tz_eest@@i`).
- **Local modding reference:** `.agents/skills/scs-modding-wiki` (163-page SCS Modding Wiki mirror; verify any 1.61/1.62 deltas online).

## Constraints

- **SCS Format & Validation:** Generated packages must load with zero ETS2 log errors and pass SCS Workshop Uploader rules (`versions.sii`, `manifest.sii`, icon dimensions, UTF-8 / SiiNunit formatting).
- **No Map Breakage:** Never silently strip SCS/map-mod `regions[]`, `region_areas[]`, `secondary_time_zone*`, or `country_code` overrides needed by map mods.
- **Convoy Compatibility:** Preserve `mp_mod_optional: true` in `manifest.sii`.
- **Open-Source Licensing & Provenance:** Respect data source licenses (e.g., EC Weekly Oil Bulletin CC BY 4.0 attribution) and keep automated pipelines reproducible without fragile secret exposure.

## Evolution

This document evolves after project research review (locking Map Combo & Data Collection decisions into `REQUIREMENTS.md` and `ROADMAP.md`) and at each phase transition.

---
*Initialized: 2026-11-15 — awaiting research synthesis and user checkpoint before finalizing Requirements & Roadmap*
