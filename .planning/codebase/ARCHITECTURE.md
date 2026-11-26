<!-- refreshed: 2026-11-26 -->
# Architecture

**Analysis Date:** 2026-11-26

## System Overview

`ets2-country-realism` (`src/ets2_realism/`, CLI `ets2-realism`) is a clean-room Python `3.12+` toolkit, data pipeline, offline compiler, and map-combo merger for Euro Truck Simulator 2 (`1.62.3.3s`+). It generates byte-deterministic **Summer** and **Winter** country realism mods and **Option 4b Zero-DDS** multi-currency gas-station totems across Vanilla+DLC (36 countries), ProMods (`EU + ME + MA + TGS`), and arbitrary global map combos (225 canonical territories, 151 currencies) while preserving third-party map identity, geometry, regions, and rail speed classes.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          CLI & CI Workflows (`ets2-realism`)                           │
│   `src/ets2_realism/cli.py` (9 command groups)  │  `.github/workflows/{ci,phase-a,osm}`│
└────┬────────────┬────────────┬────────────┬─────┴──────┬────────────┬────────────┬─────┘
     │            │            │            │            │            │            │
     ▼            ▼            ▼            ▼            ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ `fetch/` │ │`publish/`│ │ `merge/` │ │`package/`│ │`validate/`│ │`baseline/`│ │ `audit/` │
│ (Online) │ │(Phase A) │ │(ProMods &│ │(Core &   │ │(Offline  │ │(1.62 Def │ │(Quarant. │
│ FX+T1/T2 │ │Diff-Gate │ │ compose- │ │ Zero-DDS │ │ SCS Mod  │ │ Extract) │ │ OSM/Taint│
│ Collect. │ │& Logs)   │ │ local)   │ │ Totems)  │ │ Validator│ │          │ │ Read-Only│
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │            │            │            │            │
     │            ▼            ▼            ▼            │            │            │
     │      ┌────────────────────────────────────┐       │            │            │
     │      │    `registry/` (225 Laws, DST TZ,  │       │            │            │
     │      │    `RealismSnapshot` v1 + SHA256)  │       │            │            │
     │      └─────────────────┬──────────────────┘       │            │            │
     │                        │                          │            │            │
     ▼                        ▼                          │            │            │
┌────────────────────────────────────────────────┐       │            │            │
│  `normalize/` (Offline 151 FX, 225 Fuel Bounds,│       │            │            │
│  `prices.lock.json`, 460-Board Totem Catalog)  │       │            │            │
└─────────────────────────┬──────────────────────┘       │            │            │
                          │                              │            │            │
                          ▼                              ▼            ▼            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Foundation Primitives (`vfs/` & `sii/`)                         │
│ `src/ets2_realism/vfs/` (HashFS v1/v2, ZIP, Dir, `VfsStack`, MIT `CityHash64`)         │
│ `src/ets2_realism/sii/` (O(n) Lexer, Hygiene, Span-Preserving `SiiDocument`, Adapters) │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                       Immutable Stores & Generated Artifacts                           │
│  Repo Data: `data/baselines/ets2_1.62_def/`, `data/laws/countries/*.json` (225),       │
│             `data/mappings/*.json`, `data/curated/tier3_fuel_baselines.json`, `assets/`│
│  State:     `state/prices.lock.json` (151 FX / 225 territories), `state/published.json`│
│  Outputs:   `dist/workshop/`, `dist/local/`, `dist/snapshots/`, `CHANGELOG_*.md`       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Package Root & CLI | Exposes `__version__`, PEP 561 `py.typed`, and `ets2-realism` CLI dispatching 9 command groups (`vfs`, `baseline`, `registry`, `package`, `validate`, `publish`, `fetch`, `compose-local`, `audit`) | `src/ets2_realism/__init__.py`, `src/ets2_realism/cli.py` |
| VFS Subsystem | Cross-platform read-only HashFS v1/v2, ZIP/ZIP-`.scs`, unpacked directory readers, pure-Python MIT `CityHash64`, `VfsStack` overlay priority, `base/` flattening, `dlc_<id>/` scoping, `3nK`/`AEM!` detection | `src/ets2_realism/vfs/` (`types.py`, `cityhash.py`, `hashfs.py`, `zip_archive.py`, `dir_archive.py`, `stack.py`) |
| SII/SUI Engine | Single-pass $O(n)$ string/comment-aware lexer, UTF-8 no-BOM LF hygiene & unit-segment validator, span-preserving surgical `SiiDocument`, and domain adapters (`country`, `speed_limits`, `sign_board`, `localization`) | `src/ets2_realism/sii/` (`lexer.py`, `hygiene.py`, `document.py`, `country.py`, `speed_limits.py`, `sign_board.py`, `localization.py`) |
| 1.62 Baseline Pipeline | Extracts deterministic clean-room ETS2 `1.62.3.3s` metadata (`countries`, `speed_limits`, `fuel_boards`, `locales`, `manifest`) from local game archives and byte-verifies SHA-256 digests | `src/ets2_realism/baseline/` (`models.py`, `extractor.py`) |
| Offline Normalization | Data-driven 225-territory / 151-currency registry, multi-provider FX cross-validation, `0.01–5.00 EUR/L` & `±25%` WoW circuit breakers, `prices.lock.json` I/O & staleness evaluation, 461-board totem catalog & glyph/width formatter | `src/ets2_realism/normalize/` (`models.py`, `currencies.py`, `fx.py`, `fuel.py`, `lockfile.py`, `totem_catalog.py`, `totem_format.py`) |
| Realism Registry & Snapshots | Validates 225 `data/laws/countries/<iso2>.json` records + mappings/aliases, resolves seasonal DST via stdlib `zoneinfo`/`tzdata`, exports & SHA-256-verifies locked `schema_version=1` `RealismSnapshot` JSONs | `src/ets2_realism/registry/` (`models.py`, `loader.py`, `timezone.py`, `snapshot.py`) |
| Online Data Collectors | Hardened HTTPS/XML/OOXML/HTML transport (`verify=True`, host allowlists, secret redaction, XXE & zip-bomb guards), FX fetchers (Frankfurter v2, ECB, fawazahmed0, CBR), EC WOB, EU Tier 1, Global Tier 1, and guarded Tier 2 national portals | `src/ets2_realism/fetch/` (`http.py`, `_parsing.py`, `_html.py`, `models.py`, `fx.py`, `ec_bulletin.py`, `national.py`, `global_tier1.py`, `tier2_portals.py`, `pipeline.py`) |
| Offline SCS Validator | Package-independent Workshop (`00001`–`00010`, `WARN 00001`/`00002`, `276×162` `.jpg`, Zero-DDS check) and ETS2 `1.62` realism / ProMods / Combo / Totem / license-taint invariant auditor | `src/ets2_realism/validate/` (`models.py`, `workshop.py`, `invariants.py`) |
| Core & Totem Packager | Clean-room `def/country/<slug>.sui` & `speed_limits.sii` synthesis, Option 4b Zero-DDS compiler (`460` sign boards + `43` `local_module.ets2r_fuel.sii`), `276×162` Pillow icons, `versions.sii`/`manifest.sii`, dual Workshop/local ZIP emitter | `src/ets2_realism/package/` (`synthesize.py`, `totems.py`, `icons.py`, `metadata.py`, `builder.py`) |
| Phase A Release Engine | Canonical SHA-256 diff-gate ignoring `package_version`, ISO-week versioning (`1.62-YYYY.WW`), `state/published.json` ledger, structured seasonal changelogs, hard pre-emission validation gate | `src/ets2_realism/publish/` (`ledger.py`, `changelog.py`, `release.py`) |
| ProMods & Combo Merger | Multi-source load-order parser (`game.log.txt`, plaintext `profile.sii`, `modlist.txt`, Workshop `227300`), D-10 self-exclusion, `--unpacked-defs`, include-aware `VfsStack` scanner, 3-tier alias resolver with SemEuropa collision shield, `FieldOwnershipPolicy` surgical merger, ProMods EU/ME/MA/TGS builder + `pm*_fuel` compiler, opt-in JRR/7RM hardcoded totem rewriter | `src/ets2_realism/merge/` (`load_order.py`, `scanner.py`, `aliases.py`, `policy.py`, `promods_discovery.py`, `promods_fuel.py`, `promods_builder.py`, `hardcoded_totems.py`, `compose.py`) |
| Quarantined Audit & Taint | Read-only `westnordost/osm-legal-default-speeds` drift comparator with statutory allowlist, opt-in Overpass/Taginfo spot-checks, and automated `CC BY 4.0` license-taint scanner across repo/snapshots/packages | `src/ets2_realism/audit/` (`models.py`, `osm_speeds.py`, `overpass.py`, `taint.py`) |

## Pattern Overview

**Overall:** Strictly acyclic 10-subpackage layered architecture with **two hard boundary walls**:
1. **Online/Offline Wall:** Only `src/ets2_realism/fetch/` and `src/ets2_realism/audit/` perform outbound HTTPS I/O. Every build, merge, snapshot, normalization, and validation subpackage (`vfs`, `sii`, `baseline`, `normalize`, `registry`, `validate`, `package`, `publish`, `merge`) is 100% offline.
2. **License Quarantine Wall:** `src/ets2_realism/audit/` (which reads `CC BY-SA` / `ODbL` OSM speed data for maintainer review) has **zero inbound imports** from any other subpackage; only `src/ets2_realism/cli.py` invokes it.

**Key Characteristics:**
- **Strict Acyclic Subpackage DAG (verified via AST scan):**
  - `vfs`, `sii` → zero internal subpackage dependencies (completely decoupled from each other)
  - `baseline` → `sii`, `vfs`
  - `normalize` → `baseline`
  - `registry` → `baseline`, `normalize`
  - `fetch` → `baseline`, `normalize`
  - `validate` → `baseline`, `sii`, `vfs` (intentionally independent of `package/`, `registry/`, `merge/`, `audit/`)
  - `package` → `baseline`, `normalize`, `registry`, `sii`, `vfs`
  - `publish` → `baseline`, `normalize`, `package`, `registry`, `sii`, `validate`, `vfs`
  - `merge` → `baseline`, `normalize`, `package`, `registry`, `sii`, `validate`, `vfs`
  - `audit` → `fetch` (HTTP helpers only), `registry`, `vfs`
  - `cli.py` → all 10 subpackages
- **Span-preserving surgical editing over lossy AST reprinting:** `SiiDocument` (`src/ets2_realism/sii/document.py`) records half-open character spans `[start, end)` during linear lexing (`src/ets2_realism/sii/lexer.py`) and splices only targeted scalar values or array blocks before re-indexing, preserving third-party comments, `regions[]`, `region_areas[]`, `secondary_time_zone*`, custom lane classes, and `train`/`tram` blocks verbatim.
- **Frozen strict Pydantic v2 contracts:** All domain models, reports, lockfiles, snapshots, and policy objects use `ConfigDict(strict=True, frozen=True, extra="forbid")`.
- **Canonical byte-deterministic outputs:** JSON artifacts serialize with `indent=2, sort_keys=True, ensure_ascii=False` + `\n` (UTF-8 no-BOM LF); ZIP/`.scs` archives use fixed timestamp `(1980, 1, 1, 0, 0, 0)`, UNIX mode `0o100644`, `DEFLATED` level 6, and sorted POSIX entry names (`src/ets2_realism/package/builder.py:91-107`).
- **Package-independent hard validation gates:** `publish`, `merge/promods_builder.py`, and `merge/compose.py` all run `validate_workshop_package()` / `validate_local_zip()` (where any error OR warning fails `ValidationReport.ok`) before advancing `state/published.json` or emitting final release artifacts.

## Layers

### Layer 1A: Virtual Filesystem (`src/ets2_realism/vfs/`)
- **Purpose:** Uniform read-only access to ETS2 `HashFS v1` (`SCS#\x01`), `HashFS v2` (`SCS#\x02`), ZIP/ZIP-`.scs`, and unpacked directories with ETS2 overlay semantics.
- **Location:** `src/ets2_realism/vfs/` (`types.py`, `cityhash.py`, `dir_archive.py`, `zip_archive.py`, `hashfs.py`, `stack.py`, `__init__.py`)
- **Contains:** `VfsArchive` protocol, pure-Python MIT `CityHash64` 1.0.3 (`cityhash.py`), magic-dispatch `open_archive()` (`hashfs.py`), `ProtectedArchiveStub` for `AEM!`/encrypted-ZIP/`3nK`, and priority-ordered `VfsStack` with `base/` flattening, `dlc_<id>/` scoping, and empty `SiiNunit {}` stub detection (`stack.py`).
- **Depends on:** Python stdlib + `pydantic`. Zero imports from `sii/` or any other internal package.
- **Used by:** `baseline/`, `validate/`, `package/`, `publish/`, `merge/`, `audit/`, `cli.py`.

### Layer 1B: Structural SII/SUI Engine (`src/ets2_realism/sii/`)
- **Purpose:** Lex, hygiene-check, parse, and surgically mutate SCS `.sii` and headerless `.sui` files.
- **Location:** `src/ets2_realism/sii/` (`lexer.py`, `hygiene.py`, `document.py`, `country.py`, `speed_limits.py`, `sign_board.py`, `localization.py`, `__init__.py`)
- **Contains:** Linear scanner (`scan_sii_structure`, IEEE-754 `&hex` `parse_sii_float`), hygiene validator (UTF-8 no-BOM LF, `@include` col-0, POSIX `/` paths, brace balance, `[a-z0-9_]{1,12}` unit segments), `SiiDocument` surgical editor, and typed parsers/patchers for `country_data`, `speed_limits.sii`, `sign_board_template`/`sign_template_text`, and `localization_db`.
- **Depends on:** Python stdlib + `pydantic`. Zero imports from `vfs/`.
- **Used by:** `baseline/`, `validate/`, `package/`, `publish/`, `merge/`.

### Layer 2: Clean-Room ETS2 1.62 Baseline (`src/ets2_realism/baseline/`)
- **Purpose:** Extract and SHA-256-verify deterministic clean-room JSON baselines (`data/baselines/ets2_1.62_def/`) from local ETS2 `1.62.3.3s` archives so CI and offline builds never require proprietary game files.
- **Location:** `src/ets2_realism/baseline/` (`models.py`, `extractor.py`, `__init__.py`)
- **Contains:** Frozen Pydantic schemas (`BaselineBundle`, `BaselineManifest`, `CountriesBaseline`, `SpeedLimitsBaseline`, `FuelBoardsBaseline`, `LocalesBaseline`) and `extract_baseline()` / `write_baseline_bundle()` / `verify_baseline_bundle()`.
- **Depends on:** `vfs/`, `sii/`.
- **Used by:** `normalize/`, `registry/`, `fetch/`, `validate/`, `package/`, `publish/`, `merge/`, `cli.py`.

### Layer 3: Pure Offline Normalization (`src/ets2_realism/normalize/`)
- **Purpose:** Enforce all financial, currency, fuel price, lockfile staleness, and fuel totem formatting invariants completely offline.
- **Location:** `src/ets2_realism/normalize/` (`models.py`, `currencies.py`, `fx.py`, `fuel.py`, `lockfile.py`, `totem_catalog.py`, `totem_format.py`, `__init__.py`)
- **Contains:** Data-driven 225-territory / 151-currency registry loader (`currencies.py`), multi-provider FX cross-validator (`fx.py`: `±5%` major / `±10%` volatile warn, `>20%` reject), fuel bounds (`0.01–5.00 EUR/L`), `±25%` WoW jump circuit breaker and secondary grade spread synthesis (`fuel.py`), `prices.lock.json` I/O and tiered staleness rules (`lockfile.py`: 14d Tier 1, 45d monthly, 120d quarterly, 180d Tier 3), 461-board classifier skipping `gas_empty` (`totem_catalog.py`), and glyph/font-width formatter supporting uniform dot `.` and `<sup>9</sup>` tenth-cent notation (`totem_format.py`).
- **Depends on:** `baseline/` (`models.py` only).
- **Used by:** `registry/`, `fetch/`, `package/`, `publish/`, `merge/`, `cli.py`.

### Layer 4: Realism Registry & Seasonal Snapshots (`src/ets2_realism/registry/`)
- **Purpose:** Validate the 225 canonical per-country legal records (`data/laws/countries/*.json`), resolve seasonal Summer (`Jul 15`) / Winter (`Jan 15`) DST offsets and ETS2 `@@tz_*@@` tokens, and produce/verify the locked `schema_version=1` `RealismSnapshot` interchange contract.
- **Location:** `src/ets2_realism/registry/` (`models.py`, `loader.py`, `timezone.py`, `snapshot.py`, `__init__.py`)
- **Contains:** `CountryLawRecord`, `CountryMappingRegistry`, `CountryAliasRegistry`, `resolve_ets2_timezone()` (`zoneinfo` + `tzdata` + `IANA_NUMERIC_ABBR_OVERRIDES` for numeric-offset zones), `build_realism_snapshot()`, `load_or_build_snapshot()`, `verify_snapshot_file()`, and GNU coreutils `SHA256SUMS.txt` helpers.
- **Depends on:** `baseline/`, `normalize/`.
- **Used by:** `package/`, `publish/`, `merge/`, `audit/`, `cli.py`.

### Layer 5: Online FX & 3-Tier Fuel Collectors (`src/ets2_realism/fetch/`)
- **Purpose:** Isolate all live network I/O behind hardened HTTPS/XML/OOXML/HTML clients to refresh `state/prices.lock.json` cleanly with automatic fallback on feed outages or circuit-breaker trips.
- **Location:** `src/ets2_realism/fetch/` (`http.py`, `_parsing.py`, `_html.py`, `models.py`, `fx.py`, `ec_bulletin.py`, `national.py`, `global_tier1.py`, `tier2_portals.py`, `pipeline.py`, `__init__.py`)
- **Contains:** Hardened `httpx.Client` (`verify=True`, `follow_redirects=False`, manual hop-by-hop host allowlist validation, bounded response reads, secret query redaction, XXE rejection, OOXML zip-bomb validation), 4 FX providers (`Frankfurter v2`, `ECB`, `fawazahmed0` jsDelivr/Cloudflare, `CBR`), EC Weekly Oil Bulletin + EU fallbacks (`ec_bulletin.py`), 7 EU Tier 1 national collectors (`UK DESNZ`, `NO SSB`, `FR Economie`, `DE Tankerkönig`, `ES MITECO`, `IT MIMIT`, `NL CBS`), 8 Global Tier 1 collectors (`US EIA v2`, `BR ANP`, `AR Energia`, `CO SICOM/CREG`, `CL CNE`, `MY OpenDOSM`, `JP METI`, `KR Opinet`), 10 guarded Tier 2 national portals (`IS`, `CH`, `MD`, `MK`, `RU`, `IL`, `AE`, `ZA`, `SA`, `NG`), and `run_price_fetch()` orchestrating precedence + Tier 3 curated fallback (`data/curated/tier3_fuel_baselines.json`).
- **Depends on:** `baseline/`, `normalize/`, `httpx`, `openpyxl`.
- **Used by:** `cli.py` (`ets2-realism fetch`) and `audit/` (`http.py` helpers only). Never imported by `package/`, `publish/`, `merge/`, or `validate/`.

### Layer 6: Offline SCS Workshop Validator (`src/ets2_realism/validate/`)
- **Purpose:** Independently audit unpacked Steam Workshop trees and local `.zip`/`.scs` archives against SCS Workshop Uploader rules and ETS2 `1.62` realism invariants across `core`, `promods`, and `combo` profiles.
- **Location:** `src/ets2_realism/validate/` (`models.py`, `workshop.py`, `invariants.py`, `__init__.py`)
- **Contains:** `validate_workshop_package()`, `validate_local_zip()`, SCS error/warning checks (`00001`–`00010`, `WARN 00001`/`00002`, `276×162` JPEG verification, forbidden extensions including Zero-DDS `.dds`/`.tobj` ban), and invariant suites (`validate_core_realism_invariants`, `validate_promods_realism_invariants`, `validate_combo_invariants`, `validate_totem_invariants`, `validate_promods_locale_modules_consistency`, `check_license_taint_bytes`).
- **Depends on:** `baseline/`, `sii/`, `vfs/`, `Pillow`. Intentionally zero imports from `package/`, `registry/`, `merge/`, `publish/`, `audit/`.
- **Used by:** `publish/`, `merge/`, `cli.py`.

### Layer 7A: Core Mod & Zero-DDS Totem Packager (`src/ets2_realism/package/`)
- **Purpose:** Synthesize clean-room ETS2 `1.62` Vanilla+DLC Core mods (`Summer` and `Winter`) in dual output targets: unpacked Steam Workshop root (`versions.sii` + `universal/`) and byte-deterministic local `.zip`.
- **Location:** `src/ets2_realism/package/` (`synthesize.py`, `totems.py`, `icons.py`, `metadata.py`, `builder.py`, `__init__.py`)
- **Contains:** Clean-room `def/country/<slug>.sui` & `speed_limits.sii` synthesizers (`synthesize.py`), Option 4b Zero-DDS compiler emitting 460 `def/sign/board/*.sii` files with `@@fp_*_ets2r@@` tokens + synchronized `locale/<lang>/local_module.ets2r_fuel.sii` across all 43 active `1.62` locales (`totems.py`), Pillow `276×162` icon renderer (`icons.py`), manifest/description/versions renderers (`metadata.py`), and `build_core_edition()` / `write_deterministic_zip()` / `write_workshop_tree()` (`builder.py`).
- **Depends on:** `baseline/`, `normalize/`, `registry/`, `sii/`, `vfs/`, `Pillow`.
- **Used by:** `publish/`, `merge/`, `cli.py`, `scripts/generate_icons.py`.

### Layer 7B: Phase A Release Orchestrator (`src/ets2_realism/publish/`)
- **Purpose:** Orchestrate weekly Friday `06:00 UTC` Phase A semi-auto releases with canonical SHA-256 diff-gating, independent Summer/Winter ISO-week versioning, snapshot verification, and structured Markdown changelogs.
- **Location:** `src/ets2_realism/publish/` (`ledger.py`, `changelog.py`, `release.py`, `__init__.py`)
- **Contains:** `compute_workshop_canonical_sha256()` (replaces `package_version` with `__CANONICAL__` via `SiiDocument` before length-prefixed SHA-256 hashing), `resolve_next_package_version()`, `PublishedLedger` (`state/published.json`), `render_edition_changelog()`, and `run_phase_a_release()`.
- **Depends on:** `baseline/`, `normalize/`, `package/`, `registry/`, `sii/`, `validate/`, `vfs/`.
- **Used by:** `cli.py` (`ets2-realism publish release`) and `.github/workflows/phase-a-release.yml`.

### Layer 8: ProMods Companion & Local Map-Combo Composer (`src/ets2_realism/merge/`)
- **Purpose:** Offline local builders that preserve ProMods IP boundaries (`assert_out_dir_not_tracked()`) and compose realism patches cleanly atop ProMods (`EU + ME + MA + TGS`) or arbitrary user ETS2 map combos.
- **Location:** `src/ets2_realism/merge/` (`load_order.py`, `scanner.py`, `aliases.py`, `policy.py`, `promods_discovery.py`, `promods_fuel.py`, `promods_builder.py`, `hardcoded_totems.py`, `compose.py`, `__init__.py`)
- **Contains:**
  - `load_order.py`: Parses `game.log.txt`, plaintext `profile.sii` (refuses `ScsC`-encrypted profiles), or `modlist.txt`, resolves Steam Workshop `227300`, mounts `BaselineVirtualArchive` when `--game-dir` is omitted, enforces D-10 self-exclusion via `MANAGED_MANIFEST_MARKER`, handles `--unpacked-defs` substitutions, and emits structured `ProtectedArchiveDiagnostic` records for `AEM!`/encrypted-ZIP/`3nK` archives.
  - `scanner.py`: Walks `def/country*.sii` `@include` graphs across `VfsStack`, tracks empty `SiiNunit {}` stub suppressions, extracts winning country fragments + `speed_limits.sii`, and detects active `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii`.
  - `aliases.py`: O(1) 3-tier `CountryResolver` (Tier 1 bundled+user `country_aliases.json` with SemEuropa collision shield → Tier 2 `iso_country_code`/`country_code` → Tier 3 canonical `ets2_slug`).
  - `policy.py`: Schema-enforced `FieldOwnershipPolicy` surgical merger (`fuel_price`, `lights_mandatory`, `driving_tired_offence`, `speed_limits_road`, `patch_if_single_tz` DST shifting, `max_of_map_and_real` monotonic axle mass limits; preserves all map-owned identity/geometry/region/rail fields and skips `speed_limits.sii` on `imperial_units` parity mismatch).
  - `promods_discovery.py`, `promods_fuel.py`, `promods_builder.py`: Discovers local ProMods packs, compiles dynamic 43-locale `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` (guarding `mn` = Montenegro in `pm_fuel` vs Mongolia in `pm_tgs_fuel`), and emits validated standalone ProMods Editions (`dist/workshop/promods-{summer,winter}/` + `dist/local/ETS2_Country_Realism_ProMods_*.zip`).
  - `hardcoded_totems.py` & `compose.py`: Opt-in `--patch-hardcoded-totems` surgical rewriter for verified JRR/7RM single-text numeric boards, and `compose_local()` emitting offline-validated `zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs` + JSON `ComposeReport`.
- **Depends on:** `baseline/`, `normalize/`, `package/`, `registry/`, `sii/`, `validate/`, `vfs/`.
- **Used by:** `cli.py` (`ets2-realism package promods`, `ets2-realism compose-local`).

### Layer 9 (Quarantined Layer 7C): Internal OSM Drift Audit & License-Taint Gate (`src/ets2_realism/audit/`)
- **Purpose:** Strictly read-only, CI-only advisory audit comparing clean-room `data/laws/countries/*.json` against `westnordost/osm-legal-default-speeds` (plus opt-in Overpass/Taginfo spot-checks) and enforcing zero `CC BY-SA` / `ODbL` / `CC BY-NC-ND` / forbidden-source contamination across repo files, snapshots, and built packages.
- **Location:** `src/ets2_realism/audit/` (`models.py`, `osm_speeds.py`, `overpass.py`, `taint.py`, `__init__.py`)
- **Contains:** `run_osm_speed_audit()`, `load_speed_audit_allowlist()` (`data/laws/speed_audit_allowlist.json`), `render_osm_speed_drift_markdown()`, `truncate_markdown_for_github_issue()`, `fetch_overpass_speed_spot_checks()`, `fetch_taginfo_maxspeed_distributions()`, and `scan_repo_and_artifacts_for_taint()` / `scan_package_for_taint()`.
- **Depends on:** `fetch/http.py` (hardened HTTPS transport), `registry/loader.py`, `vfs/`. **Never imported by any build, publish, merge, or validation package.**
- **Used by:** `cli.py` (`ets2-realism audit osm-speeds`, `ets2-realism audit taint`) and `.github/workflows/osm-speed-audit.yml`.

## Data Flow

### Flow 1: Weekly Phase A Core Build & Semi-Auto Release (`phase-a-release.yml`)
1. **Quality Gate:** `.github/workflows/phase-a-release.yml:41-47` runs `ruff check`, `ruff format --check`, `basedpyright`, and `pytest` offline.
2. **Online FX & Fuel Fetch:** `ets2-realism fetch` (`src/ets2_realism/cli.py:653`, `src/ets2_realism/fetch/pipeline.py:235`) fetches multi-provider FX (`Frankfurter v2`, `ECB`, `fawazahmed0`, `CBR`), cross-validates rates (`src/ets2_realism/normalize/fx.py`), fetches EU Tier 1 + Global Tier 1 + Tier 2 portals in strict `_FEED_PRECEDENCE` order, validates `0.01–5.00 EUR/L` & `±25%` WoW bounds (`src/ets2_realism/normalize/fuel.py`), falls back to previous lockfile or `data/curated/tier3_fuel_baselines.json`, evaluates staleness, and atomically updates `state/prices.lock.json`.
3. **Snapshot & Dual Packaging:** `ets2-realism publish release` (`src/ets2_realism/cli.py:568`, `src/ets2_realism/publish/release.py:124`) loads `data/laws/countries/*.json` (225 countries), `data/baselines/ets2_1.62_def/`, and `state/prices.lock.json`, builds Summer & Winter `RealismSnapshot` v1 objects, and compiles both Workshop unpacked roots (`dist/workshop/{summer,winter}/`) and deterministic local ZIPs (`dist/local/ETS2_Country_Realism_Core_*.zip`) including 460 Zero-DDS sign boards + 43 `local_module.ets2r_fuel.sii` files (`src/ets2_realism/package/builder.py:140`, `src/ets2_realism/package/totems.py:272`).
4. **Canonical Diff-Gate & Validation:** `compute_workshop_canonical_sha256()` (`src/ets2_realism/publish/ledger.py:65`) hashes each edition ignoring `package_version`; changed editions re-stamp their ISO-week version (`1.62-YYYY.WW`). Both Workshop and local ZIP artifacts pass `validate_workshop_package()` and `validate_local_zip()` (`src/ets2_realism/validate/workshop.py`) as a hard gate before emitting `dist/snapshots/realism-snapshot-{summer,winter}.json`, `SHA256SUMS.txt`, `CHANGELOG_{SUMMER,WINTER}.md`, `dist/release_summary.json`, and updated `state/published.json`.
5. **CI Distribution:** Workflow uploads `phase-a-release-bundle` artifact, updates the rolling `snapshots-latest` GitHub Release, and opens/updates the persistent `release/phase-a-weekly` PR (maintainer uploads via `SCS Workshop Uploader` before merging).

### Flow 2: Offline Local Map-Combo Composition (`ets2-realism compose-local`)
1. **Load-Order & Snapshot Loading:** `compose_local()` (`src/ets2_realism/merge/compose.py:203`) verifies `out_dir` is not inside a tracked repo directory (`assert_out_dir_not_tracked()`), parses exactly one of `--game-log`, `--profile`, or `--modlist` (`src/ets2_realism/merge/load_order.py`), and loads/verifies an offline `RealismSnapshot` (`--snapshot` + `SHA256SUMS.txt`) or builds one locally from `data/laws/` + `state/prices.lock.json`.
2. **VFS Stack Assembly:** `build_combo_vfs_stack()` (`src/ets2_realism/merge/load_order.py`) mounts Vanilla `def.scs` (or `BaselineVirtualArchive` offline), excludes prior managed packages (D-10 `MANAGED_MANIFEST_MARKER`), substitutes `--unpacked-defs` for protected archives, and records `ProtectedArchiveDiagnostic` entries (failing fast if `--strict-protected`).
3. **Include-Aware Country Scan & 3-Tier Resolution:** `scan_active_countries()` (`src/ets2_realism/merge/scanner.py`) resolves `def/country*.sii` `@include` trees (respecting empty `SiiNunit {}` stub suppressions) and detects active `pm*_fuel` modules. `CountryResolver.resolve()` (`src/ets2_realism/merge/aliases.py:84`) matches each country via Tier 1 aliases (with SemEuropa shield) → Tier 2 ISO-3/ISO-2 → Tier 3 slug.
4. **Surgical Policy Merge & Totems:** `apply_country_policy()` and `apply_speed_limits_policy()` (`src/ets2_realism/merge/policy.py`) surgically patch realism-owned fields via `SiiDocument` while preserving map-owned fields. Unless `--no-totems`, compiles 460 vanilla boards + 43 `local_module.ets2r_fuel.sii`, dynamic `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` for detected ProMods packs (`src/ets2_realism/merge/promods_fuel.py`), and optional JRR/7RM hardcoded boards (`--patch-hardcoded-totems`, `src/ets2_realism/merge/hardcoded_totems.py`).
5. **Deterministic Emit & Offline Self-Validation:** Writes `zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs` via `write_deterministic_zip()`, validates it with `validate_local_zip(..., profile="combo")`, and emits `ComposeReport` (text / `--json` / `--report-json`).

### Flow 3: Offline ProMods Companion Build (`ets2-realism package promods`)
1. `build_promods_edition()` (`src/ets2_realism/merge/promods_builder.py:128`) asserts `out_dir` is gitignored/external, discovers local ProMods `EU`, `ME`, `MA`, and `TGS` def/defmap + assets archives (`src/ets2_realism/merge/promods_discovery.py`), mounts them over Vanilla/`BaselineVirtualArchive` in a `VfsStack`, scans & resolves all active countries, applies `FieldOwnershipPolicy`, compiles Vanilla Zero-DDS totems plus `pm_fuel` / `pm_me_fuel` / `pm_tgs_fuel` across 43 locales, writes dual Workshop + local ZIP targets, and hard-validates both with `profile="promods"`.

### Flow 4: Quarantined Monthly OSM Speed-Limit Audit (`osm-speed-audit.yml`)
1. `ets2-realism audit osm-speeds` (`src/ets2_realism/cli.py:831`, `src/ets2_realism/audit/osm_speeds.py`) fetches `westnordost/osm-legal-default-speeds` `legal_default_speeds.json` (plus optional `--overpass` / `--taginfo`), compares against `data/laws/countries/*.json`, filters statutory differences via `data/laws/speed_audit_allowlist.json`, writes sanitized Markdown/JSON reports to `dist/audit/` (zero Git commits), and upserts/closes a rolling `osm-audit` GitHub Issue.

**State Management:**
- **Immutable Checked-In Registries:** `data/baselines/ets2_1.62_def/`, `data/laws/countries/*.json` (225 files), `data/laws/speed_audit_allowlist.json`, `data/mappings/*.json`, `data/curated/tier3_fuel_baselines.json`, `assets/icons/*.jpg`.
- **Versioned Operational State:** `state/prices.lock.json` (151 FX rates + 225 country fuel entries + alerts) and `state/published.json` (v1 per-edition canonical payload/snapshot SHA-256 ledger).
- **Atomic File Writes:** State lockfiles, audit outputs, and compose reports write to temporary sibling files and swap via `os.replace()` (`src/ets2_realism/cli.py:810`, `src/ets2_realism/merge/compose.py:138`).

## Key Abstractions

**`VfsArchive` & `VfsStack`:**
- Purpose: Uniform read-only container protocol (`list_paths`, `exists`, `read_bytes`, `stat`, `diagnostics`) and priority-ordered overlay stack abstracting HashFS v1/v2, ZIP, directories, and `BaselineVirtualArchive`.
- Examples: `src/ets2_realism/vfs/types.py`, `src/ets2_realism/vfs/stack.py`, `src/ets2_realism/merge/load_order.py`.
- Pattern: Protocol + Composite Overlay + Null-Object Stub (`ProtectedArchiveStub`).

**`SiiDocument`:**
- Purpose: Span-indexed surgical editor for SCS `.sii`/`.sui` text files with immediate span re-indexing after edits.
- Examples: `src/ets2_realism/sii/document.py`, `src/ets2_realism/sii/country.py`, `src/ets2_realism/sii/speed_limits.py`.
- Pattern: Span-Table Buffer / Surgical Text Patcher.

**`RealismSnapshot` (`schema_version=1`):**
- Purpose: Locked, air-gapped, canonical seasonal interchange contract decoupling public CI builds from local ProMods Companion and `compose-local` consumers.
- Examples: `src/ets2_realism/registry/snapshot.py`, `src/ets2_realism/publish/release.py`, `src/ets2_realism/merge/compose.py`.
- Pattern: Versioned Immutable DTO with `SHA256SUMS.txt` Integrity Manifest.

**`FieldOwnershipPolicy`:**
- Purpose: Declarative ownership contract guaranteeing realism overlays never overwrite map-owned identity, geometry, regions, left-hand drive, imperial flags, or rail speed limits.
- Examples: `src/ets2_realism/merge/policy.py`.
- Pattern: Policy Object + Pure Surgical Transformer.

**`ValidationCollector` & `ValidationReport`:**
- Purpose: Package-independent deduplicated diagnostic accumulator where any error or warning causes hard failure (`ok == False`).
- Examples: `src/ets2_realism/validate/models.py`, `src/ets2_realism/validate/workshop.py`, `src/ets2_realism/validate/invariants.py`.
- Pattern: Collector / Specification Pipeline across `core`, `promods`, and `combo` profiles.

## Entry Points

**Primary CLI (`ets2-realism`):**
- Location: `src/ets2_realism/cli.py` (`main()` at line 1903, `build_parser()` at line 940), registered in `pyproject.toml:26` as `ets2-realism = "ets2_realism.cli:main"`.
- Triggers: Local developer/user CLI invocations and GitHub Actions workflows.
- Responsibilities: Subcommand dispatch across 9 command groups:
  - `ets2-realism vfs inspect`
  - `ets2-realism baseline extract`
  - `ets2-realism registry {validate,snapshot,snapshot-verify}`
  - `ets2-realism package {icons,promods-icons,build,promods}`
  - `ets2-realism validate {workshop,local}`
  - `ets2-realism publish release`
  - `ets2-realism fetch`
  - `ets2-realism compose-local`
  - `ets2-realism audit {osm-speeds,taint}`

**Icon Regeneration Helper Script:**
- Location: `scripts/generate_icons.py`
- Triggers: Manual maintainer invocation (`uv run python scripts/generate_icons.py`) when regenerating checked-in `assets/icons/*.jpg`.
- Responsibilities: Thin wrapper calling `generate_all_icons()` and `generate_promods_icons()`.

**GitHub Actions Workflows:**
- Location: `.github/workflows/ci.yml`, `.github/workflows/phase-a-release.yml`, `.github/workflows/osm-speed-audit.yml`
- Triggers: Push/PR (`ci.yml`), Friday `06:00 UTC` cron / manual dispatch (`phase-a-release.yml`), monthly first-Monday `07:00 UTC` cron / manual dispatch (`osm-speed-audit.yml`).
- Responsibilities: Quality gates (`ruff`, `basedpyright`, `pytest`), weekly live fetch + diff-gated Core release + rolling `snapshots-latest` GitHub Release + persistent Release PR, and monthly read-only OSM speed-drift advisory issue.

## Architectural Constraints

- **Threading / Concurrency:** 100% single-threaded synchronous Python across all 73 modules (zero `threading`, `asyncio`, or `multiprocessing`). All HTTP requests, archive scans, and builds execute sequentially for deterministic ordering and predictable rate-limit compliance.
- **Global State & Module-Level Caches:** Minimal and strictly immutable. `src/ets2_realism/normalize/currencies.py:150-167` uses `@functools.lru_cache(maxsize=8)` on `load_currency_registry()` and `load_tier3_fuel_baselines()`, and eagerly binds frozen `_DEFAULT_CURRENCY_REG` and `_DEFAULT_TIER3_REG` at import time (requiring `data/mappings/currencies.json` and `data/curated/tier3_fuel_baselines.json` relative to the repo/package root). No other mutable singletons exist.
- **Circular Imports:** Zero circular dependencies across all 10 subpackages (enforced acyclic DAG). To preserve this:
  - `src/ets2_realism/vfs/stack.py` keeps its own minimal `_strip_sii_comments()` rather than importing `src/ets2_realism/sii/lexer.py`.
  - `src/ets2_realism/validate/invariants.py` duplicates `FORBIDDEN_LICENSE_TAINT_PATTERNS` rather than importing quarantined `src/ets2_realism/audit/taint.py`.
- **ProMods IP & Repository Containment Guard:** `assert_out_dir_not_tracked()` (`src/ets2_realism/merge/promods_builder.py:96-110`) refuses writing ProMods or Combo outputs into the repo root or any tracked directory outside `{dist, out, build, raw, vendor}`.
- **SCS Engine Format Constraints:**
  - All emitted `.sii`/`.sui` files must be UTF-8 without BOM, LF-only, POSIX `/` paths, col-0 `@include`, and unit name segments strictly matching `[a-z0-9_]{1,12}` (hence `.ets2r_fuel`, 10 chars, and `@@fp_<iso2>_<grade>_ets2r@@`).
  - Zero-DDS invariant: No `.dds` or `.tobj` files are ever emitted (`FORBIDDEN_TOTEM_EXTENSIONS` in `src/ets2_realism/validate/workshop.py:87`).
  - Deprecated locale `fr_qc` is strictly forbidden; all 43 active ETS2 `1.62` locales (including `fr_ca`) must receive synchronized fuel locale modules.

## Anti-Patterns

### Importing `fetch/` or `audit/` from Offline Build/Validate Packages
**What happens:** Adding an import of `ets2_realism.fetch` or `ets2_realism.audit` inside `package/`, `publish/`, `merge/`, `registry/`, `normalize/`, or `validate/`.
**Why it's wrong:** Breaks the air-gapped offline guarantee for local ProMods/`compose-local` builds and violates the `CC BY 4.0` / `CC BY-SA` license quarantine boundary.
**Do this instead:** Pass normalized offline data via `state/prices.lock.json` (`PricesLockfile`) or verified `RealismSnapshot` JSONs (`src/ets2_realism/registry/snapshot.py`). Keep `audit/` reachable only from `src/ets2_realism/cli.py`.

### Re-serializing Third-Party `.sii`/`.sui` Files from Scratch in Map Combos
**What happens:** Using `synthesize_country_sui()` or dict-to-text reprinting on third-party map-mod country files inside `merge/`.
**Why it's wrong:** Strips map-mod `regions[]`, `region_areas[]`, `secondary_time_zone*`, custom lane classes, `train`/`tram` blocks, and mod-specific comments, causing broken map borders or crashes in ETS2.
**Do this instead:** Use `synthesize_country_sui()` only for Vanilla Core clean-room synthesis (`src/ets2_realism/package/synthesize.py`); for ProMods and map combos, always mutate the winning third-party bytes surgically through `apply_country_policy()` and `apply_speed_limits_policy()` (`src/ets2_realism/merge/policy.py`).

### Falling Through Tier 1 Aliases on Unmatched Snapshot Targets
**What happens:** Allowing a slug listed in `data/mappings/country_aliases.json` (e.g., SemEuropa Brazilian states `al`, `ba`, `es`, `ma`, `mt`, `ro`, `rs`, `se`) to fall through to Tier 2 `country_code` lookup when the target ISO-2 is missing from a snapshot.
**Why it's wrong:** Collides Brazilian state codes with European ISO-2 codes (Albania, Bosnia, Spain, Morocco, Malta, Romania, Serbia, Sweden), silently overwriting South American countries with European speed limits and fuel prices.
**Do this instead:** Always resolve via `CountryResolver.resolve()` (`src/ets2_realism/merge/aliases.py:84-110`), which terminates as `unmatched` (`alias_target_not_in_snapshot`) whenever a Tier 1 alias hits but its target is absent.

### Mutating `state/published.json` or Emitting Packages Before Offline Validation
**What happens:** Writing release ledgers, changelogs, or shipping artifacts before running `validate_workshop_package()` / `validate_local_zip()`.
**Why it's wrong:** Could publish broken Workshop metadata, bad SII hygiene, or license-tainted payloads and poison `state/published.json` hashes.
**Do this instead:** Follow `run_phase_a_release()` (`src/ets2_realism/publish/release.py:231-257`) and `compose_local()` (`src/ets2_realism/merge/compose.py`) by running the package-independent offline validator as a hard gate prior to ledger/release finalization.

## Error Handling

**Strategy:** Typed domain exceptions at library boundaries, converted to concise `stderr` diagnostics (with URL secret redaction via `redact_url_secrets()`) and POSIX exit codes (`0` / `1`) in `src/ets2_realism/cli.py`; non-fatal operational findings flow as structured frozen Pydantic report models (`ValidationReport`, `FetchRunReport`, `ComposeReport`, `OsmSpeedAuditReport`, `TaintScanReport`, `ArchiveDiagnostic`).

**Patterns:**
- **Typed domain exceptions:** `ProtectedPayloadError`, `UnsupportedCompressionError` (`src/ets2_realism/vfs/types.py`), `SiiEncodingError` (`src/ets2_realism/sii/hygiene.py`), `HttpFetchError` (`src/ets2_realism/fetch/http.py`), `Tier2EncodingError` (`src/ets2_realism/fetch/_html.py`), `Tier2RateLimitedError`, `Tier2SelectorDriftError` (`src/ets2_realism/fetch/tier2_portals.py`), `EncryptedProfileError` (`src/ets2_realism/merge/load_order.py`).
- **Fail-soft vs fail-hard separation:** Online feed outages in `fetch/pipeline.py` fail soft per feed (emitting `LockAlert` and preserving prior lockfile / Tier 3 baselines); offline SCS validation (`validate/`), SII hygiene (`_assert_hygiene`), and license-taint checks (`audit/taint.py`, `validate/invariants.py`) fail hard with zero-warning tolerance.

## Cross-Cutting Concerns

**Logging:** No Python `logging` framework is used. Every CLI subcommand supports human-readable `stdout`/`stderr` summaries and deterministic `--json` output backed by frozen Pydantic v2 models (`sort_keys=True, ensure_ascii=False`).

**Validation:** Multi-layered defense in depth:
1. Input schema validation via strict Pydantic v2 (`extra="forbid"`, finite float checks, ISO-2/ISO-3/ISO-4217/date regexes).
2. Security validation at I/O boundaries: HTTPS + exact host allowlist + bounded streaming reads + XXE/OOXML zip-bomb checks (`src/ets2_realism/fetch/http.py`, `_parsing.py`), symlink/junction & path-traversal containment (`ensure_contained()`, `validate_rel_path()` in `src/ets2_realism/package/builder.py` and `src/ets2_realism/vfs/dir_archive.py`).
3. Output SII hygiene (`validate_sii_hygiene()`) on every synthesized or surgically patched file.
4. Package-independent Offline SCS Workshop Validator (`src/ets2_realism/validate/`) and automated license-taint gate (`src/ets2_realism/audit/taint.py`).

**Authentication:** Zero Steam credentials or secrets exist in CI (Phase A uses manual maintainer handoff to `SCS Workshop Uploader`). Optional third-party API keys (`TANKERKOENIG_API_KEY`, `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`) are passed strictly via environment variables / GitHub Actions secrets in `.github/workflows/phase-a-release.yml:51-54` and scrubbed from all error strings by `redact_url_secrets()` (`src/ets2_realism/fetch/http.py:47`).

---

*Architecture analysis: 2026-11-26*
