# ETS2 Country Realism

Open-source (**MIT** code / **CC BY 4.0** curated data), clean-room Python 3.12+ pipeline, mod compiler, and local map-combo composer for **Euro Truck Simulator 2 `1.62+`**.

Maintained by **MissionWAR**.

## What It Generates

1. **Steam Workshop Vanilla + DLC Core Editions (`Summer` & `Winter`):**
   - Covers all 36 SCS `1.62` Vanilla+DLC countries from clean-room JSON baselines and statutory law registries (`data/laws/countries/`, `data/baselines/ets2_1.62_def/`).
   - Dynamic seasonal DST timezone offsets via Python `zoneinfo` + `tzdata` (honoring ETS2's 12 `@@tz_*@@` keys and emitting plain abbreviations such as `"CET"`, `"WET"`, `"AST"` elsewhere).
   - **Option 4b Zero-DDS Fuel Totems:** Rewrites all 460 single-text `1.62` `def/sign/board/*.sii` boards to namespaced `@@fp_*_ets2r@@` tokens backed by synchronized `locale/<lang>/local_module.ets2r_fuel.sii` across all **43** active ETS2 `1.62` locales (`fr_ca` included, dead `fr_qc` excluded) with **zero `.dds`/`.tobj` texture baking**.
   - Validated by an independent **Offline SCS Workshop Validator** enforcing SCS error codes `00001`–`00010`, warnings `WARN 00001`/`00002`, `276x162` RGB JPEG icons, `mp_mod_optional: true`, Zero-DDS, locale parity, and license-taint checks (`ETS2R-INV-*`).
2. **ProMods Companion Editions (`Summer` & `Winter`):**
   - Built locally from your own installed ProMods archives (`EU` + `ME` + `MA` + `TGS`) via `ets2-realism package promods`.
   - Dynamically updates `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` across all 43 active locales while preserving UK `scotland`/`wales` regions, multi-timezone definitions, and map geometry.
   - **Zero** proprietary ProMods `.scs`, `.sii`, or `.sui` files are ever stored in this repository.
3. **Local Map Combo Auto-Composer (`ets2-realism compose-local`):**
   - Runs 100% offline against the global `225`-territory `realism-snapshot-{summer|winter}.json` (`schema_version=1`) and your local ETS2 `mod/` load order (*ProMods*, *RusMap*, *TST*, *UMCF*, *Beyond*, *EAA*, *SEA*, *RoC*, *Project Japan*, *JRR*, Africa maps, etc.) to emit `zz_ETS2_Realism_ComboPatch_{Summer|Winter}.scs`.
   - Enforces `FieldOwnershipPolicy`: preserves map-owned identity/geometry (`country_id`, `pos`, `regions[]`, `train`/`tram`, `leftside_traffic`, `imperial_units`), applies `max_of_map_and_real` axle ladders (never downgrading heavy maps), skips single-TZ shifts on multi-TZ definitions (`patch_if_single_tz`), reports protected `AEM!`/`3nK`/encrypted ZIP archives with `--unpacked-defs` support (zero cracking/decryption), and supports opt-in `--patch-hardcoded-totems`.

## Requirements & Quick Start

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) package manager

```bash
uv sync --locked
uv run --offline ets2-realism --version
uv run --offline ets2-realism --help
```

## Common CLI Commands

```bash
# Validate the 225-territory canonical country law & mapping registry
uv run --offline ets2-realism registry validate

# Build Vanilla+DLC Core Summer & Winter Workshop + Local ZIP packages offline
uv run --offline ets2-realism package build --out-dir dist

# Run the Offline SCS Workshop Validator
uv run --offline ets2-realism validate workshop dist/workshop/summer
uv run --offline ets2-realism validate local dist/local/ETS2_Country_Realism_Core_Summer.zip

# Verify signed-off v1 realism snapshots against SHA256SUMS.txt
uv run --offline ets2-realism registry snapshot-verify dist/snapshots/realism-snapshot-summer.json --checksums dist/snapshots/SHA256SUMS.txt --expected-edition summer

# Build local ProMods Companion Editions (uses your local ETS2 mod/ directory)
uv run --offline ets2-realism package promods --mod-dir "<ETS2_MOD_DIR>" --out-dir dist/promods

# Compose a conflict-free local multi-map combo patch offline
uv run --offline ets2-realism compose-local --season summer --mod-dir "<ETS2_MOD_DIR>" --game-log "<ETS2_GAME_LOG>" --out-dir "<ETS2_MOD_DIR>"

# Run online weekly FX & multi-tier fuel price collection (Tier 1 EU + Global + Tier 2 guarded portals)
uv run ets2-realism fetch --lock-path state/prices.lock.json

# Run clean-room provenance / license-taint audit
uv run --offline ets2-realism audit taint --json
```

## Development & Quality Gates

```bash
uv run --offline ruff check
uv run --offline ruff format --check
uv run --offline basedpyright
uv run --offline pytest -q --tb=short -m "not local_ets2 and not local_promods"
```

## Licensing & Open Data Attribution

- **Source code & tooling (`src/`, `scripts/`, `tests/`):** [MIT License](LICENSE).
- **Curated statutory registries & snapshots (`data/laws/`, `data/mappings/`, `data/curated/`):** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Open FX & Fuel Data Sources:**
  - FX reference rates: Frankfurter v2 (MIT), European Central Bank (`eurofxref-daily.xml`), `@fawazahmed0/currency-api` (CC0), Central Bank of Russia daily XML.
  - European & EEA Tier 1 fuel feeds: European Commission Weekly Oil Bulletin (CC BY 4.0), `fuel-prices.eu` (CC BY 4.0), UK DESNZ (OGL v3.0), Statistics Norway SSB (CC BY 4.0), France `prix-carburants.gouv.fr` (Licence Ouverte 2.0), Germany Tankerkönig (CC BY 4.0, optional API key), Spain MITECO, Italy MIMIT (IODL 2.0), Netherlands CBS StatLine (CC BY 4.0).
  - Global Tier 1 & Tier 2 national feeds: US EIA v2 (optional API key), Brazil ANP, Argentina Secretaría de Energía, Colombia SICOM/CREG, Chile CNE, Malaysia OpenDOSM (CC BY 4.0), Japan METI, Korea KNOC Opinet (optional API key), Iceland Gasvaktin (MIT), Switzerland BFS/LIK, Moldova ANRE, North Macedonia ERC, Russia Rosstat, Israel Ministry of Energy, UAE MOEI, South Africa DMRE/CEF, Saudi Aramco, Nigeria NBS.
