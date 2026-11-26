"""Shared stdlib HTML anchor, numeric separator, and calendar date parsers for online fetchers."""

from __future__ import annotations

import io
import math
import re
import zipfile
import zlib
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Final

DEFAULT_OOXML_MAX_ENTRIES: Final[int] = 256
DEFAULT_OOXML_MAX_UNCOMPRESSED_BYTES: Final[int] = 67_108_864  # 64 MiB uncompressed ZIP-bomb cap

_ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_DMY_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_XML_FORBIDDEN_DECL_BYTES_RE: Final[re.Pattern[bytes]] = re.compile(
    rb"<!(?:DOCTYPE|ENTITY)\b",
    flags=re.IGNORECASE,
)
_XML_FORBIDDEN_DECL_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"<!(?:DOCTYPE|ENTITY)\b",
    flags=re.IGNORECASE,
)


class AnchorExtractor(HTMLParser):
    """Minimal stdlib HTMLParser extracting ``(href, link_text)`` pairs from ``<a>`` tags."""

    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for attr_name, attr_val in attrs:
            if attr_name.lower() == "href" and attr_val:
                self._current_href = attr_val.strip()
                self._text_parts = []
                break

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href is not None:
            text = " ".join("".join(self._text_parts).split())
            self.anchors.append((self._current_href, text))
            self._current_href = None
            self._text_parts = []


def extract_iso_date(value: object) -> str | None:
    """Extract and validate a real calendar ``YYYY-MM-DD`` date from a date/datetime/string."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        return None
    iso_match = _ISO_DATE_RE.search(value)
    if iso_match is not None:
        candidate = iso_match.group(1)
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return None
    dmy_match = _DMY_DATE_RE.search(value)
    if dmy_match is not None:
        day_s, month_s, year_s = dmy_match.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s)).isoformat()
        except ValueError:
            return None
    return None


def parse_positive_float(value: object) -> float | None:
    """Parse a positive finite float handling mixed European/English thousands and decimal marks."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) and num > 0.0 else None
    if not isinstance(value, str):
        return None

    cleaned = value.strip().replace("\u00a0", "").replace(" ", "")
    if not cleaned or cleaned in {"-", "N/A", "n/a", "NA", ".."}:
        return None

    has_comma = "," in cleaned
    has_dot = "." in cleaned
    if has_comma and has_dot:
        # Whichever separator appears last is the decimal mark; the other is thousands grouping.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        cleaned = cleaned.replace(",", "") if cleaned.count(",") > 1 else cleaned.replace(",", ".")
    elif has_dot and cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")

    try:
        num = float(cleaned)
    except ValueError:
        return None
    return num if math.isfinite(num) and num > 0.0 else None


def _looks_like_xml_member(filename: str, data: bytes) -> bool:
    if filename.lower().endswith((".xml", ".rels")):
        return True
    head = data[:64].lstrip(b" \t\r\n\x00\xef\xbb\xbf\xff\xfe\xfe\xff")
    return head.startswith((b"<", b"<\x00"))


def _contains_forbidden_xml_decl(data: bytes) -> bool:
    if _XML_FORBIDDEN_DECL_BYTES_RE.search(data):
        return True
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data[:64]:
        for enc in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                decoded = data.decode(enc)
            except UnicodeDecodeError:
                continue
            if _XML_FORBIDDEN_DECL_TEXT_RE.search(decoded):
                return True
    return False


def validate_ooxml_zip_safety(
    raw_xlsx: bytes,
    *,
    max_entries: int = DEFAULT_OOXML_MAX_ENTRIES,
    max_uncompressed_bytes: int = DEFAULT_OOXML_MAX_UNCOMPRESSED_BYTES,
) -> None:
    """Pre-validate OOXML ZIP container against ZIP bombs, encryption, and DOCTYPE/ENTITY."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_xlsx), "r") as zf:
            infos = zf.infolist()
            if len(infos) > max_entries:
                raise ValueError(
                    f"OOXML archive entry count {len(infos)} exceeds cap {max_entries}"
                )
            total_uncompressed = 0
            for info in infos:
                if info.flag_bits & 0x41:
                    raise ValueError(f"Encrypted OOXML entry {info.filename!r} is disallowed")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ValueError(f"Unsupported OOXML compression method {info.compress_type}")
                if info.file_size > max_uncompressed_bytes:
                    raise ValueError(
                        f"OOXML entry {info.filename!r} declared size exceeds uncompressed cap"
                    )
                remaining_budget = max_uncompressed_bytes - total_uncompressed
                with zf.open(info, "r") as member:
                    # Stream-read with hard cap (do not trust ZipInfo.file_size header alone)
                    data = member.read(remaining_budget + 1)
                total_uncompressed += len(data)
                if total_uncompressed > max_uncompressed_bytes:
                    raise ValueError(
                        "OOXML total uncompressed payload exceeds safety cap "
                        f"({max_uncompressed_bytes} bytes)"
                    )
                if _looks_like_xml_member(info.filename, data) and _contains_forbidden_xml_decl(
                    data
                ):
                    raise ValueError(
                        f"Forbidden DOCTYPE/ENTITY declaration in OOXML member {info.filename!r}"
                    )
    except (zipfile.BadZipFile, zlib.error, RuntimeError, EOFError) as exc:
        raise ValueError(f"Invalid or corrupt OOXML ZIP archive: {exc}") from exc
