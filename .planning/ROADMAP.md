# Roadmap: ETS2 Country Realism

## Milestones

- ✅ **v1.0 — Phase A Semi-Auto Workshop & Local Map Combo Release** (Phases 1–5, 21/21 plans, 24/24 requirements) — Shipped 2026-11-26 ([Archive](milestones/v1.0-ROADMAP.md) | [Requirements](milestones/v1.0-REQUIREMENTS.md) | [Audit](v1.0-MILESTONE-AUDIT.md))

## Active Milestone

None active. Run `/gsd-new-milestone` to define fresh requirements and phases for **v1.1** (packaging/CI polish) or **v2.0** (Phase B full-auto SteamCMD Workshop publishing).

## Future Milestone Scope (Deferred Candidates)

### v1.1 Polish Candidates (from v1.0 Audit)
- Non-editable wheel packaging (`importlib.resources` bundling of `data/` and `assets/` for `pip install` / `uv tool install`).
- Pinning GitHub Actions to immutable 40-char commit SHAs.
- Architecture & CI performance refactor (splitting monolithic CLI/pipeline/compose helpers and concurrent Tier 2 HTTP fetching).

### v2.0 Full-Auto Publishing (Deferred until Phase A proven across live weekly cycles)
- **PUB-V2-01**: Full-auto GitHub Actions `steamcmd +workshop_build_item` publishing using inline post-self-update 30-second TOTP (`STEAM_SHARED_SECRET`), dedicated unrestricted (`$5+`) Steam publisher account owning `227300`, `steam-workshop-prod` Environment approval, isolated matrix jobs (`summer`, `winter`), and sanitized logging (`GHSA-mj96-mh85-r574`).
- **PUB-V2-02**: Multi-day hidden-item (`visibility: 2`) Workshop verification spike proving zero `config.vdf` token rot (`#56`), Workshop metadata preservation, clean ETS2 `1.62+` `game.log.txt` loading, and SCS Workshop Uploader (`421800`) re-adoption after clearing `mod_items_data.sii`.
