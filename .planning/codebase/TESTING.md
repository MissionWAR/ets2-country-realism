# Testing Patterns

**Analysis Date:** 2026-11-26

## Test Framework

**Runner:**
- `pytest>=9.2,<9.3` (locked `9.2.0` in `uv.lock`) with `pytest-cov>=6,<8` (locked `7.1.0`)
- Config: `pyproject.toml` (`[tool.pytest.ini_options]`):
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["src"]
  addopts = ["-ra", "--strict-markers"]
  markers = [
      "local_ets2: tests requiring local ETS2 1.62.3.3s archives",
      "local_promods: tests requiring local ProMods or user map-combo archives",
  ]
  ```

**Assertion Library:**
- Built-in `pytest` `assert` statements, `pytest.approx(...)` for float/IEEE-754 hex comparisons, and `pytest.raises(..., match=...)` for typed exception assertions.

**Run Commands:**
```bash
uv run pytest                                                         # Full suite (638 tests collected; local markers skip cleanly on CI)
uv run --offline pytest -q --tb=short                                 # workflow.test_command (.planning/config.json)
uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright  # workflow.build_command
uv run --offline pytest -m "not local_ets2 and not local_promods"     # CI-safe offline suite only (634 tests)
uv run --offline pytest -m local_ets2                                 # Local ETS2 1.62.3.3s archive tests only (2 tests)
uv run --offline pytest -m local_promods                              # Local ProMods & user combo archive tests only (2 tests)
uv run --offline pytest --cov=ets2_realism --cov-report=term-missing -m "not local_ets2 and not local_promods"  # Coverage report
uv run --offline --no-sync pytest -p no:cacheprovider -q --tb=short   # Offline / cacheless run
```

## TDD Red-First & CI Verification Gates

- `.planning/config.json` enforces `"tdd_mode": true`, `"nyquist_validation": true`, `"code_review": true` (`deep`), and `"security_enforcement": true` (`ASVS level 2`, `block_on: medium`).
- Write failing tests **before** production implementation (`RED -> GREEN -> REFACTOR`) and gate every RED/GREEN step on `workflow.build_command` (`ruff check`, `ruff format --check`, `basedpyright`) plus `workflow.test_command` (`pytest`).
- **GitHub Actions Verification Gates:**
  - `.github/workflows/ci.yml` (push to `master`/`main` & PRs, `permissions: contents: read`, `ubuntu-latest`, `timeout-minutes: 15`): runs `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run basedpyright`, and `uv run pytest`.
  - `.github/workflows/phase-a-release.yml` (Friday `06:00 UTC` schedule + `workflow_dispatch`, `permissions: contents: write, pull-requests: write`): executes offline quality gates (`ruff`, `basedpyright`, `pytest`) before fetching live feeds, builds diff-gated Summer/Winter releases, runs explicit `ets2-realism validate workshop` and `ets2-realism validate local` on all 4 artifacts, runs `ets2-realism registry snapshot-verify` against `SHA256SUMS.txt`, updates rolling `snapshots-latest` release, and opens/updates the persistent `release/phase-a-weekly` PR.
  - `.github/workflows/osm-speed-audit.yml` (monthly first Monday `07:00 UTC` + `workflow_dispatch`, `permissions: contents: read, issues: write`): runs read-only `ets2-realism audit osm-speeds` with zero Git writes and upserts/closes a rolling `osm-audit` maintainer issue using sanitized Markdown.
  - Workflow hygiene and security invariants (UTF-8 no-BOM LF, least-privilege permissions, no `pull_request_target`, shell-injection safety) are asserted automatically in `tests/test_cli_scaffold.py` and `tests/test_publish_workflow.py`.

## Test File Organization

**Location & Structure:**
- All `638` tests live in `45` modules directly under `tests/` (`testpaths = ["tests"]`), separated from `src/ets2_realism/`.
- There is no shared `conftest.py`; fixtures and synthetic builders remain co-located inside each test module for clarity and explicit dependencies.
- `.gitattributes` reserves `fixtures/** -text` for static binary/raw fixtures if ever needed; all current synthetic archives, workbooks, HTTP payloads, and map combos are generated inline in `tmp_path` or memory.

**Complete Inventory (`638` collected tests across `45` modules: `634` CI-safe + `4` local-archive):**

| Subsystem | Test File | Tests | Scope & Key Fixtures |
| --- | --- | ---: | --- |
| Scaffold & DAG | `tests/test_cli_scaffold.py` | 12 | CLI `--version`/`--help`, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`, active layout, AST DAG & audit quarantine walls |
| VFS | `tests/test_vfs_cityhash.py` | 25 | CityHash64 1.0.3 constants (`K0`–`K3`), all byte-length buckets, salted hashes, `normalize_vfs_path` traversal/NUL rejection |
| VFS | `tests/test_vfs_archives.py` | 17 | Synthetic HashFS v1/v2, ZIP flags (`0x01`/`0x40`/`compress_type=99`), `DirectoryArchive` junctions/size caps, decompression caps |
| VFS | `tests/test_vfs_stack.py` | 18 | Multi-layer overlay priority, `base/` normalization, `dlc_<id>/` scoping, empty `SiiNunit {}` stubs, `MAX_STUB_INSPECT_BYTES` |
| SII Engine | `tests/test_sii_hygiene.py` | 10 | BOM/CRLF/CR normalization, pass-1/pass-2 idempotency, strict UTF-8 errors, column-0 `@include`, POSIX paths, `[a-z0-9_]{1,12}` |
| SII Engine | `tests/test_sii_document.py` | 9 | IEEE-754 `&hex` floats, comments/strings/arrays, scalar/array span edits, single-line & shared-brace units, last-wins scalars |
| SII Engine | `tests/test_sii_country.py` | 8 | `country.sii` `@include` extraction, `country_data` attributes, fixed-array `attr[i]` replacement, string escaping, quote preservation |
| SII Engine | `tests/test_sii_speed_limits.py` | 3 | Interleaved `lane_speed_class[]` parsing, `train`/`tram` preservation, `uncommon[]`, shared-brace edits |
| SII Engine | `tests/test_sii_boards_locales.py` | 6 | `sign_board_template` + `sign_template_text` parsing, highway sign exclusion, DoS `items` cap, `localization_db` wrapped/headerless |
| Baseline | `tests/test_baseline_extractor.py` | 5 | `resolve_game_dir` precedence, synthetic HashFS v2 extraction, `vfs inspect` & `baseline extract --check`, `data/` cache guard |
| Baseline | `tests/test_baseline_contracts.py` | 8 | Committed `data/baselines/ets2_1.62_def/*.json` SHA-256/schema contracts (`6` CI-safe) + `@pytest.mark.local_ets2` live `1.62.3.3s` (`2`) |
| Registry | `tests/test_registry_schema.py` | 9 | Strict Pydantic `CountryLawRecord`/`SeasonalRuleSet` validation, loader hygiene, `registry validate` CLI |
| Registry | `tests/test_registry_contracts.py` | 5 | Committed 36-country core realism law JSONs and `data/mappings/ets2_countries.json` contracts |
| Registry | `tests/test_registry_timezone.py` | 19 | Dynamic `zoneinfo` + `tzdata` Summer/Winter DST resolution, sub-hour offsets, southern hemisphere inversions |
| Registry | `tests/test_registry_snapshot.py` | 9 | `schema_version=1` realism snapshot generation, deterministic SHA-256, `SHA256SUMS.txt` verification, CLI |
| Registry | `tests/test_country_aliases.py` | 3 | `CountryAliasRegistry` schema, BOM/CRLF rejection, canonical coverage of map ecosystems |
| Registry | `tests/test_global_registry_expansion.py` | 35 | Global 225-territory & ~156-currency registry expansion, Tier 3 curated baselines, lockfile & snapshot parity |
| Normalize | `tests/test_normalize_fx.py` | 33 | Offline currency map, multi-provider FX cross-validation, divergence guards, atomic `prices.lock.json` I/O |
| Normalize | `tests/test_normalize_fuel.py` | 24 | Secondary grade derivation, Decimal rounding, 39-territory baseline seeding, tier/cadence staleness alerts |
| Normalize | `tests/test_totem_formatting.py` | 46 | 6-font SDF width-budget physics, `<sup>` support, native-currency formatting across core & extended currencies |
| Normalize | `tests/test_totem_compiler.py` | 4 | 460-board totem classification and Option 4b Zero-DDS 43-locale SII compilation |
| Fetch | `tests/test_fetch_fx.py` | 14 | Offline `MockTransport` tests for `fetch/http.py` (SSRF, redirects, XXE, redaction) and FX collectors (Frankfurter, ECB, Fawaz, CBR) |
| Fetch | `tests/test_fetch_fuel.py` | 16 | Offline `MockTransport` + in-memory `openpyxl` tests for EU Tier 1 fuel collectors (EC WOB, UK DESNZ, NO SSB, FR, DE, ES, IT, NL) |
| Fetch | `tests/test_fetch_global_tier1.py` | 18 | Offline `MockTransport` + in-memory `openpyxl` tests for non-EU Tier 1 global fuel APIs (EIA, ANP, NRCan, OPINET, CNE, OpenDOSM, etc.) |
| Fetch | `tests/test_fetch_tier2_portals.py` | 22 | Offline stdlib `fetch/_html.py` parser and guarded Tier 2 national portal scrapers (rate limits, selector drift, encoding) |
| Fetch | `tests/test_fetch_pipeline.py` | 17 | End-to-end offline `run_price_fetch()`, circuit-breaker/outage fallback policy, staleness alerts, `ets2-realism fetch` CLI |
| Package | `tests/test_package_icons_metadata.py` | 19 | Clean-room `276x162` Pillow JPEG icons (`<= 1 MiB`), `manifest.sii`, `versions.sii`, `description.txt` metadata |
| Package | `tests/test_package_synthesize.py` | 7 | Clean-room 36-country `.sui` and `speed_limits.sii` synthesis round-trips |
| Package | `tests/test_package_builder.py` | 5 | Dual-target Workshop + deterministic local ZIP Core packaging, VFS/ZipArchive validation, `package build` CLI |
| Validate | `tests/test_validate_workshop.py` | 45 | Independent Layer-8 DAG isolation, SCS Workshop error codes (`00001`–`00024`), icon/size/encoding/path checks, CLI |
| Validate | `tests/test_validate_invariants.py` | 15 | ETS2 1.62 core, ProMods, and combo realism invariants & reference-mod regression guards |
| Merge | `tests/test_merge_aliases.py` | 7 | Deterministic 3-tier country alias resolution, subnational timezone overrides, SemEuropa Brazilian state ISO-2 collision shield |
| Merge | `tests/test_merge_load_order.py` | 16 | Multi-source load-order resolution (`profile.sii`, `game.log.txt`, modlist, `--mod`), self-package exclusion, `ScsC` detection |
| Merge | `tests/test_merge_scanner.py` | 7 | Synthetic multi-map VFS scanner (`.sui`/`.sii`, `base/` normalization, empty stubs, protected layers) |
| Merge | `tests/test_merge_policy.py` | 6 | `FieldOwnershipPolicy` surgical country & speed-limit overlay round-trips preserving map-owned fields |
| Merge | `tests/test_hardcoded_totems.py` | 4 | Opt-in `--patch-hardcoded-totems` (JRR/7RM numeric sign boards) |
| Merge | `tests/test_promods_discovery.py` | 6 | Version-agnostic ProMods EU/ME/MA/TGS `def` + `assets` archive discovery |
| Merge | `tests/test_promods_fuel.py` | 27 | Dynamic ProMods 43-locale `local_module.pm*_fuel.sii` compiler and formatting |
| Merge | `tests/test_promods_builder.py` | 8 | Synthetic clean-room ProMods Companion builds (`7` CI-safe) + `@pytest.mark.local_promods` local ProMods build (`1`) |
| Merge | `tests/test_compose_local.py` | 8 | End-to-end synthetic multi-map combo composer & fault isolation (`7` CI-safe) + `@pytest.mark.local_promods` dry-run audit (`1`) |
| Publish | `tests/test_publish_ledger.py` | 9 | Canonical Workshop SHA-256 hashing, ISO-week versioning (`YYYY.Www`), `PublishedLedger` persistence |
| Publish | `tests/test_publish_release.py` | 14 | Phase A changelog rendering, diff-gated release orchestration, `publish release` CLI |
| Publish | `tests/test_publish_workflow.py` | 12 | Security & contract tests for `.github/workflows/{phase-a-release,ci,osm-speed-audit}.yml` |
| Audit | `tests/test_audit_osm_speeds.py` | 9 | `post_form_bytes_with_retry`, OSM rule parser, allowlist splits, Overpass/Taginfo spot checks, Markdown sanitization, CLI |
| Audit | `tests/test_license_taint_gate.py` | 19 | Automated 8-marker CC BY 4.0 taint gate across repo data, lockfile, snapshots, built Core packages, changelogs, and synthetic archives |

## Test Structure

**Suite Organization:**
- Write standalone typed test functions (`def test_<behavior>(...) -> None:`) using `@pytest.mark.parametrize` for input matrices; never use `unittest.TestCase` or `Test*` classes (`0` test classes across all 45 modules).
```python
@pytest.mark.parametrize("bad_path", ["../secret.sii", "def/../secret.sii", "def/foo\x00bar.sii"])
def test_normalize_vfs_path_rejects_traversal_and_nul(bad_path: str) -> None:
    with pytest.raises(ValueError):
        normalize_vfs_path(bad_path)
```
- Annotate pytest built-in fixtures explicitly (`tmp_path: pathlib.Path`, `tmp_path_factory: pytest.TempPathFactory`, `capsys: pytest.CaptureFixture[str]`, `monkeypatch: pytest.MonkeyPatch`) to satisfy strict `basedpyright`.
- Use `@pytest.fixture(scope="module")` sparingly for expensive read-only builds shared across many mutation/assertion tests in one module (`built_editions` in `tests/test_validate_workshop.py` and `tests/test_validate_invariants.py`; `phase4_snapshot` and `bundled_aliases` in `tests/test_merge_aliases.py`), cloning into per-test `tmp_path` (`_clone_workshop`, `_rebuild_zip_with_mutations`) before mutating.

## CI-Safe Synthetic Fixtures vs Local-Archive Markers

**CI-Safe Synthetic Builders (`634` tests):**
- Build self-contained binary containers, spreadsheets, and HTTP fixtures inline so CI runs 100% offline on `ubuntu-latest` without proprietary `.scs` files or live network calls:
  - HashFS v1/v2 & encrypted ZIP builders (`_build_hashfs_v1`, `_build_hashfs_v2`, `_build_mixed_encrypted_zip` in `tests/test_vfs_archives.py`; `_create_synthetic_ets2_install` in `tests/test_baseline_extractor.py`).
  - Synthetic ProMods & multi-map combo builders (`_create_synthetic_promods_mod_dir` in `tests/test_promods_builder.py`; `_build_synthetic_combo_fixture` and `_write_encrypted_flag_zip` in `tests/test_compose_local.py`).
  - In-memory `openpyxl.Workbook` Excel generators (`io.BytesIO`) for EC Weekly Oil Bulletin and global XLSX fuel feeds (`tests/test_fetch_fuel.py`, `tests/test_fetch_global_tier1.py`).
  - Deterministic `httpx.MockTransport` HTTP handlers for FX, Tier 1/2 fuel portals, OSM rulesets, Overpass, and Taginfo (`tests/test_fetch_*.py`, `tests/test_audit_osm_speeds.py`).

**Live/Local-Archive Tests (`4` tests gated by strict markers + `skipif`):**
- Gate every test requiring proprietary local game or map archives with **both** its registered pytest marker and `@pytest.mark.skipif(...)`:
  - **`@pytest.mark.local_ets2` (`2` tests in `tests/test_baseline_contracts.py`):**
    - `test_local_ets2_extract_matches_committed_baseline_zero_diff` — extracts local ETS2 `1.62.3.3s` archives via `resolve_game_dir()` (`ETS2_GAME_DIR` or default Steam path) and asserts zero diff against `data/baselines/ets2_1.62_def/*.json`.
    - `test_local_ets2_all_36_sii_surgical_round_trips_in_memory` — verifies byte-preserving surgical round-trips across all 36 live `def.scs` country/speed-limit files in memory.
  - **`@pytest.mark.local_promods` (`2` tests):**
    - `test_local_promods_companion_build_and_validate` (`tests/test_promods_builder.py`) — builds and validates a ProMods Companion edition against locally discovered ProMods archives.
    - `test_local_combo_dry_run_audit` (`tests/test_compose_local.py`) — runs `compose_local(..., dry_run=True)` against local `D:\ETS2Data\Euro Truck Simulator 2` profile/mod directories when present.
- When local archives are absent (as on GitHub Actions `ubuntu-latest`), `skipif` skips all 4 local tests cleanly while `--strict-markers` catches any unregistered marker typos.

## Mocking

**Frameworks:**
- Use `httpx.MockTransport` for all HTTP/API tests (`6` test modules: `tests/test_fetch_fx.py`, `tests/test_fetch_fuel.py`, `tests/test_fetch_global_tier1.py`, `tests/test_fetch_tier2_portals.py`, `tests/test_fetch_pipeline.py`, `tests/test_audit_osm_speeds.py`) paired with `create_http_client(transport=...)` and `sleep_fn=lambda _: None` for instant retry tests.
- Use pytest's `monkeypatch: pytest.MonkeyPatch` (`16` test modules) for environment variables, resource caps, OS hooks, and CWD changes. Never use `unittest.mock` (`0` occurrences across `tests/`).

**Patterns:**
```python
def _handler(request: httpx.Request) -> httpx.Response:
    if str(request.url) == FRANKFURTER_V2_URL:
        return httpx.Response(200, json=_frankfurter_v2_payload())
    return httpx.Response(404)

with create_http_client(transport=httpx.MockTransport(_handler)) as client:
    quotes = fetch_frankfurter_v2(client, sleep_fn=lambda _: None)
```
```python
monkeypatch.setattr(taint_mod, "MAX_TAINT_TEXT_BYTES", 128)
monkeypatch.setattr(stack_mod, "MAX_STUB_INSPECT_BYTES", 32)
monkeypatch.delenv("ETS2_GAME_DIR", raising=False)
monkeypatch.chdir(tmp_path)
```

**What to Mock:**
- Outbound HTTP responses (`httpx.MockTransport`), backoff sleepers (`sleep_fn`), API key env vars (`TANKERKOENIG_API_KEY`, `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`), and local install paths (`ETS2_GAME_DIR`).
- Resource ceiling constants (`MAX_STUB_INSPECT_BYTES`, `MAX_ENTRY_DECOMPRESSED_BYTES`, `MAX_ZIP_ENTRY_BYTES`, `MAX_TAINT_TEXT_BYTES`) to trigger bomb/size-cap guards with tiny inputs.
- OS/filesystem edge calls (`pathlib.Path.is_junction`, `pathlib.Path.read_bytes`, `pathlib.Path.open`) to test permission errors (`00006`) and junction pruning deterministically.

**What NOT to Mock:**
- Never mock `cityhash64`, `SiiDocument`, `validate_sii_hygiene`, `VfsStack`, `ZipArchive`/`HashFs*`, `FieldOwnershipPolicy`, `validate_workshop_package`, `validate_local_zip`, or `scan_repo_and_artifacts_for_taint` — always exercise real implementations against synthetic fixtures.

## Coverage

**Requirements:**
- `pytest-cov` (`7.1.0`) is installed in `[dependency-groups].dev` in `pyproject.toml`; no numeric coverage threshold is currently enforced in `pyproject.toml` or `.github/workflows/ci.yml`.

**View Coverage:**
```bash
uv run --offline pytest --cov=ets2_realism --cov-report=term-missing -m "not local_ets2 and not local_promods"
```

## Test Types

**Unit Tests:**
- Exercise pure hashing (`test_vfs_cityhash.py`), SII lexer/hygiene/adapters (`test_sii_*.py`), Pydantic schemas & DST timezone resolution (`test_registry_*.py`, `test_country_aliases.py`), Decimal FX/fuel/totem formatting (`test_normalize_*.py`, `test_totem_*.py`), alias resolution & field ownership (`test_merge_{aliases,policy}.py`, `test_hardcoded_totems.py`), and ledger/icon/metadata helpers (`test_publish_ledger.py`, `test_package_icons_metadata.py`).

**Integration & Contract Tests:**
- Verify multi-layer VFS overlays (`test_vfs_{archives,stack}.py`, `test_merge_{load_order,scanner}.py`), offline fetch pipelines (`test_fetch_*.py`), full Core/ProMods/combo package builds & Workshop validation (`test_package_builder.py`, `test_validate_{workshop,invariants}.py`, `test_promods_builder.py`, `test_compose_local.py`), Phase A release orchestration & CI workflow contracts (`test_publish_{release,workflow}.py`), committed baseline/registry/taint contracts (`test_baseline_contracts.py`, `test_global_registry_expansion.py`, `test_license_taint_gate.py`), and AST DAG isolation (`test_cli_scaffold.py`).

**E2E / CLI Tests:**
- Invoke `ets2_realism.cli.main([...])` directly with `capsys` and `tmp_path` across CLI subcommands (`vfs inspect`, `baseline extract`, `registry validate/snapshot/snapshot-verify`, `fetch`, `package build/promods`, `validate workshop/local`, `compose-local`, `publish release`, `audit osm-speeds/taint`).

## Common Patterns

**Idempotency, Determinism & Zero-Diff Round-Trip Testing:**
```python
pass1 = doc_bom.to_bytes()
assert pass1 == clean_bytes
assert SiiDocument.parse(pass1).to_bytes() == pass1
```
- Assert byte-for-byte determinism across repeated builds of JSON baselines, snapshots, lockfiles, icons, Workshop folders, and local ZIP SHA-256 digests (`tests/test_sii_hygiene.py`, `tests/test_registry_snapshot.py`, `tests/test_package_builder.py`, `tests/test_publish_ledger.py`).

**Diagnostics, Security & Error Testing:**
```python
with pytest.raises(ProtectedPayloadError):
    arc.read_bytes("def/country/beyond.sui")
assert any(d.kind == "encrypted_zip" for d in arc.diagnostics)
```
- Assert both failure outcomes (typed exceptions, `report.ok is False`, CLI exit code `1` with `capsys.readouterr().err`) and exact structured codes (`00006`, `00007`, `ETS2R-INV-LICENSE-TAINT`, `encrypted_zip`), plus absence of leaked query secrets or `.tmp` leftovers after atomic writes (`tests/test_fetch_fx.py`, `tests/test_compose_local.py`, `tests/test_license_taint_gate.py`).

---

*Testing analysis: 2026-11-26*
