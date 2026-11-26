"""Package-independent Offline SCS Workshop Validator for unpacked roots and local ZIPs."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Final

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from ets2v2.baseline.models import (
    CountriesBaseline,
    FuelBoardsBaseline,
    LocalesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.sii.country import CountryDataModel, parse_country_data
from ets2v2.sii.document import SiiDocument
from ets2v2.sii.hygiene import (
    SiiEncodingError,
    validate_sii_hygiene,
    validate_string_path_hygiene,
    validate_unit_name_segments,
)
from ets2v2.sii.lexer import parse_sii_bool, unquote_sii_string
from ets2v2.sii.localization import LocalizationEntry, parse_localization_db
from ets2v2.sii.sign_board import SignBoardTemplate, parse_sign_board
from ets2v2.sii.speed_limits import SpeedLimitsFile, parse_speed_limits
from ets2v2.validate.invariants import (
    check_license_taint_bytes,
    validate_combo_invariants,
    validate_core_realism_invariants,
    validate_fuel_locale_modules_consistency,
    validate_promods_locale_modules_consistency,
    validate_promods_realism_invariants,
    validate_totem_invariants,
)
from ets2v2.validate.models import PackageProfile, ValidationCollector, ValidationReport
from ets2v2.vfs.dir_archive import DirectoryArchive
from ets2v2.vfs.types import (
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsArchive,
    detect_3nk,
    normalize_vfs_path,
)
from ets2v2.vfs.zip_archive import ZipArchive

VALID_SCS_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "truck",
        "trailer",
        "interior",
        "tuning_parts",
        "ai_traffic",
        "sound",
        "paint_job",
        "cargo_pack",
        "map",
        "ui",
        "weather_setup",
        "physics",
        "graphics",
        "models",
        "movers",
        "walkers",
        "prefabs",
        "other",
    }
)
ALLOWED_MANIFEST_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "package_version",
        "display_name",
        "author",
        "category",
        "icon",
        "description_file",
        "compatible_versions",
        "dlc_dependencies",
        "mp_mod_optional",
    }
)
FORBIDDEN_TOTEM_EXTENSIONS: Final[frozenset[str]] = frozenset({".dds", ".tobj"})
ALLOWED_SCS_ASSET_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".sii",
        ".sui",
        ".txt",
        ".jpg",
        ".mat",
        ".pmd",
        ".pmg",
        ".pmc",
        ".pma",
        ".ppd",
        ".ogg",
        ".bank",
        ".guids",
        ".soundref",
        ".font",
        ".mask",
        ".sbd",
    }
)
FORBIDDEN_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".aux",
        ".base",
        ".data",
        ".desc",
        ".layer",
        ".py",
        ".pyc",
        ".json",
        ".md",
        ".yaml",
        ".yml",
        ".toml",
        ".sh",
        ".ps1",
        ".bat",
        ".exe",
        ".dll",
    }
)
MAX_ICON_BYTES: Final[int] = 1_048_576
MAX_DESCRIPTION_BYTES: Final[int] = 1_048_576
MAX_ICON_PIXELS: Final[int] = 4_000_000
REQUIRED_ICON_SIZE: Final[tuple[int, int]] = (276, 162)

EXPECTED_CORE_COUNTRY_SLUGS: Final[frozenset[str]] = frozenset(
    {
        "albania",
        "austria",
        "belgium",
        "bosnia",
        "bulgaria",
        "croatia",
        "czech",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "iceland",
        "italy",
        "kosovo",
        "latvia",
        "lithuania",
        "luxembourg",
        "macedonia",
        "montenegro",
        "netherlands",
        "norway",
        "poland",
        "portugal",
        "romania",
        "russia",
        "serbia",
        "slovakia",
        "slovenia",
        "spain",
        "sweden",
        "switzerland",
        "turkey",
        "uk",
    }
)

_PACKAGE_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]{1,256}$")
_COUNTRY_SII_RE: Final[re.Pattern[str]] = re.compile(r"^def/country(?:\.[^/]+)?\.sii$")
_COUNTRY_SUI_RE: Final[re.Pattern[str]] = re.compile(r"^def/country/([a-z0-9_]+)\.sui$")
_COUNTRY_SII_FRAGMENT_RE: Final[re.Pattern[str]] = re.compile(r"^def/country/([a-z0-9_]+)\.sii$")
_SPEED_LIMITS_RE: Final[re.Pattern[str]] = re.compile(
    r"^def/country/([a-z0-9_]+)/speed_limits\.sii$"
)
_SIGN_BOARD_RE: Final[re.Pattern[str]] = re.compile(r"^def/sign/board/([a-z0-9_]+)\.sii$")
_FUEL_LOCALE_RE: Final[re.Pattern[str]] = re.compile(
    r"^locale/([^/]+)/local_module\.ets2v2_fuel\.sii$"
)
_PROMODS_FUEL_LOCALE_RE: Final[re.Pattern[str]] = re.compile(
    r"^locale/([^/]+)/local_module\.(pm_fuel|pm_me_fuel|pm_tgs_fuel)\.sii$"
)
_LOCALE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z]{2}_[a-z]{2}$")
_WINDOWS_DRIVE_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:")
_REQUIRED_VEHICLE_CLASSES: Final[frozenset[str]] = frozenset({"car", "truck", "bus"})


def _load_optional_baselines(
    baseline_dir: Path | None,
) -> tuple[
    CountriesBaseline | None,
    SpeedLimitsBaseline | None,
    LocalesBaseline | None,
    FuelBoardsBaseline | None,
]:
    if baseline_dir is None:
        return None, None, None, None
    bl_countries = CountriesBaseline.model_validate_json(
        (baseline_dir / "countries.json").read_text("utf-8")
    )
    bl_speeds = SpeedLimitsBaseline.model_validate_json(
        (baseline_dir / "speed_limits.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (baseline_dir / "locales.json").read_text("utf-8")
    )
    bl_fuel_boards = FuelBoardsBaseline.model_validate_json(
        (baseline_dir / "fuel_boards.json").read_text("utf-8")
    )
    return bl_countries, bl_speeds, bl_locales, bl_fuel_boards


def _has_unsafe_raw_path(raw_path: str) -> str | None:
    if "\x00" in raw_path:
        return "Path contains NUL byte"
    if "\\" in raw_path:
        return "Windows backslash separator '\\' is not allowed"
    if raw_path.startswith("/"):
        return "Leading '/' absolute archive path is not allowed"
    if _WINDOWS_DRIVE_RE.match(raw_path) is not None:
        return "Windows drive prefix is not allowed in archive path"
    segments = raw_path.split("/")
    if any(seg == ".." for seg in segments):
        return "Parent directory traversal '..' is not allowed"
    return None


def _detect_unsupported_binary_magic(raw: bytes) -> str | None:
    if raw.startswith(b"SCS#"):
        return "HashFS binary archive ('SCS#') is not supported"
    if raw.startswith(b"AEM!"):
        return "Encrypted/protected 'AEM!' archive payload is not supported"
    return None


def _detect_non_jpeg_image_format(raw: bytes) -> str | None:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "GIF"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "WEBP"
    if raw.startswith(b"BM"):
        return "BMP"
    if raw.startswith((b"II*\x00", b"MM\x00*")):
        return "TIFF"
    return None


def _record_sii_hygiene(
    raw: bytes,
    rel_path: str,
    *,
    require_siinunit: bool,
    collector: ValidationCollector,
) -> bool:
    """Run ``validate_sii_hygiene`` and emit mapped SCS codes; return True when clean."""
    if detect_3nk(raw):
        collector.error("00004", rel_path, "3nK\\x01 obfuscated SII/SUI payload is not allowed")
        return False

    magic_err = _detect_unsupported_binary_magic(raw)
    if magic_err is not None:
        collector.error("00007", rel_path, magic_err)
        return False

    diags = validate_sii_hygiene(raw, require_siinunit=require_siinunit)
    for diag in diags:
        if diag.code in {"path_backslash", "path_parent_traversal"}:
            code = "00003"
        elif diag.code in {"unit_segment_invalid", "unit_segment_too_long"}:
            code = "00007"
        else:
            code = "00004"
        collector.error(
            code,
            rel_path,
            f"{diag.code} at {diag.line}:{diag.column}: {diag.message}",
        )
    return not diags


def _validate_utf8_lf_text(
    raw: bytes,
    rel_path: str,
    collector: ValidationCollector,
    *,
    max_bytes: int = MAX_DESCRIPTION_BYTES,
) -> None:
    """Validate UTF-8 no-BOM LF text hygiene and size bounds for description files."""
    if len(raw) > max_bytes:
        collector.error(
            "00009",
            rel_path,
            f"Text file size {len(raw)} bytes exceeds {max_bytes} byte limit",
        )
        return

    if detect_3nk(raw):
        collector.error("00004", rel_path, "3nK\\x01 obfuscated payload is not allowed")
        return

    if raw.startswith(b"\xef\xbb\xbf"):
        collector.error("00004", rel_path, "UTF-8 BOM (0xEF 0xBB 0xBF) is not allowed")
    if b"\r" in raw:
        collector.error("00004", rel_path, "CR/CRLF line endings are not allowed; use LF ('\\n')")

    payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        collector.error("00004", rel_path, f"Invalid UTF-8 byte sequence: {exc}")


def _is_dir_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction()) if callable(is_junction) else False


def _is_unsafe_root_link(path: Path, resolved_root: Path) -> bool:
    if path.is_symlink() or _is_dir_junction(path):
        return True
    try:
        resolved = path.resolve()
    except OSError:
        return True
    return not resolved.is_relative_to(resolved_root)


def _validate_icon_bytes(
    raw: bytes,
    rel_path: str,
    collector: ValidationCollector,
) -> None:
    """Verify JPEG icon bounds, SOI/EOI markers, baseline RGB format, and exact 276x162 size."""
    if len(raw) > MAX_ICON_BYTES:
        collector.error(
            "00009",
            rel_path,
            f"Icon size {len(raw)} bytes exceeds {MAX_ICON_BYTES} byte limit",
        )
        return

    non_jpeg = _detect_non_jpeg_image_format(raw)
    if non_jpeg is not None:
        collector.error(
            "00007",
            rel_path,
            f"Unsupported icon format {non_jpeg!r} renamed as .jpg; expected JPEG",
        )
        return

    has_jpeg_soi = raw.startswith(b"\xff\xd8")
    has_jpeg_eoi = raw.rstrip(b"\x00").endswith(b"\xff\xd9")

    try:
        with Image.open(io.BytesIO(raw)) as img:
            fmt = img.format
            size = img.size
            mode = img.mode
            is_progressive = bool(img.info.get("progressive") or img.info.get("progression"))
    except Image.DecompressionBombError as exc:
        collector.error("00009", rel_path, f"Icon exceeds pixel safety cap: {exc}")
        return
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        collector.error("00004", rel_path, f"Malformed or truncated JPEG icon: {exc}")
        return

    if fmt != "JPEG":
        collector.error("00007", rel_path, f"Unsupported icon format {fmt!r}; expected JPEG")
        return
    if not (has_jpeg_soi and has_jpeg_eoi):
        collector.error(
            "00004",
            rel_path,
            "Malformed JPEG icon: missing required SOI (FFD8) or EOI (FFD9) markers",
        )
        return
    if size[0] * size[1] > MAX_ICON_PIXELS:
        collector.error(
            "00009",
            rel_path,
            f"Icon dimensions {size[0]}x{size[1]} ({size[0] * size[1]} pixels) exceed "
            f"{MAX_ICON_PIXELS} pixel safety cap",
        )
        return
    if mode != "RGB":
        collector.error(
            "00007",
            rel_path,
            f"Unsupported JPEG icon color mode {mode!r}; expected baseline 'RGB'",
        )
        return
    if is_progressive:
        collector.error(
            "00007",
            rel_path,
            "Progressive JPEG icons are not supported; use baseline RGB JPEG",
        )
        return
    if size != REQUIRED_ICON_SIZE:
        collector.error(
            "00001",
            rel_path,
            f"Icon dimensions {size[0]}x{size[1]} do not match required 276x162",
        )
        return

    try:
        with Image.open(io.BytesIO(raw)) as verify_img:
            verify_img.verify()
        with Image.open(io.BytesIO(raw)) as decoded:
            decoded.load()
    except Image.DecompressionBombError as exc:
        collector.error("00009", rel_path, f"Icon exceeds pixel safety cap: {exc}")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        collector.error("00004", rel_path, f"Malformed or truncated JPEG icon: {exc}")


def _inspect_raw_zip(
    zip_path: Path,
    *,
    prefix: str,
    collector: ValidationCollector,
) -> bool:
    """Inspect raw ``zipfile.ZipFile.infolist()`` BEFORE VFS path normalization (T-02-09)."""
    rel_prefix = f"{prefix}/" if prefix else ""

    try:
        with zip_path.open("rb") as fh:
            header = fh.read(4)
    except PermissionError as exc:
        collector.error("00006", str(zip_path), f"Access denied reading archive: {exc}")
        return False
    except OSError as exc:
        collector.error("00008", str(zip_path), f"Unable to open archive: {exc}")
        return False

    magic_err = _detect_unsupported_binary_magic(header)
    if magic_err is not None:
        collector.error("00007", str(zip_path), magic_err)
        return False

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = zf.infolist()
    except PermissionError as exc:
        collector.error("00006", str(zip_path), f"Access denied opening ZIP archive: {exc}")
        return False
    except (zipfile.BadZipFile, OSError) as exc:
        collector.error("00008", str(zip_path), f"Corrupt or unreadable ZIP archive: {exc}")
        return False

    seen_norm: set[str] = set()
    for info in infos:
        raw_name = info.filename
        display_path = f"{rel_prefix}{raw_name}"
        unsafe_reason = _has_unsafe_raw_path(raw_name)
        if unsafe_reason is not None:
            collector.error(
                "00003",
                display_path,
                f"Unsafe raw ZIP entry name {raw_name!r}: {unsafe_reason}",
            )
        else:
            is_dir = info.is_dir()
            try:
                norm = normalize_vfs_path(raw_name, allow_empty=is_dir)
            except ValueError as exc:
                collector.error(
                    "00003",
                    display_path,
                    f"Non-canonical raw ZIP entry name {raw_name!r}: {exc}",
                )
            else:
                expected_raw = f"{norm}/" if is_dir else norm
                if not norm or raw_name != expected_raw:
                    collector.error(
                        "00003",
                        display_path,
                        f"Non-canonical ZIP entry path {raw_name!r} (expected {expected_raw!r})",
                    )
                if not is_dir and norm:
                    if norm in seen_norm:
                        collector.error(
                            "00003",
                            display_path,
                            f"Duplicate normalized ZIP entry {norm!r} (raw {raw_name!r})",
                        )
                    else:
                        seen_norm.add(norm)
        if info.flag_bits & 0x41:
            collector.error(
                "00007",
                display_path,
                "Encrypted ZIP entry (flag_bits & 0x41) is not supported",
            )
        if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            collector.error(
                "00007",
                display_path,
                f"Unsupported ZIP compression method {info.compress_type}",
            )
    return True


def _map_archive_diagnostics(
    archive: VfsArchive,
    *,
    prefix: str,
    collector: ValidationCollector,
) -> None:
    rel_prefix = f"{prefix}/" if prefix else ""
    for diag in archive.diagnostics:
        entry_loc = (
            f"{rel_prefix}{diag.entry_path}" if diag.entry_path else (prefix or str(archive.path))
        )
        if diag.kind == "path_traversal":
            collector.error("00003", entry_loc, diag.detail)
        elif diag.kind == "three_nk_obfuscated":
            collector.error("00004", entry_loc, diag.detail)
        elif diag.kind == "corrupt_archive":
            collector.error("00008", entry_loc, diag.detail)
        else:
            collector.error("00007", entry_loc, diag.detail)


def _is_valid_localized_description(
    vfs_path: str,
    desc_name: str,
    valid_locales: frozenset[str] | None,
) -> bool:
    if "/" in vfs_path or not vfs_path.lower().endswith(".txt"):
        return False
    if vfs_path == desc_name:
        return True
    stem = desc_name[:-4] if desc_name.lower().endswith(".txt") else desc_name
    prefix = f"{stem}."
    if not vfs_path.startswith(prefix):
        return False
    locale_part = vfs_path[len(prefix) : -4]
    if valid_locales is not None:
        return locale_part in valid_locales
    return _LOCALE_CODE_RE.fullmatch(locale_part) is not None


def _read_archive_entry(
    archive: VfsArchive,
    vfs_path: str,
    display_path: str,
    collector: ValidationCollector,
) -> bytes | None:
    try:
        return archive.read_bytes(vfs_path)
    except PermissionError as exc:
        collector.error("00006", display_path, f"Access denied reading {vfs_path!r}: {exc}")
        return None
    except (ProtectedPayloadError, UnsupportedCompressionError) as exc:
        collector.error("00007", display_path, str(exc))
        return None
    except (FileNotFoundError, OSError, ValueError) as exc:
        collector.error("00008", display_path, f"Unable to load {vfs_path!r}: {exc}")
        return None


def _validate_manifest(
    archive: VfsArchive,
    *,
    prefix: str,
    workshop_mode: bool,
    collector: ValidationCollector,
) -> tuple[str | None, str | None]:
    """Validate ``manifest.sii`` and return ``(icon_name, description_file)`` if declared."""
    rel_prefix = f"{prefix}/" if prefix else ""
    manifest_loc = f"{rel_prefix}manifest.sii"

    if not archive.exists("manifest.sii"):
        collector.error("00002", manifest_loc, "Missing required manifest.sii at package root")
        return None, None

    manifest_raw = _read_archive_entry(archive, "manifest.sii", manifest_loc, collector)
    if manifest_raw is None:
        return None, None

    check_license_taint_bytes(manifest_raw, manifest_loc, collector)

    _record_sii_hygiene(
        manifest_raw,
        manifest_loc,
        require_siinunit=True,
        collector=collector,
    )

    try:
        manifest_doc = SiiDocument.parse(manifest_raw, require_siinunit=True)
    except SiiEncodingError as exc:
        collector.error("00004", manifest_loc, str(exc))
        return None, None

    for unit in manifest_doc.units:
        if unit.class_name != "mod_package":
            collector.error(
                "00003",
                manifest_loc,
                f"Disallowed unit class {unit.class_name!r} in manifest.sii; "
                "only 'mod_package' is allowed",
            )

    mod_units = manifest_doc.find_units(class_name="mod_package")
    if len(mod_units) != 1:
        collector.error(
            "00001",
            manifest_loc,
            f"Expected exactly 1 mod_package unit in manifest.sii, found {len(mod_units)}",
        )
        return None, None

    mod_unit = mod_units[0]
    for diag in validate_unit_name_segments(
        mod_unit.unit_name,
        line=mod_unit.unit_name_line,
        column=mod_unit.unit_name_column,
    ):
        collector.error("00007", manifest_loc, diag.message)

    # Check unknown attributes & Workshop-disallowed attributes
    for attr in mod_unit.attributes:
        if attr.key not in ALLOWED_MANIFEST_ATTRS:
            collector.warning(
                "WARN 00002",
                manifest_loc,
                f"Unknown or unused mod_package attribute {attr.key!r}",
            )

    for dn_attr in mod_unit.get_attributes("display_name"):
        dn_val, dn_quoted = unquote_sii_string(dn_attr.raw_value)
        if not dn_quoted:
            collector.error(
                "00004",
                manifest_loc,
                "Attribute 'display_name' in mod_package must be a quoted string literal",
            )
        elif not dn_val.strip():
            collector.error(
                "00005",
                manifest_loc,
                "Attribute 'display_name' in mod_package must not be empty",
            )

    if workshop_mode:
        if mod_unit.get_attributes("display_name"):
            collector.warning(
                "WARN 00001",
                manifest_loc,
                "display_name must be omitted from Steam Workshop manifest.sii",
            )
        if mod_unit.get_attributes("compatible_versions"):
            collector.error(
                "00010",
                manifest_loc,
                "compatible_versions[] is not allowed in Steam Workshop manifest.sii",
            )
            collector.warning(
                "WARN 00002",
                manifest_loc,
                "Unused field compatible_versions[] set in Workshop manifest.sii",
            )

    # Required scalar attributes
    for req_key in ("package_version", "author"):
        scalar = mod_unit.get_scalar(req_key)
        if scalar is None:
            collector.error(
                "00005",
                manifest_loc,
                f"Missing required non-empty attribute {req_key!r} in mod_package",
            )
        else:
            req_val, req_quoted = unquote_sii_string(scalar.raw_value)
            if not req_quoted:
                collector.error(
                    "00004",
                    manifest_loc,
                    f"Attribute {req_key!r} in mod_package must be a quoted string literal",
                )
            elif not req_val.strip():
                collector.error(
                    "00005",
                    manifest_loc,
                    f"Missing required non-empty attribute {req_key!r} in mod_package",
                )

    # mp_mod_optional: true required
    mp_attr = mod_unit.get_scalar("mp_mod_optional")
    if mp_attr is None:
        collector.error(
            "00005",
            manifest_loc,
            "Missing required attribute 'mp_mod_optional: true' in mod_package",
        )
    else:
        try:
            mp_val = parse_sii_bool(mp_attr.raw_value)
        except ValueError as exc:
            collector.error("00004", manifest_loc, f"Invalid mp_mod_optional boolean: {exc}")
        else:
            if not mp_val:
                collector.error(
                    "00005",
                    manifest_loc,
                    "mp_mod_optional must be true for Core realism packages",
                )

    # category[] checks: array syntax, quoted strings, unique, 1..2 entries in 18 valid categories
    cat_attrs = mod_unit.get_attributes("category")
    if not cat_attrs:
        collector.error(
            "00005",
            manifest_loc,
            "Missing required category[] attribute in mod_package",
        )
    else:
        seen_categories: set[str] = set()
        for attr in cat_attrs:
            if not (attr.is_append or attr.index is not None):
                collector.error(
                    "00004",
                    manifest_loc,
                    "Attribute 'category' must use array syntax 'category[]' in mod_package",
                )
            cat, cat_quoted = unquote_sii_string(attr.raw_value)
            if not cat_quoted:
                collector.error(
                    "00004",
                    manifest_loc,
                    "Attribute 'category[]' in mod_package must be a quoted string literal",
                )
                continue
            if cat not in VALID_SCS_CATEGORIES:
                collector.error(
                    "00005",
                    manifest_loc,
                    f"Invalid SCS category {cat!r}; must be one of the 18 official SCS categories",
                )
            elif cat in seen_categories:
                collector.error(
                    "00003",
                    manifest_loc,
                    f"Duplicate category[] entry {cat!r} in mod_package",
                )
            else:
                seen_categories.add(cat)
        if len(cat_attrs) > 2:
            collector.warning(
                "WARN 00001",
                manifest_loc,
                f"Too many category[] entries ({len(cat_attrs)}); SCS allows at most 2",
            )

    # icon attribute checks
    icon_name: str | None = None
    icon_attr = mod_unit.get_scalar("icon")
    if icon_attr is None:
        collector.error("00005", manifest_loc, "Missing required 'icon' attribute in mod_package")
    else:
        raw_icon, icon_quoted = unquote_sii_string(icon_attr.raw_value)
        if not icon_quoted:
            collector.error(
                "00004",
                manifest_loc,
                "Attribute 'icon' in mod_package must be a quoted string literal",
            )
        elif not raw_icon.strip():
            collector.error(
                "00005", manifest_loc, "Missing required 'icon' attribute in mod_package"
            )
        else:
            for diag in validate_string_path_hygiene(
                icon_attr.raw_value,
                key="icon",
                line=icon_attr.line,
            ):
                collector.error("00003", manifest_loc, diag.message)
            if "/" in raw_icon or "\\" in raw_icon:
                collector.error(
                    "00001",
                    manifest_loc,
                    f"icon {raw_icon!r} must be a filename in the same directory as manifest.sii",
                )
            elif not raw_icon.lower().endswith(".jpg"):
                collector.error(
                    "00001",
                    manifest_loc,
                    f"icon {raw_icon!r} must use the .jpg extension",
                )
            else:
                icon_name = raw_icon
                icon_loc = f"{rel_prefix}{icon_name}"
                if not archive.exists(icon_name):
                    collector.error("00002", icon_loc, f"Declared icon {icon_name!r} not found")
                else:
                    icon_raw = _read_archive_entry(archive, icon_name, icon_loc, collector)
                    if icon_raw is not None:
                        _validate_icon_bytes(icon_raw, icon_loc, collector)

    # description_file attribute checks
    desc_name: str | None = None
    desc_attr = mod_unit.get_scalar("description_file")
    if desc_attr is None:
        collector.error(
            "00005",
            manifest_loc,
            "Missing required 'description_file' attribute in mod_package",
        )
    else:
        raw_desc, desc_quoted = unquote_sii_string(desc_attr.raw_value)
        if not desc_quoted:
            collector.error(
                "00004",
                manifest_loc,
                "Attribute 'description_file' in mod_package must be a quoted string literal",
            )
        elif not raw_desc.strip():
            collector.error(
                "00005",
                manifest_loc,
                "Missing required 'description_file' attribute in mod_package",
            )
        else:
            for diag in validate_string_path_hygiene(
                desc_attr.raw_value,
                key="description_file",
                line=desc_attr.line,
            ):
                collector.error("00003", manifest_loc, diag.message)
            if "/" in raw_desc or "\\" in raw_desc:
                collector.error(
                    "00001",
                    manifest_loc,
                    f"description_file {raw_desc!r} must be a filename beside manifest.sii",
                )
            elif not raw_desc.lower().endswith(".txt"):
                collector.error(
                    "00001",
                    manifest_loc,
                    f"description_file {raw_desc!r} must use the .txt extension",
                )
            else:
                desc_name = raw_desc
                desc_loc = f"{rel_prefix}{desc_name}"
                if not archive.exists(desc_name):
                    collector.error(
                        "00002",
                        desc_loc,
                        f"Declared description_file {desc_name!r} not found",
                    )
                else:
                    desc_raw = _read_archive_entry(archive, desc_name, desc_loc, collector)
                    if desc_raw is not None:
                        _validate_utf8_lf_text(desc_raw, desc_loc, collector)
                        check_license_taint_bytes(desc_raw, desc_loc, collector)

    return icon_name, desc_name


def _validate_country_required_fields(
    model: CountryDataModel,
    display_path: str,
    collector: ValidationCollector,
    *,
    profile: PackageProfile = "core",
) -> None:
    if model.country_id <= 0:
        collector.error("00005", display_path, "Missing or invalid positive country_id")
    if not model.name:
        collector.error("00005", display_path, "Missing required country name")
    if not model.country_code:
        collector.error("00005", display_path, "Missing required country_code")
    if profile == "core" and not model.iso_country_code:
        collector.error("00005", display_path, "Missing required iso_country_code")
    if profile == "combo":
        if (model.time_zone is None) != (model.time_zone_name is None):
            collector.error(
                "00005",
                display_path,
                "time_zone and time_zone_name must either both be present or both omitted",
            )
    elif model.time_zone is None or model.time_zone_name is None:
        collector.error("00005", display_path, "Missing required time_zone or time_zone_name")
    if model.lights_mandatory is None:
        collector.error("00005", display_path, "Missing required lights_mandatory attribute")
    if not model.mass_limit_per_axle_count:
        collector.error("00005", display_path, "Missing required mass_limit_per_axle_count[]")


def _validate_speed_limits_required_blocks(
    parsed: SpeedLimitsFile,
    display_path: str,
    collector: ValidationCollector,
    *,
    profile: PackageProfile = "core",
) -> None:
    present = set(parsed.vehicle_classes)
    if profile == "combo":
        if not (present & _REQUIRED_VEHICLE_CLASSES):
            collector.error(
                "00005",
                display_path,
                "Expected at least 1 road vehicle_speed_class block (car, truck, or bus)",
            )
    else:
        missing = sorted(_REQUIRED_VEHICLE_CLASSES - present)
        if missing:
            collector.error(
                "00005",
                display_path,
                f"Missing required vehicle_speed_class block(s): {', '.join(missing)}",
            )
    for block in parsed.blocks:
        if not block.lanes:
            collector.error(
                "00005",
                display_path,
                f"Vehicle speed block {block.vehicle_speed_class!r} has zero lane rules",
            )


def _validate_package_contents(
    archive: VfsArchive,
    *,
    prefix: str,
    workshop_mode: bool,
    expected_slugs: frozenset[str],
    valid_locales: frozenset[str] | None,
    collector: ValidationCollector,
    profile: PackageProfile = "core",
) -> tuple[
    dict[str, CountryDataModel],
    dict[str, SpeedLimitsFile],
    dict[str, SignBoardTemplate],
    dict[str, list[LocalizationEntry]],
    dict[str, dict[str, list[LocalizationEntry]]],
]:
    """Audit all files inside a mounted package archive against SCS 00001-00010 & WARN rules."""
    rel_prefix = f"{prefix}/" if prefix else ""

    def _p(path: str) -> str:
        return f"{rel_prefix}{path}"

    icon_name, desc_name = _validate_manifest(
        archive,
        prefix=prefix,
        workshop_mode=workshop_mode,
        collector=collector,
    )

    country_models: dict[str, CountryDataModel] = {}
    seen_country_slugs: dict[str, str] = {}
    speed_models: dict[str, SpeedLimitsFile] = {}
    sign_boards: dict[str, SignBoardTemplate] = {}
    fuel_locales: dict[str, list[LocalizationEntry]] = {}
    promods_locales: dict[str, dict[str, list[LocalizationEntry]]] = {}

    for vfs_path in archive.list_paths():
        display_path = _p(vfs_path)
        unsafe_reason = _has_unsafe_raw_path(vfs_path)
        if unsafe_reason is not None:
            collector.error("00003", display_path, unsafe_reason)
            continue

        suffix = Path(vfs_path).suffix.lower()

        if suffix in FORBIDDEN_TOTEM_EXTENSIONS:
            collector.error(
                "ETS2V2-INV-ZERO-DDS",
                display_path,
                f"Zero-DDS policy forbids {suffix!r} texture/object assets in packages",
            )
            continue

        if suffix == ".scs":
            raw_scs = _read_archive_entry(archive, vfs_path, display_path, collector)
            if raw_scs is not None:
                magic_err = _detect_unsupported_binary_magic(raw_scs)
                if magic_err is not None:
                    collector.error("00007", display_path, magic_err)
                elif workshop_mode and raw_scs.startswith(b"PK\x03\x04"):
                    collector.error(
                        "00003",
                        display_path,
                        "ZIP archive renamed to .scs is not allowed in Workshop packages",
                    )
            collector.error(
                "00003",
                display_path,
                ".scs archives are not allowed inside mod packages",
            )
            continue

        if not suffix or suffix not in ALLOWED_SCS_ASSET_EXTENSIONS:
            detail = (
                f"Extensionless file {vfs_path!r} is not allowed inside mod package"
                if not suffix
                else f"Unsupported file extension {suffix!r} inside mod package"
            )
            collector.error("00003", display_path, detail)
            continue

        if _COUNTRY_SII_RE.fullmatch(vfs_path) is not None:
            collector.error(
                "00003",
                display_path,
                "Packages must not emit def/country.sii or def/country.*.sii (D-05 / D-08)",
            )
            continue

        if suffix == ".jpg":
            if icon_name is None or vfs_path != icon_name:
                collector.error(
                    "00003",
                    display_path,
                    f"Unreferenced image file {vfs_path!r} (does not match manifest icon)",
                )
            continue

        if suffix == ".txt":
            if desc_name is None or not _is_valid_localized_description(
                vfs_path,
                desc_name,
                valid_locales,
            ):
                collector.error(
                    "00003",
                    display_path,
                    f"Unreferenced text file {vfs_path!r} (not declared description_file)",
                )
            elif vfs_path != desc_name:
                loc_raw = _read_archive_entry(archive, vfs_path, display_path, collector)
                if loc_raw is not None:
                    _validate_utf8_lf_text(loc_raw, display_path, collector)
                    check_license_taint_bytes(loc_raw, display_path, collector)
            continue

        if vfs_path == "manifest.sii":
            continue

        if suffix in {".sii", ".sui"}:
            raw = _read_archive_entry(archive, vfs_path, display_path, collector)
            if raw is None:
                continue

            check_license_taint_bytes(raw, display_path, collector)

            country_sii_match = (
                _COUNTRY_SII_FRAGMENT_RE.fullmatch(vfs_path) if profile != "core" else None
            )
            require_siinunit = (suffix == ".sii") and (country_sii_match is None)
            _record_sii_hygiene(
                raw,
                display_path,
                require_siinunit=require_siinunit,
                collector=collector,
            )

            if not detect_3nk(raw) and _detect_unsupported_binary_magic(raw) is None:
                try:
                    doc = SiiDocument.parse(raw, require_siinunit=require_siinunit)
                except SiiEncodingError:
                    doc = None
                if doc is not None and doc.find_units(class_name="mod_package"):
                    collector.error(
                        "00003",
                        display_path,
                        "mod_package unit is only allowed inside manifest.sii",
                    )

            sui_match = _COUNTRY_SUI_RE.fullmatch(vfs_path)
            country_match = sui_match if sui_match is not None else country_sii_match
            if country_match is not None:
                slug = country_match.group(1)
                if slug in seen_country_slugs:
                    collector.error(
                        "00003",
                        display_path,
                        f"Duplicate country definition for slug {slug!r} "
                        f"(already defined by {seen_country_slugs[slug]!r})",
                    )
                    continue
                seen_country_slugs[slug] = vfs_path
                try:
                    country_model = parse_country_data(raw)
                except (SiiEncodingError, ValueError, ValidationError) as exc:
                    collector.error(
                        "00008",
                        display_path,
                        f"Unable to load country_data unit: {exc}",
                    )
                else:
                    _validate_country_required_fields(
                        country_model,
                        display_path,
                        collector,
                        profile=profile,
                    )
                    country_models[slug] = country_model
                continue

            spd_match = _SPEED_LIMITS_RE.fullmatch(vfs_path)
            if spd_match is not None:
                slug = spd_match.group(1)
                try:
                    speed_model = parse_speed_limits(raw)
                except (SiiEncodingError, ValueError, ValidationError) as exc:
                    collector.error(
                        "00008",
                        display_path,
                        f"Unable to load speed_limits.sii: {exc}",
                    )
                else:
                    _validate_speed_limits_required_blocks(
                        speed_model,
                        display_path,
                        collector,
                        profile=profile,
                    )
                    speed_models[slug] = speed_model
                continue

            board_match = _SIGN_BOARD_RE.fullmatch(vfs_path)
            if board_match is not None:
                board_name = board_match.group(1)
                try:
                    board_model = parse_sign_board(raw)
                except (SiiEncodingError, ValueError, ValidationError) as exc:
                    collector.error(
                        "00008",
                        display_path,
                        f"Unable to load sign_board_template: {exc}",
                    )
                else:
                    sign_boards[board_name] = board_model
                continue

            fuel_loc_match = _FUEL_LOCALE_RE.fullmatch(vfs_path)
            if fuel_loc_match is not None:
                locale_code = fuel_loc_match.group(1)
                try:
                    loc_entries = parse_localization_db(raw)
                except (SiiEncodingError, ValueError, ValidationError) as exc:
                    collector.error(
                        "00008",
                        display_path,
                        f"Unable to load fuel localization_db: {exc}",
                    )
                else:
                    fuel_locales[locale_code] = loc_entries
                continue

            if profile != "core":
                pm_loc_match = _PROMODS_FUEL_LOCALE_RE.fullmatch(vfs_path)
                if pm_loc_match is not None:
                    locale_code = pm_loc_match.group(1)
                    module_name = pm_loc_match.group(2)
                    try:
                        loc_entries = parse_localization_db(raw)
                    except (SiiEncodingError, ValueError, ValidationError) as exc:
                        collector.error(
                            "00008",
                            display_path,
                            f"Unable to load ProMods fuel localization_db: {exc}",
                        )
                    else:
                        promods_locales.setdefault(module_name, {})[locale_code] = loc_entries
                    continue

            if vfs_path.startswith("locale/"):
                collector.error(
                    "00003",
                    display_path,
                    f"Unexpected locale file {vfs_path!r}; only permitted fuel locale modules "
                    "are allowed",
                )
                continue

            collector.error(
                "00003",
                display_path,
                f"Unexpected SII/SUI file {vfs_path!r} outside permitted realism allowlist",
            )
            continue

    # Check expected 36 Vanilla country files exist in core and promods profiles (SCS 00002)
    if profile in {"core", "promods"}:
        for slug in sorted(expected_slugs):
            sui_path = f"def/country/{slug}.sui"
            spd_path = f"def/country/{slug}/speed_limits.sii"
            if not archive.exists(sui_path):
                collector.error(
                    "00002",
                    _p(sui_path),
                    f"Missing required country definition {sui_path!r}",
                )
            if not archive.exists(spd_path):
                collector.error(
                    "00002",
                    _p(spd_path),
                    f"Missing required speed limits file {spd_path!r}",
                )

    _map_archive_diagnostics(archive, prefix=prefix, collector=collector)
    return country_models, speed_models, sign_boards, fuel_locales, promods_locales


def _dispatch_profile_invariants(
    profile: PackageProfile,
    *,
    country_models: dict[str, CountryDataModel],
    speed_models: dict[str, SpeedLimitsFile],
    sign_boards: dict[str, SignBoardTemplate],
    fuel_locales: dict[str, list[LocalizationEntry]],
    promods_locales: dict[str, dict[str, list[LocalizationEntry]]],
    bl_countries: CountriesBaseline | None,
    bl_speeds: SpeedLimitsBaseline | None,
    bl_locales: LocalesBaseline | None,
    bl_fuel_boards: FuelBoardsBaseline | None,
    collector: ValidationCollector,
    path_prefix: str = "",
) -> None:
    expected_locales = frozenset(bl_locales.active_locales) if bl_locales is not None else None
    if profile == "core":
        if bl_countries is not None and bl_speeds is not None and bl_locales is not None:
            validate_core_realism_invariants(
                country_models,
                speed_models,
                bl_countries,
                bl_speeds,
                bl_locales,
                collector,
                path_prefix=path_prefix,
            )
        if bl_fuel_boards is not None and bl_locales is not None:
            validate_totem_invariants(
                sign_boards,
                fuel_locales,
                bl_fuel_boards,
                bl_locales,
                collector,
                path_prefix=path_prefix,
            )
        elif fuel_locales:
            validate_fuel_locale_modules_consistency(
                fuel_locales,
                collector,
                path_prefix=path_prefix,
            )
        return

    if profile == "promods":
        validate_promods_realism_invariants(
            country_models,
            speed_models,
            bl_countries,
            bl_speeds,
            bl_locales,
            collector,
            path_prefix=path_prefix,
        )
        if bl_fuel_boards is not None and bl_locales is not None:
            validate_totem_invariants(
                sign_boards,
                fuel_locales,
                bl_fuel_boards,
                bl_locales,
                collector,
                path_prefix=path_prefix,
            )
        elif fuel_locales:
            validate_fuel_locale_modules_consistency(
                fuel_locales,
                collector,
                expected_locales=expected_locales,
                path_prefix=path_prefix,
            )
        if promods_locales:
            validate_promods_locale_modules_consistency(
                promods_locales,
                collector,
                expected_locales=expected_locales,
                path_prefix=path_prefix,
            )
        return

    validate_combo_invariants(
        country_models,
        speed_models,
        bl_locales,
        collector,
        sign_boards=sign_boards,
        fuel_locales=fuel_locales,
        promods_locales=promods_locales,
        path_prefix=path_prefix,
    )


def validate_workshop_package(
    workshop_dir: Path,
    *,
    baseline_dir: Path | None = None,
    profile: PackageProfile = "core",
) -> ValidationReport:
    """Validate an unpacked Steam Workshop directory root against SCS rules and invariants."""
    collector = ValidationCollector()
    bl_countries, bl_speeds, bl_locales, bl_fuel_boards = _load_optional_baselines(baseline_dir)
    expected_slugs = (
        frozenset(c.slug for c in bl_countries.countries)
        if bl_countries is not None
        else EXPECTED_CORE_COUNTRY_SLUGS
    )
    valid_locales = frozenset(bl_locales.active_locales) if bl_locales is not None else None

    if not workshop_dir.exists() or not workshop_dir.is_dir():
        collector.error("00002", str(workshop_dir), "Workshop root directory not found")
        return collector.build_report(workshop_dir, "workshop")

    resolved_workshop_root = workshop_dir.resolve()
    versions_path = workshop_dir / "versions.sii"
    if versions_path.is_symlink() or _is_dir_junction(versions_path):
        collector.error(
            "00003",
            "versions.sii",
            "Symlink or junction versions.sii is not allowed at Workshop root",
        )
        return collector.build_report(workshop_dir, "workshop")
    if not versions_path.is_file():
        collector.error("00002", "versions.sii", "Missing required versions.sii at Workshop root")
        return collector.build_report(workshop_dir, "workshop")
    if _is_unsafe_root_link(versions_path, resolved_workshop_root):
        collector.error(
            "00003",
            "versions.sii",
            "versions.sii escapes Workshop root directory",
        )
        return collector.build_report(workshop_dir, "workshop")

    try:
        versions_raw = versions_path.read_bytes()
    except PermissionError as exc:
        collector.error("00006", "versions.sii", f"Access denied reading versions.sii: {exc}")
        return collector.build_report(workshop_dir, "workshop")
    except OSError as exc:
        collector.error("00008", "versions.sii", f"Unable to read versions.sii: {exc}")
        return collector.build_report(workshop_dir, "workshop")

    check_license_taint_bytes(versions_raw, "versions.sii", collector)
    _record_sii_hygiene(versions_raw, "versions.sii", require_siinunit=True, collector=collector)

    try:
        versions_doc = SiiDocument.parse(versions_raw, require_siinunit=True)
    except SiiEncodingError as exc:
        collector.error("00004", "versions.sii", str(exc))
        return collector.build_report(workshop_dir, "workshop")

    for unit in versions_doc.units:
        if unit.class_name != "package_version_info":
            collector.error(
                "00003",
                "versions.sii",
                f"Disallowed unit class {unit.class_name!r} in versions.sii; "
                "only 'package_version_info' is allowed",
            )

    version_units = versions_doc.find_units(class_name="package_version_info")
    if not version_units:
        collector.error("00001", "versions.sii", "versions.sii defines zero package_version_info")
        return collector.build_report(workshop_dir, "workshop")

    universal_entries = [
        unit for unit in version_units if not unit.get_attributes("compatible_versions")
    ]
    if len(universal_entries) != 1:
        collector.error(
            "00003",
            "versions.sii",
            f"versions.sii must contain strictly 1 universal entry, found {len(universal_entries)}",
        )

    declared_root_names: set[str] = {"versions.sii"}
    seen_package_names: set[str] = set()

    for unit in version_units:
        for diag in validate_unit_name_segments(
            unit.unit_name,
            line=unit.unit_name_line,
            column=unit.unit_name_column,
        ):
            collector.error("00007", "versions.sii", diag.message)

        pkg_attr = unit.get_scalar("package_name")
        if pkg_attr is None:
            collector.error("00005", "versions.sii", "Missing required package_name attribute")
            continue

        pkg_name, pkg_quoted = unquote_sii_string(pkg_attr.raw_value)
        if not pkg_quoted:
            collector.error(
                "00004",
                "versions.sii",
                "Attribute 'package_name' in package_version_info must be a quoted string literal",
            )
            continue

        if not pkg_name:
            collector.error("00005", "versions.sii", "package_name must not be empty")
            continue

        if _PACKAGE_NAME_RE.fullmatch(pkg_name) is None:
            collector.error(
                "00003",
                "versions.sii",
                f"Invalid package_name {pkg_name!r}; must match ^[a-z0-9_]{{1,256}}$",
            )
            continue

        if pkg_name in seen_package_names:
            collector.error(
                "00003",
                "versions.sii",
                f"Duplicate package_name {pkg_name!r} in versions.sii",
            )
            continue
        seen_package_names.add(pkg_name)

        pkg_dir = workshop_dir / pkg_name
        pkg_zip = workshop_dir / f"{pkg_name}.zip"
        pkg_dir_link = pkg_dir.is_symlink() or _is_dir_junction(pkg_dir)
        pkg_zip_link = pkg_zip.is_symlink() or _is_dir_junction(pkg_zip)
        pkg_dir_present = pkg_dir.exists() or pkg_dir_link
        pkg_zip_present = pkg_zip.exists() or pkg_zip_link

        if pkg_dir_present and pkg_zip_present:
            collector.error(
                "00003",
                pkg_name,
                f"Side-by-side {pkg_name}/ directory and {pkg_name}.zip are not allowed",
            )
            declared_root_names.add(pkg_name)
            declared_root_names.add(f"{pkg_name}.zip")
            continue

        if pkg_dir_link:
            declared_root_names.add(pkg_name)
            collector.error(
                "00003",
                pkg_name,
                f"Symlink or directory junction {pkg_name!r} is not allowed at Workshop root",
            )
            continue

        if pkg_dir.is_dir():
            declared_root_names.add(pkg_name)
            if _is_unsafe_root_link(pkg_dir, resolved_workshop_root):
                collector.error(
                    "00003",
                    pkg_name,
                    f"Package directory {pkg_name!r} escapes Workshop root directory",
                )
                continue
            try:
                archive_dir = DirectoryArchive(pkg_dir)
            except PermissionError as exc:
                collector.error("00006", pkg_name, f"Access denied opening {pkg_name}/: {exc}")
                continue
            except OSError as exc:
                collector.error("00008", pkg_name, f"Unable to open {pkg_name}/: {exc}")
                continue
            with archive_dir:
                (
                    country_models,
                    speed_models,
                    sign_boards,
                    fuel_locales,
                    promods_locales,
                ) = _validate_package_contents(
                    archive_dir,
                    prefix=pkg_name,
                    workshop_mode=True,
                    expected_slugs=expected_slugs,
                    valid_locales=valid_locales,
                    collector=collector,
                    profile=profile,
                )
            _dispatch_profile_invariants(
                profile,
                country_models=country_models,
                speed_models=speed_models,
                sign_boards=sign_boards,
                fuel_locales=fuel_locales,
                promods_locales=promods_locales,
                bl_countries=bl_countries,
                bl_speeds=bl_speeds,
                bl_locales=bl_locales,
                bl_fuel_boards=bl_fuel_boards,
                collector=collector,
                path_prefix=pkg_name,
            )
        elif pkg_zip_link:
            declared_root_names.add(f"{pkg_name}.zip")
            collector.error(
                "00003",
                f"{pkg_name}.zip",
                f"Symlink or junction archive {pkg_name}.zip is not allowed at Workshop root",
            )
            continue
        elif pkg_zip.is_file():
            declared_root_names.add(f"{pkg_name}.zip")
            if _is_unsafe_root_link(pkg_zip, resolved_workshop_root):
                collector.error(
                    "00003",
                    f"{pkg_name}.zip",
                    f"Package archive {pkg_name}.zip escapes Workshop root directory",
                )
                continue
            if _inspect_raw_zip(pkg_zip, prefix=f"{pkg_name}.zip", collector=collector):
                try:
                    archive_zip = ZipArchive(pkg_zip)
                except PermissionError as exc:
                    collector.error(
                        "00006",
                        f"{pkg_name}.zip",
                        f"Access denied opening {pkg_name}.zip: {exc}",
                    )
                    continue
                except (OSError, ValueError) as exc:
                    collector.error(
                        "00008",
                        f"{pkg_name}.zip",
                        f"Unable to open {pkg_name}.zip: {exc}",
                    )
                    continue
                with archive_zip:
                    (
                        country_models,
                        speed_models,
                        sign_boards,
                        fuel_locales,
                        promods_locales,
                    ) = _validate_package_contents(
                        archive_zip,
                        prefix=f"{pkg_name}.zip",
                        workshop_mode=True,
                        expected_slugs=expected_slugs,
                        valid_locales=valid_locales,
                        collector=collector,
                        profile=profile,
                    )
                _dispatch_profile_invariants(
                    profile,
                    country_models=country_models,
                    speed_models=speed_models,
                    sign_boards=sign_boards,
                    fuel_locales=fuel_locales,
                    promods_locales=promods_locales,
                    bl_countries=bl_countries,
                    bl_speeds=bl_speeds,
                    bl_locales=bl_locales,
                    bl_fuel_boards=bl_fuel_boards,
                    collector=collector,
                    path_prefix=f"{pkg_name}.zip",
                )
        else:
            collector.error("00002", pkg_name, f"Declared package {pkg_name!r} not found")

    # Reject any extraneous files or directories at the Workshop root (SCS 00003)
    try:
        root_entries = sorted(workshop_dir.iterdir(), key=lambda p: p.name)
    except PermissionError as exc:
        collector.error("00006", str(workshop_dir), f"Access denied listing Workshop root: {exc}")
        return collector.build_report(workshop_dir, "workshop")

    for entry in root_entries:
        if entry.name not in declared_root_names:
            collector.error(
                "00003",
                entry.name,
                f"Extraneous root entry {entry.name!r} not allowed in Workshop root",
            )
            if entry.is_file() and entry.suffix.lower() in FORBIDDEN_TOTEM_EXTENSIONS:
                collector.error(
                    "ETS2V2-INV-ZERO-DDS",
                    entry.name,
                    f"Zero-DDS policy forbids {entry.suffix.lower()!r} assets at Workshop root",
                )
            if entry.is_file() and entry.suffix.lower() == ".scs":
                try:
                    with entry.open("rb") as fh:
                        magic = fh.read(4)
                except PermissionError as exc:
                    collector.error(
                        "00006", entry.name, f"Access denied reading {entry.name}: {exc}"
                    )
                except OSError:
                    pass
                else:
                    magic_err = _detect_unsupported_binary_magic(magic)
                    if magic_err is not None:
                        collector.error("00007", entry.name, magic_err)

    return collector.build_report(workshop_dir, "workshop")


def validate_local_zip(
    zip_path: Path,
    *,
    baseline_dir: Path | None = None,
    profile: PackageProfile = "core",
) -> ValidationReport:
    """Validate a standalone local playtest ``.zip`` package against SCS rules and invariants."""
    collector = ValidationCollector()
    bl_countries, bl_speeds, bl_locales, bl_fuel_boards = _load_optional_baselines(baseline_dir)
    expected_slugs = (
        frozenset(c.slug for c in bl_countries.countries)
        if bl_countries is not None
        else EXPECTED_CORE_COUNTRY_SLUGS
    )
    valid_locales = frozenset(bl_locales.active_locales) if bl_locales is not None else None

    if not zip_path.exists() or not zip_path.is_file():
        collector.error("00002", str(zip_path), "Local ZIP archive not found")
        return collector.build_report(zip_path, "local_zip")

    if not _inspect_raw_zip(zip_path, prefix="", collector=collector):
        return collector.build_report(zip_path, "local_zip")

    try:
        archive = ZipArchive(zip_path)
    except PermissionError as exc:
        collector.error("00006", str(zip_path), f"Access denied mounting ZIP archive: {exc}")
        return collector.build_report(zip_path, "local_zip")
    except (OSError, ValueError) as exc:
        collector.error("00008", str(zip_path), f"Unable to mount ZIP archive: {exc}")
        return collector.build_report(zip_path, "local_zip")

    with archive:
        (
            country_models,
            speed_models,
            sign_boards,
            fuel_locales,
            promods_locales,
        ) = _validate_package_contents(
            archive,
            prefix="",
            workshop_mode=False,
            expected_slugs=expected_slugs,
            valid_locales=valid_locales,
            collector=collector,
            profile=profile,
        )

    _dispatch_profile_invariants(
        profile,
        country_models=country_models,
        speed_models=speed_models,
        sign_boards=sign_boards,
        fuel_locales=fuel_locales,
        promods_locales=promods_locales,
        bl_countries=bl_countries,
        bl_speeds=bl_speeds,
        bl_locales=bl_locales,
        bl_fuel_boards=bl_fuel_boards,
        collector=collector,
    )

    return collector.build_report(zip_path, "local_zip")
