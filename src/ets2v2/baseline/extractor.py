"""Deterministic clean-room ETS2 baseline extraction, writing, and verification."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

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
from ets2v2.sii import (
    SiiDocument,
    parse_country_data,
    parse_country_includes,
    parse_localization_db,
    parse_sign_board,
    parse_speed_limits,
)
from ets2v2.sii.lexer import unquote_sii_string
from ets2v2.vfs import (
    HashFsV2Archive,
    VfsArchive,
    VfsLayer,
    VfsStack,
    normalize_vfs_path,
    open_archive,
)
from ets2v2.vfs.hashfs import DEFAULT_SEEDED_PREFIXES

DEFAULT_ETS2_GAME_DIR = Path(r"D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2")
EXTRACTOR_SCHEMA_VERSION = 1

_FUEL_BOARD_PREFIXES: tuple[str, ...] = (
    "gas_",
    "es_95_",
    "es_diesel_",
    "pt_95_",
    "pt_diesel_",
)

_PAYLOAD_FILENAMES: tuple[str, ...] = (
    "countries.json",
    "speed_limits.json",
    "fuel_boards.json",
    "locales.json",
)


def resolve_game_dir(game_dir: Path | str | None = None) -> Path:
    """Resolve ETS2 install path: explicit argument > ``ETS2_GAME_DIR`` > default Steam path."""
    if game_dir is not None:
        return Path(game_dir)
    env_dir = os.environ.get("ETS2_GAME_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return DEFAULT_ETS2_GAME_DIR


def _is_fuel_keyword_name(board_name: str) -> bool:
    return (
        board_name.startswith(_FUEL_BOARD_PREFIXES)
        or "fuel" in board_name
        or "diesel" in board_name
        or "_95" in board_name
        or "_98" in board_name
    )


def _extract_fp_key(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if len(stripped) > 4 and stripped.startswith("@@fp_") and stripped.endswith("@@"):
        return stripped[2:-2]
    return None


def _classify_slot_text(text: str | None) -> tuple[BoardClassification, str | None]:
    fp_key = _extract_fp_key(text)
    if fp_key is not None:
        return ("active_fp", fp_key)
    if text is None or text.strip() == "":
        return ("blank", None)
    return ("placeholder", None)


def _write_raw_cache_entry(cache_root: Path, vfs_path: str, payload: bytes) -> None:
    norm = normalize_vfs_path(vfs_path)
    dest = cache_root / norm
    resolved_root = cache_root.resolve()
    resolved_dest = dest.resolve()
    if not resolved_dest.is_relative_to(resolved_root):
        raise ValueError(f"Raw cache path escapes root: {vfs_path!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)


def _parse_version_info(raw_version_sii: bytes) -> tuple[str, str]:
    doc = SiiDocument.parse(raw_version_sii)
    unit = doc.get_unit(class_name="fs_pack_set")
    if unit is None:
        raise ValueError("Missing fs_pack_set unit in version.sii")
    app_attr = unit.get_scalar("application")
    ver_attr = unit.get_scalar("version")
    application = unquote_sii_string(app_attr.raw_value)[0] if app_attr is not None else "unknown"
    game_version = unquote_sii_string(ver_attr.raw_value)[0] if ver_attr is not None else "unknown"
    return (game_version, application)


def _is_dlc_country_path(vfs_path: str) -> bool:
    norm = normalize_vfs_path(vfs_path)
    if norm.startswith("base/"):
        norm = norm[len("base/") :]
    return norm == "def/country.sii" or norm.startswith(("def/country.", "def/country/"))


def _open_archive_ctx(
    path: Path,
    *,
    seeded_prefixes: Sequence[str] = DEFAULT_SEEDED_PREFIXES,
) -> contextlib.AbstractContextManager[VfsArchive]:
    return contextlib.closing(open_archive(path, seeded_prefixes=seeded_prefixes))


def _audit_dlc_archives(game_dir: Path) -> dict[str, int]:
    audit: dict[str, int] = {}
    for dlc_path in sorted(game_dir.glob("dlc_*.scs"), key=lambda p: p.name):
        dlc_stem = dlc_path.stem
        short_stem = dlc_stem.removeprefix("dlc_")
        with _open_archive_ctx(dlc_path) as dlc_arc:
            paths = set(dlc_arc.list_paths(["def", "base/def", "def/country", "base/def/country"]))
            candidates = {
                "def/country.sii",
                "base/def/country.sii",
                f"def/country.{dlc_stem}.sii",
                f"base/def/country.{dlc_stem}.sii",
                f"def/country.{short_stem}.sii",
                f"base/def/country.{short_stem}.sii",
            }
            for candidate in sorted(candidates):
                if dlc_arc.exists(candidate):
                    paths.add(candidate)
            count = sum(1 for p in paths if _is_dlc_country_path(p))
        audit[dlc_path.name] = count
    return audit


def _serialize_model_bytes(model: BaseModel) -> bytes:
    payload: object = model.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return text.encode("utf-8")


def _compute_payload_bytes(
    countries: CountriesBaseline,
    speed_limits: SpeedLimitsBaseline,
    fuel_boards: FuelBoardsBaseline,
    locales: LocalesBaseline,
) -> tuple[dict[str, bytes], dict[str, str]]:
    payloads: dict[str, bytes] = {
        "countries.json": _serialize_model_bytes(countries),
        "speed_limits.json": _serialize_model_bytes(speed_limits),
        "fuel_boards.json": _serialize_model_bytes(fuel_boards),
        "locales.json": _serialize_model_bytes(locales),
    }
    sha256s = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())}
    return payloads, sha256s


def _bundle_all_file_bytes(bundle: BaselineBundle) -> dict[str, bytes]:
    payloads, sha256s = _compute_payload_bytes(
        bundle.countries,
        bundle.speed_limits,
        bundle.fuel_boards,
        bundle.locales,
    )
    manifest = bundle.manifest.model_copy(update={"file_sha256s": sha256s})
    payloads["manifest.json"] = _serialize_model_bytes(manifest)
    return payloads


def extract_baseline(
    game_dir: Path | str | None = None,
    *,
    raw_cache_dir: Path | str | None = None,
) -> BaselineBundle:
    """Extract clean-room ETS2 metadata from ``version.scs``, ``def.scs``, and ``locale.scs``."""
    resolved_game_dir = resolve_game_dir(game_dir)
    if not resolved_game_dir.is_dir():
        raise FileNotFoundError(f"ETS2 game directory does not exist: {resolved_game_dir}")

    version_path = resolved_game_dir / "version.scs"
    def_path = resolved_game_dir / "def.scs"
    locale_path = resolved_game_dir / "locale.scs"
    for req_path in (version_path, def_path, locale_path):
        if not req_path.is_file():
            raise FileNotFoundError(f"Required ETS2 archive missing: {req_path}")

    cache_root: Path | None = Path(raw_cache_dir) if raw_cache_dir is not None else None
    if cache_root is not None:
        repo_data_dir = (Path(__file__).resolve().parents[3] / "data").resolve()
        if cache_root.resolve().is_relative_to(repo_data_dir):
            raise ValueError(f"raw_cache_dir must not be inside repo data directory: {cache_root}")

    with (
        _open_archive_ctx(version_path) as ver_arc,
        _open_archive_ctx(def_path) as def_arc,
        _open_archive_ctx(locale_path, seeded_prefixes=("locale",)) as loc_arc,
    ):
        raw_version = ver_arc.read_bytes("version.sii")
        if cache_root is not None:
            _write_raw_cache_entry(cache_root, "version.sii", raw_version)
        game_version, application = _parse_version_info(raw_version)

        def_stack = VfsStack([VfsLayer(name="def", priority=0, archive=def_arc)])
        def_paths = def_stack.list_paths()
        def_entry_count = len(def_paths)

        raw_country_sii = def_stack.read_bytes("def/country.sii")
        if cache_root is not None:
            _write_raw_cache_entry(cache_root, "def/country.sii", raw_country_sii)
        includes = parse_country_includes(raw_country_sii)

        countries_list: list[BaselineCountry] = []
        speed_limits_list: list[BaselineSpeedLimit] = []

        for include_rel in includes:
            norm_inc = normalize_vfs_path(include_rel)
            country_vfs = norm_inc if norm_inc.startswith("def/") else f"def/{norm_inc}"
            raw_country = def_stack.read_bytes(country_vfs)
            if cache_root is not None:
                _write_raw_cache_entry(cache_root, country_vfs, raw_country)
            c_model = parse_country_data(raw_country)
            slug = Path(country_vfs).stem

            countries_list.append(
                BaselineCountry(
                    slug=slug,
                    vfs_path=country_vfs,
                    include_path=norm_inc,
                    unit_name=c_model.unit_name,
                    country_id=c_model.country_id,
                    name=c_model.name,
                    name_localized=c_model.name_localized,
                    country_code=c_model.country_code,
                    iso_country_code=c_model.iso_country_code,
                    iso_country_code_quoted=c_model.iso_country_code_quoted,
                    pos=c_model.pos,
                    fuel_price=c_model.fuel_price,
                    lights_mandatory=c_model.lights_mandatory,
                    driving_tired_offence=c_model.driving_tired_offence,
                    imperial_units=c_model.imperial_units,
                    leftside_traffic=c_model.leftside_traffic,
                    trailer_standalone=c_model.trailer_standalone,
                    time_zone=c_model.time_zone,
                    time_zone_name=c_model.time_zone_name,
                    secondary_time_zone_area=c_model.secondary_time_zone_area,
                    secondary_time_zone=c_model.secondary_time_zone,
                    secondary_time_zone_name=c_model.secondary_time_zone_name,
                    mass_limit_per_axle_count=c_model.mass_limit_per_axle_count,
                    regions=c_model.regions,
                    region_areas=c_model.region_areas,
                    extra_attributes=c_model.extra_attributes,
                )
            )

            sl_vfs = f"def/country/{slug}/speed_limits.sii"
            raw_sl = def_stack.read_bytes(sl_vfs)
            if cache_root is not None:
                _write_raw_cache_entry(cache_root, sl_vfs, raw_sl)
            sl_file = parse_speed_limits(raw_sl)
            v_classes = sl_file.vehicle_classes
            speed_limits_list.append(
                BaselineSpeedLimit(
                    slug=slug,
                    vfs_path=sl_vfs,
                    vehicle_classes=v_classes,
                    has_train=("train" in v_classes),
                    has_tram=("tram" in v_classes),
                    blocks=sl_file.blocks,
                )
            )

        countries_list.sort(key=lambda item: item.slug)
        speed_limits_list.sort(key=lambda item: item.slug)

        # Sign board discovery (reads via def_stack to resolve base/ mounts transparently).
        board_paths = [
            p for p in def_paths if p.startswith("def/sign/board/") and p.endswith(".sii")
        ]
        total_sign_boards = len(board_paths)
        fuel_entries: list[FuelBoardEntry] = []
        excluded_boards: list[str] = []

        for board_vfs in board_paths:
            board_name = Path(board_vfs).stem
            is_prefix = board_name.startswith(_FUEL_BOARD_PREFIXES)
            is_kw = _is_fuel_keyword_name(board_name)
            raw_board = def_stack.read_bytes(board_vfs)
            if not is_kw and b"@@fp_" not in raw_board:
                continue

            sb = parse_sign_board(raw_board)
            has_fp = any(_extract_fp_key(slot.text) is not None for slot in sb.text_slots)
            if (is_prefix or has_fp) and sb.is_single_text_fuel_candidate:
                if cache_root is not None:
                    _write_raw_cache_entry(cache_root, board_vfs, raw_board)
                raw_slot = sb.text_slots[0]
                classification, fp_key = _classify_slot_text(raw_slot.text)
                fuel_entries.append(
                    FuelBoardEntry(
                        board_name=board_name,
                        vfs_path=board_vfs,
                        unit_name=sb.unit_name,
                        template_board_name=sb.board_name,
                        width=sb.width,
                        height=sb.height,
                        model_name=sb.model_name or "",
                        board_size=sb.board_size,
                        items_count=sb.items_count,
                        dynamic_attributes=sb.dynamic_attributes,
                        classification=classification,
                        fp_key=fp_key,
                        slot=FuelBoardSlot(
                            slot_index=raw_slot.slot_index,
                            unit_name=raw_slot.unit_name,
                            font_face=raw_slot.font_face,
                            font_size=raw_slot.font_size,
                            text_halign=raw_slot.text_halign,
                            text_valign=raw_slot.text_valign,
                            font_color=raw_slot.font_color,
                            font_opacity=raw_slot.font_opacity,
                            line_spacing=raw_slot.line_spacing,
                            letter_spacing=raw_slot.letter_spacing,
                            text_id=raw_slot.text_id,
                            area_name=raw_slot.area_name,
                            area_idx=raw_slot.area_idx,
                            coords_l=raw_slot.coords_l,
                            coords_r=raw_slot.coords_r,
                            coords_t=raw_slot.coords_t,
                            coords_b=raw_slot.coords_b,
                            z_order=raw_slot.z_order,
                            tag=raw_slot.tag,
                            h_align=raw_slot.h_align,
                            v_align=raw_slot.v_align,
                            text=raw_slot.text,
                        ),
                    )
                )
            elif is_kw or has_fp:
                excluded_boards.append(board_name)

        fuel_entries.sort(key=lambda item: item.board_name)
        excluded_boards.sort()

        # Stripped-root locale.scs walk via explicit "locale" seed
        locale_paths = (
            loc_arc.walk(["locale"])
            if isinstance(loc_arc, HashFsV2Archive)
            else loc_arc.list_paths(["locale"])
        )
        locale_entry_count = len(locale_paths)

        active_locales = sorted(
            {
                parts[1]
                for path in locale_paths
                if len(parts := path.split("/")) == 3
                and parts[0] == "locale"
                and parts[2] == "localization.sui"
            }
        )

        tz_key_set: set[str] = set()
        for lang in active_locales:
            loc_sui_path = f"locale/{lang}/localization.sui"
            raw_loc = loc_arc.read_bytes(loc_sui_path)
            if cache_root is not None:
                _write_raw_cache_entry(cache_root, loc_sui_path, raw_loc)
            loc_entries = parse_localization_db(raw_loc)
            for entry in loc_entries:
                if entry.key.startswith("tz_"):
                    tz_key_set.add(entry.key)

        fp_sui_path = "locale/fuel_price_strings.sui"
        raw_fp = loc_arc.read_bytes(fp_sui_path)
        if cache_root is not None:
            _write_raw_cache_entry(cache_root, fp_sui_path, raw_fp)
        fp_entries = parse_localization_db(raw_fp)
        fp_keys = sorted({entry.key for entry in fp_entries if entry.key.startswith("fp_")})
        tz_keys = sorted(tz_key_set)

    dlc_audit = _audit_dlc_archives(resolved_game_dir)

    countries_model = CountriesBaseline(countries=countries_list)
    speed_limits_model = SpeedLimitsBaseline(speed_limits=speed_limits_list)
    fuel_boards_model = FuelBoardsBaseline(
        total_sign_boards=total_sign_boards,
        excluded_fuel_keyword_boards=excluded_boards,
        boards=fuel_entries,
    )
    locales_model = LocalesBaseline(
        active_locales=active_locales,
        tz_keys=tz_keys,
        fp_keys=fp_keys,
    )

    active_fp_count = sum(1 for entry in fuel_entries if entry.classification == "active_fp")
    placeholder_blank_count = sum(
        1 for entry in fuel_entries if entry.classification in ("placeholder", "blank")
    )

    _, sha256s = _compute_payload_bytes(
        countries_model,
        speed_limits_model,
        fuel_boards_model,
        locales_model,
    )

    manifest = BaselineManifest(
        game_version=game_version,
        application=application,
        extractor_schema_version=EXTRACTOR_SCHEMA_VERSION,
        def_entry_count=def_entry_count,
        locale_entry_count=locale_entry_count,
        country_count=len(countries_list),
        speed_limit_count=len(speed_limits_list),
        total_sign_boards=total_sign_boards,
        fuel_board_count=len(fuel_entries),
        active_fp_board_count=active_fp_count,
        placeholder_or_blank_board_count=placeholder_blank_count,
        excluded_fuel_keyword_boards=excluded_boards,
        locale_count=len(active_locales),
        tz_key_count=len(tz_keys),
        fp_key_count=len(fp_keys),
        dlc_country_audit=dlc_audit,
        file_sha256s=sha256s,
    )

    return BaselineBundle(
        manifest=manifest,
        countries=countries_model,
        speed_limits=speed_limits_model,
        fuel_boards=fuel_boards_model,
        locales=locales_model,
    )


def write_baseline_bundle(bundle: BaselineBundle, out_dir: Path | str) -> dict[str, Path]:
    """Write deterministic clean-room JSON baseline files with UTF-8 no-BOM LF."""
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_bytes = _bundle_all_file_bytes(bundle)

    written: dict[str, Path] = {}
    for filename, payload in file_bytes.items():
        dest = target_dir / filename
        dest.write_bytes(payload)
        written[filename] = dest
    return written


def verify_baseline_bundle(bundle: BaselineBundle, out_dir: Path | str) -> list[str]:
    """Verify ``out_dir`` matches ``bundle`` byte-for-byte with valid SHA-256 and no raw SII."""
    target_dir = Path(out_dir)
    if not target_dir.is_dir():
        return [f"Missing baseline directory: {target_dir}"]

    issues: list[str] = []

    raw_scs = sorted(
        p.relative_to(target_dir).as_posix()
        for p in target_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".sii", ".sui"}
    )
    for rel in raw_scs:
        issues.append(f"Prohibited raw SCS file in baseline directory: {rel}")

    expected_bytes = _bundle_all_file_bytes(bundle)
    actual_sha256s: dict[str, str] = {}

    for filename in (*_PAYLOAD_FILENAMES, "manifest.json"):
        fpath = target_dir / filename
        if not fpath.is_file():
            issues.append(f"Missing baseline file: {filename}")
            continue

        actual = fpath.read_bytes()
        if actual.startswith(b"\xef\xbb\xbf"):
            issues.append(f"UTF-8 BOM detected in {filename}")
        if b"\r" in actual:
            issues.append(f"Non-LF line endings detected in {filename}")
        if actual != expected_bytes[filename]:
            issues.append(
                f"Byte mismatch in {filename}: expected {len(expected_bytes[filename])} bytes, "
                f"found {len(actual)} bytes"
            )
        if filename in _PAYLOAD_FILENAMES:
            actual_sha256s[filename] = hashlib.sha256(actual).hexdigest()

    manifest_path = target_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            disk_manifest = BaselineManifest.model_validate_json(manifest_path.read_text("utf-8"))
        except Exception as exc:
            issues.append(f"Invalid manifest.json schema: {exc}")
        else:
            for filename, digest in actual_sha256s.items():
                recorded = disk_manifest.file_sha256s.get(filename)
                if recorded != digest:
                    issues.append(
                        f"SHA-256 mismatch for {filename}: manifest={recorded}, actual={digest}"
                    )

    return issues
