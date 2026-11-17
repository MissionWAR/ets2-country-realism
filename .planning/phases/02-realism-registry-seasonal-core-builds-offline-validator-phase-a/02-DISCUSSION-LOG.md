# Phase 2: Realism Registry, Seasonal Core Builds & Offline Validator (Phase A) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-17
**Phase:** 02-Realism Registry, Seasonal Core Builds & Offline Validator (Phase A)
**Areas discussed:** Law registry layout & seasonal rules, Clean-room SII synthesis vs local def.scs patching, Workshop artifacts, metadata & icon branding, Phase A diff ledger, snapshot seed & CI release flow

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Law registry layout & seasonal rules | File format (JSON vs YAML), scope beyond 36 base countries, and Summer vs Winter speed/DRL/DST date semantics | ✓ |
| Clean-room SII synthesis vs local def.scs patching | Whether Core builds synthesize all 36 .sui/speed_limits.sii cleanly from baseline JSONs in CI & locally, and def/country.sii omission | ✓ |
| Workshop artifacts, metadata & icon branding | universal/ folder vs universal.zip vs standalone mod ZIP, package_version scheme, manifest categories, and 276x162 icon style | ✓ |
| Phase A diff ledger, snapshot seed & CI release flow | How state/published.json updates after manual uploads, GitHub Releases vs Artifacts, and whether Phase 2 emits an initial realism-snapshot JSON | ✓ |

**User's choice:** Selected all 4 gray areas.

---

## Law registry layout & seasonal rules

### Question 1: Registry format and directory structure

| Option | Description | Selected |
|--------|-------------|----------|
| Per-country JSON files (`data/laws/countries/<iso2>.json` + `data/mappings/ets2_countries.json`) | Zero extra deps, strict Pydantic validation, clean single-country diffs as we scale to 200+ territories in Phase 5 | ✓ |
| Single consolidated JSON per domain | Matches baseline JSONs directly with minimal file count, though all countries share one larger file | |
| Human-editable YAML files (`data/laws/*.yaml`) | Supports inline `#` comments for legal notes, adds PyYAML/ruamel.yaml and implicit-typing quirks | |
| You decide | Pick the cleanest layout aligned with existing baseline JSON conventions | |

**User's choice:** Per-country JSON files (`data/laws/countries/<iso2>.json` + `data/mappings/ets2_countries.json`).

### Question 2: Phase 2 country/territory scope

| Option | Description | Selected |
|--------|-------------|----------|
| 36 Vanilla+DLC countries + explicit non-vanilla bug-fix entries (`AM`, `JO`, `SY`, `SM`, `SJ`) | Satisfies non-vanilla reference-mod bug entries in Phase 2 while keeping Core mod output 36 countries | |
| Strictly the 36 Vanilla+DLC countries only | Defer Armenia, Jordan, Syria, and all other non-vanilla ISO entries to Phase 4/5 | ✓ |
| All ~75 Vanilla + ProMods Europe/ME/MA/TGS countries upfront | Populates every territory seen in `3249064596` now under `data/laws/countries/` | |
| You decide | Scope `data/laws/countries/` to match Phase 2 success criteria | |

**User's choice:** Strictly the 36 Vanilla+DLC countries only ("since we will be adding vanilla stuff now doesnt it make sense to strictly add only vanilla, dlc countries only. If it wont cause much problems I think option 2 is better").
**Notes:** Unit tests in Phase 2 still verify `zoneinfo` edge cases (`Asia/Amman`/`Asia/Damascus` `UTC+3` `AST`) and `leftside_traffic` invariants cleanly without polluting `data/laws/countries/` with unused non-vanilla countries before Phases 4–5.

### Question 3: Seasonal DST anchors, speed limits, and `lights_mandatory` semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed seasonal anchor dates (July 15 / January 15) + statutory seasonal car/truck/bus deltas; year-round DRL unless seasonal-only statute | Stable DST across EU/UK/etc., avoids edge-of-month shift churn | |
| Same July 15 / January 15 anchors + explicit seasonal `lights_mandatory` flips | Models winter-only DRL statutes explicitly across the two editions | |
| Dynamic build-date `zoneinfo` lookup (or `--date` override) | Reflects current real-world date | |
| You decide (User delegated statutory realism choices to research/planning) | Pick the most deterministic seasonal rule semantics | ✓ |

**User's choice:** Delegated seasonal statutory design to research/planning (`"I play with grimes's seasonal mods like new summer, early autumn, late autumn/mild winter etc so the speed limits feature will help me and other people feel more immersed... do what you think is the best or leave it to the planner or idk research more"`).
**Notes:** Locked deterministic peak Summer (`July 15`) and Winter (`January 15`) anchors (plus optional `--date` override), and assigned `gsd-phase-researcher` to verify exact statutory Summer/Winter speed limits, seasonal DRL (`lights_mandatory`), `bus`/`truck`/`car` rules, and axle weights across all 36 Vanilla+DLC countries.

---

## Clean-room SII synthesis vs local `def.scs` patching

### Question 1: Generating the 36 `.sui` and `speed_limits.sii` files

| Option | Description | Selected |
|--------|-------------|----------|
| Pure clean-room JSON synthesis everywhere (CI and local) | Synthesize deterministically from `data/baselines/ets2_1.62_def/*.json` + `data/laws/`, ensuring identical SHA-256 hashes on CI and local Windows | ✓ |
| Hybrid: JSON synthesis in CI, optional `--game-dir` surgical `def.scs` patching locally | Preserves original SCS comments locally, though local and CI outputs have different SHA-256 hashes | |
| Require local `def.scs` surgical patching for releases | Breaks unattended Friday GitHub Actions CI | |
| You decide | Pick the clean-room approach guaranteeing reproducible CI hashes | |

**User's choice:** Pure clean-room JSON synthesis everywhere (CI and local).

### Question 2: `def/country.sii` handling & pre-Phase-3 `fuel_price`

| Option | Description | Selected |
|--------|-------------|----------|
| Omit `def/country.sii` completely & keep `1.62` baseline `fuel_price` until Phase 3 | Emit only the 36 updated `.sui` and `speed_limits.sii` files with zero map-mod country-list collisions | ✓ |
| Emit `def/country.sii` alongside the 36 `.sui` files & keep `1.62` baseline `fuel_price` | Explicit full Vanilla index, risking erasure of lower-priority map mod countries | |
| Omit `def/country.sii` & allow optional static `fuel_price` overrides in `data/laws/` | Allows optional hand-pinned diesel prices in Phase 2 | |
| You decide | Pick the safest engine behavior for Core builds | |

**User's choice:** Omit `def/country.sii` completely & keep `1.62` baseline `fuel_price` until Phase 3.

---

## Workshop artifacts, metadata & icon branding

### Question 1: Output artifact formats

| Option | Description | Selected |
|--------|-------------|----------|
| Unpacked `universal/` in `dist/workshop/{summer,winter}/` + separate `dist/local/ETS2V2_Core_{Summer,Winter}.zip` | Ready for SCS Workshop Uploader & SteamCMD without double-zipping, plus drop-in `.zip` files for local `mod/` testing | ✓ |
| Normalized `universal.zip` (`1980-01-01` timestamps) alongside `versions.sii` | Compact single archive per Workshop root | |
| Unpacked `universal/` in `dist/workshop/{summer,winter}/` only | Strict Workshop-only directory output | |
| You decide | Pick the cleanest output packaging split | |

**User's choice:** Unpacked `universal/` in `dist/workshop/{summer,winter}/` + separate `dist/local/ETS2V2_Core_{Summer,Winter}.zip`.

### Question 2: `276x162` `.jpg` Workshop icons

| Option | Description | Selected |
|--------|-------------|----------|
| Checked-in clean-room `assets/icons/{summer,winter}.jpg` generated by a `Pillow` script | Distinct Summer/Winter `276x162` cards with zero cross-OS `libjpeg` hash drift and easy custom artwork swapping | ✓ |
| Generate `276x162` `.jpg` icons on-the-fly at build time with `Pillow` | Zero binary `.jpg` files in Git; risks minor cross-platform `libjpeg` variance | |
| You decide | Pick the most deterministic approach for `276x162` Workshop icons | |

**User's choice:** Checked-in clean-room `assets/icons/{summer,winter}.jpg` generated by a `Pillow` script.

### Question 3: Workshop `manifest.sii` metadata and versioning scheme

| Option | Description | Selected |
|--------|-------------|----------|
| ISO week-based version (`"1.62-2026.47"`, bumped only on content change), categories `["other", "ai_traffic"]`, auto-generated UTF-8 `description.txt` | Clear to Steam subscribers without weekly version churn on no-op runs | ✓ |
| Semantic version (`"2.0.0"` + patch bump), category `["other"]` only, static `description.txt` | Minimal milestone version numbering | |
| You decide | Pick the cleanest Workshop `manifest.sii` metadata & versioning scheme | |

**User's choice:** ISO week-based version (bumped only on canonical content change), categories `["other", "ai_traffic"]`, auto-generated UTF-8 `description.txt` summarizing rules & `MIT` / `CC BY 4.0` attribution.

---

## Phase A diff ledger, snapshot seed & CI release flow

### Question 1: Friday `06:00 UTC` CI delivery and `state/published.json` updates

| Option | Description | Selected |
|--------|-------------|----------|
| Workflow artifacts / Draft Release + persistent Release PR for `state/published.json` | Friday CI opens/updates one Release PR with the new `state/published.json`, merged only after manual GUI Upload | ✓ |
| Direct GitHub Release + auto-commit `state/published.json` on Friday CI | Zero manual PR merge step; marks published immediately on CI build | |
| Workflow artifacts only + local CLI `mark-published` | CI never pushes branches or PRs | |
| You decide | Pick the safest Phase A workflow | |

**User's choice:** Workflow artifacts / Draft Release + persistent Release PR for `state/published.json`.

### Question 2: Per-edition SHA-256 gating and Phase 2 `realism-snapshot` emission

| Option | Description | Selected |
|--------|-------------|----------|
| Independent `summer` & `winter` hashes in `state/published.json` + emit v1 `realism-snapshot-{summer,winter}.json` now | Avoids bumping Summer when only Winter rules change, and gives Phases 3–4 a forward-compatible v1 snapshot contract | ✓ |
| Single combined hash across both editions + emit v1 `realism-snapshot-{summer,winter}.json` | Always releases both editions together | |
| Defer `realism-snapshot` JSON until Phase 3/4 and hash editions independently | Keeps Phase 2 CI artifacts strictly to mod bundles & changelogs | |
| You decide | Pick the cleanest diff-gate granularity and snapshot integration path | |

**User's choice:** Independent `summer` & `winter` hashes in `state/published.json` + emit v1 `realism-snapshot-{summer,winter}.json` now.

---

## Claude's Discretion

- Phase 2 Python subpackage names under `src/ets2v2/` (`validate/`, `package/`, registry/build modules) and updating `tests/test_cli_scaffold.py` while keeping Phase 3–5 directories blocked.
- Exact `ets2v2` CLI subcommands/flags, JSON schema fields inside `data/laws/countries/<iso2>.json`, and `Pillow` visual styling / `description.txt` wording.

## Deferred Ideas

None — discussion stayed within Phase 2 boundaries. Non-vanilla ProMods/global countries (`AM`, `JO`, `SY`, etc.) remain deferred to Phases 4–5.
