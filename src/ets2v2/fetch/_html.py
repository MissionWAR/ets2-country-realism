"""Stdlib-only HTML table/text extractors and multi-charset fallback decoder (D-06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Final

_SKIP_TAGS: Final[frozenset[str]] = frozenset({"script", "style"})
_BLOCK_TAGS: Final[frozenset[str]] = frozenset(
    {
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "dt",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "p",
        "pre",
        "section",
        "td",
        "th",
        "tr",
    }
)


class Tier2EncodingError(ValueError):
    """Raised when a Tier 2 portal response cannot be decoded cleanly under allowed charsets."""


@dataclass
class _TableFrame:
    rows: list[list[str]] = field(default_factory=list)
    current_row: list[str] = field(default_factory=list)
    cell_parts: list[str] = field(default_factory=list)
    in_row: bool = False
    in_cell: bool = False


class TableExtractor(HTMLParser):
    """Stdlib HTMLParser collecting all HTML ``<table>`` rows as ``list[list[list[str]]]``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[_TableFrame] = []
        self._skip_depth: int = 0

    def _flush_cell(self, frame: _TableFrame) -> None:
        if frame.in_cell:
            frame.current_row.append(" ".join("".join(frame.cell_parts).split()))
            frame.cell_parts = []
            frame.in_cell = False

    def _flush_row(self, frame: _TableFrame) -> None:
        self._flush_cell(frame)
        if frame.in_row:
            if frame.current_row:
                frame.rows.append(frame.current_row)
            frame.current_row = []
            frame.in_row = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        lower = tag.lower()
        if lower in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if lower == "table":
            self._stack.append(_TableFrame())
            return
        if not self._stack:
            return
        frame = self._stack[-1]
        if lower == "tr":
            self._flush_row(frame)
            frame.in_row = True
            frame.current_row = []
        elif lower in {"td", "th"}:
            if not frame.in_row:
                frame.in_row = True
                frame.current_row = []
            self._flush_cell(frame)
            frame.in_cell = True
            frame.cell_parts = []
        elif lower == "br" and frame.in_cell:
            frame.cell_parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if self._skip_depth > 0:
            return
        if tag.lower() == "br" and self._stack and self._stack[-1].in_cell:
            self._stack[-1].cell_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0 or not self._stack:
            return
        frame = self._stack[-1]
        if frame.in_cell:
            frame.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in _SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0 or not self._stack:
            return
        frame = self._stack[-1]
        if lower in {"td", "th"}:
            self._flush_cell(frame)
        elif lower == "tr":
            self._flush_row(frame)
        elif lower == "table":
            self._flush_row(frame)
            finished = self._stack.pop()
            if finished.rows:
                self.tables.append(finished.rows)


class TextExtractor(HTMLParser):
    """Stdlib HTMLParser extracting normalized visible text blocks while ignoring script/style."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def _flush(self) -> None:
        if not self._parts:
            return
        cleaned = " ".join("".join(self._parts).split())
        self._parts = []
        if cleaned:
            self.blocks.append(cleaned)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        lower = tag.lower()
        if lower in _SKIP_TAGS:
            self._flush()
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and lower in _BLOCK_TAGS:
            self._flush()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if self._skip_depth == 0 and tag.lower() in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in _SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth == 0 and lower in _BLOCK_TAGS:
            self._flush()

    def close(self) -> None:
        super().close()
        self._flush()


def extract_html_tables(html_text: str) -> list[list[list[str]]]:
    """Extract all HTML tables into normalized row/cell string matrices."""
    parser = TableExtractor()
    parser.feed(html_text)
    parser.close()
    return parser.tables


def extract_html_text(html_text: str) -> list[str]:
    """Extract normalized visible text blocks from an HTML document."""
    parser = TextExtractor()
    parser.feed(html_text)
    parser.close()
    return parser.blocks


def decode_with_fallbacks(
    raw: bytes,
    encodings: tuple[str, ...] = ("utf-8-sig", "windows-1251", "latin-1"),
) -> str:
    """Decode bytes strictly across ordered charsets; raise Tier2EncodingError if all fail."""
    for enc in encodings:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise Tier2EncodingError(f"Failed to decode response with encodings {encodings!r}")
