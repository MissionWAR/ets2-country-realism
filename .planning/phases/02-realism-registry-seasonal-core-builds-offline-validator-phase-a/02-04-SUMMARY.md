---
phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
plan: "04"
subsystem: validate
tags: [scs-workshop-validator, offline-validation, realism-invariants, pillow, zip-hygiene, pub-01, cli]

requires:
  - phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
    provides: "Dual-target Summer/Winter Core Workshop unpacked trees and deterministic local ZIPs (02-03), 1.62 clean-room baselines, and SII/VFS engines (Phase 1)"
provides:
  - "Frozen Pydantic v2 ValidationIssue, ValidationReport, and deduplicating ValidationCollector models treating warnings as hard failures per D-09 (src/ets2v2/validate/models.py)"
  - "Package-independent Offline SCS Workshop Validator enforcing SCS 00001-00010 and WARN 00001/00002 with raw zipfile.ZipFile.infolist() inspection and Pillow icon verification (src/ets2v2/validate/workshop.py)"
  - "ETS2 1.62 core realism invariant auditor catching all reference-mod regressions across country metadata, regions, Kaliningrad secondary TZ, axle ceilings, Iceland 60t/80 km/h, rail/slow_road blocks, and 12-key @@tz_*@@ whitelist (src/ets2v2/validate/invariants.py)"
  - "Public facade (src/ets2v2/validate/__init__.py) and ets2v2 validate {workshop,local} CLI subcommands (src/ets2v2/cli.py)"
affects: [02-05, phase-3, phase-4, phase-5]

tech-stack:
  added: []
  patterns: [acyclic Layer-7 package-independent validator DAG enforced via AST test, raw zipfile central-directory pre-normalization hygiene inspection, Pillow pixel-capped JPEG verification before decode, warnings-as-hard-failures ValidationReport]

key-files:
  created:
    - src/ets2v2/validate/__init__.py
    - src/ets2v2/validate/models.py
    - src/ets2v2/validate/workshop.py
    - src/ets2v2/validate/invariants.py
    - tests/test_validate_workshop.py
    - tests/test_validate_invariants.py
  modified:
    - src/ets2v2/cli.py

key-decisions:
  - "Included EXPECTED_CORE_COUNTRY_SLUGS (all 36 Vanilla+DLC slugs) in ets2v2.validate.workshop as the default completeness set when baseline_dir is omitted, while deriving expected slugs and running full validate_core_realism_invariants() whenever baseline_dir is supplied (defaulting in CLI to data/baselines/ets2_1.62_def)."
  - "Recorded both error 00010 and warning WARN 00002 when compatible_versions[] is set in Workshop manifest.sii, and WARN 00002 for unknown mod_package attributes, ensuring every SCS Workshop warning fails ValidationReport.ok hard per D-09."

patterns-established:
  - "src/ets2v2/validate/ has strictly zero imports from ets2v2.package (verified by AST scan in tests/test_validate_workshop.py), auditing compiled artifacts independently through ets2v2.vfs, ets2v2.sii, ets2v2.baseline.models, and Pillow."
  - "Raw zipfile.ZipFile.infolist() inspection runs BEFORE ZipArchive normalization to reject raw backslashes, '..' traversal, leading '/', drive prefixes (00003), encrypted flag_bits & 0x41 (00007), and non-STORED/DEFLATED compression (00007)."
  - "JPEG icons are checked for <= 1_048_576 bytes (00009) and non-JPEG image magic (00007) BEFORE Pillow opens the stream under an Image.MAX_IMAGE_PIXELS = 4_000_000 cap, verifying SOI/EOI markers (00004) and exact 276x162 dimensions (00001)."

requirements-completed: [PUB-01]

duration: 14min
completed: 2026-11-19
status: complete
---

# Phase 2 Plan 04: Package-Independent Offline SCS Workshop Validator & 1.62 Realism Invariants Summary

**Built the strictly package-independent Offline SCS Workshop Validator (`src/ets2v2/validate/`) enforcing SCS error codes `00001`–`00010`, warnings `WARN 00001`/`WARN 00002` as hard failures, raw ZIP central-directory hygiene, Pillow `276x162` JPEG inspection, and all ETS2 `1.62` realism invariants across both unpacked Workshop roots and standalone local ZIPs, wired into `ets2v2 validate {workshop,local}`.**

## Accomplishments
- **Task 1 (Tracer — `models.py`, `workshop.py`, `__init__.py`, `cli.py`, `test_validate_workshop.py`):**
  - Created frozen strict Pydantic v2 models (`ValidationSeverity`, `ValidationMode`, `ValidationIssue`, `ValidationReport`) and deduplicating `ValidationCollector` in `src/ets2v2/validate/models.py` where `ok == (len(issues) == 0)` so warnings (`WARN 00001`, `WARN 00002`) fail hard per D-09.
  - Added automated AST DAG isolation test verifying strictly zero imports from `ets2v2.package` anywhere under `src/ets2v2/validate/`.
  - Wired `ets2v2 validate workshop <dir> [--baseline-dir ...] [--json]` and `ets2v2 validate local <zip> [--baseline-dir ...] [--json]` into `src/ets2v2/cli.py`.
- **Task 2 (Full SCS Rule Matrix — `workshop.py`, `test_validate_workshop.py`):**
  - Enforced every SCS Workshop code across unpacked Workshop directories and local ZIPs with complete positive and negative fault-injection test coverage:
    - **`00001`**: empty `versions.sii`, wrong icon dimensions (`200x100`), subdirectory paths in `icon`/`description_file`, non-singleton `mod_package`.
    - **`00002`**: missing Workshop root/ZIP, `versions.sii`, declared `universal/` dir, `manifest.sii`, `mod_icon.jpg`, `description.txt`, or any of the 36 `def/country/<slug>.sui` / `speed_limits.sii` files.
    - **`00003`**: extraneous root entries (`README.md`), side-by-side `universal/` + `universal.zip`, zero or `>=2` universal entries in `versions.sii`, invalid `package_name`, ZIP-renamed-`.scs` in Workshop mode, forbidden extensions (`.json`, `.md`, `.py`, `.aux`, etc.), unreferenced `.txt`/`.jpg`, `def/country.sii` / `def/country.ets2v2.sii` (D-05), `mod_package` outside `manifest.sii`, and raw ZIP/SII `\` or `..` traversal (T-02-09).
    - **`00004`**: missing `SiiNunit` header, UTF-8 BOM, CR/CRLF, invalid UTF-8, unbalanced braces, non-column-0 `@include`, `3nK\x01` obfuscated payloads, and corrupt/truncated JPEG bytes.
    - **`00005`**: missing `package_name`, `package_version`, `author`, `icon`, `description_file`, `mp_mod_optional != true`, 0 categories or category outside the 18 official SCS categories (`VALID_SCS_CATEGORIES`).
    - **`00006`**: clean `PermissionError` handling without crashing.
    - **`00007`**: HashFS `SCS#` / `AEM!` magic, encrypted ZIP (`flag_bits & 0x41`), unsupported ZIP compression (`ZIP_BZIP2`), non-JPEG image formats (PNG/GIF/WebP/BMP/TIFF) renamed to `.jpg`, and unit name segments `>12` chars or outside `[a-z0-9_]`.
    - **`00008`**: unparseable `.sui` (`parse_country_data`), broken `speed_limits.sii` (`parse_speed_limits`), and corrupt ZIP archives.
    - **`00009`**: icon `> 1_048_576` bytes (checked before Pillow opens, T-02-10), `description.txt > 1_048_576` bytes, and `Image.DecompressionBombError` under `MAX_ICON_PIXELS = 4_000_000`.
    - **`00010` & `WARN 00002`**: `compatible_versions[]` in Workshop `manifest.sii` and unknown/unused `mod_package` attributes.
    - **`WARN 00001`**: `display_name` in Workshop `manifest.sii` (permitted in local ZIP mode) and `>2` `category[]` entries.
- **Task 3 (1.62 Realism Invariants — `invariants.py`, `workshop.py`, `__init__.py`, `test_validate_invariants.py`):**
  - Implemented `validate_core_realism_invariants()` emitting `ETS2V2-INV-COUNTRY-COUNT`, `ETS2V2-INV-IDENTITY`, `ETS2V2-INV-LEFTSIDE`, `ETS2V2-INV-REGIONS`, `ETS2V2-INV-SECONDARY-TZ`, `ETS2V2-INV-AXLE`, `ETS2V2-INV-ICELAND`, `ETS2V2-INV-SPEED-BLOCKS`, and `ETS2V2-INV-TZ-TOKEN`.
  - Hooked `validate_core_realism_invariants()` into both `validate_workshop_package()` and `validate_local_zip()` whenever `baseline_dir` is provided, and verified freshly built Summer and Winter Workshop trees and local ZIPs pass with 0 errors and 0 warnings.
  - Verified fault-injection regressions: Estonia `"@@tz_eest@@i"` (`3249064596`), non-UK `leftside_traffic: true`, Spain stripped `regions[]` (`3668352310`), Iceland 4-element 40t axles and `90 km/h` heavy truck, Germany dropped `train`/`tram`, Bulgaria dropped `slow_road`, `@@tz_cet@@` / `@@tz_wet@@` tokens outside the 12-key `locales.json` whitelist, Russia dropped `secondary_time_zone*`, Greece `44000 -> 40000` axle downgrade, and Finland truncated 10-element HCT axle ladder.

## Deviations from Plan
None - plan executed as written.

## Verification
- `uv run --offline ruff check`: exit 0 (`All checks passed!`)
- `uv run --offline ruff format --check`: exit 0 (`55 files already formatted`)
- `uv run --offline basedpyright`: exit 0 (`0 errors, 0 warnings, 0 notes`)
- `uv run --offline pytest tests/test_validate_workshop.py tests/test_validate_invariants.py tests/test_cli_scaffold.py -x`: exit 0 (`47 passed in 37.11s`)

## Self-Check: PASSED
- Verified all 6 created files (`src/ets2v2/validate/{__init__,models,workshop,invariants}.py`, `tests/test_validate_{workshop,invariants}.py`) and 1 modified file (`src/ets2v2/cli.py`) exist on disk, contain zero stubs/TODOs, and pass all offline lint, format, strict type-checking, DAG-isolation, and positive/negative validation test suites.
- Left git commits, `STATE.md`, and `ROADMAP.md` untouched for orchestrator handling as instructed.

---
*Phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a*
*Completed: 2026-11-19*
