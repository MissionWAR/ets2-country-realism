"""Include-aware VfsStack country & speed-limits scanner (MAP-03, D-13, D-16)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.merge.promods_fuel import PM_FUEL_MODULES, ProModsFuelModuleName
from ets2v2.sii.country import CountryDataModel, parse_country_data, parse_country_includes
from ets2v2.sii.document import SiiDocument
from ets2v2.vfs.stack import VfsStack
from ets2v2.vfs.types import (
    ProtectedPayloadError,
    UnsupportedCompressionError,
    detect_3nk,
    normalize_vfs_path,
)

_COUNTRY_REG_SII_RE: Final[re.Pattern[str]] = re.compile(
    r"^def/country(?:\.[^/]+)?\.sii$",
    re.IGNORECASE,
)
_COUNTRY_FRAG_RE: Final[re.Pattern[str]] = re.compile(
    r"^def/country/([a-z0-9_]+)\.(sui|sii)$",
    re.IGNORECASE,
)
_PROMODS_FUEL_LOCALE_RE: Final[re.Pattern[str]] = re.compile(
    r"^locale/[^/]+/local_module\.(pm_fuel|pm_me_fuel|pm_tgs_fuel)\.sii$",
    re.IGNORECASE,
)
_PM_MODULE_LOOKUP: Final[dict[str, ProModsFuelModuleName]] = {
    name: name for name in PM_FUEL_MODULES
}


class SuppressedRegistrationStub(BaseModel):
    """Record of a ``def/country*.sii`` file suppressed by a higher empty ``SiiNunit {}`` stub."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    registration_path: str = Field(min_length=1)
    layer_name: str = Field(min_length=1)
    priority: int = Field(ge=0)


class ScanDiagnostic(BaseModel):
    """Non-fatal diagnostic emitted while traversing a combo ``VfsStack``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    layer_name: str | None = None


@dataclass(frozen=True, slots=True)
class ScannedMapCountry:
    """Resolved active country fragment discovered via ``VfsStack`` ``def/country*.sii`` graph."""

    slug: str
    fragment_path: str
    is_sii_fragment: bool
    has_siinunit_envelope: bool
    winning_layer: str
    winning_priority: int
    registration_files: list[str]
    country_data: CountryDataModel
    raw_bytes: bytes
    speed_limits_path: str | None = None
    speed_limits_layer: str | None = None
    speed_limits_raw: bytes | None = None


@dataclass
class ComboScanResult:
    """Complete country graph, stub suppression, diagnostic, and ``pm*_fuel`` scan output."""

    countries: list[ScannedMapCountry] = field(default_factory=list)
    suppressed_registration_files: list[SuppressedRegistrationStub] = field(default_factory=list)
    diagnostics: list[ScanDiagnostic] = field(default_factory=list)
    detected_promods_fuel_modules: list[ProModsFuelModuleName] = field(default_factory=list)


def _decode_third_party_sii(raw: bytes) -> str:
    """Decode third-party SII/SUI bytes via UTF-8 first, falling back to Windows-1252."""
    payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _resolve_include_target(source_path: str, raw_include: str) -> str:
    """Resolve an ``@include`` path relative to ``source_path`` with traversal validation."""
    cleaned = raw_include.strip()
    if not cleaned:
        raise ValueError(f"Empty @include target in {source_path!r}")
    if cleaned.startswith("/"):
        return normalize_vfs_path(cleaned)
    norm_inc = normalize_vfs_path(cleaned)
    if norm_inc.startswith("def/"):
        return norm_inc
    parent_dir = source_path.rsplit("/", 1)[0] if "/" in source_path else ""
    if parent_dir:
        return normalize_vfs_path(f"{parent_dir}/{norm_inc}")
    return norm_inc


def _detect_promods_fuel_modules(stack: VfsStack) -> list[ProModsFuelModuleName]:
    """Detect active ``local_module.{pm_fuel,pm_me_fuel,pm_tgs_fuel}.sii`` modules in stack."""
    found: set[ProModsFuelModuleName] = set()
    for rel_path in stack.list_paths("locale"):
        match = _PROMODS_FUEL_LOCALE_RE.fullmatch(rel_path)
        if match is None:
            continue
        mod_key = match.group(1).lower()
        mod_name = _PM_MODULE_LOOKUP.get(mod_key)
        if mod_name is None or mod_name in found:
            continue
        entry = stack.resolve(rel_path)
        if entry is None or entry.is_empty_stub or entry.meta.encrypted:
            continue
        found.add(mod_name)
    return sorted(found)


def scan_active_countries(stack: VfsStack) -> ComboScanResult:
    """Walk ``VfsStack`` ``def/country*.sii`` ``@include`` graphs into active map countries."""
    reg_paths = sorted(
        p for p in stack.list_paths("def") if _COUNTRY_REG_SII_RE.fullmatch(p) is not None
    )

    suppressed_stubs: list[SuppressedRegistrationStub] = []
    diagnostics: list[ScanDiagnostic] = []
    fragment_regs: dict[str, set[str]] = {}
    recorded_diag_keys: set[tuple[str, str, str]] = set()

    def _add_diag(path: str, kind: str, detail: str, layer_name: str | None = None) -> None:
        key = (path, kind, detail)
        if key in recorded_diag_keys:
            return
        recorded_diag_keys.add(key)
        diagnostics.append(
            ScanDiagnostic(path=path, kind=kind, detail=detail, layer_name=layer_name)
        )

    def _walk_include_source(
        origin_reg: str,
        source_path: str,
        source_layer: str,
        raw_bytes: bytes,
        active_chain: set[str],
        visited_wrappers: set[str],
    ) -> None:
        if detect_3nk(raw_bytes):
            _add_diag(
                source_path,
                "three_nk_obfuscated",
                "3nK\\x01 obfuscated SII/SUI file skipped; decryption is disabled.",
                source_layer,
            )
            return

        decoded = _decode_third_party_sii(raw_bytes)
        try:
            includes = parse_country_includes(decoded)
        except ValueError as exc:
            _add_diag(source_path, "invalid_include_path", str(exc), source_layer)
            return

        for raw_inc in includes:
            try:
                target = _resolve_include_target(source_path, raw_inc)
            except ValueError as exc:
                _add_diag(source_path, "invalid_include_path", str(exc), source_layer)
                continue

            if target in active_chain:
                _add_diag(
                    target,
                    "include_cycle",
                    f"Circular @include detected while traversing from {source_path!r}.",
                    source_layer,
                )
                continue

            entry = stack.resolve(target)
            if entry is None:
                _add_diag(
                    target,
                    "missing_include_target",
                    f"Included target {target!r} referenced by {source_path!r} not found in VFS.",
                    source_layer,
                )
                continue
            if entry.is_empty_stub:
                continue

            if _COUNTRY_FRAG_RE.fullmatch(target) is not None:
                fragment_regs.setdefault(target, set()).add(origin_reg)
                # Inspect for nested @includes only if the fragment itself lacks country_data
                # (e.g., wrapper .sii under def/country/ or cyclic test fixture).
                if target in visited_wrappers:
                    continue
                try:
                    frag_raw = stack.read_bytes(target)
                except ProtectedPayloadError as exc:
                    _add_diag(target, "protected_payload", str(exc), entry.layer_name)
                    continue
                except UnsupportedCompressionError as exc:
                    _add_diag(target, "unsupported_compression", str(exc), entry.layer_name)
                    continue
                except (FileNotFoundError, OSError, ValueError) as exc:
                    _add_diag(target, "read_error", str(exc), entry.layer_name)
                    continue

                if detect_3nk(frag_raw):
                    _add_diag(
                        target,
                        "three_nk_obfuscated",
                        "3nK\\x01 obfuscated country fragment skipped; decryption is disabled.",
                        entry.layer_name,
                    )
                    continue

                frag_text = _decode_third_party_sii(frag_raw)
                frag_doc = SiiDocument.parse(frag_text)
                if frag_doc.get_unit(class_name="country_data") is None and frag_doc.includes:
                    visited_wrappers.add(target)
                    active_chain.add(target)
                    try:
                        _walk_include_source(
                            origin_reg,
                            target,
                            entry.layer_name,
                            frag_raw,
                            active_chain,
                            visited_wrappers,
                        )
                    finally:
                        active_chain.discard(target)
                continue

            if target in visited_wrappers:
                continue
            visited_wrappers.add(target)

            try:
                nested_raw = stack.read_bytes(target)
            except ProtectedPayloadError as exc:
                _add_diag(target, "protected_payload", str(exc), entry.layer_name)
                continue
            except UnsupportedCompressionError as exc:
                _add_diag(target, "unsupported_compression", str(exc), entry.layer_name)
                continue
            except (FileNotFoundError, OSError, ValueError) as exc:
                _add_diag(target, "read_error", str(exc), entry.layer_name)
                continue

            active_chain.add(target)
            try:
                _walk_include_source(
                    origin_reg,
                    target,
                    entry.layer_name,
                    nested_raw,
                    active_chain,
                    visited_wrappers,
                )
            finally:
                active_chain.discard(target)

    for reg_path in reg_paths:
        reg_entry = stack.resolve(reg_path)
        if reg_entry is None:
            continue
        if reg_entry.is_empty_stub:
            suppressed_stubs.append(
                SuppressedRegistrationStub(
                    registration_path=reg_path,
                    layer_name=reg_entry.layer_name,
                    priority=reg_entry.priority,
                )
            )
            continue
        try:
            reg_raw = stack.read_bytes(reg_path)
        except ProtectedPayloadError as exc:
            _add_diag(reg_path, "protected_payload", str(exc), reg_entry.layer_name)
            continue
        except UnsupportedCompressionError as exc:
            _add_diag(reg_path, "unsupported_compression", str(exc), reg_entry.layer_name)
            continue
        except (FileNotFoundError, OSError, ValueError) as exc:
            _add_diag(reg_path, "read_error", str(exc), reg_entry.layer_name)
            continue

        _walk_include_source(
            reg_path,
            reg_path,
            reg_entry.layer_name,
            reg_raw,
            active_chain={reg_path},
            visited_wrappers={reg_path},
        )

    countries: list[ScannedMapCountry] = []
    for frag_path in sorted(fragment_regs):
        match = _COUNTRY_FRAG_RE.fullmatch(frag_path)
        if match is None:
            continue
        slug = match.group(1).lower()
        is_sii_fragment = match.group(2).lower() == "sii"

        frag_entry = stack.resolve(frag_path)
        if frag_entry is None or frag_entry.is_empty_stub:
            continue

        try:
            raw_bytes = stack.read_bytes(frag_path)
        except ProtectedPayloadError as exc:
            _add_diag(frag_path, "protected_payload", str(exc), frag_entry.layer_name)
            continue
        except UnsupportedCompressionError as exc:
            _add_diag(frag_path, "unsupported_compression", str(exc), frag_entry.layer_name)
            continue
        except (FileNotFoundError, OSError, ValueError) as exc:
            _add_diag(frag_path, "read_error", str(exc), frag_entry.layer_name)
            continue

        if detect_3nk(raw_bytes):
            _add_diag(
                frag_path,
                "three_nk_obfuscated",
                "3nK\\x01 obfuscated country fragment skipped; decryption is disabled.",
                frag_entry.layer_name,
            )
            continue

        decoded = _decode_third_party_sii(raw_bytes)
        doc = SiiDocument.parse(decoded)
        if doc.get_unit(class_name="country_data") is None:
            # Skip wrapper-only files under def/country/ that carried no country_data unit
            continue
        try:
            country_data = parse_country_data(decoded)
        except ValueError as exc:
            _add_diag(frag_path, "parse_error", str(exc), frag_entry.layer_name)
            continue

        spd_path: str | None = None
        spd_layer: str | None = None
        spd_raw: bytes | None = None
        candidate_spd = f"def/country/{slug}/speed_limits.sii"
        spd_entry = stack.resolve(candidate_spd)
        if spd_entry is not None and not spd_entry.is_empty_stub:
            try:
                raw_candidate = stack.read_bytes(candidate_spd)
            except ProtectedPayloadError as exc:
                _add_diag(candidate_spd, "protected_payload", str(exc), spd_entry.layer_name)
            except UnsupportedCompressionError as exc:
                _add_diag(candidate_spd, "unsupported_compression", str(exc), spd_entry.layer_name)
            except (FileNotFoundError, OSError, ValueError) as exc:
                _add_diag(candidate_spd, "read_error", str(exc), spd_entry.layer_name)
            else:
                if detect_3nk(raw_candidate):
                    _add_diag(
                        candidate_spd,
                        "three_nk_obfuscated",
                        "3nK\\x01 obfuscated speed_limits.sii skipped; decryption is disabled.",
                        spd_entry.layer_name,
                    )
                else:
                    spd_path = candidate_spd
                    spd_layer = spd_entry.layer_name
                    spd_raw = raw_candidate

        countries.append(
            ScannedMapCountry(
                slug=slug,
                fragment_path=frag_path,
                is_sii_fragment=is_sii_fragment,
                has_siinunit_envelope=doc.has_siinunit,
                winning_layer=frag_entry.layer_name,
                winning_priority=frag_entry.priority,
                registration_files=sorted(fragment_regs[frag_path]),
                country_data=country_data,
                raw_bytes=raw_bytes,
                speed_limits_path=spd_path,
                speed_limits_layer=spd_layer,
                speed_limits_raw=spd_raw,
            )
        )

    countries.sort(key=lambda item: (item.slug, item.fragment_path))
    detected_pm_modules = _detect_promods_fuel_modules(stack)

    return ComboScanResult(
        countries=countries,
        suppressed_registration_files=suppressed_stubs,
        diagnostics=diagnostics,
        detected_promods_fuel_modules=detected_pm_modules,
    )


__all__ = [
    "ComboScanResult",
    "ScanDiagnostic",
    "ScannedMapCountry",
    "SuppressedRegistrationStub",
    "scan_active_countries",
]
