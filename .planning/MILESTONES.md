# Milestones — ETS2 Country Realism

## Shipped

### v1.0 — Phase A Semi-Auto Workshop & Local Map Combo Release (Shipped 2026-11-26)

- **Tag:** `v1.0`
- **Scope:** Phases 1–5 (`21/21` plans, `24/24` V1 requirements, `94/94` must-haves)
- **Git Range:** `0aabcf4..2ef876c` (`120` commits, `2026-11-15` → `2026-11-26`)
- **Codebase Size:** `73` source Python files (`26,090` LOC) + `45` test files (`21,978` LOC)
- **Audit Status:** Passed ([v1.0-MILESTONE-AUDIT.md](v1.0-MILESTONE-AUDIT.md)) — `5/5` phases verified, `5/5` code reviews passed/resolved, `5/5` Nyquist validation docs compliant, `0` license-taint violations
- **Archive:**
  - [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
  - [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)
- **Key Highlights:**
  - Clean-room HashFS v1/v2 + ZIP + unpacked VFS reader and comment/region-preserving surgical SII/SUI engine for ETS2 `1.62.3.3s`+
  - Canonical `225`-territory country law registry (`151` currencies, `119` map aliases) with dynamic `zoneinfo`/`tzdata` DST calculation
  - Dual `Summer` & `Winter` Vanilla+DLC Core Workshop editions with Option 4b Zero-DDS 43-locale fuel totems across all `460` `1.62` boards
  - Independent Offline SCS Workshop Validator (`00001`–`00010`, `WARN 00001`/`00002`, Zero-DDS, locale parity, license taint)
  - Multi-tier global FX + fuel pipeline (Tier 1 EU/Global APIs + Tier 2 guarded portals + Tier 3 curated baselines) with Friday `06:00 UTC` Phase A GitHub Actions CI & rolling `snapshots-latest` releases
  - Local ProMods Companion Builder (`EU + ME + MA + TGS`, zero ProMods files in Git) and `ets2-realism compose-local` multi-map combo composer with `FieldOwnershipPolicy`
  - AST-quarantined monthly internal OSM speed-limit drift audit (`CC BY-SA` strictly isolated from `CC BY 4.0` outputs)

---

*Next milestone: Run `/gsd-new-milestone` when ready to plan v1.1 (packaging/CI polish) or v2.0 (Phase B full-auto SteamCMD Workshop publishing).*
