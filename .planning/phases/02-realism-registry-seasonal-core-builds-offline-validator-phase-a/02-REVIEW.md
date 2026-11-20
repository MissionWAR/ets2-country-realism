---
phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
reviewed: 2026-11-19T23:05:00Z
depth: deep
files_reviewed: 43
files_reviewed_list:
  - .github/workflows/phase-a-release.yml
  - pyproject.toml
  - scripts/generate_icons.py
  - state/published.json
  - src/ets2v2/cli.py
  - src/ets2v2/registry/__init__.py
  - src/ets2v2/registry/models.py
  - src/ets2v2/registry/loader.py
  - src/ets2v2/registry/timezone.py
  - src/ets2v2/registry/snapshot.py
  - src/ets2v2/package/__init__.py
  - src/ets2v2/package/synthesize.py
  - src/ets2v2/package/icons.py
  - src/ets2v2/package/metadata.py
  - src/ets2v2/package/builder.py
  - src/ets2v2/validate/__init__.py
  - src/ets2v2/validate/models.py
  - src/ets2v2/validate/workshop.py
  - src/ets2v2/validate/invariants.py
  - src/ets2v2/publish/__init__.py
  - src/ets2v2/publish/ledger.py
  - src/ets2v2/publish/changelog.py
  - src/ets2v2/publish/release.py
  - data/mappings/ets2_countries.json
  - data/laws/countries/fi.json
  - data/laws/countries/gb.json
  - data/laws/countries/hr.json
  - data/laws/countries/is.json
  - data/laws/countries/ru.json
  - data/laws/countries/tr.json
  - tests/test_cli_scaffold.py
  - tests/test_registry_schema.py
  - tests/test_registry_contracts.py
  - tests/test_registry_timezone.py
  - tests/test_registry_snapshot.py
  - tests/test_package_synthesize.py
  - tests/test_package_icons_metadata.py
  - tests/test_package_builder.py
  - tests/test_validate_workshop.py
  - tests/test_validate_invariants.py
  - tests/test_publish_ledger.py
  - tests/test_publish_release.py
  - tests/test_publish_workflow.py
findings:
  critical: 1
  high: 4
  medium: 5
  low: 5
  warning: 10
  info: 3
  total: 18
status: resolved
resolved_date: 2026-11-20
---

# Phase 02: Code Review Report

**Reviewed:** 2026-11-19T23:05:00Z
**Depth:** deep
**Files Reviewed:** 43 (plus programmatic invariant spot-check across all 36 `data/laws/countries/*.json`, cross-file call-chain inspection of `src/ets2v2/sii/{country,hygiene}.py` and `src/ets2v2/vfs/{types,dir_archive,zip_archive}.py`, and verification against official SCS Workshop Uploader documentation)
**Status:** issues_found

## Summary

Deep adversarial review of Phase 2 (`02-01`..`02-05`, commit range `6330e88..HEAD`) covering the canonical 36-country realism registry (`registry/`), clean-room seasonal Core packager (`package/`), package-independent Offline SCS Workshop Validator & 1.62 invariants (`validate/`), Phase A diff-gated release orchestrator (`publish/`), CLI wiring (`cli.py`), `.github/workflows/phase-a-release.yml`, `pyproject.toml`, `scripts/generate_icons.py`, `state/published.json`, `data/mappings/ets2_countries.json`, `data/laws/countries/*.json`, and all Phase 2 test suites.

Note on reference docs: `~/.gemini/antigravity/gsd-core/references/necessity-review.md` and `~/.gemini/antigravity/gsd-core/references/cicd-review-patterns.md` were unreadable due to sandbox path protection boundaries. Per review rules, `necessity:` is omitted from frontmatter, and CI/CD review used the built-in pipeline checklist.

**Key positive verifications:**
- **Layer 7 DAG boundary is clean:** `src/ets2v2/validate/` has zero imports (absolute or relative) from `ets2v2.package`, `ets2v2.registry`, or `ets2v2.publish`.
- **Canonical law data (`data/mappings/ets2_countries.json` + all 36 `data/laws/countries/*.json`) is clean:** exact 36 Vanilla+DLC country set, consistent seasonal diffs (`EE`/`FI`/`LT` winter car speed drops, `HR` winter DRL), and zero anomalous speed/mass inversions.
- **Deterministic ZIP metadata (`package/builder.py`)** pins timestamps (`1980-01-01`), Unix mode (`0o100644`), `create_system=3`, sorted POSIX entry order, and explicit deflate level `6`.

**Blocking defects requiring fixes before ship (1 CRITICAL, 4 HIGH):**
1. **`CR-01` (CRITICAL):** `.github/workflows/phase-a-release.yml:68-72` embeds escaped `\"` inside Python 3.12 f-string expressions in a single-quoted `python -c '...'` block, causing an unconditional `SyntaxError: unexpected character after line continuation character` on every scheduled and manual workflow run.
2. **`HI-01` (HIGH):** `src/ets2v2/package/synthesize.py:129-134` ignores `resolved.driving_tired_offence` and `resolved.fuel.eur_per_liter`, silently emitting stale 1.62 `baseline` values instead.
3. **`HI-02` (HIGH):** `src/ets2v2/validate/workshop.py:75-95,733-858` uses an 18-item extension denylist instead of an SCS asset allowlist, silently passing `.zip`, `.png`, `.bak`, `.log`, `Thumbs.db`, and `.DS_Store` files that the real SCS Workshop Uploader rejects with `00003`.
4. **`HI-03` (HIGH):** `src/ets2v2/validate/workshop.py:368-390,900-1035` leaves `ZipArchive(pkg_zip)` unguarded against `PermissionError`/`OSError`/`ValueError`, allows root-level symlinks (`versions.sii`, `universal/`) to escape `workshop_dir`, and fails to detect duplicate/shadowed ZIP entries in `_inspect_raw_zip`.
5. **`HI-04` (HIGH):** `src/ets2v2/validate/workshop.py:295-331,484-662,928-970` misses several SCS Workshop protocol checks (unquoted SII string literals, scalar `category:` instead of `category[]`, illegal extra units in `versions.sii`/`manifest.sii`, duplicate `package_name` entries, non-RGB/progressive JPEGs) and unsafely mutates global `Image.MAX_IMAGE_PIXELS` before checking `img.size`.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Python 3.12 `SyntaxError` in `phase-a-release.yml` crashes every release run [CRITICAL / BLOCKER]

**File:** `.github/workflows/phase-a-release.yml:63-73` (test gap: `tests/test_publish_workflow.py:134-155`)
**Issue:** The inline `uv run --offline python -c '...'` script that writes `dist/release_summary.json` fields to `$GITHUB_OUTPUT` uses backslash-escaped double quotes (`\"`) inside double-quoted f-string expressions:
```python
fh.write(f"any_changed={str(summary[\"any_changed\"]).lower()}\n")
...
fh.write(f"changed_editions={\",\".join(summary[\"changed_editions\"])}\n")
```
Because the script is wrapped in bash single quotes (`'...'`), bash passes `\"` literally to Python 3.12 without unescaping. Even under PEP 701, an escaped `\"` inside an f-string expression `{...}` is invalid syntax and raises `SyntaxError: unexpected character after line continuation character` (verified directly with `.venv/Scripts/python.exe`). Every Friday cron run and every `workflow_dispatch` run will crash at `Run Phase A diff-gated release build` before validating, uploading artifacts, or opening the Release PR. `tests/test_publish_workflow.py` only performed text substring checks and never compiled the embedded Python code.
**Fix:** Use single quotes inside double-quoted f-strings (or pass a heredoc `uv run --offline python - <<'PY'`) with plain dict keys, and add a `compile()` check for embedded Python snippets in `tests/test_publish_workflow.py`:
```yaml
          uv run --offline python - <<'PY'
          import json, os, pathlib

          summary = json.loads(pathlib.Path("dist/release_summary.json").read_text("utf-8"))
          out = pathlib.Path(os.environ["GITHUB_OUTPUT"])
          with out.open("a", encoding="utf-8") as fh:
              fh.write(f"any_changed={str(summary['any_changed']).lower()}\n")
              fh.write(f"summer_changed={str(summary['summer_changed']).lower()}\n")
              fh.write(f"winter_changed={str(summary['winter_changed']).lower()}\n")
              fh.write(f"changed_editions={','.join(summary['changed_editions'])}\n")
              fh.write(f"force_run={str(summary['force_run']).lower()}\n")
          PY
```

## High Issues

### HI-01: `synthesize_country_sui()` ignores `resolved.driving_tired_offence` and `resolved.fuel.eur_per_liter` [HIGH / BLOCKER]

**File:** `src/ets2v2/package/synthesize.py:129-134` (masked by `tests/test_package_synthesize.py:90-93`)
**Issue:** `CountryLawRecord` (`registry/models.py:85`), `RealismSnapshotCountry` (`registry/snapshot.py:54,127,131-136`), and `publish/changelog.py:37-41,51-55` all treat `driving_tired_offence` and `fuel.eur_per_liter` as resolved realism outputs. However, `synthesize_country_sui()` ignores both fields on `resolved` and emits frozen 1.62 baseline values instead:
```python
    if baseline.fuel_price is not None:
        lines.append(f"\tfuel_price: {_format_fuel_price(baseline.fuel_price)}")

    lines.append(f"\tlights_mandatory: {_format_bool(resolved.lights_mandatory)}")
    if baseline.driving_tired_offence is not None:
        lines.append(f"\tdriving_tired_offence: {_format_bool(baseline.driving_tired_offence)}")
```
If any country's `driving_tired_offence` is updated in `data/laws/countries/<iso2>.json` (or when Phase 3 populates live `resolved.fuel.eur_per_liter`), `realism-snapshot-*.json` and `CHANGELOG_*.md` will report the new values while the synthesized `.sui` mod silently emits the old baseline values—and `compute_workshop_canonical_sha256()` will report zero change, causing `publish release` to NO-OP. This was masked in `tests/test_package_synthesize.py:93` because the test asserted equality against `bl_country.driving_tired_offence` on inputs where all 36 countries currently share `true`.
**Fix:** Emit `resolved.fuel.eur_per_liter` and `resolved.driving_tired_offence` in `synthesize_country_sui()`:
```python
    lines.append(f"\tfuel_price: {_format_fuel_price(resolved.fuel.eur_per_liter)}")
    lines.append(f"\tlights_mandatory: {_format_bool(resolved.lights_mandatory)}")
    lines.append(f"\tdriving_tired_offence: {_format_bool(resolved.driving_tired_offence)}")
```
Add a regression test in `tests/test_package_synthesize.py` mutating `resolved.driving_tired_offence = False` and `resolved.fuel.eur_per_liter = 1.999` and asserting the synthesized `.sui` reflects both.

### HI-02: Offline SCS Workshop Validator uses a partial extension denylist and silently passes unsupported files [HIGH / BLOCKER]

**File:** `src/ets2v2/validate/workshop.py:75-95, 733-858`
**Issue:** `_validate_package_contents()` rejects only the 18 extensions in `FORBIDDEN_EXTENSIONS` and `.scs`, then silently falls through for every unrecognized file type (`.zip`, `.png`, `.bmp`, `.webp`, `.bak`, `.log`, `.tmp`, `.db`/`Thumbs.db`, `.DS_Store`, arbitrary binaries). Per official SCS Workshop Uploader validation rules (`00003`: *"File with the unsupported extension found in the mod"*), SCS enforces a strict allowlist of supported asset formats and rejects nested `.zip`, `.png`, `.bak`, `.log`, and OS metadata files on upload. Additionally, when `baseline_dir=None`, `workshop.py:860-874` only checks for missing expected country slugs and does not flag extra/stray `def/country/*.sui` files.
**Fix:** Replace the open-ended fallthrough with an explicit allowlist of valid SCS Workshop asset extensions (for Core packages or general SCS mods: `.sii`, `.sui`, `.txt`, `.jpg`, `.dds`, `.tobj`, `.mat`, `.pmd`, `.pmg`, `.pmc`, `.pma`, `.ppd`, `.ogg`, `.bank`, `.guids`, `.soundref`, `.font`, `.mask`, `.sbd`) and emit `00003` for any file whose extension is outside the allowlist (or extensionless).

### HI-03: Unguarded `ZipArchive(pkg_zip)` open, root symlink escape, and ZIP duplicate-entry shadowing in Workshop validator [HIGH / BLOCKER]

**File:** `src/ets2v2/validate/workshop.py:368-390, 895-912, 971-1035`
**Issue:** Three archive/filesystem boundary gaps in `validate/workshop.py`:
1. **Uncaught exception on `pkg_zip` mount (line 1016):** Unlike `DirectoryArchive` (lines 986–993) and `validate_local_zip` (lines 1091–1098), `validate_workshop_package` instantiates `ZipArchive(pkg_zip)` with no `try/except`, so a TOCTOU `PermissionError`, `OSError`, or `ValueError` crashes instead of recording `00006`/`00008`.
2. **Root-level symlink escape (lines 900, 984, 1013):** `versions_path.is_file()`, `pkg_dir.is_dir()`, and `pkg_zip.is_file()` follow symlinks. Because `DirectoryArchive(pkg_dir)` anchors `_resolved_root` to `pkg_dir.resolve()`, a symlink `workshop_dir/universal -> /outside/path` (or symlinked `versions.sii`) escapes `workshop_dir` without triggering `00003` (inconsistent with `publish/ledger.py:67-68`).
3. **Duplicate ZIP entry shadowing (lines 368–390):** `_inspect_raw_zip` never checks for duplicate normalized ZIP entry names (e.g. two `manifest.sii` entries or `./manifest.sii` + `manifest.sii`). Because `ZipArchive._load_central_directory` (`zip_archive.py:125`) overwrites `self._entries[norm]` (last-wins) without diagnostics, a ZIP containing two conflicting entries for the same path passes validation even though ETS2 may read the first entry while the validator only audits the second.
**Fix:**
- Wrap `ZipArchive(pkg_zip)` at line 1016 in `try/except PermissionError` (`00006`) and `except (OSError, ValueError)` (`00008`).
- Check `is_symlink()` / `_is_dir_junction()` and `path.resolve().is_relative_to(workshop_dir.resolve())` on `versions.sii`, `pkg_dir`, and `pkg_zip` before reading/mounting, emitting `00003` on violations.
- Track `seen_norm: set[str]` in `_inspect_raw_zip()` (skipping directory entries) and emit `00003` when a normalized path appears more than once or when `raw_name != normalize_vfs_path(raw_name)` (catching `./` or `//`).

### HI-04: SCS protocol validation gaps in `manifest.sii`, `versions.sii`, and icon inspection (plus thread-unsafe `Image.MAX_IMAGE_PIXELS` mutation) [HIGH / BLOCKER]

**File:** `src/ets2v2/validate/workshop.py:295-331, 484-662, 928-970`
**Issue:**
1. **Unquoted SII strings and non-array `category` accepted (`workshop.py:530-662, 958`):** `_validate_manifest()` and `validate_workshop_package()` discard the `was_quoted` boolean returned by `unquote_sii_string()`, accepting unquoted tokens such as `author: nil` or `package_name: universal`. `mod_unit.get_attributes("category")` (line 561) also accepts scalar `category: "other"` (missing `[]`) and duplicate `category[]` entries.
2. **Illegal extra unit classes & duplicate `package_name` accepted (`workshop.py:484, 928-970`):** Neither `manifest.sii` nor `versions.sii` checks `len(doc.units)` against the allowed unit class, allowing stray units (e.g. `country_data` inside `versions.sii` or `manifest.sii`, which SCS rejects with `00003`). In `versions.sii`, declaring the same `package_name` in two `package_version_info` units is never flagged and causes the same directory to be validated twice.
3. **Icon validation order, color mode, and global state mutation (`workshop.py:298-331`):** `_validate_icon_bytes()` mutates process-global `Image.MAX_IMAGE_PIXELS` without a lock (racy under concurrent validation), runs `decoded.load()` *before* verifying `size == REQUIRED_ICON_SIZE`, and never checks `img.mode == "RGB"` or `img.info.get("progressive")` (SCS Workshop Uploader rejects CMYK and certain progressive JPEGs, and `tests/test_package_icons_metadata.py:47,53` requires baseline RGB).
**Fix:**
- Assert `was_quoted is True` on `package_version`, `author`, `display_name`, `icon`, `description_file`, `category[]`, and `package_name`.
- Require `attr.is_append or attr.index is not None` and unique values for `category[]`.
- Reject any unit in `manifest.sii` whose `class_name != "mod_package"` and any unit in `versions.sii` whose `class_name != "package_version_info"` (`00003`), and reject duplicate `package_name` values in `versions.sii`.
- In `_validate_icon_bytes()`, inspect `img.format`, `img.size`, `img.mode`, and `img.info.get("progressive")` during the header open and fail fast on `size != REQUIRED_ICON_SIZE` or `mode != "RGB"` or `progressive` *before* calling `decoded.load()`, checking `size[0] * size[1] > MAX_ICON_PIXELS` directly instead of mutating process-global `Image.MAX_IMAGE_PIXELS`.

## Medium Issues

### MD-01: Cross-platform case-sensitivity bug in `validate_law_registry()` silently skips `.JSON` files on Linux and ignores stray subdirectories [MEDIUM / WARNING]

**File:** `src/ets2v2/registry/loader.py:252-258`
**Issue:** Line 253 flags stray files using `p.is_file() and p.suffix.lower() != ".json"`, while line 258 discovers law files via `countries_dir.glob("*.json")`. On Linux (`ubuntu-latest`), `glob("*.json")` is case-sensitive, so a file named `de.JSON` is skipped by *both* checks (silently ignored in CI!), whereas on Windows it is matched by `glob` and rejected at line 281. In addition, stray subdirectories inside `data/laws/countries/` containing non-`.sii`/`.sui` files are ignored by `p.is_file()`.
**Fix:**
```python
        for entry in sorted(countries_dir.iterdir(), key=lambda p: p.name):
            if not entry.is_file():
                issues.append(f"Unexpected non-file entry in {countries_dir}: {entry.name}")
            elif entry.suffix != ".json":
                issues.append(f"Unexpected non-JSON file in {countries_dir}: {entry.name}")
```

### MD-02: `previous_snapshots` is unwired in CLI and release workflow, leaving structured snapshot-diff changelogs unreachable in production [MEDIUM / WARNING]

**File:** `src/ets2v2/publish/release.py:131, 253-267`, `src/ets2v2/cli.py:383-422`, `.github/workflows/phase-a-release.yml:50-62`
**Issue:** `run_phase_a_release()` supports `previous_snapshots: Mapping[Season, RealismSnapshot] | None = None` to generate `## Changes Since Previous Snapshot` in `CHANGELOG_{SUMMER,WINTER}.md`, but `ets2v2 publish release` in `cli.py` neither accepts a `--previous-snapshots-dir` flag nor loads previously emitted snapshots. In every post-initial CI run, `prev_snap` is `None`, so `CHANGELOG_*.md` displays `Previous Version: 1.62-2026.xx` while overwriting the body with the hardcoded initial-release highlights (`_render_initial_highlights`) instead of actual country diffs. Also, on `force_run=True` with no content changes, `Previous Version` equals `Package Version`.
**Fix:** Expose `--previous-snapshots-dir` on `ets2v2 publish release` (or persist/commit the last released snapshots under `state/` alongside `state/published.json`), pass loaded previous snapshots to `run_phase_a_release()`, and avoid rendering `Previous Version == Package Version` on forced unchanged rebuilds.

### MD-03: Full-file memory read for 4-byte `.scs` magic check in `workshop.py` and missing Windows NTFS junction check in `ledger.py` [MEDIUM / WARNING]

**File:** `src/ets2v2/validate/workshop.py:1052-1054`, `src/ets2v2/publish/ledger.py:66-76`
**Issue:**
1. `workshop.py:1054` reads `magic = entry.read_bytes()[:4]`, which loads an entire extraneous `.scs` file (potentially multi-GB game archives) into RAM just to check 4 header bytes (unlike `workshop.py:344-345` which properly uses `fh.read(4)`).
2. `ledger.py:66-70` walks `workshop_dir.rglob("*")` and checks `candidate.is_symlink()`. On Windows Python 3.12, `Path.is_symlink()` returns `False` for NTFS directory junctions (unlike `dir_archive.py:21-24`), allowing empty escaping junctions or self-referential junction recursion loops inside `workshop_dir`.
**Fix:** Use `with entry.open("rb") as fh: magic = fh.read(4)` in `workshop.py:1054`, and walk `workshop_dir` with `os.walk(..., followlinks=False)` checking both `is_symlink()` and `is_junction()` in `ledger.py:66-76`.

### MD-04: Tautological `assert_leftside_traffic_immutable` call in `snapshot.py` and fragile `observes_dst` calculation in `timezone.py` [MEDIUM / WARNING]

**File:** `src/ets2v2/registry/snapshot.py:98-102`, `src/ets2v2/registry/timezone.py:82-88`
**Issue:**
1. `snapshot.py:98-102` calls `assert_leftside_traffic_immutable(law.ets2_slug, bl_country.leftside_traffic, bl_country.leftside_traffic)`. Comparing a value against itself can never fail and provides no runtime protection.
2. `timezone.py:82-88` computes `observes_dst = jan_offset != jul_offset`. For any IANA zone that permanently changes its standard UTC offset between January 15 and July 15 of `ref_date.year` without DST (e.g., `Asia/Almaty` in 2024), `jan_offset != jul_offset` falsely reports `observes_dst=True` even though `dst()` is `0` on both dates. (Also note for future expansion to Ireland: `Europe/Dublin` uses IANA negative DST, where `dt.dst()` is `0` in summer and `-1h` in winter.)
**Fix:** Remove the tautological call in `snapshot.py` (or enforce `assert_leftside_traffic_immutable` at a real boundary where baseline and synthesized/candidate values differ), and compute `observes_dst` from `bool(jan_dst) or bool(jul_dst)` via `datetime(..., tzinfo=tz).dst()`.

### MD-05: `validate_core_realism_invariants()` misses duplicate/extra lane classes, added `uncommon` flags, and `max_limit` nullability parity [MEDIUM / WARNING]

**File:** `src/ets2v2/validate/invariants.py:243-269, 289-308`
**Issue:**
1. Lines 245–246 convert `cand_block.lanes` to a dict keyed by `lane_speed_class`, silently collapsing duplicate lane definitions and ignoring extra or misordered lanes.
2. Line 264 (`elif base_lane.uncommon is not None and cand_lane.uncommon != base_lane.uncommon`) fails to catch `uncommon` being erroneously added where the baseline has `uncommon=None`.
3. Line 299–301 (`lane.max_limit is not None and lane.max_limit != _ICELAND_HEAVY_TRUCK_LIMIT`) passes if `max_limit[]` is accidentally deleted from Iceland's `truck` speed block (`max_limit=None`), and `invariants.py` does not check `(cand_lane.max_limit is None) == (base_lane.max_limit is None)` across countries (unlike `registry/loader.py:204`).
**Fix:** Compare ordered lane lists `[l.lane_speed_class for l in cand_block.lanes] == [l.lane_speed_class for l in base_block.lanes]`, check `cand_lane.uncommon != base_lane.uncommon` unconditionally, and assert `(cand_lane.max_limit is None) == (base_lane.max_limit is None)` (plus `lane.max_limit == _ICELAND_HEAVY_TRUCK_LIMIT` for Iceland truck lanes).

## Low Issues

### LO-01: CI/CD hardening in `phase-a-release.yml` (mutable tags under write permissions, hardcoded `master` base, and `&&` loop exit status) [LOW / WARNING]

**File:** `.github/workflows/phase-a-release.yml:14-16, 30, 33, 89, 111-113, 134, 138`
**Issue:**
1. Unlike read-only `ci.yml`, `phase-a-release.yml` runs with `permissions: contents: write` and `pull-requests: write`, yet pins `actions/checkout@v4`, `astral-sh/setup-uv@v5`, and `actions/upload-artifact@v4` to mutable major tags rather than full commit SHAs. (Note: `tests/test_publish_workflow.py:90-92` currently asserts exact `@v4`/`@v5` strings and would need a coordinated update.)
2. Triggering `workflow_dispatch` on a non-`master` feature branch will force-push that branch's commits onto `release/phase-a-weekly` and open/update a PR targeting hardcoded `--base master`.
3. Lines 111–113 use `[ -f "$f" ] && git add "$f"` under `set -euo pipefail`. While GNU bash suppresses `errexit` on the `for` loop itself, the loop exits with `$? = 1` whenever `CHANGELOG_WINTER.md` does not exist; `if [ -f "$f" ]; then git add "$f"; fi` is cleaner and safer across POSIX shells (requires updating `tests/test_publish_workflow.py:103`).
**Fix:** Pin actions to commit SHAs with `# v4`/`# v5` comments, guard the PR step to `github.ref == 'refs/heads/master'` (or derive base from `github.event.repository.default_branch`), and prefer `if [ -f "$f" ]; then git add "$f"; fi`.

### LO-02: Local-timezone `date.today()` default in `run_phase_a_release()` and non-ASCII `isdigit()` edge case in `resolve_next_package_version()` [LOW / WARNING]

**File:** `src/ets2v2/publish/release.py:134`, `src/ets2v2/publish/ledger.py:118`
**Issue:** `date.today()` depends on the host OS timezone, so local invocations near the Sunday/Monday midnight ISO-week boundary can compute a different week number than UTC CI runners. In `ledger.py:118`, `suffix.isdigit()` returns `True` for Unicode superscripts such as `"²"`, causing `int(suffix)` to raise `ValueError`.
**Fix:** Use `datetime.now(UTC).date()` in `release.py:134` and `suffix.isascii() and suffix.isdigit()` in `ledger.py:118`.

### LO-03: Changelog diff formatter can emit identical before/after strings for `max_limit`, `uncommon`, `currency`, or `local_prices` changes [LOW / WARNING]

**File:** `src/ets2v2/publish/changelog.py:12-19, 47-55`
**Issue:** `_format_speed_summary()` omits `max_limit` and `uncommon`, and lines 51–55 omit `fuel.currency` and `fuel.local_prices`. When only `max_limit` (e.g., Romania/Sweden truck lanes) or `fuel.local_prices` (Phase 3) changes, `prev != curr` is `True` yet the rendered bullet prints identical values on both sides of `->`.
**Fix:** Include `max_limit` (when not `None` and differing from `limit`), `uncommon`, `fuel.currency`, and changed `fuel.local_prices` entries in the diff summary.

### LO-04: 1-element `extra_attributes` array coercion, non-directory `workshop_dir` cleanup crash, and CWD-relative icon script [LOW / WARNING]

**File:** `src/ets2v2/package/synthesize.py:175-185`, `src/ets2v2/package/builder.py:191-193`, `scripts/generate_icons.py:10`
**Issue:**
1. `synthesize.py:175` uses `len(raw_values) == 1` to decide scalar vs `[]` array emission; any future ETS2 1-element array in `extra_attributes` will be coerced into a scalar (and an empty list emits a stray blank line).
2. `builder.py:191-192` runs `if workshop_dir.exists(): shutil.rmtree(workshop_dir)`, which raises `NotADirectoryError` if a stray file occupies `workshop_dir`.
3. `scripts/generate_icons.py:10` writes to CWD-relative `Path("assets/icons")` instead of anchoring to the repo root via `Path(__file__).resolve().parent.parent / "assets" / "icons"`.
**Fix:** Preserve scalar vs array distinction for `extra_attributes` (and guard empty lists), check `workshop_dir.is_file()` / `workshop_dir.is_symlink()` before `rmtree`, and anchor `scripts/generate_icons.py` to `Path(__file__).resolve().parent.parent / "assets" / "icons"`.

### LO-05: `_handle_registry_validate()` and `validate_law_registry()` do not handle `OSError`/`UnicodeDecodeError` consistently with other CLI handlers [LOW / WARNING]

**File:** `src/ets2v2/cli.py:182-193`, `src/ets2v2/registry/loader.py:231, 263, 325-337`
**Issue:** Unlike every other Phase 2 CLI handler (`_handle_registry_snapshot`, `_handle_package_build`, `_handle_validate_*`, `_handle_publish_release`), `_handle_registry_validate` does not wrap execution in `try/except (OSError, ValueError, ValidationError)`, and `validate_law_registry` calls `.read_bytes()` / `.read_text("utf-8")` without catching `PermissionError`/`OSError`/`UnicodeDecodeError`. Unreadable files or corrupted baseline UTF-8 produce raw Python tracebacks instead of clean exit-1 error messages or JSON output.
**Fix:** Catch `OSError`/`UnicodeDecodeError` in `validate_law_registry` (recording entries in `issues`) and guard `load_law_registry` inside `_handle_registry_validate`.

## Info

### IN-01: Seven Phase 2 functions exceed 150–400 lines

**File:** `src/ets2v2/cli.py:454-860`, `src/ets2v2/registry/loader.py:212-420`, `src/ets2v2/validate/workshop.py:452-662, 708-877, 880-1066`, `src/ets2v2/publish/release.py:117-316`, `src/ets2v2/validate/invariants.py:48-221`
**Issue:** `build_parser` (407 lines), `_validate_manifest` (211 lines), `validate_law_registry` (209 lines), `run_phase_a_release` (200 lines), `validate_workshop_package` (187 lines), `_check_country_identity_and_laws` (174 lines), and `_validate_package_contents` (170 lines) combine multiple concerns in single functions (continuing Phase 1 `IN-01`).
**Fix:** Extract per-subcommand parser builders in `cli.py`, per-attribute manifest checks in `workshop.py`, and staging/emission helpers in `release.py`.

### IN-02: Duplicated SII formatters, canonical JSON serializers, and baseline-loading helpers across modules

**File:** `src/ets2v2/package/synthesize.py:20-27, 51-57` vs `src/ets2v2/sii/country.py:102-117`; `src/ets2v2/registry/loader.py:29-33` vs `src/ets2v2/publish/ledger.py:125-129` vs `src/ets2v2/publish/release.py:111-114`; `src/ets2v2/cli.py:242-253` vs `src/ets2v2/package/builder.py:126-141` vs `src/ets2v2/publish/release.py:137-148`
**Issue:** Identical helper logic is repeated across three to four modules, increasing drift risk.
**Fix:** Export shared `format_sii_string`/`format_fuel_price` from `ets2v2.sii`, a single canonical JSON byte serializer helper, and a shared baseline-bundle loader in `ets2v2.baseline`.

### IN-03: DAG-isolation AST test does not inspect relative `ImportFrom` statements

**File:** `tests/test_validate_workshop.py:87-109`
**Issue:** `test_validate_package_has_zero_imports_from_ets2v2_package()` checks absolute `ets2v2.package` imports, so a future relative import such as `from ..package import builder` (`node.level > 0`, `node.module == "package"`) would not be caught. (Manual review confirmed zero such imports currently exist.)
**Fix:** Extend the `ast.ImportFrom` branch in `test_validate_package_has_zero_imports_from_ets2v2_package` to also reject `node.level > 0` imports targeting `package`.

---

## Resolution Summary (2026-11-20)

All 15 actionable findings (`CR-01`, `HI-01`..`HI-04`, `MD-01`..`MD-05`, `LO-01`..`LO-05`) and `IN-03` were fixed with targeted regression tests and re-verified (`uv run --offline ruff check`, `uv run --offline ruff format --check`, `uv run --offline basedpyright`, and `249 passed` across all 23 test modules).

_Reviewed: 2026-11-19T23:05:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
