---
phase: 04-promods-companion-builder-local-map-combo-composer
plan: "02"
subsystem: promods-companion-builder
tags: [promods, vfs-stack, pm-fuel-totems, clean-room-icons, offline-validator, profile-dispatch, cli]
dependency_graph:
  requires:
    - "04-01 (76-territory law registry, country_aliases.json, schema_version=1 RealismSnapshot, load_or_build_snapshot(), unlocked src/ets2v2/merge/ with 6 AST walls)"
    - "02-03/03-03 (Option 4b 43-locale Zero-DDS totems, clean-room Pillow icons, Offline SCS Workshop Validator)"
  provides:
    - "Version-agnostic ProMods EU/TGS/ME/MA def/defmap + HashFS assets auto-discovery with official Vanilla < EU < TGS < ME < MA stacking order, explicit overrides, and --require-all-packs fast failure"
    - "Dynamic 43-locale ProMods local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii compiler with module-scoped 67-prefix maps (fixing mn=ME Montenegro vs mn=MN Mongolia), Canary cni 0.92 tax factor, 5 derived grades, _v0.._v4 native formatter, and verbatim preservation of unrecognized/future keys"
    - "Checked-in clean-room 276x162 EXIF/ICC-stripped ProMods JPEG icons (assets/icons/promods_{summer,winter}.jpg), # ets2v2:managed-package manifest.sii self-exclusion comments (zero WARN 00002), and promoted public package writers"
    - "Profile-parameterized Offline SCS Validator (PackageProfile = 'core' | 'promods' | 'combo') validating ProMods UK scotland/wales regions, Armenia RHT, Iceland 60t/80 km/h, 43-locale pm*_fuel sync, and combo .sii fragments while maintaining validate ⊥ package ⊥ merge ⊥ fetch isolation"
    - "Standalone all-in-one ProMods Companion Builder (src/ets2v2/merge/promods_builder.py), centralized snapshot_to_totem_lockfile() adapter, tracked-repo --out-dir guard, and ets2v2 package promods / promods-icons / validate --profile CLI wiring"
  affects:
    - "04-03 (load-order parsers and VfsStack scanner sharing manifest marker and VFS conventions)"
    - "04-04 (compose-local reusing snapshot_to_totem_lockfile(), compile_promods_fuel_locales(), assert_out_dir_not_tracked(), and validate_local_zip(..., profile='combo'))"
tech-stack:
  added: []
  patterns:
    - "Version-agnostic regex + numeric version-tuple selection preferring non-ST EU def at equal version"
    - "Module-scoped prefix->ISO2 tables preventing cross-pack code collisions (mn: ME vs MN)"
    - "In-memory clean-room Vanilla 1.62 virtual base layer (_InMemoryBaselineArchive) when --game-dir is omitted"
    - "UTF-8-first with cp1252 fallback decoding for third-party mod SII/SUI comments, always emitting strict UTF-8 no-BOM LF SII"
    - "Profile-parameterized Offline SCS Validator (core | promods | combo) under strict Layer 8 AST isolation"
key-files:
  created:
    - src/ets2v2/merge/promods_discovery.py
    - src/ets2v2/merge/promods_fuel.py
    - src/ets2v2/merge/promods_builder.py
    - assets/icons/promods_summer.jpg
    - assets/icons/promods_winter.jpg
    - tests/test_promods_discovery.py
    - tests/test_promods_fuel.py
    - tests/test_promods_builder.py
  modified:
    - src/ets2v2/normalize/totem_format.py
    - src/ets2v2/package/builder.py
    - src/ets2v2/package/icons.py
    - src/ets2v2/package/metadata.py
    - src/ets2v2/package/totems.py
    - src/ets2v2/package/__init__.py
    - src/ets2v2/validate/models.py
    - src/ets2v2/validate/invariants.py
    - src/ets2v2/validate/workshop.py
    - src/ets2v2/validate/__init__.py
    - src/ets2v2/merge/__init__.py
    - src/ets2v2/cli.py
    - tests/test_package_icons_metadata.py
    - tests/test_validate_workshop.py
    - tests/test_validate_invariants.py
decisions:
  - "Preserved INTEGER_CURRENCY_ISO2S (4 Core countries) untouched in normalize/totem_format.py and added dedicated GBP_PENCE_ISO2S, EXTENDED_INTEGER_CURRENCY_ISO2S, and THREE_DEC_NATIONAL_ISO2S sets so Phase 3 39-territory contract assertions remain 100% intact while covering all 40 ProMods territories."
  - "Kept generate_all_icons() returning exact {'summer', 'winter'} (TRAP 4) and added separate generate_promods_icons() / render_promods_icon_bytes(), wiring ets2v2 package icons to generate both Core and ProMods icons and exposing ets2v2 package promods-icons."
  - "Embedded # ets2v2:managed-package kind=<core|promods> strictly as an SII comment inside manifest.sii (D-10, TRAP 5) so SiiDocument ignores it during attribute checks and WARN 00002 stays strictly zero."
  - "Scoped Offline SCS Validator primary time_zone_name whitelist checks in promods/combo profiles to model.time_zone_name while preserving map-owned secondary_time_zone_name[] entries (e.g., ProMods TGS @@tz_samt@@/@@tz_yekt@@/@@tz_omst@@) verbatim per D-15."
metrics:
  duration: "45m"
  completed: "2026-11-25"
status: complete
actuals:
  tokens: 50379
  tasks: 3
  commits: 3
plan_head_before: 9dee90449ae576ecd93f005c068a6fba67eaa3fe
plan_head_after: 139fc4f6cc5728e59069ff8bd6d530fc4401fcb6
---

# Phase 4 Plan 02: Standalone ProMods Companion Builder, Dynamic 43-Locale `pm*_fuel` Totems & Profile-Parameterized Offline Validator Summary

Delivered the 100% offline **ProMods Companion Builder** (`MAP-01`, `D-05`..`D-08`) producing validated standalone all-in-one **Summer (ProMods Edition)** and **Winter (ProMods Edition)** packages directly from user-installed ProMods `EU + TGS + ME + MA` `def`/`defmap` and `HashFsV1Archive` `assets` archives, complete with version-agnostic pack discovery, dynamic 43-locale `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` compilation (`1,136/1,136` real ProMods 2.85 keys verified), checked-in clean-room `276x162` ProMods icons, tracked-repo `--out-dir` refusal, profile-parameterized Offline SCS Validator (`core` | `promods` | `combo`), and `ets2v2 package promods` / `promods-icons` / `validate --profile` CLI wiring — with zero ProMods files stored in Git.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Version-agnostic ProMods `def`/`assets` discovery (`promods_discovery.py`), extended `totem_format.py`, and dynamic 43-locale `pm*_fuel` compiler (`promods_fuel.py`) | `4456a17` | `src/ets2v2/normalize/totem_format.py`, `src/ets2v2/merge/promods_discovery.py`, `src/ets2v2/merge/promods_fuel.py`, `tests/test_promods_discovery.py`, `tests/test_promods_fuel.py` |
| 2 | Clean-room ProMods icons (`assets/icons/promods_{summer,winter}.jpg`), `# ets2v2:managed-package` manifest marker, public package writers, and profile-parameterized Offline SCS Validator (`core` \| `promods` \| `combo`) | `5d3fc2c` | `src/ets2v2/package/{builder,icons,metadata,__init__}.py`, `assets/icons/promods_{summer,winter}.jpg`, `src/ets2v2/validate/{models,invariants,workshop,__init__}.py`, `tests/test_{package_icons_metadata,validate_workshop,validate_invariants}.py` |
| 3 | Centralized `snapshot_to_totem_lockfile()` adapter, standalone `promods_builder.py` with clean-room Vanilla fallback & tracked-repo guard, CLI wiring, and synthetic + `@pytest.mark.local_promods` integration tests | `139fc4f` | `src/ets2v2/package/{totems,__init__}.py`, `src/ets2v2/merge/{promods_builder,__init__}.py`, `src/ets2v2/validate/invariants.py`, `src/ets2v2/cli.py`, `tests/test_promods_builder.py` |

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `94 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **443 passed, 3 deselected** (0 failures across all Phase 1–4 offline suites, incl. all 6 AST DAG isolation walls)
- `uv run --offline pytest tests/test_promods_builder.py -m local_promods -v`: **1 passed, 5 deselected** against local `D:\ETS2Data\Euro Truck Simulator 2\mod` ProMods `2.85` / `ME 2.85` / `MA 1.05` / `TGS 1.71` archives (`promods-eu-assets-v285.scs` 1,004/1,004 keys, `promods-me-assets-v285.scs` 84/84 keys, `promods-tgs-assets-v171.scs` 48/48 keys, plus `promods-me-defmap-v285.scs`, `promods-ma-defmap-v105.scs`, `promods-tgs-defmap-v171.scs`, and `promods-ma-assets-v105.scs`, paired with a clean-room synthetic `eu_def` override because standalone `promods-eu-def` is not present in the local mod directory)
- Clean-room Git audit: zero ProMods `.scs`/`.sii`/`.sui` files staged or tracked in Git; zero new PyPI packages added.

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-04-05** | `assert_out_dir_not_tracked()` in `src/ets2v2/merge/promods_builder.py` resolves `--out-dir` and hard-refuses paths equal to or beneath `data/`, `src/`, `tests/`, `state/`, `assets/`, `.github/`, and `.git/`. Minimal realism-only footprint verified (zero `def/country*.sii`, zero `.dds`/`.tobj`, zero map sectors/models/companies, zero ProMods files in Git). |
| **T-04-06** | Every `@include` target and output path is canonicalized and validated via `parse_country_includes()`, `normalize_vfs_path()`, `validate_rel_path()`, and `ensure_contained()`, rejecting `..`, backslashes, NUL bytes, and symlink/root escapes. |
| **T-04-07** | `src/ets2v2/merge/promods_fuel.py` formats matched fuel prices strictly via `Decimal` `ROUND_HALF_UP`, escapes all emitted keys and preserved unknown values via `format_sii_string()`, enforces module-scoped prefix maps (`mn` -> `ME` Montenegro in `pm_fuel` vs `MN` Mongolia in `pm_tgs_fuel`), and gates every emitted module with `validate_sii_hygiene()` + `validate_unit_name_segments()`. |
| **T-04-08** | VFS reads go exclusively through `VfsStack`/`open_archive()` (retaining the 128 MiB decompression cap in `HashFsV1Archive`/`ZipArchive`), and `--require-all-packs` fails fast unless EU/ME/MA/TGS def/defmap + EU/ME/TGS assets are all present. |
| **T-04-SC** | Zero new external packages installed (`pyproject.toml` and `uv.lock` untouched). |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Legacy Windows-1252 comment byte in real ProMods `def/country.mideast.sii`**
- **Found during:** Task 3 (`@pytest.mark.local_promods` verification against `promods-me-defmap-v285.scs`)
- **Issue:** `promods-me-defmap-v285.scs` ships `def/country.mideast.sii` with a non-UTF-8 Windows-1252 byte (`0xc5` for `Å` in `# ... Åland`) inside a trailing comment table, causing strict `SiiDocument.parse(bytes)` to raise `SiiEncodingError`.
- **Fix:** Added `_decode_third_party_sii()` in `src/ets2v2/merge/promods_builder.py` decoding third-party SII/SUI inputs as UTF-8 first with `cp1252` (`errors="replace"`) fallback while continuing to emit and validate strict UTF-8 no-BOM LF outputs via `serialize_sii_text()` + `validate_sii_hygiene()`. Added regression coverage in `tests/test_promods_builder.py`.
- **Files modified:** `src/ets2v2/merge/promods_builder.py`, `tests/test_promods_builder.py`
- **Commit:** `139fc4f`

**2. [Rule 1 - Bug] ProMods TGS map-owned `secondary_time_zone_name[]` localization tokens rejected by Vanilla 12-key whitelist**
- **Found during:** Task 3 (`@pytest.mark.local_promods` verification against `promods-tgs-defmap-v171.scs`)
- **Issue:** `promods-tgs-defmap-v171.scs` (`def/country/russia.sui`) defines ProMods-owned `secondary_time_zone_name[]` keys (`@@tz_samt@@`, `@@tz_yekt@@`, `@@tz_omst@@`) backed by `promods-tgs-assets-v171.scs`. Per D-15, `secondary_time_zone*` is map-owned and preserved verbatim, so checking `secondary_time_zone_name[]` against Vanilla 1.62's 12-key `locales.json` whitelist in `promods`/`combo` profiles produced false positives.
- **Fix:** Updated `_check_tz_tokens_and_monotonic_axles()` in `src/ets2v2/validate/invariants.py` to enforce Vanilla's 12-key `@@tz_*@@` whitelist on primary `time_zone_name` (which ETS2V2 owns on single-TZ countries) while preserving map-owned `secondary_time_zone_name[]` entries verbatim in `promods`/`combo` profiles (leaving Core's strict Kaliningrad check untouched). Added `@@tz_yekt@@` regression coverage in `tests/test_promods_builder.py`.
- **Files modified:** `src/ets2v2/validate/invariants.py`, `tests/test_promods_builder.py`
- **Commit:** `139fc4f`

## Known Stubs

None.

## Self-Check: PASSED

- All 8 created files and 15 modified files exist on disk and are tracked cleanly in git.
- All 3 task commits (`4456a17`, `5d3fc2c`, `139fc4f`) are verified ancestors of `HEAD`.
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, 443-test offline `pytest`, and `@pytest.mark.local_promods` real ProMods 2.85 validation) passed with zero errors.
