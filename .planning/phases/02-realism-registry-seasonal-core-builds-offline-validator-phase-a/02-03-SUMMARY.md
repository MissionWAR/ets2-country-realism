---
phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
plan: "03"
subsystem: package
tags: [sii-synthesis, pillow-icons, workshop-metadata, deterministic-zip, sim-03, cli]

requires:
  - phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
    provides: "36-country law registry, dynamic zoneinfo+tzdata DST resolver, and v1 RealismSnapshot builder (02-01, 02-02)"
provides:
  - "Clean-room ETS2 1.62 .sui and speed_limits.sii synthesizers (src/ets2v2/package/synthesize.py) with zero def.scs dependency"
  - "Reproducible Pillow 276x162 RGB EXIF/ICC-stripped JPEG icon generator (src/ets2v2/package/icons.py, scripts/generate_icons.py) and committed assets/icons/{summer,winter}.jpg"
  - "Workshop/local metadata renderers (src/ets2v2/package/metadata.py) for versions.sii, manifest.sii, and deterministic description.txt"
  - "Dual-target Workshop unpacked + deterministic local ZIP Core packager (src/ets2v2/package/builder.py) and ets2v2 package {icons,build} CLI subcommands"
affects: [02-04, 02-05, phase-3, phase-4, phase-5]

tech-stack:
  added: []
  patterns: [clean-room SII/SUI synthesis with validate_sii_hygiene post-condition, verbatim checked-in clean-room JPEG icons, deterministic 1980-01-01 Unix-0o644 ZIP packaging]

key-files:
  created:
    - src/ets2v2/package/__init__.py
    - src/ets2v2/package/synthesize.py
    - src/ets2v2/package/icons.py
    - src/ets2v2/package/metadata.py
    - src/ets2v2/package/builder.py
    - scripts/generate_icons.py
    - assets/icons/summer.jpg
    - assets/icons/winter.jpg
    - tests/test_package_synthesize.py
    - tests/test_package_icons_metadata.py
    - tests/test_package_builder.py
  modified:
    - src/ets2v2/cli.py

key-decisions:
  - "Exposed format_sii_string() from ets2v2.package.synthesize (rejecting backslash and NUL bytes) and shared it with ets2v2.package.metadata so both synthesizers enforce identical T-02-06 SII string hygiene without private-import suppressions."
  - "Derived default package_version from the seasonal anchor date ISO week (e.g., 1.62-YYYY.WW) when --package-version is omitted so standalone package builds remain 100% deterministic with zero wall-clock date.today() coupling."

patterns-established:
  - "Every synthesized .sui/.sii payload encodes through serialize_sii_text() and asserts validate_sii_hygiene(...) == [] as a hard post-condition before returning bytes."
  - "Dual Core builds stage 76 files under <out_dir>/workshop/<edition>/ (versions.sii + unpacked universal/, never universal.zip alongside universal/, never def/country.sii) and 75 deterministic ZIP entries under <out_dir>/local/ETS2V2_Core_{Summer,Winter}.zip."

requirements-completed: [SIM-03]

duration: 10min
completed: 2026-11-19
status: complete
---

# Phase 2 Plan 03: Clean-Room SII/SUI Synthesizer, Icons, Metadata & Dual Core Packager Summary

**Implemented pure clean-room ETS2 `1.62` `.sui`/`speed_limits.sii` synthesis across all 36 Vanilla+DLC countries, committed reproducible `276x162` EXIF/ICC-stripped `assets/icons/{summer,winter}.jpg`, built Workshop/local metadata emitters and dual-target deterministic Core packager, and wired `ets2v2 package {icons,build}` CLI commands.**

## Accomplishments
- **Task 1 (Tracer — `src/ets2v2/package/synthesize.py`):** Implemented `synthesize_country_sui()` and `synthesize_speed_limits_sii()` strictly from `data/baselines/ets2_1.62_def/*.json` + resolved v1 `RealismSnapshotCountry` with zero `def.scs` dependency. Preserves `1.62` `fuel_price` (D-05), `Estonia` `"Eesti"`, all 5 countries' `regions[]`/`region_areas[]` (`bosnia`, `finland`, `norway`, `spain`, `sweden`), Russia Kaliningrad `secondary_time_zone*`, 8 West Balkans quoted vs 28 unquoted `iso_country_code`, 24 countries' `train`/`tram` rail blocks, `bulgaria`/`romania`/`turkey` `slow_road` + `uncommon`, `romania`/`sweden` `max_limit`, Germany `0` unlimited Autobahn, Iceland 5-element 60t axle array & 80 km/h heavy truck, UK imperial mph/`leftside_traffic`, Croatia seasonal DRL, and Finland/Estonia/Lithuania seasonal car speeds. Verified 100% `validate_sii_hygiene()` pass and lossless round-trip parity through `parse_country_data()` and `parse_speed_limits()` across all 36 countries in both Summer and Winter.
- **Task 2 (`src/ets2v2/package/icons.py`, `scripts/generate_icons.py`, `assets/icons/{summer,winter}.jpg`, `src/ets2v2/package/metadata.py`):**
  - Built clean-room Pillow `276x162` RGB baseline JPEG renderer (`quality=92`, `optimize=True`, `progressive=False`, `subsampling=0`, zero EXIF/ICC) and generated checked-in icons via `scripts/generate_icons.py`:
    - `assets/icons/summer.jpg`: `20,580` bytes, SHA-256 `8e1222dc15fc3a395cad8f602792f6927fbc9ec08e8e0a43075a4f73be95937f`
    - `assets/icons/winter.jpg`: `17,054` bytes, SHA-256 `b25bfd161016c807d2d17d86d3c2ce784c96dd1368bcc5ebf4bfdd834dc383c0`
  - Built `render_versions_sii()` (`.universal` -> `"universal"`), `render_manifest_sii()` (Workshop mode strictly omitting `display_name` and `compatible_versions[]`; local mode adding `display_name` while still omitting `compatible_versions[]`; `category[] = ["other", "ai_traffic"]`, `mp_mod_optional: true`), and deterministic UTF-8 no-BOM LF `render_description_txt()` (`MIT` / `CC BY 4.0` attribution, zero volatile timestamps or `package_version` strings).
- **Task 3 (`src/ets2v2/package/builder.py`, `src/ets2v2/cli.py`):**
  - Implemented `BuiltEditionPaths`, `build_core_edition()`, and `build_core_editions()` with path-traversal and root-containment guards (`normalize_vfs_path()` + `resolve().is_relative_to()`), copying checked-in icons verbatim into 76-file `<out_dir>/workshop/<edition>/` unpacked trees (no `universal.zip`, no `def/country.sii`) and 75-entry `<out_dir>/local/ETS2V2_Core_{Summer,Winter}.zip` archives (`date_time=(1980, 1, 1, 0, 0, 0)`, `create_system=3`, `external_attr=0o100644 << 16`, `ZIP_DEFLATED`, `compresslevel=6`, sorted POSIX paths).
  - Verified byte-identical outputs across independent runs and clean mounting in `ets2v2.vfs.ZipArchive` and `VfsStack`.
  - Wired `ets2v2 package icons` and `ets2v2 package build` into `src/ets2v2/cli.py`.

## Deviations from Plan
None - plan executed as written.

## Verification
- `uv run --offline ruff check`: exit 0 (`All checks passed!`)
- `uv run --offline ruff format --check`: exit 0 (`49 files already formatted`)
- `uv run --offline ruff check scripts/generate_icons.py && uv run --offline ruff format --check scripts/generate_icons.py`: exit 0 (`All checks passed!`, `1 file already formatted`)
- `uv run --offline basedpyright`: exit 0 (`0 errors, 0 warnings, 0 notes`)
- `uv run --offline pytest tests/test_package_synthesize.py tests/test_package_icons_metadata.py tests/test_package_builder.py tests/test_cli_scaffold.py -x`: exit 0 (`37 passed in 1.95s`)
- `uv run --offline pytest tests/test_registry_snapshot.py -x`: exit 0 (`4 passed in 0.27s`)

## Self-Check: PASSED
- Verified all 11 created files and 1 modified file exist on disk and pass offline lint, format, strict type-checking, and targeted test suites.
- Left git commits, `STATE.md`, and `ROADMAP.md` untouched for orchestrator handling as instructed.

---
*Phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a*
*Completed: 2026-11-19*
