"""6-font SDF glyph & width-budget physics and native-currency fuel totem formatter (D-10, D-11)."""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.baseline.models import FuelBoardEntry
from ets2v2.normalize.models import CountryFuelLockEntry
from ets2v2.normalize.totem_catalog import TotemBoardClassification

TotemFormatVariant = Literal["standard", "three_dec", "compact"]

WIDTH_TOLERANCE_FACTOR: Final[float] = 1.03
SUP_SCALE_FACTOR: Final[float] = 0.65

_ALLOWED_TOTEM_CHARS: Final[frozenset[str]] = frozenset("0123456789.")
_VALID_TOTEM_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<base>[0-9]+(?:\.[0-9]+)?)(?:<sup>(?P<sup>[0-9])</sup>)?$"
)

_QUANT_INT: Final[Decimal] = Decimal("1")
_QUANT_1DEC: Final[Decimal] = Decimal("0.1")
_QUANT_2DEC: Final[Decimal] = Decimal("0.01")
_QUANT_3DEC: Final[Decimal] = Decimal("0.001")
_TEN: Final[Decimal] = Decimal("10")
_HUNDRED: Final[Decimal] = Decimal("100")

# 17 Eurozone tenth-cent markets (3-tier width routing: <sup>9</sup> / _3_ets2v2 / _c_ets2v2)
EUROZONE_TENTH_CENT_ISO2S: Final[frozenset[str]] = frozenset(
    {
        "AT",
        "BE",
        "DE",
        "EE",
        "ES",
        "FR",
        "HR",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "ME",
        "NL",
        "PT",
        "SK",
        "XK",
    }
)

# 3 Eurozone countries displaying plain 3-decimal EUR (matching vanilla 1.62 fuel_price_strings.sui)
EUROZONE_3DEC_ISO2S: Final[frozenset[str]] = frozenset({"FI", "GR", "SI"})

# 4 Core high-unit integer currencies (no fractional pump display per D-10)
INTEGER_CURRENCY_ISO2S: Final[frozenset[str]] = frozenset({"AL", "HU", "IS", "RS"})

# Extended ProMods GBP pence Crown Dependencies (GI uses 2-decimal GBP, not pence)
GBP_PENCE_ISO2S: Final[frozenset[str]] = frozenset({"GB", "GG", "IM", "JE"})

# Extended global high-unit integer currencies (ProMods + global high-unit markets)
EXTENDED_INTEGER_CURRENCY_ISO2S: Final[frozenset[str]] = frozenset(
    {
        "AM",
        "AO",
        "AR",
        "BD",
        "BF",
        "BI",
        "BJ",
        "CD",
        "CF",
        "CG",
        "CI",
        "CL",
        "CM",
        "CO",
        "CR",
        "CV",
        "DJ",
        "DZ",
        "ET",
        "GA",
        "GN",
        "GQ",
        "GW",
        "GY",
        "HT",
        "ID",
        "IQ",
        "IR",
        "JM",
        "JP",
        "KE",
        "KH",
        "KM",
        "KP",
        "KR",
        "KZ",
        "LA",
        "LB",
        "LK",
        "LR",
        "MG",
        "ML",
        "MM",
        "MN",
        "MW",
        "NC",
        "NE",
        "NG",
        "NP",
        "PF",
        "PK",
        "PY",
        "RW",
        "SD",
        "SN",
        "SO",
        "SS",
        "SY",
        "TD",
        "TG",
        "TZ",
        "UA",
        "UG",
        "UZ",
        "VN",
        "VU",
        "YE",
    }
)

# Extended 3-decimal dinar and rial markets (BHD, JOD, KWD, LYD, OMR, TND)
THREE_DEC_NATIONAL_ISO2S: Final[frozenset[str]] = frozenset({"BH", "JO", "KW", "LY", "OM", "TN"})

# Worst-case deterministic probe strings for Eurozone width-budget routing (never flaps with prices)
_PROBE_SUP_TEXT: Final[str] = "1.88<sup>9</sup>"
_PROBE_3DEC_TEXT: Final[str] = "1.889"


class GasFontMetrics(BaseModel):
    """Verified ETS2 1.62 SDF gas sign font width ratios and glyph capabilities (base.scs)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    font_face: str = Field(min_length=1)
    digit_width_ratio: float = Field(gt=0.0, allow_inf_nan=False)
    dot_width_ratio: float = Field(gt=0.0, allow_inf_nan=False)
    supports_sup: bool
    allowed_chars: frozenset[str]


# Verified against ETS2 1.62.3.3s base.scs:/font/sign/gas_*.font
GAS_FONT_METRICS: Final[dict[str, GasFontMetrics]] = {
    "gas_karnivore_lite.font": GasFontMetrics(
        font_face="gas_karnivore_lite.font",
        digit_width_ratio=0.577,
        dot_width_ratio=0.201,
        supports_sup=True,
        allowed_chars=_ALLOWED_TOTEM_CHARS,
    ),
    "gas_roadgeek_2005_mittelschrift.font": GasFontMetrics(
        font_face="gas_roadgeek_2005_mittelschrift.font",
        digit_width_ratio=0.552,
        dot_width_ratio=0.297,
        supports_sup=True,
        allowed_chars=_ALLOWED_TOTEM_CHARS,
    ),
    "gas_segment_7_standard.font": GasFontMetrics(
        font_face="gas_segment_7_standard.font",
        digit_width_ratio=0.716,
        dot_width_ratio=0.716,
        supports_sup=False,
        allowed_chars=_ALLOWED_TOTEM_CHARS,
    ),
    "gas_ds_digib.font": GasFontMetrics(
        font_face="gas_ds_digib.font",
        digit_width_ratio=0.610,
        dot_width_ratio=0.167,
        supports_sup=True,
        allowed_chars=_ALLOWED_TOTEM_CHARS,
    ),
    "gas_sign_digit.font": GasFontMetrics(
        font_face="gas_sign_digit.font",
        digit_width_ratio=0.584,
        dot_width_ratio=0.584,
        supports_sup=False,
        allowed_chars=_ALLOWED_TOTEM_CHARS,
    ),
    "gas_fundamental_brigade_schwer.font": GasFontMetrics(
        font_face="gas_fundamental_brigade_schwer.font",
        digit_width_ratio=0.704,
        dot_width_ratio=0.220,
        supports_sup=True,
        allowed_chars=_ALLOWED_TOTEM_CHARS,
    ),
}


def _resolve_font_metrics(font_face: str) -> GasFontMetrics:
    font_name = font_face.rsplit("/", 1)[-1]
    metrics = GAS_FONT_METRICS.get(font_name)
    if metrics is None:
        raise ValueError(
            f"Unknown gas font {font_face!r} (expected one of {sorted(GAS_FONT_METRICS)})"
        )
    return metrics


def compute_rendered_text_width(
    text: str,
    font_face: str,
    font_size: float,
    letter_spacing: float = 0.0,
) -> float:
    """Compute rendered width in board metres using verified 1.62 SDF font metrics."""
    if not math.isfinite(font_size) or font_size <= 0.0:
        raise ValueError(f"font_size must be finite and > 0.0, got {font_size!r}")
    if not math.isfinite(letter_spacing):
        raise ValueError(f"letter_spacing must be finite, got {letter_spacing!r}")

    metrics = _resolve_font_metrics(font_face)
    match = _VALID_TOTEM_TEXT_RE.fullmatch(text)
    if match is None:
        raise ValueError(
            f"Invalid totem display text {text!r}; expected digits, optional '.', "
            "and optional trailing <sup>[0-9]</sup>"
        )

    base = match.group("base")
    sup = match.group("sup") or ""
    n_digits = sum(1 for ch in base if ch.isdigit())
    n_dots = base.count(".")
    n_sup = len(sup)
    n_chars = n_digits + n_dots + n_sup

    glyph_width = (
        n_digits * metrics.digit_width_ratio
        + n_sup * SUP_SCALE_FACTOR * metrics.digit_width_ratio
        + n_dots * metrics.dot_width_ratio
    ) * font_size
    spacing_width = max(0, n_chars - 1) * letter_spacing
    return glyph_width + spacing_width


def verify_totem_glyph_and_width(board: FuelBoardEntry, formatted_text: str) -> list[str]:
    """Audit formatted totem text against board SDF font capabilities and width budget."""
    errors: list[str] = []

    match = _VALID_TOTEM_TEXT_RE.fullmatch(formatted_text)
    if match is None:
        return [
            f"{board.board_name}: text {formatted_text!r} violates allowed totem pattern "
            "(digits, uniform '.' decimal separator, and optional <sup>[0-9]</sup>)"
        ]

    slot = board.slot
    if (
        slot.font_face is None
        or slot.font_size is None
        or slot.coords_l is None
        or slot.coords_r is None
        or slot.letter_spacing is None
    ):
        return [f"{board.board_name}: missing baseline font/geometry attributes for width check"]

    font_name = slot.font_face.rsplit("/", 1)[-1]
    metrics = GAS_FONT_METRICS.get(font_name)
    if metrics is None:
        return [f"{board.board_name}: unknown gas font {slot.font_face!r}"]

    base = match.group("base")
    sup = match.group("sup") or ""

    if sup and not metrics.supports_sup:
        errors.append(
            f"{board.board_name}: font {font_name!r} does not support <sup> markup "
            f"({formatted_text!r})"
        )

    for ch in base + sup:
        if ch not in metrics.allowed_chars:
            errors.append(f"{board.board_name}: character {ch!r} is not supported by {font_name!r}")

    rendered_width = compute_rendered_text_width(
        formatted_text,
        slot.font_face,
        slot.font_size,
        slot.letter_spacing,
    )
    box_width = slot.coords_r - slot.coords_l
    budget = box_width * WIDTH_TOLERANCE_FACTOR
    if rendered_width > budget:
        errors.append(
            f"{board.board_name}: text {formatted_text!r} width {rendered_width:.4f} exceeds "
            f"budget {budget:.4f} (box={box_width:.4f}, font={font_name}, fs={slot.font_size})"
        )

    return errors


def format_national_pump_price(
    iso2: str,
    local_price: float,
    *,
    variant: TotemFormatVariant = "standard",
) -> str:
    """Format a native local fuel price per D-10 and D-11 using Decimal ROUND_HALF_UP."""
    if not math.isfinite(local_price) or local_price <= 0.0:
        raise ValueError(f"local_price must be finite and > 0.0 for {iso2!r}, got {local_price!r}")

    code = iso2.strip().upper()
    dec = Decimal(str(local_price))

    if code in GBP_PENCE_ISO2S:
        pence = (dec * _HUNDRED).quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP)
        return f"{pence:.1f}"

    if code == "BG":
        return f"{dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP):.2f}"

    if code in INTEGER_CURRENCY_ISO2S or code in EXTENDED_INTEGER_CURRENCY_ISO2S:
        return f"{dec.quantize(_QUANT_INT, rounding=ROUND_HALF_UP):.0f}"

    if code == "CZ":
        rounded_tenth = dec.quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP)
        if rounded_tenth < _HUNDRED:
            return f"{rounded_tenth:.2f}"
        return f"{rounded_tenth:.1f}"

    if code == "RO":
        q2 = dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP)
        if q2 < _TEN:
            return f"{q2:.2f}"
        return f"{dec.quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP):.1f}"

    if code in {"MK", "TR"}:
        q2 = dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP)
        if q2 < _HUNDRED:
            return f"{q2:.2f}"
        return f"{dec.quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP):.1f}"

    if code in EUROZONE_3DEC_ISO2S or code in THREE_DEC_NATIONAL_ISO2S:
        return f"{dec.quantize(_QUANT_3DEC, rounding=ROUND_HALF_UP):.3f}"

    if code in EUROZONE_TENTH_CENT_ISO2S:
        if variant == "compact":
            return f"{dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP):.2f}"
        q3 = dec.quantize(_QUANT_3DEC, rounding=ROUND_HALF_UP)
        if variant == "three_dec":
            return f"{q3:.3f}"
        three_dec_str = f"{q3:.3f}"
        return f"{three_dec_str[:-1]}<sup>{three_dec_str[-1]}</sup>"

    # 2-decimal national currencies (BA, CH, DK, NO, PL, RU, SE, plus CY/MT)
    return f"{dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP):.2f}"


def resolve_totem_token_and_value(
    board: FuelBoardEntry,
    classification: TotemBoardClassification,
    entry: CountryFuelLockEntry,
) -> tuple[str, str]:
    """Route a fuel board to its width-safe localization token and native formatted pump price."""
    price = entry.local_prices.get(classification.grade)
    if price is None:
        raise ValueError(
            f"Missing canonical grade {classification.grade!r} for {classification.iso2} "
            f"in prices.lock.json"
        )
    if not math.isfinite(price) or price <= 0.0:
        raise ValueError(
            f"Invalid local price {price!r} for {classification.iso2}/{classification.grade}"
        )

    slot = board.slot
    if (
        slot.font_face is None
        or slot.font_size is None
        or slot.coords_l is None
        or slot.coords_r is None
        or slot.letter_spacing is None
    ):
        raise ValueError(
            f"Board {board.board_name!r} is missing baseline font/geometry attributes "
            "required for SDF width-budget routing"
        )

    if classification.iso2 in EUROZONE_TENTH_CENT_ISO2S:
        metrics = _resolve_font_metrics(slot.font_face)
        budget = (slot.coords_r - slot.coords_l) * WIDTH_TOLERANCE_FACTOR
        if (
            metrics.supports_sup
            and compute_rendered_text_width(
                _PROBE_SUP_TEXT,
                slot.font_face,
                slot.font_size,
                slot.letter_spacing,
            )
            <= budget
        ):
            token_key = f"{classification.token_base}_ets2v2"
            formatted = format_national_pump_price(classification.iso2, price, variant="standard")
        elif (
            not metrics.supports_sup
            and compute_rendered_text_width(
                _PROBE_3DEC_TEXT,
                slot.font_face,
                slot.font_size,
                slot.letter_spacing,
            )
            <= budget
        ):
            token_key = f"{classification.token_base}_3_ets2v2"
            formatted = format_national_pump_price(classification.iso2, price, variant="three_dec")
        else:
            token_key = f"{classification.token_base}_c_ets2v2"
            formatted = format_national_pump_price(classification.iso2, price, variant="compact")
    else:
        token_key = f"{classification.token_base}_ets2v2"
        formatted = format_national_pump_price(classification.iso2, price, variant="standard")

    errors = verify_totem_glyph_and_width(board, formatted)
    if errors:
        raise ValueError(
            f"Totem glyph/width verification failed for {board.board_name!r}: {'; '.join(errors)}"
        )

    return token_key, formatted
