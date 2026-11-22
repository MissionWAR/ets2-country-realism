"""Shared stdlib HTML anchor, numeric separator, and calendar date parsers for online fetchers."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Final

_ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DMY_DATE_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


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
