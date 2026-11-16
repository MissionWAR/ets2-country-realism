"""String- and comment-aware structural scanner for SCS SII/SUI files."""

from __future__ import annotations

import re
import struct
from bisect import bisect_right
from dataclasses import dataclass

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_HEX_FLOAT_RE = re.compile(r"^&([0-9a-fA-F]{8})$")
_ARRAY_SUFFIX_RE = re.compile(r"\[([0-9]*)\]")


@dataclass(frozen=True)
class SiiSpan:
    """Half-open character span ``[start, end)`` within a normalized SII string."""

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start

    def text_in(self, source: str) -> str:
        """Return the substring sliced by this span from ``source``."""
        return source[self.start : self.end]


@dataclass(frozen=True)
class SiiLexDiagnostic:
    """Structural diagnostic emitted during linear SII/SUI scanning."""

    code: str
    message: str
    line: int
    column: int


@dataclass(frozen=True)
class SiiIncludeSpan:
    """Parsed ``@include`` directive and its structural placement metadata."""

    path: str
    raw_quoted: str
    span: SiiSpan
    line_span: SiiSpan
    line: int
    column_0: int
    is_column_zero: bool


@dataclass(frozen=True)
class SiiAttributeSpan:
    """Parsed SII attribute entry with exact spans for surgical in-place edits."""

    key: str
    raw_value: str
    is_append: bool
    index: int | None
    span: SiiSpan
    line_span: SiiSpan
    key_span: SiiSpan
    value_span: SiiSpan
    indent: str
    inline_comment: str | None
    comment_span: SiiSpan | None
    line: int


@dataclass(frozen=True)
class SiiUnitBlock:
    """Parsed SII unit definition block ``class_name : unit_name { ... }``."""

    index: int
    class_name: str
    unit_name: str
    span: SiiSpan
    header_span: SiiSpan
    unit_name_span: SiiSpan
    open_brace_pos: int
    close_brace_pos: int
    indent: str
    header_indent: str
    line: int
    unit_name_line: int
    unit_name_column: int
    attributes: tuple[SiiAttributeSpan, ...]
    includes: tuple[SiiIncludeSpan, ...]

    def get_scalar(self, key: str) -> SiiAttributeSpan | None:
        """Return the first non-array attribute matching ``key``, if present."""
        for attr in self.attributes:
            if attr.key == key and not attr.is_append and attr.index is None:
                return attr
        return None

    def get_attributes(self, key: str) -> list[SiiAttributeSpan]:
        """Return all attributes matching ``key`` in document order."""
        return [attr for attr in self.attributes if attr.key == key]


@dataclass(frozen=True)
class SiiScanResult:
    """Result of a single-pass linear structural scan over SII/SUI text."""

    has_siinunit: bool
    siinunit_span: SiiSpan | None
    units: tuple[SiiUnitBlock, ...]
    includes: tuple[SiiIncludeSpan, ...]
    root_attributes: tuple[SiiAttributeSpan, ...]
    diagnostics: tuple[SiiLexDiagnostic, ...]


def parse_sii_float(raw: str) -> float:
    """Parse a decimal float or SCS big-endian IEEE754 ``&xxxxxxxx`` hex float."""
    token = raw.strip()
    if not token:
        raise ValueError("Empty SII float literal")

    hex_match = _HEX_FLOAT_RE.match(token)
    if hex_match is not None:
        raw_bytes = bytes.fromhex(hex_match.group(1))
        value: float = struct.unpack(">f", raw_bytes)[0]
        return value

    if token.startswith("&"):
        raise ValueError(f"Malformed SII hex float literal: {raw!r}")

    return float(token)


def unquote_sii_string(raw: str) -> tuple[str, bool]:
    """Strip outer quotes and decode basic escapes if ``raw`` is an SII quoted string."""
    stripped = raw.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        inner = stripped[1:-1]
        out: list[str] = []
        i = 0
        n = len(inner)
        while i < n:
            ch = inner[i]
            if ch == "\\" and i + 1 < n:
                nxt = inner[i + 1]
                if nxt == '"':
                    out.append('"')
                elif nxt == "\\":
                    out.append("\\")
                elif nxt == "n":
                    out.append("\n")
                elif nxt == "r":
                    out.append("\r")
                elif nxt == "t":
                    out.append("\t")
                else:
                    out.append("\\" + nxt)
                i += 2
            else:
                out.append(ch)
                i += 1
        return "".join(out), True
    return stripped, False


def _build_line_starts(text: str) -> list[int]:
    starts = [0]
    idx = text.find("\n")
    while idx != -1:
        starts.append(idx + 1)
        idx = text.find("\n", idx + 1)
    return starts


def _pos_to_line_col(line_starts: list[int], pos: int) -> tuple[int, int]:
    """Return 1-based line and 0-based column index for ``pos``."""
    line_idx = bisect_right(line_starts, pos) - 1
    return line_idx + 1, pos - line_starts[line_idx]


def _line_bounds(text: str, line_starts: list[int], line: int) -> tuple[int, int]:
    """Return ``[start, end)`` of ``line`` (1-based) excluding trailing ``\\n``/``\\r``."""
    start = line_starts[line - 1]
    end = line_starts[line] - 1 if line < len(line_starts) else len(text)
    if end > start and text[end - 1] == "\r":
        end -= 1
    return start, end


def _scan_quoted_string(text: str, start: int) -> tuple[int, str, bool]:
    """Scan a double-quoted SII string starting at ``start``.

    Returns ``(end_pos_exclusive, unquoted_value, terminated)``.
    """
    n = len(text)
    i = start + 1
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2 if i + 1 < n else 1
        elif ch == '"':
            end = i + 1
            unquoted, _ = unquote_sii_string(text[start:end])
            return end, unquoted, True
        else:
            i += 1
    unquoted, _ = unquote_sii_string(text[start:n] + '"')
    return n, unquoted, False


def _skip_ws_and_comments(
    text: str,
    pos: int,
    line_starts: list[int],
    diagnostics: list[SiiLexDiagnostic],
) -> int:
    n = len(text)
    while pos < n:
        ch = text[pos]
        if ch in " \t\n\r":
            pos += 1
        elif ch == "#":
            nl = text.find("\n", pos)
            pos = n if nl == -1 else nl + 1
        elif text.startswith("//", pos):
            nl = text.find("\n", pos + 2)
            pos = n if nl == -1 else nl + 1
        elif text.startswith("/*", pos):
            end = text.find("*/", pos + 2)
            if end == -1:
                line, col0 = _pos_to_line_col(line_starts, pos)
                diagnostics.append(
                    SiiLexDiagnostic(
                        code="unterminated_comment",
                        message="Unterminated '/*' block comment",
                        line=line,
                        column=col0 + 1,
                    )
                )
                return n
            pos = end + 2
        else:
            break
    return pos


def _scan_rhs_value(
    text: str,
    val_start: int,
    line_starts: list[int],
    diagnostics: list[SiiLexDiagnostic],
) -> tuple[int, int]:
    """Scan an attribute RHS value or unit name starting at ``val_start``.

    Returns ``(last_non_ws_pos, stop_pos)``.
    """
    n = len(text)
    i = val_start
    last_non_ws = val_start
    paren_depth = 0
    while i < n:
        ch = text[i]
        if ch == '"':
            str_end, _, terminated = _scan_quoted_string(text, i)
            if not terminated:
                line, col0 = _pos_to_line_col(line_starts, i)
                diagnostics.append(
                    SiiLexDiagnostic(
                        code="unterminated_string",
                        message="Unterminated string literal",
                        line=line,
                        column=col0 + 1,
                    )
                )
            last_non_ws = str_end
            i = str_end
        elif ch == "(":
            paren_depth += 1
            i += 1
            last_non_ws = i
        elif ch == ")":
            if paren_depth > 0:
                paren_depth -= 1
            i += 1
            last_non_ws = i
        elif (
            (ch in "{}\n\r" and paren_depth == 0)
            or ch == "#"
            or text.startswith("//", i)
            or text.startswith("/*", i)
        ):
            break
        elif ch in " \t\n\r":
            i += 1
        else:
            i += 1
            last_non_ws = i
    return last_non_ws, i


def _consume_inline_comment(
    text: str,
    pos: int,
    line_starts: list[int],
    diagnostics: list[SiiLexDiagnostic],
) -> tuple[str | None, SiiSpan | None, int]:
    """Consume an inline comment immediately at ``pos`` if present."""
    n = len(text)
    if pos >= n:
        return None, None, pos
    if text[pos] == "#" or text.startswith("//", pos):
        line, _ = _pos_to_line_col(line_starts, pos)
        _, line_end = _line_bounds(text, line_starts, line)
        comment_end = max(pos, line_end)
        return text[pos:comment_end], SiiSpan(pos, comment_end), comment_end
    if text.startswith("/*", pos):
        end = text.find("*/", pos + 2)
        if end == -1:
            line, col0 = _pos_to_line_col(line_starts, pos)
            diagnostics.append(
                SiiLexDiagnostic(
                    code="unterminated_comment",
                    message="Unterminated '/*' block comment",
                    line=line,
                    column=col0 + 1,
                )
            )
            return text[pos:n], SiiSpan(pos, n), n
        comment_end = end + 2
        return text[pos:comment_end], SiiSpan(pos, comment_end), comment_end
    return None, None, pos


@dataclass
class _OpenUnit:
    index: int
    class_name: str
    unit_name: str
    start: int
    header_end: int
    unit_name_span: SiiSpan
    open_brace_pos: int
    header_indent: str
    line: int
    unit_name_line: int
    unit_name_column: int
    brace_depth: int
    attributes: list[SiiAttributeSpan]
    includes: list[SiiIncludeSpan]


def _close_open_unit(
    text: str,
    open_unit: _OpenUnit,
    close_brace_pos: int,
    file_default_indent: str,
) -> SiiUnitBlock:
    indent = file_default_indent
    for attr in open_unit.attributes:
        if attr.indent and set(attr.indent) <= {" ", "\t"}:
            indent = attr.indent
            break
        if attr.span.start == attr.line_span.start:
            indent = ""
            break
    else:
        if open_unit.attributes:
            indent = open_unit.attributes[0].indent
        elif open_unit.header_indent:
            indent = open_unit.header_indent + "\t"

    return SiiUnitBlock(
        index=open_unit.index,
        class_name=open_unit.class_name,
        unit_name=open_unit.unit_name,
        span=SiiSpan(open_unit.start, close_brace_pos + 1),
        header_span=SiiSpan(open_unit.start, open_unit.header_end),
        unit_name_span=open_unit.unit_name_span,
        open_brace_pos=open_unit.open_brace_pos,
        close_brace_pos=close_brace_pos,
        indent=indent,
        header_indent=open_unit.header_indent,
        line=open_unit.line,
        unit_name_line=open_unit.unit_name_line,
        unit_name_column=open_unit.unit_name_column,
        attributes=tuple(open_unit.attributes),
        includes=tuple(open_unit.includes),
    )


def _detect_file_default_indent(text: str) -> str:
    """Detect whether space indentation is consistently used; otherwise tab."""
    for line in text.splitlines():
        if line.startswith("    "):
            return "    "
        if line.startswith("\t"):
            return "\t"
    return "\t"


def scan_sii_structure(source: str, *, require_siinunit: bool = False) -> SiiScanResult:
    """Perform a single-pass O(n) structural scan of normalized SII/SUI text."""
    n = len(source)
    line_starts = _build_line_starts(source)
    diagnostics: list[SiiLexDiagnostic] = []
    units: list[SiiUnitBlock] = []
    includes: list[SiiIncludeSpan] = []
    root_attributes: list[SiiAttributeSpan] = []

    file_default_indent = _detect_file_default_indent(source)
    has_siinunit = False
    siinunit_start: int | None = None
    siinunit_span: SiiSpan | None = None
    siinunit_open_depth: int | None = None
    brace_depth = 0
    active_unit: _OpenUnit | None = None

    pos = 0
    while pos < n:
        pos = _skip_ws_and_comments(source, pos, line_starts, diagnostics)
        if pos >= n:
            break

        ch = source[pos]
        if ch == "}":
            if brace_depth == 0:
                line, col0 = _pos_to_line_col(line_starts, pos)
                diagnostics.append(
                    SiiLexDiagnostic(
                        code="unbalanced_brace",
                        message="Unexpected closing brace '}'",
                        line=line,
                        column=col0 + 1,
                    )
                )
                pos += 1
            else:
                if active_unit is not None and brace_depth == active_unit.brace_depth:
                    units.append(_close_open_unit(source, active_unit, pos, file_default_indent))
                    active_unit = None
                elif siinunit_open_depth is not None and brace_depth == siinunit_open_depth:
                    if siinunit_start is not None:
                        siinunit_span = SiiSpan(siinunit_start, pos + 1)
                    siinunit_open_depth = None
                brace_depth -= 1
                pos += 1
            continue

        if ch == "{":
            line, col0 = _pos_to_line_col(line_starts, pos)
            diagnostics.append(
                SiiLexDiagnostic(
                    code="unbalanced_brace",
                    message="Unexpected opening brace '{' without header",
                    line=line,
                    column=col0 + 1,
                )
            )
            brace_depth += 1
            pos += 1
            continue

        if source.startswith("@include", pos) and (pos + 8 == n or source[pos + 8] in ' \t"\r\n'):
            line, col0 = _pos_to_line_col(line_starts, pos)
            l_start, l_end = _line_bounds(source, line_starts, line)
            cur = pos + 8
            while cur < n and source[cur] in " \t":
                cur += 1
            if cur < n and source[cur] == '"':
                str_end, path_val, terminated = _scan_quoted_string(source, cur)
                if not terminated:
                    q_line, q_col0 = _pos_to_line_col(line_starts, cur)
                    diagnostics.append(
                        SiiLexDiagnostic(
                            code="unterminated_string",
                            message="Unterminated @include string path",
                            line=q_line,
                            column=q_col0 + 1,
                        )
                    )
                inc = SiiIncludeSpan(
                    path=path_val,
                    raw_quoted=source[cur:str_end],
                    span=SiiSpan(pos, str_end),
                    line_span=SiiSpan(l_start, l_end),
                    line=line,
                    column_0=col0,
                    is_column_zero=(col0 == 0),
                )
                includes.append(inc)
                if active_unit is not None:
                    active_unit.includes.append(inc)
                pos = str_end
            else:
                diagnostics.append(
                    SiiLexDiagnostic(
                        code="malformed_include",
                        message="Expected quoted path after @include",
                        line=line,
                        column=col0 + 1,
                    )
                )
                pos = max(cur, l_end)
            continue

        if source.startswith("SiiNunit", pos) and (pos + 8 == n or source[pos + 8] in " \t\r\n{/#"):
            after_kw = _skip_ws_and_comments(source, pos + 8, line_starts, diagnostics)
            if after_kw < n and source[after_kw] == "{":
                has_siinunit = True
                siinunit_start = pos
                brace_depth += 1
                siinunit_open_depth = brace_depth
                pos = after_kw + 1
                continue

        ident_match = _IDENT_RE.match(source, pos)
        if ident_match is None:
            line, col0 = _pos_to_line_col(line_starts, pos)
            diagnostics.append(
                SiiLexDiagnostic(
                    code="unexpected_token",
                    message=f"Unexpected character {source[pos]!r}",
                    line=line,
                    column=col0 + 1,
                )
            )
            _, l_end = _line_bounds(source, line_starts, line)
            pos = max(pos + 1, l_end)
            continue

        key_start = pos
        key_name = ident_match.group(0)
        cur = ident_match.end()
        while cur < n and source[cur] in " \t":
            cur += 1

        is_append = False
        array_index: int | None = None
        has_brackets = False
        suffix_match = _ARRAY_SUFFIX_RE.match(source, cur)
        if suffix_match is not None:
            has_brackets = True
            idx_text = suffix_match.group(1)
            if idx_text == "":
                is_append = True
            else:
                array_index = int(idx_text)
            cur = suffix_match.end()
            while cur < n and source[cur] in " \t":
                cur += 1

        if cur >= n or source[cur] != ":":
            line, col0 = _pos_to_line_col(line_starts, key_start)
            diagnostics.append(
                SiiLexDiagnostic(
                    code="syntax_error",
                    message=f"Expected ':' after identifier {key_name!r}",
                    line=line,
                    column=col0 + 1,
                )
            )
            _, l_end = _line_bounds(source, line_starts, line)
            pos = cur if cur < n and source[cur] in "{}" else max(cur + 1, l_end)
            continue

        key_span = SiiSpan(key_start, cur)
        colon_pos = cur
        val_start = colon_pos + 1
        while val_start < n and source[val_start] in " \t":
            val_start += 1

        last_non_ws, rhs_stop = _scan_rhs_value(source, val_start, line_starts, diagnostics)
        value_span = SiiSpan(val_start, last_non_ws)
        raw_value = value_span.text_in(source)

        # Look ahead past trailing whitespace/comments to detect unit block '{'.
        after_rhs = _skip_ws_and_comments(source, rhs_stop, line_starts, diagnostics)
        if not has_brackets and active_unit is None and after_rhs < n and source[after_rhs] == "{":
            line, col0 = _pos_to_line_col(line_starts, key_start)
            l_start, _ = _line_bounds(source, line_starts, line)
            header_indent = source[l_start:key_start]
            if not set(header_indent) <= {" ", "\t"}:
                header_indent = ""
            u_line, u_col0 = _pos_to_line_col(line_starts, val_start)
            brace_depth += 1
            active_unit = _OpenUnit(
                index=len(units),
                class_name=key_name,
                unit_name=raw_value,
                start=key_start,
                header_end=after_rhs + 1,
                unit_name_span=value_span,
                open_brace_pos=after_rhs,
                header_indent=header_indent,
                line=line,
                unit_name_line=u_line,
                unit_name_column=u_col0 + 1,
                brace_depth=brace_depth,
                attributes=[],
                includes=[],
            )
            pos = after_rhs + 1
            continue

        inline_comment, comment_span, end_after_comment = _consume_inline_comment(
            source, rhs_stop, line_starts, diagnostics
        )
        attr_line, _ = _pos_to_line_col(line_starts, key_start)
        l_start, l_end = _line_bounds(source, line_starts, attr_line)
        prefix = source[l_start:key_start]
        indent = prefix if set(prefix) <= {" ", "\t"} else ""

        attr_end = max(last_non_ws, end_after_comment)
        if l_end < attr_end and last_non_ws > l_end:
            # Multi-line tuple value spanned beyond attr_line.
            end_line, _ = _pos_to_line_col(line_starts, max(0, attr_end - 1))
            _, attr_line_end = _line_bounds(source, line_starts, end_line)
            line_span = SiiSpan(l_start, max(attr_end, attr_line_end))
        else:
            line_span = SiiSpan(l_start, l_end)

        attr = SiiAttributeSpan(
            key=key_name,
            raw_value=raw_value,
            is_append=is_append,
            index=array_index,
            span=SiiSpan(key_start, attr_end),
            line_span=line_span,
            key_span=key_span,
            value_span=value_span,
            indent=indent,
            inline_comment=inline_comment,
            comment_span=comment_span,
            line=attr_line,
        )
        if active_unit is not None:
            active_unit.attributes.append(attr)
        else:
            root_attributes.append(attr)

        pos = max(rhs_stop, end_after_comment)

    if active_unit is not None:
        units.append(_close_open_unit(source, active_unit, n, file_default_indent))
        active_unit = None

    if brace_depth > 0:
        line, col0 = _pos_to_line_col(line_starts, max(0, n - 1))
        diagnostics.append(
            SiiLexDiagnostic(
                code="unbalanced_brace",
                message=f"Unclosed '{{' brace ({brace_depth} unclosed)",
                line=line,
                column=col0 + 1,
            )
        )

    if require_siinunit and not has_siinunit:
        diagnostics.append(
            SiiLexDiagnostic(
                code="missing_siinunit_header",
                message="Missing required 'SiiNunit { ... }' wrapper",
                line=1,
                column=1,
            )
        )

    return SiiScanResult(
        has_siinunit=has_siinunit,
        siinunit_span=siinunit_span,
        units=tuple(units),
        includes=tuple(includes),
        root_attributes=tuple(root_attributes),
        diagnostics=tuple(diagnostics),
    )
