---
phase: 02-realism-registry-seasonal-core-builds-offline-validator-phase-a
status: SECURED
asvs_level: 2
block_threshold: medium
threats_total: 16
threats_closed: 16
threats_open: 0
audited: 2026-11-20
---

# Phase 2 Security Audit — `02-SECURITY.md`

**Verdict:** `SECURED` (`16/16` STRIDE threats closed, `0` open threats at or above `medium`)
**ASVS Level:** 2

## Threat Verification Register

| Threat ID | Category | Severity | Disposition | Evidence |
|-----------|----------|----------|-------------|----------|
| `T-02-01` | Tampering | medium | mitigate | `src/ets2v2/registry/models.py` (`ConfigDict(strict=True, frozen=True, extra="forbid")`, `0..200` speed bounds, canonical lane validator, regexes & monotonic `10_000..150_000` axle weights); JSON-mode `model_validate_json()` in `src/ets2v2/registry/loader.py`. |
| `T-02-02` | Tampering / Information Disclosure | medium | mitigate | Zero `.sii`/`.sui` files under `data/` (`SCS_UNDER_DATA=0`, `LAW_FILES=36`); enforced by `src/ets2v2/registry/loader.py`, `tests/test_baseline_contracts.py`, and `tests/test_registry_contracts.py`. |
| `T-02-03` | Tampering | medium | mitigate | `src/ets2v2/registry/loader.py` (`_validate_country_against_baseline` rejects `speed_unit` vs `imperial_units` mismatch, axle downgrades, and drifted lane classes); re-enforced post-synthesis in `src/ets2v2/validate/invariants.py`. |
| `T-02-04` | Tampering / Denial of Service | medium | mitigate | `src/ets2v2/registry/timezone.py` (`IANA_NUMERIC_ABBR_OVERRIDES` for Istanbul/Amman/Damascus, typed `ValueError` on unknown IANA zones, nullable `utcoffset()` narrowing, numeric `tzname()` override prior to 12-key `locales.json` `@@tz_*@@` whitelist); verified in `src/ets2v2/validate/invariants.py`. |
| `T-02-05` | Tampering | low | mitigate | `src/ets2v2/cli.py` (`_parse_iso_date_arg` strict `date.fromisoformat()` + canonical equality); `src/ets2v2/registry/snapshot.py` (`strict=True, frozen=True, extra="forbid"`, `schema_version: Literal[1] = 1`, zero wall-clock timestamps). |
| `T-02-06` | Tampering (SII Injection) | medium | mitigate | `src/ets2v2/package/synthesize.py` (`format_sii_string` rejects `\` and `\x00`, escapes control/quote chars; strict token/unit/float formatting; `_assert_hygiene` checks `validate_sii_hygiene(...) == []`); shared with `src/ets2v2/package/metadata.py`. |
| `T-02-07` | Tampering (Path Traversal / Unsafe Clean) | medium | mitigate | `src/ets2v2/package/builder.py` (`_validate_rel_path` + `_ensure_contained` strict `is_relative_to(resolved_root)`) enforced before `shutil.rmtree(workshop_dir)`, Workshop writes, local ZIP target, and `ZipInfo` entries. |
| `T-02-08` | Information Disclosure (Image Metadata Leakage) | low | mitigate | `src/ets2v2/package/icons.py` renders fresh RGB JPEG without EXIF or ICC profile; checked-in `assets/icons/{summer,winter}.jpg` verified for zero EXIF/ICC metadata in `tests/test_package_icons_metadata.py`. |
| `T-02-09` | Tampering (Zip-Slip / Backslash Path Spoofing) | high | mitigate | `src/ets2v2/validate/workshop.py` (`_inspect_raw_zip` checks raw `zipfile.ZipFile.infolist()` for `\x00`, `\`, leading `/`, drive prefix, and `..` as SCS `00003` before `ZipArchive` normalization); `DirectoryArchive` enforces root containment & rejects symlinks; `validate_sii_hygiene()` + `validate_string_path_hygiene()` enforced. |
| `T-02-10` | Denial of Service (Image Decompression Bomb / Oversized Payload) | medium | mitigate | `src/ets2v2/validate/workshop.py` checks `len(raw) > MAX_ICON_BYTES` (`1_048_576`) -> `00009` before `Image.open`, caps `Image.MAX_IMAGE_PIXELS = 4_000_000` with `finally:` restore, catches `Image.DecompressionBombError`, caps `description_file` at `1_048_576`, and `ZipArchive` bounds reads at 128 MiB. |
| `T-02-11` | Tampering (Obfuscated / Encrypted / Spoofed Payloads) | high | mitigate | `src/ets2v2/validate/workshop.py` rejects `3nK\x01` (`00004`), `SCS#`/`AEM!` (`00007`), encrypted ZIP `flag_bits & 0x41` (`00007`), unsupported ZIP compression (`00007`), ZIP-as-`.scs` (`00003`), and non-JPEG magic (`00007`); `invariants.py` enforces `ETS2V2-INV-*`; zero imports from `ets2v2.package` enforced via AST test. |
| `T-02-12` | Tampering / Elevation of Privilege (Workflow Expression Injection) | high | mitigate | `.github/workflows/phase-a-release.yml` types `force_run` as `boolean` (`default: false`), passes `FORCE_RUN`, `GH_TOKEN`, and `CHANGED_EDITIONS` strictly through `env:`, and keeps zero `${{ ... }}` expressions inside `run:` blocks (`tests/test_publish_workflow.py`). |
| `T-02-13` | Elevation of Privilege (Untrusted PR Token Abuse) | high | mitigate | `.github/workflows/phase-a-release.yml` triggers strictly on `schedule` (`0 6 * * 5`) and `workflow_dispatch` (zero `pull_request`/`pull_request_target`); `.github/workflows/ci.yml` remains strictly `contents: read`. |
| `T-02-14` | Information Disclosure (Steam Credential Exposure) | high | mitigate | Zero Steam credentials (`STEAM_USERNAME`, `STEAM_PASSWORD`, `STEAM_SHARED_SECRET`, `secrets.STEAM`) or `steamcmd` references across `.github/workflows/*` (`tests/test_publish_workflow.py`). |
| `T-02-15` | Tampering / Repudiation (Ledger Bypass or Unvalidated Release) | medium | mitigate | `src/ets2v2/publish/ledger.py` rejects symlinks/root escapes and hashes length-prefixed sorted frames with `package_version` normalized to `__CANONICAL__`; `src/ets2v2/publish/release.py` validates both Workshop dirs and local ZIPs and raises `ValueError` BEFORE mutating snapshots, changelogs, `state/published.json`, or `release_summary.json`; `phase-a-release.yml` gates `master` behind `release/phase-a-weekly` PR. |
| `T-02-SC` | Tampering (Supply Chain: PyPI & GitHub Actions) | high | mitigate | `tzdata==2026.6` (`Apache-2.0`) and `pillow==13.0.0` (`MIT-CMU`) audited `[OK]` in `02-RESEARCH.md`, locked with SHA-256 hashes in `uv.lock`, synced with `uv sync --locked`; workflows pin `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/upload-artifact@v4`, and built-in `gh` CLI + `git`. |

## Unregistered Flags
None.

## Non-Blocking Defense-in-Depth Notes (Informational)
1. `src/ets2v2/package/builder.py` invokes `load_law_registry()` rather than `validate_law_registry()`, relying on downstream `ets2v2 validate` / `ets2v2 publish release` to reject custom-registry baseline drift.
2. `.github/workflows/{ci,phase-a-release}.yml` pin GitHub Actions to major version tags (`@v4`, `@v5`) matching `T-02-SC`; full commit-SHA pinning can be adopted in Phase 3+ if desired.
