"""Clean-room ETS2 baseline metadata schemas and extraction pipeline."""

from __future__ import annotations

from ets2v2.baseline.extractor import (
    DEFAULT_ETS2_GAME_DIR,
    EXTRACTOR_SCHEMA_VERSION,
    extract_baseline,
    resolve_game_dir,
    verify_baseline_bundle,
    write_baseline_bundle,
)
from ets2v2.baseline.models import (
    BaselineBundle,
    BaselineCountry,
    BaselineManifest,
    BaselineSpeedLimit,
    BoardClassification,
    CountriesBaseline,
    FuelBoardEntry,
    FuelBoardsBaseline,
    FuelBoardSlot,
    LocalesBaseline,
    SpeedLimitsBaseline,
)

__all__ = [
    "DEFAULT_ETS2_GAME_DIR",
    "EXTRACTOR_SCHEMA_VERSION",
    "BaselineBundle",
    "BaselineCountry",
    "BaselineManifest",
    "BaselineSpeedLimit",
    "BoardClassification",
    "CountriesBaseline",
    "FuelBoardEntry",
    "FuelBoardSlot",
    "FuelBoardsBaseline",
    "LocalesBaseline",
    "SpeedLimitsBaseline",
    "extract_baseline",
    "resolve_game_dir",
    "verify_baseline_bundle",
    "write_baseline_bundle",
]
