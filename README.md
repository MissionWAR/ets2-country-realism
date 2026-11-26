<!-- generated-by: gsd-doc-writer -->
# ETS2 Country Realism

[![ETS2 1.62.3.3s+](https://img.shields.io/badge/ETS2-1.62.3.3s%2B-1f6feb)](https://github.com/MissionWAR/ets2-country-realism)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776ab)](pyproject.toml)
[![License: MIT / CC BY 4.0](https://img.shields.io/badge/License-MIT%20%2F%20CC%20BY%204.0-2ea043)](LICENSE)

Open-source (**MIT** code / **CC BY 4.0** curated data), clean-room Python `3.12+` realism pipeline, mod compiler, and offline map-combo composer for **Euro Truck Simulator 2 `1.62.3.3s+`**, maintained by **MissionWAR**.

ETS2 Country Realism updates country-level speed limits, axle mass ladders, dynamic seasonal DST timezones, weekly real-world FX and fuel prices, and roadside fuel totem signage across **36** Vanilla + DLC countries and **225** canonical global territories — without baking a single `.dds` texture or storing proprietary map files in Git.

---

## Editions at a Glance

| Edition | Target Setup | Coverage | Output Artifact(s) | How You Get It |
| --- | --- | --- | --- | --- |
| **Vanilla + DLC Core** (`Summer` & `Winter`) | Base game + official SCS map DLCs | **36** SCS `1.62` countries, **460** Zero-DDS fuel boards, **43** active locales | Steam Workshop roots (`dist/workshop/{summer,winter}/`) & local ZIPs (`ETS2_Country_Realism_Core_{Summer,Winter}.zip`) | Steam Workshop or build offline via `ets2-realism package build` |
| **ProMods Companion** (`Summer` & `Winter`) | ProMods `EU` + `ME` + `MA` + `TGS` | All Vanilla + installed ProMods countries & `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` across **43** locales | Workshop roots (`dist/workshop/promods-{summer,winter}/`) & local ZIPs (`ETS2_Country_Realism_ProMods_{Summer,Winter}.zip`) | Built locally from your own ProMods archives via `ets2-realism package promods` |
| **Local Map Combo Auto-Composer** (`Summer` & `Winter`) | Any multi-map combo (*ProMods*, *RusMap*, *TST*, *UMCF*, *Beyond*, *EAA*, *SEA*, *RoC*, *Project Japan*, *JRR*, Africa maps, etc.) | Up to **225** global territories from `realism-snapshot-{summer,winter}.json` (`schema_version=1`) | Single top-priority patch archive `zz_ETS2_Realism_ComboPatch_{Summer,Winter}.scs` | Composed 100% offline from your `mod/` load order via `ets2-realism compose-local` |

### Key Technical Capabilities

- **Dynamic Seasonal DST Timezones:** Resolves `Summer` and `Winter` UTC offsets via Python `zoneinfo` + `tzdata`, honoring ETS2's 12 built-in `@@tz_*@@` localization keys and emitting plain abbreviations (`"CET"`, `"WET"`, `"AST"`, etc.) elsewhere.
- **Option 4b Zero-DDS Fuel Totems:** Rewrites all **460** single-text `1.62` `def/sign/board/*.sii` boards to namespaced `@@fp_*_ets2r@@` tokens backed by synchronized `locale/<lang>/local_module.ets2r_fuel.sii` files across all **43** active ETS2 `1.62` locales (`fr_ca` included, dead `fr_qc` excluded) with **zero `.dds`/`.tobj` texture baking**.
- **Independent Offline SCS Workshop Validator:** Checks generated packages against SCS error codes `00001`–`00010`, warnings `WARN 00001`/`00002`, `276x162` RGB JPEG icons, `mp_mod_optional: true`, Zero-DDS purity, 43-locale parity, and license-taint invariants (`ETS2R-INV-*`).
- **Conflict-Free Map Combo Merging (`FieldOwnershipPolicy`):** Preserves map-owned identity and geometry (`country_id`, `pos`, `regions[]` including UK `scotland`/`wales`, `train`/`tram`, `leftside_traffic`, `imperial_units`), applies `max_of_map_and_real` axle ladders (never downgrading heavy-haul maps), skips single-TZ shifts on multi-TZ definitions (`patch_if_single_tz`), transparently reports protected `AEM!`/`3nK`/encrypted ZIP archives with `--unpacked-defs` support (zero cracking or decryption), and supports opt-in `--patch-hardcoded-totems`.

---

## Documentation Map

| Guide | Audience | What It Covers |
| --- | --- | --- |
| [**Player & Map Combo User Guide**](docs/USER_GUIDE.md) | ETS2 players & map-combo users | Choosing an edition, Mod Manager load order, installing Core / ProMods / Combo patches, protected archives, and troubleshooting |
| [**Complete CLI Reference**](docs/CLI_REFERENCE.md) | Power users & developers | Every `ets2-realism` subcommand, flag, default path, exit code, and JSON output schema |
| [**Architecture & Pipeline Design**](docs/ARCHITECTURE.md) | Contributors & reviewers | VFS stack, SII/SUI parser, clean-room baseline extraction, 225-territory registry, snapshot schema, merge policies, and ODbL quarantine |
| [**Contributing & Maintainer Guide**](CONTRIBUTING.md) | Contributors & maintainers | Local dev setup, coding standards, PR checklist, adding countries/aliases, and weekly Workshop upload handoff |
| [**License & Data Attribution**](LICENSE) | Everyone | MIT source license and CC BY 4.0 curated data license terms |

---

## Requirements & Quick Start

### Prerequisites

- Python `>= 3.12`
- [`uv`](https://docs.astral.sh/uv/) package manager
- Optional: [GitHub CLI (`gh`)](https://cli.github.com/) to download verified public `snapshots-latest` releases

### Quick Start

1. **Clone and install locked dependencies:**

   ```bash
   git clone https://github.com/MissionWAR/ets2-country-realism.git
   cd ets2-country-realism
   uv sync --locked
   uv run --offline ets2-realism --version
   uv run --offline ets2-realism --help
   ```

2. **Download and verify the latest public realism snapshots (`snapshots-latest`):**

   ```bash
   gh release download snapshots-latest \
     --repo MissionWAR/ets2-country-realism \
     --pattern 'realism-snapshot-*.json' \
     --pattern 'SHA256SUMS.txt' \
     --dir dist/snapshots \
     --clobber

   uv run --offline ets2-realism registry snapshot-verify \
     dist/snapshots/realism-snapshot-summer.json \
     --checksums dist/snapshots/SHA256SUMS.txt \
     --expected-edition summer
   ```

3. **Build or compose the edition you need (100% offline):**

   - **Local Map Combo Auto-Composer** (places `zz_ETS2_Realism_ComboPatch_Summer.scs` directly in your ETS2 `mod/` folder; put it at the **very top** of Mod Manager):

     ```bash
     uv run --offline ets2-realism compose-local \
       --season summer \
       --mod-dir "<ETS2_MOD_DIR>" \
       --game-log "<ETS2_GAME_LOG>" \
       --snapshot dist/snapshots/realism-snapshot-summer.json \
       --checksums dist/snapshots/SHA256SUMS.txt \
       --out-dir "<ETS2_MOD_DIR>"
     ```

   - **ProMods Companion Edition** (reads your locally installed ProMods archives; pass `--edition summer` or `--edition winter` when using `--snapshot`, or omit `--snapshot` to build both seasons from `state/prices.lock.json`):

     ```bash
     uv run --offline ets2-realism package promods \
       --edition summer \
       --mod-dir "<ETS2_MOD_DIR>" \
       --snapshot dist/snapshots/realism-snapshot-summer.json \
       --checksums dist/snapshots/SHA256SUMS.txt \
       --out-dir dist/promods
     ```

   - **Vanilla + DLC Core Edition** (builds both `Summer` & `Winter` Workshop directories and local ZIPs):

     ```bash
     uv run --offline ets2-realism package build --out-dir dist
     ```

---

## Common CLI Commands

See [**docs/CLI_REFERENCE.md**](docs/CLI_REFERENCE.md) for the complete flag reference across all top-level command groups (`vfs`, `baseline`, `registry`, `package`, `validate`, `publish`, `fetch`, `compose-local`, `audit`).

```bash
# Validate the 225-territory canonical country law & mapping registry
uv run --offline ets2-realism registry validate

# Build Vanilla+DLC Core Summer & Winter Workshop + Local ZIP packages offline
uv run --offline ets2-realism package build --out-dir dist

# Run the Offline SCS Workshop Validator on staged Workshop roots and local ZIPs
uv run --offline ets2-realism validate workshop dist/workshop/summer
uv run --offline ets2-realism validate local dist/local/ETS2_Country_Realism_Core_Summer.zip

# Build both ProMods Companion Editions offline using state/prices.lock.json
uv run --offline ets2-realism package promods --mod-dir "<ETS2_MOD_DIR>" --out-dir dist/promods

# Compose a conflict-free local multi-map combo patch offline
uv run --offline ets2-realism compose-local \
  --season summer \
  --mod-dir "<ETS2_MOD_DIR>" \
  --game-log "<ETS2_GAME_LOG>" \
  --out-dir "<ETS2_MOD_DIR>"

# Run online weekly FX & multi-tier fuel price collection (EU Tier 1 + Global Tier 1 + Tier 2)
uv run ets2-realism fetch --lock-path state/prices.lock.json

# Run clean-room provenance & license-taint audit
uv run --offline ets2-realism audit taint --json
```

---

## Automated Weekly Pipeline

GitHub Actions drives the weekly release cadence with strict clean-room and credential isolation:

- **Weekly Release Schedule ([`.github/workflows/phase-a-release.yml`](.github/workflows/phase-a-release.yml)):** Runs automatically every **Friday at `06:00 UTC`** (plus manual `workflow_dispatch`). It executes all offline quality gates, fetches live multi-tier FX & fuel prices into `state/prices.lock.json`, runs diff-gated `ets2-realism publish release`, and verifies all staged packages and `SHA256SUMS.txt` manifests offline.
- **Rolling Public `snapshots-latest` Release:** Whenever canonical payloads or snapshots change, CI automatically updates the public `snapshots-latest` GitHub Release with verified `schema_version=1` `realism-snapshot-summer.json`, `realism-snapshot-winter.json`, and `SHA256SUMS.txt` assets for offline `compose-local` and ProMods Companion builds.
- **Zero ProMods Files in Git:** Neither the repository nor CI ever stores or redistributes proprietary ProMods `.scs`, `.sii`, or `.sui` files.
- **Zero Steam Secrets in CI:** CI uploads the validated `phase-a-release-bundle` artifact and opens/updates a persistent `release/phase-a-weekly` PR. Steam Workshop uploads are performed manually by the maintainer via **SCS Workshop Uploader** (AppID `421800`) before merging the ledger PR.
- **Quarantined Monthly OSM Speed-Limit Audit ([`.github/workflows/osm-speed-audit.yml`](.github/workflows/osm-speed-audit.yml)):** Runs read-only on the first Monday of each month (`07:00 UTC`) to flag potential statutory speed-limit drift for human verification against official government statutes — with zero automated Git writes to keep `data/laws/` strictly free of ODbL taint.

---

## Development & Quality Gates

All pull requests and pushes to `master`/`main` are gated by [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Run the full offline check suite locally before opening a PR:

```bash
uv run --offline ruff check
uv run --offline ruff format --check
uv run --offline basedpyright
uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"
uv run --offline ets2-realism audit taint --json
```

For setup details, coding conventions, and maintainer release steps, see [**CONTRIBUTING.md**](CONTRIBUTING.md).

---

## Licensing & Open Data Attribution

- **Source code & tooling (`src/`, `scripts/`, `tests/`):** [MIT License](LICENSE).
- **Curated statutory registries & snapshots (`data/laws/`, `data/mappings/`, `data/curated/`):** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Open FX & Fuel Data Sources:**
  - **FX reference rates:** Frankfurter v2 (MIT), European Central Bank (`eurofxref-daily.xml`), `@fawazahmed0/currency-api` (CC0), Central Bank of Russia daily XML.
  - **European & EEA Tier 1 fuel feeds:** European Commission Weekly Oil Bulletin (CC BY 4.0), UK DESNZ (OGL v3.0), Statistics Norway SSB (CC BY 4.0), France `data.economie.gouv.fr` OpenDataSoft v2.1 API (Licence Ouverte 2.0), Germany Tankerkönig (CC BY 4.0, optional API key), Spain MITECO, Italy MIMIT (IODL 2.0), Netherlands CBS StatLine (CC BY 4.0), with `fuel-prices.eu` (CC BY 4.0) and FionnHughes EC WOB CSV mirror fallbacks.
  - **Global Tier 1 & Tier 2 national feeds:** US EIA v2 (optional API key), Brazil ANP, Argentina Secretaría de Energía, Colombia SICOM/CREG, Chile CNE (optional API token), Malaysia OpenDOSM (CC BY 4.0), Japan METI, Korea KNOC Opinet (optional API key), Iceland Gasvaktin (MIT), Switzerland BFS/LIK, Moldova ANRE, North Macedonia ERC, Russia Rosstat, Israel Ministry of Energy, UAE MOEI, South Africa DMRE/CEF, Saudi Aramco, Nigeria NBS.
