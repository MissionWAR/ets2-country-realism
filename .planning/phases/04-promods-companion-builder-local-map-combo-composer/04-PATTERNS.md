# Phase 4: ProMods Companion Builder & Local Map Combo Composer - Pattern Map

**Mapped:** 2026-11-24
**Phase Scope:** `MAP-01`, `MAP-02`, `MAP-03`, `MAP-04`, `MAP-05` (Plans `04-01` through `04-04`)
**Files analyzed:** 42 planned new/modified files (10 new source modules under `src/ets2v2/merge/`, 15 modified source modules across `registry/`, `normalize/`, `fetch/`, `package/`, `validate/`, `publish/`, `cli.py`, 5 data/state/asset artifacts, 2 config/workflow files, 10 new/updated test modules)
**Analogs found:** 39 / 42 (3 new modules introduce net-new ETS2 user-environment / third-party-mod parsing capabilities — `game.log.txt` & plaintext `profile.sii` load-order extraction, dynamic ProMods `pm*_fuel` key discovery, and opt-in JRR/7RM numeric sign-board rewriting — with no direct Phase 1–3 analog, while strictly replicating Phase 1–3 VFS, SII, Pydantic v2, determinism, and CLI/test patterns)

---

## 1. Proposed Phase 4 Package & Module Layout

### Subpackage Alignment (`src/ets2v2/`)

Per `04-CONTEXT.md` (lines 74, 126, 131), Phase 4 unlocks the final planned subpackage **`merge/`** under `src/ets2v2/` — leaving **zero** deferred phase directories in `tests/test_cli_scaffold.py::test_active_phase_only_package_layout`.

**Layering Decision (`merge/` at Layer 9A alongside `publish/` at Layer 9B, ABOVE both `package/` [Layer 7B] and `validate/` [Layer 8]):**
Placing `ets2v2.merge` at **Layer 9A** (parallel to `ets2v2.publish` at Layer 9B) solves every Phase 4 dependency cleanly with **zero cycles** and **strict offline isolation**:
1. **`package/` (Layer 7B)** owns Core synthesis, Option 4b Vanilla totems, clean-room Pillow icons (Core + ProMods + Combo), `manifest.sii` / `versions.sii` / `description.txt` metadata renderers, and deterministic ZIP/Workshop writers. `package/` NEVER imports `merge/`, `validate/`, `publish/`, or `fetch/`.
2. **`validate/` (Layer 8)** remains **100% independent** of `package/`, `merge/`, `publish/`, `normalize/`, and `fetch/` (`validate ⊥ package ⊥ merge ⊥ fetch ⊥ normalize ⊥ publish`), inspecting built Workshop roots, local `.zip`s, and `zz_ETS2V2_ComboPatch_*.scs` archives purely via `ets2v2.vfs`, `ets2v2.sii`, `ets2v2.baseline.models`, and `PIL`.
3. **`merge/` (Layer 9A — 100% OFFLINE)** composes `vfs`, `sii`, `baseline.models`, `normalize.{models, lockfile, totem_format}`, `registry`, `package` (reusing deterministic ZIP/Workshop staging, icons, metadata, and Vanilla Option 4b totems directly), AND `validate` (enforcing pre-write/post-stage Offline SCS Validation on ProMods Editions and `zz_ETS2V2_ComboPatch_*.scs` — mirroring how `publish/release.py` calls `validate_workshop_package` & `validate_local_zip`!). `merge/` NEVER imports `fetch`, `publish`, `httpx`, or `openpyxl`.

```text
src/ets2v2/
├── __init__.py                   # Existing — __version__ = "0.1.0"
├── py.typed                      # Existing — PEP 561 marker
├── cli.py                        # Modified (04-01..04-04) — add `registry snapshot-verify`,
│                                 #   `package promods`, `compose-local`, and `validate --profile`
├── vfs/                          # Existing (Phase 1, Layers 0-2) — unchanged (VfsStack, open_archive,
│                                 #   ZipArchive, DirectoryArchive, ProtectedArchiveStub reused directly)
├── sii/                          # Existing (Phase 1, Layers 0-3) — unchanged (SiiDocument,
│                                 #   patch_country_data, patch_speed_limits, parse_country_includes,
│                                 #   parse_sign_board, parse_localization_db, validate_sii_hygiene reused)
├── baseline/                     # Existing (Phase 1, Layer 4) — unchanged
├── normalize/                    # Modified (Layer 5 — 100% offline pure domain & lockfile)
│   ├── currencies.py             # Modified (04-01) — extend territory/currency tables for ProMods
│   │                             #   EU+ME+MA+TGS currencies (keeping 17 core European FX mandatory
│   │                             #   and ProMods extra currencies optional/fallback-safe)
│   ├── fx.py                     # Modified (04-01) — support optional extended ProMods FX currencies
│   │                             #   without breaking 17-currency core cross-validation
│   ├── lockfile.py               # Modified (04-01) — preserve/seed ProMods territories cleanly
│   └── totem_format.py           # Modified (04-02) — add national pump formatting rules for ProMods
│                                 #   currencies (e.g. JOD 3-dec, integer AMD/IQD/KZT/LBP/SYP, GBP/GIP pence)
├── registry/                     # Modified (Layer 6 — offline statutory laws, aliases & locked v1 snapshot)
│   ├── __init__.py               # Modified (04-01) — export alias & snapshot verification symbols
│   ├── models.py                 # Modified (04-01) — CountryMappingEntry.country_id: int | None
│   │                             #   (required when vanilla_1_62=True) + CountryAliasRegistry (D-02)
│   ├── loader.py                 # Modified (04-01) — partition validate_law_registry() on vanilla_1_62;
│   │                             #   add load_country_aliases() & validate_country_aliases()
│   ├── timezone.py               # Modified (04-01) — extend IANA_NUMERIC_ABBR_OVERRIDES if needed
│   │                             #   for ProMods ME/TGS zones (e.g. Asia/Baghdad, Asia/Riyadh, Asia/Almaty)
│   └── snapshot.py               # Modified (04-01) — keep schema_version=1 frozen (D-02); derive
│                                 #   imperial_units=(law.speed_unit=="mph") for vanilla_1_62=False;
│                                 #   add load_realism_snapshot(), write_sha256sums(), verify_snapshot_file()
├── fetch/                        # Modified (Layer 7A — ONLINE ONLY, imported ONLY by cli.py)
│   └── pipeline.py               # Modified (04-01) — retain & FX-reprice seeded ProMods entries in
│                                 #   state/prices.lock.json so Friday CI fetch never wipes ProMods prices
├── package/                      # Modified (Layer 7B — 100% offline emitters, package ⊥ merge ⊥ validate ⊥ fetch)
│   ├── __init__.py               # Modified (04-02/04-04) — export public ZIP/Workshop helpers & icons/metadata
│   ├── builder.py                # Modified (04-01/04-02) — keep build_core_edition() strictly 36 Vanilla;
│   │                             #   expose public write_deterministic_zip(), write_workshop_tree(),
│   │                             #   validate_rel_path(), ensure_contained(), default_package_version()
│   ├── icons.py                  # Modified (04-02/04-04) — add render_promods_icon_bytes(),
│   │                             #   generate_promods_icons(), render_combo_icon_bytes() (276x162 RGB)
│   ├── metadata.py               # Modified (04-02/04-04) — add ETS2V2 self-exclusion manifest comment (D-10),
│   │                             #   ProMods & ComboPatch manifest.sii and description.txt renderers
│   ├── synthesize.py             # Existing — unchanged
│   └── totems.py                 # Existing — unchanged (reused directly by merge/promods_builder & compose)
├── validate/                     # Modified (Layer 8 — 100% offline, validate ⊥ package ⊥ merge ⊥ fetch ⊥ normalize)
│   ├── __init__.py               # Modified (04-02/04-04) — export PackageProfile & ProMods/Combo validators
│   ├── models.py                 # Modified (04-02) — add PackageProfile = Literal["core", "promods", "combo"]
│   ├── invariants.py             # Modified (04-02/04-04) — add validate_promods_realism_invariants(),
│   │                             #   validate_promods_locale_modules_consistency(), validate_combo_invariants()
│   └── workshop.py               # Modified (04-02/04-04) — parameterize validate_workshop_package() &
│                                 #   validate_local_zip() with profile: PackageProfile = "core"
├── merge/                        # NEW (Phase 4, Layer 9A — 100% OFFLINE, merge ⊥ fetch, merge ⊥ publish)
│   ├── __init__.py               # Public __all__ facade (sorted alphabetically, RUF022)
│   ├── models.py                 # Strict frozen Pydantic v2 DTOs: LoadOrderEntry, ResolvedMapCountry,
│   │                             #   FieldPolicyDecision, ProtectedArchiveDiagnostic, ProModsPackSet,
│   │                             #   ProModsBuildReport, HardcodedTotemResult, ComposeReport
│   ├── aliases.py                # D-13 deterministic 3-tier country resolver (aliases -> ISO3/ISO2 -> slug)
│   ├── policy.py                 # D-14/D-15 FieldOwnershipPolicy (max_of_map_and_real, patch_if_single_tz,
│   │                             #   custom-lane & train/tram preservation, imperial_units parity guard)
│   ├── load_order.py             # D-09/D-10/D-11 parsers (--modlist, --game-log, --profile + ScsC guard),
│   │                             #   Workshop 227300 resolution, D-10 self-exclusion, smart --unpacked-defs
│   ├── scanner.py                # D-13 VfsStack def/country*.sii @include graph scanner (.sui/.sii, base/,
│   │                             #   empty SiiNunit {} suppression stubs, winning layer provenance)
│   ├── promods_fuel.py           # D-08 dynamic local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii key reader
│   │                             #   & 43-locale native-currency emitter (verbatim unknown-key preservation)
│   ├── promods_builder.py        # D-05..D-08 ProMods Companion Builder (EU+ME+MA+TGS auto-discovery,
│   │                             #   --require-all-packs, tracked-repo --out-dir refusal, dual targets,
│   │                             #   Offline Validator profile="promods")
│   ├── hardcoded_totems.py       # D-16 opt-in --patch-hardcoded-totems rewriter (JRR/7RM numeric boards)
│   └── compose.py                # D-09..D-16 `ets2v2 compose-local` orchestrator emitting validated
│                                 #   zz_ETS2V2_ComboPatch_{Summer|Winter}.scs + --dry-run / --report-json
└── publish/                      # Modified (Layer 9B — 100% offline, publish ⊥ fetch, publish ⊥ merge)
    └── release.py                # Modified (04-01) — emit dist/snapshots/SHA256SUMS.txt alongside snapshots
```

### Complete Acyclic Module DAG Verification (Layers 0–10)

Phase 4 preserves a strictly bottom-up **11-layer DAG (Layers 0–10)** with **zero upward or lateral cycles** and **six hard AST-enforced isolation walls**:

```text
Layer 10: ets2v2.cli
            ├──► ets2v2.vfs, ets2v2.baseline                    (Phase 1)
            ├──► ets2v2.registry, ets2v2.package,
            │    ets2v2.validate, ets2v2.publish                (Phase 2)
            ├──► ets2v2.normalize, ets2v2.fetch                 (Phase 3)
            └──► ets2v2.merge                                   (Phase 4)

Layer 9A: ets2v2.merge    {models, aliases, policy, load_order, [OFFLINE — merge ⊥ fetch, merge ⊥ publish,
                           scanner, promods_fuel,                zero httpx/openpyxl]
                           promods_builder, hardcoded_totems,
                           compose}
            └──► ets2v2.vfs.*, ets2v2.sii.*, ets2v2.baseline.models,
                 ets2v2.normalize.{models, lockfile, totem_format, totem_catalog},
                 ets2v2.registry.*, ets2v2.package.{builder, icons, metadata, synthesize, totems},
                 ets2v2.validate.{models, workshop}

Layer 9B: ets2v2.publish  {ledger, changelog, release}          [OFFLINE — publish ⊥ fetch, publish ⊥ merge,
            └──► ets2v2.baseline.models, ets2v2.normalize.*,     zero httpx/openpyxl]
                 ets2v2.registry.*, ets2v2.package.*,
                 ets2v2.validate.*, ets2v2.sii.document, ets2v2.vfs.types

Layer 8:  ets2v2.validate {models, invariants, workshop}        [OFFLINE — validate ⊥ package ⊥ merge
            └──► ets2v2.vfs.{zip_archive, dir_archive, types},   ⊥ fetch ⊥ normalize ⊥ publish]
                 ets2v2.sii.{hygiene, document, country, speed_limits,
                             sign_board, localization, lexer},
                 ets2v2.baseline.models, PIL

Layer 7A: ets2v2.fetch    {models, http, fx, ec_bulletin,       [ONLINE ONLY — imported ONLY by cli.py]
                           national, pipeline}
            └──► httpx, openpyxl, ets2v2.baseline.models, ets2v2.normalize.*

Layer 7B: ets2v2.package  {synthesize, totems, metadata,        [OFFLINE — package ⊥ merge ⊥ validate
                           icons, builder}                       ⊥ fetch ⊥ publish]
            └──► ets2v2.sii.{hygiene, country, speed_limits, lexer},
                 ets2v2.baseline.models, ets2v2.normalize.{models, lockfile, totem_format},
                 ets2v2.registry.*, ets2v2.vfs.types, PIL

Layer 6:  ets2v2.registry {models, timezone, loader, snapshot}  [OFFLINE — registry ⊥ package ⊥ merge
            └──► ets2v2.baseline.models, ets2v2.sii.speed_limits, ⊥ validate ⊥ fetch ⊥ publish]
                 ets2v2.normalize.{models, fx}, stdlib zoneinfo (tzdata)

Layer 5:  ets2v2.normalize {models, currencies, lockfile, fx,   [OFFLINE — pure domain]
                            fuel, totem_catalog, totem_format}
            └──► ets2v2.baseline.models, pydantic, stdlib

Layer 4:  ets2v2.baseline {models, extractor}                   (Phase 1 — unchanged)
            └──► ets2v2.vfs, ets2v2.sii

Layer 3:  ets2v2.sii.{country, speed_limits, sign_board, localization}
Layer 2:  ets2v2.vfs.{hashfs, stack}  |  ets2v2.sii.document    (vfs ⊥ sii)
Layer 1:  ets2v2.vfs.{cityhash, dir_archive, zip_archive} | ets2v2.sii.hygiene
Layer 0:  ets2v2.__init__ | ets2v2.vfs.types | ets2v2.sii.lexer
```

**Six Mandatory AST-Enforced Isolation Walls (`tests/test_cli_scaffold.py:270-290` & `tests/test_validate_workshop.py:88-136`):**
1. **`validate` wall:** NEVER imports `package`, `merge`, `normalize`, `fetch`, `publish`, `httpx`, or `openpyxl`.
2. **`merge` wall (NEW):** NEVER imports `fetch`, `publish`, `httpx`, or `openpyxl` — guarantees 100% offline ProMods Companion Builder and `ets2v2 compose-local` execution.
3. **`package` wall:** NEVER imports `fetch`, `merge`, `validate`, `publish`, `httpx`, or `openpyxl`.
4. **`publish` wall:** NEVER imports `fetch`, `merge`, `httpx`, or `openpyxl`.
5. **`normalize` wall:** NEVER imports `fetch`, `registry`, `package`, `validate`, `merge`, `publish`, `httpx`, or `openpyxl`.
6. **`registry` wall:** NEVER imports `fetch`, `package`, `validate`, `merge`, `publish`, `httpx`, or `openpyxl`.

### Active-Phase Layout Gate & Marker Updates (`tests/test_cli_scaffold.py:64-88`, `pyproject.toml:54-56`)

Plan `04-01` (Wave 1) unlocks `merge/` and registers the `@pytest.mark.local_promods` marker:

```python
# tests/test_cli_scaffold.py
def test_active_phase_only_package_layout() -> None:
    pkg_root = REPO_ROOT / "src" / "ets2v2"
    assert pkg_root.is_dir()

    entries = {entry.name for entry in pkg_root.iterdir() if entry.name != "__pycache__"}
    allowed_phase4_entries = {
        "__init__.py",
        "py.typed",
        "cli.py",
        "vfs",
        "sii",
        "baseline",
        "normalize",
        "registry",
        "fetch",
        "package",
        "validate",
        "merge",
        "publish",
    }

    assert entries <= allowed_phase4_entries
    assert {"__init__.py", "py.typed", "cli.py", "merge"} <= entries
```

And in `pyproject.toml:54-56`:
```toml
markers = [
    "local_ets2: tests requiring local ETS2 1.62.3.3s archives",
    "local_promods: tests requiring local ProMods or user map-combo archives",
]
```

### Non-Python Repository Artifacts Added / Modified in Phase 4

| Path | Plan | Committed? | Format / Hygiene Contract |
|---|---|---|---|
| `pyproject.toml` | `04-01` | Yes | Add `local_promods` marker under `[tool.pytest.ini_options].markers`; zero new third-party dependencies required! |
| `data/laws/countries/<iso2>.json` | `04-01` | Yes | Canonical sorted UTF-8 no-BOM LF JSON expanded from 36 Vanilla countries to all ~75+ Vanilla + ProMods `EU+ME+MA+TGS` territories (`D-01`); zero `.sii`/`.sui` under `data/` |
| `data/mappings/ets2_countries.json` | `04-01` | Yes | Canonical sorted JSON (`ets2_slug` ascending); 36 `vanilla_1_62: true` entries with non-null `country_id` + ~39+ `vanilla_1_62: false` ProMods entries with `country_id: null` (`D-01`, `D-02`) |
| `data/mappings/country_aliases.json` | `04-01` | Yes | Bundled canonical sorted JSON (`schema_version: 1`) mapping sub-national/mod slugs (`indo_b`, `n_ireland`, `aland`, `svalbard`, `jersey`, `guernsey`, `isle_of_man`, `westbank`, `northern_cyprus`, Project Japan prefectures, etc.) -> ISO-2 (`D-02`, `D-13`) |
| `state/prices.lock.json` | `04-01` | Yes | Canonical sorted UTF-8 no-BOM LF JSON expanded with curated seed fuel prices + FX rates for all ProMods territories (`D-01`) |
| `assets/icons/promods_{summer,winter}.jpg` | `04-02` | Yes | Clean-room Pillow `276x162` baseline RGB JPEG, zero EXIF/ICC (`D-07`), generated via `ets2v2 package icons` |
| `.github/workflows/phase-a-release.yml` | `04-01` | Yes | UTF-8 no-BOM LF; verify `dist/snapshots/SHA256SUMS.txt` and publish `realism-snapshot-{summer,winter}.json` + `SHA256SUMS.txt` to rolling public GitHub Release `snapshots-latest` (`D-03`) |
| `dist/snapshots/SHA256SUMS.txt`, `dist/workshop/promods-{summer,winter}/`, `dist/local/ETS2V2_ProMods_*.zip`, `dist/local/zz_ETS2V2_ComboPatch_*.scs` | `04-01`, `04-02`, `04-04` | **No** | Gitignored under `dist/`; zero ProMods or third-party mod files ever committed to Git (`D-08`) |

---

## 2. File Classification & File-to-Analog Mapping Table

All analog paths below are git-tracked source files verified in `src/`, `tests/`, `.github/`, and `pyproject.toml`.

| Plan | New / Modified File | Role | Data Flow | Closest Tracked Phase 1–3 Analog | Match Quality | Key Patterns to Replicate |
|---|---|---|---|---|---|---|
| `04-01` | `pyproject.toml` | config | n/a | `pyproject.toml` (in-place) | exact | Add `local_promods` pytest marker alongside `local_ets2`; keep runtime deps, `ruff`, and strict `basedpyright` untouched |
| `04-01` | `tests/test_cli_scaffold.py` | test / contract | contract | `tests/test_cli_scaffold.py` (in-place) | exact | Unlock `"merge"` in `test_active_phase_only_package_layout`; extend `test_phase3_ast_dag_isolation_walls` -> 6 walls incl. `"merge"`, `"registry"`, `"validate"` blocking `"merge"` |
| `04-01` | `src/ets2v2/registry/models.py` | model / schema | transform | `src/ets2v2/registry/models.py` (in-place) | exact | `CountryMappingEntry.country_id: int \| None = Field(default=None, ge=1)` + `@model_validator` requiring `int` when `vanilla_1_62=True`; add frozen strict `CountryAliasRegistry` (`schema_version: Literal[1] = 1`) |
| `04-01` | `src/ets2v2/registry/loader.py` | service / loader | file-I/O | `src/ets2v2/registry/loader.py` (in-place) | exact | Partition `validate_law_registry()` on `entry.vanilla_1_62`; skip `None` in `seen_ids`; add `load_country_aliases()` & `validate_country_aliases()` using `_check_raw_hygiene()` & `serialize_registry_json_bytes()` |
| `04-01` | `src/ets2v2/registry/snapshot.py` | model / serializer | file-I/O + transform | `src/ets2v2/registry/snapshot.py` & `publish/ledger.py` | exact | Preserve locked `schema_version: Literal[1] = 1` & `extra="forbid"`; derive `imperial_units=(law.speed_unit=="mph")` for `vanilla_1_62=False`; add `load_realism_snapshot()`, `write_sha256sums()`, `parse_sha256sums()`, `verify_snapshot_file()` |
| `04-01` | `src/ets2v2/registry/timezone.py` | utility / domain | transform | `src/ets2v2/registry/timezone.py` (in-place) | exact | Extend `IANA_NUMERIC_ABBR_OVERRIDES` for ProMods ME/TGS zones with numeric `tzname()` (e.g. `Asia/Baghdad`, `Asia/Riyadh`, `Asia/Tbilisi`, `Asia/Yerevan`, `Asia/Baku`, `Asia/Almaty`) |
| `04-01` | `src/ets2v2/registry/__init__.py` | barrel / facade | n/a | `src/ets2v2/registry/__init__.py` (in-place) | exact | Export new alias and snapshot verification symbols in alphabetically sorted `__all__` (`RUF022`) |
| `04-01` | `src/ets2v2/normalize/{currencies,fx,lockfile}.py` | utility / state | transform + file-I/O | Existing files (in-place) | exact | Add ProMods territory currencies & optional FX sanity bands while keeping 17 core European FX mandatory; preserve/seed ProMods territories in `seed_initial_lockfile()` |
| `04-01` | `src/ets2v2/fetch/pipeline.py` | service / orchestrator | batch | `src/ets2v2/fetch/pipeline.py` (in-place) | exact | Preserve & FX-reprice non-European/ProMods lockfile territories during weekly `ets2v2 fetch` instead of dropping ISO2 codes outside the 39 European Phase 3 set |
| `04-01` | `src/ets2v2/publish/release.py` | service / orchestrator | batch | `src/ets2v2/publish/release.py` (in-place) | exact | Call `write_sha256sums()` to emit `dist/snapshots/SHA256SUMS.txt` after writing both seasonal snapshots; keep Core ledger & validation strictly scoped |
| `04-01` | `.github/workflows/phase-a-release.yml` | CI workflow | batch | `.github/workflows/phase-a-release.yml` (in-place) | exact | Add `ets2v2 registry snapshot-verify` step + rolling `snapshots-latest` GitHub Release upload using step-level `GH_TOKEN: ${{ github.token }}` and zero `${{` inside `run:` blocks |
| `04-01` | `data/laws/countries/*.json`, `data/mappings/{ets2_countries,country_aliases}.json`, `state/prices.lock.json` | data / state | file-I/O | Existing `data/laws/countries/de.json`, `data/mappings/ets2_countries.json`, `state/prices.lock.json` | exact | Canonical sorted UTF-8 no-BOM LF JSON (`serialize_registry_json_bytes` / `serialize_lockfile_bytes`); zero `.sii`/`.sui` under `data/` |
| `04-01` | `tests/test_registry_{schema,contracts,snapshot}.py`, `tests/test_publish_{release,workflow}.py` | test / contract | contract | Existing files (in-place) | exact | Test `country_id=None` for `vanilla_1_62=False`, alias registry hygiene, expanded snapshot counts, `SHA256SUMS.txt` & `snapshot-verify` CLI, and `snapshots-latest` workflow injection safety |
| `04-02` | `src/ets2v2/merge/__init__.py` | barrel / facade | n/a | `src/ets2v2/package/__init__.py` | exact | `from __future__ import annotations`, absolute imports, alphabetically sorted `__all__` (`RUF022`) |
| `04-02` | `src/ets2v2/merge/models.py` | model / DTO | transform | `src/ets2v2/validate/models.py` & `fetch/models.py` | exact | Strict frozen Pydantic v2 models (`ConfigDict(strict=True, frozen=True, extra="forbid")`) for load order, policy actions, protected archives, ProMods packs, and `--json` reports |
| `04-02` | `src/ets2v2/merge/aliases.py` | utility / resolver | transform | `src/ets2v2/normalize/totem_catalog.py` | role-match | Pure deterministic 3-tier country lookup (`country_aliases` -> `iso_country_code`/`country_code` -> `ets2_slug`) returning `(RealismSnapshotCountry \| None, match_tier)` |
| `04-02` | `src/ets2v2/merge/policy.py` | service / domain | transform | `src/ets2v2/sii/country.py` & `sii/speed_limits.py` | exact | Pure `FieldOwnershipPolicy` engine: `max_of_map_and_real` axles, `patch_if_single_tz`, custom-lane & `train`/`tram` preservation, `imperial_units` parity guard, delegating edits to `patch_country_data()` & `patch_speed_limits()` |
| `04-02` | `src/ets2v2/normalize/totem_format.py` | utility / domain | transform | `src/ets2v2/normalize/totem_format.py` (in-place) | exact | Extend `format_national_pump_price()` with ProMods currency formatting (e.g. `JOD` 3-dec, integer `AMD`/`IQD`/`KZT`/`LBP`/`SYP`, `GBP`/`GIP` pence) using `Decimal ROUND_HALF_UP` & uniform `.` |
| `04-02` | `src/ets2v2/merge/promods_fuel.py` | service / compiler | transform | `src/ets2v2/package/totems.py` & `sii/localization.py` | partial | Dynamically inspect installed ProMods `locale/*/local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` keys via `parse_localization_db()`, format matched keys natively across all 43 active locales, preserve unknown keys verbatim, verify `validate_sii_hygiene()` |
| `04-02` | `src/ets2v2/package/builder.py` | service / packager | file-I/O | `src/ets2v2/package/builder.py` (in-place) | exact | Export public `write_deterministic_zip()`, `write_workshop_tree()`, `validate_rel_path()`, `ensure_contained()`, `default_package_version()`; keep `build_core_edition()` strictly 36 Vanilla |
| `04-02` | `src/ets2v2/package/icons.py` | utility / renderer | transform | `src/ets2v2/package/icons.py` (in-place) | exact | Add `render_promods_icon_bytes()`, `generate_promods_icons()`, `render_combo_icon_bytes()` (`276x162` baseline RGB JPEG, zero EXIF/ICC); keep `generate_all_icons()` return keys `{"summer", "winter"}` intact |
| `04-02` | `src/ets2v2/package/metadata.py` | utility / emitter | transform | `src/ets2v2/package/metadata.py` (in-place) | exact | Emit `# ets2v2:managed-package kind=<kind>` comment in `manifest.sii` (`D-10`, zero `WARN 00002`); add ProMods & ComboPatch manifest & `description.txt` renderers with `D-16` attributions and zero volatile dates |
| `04-02` | `src/ets2v2/validate/{models,invariants,workshop,__init__}.py` | service / validator | file-I/O + transform | Existing files (in-place) | exact | Add `PackageProfile = Literal["core", "promods", "combo"]` (default `"core"`); allow `local_module.pm*_fuel.sii` 43-locale sync, ProMods UK `regions[]` preservation, and `.sii` country fragments in non-core profiles while keeping Core invariants untouched |
| `04-02` | `src/ets2v2/merge/promods_builder.py` | service / orchestrator | file-I/O + batch | `src/ets2v2/package/builder.py` & `publish/release.py` | exact | Version-agnostic ProMods `EU+ME+MA+TGS` discovery, `--require-all-packs`, tracked-repo `--out-dir` refusal (`D-08`), offline snapshot load/fallback (`D-04`), dual target emission, and post-stage `validate_workshop_package(..., profile="promods")` & `validate_local_zip(..., profile="promods")` |
| `04-02` | `tests/test_promods_builder.py` & `tests/test_merge_policy.py` | test / unit + integration | integration | `tests/test_package_builder.py`, `test_validate_workshop.py`, `test_baseline_contracts.py` | exact | Synthetic clean-room ProMods ZIP fixtures (`uk.sui` with `scotland`/`wales`, `pm_fuel`/`pm_me_fuel`/`pm_tgs_fuel`, `--require-all-packs`, tracked `--out-dir` rejection) + `@pytest.mark.local_promods` auto-skipping local suite |
| `04-03` | `src/ets2v2/merge/load_order.py` | service / parser | file-I/O | `src/ets2v2/baseline/extractor.py` & `vfs/stack.py` | partial | Cross-platform path resolvers (`resolve_mod_dir`, `resolve_workshop_dir`), `--modlist`/`--game-log`/`--profile` (`ScsC` guard + `mod_workshop_package.<hex>` -> decimal) parsers, `D-10` self-exclusion, `D-11` protected archive diagnostics + smart `--unpacked-defs` mounting |
| `04-03` | `src/ets2v2/merge/scanner.py` | service / scanner | file-I/O + transform | `src/ets2v2/baseline/extractor.py` & `vfs/stack.py` | exact | Enumerate `def/country*.sii` over `VfsStack`, skip `empty_stub_paths()` (`SiiNunit {}`), follow `@include` graphs resolving `.sui` & `.sii` fragments & `base/` mounts, record winning layer provenance + optional `speed_limits.sii` |
| `04-03` | `tests/test_merge_load_order.py` & `tests/test_merge_scanner.py` | test / unit + integration | integration | `tests/test_vfs_stack.py` & `test_sii_country.py` | exact | Synthetic `game.log.txt`, plaintext & `ScsC`-encrypted `profile.sii`, Workshop `227300` hex-to-decimal, `D-10` self-exclusion, `AEM!`/encrypted ZIP/`3nK` + smart `--unpacked-defs`, `base/` (`EAA`), `.sii` fragments (`SEA`/`RoC`/`PJ`), and empty `SiiNunit {}` stubs (`UMCF`/`SemEuropa`) |
| `04-04` | `src/ets2v2/merge/hardcoded_totems.py` | service / compiler | transform | `src/ets2v2/package/totems.py` & `sii/sign_board.py` | partial | Opt-in `--patch-hardcoded-totems` scanner/rewriter for JRR/7RM single-text numeric sign boards -> `@@fp_*_ets2v2@@` backed by 43-locale `local_module.ets2v2_fuel.sii`, leaving ambiguous signs untouched |
| `04-04` | `src/ets2v2/merge/compose.py` | service / orchestrator | file-I/O + batch | `src/ets2v2/publish/release.py` & `package/builder.py` | exact | Full offline `compose_local()` pipeline: snapshot load/verify or repo fallback -> `build_combo_vfs_stack()` -> `scan_active_countries()` -> `resolve_country()` -> `FieldOwnershipPolicy` -> self-contained totems / `--no-totems` / `--patch-hardcoded-totems` -> pre-write `validate_local_zip(..., profile="combo")` -> `zz_ETS2V2_ComboPatch_{Summer\|Winter}.scs` + `--dry-run` / `--report-json` |
| `04-04` | `src/ets2v2/cli.py` | CLI entrypoint | request-response | `src/ets2v2/cli.py` (in-place) | exact | Wire `ets2v2 registry snapshot-verify`, `ets2v2 package promods`, `ets2v2 compose-local`, and `--profile` on `ets2v2 validate {workshop,local}` using `cast(...)` & `--json` patterns |
| `04-04` | `tests/test_compose_local.py` | test / integration | integration | `tests/test_publish_release.py` & `test_package_builder.py` | exact | Full synthetic multi-map combo integration (`EAA` 80t + `base/` + multi-TZ, `TST` 27-TZ + 48t, `UMCF` 5-TZ + empty stub, `Beyond` encrypted ZIP + `gmc.beyond.fix`, `JRR`/`7RM` default vs `--patch-hardcoded-totems`, `--no-totems`, `--strict-protected`, `--dry-run`, `--json`, idempotent weekly self-exclusion) + `@pytest.mark.local_promods` |

---

## 3. Concrete Pattern Assignments (Code to Copy From)

### Pattern A — `CountryMappingEntry.country_id` Relaxation, `CountryAliasRegistry` & Partitioned Registry Validation (`04-01`)

**Analog:** `src/ets2v2/registry/models.py:102-131` & `src/ets2v2/registry/loader.py:365-443`

**In `src/ets2v2/registry/models.py`:**
```python
class CountryMappingEntry(BaseModel):
    """Canonical mapping entry between an ETS2 country slug and ISO-3166 alpha-2 code."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ets2_slug: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    iso3: str = Field(pattern=r"^[a-z]{3}$")
    country_id: int | None = Field(default=None, ge=1)
    name_english: str = Field(min_length=1)
    vanilla_1_62: bool

    @model_validator(mode="after")
    def _validate_vanilla_country_id(self) -> CountryMappingEntry:
        if self.vanilla_1_62 and self.country_id is None:
            raise ValueError(
                f"vanilla_1_62=True entry {self.ets2_slug!r} ({self.iso2}) requires non-null country_id"
            )
        return self


class CountryAliasRegistry(BaseModel):
    """Top-level ``data/mappings/country_aliases.json`` schema mapping map slugs -> ISO-2 (D-02)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    aliases: dict[str, str] = Field(default_factory=dict)

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, value: dict[str, str]) -> dict[str, str]:
        slug_re = re.compile(r"^[a-z0-9_]{1,64}$")
        iso2_re = re.compile(r"^[A-Z]{2}$")
        for slug, iso2 in value.items():
            if slug_re.fullmatch(slug) is None:
                raise ValueError(f"Invalid alias map slug {slug!r}")
            if iso2_re.fullmatch(iso2) is None:
                raise ValueError(f"Invalid ISO-2 target {iso2!r} for alias {slug!r}")
        return value
```

**In `src/ets2v2/registry/loader.py` (replacing lines 384-391 and 423-442):**
```python
        # Unique non-null country_ids only (non-vanilla entries may set country_id=None)
        if entry.country_id is not None:
            if entry.country_id in seen_ids:
                issues.append(
                    f"Duplicate country_id {entry.country_id} in {mappings_file.name} "
                    f"({seen_ids[entry.country_id]} and {entry.ets2_slug})"
                )
            else:
                seen_ids[entry.country_id] = entry.ets2_slug
...
    vanilla_by_slug = {e.ets2_slug: e for e in mappings.countries if e.vanilla_1_62}
    non_vanilla_by_slug = {e.ets2_slug: e for e in mappings.countries if not e.vanilla_1_62}

    for slug in sorted(set(bl_countries_by_slug) - set(vanilla_by_slug)):
        issues.append(
            f"Baseline country slug {slug!r} missing from {mappings_file.name} (vanilla_1_62=true)"
        )
    for slug in sorted(set(vanilla_by_slug) - set(bl_countries_by_slug)):
        issues.append(
            f"Non-baseline country slug {slug!r} marked vanilla_1_62=true in {mappings_file.name}"
        )
    for slug in sorted(set(non_vanilla_by_slug) & set(bl_countries_by_slug)):
        issues.append(
            f"Baseline country slug {slug!r} must have vanilla_1_62=true in {mappings_file.name}"
        )

    for slug in sorted(set(bl_countries_by_slug) & set(vanilla_by_slug)):
        entry = vanilla_by_slug[slug]
        record = laws_by_iso2.get(entry.iso2)
        if record is None:
            continue
        _validate_country_against_baseline(
            entry=entry,
            record=record,
            bl_country=bl_countries_by_slug[slug],
            bl_speed=bl_speeds_by_slug.get(slug),
            issues=issues,
        )
```

---

### Pattern B — Locked v1 `RealismSnapshot` Non-Vanilla Derivation, `SHA256SUMS.txt` & Air-Gapped Verifier (`04-01`, `04-04`)

**Analog:** `src/ets2v2/registry/snapshot.py:74-173` & `src/ets2v2/publish/ledger.py:155-165`

**Non-vanilla handling inside `build_realism_snapshot()` (`D-02`, preserving locked `schema_version: Literal[1] = 1` & `extra="forbid"`):**
```python
    mapping_by_iso2 = {entry.iso2: entry for entry in registry.mappings.countries}
    for iso2 in sorted(registry.laws_by_iso2):
        law = registry.laws_by_iso2[iso2]
        mapping_entry = mapping_by_iso2[iso2]
        if vanilla_only and not mapping_entry.vanilla_1_62:
            continue
        bl_country = baseline_by_slug.get(law.ets2_slug)
        if mapping_entry.vanilla_1_62:
            if bl_country is None:
                raise ValueError(f"Missing baseline country entry for {iso2} ({law.ets2_slug!r})")
            imperial_units = bl_country.imperial_units is True
            if imperial_units != (law.speed_unit == "mph"):
                raise ValueError(f"imperial_units parity mismatch for {iso2} ({law.ets2_slug!r})")
        else:
            imperial_units = law.speed_unit == "mph"
```
> **Note (`D-02`):** `RealismSnapshot`, `RealismSnapshotCountry`, and `RealismSnapshotFuel` MUST NOT add or rename any fields. When `prices_lock is None`, pass `vanilla_only=True` (or default `vanilla_only = prices_lock is None`? Better: explicit `vanilla_only: bool = False`, and fail with a clear message if a `vanilla_1_62=False` entry has neither `prices_lock` nor `bl_country`, while Phase 2 baseline-only unit tests either pass `prices_lock` or `vanilla_only=True` — see Regression Trap 2!).

**Deterministic `SHA256SUMS.txt` + Air-Gapped Verifier (`src/ets2v2/registry/snapshot.py`):**
```python
_SHA256SUM_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^([0-9a-f]{64})  ([^\r\n/\\]+)$")


class SnapshotVerificationResult(BaseModel):
    """Structured offline verification report for a v1 realism snapshot (D-03, D-04)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ok: bool
    snapshot_path: str
    schema_version: int | None = None
    edition: Season | None = None
    anchor_date: str | None = None
    country_count: int = 0
    sha256: str | None = None
    checksum_verified: bool = False
    issues: list[str] = Field(default_factory=list)


def load_realism_snapshot(path: Path) -> RealismSnapshot:
    """Strictly load and validate a UTF-8 no-BOM LF schema_version=1 realism snapshot."""
    if not path.is_file():
        raise FileNotFoundError(f"Realism snapshot does not exist: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"Realism snapshot must not contain a UTF-8 BOM: {path}")
    if b"\r" in raw:
        raise ValueError(f"Realism snapshot must use LF line endings only: {path}")
    return RealismSnapshot.model_validate_json(raw.decode("utf-8"))


def render_sha256sums(paths: Sequence[Path]) -> bytes:
    """Render GNU coreutils ``SHA256SUMS.txt`` (``<sha256>  <filename>\\n``) sorted by filename."""
    entries: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Cannot checksum missing file: {path}")
        name = path.name
        if name in seen_names:
            raise ValueError(f"Duplicate filename in SHA256SUMS manifest: {name!r}")
        seen_names.add(name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append((name, digest))
    entries.sort(key=lambda item: item[0])
    text = "".join(f"{digest}  {name}\n" for name, digest in entries)
    return text.encode("utf-8")
```

---

### Pattern C — `FieldOwnershipPolicy` Merge Engine (`04-02`, `04-04`)

**Analog:** `src/ets2v2/sii/country.py:74-85, 264-292` & `src/ets2v2/sii/speed_limits.py:250-294`

**1. `max_of_map_and_real` axle ladder (`D-14`):**
```python
def merge_axle_mass_limits(
    map_axles: Sequence[int],
    real_axles: Sequence[int],
) -> list[int]:
    """Merge axle mass limits per D-14: element-wise max with carry-forward + monotonic clamp."""
    if not map_axles:
        return list(real_axles)
    if not real_axles:
        return list(map_axles)
    target_len = max(len(map_axles), len(real_axles))
    merged: list[int] = []
    running_max = 0
    for idx in range(target_len):
        map_val = map_axles[min(idx, len(map_axles) - 1)]
        real_val = real_axles[min(idx, len(real_axles) - 1)]
        running_max = max(running_max, map_val, real_val)
        merged.append(running_max)
    return merged
```
- **Verified edge cases (`D-14`):**
  - EAA Brazil `[18000, ..., 80000]` vs shorter real array -> preserves `80000` (never downgraded/truncated).
  - Iceland map `[18000, 26000, 36000, 40000]` vs real `[18000, 29000, 38000, 46000, 60000]` -> upgrades cleanly to 5-element `[18000, 29000, 38000, 46000, 60000]`.
  - RusMap/TST `48t` & Finland `105t` -> preserved verbatim.

**2. `patch_if_single_tz` guard (`D-15`):**
```python
def should_patch_timezone(map_country: CountryDataModel) -> tuple[bool, str]:
    """Return ``(True, 'patched')`` only on single-TZ definitions omitting secondary_time_zone*."""
    if map_country.secondary_time_zone or map_country.secondary_time_zone_area:
        return False, "skipped_multi_tz"
    if map_country.time_zone is None:
        return False, "skipped_missing_tz"
    return True, "patched"
```
- **Verified edge cases (`D-15`):**
  - TST `27`-TZ Russia, UMCF `5`-TZ Kazakhstan, EAA Brazil, Vanilla Russia (Kaliningrad) -> all define `secondary_time_zone` / `secondary_time_zone_area` -> `time_zone` and `time_zone_name` remain untouched!
  - Single-TZ countries (`DE`, `FR`, `GB`, `IS`, `JO`, `SY`, etc.) -> `time_zone` and `time_zone_name` receive seasonal DST values via `patch_country_data()`.

**3. Surgical `country_data` merge (`D-14`, `D-15`):**
```python
def apply_country_policy(
    raw_source: bytes,
    map_country: CountryDataModel,
    snapshot_country: RealismSnapshotCountry,
) -> tuple[bytes, CountryPolicyAction]:
    """Surgically patch realism-owned fields via ``patch_country_data()``, preserving map geometry."""
    patch_tz, tz_reason = should_patch_timezone(map_country)
    merged_axles = merge_axle_mass_limits(
        map_country.mass_limit_per_axle_count,
        snapshot_country.mass_limit_per_axle_count,
    )
    patch = CountryDataPatch(
        fuel_price=snapshot_country.fuel.eur_per_liter,
        lights_mandatory=snapshot_country.lights_mandatory,
        driving_tired_offence=snapshot_country.driving_tired_offence,
        time_zone=snapshot_country.time_zone if patch_tz else None,
        time_zone_name=snapshot_country.time_zone_name if patch_tz else None,
        mass_limit_per_axle_count=merged_axles,
    )
    rendered = patch_country_data(raw_source, patch)
    out_bytes = serialize_sii_text(rendered)
    # Require SiiNunit wrapper strictly matching source fragment kind (.sii vs headerless .sui)
    ...
```
- **Why this is structurally immune to clobbering (`D-15`):** `CountryDataPatch` (`src/ets2v2/sii/country.py:74-85`) literally ONLY has the 6 realism-owned fields! It CANNOT mutate `country_id`, `name`, `name_localized`, `country_code`, `iso_country_code`, `pos`, `regions[]`, `region_areas[]`, `secondary_time_zone*`, `leftside_traffic`, `imperial_units`, or `trailer_standalone`!

**4. Custom-lane-preserving `speed_limits.sii` merge + `imperial_units` parity guard (`D-15`):**
```python
def apply_speed_limits_policy(
    raw_source: bytes,
    map_country: CountryDataModel,
    snapshot_country: RealismSnapshotCountry,
) -> tuple[bytes | None, str]:
    """Patch canonical lanes in car/truck/bus while preserving custom lanes & train/tram verbatim."""
    map_is_imperial = map_country.imperial_units is True
    if map_is_imperial != snapshot_country.imperial_units:
        return None, "skipped_imperial_mismatch"

    parsed = parse_speed_limits(raw_source)
    updates: dict[str, list[LaneSpeedRule]] = {}
    for vclass in ("car", "truck", "bus"):
        block = parsed.get_block(vclass)
        if block is None:
            continue
        overrides_by_lane = {
            lane.lane_speed_class: lane for lane in snapshot_country.speed_limits[vclass]
        }
        new_lanes: list[LaneSpeedRule] = []
        for existing_lane in block.lanes:
            override = overrides_by_lane.get(existing_lane.lane_speed_class)
            if override is None:
                # Preserve map-added custom lane classes verbatim in their exact slot!
                new_lanes.append(existing_lane)
            else:
                new_lanes.append(
                    LaneSpeedRule(
                        lane_speed_class=existing_lane.lane_speed_class,
                        limit=override.limit,
                        urban_limit=override.urban_limit,
                        max_limit=override.max_limit if existing_lane.max_limit is not None else None,
                        uncommon=existing_lane.uncommon,
                    )
                )
        updates[vclass] = new_lanes

    if not updates:
        return None, "skipped_no_road_blocks"
    rendered = patch_speed_limits(raw_source, updates)
    return serialize_sii_text(rendered), "patched"
```
> **Crucial SII Engine Insight (`src/ets2v2/sii/speed_limits.py:289-292`):** Because `new_lanes` preserves `existing_lane.lane_speed_class` in exact original order (including any custom lane classes!), `existing_names == target_names` is ALWAYS `True` inside `patch_speed_limits()`, which invokes `_patch_unit_lanes_in_place()` — updating numeric values in-place while leaving comments, custom lanes, and `train`/`tram` units byte-identical!

---

### Pattern D — 3-Tier Country Alias Resolution & Active `VfsStack` Country Graph Scanner (`04-03`)

**Analog:** `src/ets2v2/baseline/extractor.py:137-205` & `src/ets2v2/vfs/stack.py:301-343`

**1. 3-Tier Country Resolution (`src/ets2v2/merge/aliases.py`, `D-13`):**
```python
MatchTier = Literal["alias", "iso3", "iso2", "slug", "unmatched"]


def resolve_country_in_snapshot(
    slug: str,
    country_data: CountryDataModel,
    snapshot: RealismSnapshot,
    aliases: Mapping[str, str],
) -> tuple[RealismSnapshotCountry | None, MatchTier]:
    """Resolve an active map country against ``snapshot`` in strict D-13 3-tier order."""
    norm_slug = slug.strip().lower()
    # Tier 1: exact slug override in bundled + optional --aliases registry
    alias_iso2 = aliases.get(norm_slug)
    if alias_iso2 is not None and alias_iso2 in snapshot.countries:
        return snapshot.countries[alias_iso2], "alias"

    # Tier 2: exact iso_country_code (ISO-3) or country_code (ISO-2)
    iso3 = country_data.iso_country_code.strip().lower()
    if iso3:
        by_iso3 = {c.iso3.lower(): c for c in snapshot.countries.values()}
        if iso3 in by_iso3:
            return by_iso3[iso3], "iso3"

    cc = country_data.country_code.strip().upper()
    if cc and cc in snapshot.countries:
        return snapshot.countries[cc], "iso2"

    # Tier 3: canonical ets2_slug match
    by_slug = {c.ets2_slug.lower(): c for c in snapshot.countries.values()}
    if norm_slug in by_slug:
        return by_slug[norm_slug], "slug"

    return None, "unmatched"
```
*(Pre-build `by_iso3` and `by_slug` index dicts once per `CountryResolver` instance rather than inside the loop.)*

**2. Active `def/country*.sii` `@include` Graph Scanner (`src/ets2v2/merge/scanner.py`, `MAP-03`):**
- Enumerate all canonical paths matching `^def/country(?:\.[^/]+)?\.sii$` via `stack.list_paths("def")`.
- For each registration file:
  - Call `entry = stack.resolve(reg_path)`.
  - If `entry is None or entry.is_empty_stub` (`VfsStack` already implements `is_empty_sii_stub()` at `src/ets2v2/vfs/stack.py:86-98`!): record as suppressed stub (`UMCF`, `gmc.beyond.fix`, `SemEuropa`) and skip!
  - Read bytes (catching `ProtectedPayloadError` / `UnsupportedCompressionError` -> record diagnostic without crashing!) and extract `@include` paths via `parse_country_includes(raw)` (`src/ets2v2/sii/country.py:129-145`).
  - Resolve each relative include path against the registration file's parent directory (`def/` -> `def/country/<slug>.sui` OR `def/country/<slug>.sii`, handling both `.sui` and `.sii` fragments cleanly as in `SEA`, `RoC`, `Project Japan`, plus `base/` prefixes already flattened automatically by `VfsStack.classify_mount_path()` at `src/ets2v2/vfs/stack.py:100-122`!).
  - Follow nested `@include`s with a cycle-guard `visited: set[str]` if a country file wraps another fragment; check `frag_entry.is_empty_stub` on each included target as well.
  - Parse `CountryDataModel` via `parse_country_data(frag_bytes)` and check `def/country/<slug>/speed_limits.sii` via `stack.resolve(...)` (skipping if absent or empty stub).
  - Deduplicate by canonical fragment path / `unit_name`, preserving deterministic sorted output and exact `winning_layer = frag_entry.layer_name`.

---

### Pattern E — Multi-Source Load-Order Resolution, `D-10` Self-Exclusion & `D-11` Protected Archive + `--unpacked-defs` Handling (`04-03`, `04-04`)

**Analog:** `src/ets2v2/baseline/extractor.py:65-72`, `src/ets2v2/vfs/stack.py:184-203`, `src/ets2v2/vfs/zip_archive.py:127-140`, `src/ets2v2/vfs/hashfs.py:707-796`

**1. Load-Order Precedence Normalization (`D-09`):**
- Always normalize parsed entries into **lowest-to-highest VFS mount priority** (matching `VfsStack.from_paths()` at `src/ets2v2/vfs/stack.py:192`: later layers override earlier layers!):
  - **Base layer (priority `0`):** `--game-dir/def.scs` (if `--game-dir` supplied and exists; otherwise clean-room baseline fallback using `data/baselines/ets2_1.62_def/` synthesized in-memory or `BaselineCountry` fallback).
  - **`--profile <profile.sii>`:** Check first 4 bytes for `b"ScsC"` (encrypted save/profile) -> **NEVER decrypt**; raise `ValueError("profile.sii is ScsC-encrypted; pass --game-log <game.log.txt> or enable plaintext saves via 'g_save_format 2' in ETS2 config.cfg")` (`D-09`). In plaintext `profile.sii`, `active_mods[0]` is lowest priority and `active_mods[N-1]` is highest priority; entries have format `"<pkg_stem>|<display_name>"`; Workshop entries use `"mod_workshop_package.<hex_id>"` -> `str(int(hex_id, 16))` under `--workshop-dir` (`.../steamapps/workshop/content/227300/<decimal_id>/`).
  - **`--game-log <game.log.txt>`:** Parse `[mod_package_manager]` / `[zipfs]` / `[hashfs]` mount lines in exact ETS2 engine mount order (verified against real `1.62.3.3s` `game.log.txt` during Phase 4 research), mapping local `mod/` archives and Steam Workshop `227300/<id>` directories/archives cleanly.
  - **`--modlist <file>`:** Strip blank lines and `#` comments; support explicit `--modlist-order {bottom-up,top-down}` (default `bottom-up` matching `VfsStack`, or `top-down` matching Mod Manager visual order so users can paste Mod Manager lists directly!).

**2. `D-10` Automatic Self-Exclusion (`is_ets2v2_self_package()`):**
```python
ETS2V2_MANIFEST_MARKER: Final[str] = "# ets2v2:managed-package"
_SELF_PACKAGE_STEM_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:zz_ets2v2_combopatch_|ets2v2_core_|ets2v2_promods_)",
    re.IGNORECASE,
)


def is_ets2v2_self_package(archive_path: Path, archive: VfsArchive | None = None) -> tuple[bool, str | None]:
    """Detect previously generated ETS2V2 packages by filename pattern or manifest.sii marker (D-10)."""
    if _SELF_PACKAGE_STEM_RE.match(archive_path.stem) is not None:
        return True, f"filename:{archive_path.name}"
    if archive is not None and archive.exists("manifest.sii"):
        try:
            raw = archive.read_bytes("manifest.sii")
        except (ProtectedPayloadError, UnsupportedCompressionError, OSError, ValueError):
            return False, None
        if ETS2V2_MANIFEST_MARKER.encode("utf-8") in raw:
            return True, "manifest_marker"
    return False, None
```

**3. `D-11` Protected Archive Diagnostics & Smart Repeatable `--unpacked-defs`:**
- When `open_archive(path)` returns a `ProtectedArchiveStub` (`aem_protected`, `corrupt_archive`, `unknown_magic`) OR a `ZipArchive` whose `diagnostics` include `encrypted_zip` / `three_nk_obfuscated`:
  - For `ZipArchive` with `encrypted_zip`, inspect `archive.list_paths(["def/country", "def/sign/board"])` — remember `ZipArchive._load_central_directory()` (`src/ets2v2/vfs/zip_archive.py:98-140`) ALREADY indexes all unencrypted central-directory filenames even when payloads are password-encrypted! Surface those visible `def/country*` / `def/sign/board*` paths in `ProtectedArchiveDiagnostic.visible_relevant_paths` along with an actionable `--unpacked-defs` hint.
- For each repeatable `--unpacked-defs <dir>`:
  - **Mode 1 (In-place substitution):** Check if `<dir>/<protected_stem>` (case-insensitive match on archive stem) exists as a subdirectory -> mount `DirectoryArchive(sub_dir)` **at the protected archive's exact load-order priority** and mark the protected archive as `substituted_by=str(sub_dir)`!
  - **Mode 2 (Raw unpacked tree):** If `<dir>` directly contains `def/` or `locale/` (or `base/def/`), mount `DirectoryArchive(<dir>)` as an explicit high-priority override layer on top of the stack.
- Default policy: warn clearly in report/stderr and continue (exit `0`); when `--strict-protected` is set and any un-substituted protected archive remains, fail non-zero (`1`) without writing `.scs` (`D-11`).

---

### Pattern F — Dynamic ProMods `local_module.pm*_fuel.sii` Updater, Opt-In `--patch-hardcoded-totems` & Tracked-Repo `--out-dir` Guard (`04-02`, `04-04`)

**Analog:** `src/ets2v2/package/totems.py:175-266` & `src/ets2v2/sii/localization.py:45-57` & `src/ets2v2/cli.py:130-142`

**1. Tracked-repo `--out-dir` refusal (`D-08`, zero ProMods files in Git):**
```python
_FORBIDDEN_REPO_SUBDIRS: Final[tuple[str, ...]] = ("data", "src", "tests", "state", ".github", ".git")


def assert_out_dir_not_tracked(out_dir: Path, *, repo_root: Path | None = None) -> None:
    """Refuse --out-dir inside tracked repository directories so ProMods data never enters Git (D-08)."""
    root = (repo_root if repo_root is not None else Path.cwd()).resolve()
    resolved_out = out_dir.resolve()
    for subdir in _FORBIDDEN_REPO_SUBDIRS:
        guarded = (root / subdir).resolve()
        if resolved_out == guarded or resolved_out.is_relative_to(guarded):
            raise ValueError(
                f"Refusing to write ProMods/local output inside tracked directory {guarded}: {out_dir}"
            )
```

**2. Dynamic `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` 43-locale synthesis (`src/ets2v2/merge/promods_fuel.py`, `D-08`):**
- Probe installed ProMods VFS stack for each module in `("local_module.pm_fuel.sii", "local_module.pm_me_fuel.sii", "local_module.pm_tgs_fuel.sii")` across `locale/en_gb/` (or first available locale in `locales.active_locales`).
- Read the exact `localization_db` unit name (e.g. `.pm_fuel` / `.pm_me_fuel` / `.pm_tgs_fuel`, verifying `validate_unit_name_segments()`) and ordered `LocalizationEntry(key, val)` list dynamically via `parse_localization_db(raw)`.
- For every entry:
  - Parse country/grade token from `entry.key` using a clean adapter reusing `GRADE_SUFFIX_TO_CANONICAL` (`src/ets2v2/normalize/totem_catalog.py:33-55`) and `CountryAliasRegistry` / snapshot ISO-2 map.
  - When matched to `(snapshot_country, canonical_grade)` with a valid local price -> format natively via `format_national_pump_price(iso2, price, variant=...)` (`src/ets2v2/normalize/totem_format.py:228-283`).
  - When unrecognized / non-price key -> **preserve `(entry.key, entry.val)` verbatim** (`D-08`) so future ProMods releases never break totems!
- Emit the rendered `localization_db` cleanly across **all 43 active ETS2 `1.62` locales** from `LocalesBaseline.active_locales` (`fr_qc` excluded, `fr_ca` synced), validating every emitted file with `validate_sii_hygiene(raw, require_siinunit=True)`.

**3. Opt-in `--patch-hardcoded-totems` (`src/ets2v2/merge/hardcoded_totems.py`, `D-16`):**
- Default behavior (`patch_hardcoded_totems=False`): do NOT touch non-Vanilla community map boards (JRR/7RM).
- When `patch_hardcoded_totems=True`:
  - Scan `def/sign/board/*.sii` in `VfsStack` excluding Vanilla `FuelBoardsBaseline` board names (already handled by Option 4b) and excluding `excluded_fuel_keyword_boards` / `gas_empty`.
  - Parse via `parse_sign_board(raw)` and inspect single-text boards (`is_single_text_fuel_candidate` or single numeric `sign_template_text` slot whose `text` matches a pure numeric price literal like `1.85` / `14500` rather than an `@@...@@` token) whose board filename & resolved map context unambiguously map to `(iso2, grade)` in `snapshot`.
  - Rewrite **surgically** via `SiiDocument` (`doc.update_attribute_value(text_attr, format_sii_string(f"@@{token_key}@@"))`) preserving all board geometry/attributes verbatim, register `token_key -> formatted_price` into `local_module.ets2v2_fuel.sii` across all 43 active locales, and leave every ambiguous/non-matching sign untouched (recording every patched and skipped board in `ComposeReport`)!

---

### Pattern G — Clean-Room ProMods/Combo Icons, Self-Exclusion `manifest.sii` Comment & Profile-Parameterized Offline Validator (`04-02`, `04-04`)

**Analog:** `src/ets2v2/package/icons.py:95-195`, `src/ets2v2/package/metadata.py:42-127`, `src/ets2v2/validate/workshop.py:905-1130`, `src/ets2v2/validate/invariants.py:346-791`

**1. `manifest.sii` D-10 self-exclusion marker (zero `WARN 00002`):**
```text
SiiNunit
{
# ets2v2:managed-package kind=promods
mod_package : .package_name
{
	package_version: "1.62-2026.47"
	author: "ETS2 World Realism"
	category[]: "other"
	category[]: "ai_traffic"
	icon: "mod_icon.jpg"
	description_file: "description.txt"
	mp_mod_optional: true
}
}
```
- **Verified against `src/ets2v2/validate/workshop.py:591-630`:** `#` line comments are stripped cleanly by `SiiDocument.parse()` and NEVER added to `mod_unit.attributes`, so `ALLOWED_MANIFEST_ATTRS` / `WARN 00002` passes with **0 warnings**!

**2. Profile-parameterized Offline Validator (`src/ets2v2/validate/{models,workshop,invariants}.py`):**
```python
# src/ets2v2/validate/models.py
PackageProfile = Literal["core", "promods", "combo"]

# src/ets2v2/validate/workshop.py
_PROMODS_FUEL_LOCALE_RE: Final[re.Pattern[str]] = re.compile(
    r"^locale/([^/]+)/local_module\.(pm_fuel|pm_me_fuel|pm_tgs_fuel)\.sii$"
)
_COUNTRY_SII_FRAGMENT_RE: Final[re.Pattern[str]] = re.compile(r"^def/country/([a-z0-9_]+)\.sii$")


def validate_workshop_package(
    workshop_dir: Path,
    *,
    baseline_dir: Path | None = None,
    profile: PackageProfile = "core",
) -> ValidationReport: ...


def validate_local_zip(
    zip_path: Path,
    *,
    baseline_dir: Path | None = None,
    profile: PackageProfile = "core",
) -> ValidationReport: ...
```
- `profile="core"` (default): 100% identical to Phase 2/3 behavior (exact 36 Vanilla slugs, exact Vanilla `regions[]`, only `local_module.ets2v2_fuel.sii` allowed).
- `profile="promods"`: accepts `local_module.{ets2v2_fuel,pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii`, verifies 43-locale sync (`fr_qc` excluded, `fr_ca` included) on every emitted `pm*_fuel` module, requires superset of the 36 Vanilla countries (`>= 36`), verifies **ProMods UK `regions[]` preservation** (`{"scotland", "wales"} <= set(country_models["uk"].regions)`), Armenia `leftside_traffic is False`, Iceland 60t/80 km/h, Zero-DDS, and `00001`–`00010` + `WARN 00001`/`00002`!
- `profile="combo"`: accepts `def/country/<slug>.sui` AND `def/country/<slug>.sii` fragments, allows subset/superset of countries & optional `speed_limits.sii`, enforces Zero-DDS, no `def/country*.sii` registration file, `manifest.sii` + `276x162` icon + UTF-8/LF SII hygiene, zero duplicate `country_id`/`unit_name`, valid `@@tz_*@@` whitelist, monotonic axles, and 43-locale sync on any emitted `local_module.{ets2v2_fuel,pm*_fuel}.sii`!

---

### Pattern H — Rolling `snapshots-latest` GitHub Release Step & `@pytest.mark.local_promods` Pattern (`04-01`, `04-02`, `04-04`)

**Analog:** `.github/workflows/phase-a-release.yml:149-211` & `tests/test_baseline_contracts.py:48-56, 264-273`

**1. Rolling `snapshots-latest` step in `.github/workflows/phase-a-release.yml` (`D-03`, zero `${{` inside `run:`):**
```yaml
      - name: Verify v1 realism snapshots and SHA256SUMS manifest
        run: |
          set -euo pipefail
          uv run --offline ets2v2 registry snapshot-verify dist/snapshots/realism-snapshot-summer.json --checksums dist/snapshots/SHA256SUMS.txt
          uv run --offline ets2v2 registry snapshot-verify dist/snapshots/realism-snapshot-winter.json --checksums dist/snapshots/SHA256SUMS.txt

      - name: Publish rolling public snapshots-latest GitHub Release
        if: (steps.release.outputs.any_changed == 'true' || env.FORCE_RUN == 'true' || steps.release.outputs.force_run == 'true') && (github.event_name == 'schedule' || github.ref == 'refs/heads/master')
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          TAG="snapshots-latest"
          TITLE="Latest Realism Snapshots (schema_version=1)"
          NOTES="Automated rolling public release of verified schema_version=1 summer/winter realism snapshots and SHA256SUMS.txt for offline ProMods Companion Builder and ets2v2 compose-local."
          ASSETS=(
            dist/snapshots/realism-snapshot-summer.json
            dist/snapshots/realism-snapshot-winter.json
            dist/snapshots/SHA256SUMS.txt
          )
          if gh release view "$TAG" >/dev/null 2>&1; then
            gh release upload "$TAG" "${ASSETS[@]}" --clobber
            gh release edit "$TAG" --title "$TITLE" --notes "$NOTES"
          else
            gh release create "$TAG" "${ASSETS[@]}" --title "$TITLE" --notes "$NOTES"
          fi
```

**2. Local ProMods / Map-Combo Test Pattern (`tests/test_promods_builder.py`, `tests/test_compose_local.py`, `D-08`):**
```python
def _has_local_promods() -> bool:
    mod_dir = resolve_mod_dir()
    if not mod_dir.is_dir():
        return False
    return discover_promods_packs(mod_dir).eu_def is not None


@pytest.mark.local_promods
@pytest.mark.skipif(not _has_local_promods(), reason="Local ProMods archives not present")
def test_local_promods_companion_build_and_validate(tmp_path: pathlib.Path) -> None:
    ...
```
- Runs 100% offline in CI using clean-room synthetic ProMods & combo ZIP fixtures (zero third-party files in Git!), while automatically exercising real local `D:\ETS2Data\Euro Truck Simulator 2\mod` archives when present on developer machines!

---

## 4. Exact Reusable Phase 1–3 APIs & Signatures

Phase 4 modules **MUST reuse** these verified existing symbols directly rather than duplicating VFS, SII, formatting, packaging, or validation logic.

### `ets2v2.vfs` (`src/ets2v2/vfs/{stack,hashfs,zip_archive,dir_archive,types}.py`)

| Symbol | Location | Exact Signature / Contract | Phase 4 Consumers |
|---|---|---|---|
| `VfsStack` | `vfs/stack.py:161` | `.from_paths()`, `.mount(archive, name=..., priority=...)`, `.resolve(path) -> EffectiveVfsEntry \| None`, `.list_paths(prefix="")`, `.empty_stub_paths(prefix="")`, `.read_bytes(path)`, `.diagnostics()` | `merge.load_order`, `merge.scanner`, `merge.promods_builder`, `merge.compose` |
| `is_empty_sii_stub` | `vfs/stack.py:86` | `(data: bytes) -> bool` (handles comments + `SiiNunit {}` / `{}` stubs) | `merge.scanner` |
| `classify_mount_path` | `vfs/stack.py:100` | `(raw_path, *, enabled_dlcs=None) -> tuple[str, str]` (flattens `base/`, scopes `dlc_<id>/`) | `merge.scanner`, `merge.load_order` |
| `open_archive` | `vfs/hashfs.py:707` | `(path: Path, *, seeded_prefixes=DEFAULT_SEEDED_PREFIXES) -> VfsArchive` (auto-dispatches dir/ZIP/HashFS v1-v2/`ProtectedArchiveStub`) | `merge.load_order`, `merge.promods_builder` |
| `ProtectedArchiveStub` | `vfs/hashfs.py:648` | Safe stub returned for `AEM!`, corrupt, or unknown magic bytes (zero decryption) | `merge.load_order` (`D-11`) |
| `ZipArchive` | `vfs/zip_archive.py:52` | Indexes encrypted ZIP central-directory filenames without decrypting payloads | `merge.load_order` (`D-11`), `validate.workshop` |
| `DirectoryArchive` | `vfs/dir_archive.py:26` | Symlink/junction-contained unpacked directory reader | `merge.load_order` (`--unpacked-defs`), `validate.workshop` |
| `ArchiveDiagnostic`, `ProtectedPayloadError`, `UnsupportedCompressionError`, `normalize_vfs_path` | `vfs/types.py:25-83` | Structured diagnostics, protected exceptions, POSIX path canonicalizer | `merge.*`, `validate.*` |

### `ets2v2.sii` (`src/ets2v2/sii/{document,country,speed_limits,sign_board,localization,hygiene}.py`)

| Symbol | Location | Exact Signature / Contract | Phase 4 Consumers |
|---|---|---|---|
| `SiiDocument` | `sii/document.py:29` | `.parse()`, `.find_units()`, `.get_unit()`, `.update_attribute_value()`, `.replace_span()`, `.to_bytes()` | `merge.hardcoded_totems`, `merge.promods_fuel`, `merge.load_order` (plaintext `profile.sii`) |
| `parse_country_includes` | `sii/country.py:129` | `(source: str \| bytes) -> list[str]` (rejects col!=0 `@include`, backslashes, `..`) | `merge.scanner` |
| `parse_country_data` | `sii/country.py:148` | `(source: str \| bytes) -> CountryDataModel` | `merge.scanner`, `merge.policy`, `validate.workshop` |
| `patch_country_data` | `sii/country.py:264` | `(source: str \| bytes, patch: CountryDataPatch) -> str` (6 realism fields only; preserves comments, regions, `secondary_time_zone*`, geometry) | `merge.policy` |
| `parse_speed_limits` / `patch_speed_limits` | `sii/speed_limits.py:250, 267` | Interleaved lane parser & in-place surgical patcher preserving `train`/`tram` & custom lanes | `merge.policy`, `merge.scanner`, `validate.workshop` |
| `parse_sign_board` | `sii/sign_board.py:149` | `(source: str \| bytes) -> SignBoardTemplate` (`.is_single_text_fuel_candidate`, `.text_slots[0].localization_key`) | `merge.hardcoded_totems`, `validate.workshop` |
| `parse_localization_db` | `sii/localization.py:45` | `(source: str \| bytes) -> list[LocalizationEntry]` | `merge.promods_fuel`, `validate.workshop` |
| `serialize_sii_text` / `validate_sii_hygiene` / `validate_unit_name_segments` | `sii/hygiene.py:61, 71, 235` | UTF-8 no-BOM LF serializer, hygiene gate, 12-char unit segment validator | `merge.policy`, `merge.promods_fuel`, `merge.hardcoded_totems`, `package.metadata` |

### `ets2v2.normalize`, `ets2v2.registry`, `ets2v2.package`, `ets2v2.validate`

| Symbol | Location | Exact Signature / Contract | Phase 4 Consumers |
|---|---|---|---|
| `format_national_pump_price` | `normalize/totem_format.py:228` | `(iso2: str, local_price: float, *, variant="standard") -> str` | `merge.promods_fuel`, `merge.hardcoded_totems` |
| `GRADE_SUFFIX_TO_CANONICAL` | `normalize/totem_catalog.py:33` | Canonical `fp_*` grade suffix adapter (`natural95`->`petrol_95`, `diesel5`->`diesel_plus`, etc.) | `merge.promods_fuel`, `merge.hardcoded_totems` |
| `compile_totem_payloads` / `synthesize_fuel_locale_module_sii` | `package/totems.py:175, 206` | Compiles Vanilla 460 boards + 43 synchronized `local_module.ets2v2_fuel.sii` files | `merge.promods_builder`, `merge.compose` |
| `format_sii_string` | `package/synthesize.py:20` | Escapes `"`, `\r`, `\n`, `\t`; rejects `\` and `\x00` | `merge.promods_fuel`, `merge.hardcoded_totems`, `package.metadata` |
| `write_deterministic_zip` (promoted from `_write_deterministic_zip`) | `package/builder.py:91` | Writes sorted POSIX entries with `1980-01-01` timestamps, `0o100644 << 16`, level 6 deflate, returns SHA-256 | `merge.promods_builder`, `merge.compose` |
| `resolve_game_dir` | `baseline/extractor.py:65` | Explicit arg > `ETS2_GAME_DIR` > default Steam path (pattern analog for `resolve_mod_dir` / `resolve_workshop_dir`) | `merge.load_order`, `merge.promods_builder`, `merge.compose` |
| `validate_workshop_package` / `validate_local_zip` | `validate/workshop.py:1131, 1447` | Offline SCS `00001`–`00010`, `WARN 00001`/`00002`, Zero-DDS, totem & realism invariants (extended via `profile=`) | `merge.promods_builder`, `merge.compose`, `publish.release` |

---

## 5. Key Integration Points, Regression Traps & Typing/CI Guardrails

### Regression Trap Checklist (Existing Code & Tests Impacted by Phase 4)

Every trap below was verified directly against the current tracked repository source and test suite:

1. **TRAP 1 — Friday CI `ets2v2 fetch` Will Wipe Out ProMods Seeded Prices Unless Preserved (`src/ets2v2/fetch/pipeline.py:394, 425, 505-542`):**
   - `run_price_fetch()` currently loops ONLY over `EUROPEAN_TERRITORY_ISO2S` (the 39 Phase 3 territories). Once Plan `04-01` expands `state/prices.lock.json` to ~75+ Vanilla + ProMods territories, any Friday CI `ets2v2 fetch` run would drop all ~36+ ProMods entries unless `pipeline.py` retains & FX-reprices extended territories and `normalize/fx.py` validates extended ProMods FX currencies (`AMD`, `AZN`, `BYN`, `EGP`, `GEL`, `GIP`, `ILS`, `IQD`, `JOD`, `KZT`, `LBP`, `MDL`, `SAR`, `SYP`, `UAH`, etc.) as **optional/fallback-safe** (so existing Phase 3 FX tests mocking only the 16 core non-EUR rates never break!).
   - **Action:** Plan `04-01` MUST update `normalize/currencies.py`, `normalize/fx.py`, `normalize/lockfile.py`, and `fetch/pipeline.py` together and add an offline `MockTransport` regression test proving `run_price_fetch()` preserves all Vanilla + ProMods entries in `state/prices.lock.json`.

2. **TRAP 2 — Phase 2/3 Hardcoded `36`-Country Registry & Snapshot Assertions (`tests/test_registry_contracts.py:139-151`, `tests/test_registry_snapshot.py:82-83, 155, 231`, `tests/test_publish_release.py:146`):**
   - `tests/test_registry_contracts.py:139-151` explicitly asserts `len(law_files) == 36`, `len(bundle.mappings.countries) == 36`, and `for forbidden_non_vanilla in ("AM", "JO", "SY", "SM", "SJ"): assert forbidden_non_vanilla not in bundle.laws_by_iso2`.
   - `tests/test_registry_snapshot.py:82-83, 129-132, 155, 219-231` calls `build_realism_snapshot(...)` and `ets2v2 registry snapshot` **without** `--prices-lock` and asserts `len(summer.countries) == 36` and `"36 countries" in captured.out`.
   - `tests/test_publish_release.py:146` asserts `len(summer_snap.countries) == 36`.
   - **Action:** Plan `04-01` MUST intentionally update these assertions when expanding `data/laws/` & `ets2_countries.json` to Vanilla + ProMods territories:
     - Assert **exact 36** `vanilla_1_62 == True` entries matching `countries.json` AND **exact N** (`>= 70`) total Vanilla + ProMods entries in `test_registry_contracts.py`.
     - Decide cleanly how `build_realism_snapshot(..., prices_lock=None)` behaves: either pass `vanilla_only=True` for legacy `baseline_1.62` snapshot tests and default CLI `ets2v2 registry snapshot --prices-lock` to `Path("state/prices.lock.json")` (when present) so full snapshots include all ~75+ territories, and update `test_registry_snapshot.py` & `test_publish_release.py:146` to assert `len(summer_snap.countries) == len(registry.laws_by_iso2)` (`>= 70`) while Core Workshop packages remain strictly 36 countries (`579` Workshop files / `578` local ZIP entries)!

3. **TRAP 3 — `publish/changelog.py` Table Header & Core Scope (`src/ets2v2/publish/changelog.py:36` & `publish/release.py:285`):**
   - `render_edition_changelog()` renders `## {len(snapshot.countries)}-Country Fuel Price Summary` iterating `snapshot.countries`, and `publish/release.py:285` records `country_count=len(staged.snapshot.countries)` in `state/published.json`.
   - Verify whether Core changelogs (`CHANGELOG_SUMMER.md` / `CHANGELOG_WINTER.md`) should show all snapshot territories (now ~75+) or keep Core's 36-country table clearly labeled; either way, ensure `tests/test_publish_release.py` and `tests/test_publish_ledger.py` stay green and `CHANGELOG_*.md` does not regress any Phase 3 assertion!

4. **TRAP 4 — `generate_all_icons()` Return Dict Contract (`tests/test_package_icons_metadata.py:67-74`):**
   - `test_generate_all_icons_writes_expected_files` asserts `assert set(written.keys()) == {"summer", "winter"}`.
   - **Action:** Keep `generate_all_icons(out_dir)` returning `dict[Season, Path]` (`{"summer", "winter"}`) unchanged! Add separate `generate_promods_icons(out_dir) -> dict[Season, Path]` (writing `promods_summer.jpg` & `promods_winter.jpg`) and `render_combo_icon_bytes(edition) -> bytes`, and have `_handle_package_icons()` in `cli.py` invoke both `generate_all_icons()` and `generate_promods_icons()`.

5. **TRAP 5 — `manifest.sii` Self-Exclusion Marker Must Be a Comment, NEVER a Custom Attribute (`src/ets2v2/validate/workshop.py:624-630`):**
   - Any attribute key outside `ALLOWED_MANIFEST_ATTRS` emits `WARN 00002`, which fails validation hard (`ValidationCollector.build_report` sets `ok=False` on any warning).
   - **Action:** Embed `# ets2v2:managed-package kind=<core|promods|combo>` strictly as an SII `#` comment line inside `manifest.sii` (`D-10`).

6. **TRAP 6 — `validate/workshop.py` Hard-Blocks Non-`ets2v2_fuel` Locales & Extra Countries Under Core Mode (`lines 179-181, 1101-1126`):**
   - `_validate_package_contents()` rejects `locale/<lang>/local_module.pm_fuel.sii` with `00003`, requires exact 36 `EXPECTED_CORE_COUNTRY_SLUGS`, and rejects `def/country/<slug>.sii` fragments.
   - **Action:** Parameterize with `profile: PackageProfile = "core"` so Core validation stays 100% strict while `profile="promods"` validates `pm*_fuel` 43-locale sync + UK `regions[]` preservation + superset countries, and `profile="combo"` validates `.sui`/`.sii` country fragments + optional `speed_limits.sii` + self-contained/opt-in totems.

7. **TRAP 7 — `validate` AST Isolation Tests Exist in TWO Test Files (`tests/test_cli_scaffold.py:270-290` AND `tests/test_validate_workshop.py:88-136`):**
   - Both files independently AST-scan `src/ets2v2/validate/`.
   - **Action:** Update BOTH tests when adding `merge/` — add `"merge"` and `"publish"` to `validate`'s forbidden subpackages in both places, and add `"merge": frozenset({"fetch", "publish"})` (+ `httpx`, `openpyxl`) and `"registry": frozenset({"fetch", "package", "validate", "merge", "publish"})` in `tests/test_cli_scaffold.py`!

8. **TRAP 8 — `tests/test_publish_workflow.py` Zero `${{` Inside `run:` Blocks (`lines 151-157`) & `def _sanitize(` Check (`lines 209-212`):**
   - Every `run:` block in `.github/workflows/phase-a-release.yml` is scanned for `"${{"` and fails hard if found.
   - **Action:** In the new `snapshots-latest` GitHub Release step, pass `GH_TOKEN: ${{ github.token }}` strictly via step-level `env:` — zero `${{` inside `run:`! Keep `ci.yml` strictly read-only (`contents: read`).

9. **TRAP 9 — `tests/test_package_icons_metadata.py` Volatile-Date Regex & `D-16` Attributions (`lines 173-202`):**
   - `description.txt` renderers for Core and ProMods MUST include all `D-16` open-data attributions and MUST NOT embed any `YYYY-MM-DD` date or `1.62-YYYY.WW` version string.

10. **TRAP 10 — `data/` Clean-Room Guard (`tests/test_baseline_contracts.py:83-89`, `tests/test_registry_contracts.py:141-144`):**
    - Zero `.sii` or `.sui` files may ever exist under `data/` (and zero ProMods binaries/extracted assets anywhere in Git per `D-08`). All synthetic ProMods and map-combo test fixtures MUST be constructed in-memory inside `tmp_path` using Python `zipfile.ZipFile` / `pathlib.Path` during test execution!

### `basedpyright` (`strict`) & `ruff` Phase 4 Guardrails

- `pyproject.toml` enforces `basedpyright` `strict` mode (`pythonVersion = "3.12"`, zero `# type: ignore` / `# pyright: ignore`) and `ruff` (`E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`, `line-length = 100`, zero `# noqa`) across **both `src/` and `tests/`**:
  - Always use `ConfigDict(strict=True, frozen=True, extra="forbid")` on all new `merge/models.py` & `registry/models.py` Pydantic models, and deserialize JSON via `Model.model_validate_json(...)`.
  - Always `cast(...)` every `argparse.Namespace` attribute read in `src/ets2v2/cli.py`, and annotate `payload: object = model.model_dump(mode="json")` before `json.dumps(...)`.
  - Zero `print()` or `logging` inside `src/ets2v2/merge/`, `package/`, `registry/`, `validate/`, `normalize/`, `publish/`.
  - Absolute imports only, `zip(..., strict=True)` (`B905`), `raise ... from exc` (`B904`), combined `with (a, b):` (`SIM117`), alphabetically sorted `__all__` (`RUF022`), `Final[...]` on constants.
  - Note on Windows/Linux path normalization: when writing `load_order.py` parsers for `game.log.txt` (which contains Windows backslashes or POSIX slashes depending on host OS), handle both `/` and `\` cleanly via `PureWindowsPath` / `PurePosixPath` or string splitting so unit tests pass identically on Ubuntu CI and Windows!

---

## 6. No Analog Found

Files introducing net-new Phase 4 ETS2 user-environment or third-party-mod parsing capabilities with no direct Phase 1–3 analog (planner should combine `04-CONTEXT.md` decisions + Phase 4 research findings on disk with Patterns A–H typing, VFS, SII, and testing discipline above):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/ets2v2/merge/load_order.py` | service / parser | file-I/O | First parser in the repo for ETS2 `game.log.txt` mount lines (`[mod_package_manager]`/`[zipfs]`/`[hashfs]`), plaintext `profile.sii` `active_mods[]` + `ScsC` header refusal + `mod_workshop_package.<hex>` decimal conversion, and `--unpacked-defs` substitution |
| `src/ets2v2/merge/promods_fuel.py` | service / compiler | transform | First dynamic third-party localization key inspector/updater preserving unrecognized ProMods `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` keys verbatim across all 43 locales |
| `src/ets2v2/merge/hardcoded_totems.py` | service / compiler | transform | First opt-in heuristic rewriter for non-Vanilla community map numeric gas boards (JRR `indo_gas_totem_01a.sii` / 7RM numeric boards) -> `@@fp_*_ets2v2@@` |

---

## Metadata

**Analog search scope:** `src/ets2v2/{vfs,sii,baseline,normalize,registry,fetch,package,validate,publish,cli.py}`, `tests/`, `.github/workflows/`, `pyproject.toml`
**Files scanned:** 31 tracked source, config, workflow, and test files
**Pattern extraction date:** 2026-11-24
