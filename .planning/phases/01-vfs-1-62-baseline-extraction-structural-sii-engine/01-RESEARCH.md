# Phase 1: VFS, 1.62 Baseline Extraction & Structural SII Engine - Verified Implementation Specs

**Gathered:** 2026-11-16
**Scope:** Empirical verification of binary container layouts, CityHash64 variant, and ETS2 `1.62.3.3s` (`def.scs` / `locale.scs`) SII/SUI structures for Phase 1 (`01-01` through `01-04`).

## 1. Clean-Room HashFS v1 / v2 Binary Format Specs

Verified directly against ETS2 `1.62.3.3s` (`def.scs`, `locale.scs`, `version.scs`) and local HashFS v1 mod archives (`53RXF1.scs`):

### 1.1 CityHash64 Variant (Google CityHash 1.0.3 — MIT License)
- **Critical Finding:** SCS HashFS uses **CityHash 1.0.3** (`google/cityhash` commit `00b9287e8c1255b5922ef90e304d5287361b2c2a`, MIT License), **NOT** CityHash 1.1 (`master`).
- Specifically, CityHash 1.0.3 defines `k3 = 0xc949d7c7509e6557` and uses distinct `HashLen0to16`, `HashLen17to32`, and `HashLen33to64` formulas from CityHash 1.1.
- Path inputs are UTF-8 encoded POSIX paths **without** a leading `/` (root directory is empty bytes `b""`, whose `CityHash64(b"")` equals `k2 = 0x9ae16a3b2f90404f`).
- Verified against `def.scs` (`b""`, `b"def"`, `b"def/country.sii"`, `b"def/country/iceland.sui"`, `b"def/country/germany/speed_limits.sii"`) and `locale.scs` (`b"locale/fuel_price_strings.sui"`, `b"locale/en_gb/localization.sui"`) — 100% hash match across all length buckets (`0`, `<=16`, `17..32`, `33..64`, `>64`).
- Salted archives (`salt != 0`): prepend decimal salt string (or configured salt) prior to hashing; record `salt` cleanly in archive metadata.

### 1.2 HashFS v1 (`SCS#\x01`)
- **32-byte header** (`<4sHH4sIQQ`):
  - `magic` (`4s`): `b"SCS#"`
  - `version` (`uint16`): `1`
  - `salt` (`uint16`): `0` (or non-zero salt)
  - `hash_method` (`4s`): `b"CITY"`
  - `num_entries` (`uint32`): entry count
  - `start_offset` (`uint64`): byte offset of entry table
  - `reserved` (`uint64`): `0`
- **32-byte entry** (`<QQIIII`):
  - `hash` (`uint64`), `offset` (`uint64`), `flags` (`uint32`), `crc32` (`uint32`), `size` (`uint32`), `zsize` (`uint32`)
- **Flags:**
  - `flags & 1 != 0`: directory listing
  - `flags & 2 != 0`: zlib-compressed (`zsize` bytes -> `size` bytes)
- **Directory listing payload:** UTF-8 lines (`\n` / `\r\n`); subdirectories are prefixed with `*` (e.g., `*editor\n*in\n*out\n`).

### 1.3 HashFS v2 (`SCS#\x02`)
- **Header** (`<4sHH4sIIIIQQ`, `44` bytes + trailing `uint64`s up to `start_offset` / `128`):
  - `magic` (`4s`): `b"SCS#"`
  - `version` (`uint16`): `2`
  - `salt` (`uint16`): `0`
  - `hash_method` (`4s`): `b"CITY"`
  - `entry_count` (`uint32`)
  - `entry_table_size` (`uint32`)
  - `metadata_count` (`uint32`) — count of `uint32` words in metadata table
  - `metadata_table_size` (`uint32`)
  - `entry_table_offset` (`uint64`)
  - `metadata_table_offset` (`uint64`)
- **Critical Table Compression Finding (`version.scs`):**
  - Even when uncompressed table bytes (`entry_count * 16 = 32`) are smaller than compressed bytes (`entry_table_size = 36`), HashFS v2 still zlib-compresses the table (`eb[:2] = 0x78da`). Always attempt `zlib.decompress` on `entry_table` and `metadata_table` (falling back to raw only if uncompressed length already equals expected size and magic isn't zlib).
- **16-byte entry** (`<QIHH`):
  - `hash` (`uint64`), `metadata_index` (`uint32`), `metadata_count` (`uint16`), `flags` (`uint16`, `flags & 1` = directory).
- **Metadata table (`metadata_count` `uint32` words):**
  - Standard Plain (`word0 >> 24 == 0x80`) and Directory (`word0 >> 24 == 0x81`) entries span 5 `uint32` words at `metas[metadata_index : metadata_index + 5]`:
    - `word0`: `(kind << 24) | index_or_info` (`0x80` = plain file, `0x81` = directory)
    - `word1`: `(comp_nibble << 28) | zsize` (`comp_nibble == 0` uncompressed, `comp_nibble == 1` zlib deflate; any other value emits an explicit unsupported-compression `ArchiveDiagnostic`)
    - `word2`: `size` (uncompressed byte size)
    - `word3`: `0` / flags
    - `word4`: `offset_blocks` (`offset = word4 * 16`)
- **Directory listing payload:** `<I` `count`, followed by `count` `uint8` filename lengths, followed by `count` UTF-8 filenames; subdirectories are prefixed with `/` (e.g., `['/custom', '/def']`).
- **Stripped-Root Archives (`locale.scs`):** `locale.scs` omits root `""` (`CityHash64(b"")`) from its entry table. Seeded prefix walking (`["locale", "def", "base", ...]`) resolves `/locale` (`43` locale dirs + `4` root files) cleanly without requiring root `/` listing.

### 1.4 Protected / Non-Standard Archive & Payload Detection
- **`3nK` payloads:** File bytes starting with `b"3nK\x01"` are flagged as protected (`3nK`) without attempting decryption or copying decoded output.
- **Protected containers:**
  - `b"AEM!"` header -> emit `ArchiveDiagnostic(kind="aem_protected", ...)`.
  - Unknown non-`SCS#`/non-`PK` archive magic -> emit `ArchiveDiagnostic(kind="unknown_magic", ...)`.
  - Encrypted ZIP entries (`ZipInfo.flag_bits & 0x1`) -> inspect central-directory filenames into metadata/diagnostics, emit `ArchiveDiagnostic(kind="encrypted_zip", ...)` on entry read without crashing.

## 2. ETS2 `1.62.3.3s` Baseline Empirical Verification (`def.scs` & `locale.scs`)

- **`def/country.sii`:** Starts with UTF-8 BOM (`\xef\xbb\xbfSiiNunit`); contains **36** `@include "country/<slug>.sui"` lines.
- **`def/country/*.sui` (`36` files):**
  - Exactly `20` observed attribute keys: `country_id`, `name`, `name_localized`, `country_code`, `iso_country_code`, `pos`, `fuel_price`, `lights_mandatory`, `driving_tired_offence`, `imperial_units`, `leftside_traffic`, `trailer_standalone`, `time_zone`, `time_zone_name`, `secondary_time_zone_area[]`, `secondary_time_zone[]`, `secondary_time_zone_name[]`, `mass_limit_per_axle_count[]`, `regions[]`, `region_areas[]`.
  - Mixed quoting on `iso_country_code` (`isl` unquoted vs `"bih"` quoted) must be preserved when untouched.
  - Inline `#` comments exist on attribute lines (e.g., `time_zone: 0\t\t# +0 hours in minutes`, `mass_limit_per_axle_count[]: 18000\t# 2-axle vehicle`).
- **`def/country/*/speed_limits.sii` (`36` files):**
  - `vehicle_speed_class` values: `car`, `truck`, `bus`, `train`, `tram` (note: `train`/`tram` are optional per country; e.g., `bulgaria` omits them while `germany` includes them).
  - Unit header uses inline `{` (`country_speed_limit : .speed_limit.car {`).
  - Attributes are **interleaved per lane class**, e.g. repeating groups of `lane_speed_class[]`, `limit[]`, `urban_limit[]`, optional `max_limit[]`, and optional `uncommon[]` (`bulgaria`, `romania`, `turkey` include `uncommon[]` + `slow_road`).
  - `train` and `tram` often omit `limit[]` and define only `lane_speed_class[]` + `urban_limit[]` (with inline comments like `# combined rail+road`).
- **`def/sign/board/*.sii` (`12,942` total boards):**
  - **`461` fuel totem boards** (`457` `gas_*` + `es_95_01.sii`, `es_diesel_01.sii`, `pt_95_01.sii`, `pt_diesel_01.sii`):
    - **100%** of these 461 fuel boards have `model_name: ""` and `items: 1` (single `sign_template_text` child unit).
    - **373** currently reference `@@fp_*@@` localization keys; the remaining `88` `gas_*` boards use numeric/blank placeholders (e.g., `"123.9"`, `"0.00"`, `" "`).
  - Non-fuel boards matching keywords like `95`/`98`/`fuel` (`fi_oulu_95.sii`, `fi_oulu_98.sii`, `rs_fuel_01.sii`, `ru_m_95.sii`, `ru_m_98.sii`) are highway directional signs with non-empty `model_name` and `items >= 8` (`sign_template_frame` / `sign_template_image`) — **must be excluded** from fuel board discovery!
- **`locale.scs`:**
  - **43** active locale directories (`bg_bg` through `zh_tw`; `fr_qc` does not exist).
  - `locale/fuel_price_strings.sui` defines **99** `fp_*` keys (`key[]` / `val[]` pairs, headerless `.sui` fragment).
  - `locale/<lang>/localization.sui` defines **12** `tz_*` keys (identical set across all 43 locales): `tz_bst`, `tz_cdt`, `tz_cest`, `tz_eet`, `tz_eest`, `tz_gmt`, `tz_msk`, `tz_mst`, `tz_mdt`, `tz_pdt`, `tz_trt`, `tz_west`.

## Package Legitimacy Audit

Verified directly against `https://pypi.org/project/<pkg>/` and `https://pypi.org/pypi/<pkg>/json` on 2026-11-16:

| Package | Role | Verified Latest | Maintainer / Org | License | Status | Version Bound Note |
|---|---|---|---|---|---|---|
| `hatchling` | Build backend | `1.33.0` (2026-10-28) | PyPA (`pypa/hatch`) | MIT | VERIFIED | `>=1.25,<2` |
| `pydantic` | Core schema validation | `2.14.3` (2026-11-04) | Pydantic (`pydantic/pydantic`) | MIT | VERIFIED | `>=2.14,<3` |
| `basedpyright` | Strict static type checker | `1.40.2` | `detachhead` (`detachhead/basedpyright`) | MIT | VERIFIED | `>=1.40,<2` |
| `pytest` | Test runner | `9.2.0` (2026-10-27) | `pytest-dev` (`pytest-dev/pytest`) | MIT | VERIFIED | `>=9.2,<9.3` |
| `pytest-cov` | Coverage plugin | `7.1.0` (2026-03-21) | `pytest-dev` (`pytest-dev/pytest-cov`) | MIT | VERIFIED | Use `>=6,<8` (or `>=5,<8`) so `7.1.0` resolves cleanly alongside `pytest 9.2` (`<7` excludes `7.x`) |
| `ruff` | Linter & formatter | `0.17.5` (2026-11-12) | Astral (`astral-sh/ruff`) | MIT | VERIFIED | `>=0.16` |

