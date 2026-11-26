<!-- generated-by: gsd-doc-writer -->
# ETS2 Country Realism — Player & Power-User Guide

Welcome to **ETS2 Country Realism** for **Euro Truck Simulator 2 (`1.62.3.3s+`)**. This guide helps you choose the right edition for your map setup, configure ETS2 Mod Manager load order cleanly, compose conflict-free local map-combo patches, build standalone ProMods Companion editions, and troubleshoot common issues.

---

## 1. Choosing the Right Edition

ETS2 Country Realism ships in **Summer** (July 15 DST anchor, summer daytime running lights, and summer seasonal speed limits in Finland, Estonia, and Lithuania) and **Winter** (January 15 standard-time anchor, winter daytime running lights, and winter seasonal speed limits) variants across three editions:

| Edition | Best For | How You Get It | Output / Mod Package |
| --- | --- | --- | --- |
| **Vanilla + DLC Core Edition** | Standard ETS2 `1.62+` map + official SCS map DLCs (all 36 SCS countries) | Steam Workshop subscription *(or build locally with `ets2-realism package build`)* | Workshop item or `ETS2_Country_Realism_Core_{Summer,Winter}.zip` |
| **ProMods Companion Edition** | ProMods **EU** (with optional **TGS**, **ME**, and **MA** add-ons) and no other map mods | Build locally from your installed ProMods archives via `ets2-realism package promods` | `ETS2_Country_Realism_ProMods_{Summer,Winter}.zip` + unpacked Workshop roots |
| **Local Map Combo Patch (`compose-local`)** | Multi-map combos (ProMods + RusMap, TST, UMCF, Beyond, EAA, SEA, RoC, Project Japan, JRR, Africa maps, etc.) | Compose 100% offline from your active load order + weekly snapshot via `ets2-realism compose-local` | `zz_ETS2_Realism_ComboPatch_{Summer,Winter}.scs` |

> **Important:** All three editions are **standalone replacements for one another**. Enable **only one** edition and **only one** season (`Summer` **or** `Winter`) in your ETS2 profile at a time.

### What Every Edition Provides
- **Verified statutory country laws:** Real-world speed limits for `car`, `truck` (>3.5t), and `bus` classes, daytime running light (`lights_mandatory`) rules, fatigue rules (`driving_tired_offence`), and axle weight ceilings (`mass_limit_per_axle_count`).
- **Dynamic seasonal timezones:** Computed via Python `zoneinfo` + `tzdata`, honoring ETS2's 12 built-in `@@tz_*@@` locale keys and clean plain abbreviations elsewhere.
- **Zero-DDS roadside fuel totems:** Updates all 460 single-text Vanilla `def/sign/board/*.sii` fuel price signs via namespaced `@@fp_*_ets2r@@` tokens backed by `locale/<lang>/local_module.ets2r_fuel.sii` across all **43** active ETS2 `1.62` locales — with **zero `.dds`/`.tobj` texture files**. ProMods Companion and Combo Patch builds also dynamically update ProMods `local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii` across all 43 locales.
- **Safe, minimal footprint:** Never emits `def/country.sii` or `def/country.*.sii` registration files, so map registrations and road connections stay intact.

---

## 2. ETS2 Mod Manager Load-Order Rules

In Euro Truck Simulator 2, **Mod Manager resolves priority from bottom (lowest) to top (highest)** — mods placed higher in the active list override files from mods below them.

### Recommended Placement

```text
[TOP — HIGHEST PRIORITY]
  1. ETS2 Country Realism (pick ONE):
     - zz_ETS2_Realism_ComboPatch_Summer.scs  (or Winter)        <-- Multi-map combos
     - ETS2 Country Realism - Summer (ProMods Edition) (or Winter) <-- ProMods-only
     - ETS2 Country Realism - Summer (Core)            (or Winter) <-- Vanilla + DLC
  2. Map fixes, road connections, and background maps
  3. ProMods Def / ME / MA / TGS & other map mods
[BOTTOM — LOWEST PRIORITY]
```

### Essential Mod Manager Checklist
- **Place at the top of your active list:**
  - **Combo Patch (`zz_ETS2_Realism_ComboPatch_*.scs`):** Place at the **very top** of Mod Manager (above all map mods, road connections, map fix packs, and ProMods Def).
  - **ProMods Companion Edition:** Place **above** ProMods Def, Middle East (ME), Maghreb/Africa (MA), and The Great Steppe (TGS). Disable the Vanilla Core Edition.
  - **Core Edition:** Place above any mods that might alter country definitions. Pairs cleanly with seasonal weather/graphics mods without touching `def/country.sii`.
- **Keep only ONE realism overlay active:** Disable any legacy or third-party **real fuel prices**, **realistic speed limits**, **country realism**, or **timezone** mods so they do not overwrite or conflict with ETS2 Country Realism. Do not enable both `Summer` and `Winter` simultaneously.
- **Convoy Multiplayer (`mp_mod_optional: true`):** Every generated package (Core, ProMods Edition, and Combo Patch) sets `mp_mod_optional: true` in `manifest.sii`. You can safely keep the mod enabled in Convoy multiplayer sessions even when other participants do not have it installed.

---

## 3. Prerequisites for Local CLI Workflows

If you only use the **Vanilla + DLC Core Edition** from Steam Workshop, you do not need Python or the CLI.

To run the **Local Map Combo Auto-Composer** (`compose-local`), **ProMods Companion Builder** (`package promods`), or local Core builds (`package build`), install:

1. **Python `>= 3.12`**
2. **[`uv`](https://docs.astral.sh/uv/)** package manager

Clone the repository and sync locked dependencies from the repository root:

```bash
git clone https://github.com/MissionWAR/ets2-country-realism.git
cd ets2-country-realism
uv sync --locked
uv run --offline ets2-realism --version
```

> **Tip:** Run `ets2-realism` commands from the **repository root** (or pass `uv run --directory <path-to-repo> --offline ets2-realism ...`) so default relative paths (`data/laws`, `data/mappings/`, `data/baselines/ets2_1.62_def`, `assets/icons`, `state/prices.lock.json`) resolve automatically.

---

## 4. Local Map Combo Auto-Composer Guide (`compose-local`)

`ets2-realism compose-local` reads your active ETS2 map combo load order completely offline, resolves every active country against the global 225-territory realism snapshot, applies strict `FieldOwnershipPolicy` guardrails, validates the resulting archive with the built-in Offline SCS Validator, and writes `zz_ETS2_Realism_ComboPatch_Summer.scs` or `zz_ETS2_Realism_ComboPatch_Winter.scs`.

### Step 1: Download the Latest Weekly Snapshot & Verify `SHA256SUMS.txt`

Every Friday at `06:00 UTC`, the automated release workflow publishes updated `schema_version=1` snapshots and checksums to the rolling public GitHub Release tag **`snapshots-latest`**:

- Release page: `https://github.com/MissionWAR/ets2-country-realism/releases/tag/snapshots-latest`
- Assets:
  - `realism-snapshot-summer.json`
  - `realism-snapshot-winter.json`
  - `SHA256SUMS.txt`

Download them into a local folder (for example `dist/snapshots/`) via your browser or GitHub CLI:

```bash
gh release download snapshots-latest \
  --repo MissionWAR/ets2-country-realism \
  --pattern "realism-snapshot-*.json" \
  --pattern "SHA256SUMS.txt" \
  --dir dist/snapshots \
  --clobber
```

Verify the downloaded snapshot offline against `SHA256SUMS.txt`:

```bash
uv run --offline ets2-realism registry snapshot-verify \
  dist/snapshots/realism-snapshot-summer.json \
  --checksums dist/snapshots/SHA256SUMS.txt \
  --expected-edition summer
```

> **Automatic sibling checksum check:** Whenever `SHA256SUMS.txt` is stored in the same directory as the snapshot file, `registry snapshot-verify`, `compose-local`, and `package promods` automatically verify the snapshot against that sibling `SHA256SUMS.txt` even if you omit `--checksums`.

### Step 2: Choose a Load-Order Source

`compose-local` requires **exactly one** of these mutually exclusive load-order flags:

| Flag | Recommended? | How It Works |
| --- | --- | --- |
| `--game-log <path>` | **Yes (Recommended)** | Reads ETS2's `game.log.txt` and extracts the most recent active profile mount session (`[mod_package_manager] Mod "..." has been mounted.`), ignoring startup directory scans and unmount cycles. Works even if your ETS2 profile is encrypted. |
| `--profile <path>` | Plaintext profiles only | Parses `active_mods[]` from a plaintext ETS2 `profile.sii`. **Refuses `ScsC`-encrypted profiles** (never decrypts SCS save/profile files). |
| `--modlist <path>` | Custom / headless lists | Reads a plain text file with one mod per line (blank lines and `#` comments ignored). Accepts archive stems/filenames, `workshop:<id>`, `mod_workshop_package.<16-hex>`, or explicit archive/folder paths (UNC network paths are rejected). |

When using `--modlist`, control line ordering with `--modlist-order`:
- `--modlist-order top-to-bottom` *(default)*: Matches the ETS2 Mod Manager UI — line 1 is the **highest** priority mod.
- `--modlist-order bottom-to-top`: Matches VFS mount order — line 1 is the **lowest** priority mod.

> **Encrypted `profile.sii` note:** By default, ETS2 saves `profile.sii` in encrypted `ScsC` format. If you pass an encrypted file to `--profile`, `ets2-realism` stops cleanly rather than decrypting it. Either switch to `--game-log "<ETS2_USER_DIR>/game.log.txt"`, or set `uset g_save_format "2"` in your ETS2 `config.cfg` and re-save your profile in-game.

### Step 3: Including Local Mods & Steam Workshop `227300` Mods

- **`--mod-dir <path>`:** Your ETS2 local `mod/` directory containing `.scs`, `.zip`, or unpacked mod folders. If omitted, `ets2-realism` checks the `ETS2_MOD_DIR` environment variable, then platform defaults (`D:\ETS2Data\Euro Truck Simulator 2\mod` if present, else `%USERPROFILE%\Documents\Euro Truck Simulator 2\mod` on Windows; `~/.local/share/Euro Truck Simulator 2/mod` on Linux/macOS).
- **`--workshop-dir <path>`:** Your Steam Workshop ETS2 directory (`.../steamapps/workshop/content/227300`). If omitted, `ets2-realism` checks `ETS2_WORKSHOP_DIR`, then checks relative to `--game-dir` (`../../workshop/content/227300`), then standard Steam library locations. Workshop packages are resolved via `versions.sii` (preferring `1.62`-compatible entries, then universal fallbacks).
- **`--game-dir <path>` *(optional)*:** Your ETS2 install folder containing `def.scs`. If omitted, `compose-local` uses the bundled clean-room `1.62` virtual baseline (`data/baselines/ets2_1.62_def`) with zero game-archive extraction required.
- **Automatic self-exclusion:** Any previously generated `zz_ETS2_Realism_ComboPatch_*`, `ets2_country_realism_*`, or package containing `# ets2-realism:managed-package` in `manifest.sii` is automatically excluded from the scanned load order so re-runs always patch cleanly against your underlying map mods. (Pass `--no-self-exclude` only if you intentionally want to disable this safeguard.)

### Step 4: Run `compose-local`

**Windows (PowerShell) — using `game.log.txt` and a downloaded snapshot:**

```powershell
uv run --offline ets2-realism compose-local `
  --season summer `
  --game-log "$HOME\Documents\Euro Truck Simulator 2\game.log.txt" `
  --mod-dir "$HOME\Documents\Euro Truck Simulator 2\mod" `
  --workshop-dir "C:\Program Files (x86)\Steam\steamapps\workshop\content\227300" `
  --snapshot "dist\snapshots\realism-snapshot-summer.json" `
  --checksums "dist\snapshots\SHA256SUMS.txt" `
  --out-dir "$HOME\Documents\Euro Truck Simulator 2\mod" `
  --report-json "dist\compose-report-summer.json"
```

**Linux / macOS — using `game.log.txt` and a downloaded snapshot:**

```bash
uv run --offline ets2-realism compose-local \
  --season summer \
  --game-log "$HOME/.local/share/Euro Truck Simulator 2/game.log.txt" \
  --mod-dir "$HOME/.local/share/Euro Truck Simulator 2/mod" \
  --workshop-dir "$HOME/.local/share/Steam/steamapps/workshop/content/227300" \
  --snapshot "dist/snapshots/realism-snapshot-summer.json" \
  --checksums "dist/snapshots/SHA256SUMS.txt" \
  --out-dir "$HOME/.local/share/Euro Truck Simulator 2/mod" \
  --report-json "dist/compose-report-summer.json"
```

When complete, `compose-local` atomically writes `zz_ETS2_Realism_ComboPatch_Summer.scs` (or `zz_ETS2_Realism_ComboPatch_Winter.scs`) into `--out-dir` (default: `dist/local`). Enable it at the **very top** of ETS2 Mod Manager.

### `FieldOwnershipPolicy` Guarantees

`compose-local` (and `package promods`) enforces a strict `FieldOwnershipPolicy` contract so realism updates never break map geometry, rail traffic, or multi-timezone regions:

| Field / Area | Policy | Guarantee |
| --- | --- | --- |
| `fuel_price`, `lights_mandatory`, `driving_tired_offence` | `always` | Surgically patched from the verified seasonal realism snapshot. |
| `country_id`, `name`, `country_code`, `pos`, `regions[]`, `leftside_traffic`, `imperial_units` | **Map-owned (preserved)** | Never altered — preserves ProMods UK `scotland`/`wales` `regions[]`, left-hand drive flags, map coordinates, and country IDs. |
| `speed_limits.sii` (`car`, `truck`, `bus`) | `always` + **parity guard** | Patches canonical lanes (`local_road`, `expressway`, `motorway`, `slow_road`). **Preserves `train` and `tram` blocks** and any map-added custom lane classes verbatim. If a map's `imperial_units` (`mph` vs `km/h`) disagrees with the snapshot, `speed_limits.sii` is skipped (`skipped_imperial_mismatch`) with a warning. |
| `mass_limit_per_axle_count` | `max_of_map_and_real` | Element-wise maximum across map and real-world axle ladders with carry-forward and monotonic clamping — never downgrades heavy-haul or custom map axle ceilings. |
| `time_zone` / `time_zone_name` | `patch_if_single_tz` | Only patched on single-timezone country definitions. Any country with `secondary_time_zone`, `secondary_time_zone_area`, or `secondary_time_zone_name` (such as Kaliningrad, TST Russia, UMCF Kazakhstan, or EAA Brazil) is skipped (`skipped_multi_tz`). |
| `def/country.sii` & `def/country.*.sii` | **Never emitted** | Zero registration files emitted; honors empty `SiiNunit {}` suppression stubs from higher-priority map fix packs. |

### Handling Protected Archives (`AEM!`, `3nK`, Encrypted ZIPs)

ETS2 Country Realism is strictly clean-room and **never decrypts or cracks** protected map archives. When `compose-local` scans your load order, it detects and classifies protected archives:

- **`aem_protected`:** Archives with an `AEM!` header.
- **`encrypted_zip`:** Password-protected/encrypted ZIP archives.
- **`three_nk_obfuscated`:** Country `.sii`/`.sui` entries starting with the `3nK\x01` obfuscation header.

By default, `compose-local` logs a warning for each unsubstituted protected archive, records full details in `ComposeReport.protected_archives` (including whether a higher readable layer already overrides its visible country/board paths via `overridden_by_higher_layer`), and continues patching all readable layers.

#### Substituting Protected Archives with `--unpacked-defs`

If you have legitimately unpacked a protected map's `def/` files locally, pass `--unpacked-defs <dir>` (repeatable):

1. **In-place priority substitution (recommended):** Create a subfolder inside `<dir>` named after the archive's stem (filename without `.scs`/`.zip`) and place its extracted `def/` (and optional `locale/`) inside it:
   ```text
   unpacked_defs/
   └── my_protected_map_def/
       └── def/
           └── country/
               └── ...
   ```
   Pass `--unpacked-defs unpacked_defs`. `compose-local` mounts `unpacked_defs/my_protected_map_def/` at the **exact load-order priority** of `my_protected_map_def.scs`.
2. **High-priority raw override:** If a directory passed to `--unpacked-defs` directly contains `def/`, `locale/`, `base/def/`, or `base/locale/`, it mounts above the active load order as a high-priority override.

#### Failing Fast with `--strict-protected`

Pass `--strict-protected` if you want `compose-local` to exit non-zero **without writing a `.scs` file** whenever any protected archive in your load order remains unsubstituted:

```bash
uv run --offline ets2-realism compose-local \
  --season summer \
  --game-log "<ETS2_GAME_LOG>" \
  --mod-dir "<ETS2_MOD_DIR>" \
  --strict-protected \
  --dry-run
```

### Totem, Audit & Dry-Run Options

| Flag | Default | Purpose |
| --- | --- | --- |
| `--patch-hardcoded-totems` | Off | Opt-in surgical rewriting of verified single-text hardcoded numeric gas signs — including JRR (`indo_gas_totem_01{a,l,m,n,o,p,q,r}`) and community `{kg,kz,uz,tm,cn,ru,by,ua}_gas_*_{92,95,98,100,diesel,diesel_plus,lpg}` boards — into `@@fp_*_ets2r@@` tokens. Strictly skips station IDs, label boards, multi-item signs, already-localized boards, and ambiguous boards. |
| `--no-totems` | Off | Emits `def/country/` realism patches only; skips all Vanilla sign boards, ProMods fuel locale modules, and hardcoded totems. |
| `--dry-run` | Off | Runs the entire load-order scan, policy merge, and audit without writing a `.scs` file. |
| `--report-json <path>` | None | Writes the deterministic sorted JSON `ComposeReport` (per-country match tiers, timezone/axle/speed-limit actions, custom lanes preserved, protected archives, and totem actions) to `<path>`. |
| `--json` | Off | Prints the `ComposeReport` JSON directly to stdout. |
| `--aliases <path>` | None | Optional user `country_aliases.json` merged atop bundled `data/mappings/country_aliases.json` for custom map country slugs. |
| `--package-version <str>` | Auto (`1.62-YYYY.WW`) | Optional explicit `package_version` override for `manifest.sii`. |
| `--author <str>` | `MissionWAR` | Optional `author` override for `manifest.sii`. |

### Weekly Update Routine (No Local Fetch Needed!)

You do **not** need to run `ets2-realism fetch` or configure any fuel API keys to keep your combo patch up to date:

1. Download the latest `realism-snapshot-{summer|winter}.json` and `SHA256SUMS.txt` from the `snapshots-latest` GitHub Release.
2. Re-run your saved `ets2-realism compose-local` command pointing `--snapshot` at the downloaded file and `--out-dir` at your ETS2 `mod/` folder.
3. Automatic self-exclusion skips your previous `zz_ETS2_Realism_ComboPatch_*.scs`, verifies the snapshot checksum, validates the newly built `.scs`, and replaces the old archive atomically.

---

## 5. Local ProMods Companion Builder Guide (`package promods`)

If you play **ProMods** (`EU` alone, or `EU` + any combination of `TGS`, `ME`, and `MA`) without additional third-party map combos, you can build a standalone all-in-one ProMods Companion Edition locally.

### Why ProMods Builds Run Locally

To strictly respect the **ProMods no-reupload / no-redistribution EULA**, zero ProMods `.scs`, `.sii`, or `.sui` files are ever stored in this repository or redistributed in public releases. Instead, `ets2-realism package promods` reads your own locally installed ProMods archives on your machine and outputs a minimal realism-only package for your personal use.

### Supported ProMods Archives & Auto-Discovery

When you pass `--mod-dir` (or rely on `ETS2_MOD_DIR` / default ETS2 `mod/` folder), `package promods` automatically discovers the newest version of each ProMods archive (`.scs` or `.zip`), stacking them in official bottom-to-top priority order (**Vanilla < EU < TGS < ME < MA**):

| Pack | Role | Auto-Discovered Filename Pattern | Explicit Override Flag | Required? |
| --- | --- | --- | --- | --- |
| **ProMods Europe (EU)** | Def | `promods-def-v*.scs` / `promods-eu-def-v*.scs` *(prefers non-ST over `-st-` at equal version)* | `--promods-eu` | **Always required** |
| **ProMods Europe (EU)** | Assets | `promods-assets-v*.scs` / `promods-eu-assets-v*.scs` | `--promods-eu-assets` | Optional *(required with `--require-all-packs`)* |
| **The Great Steppe (TGS)** | Defmap | `promods-tgs-defmap-v*.scs` | `--promods-tgs` | Optional *(required with `--require-all-packs`)* |
| **The Great Steppe (TGS)** | Assets | `promods-tgs-assets-v*.scs` | `--promods-tgs-assets` | Optional *(required with `--require-all-packs`)* |
| **Middle East (ME)** | Defmap | `promods-me-defmap-v*.scs` | `--promods-me` | Optional *(required with `--require-all-packs`)* |
| **Middle East (ME)** | Assets | `promods-me-assets-v*.scs` | `--promods-me-assets` | Optional *(required with `--require-all-packs`)* |
| **Maghreb / Africa (MA)** | Defmap | `promods-ma-defmap-v*.scs` | `--promods-ma` | Optional *(required with `--require-all-packs`)* |
| **Maghreb / Africa (MA)** | Assets | `promods-ma-assets-v*.scs` | `--promods-ma-assets` | Optional |

### Building Your ProMods Edition

**Build both Summer and Winter editions using auto-discovery:**

```bash
uv run --offline ets2-realism package promods \
  --edition all \
  --mod-dir "<ETS2_MOD_DIR>" \
  --out-dir dist/promods
```

**Build a single season from a downloaded `snapshots-latest` snapshot (with `--require-all-packs`):**

```bash
uv run --offline ets2-realism package promods \
  --edition summer \
  --mod-dir "<ETS2_MOD_DIR>" \
  --snapshot dist/snapshots/realism-snapshot-summer.json \
  --checksums dist/snapshots/SHA256SUMS.txt \
  --require-all-packs \
  --out-dir dist/promods
```

> **Note:** When using `--snapshot` with `package promods`, you must specify a single season (`--edition summer` or `--edition winter`), because each snapshot file targets one season. When `--snapshot` is omitted, `package promods` builds from the repository's `data/laws/`, `data/mappings/`, `data/baselines/ets2_1.62_def/`, and `state/prices.lock.json` (`--prices-lock`).

**Explicit archive overrides (useful if your archives are stored outside `mod/`):**

```bash
uv run --offline ets2-realism package promods \
  --edition summer \
  --promods-eu "/path/to/promods-def-v285.scs" \
  --promods-eu-assets "/path/to/promods-assets-v285.scs" \
  --promods-me "/path/to/promods-me-defmap-v285.scs" \
  --promods-me-assets "/path/to/promods-me-assets-v285.scs" \
  --promods-ma "/path/to/promods-ma-defmap-v105.scs" \
  --promods-tgs "/path/to/promods-tgs-defmap-v171.scs" \
  --promods-tgs-assets "/path/to/promods-tgs-assets-v171.scs" \
  --out-dir dist/promods
```

### ProMods Build Outputs

Every build runs the Offline SCS Workshop Validator (`profile="promods"`) on both targets before promoting them atomically. With `--out-dir dist/promods`, you receive:

- **Unpacked Workshop directories:**
  - `dist/promods/workshop/promods-summer/` (`versions.sii` + `universal/...`)
  - `dist/promods/workshop/promods-winter/` (`versions.sii` + `universal/...`)
- **Local ZIP packages (ready for ETS2 `mod/`):**
  - `dist/promods/local/ETS2_Country_Realism_ProMods_Summer.zip`
  - `dist/promods/local/ETS2_Country_Realism_ProMods_Winter.zip`

Copy **one** seasonal `.zip` into your ETS2 `mod/` folder and place it **above** ProMods Def in Mod Manager (with Vanilla Core disabled).

*(If you also want to build the Vanilla + DLC Core Edition locally offline, run `uv run --offline ets2-realism package build --edition all --out-dir dist`, which produces `dist/workshop/{summer,winter}/` and `dist/local/ETS2_Country_Realism_Core_{Summer,Winter}.zip`.)*

---

## 6. Troubleshooting Common Issues

### External Working Directory (CWD) & Tracked Output Directory Guards

- **Missing `data/baselines/...` or `data/mappings/...` errors when running outside the repo:**
  Default CLI paths (`--laws-dir`, `--mappings`, `--aliases`, `--baseline-dir`, `--icons-dir`, `--prices-lock`) are relative to the current working directory. Run commands from the repository root (`cd ets2-country-realism`), or invoke `uv` with `--directory`:
  ```bash
  uv run --directory /path/to/ets2-country-realism --offline ets2-realism compose-local ...
  ```
- **`Refusing to write ProMods/Combo output directly into repository root` or `inside tracked/unignored repository directory`:**
  Both `package promods` and `compose-local` block writing outputs to the repository root or git-tracked directories so third-party derived mods are never accidentally committed. Point `--out-dir` to a gitignored subdirectory inside the repo (`dist`, `out`, `build`, `raw`, `vendor`) or directly to an external path such as your ETS2 `mod/` folder.

### `ScsC`-Encrypted `profile.sii` Refused

If you see:

```text
Profile ... is ScsC-encrypted; ETS2 Country Realism never decrypts SCS profiles.
```

Choose either fix:
1. **Easiest:** Use `--game-log "<ETS2_USER_DIR>/game.log.txt"` instead of `--profile`.
2. **Plaintext profiles:** Open `<ETS2_USER_DIR>/config.cfg`, change `uset g_save_format "0"` to `uset g_save_format "2"`, launch ETS2, load your profile, and save once so ETS2 rewrites `profile.sii` in plaintext.

### Missing `promods-eu-def` or Missing Packs under `--require-all-packs`

- **`Required ProMods EU def archive not found`:** Confirm `--mod-dir` points to the exact folder holding your `promods-def-v*.scs` (or `promods-eu-def-v*.scs`) file, or pass `--promods-eu "<path>"` explicitly.
- **`Missing required ProMods packs under --require-all-packs`:** `--require-all-packs` requires all 7 slots (`EU def`, `EU assets`, `TGS defmap`, `TGS assets`, `ME defmap`, `ME assets`, and `MA defmap`). If you do not use all four ProMods expansions, omit `--require-all-packs` and `package promods` will compile for the packs you have installed.
- **`--snapshot targets a single season`:** When passing `--snapshot` to `package promods`, add `--edition summer` or `--edition winter` (the default `--edition all` builds both seasons and cannot use a single-season snapshot).

### Protected Archives (`aem_protected`, `encrypted_zip`, `three_nk_obfuscated`)

- Run with `--report-json dist/compose-report.json` (or `--json`) and inspect the `protected_archives` list.
- If `"overridden_by_higher_layer": true` is reported for an archive, a higher readable mod already overrides its visible relevant country/board paths and no action is needed.
- If the protected archive owns unique map countries that you want patched, extract its `def/` tree locally into `<unpacked_root>/<archive_stem>/def/...` and re-run with `--unpacked-defs <unpacked_root>`.
- Remember: `compose-local` succeeds with warnings by default; pass `--strict-protected` only if you want unsubstituted protected archives to fail the build.

### Snapshot Verification Errors

- **`SHA-256 mismatch` / `UTF-8 BOM detected` / `Non-LF line endings detected`:** Re-download `realism-snapshot-{summer|winter}.json` and `SHA256SUMS.txt` directly as raw files (avoid opening and re-saving them in editors that convert LF to CRLF or insert a UTF-8 BOM).
- **`Edition mismatch`:** Make sure `--season summer` (or `--edition summer`) is paired with `realism-snapshot-summer.json`, and `winter` with `realism-snapshot-winter.json`.

### Verifying Clean Loading in `game.log.txt`

After enabling your generated mod in ETS2 Mod Manager and loading into the truck cabin:

1. Open your ETS2 `game.log.txt`:
   - **Windows:** `%USERPROFILE%\Documents\Euro Truck Simulator 2\game.log.txt`
   - **Linux:** `~/.local/share/Euro Truck Simulator 2/game.log.txt`
2. Verify the `[mod_package_manager]` lines show your ETS2 Country Realism package mounted **last** (highest priority) and no other conflicting speed-limit/fuel-price mods mounted above it.
3. Search `game.log.txt` for `<ERROR>` or `ets2r` / `country`:
   - Confirm zero `[unit]` parse errors in `def/country/` or `def/sign/board/`.
   - Confirm zero missing localization key warnings (`@@fp_*_ets2r@@`, `@@tz_*@@`).
   - Confirm zero duplicate country registration errors.
4. You can also run the Offline SCS Validator manually on any local `.zip` or `.scs` package at any time:
   ```bash
   # Validate a composed ComboPatch archive
   uv run --offline ets2-realism validate local "<ETS2_MOD_DIR>/zz_ETS2_Realism_ComboPatch_Summer.scs" --profile combo

   # Validate a ProMods Companion local ZIP
   uv run --offline ets2-realism validate local dist/promods/local/ETS2_Country_Realism_ProMods_Summer.zip --profile promods

   # Validate a Vanilla+DLC Core local ZIP
   uv run --offline ets2-realism validate local dist/local/ETS2_Country_Realism_Core_Summer.zip --profile core
   ```
