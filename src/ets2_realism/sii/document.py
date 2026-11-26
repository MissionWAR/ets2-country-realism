"""Span-preserving surgical SII/SUI document model."""

from __future__ import annotations

from collections.abc import Sequence

from ets2_realism.sii.hygiene import (
    SiiDiagnostic,
    normalize_sii_bytes,
    serialize_sii_text,
    validate_sii_hygiene,
)
from ets2_realism.sii.lexer import (
    SiiAttributeSpan,
    SiiIncludeSpan,
    SiiScanResult,
    SiiUnitBlock,
    scan_sii_structure,
)

__all__ = [
    "SiiAttributeSpan",
    "SiiDocument",
    "SiiIncludeSpan",
    "SiiUnitBlock",
]


class SiiDocument:
    """Span-preserving SII/SUI document supporting surgical field and array mutations."""

    def __init__(self, text: str, *, require_siinunit: bool = False) -> None:
        self._text = text
        self._require_siinunit = require_siinunit
        self._scan: SiiScanResult = scan_sii_structure(text, require_siinunit=require_siinunit)

    @classmethod
    def parse(
        cls,
        source: str | bytes,
        *,
        require_siinunit: bool = False,
    ) -> SiiDocument:
        """Parse raw bytes or text into a normalized, span-indexed ``SiiDocument``."""
        if isinstance(source, bytes):
            text = normalize_sii_bytes(source)
        else:
            cleaned = source[1:] if source.startswith("\ufeff") else source
            text = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        return cls(text, require_siinunit=require_siinunit)

    @property
    def text(self) -> str:
        return self._text

    @property
    def has_siinunit(self) -> bool:
        return self._scan.has_siinunit

    @property
    def units(self) -> list[SiiUnitBlock]:
        return list(self._scan.units)

    @property
    def includes(self) -> list[SiiIncludeSpan]:
        return list(self._scan.includes)

    @property
    def root_attributes(self) -> list[SiiAttributeSpan]:
        return list(self._scan.root_attributes)

    @property
    def diagnostics(self) -> list[SiiDiagnostic]:
        return validate_sii_hygiene(self._text, require_siinunit=self._require_siinunit)

    def find_units(
        self,
        class_name: str | None = None,
        unit_name: str | None = None,
    ) -> list[SiiUnitBlock]:
        """Return all unit blocks matching optional ``class_name`` and ``unit_name``."""
        return [
            unit
            for unit in self._scan.units
            if (class_name is None or unit.class_name == class_name)
            and (unit_name is None or unit.unit_name == unit_name)
        ]

    def get_unit(
        self,
        class_name: str | None = None,
        unit_name: str | None = None,
    ) -> SiiUnitBlock | None:
        """Return the first unit block matching optional filters, or ``None``."""
        matches = self.find_units(class_name=class_name, unit_name=unit_name)
        return matches[0] if matches else None

    def get_root_attributes(self, key: str | None = None) -> list[SiiAttributeSpan]:
        """Return top-level bare attributes (for headerless ``.sui`` fragments)."""
        if key is None:
            return list(self._scan.root_attributes)
        return [attr for attr in self._scan.root_attributes if attr.key == key]

    def render(self) -> str:
        """Return the current LF-normalized SII/SUI text."""
        return self._text

    def to_bytes(self) -> bytes:
        """Serialize the document as strict UTF-8 without BOM and LF line endings."""
        return serialize_sii_text(self._text)

    def _refresh(self) -> None:
        self._scan = scan_sii_structure(self._text, require_siinunit=self._require_siinunit)

    def _resolve_unit(self, unit: SiiUnitBlock | int) -> SiiUnitBlock:
        idx = unit if isinstance(unit, int) else unit.index
        if 0 <= idx < len(self._scan.units):
            current = self._scan.units[idx]
            if isinstance(unit, int) or (
                current.class_name == unit.class_name and current.unit_name == unit.unit_name
            ):
                return current
        raise KeyError(f"Unit not found in document: {unit!r}")

    def replace_span(self, start: int, end: int, replacement: str) -> None:
        """Surgically replace character range ``[start, end)`` and re-index spans."""
        if start < 0 or end < start or end > len(self._text):
            raise ValueError(f"Invalid span [{start}, {end}) for length {len(self._text)}")
        self._text = self._text[:start] + replacement + self._text[end:]
        self._refresh()

    def update_attribute_value(self, attr: SiiAttributeSpan, value: str) -> None:
        """Replace only ``attr.value_span`` in place, preserving indentation and comments."""
        if attr.raw_value == value:
            return
        self.replace_span(attr.value_span.start, attr.value_span.end, value)

    def remove_attribute_line(self, attr: SiiAttributeSpan) -> None:
        """Remove an attribute cleanly without deleting shared ``{`` or ``}`` braces."""
        start, end = self._attribute_removal_bounds(attr)
        self.replace_span(start, end, "")

    def insert_lines_after_attribute(
        self,
        attr: SiiAttributeSpan,
        lines: Sequence[str],
    ) -> None:
        """Insert ``lines`` immediately after ``attr``'s line (or before same-line ``}``)."""
        if not lines:
            return
        unit = self._owning_unit(attr)
        if unit is not None and attr.line_span.start <= unit.close_brace_pos < attr.line_span.end:
            ins_pos = unit.close_brace_pos
            while ins_pos > attr.span.end and self._text[ins_pos - 1] in " \t":
                ins_pos -= 1
            payload = "\n" + "\n".join(lines)
            self.replace_span(ins_pos, ins_pos, payload)
            return

        end = attr.line_span.end
        if end < len(self._text) and self._text[end] == "\n":
            insert_pos = end + 1
            payload = "".join(f"{line}\n" for line in lines)
        else:
            insert_pos = end
            payload = "\n" + "\n".join(lines)
        self.replace_span(insert_pos, insert_pos, payload)

    def insert_lines(self, unit: SiiUnitBlock | int, lines: Sequence[str]) -> None:
        """Insert ``lines`` cleanly into ``unit`` before its closing ``}`` or trailing @include."""
        current_unit = self._resolve_unit(unit)
        self._insert_lines_into_unit(current_unit, lines)

    def _owning_unit(self, attr: SiiAttributeSpan) -> SiiUnitBlock | None:
        for unit in self._scan.units:
            if unit.open_brace_pos < attr.span.start and attr.span.end <= unit.close_brace_pos:
                return unit
        return None

    def _attribute_removal_bounds(self, attr: SiiAttributeSpan) -> tuple[int, int]:
        l_start = attr.line_span.start
        l_end = attr.line_span.end
        unit = self._owning_unit(attr)
        same_open = unit is not None and l_start <= unit.open_brace_pos < l_end
        same_close = unit is not None and l_start <= unit.close_brace_pos < l_end

        if unit is not None and (same_open or same_close):
            if same_open and same_close:
                del_start = attr.span.start
                while del_start > unit.open_brace_pos + 1 and self._text[del_start - 1] in " \t":
                    del_start -= 1
                del_end = attr.span.end
                while del_end < unit.close_brace_pos and self._text[del_end] in " \t":
                    del_end += 1
                return del_start, del_end
            if same_open:
                del_start = attr.span.start
                while del_start > unit.open_brace_pos + 1 and self._text[del_start - 1] in " \t":
                    del_start -= 1
                return del_start, l_end
            del_start = attr.span.start
            while del_start > l_start and self._text[del_start - 1] in " \t":
                del_start -= 1
            if (
                del_start == l_start
                and unit.header_indent
                and l_start + len(unit.header_indent) <= attr.span.start
                and self._text.startswith(unit.header_indent, l_start)
            ):
                del_start = l_start + len(unit.header_indent)
            return del_start, unit.close_brace_pos

        if l_end < len(self._text) and self._text[l_end] == "\n":
            return l_start, l_end + 1
        if l_start > 0 and self._text[l_start - 1] == "\n":
            return l_start - 1, l_end
        return l_start, l_end

    def _replace_attribute_line_with_lines(
        self,
        attr: SiiAttributeSpan,
        unit: SiiUnitBlock,
        lines: Sequence[str],
    ) -> tuple[int, int, str]:
        l_start = attr.line_span.start
        l_end = attr.line_span.end
        same_open = l_start <= unit.open_brace_pos < l_end
        same_close = l_start <= unit.close_brace_pos < l_end
        joined = "\n".join(lines)

        if same_open and same_close:
            r_start, r_end = self._attribute_removal_bounds(attr)
            return (r_start, r_end, f"\n{joined}\n{unit.header_indent}")
        if same_open:
            r_start, r_end = self._attribute_removal_bounds(attr)
            return (r_start, r_end, f"\n{joined}")
        if same_close:
            r_start, r_end = self._attribute_removal_bounds(attr)
            kept_indent_end = l_start + (
                len(unit.header_indent)
                if unit.header_indent and self._text.startswith(unit.header_indent, l_start)
                else 0
            )
            if r_start > kept_indent_end:
                return (r_start, r_end, f"\n{joined}\n{unit.header_indent}")
            return (l_start, r_end, f"{joined}\n{unit.header_indent}")
        return (l_start, l_end, joined)

    def _apply_reverse_edits(self, edits: list[tuple[int, int, str]]) -> None:
        if not edits:
            return
        edits.sort(key=lambda item: (item[0], item[1]), reverse=True)
        updated = self._text
        for start, end, replacement in edits:
            updated = updated[:start] + replacement + updated[end:]
        self._text = updated
        self._refresh()

    def _insert_lines_into_unit(
        self,
        current_unit: SiiUnitBlock,
        lines: Sequence[str],
    ) -> None:
        if not lines:
            return
        payload = "".join(f"{line}\n" for line in lines)

        # Insert before any trailing @include directive inside the unit block.
        last_attr_end = max((a.span.end for a in current_unit.attributes), default=-1)
        for inc in current_unit.includes:
            if inc.span.start > last_attr_end:
                self.replace_span(inc.line_span.start, inc.line_span.start, payload)
                return

        close_pos = current_unit.close_brace_pos
        brace_line_start = self._text.rfind("\n", 0, close_pos) + 1
        prefix_on_brace_line = self._text[brace_line_start:close_pos]
        if prefix_on_brace_line.strip() == "":
            self.replace_span(brace_line_start, brace_line_start, payload)
            return

        # Single-line block such as ``country_data : .empty { }``.
        ins_pos = close_pos
        while ins_pos > brace_line_start and self._text[ins_pos - 1] in " \t":
            ins_pos -= 1
        replacement = f"\n{payload}{current_unit.header_indent}"
        self.replace_span(ins_pos, close_pos, replacement)

    def set_scalar(self, unit: SiiUnitBlock | int, key: str, value: str) -> None:
        """Update scalar ``key`` (last occurrence) in place or insert cleanly if absent."""
        current_unit = self._resolve_unit(unit)
        existing = current_unit.get_scalar(key)
        if existing is not None:
            self.update_attribute_value(existing, value)
            return
        self._insert_lines_into_unit(current_unit, [f"{current_unit.indent}{key}: {value}"])

    def replace_array_append(
        self,
        unit: SiiUnitBlock | int,
        key: str,
        values: Sequence[str],
    ) -> None:
        """Replace a contiguous ``key[]`` or fixed-array ``key`` block cleanly."""
        current_unit = self._resolve_unit(unit)
        all_for_key = [attr for attr in current_unit.attributes if attr.key == key]

        if not all_for_key:
            if not values:
                return
            lines = [f"{current_unit.indent}{key}[]: {val}" for val in values]
            self._insert_lines_into_unit(current_unit, lines)
            return

        if all(attr.is_append for attr in all_for_key):
            existing = all_for_key
            first_start = existing[0].span.start
            last_end = existing[-1].span.end
            for other in current_unit.attributes:
                if first_start <= other.span.start <= last_end and not (
                    other.key == key and other.is_append
                ):
                    raise ValueError(
                        f"Cannot replace non-contiguous/interleaved array {key!r}[] "
                        "as a single block"
                    )

            if len(existing) == len(values) and all(
                attr.raw_value == val for attr, val in zip(existing, values, strict=True)
            ):
                return

            edits: list[tuple[int, int, str]] = []
            common = min(len(existing), len(values))

            if len(values) > len(existing):
                last_attr = existing[-1]
                elem_indent = last_attr.indent or current_unit.indent
                extra_lines = [f"{elem_indent}{key}[]: {val}" for val in values[common:]]
                same_line_close = (
                    last_attr.line_span.start
                    <= current_unit.close_brace_pos
                    < last_attr.line_span.end
                )
                if same_line_close:
                    ins_pos = current_unit.close_brace_pos
                    while ins_pos > last_attr.span.end and self._text[ins_pos - 1] in " \t":
                        ins_pos -= 1
                    edits.append((ins_pos, ins_pos, "\n" + "\n".join(extra_lines)))
                else:
                    end = last_attr.line_span.end
                    if end < len(self._text) and self._text[end] == "\n":
                        edits.append(
                            (end + 1, end + 1, "".join(f"{line}\n" for line in extra_lines))
                        )
                    else:
                        edits.append((end, end, "\n" + "\n".join(extra_lines)))
            elif len(values) < len(existing):
                # Remove surplus trailing elements (reverse order so offsets stay disjoint).
                for idx in range(len(existing) - 1, common - 1, -1):
                    r_start, r_end = self._attribute_removal_bounds(existing[idx])
                    edits.append((r_start, r_end, ""))

            for idx in range(common - 1, -1, -1):
                attr = existing[idx]
                new_val = values[idx]
                if attr.raw_value != new_val:
                    edits.append((attr.value_span.start, attr.value_span.end, new_val))

            self._apply_reverse_edits(edits)
            return

        # Fixed-array (key: N + key[0..N-1]) or mixed representation: replace all spans cleanly.
        array_elems = [attr for attr in all_for_key if attr.is_append or attr.index is not None]
        if array_elems:
            first_start = array_elems[0].span.start
            last_end = array_elems[-1].span.end
            for other in current_unit.attributes:
                if first_start <= other.span.start <= last_end and other.key != key:
                    raise ValueError(
                        f"Cannot replace non-contiguous/interleaved array {key!r} as a single block"
                    )

        edits = []
        if not values:
            for attr in reversed(all_for_key):
                r_start, r_end = self._attribute_removal_bounds(attr)
                edits.append((r_start, r_end, ""))
            self._apply_reverse_edits(edits)
            return

        anchor = array_elems[0] if array_elems else all_for_key[0]
        elem_indent = anchor.indent or all_for_key[0].indent or current_unit.indent
        new_lines = [f"{elem_indent}{key}[]: {val}" for val in values]

        for attr in reversed(all_for_key):
            if attr is anchor:
                edits.append(
                    self._replace_attribute_line_with_lines(anchor, current_unit, new_lines)
                )
            else:
                r_start, r_end = self._attribute_removal_bounds(attr)
                edits.append((r_start, r_end, ""))

        self._apply_reverse_edits(edits)
