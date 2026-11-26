"""SCS SII/SUI encoding, line-ending normalization, and hygiene validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ets2_realism.sii.lexer import (
    SiiAttributeSpan,
    scan_sii_structure,
    unquote_sii_string,
)

_UNIT_SEGMENT_CHARS_RE = re.compile(r"^[a-z0-9_]+$")
_DOTDOT_PATH_RE = re.compile(r"(^|[\\/])\.\.([\\/]|$)")
_ASSET_EXT_RE = re.compile(
    r"\.(sii|sui|txt|jpg|jpeg|png|dds|mat|tobj|pmd|pmg|pmc|pma|ppd|font|ogg|soundref)$",
    re.IGNORECASE,
)
_PATH_ATTR_KEYS = frozenset(
    {
        "icon",
        "description_file",
        "font_face",
        "model_name",
        "path",
        "file",
        "material",
        "texture",
        "sound",
    }
)


class SiiEncodingError(ValueError):
    """Raised when SII/SUI bytes or text cannot be strictly encoded/decoded as UTF-8."""


@dataclass(frozen=True)
class SiiDiagnostic:
    """Typed hygiene or structural diagnostic for an SII/SUI file."""

    code: str
    message: str
    line: int = 1
    column: int = 1
    severity: Literal["error", "warning"] = "error"


def normalize_sii_bytes(raw: bytes) -> str:
    """Strictly decode UTF-8 (stripping UTF-8 BOM only) and normalize CR/CRLF to LF."""
    payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SiiEncodingError(f"Invalid UTF-8 byte sequence in SII/SUI payload: {exc}") from exc
    return decoded.replace("\r\n", "\n").replace("\r", "\n")


def serialize_sii_text(text: str) -> bytes:
    """Normalize text to LF without BOM and encode strictly as UTF-8 bytes."""
    cleaned = text[1:] if text.startswith("\ufeff") else text
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    try:
        return cleaned.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SiiEncodingError(f"Cannot encode SII/SUI text as UTF-8: {exc}") from exc


def validate_unit_name_segments(
    unit_name: str,
    *,
    line: int = 1,
    column: int = 1,
) -> list[SiiDiagnostic]:
    """Validate SCS ``[a-z0-9_]{1,12}`` dot-separated unit name segment constraints."""
    diagnostics: list[SiiDiagnostic] = []
    body = unit_name[1:] if unit_name.startswith(".") else unit_name
    if not body:
        diagnostics.append(
            SiiDiagnostic(
                code="unit_segment_invalid",
                message=f"Invalid empty unit name {unit_name!r}",
                line=line,
                column=column,
            )
        )
        return diagnostics

    for seg in body.split("."):
        if not seg or _UNIT_SEGMENT_CHARS_RE.fullmatch(seg) is None:
            diagnostics.append(
                SiiDiagnostic(
                    code="unit_segment_invalid",
                    message=(
                        f"Invalid unit segment {seg!r} in {unit_name!r}; "
                        "expected non-empty [a-z0-9_]{1,12}"
                    ),
                    line=line,
                    column=column,
                )
            )
        elif len(seg) > 12:
            diagnostics.append(
                SiiDiagnostic(
                    code="unit_segment_too_long",
                    message=(
                        f"Unit segment {seg!r} in {unit_name!r} exceeds 12 chars ({len(seg)})"
                    ),
                    line=line,
                    column=column,
                )
            )
    return diagnostics


def _has_disallowed_backslash(raw_inner: str, key: str | None) -> bool:
    """Detect Windows backslash separators while allowing valid text escapes in UI strings."""
    if "\\" not in raw_inner:
        return False
    if key is not None and key in _PATH_ATTR_KEYS:
        return True

    i = 0
    n = len(raw_inner)
    while i < n:
        if raw_inner[i] == "\\":
            if i + 1 >= n:
                return True
            nxt = raw_inner[i + 1]
            if nxt not in {'"', "\\", "n", "r", "t"}:
                return True
            i += 2
        else:
            i += 1

    if key is None:
        return (
            raw_inner.startswith("\\")
            or "/" in raw_inner
            or _ASSET_EXT_RE.search(raw_inner) is not None
        )
    return False


def validate_string_path_hygiene(
    raw_value: str,
    *,
    key: str | None = None,
    is_include: bool = False,
    line: int = 1,
    column: int = 1,
) -> list[SiiDiagnostic]:
    """Validate POSIX ``/`` separator and ``..`` traversal rules for paths and strings."""
    diagnostics: list[SiiDiagnostic] = []
    stripped = raw_value.strip()
    if len(stripped) < 2 or not (stripped.startswith('"') and stripped.endswith('"')):
        return diagnostics

    raw_inner = stripped[1:-1]
    unquoted, _ = unquote_sii_string(stripped)

    if is_include:
        if "\\" in raw_inner or "\\" in unquoted:
            diagnostics.append(
                SiiDiagnostic(
                    code="path_backslash",
                    message=f"Windows backslash not allowed in @include path {stripped}",
                    line=line,
                    column=column,
                )
            )
        if ".." in raw_inner or ".." in unquoted:
            diagnostics.append(
                SiiDiagnostic(
                    code="path_parent_traversal",
                    message=f"Parent traversal '..' not allowed in @include path {stripped}",
                    line=line,
                    column=column,
                )
            )
        return diagnostics

    if _has_disallowed_backslash(raw_inner, key):
        diagnostics.append(
            SiiDiagnostic(
                code="path_backslash",
                message=f"Windows backslash not allowed in resource path {stripped}",
                line=line,
                column=column,
            )
        )

    is_path_like = (
        "/" in raw_inner
        or "\\" in raw_inner
        or _ASSET_EXT_RE.search(raw_inner) is not None
        or (key is not None and key in _PATH_ATTR_KEYS)
    )
    if is_path_like and (
        _DOTDOT_PATH_RE.search(raw_inner) is not None
        or _DOTDOT_PATH_RE.search(unquoted) is not None
    ):
        diagnostics.append(
            SiiDiagnostic(
                code="path_parent_traversal",
                message=f"Parent traversal '..' not allowed in resource path {stripped}",
                line=line,
                column=column,
            )
        )

    return diagnostics


def _offset_to_line_col(text: str, pos: int) -> tuple[int, int]:
    """Return 1-based ``(line, column)`` for character offset ``pos`` in LF-normalized text."""
    line = text.count("\n", 0, pos) + 1
    line_start = text.rfind("\n", 0, pos) + 1
    return line, pos - line_start + 1


def _validate_attribute_hygiene(attr: SiiAttributeSpan, text: str) -> list[SiiDiagnostic]:
    line, column = _offset_to_line_col(text, attr.value_span.start)
    return validate_string_path_hygiene(
        attr.raw_value,
        key=attr.key,
        is_include=False,
        line=line,
        column=column,
    )


def validate_sii_hygiene(
    source: str | bytes,
    *,
    require_siinunit: bool = False,
) -> list[SiiDiagnostic]:
    """Run full SCS SII/SUI hygiene checks (encoding, LF, @include col-0, paths, units, braces)."""
    diagnostics: list[SiiDiagnostic] = []

    if isinstance(source, bytes):
        payload = source
        if source.startswith(b"\xef\xbb\xbf"):
            diagnostics.append(
                SiiDiagnostic(
                    code="utf8_bom",
                    message="UTF-8 BOM (0xEF 0xBB 0xBF) is disallowed in normalized SII/SUI",
                    line=1,
                    column=1,
                )
            )
            payload = source[3:]
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            diagnostics.append(
                SiiDiagnostic(
                    code="invalid_utf8",
                    message=f"Invalid UTF-8 byte sequence: {exc}",
                    line=1,
                    column=1,
                )
            )
            return diagnostics
    else:
        text = source
        if text.startswith("\ufeff"):
            diagnostics.append(
                SiiDiagnostic(
                    code="utf8_bom",
                    message="Unicode BOM U+FEFF is disallowed in normalized SII/SUI",
                    line=1,
                    column=1,
                )
            )
            text = text[1:]

    if "\r" in text:
        cr_idx = text.find("\r")
        cr_line = text[:cr_idx].count("\n") + 1
        diagnostics.append(
            SiiDiagnostic(
                code="non_lf_line_ending",
                message="CR/CRLF line endings must be normalized to LF ('\\n')",
                line=cr_line,
                column=1,
            )
        )
        text = text.replace("\r\n", "\n").replace("\r", "\n")

    scan = scan_sii_structure(text, require_siinunit=require_siinunit)
    for lex_diag in scan.diagnostics:
        diagnostics.append(
            SiiDiagnostic(
                code=lex_diag.code,
                message=lex_diag.message,
                line=lex_diag.line,
                column=lex_diag.column,
            )
        )

    for inc in scan.includes:
        if not inc.is_column_zero:
            diagnostics.append(
                SiiDiagnostic(
                    code="include_not_column_0",
                    message="@include directive must start at column 0 with no leading whitespace",
                    line=inc.line,
                    column=inc.column_0 + 1,
                )
            )
        diagnostics.extend(
            validate_string_path_hygiene(
                inc.raw_quoted,
                is_include=True,
                line=inc.line,
                column=inc.column_0 + 1,
            )
        )

    for unit in scan.units:
        diagnostics.extend(
            validate_unit_name_segments(
                unit.unit_name,
                line=unit.unit_name_line,
                column=unit.unit_name_column,
            )
        )
        for attr in unit.attributes:
            diagnostics.extend(_validate_attribute_hygiene(attr, text))

    for attr in scan.root_attributes:
        diagnostics.extend(_validate_attribute_hygiene(attr, text))

    return diagnostics
