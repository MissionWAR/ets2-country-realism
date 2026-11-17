# Phase 2: Realism Registry, Seasonal Core Builds & Offline Validator (Phase A) - Context

**Gathered:** 2026-11-17
**Status:** Ready for planning
**Scope:** Requirements `SIM-01`, `SIM-02`, `SIM-03`, `PUB-01`, `PUB-02`, `PUB-03` (Plans `02-01` through `02-05`)

<domain>
## Phase Boundary

Phase 2 builds the canonical ISO realism registry (`data/laws/`, `data/mappings/`), dynamic `zoneinfo` + `tzdata` seasonal DST timezone resolver, dual **Summer** and **Winter** 36-country Vanilla+DLC Core mod compiler (`dist/workshop/{summer,winter}/` and `dist/local/`), Offline SCS Workshop Validator (`00001`–`00010` + `WARN 00001`/`00002`), canonical SHA-256 diff gate (`state/published.json`), and Friday `06:00 UTC` Phase A GitHub Actions release pipeline with zero stored Steam secrets.

Out of scope for Phase 2 (explicitly deferred to later phases):
- Live FX conversion (`Frankfurter v2`/`ECB`/`fawazahmed0`/`CBR`), Tier 1 EU/EEA fuel APIs, `prices.lock.json` circuit breakers, and Option 4b 43-locale Zero-DDS fuel totems (**Phase 3**).
- ProMods (`EU + ME + MA + TGS`) country data/editions and `ets2v2 compose-local` map-combo composer (**Phase 4**).
- Non-EU Tier 1/2/3 global territory expansion (`200+` countries) and CI-only OSM (`CC BY-SA`) speed-limit drift audits (**Phase 5**).
- Full-auto SteamCMD Workshop publishing and hidden-item TOTP spike (**Future V2**).

</domain>

<decisions>
## Implementation Decisions

### 1. Law Registry Layout & Seasonal Rules (`SIM-01`, `SIM-02`)
- **D-01 — Per-Country JSON Registry Layout:** Store canonical country laws as individual JSON files under `data/laws/countries/<iso2>.json` paired with `data/mappings/ets2_countries.json` mapping ETS2 `1.62` country slugs (`albania`..`uk`) and metadata to ISO-3166 alpha-2 keys. Validate strictly with Pydantic v2 (`ConfigDict(strict=True, frozen=True, extra="forbid")`), `sort_keys=True`, UTF-8 no-BOM LF formatting, and zero extra YAML runtime dependencies. — **Reversibility:** `costly` — changing directory layout or schema keys affects Phase 3–5 data collectors and `compose-local` snapshot consumers.
- **D-02 — Strictly 36 Vanilla+DLC Countries in Phase 2:** Populate `data/laws/countries/` strictly for the **36 Vanilla+DLC countries** present in ETS2 `1.62.3.3s` `def.scs` (`data/baselines/ets2_1.62_def/countries.json`). Do not add ProMods or global non-vanilla entries (`AM`, `JO`, `SY`, `SM`, etc.) to `data/laws/countries/` until Phases 4–5; however, Phase 2 unit tests MUST still verify `zoneinfo` and schema invariants against edge cases such as `Asia/Amman`/`Asia/Damascus` (`UTC+3` `AST` permanent time) and `leftside_traffic` immutability guards.
- **D-03 — Seasonal Anchor Dates & Realism Semantics:** Derive `Summer` and `Winter` editions deterministically from peak seasonal reference dates (**July 15** for Summer, **January 15** for Winter, with an optional CLI `--date` override for inspection/testing) so editions pair naturally with seasonal weather mods (e.g., Grimes *New Summer* and *Frosty Winter*). Use `zoneinfo` + `tzdata` for UTC offsets and zone names (emitting `@@tz_*@@` only for the 12 keys present in `data/baselines/ets2_1.62_def/locales.json` and plain `"CET"`, `"WET"`, `"AST"`, etc. elsewhere), and apply verified statutory Summer/Winter speed limits (`car`, `truck`, `bus` — preserving `uk` imperial mph conventions), statutory `lights_mandatory` (including any verified seasonal DRL laws and fixing `NL`/`CH`/`AL`/`TR` vs `1.62` and `3668352310`), and statutory `mass_limit_per_axle_count[]` (including Iceland's 5-axle 60t and 80 km/h heavy-truck limit). Delegate per-country statutory lookup and verification across all 36 countries to `gsd-phase-researcher` during planning.

### 2. Clean-Room SII Synthesis & Engine Compatibility (`SIM-03`)
- **D-04 — Pure Clean-Room Synthesis Everywhere:** Generate all 36 `def/country/<slug>.sui` and `def/country/<slug>/speed_limits.sii` files deterministically from `data/baselines/ets2_1.62_def/*.json` + `data/laws/` + `data/mappings/` in both CI (`ubuntu-latest`) and local builds, guaranteeing byte-identical SHA-256 digests across platforms without requiring `def.scs` on build runners. Preserve `country_id`, `name`, `name_localized`, `country_code`, `iso_country_code` (and `iso_country_code_quoted`), `pos`, `imperial_units`, `leftside_traffic`, `trailer_standalone`, `regions[]`/`region_areas[]`, `secondary_time_zone*`, `extra_attributes`, and `train`/`tram` speed blocks from `countries.json` / `speed_limits.json`. (Surgical binary `.scs` patching remains scoped to Phase 4's `compose-local`.) — **Reversibility:** `costly` — affects canonical SHA-256 stability between local and CI builds.
- **D-05 — Omit `def/country.sii` & Keep 1.62 `fuel_price` Baseline:** Do **not** emit `def/country.sii` or `def/country.ets2v2.sii` in Core builds; emit only the 36 updated `def/country/<slug>.sui` and `def/country/<slug>/speed_limits.sii` files so vanilla `def.scs:/def/country.sii` loads our overrides cleanly with zero map-mod registration or duplicate-unit conflicts. Preserve `1.62` baseline `fuel_price` values from `countries.json` unchanged in Phase 2 until Phase 3 wires live FX/fuel feeds.

### 3. Workshop Packaging, Metadata & Icon Branding (`SIM-03`, `PUB-01`)
- **D-06 — Dual Packaging Targets (`dist/workshop/` + `dist/local/`):** Emit unpacked `universal/` directories beside `versions.sii` (`package_version_info : .universal { package_name: "universal" }`) under `dist/workshop/summer/` and `dist/workshop/winter/` for direct use in SCS Workshop Uploader (and future Phase B SteamCMD Steampipe delta uploads without double-zipping), **plus** separate standalone `dist/local/ETS2V2_Core_Summer.zip` and `dist/local/ETS2V2_Core_Winter.zip` (with `1980-01-01` normalized timestamps, POSIX `0o644` permissions, sorted paths, and local `display_name`) for drop-in `mod/` playtesting. Never place `universal.zip` and `universal/` side-by-side in the same Workshop root.
- **D-07 — Checked-In Clean-Room `276x162` `.jpg` Icons:** Author clean-room `assets/icons/summer.jpg` and `assets/icons/winter.jpg` (`276x162` px, EXIF/ICC stripped, `< 1 MB`) via a reproducible `Pillow` generation script committed in the repository, avoiding cross-OS `libjpeg-turbo` byte drift in CI and allowing custom artwork replacement later.
- **D-08 — Workshop `manifest.sii` Metadata & ISO-Week Versioning:** Use ISO-week `package_version` (`"1.62-YYYY.WW"` bumped **only** when canonical content changes so no-op runs do not alter hashes), `category[]` set to `["other", "ai_traffic"]`, `mp_mod_optional: true`, configurable `author` defaulting to `"ETS2 World Realism"`, and an auto-generated UTF-8 no-BOM LF `description.txt` (`< 1 MB`) summarizing edition scope, key rule changes, and `MIT` / `CC BY 4.0` open-source attribution. Omit `display_name` and `compatible_versions[]` from Workshop `manifest.sii` (`00010`, `WARN 00001`, `WARN 00002`).
- **D-09 — Strict Offline SCS Validator (`PUB-01`):** Enforce SCS Workshop rules `00001`–`00010` and warnings `WARN 00001`–`WARN 00002` as hard validation failures across both `dist/workshop/{summer,winter}/` (and standalone ZIPs), verifying `versions.sii` single-`.universal` layout, no extraneous root/unreferenced files, `276x162` JPEG `< 1 MB`, UTF-8 `< 1 MB` `description.txt`, plaintext SII/SUI hygiene (`validate_sii_hygiene()`), `<=12`-char `[a-z0-9_]` unit segments, `<=2` valid categories, zero `3nK` / `\` / `..`, and `1.62` realism invariants (`Estonia`, `regions[]`, `iceland` 5-axle 60t, `bus`/`train`/`tram` intact, `@@tz_*@@` whitelist).

### 4. Phase A Diff Ledger, Snapshot Seed & CI Release Flow (`PUB-02`, `PUB-03`)
- **D-10 — Persistent Release PR & `state/published.json` Lifecycle:** Run Friday `06:00 UTC` GitHub Actions CI (`+ workflow_dispatch` with `force_run` input) with zero Steam secrets. When a change is detected, upload validated `Summer` and `Winter` bundles + `CHANGELOG_SUMMER.md` / `CHANGELOG_WINTER.md` as GitHub workflow artifacts / draft release assets and open or update **one persistent Release PR** (via `github-actions[bot]`) updating `state/published.json` and changelogs — ensuring `state/published.json` advances only when the maintainer merges the PR after completing the manual SCS Workshop Uploader upload. — **Reversibility:** `costly` — defines the CI/human handoff contract and GitHub Actions workflow permissions (`contents: write`, `pull-requests: write`).
- **D-11 — Independent Per-Edition Hashing & Forward-Compatible v1 Snapshot:** Track `summer` and `winter` canonical payload SHA-256 digests independently in `state/published.json` (computed over sorted `(relative_path, normalized_bytes)` excluding `package_version`/volatile timestamps) so an edition with no content changes exits as a clean no-op even if the other edition updates. Emit versioned `schema_version: 1` `realism-snapshot-{summer,winter}.json` artifacts in Phase 2 containing the resolved 36-country rules (DST offsets/names, `lights_mandatory`, `mass_limit_per_axle_count`, speed limits, baseline `fuel_price`) with forward-compatible schema structure for Phases 3–5. — **Reversibility:** `one-way` — published `state/published.json` and `realism-snapshot` v1 schema form the persistent state and downstream Phase 3–4 integration contract.

### Claude's Discretion
- Exact Python subpackage structure for Phase 2 (`src/ets2v2/validate/`, `src/ets2v2/package/`, and registry/build module naming, updating `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` cleanly while keeping Phase 3–5 directories `fetch/`, `normalize/`, `merge/` blocked).
- Exact `ets2v2` CLI subcommand and flag names for registry validation, icon generation, seasonal Core builds, offline SCS validation, snapshot export, and diff-gate / changelog generation.
- Exact schema fields inside `data/laws/countries/<iso2>.json` (e.g., statutory citation URLs/notes, `effective_season` overrides, unit tags) and `state/published.json` JSON keys.
- Exact `Pillow` typography/color palette and `description.txt` wording/formatting (including optional SCS color tags).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or executing Phase 2:**

### Project & Milestone Specs
- `.planning/PROJECT.md` — Core value, Option C distribution model, clean-room IP boundaries, and Phase A semi-auto rules.
- `.planning/REQUIREMENTS.md` — Requirements `SIM-01`, `SIM-02`, `SIM-03`, `PUB-01`, `PUB-02`, `PUB-03` and `MAP-02` snapshot alignment.
- `.planning/ROADMAP.md` — Phase 2 goal, 4 success criteria, and 5-plan breakdown (`02-01`..`02-05`).
- `.planning/STATE.md` — Locked decisions and operational dependencies (`AppID 421800` optional manual upload check).
- `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-CONTEXT.md` — Phase 1 hygiene, JSON-only `data/` boundary, and SII/VFS decisions carried forward.

### Research & Codebase Maps
- `.planning/research/FEATURES.md` — Verified 36-country deltas (`3249064596`/`3668352310` vs `1.62`), statutory speed/DRL notes, and 12 `@@tz_*@@` keys.
- `.planning/research/PITFALLS.md` — SCS error codes `00001`–`00010` + `WARN 00001`/`00002`, `package_version` vs no-op SHA-256 gate trap, and Windows `tzdata` requirement.
- `.planning/research/ARCHITECTURE.md` — Field-ownership rules and ETS2 `.sui`/`.sii` load-order behavior.
- `.planning/research/STACK.md` — Pinned Phase 2 dependencies (`tzdata`, `pillow>=12,<14`).
- `.planning/research/SUMMARY.md` — Synthesized baseline metrics and Phase 2 deliverables.
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/STACK.md` — Strict typing, acyclic DAG, deterministic JSON, and `ruff`/`basedpyright`/`pytest` standards.

### Baseline Data & Official SCS Wiki Docs
- `data/baselines/ets2_1.62_def/manifest.json`, `countries.json`, `speed_limits.json`, `locales.json` — Clean-room `1.62.3.3s` schemas for all 36 countries, `regions[]`/`region_areas[]`, `train`/`tram`, and 12 `@@tz_*@@` tokens.
- `.agents/skills/scs-modding-wiki/docs/engine/units.md` — `SiiNunit` syntax, `@include` col-0, and `[a-z0-9_]{1,12}` unit segments.
- `.agents/skills/scs-modding-wiki/docs/engine/mod_manager.md` — `manifest.sii` attributes, 18 valid categories (`<= 2`), `mp_mod_optional`, and `description.txt` rules.
- `.agents/skills/scs-modding-wiki/docs/tools/scs_workshop_uploader/versions.sii.md` & `workshop_mod_structure.md` — `versions.sii` `.universal` schema and Workshop folder/ZIP layout.
- `.agents/skills/scs-modding-wiki/docs/tools/scs_workshop_uploader/validation_errors_and_solutions_for_them.md`, `warning_and_error_codes.md`, & `difference_between_workshop_mod_and_the_standard_mod.md` — Exact `00001`–`00010` and `WARN 00001`/`00002` checks.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ets2v2/sii/hygiene.py` (`validate_sii_hygiene`, `serialize_sii_text`, `validate_unit_name_segments`) — Enforces UTF-8 no-BOM, LF, column-0 `@include`, POSIX `/`, balanced braces, and `<=12`-char `[a-z0-9_]` unit segments; ready to plug directly into the Offline SCS Validator (`PUB-01`) and Core `.sui`/`.sii` synthesizers.
- `src/ets2v2/sii/country.py` (`CountryDataModel`, `CountryDataPatch`) & `src/ets2v2/sii/speed_limits.py` (`SpeedLimitsFile`, `VehicleSpeedLimitBlock`, `LaneSpeedRule`) — Existing frozen Pydantic models representing all country and speed-limit attributes extracted into `data/baselines/ets2_1.62_def/`.
- `src/ets2v2/baseline/models.py` (`BaselineBundle`, `BaselineCountry`, `BaselineSpeedLimit`, `LocalesBaseline`) — Deterministic JSON baseline loader contract consumed by Phase 2 builders and validators.
- `src/ets2v2/vfs/zip_archive.py` & `src/ets2v2/vfs/stack.py` — Can validate generated `dist/local/*.zip` archives in `PUB-01` tests using the exact same VFS reader used by `ets2v2`.

### Established Patterns
- Frozen Pydantic v2 models + deterministic sorted JSON serialization (`json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`, zero volatile timestamps).
- Acyclic layered `src/ets2v2/` package DAG enforced under `basedpyright` `strict` mode (`pythonVersion = "3.12"`) and `ruff` (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`).
- `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` gates which subpackages may exist under `src/ets2v2/` per active phase (Phase 2 activates its new subpackages while continuing to block `fetch/`, `normalize/`, `merge/`).

### Integration Points
- `pyproject.toml` & `uv.lock` — Add `tzdata` and `pillow>=12,<14` cleanly (keeping permissive MIT/BSD/Apache/PSF licensing).
- `src/ets2v2/cli.py` — Wire new Phase 2 subcommands (e.g., build, validate, publish/diff-gate) onto `build_parser()`.
- `.github/workflows/ci.yml` & new Friday Phase A workflow — Keep PR/push quality checks offline-fast while running Friday `06:00 UTC` Phase A builds + persistent Release PR updates.

</code_context>

<specifics>
## Specific Ideas

- User actively plays ETS2 with Grimes' seasonal weather mods (*New Summer*, *Early Autumn*, *Late Autumn/Mild Winter*, *Frosty Winter*), so **Summer** and **Winter** speed/DST/DRL realism is specifically intended to complement those seasonal packs cleanly.
- Detailed statutory lookup across the 36 Vanilla+DLC countries (seasonal `car`/`truck`/`bus` speeds, seasonal vs year-round `lights_mandatory`, and statutory `mass_limit_per_axle_count[]`) should be researched and verified by `gsd-phase-researcher` rather than guessed.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 2 boundaries. Non-vanilla ProMods countries (`AM`, `JO`, `SY`, `SM`, `SJ`, etc.) and `200+` global territories remain mapped to Phases 4 and 5 (`MAP-01`, `GLB-03`), while Phase 2 unit tests still cover `zoneinfo` edge cases (`Asia/Amman`, `Asia/Damascus`) and `leftside_traffic` invariants.

</deferred>

---

*Phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a*
*Context gathered: 2026-11-17*
