# Codebase Concerns

**Analysis Date:** 2026-11-26

## Tech Debt

### Oversized Multi-Responsibility Functions Across Core Modules

- **Issue:** Across `73` Python modules (`29,395` LOC) in `src/ets2_realism/`, `25` functions exceed `120` lines and concentrate CLI argument wiring, network orchestration, VFS scanning, SII lexing, and multi-profile validation inside single scopes:
  - `build_parser()` in `src/ets2_realism/cli.py:940-1900` (`961` lines): registers all subcommands, flags, and defaults in one monolithic builder (out of `1,925` total lines in `cli.py`).
  - `run_price_fetch()` in `src/ets2_realism/fetch/pipeline.py:235-697` (`463` lines): combines lockfile loading, FX cross-validation, 32 sequential feed invocations, precedence sorting, circuit-breaker evaluation, Tier 3 repricing, staleness checks, and persistence.
  - `compose_local()` in `src/ets2_realism/merge/compose.py:203-604` (`402` lines): orchestrates snapshot loading, load-order parsing, VFS mounting, country scanning, alias resolution, policy patching, totem compilation, staging, offline validation, and report generation.
  - `validate_workshop_package()` (`304` lines, `1312-1615`), `_validate_manifest()` (`298` lines, `573-870`), and `_validate_package_contents()` (`284` lines, `935-1218`) in `src/ets2_realism/validate/workshop.py` (`1,681` lines total).
  - `build_promods_edition()` in `src/ets2_realism/merge/promods_builder.py:128-414` (`287` lines), `scan_active_countries()` in `src/ets2_realism/merge/scanner.py:132-417` (`286` lines), `scan_sii_structure()` in `src/ets2_realism/sii/lexer.py:473-747` (`275` lines), `extract_baseline()` in `src/ets2_realism/baseline/extractor.py:198-462` (`265` lines), `run_phase_a_release()` in `src/ets2_realism/publish/release.py:124-362` (`239` lines), `validate_law_registry()` in `src/ets2_realism/registry/loader.py:220-454` (`235` lines), `patch_hardcoded_numeric_totems()` in `src/ets2_realism/merge/hardcoded_totems.py:133-357` (`225` lines), and `HashFsV2Archive._load_tables()` in `src/ets2_realism/vfs/hashfs.py:484-646` (`163` lines).
- **Files:** `src/ets2_realism/cli.py`, `src/ets2_realism/fetch/pipeline.py`, `src/ets2_realism/merge/compose.py`, `src/ets2_realism/validate/workshop.py`, `src/ets2_realism/merge/promods_builder.py`, `src/ets2_realism/merge/scanner.py`, `src/ets2_realism/sii/lexer.py`, `src/ets2_realism/baseline/extractor.py`, `src/ets2_realism/publish/release.py`, `src/ets2_realism/registry/loader.py`, `src/ets2_realism/merge/hardcoded_totems.py`, `src/ets2_realism/vfs/hashfs.py`
- **Impact:** High cyclomatic complexity increases regression risk when extending CLI subcommands, ETS2 `1.63+` schema rules, or V2 SteamCMD publishing, and makes targeted unit testing of internal stages harder.
- **Fix approach:** Split `cli.py` into per-command parser registration helpers (`_register_fetch_parser`, `_register_merge_parser`, etc.), decompose `run_price_fetch()` into fetch/merge/reprice stages, and extract per-attribute manifest checks in `validate/workshop.py` before starting V2 milestones.

### Editable-Checkout Layout Coupling (Non-Editable Wheel Installation Broken)

- **Issue:** `pyproject.toml:37-38` configures `[tool.hatch.build.targets.wheel]` with `packages = ["src/ets2_realism"]` only, omitting `data/` and `assets/`. However, `src/ets2_realism/normalize/currencies.py:13-17` resolves `DEFAULT_CURRENCIES_JSON_PATH` and `DEFAULT_TIER3_BASELINES_JSON_PATH` via `Path(__file__).resolve().parents[3] / "data"` and loads them at module import time. Similarly, `src/ets2_realism/baseline/extractor.py:217` and `src/ets2_realism/merge/promods_builder.py:88` anchor repository-root checks on `Path(__file__).resolve().parents[3]`, while CLI default paths (`data/laws`, `data/mappings/ets2_countries.json`, `data/baselines/ets2_1.62_def`, `assets/icons`, `state/prices.lock.json`) are CWD-relative (`src/ets2_realism/cli.py`, `src/ets2_realism/publish/release.py:126-134`, `src/ets2_realism/merge/promods_builder.py:145-150`).
- **Files:** `pyproject.toml`, `src/ets2_realism/normalize/currencies.py`, `src/ets2_realism/baseline/extractor.py`, `src/ets2_realism/merge/promods_builder.py`, `src/ets2_realism/cli.py`
- **Impact:** Installing `ets2-country-realism` as a non-editable wheel (`pip install` / `uv tool install`) fails immediately with `FileNotFoundError` on `import ets2_realism.normalize.currencies`. End users running `ets2-realism compose-local` or `ets2-realism package promods` are forced to clone the repository and execute from the repo root via `uv run`.
- **Fix approach:** Bundle clean-room static registries (`data/mappings/`, `data/curated/`, `data/baselines/ets2_1.62_def/`, `data/laws/`, `assets/icons/`) via `importlib.resources` (or Hatch `force-include` shared-data) with explicit repo-checkout override, and locate Git repo roots by walking upward for `.git`/`pyproject.toml` rather than hardcoding `parents[3]`.

### Mutable GitHub Actions Tags Coupled to Contract Tests

- **Issue:** All three GitHub Actions workflows pin actions to mutable major tags (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/upload-artifact@v4`) rather than immutable 40-character commit SHAs: `.github/workflows/ci.yml:19,22`, `.github/workflows/phase-a-release.yml:30,33,196`, and `.github/workflows/osm-speed-audit.yml:36,39,82`. Both `tests/test_cli_scaffold.py:180-190` and `tests/test_publish_workflow.py:92-94` explicitly assert those `@v4`/`@v5` strings.
- **Files:** `.github/workflows/ci.yml`, `.github/workflows/phase-a-release.yml`, `.github/workflows/osm-speed-audit.yml`, `tests/test_cli_scaffold.py`, `tests/test_publish_workflow.py`
- **Impact:** Upstream tag re-pointing creates a supply-chain drift vector in write-scoped workflows (`phase-a-release.yml` holds `contents: write`, `pull-requests: write`, and 4 optional API secrets; `osm-speed-audit.yml` holds `issues: write`).
- **Fix approach:** Resolve verified 40-character commit SHAs online for `actions/checkout`, `astral-sh/setup-uv`, and `actions/upload-artifact`, pin them with `# v4` / `# v5` comments across all three workflows, and update the workflow contract assertions in `tests/test_cli_scaffold.py` and `tests/test_publish_workflow.py` in lockstep.

### Duplicated Helpers, Inline Workflow Python Scripts, and Hardcoded `DEFAULT_ANCHOR_YEAR`

- **Issue:** Several small maintenance debts accumulated across Phases 1–5:
  - **Duplicated SII formatters:** `_format_fuel_price()` and `_format_sii_string()` are duplicated verbatim between `src/ets2_realism/sii/country.py:102-117` and `src/ets2_realism/package/synthesize.py:20-57`.
  - **Duplicated inline Python in YAML workflows:** Identical `_sanitize()` and `_is_ext_fx_warn()` alert-formatting Python heredocs are duplicated twice inside `.github/workflows/phase-a-release.yml:63-145,264-338` and again in `.github/workflows/osm-speed-audit.yml:93-137`.
  - **Hardcoded DST anchor year:** `DEFAULT_ANCHOR_YEAR = 2026` in `src/ets2_realism/registry/timezone.py:14` is used as the default in `cli.py`, `package/builder.py`, `publish/release.py`, `merge/promods_builder.py`, and `merge/compose.py`. Once the calendar rolls into `2027+`, builds omitting `--anchor-year` will continue computing DST rules for `2026` rather than the active release year.
  - **Residual VFS ergonomics:** `VfsStack.__init__()` (`src/ets2_realism/vfs/stack.py:164-171`) accepts `seeded_prefixes` only to discard it (`del seeded_prefixes`), and `ZipArchive._load_central_directory()` (`src/ets2_realism/vfs/zip_archive.py:125`) silently overwrites duplicate normalized paths (`self._entries[norm] = info`) without emitting an archive diagnostic (only `validate/workshop.py` inspects raw ZIP duplicates separately).
  - **Active-phase layout test coupling:** `test_active_phase_only_package_layout()` and `test_pyproject_metadata_and_quality_gates()` in `tests/test_cli_scaffold.py:64-139` hardcode exact subpackage sets and exact dependency version strings; every V2 dependency or subpackage addition requires updating that test file.
  - **Pre-rename `ets2v2` prose in `.planning/`:** Commit `67e2071` cleanly renamed `src/ets2_realism/`, `tests/`, `scripts/`, `.github/`, `data/`, and `state/` (`0` residual `ets2v2` references in code/config), while `.planning/STATE.md` and historical phase docs still reference `src/ets2v2/` and `ets2v2`.
- **Files:** `src/ets2_realism/sii/country.py`, `src/ets2_realism/package/synthesize.py`, `.github/workflows/phase-a-release.yml`, `.github/workflows/osm-speed-audit.yml`, `src/ets2_realism/registry/timezone.py`, `src/ets2_realism/vfs/stack.py`, `src/ets2_realism/vfs/zip_archive.py`, `tests/test_cli_scaffold.py`, `.planning/STATE.md`
- **Impact:** Duplicated formatting/sanitization logic risks behavioral drift across modules and workflows; `DEFAULT_ANCHOR_YEAR = 2026` will silently anchor future `2027+` releases to `2026` IANA DST rules.
- **Fix approach:** Export shared SII formatters from `ets2_realism.sii`, extract workflow summary/PR-body rendering into a CLI subcommand (`ets2-realism publish format-summary`), default `anchor_year` to `build_date.year` in `run_phase_a_release()` / `compose_local()`, and emit duplicate-entry diagnostics in `ZipArchive`.

## Known Bugs

### `assert_out_dir_not_tracked()` Falsely Blocks Valid User Output Directories When Run Outside the Repo

- **Symptoms:** Running `ets2-realism compose-local --out-dir ./mod` or `ets2-realism package promods --out-dir ./my_builds` from a working directory outside the repository (e.g., `D:\ETS2Data\Euro Truck Simulator 2`) raises `ValueError: Refusing to write ProMods/Combo output inside tracked/unignored repository directory`.
- **Files:** `src/ets2_realism/merge/promods_builder.py:82-110` (called by both `build_promods_edition()` at line `157` and `compose_local()` in `src/ets2_realism/merge/compose.py:217`)
- **Trigger:** `_candidate_repo_roots()` unconditionally appends `Path.cwd().resolve()` to the protected-repo root list even when CWD is not a Git repository. Any `out_dir` beneath CWD whose first relative path segment is not in `{"dist", "out", "build", "raw", "vendor"}` (including `mod/`!) is rejected.
- **Workaround:** Pass an `--out-dir` outside CWD or named `dist`/`out`/`build`, or invoke from inside the repository root; fix by only adding `cwd` to `_candidate_repo_roots()` when `(cwd / ".git").exists()` or `(cwd / "pyproject.toml").is_file()`.

### `fetch_ch_bfs_lik()` Issues HTTP `GET` Against a PxWeb v1 `.px` Endpoint Expecting `POST`

- **Symptoms:** On live network runs, Switzerland's Tier 2 collector (`ch_bfs_lik`) receives PxWeb table variable metadata JSON (`{"title": ..., "variables": [...]}`) instead of JSON-stat2 price data, trips `Tier2SelectorDriftError("CH BFS JSON-stat2 missing dimension/value fields")`, emits a `tier2_selector_drift` warning, and falls back to `fuel_prices_eu` or `state/prices.lock.json`.
- **Files:** `src/ets2_realism/fetch/tier2_portals.py:53-58,632-668`
- **Trigger:** `CH_BFS_LIK_URL` targets `https://www.pxweb.bfs.admin.ch/api/v1/de/px-x-0501000000_105/px-x-0501000000_105.px` via `fetch_bytes_with_retry()` (`GET`). PxWeb v1 `.px` URLs require a `POST` request with a JSON query payload (`"response": {"format": "json-stat2"}`) to return data; `GET` returns schema metadata only.
- **Workaround:** Per-country `_run_tier2_guarded()` isolates the failure so `CH` falls back cleanly to `fuel_prices_eu`/lockfile; fix by either `POST`ing a PxWeb query (analogous to `fetch_no_ssb_09654()` in `src/ets2_realism/fetch/national.py`) or targeting a direct `dam-api.bfs.admin.ch` CSV asset endpoint.

### `phase-a-release.yml` Never Passes `--previous-snapshots-dir`, Leaving Structured Changelog Diffs Inactive in CI

- **Symptoms:** Every scheduled and manual run of `.github/workflows/phase-a-release.yml` renders the static initial-release highlights (`_render_initial_highlights`) in `CHANGELOG_SUMMER.md` and `CHANGELOG_WINTER.md` instead of structured `## Changes Since Previous Snapshot` diffs.
- **Files:** `.github/workflows/phase-a-release.yml:151-161`, `src/ets2_realism/cli.py:582-608`, `src/ets2_realism/publish/release.py:140,283-295`
- **Trigger:** `cli.py` exposes `--previous-snapshots-dir`, but `phase-a-release.yml` never downloads the prior `realism-snapshot-{summer,winter}.json` files from the rolling `snapshots-latest` GitHub Release and never passes `--previous-snapshots-dir` to `ets2-realism publish release`. Separately, `cli.py:603-605` reads `--previous-snapshots-dir` files via unbounded `snap_file.read_text("utf-8")` instead of calling `load_realism_snapshot()` (which enforces `MAX_SNAPSHOT_BYTES = 64 MiB`).
- **Workaround:** Pass `--previous-snapshots-dir` manually in local runs; fix by adding a best-effort `gh release download snapshots-latest` step into a temp dir before `publish release` in `phase-a-release.yml` and routing `cli.py:603` through `load_realism_snapshot()`.

### `SiiDocument.diagnostics` Masks Raw UTF-8 BOM and CRLF Hygiene Errors

- **Symptoms:** Calling `SiiDocument.parse(raw_bytes).diagnostics` on files containing a leading UTF-8 BOM (`\xef\xbb\xbf`) or `\r\n`/`\r` line endings reports zero `utf8_bom` or `non_lf_line_ending` issues.
- **Files:** `src/ets2_realism/sii/document.py:44-50,72-74`
- **Trigger:** `SiiDocument.parse()` strips leading BOM and normalizes line endings to `\n` before storing `self._text`, and `diagnostics` runs `validate_sii_hygiene(self._text)` on the already-normalized string.
- **Workaround:** `src/ets2_realism/validate/workshop.py` already passes raw file bytes directly to `validate_sii_hygiene(raw_bytes)`. Maintain that rule for any future validator or linter caller.

## Security Considerations

### Write-Scoped CI Workflows & Optional API Key Handling

- **Risk:** `.github/workflows/phase-a-release.yml` runs with `permissions: { contents: write, pull-requests: write }` and accepts 4 optional repository secrets (`TANKERKOENIG_API_KEY`, `EIA_API_KEY`, `OPINET_API_KEY`, `CNE_API_TOKEN`, lines `51-54`); `.github/workflows/osm-speed-audit.yml` runs with `permissions: { contents: read, issues: write }`. Both still use mutable major action tags (`@v4`/`@v5`).
- **Files:** `.github/workflows/phase-a-release.yml`, `.github/workflows/osm-speed-audit.yml`, `src/ets2_realism/fetch/http.py`, `src/ets2_realism/fetch/global_tier1.py`, `src/ets2_realism/fetch/national.py`
- **Current mitigation:** Zero Steam credentials in CI; `pull_request` and `pull_request_target` triggers are forbidden on both write-scoped workflows; zero `${{ ... }}` expressions appear inside `run:` blocks; all secrets pass via step-level `env:`; `redact_url_secrets()` (`src/ets2_realism/fetch/http.py:29-49`) masks `apikey`, `api_key`, `token`, `key`, and `code` query parameters; every keyed collector scrubs raw secret values before logging/alerts; untrusted error strings are sanitized (including `[`, `]`, `|`, `<`, `>`, `` ` ``) before Markdown rendering.
- **Recommendations:** Pin all third-party GitHub Actions to 40-character commit SHAs across all three workflows.

### Untrusted External Feeds (OOXML, XML, HTML, CSV, JSON)

- **Risk:** `ets2-realism fetch` and `ets2-realism audit osm-speeds` consume 35+ third-party HTTPS endpoints (including dynamic `.xlsx` attachments from EC WOB, JP METI, RU Rosstat, ZA DMRE/CEF, NG NBS and legacy national HTML portals), creating exposure to SSRF redirects, XXE/UTF-16 DOCTYPE attacks, ZIP bombs, charset confusion, and response-size exhaustion.
- **Files:** `src/ets2_realism/fetch/http.py`, `src/ets2_realism/fetch/_parsing.py`, `src/ets2_realism/fetch/_html.py`, `src/ets2_realism/fetch/ec_bulletin.py`, `src/ets2_realism/fetch/global_tier1.py`, `src/ets2_realism/fetch/tier2_portals.py`, `src/ets2_realism/audit/overpass.py`
- **Current mitigation:** `validate_https_url()` enforces HTTPS-only, port 443 only, no embedded credentials, and per-feed host allowlists across redirects (`_MAX_REDIRECTS = 5`, `follow_redirects=False`, TLS `verify=True`); streaming byte caps (`DEFAULT_MAX_RESPONSE_BYTES = 30 MiB`, `ES_MITECO_MAX_BYTES = 50 MiB`, `DEFAULT_MAX_XML_BYTES = 2 MiB`); `validate_ooxml_zip_safety()` (`fetch/_parsing.py:113-165`) caps OOXML at `256` entries / `64 MiB` uncompressed, rejects encrypted/non-deflate members, catches `zlib.error`/`BadZipFile`, and blocks both UTF-8 and UTF-16 `<!DOCTYPE`/`<!ENTITY` payloads; Overpass QL strictly validates `^[A-Z]{2}$` before query interpolation.
- **Recommendations:** Keep `fetch/_html.py` stdlib-only (avoiding native `lxml` C-parser attack surface) and maintain strict `scanned_rows` caps on any new `.xlsx` or `.csv` collectors.

### Clean-Room IP & License Contamination Boundaries (`MIT` / `CC BY 4.0` vs `CC BY-SA` / ProMods / Proprietary)

- **Risk:** Accidental leakage of `CC BY-SA` / `ODbL` OpenStreetMap data (`westnordost/osm-legal-default-speeds`, Overpass, Taginfo), `CC BY-NC-ND` (`GlobalPetrolPrices.com`), `MyLPG.eu`, paid `IEA` reports, raw ETS2 `.sii`/`.sui` game files, or proprietary ProMods `.scs`/def files into Git or `CC BY 4.0` snapshots/packages would violate project licensing and ProMods redistribution rules.
- **Files:** `src/ets2_realism/audit/taint.py`, `src/ets2_realism/validate/invariants.py`, `src/ets2_realism/validate/workshop.py`, `src/ets2_realism/merge/promods_builder.py`, `tests/test_cli_scaffold.py`, `tests/test_license_taint_gate.py`, `tests/test_validate_workshop.py`, `data/laws/speed_audit_allowlist.json`
- **Current mitigation:**
  - **Universal AST DAG quarantine:** `tests/test_cli_scaffold.py` and `tests/test_validate_workshop.py` enforce all 6 offline isolation walls (`validate`, `merge`, `package`, `publish`, `normalize`, `registry`) plus zero inbound imports of `ets2_realism.audit` across all 10 non-audit subpackages.
  - **Dual independent license-taint gates:** Both `src/ets2_realism/audit/taint.py` (`ets2-realism audit taint`) and self-contained `check_license_taint_bytes()` in `src/ets2_realism/validate/invariants.py:46-75` (`ETS2R-INV-LICENSE-TAINT`, wired into all 3 profiles `core`/`promods`/`combo` in `validate/workshop.py`) reject `CC BY-SA`, `ODbL`, `OpenStreetMap`, `osm-legal-default-speeds`, `GlobalPetrolPrices`, `CC BY-NC-ND`, `MyLPG`, and `IEA` across multi-line and underscore variants.
  - **Zero proprietary/SCS files in Git:** `data/` holds strictly clean-room JSON (`0` `.sii`/`.sui`/`.scs`/`.dds`/`.tobj` files); `.github/workflows/osm-speed-audit.yml` has `contents: read` and zero `git` write commands.
- **Recommendations:** Maintainers triaging monthly `osm-audit` GitHub issues must always verify statutory changes against official national legislation and author clean-room rationales in `data/laws/` — never paste OSM wiki URLs or `osm-legal-default-speeds` text into `data/laws/`. Also fix `assert_out_dir_not_tracked()`'s CWD bug carefully so tracked-repo protection remains airtight.

### Protected & Obfuscated Local Mod Containers (`3nK`, `AEM!`, `ScsC`, Encrypted ZIPs, Traversal/Junctions)

- **Risk:** `ets2-realism compose-local` and `package promods` mount untrusted local user `.scs`/`.zip`/directory mods, `profile.sii`, `game.log.txt`, and Steam Workshop `227300` directories.
- **Files:** `src/ets2_realism/vfs/hashfs.py`, `src/ets2_realism/vfs/zip_archive.py`, `src/ets2_realism/vfs/dir_archive.py`, `src/ets2_realism/vfs/types.py`, `src/ets2_realism/merge/load_order.py`
- **Current mitigation:** Zero decryption/cracking code for `3nK\x01`, `AEM!`, `ScsC`, or PKZIP encryption (`flag_bits & 0x41`); `128 MiB` entry decompression/read caps across `HashFs*`, `ZipArchive`, and `DirectoryArchive`; `64 MiB` HashFS v2 table caps and `64 MiB` text caps for `profile.sii`/`game.log.txt`/snapshots/taint scans; strict `mod_dir` & Workshop `item_dir` containment, UNC (`\\server\share`) NTLMv2 leak rejection, `explicit_path` restricted to `--modlist` only, and Windows NTFS junction cycle/escape pruning in `dir_archive.py` and `publish/ledger.py`.
- **Recommendations:** Note that `VfsEntryMeta.three_nk` is still detected lazily upon `read_bytes()` or `<= 1 MiB` `.sii`/`.sui` stub inspection (`vfs/stack.py:283-294`); callers inspecting non-`.sii`/`.sui` entries or `> 1 MiB` files via `get_meta()` alone must not assume `three_nk=False` guarantees plaintext.

## Performance Bottlenecks

### Sequential Execution of Up to 32 External HTTP Feeds Under a 20-Minute CI Timeout

- **Problem:** `run_price_fetch()` (`src/ets2_realism/fetch/pipeline.py:302-380`) invokes all 4 FX providers, up to 10 European fuel feeds (including 5 sequential city requests for `de_tankerkoenig` and 50 MiB JSON for `es_miteco`), 8 Global Tier 1 feeds, and 10 Tier 2 national portal scrapers **synchronously and sequentially** on a single `httpx.Client` inside `.github/workflows/phase-a-release.yml` (`timeout-minutes: 20`).
- **Files:** `src/ets2_realism/fetch/pipeline.py`, `src/ets2_realism/fetch/http.py`, `src/ets2_realism/fetch/national.py`, `src/ets2_realism/fetch/global_tier1.py`, `src/ets2_realism/fetch/tier2_portals.py`, `.github/workflows/phase-a-release.yml`
- **Cause:** With `DEFAULT_TIMEOUT_SECONDS = 20.0` and `DEFAULT_MAX_RETRIES = 2` (3 attempts + backoff per request, and 2–5 requests per portal for landing + attachment downloads), 8–10 slow/tarpitting Tier 2 or Global government portals can add `8–12+` minutes of serial blocking time on top of quality gates (`ruff` + `basedpyright` + `634` pytest tests) and dual-edition builds/validation, risking a `20`-minute GitHub Actions timeout.
- **Improvement path:** Use bounded `concurrent.futures.ThreadPoolExecutor` (or `asyncio`/`httpx.AsyncClient` with per-host semaphores) to fetch independent Global Tier 1 and Tier 2 feeds concurrently with a total wall-clock budget, or cap Tier 2 `timeout` to `10s` with `max_retries=1` since Tier 2 failures are non-blocking.

### Eager Full-Archive Indexing in Generic `VfsStack._ensure_index()`

- **Problem:** First access on a generic `VfsStack` triggers `_ensure_index()` (`src/ets2_realism/vfs/stack.py:240-273`), enumerating every path and calling `get_meta()` across all layers.
- **Files:** `src/ets2_realism/vfs/stack.py`, `src/ets2_realism/vfs/cityhash.py`, `src/ets2_realism/baseline/extractor.py`
- **Cause:** Pure-Python `cityhash64` BFS traversal over ETS2 `def.scs` (`66,066` entries) plus full decompression of all `12,942` sign boards in `extract_baseline()` (`baseline/extractor.py:304-317`) makes local baseline verification take ~35–40s. (`compose-local` mitigates this for 500-mod combos using `_ComboScopedArchive`, `DirectoryArchive(include_top_dirs=...)`, and `_BaseHashFsArchive.list_direct_files()`.)
- **Improvement path:** Add optional `index_prefixes` directly to `VfsStack` and defer `get_meta()` until entry access so all callers benefit without needing wrapper archives.

### Repeated Full-Document SII Re-Scans & Slow Instrumented `pytest-cov` Runs

- **Problem:** Every individual `SiiDocument` mutation (`set_scalar`, `update_attribute_value`, `remove_attribute_line`) runs a full `scan_sii_structure()` (`src/ets2_realism/sii/document.py:112-136`, amplified in nested lane loops in `src/ets2_realism/sii/speed_limits.py:152-178`). Additionally, multiple integration tests (`tests/test_license_taint_gate.py`, `tests/test_package_builder.py`, `tests/test_promods_builder.py`, `tests/test_publish_release.py`, `tests/test_validate_workshop.py`) each build and offline-validate full 460-board × 43-locale packages from scratch, causing full `pytest-cov` runs on Windows to take `>5` minutes (even with `COVERAGE_CORE=sysmon`) because pure-Python SII lexing/hygiene loops run under bytecode tracing.
- **Files:** `src/ets2_realism/sii/document.py`, `src/ets2_realism/sii/speed_limits.py`, `tests/test_license_taint_gate.py`, `tests/test_package_builder.py`, `tests/test_promods_builder.py`, `tests/test_publish_release.py`
- **Cause:** Unbatched sequential span edits and unshared per-test full-package fixtures.
- **Improvement path:** Batch edits via `_apply_reverse_edits()` in `speed_limits.py`, and use module/session-scoped read-only built-package fixtures across validator/taint tests to cut coverage runtime sharply.

## Fragile Areas

### Unverified Live-Network Execution Across All 32 FX/Fuel Collectors & 10 Tier 2 Portals

- **Files:** `src/ets2_realism/fetch/fx.py`, `src/ets2_realism/fetch/ec_bulletin.py`, `src/ets2_realism/fetch/national.py`, `src/ets2_realism/fetch/global_tier1.py`, `src/ets2_realism/fetch/tier2_portals.py`, `state/prices.lock.json`, `state/published.json`
- **Why fragile:** `state/published.json` is still empty (`{"editions": {}, "schema_version": 1}`) and `state/prices.lock.json` is 100% pre-launch seeded (`39` `baseline_1.62_seeded` + `37` `promods_curated_seed` + `149` `tier3_curated_baseline`, `alerts: []`). None of the 32 external endpoints (especially dynamic HTML/XLSX scrapers for EC WOB, UK DESNZ, JP METI, CO CREG, and the 10 Tier 2 portals `anre.md`, `erc.org.mk`, `rosstat.gov.ru`, `gov.il`, `moei.gov.ae`, `cefgroup.co.za`, `aramco.com`, `nigerianstat.gov.ng`, `pxweb.bfs.admin.ch`) have been exercised in a live scheduled GitHub Actions run. Real-world WAFs, TLS/geo-blocks from `ubuntu-latest` IPs, HTML table changes, or CMS URL rotations can break individual collectors on first live execution.
- **Safe modification:** Keep every Global Tier 1 and Tier 2 feed strictly isolated behind warning-only circuit breakers and never widen the EU Core hard-fail gate; run a manual `workflow_dispatch` dry-run on GitHub Actions to validate live responses and fix selector/endpoint drift (starting with `ch_bfs_lik`).
- **Test coverage:** 100% offline mocked `httpx.MockTransport` tests only; zero live-network canary tests.

### Synchronized 180-Day Staleness Cliff for All 186 Curated Tier 3 Baselines

- **Files:** `data/curated/tier3_fuel_baselines.json`, `src/ets2_realism/normalize/lockfile.py:135-148`
- **Why fragile:** Every one of the `186` entries in `data/curated/tier3_fuel_baselines.json` shares the exact same `verified_date: "2026-11-25"`. On `2027-05-25` (`+181` days), all territories remaining on Tier 3 / `promods_curated_seed` will cross `TIER3_CURATED_STALE_DAYS = 180` simultaneously, triggering a permanent `stale_tier3_curated` rollup warning across every changelog, Step Summary, and Release PR until manually re-verified.
- **Safe modification:** Plan a semi-annual Tier 3 refresh cycle (or stagger regional audits) and verify `IR`/`VE` `clamped_to_floor: true` (`0.010 EUR/L`) invariants whenever updating `tier3_fuel_baselines.json`.

### ETS2 `1.63+` Baseline, HashFS v2 Compression, and Community Map-Mod Schema Coupling

- **Files:** `data/baselines/ets2_1.62_def/`, `src/ets2_realism/baseline/extractor.py:49-55,304-354`, `src/ets2_realism/vfs/hashfs.py:576-586`, `src/ets2_realism/validate/invariants.py:32-44`, `src/ets2_realism/merge/promods_fuel.py:49-135`, `src/ets2_realism/merge/hardcoded_totems.py:39-52`
- **Why fragile:**
  - Baseline extraction relies on `_FUEL_BOARD_PREFIXES` (`gas_`, `es_95_`, `es_diesel_`, `pt_95_`, `pt_diesel_`), keyword heuristics, and `b"@@fp_"` scans; new ETS2 `1.63+` fuel boards using different naming or placeholder text could be missed.
  - `HashFsV2Archive` only implements compression nibbles `0` (stored) and `1` (zlib); if SCS adopts Zstd/GDeflate in a future ETS2 update, `extract_baseline` and local ProMods discovery will fail with `UnsupportedCompressionError`.
  - `validate/invariants.py` hardcodes 1.62-specific invariants (Iceland 5-axle 60t / 80 km/h, 6 `D-09` exact board token mappings, 36 Vanilla countries, 43 locales).
  - `merge/promods_fuel.py` relies on curated prefix maps (`PM_EU_PREFIX_TO_ISO2`, `PM_ME_PREFIX_TO_ISO2`, `PM_TGS_PREFIX_TO_ISO2`, including collision guard `mn=ME` vs `mn=MN`) and `merge/hardcoded_totems.py` hardcodes `JRR_NUMERIC_BOARD_SIGNATURES` and `_COMMUNITY_NUMERIC_BOARD_RE`; ProMods/JRR/7RM renames require coordinated map updates.
- **Safe modification:** Always run `ets2-realism baseline extract --check` against local ETS2 archives after each game patch, inspect `excluded_fuel_keyword_boards` and `total_sign_boards` in `data/baselines/ets2_1.62_def/manifest.json`, and run `@pytest.mark.local_promods` after ProMods updates.

### Hardcoded Windows Workstation Paths & `VfsStack` Opt-In DLC Scoping

- **Files:** `src/ets2_realism/baseline/extractor.py:46`, `src/ets2_realism/merge/promods_discovery.py:15`, `src/ets2_realism/merge/load_order.py:388-389`, `src/ets2_realism/vfs/stack.py:100-123`, `src/ets2_realism/cli.py:77-110`
- **Why fragile:** Default paths hardcode maintainer-specific Windows drives (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`, `D:\ETS2Data\Euro Truck Simulator 2\mod`, `D:\SteamLibrary\steamapps\workshop\content\227300`), which fail on Linux/macOS or non-`D:` Windows installs unless `ETS2_GAME_DIR`, `ETS2_MOD_DIR`, `ETS2_WORKSHOP_DIR`, or CLI flags are set. Separately, `VfsStack` only flattens `dlc_<id>/` paths when `enabled_dlcs` is explicitly passed, and `ets2-realism vfs inspect` does not expose `--enable-dlc`; if ETS2 `1.63+` moves `country_data` inside `dlc_<id>/def/country/`, `extract_baseline` and `vfs inspect` will require explicit `enabled_dlcs` wiring.

### OSM Speed-Limit Audit Upstream & Allowlist Maintenance

- **Files:** `src/ets2_realism/audit/osm_speeds.py:39-99`, `src/ets2_realism/audit/overpass.py:28-35`, `data/laws/speed_audit_allowlist.json`
- **Why fragile:** `osm_speeds.py` depends on the third-party `westnordost.github.io/osm-legal-default-speeds/legal_default_speeds.json` schema and heuristic filter-string classification (`_GENERAL_FILTERS`, `_SKIP_SUBRULE_TOKENS`, `_CONDITIONAL_NON_GENERAL_RE`), while opt-in `--overpass` calls the public rate-limited `overpass-api.de` instance. `data/laws/speed_audit_allowlist.json` currently contains only `11` entries (covering `DE`, `EE`, `FI`, `IM`, `LT`); the first live monthly audit across all `225` territories will likely surface many legitimate statutory/abstraction differences requiring clean-room allowlist triage.

## Scaling Limits

### Archive, Payload, and Text Memory Ceilings

- **Current capacity:**
  - HashFS v2 tables: `MAX_V2_TABLE_BYTES = 64 MiB` (~4.19M entries / ~16.7M metadata words; ETS2 `1.62.3.3s` `def.scs` has `66,066` entries).
  - Single archive/file reads: `128 MiB` across `HashFs*`, `ZipArchive`, and `DirectoryArchive`; `64 MiB` for `profile.sii`, `game.log.txt`, `RealismSnapshot`, and `audit/taint.py` text scans; `1 MiB` for `VfsStack` empty-stub inspection (`MAX_STUB_INSPECT_BYTES`).
  - HTTP / OOXML caps: `30 MiB` default HTTP (`50 MiB` for `es_miteco`), `20 MiB` compressed / `64 MiB` uncompressed / `256` entries / `5,000` rows for `.xlsx`.
- **Limit:** Multi-GB monolithic `base.scs` / map-asset archives can exceed `64 MiB` HashFS table caps if mounted unfiltered; single community map files `> 128 MiB` or JSON station feeds `> 50 MiB` (`es_miteco` ~12k stations) will fail bounded-read checks.
- **Scaling path:** Keep `compose-local` restricted to `def/` and `locale/` via `_ComboScopedArchive` and `DirectoryArchive(include_top_dirs=...)`; stream very large station JSON/CSV feeds incrementally if `es_miteco` or `br_anp` grows past `50 MiB`.

### Global Territory, Hyperinflationary Currency, and Map-Combo Maintenance Scale

- **Current capacity:** `225` canonical country laws (`data/laws/countries/*.json`), `151` ISO-4217 currencies (`data/mappings/currencies.json`), `186` Tier 3 curated fuel baselines (`data/curated/tier3_fuel_baselines.json`), `119` map-mod aliases (`data/mappings/country_aliases.json`), and verified compatibility against a `503`-mod local combo (`86` touching country/speed/totem defs, `12` protected `AEM!`/encrypted archives).
- **Limit:** Static FX sanity bands in `data/mappings/currencies.json` (e.g., `ARS`, `IRR`, `LBP`, `SYP`, `TRY`, `VES`, `ZWG`) can be breached over 12–24 months by severe inflation or currency redenominations, causing `fx_sanity_rejected` fallbacks until bands are updated. Likewise, the `12` local `AEM!`/encrypted community mods cannot be automated without user-supplied `--unpacked-defs` directories.
- **Scaling path:** Review `extended_fx_alerts` rollups in weekly Step Summaries to adjust redenominated currency bands proactively, and expand `data/mappings/country_aliases.json` as new map mods emerge.

## Dependencies at Risk

### Locked Python Runtime & Dev Toolchain (`pyproject.toml`, `uv.lock`)

- **Current footprint:** `28` locked packages in `uv.lock` (`5` runtime: `httpx>=0.28,<0.29`, `openpyxl>=3.1,<4`, `pillow>=12,<14`, `pydantic>=2.14,<3`, `tzdata>=2025.2`; `5` dev: `basedpyright>=1.40,<2`, `pytest>=9.2,<9.3`, `pytest-cov>=6,<8`, `ruff>=0.16`, `types-openpyxl>=3.1`; build backend `hatchling>=1.27,<2`). Zero GPL dependencies.
- **Risk:**
  - `httpx>=0.28,<0.29` pins a single minor version and blocks upgrades to `0.29+` / `1.0` without manual constraint updates.
  - `tzdata>=2025.2` freezes the IANA timezone database inside `uv.lock`; countries changing DST laws (e.g., future EU/MENA/Latin America DST abolitions) will not take effect until `uv lock --upgrade-package tzdata` is run.
  - `pillow>=12,<14` relies on an upper bound aligned with Pillow 12/13; major Pillow releases require verification of deterministic baseline RGB EXIF/ICC-stripped JPEG output (`276x162`).

### External Free Data Providers With No SLA

- **Risk:** Several critical live feeds are community-hosted with no uptime or stability SLA:
  - **`@fawazahmed0/currency-api`** (`cdn.jsdelivr.net` + `latest.currency-api.pages.dev`, `src/ets2_realism/fetch/fx.py:43-46`): sole live FX source for ~120 non-ECB extended global currencies. If both mirrors fail or stop updating, all 120+ extended currencies freeze on `state/prices.lock.json` rates.
  - **`fuel-prices.eu`** (`ec_bulletin.py:66`) & **`FionnHughes/eu-weekly-oil-bulletin`** (`ec_bulletin.py:59`): primary live fallback for non-EU European territories and EC WOB outages.
  - **`gasvaktin/gasvaktin`** (`tier2_portals.py:47`), **`westnordost.github.io/osm-legal-default-speeds`** (`audit/osm_speeds.py:39`), and **`overpass-api.de`** (`audit/overpass.py:29`).
- **Impact:** Outages do not fail Core European CI (EU Core FX uses `Frankfurter v2` + `ECB XML` + `CBR XML`; fuel uses `EC WOB` + 7 national Tier 1 APIs), but extended global FX/fuel and monthly OSM audits degrade gracefully to lockfile/warning state.
- **Migration plan:** Circuit breakers and `state/prices.lock.json` cushion temporary outages; if `fawazahmed0` ever retires, add an alternative open multi-currency FX feed (e.g., IMF / Open ER-API) behind `normalize/fx.py`.

### Operational Local & Optional External Dependencies

- **Local ETS2 `1.62.3.3s` archives (`VFS-02`):** Maintainer machine needs `def.scs` and `locale.scs` (`ETS2_GAME_DIR` / `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`) to refresh `data/baselines/ets2_1.62_def/` after game patches and run `@pytest.mark.local_ets2`.
- **Local ProMods & map-combo archives (`MAP-01`, `MAP-03`):** Building ProMods Companion Editions (`ets2-realism package promods`), running `ets2-realism compose-local`, and executing `@pytest.mark.local_promods` require user-installed ProMods (`EU`/`ME`/`MA`/`TGS` `def`/`defmap`/`assets`) and combo archives in `ETS2_MOD_DIR` (`D:\ETS2Data\Euro Truck Simulator 2\mod`).
- **Manual `SCS Workshop Uploader` (`AppID 421800`, `PUB-03`):** Not installed on the current local workstation. Every Phase A release requires a maintainer to download the `phase-a-release-bundle` artifact, upload `dist/workshop/{summer,winter}/` manually via `AppID 421800`, and only then merge the persistent `release/phase-a-weekly` PR.
- **Optional CI API keys (`DAT-02`, `GLB-01`):** `TANKERKOENIG_API_KEY` (DE multi-grade), `EIA_API_KEY` (US), `OPINET_API_KEY` (KR), and `CNE_API_TOKEN` (CL v4). Without them configured in GitHub Actions secrets, `DE` falls back to EC WOB, `US`/`KR` remain on Tier 3 curated baselines, and `CL` falls back to CNE v3/Tier 3.

## Missing Critical Features

### Deferred V2 Automated Steam Workshop Publishing (`PUB-V2-01`, `PUB-V2-02`)

- **Problem:** Phase A stops at validated Workshop artifacts, rolling `snapshots-latest` GitHub Releases, and a persistent Release PR; actual Steam Workshop uploads are still manual via `SCS Workshop Uploader` (`AppID 421800`).
- **Blocks:** Fully hands-free Friday Workshop publishing via `steamcmd +workshop_build_item` with inline post-self-update 30s TOTP (`STEAM_SHARED_SECRET`), isolated Summer/Winter matrix jobs, and multi-day hidden-item (`visibility: 2`) verification (`PUB-V2-01`, `PUB-V2-02` in `.planning/STATE.md:58-59`).

### First Live End-to-End Production Release & Workshop Upload Verification

- **Problem:** `state/published.json` has never recorded a live release (`editions: {}`), `state/prices.lock.json` contains zero live-fetched entries yet, `.github/workflows/phase-a-release.yml` has not run end-to-end against live upstream APIs or pushed a real `snapshots-latest` GitHub Release, and generated Workshop bundles have not yet been uploaded through real `AppID 421800` / tested in ETS2 `1.62.3.3s` `game.log.txt`.
- **Blocks:** Production confidence across live upstream feed behavior, real Steam Workshop ingestion, and in-game rendering verification of all 460 Zero-DDS boards and ProMods `pm*_fuel` modules.

### Standalone Wheel / Non-Editable Packaging for End-Users

- **Problem:** Users running `ets2-realism compose-local` or `ets2-realism package promods` cannot install a standalone wheel (`pipx` / `uv tool install`) because `data/` and `assets/` are excluded from the wheel (`pyproject.toml:37-38`) and loaded via `parents[3]` (`src/ets2_realism/normalize/currencies.py:13-17`).
- **Blocks:** Frictionless distribution of the local CLI tool to ETS2 players outside a developer Git checkout.

## Test Coverage Gaps

The test suite comprises `45` test modules (`24,654` LOC, `437` test functions expanding to **`638` collected tests**: `634` CI-safe + `4` local-archive tests) with `0` `ruff` and `0` `basedpyright` strict errors.

### Unenforced Coverage Gate in CI & Slow Instrumented Coverage Execution

- **What's not tested / enforced:** `.github/workflows/ci.yml:40` runs `uv run pytest` with neither `--cov` nor `--cov-fail-under`, even though `pytest-cov` is declared in `pyproject.toml:32`. Meanwhile, running `pytest --cov=ets2_realism` locally on Windows exceeds `5` minutes because multiple tests rebuild and offline-validate complete 460-board × 43-locale packages under bytecode coverage tracing.
- **Files:** `.github/workflows/ci.yml`, `pyproject.toml`, `tests/test_license_taint_gate.py`, `tests/test_package_builder.py`, `tests/test_promods_builder.py`, `tests/test_publish_release.py`
- **Risk:** Silent coverage regressions can slip into PRs undetected, and slow local coverage runs discourage developers from checking branch coverage.
- **Priority:** Medium.

### Zero Live-HTTP Contract / Canary Tests for External Feeds

- **What's not tested:** All `32` FX/fuel collectors and the OSM/Overpass/Taginfo audit clients are verified solely against handcrafted mock payloads via `httpx.MockTransport`. No opt-in `@pytest.mark.live_network` canary test exists to verify real upstream URLs, HTTP verbs (which allowed the `CH_BFS_LIK_URL` `GET`-vs-`POST` bug to pass offline tests), TLS chains, or CMS selectors.
- **Files:** `tests/test_fetch_fx.py`, `tests/test_fetch_fuel.py`, `tests/test_fetch_global_tier1.py`, `tests/test_fetch_tier2_portals.py`, `tests/test_audit_osm_speeds.py`, `src/ets2_realism/fetch/tier2_portals.py`
- **Risk:** Upstream URL/schema/method mismatches remain invisible until a live Friday `phase-a-release.yml` or monthly `osm-speed-audit.yml` run fails or degrades to fallback.
- **Priority:** High.

### CI-Skipped Local-Archive & Platform-Specific Tests (`4` of `638` Tests + Windows Junctions)

- **What's not tested on CI (`ubuntu-latest`):**
  - `2` `@pytest.mark.local_ets2` tests (`tests/test_baseline_contracts.py:264,271`) testing zero-diff baseline extraction and 36-country surgical SII round-trips against real `def.scs`/`locale.scs`.
  - `2` `@pytest.mark.local_promods` tests (`tests/test_promods_builder.py:773`, `tests/test_compose_local.py:1065`) testing real local ProMods Companion build/validation and real local `mod/` combo dry-run. Note that `tests/test_promods_builder.py:782-811` substitutes a synthetic 1-country UK `eu_def` fixture whenever local `promods-eu-def-*.scs` is absent, partially masking real EU def edge cases.
  - Real Windows NTFS directory junction pruning in `src/ets2_realism/vfs/dir_archive.py` and `src/ets2_realism/publish/ledger.py` does not execute on Linux CI runners.
- **Files:** `tests/test_baseline_contracts.py`, `tests/test_promods_builder.py`, `tests/test_compose_local.py`, `src/ets2_realism/vfs/dir_archive.py`, `src/ets2_realism/publish/ledger.py`
- **Risk:** Real ETS2 `1.63+` or ProMods format changes and Windows-only filesystem regressions will not surface in GitHub Actions PR checks.
- **Priority:** Medium-High.

### Residual Edge-Case & Packaging Test Gaps

- **What's not tested:**
  - External-CWD invocation of `assert_out_dir_not_tracked()` / `compose_local()` / `build_promods_edition()` from a non-repo working directory (`src/ets2_realism/merge/promods_builder.py:82-110`).
  - Built wheel (`uv build --wheel`) installation and import smoke test (currently fails due to missing `data/` package data).
  - Full `phase-a-release.yml` `--previous-snapshots-dir` incremental diff path (wired in `cli.py:593-608`, unwired in workflow).
  - Phase 1 low-level error branches in `src/ets2_realism/vfs/dir_archive.py` (broken symlinks, post-scan root-escape), `src/ets2_realism/vfs/hashfs.py` (truncated v1/v2 headers, corrupt metadata spans), `src/ets2_realism/sii/lexer.py` (malformed comment/string/include diagnostics), `src/ets2_realism/sii/document.py` (interleaved array `ValueError` guards, same-line brace edits), and `src/ets2_realism/sii/speed_limits.py` (orphan/duplicate lane errors).
- **Files:** `src/ets2_realism/merge/promods_builder.py`, `src/ets2_realism/cli.py`, `src/ets2_realism/vfs/dir_archive.py`, `src/ets2_realism/vfs/hashfs.py`, `src/ets2_realism/sii/lexer.py`, `src/ets2_realism/sii/document.py`, `src/ets2_realism/sii/speed_limits.py`
- **Risk:** Edge-case failures on malformed community `.scs` mods or end-user external-CWD CLI runs.
- **Priority:** Medium.

---

*Concerns audit: 2026-11-26*
