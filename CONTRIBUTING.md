<!-- generated-by: gsd-doc-writer -->
# Contributing to ETS2 Country Realism

Thank you for contributing to **ETS2 Country Realism** (`MissionWAR/ets2-country-realism`). See [README.md](README.md) for a high-level project overview and common CLI usage.

## Development Environment Setup

- **Prerequisites:** Python `>= 3.12` and [`uv`](https://docs.astral.sh/uv/)
- Clone your fork and install locked dependencies into `.venv`:

```bash
git clone https://github.com/<your-username>/ets2-country-realism.git
cd ets2-country-realism
uv sync --locked
```

- Verify the CLI entrypoint works offline:

```bash
uv run --offline ets2-realism --version
```

## Coding Standards & Mandatory Quality Gates

All pull requests are checked by `.github/workflows/ci.yml` on pushes to `master`/`main` and on pull requests (`ruff check`, `ruff format --check`, `basedpyright`, and `pytest`). Run the full local gate suite before opening a PR:

- **Linting (`ruff`, `line-length = 100`, rules `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF` in `pyproject.toml`):**
  ```bash
  uv run --offline ruff check
  ```
- **Formatting (`ruff format`):**
  ```bash
  uv run --offline ruff format --check
  ```
- **Strict static type checking (`basedpyright`, `typeCheckingMode = "strict"` across `src` and `tests`):**
  ```bash
  uv run --offline basedpyright
  ```
- **Test suite (`pytest` with `--strict-markers`):**
  ```bash
  # Default offline / CI-safe suite (excludes tests needing local game/map archives)
  uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"
  ```
  - Custom `pytest` markers declared in `pyproject.toml`:
    - `local_ets2`: tests requiring local ETS2 `1.62.3.3s` archives.
    - `local_promods`: tests requiring local ProMods or user map-combo archives.
- **Canonical country law & mapping registry validation:**
  ```bash
  uv run --offline ets2-realism registry validate
  ```
- **Clean-room license-taint audit:**
  ```bash
  uv run --offline ets2-realism audit taint
  ```
  (Add `--json` for machine-readable `TaintScanReport` output, or `--snapshot <path>` / `--package <path>` to also scan generated artifacts.)

## Clean-Room IP & Licensing Rules

This repository uses dual licensing (see [LICENSE](LICENSE)):
- **Source code & tooling (`src/`, `scripts/`, `tests/`):** MIT License.
- **Curated statutory registries & baseline data (`data/laws/`, `data/mappings/`, `data/curated/`):** CC BY 4.0.

To keep all code MIT-licensed and all curated data cleanly redistributable under CC BY 4.0, the following are **strictly prohibited**:

- **Proprietary map-mod files:** Never commit ProMods `.scs`, `.sii`, `.sui`, or extracted `def/` dumps from ProMods or any third-party map mod. ProMods Companion Editions are always compiled locally from a user's own installed archives.
- **Encrypted/protected archive cracking:** Never add decryption, key-extraction, or cracking code for `3nK`, `AEM!`, `ScsC`, or password-protected archives. The local composer reports protected archives transparently and accepts user-supplied `--unpacked-defs` directories instead.
- **`CC BY-SA` / `ODbL` / OpenStreetMap data in registries or mod outputs:** Never copy speed limits, notes, or URLs from OpenStreetMap, `westnordost/osm-legal-default-speeds`, or `CC BY-SA` / `ODbL` sources into `data/laws/`, `data/mappings/`, `data/curated/`, snapshots, or built mod packages. The internal `ets2-realism audit osm-speeds` command is strictly a read-only drift detector; every change to `data/laws/` must be verified against an official national statute or government portal.
- **`CC BY-NC-ND` and restricted fuel scrapers:** Never add scrapers, URLs, or data from `CC BY-NC-ND` or restricted aggregators such as `GlobalPetrolPrices`, `MyLPG`, or `IEA` (International Energy Agency).
- **GPL / strong-copyleft dependencies:** Do not introduce GPL or incompatible copyleft dependencies into `pyproject.toml` or `uv.lock`.

### Automated Enforcement (`ETS2R-INV-LICENSE-TAINT`)

Clean-room provenance is enforced automatically in two places using `FORBIDDEN_LICENSE_TAINT_PATTERNS` (`src/ets2_realism/audit/taint.py` and `src/ets2_realism/validate/invariants.py`):

1. **`ets2-realism audit taint`** scans text files (`.sii`, `.sui`, `.txt`, `.json`, `.md`, `.csv`, `.xml`, `.yml`, `.yaml`, `.toml`) under `data/laws/`, `data/curated/`, `data/mappings/`, `state/prices.lock.json`, `CHANGELOG_SUMMER.md`, `CHANGELOG_WINTER.md`, plus any `--snapshot` or `--package` targets.
2. **Offline SCS Workshop Validator (`ets2-realism validate workshop` / `validate local`)** runs `check_license_taint_bytes` over package text files and fails validation with error code `ETS2R-INV-LICENSE-TAINT` on any forbidden marker (`CC BY-SA`, `ODbL`, `OpenStreetMap`, `osm-legal-default-speeds`, `GlobalPetrolPrices`, `CC BY-NC-ND`, `MyLPG`, `IEA` / `International Energy Agency`).

## How to Contribute Data Updates

### 1. Country Statutory Speed Limits, DRL Rules, or Axle Limits (`data/laws/countries/<iso2>.json`)

Each territory has a lowercase ISO-3166 alpha-2 JSON record under `data/laws/countries/<iso2>.json` validated by `CountryLawRecord` (`src/ets2_realism/registry/models.py`):

- **Top-level fields:** `iso2` (uppercase), `iso3` (lowercase), `ets2_slug`, `iana_timezone`, `speed_unit` (`"kmh"` or `"mph"`), `currency` (ISO 4217), `driving_tired_offence` (`bool`), `mass_limit_per_axle_count` (3–12 non-decreasing integer kg values between `10000` and `150000`), `statutory_notes`, and `sources` (required non-empty list of official statutory or government URLs).
- **Seasonal rulesets (`summer` and `winter`):**
  - `lights_mandatory`: `true` if daytime running lights / dipped headlights are legally mandatory in that season, else `false`.
  - `speed_limits`: must define exact keys `car`, `truck`, and `bus`, each containing canonical `lane_speed_class` entries in order (`local_road`, `expressway`, `motorway`, and optionally `slow_road`) with `limit`, `urban_limit`, `max_limit` (must be `null` for `car`), and `uncommon`. Use `0` where a statute imposes no general ceiling (for example, German Autobahn car limits in `data/laws/countries/de.json`).
- **Verification steps:**
  1. Cite the official national traffic act or government transport authority URL in `sources` and summarize the rule in `statutory_notes`.
  2. Run `uv run --offline ets2-realism registry validate` and `uv run --offline ets2-realism audit taint`.

### 2. Map-Mod Country Slug Aliases (`data/mappings/country_aliases.json`)

To map a map-mod country slug to a canonical ISO-2 territory (or shield a sub-national slug from colliding with an unrelated European ISO-2 code during local map-combo resolution), add an alphabetically sorted entry under `aliases` in `data/mappings/country_aliases.json`:

```json
"can_islands": {
  "iana_timezone_override": "Atlantic/Canary",
  "iso2": "ES",
  "note": "ProMods EU Canary Islands (WET/WEST)"
}
```

- Keys must match `^[a-z0-9_]{1,64}$`.
- `iso2` must be a valid uppercase ISO-2 code present in `data/laws/countries/`.
- `iana_timezone_override` must be `null` or a valid IANA timezone identifier (e.g., `"Atlantic/Canary"`).
- Aliases are evaluated first by `CountryResolver` (`src/ets2_realism/merge/aliases.py`) before ISO-3/ISO-2 fallback matching, preventing sub-national slugs (such as Brazilian states) from colliding with European ISO-2 codes.

### 3. Intentional Statutory Differences (`data/laws/speed_audit_allowlist.json`)

When a verified national statute intentionally differs from OSM's single-season default speed model (for example, Finland's seasonal summer/winter car limits or Germany's unrestricted Autobahn encoded as `0`), record an entry in `data/laws/speed_audit_allowlist.json` (`SpeedAuditAllowlistEntry` in `src/ets2_realism/audit/models.py`):

```json
{
  "field": "limit",
  "iso2": "FI",
  "lane_speed_class": "motorway",
  "statutory_rationale": "Finnish Road Traffic Act (Tieliikennelaki 729/2018) seasonal Summer (120 km/h) vs Winter (100 km/h) motorway ceiling modeled via dual ETS2 seasonal editions.",
  "vehicle_class": "car",
  "verified_date": "2026-11-25"
}
```

- Allowed values: `vehicle_class` in `car | truck | bus`; `lane_speed_class` in `local_road | expressway | motorway`; `field` in `limit | urban_limit | max_limit`; `verified_date` as `YYYY-MM-DD`.
- `(iso2, vehicle_class, lane_speed_class, field)` keys must be unique.
- Never mention OSM or any forbidden taint marker inside `statutory_rationale`; cite only the governing national statute and ETS2 modeling rationale, then verify with `uv run --offline ets2-realism audit taint`.

## Pull Request Guidelines

- Branch from `master` and open your pull request targeting `master`.
- Follow Conventional Commits (e.g., `feat(laws): ...`, `fix(fetch): ...`, `docs: ...`, `chore(release): ...`).
- Keep changes focused and include unit tests under `tests/` for behavioral changes.
- Ensure all quality gates (`ruff check`, `ruff format --check`, `basedpyright`, `pytest`, `ets2-realism registry validate`, `ets2-realism audit taint`) pass locally before requesting review.
- For statutory or pricing-source changes, include official primary source URLs in the PR description.

## Issue Reporting

Report bugs, statutory law updates, or map-mod alias requests on [GitHub Issues](https://github.com/MissionWAR/ets2-country-realism/issues). Please include:

- ETS2 game version, mod edition (`Core`, `ProMods`, or `Combo Patch`), and season (`Summer` or `Winter`).
- Exact CLI command or mod load order and steps to reproduce.
- Expected vs. actual behavior (plus relevant `game.log.txt` excerpts or `--json` CLI output, without attaching proprietary `.scs` files).
- For statutory law reports, a link to the official national statute or government road-safety page.

## Maintainer Operations (Phase A Semi-Auto Weekly Release)

Weekly Core releases are orchestrated by `.github/workflows/phase-a-release.yml` (scheduled Fridays at `06:00 UTC` and manually triggerable via `workflow_dispatch` with optional `force_run`).

### Optional GitHub Actions Secrets

Configure these optional repository secrets under **Settings → Secrets and variables → Actions** to enable API-key-authenticated Tier 1 fuel feeds during `ets2-realism fetch` (the pipeline falls back gracefully if omitted):

| Secret | Feed |
| --- | --- |
| `TANKERKOENIG_API_KEY` | Germany Tankerkönig fuel prices |
| `EIA_API_KEY` | US EIA v2 fuel prices |
| `OPINET_API_KEY` | South Korea KNOC Opinet fuel prices |
| `CNE_API_TOKEN` | Chile CNE fuel prices |

### Required GitHub Actions Repository Setting

Under **Settings → Actions → General → Workflow permissions**, enable **Read and write permissions** (or rely on workflow-level `contents: write` / `pull-requests: write`) and check **"Allow GitHub Actions to create and approve pull requests"** so `phase-a-release.yml` can open and update the persistent `release/phase-a-weekly` PR against `master`.

### Weekly Friday Handoff Procedure

1. **Inspect the workflow run:** Open the latest **Phase A Weekly Release** run, review the `Phase A Fetch Summary` and any `Circuit-Breaker & Staleness Alerts`, and confirm `snapshots-latest` updated if canonical content changed.
2. **Download the release bundle:** Download the `phase-a-release-bundle` artifact containing `dist/workshop/`, `dist/local/`, `dist/snapshots/`, `dist/fetch_summary.json`, `dist/release_summary.json`, `CHANGELOG_SUMMER.md`, and `CHANGELOG_WINTER.md`.
3. **Upload Core Summer & Winter via SCS Workshop Uploader (`AppID 421800`):**
   - Upload `dist/workshop/summer/` and/or `dist/workshop/winter/` for whichever editions changed.
   - Attach a `640x360` Workshop preview JPG (max 1 MB) in the SCS Workshop Uploader UI (`mod_icon.jpg` inside each bundle is the `276x162` in-game Mod Manager icon).
4. **Merge the persistent Release PR:** Merge the `release/phase-a-weekly` PR into `master` **only after** Workshop uploads succeed so `state/published.json`, `state/prices.lock.json`, `CHANGELOG_SUMMER.md`, and `CHANGELOG_WINTER.md` advance atomically on `master`.
5. **Locally compile & upload ProMods Editions from `snapshots-latest`:**
   - Download `realism-snapshot-summer.json`, `realism-snapshot-winter.json`, and `SHA256SUMS.txt` from the rolling `snapshots-latest` GitHub Release (e.g., `gh release download snapshots-latest --dir dist/snapshots --clobber`).
   - Compile both seasonal ProMods Editions offline against your local ProMods archives:
     ```bash
     uv run --offline ets2-realism package promods --edition summer --mod-dir "<ETS2_MOD_DIR>" --snapshot dist/snapshots/realism-snapshot-summer.json --checksums dist/snapshots/SHA256SUMS.txt --out-dir dist
     uv run --offline ets2-realism package promods --edition winter --mod-dir "<ETS2_MOD_DIR>" --snapshot dist/snapshots/realism-snapshot-winter.json --checksums dist/snapshots/SHA256SUMS.txt --out-dir dist
     ```
   - Upload `dist/workshop/promods-summer/` and `dist/workshop/promods-winter/` via **SCS Workshop Uploader** (`AppID 421800`).

### Reviewing Monthly `osm-audit` GitHub Issues

`.github/workflows/osm-speed-audit.yml` runs read-only on the first Monday of each month at `07:00 UTC` (`cron: "0 7 1-7 * 1"`, or on demand via `workflow_dispatch` with optional `iso2` and `overpass` inputs). It writes zero files to Git, uploads `osm-speed-drift-report`, and opens or updates a rolling issue titled **`Monthly OSM Speed-Limit Drift Review`** labeled `osm-audit` whenever unacknowledged drift findings exist:

1. Inspect each flagged `(iso2, vehicle_class, lane_speed_class, field)` finding in the issue or downloaded `osm-speed-drift-report` artifact.
2. Verify the actual rule against an **official national statute or government road-safety portal** (never copy OSM values directly).
3. Either update `data/laws/countries/<iso2>.json` with an official citation if the law changed, or add a documented statutory rationale to `data/laws/speed_audit_allowlist.json` if the difference is an intentional statutory modeling choice.
4. Once all findings are resolved on `master`, the next unfiltered audit run reporting `0` unacknowledged findings automatically closes the `osm-audit` issue.
