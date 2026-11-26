# Codebase Structure

**Analysis Date:** 2026-11-26

## Directory Layout

```text
d:\CODE\Ets2 Mod V2\
├── .agents/                          # Project-local agent skills (vendored SCS Modding Wiki)
│   └── skills/
│       └── scs-modding-wiki/         # SKILL.md, index.json, sources.json, 162 mirrored wiki docs
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Push/PR quality gates: ruff check/format, basedpyright strict, pytest
│       ├── osm-speed-audit.yml       # Monthly quarantined OSM speed-limit drift audit -> rolling Issue
│       └── phase-a-release.yml       # Friday 06:00 UTC fetch, diff-gated Core build, snapshots-latest & Release PR
├── .planning/                        # GSD planning artifacts, research, phase logs & codebase maps
│   ├── codebase/                     # ARCHITECTURE.md, STRUCTURE.md, STACK.md, INTEGRATIONS.md, etc.
│   ├── intel/                        # Cached codebase intel JSONs
│   └── phases/                       # Completed V1 Phase 1–5 plans, summaries, reviews & verifications
├── assets/
│   └── icons/                        # Checked-in clean-room 276x162 JPEG mod icons (4 files)
│       ├── promods_summer.jpg
│       ├── promods_winter.jpg
│       ├── summer.jpg
│       └── winter.jpg
├── data/                             # Checked-in clean-room immutable registries & baselines
│   ├── baselines/
│   │   └── ets2_1.62_def/            # Deterministic ETS2 1.62.3.3s baseline JSONs (5 files)
│   │       ├── countries.json        # 36 Vanilla+DLC country_data schemas
│   │       ├── fuel_boards.json      # 461 single-text fuel boards (373 active_fp, 88 placeholder/blank)
│   │       ├── locales.json          # 43 active locales, 12 @@tz_*@@ keys, 99 @@fp_*@@ keys
│   │       ├── manifest.json         # Counts, 107-DLC country audit, payload SHA-256 digests
│   │       └── speed_limits.json     # 36 country speed_limits.sii schemas (incl. train/tram)
│   ├── curated/
│   │   └── tier3_fuel_baselines.json # 186 curated CC BY 4.0 Tier 3 global retail fuel baselines
│   ├── laws/
│   │   ├── countries/                # 225 canonical per-country law JSONs (<iso2>.json, ad.json..zw.json)
│   │   └── speed_audit_allowlist.json# 11 clean-room documented statutory speed-limit deviations
│   └── mappings/
│       ├── country_aliases.json      # 119 third-party slug aliases (incl. SemEuropa shields & TZ overrides)
│       ├── currencies.json           # 151 ISO-4217 currencies, sanity bands & 225 territory mappings
│       └── ets2_countries.json       # 225 country-to-ETS2 slug/ISO mappings (36 vanilla_1_62 + 189 global)
├── scripts/
│   └── generate_icons.py             # Thin reproducible wrapper to regenerate assets/icons/*.jpg
├── src/
│   └── ets2_realism/                 # Installable Python 3.12+ package (`ets2-country-realism`, 73 files)
│       ├── __init__.py               # Package docstring & __version__ = "0.1.0"
│       ├── cli.py                    # Root CLI entrypoint (`ets2-realism`, 9 command groups)
│       ├── py.typed                  # PEP 561 typed-package marker
│       ├── audit/                    # Quarantined Layer 7C OSM speed drift & CC BY 4.0 taint scanner (5 files)
│       ├── baseline/                 # Clean-room ETS2 1.62 metadata schemas & extractor (3 files)
│       ├── fetch/                    # Online-only hardened HTTP/XML/HTML FX & Tier 1/2 collectors (11 files)
│       ├── merge/                    # Offline ProMods Companion Builder & compose-local engine (10 files)
│       ├── normalize/                # Pure offline FX/fuel bounds, lockfile & 460-board totem logic (8 files)
│       ├── package/                  # Clean-room Core SII synthesizer, Zero-DDS totems, icons & builder (6 files)
│       ├── publish/                  # Phase A canonical SHA-256 diff-gate, ledger & changelogs (4 files)
│       ├── registry/                 # 225-country law validator, DST zoneinfo & v1 RealismSnapshot (5 files)
│       ├── sii/                      # Structural SII/SUI lexer, hygiene, surgical SiiDocument & adapters (8 files)
│       └── vfs/                      # HashFS v1/v2, ZIP, Dir, VfsStack overlay & MIT CityHash64 (7 files)
├── state/                            # Versioned operational state updated by Phase A Release PRs
│   ├── prices.lock.json              # Canonical 151-FX / 225-territory fuel & FX lockfile
│   └── published.json                # v1 per-edition canonical payload/snapshot SHA-256 release ledger
├── tests/                            # Pytest suite (45 test modules, 634 CI-safe + 4 local-archive tests)
├── .gitattributes                    # Enforces LF line endings and binary markers (.scs, .dds, .jpg, .png)
├── .gitignore                        # Excludes .venv/, build/, dist/, out/, raw/, vendor/, caches, *.tmp
├── pyproject.toml                    # Hatchling build, dependencies, ets2-realism script, Ruff, Basedpyright, Pytest
└── uv.lock                           # Locked reproducible uv dependency graph
```

## Directory Purposes

**`src/ets2_realism/`:**
- Purpose: Root installable Python package (`ets2-country-realism`) containing the `ets2-realism` CLI and 10 strictly acyclic domain subpackages.
- Contains: Typed Python 3.12+ modules (`basedpyright` strict, `py.typed`), frozen Pydantic v2 models, and pure-Python VFS/SII/packaging/merge engines.
- Key files: `src/ets2_realism/__init__.py`, `src/ets2_realism/cli.py`, `src/ets2_realism/py.typed`.

**`src/ets2_realism/vfs/`:**
- Purpose: Cross-platform read-only SCS virtual filesystem layer.
- Contains: Protocol & diagnostic types (`types.py`), MIT pure-Python `CityHash64` 1.0.3 (`cityhash.py`), HashFS v1/v2 & magic dispatcher (`hashfs.py`), ZIP/ZIP-`.scs` reader (`zip_archive.py`), root-contained directory reader (`dir_archive.py`), and priority overlay engine (`stack.py`).
- Key files: `src/ets2_realism/vfs/stack.py`, `src/ets2_realism/vfs/hashfs.py`, `src/ets2_realism/vfs/types.py`.

**`src/ets2_realism/sii/`:**
- Purpose: Structural SII/SUI lexer, SCS hygiene checker, span-preserving surgical editor, and ETS2 domain adapters.
- Contains: Linear scanner (`lexer.py`), UTF-8/LF/path/unit-segment validator (`hygiene.py`), surgical `SiiDocument` (`document.py`), read+patch adapters (`country.py`, `speed_limits.py`), and read-only parsers (`sign_board.py`, `localization.py`).
- Key files: `src/ets2_realism/sii/document.py`, `src/ets2_realism/sii/lexer.py`, `src/ets2_realism/sii/country.py`, `src/ets2_realism/sii/speed_limits.py`.

**`src/ets2_realism/baseline/`:**
- Purpose: Clean-room ETS2 `1.62.3.3s` metadata extraction, canonical JSON writing, and SHA-256 verification.
- Contains: Frozen Pydantic baseline models (`models.py`) and extraction pipeline (`extractor.py`).
- Key files: `src/ets2_realism/baseline/extractor.py`, `src/ets2_realism/baseline/models.py`.

**`src/ets2_realism/normalize/`:**
- Purpose: Pure offline currency, FX, fuel price, lockfile, and Option 4b Zero-DDS totem formatting logic.
- Contains: Lockfile/alert schemas (`models.py`), 225-territory / 151-currency registry loader (`currencies.py`), multi-provider FX cross-validator (`fx.py`), bounds/WoW circuit-breaker & secondary-grade spreads (`fuel.py`), `prices.lock.json` I/O & staleness (`lockfile.py`), 461-board classifier (`totem_catalog.py`), and glyph/font-width formatter (`totem_format.py`).
- Key files: `src/ets2_realism/normalize/currencies.py`, `src/ets2_realism/normalize/fx.py`, `src/ets2_realism/normalize/fuel.py`, `src/ets2_realism/normalize/totem_format.py`.

**`src/ets2_realism/registry/`:**
- Purpose: Canonical 225-country law registry validation, dynamic seasonal DST timezone resolution, and locked `schema_version=1` `RealismSnapshot` export/verification.
- Contains: Law & alias schemas (`models.py`), strict loader/validator (`loader.py`), `zoneinfo`/`tzdata` DST resolver (`timezone.py`), and snapshot + `SHA256SUMS.txt` engine (`snapshot.py`).
- Key files: `src/ets2_realism/registry/models.py`, `src/ets2_realism/registry/loader.py`, `src/ets2_realism/registry/timezone.py`, `src/ets2_realism/registry/snapshot.py`.

**`src/ets2_realism/fetch/`:**
- Purpose: Online-only hardened HTTP/XML/OOXML/HTML transport and live FX + Tier 1/2 fuel price collectors.
- Contains: Hardened HTTP/XXE client (`http.py`), OOXML zip-bomb guard (`_parsing.py`), stdlib HTML table/text decoders (`_html.py`), fetch DTOs (`models.py`), FX fetchers (`fx.py`), EC Weekly Oil Bulletin (`ec_bulletin.py`), 7 EU Tier 1 national feeds (`national.py`), 8 Global Tier 1 feeds (`global_tier1.py`), 10 guarded Tier 2 national portals (`tier2_portals.py`), and full orchestrator (`pipeline.py`).
- Key files: `src/ets2_realism/fetch/pipeline.py`, `src/ets2_realism/fetch/http.py`, `src/ets2_realism/fetch/global_tier1.py`, `src/ets2_realism/fetch/tier2_portals.py`.

**`src/ets2_realism/validate/`:**
- Purpose: Package-independent Offline SCS Workshop Validator and ETS2 `1.62` realism / ProMods / Combo / Totem / License-Taint invariant engine.
- Contains: Diagnostic models & hard-fail collector (`models.py`), Workshop/local ZIP validator (`workshop.py`), and invariant auditor (`invariants.py`).
- Key files: `src/ets2_realism/validate/workshop.py`, `src/ets2_realism/validate/invariants.py`, `src/ets2_realism/validate/models.py`.

**`src/ets2_realism/package/`:**
- Purpose: Clean-room Vanilla+DLC Core mod synthesis, Option 4b Zero-DDS totem compilation, icon generation, and dual-target Workshop/local ZIP building.
- Contains: SII/SUI synthesizers (`synthesize.py`), 460-board + 43-locale totem compiler (`totems.py`), Pillow `276×162` icon generator (`icons.py`), manifest/description/versions renderers (`metadata.py`), and deterministic ZIP/Workshop builder (`builder.py`).
- Key files: `src/ets2_realism/package/builder.py`, `src/ets2_realism/package/totems.py`, `src/ets2_realism/package/synthesize.py`, `src/ets2_realism/package/metadata.py`.

**`src/ets2_realism/publish/`:**
- Purpose: Phase A weekly semi-auto release orchestration, canonical SHA-256 diff-gating, and structured seasonal changelogs.
- Contains: Canonical Workshop hashing & ledger I/O (`ledger.py`), Markdown changelog renderer (`changelog.py`), and release orchestrator (`release.py`).
- Key files: `src/ets2_realism/publish/release.py`, `src/ets2_realism/publish/ledger.py`, `src/ets2_realism/publish/changelog.py`.

**`src/ets2_realism/merge/`:**
- Purpose: Offline ProMods Companion Builder (`EU + ME + MA + TGS`) and `compose-local` arbitrary map-combo patch composer.
- Contains: Multi-source load-order parser & D-10 self-exclusion (`load_order.py`), include-aware `VfsStack` country scanner (`scanner.py`), 3-tier alias resolver with SemEuropa shield (`aliases.py`), `FieldOwnershipPolicy` surgical merger (`policy.py`), ProMods pack discovery (`promods_discovery.py`), dynamic 43-locale `pm*_fuel` compiler (`promods_fuel.py`), ProMods edition builder (`promods_builder.py`), opt-in JRR/7RM hardcoded totem rewriter (`hardcoded_totems.py`), and `compose_local()` orchestrator (`compose.py`).
- Key files: `src/ets2_realism/merge/compose.py`, `src/ets2_realism/merge/policy.py`, `src/ets2_realism/merge/load_order.py`, `src/ets2_realism/merge/promods_builder.py`, `src/ets2_realism/merge/promods_fuel.py`.

**`src/ets2_realism/audit/`:**
- Purpose: Strictly quarantined read-only internal OSM speed-limit drift auditor and automated `CC BY 4.0` license-taint scanner.
- Contains: Audit/taint Pydantic models (`models.py`), `westnordost` comparator & Markdown renderer (`osm_speeds.py`), opt-in Overpass/Taginfo spot-checker (`overpass.py`), and repo/snapshot/package taint scanner (`taint.py`).
- Key files: `src/ets2_realism/audit/osm_speeds.py`, `src/ets2_realism/audit/taint.py`, `src/ets2_realism/audit/overpass.py`.

**`data/`:**
- Purpose: All checked-in clean-room static data inputs (ETS2 `1.62` baseline schemas, 225 statutory country law files, alias/currency/slug mappings, and 186 curated Tier 3 fuel baselines).
- Contains: Sorted, UTF-8 no-BOM LF JSON files validated by strict Pydantic schemas and license-taint gates.
- Key files: `data/baselines/ets2_1.62_def/manifest.json`, `data/laws/countries/<iso2>.json`, `data/laws/speed_audit_allowlist.json`, `data/mappings/ets2_countries.json`, `data/mappings/country_aliases.json`, `data/mappings/currencies.json`, `data/curated/tier3_fuel_baselines.json`.

**`state/`:**
- Purpose: Mutable operational state committed via automated Phase A Release PRs.
- Contains: Canonical price/FX lockfile and per-edition release ledger.
- Key files: `state/prices.lock.json`, `state/published.json`.

**`assets/icons/`:**
- Purpose: Checked-in clean-room `276×162` JPEG Workshop/Mod Manager preview icons.
- Contains: `summer.jpg`, `winter.jpg`, `promods_summer.jpg`, `promods_winter.jpg`.
- Key files: Regenerable via `scripts/generate_icons.py` or `ets2-realism package icons`.

**`tests/`:**
- Purpose: Comprehensive offline pytest suite covering every subpackage, contract, security edge case, and taint invariant, plus opt-in local archive integration tests.
- Contains: 45 `test_*.py` files (`634` CI-safe tests + `4` `@pytest.mark.local_ets2` / `@pytest.mark.local_promods` tests).
- Key files: `tests/test_cli_scaffold.py`, `tests/test_baseline_contracts.py`, `tests/test_registry_contracts.py`, `tests/test_validate_workshop.py`, `tests/test_totem_compiler.py`, `tests/test_compose_local.py`, `tests/test_promods_builder.py`, `tests/test_license_taint_gate.py`.

## Key File Locations

**Entry Points:**
- `src/ets2_realism/cli.py`: Root `ets2-realism` CLI entrypoint and all 9 command handlers.
- `scripts/generate_icons.py`: Standalone icon regeneration wrapper.
- `.github/workflows/ci.yml`: Push/PR lint, format, strict typecheck, and pytest gate.
- `.github/workflows/phase-a-release.yml`: Weekly Phase A fetch, release build, validation, snapshot release, and persistent Release PR workflow.
- `.github/workflows/osm-speed-audit.yml`: Monthly quarantined OSM speed-limit drift advisory workflow.

**Configuration:**
- `pyproject.toml`: Package metadata (`ets2-country-realism`), Hatchling wheel target (`src/ets2_realism`), `ets2-realism` console script, runtime & dev dependencies, Ruff (`line-length = 100`, `py312`), Basedpyright (`strict`), Pytest markers (`local_ets2`, `local_promods`).
- `uv.lock`: Locked reproducible dependency graph.
- `.gitattributes`: Enforces LF line endings on source/JSON/SII and binary attributes on `.scs`/`.dds`/`.jpg`/`.png`.
- `.gitignore`: Excludes `.venv/`, `build/`, `dist/`, `out/`, `raw/`, `vendor/`, caches, and temp files.

**Core Logic:**
- `src/ets2_realism/vfs/stack.py` & `src/ets2_realism/vfs/hashfs.py`: Multi-layer VFS overlay and HashFS v1/v2 container readers.
- `src/ets2_realism/sii/document.py` & `src/ets2_realism/sii/lexer.py`: Span-preserving surgical SII/SUI engine.
- `src/ets2_realism/registry/snapshot.py` & `src/ets2_realism/registry/timezone.py`: Locked v1 `RealismSnapshot` contract and seasonal DST resolver.
- `src/ets2_realism/fetch/pipeline.py` & `src/ets2_realism/normalize/fuel.py`: 3-tier global FX/fuel fetch & circuit-breaker normalization.
- `src/ets2_realism/package/builder.py` & `src/ets2_realism/package/totems.py`: Core dual-target packager & Option 4b Zero-DDS totem compiler.
- `src/ets2_realism/validate/workshop.py` & `src/ets2_realism/validate/invariants.py`: Package-independent Offline SCS Workshop Validator.
- `src/ets2_realism/publish/release.py` & `src/ets2_realism/publish/ledger.py`: Canonical SHA-256 diff-gate & Phase A release pipeline.
- `src/ets2_realism/merge/compose.py`, `src/ets2_realism/merge/policy.py`, `src/ets2_realism/merge/promods_builder.py`: `FieldOwnershipPolicy` surgical merger, ProMods Companion Builder, and `compose-local`.
- `src/ets2_realism/audit/osm_speeds.py` & `src/ets2_realism/audit/taint.py`: Quarantined OSM speed audit and license-taint gate.

**Testing:**
- `tests/test_vfs_*.py` (3 files): CityHash64, HashFS/ZIP/Dir archives, `VfsStack`.
- `tests/test_sii_*.py` (5 files): Lexer/document, hygiene, country, speed limits, sign boards & locales.
- `tests/test_baseline_*.py` (2 files): Baseline extraction & 1.62 contract assertions.
- `tests/test_registry_*.py`, `tests/test_country_aliases.py`, `tests/test_global_registry_expansion.py` (6 files): 225-country registry schema, contracts, timezone, aliases, v1 snapshot verification.
- `tests/test_fetch_*.py` & `tests/test_normalize_*.py` (7 files): FX, EU/Global Tier 1, Tier 2 portals, fetch pipeline, currency/fuel normalization.
- `tests/test_totem_*.py`, `tests/test_package_*.py`, `tests/test_hardcoded_totems.py` (6 files): Zero-DDS totem formatting/compiling, SII synthesis, icons/metadata, Core builder, JRR/7RM hardcoded totems.
- `tests/test_validate_*.py` (2 files): Offline SCS Workshop Validator & 1.62/ProMods/Combo invariants.
- `tests/test_publish_*.py` (3 files): Release ledger, Phase A orchestrator, workflow contract.
- `tests/test_merge_*.py`, `tests/test_promods_*.py`, `tests/test_compose_local.py` (8 files): Load order, scanner, aliases, policy, ProMods discovery/fuel/builder, `compose-local`.
- `tests/test_audit_osm_speeds.py`, `tests/test_license_taint_gate.py`, `tests/test_cli_scaffold.py` (3 files): Quarantined OSM audit, CC BY 4.0 taint gate, CLI subcommand coverage.

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `promods_builder.py`, `totem_catalog.py`, `speed_limits.py`); internal helper modules use a leading underscore (`src/ets2_realism/fetch/_html.py`, `src/ets2_realism/fetch/_parsing.py`).
- Test modules: `test_<subsystem>_<topic>.py` flat inside `tests/` (e.g., `tests/test_merge_policy.py`, `tests/test_fetch_tier2_portals.py`).
- Country law records: lowercase ISO-2 JSON files `data/laws/countries/<iso2>.json` (e.g., `data/laws/countries/is.json`, `data/laws/countries/de.json`).
- Emitted ETS2 archives: `ETS2_Country_Realism_Core_{Summer|Winter}.zip`, `ETS2_Country_Realism_ProMods_{Summer|Winter}.zip`, `zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs`.
- Emitted fuel locale modules: `locale/<lang>/local_module.ets2r_fuel.sii` (unit `.ets2r_fuel`), `locale/<lang>/local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii`.

**Directories:**
- Python subpackages: single lowercase domain noun (`vfs/`, `sii/`, `baseline/`, `normalize/`, `registry/`, `fetch/`, `validate/`, `package/`, `publish/`, `merge/`, `audit/`).
- Data directories: lowercase plural nouns (`data/baselines/`, `data/laws/countries/`, `data/mappings/`, `data/curated/`).
- Build output directories (gitignored): `dist/workshop/{summer,winter,promods-summer,promods-winter}/`, `dist/local/`, `dist/snapshots/`, `dist/audit/`.

## Where to Add New Code

**New Country Law / Territory Support:**
- Statutory law record: `data/laws/countries/<iso2>.json`
- Country slug/ISO mapping: `data/mappings/ets2_countries.json`
- Third-party map-mod slug alias or TZ override: `data/mappings/country_aliases.json`
- New currency or Tier 3 curated fuel baseline: `data/mappings/currencies.json` and `data/curated/tier3_fuel_baselines.json`
- Tests: `tests/test_registry_contracts.py` and `tests/test_global_registry_expansion.py`

**New Live Fuel Collector (Tier 1 or Tier 2):**
- Online collector implementation: `src/ets2_realism/fetch/national.py` (EU Tier 1), `src/ets2_realism/fetch/global_tier1.py` (Global Tier 1), or `src/ets2_realism/fetch/tier2_portals.py` (guarded Tier 2)
- Precedence & pipeline wiring: `src/ets2_realism/fetch/pipeline.py` (`_FEED_PRECEDENCE`) and `src/ets2_realism/fetch/__init__.py`
- Staleness bucket (if monthly/quarterly): `src/ets2_realism/normalize/lockfile.py`
- Tests: `tests/test_fetch_fuel.py`, `tests/test_fetch_global_tier1.py`, `tests/test_fetch_tier2_portals.py`, or `tests/test_fetch_pipeline.py` (using mocked `httpx.MockTransport`)

**New Validation Rule or ETS2 Invariant:**
- Workshop/archive/format check: `src/ets2_realism/validate/workshop.py`
- Realism/ProMods/Combo/Totem/Taint invariant: `src/ets2_realism/validate/invariants.py` (keep `validate/` strictly independent of `package/`, `merge/`, `audit/`)
- Tests: `tests/test_validate_workshop.py` or `tests/test_validate_invariants.py`

**New Map-Combo Policy / Totem Pattern:**
- Merge policy rule: `src/ets2_realism/merge/policy.py`
- Load-order / archive detection: `src/ets2_realism/merge/load_order.py` or `src/ets2_realism/merge/scanner.py`
- Opt-in hardcoded board signature: `src/ets2_realism/merge/hardcoded_totems.py`
- Tests: `tests/test_merge_policy.py`, `tests/test_compose_local.py`, `tests/test_hardcoded_totems.py`

**New CLI Subcommand:**
- Parser registration & handler: `src/ets2_realism/cli.py` (keep domain logic inside the appropriate subpackage; CLI handles arg parsing, exit codes, and text/`--json` rendering only)
- Tests: `tests/test_cli_scaffold.py`

**Shared Offline Utilities:**
- Path normalization & VFS helpers: `src/ets2_realism/vfs/types.py`
- SII string quoting & hygiene: `src/ets2_realism/package/synthesize.py`, `src/ets2_realism/sii/hygiene.py`
- Hardened HTTPS / XML / HTML helpers (online-only): `src/ets2_realism/fetch/http.py`, `_parsing.py`, `_html.py`

## Special Directories

**`dist/`, `out/`, `build/`, `raw/`, `vendor/`:**
- Purpose: Generated Workshop staging trees, local `.zip`/`.scs` mods, `realism-snapshot-*.json` + `SHA256SUMS.txt`, raw baseline caches, and audit reports.
- Generated: Yes
- Committed: No (explicitly ignored in `.gitignore` and enforced by `assert_out_dir_not_tracked()` for ProMods/Combo IP protection).

**`data/baselines/ets2_1.62_def/`:**
- Purpose: Deterministic clean-room JSON extracts of ETS2 `1.62.3.3s` metadata enabling 100% offline CI builds without game archives.
- Generated: Yes (via `ets2-realism baseline extract` on a machine with ETS2 `1.62.3.3s` installed).
- Committed: Yes (byte-verified via `ets2-realism baseline extract --check`).

**`state/`:**
- Purpose: Versioned operational lockfile (`prices.lock.json`) and Phase A release ledger (`published.json`).
- Generated: Yes (updated by `ets2-realism fetch` and `ets2-realism publish release --write-state`).
- Committed: Yes (advanced via `release/phase-a-weekly` PRs after manual Workshop upload).

**`.agents/skills/scs-modding-wiki/`:**
- Purpose: Vendored local mirror of official SCS Modding Wiki documentation (162 pages) for offline modding reference.
- Generated: No (vendored reference skill).
- Committed: Yes (excluded from Ruff linting in `pyproject.toml:44`).

**`.planning/`:**
- Purpose: GSD project roadmap, requirements, phase plans/summaries/verifications, and codebase maps.
- Generated: Managed by GSD workflows.
- Committed: Yes (excluded from Ruff linting in `pyproject.toml:44`).

---

*Structure analysis: 2026-11-26*
