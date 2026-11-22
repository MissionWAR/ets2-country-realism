"""Option 4b Zero-DDS compiler emitting 460 def/sign/board/*.sii and 43 locale modules."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict

from ets2v2.baseline.models import FuelBoardEntry, FuelBoardsBaseline, LocalesBaseline
from ets2v2.normalize.models import CountryFuelLockEntry, PricesLockfile
from ets2v2.normalize.totem_catalog import TotemBoardClassification, classify_all_fuel_boards
from ets2v2.normalize.totem_format import resolve_totem_token_and_value
from ets2v2.package.synthesize import format_sii_string
from ets2v2.sii.hygiene import serialize_sii_text, validate_sii_hygiene

# SCS unit segment rule: <= 12 chars matching [a-z0-9_]{1,12} ("ets2v2_fuel" = 11 chars).
FUEL_LOCALE_UNIT_NAME: Final[str] = ".ets2v2_fuel"
FUEL_LOCALE_FILENAME: Final[str] = "local_module.ets2v2_fuel.sii"

_TOKEN_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$")
_UNIT_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^\.?[a-z0-9_]+(\.[a-z0-9_]+)*$")
_LOCALE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z]{2}_[a-z]{2}$")
_VALID_HALIGN: Final[frozenset[str]] = frozenset({"left", "center", "right"})
_VALID_VALIGN: Final[frozenset[str]] = frozenset({"top", "center", "bottom"})


class TotemTokenResolver(Protocol):
    """Callable resolving ``(token_key, display_value)`` for one classified fuel board."""

    def __call__(
        self,
        board: FuelBoardEntry,
        classification: TotemBoardClassification,
        entry: CountryFuelLockEntry,
    ) -> tuple[str, str]: ...


class CompiledTotems(BaseModel):
    """Compiled Zero-DDS sign board overrides and 43-locale fuel localization modules."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    board_files: dict[str, bytes]
    locale_files: dict[str, bytes]
    token_values: dict[str, str]
    board_tokens: dict[str, str]
    skipped_boards: list[str]


def _format_sii_float(value: float, *, field_name: str) -> str:
    """Format a finite float cleanly without scientific notation while preserving float32 detail."""
    if not math.isfinite(value):
        raise ValueError(f"Non-finite float for {field_name}: {value!r}")
    if value == 0.0:
        return "0"
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    formatted = f"{value:.9f}".rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _require_unit_name(unit_name: str, *, field_name: str) -> str:
    if _UNIT_NAME_RE.fullmatch(unit_name) is None:
        raise ValueError(f"Invalid SII unit name for {field_name}: {unit_name!r}")
    return unit_name


def _require_token_key(token_key: str, *, label: str) -> str:
    if _TOKEN_KEY_RE.fullmatch(token_key) is None:
        raise ValueError(
            f"Invalid totem localization {label} {token_key!r}; "
            "expected ^fp_[a-z]{2}_[a-z0-9_]+_ets2v2$"
        )
    return token_key


def _assert_hygiene(raw: bytes, *, label: str) -> None:
    diagnostics = validate_sii_hygiene(raw, require_siinunit=True)
    if diagnostics:
        summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in diagnostics)
        raise ValueError(f"Synthesized SII hygiene failure for {label}: {summary}")


def synthesize_sign_board_sii(board: FuelBoardEntry, token_key: str) -> bytes:
    """Synthesize a clean-room ``def/sign/board/<board>.sii`` preserving all 24 1.62 attributes."""
    safe_token = _require_token_key(token_key, label="token")
    if board.model_name != "" or board.items_count != 1:
        raise ValueError(
            f"Board {board.board_name!r} is not a single-text empty-model fuel totem "
            f"(model_name={board.model_name!r}, items_count={board.items_count})"
        )

    slot = board.slot
    if (
        board.template_board_name is None
        or board.width is None
        or board.height is None
        or board.dynamic_attributes is None
        or slot.font_face is None
        or slot.font_size is None
        or slot.text_halign is None
        or slot.text_valign is None
        or slot.font_opacity is None
        or slot.line_spacing is None
        or slot.letter_spacing is None
        or slot.text_id is None
        or slot.area_name is None
        or slot.coords_l is None
        or slot.coords_r is None
        or slot.coords_t is None
        or slot.coords_b is None
        or slot.z_order is None
        or slot.tag is None
    ):
        raise ValueError(
            f"Board {board.board_name!r} is missing required ETS2 1.62 rendering attributes; "
            "re-extract data/baselines/ets2_1.62_def/fuel_boards.json"
        )

    if slot.text_halign not in _VALID_HALIGN:
        raise ValueError(f"Invalid text_halign {slot.text_halign!r} on board {board.board_name!r}")
    if slot.text_valign not in _VALID_VALIGN:
        raise ValueError(f"Invalid text_valign {slot.text_valign!r} on board {board.board_name!r}")

    board_unit = _require_unit_name(board.unit_name, field_name="board.unit_name")
    slot_unit = _require_unit_name(slot.unit_name, field_name="slot.unit_name")

    font_color_str = "nil" if slot.font_color is None else str(slot.font_color)
    area_idx_str = "nil" if slot.area_idx is None else str(slot.area_idx)

    lines: list[str] = [
        "SiiNunit",
        "{",
        f"sign_board_template : {board_unit} {{",
        f" board_name: {format_sii_string(board.template_board_name)}",
        f" width: {_format_sii_float(board.width, field_name='width')}",
        f" height: {_format_sii_float(board.height, field_name='height')}",
        ' model_name: ""',
        " items: 1",
        f" items[0]: {slot_unit}",
        f" dynamic_attributes: {board.dynamic_attributes}",
        "}",
        "",
        f"sign_template_text : {slot_unit} {{",
        f" text: {format_sii_string(f'@@{safe_token}@@')}",
        f" font_face: {format_sii_string(slot.font_face)}",
        f" font_size: {_format_sii_float(slot.font_size, field_name='font_size')}",
        f" text_halign: {slot.text_halign}",
        f" text_valign: {slot.text_valign}",
        f" font_color: {font_color_str}",
        f" font_opacity: {_format_sii_float(slot.font_opacity, field_name='font_opacity')}",
        f" line_spacing: {_format_sii_float(slot.line_spacing, field_name='line_spacing')}",
        f" letter_spacing: {_format_sii_float(slot.letter_spacing, field_name='letter_spacing')}",
        f" id: {slot.text_id}",
        f" area_name: {format_sii_string(slot.area_name)}",
        f" area_idx: {area_idx_str}",
        f" coords_l: {_format_sii_float(slot.coords_l, field_name='coords_l')}",
        f" coords_r: {_format_sii_float(slot.coords_r, field_name='coords_r')}",
        f" coords_t: {_format_sii_float(slot.coords_t, field_name='coords_t')}",
        f" coords_b: {_format_sii_float(slot.coords_b, field_name='coords_b')}",
        f" z_order: {slot.z_order}",
        f" tag: {format_sii_string(slot.tag)}",
        "}",
        "",
        "}",
    ]
    raw = serialize_sii_text("\n".join(lines) + "\n")
    _assert_hygiene(raw, label=f"def/sign/board/{board.board_name}.sii")
    return raw


def synthesize_fuel_locale_module_sii(token_values: Mapping[str, str]) -> bytes:
    """Synthesize a clean-room ``locale/<lang>/local_module.ets2v2_fuel.sii`` payload."""
    if not token_values:
        raise ValueError("Cannot synthesize fuel localization module with zero token values")

    lines: list[str] = [
        "SiiNunit",
        "{",
        f"localization_db : {FUEL_LOCALE_UNIT_NAME}",
        "{",
    ]
    for key in sorted(token_values):
        safe_key = _require_token_key(key, label="key")
        val = token_values[key]
        if not val:
            raise ValueError(f"Empty display value for localization key {safe_key!r}")
        if "," in val:
            raise ValueError(
                f"Disallowed comma decimal separator in localization value for {safe_key!r}: "
                f"{val!r} (D-11 requires uniform dot '.')"
            )
        lines.append(f"\tkey[]: {format_sii_string(safe_key)}")
        lines.append(f"\tval[]: {format_sii_string(val)}")

    lines.append("}")
    lines.append("}")
    raw = serialize_sii_text("\n".join(lines) + "\n")
    _assert_hygiene(raw, label=FUEL_LOCALE_FILENAME)
    return raw


def compile_totem_payloads(
    fuel_boards: FuelBoardsBaseline,
    locales: LocalesBaseline,
    prices_lock: PricesLockfile,
    *,
    resolver: TotemTokenResolver | None = None,
) -> CompiledTotems:
    """Compile all identifiable fuel boards and synchronized active locale modules offline."""
    active_resolver: TotemTokenResolver = (
        resolver if resolver is not None else resolve_totem_token_and_value
    )

    classifications = classify_all_fuel_boards(fuel_boards)
    boards_by_name = {board.board_name: board for board in fuel_boards.boards}
    classified_names = {item.board_name for item in classifications}
    skipped_boards = sorted(
        board.board_name for board in fuel_boards.boards if board.board_name not in classified_names
    )

    board_files: dict[str, bytes] = {}
    board_tokens: dict[str, str] = {}
    token_values_unsorted: dict[str, str] = {}

    for item in classifications:
        board = boards_by_name[item.board_name]
        lock_entry = prices_lock.countries.get(item.iso2)
        if lock_entry is None:
            raise ValueError(
                f"Missing prices.lock.json country entry for {item.iso2!r} "
                f"(required by board {item.board_name!r})"
            )

        token_key, display_value = active_resolver(board, item, lock_entry)
        safe_token = _require_token_key(token_key, label="token")
        existing_val = token_values_unsorted.get(safe_token)
        if existing_val is not None and existing_val != display_value:
            raise ValueError(
                f"Conflicting display values for token {safe_token!r}: "
                f"{existing_val!r} vs {display_value!r} (board {item.board_name!r})"
            )

        token_values_unsorted[safe_token] = display_value
        board_tokens[item.board_name] = safe_token
        rel_path = f"def/sign/board/{item.board_name}.sii"
        board_files[rel_path] = synthesize_sign_board_sii(board, safe_token)

    token_values = {k: token_values_unsorted[k] for k in sorted(token_values_unsorted)}

    active_locales = sorted(locales.active_locales)
    if not active_locales:
        raise ValueError("LocalesBaseline.active_locales must not be empty")
    if "fr_qc" in active_locales:
        raise ValueError("Deprecated locale 'fr_qc' must not be emitted (D-09 / D-12)")

    locale_payload = synthesize_fuel_locale_module_sii(token_values)
    locale_files: dict[str, bytes] = {}
    for lang in active_locales:
        if _LOCALE_CODE_RE.fullmatch(lang) is None:
            raise ValueError(f"Invalid ETS2 locale directory code: {lang!r}")
        locale_files[f"locale/{lang}/{FUEL_LOCALE_FILENAME}"] = locale_payload

    return CompiledTotems(
        board_files=board_files,
        locale_files=locale_files,
        token_values=token_values,
        board_tokens=board_tokens,
        skipped_boards=skipped_boards,
    )
