"""Deterministic 461-board ETS2 1.62 fuel totem classifier and canonical fp_* alias adapter."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.baseline.models import BoardClassification, FuelBoardEntry, FuelBoardsBaseline
from ets2v2.normalize.currencies import TERRITORY_CURRENCIES
from ets2v2.normalize.models import FuelGrade

# Structural spacer boards left untouched (gas_empty has font_size == 0 & font_opacity == 0)
STRUCTURAL_SPACER_BOARDS: Final[frozenset[str]] = frozenset({"gas_empty"})

# Legacy non-`gas_` single-text fuel boards in ETS2 1.62 def.scs
NON_GAS_LEGACY_BOARDS: Final[dict[str, tuple[str, FuelGrade]]] = {
    "es_95_01": ("ES", "petrol_95"),
    "es_diesel_01": ("ES", "diesel"),
    "pt_95_01": ("PT", "petrol_95"),
    "pt_diesel_01": ("PT", "diesel"),
}

# Region token -> canonical ISO-2 mapping covering all 37 countries with vanilla 1.62 boards
# (36 Vanilla+DLC + IE; CY and MT have 0 vanilla boards) plus British Isles & Dortmund aliases.
REGION_ALIAS_TO_ISO2: Final[dict[str, str]] = {
    **{iso2.lower(): iso2 for iso2 in sorted(TERRITORY_CURRENCIES) if iso2 not in {"CY", "MT"}},
    "bi": "GB",
    "dortmund": "DE",
}

# Canonical D-14 grade suffix / fp_* alias adapter
GRADE_SUFFIX_TO_CANONICAL: Final[dict[str, FuelGrade]] = {
    "diesel": "diesel",
    "95": "petrol_95",
    "unleaded": "petrol_95",
    "natural95": "petrol_95",
    "98": "petrol_98",
    "97": "petrol_98",
    "super": "petrol_98",
    "natural98": "petrol_98",
    "100": "petrol_100",
    "natural100": "petrol_100",
    "92": "petrol_92",
    "natural92": "petrol_92",
    "85": "e85",
    "e85": "e85",
    "lpg": "lpg",
    "mpo": "mpo",
    "diesel5": "diesel_plus",
    "dieselplus": "diesel_plus",
    "diesel_plus": "diesel_plus",
    "superdiesel": "diesel_plus",
    "superd": "diesel_plus",
}


class TotemBoardClassification(BaseModel):
    """Canonical country/grade classification for one identifiable single-text fuel board."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    board_name: str = Field(min_length=1)
    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    grade: FuelGrade
    token_base: str = Field(pattern=r"^fp_[a-z]{2}_[a-z0-9_]+$")
    classification: BoardClassification


def classify_fuel_board(board: FuelBoardEntry) -> TotemBoardClassification | None:
    """Classify one single-text fuel board, returning ``None`` only for verified spacers."""
    name = board.board_name

    if name in STRUCTURAL_SPACER_BOARDS:
        if board.slot.font_size != 0.0 or board.slot.font_opacity != 0.0:
            raise ValueError(
                f"Structural spacer board {name!r} expected font_size==0.0 and "
                f"font_opacity==0.0, got font_size={board.slot.font_size!r}, "
                f"font_opacity={board.slot.font_opacity!r}"
            )
        return None

    iso2: str | None = None
    grade: FuelGrade | None = None

    if name in NON_GAS_LEGACY_BOARDS:
        iso2, grade = NON_GAS_LEGACY_BOARDS[name]
    elif name.startswith("gas_"):
        parts = name.split("_")
        if len(parts) >= 3:
            region_token = parts[1]
            grade_token = parts[-1]
            iso2 = REGION_ALIAS_TO_ISO2.get(region_token)
            grade = GRADE_SUFFIX_TO_CANONICAL.get(grade_token)

    if iso2 is None or grade is None:
        raise ValueError(
            f"Unable to deterministically classify fuel board {name!r} "
            f"(iso2={iso2!r}, grade={grade!r})"
        )

    return TotemBoardClassification(
        board_name=name,
        iso2=iso2,
        grade=grade,
        token_base=f"fp_{iso2.lower()}_{grade}",
        classification=board.classification,
    )


def classify_all_fuel_boards(baseline: FuelBoardsBaseline) -> list[TotemBoardClassification]:
    """Exhaustively classify all identifiable fuel boards in sorted deterministic order."""
    excluded_set = set(baseline.excluded_fuel_keyword_boards)
    results: list[TotemBoardClassification] = []

    for board in sorted(baseline.boards, key=lambda b: b.board_name):
        if board.board_name in excluded_set:
            raise ValueError(
                f"Excluded multi-item highway sign {board.board_name!r} must not appear in "
                "single-text fuel boards"
            )
        classified = classify_fuel_board(board)
        if classified is not None:
            results.append(classified)

    return results
