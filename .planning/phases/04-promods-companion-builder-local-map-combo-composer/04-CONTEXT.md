# Phase 4: ProMods Companion Builder & Local Map Combo Composer - Context

**Gathered:** 2026-11-24
**Status:** Ready for planning
**Scope:** Requirements `MAP-01`, `MAP-02`, `MAP-03`, `MAP-04`, `MAP-05` (Plans `04-01` through `04-04`)

<domain>
## Phase Boundary

Phase 4 extends the clean-room V2 realism pipeline beyond Vanilla+DLC Core to **ProMods (`EU + ME + MA + TGS`)** and **arbitrary multi-map combos** while maintaining strict ProMods EULA / clean-room IP boundaries and 100% offline local composition. Specifically, it delivers:
- Versioned `schema_version: 1` `realism-snapshot-{summer|winter}.json` expansion covering all Vanilla + ProMods EU/ME/MA/TGS territories, bundled map-mod country aliases (`data/mappings/country_aliases.json`), snapshot verification CLI, and rolling public GitHub Release (`snapshots-latest`) distribution with `SHA256SUMS.txt` (`MAP-02`).
- Local **ProMods Companion Builder** producing standalone all-in-one **Summer (ProMods Edition)** and **Winter (ProMods Edition)** packages (`dist/workshop/promods-{summer,winter}/` + `dist/local/ETS2V2_ProMods_{Summer,Winter}.zip`) directly from user-installed ProMods `def`/`defmap` archives (`EU + ME + MA + TGS`), including dynamic 43-locale `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` totems, dedicated clean-room `276x162` icons, and Offline SCS Validator checks — with zero ProMods files ever committed to Git (`MAP-01`).
- Offline **`ets2v2 compose-local`** map-combo auto-composer scanning active user load orders (`--game-log`, plaintext `--profile`, or `--modlist`) across `--mod-dir` and optional Steam Workshop (`227300`) packages, resolving `.sui`/`.sii` fragments (`SEA`, `RoC`, `Project Japan`), `base/` mount prefixes (`EAA`), empty `SiiNunit { }` suppression stubs (`UMCF`, `gmc.beyond.fix`, `SemEuropa`), and country aliases into a validated `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` (`MAP-03`).
- Schema-enforced **`FieldOwnershipPolicy`** merge guardrails (`max_of_map_and_real` axle weights, `patch_if_single_tz` seasonal DST shifting, custom lane & `train`/`tram` preservation, `imperial_units` parity guard), clear `AEM!`/encrypted-ZIP/`3nK` diagnostics with smart repeatable `--unpacked-defs` support, and opt-in `--patch-hardcoded-totems` for JRR/7RM numeric boards (`MAP-04`, `MAP-05`).

Out of scope for Phase 4 (explicitly deferred to later phases):
- Non-EU Tier 1 open government fuel APIs (`US EIA`, `BR ANP`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`), Tier 2 guarded national portal scrapers (`CH`, `IS`, `MD`, `MK`, `RU`, `IL`, `SA`, `JO`, `EG`, `ZA`, `KE`, `NG`, etc.), Tier 3 `200+` global baseline expansion, and CI-only OSM `CC BY-SA` speed-limit drift audits (**Phase 5**, `GLB-01`..`GLB-04`).
- Full-auto SteamCMD Workshop publishing and hidden-item TOTP spike (**Future V2**, `PUB-V2-01`, `PUB-V2-02`).

</domain>

<decisions>
## Implementation Decisions

### 1. ProMods Registry Expansion & `RealismSnapshot` Distribution (`MAP-01`, `MAP-02`)
- **D-01 — Full ProMods Territory Laws & Seeded Lockfile Prices in Phase 4:** Populate canonical statutory law records under `data/laws/countries/<iso2>.json` (registered in `data/mappings/ets2_countries.json` with `vanilla_1_62: false`) and curated seed fuel prices in `state/prices.lock.json` for all ProMods `EU + ME + MA + TGS` territories (~75+ total Vanilla + ProMods territories, exact inventory verified on disk during Phase 4 research). Keep Vanilla+DLC Core builds strictly scoped to the `36` `vanilla_1_62: true` countries so Core Workshop packages never bloat or change scope, while `realism-snapshot-{summer|winter}.json` immediately covers all Vanilla + ProMods territories cleanly (converting non-EUR currencies via existing live FX providers in `ets2v2 fetch`). — **Reversibility:** `moderate` — cleanly bridges Phase 4 ProMods/snapshots and Phase 5's `200+` global expansion.
- **D-02 — Keep `RealismSnapshot` Frozen at `schema_version: 1` & Externalize Map Aliases:** Keep `RealismSnapshot` (`src/ets2v2/registry/snapshot.py`, locked as `one-way` in Phase 2 `D-11` and Phase 3 `D-13`) strictly at `schema_version: 1` with `extra="forbid"`. For non-vanilla countries absent from `data/baselines/ets2_1.62_def/countries.json`, derive `imperial_units` deterministically from `CountryLawRecord.speed_unit == "mph"` (continuing to assert parity against `countries.json` for `vanilla_1_62: true` entries). Store sub-national and mod-specific slug mappings (e.g., `indo_b`, `n_ireland`, `aland`, `svalbard`, `jersey`, `guernsey`, `isle_of_man`, `westbank`, `northern_cyprus`, Project Japan prefectures) in a separate bundled `data/mappings/country_aliases.json` file (overridable via `--aliases <path>` in `compose-local`). — **Reversibility:** `one-way` — preserves full `schema_version: 1` wire compatibility across Phases 2–5.
- **D-03 — Rolling Public GitHub Release (`snapshots-latest`) + `SHA256SUMS.txt`:** Extend `.github/workflows/phase-a-release.yml` (and/or a paired release step on `master`) to publish `realism-snapshot-summer.json`, `realism-snapshot-winter.json`, and `SHA256SUMS.txt` to a rolling public GitHub Release tagged `snapshots-latest` alongside the `phase-a-release-bundle` workflow artifact. This gives offline `compose-local` and ProMods users direct, unauthenticated HTTPS download links with verifiable checksums without committing weekly snapshot JSONs into Git history.
- **D-04 — Offline Snapshot Loading, Verification & Repo Checkout Fallback:** Both the ProMods builder and `ets2v2 compose-local` accept `--snapshot <path>` (validating `schema_version: 1` via `RealismSnapshot.model_validate_json` and optionally verifying integrity against `--checksums <SHA256SUMS.txt>` or a sibling checksum manifest). When `--snapshot` is omitted inside a local repository checkout, fall back 100% offline to building the snapshot in-memory from `data/laws/` + `state/prices.lock.json` for the requested `--season`. Expose a dedicated snapshot verification CLI subcommand (e.g., `ets2v2 registry snapshot-verify` / `ets2v2 snapshot verify`) for air-gapped auditing.

### 2. ProMods Companion Packaging, Scope & Clean-Room Boundaries (`MAP-01`)
- **D-05 — Standalone All-in-One ProMods Edition (Replaces Core):** Build **Summer (ProMods Edition)** and **Winter (ProMods Edition)** as **standalone all-in-one replacements** for Vanilla+DLC Core — not layered addons requiring Core below them. Each ProMods Edition ships surgically patched Vanilla + ProMods `def/country/<slug>.sui` & `speed_limits.sii` (preserving ProMods `uk.sui` `scotland`/`wales` regions and ProMods country geometry), Vanilla `def/sign/board/*.sii` + 43-locale `local_module.ets2v2_fuel.sii`, AND ProMods 43-locale `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` so ProMods users enable **one single mod** above ProMods Def with zero Core-above-ProMods clobber risk. — **Reversibility:** `costly` — defines Workshop listing semantics and Mod Manager placement instructions.
- **D-06 — Version-Agnostic Auto-Discovery with Modular Subsets & `--require-all-packs`:** Auto-discover installed ProMods `def` / `defmap` archives in `--mod-dir` using version-agnostic filename matching (handling future ProMods version bumps cleanly beyond `v284`/`v104`/`v170`, plus explicit per-pack path overrides `--promods-eu`, `--promods-me`, `--promods-ma`, `--promods-tgs`). Require ProMods `EU` def by default and include `ME`, `MA`, and `TGS` automatically whenever present; provide `--require-all-packs` so official maintainer Workshop builds fail fast if any of the 4 ProMods packs is missing.
- **D-07 — Dual ProMods Packaging Targets, Dedicated Icons & Validator Coverage:** Mirror Core's dual-target layout (`02-CONTEXT` `D-06`/`D-07`/`D-09`) by emitting both:
  - Unpacked Workshop Uploader roots under `dist/workshop/promods-summer/` and `dist/workshop/promods-winter/` (`versions.sii` with single `.universal`, `universal/`, `manifest.sii` with `mp_mod_optional: true` and no `display_name`/`compatible_versions[]`).
  - Drop-in local ZIPs under `dist/local/ETS2V2_ProMods_Summer.zip` and `dist/local/ETS2V2_ProMods_Winter.zip` (normalized `1980-01-01` timestamps, POSIX `0o644` permissions).
  - Checked-in clean-room `276x162` EXIF/ICC-stripped JPEG icons (`assets/icons/promods_summer.jpg`, `assets/icons/promods_winter.jpg`) generated by `ets2v2 package icons`.
  - Offline SCS Validator enforcement covering `00001`–`00010`, `WARN 00001`/`00002`, Zero-DDS, ProMods UK `regions[]` preservation, and exact 43-locale sync across `local_module.ets2v2_fuel.sii` and emitted `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` modules.
- **D-08 — Minimal Realism-Only Footprint, Dynamic `pm*_fuel` Key Discovery & Git/IP Guards:**
  - Emit **strictly** patched country `.sui` / `speed_limits.sii`, Vanilla totem boards/locales, and ProMods `local_module.pm*_fuel.sii` — never copying `def/country.sii`, `def/country.promods*.sii`, map sectors, models, companies, or unpatched ProMods assets.
  - Read exact `key[]` sets dynamically from the user's installed ProMods `locale/<lang>/local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` files, update every matched fuel-price key in native local currency formatting from the snapshot across all **43** active ETS2 `1.62` locales (`fr_qc` excluded, `fr_ca` synced), and preserve any unrecognized/non-price keys verbatim so ProMods updates never break totems.
  - Refuse `--out-dir` paths inside tracked repository directories (`data/`, `src/`, `tests/`, `state/`) to guarantee zero ProMods files ever enter Git. Run CI tests against clean-room synthetic ProMods fixtures and mirror Phase 1's `@pytest.mark.local_ets2` with `@pytest.mark.local_promods` for optional verification against local `D:\ETS2Data\Euro Truck Simulator 2\mod`.

### 3. `ets2v2 compose-local` Load-Order Discovery, Protection & CLI UX (`MAP-03`, `MAP-05`)
- **D-09 — Multi-Source Load-Order Resolution (`--game-log`, `--profile`, `--modlist`) + Workshop `227300`:** Support three deterministic load-order inputs for `ets2v2 compose-local`:
  1. `--modlist <file>` — explicit line-delimited archive/mod list (ordered top-to-bottom or bottom-to-top per documented convention).
  2. `--game-log <path>` — plaintext ETS2 `game.log.txt` parsing mounted local `mod/` and Steam Workshop (`227300`) packages in exact engine mount order (works cleanly even when `profile.sii` is `ScsC`-encrypted).
  3. `--profile <path>` — plaintext `SiiNunit` `profile.sii` `active_mods[]` parser; if the file starts with an encrypted `ScsC` header, never attempt decryption — emit an actionable error advising `--game-log` or setting `g_save_format 2`.
  Resolve mounted packages across `--mod-dir` and optional `--workshop-dir` (`.../steamapps/workshop/content/227300`), layered cleanly on top of `--game-dir` `def.scs` (or clean-room `data/baselines/ets2_1.62_def/` fallback when `--game-dir` is not supplied).
- **D-10 — Automatic Self-Exclusion for Idempotent Weekly Re-Runs:** Automatically detect and exclude previously generated ETS2V2 packages (`zz_ETS2V2_ComboPatch_*`, `ETS2V2_Core_*`, `ETS2V2_ProMods_*` via filename pattern and/or an embedded ETS2V2 marker in `manifest.sii` / metadata) from the scanned input VFS stack by default, recording each skipped self-package in the compose report so players can re-run `compose-local` weekly without disabling last week's patch in Mod Manager first.
- **D-11 — Protected Archive (`AEM!`/Encrypted ZIP/`3nK`) Warning Policy & Smart `--unpacked-defs`:**
  - Never decrypt or crack `AEM!`, `3nK`, or password-encrypted ZIP archives. Emit structured diagnostics naming each protected archive, its protection kind, any visible `def/country*` or `def/sign/board*` paths discovered from unencrypted ZIP central directories, and an actionable `--unpacked-defs` hint.
  - Default to **warn clearly and continue** patching all readable layers (exit `0`) so map combos with plain-ZIP fix packs above encrypted bases (e.g., `gmc.beyond.fix` above `Beyond_by_TerraMaps`) work seamlessly; provide `--strict-protected` to exit non-zero when an operator requires hard failure on any protected archive.
  - Support repeatable `--unpacked-defs <dir>`: if `<dir>` contains per-archive subdirectories matching protected archive stems, substitute them **in-place at the protected archive's exact load-order priority**; if `<dir>` is a raw unpacked mod tree (`def/` / `locale/` directly at root), mount it as an explicit override layer in the stack.
- **D-12 — Local `.scs` Output, Pre-Write Offline Validation & Audit Reporting:** Emit deterministic local ZIP-format `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` (`1980-01-01` normalized timestamps, POSIX `0o644` permissions, `manifest.sii` with `display_name` and `mp_mod_optional: true`, clean-room icon). Run Offline Validator checks (SII hygiene, Zero-DDS, 43-locale sync, manifest integrity) before finalizing output. Expose `--dry-run` (compute & audit without writing `.scs`) and `--json` / `--report-json <path>` reporting every resolved country, winning mod layer, `FieldOwnershipPolicy` action, unmatched/skipped territory, and protected-archive diagnostic.

### 4. `FieldOwnershipPolicy`, Country Aliases & Totem Controls (`MAP-04`, `MAP-05`)
- **D-13 — Deterministic 3-Tier Country Alias Resolution & Safe Unmatched Skipping:** Match each active map country discovered through `VfsStack` (`def/country*.sii` `@include` graph respecting `.sui`/`.sii` fragments, `base/` mounts, and empty `SiiNunit { }` suppression stubs) against the loaded `RealismSnapshot` using a strict 3-tier order:
  1. Exact slug override in `data/mappings/country_aliases.json` (plus optional `--aliases` file) — handles sub-national & microstate slugs (`indo_b`, `indo_th`, `indo_tm`, Project Japan prefectures, `n_ireland`, `aland`, `svalbard`, `jersey`, `guernsey`, `isle_of_man`, `northern_cyprus`, `transnistria`, `westbank`, etc.) cleanly even when a map mod sets an unexpected `iso_country_code`.
  2. Exact `iso_country_code` (ISO3) or `country_code` (ISO2) match against snapshot countries.
  3. Canonical `ets2_slug` match against snapshot countries.
  Any country still unmatched (e.g., fictional maps or global territories awaiting Phase 5's `200+` expansion) is **skipped untouched** and recorded clearly in the compose report — never crashing or corrupting map files.
- **D-14 — `max_of_map_and_real` Axle Merge Semantics (`mass_limit_per_axle_count[]`):** Merge map and snapshot axle mass arrays across `N = max(len(map), len(real))` by taking element-wise `max(map_val(i), real_val(i))` with last-value carry-forward (`arr[min(i, len(arr)-1)]`, matching ETS2's own fallback semantics for higher axle counts) followed by monotonic non-decreasing enforcement (`out[i] = max(out[i], out[i-1])`). This guarantees extra/higher map axles are never downgraded (EAA `80t`, RusMap/TST `48t`, Finland `105t`) while stale shorter map arrays are safely upgraded (4-axle `40t` Iceland -> 5-axle `60t`).
- **D-15 — `patch_if_single_tz`, Custom Lane Preservation & `imperial_units` Parity Guard:**
  - **Timezones (`patch_if_single_tz`):** Skip `time_zone` and `time_zone_name` updates whenever the resolved `country_data` unit defines `secondary_time_zone` or `secondary_time_zone_area` (preserving TST `27`-TZ Russia, UMCF `5`-TZ Kazakhstan, EAA Brazil) OR omits `time_zone` entirely. Patch seasonal DST offsets/names strictly on single-TZ definitions.
  - **Map-owned identity/geometry:** Never mutate `country_id`, `name`, `name_localized`, `country_code`, `iso_country_code`, `pos`, `regions[]`, `region_areas[]`, `secondary_time_zone*`, `leftside_traffic`, `imperial_units`, `trailer_standalone`, or `train`/`tram` speed blocks.
  - **Speed limits (`speed_limits.sii`):** Surgically patch only matching canonical lane classes (`local_road`, `expressway`, `motorway`, `slow_road`) inside `car`/`truck`/`bus`, preserving any map-added custom lane classes and `train`/`tram` units verbatim. Skip `speed_limits.sii` if absent from the map's VFS. Enforce an **`imperial_units` parity guard**: if the map country's `imperial_units` flag disagrees with the snapshot country's `imperial_units`, emit a warning and skip `speed_limits.sii` patching rather than writing `km/h` numbers into an `mph` country (or vice versa).
- **D-16 — Self-Contained Combo Totems by Default, Opt-In `--patch-hardcoded-totems` & `--no-totems`:**
  - By default, `ets2v2 compose-local` makes `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` self-contained for fuel totems: it emits Vanilla `1.62` Option 4b Zero-DDS boards + 43-locale `local_module.ets2v2_fuel.sii` AND dynamically updates any ProMods `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` detected in the active VFS stack across all 43 locales.
  - Hardcoded numeric community map boards (e.g., JRR `indo_gas_totem_01a.sii` / 7RM numeric gas signs) remain **untouched by default** and are rewritten only when `--patch-hardcoded-totems` is explicitly passed — rewriting matched numeric boards cleanly to namespaced `@@fp_*_ets2v2@@` tokens backed by `local_module.ets2v2_fuel.sii` across all 43 locales while leaving ambiguous/non-matching signs untouched.
  - Provide `--no-totems` as an escape hatch for users who want `def/country/` realism patches only alongside a third-party sign/totem mod.

### Claude's Discretion
- Unlocking `src/ets2v2/merge/` in `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` and exact internal module layout across `src/ets2v2/merge/`, `src/ets2v2/package/`, `src/ets2v2/registry/`, and `src/ets2v2/validate/` while preserving the acyclic DAG and offline AST isolation walls (`test_offline_dag_isolation.py`).
- Exact `ets2v2` CLI subcommand and flag names (e.g., `ets2v2 package promods`, `ets2v2 compose-local`, `ets2v2 registry snapshot-verify`), default path discovery on Windows/Linux, and JSON report schema field names.
- Exact `CountryMappingEntry.country_id` relaxation (`int | None`, required when `vanilla_1_62: true`, optional when `vanilla_1_62: false`) and `data/mappings/country_aliases.json` Pydantic schema.
- Exact `Pillow` typography/badge styling for `assets/icons/promods_{summer,winter}.jpg` and `ComboPatch` icon artwork.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or executing Phase 4:**

### Project & Milestone Specs
- `.planning/PROJECT.md` — Core value, Option C distribution model, ProMods IP boundary, and `FieldOwnershipPolicy` contract.
- `.planning/REQUIREMENTS.md` — Requirements `MAP-01`, `MAP-02`, `MAP-03`, `MAP-04`, `MAP-05` and Out-of-Scope exclusions.
- `.planning/ROADMAP.md` — Phase 4 goal, 4 success criteria, research flag (`gsd-phase-researcher` recommended), and plan breakdown (`04-01`..`04-04`).
- `.planning/STATE.md` — Locked decisions and local operational dependency (`D:\ETS2Data\Euro Truck Simulator 2\mod` ProMods + combo archives).
- `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-CONTEXT.md` — VFS stack (`base/`, empty stubs, `AEM!`/`3nK`/encrypted ZIP), surgical SII/SUI engine, and clean-room JSON-only `data/` boundary.
- `.planning/phases/02-realism-registry-seasonal-core-builds-offline-validator-phase-a/02-CONTEXT.md` — Registry layout, dual packaging (`dist/workshop/` + `dist/local/`), Offline SCS Validator (`00001`–`00010`), and locked `schema_version: 1` `RealismSnapshot` (`D-11`).
- `.planning/phases/03-open-european-fuel-fx-pipeline-zero-dds-totem-engine/03-CONTEXT.md` — `state/prices.lock.json` 39-territory lockfile, `RealismSnapshot` v1 preservation (`D-13`), canonical grade keys (`D-14`), Option 4b 43-locale Zero-DDS totems, and Offline SCS Validator totem invariants (`D-12`).

### Research & Codebase Maps
- `.planning/research/ARCHITECTURE.md` — Field-Ownership Contract, ETS2 engine rules (`.sui` vs `.sii` fragments, `base/` mounts, empty `{}` suppression stubs, file-scoped `.speed_limit.*`, no `mod_<id>/`), and 503-mod combo census edge cases.
- `.planning/research/FEATURES.md` — ProMods country deltas (`uk.sui` `scotland`/`wales`, `armenia`, `jordan`, `syria`, `svalbard`, `sanmarino`), `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` observations, and JRR/7RM numeric totem findings.
- `.planning/research/PITFALLS.md` — Duplicate `country_id` / `country.data.*` crashes, SCS validation rules, `3nK`/`AEM!`/encrypted ZIP hazards, and multi-TZ / axle clobber traps.
- `.planning/research/SUMMARY.md` — Synthesized 503-mod census, Option C tradeoffs, and Phase 4 research flags.
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/STRUCTURE.md` — Acyclic package DAG, VFS/SII abstractions, and clean-room constraints.

### Existing Code & Schemas
- `src/ets2v2/vfs/stack.py`, `src/ets2v2/vfs/hashfs.py`, `src/ets2v2/vfs/zip_archive.py`, `src/ets2v2/vfs/dir_archive.py`, `src/ets2v2/vfs/types.py` — Multi-layer VFS overlay, `base/` flattening, `empty_stub_paths()`, `ProtectedArchiveStub`, encrypted ZIP central-directory inspection, and `ArchiveDiagnostic`.
- `src/ets2v2/sii/country.py`, `src/ets2v2/sii/speed_limits.py`, `src/ets2v2/sii/document.py`, `src/ets2v2/sii/sign_board.py`, `src/ets2v2/sii/localization.py`, `src/ets2v2/sii/hygiene.py` — Surgical SII/SUI patching (`patch_country_data`, `patch_speed_limits`, `parse_country_includes`, `parse_sign_board`, `parse_localization_db`, `validate_sii_hygiene`).
- `src/ets2v2/registry/models.py`, `src/ets2v2/registry/loader.py`, `src/ets2v2/registry/snapshot.py`, `src/ets2v2/registry/timezone.py` — Law registry models, loader, and locked `schema_version: 1` `RealismSnapshot`.
- `src/ets2v2/normalize/models.py`, `src/ets2v2/normalize/currencies.py`, `src/ets2v2/normalize/totem_catalog.py`, `src/ets2v2/normalize/totem_format.py` — `PricesLockfile`, currency metadata, and native-currency 6-font SDF totem formatting.
- `src/ets2v2/package/builder.py`, `src/ets2v2/package/totems.py`, `src/ets2v2/package/icons.py`, `src/ets2v2/package/metadata.py` — Core packaging, Option 4b totem compiler, Pillow `276x162` icons, and `manifest.sii`/`description.txt` generators.
- `src/ets2v2/validate/workshop.py`, `src/ets2v2/validate/invariants.py`, `src/ets2v2/validate/models.py` — Offline SCS Workshop/local ZIP validator and `1.62` invariants.
- `src/ets2v2/publish/release.py`, `.github/workflows/phase-a-release.yml` — Phase A release pipeline emitting `dist/snapshots/realism-snapshot-{summer|winter}.json`.
- `.agents/skills/scs-modding-wiki/docs/engine/units.md` & `.agents/skills/scs-modding-wiki/docs/engine/mod_manager.md` — SCS unit scoping, `@include`, and local vs Workshop `manifest.sii` contracts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ets2v2/vfs/stack.py` (`VfsStack`, `VfsLayer`, `EffectiveVfsEntry`, `empty_stub_paths`, `diagnostics`) — Already implements priority-ordered multi-layer resolution, `base/` mount normalization, `dlc_<id>/` scoping, empty `SiiNunit {}` stub detection, and aggregated `ArchiveDiagnostic` reporting; directly powers both the ProMods Companion Builder and `ets2v2 compose-local`.
- `src/ets2v2/sii/country.py` (`parse_country_includes`, `parse_country_data`, `patch_country_data`, `CountryDataPatch`) & `src/ets2v2/sii/speed_limits.py` (`parse_speed_limits`, `patch_speed_limits`) — Already implement comment-, region-, `secondary_time_zone*`-, and `train`/`tram`-preserving surgical SII/SUI edits ready for `FieldOwnershipPolicy` orchestration.
- `src/ets2v2/normalize/totem_format.py` & `src/ets2v2/package/totems.py` — Existing 6-font native-currency formatter and 43-locale `local_module.ets2v2_fuel.sii` / `def/sign/board/*.sii` compiler reusable directly by ProMods builds and `compose-local`.
- `src/ets2v2/validate/workshop.py` (`validate_workshop_package`, `validate_local_zip`) — Reusable Offline SCS Validator ready to parameterize/extend for ProMods Edition (`pm_*_fuel` locales, ProMods country set) and `zz_ETS2V2_ComboPatch_*.scs` local validation.

### Established Patterns
- Frozen Pydantic v2 models (`ConfigDict(strict=True, frozen=True, extra="forbid")`), deterministic UTF-8 no-BOM LF sorted JSON, strict `basedpyright` (`strict` mode, Python `3.12`), `ruff` (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`), and 100% offline PR CI (`uv run --offline pytest`).
- AST offline DAG isolation tests (`tests/test_offline_dag_isolation.py`) ensuring `merge/`, `package/`, `registry/`, `validate/`, `sii/`, and `vfs/` never import `httpx` or `ets2v2.fetch`.
- `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` gates active subpackages under `src/ets2v2/` — Phase 4 unlocks `src/ets2v2/merge/`!
- `@pytest.mark.local_ets2` pattern (`tests/test_baseline_contracts.py`) auto-skipping local-archive integration tests in CI while running full verification locally when archives exist.

### Integration Points
- `data/laws/countries/<iso2>.json`, `data/mappings/ets2_countries.json`, `data/mappings/country_aliases.json`, `state/prices.lock.json` — Expanded to cover all Vanilla + ProMods `EU + ME + MA + TGS` territories and map-combo slug aliases while keeping Core strictly 36 countries.
- `src/ets2v2/merge/` (new Phase 4 subpackage) — `FieldOwnershipPolicy` engine, load-order parsers (`game.log.txt`, plaintext `profile.sii`, modlist), ProMods package discovery & `pm*_fuel` updater, and `compose-local` orchestrator.
- `src/ets2v2/package/` & `src/ets2v2/validate/` — ProMods dual-target packager, dedicated `promods_{summer,winter}.jpg` icons, local `.scs` combo packager, and extended Offline Validator checks.
- `src/ets2v2/cli.py` — Wire `compose-local`, ProMods builder subcommand, and snapshot verification subcommand onto `build_parser()`.
- `.github/workflows/phase-a-release.yml` — Emit `SHA256SUMS.txt` and publish `realism-snapshot-{summer|winter}.json` + `SHA256SUMS.txt` to the rolling public `snapshots-latest` GitHub Release.

</code_context>

<specifics>
## Specific Ideas

- **Research targets for `gsd-phase-researcher` (read-only inspection of local archives without committing any ProMods/third-party files to Git):**
  - Inspect exact country definitions, `country_id`s, `iso_country_code`s, `regions[]` (incl. UK `scotland`/`wales`), `speed_limits.sii`, and `locale/<lang>/local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` key schemas across local ProMods archives (`promods-eu-def-v284.scs`, `promods-me-defmap-v284.scs`, `promods-ma-defmap-v104.scs`, `promods-tgs-defmap-v170.scs`) under `D:\ETS2Data\Euro Truck Simulator 2\mod` to obtain the exact ProMods territory inventory, statutory road rules, currencies, and `pm*_fuel` key naming conventions.
  - Inspect real ETS2 `1.62.3.3s` `game.log.txt` mount log lines (`[mod_package_manager]`, `[zipfs]`, `[hashfs]`, Steam Workshop `227300` paths, mount ordering top-vs-bottom) and plaintext `profile.sii` `active_mods[]` formatting (including `mod_workshop_package.<hex>` decimal conversion) so load-order parsing matches ETS2's exact engine precedence.
  - Inspect real map-combo edge cases in `D:\ETS2Data\Euro Truck Simulator 2\mod` (`RusMap`, `TST`, `UMCF`, `gmc.beyond.fix`, `EAA`, `SemEuropa`, `SEA`, `RoC`, `Project Japan Relocated`, `JRR`, `7RM`) to confirm exact country slugs for `data/mappings/country_aliases.json`, `base/` mount paths, empty `SiiNunit { }` stub paths, and JRR/7RM numeric fuel totem board signatures (`def/sign/board/*.sii`) for `--patch-hardcoded-totems`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed strictly within Phase 4 boundaries. Global Tier 1 non-EU fuel APIs (`US`, `BR`, `AR`, `CO`, `CL`, `MY`, `JP`, `KR`), Tier 2 guarded national portal scrapers, Tier 3 `200+` global baselines, and CI-only OSM (`CC BY-SA`) speed-limit drift audits remain mapped to Phase 5 (`GLB-01`..`GLB-04`); full-auto SteamCMD Workshop publishing remains deferred to V2 (`PUB-V2-01`, `PUB-V2-02`).

</deferred>

---

*Phase: 04-promods-companion-builder-local-map-combo-composer*
*Context gathered: 2026-11-24*
