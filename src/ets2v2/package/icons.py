"""Clean-room Pillow 276x162 RGB JPEG Workshop icon generator."""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont

from ets2v2.registry.models import Season

ICON_SIZE: Final[tuple[int, int]] = (276, 162)

_SUMMER_SKY_TOP: Final[tuple[int, int, int]] = (26, 76, 140)
_SUMMER_SKY_BOTTOM: Final[tuple[int, int, int]] = (242, 169, 68)
_SUMMER_GROUND: Final[tuple[int, int, int]] = (66, 112, 62)
_SUMMER_ACCENT: Final[tuple[int, int, int]] = (255, 214, 82)
_SUMMER_BADGE_BG: Final[tuple[int, int, int]] = (18, 44, 84)

_WINTER_SKY_TOP: Final[tuple[int, int, int]] = (16, 36, 68)
_WINTER_SKY_BOTTOM: Final[tuple[int, int, int]] = (146, 198, 232)
_WINTER_GROUND: Final[tuple[int, int, int]] = (224, 236, 246)
_WINTER_ACCENT: Final[tuple[int, int, int]] = (130, 220, 255)
_WINTER_BADGE_BG: Final[tuple[int, int, int]] = (12, 30, 58)

_ROAD_FILL: Final[tuple[int, int, int]] = (42, 46, 54)
_ROAD_EDGE: Final[tuple[int, int, int]] = (232, 236, 242)
_TEXT_WHITE: Final[tuple[int, int, int]] = (250, 252, 255)
_TEXT_SHADOW: Final[tuple[int, int, int]] = (10, 18, 32)


def _lerp_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    return (
        int(start[0] + (end[0] - start[0]) * t),
        int(start[1] + (end[1] - start[1]) * t),
        int(start[2] + (end[2] - start[2]) * t),
    )


def _draw_sun_emblem(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
) -> None:
    cx, cy = center
    for ray_idx in range(12):
        angle = math.radians(ray_idx * 30.0)
        x1 = round(cx + math.cos(angle) * (radius + 4))
        y1 = round(cy + math.sin(angle) * (radius + 4))
        x2 = round(cx + math.cos(angle) * (radius + 11))
        y2 = round(cy + math.sin(angle) * (radius + 11))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=color,
        outline=(255, 244, 196),
        width=2,
    )


def _draw_snowflake_emblem(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
) -> None:
    cx, cy = center
    for arm_idx in range(6):
        angle = math.radians(arm_idx * 60.0)
        ex = round(cx + math.cos(angle) * radius)
        ey = round(cy + math.sin(angle) * radius)
        draw.line([(cx, cy), (ex, ey)], fill=color, width=2)

        branch_origin_x = cx + math.cos(angle) * (radius * 0.62)
        branch_origin_y = cy + math.sin(angle) * (radius * 0.62)
        for delta_deg in (-42.0, 42.0):
            b_angle = angle + math.radians(delta_deg)
            bx = round(branch_origin_x + math.cos(b_angle) * (radius * 0.34))
            by = round(branch_origin_y + math.sin(b_angle) * (radius * 0.34))
            draw.line(
                [(round(branch_origin_x), round(branch_origin_y)), (bx, by)],
                fill=color,
                width=2,
            )
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=_TEXT_WHITE)


def _render_icon_canvas(
    edition: Season,
    *,
    season_label: str,
    meta_line_1: str,
    meta_line_2: str,
    badge_accent: tuple[int, int, int] | None = None,
    badge_ribbon: str | None = None,
) -> bytes:
    """Render a deterministic clean-room 276x162 RGB baseline JPEG icon (zero EXIF/ICC)."""
    width, height = ICON_SIZE
    horizon_y = 96

    is_summer = edition == "summer"
    sky_top = _SUMMER_SKY_TOP if is_summer else _WINTER_SKY_TOP
    sky_bottom = _SUMMER_SKY_BOTTOM if is_summer else _WINTER_SKY_BOTTOM
    ground_color = _SUMMER_GROUND if is_summer else _WINTER_GROUND
    accent_color = (
        badge_accent
        if badge_accent is not None
        else (_SUMMER_ACCENT if is_summer else _WINTER_ACCENT)
    )
    badge_bg = _SUMMER_BADGE_BG if is_summer else _WINTER_BADGE_BG

    img = Image.new("RGB", ICON_SIZE, sky_top)
    draw = ImageDraw.Draw(img)

    for y in range(horizon_y):
        t = y / max(horizon_y - 1, 1)
        row_color = _lerp_rgb(sky_top, sky_bottom, t)
        draw.line([(0, y), (width - 1, y)], fill=row_color)

    draw.rectangle((0, horizon_y, width - 1, height - 1), fill=ground_color)

    # Perspective highway trapezoid across the lower band
    road_poly: list[tuple[int, int]] = [
        (178, horizon_y),
        (222, horizon_y),
        (275, height - 1),
        (114, height - 1),
    ]
    draw.polygon(road_poly, fill=_ROAD_FILL)
    draw.line([(178, horizon_y), (114, height - 1)], fill=_ROAD_EDGE, width=2)
    draw.line([(222, horizon_y), (275, height - 1)], fill=_ROAD_EDGE, width=2)

    # Dashed center highway line
    for step in range(4):
        t0 = 0.08 + step * 0.24
        t1 = min(t0 + 0.13, 0.96)
        x0 = round(200 - 5 * t0)
        y0 = round(horizon_y + (height - horizon_y) * t0)
        x1 = round(200 - 5 * t1)
        y1 = round(horizon_y + (height - horizon_y) * t1)
        draw.line([(x0, y0), (x1, y1)], fill=accent_color, width=2)

    # Seasonal emblem on upper-right horizon
    emblem_center: tuple[int, int] = (224, 48)
    if is_summer:
        _draw_sun_emblem(draw, emblem_center, 17, accent_color)
    else:
        _draw_snowflake_emblem(draw, emblem_center, 22, _TEXT_WHITE)

    # Left typography badge panel
    draw.rounded_rectangle(
        (12, 16, 174, 146),
        radius=10,
        fill=badge_bg,
        outline=accent_color,
        width=2,
    )

    title_font: ImageFont.ImageFont | ImageFont.FreeTypeFont = ImageFont.load_default(size=24)
    sub_font: ImageFont.ImageFont | ImageFont.FreeTypeFont = ImageFont.load_default(size=17)
    meta_font: ImageFont.ImageFont | ImageFont.FreeTypeFont = ImageFont.load_default(size=13)

    draw.text((25, 29), "ETS2V2", fill=_TEXT_SHADOW, font=title_font)
    draw.text((24, 28), "ETS2V2", fill=_TEXT_WHITE, font=title_font)

    draw.line([(24, 62), (160, 62)], fill=accent_color, width=2)

    draw.text((25, 73), season_label, fill=_TEXT_SHADOW, font=sub_font)
    draw.text((24, 72), season_label, fill=accent_color, font=sub_font)

    draw.text((24, 104), meta_line_1, fill=_TEXT_WHITE, font=meta_font)
    draw.text((24, 122), meta_line_2, fill=_ROAD_EDGE, font=meta_font)

    if badge_ribbon is not None:
        ribbon_font: ImageFont.ImageFont | ImageFont.FreeTypeFont = ImageFont.load_default(size=11)
        draw.rounded_rectangle(
            (184, 128, 268, 150),
            radius=5,
            fill=badge_bg,
            outline=accent_color,
            width=2,
        )
        draw.text((192, 132), badge_ribbon, fill=accent_color, font=ribbon_font)

    # Clean outer border
    draw.rectangle((0, 0, width - 1, height - 1), outline=accent_color, width=2)

    buf = io.BytesIO()
    img.save(
        buf,
        format="JPEG",
        quality=92,
        optimize=True,
        progressive=False,
        subsampling=0,
    )
    return buf.getvalue()


def render_edition_icon_bytes(edition: Season) -> bytes:
    """Render a deterministic clean-room 276x162 RGB baseline JPEG icon (zero EXIF/ICC)."""
    season_label = "SUMMER CORE" if edition == "summer" else "WINTER CORE"
    return _render_icon_canvas(
        edition,
        season_label=season_label,
        meta_line_1="1.62 REALISM",
        meta_line_2="36 COUNTRIES",
    )


def render_promods_icon_bytes(edition: Season) -> bytes:
    """Render a deterministic clean-room 276x162 RGB JPEG icon for ProMods Editions (D-07)."""
    is_summer = edition == "summer"
    season_label = "SUMMER PM" if is_summer else "WINTER PM"
    accent = (255, 190, 56) if is_summer else (106, 232, 255)
    return _render_icon_canvas(
        edition,
        season_label=season_label,
        meta_line_1="PROMODS ED.",
        meta_line_2="EU+ME+MA+TGS",
        badge_accent=accent,
        badge_ribbon="PROMODS",
    )


def generate_all_icons(out_dir: Path) -> dict[Season, Path]:
    """Generate and write clean-room ``summer.jpg`` and ``winter.jpg`` icons into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[Season, Path] = {}
    editions: tuple[Season, Season] = ("summer", "winter")
    for edition in editions:
        target = out_dir / f"{edition}.jpg"
        target.write_bytes(render_edition_icon_bytes(edition))
        written[edition] = target
    return written


def generate_promods_icons(out_dir: Path) -> dict[Season, Path]:
    """Generate clean-room ``promods_summer.jpg`` and ``promods_winter.jpg`` icons (D-07)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[Season, Path] = {}
    editions: tuple[Season, Season] = ("summer", "winter")
    for edition in editions:
        target = out_dir / f"promods_{edition}.jpg"
        target.write_bytes(render_promods_icon_bytes(edition))
        written[edition] = target
    return written
