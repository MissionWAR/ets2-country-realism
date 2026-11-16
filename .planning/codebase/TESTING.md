# Testing Patterns

**Analysis Date:** 2026-11-16

## Test Framework

**Runner:**
- `pytest>=9.2,<9.3` (locked `9.2.0` in `uv.lock`) with `pytest-cov>=6,<8` (locked `7.1.0`)
- Config: `pyproject.toml` (`[tool.pytest.ini_options]`):
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["src"]
  addopts = ["-ra", "--strict-markers"]
  markers = [
      "local_ets2: tests requiring local ETS2 1.62.3.3s archives",
  ]
  ```

**Assertion Library:**
- Built-in `pytest` `assert` statements, `pytest.approx(...)` for float/IEEE-754 hex comparisons, and `pytest.raises(..., match=...)` for typed exception assertions.

**Run Commands:**
```bash
uv run pytest                                  # Full suite (115 tests locally; local_ets2 skips on CI)
uv run --offline pytest -q --tb=short          # workflow.test_command (.planning/config.json)
uv run --offline ruff check && uv run --offline ruff format --check && uv run --offline basedpyright  # workflow.build_command
uv run pytest -k "not local_ets2"              # CI-safe suite only (113 tests, ~0.6s)
uv run pytest -m local_ets2                    # Live ETS2 1.62.3.3s archives only (2 tests, ~36s)
uv run pytest --cov=ets2v2 --cov-report=term-missing -k "not local_ets2"  # Coverage report
uv run --offline --no-sync pytest -p no:cacheprovider -q --tb=short       # Offline / cacheless run
```

## TDD Red-First Workflow

- `.planning/config.json` enforces `"tdd_mode": true` and `"nyquist_validation": true`.
- Write failing tests **before** production implementation or artifact generation (`RED -> GREEN -> REFACTOR`), documented directly in test module docstrings (e.g., `"""Red-first tests for ..."""` in `tests/test_sii_*.py`) and `.planning/phases/01-vfs-1-62-baseline-extraction-structural-sii-engine/01-VALIDATION.md`.
- Gate every RED step on lint/type cleanliness (`ruff check`, `ruff format --check`, `basedpyright`) alongside expected test failure (for example, `tests/test_baseline_contracts.py` verifies RED failure before extracting `data/baselines/ets2_1.62_def/*.json`).
- Execute `workflow.build_command` and `workflow.test_command` at every wave/task boundary; `.github/workflows/ci.yml` executes `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run basedpyright`, and `uv run pytest` on `ubuntu-latest`.

## Test File Organization

**Location:**
- All tests live in `tests/` (`testpaths = ["tests"]`), separated from `src/ets2v2/`.
- `.gitattributes` reserves `fixtures/** -text` for future static test fixtures; all current synthetic containers are generated inline per test module inside `tmp_path`.

**Naming & Inventory (`115` collected tests across `11` modules):**
| Test File | Tests | Scope & Fixtures |
| --- | --- | --- |
| `tests/test_cli_scaffold.py` | 9 | CLI `--version`/`--help`, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml` LF/no-BOM, active-phase `src/ets2v2/` layout |
| `tests/test_vfs_cityhash.py` | 25 | CityHash64 1.0.3 constants (`K0`–`K3`), all byte-length buckets, salted hashes, `normalize_vfs_path` traversal/NUL rejection |
| `tests/test_vfs_archives.py` | 15 | Synthetic HashFS v1/v2 (`_build_hashfs_v1`, `_build_hashfs_v2`), ZIP flags (`0x01`, `0x40`, `compress_type=99`), `DirectoryArchive` symlinks/NTFS junctions, decompression caps |
| `tests/test_vfs_stack.py` | 18 | Multi-layer overlay priority, `base/` normalization, `dlc_<id>/` scoping, empty `SiiNunit {}` stub shadowing, `MAX_STUB_INSPECT_BYTES` |
| `tests/test_sii_hygiene.py` | 10 | BOM/CRLF/CR normalization, pass-1/pass-2 idempotency, strict UTF-8/surrogate errors, column-0 `@include`, POSIX paths, `[a-z0-9_]{1,12}` segments |
| `tests/test_sii_document.py` | 9 | IEEE-754 `&hex` floats, comments/strings/arrays, scalar/array span edits, single-line & shared-brace units, unclosed `(` recovery, last-wins scalars |
| `tests/test_sii_country.py` | 8 | `country.sii` `@include` extraction, all 20 `country_data` attributes, fixed-array `attr[i]` replacement, string escaping, quote preservation |
| `tests/test_sii_speed_limits.py` | 3 | Interleaved `lane_speed_class[]` parsing, `train`/`tram` verbatim preservation, `uncommon[]`, shared-brace edits |
| `tests/test_sii_boards_locales.py` | 5 | `sign_board_template` + `sign_template_text` parsing, highway sign exclusion, DoS `items` count safety, `localization_db` wrapped/headerless parsing |
| `tests/test_baseline_extractor.py` | 5 | `resolve_game_dir` precedence, `_create_synthetic_ets2_install` HashFS v2 extraction, `ets2v2` CLI `vfs inspect` & `baseline extract --check`, `data/` cache guard |
| `tests/test_baseline_contracts.py` | 8 | Committed `data/baselines/ets2_1.62_def/*.json` schema/SHA-256 contracts (`6` CI-safe) + `@pytest.mark.local_ets2` live `1.62.3.3s` round-trips (`2` local) |

## Test Structure

**Suite Organization:**
- Write standalone typed test functions (`def test_<behavior>(...) -> None:`) with `@pytest.mark.parametrize` for input matrices; avoid `unittest.TestCase` classes.
```python
@pytest.mark.parametrize("bad_path", ["../secret.sii", "def/../secret.sii", "def/foo\x00bar.sii"])
def test_normalize_vfs_path_rejects_traversal_and_nul(bad_path: str) -> None:
    with pytest.raises(ValueError):
        normalize_vfs_path(bad_path)
```
- Annotate pytest fixtures explicitly (`tmp_path: pathlib.Path`, `capsys: pytest.CaptureFixture[str]`, `monkeypatch: pytest.MonkeyPatch`) to satisfy strict `basedpyright` (`tests/test_cli_scaffold.py`, `tests/test_vfs_stack.py`, `tests/test_baseline_extractor.py`).

## CI-Safe Synthetic Fixtures vs `@pytest.mark.local_ets2`

**CI-Safe Synthetic Builders (`113` tests):**
- Build self-contained binary containers in `tmp_path` so CI runs cleanly on `ubuntu-latest` without proprietary `.scs` files:
  - `_build_hashfs_v1` (`tests/test_vfs_archives.py`) and `_build_hashfs_v1_simple` (`tests/test_vfs_stack.py`) pack `SCS#\x01` headers, zlib entries, and sorted CityHash64 entry tables.
  - `_build_hashfs_v2` and `_encode_v2_dir_listing` (`tests/test_vfs_archives.py`, `tests/test_baseline_extractor.py`) emit 16-byte aligned `SCS#\x02` containers with `0x80`/`0x81` metadata descriptors and optional stripped-root `locale.scs` layouts.
  - `_build_mixed_encrypted_zip` (`tests/test_vfs_archives.py`) and `_build_encrypted_single_zip` (`tests/test_vfs_stack.py`) patch ZIP `flag_bits` (`0x01` legacy / `0x40` strong encryption) and `compress_type` (`99`) directly in ZIP headers.
  - `_create_synthetic_ets2_install` (`tests/test_baseline_extractor.py`) constructs a complete synthetic ETS2 install (`version.scs`, `def.scs`, `locale.scs`, `dlc_*.scs`) for offline extractor and CLI verification.
- Verify committed baseline contracts in `tests/test_baseline_contracts.py` by validating all 5 JSON files under `data/baselines/ets2_1.62_def/` against `BaselineBundle` and checking `file_sha256s` without local archives.

**Live-Archive Verification (`@pytest.mark.local_ets2`, `2` tests):**
- Gate every test requiring real ETS2 `1.62.3.3s` archives with both `@pytest.mark.local_ets2` and `skipif`:
  ```python
  @pytest.mark.local_ets2
  @pytest.mark.skipif(not _has_local_ets2(), reason="Local ETS2 1.62.3.3s archives not present")
  def test_local_ets2_extract_matches_committed_baseline_zero_diff() -> None:
      bundle = extract_baseline(resolve_game_dir())
      assert verify_baseline_bundle(bundle, BASELINE_DIR) == []
  ```
- `_has_local_ets2()` in `tests/test_baseline_contracts.py` uses `resolve_game_dir()` (`ETS2_GAME_DIR` env var or `D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2`) to verify `version.scs`, `def.scs`, and `locale.scs` exist; when absent in CI, pytest skips both tests cleanly.
- `test_local_ets2_all_36_sii_surgical_round_trips_in_memory` verifies byte-preserving surgical no-op and mutation round-trips across all 36 `def.scs` country and `speed_limits.sii` files strictly in memory.

## Mocking

**Framework:**
- Use pytest's `monkeypatch: pytest.MonkeyPatch` (`tests/test_vfs_stack.py`, `tests/test_vfs_archives.py`, `tests/test_baseline_extractor.py`) rather than `unittest.mock`.

**Patterns:**
```python
monkeypatch.setattr(stack_mod, "MAX_STUB_INSPECT_BYTES", 32)
monkeypatch.setattr(pathlib.Path, "is_junction", fake_is_junction, raising=False)
monkeypatch.delenv("ETS2_GAME_DIR", raising=False)
monkeypatch.chdir(tmp_path)
```

**What to Mock:**
- Resource ceiling constants (`MAX_STUB_INSPECT_BYTES`, `MAX_ENTRY_DECOMPRESSED_BYTES`, `MAX_ZIP_ENTRY_BYTES`) to test decompression/stub caps with tiny payloads.
- OS/filesystem edge calls (`pathlib.Path.is_junction`, `pathlib.Path.resolve`, `zipfile.ZipFile.open`, `ETS2_GAME_DIR`, CWD) to test cross-platform junction pruning and streaming bomb aborts deterministically.

**What NOT to Mock:**
- Never mock `cityhash64`, `SiiDocument`, `validate_sii_hygiene`, `VfsStack` priority resolution, or `ZipArchive`/`HashFs*` binary parsing — exercise real implementations against synthetic fixtures.

## Coverage

**Requirements:**
- `pytest-cov` (`7.1.0`) is installed in `[dependency-groups].dev` in `pyproject.toml`; no coverage floor is enforced yet in `pyproject.toml` or `.github/workflows/ci.yml`.

**View Coverage:**
```bash
uv run pytest --cov=ets2v2 --cov-report=term-missing -k "not local_ets2"
```

## Test Types

**Unit Tests:**
- Verify pure hashing (`tests/test_vfs_cityhash.py`), SII hygiene/lexer/document mutations (`tests/test_sii_hygiene.py`, `tests/test_sii_document.py`), ETS2 unit adapters (`tests/test_sii_country.py`, `tests/test_sii_speed_limits.py`, `tests/test_sii_boards_locales.py`), and package/CI metadata (`tests/test_cli_scaffold.py`).

**Integration Tests:**
- Verify archive dispatch and multi-layer `VfsStack` overlays (`tests/test_vfs_archives.py`, `tests/test_vfs_stack.py`), end-to-end synthetic extraction and `ets2v2` CLI subcommands (`tests/test_baseline_extractor.py`), committed JSON baseline contracts (`tests/test_baseline_contracts.py`), and live `1.62.3.3s` archive verification (`@pytest.mark.local_ets2`).

**E2E Tests:**
- Not separate from CLI `ets2v2.cli.main([...])` end-to-end invocations in `tests/test_baseline_extractor.py` and `ets2v2 baseline extract --check`.

## Common Patterns

**Idempotency & Zero-Diff Round-Trip Testing:**
```python
pass1 = doc_bom.to_bytes()
assert pass1 == clean_bytes
assert SiiDocument.parse(pass1).to_bytes() == pass1
```
- Assert clean LF no-BOM inputs round-trip unchanged on pass 1 and BOM/CRLF inputs normalize on pass 1 with zero diff on pass 2+ (`tests/test_sii_hygiene.py`, `tests/test_sii_document.py`, `tests/test_sii_country.py`, `tests/test_sii_speed_limits.py`, `tests/test_baseline_contracts.py`).

**Diagnostics, Error & CLI Testing:**
```python
with pytest.raises(ProtectedPayloadError):
    arc.read_bytes("def/country/beyond.sui")
assert any(d.kind == "encrypted_zip" for d in arc.diagnostics)
```
- Assert both raised exceptions/non-zero CLI exit codes (`capsys.readouterr().err`) and emitted `ArchiveDiagnostic` / `SiiDiagnostic` records across `tests/test_vfs_*.py`, `tests/test_sii_hygiene.py`, and `tests/test_baseline_extractor.py`.

---

*Testing analysis: 2026-11-16*
