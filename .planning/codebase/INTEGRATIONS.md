# External Integrations

**Analysis Date:** 2026-11-16

> **Scope Boundary (Phase 1 Implemented vs Phases 2–5 Planned):** Implemented codebase modules under `src/ets2v2/` perform **zero network or remote API calls** and integrate strictly with local ETS2 `1.62.3.3s` archives, clean-room repository JSON baselines (`data/baselines/ets2_1.62_def/`), vendored wiki docs (`.agents/skills/scs-modding-wiki/`), and GitHub Actions CI (`.github/workflows/ci.yml`). Downstream external data APIs and publishing targets documented in `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and `.planning/research/SUMMARY.md` are listed in clearly labeled **Planned** subsections below.

## APIs & External Services

**Implemented (Phase 1 — Local / Offline Only):**
- **SCS Modding Wiki Offline Mirror** (`.agents/skills/scs-modding-wiki/SKILL.md`) - Vendored 162-page documentation snapshot (`index.json`, `sources.json`, `docs/`) covering SCS `.sii`/`.sui` units, Workshop Uploader validation rules, and archive formats. Used by planning/research agents per `.planning/config.json`.
- **Network / HTTP APIs:** None implemented in `src/ets2v2/` (Phase 1 has zero HTTP clients or external API calls).

**Planned Downstream External APIs (Phases 3 & 5 — Not Implemented in Phase 1):**
- **Currency Exchange Rates (Phase 3, `DAT-01`):**
  - `Frankfurter v2` (`MIT`, 219 currencies) — planned primary FX converter (`eur_per_liter` vs `local_display_price`).
  - `ECB eurofxref-daily.xml` — planned secondary FX validator.
  - `fawazahmed0/exchange-api` (`CC0 1.0`) and `CBR XML` (`XML_daily.asp`) — planned fallback and `RUB`/`BYN`/`KZT`/`UZS` cross-check feeds.
- **Tier 1 Open European & EEA Fuel Feeds (Phase 3, `DAT-02`):**
  - `EC Weekly Oil Bulletin` (`CC BY 4.0`, dynamic `.xlsx` discovery) with `FionnHughes` / `fuel-prices.eu` (`CC BY 4.0`) fallbacks.
  - `UK DESNZ` Weekly Road Fuel (`OGL v3`) and `Norway SSB` Table `09654` (`CC BY 4.0`).
  - National multi-grade APIs: France (`prix-carburants.gouv.fr`, *Licence Ouverte*), Germany (`Tankerkönig`, `CC BY 4.0`, optional free API key per `.planning/STATE.md`), Spain (`MITECO`), Italy (`MIMIT`, *IODL 2.0*), and Netherlands (`CBS StatLine`).
- **Tier 1 Non-EU Government Fuel APIs (Phase 5, `GLB-01`):**
  - `US EIA v2` (`Public Domain`, optional API key), `BR ANP`, `AR Energía`, `CO SICOM`, `CL CNE`, `MY OpenDOSM` (`CC BY 4.0`), `JP METI`, and `KR KNOC Opinet` (optional API key per `.planning/STATE.md`).
- **Tier 2 Guarded National Portals (Phase 5, `GLB-02`):**
  - Isolated per-country portal collectors (`CH BFS/LIK`, `MD ANRE`, `MK ERC`, `RU Rosstat`, `AZ`/`BY`, `IS Orkusetur`, `ID Pertamina/ESDM`, `IL MoE/CBS`, `GCC`/`EG`, `ZA DMRE`, `KE EPRA`, `NG NBS`) backed by circuit-breaker fallbacks.
- **CI-Only Speed-Limit Audit Source (Phase 5, `GLB-04`):**
  - OSM Overpass / Taginfo (`westnordost/osm-legal-default-speeds`, `CC BY-SA 2.0`) — planned strictly as an isolated CI drift-audit report so zero `CC BY-SA` data enters `CC BY 4.0` mod outputs.
- **Explicitly Excluded / Rejected External Services (`.planning/REQUIREMENTS.md`):**
  - `GlobalPetrolPrices.com` (`CC BY-NC-ND 3.0`), `MyLPG.eu` (scraping prohibited), paid `IEA` commercial feeds, `3nK` decryption of third-party mods (`3668352310`), and copyleft GPL extractors (`TruckLib`/`Extractor`, `easy-scsmodmanager`).

## Data Storage

**Implemented — Local ETS2 `1.62.3.3s` Archive Inputs (`src/ets2v2/vfs/`, `src/ets2v2/baseline/`):**
- **Target Game Directory:** Defaults to `DEFAULT_ETS2_GAME_DIR = Path(r"D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2")` in `src/ets2v2/baseline/extractor.py`, overridable via `ETS2_GAME_DIR` environment variable (`resolve_game_dir()`) or `--game-dir` CLI option (`src/ets2v2/cli.py`).
- **Consumed Game Archives:**
  - `version.scs`, `def.scs`, and `locale.scs` (HashFS v2 `SCS#\x02`, method `CITY`, read via `HashFsV2Archive` in `src/ets2v2/vfs/hashfs.py`, with explicit `seeded_prefixes=("locale",)` walking for stripped-root `locale.scs`).
  - `dlc_*.scs` (`107` DLC archives audited by `_audit_dlc_archives()` in `src/ets2v2/baseline/extractor.py` for `def/country*` presence).
- **Generic Local Mod Containers (`src/ets2v2/vfs/`):**
  - Supports HashFS v1 (`HashFsV1Archive`), HashFS v2 (`HashFsV2Archive`), standard ZIP / ZIP-wrapped `.scs` (`ZipArchive` in `src/ets2v2/vfs/zip_archive.py`), unpacked filesystem trees (`DirectoryArchive` in `src/ets2v2/vfs/dir_archive.py`), and priority-ordered multi-layer overlays (`VfsStack` in `src/ets2v2/vfs/stack.py`) handling `base/` mount normalization, `dlc_<id>/` scoping, and empty `SiiNunit {}` stubs.
  - Refuses to decrypt or crack `3nK\x01` (`detect_3nk()`), `AEM!` headers (`ProtectedArchiveStub`), or password-encrypted ZIPs (`flag_bits & 0x41` in `ZipArchive`), emitting typed `ArchiveDiagnostic` records and raising `ProtectedPayloadError` (`src/ets2v2/vfs/types.py`).

**Implemented — Clean-Room JSON Baseline Storage (`data/baselines/ets2_1.62_def/`):**
- `data/baselines/ets2_1.62_def/manifest.json` - Extraction metadata (`application: "eut2"`, `game_version: "1.62.3.3"`, `extractor_schema_version: 1`, counts for `66066` `def.scs` entries, `521` `locale.scs` entries, `12942` total sign boards, `107`-entry `dlc_country_audit`, and deterministic `file_sha256s`).
- `data/baselines/ets2_1.62_def/countries.json` - `36` Vanilla+DLC `country_data` definitions (`BaselineCountry` schema in `src/ets2v2/baseline/models.py`).
- `data/baselines/ets2_1.62_def/speed_limits.json` - `36` country `speed_limits.sii` blocks (`car`, `truck`, `bus`, `train`, `tram` via `BaselineSpeedLimit`).
- `data/baselines/ets2_1.62_def/fuel_boards.json` - `461` single-text fuel totem boards (`373` `active_fp` + `88` `placeholder`/`blank`) plus `5` excluded multi-item highway boards (`fi_oulu_95`, `fi_oulu_98`, `rs_fuel_01`, `ru_m_95`, `ru_m_98`).
- `data/baselines/ets2_1.62_def/locales.json` - `43` active ETS2 `1.62` locales (excluding dead `fr_qc`, including `fr_ca`), `12` `tz_*` keys, and `99` `fp_*` fallback keys.
- **Clean-Room Enforcement:** Raw `.sii`/`.sui` files are strictly prohibited under `data/` (`verify_baseline_bundle()` in `src/ets2v2/baseline/extractor.py` and `test_no_raw_scs_files_committed_under_data` in `tests/test_baseline_contracts.py`). Optional `--raw-cache-dir` in `ets2v2 baseline extract` (`src/ets2v2/cli.py`) enforces CWD-independent rejection of paths inside `data/` or overlapping `--out-dir` (targeting gitignored directories such as `build/`).

**Planned Downstream Storage & Local Mod Inputs (Phases 2–4):**
- `data/laws/` and `data/mappings/` (Phase 2, `SIM-01`) - Canonical seasonal country realism registry.
- `state/published.json` (Phase 2, `PUB-02`) - Canonical payload SHA-256 diff ledger preventing no-op updates.
- `prices.lock.json` (Phase 3, `DAT-03`) - Circuit-breaker last-known-good price cache.
- `realism-snapshot-{summer|winter}.json` (Phase 4, `MAP-02`) - Versioned snapshot decoupling CI data ingestion from local patch generation.
- Local ProMods & User Map Combo Directories (Phase 4, `MAP-01`, `MAP-03`, never tracked in Git): Maintainer/user local `D:\ETS2Data\Euro Truck Simulator 2\mod` containing `promods-eu-def-v284.scs`, `promods-me-defmap-v284.scs`, `promods-ma-defmap-v104.scs`, `promods-tgs-defmap-v170.scs`, and user combo archives/load-order inputs (`profile.sii` / `game.log.txt`) consumed offline by `ets2v2 compose-local` to emit `zz_ETS2V2_ComboPatch_{Summer|Winter}.scs` (`.planning/STATE.md`, `.planning/ROADMAP.md`).

**Databases & Caching:**
- **Databases:** None (pure filesystem + JSON artifacts).
- **Caching:** In-memory per-stack index and empty-stub cache (`_index`, `_stub_cache`) inside `VfsStack` (`src/ets2v2/vfs/stack.py`); GitHub Actions `astral-sh/setup-uv@v5` dependency caching (`enable-cache: true` in `.github/workflows/ci.yml`).

## Authentication & Identity

**Implemented (Phase 1):**
- None. All Phase 1 commands run locally and read-only against filesystem paths/archives.
- `.github/workflows/ci.yml` enforces minimal token scope: `permissions: contents: read`.

**Planned Downstream (Phases 3, 5 & Deferred V2):**
- Optional free API keys for enhanced data sources (`Tankerkönig` in Phase 3; `US EIA v2` and `KR KNOC Opinet` in Phase 5 per `.planning/STATE.md`).
- **Phase A Semi-Auto Publishing (Phase 2, `PUB-03`):** Stores **zero Steam credentials** in GitHub Actions; builds validated `dist/workshop/{summer,winter}/` bundles for manual GUI upload via `SCS Workshop Uploader` (`AppID 421800`, `.planning/STATE.md`).
- **Phase B Full-Auto Publishing (Deferred Post-V1, `PUB-V2-01`):** Deferred `steamcmd +workshop_build_item` / `m00nl1ght-dev/steam-workshop-deploy@v4` with inline 30s TOTP (`STEAM_SHARED_SECRET`) and `steam-workshop-prod` GitHub Environment approval.

## Monitoring & Observability

**Error Tracking & Diagnostics:**
- **Implemented:** No external error-tracking SaaS. Diagnostics are emitted as frozen Pydantic `ArchiveDiagnostic` records (`src/ets2v2/vfs/types.py`), `SiiDiagnostic` hygiene records (`src/ets2v2/sii/hygiene.py`), CLI exit codes/stderr messages (`src/ets2v2/cli.py`), and `verify_baseline_bundle()` SHA-256 integrity checks (`src/ets2v2/baseline/extractor.py`).
- **Planned:** `0.01–5.00 EUR/L` price bounds and `±25%` change/staleness alerts (`DAT-03`), Offline SCS Workshop Validator (`00001`–`00010` + `WARN 00001`/`00002`, `PUB-01`), and CI-only OSM speed-limit drift audit reports (`GLB-04`).

**Logs:**
- Standard stdout/stderr console output in `src/ets2v2/cli.py` and GitHub Actions job logs (`.github/workflows/ci.yml`).

## CI/CD & Deployment

**Implemented CI Pipeline (`.github/workflows/ci.yml`):**
- **Triggers:** `push` on `master` and `main`; all `pull_request` events.
- **Runner & Limits:** `ubuntu-latest`, `timeout-minutes: 15`, `permissions: contents: read`.
- **Toolchain Setup:** `actions/checkout@v4` followed by `astral-sh/setup-uv@v5` (`enable-cache: true`, `python-version: "3.12"`) and `uv sync --locked`.
- **Quality Gates:**
  1. `uv run ruff check`
  2. `uv run ruff format --check`
  3. `uv run basedpyright`
  4. `uv run pytest` (`tests/test_baseline_contracts.py` auto-skips `@pytest.mark.local_ets2` tests in CI via `_has_local_ets2()` while verifying all committed `data/baselines/ets2_1.62_def/` contracts).

**Planned Release Pipeline (Phase 2, `PUB-03` & `.planning/ROADMAP.md`):**
- Scheduled Friday `06:00 UTC` + manual `workflow_dispatch` GitHub Actions workflow producing validated `dist/workshop/summer/` and `dist/workshop/winter/` bundles (`universal/` or normalized `universal.zip`), `realism-snapshot-{summer|winter}.json`, and markdown changelogs gated by `state/published.json`.

## Environment Configuration

**Implemented Variables:**
- `ETS2_GAME_DIR` - Overrides `DEFAULT_ETS2_GAME_DIR` (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`) in `resolve_game_dir()` (`src/ets2v2/baseline/extractor.py`) when `--game-dir` is omitted.

**Secrets & Dotfiles:**
- No `.env` files, credentials files, or CI secrets are present or required in Phase 1.
- Future API keys (`Tankerkönig`, `US EIA`, `KR Opinet`) and deferred `STEAM_SHARED_SECRET` belong strictly in GitHub Actions Secrets / protected Environments, never in tracked files.

## Webhooks & Callbacks

**Incoming:**
- None (CLI and scheduled/push CI workflows only).

**Outgoing:**
- None (Phase 1 has zero outbound network integrations; Phases 3 and 5 plan outbound HTTP `GET` collection only).

---

*Integration audit: 2026-11-16*
