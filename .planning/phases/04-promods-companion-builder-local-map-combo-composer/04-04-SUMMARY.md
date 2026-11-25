---
phase: 04-promods-companion-builder-local-map-combo-composer
plan: "04"
subsystem: local-map-combo-composer-policy-totems
tags: [field-ownership-policy, hardcoded-totems, compose-local, combo-patch, offline-validator, cli, local-promods]
dependency_graph:
  requires:
    - "04-01 (76-territory RealismSnapshot v1, CountryAliasRegistry & bundled data/mappings/country_aliases.json, unlocked src/ets2v2/merge/ with 6 AST walls)"
    - "04-02 (snapshot_to_totem_lockfile() in package/totems.py, compile_promods_fuel_locales() in merge/promods_fuel.py, assert_out_dir_not_tracked(), profile-parameterized validate_local_zip(..., profile='combo'))"
    - "04-03 (multi-source load_order.py with Workshop 227300, D-10 self-exclusion, D-11 protected diagnostics + --unpacked-defs; include-aware scanner.py; 3-tier CountryResolver in aliases.py)"
  provides:
    - "Schema-enforced FieldOwnershipPolicy merge engine (src/ets2v2/merge/policy.py): max_of_map_and_real carry-forward + monotonic axle merge, patch_if_single_tz (+ iana_timezone_override), headerless/wrapped SII envelope preservation, custom-lane & train/tram-preserving speed_limits.sii patching, and imperial_units parity guard"
    - "Opt-in --patch-hardcoded-totems detector and surgical SiiDocument rewriter (src/ets2v2/merge/hardcoded_totems.py) for verified JRR 01{a,l..r} and 7RM numeric gas signs backed by 43-locale local_module.ets2v2_fuel.sii while strictly leaving label boards, station IDs ('34.138.06'), multi-item signs, and missing-snapshot ISO2s untouched"
    - "100% offline ets2v2 compose-local orchestrator (src/ets2v2/merge/compose.py) emitting pre-write Offline-Validator-gated zz_ETS2V2_ComboPatch_{Summer|Winter}.scs with --dry-run, --strict-protected, --unpacked-defs, --no-totems, --patch-hardcoded-totems, --json, and --report-json audit reports"
    - "Clean-room 276x162 ComboPatch icon & manifest/description renderers (package/{icons,metadata,__init__}.py), complete sorted Layer 9A public merge facade (src/ets2v2/merge/__init__.py), and ets2v2 compose-local CLI wiring (src/ets2v2/cli.py)"
  affects:
    - "Phase 5 (Global 200+ territory expansion plugs directly into CountryResolver, FieldOwnershipPolicy, JRR ID numeric totems, and compose-local without schema breaks)"
tech-stack:
  added: []
  patterns:
    - "Strict frozen Pydantic v2 FieldOwnershipPolicy enforcing D-14 carry-forward monotonic axles, D-15 multi-TZ preservation, custom-lane equal-length in-place patching, and imperial_units parity guard"
    - "Opt-in allowlist + strict numeric regex (^\\d+(?:\\.\\d{1,3})?$) surgical SiiDocument editing for community fuel boards (zero dangling tokens)"
    - "Atomic temp-file staging with mandatory pre-write validate_local_zip(..., profile='combo') hard gate before os.replace() promotion and guaranteed temp cleanup on failure"
    - "Scoped HashFS direct-file listing + DirectoryArchive top-dir filtering + active-handle 3nK probing enabling 340-mod real map combos to scan offline in ~38s"
key-files:
  created:
    - src/ets2v2/merge/policy.py
    - src/ets2v2/merge/hardcoded_totems.py
    - src/ets2v2/merge/compose.py
    - tests/test_merge_policy.py
    - tests/test_hardcoded_totems.py
    - tests/test_compose_local.py
  modified:
    - src/ets2v2/package/icons.py
    - src/ets2v2/package/metadata.py
    - src/ets2v2/package/__init__.py
    - src/ets2v2/validate/invariants.py
    - src/ets2v2/vfs/dir_archive.py
    - src/ets2v2/vfs/hashfs.py
    - src/ets2v2/merge/load_order.py
    - src/ets2v2/merge/__init__.py
    - src/ets2v2/cli.py
decisions:
  - "Exempted multi-TZ map countries (carrying secondary_time_zone*) from Vanilla's 12-key locales.json whitelist on primary time_zone_name inside validate/invariants.py (combo/promods profiles) while keeping single-TZ whitelist enforcement, non-empty/non-numeric TZ validation, and monotonic axle checks strict, so map-owned primary tokens such as UMCF @@tz_aqtt@@ preserved verbatim by patch_if_single_tz pass pre-write validation cleanly."
  - "Formatted opt-in hardcoded community fuel boards without <sup> markup (integer IDR for ID, compact 2-decimal for Eurozone, native format_national_pump_price elsewhere) so custom community sign fonts such as JRR /font/sign/dot_matrix.font render reliably without unsupported tag artifacts."
  - "Added backwards-compatible DirectoryArchive(include_top_dirs=...), _BaseHashFsArchive.list_direct_files(), and _ComboScopedArchive / active-handle 3nK probing in load_order.py after real-world 340-mod @pytest.mark.local_promods profiling showed full-tree unpacked Workshop walks and per-entry ZIP/HashFS re-opens were dominating runtime."
metrics:
  duration: "54m"
  completed: "2026-11-25"
status: complete
actuals:
  tokens: 36906
  tasks: 3
  commits: 3
plan_head_before: bb8b9e9a2dea0cdc487b61016eedcd2f9abbbc54
plan_head_after: 8da00546e9c2021896e515a7c543863dd870138c
---

# Phase 4 Plan 04: `FieldOwnershipPolicy` Merge Engine, Opt-In Hardcoded Totems & Offline `ets2v2 compose-local` Composer Summary

Completed Phase 4 by delivering the schema-enforced **`FieldOwnershipPolicy`** merge engine (`src/ets2v2/merge/policy.py`), opt-in **`--patch-hardcoded-totems`** JRR/7RM numeric board rewriter (`src/ets2v2/merge/hardcoded_totems.py`), and end-to-end 100% offline **`ets2v2 compose-local`** map-combo patch composer (`src/ets2v2/merge/compose.py`, `package/{icons,metadata,__init__}.py`, complete sorted `merge/__init__.py` facade, and `cli.py` wiring) verified across 14 new unit/integration tests (`tests/test_{merge_policy,hardcoded_totems,compose_local}.py`), the full 482-test Phase 1–4 offline suite, and a live 340-mod `@pytest.mark.local_promods` dry-run audit.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Build `FieldOwnershipPolicy` merge engine (`policy.py`) with `max_of_map_and_real` axles, `patch_if_single_tz` (+ `iana_timezone_override`), headerless/wrapped SII preservation, custom-lane speed limit patching, and `imperial_units` parity guard | `cf72269` | `src/ets2v2/merge/policy.py`, `tests/test_merge_policy.py` |
| 2 | Build opt-in `--patch-hardcoded-totems` detector and surgical `SiiDocument` rewriter for JRR `01{a,l..r}` and 7RM numeric gas signs (`hardcoded_totems.py`) | `3a01340` | `src/ets2v2/merge/hardcoded_totems.py`, `tests/test_hardcoded_totems.py` |
| 3 | Build `compose_local()` orchestrator (`compose.py`), ComboPatch icon/metadata helpers, complete sorted `merge/__init__.py` facade, `ets2v2 compose-local` CLI wiring, multi-TZ validator & real-combo scan optimizations, and synthetic + `@pytest.mark.local_promods` integration tests | `8da0054` | `src/ets2v2/package/{icons,metadata,__init__}.py`, `src/ets2v2/validate/invariants.py`, `src/ets2v2/vfs/{dir_archive,hashfs}.py`, `src/ets2v2/merge/{load_order,compose,__init__}.py`, `src/ets2v2/cli.py`, `tests/test_compose_local.py` |

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `106 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **482 passed, 4 deselected, 1 warning** (all 6 AST DAG isolation walls verified green; zero `fetch`/`publish`/`httpx`/`openpyxl` imports in `src/ets2v2/merge/`)
- `uv run --offline pytest tests/test_compose_local.py -m local_promods -v`: **1 passed, 5 deselected in 38.04s** (full offline `--dry-run` audit against the maintainer's real 340-mod `D:\ETS2Data\Euro Truck Simulator 2` profile/mod stack including ProMods, RusMap, TST, UMCF, Beyond, EAA, SemEuropa, SEA, RoC, Project Japan, JRR, SRMap, RIW, and Steam Workshop `227300`)
- Clean-room Git audit: zero third-party `.scs`/`.sii`/`.sui` files staged or tracked in Git; zero new PyPI dependencies added (`pyproject.toml` and `uv.lock` unchanged).

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-04-13** | `FieldOwnershipPolicy` + `apply_country_policy()` restrict edits strictly to the 6 realism-owned fields via `CountryDataPatch`, preserve EAA `80t`/TST `48t`/FI `105t` while upgrading Iceland 4-axle `40t` -> 5-axle `60t`, skip `time_zone*` on all `secondary_time_zone*` definitions (TST Russia, UMCF Kazakhstan, EAA Brazil), preserve custom lanes (`highway_toll`, `autobahn_special`) and `train`/`tram` verbatim via equal-length in-place `patch_speed_limits()`, and skip `speed_limits.sii` with a warning on `imperial_units` parity mismatch. Verified in `tests/test_merge_policy.py` and `tests/test_compose_local.py`. |
| **T-04-14** | `patch_hardcoded_numeric_totems()` stays strictly opt-in (`False` by default), enforces `is_single_text_fuel_candidate` + strict `^\d+(?:\.\d{1,3})?$` numeric regex + explicit JRR/7RM allowlist, rejects JRR labels (`01{b..i}`), station IDs (`01{j,k}` `"34.138.06"`), multi-item exit signs, already-localized boards, and missing-snapshot ISO-2s (`ID` in 76-territory Phase 4 snapshot -> zero dangling tokens), and edits only `text:` via `SiiDocument.update_attribute_value()`. Verified in `tests/test_hardcoded_totems.py` and `tests/test_compose_local.py`. |
| **T-04-15** | `compose_local()` enforces `assert_out_dir_not_tracked()` before writing (verified rejecting `data/`, `src/`, `tests/`, `state/`), stages `.scs` output to a temporary file in `out_dir`, runs `validate_local_zip(staged_path, baseline_dir=..., profile="combo")` as a mandatory hard gate BEFORE atomic `os.replace()` promotion to `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs`, and unlinks temp files on failure. Verified in `tests/test_compose_local.py`. |
| **T-04-16** | `compose_local()` surfaces structured `ProtectedArchiveDiagnostic` warnings and exits `0` by default while aborting with `ok=False` (CLI exit `1`) and writing zero `.scs` files under `--strict-protected` whenever any protected archive remains unsubstituted; supplying stem-matched `--unpacked-defs` satisfies `--strict-protected` cleanly. Verified in `tests/test_compose_local.py`. |
| **T-04-SC** | Zero new external PyPI packages added (`pyproject.toml` and `uv.lock` unchanged). |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Multi-TZ map-owned primary `@@tz_*@@` token rejected by Vanilla 12-key whitelist in `combo` profile**
- **Found during:** Task 3 (`validate_local_zip(..., profile="combo")` integration with UMCF 5-TZ `kazakhstan.sui`)
- **Issue:** Per D-15 (`patch_if_single_tz`), multi-TZ map definitions (e.g., UMCF `kazakhstan.sui` carrying `secondary_time_zone*`) preserve their map-owned primary `time_zone_name: "@@tz_aqtt@@"` verbatim, which is backed by UMCF's own locale file rather than Vanilla 1.62's 12-key `locales.json`. `validate_combo_invariants()` previously applied the 12-key whitelist unconditionally to primary `time_zone_name`.
- **Fix:** Updated `validate_combo_invariants()` and `validate_promods_realism_invariants()` in `src/ets2v2/validate/invariants.py` to skip only the 12-key `locales.json` whitelist on multi-TZ definitions (`bool(secondary_time_zone or secondary_time_zone_area or secondary_time_zone_name)`), while retaining strict 12-key enforcement on single-TZ definitions and retaining non-empty, non-numeric TZ & monotonic axle checks on all countries.
- **Files modified:** `src/ets2v2/validate/invariants.py`
- **Commit:** `8da0054`

**2. [Rule 3 - Blocking Performance Issue] Real 340-mod combo scanning bottleneck in unpacked Workshop dirs and HashFS/ZIP 3nK probing**
- **Found during:** Task 3 (`@pytest.mark.local_promods` verification against the real 340-mod local ETS2 profile/mod folder)
- **Issue:** Walking all 50,000+ unpacked `.dds`/`.mat`/`.pmd` files in Steam Workshop `DirectoryArchive` folders, traversing full HashFS v2 root trees without prefix scoping, and probing every `def/country/*/ai/*.sii` file without an active ZIP/HashFS handle caused 340-mod combo dry-runs to stall >60s.
- **Fix:** Added backwards-compatible `include_top_dirs` scoping to `DirectoryArchive`, `list_direct_files()` to `_BaseHashFsArchive`, tightened `_RELEVANT_COUNTRY_PROBE_RE` to country registrations/fragments/`speed_limits.sii`, wrapped combo layers in `_ComboScopedArchive`, and held active archive handles during probing — bringing the full 340-mod real combo dry-run to 38.04s cleanly with zero behavior change on synthetic or Core tests.
- **Files modified:** `src/ets2v2/vfs/dir_archive.py`, `src/ets2v2/vfs/hashfs.py`, `src/ets2v2/merge/load_order.py`
- **Commit:** `8da0054`

## Known Stubs

None.

## Self-Check: PASSED

- All 6 created files (`src/ets2v2/merge/{policy,hardcoded_totems,compose}.py`, `tests/test_{merge_policy,hardcoded_totems,compose_local}.py`) and all 9 modified files exist on disk and are tracked cleanly in git.
- All 3 task commits (`cf72269`, `3a01340`, `8da0054`) are verified ancestors of `HEAD` (`plan_head_before=bb8b9e9`, `plan_head_after=8da0054`).
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, 482-test full offline `pytest`, and `@pytest.mark.local_promods` 340-mod real combo dry-run) passed with zero errors.
