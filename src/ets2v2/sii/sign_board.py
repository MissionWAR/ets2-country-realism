"""Read-only parser for ETS2 ``sign_board_template`` and ``sign_template_text`` units."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.sii.document import SiiDocument
from ets2v2.sii.lexer import (
    SiiUnitBlock,
    parse_sii_float,
    split_sii_tuple,
    unquote_sii_string,
)


class SignTemplateTextSlot(BaseModel):
    """Resolved ``sign_template_text`` child slot linked from a ``sign_board_template``."""

    model_config = ConfigDict(frozen=True)

    slot_index: int
    unit_name: str
    font_face: str | None = None
    coords_l: float | None = None
    coords_r: float | None = None
    coords_t: float | None = None
    coords_b: float | None = None
    h_align: str | None = None
    v_align: str | None = None
    text: str | None = None

    @property
    def localization_key(self) -> str | None:
        """Extract the inner key when ``text`` is an ``@@...@@`` localization token."""
        if (
            self.text is not None
            and len(self.text) > 4
            and self.text.startswith("@@")
            and self.text.endswith("@@")
        ):
            return self.text[2:-2]
        return None


class SignBoardTemplate(BaseModel):
    """Read-only model of a ``sign_board_template`` and its linked ``sign_template_text`` slots."""

    model_config = ConfigDict(frozen=True)

    unit_name: str
    model_name: str | None = None
    board_size: tuple[float, float] | None = None
    items_count: int = 0
    item_refs: list[str | None] = Field(default_factory=list)
    child_types: list[str] = Field(default_factory=list)
    text_slots: list[SignTemplateTextSlot] = Field(default_factory=list)

    @property
    def is_single_text_fuel_candidate(self) -> bool:
        """Return True when board matches 1.62 fuel-totem shape (empty model, 1 text slot)."""
        return (
            self.model_name == ""
            and self.items_count == 1
            and len(self.text_slots) == 1
            and self.child_types == ["sign_template_text"]
        )


def _scalar_non_nil(unit: SiiUnitBlock, key: str) -> str | None:
    attr = unit.get_scalar(key)
    if attr is None:
        return None
    raw = attr.raw_value.strip()
    if not raw or raw == "nil":
        return None
    return raw


def _parse_float_2(raw: str) -> tuple[float, float]:
    parts = split_sii_tuple(raw, expected_len=2)
    return (parse_sii_float(parts[0]), parse_sii_float(parts[1]))


def _parse_text_slot(slot_index: int, unit: SiiUnitBlock) -> SignTemplateTextSlot:
    font_raw = _scalar_non_nil(unit, "font_face")
    coords_l_raw = _scalar_non_nil(unit, "coords_l")
    coords_r_raw = _scalar_non_nil(unit, "coords_r")
    coords_t_raw = _scalar_non_nil(unit, "coords_t")
    coords_b_raw = _scalar_non_nil(unit, "coords_b")
    h_raw = _scalar_non_nil(unit, "h_align")
    v_raw = _scalar_non_nil(unit, "v_align")
    text_raw = _scalar_non_nil(unit, "text")

    return SignTemplateTextSlot(
        slot_index=slot_index,
        unit_name=unit.unit_name,
        font_face=unquote_sii_string(font_raw)[0] if font_raw is not None else None,
        coords_l=parse_sii_float(coords_l_raw) if coords_l_raw is not None else None,
        coords_r=parse_sii_float(coords_r_raw) if coords_r_raw is not None else None,
        coords_t=parse_sii_float(coords_t_raw) if coords_t_raw is not None else None,
        coords_b=parse_sii_float(coords_b_raw) if coords_b_raw is not None else None,
        h_align=unquote_sii_string(h_raw)[0] if h_raw is not None else None,
        v_align=unquote_sii_string(v_raw)[0] if v_raw is not None else None,
        text=unquote_sii_string(text_raw)[0] if text_raw is not None else None,
    )


def parse_sign_board(source: str | bytes) -> SignBoardTemplate:
    """Parse a ``sign_board_template`` ``.sii`` file and resolve ``sign_template_text`` slots."""
    doc = SiiDocument.parse(source)
    board_unit = doc.get_unit(class_name="sign_board_template")
    if board_unit is None:
        raise ValueError("No sign_board_template unit found in SII source")

    model_raw = _scalar_non_nil(board_unit, "model_name")
    model_name = unquote_sii_string(model_raw)[0] if model_raw is not None else None

    board_size_raw = _scalar_non_nil(board_unit, "board_size")
    board_size = _parse_float_2(board_size_raw) if board_size_raw is not None else None

    items_scalar_raw = _scalar_non_nil(board_unit, "items")
    indexed_items = sorted(
        (attr for attr in board_unit.attributes if attr.key == "items" and attr.index is not None),
        key=lambda attr: attr.index if attr.index is not None else -1,
    )
    items_count = int(items_scalar_raw) if items_scalar_raw is not None else len(indexed_items)

    units_by_name = {unit.unit_name: unit for unit in doc.units}
    item_refs: list[str | None] = []
    child_types: list[str] = []
    text_slots: list[SignTemplateTextSlot] = []

    for item_attr in indexed_items:
        slot_index = item_attr.index if item_attr.index is not None else len(item_refs)
        raw_ref = item_attr.raw_value.strip()
        if not raw_ref or raw_ref == "nil":
            item_refs.append(None)
            continue

        ref_name = unquote_sii_string(raw_ref)[0]
        item_refs.append(ref_name)
        child = units_by_name.get(ref_name)
        if child is not None:
            child_types.append(child.class_name)
            if child.class_name == "sign_template_text":
                text_slots.append(_parse_text_slot(slot_index, child))

    return SignBoardTemplate(
        unit_name=board_unit.unit_name,
        model_name=model_name,
        board_size=board_size,
        items_count=items_count,
        item_refs=item_refs,
        child_types=child_types,
        text_slots=text_slots,
    )
