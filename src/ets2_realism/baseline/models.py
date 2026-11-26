"""Clean-room Pydantic v2 schemas for ETS2 baseline metadata."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2_realism.sii.speed_limits import VehicleSpeedLimitBlock

BoardClassification = Literal["active_fp", "placeholder", "blank"]


class BaselineManifest(BaseModel):
    """Deterministic manifest and SHA-256 inventory for an extracted ETS2 baseline."""

    model_config = ConfigDict(frozen=True)

    game_version: str
    application: str
    extractor_schema_version: int = 1
    def_entry_count: int
    locale_entry_count: int
    country_count: int
    speed_limit_count: int
    total_sign_boards: int
    fuel_board_count: int
    active_fp_board_count: int
    placeholder_or_blank_board_count: int
    excluded_fuel_keyword_boards: list[str] = Field(default_factory=list)
    locale_count: int
    tz_key_count: int
    fp_key_count: int
    dlc_country_audit: dict[str, int] = Field(default_factory=dict)
    file_sha256s: dict[str, str] = Field(default_factory=dict)


class BaselineCountry(BaseModel):
    """Clean-room structured metadata for one ``country_data`` definition."""

    model_config = ConfigDict(frozen=True)

    slug: str
    vfs_path: str
    include_path: str
    unit_name: str
    country_id: int
    name: str
    name_localized: str | None = None
    country_code: str
    iso_country_code: str
    iso_country_code_quoted: bool = False
    pos: tuple[float, float, float] | None = None
    fuel_price: float | None = None
    lights_mandatory: bool | None = None
    driving_tired_offence: bool | None = None
    imperial_units: bool | None = None
    leftside_traffic: bool | None = None
    trailer_standalone: bool | None = None
    time_zone: int | None = None
    time_zone_name: str | None = None
    secondary_time_zone_area: list[tuple[float, float, float, float]] = Field(default_factory=list)
    secondary_time_zone: list[int] = Field(default_factory=list)
    secondary_time_zone_name: list[str] = Field(default_factory=list)
    mass_limit_per_axle_count: list[int] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    region_areas: list[tuple[float, float, float, float]] = Field(default_factory=list)
    extra_attributes: dict[str, list[str]] = Field(default_factory=dict)


class CountriesBaseline(BaseModel):
    """Collection of all extracted base ``country_data`` definitions."""

    model_config = ConfigDict(frozen=True)

    countries: list[BaselineCountry] = Field(default_factory=list)


class BaselineSpeedLimit(BaseModel):
    """Structured speed-limit metadata for one country's ``speed_limits.sii``."""

    model_config = ConfigDict(frozen=True)

    slug: str
    vfs_path: str
    vehicle_classes: list[str] = Field(default_factory=list)
    has_train: bool = False
    has_tram: bool = False
    blocks: list[VehicleSpeedLimitBlock] = Field(default_factory=list)


class SpeedLimitsBaseline(BaseModel):
    """Collection of all extracted ``speed_limits.sii`` definitions."""

    model_config = ConfigDict(frozen=True)

    speed_limits: list[BaselineSpeedLimit] = Field(default_factory=list)


class FuelBoardSlot(BaseModel):
    """Metadata for the single ``sign_template_text`` slot of a fuel totem board."""

    model_config = ConfigDict(frozen=True)

    slot_index: int
    unit_name: str
    font_face: str | None = None
    font_size: float | None = None
    text_halign: str | None = None
    text_valign: str | None = None
    font_color: int | None = None
    font_opacity: float | None = None
    line_spacing: float | None = None
    letter_spacing: float | None = None
    text_id: int | None = None
    area_name: str | None = None
    area_idx: int | None = None
    coords_l: float | None = None
    coords_r: float | None = None
    coords_t: float | None = None
    coords_b: float | None = None
    z_order: int | None = None
    tag: str | None = None
    h_align: str | None = None
    v_align: str | None = None
    text: str | None = None


class FuelBoardEntry(BaseModel):
    """Discovered fuel totem sign board and its slot/localization classification."""

    model_config = ConfigDict(frozen=True)

    board_name: str
    vfs_path: str
    unit_name: str
    template_board_name: str | None = None
    width: float | None = None
    height: float | None = None
    model_name: str
    board_size: tuple[float, float] | None = None
    items_count: int
    dynamic_attributes: int | None = None
    classification: BoardClassification
    fp_key: str | None = None
    slot: FuelBoardSlot


class FuelBoardsBaseline(BaseModel):
    """Discovered fuel totem boards and excluded fuel-keyword highway signs."""

    model_config = ConfigDict(frozen=True)

    total_sign_boards: int
    excluded_fuel_keyword_boards: list[str] = Field(default_factory=list)
    boards: list[FuelBoardEntry] = Field(default_factory=list)


class LocalesBaseline(BaseModel):
    """Active locale directories and ``tz_*`` / ``fp_*`` localization key inventories."""

    model_config = ConfigDict(frozen=True)

    active_locales: list[str] = Field(default_factory=list)
    tz_keys: list[str] = Field(default_factory=list)
    fp_keys: list[str] = Field(default_factory=list)


class BaselineBundle(BaseModel):
    """Complete clean-room baseline package extracted from ETS2 archives."""

    model_config = ConfigDict(frozen=True)

    manifest: BaselineManifest
    countries: CountriesBaseline
    speed_limits: SpeedLimitsBaseline
    fuel_boards: FuelBoardsBaseline
    locales: LocalesBaseline
