<!-- generated-by: gsd-doc-writer -->

# CLI Reference (`ets2-realism`)

Complete reference for the `ets2-realism` command-line interface (`ets2_realism.cli:main`, version `0.1.0`), covering all top-level commands, subcommands, flags, defaults, exit codes, and environment variables.

## Table of Contents

- [Global Invocation & Exit Codes](#global-invocation--exit-codes)
- [Command Overview](#command-overview)
- [`vfs`](#vfs)
  - [`vfs inspect`](#vfs-inspect)
- [`baseline`](#baseline)
  - [`baseline extract`](#baseline-extract)
- [`registry`](#registry)
  - [`registry validate`](#registry-validate)
  - [`registry snapshot`](#registry-snapshot)
  - [`registry snapshot-verify`](#registry-snapshot-verify)
- [`package`](#package)
  - [`package icons`](#package-icons)
  - [`package promods-icons`](#package-promods-icons)
  - [`package build`](#package-build)
  - [`package promods`](#package-promods)
- [`validate`](#validate)
  - [`validate workshop`](#validate-workshop)
  - [`validate local`](#validate-local)
- [`publish`](#publish)
  - [`publish release`](#publish-release)
- [`fetch`](#fetch)
- [`compose-local`](#compose-local)
- [`audit`](#audit)
  - [`audit osm-speeds`](#audit-osm-speeds)
  - [`audit taint`](#audit-taint)
- [Environment Variables](#environment-variables)

---

## Global Invocation & Exit Codes

Install the locked environment once with [`uv`](https://docs.astral.sh/uv/) (Python `>= 3.12`):

```bash
uv sync --locked
```

### Offline vs. Online Invocation

- **Offline commands** (`vfs`, `baseline`, `registry`, `package`, `validate`, `publish`, `compose-local`, `audit taint`, `fetch --seed-offline`, `audit osm-speeds --rules-file`): run with `uv run --offline` so `uv` executes directly from the locked local environment without touching the network:

  ```bash
  uv run --offline ets2-realism <COMMAND> [SUBCOMMAND] [OPTIONS]
  ```

- **Online commands** (`fetch` for live FX/fuel feeds and `audit osm-speeds` when fetching remote rules/Overpass/Taginfo): invoke with `uv run` (or `uv run --offline` once dependencies are already synced with `uv sync --locked`, since `--offline` only restricts `uv` package resolution, not HTTPS requests made by Python):

  ```bash
  uv run ets2-realism fetch --lock-path state/prices.lock.json
  uv run ets2-realism audit osm-speeds --out-md dist/audit/osm_speed_drift_report.md
  ```

### Global Options

| Option | Description |
| --- | --- |
| `--version` | Print `ets2-realism 0.1.0` and exit `0`. |
| `-h`, `--help` | Show root or subcommand help and exit `0`. |

Invoking `ets2-realism` (or any command group without a subcommand) prints usage help and exits `0`.

### Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Command succeeded (or help/version printed, or clean no-op in `publish release`). |
| `1` | Runtime error, validation failure, checksum mismatch, circuit-breaker error, taint violation, or unacknowledged drift (when `--fail-on-drift` is set). |
| `2` | CLI argument syntax error (missing required option, invalid choice, or conflicting mutually exclusive flags from `argparse`). |

---

## Command Overview

| Command | Subcommands | Purpose | Network |
| --- | --- | --- | --- |
| `vfs` | `inspect` | Inspect `.scs`/`.zip` archives and unpacked VFS directories | Offline |
| `baseline` | `extract` | Extract or byte-verify clean-room ETS2 1.62+ baseline JSONs | Offline |
| `registry` | `validate`, `snapshot`, `snapshot-verify` | Validate law registries and export/verify v1 realism snapshots | Offline |
| `package` | `icons`, `promods-icons`, `build`, `promods` | Generate 276×162 icons and build Core or ProMods editions | Offline |
| `validate` | `workshop`, `local` | Run Offline SCS Workshop Validator and 1.62 realism invariants | Offline |
| `publish` | `release` | Build, validate, diff-gate, and emit Phase A seasonal Core releases | Offline |
| `fetch` | *(direct)* | Collect multi-provider FX rates and Tier 1/Tier 2 fuel prices | Online (offline with `--seed-offline`) |
| `compose-local` | *(direct)* | Compose an offline `zz_ETS2_Realism_ComboPatch_{Summer\|Winter}.scs` | Offline |
| `audit` | `osm-speeds`, `taint` | Run quarantined OSM speed-limit drift and license-taint audits | Online (`osm-speeds`) / Offline (`taint`) |

---

## `vfs`

Inspect ETS2 VFS archives (HashFS v1/v2 `.scs`, `.zip`, or unpacked directories) layered in priority order.

### `vfs inspect`

Inspect one or more `.scs`/`.zip` archives or unpacked directories ordered from lowest to highest priority.

```bash
uv run --offline ets2-realism vfs inspect PATH [PATH ...] [OPTIONS]
```

| Argument / Option | Type | Default | Description |
| --- | --- | --- | --- |
| `paths` | `Path` (1+ positional) | *(required)* | Archive or directory path(s) ordered from lowest to highest VFS priority. |
| `--prefix` | `str` (repeatable) | `None` (seeds `locale`, `def`, `base`) | Seeded HashFS traversal prefix and output filter prefix. Repeat to pass multiple prefixes. |
| `--limit` | `int` | `20` | Maximum number of sample entry paths to display. |
| `--json` | flag | `False` | Print structured inspection output (`layers`, `entry_count`, `sample_paths`, `diagnostics`) as JSON. |

**Exit behavior:** Returns `0` on success; returns `1` if any input path does not exist or an archive cannot be opened.

**Examples:**

```bash
# Inspect vanilla def.scs and locale.scs filtered to def/country/
uv run --offline ets2-realism vfs inspect \
  "D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\def.scs" \
  "D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\locale.scs" \
  --prefix def/country --limit 30

# Emit JSON diagnostics for a local mod archive
uv run --offline ets2-realism vfs inspect dist/local/ETS2_Country_Realism_Core_Summer.zip --json
```

---

## `baseline`

Extract and verify clean-room JSON baselines (`countries.json`, `speed_limits.json`, `fuel_boards.json`, `locales.json`, `manifest.json`) from a local ETS2 installation.

### `baseline extract`

Extract clean-room ETS2 baseline JSON files from local game archives, or verify existing baseline JSONs with `--check`.

```bash
uv run --offline ets2-realism baseline extract [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--game-dir` | `Path` | `None` | ETS2 install directory. Precedence: `--game-dir` > `ETS2_GAME_DIR` > `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`. |
| `--out-dir` | `Path` | `data/baselines/ets2_1.62_def` | Target directory for extracted clean-room baseline JSON files. |
| `--raw-cache-dir` | `Path` | `None` | Optional gitignored directory to dump raw `.sii`/`.sui` files for local testing. Must not equal or overlap `--out-dir`; ignored when `--check` is set. |
| `--check` | flag | `False` | Verify existing baseline JSON files in `--out-dir` match fresh extraction with zero byte diff (does not overwrite files). |

**Exit behavior:** Returns `0` on successful extraction or zero-diff `--check`; returns `1` if `--raw-cache-dir` overlaps `--out-dir`, extraction fails (including protected or unsupported archives), or `--check` detects any mismatch.

**Examples:**

```bash
# Extract baseline JSONs from an explicit ETS2 installation
uv run --offline ets2-realism baseline extract \
  --game-dir "D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2" \
  --out-dir data/baselines/ets2_1.62_def

# Verify checked-in baseline JSONs match local ETS2 archives byte-for-byte
uv run --offline ets2-realism baseline extract --check
```

---

## `registry`

Validate canonical per-country realism law records and export or verify deterministic `schema_version=1` realism snapshots.

### `registry validate`

Validate country law JSON files under `data/laws/countries/<iso2>.json` and `ets2_countries.json` mappings against the ETS2 baseline.

```bash
uv run --offline ets2-realism registry validate [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--laws-dir` | `Path` | `data/laws` | Directory containing `countries/<iso2>.json` law records. |
| `--mappings` | `Path` | `data/mappings/ets2_countries.json` | Path to the `ets2_countries.json` mapping file. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--json` | flag | `False` | Print validation report (`country_count`, `issue_count`, `issues`, `ok`) as JSON. |

**Exit behavior:** Returns `0` when all checks pass (`issue_count == 0`); returns `1` on schema, mapping, or baseline validation errors.

**Examples:**

```bash
uv run --offline ets2-realism registry validate
uv run --offline ets2-realism registry validate --json
```

### `registry snapshot`

Export a deterministic `schema_version=1` realism snapshot JSON file for a single seasonal edition.

```bash
uv run --offline ets2-realism registry snapshot --season {summer,winter} --out PATH [OPTIONS]
```

| Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `--season` | `summer` \| `winter` | *(required)* | Seasonal edition to resolve for DST offsets. |
| `--out` | `Path` | *(required)* | Output JSON file path for the generated realism snapshot. |
| `--date` | `str` (`YYYY-MM-DD`) | `None` | Optional strict ISO `YYYY-MM-DD` override date for timezone/DST resolution. |
| `--anchor-year` | `int` | `2026` | Anchor year used when `--date` is omitted. |
| `--laws-dir` | `Path` | `data/laws` | Directory containing `countries/<iso2>.json` law records. |
| `--mappings` | `Path` | `data/mappings/ets2_countries.json` | Path to `ets2_countries.json`. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--prices-lock` | `Path` | `None` | Optional path to `state/prices.lock.json` to inject locked live fuel prices into the snapshot. |

**Exit behavior:** Returns `0` on success; returns `1` on invalid `--date` format or export/validation error.

**Examples:**

```bash
uv run --offline ets2-realism registry snapshot \
  --season summer \
  --prices-lock state/prices.lock.json \
  --out dist/snapshots/realism-snapshot-summer.json
```

### `registry snapshot-verify`

Verify a `schema_version=1` realism snapshot file offline (schema validation, SII hygiene, optional edition check, and `SHA256SUMS.txt` checksum verification).

```bash
uv run --offline ets2-realism registry snapshot-verify SNAPSHOT_PATH [OPTIONS]
```

| Argument / Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `snapshot_path` | `Path` (positional) | *(required)* | Path to the `realism-snapshot-{summer,winter}.json` file to verify. |
| `--checksums` | `Path` | `None` | Optional path to `SHA256SUMS.txt`. When omitted, auto-checks a sibling `SHA256SUMS.txt` next to `snapshot_path` if present. |
| `--expected-edition` | `summer` \| `winter` | `None` | Optional expected seasonal edition; fails verification if snapshot edition does not match. |
| `--json` | flag | `False` | Print `SnapshotVerificationResult` as JSON. |

**Exit behavior:** Returns `0` when `result.ok` is true; returns `1` on any schema, hygiene, edition, or checksum failure.

**Examples:**

```bash
uv run --offline ets2-realism registry snapshot-verify \
  dist/snapshots/realism-snapshot-summer.json \
  --checksums dist/snapshots/SHA256SUMS.txt \
  --expected-edition summer
```

---

## `package`

Generate clean-room `276×162` RGB JPEG Workshop icons and compile Vanilla+DLC Core or ProMods Companion packages (both unpacked Steam Workshop roots and deterministic local `.zip` archives).

### `package icons`

Generate clean-room `276×162` RGB JPEG icons for **both** Core (`summer.jpg`, `winter.jpg`) and ProMods (`promods_summer.jpg`, `promods_winter.jpg`) editions.

```bash
uv run --offline ets2-realism package icons [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--out-dir` | `Path` | `assets/icons` | Output directory for Core and ProMods JPEG icons. |

**Exit behavior:** Returns `0` on success; returns `1` on I/O or rendering error.

### `package promods-icons`

Generate clean-room `276×162` RGB JPEG icons for ProMods editions only (`promods_summer.jpg`, `promods_winter.jpg`).

```bash
uv run --offline ets2-realism package promods-icons [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--out-dir` | `Path` | `assets/icons` | Output directory for `promods_summer.jpg` and `promods_winter.jpg`. |

**Exit behavior:** Returns `0` on success; returns `1` on I/O or rendering error.

### `package build`

Build unpacked Steam Workshop roots (`<out-dir>/workshop/{summer,winter}/`) and deterministic local `.zip` Core mods (`<out-dir>/local/ETS2_Country_Realism_Core_{Summer,Winter}.zip`).

```bash
uv run --offline ets2-realism package build [OPTIONS]
```

| Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `--edition` | `summer` \| `winter` \| `all` | `all` | Seasonal Core edition(s) to compile. |
| `--out-dir` | `Path` | `dist` | Root output directory for `workshop/` and `local/` targets. |
| `--laws-dir` | `Path` | `data/laws` | Directory containing `countries/<iso2>.json` law records. |
| `--mappings` | `Path` | `data/mappings/ets2_countries.json` | Path to `ets2_countries.json`. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--icons-dir` | `Path` | `assets/icons` | Directory containing `summer.jpg` and `winter.jpg`. |
| `--prices-lock` | `Path` | `state/prices.lock.json` | Path to canonical `prices.lock.json` lockfile. |
| `--package-version` | `str` | `None` | Optional explicit `package_version` override (defaults to ISO week of anchor date). |
| `--author` | `str` | `"MissionWAR"` | Mod author string written to `manifest.sii`. |
| `--date` | `str` (`YYYY-MM-DD`) | `None` | Optional strict ISO `YYYY-MM-DD` override date for timezone resolution. |
| `--anchor-year` | `int` | `2026` | Anchor year when `--date` is omitted. |

**Exit behavior:** Returns `0` on success; returns `1` on invalid `--date`, missing icons/inputs, or build failure.

**Examples:**

```bash
# Build both Summer and Winter Core editions into dist/
uv run --offline ets2-realism package build --out-dir dist

# Build Summer Core only with an explicit package version
uv run --offline ets2-realism package build --edition summer --package-version 1.62-2026.15 --out-dir dist
```

### `package promods`

Build and offline-validate standalone all-in-one ProMods Editions from locally installed ProMods archives (`EU`, `ME`, `MA`, `TGS`). Outputs `<out-dir>/workshop/promods-{summer,winter}/` and `<out-dir>/local/ETS2_Country_Realism_ProMods_{Summer,Winter}.zip`.

```bash
uv run --offline ets2-realism package promods [OPTIONS]
```

| Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `--edition` | `summer` \| `winter` \| `all` | `all` | Seasonal ProMods edition(s) to compile. |
| `--mod-dir` | `Path` | `None` | ETS2 `mod/` directory containing ProMods def/defmap and assets archives. Falls back to `ETS2_MOD_DIR`, then platform default. |
| `--game-dir` | `Path` | `None` | Optional ETS2 install directory containing vanilla `def.scs` (defaults to clean-room 1.62 baseline). |
| `--out-dir` | `Path` | `dist` | Root output directory for `workshop/promods-*` and `local/` outputs. |
| `--snapshot` | `Path` | `None` | Optional offline v1 `realism-snapshot-{summer,winter}.json` path. |
| `--checksums` | `Path` | `None` | Optional `SHA256SUMS.txt` manifest path to verify `--snapshot`. |
| `--require-all-packs` | flag | `False` | Fail fast unless EU, ME, MA, and TGS def/defmap plus EU/ME/TGS assets are all present. |
| `--promods-eu` | `Path` | `None` | Explicit ProMods Europe `def` archive path. |
| `--promods-eu-assets` | `Path` | `None` | Explicit ProMods Europe `assets` archive path. |
| `--promods-me` | `Path` | `None` | Explicit ProMods Middle-East `defmap` archive path. |
| `--promods-me-assets` | `Path` | `None` | Explicit ProMods Middle-East `assets` archive path. |
| `--promods-ma` | `Path` | `None` | Explicit ProMods Maghreb `defmap` archive path. |
| `--promods-ma-assets` | `Path` | `None` | Explicit ProMods Maghreb `assets` archive path. |
| `--promods-tgs` | `Path` | `None` | Explicit ProMods The Great Steppe `defmap` archive path. |
| `--promods-tgs-assets` | `Path` | `None` | Explicit ProMods The Great Steppe `assets` archive path. |
| `--laws-dir` | `Path` | `data/laws` | Directory containing `countries/<iso2>.json` law records. |
| `--mappings` | `Path` | `data/mappings/ets2_countries.json` | Path to `ets2_countries.json`. |
| `--aliases` | `Path` | `data/mappings/country_aliases.json` | Path to bundled `country_aliases.json`. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--icons-dir` | `Path` | `assets/icons` | Directory containing `promods_summer.jpg` and `promods_winter.jpg`. |
| `--prices-lock` | `Path` | `state/prices.lock.json` | Path to canonical `prices.lock.json` (used only when `--snapshot` is omitted). |
| `--package-version` | `str` | `None` | Optional explicit `package_version` override. |
| `--author` | `str` | `"MissionWAR"` | Mod author string written to `manifest.sii`. |
| `--json` | flag | `False` | Print `ProModsBuildReport` mapping (`summer`/`winter`) as JSON. |

**Exit behavior:** Returns `0` on success; returns `1` on missing required packs, protected/unsupported archive errors, snapshot verification failures, or build/validation errors.

**Examples:**

```bash
# Auto-discover ProMods packs from ETS2 mod/ directory and build Summer & Winter
uv run --offline ets2-realism package promods \
  --mod-dir "D:\ETS2Data\Euro Truck Simulator 2\mod" \
  --out-dir dist/promods

# Build Summer ProMods Edition from a verified release snapshot, requiring all 4 regions
uv run --offline ets2-realism package promods \
  --edition summer \
  --mod-dir "D:\ETS2Data\Euro Truck Simulator 2\mod" \
  --snapshot dist/snapshots/realism-snapshot-summer.json \
  --checksums dist/snapshots/SHA256SUMS.txt \
  --require-all-packs \
  --out-dir dist/promods \
  --json
```

---

## `validate`

Run the independent Offline SCS Workshop Validator (SCS error codes `00001`–`00010`, warnings `WARN 00001`/`00002`, JPEG icon dimensions, `mp_mod_optional: true`, Zero-DDS, locale parity, and `ETS2R-INV-*` invariants).

### `validate workshop`

Validate an unpacked Steam Workshop directory root (`versions.sii` + `universal/`).

```bash
uv run --offline ets2-realism validate workshop TARGET [OPTIONS]
```

| Argument / Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `target` | `Path` (positional) | *(required)* | Path to the staged Workshop root directory. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--profile` | `core` \| `promods` \| `combo` | `core` | Validation profile matching the package type. |
| `--json` | flag | `False` | Print `ValidationReport` as JSON. |

**Exit behavior:** Returns `0` when `report.ok` is true (zero errors/warnings); returns `1` on any validation issue or read error.

### `validate local`

Validate a standalone local playtest `.zip` (or `.scs`) package archive.

```bash
uv run --offline ets2-realism validate local TARGET [OPTIONS]
```

| Argument / Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `target` | `Path` (positional) | *(required)* | Path to the standalone local `.zip`/`.scs` archive. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--profile` | `core` \| `promods` \| `combo` | `core` | Validation profile matching the package type. |
| `--json` | flag | `False` | Print `ValidationReport` as JSON. |

**Exit behavior:** Returns `0` when `report.ok` is true; returns `1` on any validation issue or read error.

**Examples:**

```bash
uv run --offline ets2-realism validate workshop dist/workshop/summer
uv run --offline ets2-realism validate local dist/local/ETS2_Country_Realism_Core_Summer.zip
uv run --offline ets2-realism validate local dist/promods/local/ETS2_Country_Realism_ProMods_Summer.zip --profile promods --json
uv run --offline ets2-realism validate local dist/local/zz_ETS2_Realism_ComboPatch_Summer.scs --profile combo
```

---

## `publish`

Run diff-gated Phase A seasonal Core release orchestration, snapshot publishing, and changelog generation.

### `publish release`

Build both Summer and Winter Core editions, offline-validate them, compare canonical content hashes against `state/published.json`, emit `dist/snapshots/realism-snapshot-{summer,winter}.json` + `SHA256SUMS.txt` + `dist/release_summary.json`, and generate `CHANGELOG_SUMMER.md` / `CHANGELOG_WINTER.md`.

```bash
uv run --offline ets2-realism publish release [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--state` | `Path` | `state/published.json` | Path to the v1 published release ledger. |
| `--prices-lock` | `Path` | `state/prices.lock.json` | Path to canonical `prices.lock.json`. |
| `--out-dir` | `Path` | `dist` | Output directory for `workshop/`, `local/`, `snapshots/`, and `release_summary.json`. |
| `--changelogs-dir` | `Path` | `.` | Output directory for `CHANGELOG_SUMMER.md` and `CHANGELOG_WINTER.md`. |
| `--laws-dir` | `Path` | `data/laws` | Directory containing `countries/<iso2>.json` law records. |
| `--mappings` | `Path` | `data/mappings/ets2_countries.json` | Path to `ets2_countries.json`. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--icons-dir` | `Path` | `assets/icons` | Directory containing `summer.jpg` and `winter.jpg`. |
| `--build-date` | `str` (`YYYY-MM-DD`) | `None` (current UTC date) | Optional strict ISO `YYYY-MM-DD` date used for ISO-week `package_version` resolution. |
| `--author` | `str` | `"MissionWAR"` | Mod author string written to `manifest.sii`. |
| `--anchor-year` | `int` | `None` (build date year) | Anchor year for seasonal DST resolution. |
| `--write-state` | flag | `False` | Update `--state` ledger file when one or more editions changed. |
| `--force` | flag | `False` | Emit validated changelogs and artifacts even when canonical hashes are unchanged. |
| `--previous-snapshots-dir` | `Path` | `None` | Optional directory containing previous `realism-snapshot-{summer,winter}.json` files for structured changelog diffing. |
| `--json` | flag | `False` | Print `PhaseAReleaseSummary` as JSON. |

**Exit behavior:** Returns `0` on success (including clean no-op when hashes match); returns `1` on invalid `--build-date`, missing `--previous-snapshots-dir`, validation error, or pipeline failure.

**Examples:**

```bash
# Dry check against state/published.json without updating the ledger
uv run --offline ets2-realism publish release --out-dir dist --json

# Full release run matching .github/workflows/phase-a-release.yml
uv run --offline ets2-realism publish release \
  --state state/published.json \
  --prices-lock state/prices.lock.json \
  --out-dir dist \
  --changelogs-dir . \
  --previous-snapshots-dir /tmp/prev-snapshots \
  --write-state
```

---

## `fetch`

Fetch live multi-provider FX rates and open fuel price data (Tier 1 EU Core, Global Tier 1, and Tier 2 guarded national portals) into `state/prices.lock.json`, applying cross-provider FX validation and week-over-week jump circuit breakers.

```bash
uv run ets2-realism fetch [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--lock-path` | `Path` | `state/prices.lock.json` | Path to the `prices.lock.json` state file to read/update. |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--allow-jump` | `str` (repeatable) | `None` | Explicitly allow a `>25%` week-over-week price jump for an ISO-2 country code (case-insensitive, normalized to uppercase). Repeat for multiple countries. |
| `--fx-only` | flag | `False` | Fetch and cross-validate multi-provider FX rates only (skip fuel collectors). |
| `--seed-offline` | flag | `False` | Deterministically seed `--lock-path` offline from the 1.62 baseline (zero network requests). |
| `--no-global` | flag | `False` | Skip non-EU Global Tier 1 fuel collectors (EU Core only). |
| `--no-tier2` | flag | `False` | Skip Tier 2 guarded national portal scrapers. |
| `--timeout` | `float` | `20.0` | Per-request HTTP timeout in seconds (must be finite and `> 0.0`). |
| `--dry-run` | flag | `False` | Run collection and validation without modifying `--lock-path` on disk. |
| `--json` | flag | `False` | Print `FetchRunReport` as JSON. |

**Exit behavior:** Returns `0` when `report.ok` is true; returns `1` on invalid `--timeout`, unhandled I/O/validation errors (with URL query secrets redacted), or fetch/circuit-breaker failures.

**Examples:**

```bash
# Standard online weekly collection (EU Core + Global Tier 1 + Tier 2 portals)
uv run ets2-realism fetch --lock-path state/prices.lock.json

# Dry-run FX and EU Core only with JSON output
uv run ets2-realism fetch --no-global --no-tier2 --dry-run --json

# Allow verified >25% weekly price jumps for specific countries
uv run ets2-realism fetch --allow-jump DE --allow-jump FR

# Seed lockfile deterministically offline from clean-room 1.62 baseline
uv run --offline ets2-realism fetch --seed-offline --lock-path state/prices.lock.json
```

---

## `compose-local`

Compose and offline-validate `zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs` for an arbitrary local multi-map combo load order (*ProMods*, *RusMap*, *TST*, *UMCF*, *Beyond*, *EAA*, *SEA*, *RoC*, *Project Japan*, *JRR*, etc.) using `FieldOwnershipPolicy` to preserve map identity/geometry while harmonizing country laws, speed limits, timezones, and fuel prices.

```bash
uv run --offline ets2-realism compose-local --season {summer,winter} (--game-log PATH | --profile PATH | --modlist PATH) [OPTIONS]
```

### Season & Input

| Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `--season` | `summer` \| `winter` | *(required)* | Seasonal realism edition to compose. |

### Load Order Discovery

Exactly **one** of `--game-log`, `--profile`, or `--modlist` is required (mutually exclusive).

| Option | Type / Choices | Default | Description |
| --- | --- | --- | --- |
| `--game-log` | `Path` | `None` | Path to ETS2 `game.log.txt` for active mount order discovery. |
| `--profile` | `Path` | `None` | Path to plaintext ETS2 `profile.sii` (`ScsC`-encrypted profiles are refused). |
| `--modlist` | `Path` | `None` | Path to a line-delimited mod list text file. |
| `--modlist-order` | `top-to-bottom` \| `bottom-to-top` | `top-to-bottom` | Priority ordering of `--modlist` lines (`top-to-bottom` matches ETS2 Mod Manager UI order). |

### Paths & Data Sources

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--mod-dir` | `Path` | `None` | ETS2 local `mod/` directory containing `.scs`/`.zip`/unpacked mods. Falls back to `ETS2_MOD_DIR`, then platform default. |
| `--workshop-dir` | `Path` | `None` | Optional Steam Workshop `227300` directory (`steamapps/workshop/content/227300`). Falls back to `ETS2_WORKSHOP_DIR`, then Steam library auto-detection. |
| `--game-dir` | `Path` | `None` | Optional ETS2 install directory containing `def.scs` (defaults to clean-room 1.62 baseline). |
| `--out-dir` | `Path` | `dist/local` | Output directory for `zz_ETS2_Realism_ComboPatch_{Summer\|Winter}.scs`. Refuses tracked git repo subdirectories when writing (non-`--dry-run`). |
| `--laws-dir` | `Path` | `data/laws` | Directory containing `countries/<iso2>.json` law records (used when `--snapshot` is omitted). |
| `--mappings` | `Path` | `data/mappings/ets2_countries.json` | Path to `ets2_countries.json` (used when `--snapshot` is omitted). |
| `--baseline-dir` | `Path` | `data/baselines/ets2_1.62_def` | Directory containing clean-room ETS2 baseline JSON files. |
| `--prices-lock` | `Path` | `state/prices.lock.json` | Path to canonical `prices.lock.json` (used only when `--snapshot` is omitted). |

### Snapshot, Aliases & Package Metadata

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--snapshot` | `Path` | `None` | Optional offline v1 `realism-snapshot-{summer,winter}.json` path. |
| `--checksums` | `Path` | `None` | Optional `SHA256SUMS.txt` manifest path to verify `--snapshot`. |
| `--aliases` | `Path` | `None` | Optional user `country_aliases.json` override merged atop bundled `data/mappings/country_aliases.json`. |
| `--package-version` | `str` | `None` | Optional explicit `package_version` override. |
| `--author` | `str` | `"MissionWAR"` | Mod author string written to `manifest.sii`. |

### Protected Archives, Totems & Exclusion

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--unpacked-defs` | `Path` (repeatable) | `None` | Unpacked def directory: stem-matched child directories substitute protected archives in-place; raw `def/`/`locale/` directories mount as high-priority overrides. |
| `--strict-protected` | flag | `False` | Exit non-zero without writing `.scs` if any protected (`AEM!`/`3nK`/encrypted ZIP) archive remains unsubstituted. |
| `--patch-hardcoded-totems` | flag | `False` | Opt-in surgical rewriting of verified JRR/7RM hardcoded numeric gas boards. |
| `--no-totems` | flag | `False` | Emit `def/country/` realism patches only (skip all sign boards and fuel locales). |
| `--no-self-exclude` | flag | `False` | Disable automatic exclusion of previously emitted managed packages in the load order. |

### Output & Reporting

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--dry-run` | flag | `False` | Compute and audit the full combo merge without writing a `.scs` archive. |
| `--report-json` | `Path` | `None` | Optional file path to write the deterministic sorted JSON `ComposeReport`. |
| `--json` | flag | `False` | Print `ComposeReport` as deterministic JSON to stdout. |

**Exit behavior:** Returns `0` when `report.ok` is true; returns `1` on errors, `--strict-protected` violations, encrypted `profile.sii`, or offline validation failures.

**Examples:**

```bash
# Compose Summer ComboPatch from game.log.txt directly into your ETS2 mod/ folder
uv run --offline ets2-realism compose-local \
  --season summer \
  --game-log "D:\ETS2Data\Euro Truck Simulator 2\game.log.txt" \
  --mod-dir "D:\ETS2Data\Euro Truck Simulator 2\mod" \
  --out-dir "D:\ETS2Data\Euro Truck Simulator 2\mod"

# Dry-run audit using a verified snapshot, custom modlist, unpacked protected defs, and JSON report
uv run --offline ets2-realism compose-local \
  --season winter \
  --modlist my_combo_order.txt \
  --modlist-order top-to-bottom \
  --mod-dir "D:\ETS2Data\Euro Truck Simulator 2\mod" \
  --workshop-dir "D:\SteamLibrary\steamapps\workshop\content\227300" \
  --snapshot dist/snapshots/realism-snapshot-winter.json \
  --checksums dist/snapshots/SHA256SUMS.txt \
  --unpacked-defs "D:\ETS2Data\unpacked_defs" \
  --patch-hardcoded-totems \
  --strict-protected \
  --dry-run \
  --report-json dist/combo_report.json
```

---

## `audit`

Quarantined internal auditing commands for statutory speed-limit drift verification against OpenStreetMap reference rules and clean-room license-taint scanning.

### `audit osm-speeds`

Compare `data/laws/` statutory speed limits against `westnordost/osm-legal-default-speeds` (read-only; never writes to `data/laws/`).

```bash
uv run ets2-realism audit osm-speeds [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--iso2` | `str` | `None` (all countries) | Comma-separated ISO-2 country codes to audit (e.g., `DE,FR,PL`). |
| `--overpass` | flag | `False` | Opt-in Overpass API tags-only spot-checks (requires `<= 10` selected ISO-2 codes via `--iso2`). |
| `--taginfo` | flag | `False` | Opt-in Taginfo API v4 global `maxspeed` value distributions. |
| `--rules-url` | `str` | `https://westnordost.github.io/osm-legal-default-speeds/legal_default_speeds.json` | HTTPS URL to westnordost `legal_default_speeds.json`. |
| `--rules-file` | `Path` | `None` | Optional local path to `legal_default_speeds.json` for offline execution. |
| `--allowlist` | `Path` | `data/laws/speed_audit_allowlist.json` | Clean-room statutory deviation allowlist JSON file. |
| `--laws-dir` | `Path` | `data/laws` | Directory containing `countries/<iso2>.json` law records. |
| `--mappings` | `Path` | `data/mappings/ets2_countries.json` | Path to `ets2_countries.json`. |
| `--out-md` | `Path` | `None` | Optional output path for sanitized Markdown drift report (written atomically). |
| `--out-json` | `Path` | `None` | Optional output path for deterministic sorted JSON drift report (written atomically). |
| `--timeout` | `float` | `20.0` | HTTP timeout in seconds (must be finite and `> 0.0`). |
| `--fail-on-drift` | flag | `False` | Exit `1` if any unacknowledged speed-limit drift is detected. |
| `--json` | flag | `False` | Print `OsmSpeedAuditReport` as deterministic sorted JSON to stdout. |

**Exit behavior:** Returns `0` on completion (even if unacknowledged drift exists, unless `--fail-on-drift` is passed); returns `1` on invalid `--timeout`, HTTP/parse/validation error, or unacknowledged drift when `--fail-on-drift` is set.

**Examples:**

```bash
# Run full monthly drift audit and save Markdown + JSON reports
uv run ets2-realism audit osm-speeds \
  --out-md dist/audit/osm_speed_drift_report.md \
  --out-json dist/audit/osm_speed_drift_report.json

# Targeted spot-check with Overpass tags-only queries and CI failure gate
uv run ets2-realism audit osm-speeds --iso2 DE,FR,NL --overpass --fail-on-drift

# Offline audit against a local legal_default_speeds.json snapshot
uv run --offline ets2-realism audit osm-speeds --rules-file /tmp/legal_default_speeds.json --json
```

### `audit taint`

Scan `data/`, `state/`, realism snapshots, and built mod packages for forbidden license/source taint markers.

```bash
uv run --offline ets2-realism audit taint [OPTIONS]
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--repo-root` | `Path` | `.` | Repository root directory to scan. |
| `--snapshot` | `Path` (repeatable) | `None` | Repeatable `realism-snapshot-*.json` path to include in the taint scan. |
| `--package` | `Path` (repeatable) | `None` | Repeatable unpacked Workshop directory or `.zip`/`.scs` package path to scan. |
| `--json` | flag | `False` | Print `TaintScanReport` as deterministic sorted JSON. |

**Exit behavior:** Returns `0` when zero violations are detected (`report.ok`); returns `1` on any taint violation or unreadable archive/file.

**Examples:**

```bash
# Scan repository data/ and state/
uv run --offline ets2-realism audit taint --json

# Scan repository plus built snapshots and packages
uv run --offline ets2-realism audit taint \
  --snapshot dist/snapshots/realism-snapshot-summer.json \
  --package dist/workshop/summer \
  --package dist/local/ETS2_Country_Realism_Core_Summer.zip
```

---

## Environment Variables

All environment variables below are **optional**. Missing API keys trigger graceful skip/fallback behavior (zero hard failures), and path variables act as fallbacks when the corresponding CLI flag is omitted.

### Fuel Feed API Keys (`ets2-realism fetch`)

These secrets are also wired into `.github/workflows/phase-a-release.yml` for automated weekly runs.

| Variable | Feed / Country | When Unset | Source Module |
| --- | --- | --- | --- |
| `TANKERKOENIG_API_KEY` | Germany (`DE`) Tankerkönig 5-city station median | Skipped silently; falls back to EC Weekly Oil Bulletin (`de_tankerkoenig`). | `src/ets2_realism/fetch/national.py` |
| `EIA_API_KEY` | United States (`US`) EIA Open Data API v2 weekly retail prices | Skipped silently; retains lockfile / Tier 3 baseline (`us_eia_v2`). | `src/ets2_realism/fetch/global_tier1.py` |
| `OPINET_API_KEY` | South Korea (`KR`) KNOC Opinet daily national averages | Skipped silently; retains lockfile / Tier 3 baseline (`kr_opinet`). | `src/ets2_realism/fetch/global_tier1.py` |
| `CNE_API_TOKEN` | Chile (`CL`) CNE Bencina en Línea v4/v3 station medians | Skipped silently; retains lockfile / Tier 3 baseline (`cl_cne`). | `src/ets2_realism/fetch/global_tier1.py` |

### Local ETS2 Path Overrides (`baseline`, `package promods`, `compose-local`)

| Variable | Overridden By | Fallback When Unset | Source Module |
| --- | --- | --- | --- |
| `ETS2_GAME_DIR` | `--game-dir` | `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2` (used by `baseline extract`). | `src/ets2_realism/baseline/extractor.py` |
| `ETS2_MOD_DIR` | `--mod-dir` | Windows: `D:\ETS2Data\Euro Truck Simulator 2\mod` if present, else `~/Documents/Euro Truck Simulator 2/mod`. Linux/macOS: `~/.local/share/Euro Truck Simulator 2/mod`. | `src/ets2_realism/merge/promods_discovery.py` |
| `ETS2_WORKSHOP_DIR` | `--workshop-dir` | Derived from `--game-dir` (`../../workshop/content/227300`), then standard Windows (`C:\Program Files (x86)\Steam\...`, `D:\SteamLibrary\...`) or Linux (`~/.local/share/Steam/...`, `~/.steam/steam/...`) Steam paths. | `src/ets2_realism/merge/load_order.py` |
