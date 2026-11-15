# Technology Stack & ETS2 1.62 Ecosystem Research

**Project:** ETS2 World Country Realism Generator (V2)
**Researched:** 2026-11-15
**Baseline Target:** Euro Truck Simulator 2 `1.62.3.3s` (`version.scs`: `"1.62.3.3"`)
**Overall Confidence:** HIGH (backed by direct binary inspection of ETS2 `1.62.3.3s`, Workshop archives `3668352310` & `3249064596`, live SCS Modding Wiki scrapes, and V1 codebase audit)

---

## Executive Stack Verdict

Build V2 as a modular, typed Python 3.12 (`uv`) package (`src/` layout) using **Pydantic v2** for strict domain schemas, **httpx** + **openpyxl** for upstream data acquisition, a **clean-room pure-Python HashFS v1/v2 + SCS `3nK` reader** for cross-platform baseline extraction, a **surgical comment/order-preserving SII/SUI overlay engine** for conflict-free `def/country/` generation, **zero-DDS locale-token sign patching** (`def/sign/board/*.sii` + `locale/*/local_module.*.sii`), **pytest** + **ruff** + **basedpyright** for quality gates, and **zip/directory Workshop outputs** validated against SCS Workshop Uploader rules before semi-automatic (later `m00nl1ght-dev/steam-workshop-deploy@v4`) release.

---

## Recommended Stack

### Core Language & Package Management

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Python** | `3.12.13` (`>=3.12`) | Runtime | Matches installed toolchain (`uv` CPython `3.12.13`), modern typing (`type` aliases, `Protocol`), zero Windows dependency friction for all recommended pure-Python packages. | HIGH |
| **uv** | `0.11.31+` | Env, lockfile, script runner | Reproducible `uv.lock`, instant virtualenvs on Windows & Linux CI (`astral-sh/setup-uv@v5`), eliminates `pip`/`venv` drift. | HIGH |
| **src-layout package** | PEP 621 / `hatchling` or `uv_build` | Project structure | Replaces V1's flat `tools/` monolith (`update_fuel.py` 1,632 LOC, `update_limits.py` 1,508 LOC) with clean testable modules (`archive/`, `sources/`, `sii/`, `emitters/`, `validators/`). | HIGH |

### Data Acquisition, Validation & Modeling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Pydantic** | `>=2.14,<3` (`2.14.3`) | Country, speed-limit, fuel-price, manifest, and override schemas | Strict type/range validation (e.g., axle mass limits, UTC offset minutes, ISO/plate codes, non-negative fuel prices, SII token `[a-z0-9_]{1,12}` constraints) with clean JSON schema export and native `basedpyright` inference. | HIGH |
| **httpx** | `>=0.28,<0.29` (`0.28.1`) | HTTP/2 client for EC Oil Bulletin & global open sources | Proven in V1, clean timeouts/retries/redirects, async-capable if parallelizing multi-source fetches in later phases, zero `requests` `urllib3` quirks. | HIGH |
| **openpyxl** | `>=3.1,<4` (`3.1.5`) | Parsing EC Weekly Oil Bulletin `.xlsx` workbooks | Required for EU27 official diesel/petrol spreadsheets (note: V1 hit malformed/merged sheet edge cases like `repair-2320.xlsx`, so wrap with explicit cell-type & sheet validation). | HIGH |
| **BeautifulSoup4 + lxml** *(or stdlib `csv`/`json`)* | `>=4.12` (add only when non-API HTML sources are chosen) | Optional HTML table extraction for non-XLSX global fuel/speed sources | Defer until Phase 2+ data-source research locks which non-EU countries require HTML parsing vs JSON/API feeds. | MEDIUM |

### SCS Binary Containers, Encryption & Mod Asset Tooling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Clean-room Python HashFS v1/v2 + `3nK` reader** | Stdlib `struct` + `zlib` + MIT CityHash64 | Read-only extraction of `def.scs`, `locale.scs`, `version.scs`, `dlc_*.scs`, and Workshop `.scs` archives | Eliminates V1's Windows-only manual `scs_extractor.exe` bottleneck. HashFS v1/v2 `def`/`locale`/text entries use standard `zlib` (`deflate`) + CityHash64 (MIT spec); SCS `3nK` uses a deterministic 6-byte header + 256-byte XOR table. Runs identically on Windows dev and Ubuntu CI. *(Do NOT copy GPL code from `TruckLib` or `easy-scsmodmanager`.)* | HIGH |
| **Stdlib `zipfile`** | Python 3.12 stdlib | Packaging Workshop `universal.zip` / directories & local `.scs` ZIP drops | Official SCS Workshop Uploader rules explicitly allow **folders or normal `.zip` packages** for Workshop mods (and disallow ZIP-renamed-to-`.scs` on Workshop; HashFS v2 `.scs` is optional, not mandatory). Works natively on Linux CI without Wine/EXEs. | HIGH |
| **SCS Official CLI Tools (`scs_packer` / `scs_extractor`)** | `1.55+` (Windows 64-bit) | Optional Windows-only HashFS v2 `.scs` packing & reference validation | Only needed if V2 later ships HashFS v2 `.scs` binaries (note: `scs_packer 1.55+` fixed a 2025-09-12 threading crash and writes HashFS v2 only). Not required for CI if publishing directory/`.zip` Workshop packages. | HIGH |
| **Custom Surgical SII/SUI Parser & Overlay Engine** | Project-owned module (evolution of V1 `merge_sui.py`) | Parsing & patching `def/country/*.sui`, `speed_limits.sii`, `def/sign/board/*.sii`, `locale/*/local_module.*.sii` | Generic `SiiNunit` AST re-serializers destroy vanilla comments (`#`, `//`, `/* */`), key ordering, `regions[]` blocks, and CRLF/LF/BOM fidelity, and risk mangling `@include` placement rules (must start at column 0). Surgical field/block replacement + schema-aware `.sui` overlay preserves unknown map-mod fields (`regions[]`, `secondary_time_zone*`, `trailer_standalone`). | HIGH |
| **Pillow** | `>=12,<14` (`13.0.0`) | **ONLY** Workshop `276x162` `.jpg` icon validation / generation | V1's `docs/DDS-SPIKE-VERDICT.md` proved Pillow is **NO-GO for `.dds`** (cannot read/write SCS sRGB DXGI 72/78/91/88, strips mipmaps). Totem price boards use zero DDS files (only `.sii` + `locale/*/local_module.*.sii`). Keep Pillow strictly scoped to `276x162` JPEG validation/compositing (or omit if static pre-built icons suffice). | HIGH |

### Testing, Linting, Type Checking & CI/CD

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **pytest** + **pytest-cov** | `>=9.2,<9.3` (`9.2.0`) | Unit, golden-file, round-trip, and pre-flight SCS rule verification | Proven in V1; enforces byte-level round-trip, no-op preservation, dual Summer/Winter parity, and zero unreferenced asset errors. | HIGH |
| **ruff** | `>=0.16` (`0.17.x`) | Linting + formatting (`ruff check`, `ruff format`) | Single fast Rust tool replacing `flake8` + `isort` + `black`. | HIGH |
| **basedpyright** | `>=1.40,<2` (`1.40.2`) | Strict static type checking | Stable `1.x` release with first-class Pydantic v2 & Python 3.12 support; preferred over `ty` (`0.0.104`, still `0.0.x` beta) and slower `mypy` (`2.4.1`). Re-evaluate `ty` once it hits `>=0.1`/`1.0`. | HIGH |
| **GitHub Actions** | `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/setup-python@v5` | Automated test, data refresh PRs, and artifact builds (`ubuntu-latest`) | Zero Windows runner dependency for building Summer + Winter Workshop staging artifacts (`versions.sii` + `universal/` + `universal.zip`). | HIGH |
| **Steam Workshop Deploy** | `m00nl1ght-dev/steam-workshop-deploy@v4` | Phase 2+ automated Steam Workshop uploads | Mandatory minimum `v4` (`v1`–`v3` disabled due to `.git` leak risk; `v4` excludes `.git` and supports `.deployignore`). Gate behind manual `workflow_dispatch` / protected GitHub Environment until semi-auto validation proves airtight. | HIGH |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **HashFS Extraction** | Clean-room pure-Python HashFS v1/v2 reader + stdlib `zlib` | Copying `TruckLib.HashFs` or `easy-scsmodmanager` (`hashfs_reader.py`) | Both `sk-zk/TruckLib` / `sk-zk/Extractor` (`GPL-2.0`) and `Switch-Bros/easy-scsmodmanager` (`GPL-3.0-or-later`) are copyleft GPL; copying their code would force GPL licensing onto V2. Implement directly from the documented binary layout + MIT-licensed Google CityHash64 spec. |
| **HashFS CityHash64** | 100-line pure-Python `cityhash64` (MIT Google spec) | `cityhash` / `clickhouse-cityhash` C extensions from PyPI | `clickhouse-cityhash` / `cityhash` frequently lack `win_amd64` `cp312` prebuilt wheels, breaking `uv sync` on developer Windows machines without MSVC Build Tools; 64-bit path hashing runs in microseconds in pure Python. |
| **Archive Packaging** | `zipfile` (`universal.zip`) / directory (`universal/`) for Workshop; optional `scs_packer 1.55+` for HashFS v2 | Rewriting HashFS v2 writer in Python or uploading `.scs`-renamed ZIPs | Per SCS Wiki *Validation errors*, Steam Workshop **forbids `.scs`-renamed ZIPs** (Error `00003`) while explicitly allowing normal `.zip` or directory packages. Implementing a full HashFS v2 + GDeflate packer in Python brings zero benefit when we ship zero `.tobj`/`.dds`/`.pmg` binaries. |
| **Price Totem Updates** | `def/sign/board/*.sii` + `locale/*/local_module.*.sii` (`@@fp_*@@` tokens, zero DDS) | Pillow DDS texture baking (`dds_spike.py` approach) | V1 spike proved Pillow fails on SCS sRGB DXGI 72/78/91/88 DDS textures and drops all 9 mipmaps; ETS2 vanilla & `3249064596` both drive dynamic gas-station totems via `sign_board_template` + localization tokens. |
| **Type Checker** | `basedpyright` (`1.40.2`) | `ty` (`0.0.104`) / `mypy` (`2.4.1`) | `ty` is still `0.0.x` beta; `mypy` requires extra `pydantic.mypy` plugin config and lags Pyright on Pydantic v2/generic narrowing. |
| **SII Parsing** | Surgical token/block parser + overlay | Full AST round-trip rewrite or regex-only sed | Full AST rewrites strip vanilla comments and re-indent `@include` directives; pure ad-hoc regex broke when V1 scattered rules across 1,500-LOC scripts. Surgical line/block replacement backed by a typed SII lexer gives the best of both worlds. |

---

## Empirical Findings from Target Game & Ecosystem (2026-11-15)

### 1. Installed ETS2 `1.62.3.3s` Archives (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`)

Direct read-only inspection across **all 96 `.scs` archives** (all HashFS v2 `SCS#\x02`, method `CITY`):

- **`version.scs`:** `application: eut2`, `version: "1.62.3.3"`.
- **Where country, speed-limit, sign-board, and locale data actually live in `1.62.3.3s`:**
  - **`def.scs`** (68,372 entries): **Sole source** of `def/country.sii` (`36` `@include` entries), `def/country.custom.sii` (`@include "/custom/country.sii"`), `def/country/*.sui` (`36` files), `def/country/*/speed_limits.sii` (`36` files), and `def/sign/board/*.sii` (**12,942** board templates, **373** of which reference `@@fp_*@@` fuel price localization tokens).
  - **9 DLC archives** contain **only** AI traffic frequency overrides under `def/country/<country>/traffic.<dlc>.sii` (`dlc_balt` [4], `dlc_daf_2021` [4], `dlc_daf_xd` [4], `dlc_fr` [1], `dlc_iberia` [2], `dlc_it` [9], `dlc_man_tgx_2020` [4], `dlc_north` [3], `dlc_volvo_fh_2024` [4]) — **none** contain `country_data`, `speed_limits.sii`, or `def/sign/board`.
  - **New/regional map & gameplay DLCs (`dlc_iceland.scs`, `dlc_polar.scs`, `dlc_bus.scs`, `dlc_greece.scs`, `dlc_balkan_e.scs`, `dlc_balkan_w.scs`, `dlc_east.scs`)** contain **zero** `def/country*` or `def/sign/board*` entries. Notably, `iceland.sui` + `iceland/speed_limits.sii` and `norway`/`sweden`/`finland` already live inside `def.scs`.
  - **`locale.scs`** (565 entries; omits root `/` listing — walk via seeded `/locale` directory!):
    - `/locale/fuel_price_strings.sui` defines **99** `fp_*` fallback keys across vanilla ETS2 countries.
    - **43 locale directories** (`bg_bg` through `zh_tw`), each carrying `localization.sui` with **12** `tz_*` timezone localization tokens (`tz_bst`, `tz_cdt`, `tz_cest`, `tz_eet`, `tz_eest`, `tz_gmt`, `tz_msk`, `tz_mst`, `tz_mdt`, `tz_pdt`, `tz_trt`, `tz_west`).

- **Schema & Data Diff: ETS2 `1.62.3.3s` vs V1 `1.60.1.7` Baseline:**
  - **Countries:** Unchanged count (**36** in both `1.60.1.7` and `1.62.3.3s`).
  - **Schemas:** Zero new or removed keys in either `country_data` (20 distinct attributes across all `.sui` files: `country_id`, `name`, `name_localized`, `country_code`, `iso_country_code`, `pos`, `fuel_price`, `lights_mandatory`, `driving_tired_offence`, `imperial_units`, `leftside_traffic`, `trailer_standalone`, `time_zone`, `time_zone_name`, `secondary_time_zone_area[]`, `secondary_time_zone[]`, `secondary_time_zone_name[]`, `mass_limit_per_axle_count[]`, `regions[]`, `region_areas[]`) or `country_speed_limit` (6 attributes: `vehicle_speed_class`, `lane_speed_class[]`, `limit[]`, `urban_limit[]`, `max_limit[]`, `uncommon[]`).
  - **Fuel prices:** **36 / 36** `fuel_price` values changed between `1.60.1.7` and `1.62.3.3s` (`0` non-fuel diffs in `.sui` files).
  - **Speed limits:** **14 / 36** `speed_limits.sii` files changed values between `1.60.1.7` and `1.62.3.3s` (`czech`, `france`, `germany`, `iceland`, `italy`, `latvia`, `luxembourg`, `montenegro`, `poland`, `romania`, `slovenia`, `sweden`, `switzerland`, `uk`) — e.g., `czech` (`80→90`, `80→110`, `100→130`), `iceland` (`80→90`), `germany` (`70→80`), `uk` (`50→60`). **Implication:** V2 must extract fresh baselines directly from installed `1.62+` game files; V1 `1.60.1.7` fixtures are obsolete.

### 2. Reference Workshop Mod `3668352310` (*Updated WINTER speed limits*)

- **Container:** HashFS v1 (`salt=0`, `152` entries, `112` walked files). `versions.sii` declares `.universal` (`package_name: "universal"`) and informational `.pre144info`. `manifest.sii` sets `mp_mod_optional: true`, categories `other` + `ai_traffic`.
- **Critical Finding — What `_vtd/*.sui` Actually Does:**
  - Placed at `/def/country/_vtd/<country>.sui` (**36** files) and injected at the bottom of each `/def/country/<country>.sui` via `@include "_vtd/<country>.sui"` (column 0, inside `country_data { ... }`).
  - Inspection of all 36 files shows `/def/country/_vtd/*.sui` contains **exclusively `regions[]` and `region_areas[]`** (**247** total pairs across 36 countries: a shared `_worldmap` box `(-153000, 126000, -143000, 131000)` plus city-named bounding boxes like `_berlin`, `_tirane`, `_barcelona`). It does **not** define speed limits or vehicle-type classes! (The speed limits themselves live in `speed_limits.sii`.)
  - Notice `def/country/*.sui` in `3668352310` leaves `fuel_price` untouched (`0` diffs vs `1.62`), switches `time_zone` to winter standard time, **overwrites `@@tz_*@@` localization keys with hardcoded English strings** (`"CET"`, `"EET"`, `"GMT"`, `"MSK"` — a regression relative to vanilla `1.62`!), and strips SCS comments. V2 should **improve** on this by preserving `@@tz_*@@` keys (`@@tz_gmt@@`, `@@tz_eet@@`, `@@tz_msk@@`, etc.) wherever present in `locale.scs`!
- **Critical Finding — `3nK` in `speed_limits.sii`:**
  - All **36 / 36** `speed_limits.sii` files start with `b'3nK\x01\x00<seed>'` (standard SCS `3nK` XOR header).
  - Running SCS's standard 256-byte `SII_3nK_KeyTable` (`key[i] = (((i << 2) ^ (~i & 0xFF)) << 3 ^ i) & 0xFF`) decoded **36 / 36 (`0` failures)** cleanly into plain UTF-8 `SiiNunit` files with `country_speed_limit` units.
  - **Verdict:** `3nK` is standard `SII_Decrypt` / `3nK_Transcode`-compatible SCS encoding (mild author tamper deterrence), **not** proprietary encryption; `32 / 36` files differ numerically from `1.62` vanilla speed limits. V2's emitted files should remain unencrypted plain-text UTF-8 per SCS modding best practices.

### 3. Reference Workshop Mod `3249064596` (*Real life fuel prices*)

- **Container:** HashFS v2 (`salt=0`, `678` entries, `628` walked files; **100% plain-text** `.sii`/`.sui`/`.txt` + `mod_icon.jpg`). `versions.sii` defines only `.universal`.
- **`def/country/*.sui` (`75` files):** `36` vanilla + `39` Map Combo countries (ProMods, ProMods ME/TGS, RusMap, etc. — no `def/country.sii` and no `speed_limits.sii`). Keeps dual `# verão` / `# inverno` commented timezone pairs, and `russia.sui` includes 13 `secondary_time_zone_area[]` rectangles covering RusMap / ProMods TGS / Sibir / Altai.
- **`def/sign/board/*.sii` (`375` files):** **100% overlap with vanilla `def.scs/def/sign/board/` names** (`0` map-mod-unique board filenames). However:
  - **356** overlap vanilla's `373` `@@fp_*@@` boards;
  - **19** patch vanilla `def.scs` boards (`gas_is_skanfill_*`, `gas_de_*_98`, `gas_al_apus_98`, `gas_fi_tqg_85`, etc.) to wire them to `@@fp_*_kwo@@` localization keys;
  - **17** vanilla `@@fp_*@@` boards (`gas_ie_*`, `gas_bi_*`, `gas_dk_92`, `gas_ba_*_lpg`) are omitted.
  - **Implication for V2:** Always discover sign boards dynamically from `def.scs:/def/sign/board/` rather than hardcoding a static list.
- **`locale/<lang>/local_module.*.sii` (`175` files across `44` locales):** Emits `local_module.kworey_fuel_ets.sii`, `pm_fuel.sii`, `pm_me_fuel.sii`, and `pm_tgs_fuel.sii` across 43 vanilla locales + `fr_qc` (note `fr_ca` only has 3/4 files — likely an author oversight V2 should avoid!). Uses `localization_db : .localization` (`key[]`/`val[]`) — zero DDS textures needed.

### 4. Online SCS Modding Wiki Deltas (`2026-06-29` Mirror vs Live `2026-11-15`)

- **`SCS_Workshop_Uploader/Changelog` (`oldid=5814`):** Added `1.61.0` (`01.09.2026`), `1.61.2` (`13.10.2026` — ATS car tags), and `1.62.0` (`20.10.2026` — initial 1.62 support).
- **`Documentation/Engine/Units` (`oldid=5765`):** Added `vehicle_animation_data` (introduced 1.61). **Zero** changes to `SiiNunit` grammar, attribute types, `@include` column-0 rule, or country/sign unit definitions.
- **`Special:RecentChanges` (through `2026-11-15`):** All recent documentation edits cover interior animations, chassis/cabin/engine/trailer data, and telemetry SDK — confirming country, speed-limit, sign-board, and localization unit schemas are stable in 1.62.
- **`Validation_errors_and_solutions_for_them` (`oldid=5757`) & `Game_Archive_Packer` (`oldid=5720`):** Unchanged core validation constraints: `versions.sii` + version packages only at root, `[a-z0-9_]` package names, `276x162` `.jpg` icon (<=1 MB), UTF-8 `.txt` description (<=1 MB), Unix `/` paths only, all `.txt`/`.jpg` referenced by `.sii`, HashFS v2 or `.zip`/folder required on Workshop (`scs_packer_1_55.zip` recommended if HashFS v2 `.scs` is ever needed).

---

## Legacy V1 Audit (`d:\CODE\Ets2 Mod`): Keep vs Drop

| V1 Artifact / Library | Verdict | Rationale |
|-----------------------|---------|-----------|
| `uv` + Python `3.12` + `pyproject.toml` + `uv.lock` | **KEEP** | Fast, deterministic, CI-ready. |
| `pydantic`, `httpx`, `openpyxl`, `pytest`, `ruff` | **KEEP** | Clean, well-tested core stack with zero bloat. |
| `merge_sui.py` surgical overlay design (BOM/CRLF/LF & unknown-field preservation) | **KEEP & GENERALIZE** | Preserving unowned fields (`regions[]`, `secondary_time_zone*`, comments) is essential for Map Combo safety; generalize into a clean SII/SUI surgical library supporting both `.sui` and `speed_limits.sii`. |
| `country_attributes.py` strict CSV + summer/winter model | **KEEP IDEA, EVOLVE** | Keep strict typed attribute validation and explicit Summer/Winter timezone pairs; move away from awkward `;`-delimited strings in CSV where structured JSON/YAML/TOML + generated schemas are cleaner. |
| `tools/update_fuel.py` (1,632 LOC) & `tools/update_limits.py` (1,508 LOC) | **DROP STRUCTURE** | Monolithic scripts mixed HTTP fetching, XLSX parsing, CLI flags, heuristics, and SII string emission in single files. Decompose cleanly under `src/`. |
| `pillow>=12,<13` for DDS totem baking (`dds_spike.py`) | **DROP DDS USE** | Proven **NO-GO** in V1 `docs/DDS-SPIKE-VERDICT.md`. Keep Pillow **only** if validating/generating `276x162` `.jpg` Workshop icons. |
| Manual `scs_extractor 1.55` workflow & stale `1.60.1.7` fixtures | **REPLACE** | Replace manual baseline extraction with automated clean-room Python HashFS v1/v2 extraction + `1.62.3.3s` baseline extractor command. |
| Missing `.github/` workflows & zero static type-checker gate | **ADD** | V1 had no `.github/` CI directory; V2 adds CI lint + `basedpyright` + `pytest` + build verification from day one. |

---

## Installation & Target `pyproject.toml` Baseline

```toml
[project]
name = "ets2-world-realism"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.28,<0.29",
    "openpyxl>=3.1,<4",
    "pydantic>=2.14,<3",
    "pillow>=12,<14",  # Workshop 276x162 JPG icon validation/generation only (NOT DDS)
]

[dependency-groups]
dev = [
    "basedpyright>=1.40,<2",
    "pytest>=9.2,<9.3",
    "pytest-cov>=5,<7",
    "ruff>=0.16",
]
```

Quick bootstrap command:

```bash
uv init --lib --python 3.12
uv add "httpx>=0.28,<0.29" "openpyxl>=3.1,<4" "pydantic>=2.14,<3" "pillow>=12,<14"
uv add --dev "basedpyright>=1.40,<2" "pytest>=9.2,<9.3" "pytest-cov>=5,<7" "ruff>=0.16"
```

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **ETS2 `1.62.3.3s` file & schema layout** | **HIGH** | Directly inspected all 96 `.scs` archives, `version.scs`, `def.scs`, `locale.scs`, and diffed all 36 countries + speed limits against `1.60.1.7`. |
| **Workshop `3668352310` & `3249064596` internals** | **HIGH** | Directly unpacked HashFS v1 & v2 archives, decoded all 36 `3nK` `speed_limits.sii` files, inspected all 36 `_vtd/*.sui` files, 375 boards, and 175 locale modules. |
| **Online SCS Wiki `1.61`/`1.62` delta** | **HIGH** | Live-scraped `Changelog`, `Units`, `Game_data`, `Validation_errors_and_solutions_for_them`, and `Special:RecentChanges` (`2026-11-15`). |
| **V2 Python & CI Stack** | **HIGH** | Package versions verified via PyPI/search and local toolchain (`uv 0.11.31`, Python `3.12.13`); CI action major tags (`setup-uv@v5`, `steam-workshop-deploy@v4`) verified online. |

---

## Sources

- Local ETS2 `1.62.3.3s` installation (`D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\`) — inspected via read-only HashFS v2 Python check (`2026-11-15`)
- Local Steam Workshop items `3668352310` and `3249064596` (`D:\SteamLibrary\steamapps\workshop\content\227300\`) — inspected via read-only HashFS v1/v2 + `3nK` Python check (`2026-11-15`)
- [SCS Modding Wiki — SCS Workshop Uploader Changelog](https://modding.scssoft.com/wiki/Documentation/Tools/SCS_Workshop_Uploader/Changelog) (`oldid=5814`)
- [SCS Modding Wiki — Documentation/Engine/Units](https://modding.scssoft.com/wiki/Documentation/Engine/Units) (`oldid=5765`)
- [SCS Modding Wiki — Documentation/Engine/Game data](https://modding.scssoft.com/wiki/Documentation/Engine/Game_data) (`oldid=5754`)
- [SCS Modding Wiki — Validation errors and solutions for them](https://modding.scssoft.com/wiki/Documentation/Tools/SCS_Workshop_Uploader/Validation_errors_and_solutions_for_them) (`oldid=5757`)
- [SCS Modding Wiki — Game Archive Packer](https://modding.scssoft.com/wiki/Documentation/Tools/Game_Archive_Packer) & [Mod Manager](https://modding.scssoft.com/wiki/Documentation/Engine/Mod_manager)
- [3nK_Transcode (`SII_3nK_Transcoder.pas`)](https://github.com/TheLazyTomcat/3nK_Transcode) — standard SCS `3nK` header & 256-byte XOR key table verification
- [sk-zk/Extractor & TruckLib](https://github.com/sk-zk/TruckLib) / [Switch-Bros/easy-scsmodmanager](https://github.com/Switch-Bros/easy-scsmodmanager) — HashFS v1/v2 binary structure cross-check (GPL-licensed; cited for format verification only)
- [m00nl1ght-dev/steam-workshop-deploy](https://github.com/marketplace/actions/steam-workshop-deploy) (`v4` action & security notes) and [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) (`v5`)
- Legacy V1 repository (`D:\CODE\Ets2 Mod\pyproject.toml`, `docs/DDS-SPIKE-VERDICT.md`, `docs/SCS-REFERENCE-VERDICT.md`, `tools/`)
