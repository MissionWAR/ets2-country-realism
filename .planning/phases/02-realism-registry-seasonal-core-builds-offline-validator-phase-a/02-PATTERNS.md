# Phase 2: Realism Registry, Seasonal Core Builds & Offline Validator (Phase A) - Pattern Map

**Mapped:** 2026-11-19
**Phase Scope:** `SIM-01`, `SIM-02`, `SIM-03`, `PUB-01`, `PUB-02`, `PUB-03` (Plans `02-01` through `02-05`)
**Files analyzed:** 33 planned new/modified files (18 source modules, 3 data/state artifact families, 1 CI workflow, 1 config/lock pair, 10 test modules)
**Analogs found:** 31 / 33 (2 files introduce new Phase 2 capabilities — `Pillow` icon generation and `zoneinfo` DST derivation — that follow repo typing/determinism conventions with no direct Phase 1 library analog)

---

## 1. Proposed Phase 2 Package & Module Layout

### Subpackage Alignment (`src/ets2v2/`)

> **Important alignment note vs Phase 1 `STRUCTURE.md`:** `.planning/codebase/STRUCTURE.md` (written at the end of Phase 1) speculatively placed `normalize/` and `merge/` in Phase 2. Locked Phase 2 decisions in `02-CONTEXT.md` (lines 43, 91) override that: **`fetch/`, `normalize/`, and `merge/` MUST remain blocked** in `tests/test_cli_scaffold.py::test_active_phase_only_package_layout` until Phases 3–5 begin.

Phase 2 introduces **four clean, acyclic subpackages** under `src/ets2v2/`, one per functional domain across Plans `02-01`–`02-05`:

```text
src/ets2v2/
├── __init__.py               # Existing — __version__ = "0.1.0"
├── py.typed                  # Existing — PEP 561 marker
├── cli.py                    # Modified (02-01..02-05) — wire Phase 2 subcommands onto build_parser()
├── vfs/                      # Existing (Phase 1, Layer 0-2) — unchanged
├── sii/                      # Existing (Phase 1, Layer 0-3) — unchanged (reused directly)
├── baseline/                 # Existing (Phase 1, Layer 4) — unchanged (reused directly)
├── registry/                 # NEW (02-01, 02-02 — Layer 5)
│   ├── __init__.py           # Public __all__ facade
│   ├── models.py             # Strict frozen Pydantic v2 law/mapping schemas (ConfigDict strict+frozen+forbid)
│   ├── loader.py             # Load & cross-validate data/laws/countries/*.json + data/mappings/ets2_countries.json
│   ├── timezone.py           # Dynamic zoneinfo + tzdata DST resolver & 12-key @@tz_*@@ whitelist mapper
│   └── snapshot.py           # Forward-compatible schema_version=1 realism-snapshot-{summer,winter}.json emitter
├── package/                  # NEW (02-03 — Layer 6)
│   ├── __init__.py           # Public __all__ facade
│   ├── synthesize.py         # Pure clean-room .sui & speed_limits.sii synthesizers from 1.62 baseline + resolved laws
│   ├── metadata.py           # versions.sii (.universal), Workshop/local manifest.sii, description.txt renderers
│   ├── icons.py              # Reproducible clean-room 276x162 EXIF/ICC-stripped JPEG generator (Pillow)
│   └── builder.py            # Stages dist/workshop/{summer,winter}/universal/ + dist/local/ETS2V2_Core_*.zip
├── validate/                 # NEW (02-04 — Layer 7)
│   ├── __init__.py           # Public __all__ facade
│   ├── models.py             # ValidationIssue, ValidationReport (SCS 00001-00010, WARN 00001-00002, invariants)
│   ├── invariants.py         # 1.62 realism invariants (Estonia, regions[], Iceland 60t/80, rail blocks, @@tz_*@@)
│   └── workshop.py           # Offline SCS Workshop Validator across unpacked Workshop roots & local ZIPs
└── publish/                  # NEW (02-05 — Layer 8)
    ├── __init__.py           # Public __all__ facade
    ├── ledger.py             # Canonical per-edition SHA-256 hashing, state/published.json & ISO-week versioning
    ├── changelog.py          # Deterministic Markdown diff generator (CHANGELOG_SUMMER.md / CHANGELOG_WINTER.md)
    └── release.py            # Phase A release orchestrator (build -> validate -> diff-gate -> snapshot -> changelog)
```

> **Why `icons.py` lives in `src/ets2v2/package/icons.py` (not a standalone `scripts/` file):** `pyproject.toml` configures `[tool.ruff] src = ["src", "tests"]` and `[tool.basedpyright] include = ["src", "tests"]`. Placing the reproducible Pillow icon generator inside `src/ets2v2/package/icons.py` (exposed via `ets2v2 package icons`) guarantees 100% `ruff` and strict `basedpyright` coverage without widening tool configs. If a convenience script `scripts/generate_icons.py` is also added, keep it a 5-line thin wrapper calling `ets2v2.package.icons.generate_all_icons()`.

### Acyclic Module DAG Verification

Phase 2 extends Phase 1's strict bottom-up DAG with **zero upward or lateral cycles**:

```text
Layer 9:  ets2v2.cli
            ├──► ets2v2.vfs, ets2v2.baseline              (Phase 1)
            └──► ets2v2.registry, ets2v2.package,
                 ets2v2.validate, ets2v2.publish          (Phase 2)

Layer 8:  ets2v2.publish  {ledger, changelog, release}
            └──► ets2v2.registry, ets2v2.package, ets2v2.validate, ets2v2.baseline.models

Layer 7:  ets2v2.validate {models, invariants, workshop}
            └──► ets2v2.vfs {zip_archive, dir_archive, stack, types},
                 ets2v2.sii {hygiene, document, country, speed_limits, lexer},
                 ets2v2.baseline.models, ets2v2.registry.models, PIL
            (NOTE: validate NEVER imports package — validator inspects built artifacts independently!)

Layer 6:  ets2v2.package  {synthesize, metadata, icons, builder}
            └──► ets2v2.sii {hygiene, country, speed_limits, lexer},
                 ets2v2.baseline.models, ets2v2.registry.*, PIL

Layer 5:  ets2v2.registry {models, timezone, loader, snapshot}
            └──► ets2v2.baseline.models, ets2v2.sii.speed_limits, stdlib zoneinfo (tzdata)

Layer 4:  ets2v2.baseline {models, extractor}             (Phase 1 — unchanged)
            └──► ets2v2.vfs, ets2v2.sii

Layer 3:  ets2v2.sii.{country, speed_limits, sign_board, localization}   (Phase 1)
Layer 2:  ets2v2.vfs.{hashfs, stack}  |  ets2v2.sii.document             (Phase 1 — vfs ⊥ sii)
Layer 1:  ets2v2.vfs.{cityhash, dir_archive, zip_archive} | ets2v2.sii.hygiene
Layer 0:  ets2v2.__init__ | ets2v2.vfs.types | ets2v2.sii.lexer
```

**Blocked Phase 3–5 Directories (MUST stay rejected in `test_active_phase_only_package_layout`):**
- `src/ets2v2/fetch/` — Phase 3 (`DAT-01`, `DAT-02`) & Phase 5 (`GLB-01`, `GLB-02`)
- `src/ets2v2/normalize/` — Phase 3 (`DAT-01`, `TOT-02`) & Phase 4 (`MAP-02`)
- `src/ets2v2/merge/` — Phase 3 (`TOT-01`) & Phase 4 (`MAP-01`, `MAP-03`, `MAP-04`, `MAP-05`)

### Non-Python Repository Artifacts Added in Phase 2

| Path | Plan | Committed? | Format / Hygiene Contract |
|---|---|---|---|
| `data/mappings/ets2_countries.json` | `02-01` | Yes | UTF-8 no-BOM LF, `indent=2`, `sort_keys=True`, trailing `\n`; 36 vanilla slugs -> ISO-3166 alpha-2 |
| `data/laws/countries/<iso2>.json` (36 files) | `02-01` | Yes | UTF-8 no-BOM LF, `indent=2`, `sort_keys=True`, trailing `\n`; zero `.sii`/`.sui` under `data/` |
| `assets/icons/summer.jpg`, `assets/icons/winter.jpg` | `02-03` | Yes | `276x162` baseline JPEG, EXIF/ICC stripped, `< 1 MB`; `.gitattributes` already marks `*.jpg binary` |
| `state/published.json` | `02-05` | Yes | UTF-8 no-BOM LF, `indent=2`, `sort_keys=True`, trailing `\n`; independent `summer`/`winter` SHA-256 ledger |
| `.github/workflows/release-phase-a.yml` | `02-05` | Yes | UTF-8 no-BOM LF; Friday `06:00 UTC` cron + `workflow_dispatch(force_run)`, zero Steam secrets |
| `dist/workshop/{summer,winter}/`, `dist/local/*.zip` | `02-03` | **No** | Already gitignored via `dist/` in `.gitignore` |

---

## 2. File Classification & File-to-Analog Mapping Table

All analog paths below are verified git-tracked via `git ls-files`.

| Plan | New / Modified File | Role | Data Flow | Closest Tracked Phase 1 Analog | Match Quality | Key Patterns to Replicate |
|---|---|---|---|---|---|---|
| `02-01` | `src/ets2v2/registry/__init__.py` | barrel / facade | n/a | `src/ets2v2/baseline/__init__.py` | exact | `from __future__ import annotations`, absolute imports, alphabetically sorted `__all__` (`RUF022`) |
| `02-01` | `src/ets2v2/registry/models.py` | model / schema | transform | `src/ets2v2/baseline/models.py` | exact | Frozen Pydantic v2 models upgraded to `ConfigDict(strict=True, frozen=True, extra="forbid")` per D-01; `Literal` aliases; `Field(default_factory=...)` |
| `02-01` | `src/ets2v2/registry/loader.py` | service / loader | file-I/O | `src/ets2v2/baseline/extractor.py` | role-match | Deterministic JSON serializer (`_serialize_model_bytes`), `model_validate_json()`, BOM/LF checks, `list[str]` issue collector |
| `02-01` | `data/mappings/ets2_countries.json` | data / config | file-I/O | `data/baselines/ets2_1.62_def/countries.json` | exact | Sorted canonical JSON, UTF-8 no-BOM LF, zero volatile timestamps |
| `02-01` | `data/laws/countries/<iso2>.json` | data / config | file-I/O | `data/baselines/ets2_1.62_def/countries.json` | exact | Per-country sorted canonical JSON strictly for the 36 Vanilla+DLC countries (D-02) |
| `02-01` | `tests/test_registry_schema.py` | test | unit | `tests/test_sii_country.py` | role-match | Typed `def test_...() -> None:`, `@pytest.mark.parametrize`, `pytest.raises(ValidationError)` |
| `02-01` | `tests/test_registry_contracts.py` | test | contract | `tests/test_baseline_contracts.py` | exact | Committed JSON integrity, BOM/LF checks, 36-country parity against `data/baselines/ets2_1.62_def/countries.json` |
| `02-02` | `src/ets2v2/registry/timezone.py` | utility / domain | transform | `src/ets2v2/sii/hygiene.py` | role-match | Pure stateless functions, frozen dataclass/Pydantic output, explicit error raising on invalid IANA/offset, 12-key `LocalesBaseline.tz_keys` whitelist |
| `02-02` | `src/ets2v2/registry/snapshot.py` | model / serializer | transform | `src/ets2v2/baseline/models.py` & `extractor.py` | exact | Frozen Pydantic v2 `schema_version: Literal[1]`, deterministic sorted JSON bytes (`realism-snapshot-{summer,winter}.json`, D-11) |
| `02-02` | `pyproject.toml` & `uv.lock` | config | n/a | `pyproject.toml` (in-place) | exact | Add permissive runtime deps `tzdata` and `pillow>=12,<14`; regenerate `uv.lock` via `uv lock` |
| `02-02` | `tests/test_registry_timezone.py` | test | unit | `tests/test_sii_hygiene.py` | exact | Parametrized Summer (July 15) / Winter (Jan 15) DST matrix, `Asia/Amman`/`Asia/Damascus` permanent `UTC+3` `AST`, `@@tz_*@@` 12-key boundary |
| `02-03` | `src/ets2v2/package/__init__.py` | barrel / facade | n/a | `src/ets2v2/sii/__init__.py` | exact | Absolute imports, sorted `__all__` |
| `02-03` | `src/ets2v2/package/synthesize.py` | service / compiler | transform | `src/ets2v2/sii/country.py` & `speed_limits.py` | exact | Clean-room `.sui` & `speed_limits.sii` synthesis from `BaselineCountry` + `BaselineSpeedLimit` + resolved laws; preserve `iso_country_code_quoted`, `regions[]`, `region_areas[]`, `secondary_time_zone*`, `train`/`tram`; validate output via `validate_sii_hygiene()` + `serialize_sii_text()` |
| `02-03` | `src/ets2v2/package/metadata.py` | utility / emitter | transform | `src/ets2v2/sii/country.py` & `hygiene.py` | role-match | Safe SII string formatting (`_format_sii_string` rules), `serialize_sii_text()`, emit `versions.sii`, Workshop/local `manifest.sii`, UTF-8 LF `description.txt` |
| `02-03` | `src/ets2v2/package/icons.py` | utility / generator | file-I/O | `src/ets2v2/baseline/extractor.py` | partial (new Pillow lib) | Deterministic output writing; `Pillow` `276x162` RGB JPEG with EXIF/ICC stripped (`assets/icons/{summer,winter}.jpg`) |
| `02-03` | `src/ets2v2/package/builder.py` | service / packager | file-I/O | `src/ets2v2/baseline/extractor.py` | role-match | Clean staging of `dist/workshop/{summer,winter}/` (`versions.sii` + `universal/`, never `universal.zip` beside `universal/`) & `dist/local/ETS2V2_Core_{Summer,Winter}.zip` (deterministic `ZipInfo` `1980-01-01`, `0o644`, sorted paths) |
| `02-03` | `tests/test_package_synthesize.py` | test | unit | `tests/test_sii_country.py` & `test_sii_speed_limits.py` | exact | Parse synthesized `.sui`/`speed_limits.sii` back via `parse_country_data()`/`parse_speed_limits()`, verify zero hygiene diagnostics, `Estonia`, `regions[]`, `iceland` 60t/80, `train`/`tram` |
| `02-03` | `tests/test_package_builder.py` | test | integration | `tests/test_baseline_extractor.py` | exact | Build into `tmp_path`, verify byte-identical repeat runs, verify local ZIP via `ZipArchive` & `VfsStack`, verify no `def/country.sii` emitted |
| `02-04` | `src/ets2v2/validate/__init__.py` | barrel / facade | n/a | `src/ets2v2/vfs/__init__.py` | exact | Absolute imports, sorted `__all__` |
| `02-04` | `src/ets2v2/validate/models.py` | model / diagnostic | transform | `src/ets2v2/vfs/types.py` & `sii/hygiene.py` | exact | Frozen Pydantic `ValidationIssue` (`code`, `severity`, `path`, `detail`), `ValidationReport` (`ok`, `errors`, `warnings`, `issues`), deduplicating collector |
| `02-04` | `src/ets2v2/validate/invariants.py` | service / validator | transform | `tests/test_baseline_contracts.py` | role-match | Promotes 1.62 invariants (`Estonia`, `regions[]`, `iceland` 60t/80, `bus`/`train`/`tram`, `leftside_traffic`, `@@tz_*@@` 12-key whitelist) into typed library checks |
| `02-04` | `src/ets2v2/validate/workshop.py` | service / validator | file-I/O | `src/ets2v2/sii/hygiene.py` & `baseline/extractor.py::verify_baseline_bundle` | exact | Enforces SCS `00001`–`00010` + `WARN 00001`–`00002`, wraps `validate_sii_hygiene()`, `detect_3nk()`, `ZipArchive`/`DirectoryArchive`, Pillow `276x162` check |
| `02-04` | `tests/test_validate_workshop.py` | test | unit + integration | `tests/test_sii_hygiene.py` & `tests/test_vfs_archives.py` | exact | Positive pass on valid Summer/Winter builds + targeted fault-injection tests for every error code `00001`–`00010` and `WARN 00001`/`00002` |
| `02-05` | `src/ets2v2/publish/__init__.py` | barrel / facade | n/a | `src/ets2v2/baseline/__init__.py` | exact | Absolute imports, sorted `__all__` |
| `02-05` | `src/ets2v2/publish/ledger.py` | service / state | file-I/O | `src/ets2v2/baseline/extractor.py` & `models.py` | exact | Canonical SHA-256 over sorted `(rel_path, normalized_bytes)` excluding `package_version`, ISO-week `"1.62-YYYY.WW"` bump-only-on-change, `state/published.json` |
| `02-05` | `src/ets2v2/publish/changelog.py` | service / renderer | transform | `src/ets2v2/baseline/models.py` | role-match | Deterministic LF UTF-8 Markdown diff (`CHANGELOG_SUMMER.md`, `CHANGELOG_WINTER.md`) comparing previous vs current resolved snapshot |
| `02-05` | `src/ets2v2/publish/release.py` | service / orchestrator | batch | `src/ets2v2/baseline/extractor.py` | role-match | Composes `registry` -> `package` -> `validate` -> `publish.ledger` -> `publish.changelog`, clean no-op exit when canonical hashes match |
| `02-05` | `state/published.json` | state / ledger | file-I/O | `data/baselines/ets2_1.62_def/manifest.json` | exact | Deterministic sorted JSON tracking `summer` and `winter` canonical SHA-256s and `package_version` independently |
| `02-05` | `src/ets2v2/cli.py` | CLI entrypoint | request-response | `src/ets2v2/cli.py` (in-place) | exact | `_handle_*` functions with explicit `cast(...)`, `_make_help_handler()`, subparsers, stderr errors + POSIX exit codes `0`/`1` |
| `02-05` | `.github/workflows/release-phase-a.yml` | CI workflow | batch | `.github/workflows/ci.yml` | exact | `ubuntu-latest`, `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `uv sync --locked`, cron `'0 6 * * 5'`, `workflow_dispatch`, persistent PR (`contents: write`, `pull-requests: write`), zero Steam secrets |
| `02-05` | `tests/test_publish_ledger.py` | test | unit + integration | `tests/test_baseline_extractor.py` | exact | No-op SHA-256 gate (unchanged edition doesn't bump), independent summer/winter bump, ISO-week formatting, deterministic changelog |
| `02-05` | `tests/test_publish_workflow.py` | test | contract | `tests/test_cli_scaffold.py::test_ci_workflow_configuration` | exact | Verifies LF no-BOM, cron `0 6 * * 5`, `force_run`, zero Steam secrets, least-privilege permissions in `release-phase-a.yml` |
| `02-01` | `tests/test_cli_scaffold.py` | test | contract | `tests/test_cli_scaffold.py` (in-place) | exact | Update `test_active_phase_only_package_layout`, `test_pyproject_metadata_and_quality_gates`, `test_uv_lock_contains_verified_packages` |

---

## 3. Concrete Pattern Assignments (Code to Copy From)

### Pattern A — Strict Frozen Pydantic v2 Models (`02-01`, `02-02`, `02-04`, `02-05`)

**Analog:** `src/ets2v2/baseline/models.py` (lines 1-36) & `src/ets2v2/vfs/types.py` (lines 11-47)

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Season = Literal["summer", "winter"]


class CountryLawRecord(BaseModel):
    """Canonical statutory rules for one ISO-3166 alpha-2 country."""

    # Upgrade Phase 1's ConfigDict(frozen=True) to strict + extra="forbid" per D-01:
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str
    iana_timezone: str
    mass_limit_per_axle_count: list[int] = Field(default_factory=list)
```

**Conventions to preserve:**
- Always include `from __future__ import annotations` at line 3.
- Use `Field(default_factory=list)` / `Field(default_factory=dict)` with explicit type annotations (never bare `= []`).
- Immutable updates via `model.model_copy(update={...})` (`src/ets2v2/baseline/extractor.py:193`, `src/ets2v2/vfs/types.py:147`).
- JSON deserialization **always** via `Model.model_validate_json(path.read_text("utf-8"))` (`src/ets2v2/baseline/extractor.py:504`, `tests/test_baseline_contracts.py:59-73`) — **never** `Model.model_validate(json.loads(...))` under `strict=True` (see Section 5).

---

### Pattern B — Deterministic Canonical JSON & SHA-256 Helper (`02-01`, `02-02`, `02-05`)

**Analog:** `src/ets2v2/baseline/extractor.py` (lines 164-184, 449-515)

```python
def _serialize_model_bytes(model: BaseModel) -> bytes:
    payload: object = model.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")
```

**Apply to:**
- Writing/verifying `data/laws/countries/<iso2>.json` and `data/mappings/ets2_countries.json` (`02-01`).
- Emitting `realism-snapshot-{summer,winter}.json` (`02-02`, `02-05`).
- Reading/writing `state/published.json` and computing canonical SHA-256 digests (`02-05`).
- Note the exact `payload: object = model.model_dump(mode="json")` annotation: this avoids `basedpyright` `reportUnknownVariableType` warnings when `model_dump()` returns `dict[str, Any]`.
- Always check UTF-8 no-BOM (`not raw.startswith(b"\xef\xbb\xbf")`) and LF-only (`b"\r" not in raw`) just like `verify_baseline_bundle()` (`src/ets2v2/baseline/extractor.py:488-492`).

---

### Pattern C — Clean-Room SII/SUI Synthesis & Hygiene Verification (`02-03`)

**Analog:** `src/ets2v2/sii/country.py` (lines 102-118), `src/ets2v2/sii/speed_limits.py` (lines 125-136), `src/ets2v2/sii/hygiene.py` (lines 61-69, 235-337)

Exact string & float formatting rules to match `src/ets2v2/sii/country.py:102-118`:
```python
def _format_fuel_price(value: float) -> str:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid fuel_price: {value!r}")
    formatted = f"{value:.6f}".rstrip("0")
    if formatted.endswith("."):
        formatted += "0"
    return formatted


def _format_sii_string(value: str) -> str:
    if "\\" in value or "\x00" in value:
        raise ValueError(f"Disallowed backslash or NUL in SII string literal: {value!r}")
    escaped = (
        value.replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    )
    return f'"{escaped}"'
```

Exact lane block rendering matching `src/ets2v2/sii/speed_limits.py:125-135`:
```python
def _format_lane_rule_lines(rule: LaneSpeedRule, indent: str) -> list[str]:
    lines = [f"{indent}lane_speed_class[]: {rule.lane_speed_class}"]
    if rule.limit is not None:
        lines.append(f"{indent}limit[]: {rule.limit}")
    if rule.urban_limit is not None:
        lines.append(f"{indent}urban_limit[]: {rule.urban_limit}")
    if rule.max_limit is not None:
        lines.append(f"{indent}max_limit[]: {rule.max_limit}")
    if rule.uncommon is not None:
        lines.append(f"{indent}uncommon[]: {'true' if rule.uncommon else 'false'}")
    return lines
```

**Mandatory Synthesis Post-Condition (D-04, D-05):**
1. Preserve `BaselineCountry.iso_country_code_quoted`: emit `iso_country_code: "bih"` when `True`, unquoted `iso_country_code: isl` when `False`.
2. Preserve `country_id`, `name`, `name_localized`, `country_code`, `pos`, `fuel_price` (1.62 baseline unchanged in Phase 2), `driving_tired_offence`, `imperial_units`, `leftside_traffic`, `trailer_standalone`, `secondary_time_zone_area[]`/`secondary_time_zone[]`/`secondary_time_zone_name[]`, `regions[]`/`region_areas[]`, and `extra_attributes` verbatim from `BaselineCountry`.
3. Preserve `train` and `tram` `VehicleSpeedLimitBlock` blocks verbatim from `BaselineSpeedLimit` alongside synthesized `car`/`truck`/`bus` blocks.
4. Encode every emitted `.sii`/`.sui` via `serialize_sii_text(rendered)` and assert `validate_sii_hygiene(raw_bytes, require_siinunit=is_sii) == []` (`require_siinunit=False` for `.sui` country fragments, `True` for `speed_limits.sii`, `versions.sii`, `manifest.sii`).
5. Never emit `def/country.sii` or `def/country.ets2v2.sii` in Core builds (D-05).

---

### Pattern D — Deduplicated Diagnostic Collection & Validation (`02-04`)

**Analog:** `src/ets2v2/vfs/types.py` (lines 111-165) & `src/ets2v2/sii/hygiene.py` (lines 40-49, 235-337)

```python
class ValidationCollector:
    """Deduplicated accumulator mirroring ``ets2v2.vfs.types.DiagnosticCollector``."""

    def __init__(self) -> None:
        self._items: list[ValidationIssue] = []
        self._keys: set[tuple[str, Literal["error", "warning"], str | None, str]] = set()

    @property
    def items(self) -> list[ValidationIssue]:
        return list(self._items)

    def add(
        self,
        code: str,
        severity: Literal["error", "warning"],
        path: str | None,
        detail: str,
    ) -> None:
        key = (code, severity, path, detail)
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(
            ValidationIssue(code=code, severity=severity, path=path, detail=detail)
        )
```

**Key Offline Validator Boundary Detail (`02-04`):**
- Reuse `validate_sii_hygiene(raw_bytes, require_siinunit=...)` directly on `versions.sii`, `manifest.sii`, `def/country/*.sui`, and `def/country/*/speed_limits.sii`. Note that `src/ets2v2/sii/hygiene.py:21-33` **already** lists `"icon"` and `"description_file"` in `_PATH_ATTR_KEYS`, so backslash and `..` checks on `manifest.sii` paths work out of the box!
- Reuse `detect_3nk(raw_bytes)` (`ets2v2.vfs.types`) to reject `3nK\x01` obfuscated payloads.
- Reuse `ZipArchive` / `DirectoryArchive` / `VfsStack` to verify archive readability, zero `ArchiveDiagnostic` errors, and POSIX path resolution.
- **IMPORTANT ZIP raw-header check:** `ZipArchive._load_central_directory()` (`src/ets2v2/vfs/zip_archive.py:114`) normalizes `\` to `/` via `normalize_vfs_path()`. Therefore, for SCS ZIP hygiene checks (rejecting raw `\` entry names, verifying `ZIP_STORED`/`ZIP_DEFLATED`, rejecting encrypted `flag_bits & 0x41`, checking deterministic `1980-01-01` timestamps when desired), also inspect `zipfile.ZipFile(path, "r").infolist()` raw `info.filename` alongside `ZipArchive`.

---

### Pattern E — CLI Subcommand Wiring (`02-01` through `02-05`)

**Analog:** `src/ets2v2/cli.py` (lines 25-33, 95-155, 157-252)

```python
def _handle_validate_workshop(args: argparse.Namespace) -> int:
    target = cast(Path, args.target)
    as_json = cast(bool, args.json)
    try:
        report = validate_workshop_package(target)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: validation failed: {exc}", file=sys.stderr)
        return 1

    if as_json:
        payload: object = report.model_dump(mode="json")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if report.ok else 1

    for issue in report.issues:
        loc = f" [{issue.path}]" if issue.path else ""
        print(f"{issue.severity.upper()} {issue.code}{loc}: {issue.detail}", file=sys.stderr)
    return 0 if report.ok else 1
```

**Conventions from `src/ets2v2/cli.py`:**
- Group Phase 2 commands cleanly under top-level noun subparsers (`registry`, `package`, `validate`, `publish`) mirroring `vfs` and `baseline`, each attaching `.set_defaults(handler=_make_help_handler(sub))` so bare `ets2v2 <noun>` prints help and exits `0`.
- Never call `print()` or import `logging` inside library modules (`registry/`, `package/`, `validate/`, `publish/`); all stdout/stderr formatting stays in `src/ets2v2/cli.py`.
- Explicitly `cast(...)` every attribute read off `argparse.Namespace`.
- Catch domain/IO errors at the CLI boundary, print `error: ...` to `sys.stderr`, and return `1`.

---

### Pattern F — GitHub Actions CI Workflow (`02-05`)

**Analog:** `.github/workflows/ci.yml` (lines 1-40)

```yaml
name: Phase A Weekly Release

on:
  schedule:
    - cron: "0 6 * * 5"
  workflow_dispatch:
    inputs:
      force_run:
        description: "Force rebuild and artifact upload even if canonical hashes match"
        required: false
        default: false
        type: boolean

permissions:
  contents: write
  pull-requests: write

jobs:
  release-phase-a:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Set up uv and Python 3.12
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
          python-version: "3.12"
      - name: Install locked dependencies
        run: uv sync --locked
```

**Conventions:**
- Strictly UTF-8 without BOM and LF (`\n`) endings (asserted in `tests/test_publish_workflow.py` copying `tests/test_cli_scaffold.py:137-160`).
- Zero Steam credentials/secrets referenced anywhere in the workflow (`STEAM_USERNAME`, `STEAM_PASSWORD`, `STEAM_SHARED_SECRET`, `steamcmd` strictly absent).
- Keep `.github/workflows/ci.yml` unchanged and fast (`permissions: contents: read`), isolating write permissions (`contents: write`, `pull-requests: write`) exclusively to `.github/workflows/release-phase-a.yml`.

---

### Pattern G — Test Structure & Fixtures (`02-01` through `02-05`)

**Analogs:** `tests/test_baseline_contracts.py`, `tests/test_baseline_extractor.py`, `tests/test_sii_hygiene.py`, `tests/test_sii_country.py`, `tests/test_cli_scaffold.py`

- Standalone typed functions (`def test_<behavior>(tmp_path: pathlib.Path) -> None:`), zero `unittest.TestCase`.
- Annotate pytest fixtures explicitly: `tmp_path: pathlib.Path`, `capsys: pytest.CaptureFixture[str]`, `monkeypatch: pytest.MonkeyPatch`.
- Use `@pytest.mark.parametrize(...)` for matrix cases (timezone edge cases, SCS validation error codes `00001`–`00010`, malformed laws).
- Use `REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent` for committed repo data paths (`data/baselines/ets2_1.62_def`, `data/laws`, `data/mappings`, `assets/icons`, `state/published.json`).
- Keep 100% of Phase 2 tests CI-safe (zero `@pytest.mark.local_ets2` required because D-04 compiles purely from committed `data/baselines/ets2_1.62_def/*.json` + `data/laws/` + `data/mappings/`).

---

## 4. Exact Reusable Phase 1 APIs & Signatures

Phase 2 modules **MUST reuse** these existing symbols directly instead of duplicating parsing, hygiene, VFS, or baseline logic.

### `ets2v2.baseline.models` (`src/ets2v2/baseline/models.py`)

| Symbol | Line | Exact Fields / Contract | Phase 2 Consumers |
|---|---|---|---|
| `BaselineManifest` | `:14` | `game_version: str`, `application: str`, `extractor_schema_version: int = 1`, `country_count: int`, `speed_limit_count: int`, `locale_count: int`, `tz_key_count: int`, `file_sha256s: dict[str, str]` | `registry.loader`, `publish.ledger` |
| `BaselineCountry` | `:38` | `slug: str`, `vfs_path: str`, `include_path: str`, `unit_name: str`, `country_id: int`, `name: str`, `name_localized: str \| None`, `country_code: str`, `iso_country_code: str`, `iso_country_code_quoted: bool`, `pos: tuple[float, float, float] \| None`, `fuel_price: float \| None`, `lights_mandatory: bool \| None`, `driving_tired_offence: bool \| None`, `imperial_units: bool \| None`, `leftside_traffic: bool \| None`, `trailer_standalone: bool \| None`, `time_zone: int \| None`, `time_zone_name: str \| None`, `secondary_time_zone_area: list[tuple[float, float, float, float]]`, `secondary_time_zone: list[int]`, `secondary_time_zone_name: list[str]`, `mass_limit_per_axle_count: list[int]`, `regions: list[str]`, `region_areas: list[tuple[float, float, float, float]]`, `extra_attributes: dict[str, list[str]]` | `registry.loader`, `registry.snapshot`, `package.synthesize`, `validate.invariants` |
| `CountriesBaseline` | `:71` | `countries: list[BaselineCountry]` (load via `CountriesBaseline.model_validate_json(...)`) | `registry.loader`, `package.builder`, `validate.invariants` |
| `BaselineSpeedLimit` | `:79` | `slug: str`, `vfs_path: str`, `vehicle_classes: list[str]`, `has_train: bool`, `has_tram: bool`, `blocks: list[VehicleSpeedLimitBlock]` | `package.synthesize`, `validate.invariants` |
| `SpeedLimitsBaseline` | `:92` | `speed_limits: list[BaselineSpeedLimit]` (load via `SpeedLimitsBaseline.model_validate_json(...)`) | `package.builder`, `validate.invariants` |
| `LocalesBaseline` | `:143` | `active_locales: list[str]`, `tz_keys: list[str]`, `fp_keys: list[str]` (12 `tz_*` keys whitelist!) | `registry.timezone`, `validate.invariants` |
| `BaselineBundle` | `:153` | `manifest`, `countries`, `speed_limits`, `fuel_boards`, `locales` | `package.builder`, `validate.workshop` |

### `ets2v2.sii.hygiene` (`src/ets2v2/sii/hygiene.py`)

| Symbol | Line | Exact Signature | Re-exported in `ets2v2.sii`? | Phase 2 Consumers |
|---|---|---|---|---|
| `SiiEncodingError` | `:36` | `class SiiEncodingError(ValueError)` | Yes | `package.*`, `validate.workshop` |
| `SiiDiagnostic` | `:41` | `@dataclass(frozen=True)`: `code: str`, `message: str`, `line: int = 1`, `column: int = 1`, `severity: Literal["error", "warning"] = "error"` | Yes | `validate.workshop` |
| `normalize_sii_bytes` | `:51` | `(raw: bytes) -> str` | Yes | `validate.workshop` |
| `serialize_sii_text` | `:61` | `(text: str) -> bytes` | Yes | `package.synthesize`, `package.metadata` |
| `validate_unit_name_segments` | `:71` | `(unit_name: str, *, line: int = 1, column: int = 1) -> list[SiiDiagnostic]` | **No** (import from `ets2v2.sii.hygiene`) | `validate.workshop` |
| `validate_string_path_hygiene` | `:147` | `(raw_value: str, *, key: str \| None = None, is_include: bool = False, line: int = 1, column: int = 1) -> list[SiiDiagnostic]` | **No** (import from `ets2v2.sii.hygiene`) | `validate.workshop` |
| `validate_sii_hygiene` | `:235` | `(source: str \| bytes, *, require_siinunit: bool = False) -> list[SiiDiagnostic]` | Yes | `package.synthesize`, `package.metadata`, `validate.workshop` |

### `ets2v2.sii.document` & `ets2v2.sii.lexer` (`src/ets2v2/sii/document.py`, `lexer.py`)

| Symbol | Location | Exact Signature | Phase 2 Consumers |
|---|---|---|---|
| `SiiDocument.parse` | `document.py:38` | `(source: str \| bytes, *, require_siinunit: bool = False) -> SiiDocument` | `validate.workshop` (inspecting `versions.sii`, `manifest.sii` units & attributes!) |
| `SiiDocument.find_units` | `document.py:76` | `(class_name: str \| None = None, unit_name: str \| None = None) -> list[SiiUnitBlock]` | `validate.workshop` (`package_version_info`, `mod_package`) |
| `SiiDocument.get_unit` | `document.py:89` | `(class_name: str \| None = None, unit_name: str \| None = None) -> SiiUnitBlock \| None` | `validate.workshop` |
| `SiiUnitBlock.get_scalar` | `lexer.py:92` | `(key: str) -> SiiAttributeSpan \| None` | `validate.workshop` (`package_name`, `icon`, `description_file`, `mp_mod_optional`, `display_name`) |
| `SiiUnitBlock.get_attributes` | `lexer.py:99` | `(key: str) -> list[SiiAttributeSpan]` | `validate.workshop` (`category[]`, `compatible_versions[]`) |
| `unquote_sii_string` | `lexer.py:155` | `(raw: str) -> tuple[str, bool]` | `validate.workshop` |
| `parse_sii_bool` | `lexer.py:134` | `(raw: str) -> bool` | `validate.workshop` |

### `ets2v2.sii.country` (`src/ets2v2/sii/country.py`)

| Symbol | Line | Exact Signature | Phase 2 Consumers |
|---|---|---|---|
| `CountryDataModel` | `:44` | Frozen Pydantic v2 model (20 ETS2 `country_data` attributes + `iso_country_code_quoted` + `extra_attributes`) | `validate.invariants`, `tests/test_package_synthesize.py` |
| `CountryDataPatch` | `:74` | Frozen Pydantic v2 patch (`fuel_price`, `lights_mandatory`, `driving_tired_offence`, `time_zone`, `time_zone_name`, `mass_limit_per_axle_count`) | Optional round-trip validation / future Phase 4 |
| `parse_country_includes` | `:129` | `(source: str \| bytes) -> list[str]` | `validate.workshop` (if checking stray includes) |
| `parse_country_data` | `:148` | `(source: str \| bytes) -> CountryDataModel` | `validate.invariants`, `validate.workshop`, `tests/test_package_synthesize.py` |
| `patch_country_data` | `:264` | `(source: str \| bytes, patch: CountryDataPatch) -> str` | Round-trip verification |

### `ets2v2.sii.speed_limits` (`src/ets2v2/sii/speed_limits.py`)

| Symbol | Line | Exact Signature | Phase 2 Consumers |
|---|---|---|---|
| `LaneSpeedRule` | `:21` | `lane_speed_class: str`, `limit: int \| None = None`, `urban_limit: int \| None = None`, `max_limit: int \| None = None`, `uncommon: bool \| None = None` | `registry.models`, `registry.snapshot`, `package.synthesize`, `validate.invariants` |
| `VehicleSpeedLimitBlock` | `:33` | `unit_name: str`, `vehicle_speed_class: str`, `lanes: list[LaneSpeedRule]` | `package.synthesize`, `validate.invariants` |
| `SpeedLimitsFile` | `:43` | `blocks: list[VehicleSpeedLimitBlock]`, `.vehicle_classes -> list[str]`, `.get_block(vehicle_speed_class: str) -> VehicleSpeedLimitBlock \| None` | `validate.invariants`, `tests/test_package_synthesize.py` |
| `parse_speed_limits` | `:250` | `(source: str \| bytes) -> SpeedLimitsFile` | `validate.invariants`, `validate.workshop`, `tests/test_package_synthesize.py` |
| `patch_speed_limits` | `:267` | `(source: str \| bytes, updates: Mapping[str, Sequence[LaneSpeedRule]]) -> str` | Round-trip verification |

### `ets2v2.vfs` (`src/ets2v2/vfs/types.py`, `zip_archive.py`, `dir_archive.py`, `stack.py`)

| Symbol | Location | Exact Signature | Phase 2 Consumers |
|---|---|---|---|
| `detect_3nk` | `vfs/types.py:33` | `(data: bytes) -> bool` | `validate.workshop` (zero `3nK\x01` invariant) |
| `normalize_vfs_path` | `vfs/types.py:63` | `(path: str, *, allow_empty: bool = False) -> str` | `package.builder`, `validate.workshop`, `publish.ledger` |
| `ArchiveDiagnostic` | `vfs/types.py:38` | `kind: DiagnosticKind`, `archive_path: str`, `entry_path: str \| None`, `detail: str` | `validate.workshop` |
| `ZipArchive` | `vfs/zip_archive.py:52` | `ZipArchive(path: Path)` — `list_paths()`, `read_bytes()`, `exists()`, `get_meta()`, `diagnostics`, context manager | `validate.workshop`, `tests/test_package_builder.py` |
| `DirectoryArchive` | `vfs/dir_archive.py` | `DirectoryArchive(path: Path)` — root-contained unpacked reader | `validate.workshop` |
| `VfsStack` | `vfs/stack.py:161` | `VfsStack.from_paths(paths, *, seeded_prefixes=..., enabled_dlcs=...)`, `.list_paths()`, `.read_bytes()`, `.diagnostics()`, `.empty_stub_paths()` | `validate.workshop`, `tests/test_package_builder.py` |

### `ets2v2.cli` (`src/ets2v2/cli.py`)

| Symbol | Line | Exact Signature | Phase 2 Consumers |
|---|---|---|---|
| `CommandHandler` | `:25` | `Callable[[argparse.Namespace], int]` | All new Phase 2 CLI subcommand handlers |
| `_make_help_handler` | `:157` | `(subparser: argparse.ArgumentParser) -> CommandHandler` | New `registry`, `package`, `validate`, `publish` parent subparsers |
| `build_parser` | `:165` | `() -> argparse.ArgumentParser` | Extend with Phase 2 subcommand trees |
| `main` | `:255` | `(argv: Sequence[str] \| None = None) -> int` | CLI integration tests |

---

## 5. Testing, Typing & CI Guardrails

### `basedpyright` Strict Pitfalls (`typeCheckingMode = "strict"`, `pythonVersion = "3.12"`)

`pyproject.toml` runs `basedpyright` in strict mode across **both `src/` and `tests/`** with zero `# type: ignore` or `# pyright: ignore` comments allowed. Watch out for these six Phase 2 traps:

1. **Pydantic v2 `strict=True` + JSON Deserialization (`model_validate_json` vs `model_validate`):**
   - **Pitfall:** Under `ConfigDict(strict=True, frozen=True, extra="forbid")` (D-01), calling `MyModel.model_validate(json.loads(text))` **fails at runtime** for `tuple[...]` fields (JSON arrays become `list`, which fails strict `tuple` checks), `datetime.date` fields (strings fail strict `date` checks), and `set`/`frozenset` fields.
   - **Rule:** Always load JSON files with `MyModel.model_validate_json(path.read_text("utf-8"))` (or `.read_bytes()`). In JSON mode, Pydantic v2 validates JSON types strictly (`"1"` does not coerce to `int`, `1` does not coerce to `bool`) while cleanly constructing `tuple`, `date`, and `Literal` fields.
   - **Dump rule:** `model.model_dump(mode="json")` is typed as `dict[str, Any]`. Assign `payload: object = model.model_dump(mode="json")` before `json.dumps(payload, ...)` (mirroring `src/ets2v2/baseline/extractor.py:165`).

2. **`Pillow` (`PIL`) Typing Quirks under Strict `basedpyright`:**
   - `Image.open(path)` returns `ImageFile.ImageFile`: `img.format` is `str | None` (narrow with `if img.format != "JPEG":`), and `img.info` is typed as `dict[Any, Any]` — accessing `img.info` directly triggers `reportUnknownMemberType` / `reportUnknownVariableType`. Narrow via `info = cast(dict[str, object], img.info)` or use `img.getexif()` (typed as `Image.Exif`, check `len(img.getexif()) == 0`).
   - `ImageFont.load_default(size=...)` returns `ImageFont.FreeTypeFont | ImageFont.ImageFont`; annotate variables explicitly as `font: ImageFont.ImageFont | ImageFont.FreeTypeFont`.
   - Pass explicit `tuple[int, int]` / `tuple[int, int, int]` / `tuple[int, int, int, int]` coordinates to `ImageDraw.Draw(img)` calls, and explicit keyword arguments to `img.save(buf, format="JPEG", quality=92, optimize=True, subsampling=0)` (never untyped `**kwargs` dicts).

3. **`zoneinfo` + `tzdata` Typing & Windows Discovery:**
   - `dt = datetime(year, month, day, 12, 0, tzinfo=ZoneInfo(iana_tz))`: both `dt.utcoffset()` (`timedelta | None`) and `dt.tzname()` (`str | None`) are nullable in typeshed! Explicitly check `if offset is None or abbr is None: raise ValueError(...)` before arithmetic or `.lower()`.
   - `tzdata` is a data-only package; do **not** `import tzdata` in `src/` (would trigger Ruff `F401`). Verify presence in tests via `importlib.metadata.version("tzdata")` (mirroring `tests/test_cli_scaffold.py:163`).

4. **Mutable Container Invariance (`list` / `dict`):**
   - `list[Child]` is invariant and not assignable to `list[Base]`; `dict[str, int]` is not assignable to `dict[str, object]`.
   - Accept `Sequence[...]` / `Mapping[...]` / `Iterable[...]` in all public function parameters (matching `src/ets2v2/sii/speed_limits.py:269`), and return concrete `list[...]` / `dict[...]` / `tuple[...]`.

5. **Untyped `argparse.Namespace`, `json.loads()`, and `tomllib.loads()`:**
   - Cast `argparse.Namespace` fields explicitly at the top of every `_handle_*` handler (`cast(Path, args.out_dir)` — `src/ets2v2/cli.py:29-32`).
   - Narrow `json.loads(...)` via `cast(dict[str, object], json.loads(...))` or typed helpers `_as_table`/`_as_str_list` (`tests/test_cli_scaffold.py:20-32`).

6. **Typed `pytest` Fixtures & Return Annotations:**
   - Every test function must annotate `-> None` and parameter types (`tmp_path: pathlib.Path`, `capsys: pytest.CaptureFixture[str]`, `monkeypatch: pytest.MonkeyPatch`).

### `ruff` Rule Set Enforcement (`select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`)

Configured in `pyproject.toml` (`target-version = "py312"`, `line-length = 100`, `src = ["src", "tests"]`, zero `# noqa`):
- **`I`**: 4-group sorted imports (`__future__`, stdlib, third-party, `ets2v2.*`); absolute imports only (never `from .models import ...`).
- **`UP`**: PEP 604 `X | Y`, built-in generics `list[str]`, `collections.abc.{Sequence,Mapping,Iterable,Callable}`.
- **`B`**: Always `zip(..., strict=True)` (`B905`), `raise ... from exc` (`B904`), no mutable defaults (`B006`).
- **`SIM`**: Combine nested `with` blocks into `with (a as x, b as y):` (`SIM117`), simplify boolean returns (`SIM103`).
- **`RUF`**: Sort `__all__` alphabetically in every `__init__.py` (`RUF022`), annotate class constants with `Final` / `ClassVar` where appropriate (`RUF012`).

### Required `tests/test_cli_scaffold.py` Updates in Wave 1 of Phase 2

Plan `02-01` (Wave 1) **MUST** update `tests/test_cli_scaffold.py` alongside adding Phase 2 dependencies and activating Phase 2 subpackages so CI stays green at every plan boundary:

1. **`test_active_phase_only_package_layout()` (`tests/test_cli_scaffold.py:63-74`):**
   - Replace lines 68–72:
     ```python
     deferred_phase_dirs = {"fetch", "normalize", "merge"}
     allowed_phase2_entries = {
         "__init__.py",
         "py.typed",
         "cli.py",
         "vfs",
         "sii",
         "baseline",
         "registry",
         "package",
         "validate",
         "publish",
     }

     assert entries.isdisjoint(deferred_phase_dirs)
     assert entries <= allowed_phase2_entries
     assert {"__init__.py", "py.typed", "cli.py"} <= entries
     ```
   - Because `entries <= allowed_phase2_entries` is a subset check, Plans `02-01` -> `02-05` can create `registry/`, `package/`, `validate/`, and `publish/` sequentially without intermediate scaffold churn while still strictly blocking `fetch/`, `normalize/`, `merge/` and any unplanned top-level directories.

2. **`test_pyproject_metadata_and_quality_gates()` (`tests/test_cli_scaffold.py:88`):**
   - Line 88 currently asserts exact list equality:
     `assert _as_str_list(project["dependencies"]) == ["pydantic>=2.14,<3"]`
   - Update when adding `tzdata` and `pillow>=12,<14` in `pyproject.toml` (e.g., assert exact sorted list or `set(...)` containing `"pydantic>=2.14,<3"`, `"tzdata>=2024.1"` [or exact pin chosen], and `"pillow>=12,<14"`).

3. **`test_uv_lock_contains_verified_packages()` (`tests/test_cli_scaffold.py:133`):**
   - Line 133 currently asserts `expected = {"pydantic", "basedpyright", "pytest", "pytest-cov", "ruff"}`.
   - Extend `expected` to include `"tzdata"` and `"pillow"` once `uv lock` updates `uv.lock`.

4. **Inherited `data/` Clean-Room Guard (`tests/test_baseline_contracts.py:83-89`):**
   - `test_no_raw_scs_files_committed_under_data()` already recursively scans all of `data/` and fails if any `.sii` or `.sui` file is added anywhere under `data/` (including `data/laws/` and `data/mappings/`). No modification needed — keep passing!

### Quality Gate Commands (Run at Every Plan Boundary)

From `.planning/config.json` & `.github/workflows/ci.yml`:
```bash
uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright
uv run --offline pytest -q --tb=short
```
*(After modifying `pyproject.toml` in `02-01`/`02-02`, run `uv lock` + `uv sync --locked` online once so `--offline` commands and CI `uv sync --locked` remain deterministic.)*

---

## 6. No Direct Analog Found

Files introducing net-new Phase 2 dependencies/capabilities (planner should follow `02-CONTEXT.md` + `02-RESEARCH.md` + Section 5 strict-typing guardrails):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/ets2v2/registry/timezone.py` | utility / domain | transform | First use of stdlib `zoneinfo` + `tzdata` in repo; follow `sii/hygiene.py` pure-function + explicit `None`-narrowing style |
| `src/ets2v2/package/icons.py` | utility / generator | file-I/O | First use of `Pillow` in repo (`276x162` EXIF/ICC-stripped JPEG only — strictly zero `.dds` use); follow Section 5 `PIL` strict-typing rules |

---

## Metadata

**Analog search scope:** `src/ets2v2/`, `tests/`, `data/baselines/ets2_1.62_def/`, `.github/workflows/`, `pyproject.toml`, `.gitattributes`, `.gitignore`
**Files scanned:** 26 tracked source, test, baseline, and config files (all verified git-tracked via `git ls-files`)
**Pattern extraction date:** 2026-11-19
