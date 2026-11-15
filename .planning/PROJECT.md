# ETS2 World Country Realism Generator (V2)

## What This Is

A clean-room, open-source (**public GitHub repo**) ETS2 `1.62+` country-realism data pipeline, mod compiler, and local map-combo composer written in Python `3.12+` (`uv`). Instead of manually merging incompatible Steam Workshop mods every week (such as *Updated WINTER speed limits* `3668352310` and *Real life fuel prices* `3249064596`), V2 collects verified real-world global fuel prices, FX rates, seasonal speed limits, DST timezones, mandatory daytime running light laws, and axle mass limits into one canonical snapshot — producing:

1. **Steam Workshop Vanilla + DLC Core Editions:** **Summer** and **Winter** (built automatically via CI from ETS2 `1.62.3.3s` clean baselines).
2. **Steam Workshop ProMods Companion Editions:** **Summer (ProMods Edition)** and **Winter (ProMods Edition)** covering **ProMods Europe + ProMods Middle East + ProMods Maghreb + ProMods The Great Steppe** (compiled locally from the user's installed ProMods `def` packages so zero proprietary ProMods assets or copied `.scs` files are ever redistributed in the public repo).
3. **Local Map Combo Auto-Composer (`ets2v2 compose-local`):** A CLI tool consuming CI's global `realism-snapshot-{summer|winter}.json` across any user's `mod/` load order (*RusMap*, *Trans-Siberian Truckway*, *UMCF*, *Beyond Map*, *Project Japan Relocated*, *Java Road Revolution*, *Southeast Asia*, *Roads of Chunghwa*, *EAA Rescaled*, Africa mods, etc.) to output a conflict-free `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs`.

## Core Value

One public, open-source, reproducible pipeline generating bug-free **Summer** and **Winter** ETS2 country realism mods and multi-currency gas-station totems — preserving map-mod geometry, zones, and regions cleanly across Vanilla, ProMods, and arbitrary global Map Combos.

## Current Baseline & Scope Decisions

### Locked Decisions (2026-11-16 Post-Research Checkpoint)

- **Clean V2 Public Open-Source Rewrite:** Built from scratch in `d:\CODE\Ets2 Mod V2` (`MIT` / `CC BY 4.0` clean-room codebase; legacy `d:\CODE\Ets2 Mod` is reference-only; `.agents/skills/scs-modding-wiki` is vendored locally). Zero GPL dependency contamination and zero `3nK` decryption/copying.
- **Target Game Version:** **ETS2 `1.62.3.3s`** (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`). Uses fresh base extracts from `def.scs` (36 countries incl. 5-axle 60t `iceland.sui`) and `locale.scs` (43 active locales, 12 supported `@@tz_*@@` keys).
- **Workshop Distribution & ProMods IP Boundary (Option C):**
  - Public CI generates **Vanilla + DLC (`Summer` & `Winter`)** plus global `realism-snapshot-{summer|winter}.json` without committing any ProMods `.scs` or copied ProMods map/def files into GitHub.
  - **ProMods Edition (`Summer` & `Winter`, covering Europe + Middle East + Maghreb + The Great Steppe)** builds cleanly on the maintainer's PC from local installed ProMods `def` archives using the exact same `merge` engine + `realism-snapshot`.
- **Map Combo Protection & Field-Ownership Policy:**
  - Strict separation between realism fields (`fuel_price`, `lights_mandatory`, `driving_tired_offence`, `speed_limits` `car`/`truck`/`bus`) and map-owned identity/geometry (`country_id`, `pos`, `regions[]`/`region_areas[]`, `train`/`tram` speed units, `leftside_traffic`, `imperial_units`, `country_code` by default).
  - **`max_of_map_and_real`** for `mass_limit_per_axle_count[]` (never downgrades EAA 80t, Iceland 60t, RusMap/TST 48t, Finland 105t).
  - **`patch_if_single_tz`** for `time_zone` (preserves multi-TZ coordinate boxes in TST 27-TZ Russia, UMCF 5-TZ Kazakhstan, EAA Brazil; shifts single-TZ Summer/Winter DST via Python `zoneinfo` + `tzdata`, emitting plain `"CET"`/`"WET"` where `locale.scs` lacks keys).
  - Explicit diagnostics + `--unpacked-defs` fallback on `AEM!` / encrypted ZIP archives; hardcoded community map totems (JRR/7RM) opt-in only (`--patch-hardcoded-totems`).
- **Full Sign-Board Totem System (Option 4b, Zero DDS):** Namespaced `@@fp_*_ets2v2@@` `def/sign/board/*.sii` rewrites + `locale/<lang>/local_module.ets2v2_fuel.sii` across all **43** active ETS2 `1.62` locales (zero `.dds`/`.tobj` textures), displaying native local currencies/formats (`pence` vs `GBP`, `eurocents` vs `EUR`, `<sup>9</sup>` tenth-cents, post-2026 Bulgaria `EUR`, multi-grade `95`/`98`/`100`/`Diesel`/`Diesel+`/`E85`/`LPG`), repairing all 17+ active missing/placeholder `1.62` boards (`gas_bi_*`, `gas_ie_*`, `gas_ba_*_lpg`, `gas_dk_92`, `gas_is_ip1_98`), and updating `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` in ProMods Edition.
- **3-Tier Global Data Collection Pipeline (`CC BY 4.0` Compatible):**
  - **FX:** `Frankfurter v2` (MIT, 219 currencies) primary + `ECB eurofxref-daily.xml` validator + `fawazahmed0/exchange-api` (CC0) & CBR XML fallbacks.
  - **Fuel Tiers:** Tier 1 open government APIs (`EC Weekly Oil Bulletin` + `FionnHughes`/`fuel-prices.eu` `CC BY 4.0` fallbacks, `UK DESNZ` OGL v3, `NO SSB`, `FR`/`DE`/`ES`/`IT`/`NL` multi-grade APIs, `US EIA`, `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`), Tier 2 guarded national portals with `prices.lock.json` circuit-breaker fallback & range alerts, and Tier 3 curated community baselines.
  - **Explicitly Excluded:** `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`), `MyLPG.eu`, paid `IEA`, and direct redistribution of `CC BY-SA` OSM Wiki data (used internally as CI speed-limit drift audit only).
- **Workshop Publishing Strategy (Phase A Now, Phase B Later):**
  - **Phase A (Semi-Auto in Scope):** Automated weekly Friday `06:00 UTC` CI build, strict **Offline SCS Validator** (`00001`–`00010` + `WARN 00001`/`00002`, `276x162` `.jpg` icon, zero `display_name`/`compatible_versions[]` in Workshop `manifest.sii`, no ZIP-as-`.scs`), canonical payload SHA-256 diff gate against `state/published.json`, and generated Summer/Winter changelogs + artifacts for 1-click GUI upload.
  - **Phase B (Full-Auto Deferred):** SteamCMD `+workshop_build_item` + inline post-self-update 30s `STEAM_SHARED_SECRET` TOTP + isolated matrix deploys + hidden-item (`visibility: 2`) verification spike deferred until after V1 Semi-Auto workflow is battle-tested.

## Context

- **Installed ETS2 baseline:** `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\def.scs` & `locale.scs` (HashFS v2, ETS2 `1.62.3.3s`).
- **Local reference Workshop mods:** `3668352310` (*Updated WINTER speed limits*, HashFS v1) and `3249064596` (*Real life fuel prices*, HashFS v2).
- **User's local mod & combo directory:** `D:\ETS2Data\Euro Truck Simulator 2\mod` (audited 503 mods across ProMods EU/ME/TGS/MA, RusMap, TST, UMCF, GMC Beyond Fix, JRR, SEA, RoC, Project Japan Relocated, EAA Rescaled, SemEuropa).
- **Research synthesis:** Full technical forensics, license checks, and 503-mod census documented in [SUMMARY.md](file:///d:/CODE/Ets2%20Mod%20V2/.planning/research/SUMMARY.md).

## Constraints

- **Zero Engine / Validator Errors:** Generated packages must pass every SCS Workshop Uploader rule (`00001`–`00010`, `WARN 00001`/`00002`, UTF-8 no-BOM LF, POSIX `/`, `<=12`-char unit segments) and load in ETS2 `1.62` `game.log.txt` with zero `[unit]` / `[mods]` errors.
- **No Map Clobbering:** Never strip `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`/`tram` speed units, higher map axle limits, or `leftside_traffic`.
- **Convoy Compatibility:** Always set `mp_mod_optional: true` in `manifest.sii`.
- **Clean Provenance & Public License:** Public GitHub repo stays strictly free of ProMods `.scs`/def dumps, `CC BY-NC-ND` scrapers, `CC BY-SA` redistributed blobs, and GPL archive extractors.

## Evolution

This document evolves cleanly across milestone phases. Current phase decisions are locked into `REQUIREMENTS.md` and `ROADMAP.md`.

---
*Updated: 2026-11-16 — Post-research architectural, map-combo, data-tier, and semi-auto publishing decisions locked.*
