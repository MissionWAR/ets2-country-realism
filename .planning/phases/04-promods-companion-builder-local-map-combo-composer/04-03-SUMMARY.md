---
phase: 04-promods-companion-builder-local-map-combo-composer
plan: "03"
subsystem: local-combo-load-order-scanner-aliases
tags: [load-order, workshop-227300, self-exclusion, protected-archives, unpacked-defs, vfs-scanner, country-aliases, semeuropa-shield]
dependency_graph:
  requires:
    - "04-01 (76-territory RealismSnapshot v1, CountryAliasRegistry & bundled data/mappings/country_aliases.json, unlocked src/ets2v2/merge/ with 6 AST walls)"
    - "04-02 (ETS2V2_MANIFEST_MARKER in package/metadata.py, PM_FUEL_MODULES in merge/promods_fuel.py, cp1252 third-party SII decoding insight)"
  provides:
    - "Multi-source ETS2 load-order parsers (--profile with ScsC refusal, --game-log active mounts taking last session and ignoring startup scans, --modlist top-to-bottom/bottom-to-top) and Workshop 227300 versions.sii 1.62/universal package selector (src/ets2v2/merge/load_order.py)"
    - "In-memory clean-room BaselineVirtualArchive fallback (36 Vanilla 1.62 countries + def/country.sii), automatic D-10 ETS2V2 self-exclusion (filename regex + manifest.sii marker), and D-11 AEM!/encrypted-ZIP/3nK diagnostics + smart repeatable --unpacked-defs (in-place stem substitution + raw def/ override mounting)"
    - "Include-aware VfsStack country & speed-limits scanner handling headerless/wrapped .sii fragments (SEA/RoC/PJ), .sui fragments, EAA base/ mounts, empty SiiNunit {} suppression stubs (UMCF/Beyond/SemEuropa), cp1252 legacy comments, cycle guards, protected payload resilience, and active pm*_fuel detection (src/ets2v2/merge/scanner.py)"
    - "Deterministic pre-indexed 3-tier CountryResolver (Tier 1 bundled + user --aliases with iana_timezone_override and SemEuropa Brazilian state collision shield -> Tier 2 ISO3/ISO2 -> Tier 3 canonical slug -> unmatched skipped untouched) (src/ets2v2/merge/aliases.py)"
  affects:
    - "04-04 (compose-local orchestrator composing load_order, scanner, aliases, FieldOwnershipPolicy, totems, and ComboPatch .scs output)"
tech-stack:
  added: []
  patterns:
    - "Bounded <= 64 MiB text reads and strict resolve().is_relative_to() containment on Workshop versions.sii and --unpacked-defs"
    - "Zero-decryption ScsC refusal (EncryptedProfileError) and central-directory-only encrypted ZIP inspection plus 3nK country probing"
    - "Smart repeatable --unpacked-defs classification: in-place stem-matched substitution preserving exact load-order priority vs raw def/locale root override"
    - "UTF-8-first with cp1252 fallback decoding for third-party mod SII/SUI comments alongside doc.has_siinunit envelope detection"
    - "Tier 1 hard-stop alias semantics preventing sub-national Brazilian state ISO-2 codes from falling through to European/North African sovereign territories"
key-files:
  created:
    - src/ets2v2/merge/load_order.py
    - src/ets2v2/merge/scanner.py
    - src/ets2v2/merge/aliases.py
    - tests/test_merge_load_order.py
    - tests/test_merge_scanner.py
    - tests/test_merge_aliases.py
  modified: []
decisions:
  - "Reused ETS2V2_MANIFEST_MARKER directly from ets2v2.package.metadata in ets2v2.merge.load_order so D-10 self-exclusion marker detection shares a single canonical constant across Core, ProMods, and ComboPatch builders."
  - "In parse_game_log(), delayed session clearing until a new mount follows a [mod_package_manager] unmount boundary (session_ended flag) so normal game-shutdown unmounts at the end of game.log.txt never wipe the final active profile session while profile switches cleanly replace earlier sessions."
  - "Added lightweight <= 1 MiB def/country* 3nK\\x01 probing in build_combo_vfs_stack() so 3nK-obfuscated archives are immediately surfaced in ProtectedArchiveDiagnostic and eligible for in-place --unpacked-defs substitution before scanning."
  - "Applied UTF-8-first with cp1252 fallback decoding in scanner.py (matching promods_builder.py) and detected has_siinunit_envelope strictly from SiiDocument.has_siinunit rather than file extension so headerless SEA/RoC/Project Japan .sii fragments round-trip cleanly."
metrics:
  duration: "58m"
  completed: "2026-11-25"
status: complete
actuals:
  tokens: 24470
  tasks: 3
  commits: 3
plan_head_before: b2c027025e7efe3780dc9a25692a1f932525e352
plan_head_after: 7624564654cee5d59021d8d4cbc944a38d588c53
---

# Phase 4 Plan 03: Multi-Source Load-Order, Include-Aware `VfsStack` Scanner & 3-Tier Country Alias Resolver Summary

Delivered the 100% offline load-order, `VfsStack` country-graph scanning, and deterministic 3-tier country resolution core for `ets2v2 compose-local` (`MAP-03`, `D-09`, `D-10`, `D-11`, `D-13`) across `src/ets2v2/merge/{load_order,scanner,aliases}.py` with 25 new unit and synthetic multi-layer VFS tests (`tests/test_merge_{load_order,scanner,aliases}.py`), maintaining strict `basedpyright` compliance (`0` errors, `0` warnings, zero `# type: ignore`) and all 6 AST-enforced offline DAG isolation walls.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Multi-source load-order parsers (`--profile` + `ScsC` guard, `--game-log`, `--modlist`), Workshop `227300` `versions.sii` resolver, `BaselineVirtualArchive` fallback, `D-10` self-exclusion, and `D-11` protected diagnostics + smart `--unpacked-defs` | `c8b4287` | `src/ets2v2/merge/load_order.py`, `tests/test_merge_load_order.py` |
| 2 | Include-aware `VfsStack` country & `speed_limits.sii` scanner handling headerless/wrapped `.sii` & `.sui` fragments, `base/` mounts, empty `SiiNunit {}` stubs, `cp1252` comments, cycle guards, protected payloads, and `pm*_fuel` detection | `f4b3085` | `src/ets2v2/merge/scanner.py`, `tests/test_merge_scanner.py` |
| 3 | Deterministic pre-indexed 3-tier `CountryResolver` (`merge_alias_registries`, `iana_timezone_override`, SemEuropa 27-state ISO-2 collision shield, safe unmatched skipping) | `7624564` | `src/ets2v2/merge/aliases.py`, `tests/test_merge_aliases.py` |

## Verification Results

- `uv run --offline ruff check`: `All checks passed!`
- `uv run --offline ruff format --check`: `100 files already formatted`
- `uv run --offline basedpyright`: `0 errors, 0 warnings, 0 notes` (strict mode, zero `# type: ignore`)
- `uv run --offline pytest tests/test_merge_load_order.py tests/test_merge_scanner.py tests/test_merge_aliases.py tests/test_cli_scaffold.py -x -q --tb=short`: **37 passed** (all 6 AST DAG isolation walls verified green; zero `fetch`/`publish`/`httpx`/`openpyxl` imports in `src/ets2v2/merge/`)
- `uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"`: **468 passed, 3 deselected** (zero failures across all Phase 1–4 offline suites)

## Threat Mitigations Verified

| Threat ID | Mitigation Verified |
|-----------|---------------------|
| **T-04-09** | `resolve_workshop_package_path()` enforces strict ASCII-digit IDs, rejects `..`/NUL/slashes/drive letters in `versions.sii` `package_name`, and verifies `resolve().is_relative_to(item_dir)`. `_classify_unpacked_defs()` enforces containment on child directories and delegates reads to symlink-contained `DirectoryArchive`. `_resolve_include_target()` + `parse_country_includes()` reject `..`/NUL bytes in `@include` targets. Zero shell execution on user filenames. |
| **T-04-10** | `parse_profile_sii()` immediately raises `EncryptedProfileError` on `b"ScsC"` headers with `--game-log` / `g_save_format 2` guidance without decrypting. `build_combo_vfs_stack()` never decrypts `AEM!`, `3nK`, or encrypted ZIPs, inspecting only unencrypted ZIP central-directory `def/country*` & `def/sign/board*` paths and emitting actionable `--unpacked-defs` diagnostics. |
| **T-04-11** | All text load-order inputs (`profile.sii`, `game.log.txt`, `--modlist`, `versions.sii`) are read through `_read_bounded_bytes()` capped at `MAX_TEXT_INPUT_BYTES = 64 MiB`. `scan_active_countries()` enforces an `active_chain` + `visited_wrappers` cycle detector emitting `include_cycle` diagnostics cleanly while relying on VFS 128 MiB decompression caps. |
| **T-04-12** | `CountryResolver.resolve()` enforces strict Tier 1 `country_aliases.json` precedence with a hard stop (`match_tier="unmatched"`, `unmatched_reason="alias_target_not_in_snapshot"`) whenever a known alias's target ISO-2 is outside the snapshot, neutralizing all 9 colliding SemEuropa Brazilian state ISO-2 codes (`AL`, `AM`, `BA`, `ES`, `MA`, `MT`, `RS`, `RO`, `SE`) as verified in `tests/test_merge_aliases.py`. |
| **T-04-SC** | Zero new external PyPI dependencies installed (`pyproject.toml` and `uv.lock` unchanged). |

## Deviations from Plan

None - plan executed cleanly as written (incorporating the cross-plan `04-02` `cp1252` fallback decoding practice proactively in `scanner.py`).

## Known Stubs

None.

## Self-Check: PASSED

- All 6 created files (`src/ets2v2/merge/{load_order,scanner,aliases}.py`, `tests/test_merge_{load_order,scanner,aliases}.py`) exist on disk and are tracked cleanly in git.
- All 3 task commits (`c8b4287`, `f4b3085`, `7624564`) are verified ancestors of `HEAD` (`plan_head_before=b2c0270`, `plan_head_after=7624564`).
- All quality gates (`ruff check`, `ruff format --check`, `basedpyright`, 37 plan+scaffold tests, and 468-test full offline `pytest`) passed with zero errors.
