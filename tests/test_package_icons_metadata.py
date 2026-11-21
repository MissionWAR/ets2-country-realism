"""Unit and contract tests for clean-room 276x162 icons and Workshop/local metadata."""

from __future__ import annotations

import io
import pathlib
import re
from typing import cast

import pytest
from PIL import Image

from ets2v2.package.icons import (
    ICON_SIZE,
    generate_all_icons,
    render_edition_icon_bytes,
)
from ets2v2.package.metadata import (
    DEFAULT_AUTHOR,
    LOCAL_DISPLAY_NAMES,
    WORKSHOP_CATEGORIES,
    render_description_txt,
    render_manifest_sii,
    render_versions_sii,
)
from ets2v2.registry.models import Season
from ets2v2.sii.document import SiiDocument
from ets2v2.sii.hygiene import validate_sii_hygiene
from ets2v2.sii.lexer import parse_sii_bool, unquote_sii_string

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS_ICONS_DIR = REPO_ROOT / "assets" / "icons"
MAX_SCS_FILE_BYTES = 1_048_576


def _assert_valid_clean_room_jpeg(raw: bytes) -> None:
    assert 0 < len(raw) < MAX_SCS_FILE_BYTES
    assert raw.startswith(b"\xff\xd8")
    assert raw.endswith(b"\xff\xd9")

    with Image.open(io.BytesIO(raw)) as verify_img:
        verify_img.verify()

    with Image.open(io.BytesIO(raw)) as img:
        img.load()
        assert img.format == "JPEG"
        assert img.mode == "RGB"
        assert img.size == ICON_SIZE == (276, 162)
        assert len(img.getexif()) == 0
        info = cast(dict[str, object], img.info)
        assert "icc_profile" not in info
        assert "exif" not in info
        assert not info.get("progressive", False)


def test_render_edition_icon_bytes_clean_room_and_distinct() -> None:
    summer_bytes = render_edition_icon_bytes("summer")
    winter_bytes = render_edition_icon_bytes("winter")

    _assert_valid_clean_room_jpeg(summer_bytes)
    _assert_valid_clean_room_jpeg(winter_bytes)
    assert summer_bytes != winter_bytes
    assert summer_bytes == render_edition_icon_bytes("summer")
    assert winter_bytes == render_edition_icon_bytes("winter")


def test_generate_all_icons_writes_expected_files(tmp_path: pathlib.Path) -> None:
    written = generate_all_icons(tmp_path)
    assert set(written.keys()) == {"summer", "winter"}
    for edition, path in written.items():
        assert path == tmp_path / f"{edition}.jpg"
        assert path.is_file()
        _assert_valid_clean_room_jpeg(path.read_bytes())


@pytest.mark.parametrize("edition", ["summer", "winter"])
def test_committed_assets_icons_exist_and_are_clean(edition: Season) -> None:
    icon_path = ASSETS_ICONS_DIR / f"{edition}.jpg"
    assert icon_path.is_file(), f"Missing committed clean-room icon: {icon_path}"
    _assert_valid_clean_room_jpeg(icon_path.read_bytes())


def test_committed_icons_are_distinct() -> None:
    summer = (ASSETS_ICONS_DIR / "summer.jpg").read_bytes()
    winter = (ASSETS_ICONS_DIR / "winter.jpg").read_bytes()
    assert summer != winter


def test_render_versions_sii_hygiene_and_structure() -> None:
    raw = render_versions_sii()
    assert validate_sii_hygiene(raw, require_siinunit=True) == []
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw

    doc = SiiDocument.parse(raw, require_siinunit=True)
    units = doc.find_units(class_name="package_version_info")
    assert len(units) == 1
    unit = units[0]
    assert unit.unit_name == ".universal"
    pkg_name_attr = unit.get_scalar("package_name")
    assert pkg_name_attr is not None
    assert unquote_sii_string(pkg_name_attr.raw_value) == ("universal", True)
    assert unit.get_attributes("compatible_versions") == []


@pytest.mark.parametrize("edition", ["summer", "winter"])
def test_render_manifest_sii_workshop_mode_omits_forbidden_fields(edition: Season) -> None:
    raw = render_manifest_sii(edition, "1.62-2026.47", workshop=True)
    assert validate_sii_hygiene(raw, require_siinunit=True) == []
    text = raw.decode("utf-8")
    assert "display_name" not in text
    assert "compatible_versions" not in text

    doc = SiiDocument.parse(raw, require_siinunit=True)
    units = doc.find_units(class_name="mod_package")
    assert len(units) == 1
    unit = units[0]
    assert unit.unit_name == ".package_name"

    pkg_ver = unit.get_scalar("package_version")
    author = unit.get_scalar("author")
    icon = unit.get_scalar("icon")
    desc = unit.get_scalar("description_file")
    mp_opt = unit.get_scalar("mp_mod_optional")
    assert pkg_ver is not None and unquote_sii_string(pkg_ver.raw_value) == ("1.62-2026.47", True)
    assert author is not None and unquote_sii_string(author.raw_value) == (DEFAULT_AUTHOR, True)
    assert icon is not None and unquote_sii_string(icon.raw_value) == ("mod_icon.jpg", True)
    assert desc is not None and unquote_sii_string(desc.raw_value) == ("description.txt", True)
    assert mp_opt is not None and parse_sii_bool(mp_opt.raw_value) is True

    categories = [unquote_sii_string(a.raw_value)[0] for a in unit.get_attributes("category")]
    assert tuple(categories) == WORKSHOP_CATEGORIES == ("other", "ai_traffic")
    assert unit.get_scalar("display_name") is None
    assert unit.get_attributes("compatible_versions") == []


@pytest.mark.parametrize("edition", ["summer", "winter"])
def test_render_manifest_sii_local_mode_includes_display_name_only(edition: Season) -> None:
    raw = render_manifest_sii(edition, "1.62-2026.47", workshop=False, author="Custom Author")
    assert validate_sii_hygiene(raw, require_siinunit=True) == []
    text = raw.decode("utf-8")
    assert "compatible_versions" not in text

    doc = SiiDocument.parse(raw, require_siinunit=True)
    unit = doc.get_unit(class_name="mod_package")
    assert unit is not None
    display_name = unit.get_scalar("display_name")
    author = unit.get_scalar("author")
    assert display_name is not None
    assert unquote_sii_string(display_name.raw_value) == (LOCAL_DISPLAY_NAMES[edition], True)
    assert author is not None
    assert unquote_sii_string(author.raw_value) == ("Custom Author", True)


@pytest.mark.parametrize("bad_input", ["", "   ", "bad\\author", "bad\x00author"])
def test_render_manifest_sii_rejects_invalid_author_or_version(bad_input: str) -> None:
    with pytest.raises(ValueError):
        render_manifest_sii("summer", "1.62-2026.47", workshop=True, author=bad_input)
    with pytest.raises(ValueError):
        render_manifest_sii("summer", bad_input, workshop=True)


@pytest.mark.parametrize("edition", ["summer", "winter"])
def test_render_description_txt_hygiene_attribution_and_no_volatile_tokens(
    edition: Season,
) -> None:
    raw = render_description_txt(edition)
    assert 0 < len(raw) < MAX_SCS_FILE_BYTES
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw == render_description_txt(edition)

    text = raw.decode("utf-8")
    assert "MIT" in text
    assert "CC BY 4.0" in text
    assert "36" in text
    assert "1.62" in text
    assert edition.capitalize() in text
    assert "Zero-DDS" in text
    assert "43" in text

    # D-16 complete open-data source & license attributions
    required_attributions = (
        "EC Weekly Oil Bulletin CC BY 4.0",
        "fuel-prices.eu CC BY 4.0",
        "UK DESNZ OGL v3",
        "Norway SSB CC BY 4.0",
        "France Licence Ouverte",
        "Italy MIMIT IODL 2.0",
        "Spain MITECO",
        "Netherlands CBS",
        "Germany Tankerkönig CC BY 4.0",
        "Frankfurter v2 MIT",
        "ECB",
        "fawazahmed0 CC0",
    )
    for attribution in required_attributions:
        assert attribution in text, f"Missing D-16 attribution in description.txt: {attribution!r}"

    # Must NOT embed volatile ISO dates or ISO-week package_version strings (TRAP 4)
    assert re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text) is None
    assert re.search(r"1\.62-\d{4}\.\d{2}", text) is None
