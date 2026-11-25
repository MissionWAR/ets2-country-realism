"""Multi-source ETS2 load-order resolution, Workshop 227300, D-10 self-exclusion, D-11 VFS stack."""

from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from ets2v2.baseline.models import (
    BaselineCountry,
    BaselineSpeedLimit,
    CountriesBaseline,
    SpeedLimitsBaseline,
)
from ets2v2.package.metadata import ETS2V2_MANIFEST_MARKER
from ets2v2.package.synthesize import synthesize_country_sui, synthesize_speed_limits_sii
from ets2v2.registry.models import LaneClass, LaneSpeedOverride, RoadVehicleClass
from ets2v2.registry.snapshot import RealismSnapshot, RealismSnapshotCountry, RealismSnapshotFuel
from ets2v2.sii.document import SiiDocument
from ets2v2.sii.hygiene import serialize_sii_text
from ets2v2.sii.lexer import parse_sii_bool, unquote_sii_string
from ets2v2.vfs.dir_archive import DirectoryArchive
from ets2v2.vfs.hashfs import ProtectedArchiveStub, open_archive
from ets2v2.vfs.stack import VfsStack, classify_mount_path
from ets2v2.vfs.types import (
    ArchiveDiagnostic,
    ProtectedPayloadError,
    UnsupportedCompressionError,
    VfsArchive,
    VfsEntryMeta,
    decode_vfs_text,
    filter_paths_by_prefixes,
    normalize_vfs_path,
)
from ets2v2.vfs.zip_archive import ZipArchive

MAX_TEXT_INPUT_BYTES: Final[int] = 64 * 1024 * 1024
_MAX_3NK_PROBE_BYTES: Final[int] = 1 * 1024 * 1024
_ROAD_CLASSES: Final[tuple[RoadVehicleClass, ...]] = ("car", "truck", "bus")
_CANONICAL_LANES: Final[dict[str, LaneClass]] = {
    "local_road": "local_road",
    "expressway": "expressway",
    "motorway": "motorway",
    "slow_road": "slow_road",
}

ModlistOrder = Literal["top-to-bottom", "bottom-to-top"]
LoadOrderEntrySource = Literal["local", "workshop", "explicit_path"]

_WORKSHOP_PKG_RE: Final[re.Pattern[str]] = re.compile(
    r"^mod_workshop_package\.([0-9A-Fa-f]{16})$",
    re.IGNORECASE,
)
_WORKSHOP_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^workshop:(\d+)$", re.IGNORECASE)
_WORKSHOP_LOG_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[\\/])workshop[\\/]content[\\/]227300[\\/](\d+)(?:$|[\\/])",
    re.IGNORECASE,
)
_DIGITS_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\d+$")
_ARCHIVE_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(r"\.(?:scs|zip)$", re.IGNORECASE)
_SELF_PACKAGE_STEM_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:zz_)?ets2v2_(?:combopatch|core|promods)_",
    re.IGNORECASE,
)
_GAME_LOG_MOUNT_RE: Final[re.Pattern[str]] = re.compile(
    r'\[mod_package_manager\]\s+Mod\s+"(?P<display>.*)"\s+has been mounted\.\s*'
    r"\(package_name:\s*(?P<inner>.+)\)\s*$",
    re.IGNORECASE,
)
_GAME_LOG_UNMOUNT_RE: Final[re.Pattern[str]] = re.compile(
    r'\[mod_package_manager\]\s+(?:unmounting\b|mod\s+".*"\s+has been unmounted\b)',
    re.IGNORECASE,
)
_RELEVANT_COUNTRY_OR_BOARD_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:base/)?(?:def/country(?:\.[^/]+)?\.sii|def/country/.+|def/sign/board/.+)$",
    re.IGNORECASE,
)
_RELEVANT_COUNTRY_PROBE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:base/)?(?:def/country(?:\.[^/]+)?\.sii|def/country/.+\.(?:sui|sii))$",
    re.IGNORECASE,
)
_WINDOWS_DRIVE_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:")


class EncryptedProfileError(ValueError):
    """Raised when ``profile.sii`` starts with an encrypted ``ScsC`` header (D-09, T-04-10)."""


class LoadOrderEntry(BaseModel):
    """Normalized active mod entry in lowest-to-highest VFS mount order."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    package_name: str = Field(min_length=1)
    source: LoadOrderEntrySource
    raw_spec: str = Field(min_length=1)
    display_name: str | None = None
    workshop_id: str | None = None
    resolved_path: Path | None = None


class ExcludedSelfPackage(BaseModel):
    """Record of an ETS2V2 package automatically excluded from input VFS scanning (D-10)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    package_name: str = Field(min_length=1)
    archive_path: Path
    reason: str = Field(min_length=1)


class ProtectedArchiveDiagnostic(BaseModel):
    """Structured diagnostic for a protected archive encountered in load order (D-11)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    layer_name: str = Field(min_length=1)
    archive_path: Path
    protection_kind: str = Field(min_length=1)
    visible_relevant_paths: list[str] = Field(default_factory=list)
    substituted_by: Path | None = None
    overridden_by_higher_layer: bool = False
    hint: str = Field(min_length=1)


@dataclass
class ComboVfsBuildResult:
    """Assembled priority-ordered combo ``VfsStack`` with load-order & protection telemetry."""

    stack: VfsStack
    base_layer_name: str
    resolved_entries: list[LoadOrderEntry] = field(default_factory=list)
    excluded_self_packages: list[ExcludedSelfPackage] = field(default_factory=list)
    missing_entries: list[LoadOrderEntry] = field(default_factory=list)
    protected_archives: list[ProtectedArchiveDiagnostic] = field(default_factory=list)
    unpacked_overrides: list[Path] = field(default_factory=list)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self.stack.close()


def _read_bounded_bytes(path: Path, *, max_bytes: int = MAX_TEXT_INPUT_BYTES) -> bytes:
    """Read file bytes up to ``max_bytes`` to guard against oversized inputs (T-04-11)."""
    if not path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"Input file {path} exceeds maximum allowed size ({size} > {max_bytes} bytes)"
        )
    with path.open("rb") as fh:
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"Input file {path} exceeded maximum allowed size ({max_bytes} bytes)")
    return data


def _decode_text_permissive(raw: bytes) -> str:
    """Decode user/mod SII text via UTF-8 first with cp1252 fallback, normalizing line endings."""
    payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _strip_archive_suffix(name: str) -> str:
    return _ARCHIVE_SUFFIX_RE.sub("", name)


def _baseline_country_to_snapshot_proxy(
    bl_country: BaselineCountry,
    bl_speed: BaselineSpeedLimit,
) -> RealismSnapshotCountry:
    """Convert Vanilla 1.62 baseline models into a proxy for clean-room SII/SUI synthesis."""
    speed_limits: dict[RoadVehicleClass, list[LaneSpeedOverride]] = {}
    for vclass in _ROAD_CLASSES:
        block = next((b for b in bl_speed.blocks if b.vehicle_speed_class == vclass), None)
        overrides: list[LaneSpeedOverride] = []
        if block is not None:
            for lane in block.lanes:
                canonical = _CANONICAL_LANES.get(lane.lane_speed_class)
                if canonical is None:
                    continue
                overrides.append(
                    LaneSpeedOverride(
                        lane_speed_class=canonical,
                        limit=lane.limit if lane.limit is not None else 0,
                        urban_limit=lane.urban_limit if lane.urban_limit is not None else 0,
                        max_limit=lane.max_limit,
                        uncommon=lane.uncommon,
                    )
                )
        speed_limits[vclass] = overrides

    raw_iso3 = bl_country.iso_country_code.strip().lower()
    iso3 = raw_iso3 if re.fullmatch(r"^[a-z]{3}$", raw_iso3) is not None else "xxx"
    axles = (
        list(bl_country.mass_limit_per_axle_count)
        if 3 <= len(bl_country.mass_limit_per_axle_count) <= 12
        else [18000, 26000, 36000, 40000]
    )

    return RealismSnapshotCountry(
        iso2="XX",
        iso3=iso3,
        ets2_slug=bl_country.slug,
        iana_timezone="UTC",
        time_zone=bl_country.time_zone if bl_country.time_zone is not None else 0,
        time_zone_name=bl_country.time_zone_name or "UTC",
        observes_dst=False,
        lights_mandatory=bl_country.lights_mandatory is True,
        driving_tired_offence=bl_country.driving_tired_offence is not False,
        imperial_units=bl_country.imperial_units is True,
        mass_limit_per_axle_count=axles,
        speed_limits=speed_limits,
        fuel=RealismSnapshotFuel(
            currency="EUR",
            eur_per_liter=bl_country.fuel_price if bl_country.fuel_price is not None else 1.5,
            source="baseline_1.62",
        ),
    )


class BaselineVirtualArchive:
    """In-memory clean-room Vanilla 1.62 VFS base layer when ``--game-dir`` is omitted (D-09)."""

    def __init__(self, entries: Mapping[str, bytes]) -> None:
        self._path = Path("<baseline_1.62_virtual>")
        self._entries: dict[str, bytes] = {
            normalize_vfs_path(k): v for k, v in sorted(entries.items())
        }

    @classmethod
    def from_baselines(
        cls,
        bl_countries: CountriesBaseline,
        bl_speeds: SpeedLimitsBaseline,
        *,
        snapshot: RealismSnapshot | None = None,
    ) -> BaselineVirtualArchive:
        """Synthesize ``def/country.sii`` + all 36 Vanilla ``.sui`` & ``speed_limits.sii`` files."""
        resolved_by_slug = (
            {c.ets2_slug: c for c in snapshot.countries.values()} if snapshot is not None else {}
        )
        speeds_by_slug = {s.slug: s for s in bl_speeds.speed_limits}
        entries: dict[str, bytes] = {}
        include_lines: list[str] = ["SiiNunit", "{"]

        for bl_country in sorted(bl_countries.countries, key=lambda c: c.slug):
            slug = bl_country.slug
            bl_speed = speeds_by_slug.get(slug)
            if bl_speed is None:
                raise ValueError(f"Missing baseline speed_limits entry for slug {slug!r}")
            resolved = resolved_by_slug.get(slug) or _baseline_country_to_snapshot_proxy(
                bl_country, bl_speed
            )
            include_lines.append(f'@include "country/{slug}.sui"')
            entries[f"def/country/{slug}.sui"] = synthesize_country_sui(bl_country, resolved)
            entries[f"def/country/{slug}/speed_limits.sii"] = synthesize_speed_limits_sii(
                bl_speed, resolved
            )

        include_lines.append("}")
        entries["def/country.sii"] = serialize_sii_text("\n".join(include_lines) + "\n")
        return cls(entries)

    @classmethod
    def from_baseline_dir(
        cls,
        baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
        *,
        snapshot: RealismSnapshot | None = None,
    ) -> BaselineVirtualArchive:
        """Load clean-room baseline JSONs from ``baseline_dir`` into an in-memory VFS layer."""
        countries_json = baseline_dir / "countries.json"
        speeds_json = baseline_dir / "speed_limits.json"
        if not countries_json.is_file():
            raise FileNotFoundError(f"Missing baseline countries.json: {countries_json}")
        if not speeds_json.is_file():
            raise FileNotFoundError(f"Missing baseline speed_limits.json: {speeds_json}")
        bl_countries = CountriesBaseline.model_validate_json(countries_json.read_text("utf-8"))
        bl_speeds = SpeedLimitsBaseline.model_validate_json(speeds_json.read_text("utf-8"))
        return cls.from_baselines(bl_countries, bl_speeds, snapshot=snapshot)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def format_name(self) -> str:
        return "virtual_baseline"

    @property
    def diagnostics(self) -> list[ArchiveDiagnostic]:
        return []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def exists(self, vfs_path: str) -> bool:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        return norm in self._entries

    def get_meta(self, vfs_path: str) -> VfsEntryMeta | None:
        norm = normalize_vfs_path(vfs_path, allow_empty=True)
        payload = self._entries.get(norm)
        if payload is None:
            return None
        return VfsEntryMeta(
            path=norm,
            is_dir=False,
            size=len(payload),
            compressed_size=len(payload),
        )

    def list_paths(self, prefixes: Sequence[str] | None = None) -> list[str]:
        return filter_paths_by_prefixes(self._entries.keys(), prefixes)

    def read_bytes(self, vfs_path: str) -> bytes:
        norm = normalize_vfs_path(vfs_path)
        payload = self._entries.get(norm)
        if payload is None:
            raise FileNotFoundError(f"Entry {norm!r} not found in virtual baseline archive")
        return payload

    def read_text(self, vfs_path: str, encoding: str = "utf-8") -> str:
        return decode_vfs_text(self.read_bytes(vfs_path), vfs_path, encoding=encoding)

    def close(self) -> None:
        return None


def resolve_workshop_dir(
    explicit: Path | str | None = None,
    *,
    game_dir: Path | None = None,
) -> Path:
    """Resolve Steam Workshop ETS2 ``227300`` directory cross-platform."""
    if explicit is not None:
        return Path(explicit)

    env_dir = os.environ.get("ETS2_WORKSHOP_DIR", "").strip()
    if env_dir:
        return Path(env_dir)

    if game_dir is not None:
        steamapps_candidate = game_dir.resolve().parent.parent / "workshop" / "content" / "227300"
        if steamapps_candidate.is_dir():
            return steamapps_candidate

    if os.name == "nt":
        candidates = (
            Path(r"C:\Program Files (x86)\Steam\steamapps\workshop\content\227300"),
            Path(r"D:\SteamLibrary\steamapps\workshop\content\227300"),
        )
    else:
        home = Path.home()
        candidates = (
            home / ".local" / "share" / "Steam" / "steamapps" / "workshop" / "content" / "227300",
            home / ".steam" / "steam" / "steamapps" / "workshop" / "content" / "227300",
        )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def _entry_from_package_token(
    raw_token: str,
    *,
    display_name: str | None = None,
    raw_spec: str | None = None,
    source_hint: str | None = None,
) -> LoadOrderEntry:
    token = raw_token.strip()
    spec = raw_spec if raw_spec is not None else token

    ws_match = _WORKSHOP_PKG_RE.fullmatch(token)
    if ws_match is not None:
        decimal_id = str(int(ws_match.group(1), 16))
        return LoadOrderEntry(
            package_name=token,
            source="workshop",
            raw_spec=spec,
            display_name=display_name,
            workshop_id=decimal_id,
        )

    ws_prefix = _WORKSHOP_PREFIX_RE.fullmatch(token)
    if ws_prefix is not None:
        decimal_id = ws_prefix.group(1)
        hex_pkg = f"mod_workshop_package.{int(decimal_id):016X}"
        return LoadOrderEntry(
            package_name=hex_pkg,
            source="workshop",
            raw_spec=spec,
            display_name=display_name,
            workshop_id=decimal_id,
        )

    ws_path_match = _WORKSHOP_LOG_PATH_RE.search(token)
    if ws_path_match is not None:
        decimal_id = ws_path_match.group(1)
        hex_pkg = f"mod_workshop_package.{int(decimal_id):016X}"
        return LoadOrderEntry(
            package_name=hex_pkg,
            source="workshop",
            raw_spec=spec,
            display_name=display_name,
            workshop_id=decimal_id,
        )

    if (
        source_hint is not None
        and "workshop" in source_hint.lower()
        and _DIGITS_ONLY_RE.fullmatch(token) is not None
    ):
        hex_pkg = f"mod_workshop_package.{int(token):016X}"
        return LoadOrderEntry(
            package_name=hex_pkg,
            source="workshop",
            raw_spec=spec,
            display_name=display_name,
            workshop_id=token,
        )

    if "/" in token or "\\" in token or _WINDOWS_DRIVE_RE.match(token) is not None:
        posix_name = token.replace("\\", "/").rstrip("/")
        leaf = posix_name.rsplit("/", 1)[-1]
        stem = _strip_archive_suffix(leaf) or leaf
        return LoadOrderEntry(
            package_name=stem,
            source="explicit_path",
            raw_spec=spec,
            display_name=display_name,
        )

    stem = _strip_archive_suffix(token) or token
    return LoadOrderEntry(
        package_name=stem,
        source="local",
        raw_spec=spec,
        display_name=display_name,
    )


def parse_profile_sii(profile_path: Path) -> list[LoadOrderEntry]:
    """Parse plaintext ETS2 ``profile.sii`` ``active_mods[]`` in lowest-to-highest order (D-09)."""
    raw = _read_bounded_bytes(profile_path)
    if raw.startswith(b"ScsC"):
        raise EncryptedProfileError(
            f"Profile {profile_path} is ScsC-encrypted; ETS2V2 never decrypts SCS profiles. "
            'Use --game-log <path-to-game.log.txt> or set `uset g_save_format "2"` in ETS2 '
            "config.cfg and re-save your profile."
        )

    text = _decode_text_permissive(raw)
    doc = SiiDocument.parse(text)
    unit = doc.get_unit(class_name="user_profile")
    if unit is None:
        raise ValueError(f"No user_profile unit found in {profile_path}")

    mod_attrs = unit.get_attributes("active_mods")
    indexed = [attr for attr in mod_attrs if attr.index is not None]
    if indexed:
        indexed.sort(key=lambda attr: attr.index if attr.index is not None else -1)
        ordered_attrs = indexed
    else:
        ordered_attrs = [attr for attr in mod_attrs if attr.is_append]

    entries: list[LoadOrderEntry] = []
    for attr in ordered_attrs:
        unquoted = unquote_sii_string(attr.raw_value)[0].strip()
        if not unquoted:
            continue
        if "|" in unquoted:
            stem, display = unquoted.split("|", 1)
            display_name: str | None = display.strip() or None
        else:
            stem = unquoted
            display_name = None
        entries.append(
            _entry_from_package_token(
                stem,
                display_name=display_name,
                raw_spec=unquoted,
            )
        )
    return entries


def parse_game_log(log_path: Path) -> list[LoadOrderEntry]:
    """Parse active profile mounts from ETS2 ``game.log.txt``, ignoring startup scans (D-09)."""
    raw = _read_bounded_bytes(log_path)
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")

    current_session: list[LoadOrderEntry] = []
    session_ended = False

    for line in text.splitlines():
        mount_match = _GAME_LOG_MOUNT_RE.search(line)
        if mount_match is not None:
            if session_ended:
                current_session = []
                session_ended = False

            display = mount_match.group("display").strip() or None
            inner = mount_match.group("inner").strip()
            source_hint: str | None = None

            source_split = re.split(r",\s*source:\s*", inner, maxsplit=1, flags=re.IGNORECASE)
            if len(source_split) == 2:
                inner, source_hint = source_split[0].strip(), source_split[1].strip()

            version_split = re.split(r",\s*version:\s*", inner, maxsplit=1, flags=re.IGNORECASE)
            package_token = version_split[0].strip()
            if not package_token:
                continue

            entry = _entry_from_package_token(
                package_token,
                display_name=display,
                raw_spec=package_token,
                source_hint=source_hint,
            )
            # In game.log.txt, package_name from [mod_package_manager] is a local stem or
            # workshop token; preserve local stem even if an odd path separator appears.
            if entry.source == "explicit_path" and source_hint is not None:
                entry = entry.model_copy(update={"source": "local"})
            current_session.append(entry)
            continue

        if current_session and _GAME_LOG_UNMOUNT_RE.search(line) is not None:
            session_ended = True

    return current_session


def parse_modlist(
    modlist_path: Path,
    *,
    order: ModlistOrder = "top-to-bottom",
) -> list[LoadOrderEntry]:
    """Parse line-delimited ``--modlist`` into lowest-to-highest VFS mount order (D-09)."""
    if order not in ("top-to-bottom", "bottom-to-top"):
        raise ValueError(f"Unsupported modlist order: {order!r}")

    raw = _read_bounded_bytes(modlist_path)
    text = _decode_text_permissive(raw)

    entries: list[LoadOrderEntry] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(_entry_from_package_token(stripped, raw_spec=stripped))

    if order == "top-to-bottom":
        entries.reverse()
    return entries


def _version_matches(pattern: str, target_game_version: str) -> bool:
    clean_pat = pattern.strip()
    if not clean_pat:
        return False
    if clean_pat == target_game_version or clean_pat.startswith(f"{target_game_version}."):
        return True
    return fnmatch.fnmatchcase(target_game_version, clean_pat) or fnmatch.fnmatchcase(
        f"{target_game_version}.0", clean_pat
    )


def _resolve_contained_workshop_target(item_dir: Path, package_name: str) -> Path | None:
    """Resolve ``package_name`` inside ``item_dir``, rejecting traversal and symlink escapes."""
    cleaned = package_name.strip()
    if (
        not cleaned
        or "\x00" in cleaned
        or "\\" in cleaned
        or cleaned.startswith("/")
        or _WINDOWS_DRIVE_RE.match(cleaned) is not None
    ):
        raise ValueError(f"Unsafe Workshop package_name {package_name!r} in {item_dir}")

    parts = Path(cleaned).parts
    if any(part in ("..", "") for part in parts):
        raise ValueError(f"Path traversal rejected in Workshop package_name {package_name!r}")

    resolved_root = item_dir.resolve()
    candidates = (
        item_dir / cleaned,
        item_dir / f"{cleaned}.zip",
        item_dir / f"{cleaned}.scs",
    )
    for candidate in candidates:
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(resolved_root):
            raise ValueError(
                f"Workshop package_name {package_name!r} escapes {resolved_root}: {resolved}"
            )
        return resolved
    return None


def resolve_workshop_package_path(
    workshop_id_decimal: str,
    workshop_dir: Path,
    *,
    target_game_version: str = "1.62",
) -> Path | None:
    """Resolve a Steam Workshop ``227300/<id>`` item via ``versions.sii`` (D-09, T-04-09)."""
    if _DIGITS_ONLY_RE.fullmatch(workshop_id_decimal) is None:
        raise ValueError(f"Invalid decimal Steam Workshop ID: {workshop_id_decimal!r}")

    ws_root = workshop_dir.resolve()
    item_dir = (workshop_dir / workshop_id_decimal).resolve()
    if not item_dir.is_relative_to(ws_root):
        raise ValueError(f"Workshop item {workshop_id_decimal!r} escapes {ws_root}")
    if not item_dir.is_dir():
        return None

    versions_sii = item_dir / "versions.sii"
    if versions_sii.is_file():
        raw = _read_bounded_bytes(versions_sii)
        doc = SiiDocument.parse(_decode_text_permissive(raw))
        matching_packages: list[str] = []
        universal_packages: list[str] = []

        for unit in doc.find_units(class_name="package_version_info"):
            info_attr = unit.get_scalar("informational")
            if info_attr is not None:
                try:
                    if parse_sii_bool(info_attr.raw_value):
                        continue
                except ValueError:
                    pass

            pkg_attr = unit.get_scalar("package_name")
            if pkg_attr is None:
                continue
            pkg_name = unquote_sii_string(pkg_attr.raw_value)[0].strip()
            if not pkg_name:
                continue

            compat_attrs = [
                attr
                for attr in unit.get_attributes("compatible_versions")
                if attr.is_append or attr.index is not None
            ]
            compat_vals = [unquote_sii_string(a.raw_value)[0].strip() for a in compat_attrs]
            compat_vals = [v for v in compat_vals if v]

            if not compat_vals:
                universal_packages.append(pkg_name)
            elif any(_version_matches(v, target_game_version) for v in compat_vals):
                matching_packages.append(pkg_name)

        for pkg_name in (*matching_packages, *universal_packages):
            resolved = _resolve_contained_workshop_target(item_dir, pkg_name)
            if resolved is not None:
                return resolved
        return None

    # Fallback when versions.sii is absent
    for fallback_name in ("universal",):
        resolved = _resolve_contained_workshop_target(item_dir, fallback_name)
        if resolved is not None:
            return resolved
    if (item_dir / "def").is_dir() or (item_dir / "manifest.sii").is_file():
        return item_dir
    return None


def is_ets2v2_self_package(
    archive_path: Path,
    archive: VfsArchive | None = None,
) -> tuple[bool, str | None]:
    """Detect previously generated ETS2V2 packages by filename or manifest.sii marker (D-10)."""
    if _SELF_PACKAGE_STEM_RE.match(archive_path.stem) is not None:
        return True, f"filename:{archive_path.name}"

    if archive is not None and archive.exists("manifest.sii"):
        try:
            raw = archive.read_bytes("manifest.sii")
        except (ProtectedPayloadError, UnsupportedCompressionError, OSError, ValueError):
            return False, None
        if ETS2V2_MANIFEST_MARKER.encode("utf-8") in raw:
            return True, "manifest_marker"

    return False, None


def _is_raw_unpacked_mod_tree(directory: Path) -> bool:
    """Return True when ``directory`` directly houses a mod root (``def/`` or ``locale/``)."""
    resolved_root = directory.resolve()
    for rel_parts in (("def",), ("locale",), ("base", "def"), ("base", "locale")):
        candidate = directory.joinpath(*rel_parts)
        if candidate.is_dir():
            try:
                if candidate.resolve().is_relative_to(resolved_root):
                    return True
            except OSError:
                continue
    return False


def _classify_unpacked_defs(
    unpacked_defs: Sequence[Path],
) -> tuple[dict[str, Path], list[Path]]:
    """Classify repeatable ``--unpacked-defs`` dirs into stem substitutions vs root overrides."""
    stem_substitutions: dict[str, Path] = {}
    override_dirs: list[Path] = []

    for udir in unpacked_defs:
        if not udir.exists():
            raise FileNotFoundError(f"--unpacked-defs directory does not exist: {udir}")
        if not udir.is_dir():
            raise NotADirectoryError(f"--unpacked-defs path is not a directory: {udir}")

        if _is_raw_unpacked_mod_tree(udir):
            override_dirs.append(udir)
            continue

        resolved_parent = udir.resolve()
        for child in sorted(udir.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir():
                continue
            resolved_child = child.resolve()
            if not resolved_child.is_relative_to(resolved_parent):
                raise ValueError(
                    f"Symlink/junction child {child} escapes --unpacked-defs root {resolved_parent}"
                )
            stem_substitutions[child.name.lower()] = child

    return stem_substitutions, override_dirs


def _resolve_local_mod_path(entry: LoadOrderEntry, mod_dir: Path | None) -> Path | None:
    if entry.resolved_path is not None and entry.resolved_path.exists():
        return entry.resolved_path

    if entry.source == "explicit_path":
        raw_path = Path(entry.raw_spec)
        if raw_path.exists():
            return raw_path
        if mod_dir is not None:
            candidate = mod_dir / raw_path
            if candidate.exists():
                return candidate
        return None

    if mod_dir is None or not mod_dir.is_dir():
        return None

    mod_root = mod_dir.resolve()
    raw_names = (
        f"{entry.package_name}.scs",
        f"{entry.package_name}.zip",
        entry.raw_spec,
        entry.package_name,
    )
    for name in raw_names:
        if "/" in name or "\\" in name or ".." in Path(name).parts:
            continue
        candidate = mod_dir / name
        if candidate.exists():
            resolved = candidate.resolve()
            if resolved.is_relative_to(mod_root):
                return candidate

    # Case-insensitive fallback scan for cross-platform profile/log portability
    target_lower = entry.package_name.lower()
    for child in sorted(mod_dir.iterdir(), key=lambda p: p.name.lower()):
        child_stem = _strip_archive_suffix(child.name).lower()
        if child_stem == target_lower or child.name.lower() == target_lower:
            resolved = child.resolve()
            if resolved.is_relative_to(mod_root):
                return child
    return None


def _find_visible_relevant_paths(archive: VfsArchive) -> list[str]:
    relevant: list[str] = []
    for raw_path in archive.list_paths():
        if _RELEVANT_COUNTRY_OR_BOARD_RE.fullmatch(raw_path) is not None:
            relevant.append(raw_path)
    return sorted(set(relevant))


def _probe_3nk_country_files(archive: VfsArchive) -> list[str]:
    """Probe small readable ``def/country*`` entries for ``3nK\\x01`` obfuscation headers."""
    found: list[str] = []
    for raw_path in archive.list_paths():
        if _RELEVANT_COUNTRY_PROBE_RE.fullmatch(raw_path) is None:
            continue
        meta = archive.get_meta(raw_path)
        if meta is None or meta.encrypted or meta.compression == "unknown":
            continue
        if meta.size <= 0 or meta.size > _MAX_3NK_PROBE_BYTES:
            continue
        try:
            archive.read_bytes(raw_path)
        except (ProtectedPayloadError, UnsupportedCompressionError, OSError, ValueError):
            continue
        updated_meta = archive.get_meta(raw_path)
        if updated_meta is not None and updated_meta.three_nk:
            found.append(raw_path)
    return sorted(set(found))


def _inspect_protection(
    archive: VfsArchive,
    archive_path: Path,
) -> tuple[str, list[str]] | None:
    """Detect ``ProtectedArchiveStub``, encrypted ``ZipArchive``, or ``3nK`` country files."""
    if isinstance(archive, ProtectedArchiveStub):
        kind = archive.diagnostics[0].kind if archive.diagnostics else "unknown_magic"
        return kind, []

    if isinstance(archive, ZipArchive) and any(
        d.kind == "encrypted_zip" for d in archive.diagnostics
    ):
        return "encrypted_zip", _find_visible_relevant_paths(archive)

    three_nk_paths = _probe_3nk_country_files(archive)
    if three_nk_paths:
        return "three_nk_obfuscated", three_nk_paths

    if any(d.kind == "three_nk_obfuscated" for d in archive.diagnostics):
        paths = sorted(
            {
                d.entry_path
                for d in archive.diagnostics
                if d.kind == "three_nk_obfuscated" and d.entry_path is not None
            }
        )
        return "three_nk_obfuscated", paths

    del archive_path
    return None


def _build_protection_hint(
    archive_path: Path,
    protection_kind: str,
    substituted_by: Path | None,
) -> str:
    if substituted_by is not None:
        return f"Substituted in-place via --unpacked-defs directory: {substituted_by}"
    return (
        f"Archive {archive_path.name!r} uses {protection_kind}; ETS2V2 never decrypts protected "
        f"archives. To include its country definitions at exact load-order priority, extract its "
        f"def/ folder into <dir>/{archive_path.stem}/ and pass --unpacked-defs <dir>."
    )


def build_combo_vfs_stack(
    entries: Sequence[LoadOrderEntry],
    *,
    mod_dir: Path | None = None,
    workshop_dir: Path | None = None,
    game_dir: Path | None = None,
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    snapshot: RealismSnapshot | None = None,
    unpacked_defs: Sequence[Path] = (),
    exclude_self: bool = True,
    target_game_version: str = "1.62",
) -> ComboVfsBuildResult:
    """Assemble priority-ordered combo ``VfsStack`` with D-10 self-exclusion & D-11 handling."""
    stem_substitutions, override_dirs = _classify_unpacked_defs(unpacked_defs)

    stack = VfsStack()
    resolved_entries: list[LoadOrderEntry] = []
    excluded_self_packages: list[ExcludedSelfPackage] = []
    missing_entries: list[LoadOrderEntry] = []
    protected_archives: list[ProtectedArchiveDiagnostic] = []
    pending_override_checks: list[tuple[int, int, list[str]]] = []

    try:
        if game_dir is not None:
            def_scs = game_dir / "def.scs"
            if not def_scs.is_file():
                raise FileNotFoundError(
                    f"Required Vanilla def.scs missing under --game-dir: {def_scs}"
                )
            base_layer_name = "vanilla_def"
            stack.mount(open_archive(def_scs), name=base_layer_name, priority=0)
        else:
            base_layer_name = "vanilla_baseline_1_62"
            stack.mount(
                BaselineVirtualArchive.from_baseline_dir(baseline_dir, snapshot=snapshot),
                name=base_layer_name,
                priority=0,
            )

        priority = 0
        for entry in entries:
            if entry.source == "workshop":
                if entry.resolved_path is not None and entry.resolved_path.exists():
                    resolved_path: Path | None = entry.resolved_path
                elif workshop_dir is not None and entry.workshop_id is not None:
                    resolved_path = resolve_workshop_package_path(
                        entry.workshop_id,
                        workshop_dir,
                        target_game_version=target_game_version,
                    )
                else:
                    resolved_path = None
            else:
                resolved_path = _resolve_local_mod_path(entry, mod_dir)

            if resolved_path is None or not resolved_path.exists():
                missing_entries.append(entry)
                continue

            archive = open_archive(resolved_path)

            if exclude_self:
                is_self, reason = is_ets2v2_self_package(resolved_path, archive)
                if is_self:
                    archive.close()
                    excluded_self_packages.append(
                        ExcludedSelfPackage(
                            package_name=entry.package_name,
                            archive_path=resolved_path,
                            reason=reason or "self_package",
                        )
                    )
                    continue

            priority += 1
            protection = _inspect_protection(archive, resolved_path)
            if protection is not None:
                protection_kind, visible_paths = protection
                sub_dir = stem_substitutions.get(
                    resolved_path.stem.lower()
                ) or stem_substitutions.get(entry.package_name.lower())
                if sub_dir is not None:
                    archive.close()
                    sub_archive = DirectoryArchive(sub_dir)
                    stack.mount(
                        sub_archive,
                        name=f"{resolved_path.stem} (unpacked-defs)",
                        priority=priority,
                    )
                    protected_archives.append(
                        ProtectedArchiveDiagnostic(
                            layer_name=resolved_path.name,
                            archive_path=resolved_path,
                            protection_kind=protection_kind,
                            visible_relevant_paths=visible_paths,
                            substituted_by=sub_dir,
                            overridden_by_higher_layer=False,
                            hint=_build_protection_hint(resolved_path, protection_kind, sub_dir),
                        )
                    )
                    resolved_entries.append(entry.model_copy(update={"resolved_path": sub_dir}))
                    continue

                stack.mount(archive, name=resolved_path.name, priority=priority)
                diag_idx = len(protected_archives)
                protected_archives.append(
                    ProtectedArchiveDiagnostic(
                        layer_name=resolved_path.name,
                        archive_path=resolved_path,
                        protection_kind=protection_kind,
                        visible_relevant_paths=visible_paths,
                        substituted_by=None,
                        overridden_by_higher_layer=False,
                        hint=_build_protection_hint(resolved_path, protection_kind, None),
                    )
                )
                if visible_paths:
                    pending_override_checks.append((diag_idx, priority, visible_paths))
                resolved_entries.append(entry.model_copy(update={"resolved_path": resolved_path}))
                continue

            stack.mount(archive, name=resolved_path.name, priority=priority)
            resolved_entries.append(entry.model_copy(update={"resolved_path": resolved_path}))

        for udir in override_dirs:
            priority += 1
            stack.mount(
                DirectoryArchive(udir),
                name=f"unpacked_defs:{udir.name}",
                priority=priority,
            )

        # Compute overridden_by_higher_layer across the final assembled stack
        for diag_idx, diag_prio, visible_paths in pending_override_checks:
            all_overridden = True
            for raw_rel in visible_paths:
                canonical, _ = classify_mount_path(raw_rel)
                winner = stack.resolve(canonical)
                if (
                    winner is None
                    or winner.priority <= diag_prio
                    or winner.meta.encrypted
                    or winner.meta.three_nk
                ):
                    all_overridden = False
                    break
            if all_overridden:
                protected_archives[diag_idx] = protected_archives[diag_idx].model_copy(
                    update={"overridden_by_higher_layer": True}
                )
    except Exception:
        stack.close()
        raise

    return ComboVfsBuildResult(
        stack=stack,
        base_layer_name=base_layer_name,
        resolved_entries=resolved_entries,
        excluded_self_packages=excluded_self_packages,
        missing_entries=missing_entries,
        protected_archives=protected_archives,
        unpacked_overrides=override_dirs,
    )


__all__ = [
    "ETS2V2_MANIFEST_MARKER",
    "MAX_TEXT_INPUT_BYTES",
    "BaselineVirtualArchive",
    "ComboVfsBuildResult",
    "EncryptedProfileError",
    "ExcludedSelfPackage",
    "LoadOrderEntry",
    "LoadOrderEntrySource",
    "ModlistOrder",
    "ProtectedArchiveDiagnostic",
    "build_combo_vfs_stack",
    "is_ets2v2_self_package",
    "parse_game_log",
    "parse_modlist",
    "parse_profile_sii",
    "resolve_workshop_dir",
    "resolve_workshop_package_path",
]
