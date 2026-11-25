---
phase: 04-promods-companion-builder-local-map-combo-composer
reviewed: 2026-11-25T13:15:00Z
depth: deep
files_reviewed: 111
files_reviewed_list:
  - .github/workflows/phase-a-release.yml
  - assets/icons/promods_summer.jpg
  - assets/icons/promods_winter.jpg
  - data/laws/countries/ad.json
  - data/laws/countries/am.json
  - data/laws/countries/ax.json
  - data/laws/countries/az.json
  - data/laws/countries/by.json
  - data/laws/countries/cn.json
  - data/laws/countries/cy.json
  - data/laws/countries/dz.json
  - data/laws/countries/eg.json
  - data/laws/countries/fo.json
  - data/laws/countries/ge.json
  - data/laws/countries/gg.json
  - data/laws/countries/gi.json
  - data/laws/countries/gl.json
  - data/laws/countries/ie.json
  - data/laws/countries/il.json
  - data/laws/countries/im.json
  - data/laws/countries/iq.json
  - data/laws/countries/je.json
  - data/laws/countries/jo.json
  - data/laws/countries/kg.json
  - data/laws/countries/kz.json
  - data/laws/countries/lb.json
  - data/laws/countries/li.json
  - data/laws/countries/ly.json
  - data/laws/countries/ma.json
  - data/laws/countries/mc.json
  - data/laws/countries/md.json
  - data/laws/countries/mn.json
  - data/laws/countries/mt.json
  - data/laws/countries/ps.json
  - data/laws/countries/sa.json
  - data/laws/countries/sj.json
  - data/laws/countries/sm.json
  - data/laws/countries/sy.json
  - data/laws/countries/tj.json
  - data/laws/countries/tm.json
  - data/laws/countries/tn.json
  - data/laws/countries/ua.json
  - data/laws/countries/uz.json
  - data/mappings/country_aliases.json
  - data/mappings/ets2_countries.json
  - pyproject.toml
  - src/ets2v2/cli.py
  - src/ets2v2/fetch/ec_bulletin.py
  - src/ets2v2/fetch/fx.py
  - src/ets2v2/fetch/pipeline.py
  - src/ets2v2/merge/__init__.py
  - src/ets2v2/merge/aliases.py
  - src/ets2v2/merge/compose.py
  - src/ets2v2/merge/hardcoded_totems.py
  - src/ets2v2/merge/load_order.py
  - src/ets2v2/merge/policy.py
  - src/ets2v2/merge/promods_builder.py
  - src/ets2v2/merge/promods_discovery.py
  - src/ets2v2/merge/promods_fuel.py
  - src/ets2v2/merge/scanner.py
  - src/ets2v2/normalize/__init__.py
  - src/ets2v2/normalize/currencies.py
  - src/ets2v2/normalize/fuel.py
  - src/ets2v2/normalize/fx.py
  - src/ets2v2/normalize/lockfile.py
  - src/ets2v2/normalize/totem_format.py
  - src/ets2v2/package/__init__.py
  - src/ets2v2/package/builder.py
  - src/ets2v2/package/icons.py
  - src/ets2v2/package/metadata.py
  - src/ets2v2/package/totems.py
  - src/ets2v2/publish/changelog.py
  - src/ets2v2/publish/release.py
  - src/ets2v2/registry/__init__.py
  - src/ets2v2/registry/loader.py
  - src/ets2v2/registry/models.py
  - src/ets2v2/registry/snapshot.py
  - src/ets2v2/registry/timezone.py
  - src/ets2v2/validate/__init__.py
  - src/ets2v2/validate/invariants.py
  - src/ets2v2/validate/models.py
  - src/ets2v2/validate/workshop.py
  - src/ets2v2/vfs/dir_archive.py
  - src/ets2v2/vfs/hashfs.py
  - state/prices.lock.json
  - tests/test_cli_scaffold.py
  - tests/test_compose_local.py
  - tests/test_country_aliases.py
  - tests/test_fetch_fuel.py
  - tests/test_fetch_fx.py
  - tests/test_fetch_pipeline.py
  - tests/test_hardcoded_totems.py
  - tests/test_merge_aliases.py
  - tests/test_merge_load_order.py
  - tests/test_merge_policy.py
  - tests/test_merge_scanner.py
  - tests/test_normalize_fuel.py
  - tests/test_normalize_fx.py
  - tests/test_package_icons_metadata.py
  - tests/test_promods_builder.py
  - tests/test_promods_discovery.py
  - tests/test_promods_fuel.py
  - tests/test_publish_release.py
  - tests/test_publish_workflow.py
  - tests/test_registry_contracts.py
  - tests/test_registry_schema.py
  - tests/test_registry_snapshot.py
  - tests/test_registry_timezone.py
  - tests/test_totem_formatting.py
  - tests/test_validate_invariants.py
  - tests/test_validate_workshop.py
findings:
  critical: 0
  high: 5
  medium: 7
  low: 4
  warning: 11
  info: 3
  total: 19
status: resolved
resolved: 2026-11-25T15:20:00Z
---

# Phase 04: Code Review Report

**Reviewed:** 2026-11-25T13:15:00Z
**Depth:** deep (ASVS Level 2 + cross-file call-chain, data integrity, and clean-room IP audit)
**Files Reviewed:** 111 (all 110 non-`.planning` files changed in `0cc5a35..HEAD` plus cross-file inspection of `src/ets2v2/fetch/fx.py`, `src/ets2v2/vfs/{stack,zip_archive}.py`, and `src/ets2v2/sii/{country,document,hygiene,lexer,localization,sign_board,speed_limits}.py`)
**Status:** issues_found

## Summary

Deep adversarial code and ASVS Level 2 security review of Phase 4 (`04-promods-companion-builder-local-map-combo-composer`, git range `0cc5a35..HEAD`, Plans `04-01`..`04-04`) covering the 76-territory law/currency/snapshot expansion (`data/laws/countries/*.json`, `data/mappings/{ets2_countries,country_aliases}.json`, `state/prices.lock.json`, `registry/`, `normalize/`, `fetch/`), the new Layer 9A offline `merge/` subpackage (`promods_discovery.py`, `promods_fuel.py`, `promods_builder.py`, `load_order.py`, `scanner.py`, `aliases.py`, `policy.py`, `hardcoded_totems.py`, `compose.py`), VFS/packaging/validator/publish extensions (`vfs/`, `package/`, `validate/`, `publish/`, `cli.py`), clean-room ProMods JPEG icons (`assets/icons/promods_{summer,winter}.jpg`), and the rolling `snapshots-latest` GitHub Release step in `.github/workflows/phase-a-release.yml`.

Note on reference docs: `~/.gemini/antigravity/gsd-core/references/necessity-review.md` and `~/.gemini/antigravity/gsd-core/references/cicd-review-patterns.md` were unreadable due to sandbox path protection boundaries. Per review rules, `necessity:` is omitted from frontmatter, and CI/CD review used the built-in pipeline checklist.

**Key positive verifications:**
- **All 6 AST DAG isolation walls hold with zero violations:** `validate` imports only `baseline`/`sii`/`vfs`; `merge` has zero imports from `fetch`/`publish` and zero network imports; `package` and `publish` have zero imports from `fetch` or `merge`; `normalize` imports only `baseline`; `registry` imports only `baseline`/`normalize`.
- **Strict typing & lint hygiene holds:** zero `# type: ignore` or `# pyright: ignore` suppressions anywhere under `src/ets2v2/`, `ruff check` (`All checks passed!`), and `basedpyright` (`0 errors, 0 warnings, 0 notes`).
- **Clean-room IP & JSON boundary holds:** zero `.scs`/`.sii`/`.sui`/`.dds`/`.tobj` files tracked in Git or under `data/`, all 76 law records + 119 aliases + 76-territory / 41-FX `state/prices.lock.json` pass canonical formatting, sanity-band, and timezone checks, and both `assets/icons/promods_{summer,winter}.jpg` icons are exact `276x162` baseline RGB JPEGs with zero EXIF/ICC metadata.
- **No decryption or cracking of protected archives:** `ScsC` profiles, `AEM!`, `3nK`, and password-encrypted ZIPs are detected via headers/central-directory flags only, with zero decryption attempts.
- **SemEuropa 27-state collision shield & D-14/D-15 core rules hold:** Tier 1 alias hits never fall through to Tier 2 `country_code`/`iso_country_code` when the target ISO-2 is absent from the snapshot; `max_of_map_and_real` carry-forward axle merge and `patch_if_single_tz` guardrails work accurately on clean inputs.

**Blocking defects requiring fixes before ship (`security_block_on: "medium"` — 0 CRITICAL, 5 HIGH, 7 MEDIUM):**
1. **`HI-01` (HIGH / BLOCKER):** `src/ets2v2/merge/load_order.py:456-465, 505-517, 557-558, 770-782` classifies any token with `/`, `\`, or `C:` as `source="explicit_path"`, bypassing `mod_dir` containment for `profile.sii` and `game.log.txt` (verified: `active_mods[0]: "../outside_secret/escaped.scs"` and `game.log.txt` mount lines without `, source:` escape `mod_dir`) and exposing Windows hosts to outbound SMB/NTLMv2 leaks via UNC paths (`\\server\share`).
2. **`HI-02` (HIGH / BLOCKER):** `src/ets2v2/merge/load_order.py:94-98, 841-888` (`_ComboScopedArchive` + `_COMBO_SCOPED_PATH_RE`) hides nested `@include` wrapper files outside `def/country/<slug>.{sui,sii}`, breaking `scan_active_countries()`'s recursive include traversal in `compose-local` (verified: `def/country.wrap.sii -> def/country_wrap_list.sui -> def/country/mytest.sui` works on raw `VfsStack` but fails with `missing_include_target` in `build_combo_vfs_stack()`).
3. **`HI-03` (HIGH / BLOCKER):** `src/ets2v2/fetch/fx.py:354-391` (`run_fx_only_fetch()`, invoked by `ets2v2 fetch --fx-only`) calls `cross_validate_fx_rates()` without `include_extended=True`, silently wiping all 24 extended ProMods FX rates from `state/prices.lock.json` (verified: 41 FX rates reduced to 17 on write).
4. **`HI-04` (HIGH / BLOCKER):** `src/ets2v2/merge/promods_builder.py:78-86, 183-194` (`assert_out_dir_not_tracked()`) allows `--out-dir .` (the un-gitignored repo root itself!) as well as Git-tracked `.planning/`, `scripts/`, and `.agents/` directories, bypassing the D-08 ProMods clean-room IP guard.
5. **`HI-05` (HIGH / BLOCKER):** `src/ets2v2/merge/promods_builder.py:642-690` deletes/overwrites the final Workshop tree and local ZIP *before* running Offline SCS Validator checks, leaving invalid/unvalidated ProMods packages on disk on validation failure (reproduced: both `workshop/promods-summer/` and `local/ETS2V2_ProMods_Summer.zip` remain on disk after validation raises `ValueError`).
6. **`MD-01`..`MD-07` (7 MEDIUM / WARNING — blocking per `security_block_on: "medium"`):** `promods_fuel.py` `3nK`/empty-module/`cp1252`/backslash failures; missing fault isolation in `compose.py` and `hardcoded_totems.py` on malformed third-party map files; Offline Validator `combo` profile gaps (dangling board tokens when `fuel_locales` absent, missing 7-seg `<sup>` check, silent duplicate `.sui`+`.sii` overwrite, rogue `def/` `.sii` files); `RealismSnapshot.anchor_date` missing calendar validation + TOCTOU double-read + unbounded reads; `promods_builder.py` duplicated scanner/policy drift crashing on wrapper `.sii` files; `phase-a-release.yml` starving `snapshots-latest` updates when only non-Core ProMods snapshot data changes; missing symlink containment on Workshop `versions.sii` and half-TZ third-party fragment failures.

## Narrative Findings (AI reviewer)

## High Issues

### HI-01: Path traversal, `mod_dir` containment bypass, and Windows UNC SMB exposure in `_entry_from_package_token()` / `_resolve_local_mod_path()` [HIGH / BLOCKER]

**File:** `src/ets2v2/merge/load_order.py:456-465, 505-517, 557-558, 770-782` (ASVS V12.3.1 / V5.1.3)
**Issue:** `_resolve_local_mod_path()` enforces strict `mod_dir` containment (`"/" in name or "\\" in name or ".." in Path(name).parts` and `resolved.is_relative_to(mod_root)`) for `source == "local"` entries (`lines 794-801`). However, `_entry_from_package_token()` (`lines 456-465`) automatically promotes **any** token containing `/`, `\`, or a Windows drive prefix (`C:`) to `source="explicit_path"`, which completely bypasses lines 794-801 and executes `Path(entry.raw_spec).exists()` and `(mod_dir / raw_path).exists()` (`lines 774-782`) with zero containment or UNC checks:
1. **`profile.sii` containment bypass (reproduced):** ETS2 `profile.sii` `active_mods[]` never legitimately holds filesystem paths (only mod stems or `mod_workshop_package.<hex>`). Yet `active_mods[0]: "../outside_secret/escaped.scs"` (without `|Display`) parses as `source="explicit_path"` and mounts `mods/../outside_secret/escaped.scs` outside `mod_dir` cleanly.
2. **`game.log.txt` containment bypass (reproduced):** Line 557 only demotes `explicit_path` back to `local` when `source_hint is not None`. A `[mod_package_manager]` line omitting `, source: ...` (`package_name: ../outside_secret/escaped.scs`) stays `explicit_path` and escapes `mod_dir`.
3. **Windows UNC NTLM credential leak & `--modlist` relative traversal:** A crafted `profile.sii`, `game.log.txt`, or shared `--modlist` containing `\\attacker-host\share\mod.scs` hits `Path(entry.raw_spec).exists()` at line 776, causing Windows to initiate an outbound SMB connection and leak NTLMv2 hashes; relative `../` lines in `--modlist` also escape `mod_dir` via `candidate = mod_dir / raw_path`.

**Fix:**
- Add a dedicated parameter `allow_explicit_path: bool = False` to `_entry_from_package_token()` — set `allow_explicit_path=True` **only** in `parse_modlist()`, never in `parse_profile_sii()` or `parse_game_log()`.
- Reject NUL bytes (`"\x00"`) and UNC/network paths (`token.startswith(("\\\\", "//"))` or `Path(token).drive.startswith("\\\\")`) unconditionally with `ValueError`.
- In `_resolve_local_mod_path()` for `explicit_path`: reject UNC paths and reject relative paths containing `..` that resolve outside `mod_dir.resolve()` (only permit explicit absolute local filesystem paths or relative paths contained within `mod_dir`):
```python
if entry.source == "explicit_path":
    if "\x00" in entry.raw_spec or entry.raw_spec.startswith(("\\\\", "//")):
        raise ValueError(f"Unsafe or UNC mod path rejected: {entry.raw_spec!r}")
    raw_path = Path(entry.raw_spec)
    if raw_path.is_absolute():
        if raw_path.drive.startswith("\\\\"):
            raise ValueError(f"UNC network path rejected: {entry.raw_spec!r}")
        return raw_path if raw_path.exists() else None
    if mod_dir is not None:
        mod_root = mod_dir.resolve()
        candidate = (mod_dir / raw_path).resolve()
        if not candidate.is_relative_to(mod_root):
            raise ValueError(f"Relative mod path escapes --mod-dir: {entry.raw_spec!r}")
        return candidate if candidate.exists() else None
    return None
```

---

### HI-02: `_ComboScopedArchive` hides nested `@include` wrapper files, silently breaking `scan_active_countries()` in `compose-local` [HIGH / BLOCKER]

**File:** `src/ets2v2/merge/load_order.py:94-98, 814-838, 841-888`
**Issue:** `VfsStack._ensure_index()` (`src/ets2v2/vfs/stack.py:248`) constructs the stack's entire lookup index exclusively from `layer.archive.list_paths()`. When `build_combo_vfs_stack()` mounts mod archives, it wraps every archive in `_ComboScopedArchive`, which filters `list_paths()` through `_COMBO_SCOPED_PATH_RE`:
```python
_COMBO_SCOPED_PATH_RE = re.compile(
    r"^(?:(?:base|dlc_[^/]+)/)?(?:def/country(?:\.[^/]+)?\.sii$|def/country/[^/]+\.(?:sui|sii)$|"
    r"def/country/[^/]+/speed_limits\.sii$|def/sign/board/|locale/)",
    re.IGNORECASE,
)
```
This regex drops any nested wrapper file referenced by `@include` in `def/country*.sii` that does not match `def/country/<slug>.{sui,sii}` — such as `def/country_wrap_list.sui` or `def/country/subdir/list.sii` — even though `scanner.py:249-276` explicitly implements recursive `@include` traversal for wrapper files!
**Directly reproduced:** A synthetic mod archive containing `def/country.wrap.sii` (`@include "country_wrap_list.sui"`) -> `def/country_wrap_list.sui` (`@include "country/mytest.sui"`) -> `def/country/mytest.sui`:
- `scan_active_countries(VfsStack.from_paths([wrapper_zip]))` -> `mytest` found (`True`).
- `scan_active_countries(build_combo_vfs_stack(...).stack)` -> `mytest` **NOT found (`False`)**, emitting `ScanDiagnostic(kind='missing_include_target', path='def/country_wrap_list.sui')`, silently dropping every country behind the wrapper!

**Fix:** Broaden `_COMBO_SCOPED_PATH_RE` to include all `.sii`/`.sui` files directly under `def/` and under `def/country/` (including nested subdirectories), keeping the fast subtree pruning that skips `model/`, `material/`, `prefab/`, `map/`, `vehicle/`, etc.:
```python
_COMBO_SCOPED_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:base|dlc_[^/]+)/)?(?:"
    r"def/[^/]+\.(?:sii|sui)$|"
    r"def/country/.*\.(?:sii|sui)$|"
    r"def/sign/board/|"
    r"locale/)",
    re.IGNORECASE,
)
```
Add an end-to-end regression test in `tests/test_compose_local.py` verifying nested wrapper `@include` files resolve cleanly through `build_combo_vfs_stack()` + `compose_local()`.

---

### HI-03: `run_fx_only_fetch()` omits `include_extended=True`, silently wiping all 24 extended ProMods FX rates from `state/prices.lock.json` [HIGH / BLOCKER]

**File:** `src/ets2v2/fetch/fx.py:354-391`
**Issue:** Phase 4 expanded `state/prices.lock.json` from 17 to 41 FX currencies (adding the 24 extended ProMods currencies in `EXTENDED_PROMODS_CURRENCIES`) and updated `fetch/pipeline.py:289` to pass `include_extended=True` to `cross_validate_fx_rates()`. However, `run_fx_only_fetch()` (`src/ets2v2/fetch/fx.py:354-358`, called by `ets2v2 fetch --fx-only` via `pipeline.py:240-248`) was not updated and still calls `cross_validate_fx_rates()` with the default `include_extended=False`. When `write_lock=True`, line 378 overwrites `existing_lock.fx_rates` with `validation.rates`.
**Directly reproduced:** Running `run_fx_only_fetch(lock_path=lock_copy, write_lock=True, ...)` against a copy of `state/prices.lock.json` dropped `len(fx_rates)` from **41 to 17**, silently deleting all 24 extended ProMods currencies (`AMD`, `AZN`, `BYN`, `CNY`, `DZD`, `EGP`, `GEL`, `ILS`, `IQD`, `JOD`, `KGS`, `KZT`, `LBP`, `LYD`, `MAD`, `MDL`, `MNT`, `SAR`, `SYP`, `TJS`, `TMT`, `TND`, `UAH`, `UZS`) from the lockfile while leaving 76 territories referencing them.

**Fix:** Pass `include_extended=True` in `run_fx_only_fetch()` (`src/ets2v2/fetch/fx.py:354-359`):
```python
    validation = cross_validate_fx_rates(
        provider_quotes,
        previous_fx=previous_fx,
        fetched_at=now_iso,
        include_extended=True,
    )
```
Add a regression test in `tests/test_fetch_fx.py` verifying `ets2v2 fetch --fx-only` preserves all 41 FX currencies in `state/prices.lock.json`.

---

### HI-04: `assert_out_dir_not_tracked()` permits writing ProMods/Combo outputs into the repository root (`.`) and tracked dirs (`.planning/`, `scripts/`, `.agents/`) [HIGH / BLOCKER]

**File:** `src/ets2v2/merge/promods_builder.py:78-86, 183-194` (D-08, T-04-05)
**Issue:** `assert_out_dir_not_tracked()` guards only 7 hardcoded subdirectories (`data`, `src`, `tests`, `state`, `assets`, `.github`, `.git`).
**Directly reproduced:**
- `assert_out_dir_not_tracked(Path("."), repo_root=repo)` **passes silently!** Running `ets2v2 package promods --out-dir .` writes `workshop/promods-summer/universal/def/country/...` and `local/ETS2V2_ProMods_Summer.zip` directly into the repository root (`workshop/` and `local/` are NOT in `.gitignore`), and `ets2v2 compose-local --out-dir .` writes `zz_ETS2V2_ComboPatch_Summer.scs` directly into the repository root — defeating D-08's clean-room IP guard against committing third-party ProMods files into Git.
- `assert_out_dir_not_tracked(repo / d, repo_root=repo)` also **passes silently** for `d in {".planning", "scripts", ".agents"}`, all of which are Git-tracked top-level directories (`git ls-tree -d --name-only HEAD`).

**Fix:** Refuse the repository root itself (`resolved_out == root`) and block any non-gitignored subdirectory inside the repository root (allowing only the gitignored artifact roots `dist`, `out`, `build`, `raw`, `vendor` inside `root`, while allowing any path outside `root`):
```python
_ALLOWED_REPO_OUTPUT_SUBDIRS: Final[frozenset[str]] = frozenset(
    {"dist", "out", "build", "raw", "vendor"}
)

def assert_out_dir_not_tracked(out_dir: Path, *, repo_root: Path | None = None) -> None:
    resolved_out = out_dir.resolve()
    for root in _candidate_repo_roots(repo_root):
        if resolved_out == root:
            raise ValueError(
                f"Refusing to write ProMods/Combo output directly into repository root: {out_dir}"
            )
        if resolved_out.is_relative_to(root):
            top_dir = resolved_out.relative_to(root).parts[0]
            if top_dir.lower() not in _ALLOWED_REPO_OUTPUT_SUBDIRS:
                raise ValueError(
                    f"Refusing to write ProMods/Combo output inside tracked/unignored repository "
                    f"directory {root / top_dir}: {out_dir}"
                )
```

---

### HI-05: `build_promods_edition()` overwrites final Workshop tree and local ZIP *before* Offline Validator gating, leaving unvalidated artifacts on disk on failure [HIGH / BLOCKER]

**File:** `src/ets2v2/merge/promods_builder.py:642-690` (D-07, ASVS V12.3)
**Issue:** Unlike `compose_local()` (`src/ets2v2/merge/compose.py:446-473`), which stages to a temporary file, gates with `validate_local_zip(..., profile="combo")`, and promotes via `os.replace()` only on pass, `build_promods_edition()` writes directly to the final destinations first:
1. Line 656 calls `write_workshop_tree(workshop_dir, out_dir, workshop_files)`, which runs `shutil.rmtree(workshop_dir)` (destroying any previous valid Workshop build) and writes unvalidated files into `out_dir/workshop/promods-{edition}/`.
2. Line 670 calls `write_deterministic_zip(local_zip_path, local_entries)`, overwriting `out_dir/local/ETS2V2_ProMods_{Summer|Winter}.zip`.
3. Lines 673-689 only then invoke `validate_workshop_package()` and `validate_local_zip()`.

**Directly reproduced:** Building against a ProMods EU fixture missing UK `scotland`/`wales` regions raises `ValueError: ProMods Workshop validation failed`, while **both `pm_out/workshop/promods-summer/` (`ws_left_on_disk=True`) and `pm_out/local/ETS2V2_ProMods_Summer.zip` (`zip_left_on_disk=True`) remain written at the final output paths**.

**Fix:** Stage both targets into sibling temporary paths (`tempfile.mkdtemp(dir=out_dir / "workshop", prefix=f".tmp_promods-{edition}_")` and `tempfile.NamedTemporaryFile(dir=out_dir / "local", prefix=f".tmp_promods_{edition}_", suffix=".zip", delete=False)`), run both `validate_workshop_package(staged_ws, ..., profile="promods")` and `validate_local_zip(staged_zip, ..., profile="promods")` against the staged outputs, and only promote them into `workshop_dir` / `local_zip_path` after both reports return `ok=True` (cleaning up staged paths in `except Exception:`).

---

## Medium Issues

### MD-01: `compile_promods_fuel_module()` silently emits empty `localization_db` on `3nK` files and crashes uncaught on `cp1252` or preserved backslashes [MEDIUM / WARNING]

**File:** `src/ets2v2/merge/promods_fuel.py:346-350, 362-427, 430-447` (ASVS V5.1.3 / V12.1)
**Issue:**
1. **Silent empty module on `3nK` obfuscation (reproduced):** `_find_module_source_in_stack()` and `compile_promods_fuel_module()` never call `detect_3nk(raw_bytes)`. Passing `b"3nK\x01" + b"\x00" * 32` succeeds in `parse_localization_db()` with `[]` (0 entries) and emits an **empty** `localization_db : .pm_fuel {}` across all 43 locales — wiping ProMods fuel totems and failing `validate_promods_locale_modules_consistency()` ("zero key/val entries").
2. **Crash on `cp1252` comments (reproduced):** `compile_promods_fuel_module()` passes raw `source_bytes` directly to `parse_localization_db()`, which invokes strict UTF-8 `normalize_sii_bytes()`. A single legacy Windows-1252 comment byte (`0xe9`) raises uncaught `SiiEncodingError` and aborts `compose_local()` / `build_promods_edition()`.
3. **Crash on preserved verbatim backslash strings (reproduced):** Unrecognized keys/values are preserved verbatim and re-serialized via `format_sii_string()` (`package/synthesize.py:22`), which rejects any string containing `\` (`ValueError: Disallowed backslash or NUL`).

**Fix:**
- In `_find_module_source_in_stack()`, check `if detect_3nk(raw): continue` and catch `(FileNotFoundError, ProtectedPayloadError, UnsupportedCompressionError, OSError, ValueError)`.
- In `compile_promods_fuel_module()`, guard `if detect_3nk(source_bytes): raise ValueError(...)`, decode via UTF-8 with `cp1252` fallback (matching `scanner.py` / `policy.py`), and skip/reject empty `raw_entries`.
- In `_render_promods_localization_db()`, escape backslashes as `\\` (rejecting only `\x00`) for preserved verbatim non-path localization values instead of rejecting `\`, and skip empty values if any upstream placeholder key has `val == ""` (or align validator empty-val check for verbatim preserved keys).

---

### MD-02: Missing fault isolation in `compose_local()` and `patch_hardcoded_numeric_totems()` crashes the entire combo build on one malformed third-party map file [MEDIUM / WARNING]

**File:** `src/ets2v2/merge/compose.py:339-371`, `src/ets2v2/merge/hardcoded_totems.py:155-184, 298-301`
**Issue:** Third-party map combos routinely contain community mods with legacy SII quirks or broken files. Three unguarded sites abort the entire `compose-local` run instead of recording a warning/diagnostic and continuing:
1. **`compose.py:357` (reproduced):** One third-party mod with a malformed `def/country/germany/speed_limits.sii` (`limit[]` before `lane_speed_class[]`) raises uncaught `ValueError: Found limit[] before lane_speed_class[]` in `apply_speed_limits_policy()`, crashing `compose_local()` instead of skipping that country's `speed_limits.sii`. The same applies to `apply_country_policy()` at line 339 (e.g., non-contiguous `mass_limit_per_axle_count[]` or >12-char unit segment hygiene error).
2. **`hardcoded_totems.py:298-301` (reproduced):** Rewriting a community numeric board whose existing unit name has a >12-char segment (`sign_templ.kz_gas_diesel_long`, 18 chars) raises uncaught `ValueError: Rewritten hardcoded board hygiene failure` and aborts `compose-local --patch-hardcoded-totems` instead of recording `status="skipped_unreadable"`.
3. **`hardcoded_totems.py:157`:** `stack.read_bytes(vfs_path)` catches only `(FileNotFoundError, ProtectedPayloadError, UnsupportedCompressionError)`, omitting `ValueError` and `OSError` raised by `ZipArchive.read_bytes()` / `HashFs*.read_bytes()` on corrupt zlib streams or oversized entries (and omits `detect_3nk(raw_bytes)`).

**Fix:**
- In `compose.py:339-371`, wrap `apply_country_policy()` and `apply_speed_limits_policy()` in `try/except ValueError as exc:`, recording a warning/audit entry (`emitted=False` or `speed_limits_status="skipped_parse_error"`) and continuing to patch all remaining countries.
- In `hardcoded_totems.py`, add `OSError, ValueError` to the read `except` tuple, skip `detect_3nk(raw_bytes)` cleanly, and convert post-rewrite hygiene failures into `HardcodedTotemBoardAction(..., status="skipped_unreadable", detail=summary)` rather than raising `ValueError`.

---

### MD-03: Offline Validator `combo` profile passes dangling sign-board tokens when `fuel_locales` is absent, omits 7-segment `<sup>` checks, silently overwrites duplicate `.sui`+`.sii` slugs, and permits rogue `def/` `.sii` files [MEDIUM / WARNING]

**File:** `src/ets2v2/validate/invariants.py:1146-1160`, `src/ets2v2/validate/workshop.py:1048-1174`
**Issue:** Directly reproduced via `validate_local_zip(..., profile="combo")`:
1. **Dangling tokens pass when `fuel_locales` is missing (`invariants.py:1153`):** `if token is not None and canonical_tokens and token not in canonical_tokens:` short-circuits to `False` whenever `fuel_locales` is absent (`canonical_tokens` empty). A combo `.scs` containing `def/sign/board/custom_board.sii` with `@@fp_xx_missing_ets2v2@@` and **zero** `local_module.ets2v2_fuel.sii` files passes with `ok=True, issues=[]`.
2. **Missing 7-segment `<sup>` font cross-check (`invariants.py:1146-1160`):** Unlike `validate_totem_invariants()` (`lines 566-575`), `validate_combo_invariants()` never checks that boards using `_NON_SUP_GAS_FONTS` (`gas_segment_7_standard.font`, `gas_sign_digit.font`) do not reference a token whose value contains `<sup>`.
3. **Silent overwrite on duplicate `.sui` + `.sii` for the same slug (`workshop.py:1076-1096`):** A `combo` or `promods` package containing both `def/country/foo.sui` and `def/country/foo.sii` overwrites `country_models["foo"]` silently, passing with `ok=True, issues=[]` while skipping invariant checks on the overwritten fragment.
4. **Rogue `.sii`/`.sui` files permitted (`workshop.py:1048-1174`):** A package containing `def/economy_data.sii` and `def/country/germany/traffic.sii` passes `validate_local_zip(..., profile="combo")` (and `core`/`promods`) with `ok=True, issues=[]`, violating D-08's minimal realism-only footprint contract.

**Fix:**
- In `validate_combo_invariants()`, emit `ETS2V2-INV-TOTEM-BOARDS` whenever a board's `@@token@@` is not in `canonical_tokens` (even if `canonical_tokens` is empty), and cross-check `_NON_SUP_GAS_FONTS` against `canonical_token_values`.
- In `_validate_package_contents()`, reject duplicate country definitions for the same `slug` (`if slug in country_models: collector.error("00003", display_path, ...)`) and reject any `.sii`/`.sui` file outside the permitted realism allowlist (`manifest.sii`, `def/country/<slug>.sui`, `def/country/<slug>.sii` in non-core, `def/country/<slug>/speed_limits.sii`, `def/sign/board/<name>.sii`, and allowed `locale/...` fuel modules) with SCS `00003`.

---

### MD-04: `RealismSnapshot.anchor_date` lacks calendar validation, and snapshot loading/verification performs unbounded reads and a TOCTOU double-read [MEDIUM / WARNING]

**File:** `src/ets2v2/registry/snapshot.py:75, 215, 255, 295, 385-394` (ASVS V5.1.3 / V12.1.2 / V12.3.1)
**Issue:**
1. **Invalid calendar dates pass `verify_snapshot_file()` (reproduced):** `RealismSnapshot.anchor_date` checks only regex `^\d{4}-\d{2}-\d{2}$` without calling `date.fromisoformat()`. A snapshot with `"anchor_date": "2026-99-99"` returns `ok=True` from `verify_snapshot_file()` and then crashes `compose_local()` (`compose.py:234`) and `build_promods_edition()` (`promods_builder.py:511`) with `ValueError: month must be in 1..12`.
2. **TOCTOU double-read between SHA-256 verification and deserialization (`snapshot.py:385-394`):** `load_or_build_snapshot()` calls `verify_snapshot_file(snapshot_path)` (which hashes and parses the file, then discards the parsed `RealismSnapshot`) and then calls `load_realism_snapshot(snapshot_path)` to re-read the file from disk a second time.
3. **Unbounded `.read_bytes()` on untrusted `--snapshot` / `--checksums` inputs (`snapshot.py:215, 255, 295`):** Unlike `load_order.py`'s `MAX_TEXT_INPUT_BYTES` guard, `load_realism_snapshot()`, `verify_snapshot_file()`, and `parse_sha256sums()` read arbitrary file sizes into memory without bounds.

**Fix:**
- Add a `@field_validator("anchor_date")` calling `date.fromisoformat(value)` on `RealismSnapshot`.
- Enforce bounded reads (`MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024`, `MAX_CHECKSUMS_BYTES = 1 * 1024 * 1024`) before reading into memory.
- Extract an internal `_verify_and_parse_snapshot()` returning `(SnapshotVerificationResult, RealismSnapshot | None)` so `load_or_build_snapshot()` returns the exact verified snapshot instance from the hashed bytes without re-reading disk.

---

### MD-05: `promods_builder.py` duplicates VFS/scanner/policy logic with verified defect drift (wrapper `.sii` crash, missing `3nK` checks, missing monotonicity clamp) [MEDIUM / WARNING]

**File:** `src/ets2v2/merge/promods_builder.py:88-89, 196-214, 254-302, 572-621`
**Issue:** `promods_builder.py` re-implements private copies of `BaselineVirtualArchive`, `scan_active_countries()`, `CountryResolver`, `apply_country_policy()`, and `apply_speed_limits_policy()`, introducing multiple concrete regressions relative to the hardened `compose-local` modules:
1. **Wrapper `.sii` crash (reproduced):** `_discover_active_country_fragments()` (`lines 281-285`) treats any `def/country/<name>.sii` as a leaf country without checking whether it contains a `country_data` unit, and line 579 calls `parse_country_data()` unguarded. A wrapper `def/country/wrapper.sii` containing `@include "andorra.sui"` crashes `build_promods_edition()` with `ValueError: No country_data unit found in SII/SUI source`.
2. **Missing `3nK` detection & case-sensitivity:** Lines 263, 575, and 610 never call `detect_3nk()`, and lines 88-89 omit `re.IGNORECASE` (unlike `scanner.py:22-29`).
3. **Root-absolute `@include`, axle monotonicity, and `SiiNunit` hygiene drift:** Line 266 mishandles root-absolute `@include "/custom/..."` paths; `_merge_axle_mass_limits()` (`lines 201-204`) omits monotonic clamping when one array is empty (unlike `policy.py:107-110`); and `_patch_country_fragment_bytes()` (`line 380`) hardcodes `require_siinunit=False` even for `SiiNunit`-wrapped `.sii` country fragments (unlike `policy.py:208`).

**Fix:** Remove the duplicated private helpers in `promods_builder.py` and delegate directly to `BaselineVirtualArchive.from_baselines()`, `scan_active_countries()`, `CountryResolver`, `apply_country_policy()`, and `apply_speed_limits_policy()`.

---

### MD-06: `phase-a-release.yml` gates rolling `snapshots-latest` Release and Release PR solely on 36-country Core `any_changed`, starving ProMods/extended snapshot updates [MEDIUM / WARNING]

**File:** `.github/workflows/phase-a-release.yml:30, 33, 142, 155-177`, `src/ets2v2/publish/release.py:200-206`
**Issue:**
1. `run_phase_a_release()` determines `changed` exclusively from `compute_workshop_canonical_sha256(built.workshop_dir)` (the 36 Vanilla Core countries + 460 boards). When weekly online fetches (`fuel_prices_eu`, `frankfurter_v2`, `fawazahmed0`) update fuel prices or FX rates for any of the 40 non-Vanilla ProMods territories (`UA`, `MD`, `BY`, `CY`, `MT`, `IL`, `KZ`, etc.) or 24 extended FX currencies without changing the 36-country Core payload hash, `any_changed` remains `false`. Consequently, both `Publish rolling public snapshots-latest GitHub Release` (`line 156`) and `Create or update persistent Release PR` (`line 177`) are skipped — leaving `snapshots-latest` stale and discarding non-Core `state/prices.lock.json` updates unless a maintainer manually dispatches `force_run: true`.
2. In addition, this write-scoped workflow (`contents: write`, `pull-requests: write`, `secrets.TANKERKOENIG_API_KEY`) still references mutable major action tags (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/upload-artifact@v4`) rather than immutable 40-character commit SHAs (carried forward from Phase 3 deferred ops note).

**Fix:** Track `snapshots_changed` in `PhaseAReleaseSummary` (comparing `staged.snapshot_sha256` against `prev_state.snapshot_sha256` for both editions) and emit `snapshots_changed` to `$GITHUB_OUTPUT`. Gate the `snapshots-latest` GitHub Release upload on `any_changed == 'true' || snapshots_changed == 'true' || env.FORCE_RUN == 'true'` (and optionally commit `state/prices.lock.json` without bumping Core package versions when only non-Core snapshot data changed). Pin workflow actions to verified commit SHAs when online verification is available.

---

### MD-07: Missing symlink containment check on Workshop `versions.sii` and unguarded third-party half-TZ/missing-`country_code` fragments failing pre-write combo validation [MEDIUM / WARNING]

**File:** `src/ets2v2/merge/load_order.py:654-657`, `src/ets2v2/merge/compose.py:339-351`, `src/ets2v2/validate/workshop.py:876-890` (ASVS V12.3.1)
**Issue:**
1. **Workshop `versions.sii` symlink escape (`load_order.py:654-657`):** `resolve_workshop_package_path()` verifies `item_dir.is_relative_to(ws_root)` and verifies resolved targets in `_resolve_contained_workshop_target()`, but calls `_read_bounded_bytes(versions_sii)` directly without checking `versions_sii.resolve().is_relative_to(item_dir)`. A symlinked `versions.sii` pointing outside `item_dir` bypasses containment.
2. **Third-party map fragment validation deadlock (`compose.py:339-351` vs `workshop.py:876-890`):** If a matched third-party map country omits `country_code` or sets `time_zone_name` while omitting `time_zone`, `apply_country_policy()` preserves those map-owned fields untouched and emits the patched fragment into `payloads`. Then `compose_local()` invokes `validate_local_zip(staged_path, ..., profile="combo")` (`compose.py:457`), which rejects the fragment with SCS `00005` (`Missing required country_code` or `time_zone and time_zone_name must either both be present or both omitted`) and aborts the entire combo build.

**Fix:**
- In `resolve_workshop_package_path()`, verify `if not versions_sii.resolve().is_relative_to(item_dir): raise ValueError(f"Workshop versions.sii escapes item directory: {versions_sii}")` before calling `_read_bounded_bytes(versions_sii)`.
- In `compose_local()`, pre-check required map-owned fields (`country_id > 0`, non-empty `name` and `country_code`, symmetric `time_zone`/`time_zone_name`) before emitting a patched third-party country fragment — recording a clear warning and skipping malformed third-party country definitions rather than failing the entire combo build at the final ZIP validation gate.

---

## Low Issues

### LO-01: `promods_discovery.py` version tuple comparison mishandles mixed compact vs dotted versions (`v284 > v2.85`) and dead `-` split in `_is_st_variant()` [LOW / WARNING]

**File:** `src/ets2v2/merge/promods_discovery.py:18-21, 137-146, 206-218`
**Issue:** `_parse_version_tuple("284")` returns `(284,)` while `_parse_version_tuple("2.85")` returns `(2, 85)`. Because `(284,) > (2, 85)` in Python, an older compact `v284` would beat a newer dotted `v2.85` if naming formats are ever mixed in a user's `mod/` directory. Also, `_is_st_variant()` splits on `r"[-_]"` (`line 144`), but `_EU_DEF_RE`'s `(?P<variant>[a-z0-9_]+)` never captures `-`.
**Fix:** Normalize compact 3-digit ProMods versions (`len == 1 and 100 <= v < 1000` -> `(v // 100, v % 100)`) so `v284` -> `(2, 84) < (2, 85)` consistently, and simplify `_is_st_variant()` to split on `"_"` (matching `_EU_DEF_RE`).

---

### LO-02: `phase-a-release.yml` masks GitHub API errors in `gh release view` check [LOW / WARNING]

**File:** `.github/workflows/phase-a-release.yml:169-174`
**Issue:** `if gh release view "$TAG" >/dev/null 2>&1;` treats any non-zero exit (401/403 token permission error, 5xx API outage, secondary rate limit) identically to 404 "release not found", falling through to `gh release create` and masking the underlying error.
**Fix:** Capture exit status / stderr or query `gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${TAG}"` explicitly distinguishing HTTP 404 (create) from HTTP 200 (upload + edit) and failing fast on any other API error.

---

### LO-03: `HashFs` `list_direct_files()` silently drops unsafe traversal names without recording `ArchiveDiagnostic` and skips deduplication [LOW / WARNING]

**File:** `src/ets2v2/vfs/hashfs.py:319-346`
**Issue:** Unlike `_walk_with_parser()` (`hashfs.py:274-285`), `list_direct_files()` silently skips unsafe child names (`".."`, `"/"`, `"\\"`, `"\x00"`) without calling `self._diag.add("path_traversal", ...)`, and does not deduplicate repeated entries within a malformed HashFS directory listing.
**Fix:** Record `self._diag.add("path_traversal", norm or "/", f"Rejected unsafe directory entry name {child_name!r}")` on unsafe names and deduplicate `files` with a `seen: set[str]`.

---

### LO-04: `DirectoryArchive.read_bytes()` lacks a maximum file-size cap (unlike `ZipArchive` and `HashFs*` 128 MiB caps) [LOW / WARNING]

**File:** `src/ets2v2/vfs/dir_archive.py:177-193` (ASVS V12.1.2)
**Issue:** Both `ZipArchive` (`zip_archive.py:24`) and `HashFs*` (`hashfs.py:32`) enforce a `128 MiB` entry size cap to guard against memory exhaustion, whereas `DirectoryArchive.read_bytes()` calls `resolved.read_bytes()` unconditionally (including when `is_ets2v2_self_package()` probes `manifest.sii` in an unpacked mod directory).
**Fix:** Enforce `MAX_DIR_ENTRY_BYTES = 128 * 1024 * 1024` via `resolved.stat().st_size` and a bounded `fh.read(MAX_DIR_ENTRY_BYTES + 1)` check in `DirectoryArchive.read_bytes()`.

---

## Info

### IN-01: `PM_EU_PREFIX_TO_ISO2` omits 6 ProMods territories (`DZ`, `LI`, `LY`, `MA`, `SM`, `TN`) present in the 76-territory snapshot [INFO]

**File:** `src/ets2v2/merge/promods_fuel.py:50-132`
**Issue:** ProMods 2.85 / MA 1.05 currently omits `pm_fuel` keys for Liechtenstein (`LI`), San Marino (`SM`), and Maghreb (`DZ`, `LY`, `MA`, `TN`). Adding `"li"` and `"sm"` proactively (consistent with the 4 future-proof TGS v1.71 prefixes already mapped in `PM_TGS_PREFIX_TO_ISO2`) ensures seamless updates if future ProMods releases add them.
**Fix:** Add `"li": "LI"` and `"sm": "SM"` to `PM_EU_PREFIX_TO_ISO2` (and Maghreb prefixes when a ProMods MA fuel module appears).

---

### IN-02: `fetch/pipeline.py` flags live `fuel_prices_eu` quotes for non-EU ProMods territories as `fallback_used=True` [INFO]

**File:** `src/ets2v2/fetch/pipeline.py:58-60, 438`
**Issue:** Line 438 sets `is_fallback_entry = cand.feed_tier == "fallback" and iso2 not in _NON_EU_VANILLA_ISO2S`, exempting only the 10 non-EU Vanilla territories (`AL`, `BA`, `CH`, `IS`, `ME`, `MK`, `RS`, `RU`, `TR`, `XK`). Non-EU ProMods territories (`UA`, `MD`, `BY`, `AD`, `MC`, `SM`, `GI`, `LI`, `GE`, `AM`, `AZ`, etc.) whose primary live European feed is `fuel_prices_eu` are marked `fallback_used=True` even on fresh live quotes.
**Fix:** Expand the non-EU primary-fallback exemption set to cover non-EU ProMods territories where `fuel_prices_eu` is the primary live source.

---

### IN-03: Non-atomic `--report-json` writes in `compose_local()` and duplicate fragment reads in `scan_active_countries()` [INFO]

**File:** `src/ets2v2/merge/compose.py:137-141`, `src/ets2v2/merge/scanner.py:211, 325`
**Issue:** `_write_report_json()` writes directly via `report_path.write_bytes(...)` instead of atomic temp-file + `os.replace()` (risking truncated JSON on crash/interrupt), and `scan_active_countries()` reads each active country fragment twice from VFS (once during wrapper include inspection and again during `country_data` parsing).
**Fix:** Use `NamedTemporaryFile` + `os.replace()` in `_write_report_json()`, and cache already-read fragment bytes inside `scan_active_countries()`.

---

## Resolution Summary (2026-11-25)

All 19 review findings (`5` HIGH, `7` MEDIUM, `4` LOW, `3` INFO) were addressed across 10 atomic commits on `gsd/phase-04-promods-companion-builder-local-map-combo-composer` with targeted regression tests:

- `3bc91ba` — `HI-01`, `HI-02`, `MD-07` (`load_order.py`: restrict `explicit_path` to `--modlist` only, unconditionally reject NUL/UNC paths and relative `..` escapes, broaden `_COMBO_SCOPED_PATH_RE` for nested wrapper `@include` files, enforce symlink containment on Workshop `versions.sii`)
- `5b0d6c1` — `HI-03`, `IN-02` (`fetch/fx.py`, `fetch/pipeline.py`: pass `include_extended=True` in `run_fx_only_fetch()` to preserve all 41 FX rates, expand primary non-EU `fuel_prices_eu` exemption set to cover non-EU ProMods territories)
- `bc25ea5` — `HI-04`, `HI-05`, `MD-05`, `LO-01` (`promods_builder.py`, `promods_discovery.py`: enforce strict gitignored output allowlist blocking repo root `.` and tracked dirs, stage + validate Workshop tree and local ZIP before atomic promotion, deduplicate ProMods builder to reuse `BaselineVirtualArchive`/`scan_active_countries()`/`CountryResolver`/`apply_country_policy()`/`apply_speed_limits_policy()`, normalize 3-digit ProMods versions and simplify `_is_st_variant()`)
- `306031b` — `MD-01`, `IN-01` (`promods_fuel.py`: detect `3nK`, add UTF-8 + `cp1252` fallback, reject empty modules, escape backslashes in verbatim preserved values, add `"li"` and `"sm"` prefixes to `PM_EU_PREFIX_TO_ISO2`)
- `d5822a0` — `MD-02`, `MD-07`, `IN-03` (`compose.py`, `hardcoded_totems.py`, `scanner.py`: add per-country/per-board fault isolation, pre-check required third-party map-owned fields before emission, atomic `NamedTemporaryFile` + `os.replace()` for `--report-json`, cache fragment bytes in `scan_active_countries()`)
- `7eeb819` — `MD-04` (`registry/snapshot.py`: validate `anchor_date` via `date.fromisoformat()`, enforce bounded snapshot/checksum reads, eliminate TOCTOU double-read via `_verify_and_parse_snapshot()`)
- `fb10477` — `MD-03` (`validate/invariants.py`, `validate/workshop.py`: reject dangling combo board tokens when `fuel_locales` is absent, cross-check `_NON_SUP_GAS_FONTS` against `<sup>`, reject duplicate `.sui`+`.sii` country slugs, enforce realism `.sii`/`.sui` allowlist)
- `dcf7ac9` — `LO-03`, `LO-04` (`vfs/hashfs.py`, `vfs/dir_archive.py`: record `path_traversal` diagnostics and deduplicate in `HashFs.list_direct_files()`, enforce `MAX_DIR_ENTRY_BYTES = 128 MiB` cap in `DirectoryArchive.read_bytes()`)
- `48f5484` — `MD-06`, `LO-02` (`publish/release.py`, `cli.py`, `.github/workflows/phase-a-release.yml`: track `snapshots_changed` in `PhaseAReleaseSummary`/`$GITHUB_OUTPUT` so non-Core ProMods snapshot updates publish `snapshots-latest` and advance `snapshot_sha256` without bumping Core versions, explicitly distinguish HTTP 404 vs API errors in `gh api`)
- `eccea96` — `LO-04` test compatibility (`tests/test_validate_workshop.py`: intercept `Path.open` alongside `Path.read_bytes` in `test_scs_00006_permission_error_reported_cleanly`)

**Deferred Ops Note:** `MD-06` GitHub Actions commit-SHA pinning keeps `actions/checkout@v4`, `astral-sh/setup-uv@v5`, and `actions/upload-artifact@v4` aligned with `.github/workflows/ci.yml` rather than guessing unverified SHAs offline.

**Post-Fix Final Verification:** `ruff check` (`All checks passed!`), `ruff format --check` (`106 files already formatted`), `basedpyright` (`0 errors, 0 warnings, 0 notes`), zero `# type: ignore` / `# pyright: ignore` hits under `src/ets2v2/`, and full `pytest -q --tb=short` (**505/505 passed**: 504 passed in full sweep + `test_scs_00006_permission_error_reported_cleanly` passed after `eccea96`).

---

_Reviewed: 2026-11-25T13:15:00Z_
_Resolved: 2026-11-25T15:20:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
