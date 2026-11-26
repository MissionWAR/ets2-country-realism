"""Opt-in --patch-hardcoded-totems detector and surgical SiiDocument rewriter (D-16, T-04-14)."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2_realism.baseline.models import FuelBoardsBaseline
from ets2_realism.normalize.totem_format import (
    EUROZONE_TENTH_CENT_ISO2S,
    format_national_pump_price,
)
from ets2_realism.package.synthesize import format_sii_string
from ets2_realism.registry.snapshot import RealismSnapshot
from ets2_realism.sii.document import SiiDocument
from ets2_realism.sii.hygiene import validate_sii_hygiene
from ets2_realism.sii.sign_board import parse_sign_board
from ets2_realism.vfs.stack import VfsStack
from ets2_realism.vfs.types import ProtectedPayloadError, UnsupportedCompressionError, detect_3nk

HardcodedTotemStatus = Literal[
    "patched",
    "skipped_not_in_snapshot",
    "skipped_missing_grade",
    "skipped_non_numeric",
    "skipped_already_localized",
    "skipped_multi_item",
    "skipped_ambiguous",
    "skipped_unreadable",
]

# Empirically verified JRR single-text numeric boards (D-16, 04-RESEARCH §4.4).
# Label boards (01{b..i}), station IDs (01{j,k} "34.138.06"), and multi-item exit signs are
# strictly excluded and never rewritten.
JRR_NUMERIC_BOARD_SIGNATURES: Final[dict[str, tuple[str, str]]] = {
    "indo_gas_totem_01a": ("ID", "petrol_98"),
    "indo_gas_totem_01l": ("ID", "petrol_92"),
    "indo_gas_totem_01m": ("ID", "petrol_92"),
    "indo_gas_totem_01n": ("ID", "petrol_95"),
    "indo_gas_totem_01o": ("ID", "diesel"),
    "indo_gas_totem_01p": ("ID", "petrol_98"),
    "indo_gas_totem_01q": ("ID", "petrol_95"),
    "indo_gas_totem_01r": ("ID", "diesel"),
}

_COMMUNITY_NUMERIC_BOARD_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<cc>kg|kz|uz|tm|cn|ru|by|ua)_gas_(?:[a-z0-9_]+_)?(?P<grade>92|95|98|100|diesel|diesel_plus|lpg)$"
)
_NUMERIC_LITERAL_RE: Final[re.Pattern[str]] = re.compile(r"^\d+(?:\.\d{1,3})?$")
_SIGN_BOARD_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^def/sign/board/([^/]+)\.sii$")
_FUEL_KEYWORD_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:gas|fuel|totem|petrol|diesel|benz|azs)",
    re.IGNORECASE,
)

_GRADE_TOKEN_MAP: Final[dict[str, str]] = {
    "92": "petrol_92",
    "95": "petrol_95",
    "98": "petrol_98",
    "100": "petrol_100",
    "diesel": "diesel",
    "diesel_plus": "diesel_plus",
    "lpg": "lpg",
}

# Integer-display national currencies outside Phase 4 Core/ProMods sets (e.g. Indonesian Rupiah).
_EXTRA_INTEGER_ISO2S: Final[frozenset[str]] = frozenset({"ID"})
_QUANT_INT: Final[Decimal] = Decimal("1")


class HardcodedTotemBoardAction(BaseModel):
    """Per-board audit record produced by ``patch_hardcoded_numeric_totems()``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    board_name: str
    vfs_path: str
    winning_layer: str
    status: HardcodedTotemStatus
    iso2: str | None = None
    grade: str | None = None
    original_text: str | None = None
    token_key: str | None = None
    formatted_price: str | None = None
    detail: str | None = None


class HardcodedTotemResult(BaseModel):
    """Structured output of opt-in hardcoded numeric totem rewriting."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    board_files: dict[str, bytes] = Field(default_factory=dict)
    extra_locale_tokens: dict[str, str] = Field(default_factory=dict)
    actions: list[HardcodedTotemBoardAction] = Field(default_factory=list)


def _decode_third_party_sii(raw: bytes) -> str:
    payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _match_board_signature(board_name: str) -> tuple[str, str] | None:
    norm = board_name.strip().lower()
    if norm in JRR_NUMERIC_BOARD_SIGNATURES:
        return JRR_NUMERIC_BOARD_SIGNATURES[norm]
    match = _COMMUNITY_NUMERIC_BOARD_RE.fullmatch(norm)
    if match is None:
        return None
    iso2 = match.group("cc").upper()
    grade = _GRADE_TOKEN_MAP[match.group("grade")]
    return iso2, grade


def _format_hardcoded_board_price(iso2: str, local_price: float) -> str:
    """Format native price for community boards without ``<sup>`` markup (safe on custom fonts)."""
    code = iso2.strip().upper()
    if code in _EXTRA_INTEGER_ISO2S:
        dec = Decimal(str(local_price))
        return f"{dec.quantize(_QUANT_INT, rounding=ROUND_HALF_UP):.0f}"
    variant = "compact" if code in EUROZONE_TENTH_CENT_ISO2S else "standard"
    return format_national_pump_price(code, local_price, variant=variant)


def patch_hardcoded_numeric_totems(
    stack: VfsStack,
    snapshot: RealismSnapshot,
    baseline_fuel_boards: FuelBoardsBaseline,
) -> HardcodedTotemResult:
    """Conservatively rewrite verified JRR/7RM numeric fuel boards to ``@@fp_*_ets2r@@`` tokens."""
    vanilla_board_names = frozenset(b.board_name for b in baseline_fuel_boards.boards)
    excluded_boards = frozenset(baseline_fuel_boards.excluded_fuel_keyword_boards) | {"gas_empty"}

    board_files: dict[str, bytes] = {}
    extra_locale_tokens: dict[str, str] = {}
    actions: list[HardcodedTotemBoardAction] = []

    for vfs_path in sorted(stack.list_paths("def/sign/board")):
        path_match = _SIGN_BOARD_PATH_RE.fullmatch(vfs_path)
        if path_match is None:
            continue
        board_name = path_match.group(1)
        if board_name in vanilla_board_names or board_name in excluded_boards:
            continue

        entry = stack.resolve(vfs_path)
        if entry is None or entry.is_empty_stub:
            continue

        try:
            raw_bytes = stack.read_bytes(vfs_path)
        except (
            FileNotFoundError,
            ProtectedPayloadError,
            UnsupportedCompressionError,
            OSError,
            ValueError,
        ) as exc:
            if _FUEL_KEYWORD_RE.search(board_name) is not None:
                actions.append(
                    HardcodedTotemBoardAction(
                        board_name=board_name,
                        vfs_path=vfs_path,
                        winning_layer=entry.layer_name,
                        status="skipped_unreadable",
                        detail=str(exc),
                    )
                )
            continue

        if detect_3nk(raw_bytes):
            if _FUEL_KEYWORD_RE.search(board_name) is not None:
                actions.append(
                    HardcodedTotemBoardAction(
                        board_name=board_name,
                        vfs_path=vfs_path,
                        winning_layer=entry.layer_name,
                        status="skipped_unreadable",
                        detail="3nK\\x01 obfuscated sign board skipped; decryption is disabled.",
                    )
                )
            continue

        decoded = _decode_third_party_sii(raw_bytes)
        try:
            board = parse_sign_board(decoded)
        except ValueError as exc:
            if _FUEL_KEYWORD_RE.search(board_name) is not None:
                actions.append(
                    HardcodedTotemBoardAction(
                        board_name=board_name,
                        vfs_path=vfs_path,
                        winning_layer=entry.layer_name,
                        status="skipped_unreadable",
                        detail=str(exc),
                    )
                )
            continue

        if not board.is_single_text_fuel_candidate:
            if _FUEL_KEYWORD_RE.search(board_name) is not None:
                actions.append(
                    HardcodedTotemBoardAction(
                        board_name=board_name,
                        vfs_path=vfs_path,
                        winning_layer=entry.layer_name,
                        status="skipped_multi_item",
                        detail=(
                            f"model_name={board.model_name!r}, items_count={board.items_count}, "
                            f"text_slots={len(board.text_slots)}"
                        ),
                    )
                )
            continue

        slot = board.text_slots[0]
        raw_text = (slot.text or "").strip()

        if slot.localization_key is not None:
            actions.append(
                HardcodedTotemBoardAction(
                    board_name=board_name,
                    vfs_path=vfs_path,
                    winning_layer=entry.layer_name,
                    status="skipped_already_localized",
                    original_text=raw_text,
                )
            )
            continue

        if _NUMERIC_LITERAL_RE.fullmatch(raw_text) is None:
            actions.append(
                HardcodedTotemBoardAction(
                    board_name=board_name,
                    vfs_path=vfs_path,
                    winning_layer=entry.layer_name,
                    status="skipped_non_numeric",
                    original_text=raw_text,
                )
            )
            continue

        sig = _match_board_signature(board_name)
        if sig is None:
            actions.append(
                HardcodedTotemBoardAction(
                    board_name=board_name,
                    vfs_path=vfs_path,
                    winning_layer=entry.layer_name,
                    status="skipped_ambiguous",
                    original_text=raw_text,
                )
            )
            continue

        iso2, canonical_grade = sig
        snap_country = snapshot.countries.get(iso2)
        if snap_country is None:
            actions.append(
                HardcodedTotemBoardAction(
                    board_name=board_name,
                    vfs_path=vfs_path,
                    winning_layer=entry.layer_name,
                    status="skipped_not_in_snapshot",
                    iso2=iso2,
                    grade=canonical_grade,
                    original_text=raw_text,
                    detail=f"ISO-2 {iso2!r} not present in loaded realism snapshot",
                )
            )
            continue

        price = snap_country.fuel.local_prices.get(canonical_grade)
        if price is None or not math.isfinite(price) or price <= 0.0:
            actions.append(
                HardcodedTotemBoardAction(
                    board_name=board_name,
                    vfs_path=vfs_path,
                    winning_layer=entry.layer_name,
                    status="skipped_missing_grade",
                    iso2=iso2,
                    grade=canonical_grade,
                    original_text=raw_text,
                    detail=f"Grade {canonical_grade!r} unavailable for {iso2!r} in snapshot",
                )
            )
            continue

        formatted_price = _format_hardcoded_board_price(iso2, price)
        token_key = f"fp_{iso2.lower()}_{canonical_grade}_ets2r"

        doc = SiiDocument.parse(decoded)
        text_unit = doc.get_unit(class_name="sign_template_text", unit_name=slot.unit_name)
        text_attr = text_unit.get_scalar("text") if text_unit is not None else None
        if text_unit is None or text_attr is None:
            actions.append(
                HardcodedTotemBoardAction(
                    board_name=board_name,
                    vfs_path=vfs_path,
                    winning_layer=entry.layer_name,
                    status="skipped_unreadable",
                    iso2=iso2,
                    grade=canonical_grade,
                    original_text=raw_text,
                    detail=f"Unable to locate text scalar on unit {slot.unit_name!r}",
                )
            )
            continue

        doc.update_attribute_value(text_attr, format_sii_string(f"@@{token_key}@@"))
        out_bytes = doc.to_bytes()
        hygiene = validate_sii_hygiene(out_bytes, require_siinunit=True)
        if hygiene:
            summary = "; ".join(f"{d.code}@{d.line}:{d.column}: {d.message}" for d in hygiene)
            actions.append(
                HardcodedTotemBoardAction(
                    board_name=board_name,
                    vfs_path=vfs_path,
                    winning_layer=entry.layer_name,
                    status="skipped_unreadable",
                    iso2=iso2,
                    grade=canonical_grade,
                    original_text=raw_text,
                    detail=f"Rewritten hardcoded board hygiene failure: {summary}",
                )
            )
            continue

        board_files[vfs_path] = out_bytes
        extra_locale_tokens[token_key] = formatted_price
        actions.append(
            HardcodedTotemBoardAction(
                board_name=board_name,
                vfs_path=vfs_path,
                winning_layer=entry.layer_name,
                status="patched",
                iso2=iso2,
                grade=canonical_grade,
                original_text=raw_text,
                token_key=token_key,
                formatted_price=formatted_price,
            )
        )

    return HardcodedTotemResult(
        board_files=board_files,
        extra_locale_tokens=dict(sorted(extra_locale_tokens.items())),
        actions=actions,
    )


__all__ = [
    "JRR_NUMERIC_BOARD_SIGNATURES",
    "HardcodedTotemBoardAction",
    "HardcodedTotemResult",
    "HardcodedTotemStatus",
    "patch_hardcoded_numeric_totems",
]
