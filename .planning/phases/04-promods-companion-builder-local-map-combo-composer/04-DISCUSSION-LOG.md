# Phase 4: ProMods Companion Builder & Local Map Combo Composer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-24
**Phase:** 04-ProMods Companion Builder & Local Map Combo Composer
**Areas discussed:** ProMods registry & snapshot contract; ProMods Companion packaging & scope; compose-local load-order & CLI UX; FieldOwnershipPolicy, aliases & totems

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| ProMods registry & snapshot contract | Adding laws/prices for all ~70–80 ProMods EU+ME+MA+TGS territories into `realism-snapshot-{summer|winter}.json`, keeping `schema_version: 1`, and CI snapshot distribution | ✓ |
| ProMods Companion packaging & scope | Standalone all-in-one ProMods Edition vs layered addon above Core, modular detection of EU/ME/MA/TGS subsets, and Workshop + local output targets | ✓ |
| `compose-local` load-order & CLI UX | Discovering active load order (`game.log.txt`, `profile.sii`, explicit modlist), Steam Workshop `227300` resolution, self-exclusion on re-runs, and `--unpacked-defs` / `AEM!` policy | ✓ |
| `FieldOwnershipPolicy`, aliases & totems | Country alias matching for sub-national map slugs (`JRR`/`PJ`/ProMods microstates), axle array length-mismatch rules, multi-TZ/speed-limit guardrails, and totem defaults vs `--patch-hardcoded-totems` | ✓ |

**User's choice:** Selected all 4 gray areas.

---

## ProMods registry & snapshot contract

### Question 1: Non-vanilla ProMods (`EU + ME + MA + TGS`) territories in law registry, lockfile, and snapshots

| Option | Description | Selected |
|--------|-------------|----------|
| Add full ProMods territory laws & seeded prices now | Populate `data/laws/countries/<iso2>.json` (`vanilla_1_62: false` in mappings) + curated seed prices in `state/prices.lock.json` for all ProMods EU+ME+MA+TGS territories while Vanilla+DLC Core stays strictly 36 countries | ✓ |
| Only add `IE`/`CY`/`MT` now, defer rest to Phase 5 | Keep `data/laws/countries/` at 39 EU/EEA territories in Phase 4 and defer non-EU ProMods countries until Phase 5 | |
| Separate ProMods-only registry file | Keep `data/laws/countries/` strictly 36 vanilla countries and merge a separate `data/laws/promods/` overlay only into snapshots | |

**User's choice:** Add full ProMods territory laws & seeded prices now.

### Question 2: Representing non-vanilla territories and map-mod slug aliases in `RealismSnapshot` vs `data/mappings/`

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `schema_version: 1` frozen & store map aliases in `data/mappings/country_aliases.json` | Zero breaking change to `RealismSnapshot` (deriving `imperial_units` from `speed_unit == "mph"` for non-vanilla countries); `compose-local` loads bundled `country_aliases.json` (plus optional `--aliases` override) | ✓ |
| Bump `RealismSnapshot` to `schema_version: 2` with embedded aliases | Embed alias mappings and extra metadata directly inside `realism-snapshot-{summer|winter}.json` | |
| Additive optional fields in `schema_version: 1` | Keep `schema_version: 1` and add optional default-empty fields (`aliases: dict[str, str] = {}`) inline | |
| You decide | Pick whichever balances schema stability and offline portability best | |

**User's choice:** Keep `schema_version: 1` frozen & store map aliases in `data/mappings/country_aliases.json`.

### Question 3: CI distribution of `realism-snapshot-{summer|winter}.json` for offline local builds

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling public GitHub Release (`snapshots-latest`) + `SHA256SUMS.txt` alongside workflow artifacts | Publishes `realism-snapshot-summer.json`, `realism-snapshot-winter.json`, and `SHA256SUMS.txt` to a public rolling GitHub Release for direct unauthenticated download without bloating Git history | ✓ |
| Commit snapshots in the persistent Release PR (`state/snapshots/`) | Ships `realism-snapshot-{summer|winter}.json` directly inside the repo alongside `state/prices.lock.json` | |
| Workflow artifacts only (no GitHub Release or repo copy) | Keep `dist/snapshots/` strictly inside `phase-a-release-bundle` workflow artifact | |

**User's choice:** Rolling public GitHub Release (`snapshots-latest`) + `SHA256SUMS.txt` alongside workflow artifacts.

### Question 4: Offline snapshot loading and integrity checks in CLI

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit `--snapshot <file>` with optional SHA-256 verify + offline repo fallback + dedicated verify CLI | Consumers accept `--snapshot <path>` (validating `schema_version: 1` and optional `--checksums SHA256SUMS.txt`), fall back offline to local `data/laws` + `state/prices.lock.json` inside a repo checkout when omitted, and expose a dedicated snapshot verification command | ✓ |
| Strict `--snapshot <file>` required always | Always require an explicit `--snapshot` path for `compose-local` and ProMods builds | |
| You decide | Choose the cleanest CLI contract for both end-users and maintainers | |

**User's choice:** Explicit `--snapshot <file>` with optional SHA-256 verify + offline repo fallback + dedicated verify CLI.

---

## ProMods Companion packaging & scope

### Question 1: Standalone all-in-one ProMods Edition vs layered addon requiring Core below it

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone all-in-one ProMods Edition (replaces Core) | Contains patched vanilla + ProMods countries (preserving ProMods UK `regions[]` and map geometry), Vanilla 43-locale totems (`local_module.ets2v2_fuel.sii`), AND ProMods `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` as one single mod above ProMods Def | ✓ |
| Layered Companion Addon (requires Core below it) | Ships only ProMods-specific country deltas and `pm*_fuel` modules, requiring both Core and Companion Addon in exact priority order | |
| Support both via CLI flag | Default to standalone all-in-one with an optional `--addon-only` mode | |

**User's choice:** Standalone all-in-one ProMods Edition (replaces Core).

### Question 2: Discovering ProMods `EU`/`ME`/`MA`/`TGS` archives and handling partial installations

| Option | Description | Selected |
|--------|-------------|----------|
| Version-agnostic auto-discovery in `--mod-dir` (modular subset + `--require-all-packs`) | Auto-detect installed ProMods `def`/`defmap` archives by pattern (`EU` required; `ME`/`MA`/`TGS` included when present, with explicit per-pack path overrides), plus `--require-all-packs` for maintainer Workshop builds | ✓ |
| Always require all 4 packs (`EU + ME + MA + TGS`) | Fail immediately if any of the four ProMods `def`/`defmap` archives is absent | |
| Explicit archive paths only | No filename pattern scanning; caller always passes exact paths | |

**User's choice:** Version-agnostic auto-discovery in `--mod-dir` (modular subset + `--require-all-packs`).

### Question 3: ProMods Companion output targets, icons, and validation

| Option | Description | Selected |
|--------|-------------|----------|
| Dual targets (Workshop root + local ZIP) with dedicated ProMods icons & Offline SCS Validator | Emit both `dist/workshop/promods-{summer,winter}/` and `dist/local/ETS2V2_ProMods_{Summer,Winter}.zip`, generate checked-in `276x162` `assets/icons/promods_{summer,winter}.jpg`, and run Offline SCS Validator including 43-locale `pm_*_fuel` checks | ✓ |
| Local drop-in package only (no Workshop root) | Emit only `dist/local/ETS2V2_ProMods_{Summer,Winter}.scs`/`.zip` reusing Core icons | |
| Dual targets reusing Core icons | Emit both Workshop root and local ZIP reusing `assets/icons/{summer,winter}.jpg` | |

**User's choice:** Dual targets (Workshop root + local ZIP) with dedicated ProMods icons & Offline SCS Validator.

### Question 4: ProMods output footprint, `pm*_fuel` localization updates, and Git/IP guards

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal realism-only footprint + dynamic `pm*_fuel` key discovery | Emit only patched country `.sui`/`speed_limits.sii` (never `def/country*.sii` or unrelated ProMods files), dynamically read `key[]` sets from installed ProMods `local_module.pm*_fuel.sii`, update matched price tokens in native currencies across all 43 locales preserving unknown keys verbatim, forbid writing into tracked repo dirs, and add `@pytest.mark.local_promods` tests | ✓ |
| Hardcoded `pm*_fuel` key catalog | Maintain a static list of known `pm_fuel`/`pm_me_fuel`/`pm_tgs_fuel` keys in repo JSON | |
| You decide | Pick the safest clean-room approach for ProMods compatibility across version updates | |

**User's choice:** Minimal realism-only footprint + dynamic `pm*_fuel` key discovery.

---

## `compose-local` load-order & CLI UX

### Question 1: Active load-order discovery and local vs Steam Workshop (`227300`) archive resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Support `--game-log`, plaintext `--profile` (with `ScsC` diagnostic), and explicit `--modlist` + optional `--workshop-dir` | Parse `game.log.txt`, plaintext `SiiNunit` `profile.sii` (advising `--game-log` on `ScsC`), or a plain modlist file; resolve both `--mod-dir` and Steam Workshop `227300` dirs on top of `--game-dir` `def.scs` (or `1.62` JSON baseline fallback) | ✓ |
| Only `--game-log` and explicit `--modlist` | Skip `profile.sii` parsing entirely | |
| Scan `--mod-dir` directory alphabetically by default | Treat all archives in `--mod-dir` as active in filename order unless `--modlist` is passed | |

**User's choice:** Support `--game-log`, plaintext `--profile` (with `ScsC` diagnostic), and explicit `--modlist` + optional `--workshop-dir`.

### Question 2: Handling previously generated ETS2V2 packages in the user's active load order

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-exclude previous ETS2V2 packages by default | Detect and skip our own previous ComboPatch / Core / ProMods packages (via package marker + filename pattern) during VFS scan and log them in the report so weekly re-runs are idempotent | ✓ |
| Warn and abort unless `--ignore-self` is passed | Fail fast when an ETS2V2 package appears in the active load order | |
| Include literally (no self-exclusion) | Mount every archive verbatim; user removes old patches manually | |

**User's choice:** Auto-exclude previous ETS2V2 packages by default.

### Question 3: `AEM!`/encrypted-ZIP/`3nK` handling and `--unpacked-defs` mounting

| Option | Description | Selected |
|--------|-------------|----------|
| Warn clearly & continue by default (`+ --strict-protected`) + smart `--unpacked-defs` mounting | Report each protected archive (kind, visible `def/country*` central-dir paths, `--unpacked-defs` hint), keep patching readable maps (exit `0`), add `--strict-protected` to fail non-zero, and allow repeatable `--unpacked-defs` (in-place priority substitution for matching archive-stem subfolders, or raw `def/` override layers) | ✓ |
| Fail non-zero on any protected archive unless `--allow-partial` is passed | Stop immediately whenever an active mod is protected | |
| Always mount `--unpacked-defs` at highest priority only & warn/continue | Same warn-and-continue policy without per-archive slot substitution | |

**User's choice:** Warn clearly & continue by default (`+ --strict-protected`) + smart `--unpacked-defs` mounting.

### Question 4: `compose-local` output format, validation, and dry-run/reporting

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic local ZIP-format `.scs` + auto Offline Validator + `--dry-run` & structured JSON report | Emit normalized `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` (`manifest.sii`, `mp_mod_optional: true`, clean-room icon), run Offline Validator before writing final output, and support `--dry-run` plus `--json` / `--report-json` | ✓ |
| Minimal `.scs` output with text summary only | Emit `.scs` and concise stdout summary without `--dry-run` or JSON report options | |
| You decide | Choose the best CLI diagnostics and validation UX consistent with existing subcommands | |

**User's choice:** Deterministic local ZIP-format `.scs` + auto Offline Validator + `--dry-run` & structured JSON report.

---

## `FieldOwnershipPolicy`, aliases & totems

### Question 1: Resolving map-mod countries to `RealismSnapshot` entries and handling unmatched territories

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic 3-tier lookup (`country_aliases.json` slug -> `iso_country_code`/`country_code` -> canonical `ets2_slug`) + skip unmatched safely | Explicit slug aliases win first (handling sub-national territories cleanly), and unmatched/fictional/not-yet-covered countries are skipped untouched and listed in the compose report | ✓ |
| Match `iso_country_code` first, then alias table fallback + skip unmatched | Trust map `iso_country_code` ahead of slug aliases | |
| Strict matching (fail on unknown country) | Exit non-zero on any unmatched country unless `--allow-unmatched` is passed | |

**User's choice:** Deterministic 3-tier lookup (`country_aliases.json` slug -> `iso_country_code`/`country_code` -> canonical `ets2_slug`) + skip unmatched safely.

### Question 2: `max_of_map_and_real` axle array merge semantics for mismatched array lengths

| Option | Description | Selected |
|--------|-------------|----------|
| Element-wise `max` across `max(len(map), len(real))` with last-value carry-forward + monotonic enforcement | Mirrors ETS2's own last-element fallback: preserves every higher/extra map axle (EAA `80t`, TST `48t`, FI `105t`), upgrades shorter stale map arrays (4-axle Iceland -> 5-axle `60t`), and guarantees non-decreasing weights | ✓ |
| Preserve map array length strictly (element-wise max up to `len(map)`) | Never expand or shrink the map's array length | |
| All-or-nothing array selection | Keep whole map array if `max(map) >= max(real)`, else replace with `real` | |

**User's choice:** Element-wise `max` across `max(len(map), len(real))` with last-value carry-forward + monotonic enforcement.

### Question 3: `patch_if_single_tz`, custom speed-limit lane classes, and `imperial_units` mismatches

| Option | Description | Selected |
|--------|-------------|----------|
| Strict preservation + unit-parity guard | Skip TZ override whenever `secondary_time_zone*` is present (or `time_zone` is absent); in `speed_limits.sii` patch only matching canonical lane classes in `car`/`truck`/`bus` preserving extra custom lane classes and `train`/`tram` verbatim, skip when `speed_limits.sii` is absent, and warn+skip `speed_limits` on map vs snapshot `imperial_units` mismatch | ✓ |
| Replace `car`/`truck`/`bus` lane lists wholesale (preserving `train`/`tram` & multi-TZ) | Overwrite full `car`/`truck`/`bus` lane arrays and auto-convert `kmh`/`mph` on mismatch | |
| You decide | Pick the safest `FieldOwnershipPolicy` guardrails for arbitrary map combos | |

**User's choice:** Strict preservation + unit-parity guard.

### Question 4: Totem patching defaults in `compose-local` vs opt-in `--patch-hardcoded-totems`

| Option | Description | Selected |
|--------|-------------|----------|
| Include Vanilla + detected ProMods Zero-DDS totems by default; JRR/7RM numeric boards strictly opt-in (`--patch-hardcoded-totems`) + `--no-totems` escape hatch | Makes `zz_ETS2V2_ComboPatch_*.scs` self-contained (updating Vanilla boards + any detected ProMods `local_module.pm*_fuel.sii` across 43 locales), leaves hardcoded numeric community signs untouched unless `--patch-hardcoded-totems` is passed (rewritten to `@@fp_*_ets2v2@@` tokens), and exposes `--no-totems` | ✓ |
| Country/speed patches only by default; all totems opt-in | Only patch `def/country/` files by default | |
| Vanilla + ProMods totems always on, hardcoded numeric boards patched via literal text replacement | Write literal numbers directly into `sign_template_text` instead of `@@fp_*_ets2v2@@` tokens | |

**User's choice:** Include Vanilla + detected ProMods Zero-DDS totems by default; JRR/7RM numeric boards strictly opt-in (`--patch-hardcoded-totems`) + `--no-totems` escape hatch.

---

## Claude's Discretion

- Unlocking `src/ets2v2/merge/` in `tests/test_cli_scaffold.py` and internal module layout across `merge/`, `package/`, `registry/`, and `validate/` while preserving offline AST DAG isolation walls.
- Exact `ets2v2` CLI subcommand/flag names (`package promods`, `compose-local`, `registry snapshot-verify`), default Windows/Linux path discovery, and JSON report schema keys.
- Relaxing `CountryMappingEntry.country_id` to `int | None` for `vanilla_1_62: false` entries and defining `data/mappings/country_aliases.json` Pydantic schema.
- Clean-room Pillow artwork styling for `assets/icons/promods_{summer,winter}.jpg` and `ComboPatch` icons.

## Deferred Ideas

None — discussion stayed strictly within Phase 4 boundaries. Non-EU Tier 1/2/3 global collectors (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`, `200+` territories) and CI-only OSM (`CC BY-SA`) speed-limit drift audits remain mapped to Phase 5 (`GLB-01`..`GLB-04`); full-auto SteamCMD Workshop publishing remains deferred to V2 (`PUB-V2-01`, `PUB-V2-02`).
