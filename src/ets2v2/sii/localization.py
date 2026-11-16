"""Read-only parser for ETS2 ``localization_db`` units and headerless ``.sui`` fragments."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from ets2v2.sii.document import SiiDocument
from ets2v2.sii.lexer import SiiAttributeSpan, unquote_sii_string


class LocalizationEntry(BaseModel):
    """Ordered ``(key, val)`` localization pair from ``localization_db`` or ``.sui``."""

    model_config = ConfigDict(frozen=True)

    key: str
    val: str


def _collect_pairs(attrs: Sequence[SiiAttributeSpan]) -> list[LocalizationEntry]:
    keys = [a for a in attrs if a.key == "key" and (a.is_append or a.index is not None)]
    vals = [a for a in attrs if a.key == "val" and (a.is_append or a.index is not None)]

    if keys and all(k.index is not None for k in keys):
        keys.sort(key=lambda a: a.index if a.index is not None else -1)
    if vals and all(v.index is not None for v in vals):
        vals.sort(key=lambda a: a.index if a.index is not None else -1)

    if len(keys) != len(vals):
        raise ValueError(
            f"Mismatched localization key[]/val[] counts: {len(keys)} keys vs {len(vals)} vals"
        )

    return [
        LocalizationEntry(
            key=unquote_sii_string(k.raw_value)[0],
            val=unquote_sii_string(v.raw_value)[0],
        )
        for k, v in zip(keys, vals, strict=True)
    ]


def parse_localization_db(source: str | bytes) -> list[LocalizationEntry]:
    """Parse ``key[]`` / ``val[]`` pairs from wrapped ``localization_db`` or headerless ``.sui``."""
    doc = SiiDocument.parse(source)
    if doc.units:
        loc_units = doc.find_units(class_name="localization_db")
        if not loc_units:
            raise ValueError("Expected localization_db unit or headerless key[]/val[] fragment")
        entries: list[LocalizationEntry] = []
        for unit in loc_units:
            entries.extend(_collect_pairs(unit.attributes))
        return entries

    return _collect_pairs(doc.root_attributes)
