---
phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine
plan: "02"
subsystem: vfs
status: complete
tags: [vfs, cityhash64, hashfs-v1, hashfs-v2, zip, directory, overlay, pydantic, tdd, basedpyright, ruff]

requires:
  - "01-01"
provides:
  - "Pure-Python MIT Google CityHash64 1.0.3 (00b9287e) and salted VFS path hasher (ets2v2.vfs.cityhash)"
  - "Read-only HashFsV1Archive, HashFsV2Archive, ProtectedArchiveStub, detect_3nk(), and open_archive() (ets2v2.vfs.hashfs)"
  - "Read-only ZipArchive with encrypted flag_bits & 0x1 central-directory inspection (ets2v2.vfs.zip_archive)"
  - "Read-only DirectoryArchive with root containment and symlink/traversal guards (ets2v2.vfs.dir_archive)"
  - "Priority-ordered VfsStack overlay engine with base/ normalization, dlc_<id>/ scoping, and empty SiiNunit {} stub detection (ets2v2.vfs.stack)"
  - "VfsArchive protocol, ArchiveDiagnostic, VfsEntryMeta, ProtectedPayloadError, UnsupportedCompressionError, and normalize_vfs_path() (ets2v2.vfs.types)"
affects: [01-03, phase-2, phase-3, phase-4]

tech-stack:
  added: []
  patterns: [clean-room MIT CityHash64 1.0.3, bounded zlib decompression for tables/payloads, multi-descriptor HashFS v2 metadata safety, deduplicated seeded prefix walking, detect-and-report protected container policy]

key-files:
  created:
    - src/ets2v2/vfs/__init__.py
    - src/ets2v2/vfs/types.py
    - src/ets2v2/vfs/cityhash.py
    - src/ets2v2/vfs/hashfs.py
    - src/ets2v2/vfs/zip_archive.py
    - src/ets2v2/vfs/dir_archive.py
    - src/ets2v2/vfs/stack.py
    - tests/test_vfs_cityhash.py
    - tests/test_vfs_archives.py
    - tests/test_vfs_stack.py
  modified: []

key-decisions:
  - "Placed detect_3nk() in types.py and re-exported from hashfs.py and __init__.py so zip_archive.py and dir_archive.py share 3nK detection in an acyclic DAG."
  - "Implemented HashFS v2 metadata parsing over metadata_count descriptor headers so multi-descriptor entries ([0x80, 0x06]) resolve via payload_idx while non-0x80/0x81 entries (e.g., Image/Sample blocks) are bounds-checked and safely skipped/reported without assuming 5 words."
  - "Used bounded zlib.decompressobj().decompress(..., expected_size + 1) for HashFS v2 entry/metadata tables with raw fallback only when raw size == expected_size, handling version.scs compressed small tables cleanly while mitigating zip-bomb headers."
  - "Normalized base/ paths unconditionally into canonical root VFS paths in VfsStack while preserving dlc_<id>/ under mount_scope='dlc:<id>' without unconditional flattening unless explicitly enabled via enabled_dlcs."

patterns-established:
  - "All archive readers open handles lazily per read unless entered as a context manager (`with open_archive(...)`), preventing Windows file-locking conflicts while enabling fast batched reads."
  - "Protected payloads (3nK\\x01, AEM!, unknown magic, encrypted ZIP flag 0x1, unsupported compression nibbles) emit structured ArchiveDiagnostic records cleanly without cracking or copying third-party blobs."

requirements-completed: [VFS-01]

actuals:
  tokens: 24376
  tasks: 3
  commits: 0  # Coordinator commits after Wave 2 verification

duration: 15min
completed: 2026-11-16
---

# Phase 1 Plan 02: Cross-Platform VFS Container Readers & VfsStack Summary

**Implemented clean-room pure-Python MIT CityHash64 1.0.3 (`k3=0xc949d7c7509e6557`, `b""->k2`), HashFS v1/v2 readers, ZIP/directory containers, detect-and-report protected container stubs, and multi-layer `VfsStack` overlay engine with `base/` normalization and empty `SiiNunit {}` stub shadowing.**

## Accomplishments
- **Task 1 (Tracer, Red -> Green):** Built `types.py`, `cityhash.py`, and `hashfs.py` (`HashFsV1Archive`, `HashFsV2Archive`, `detect_3nk`). Verified CityHash64 1.0.3 across every length bucket (`0`, `1..3`, `4..7`, `8..16`, `17..32`, `33..64`, `>64`), UTF-8 normalization, and decimal salt prefixing (`tests/test_vfs_cityhash.py`: 25 passed). Verified synthetic HashFS v1 (`*subdir`, zlib, salt), HashFS v2 compressed small tables (`version.scs` case), seeded prefix walking (`locale.scs` omitted root `""`) with visited-hash/path deduplication, bounds-checked skipping/reporting of non-`0x80`/`0x81` metadata kinds, unsupported compression nibble diagnostics, and `3nK\x01` diagnostics.
- **Task 2 (TDD, Red -> Green):** Built `zip_archive.py` (`ZipArchive` inspecting `flag_bits & 0x1` encrypted central-directory paths into metadata + `ArchiveDiagnostic` while raising `ProtectedPayloadError` on read, rejecting `..` ZIP paths), `dir_archive.py` (`DirectoryArchive` enforcing `Path.resolve().is_relative_to(root.resolve())` root containment), and extended `hashfs.py` with `ProtectedArchiveStub` and `open_archive()` dispatching directories, ZIP, HashFS v1/v2, `AEM!`, unknown/short magic, and corrupt headers cleanly (`tests/test_vfs_archives.py`: 9 passed).
- **Task 3 (TDD, Red -> Green):** Built `stack.py` (`is_empty_sii_stub`, `classify_mount_path`, `EffectiveVfsEntry`, `VfsLayer`, `VfsStack`) and exported the complete public VFS API in `src/ets2v2/vfs/__init__.py`. Verified priority-ordered overlay resolution across mixed containers, `base/` normalization preserving `raw_path`/`mount_scope="base"`, distinct `dlc_<id>/` (`"dlc:<id>"`) handling, empty `SiiNunit {}` shadowing, cross-platform Windows/Linux path canonicalization, and aggregated diagnostics (`tests/test_vfs_stack.py`: 16 passed).
- **Optional Read-Only Local Smoke Check:** Verified `HashFsV2Archive` and `VfsStack.from_paths` interactively against local ETS2 `1.62.3.3s` `version.scs` (`1` file), `def.scs` (`66,066` files, `68,371/68,371` walked paths matched CityHash64 1.0.3), and `locale.scs` (`521` files via seeded `"locale"` walk) with zero diagnostics. Committed test suites remain 100% CI-safe using synthetic/in-memory and `tmp_path` archives.

## Deviations from Plan
- None — plan executed as specified (commits and `STATE.md`/`ROADMAP.md`/`01-VALIDATION.md` updates deferred to Wave 2 coordinator per parallel execution rules).

## Known Stubs
- None (stub/placeholder scan across `src/ets2v2/vfs/*.py` returned zero matches).

## Verification
- `uv run pytest -p no:cacheprovider tests/test_cli_scaffold.py tests/test_vfs_cityhash.py tests/test_vfs_archives.py tests/test_vfs_stack.py -v`: `59 passed` (50 VFS tests + 9 scaffold tests)
- `uv run ruff check --no-cache src/ets2v2/vfs tests/test_vfs_*.py`: `All checks passed!`
- `uv run ruff format --check --no-cache src/ets2v2/vfs tests/test_vfs_*.py`: `10 files already formatted`
- `uv run basedpyright src/ets2v2/vfs tests/test_vfs_*.py`: `0 errors, 0 warnings, 0 notes`
- All 10 owned source/test files and `01-02-SUMMARY.md` verified UTF-8 without BOM and LF (`\n`) line endings.

## Self-Check: PASSED

---
*Phase: 01-vfs-1-62-baseline-extraction-structural-sii-engine*
*Completed: 2026-11-16*
