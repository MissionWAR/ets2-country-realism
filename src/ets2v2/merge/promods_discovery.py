"""Version-agnostic ProMods EU/TGS/ME/MA def/defmap + assets archive discovery (D-06)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

ProModsPackId = Literal["eu", "tgs", "me", "ma"]
ProModsPackRole = Literal["def", "defmap", "assets"]

_DEFAULT_WINDOWS_DATA_MOD_DIR: Final[Path] = Path(r"D:\ETS2Data\Euro Truck Simulator 2\mod")

# Version-agnostic regexes verified against ProMods 2.85 / ME 2.85 / MA 1.05 / TGS 1.71
_EU_DEF_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-(?:eu-)?def(?:-(?P<variant>[a-z0-9_]+))?-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)
_EU_ASSETS_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-(?:eu-)?assets-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)
_TGS_DEF_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-tgs-defmap-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)
_TGS_ASSETS_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-tgs-assets-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)
_ME_DEF_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-me-defmap-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)
_ME_ASSETS_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-me-assets-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)
_MA_DEF_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-ma-defmap-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)
_MA_ASSETS_RE: Final[re.Pattern[str]] = re.compile(
    r"^promods-ma-assets-v(?P<version>\d+(?:\.\d+)*)\.(?:scs|zip)$",
    re.IGNORECASE,
)

# Official bottom-to-top ProMods stacking priority: Vanilla (0) < EU < TGS < ME < MA
_PACK_PRIORITIES: Final[dict[tuple[ProModsPackId, ProModsPackRole], int]] = {
    ("eu", "assets"): 10,
    ("eu", "def"): 11,
    ("tgs", "assets"): 20,
    ("tgs", "defmap"): 21,
    ("me", "assets"): 30,
    ("me", "defmap"): 31,
    ("ma", "assets"): 40,
    ("ma", "defmap"): 41,
}

_SLOT_PATTERNS: Final[dict[tuple[ProModsPackId, ProModsPackRole], re.Pattern[str]]] = {
    ("eu", "def"): _EU_DEF_RE,
    ("eu", "assets"): _EU_ASSETS_RE,
    ("tgs", "defmap"): _TGS_DEF_RE,
    ("tgs", "assets"): _TGS_ASSETS_RE,
    ("me", "defmap"): _ME_DEF_RE,
    ("me", "assets"): _ME_ASSETS_RE,
    ("ma", "defmap"): _MA_DEF_RE,
    ("ma", "assets"): _MA_ASSETS_RE,
}


class ProModsPackSpec(BaseModel):
    """Single discovered or explicitly overridden ProMods archive slot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    pack: ProModsPackId
    role: ProModsPackRole
    path: Path
    version: tuple[int, ...] = ()
    layer_name: str = Field(min_length=1)
    priority: int = Field(ge=1)
    is_explicit_override: bool = False
    is_special_transport: bool = False


ProModsPackEntry = ProModsPackSpec


class ProModsPackSet(BaseModel):
    """Discovered set of ProMods EU/TGS/ME/MA def/defmap and assets archives."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    mod_dir: Path | None = None
    eu_def: ProModsPackSpec | None = None
    eu_assets: ProModsPackSpec | None = None
    tgs_def: ProModsPackSpec | None = None
    tgs_assets: ProModsPackSpec | None = None
    me_def: ProModsPackSpec | None = None
    me_assets: ProModsPackSpec | None = None
    ma_def: ProModsPackSpec | None = None
    ma_assets: ProModsPackSpec | None = None

    def ordered_packs(self) -> list[ProModsPackSpec]:
        """Return present packs in official bottom-to-top stacking order: EU < TGS < ME < MA."""
        candidates = (
            self.eu_assets,
            self.eu_def,
            self.tgs_assets,
            self.tgs_def,
            self.me_assets,
            self.me_def,
            self.ma_assets,
            self.ma_def,
        )
        return [spec for spec in candidates if spec is not None]


def resolve_mod_dir(explicit: Path | str | None = None) -> Path:
    """Resolve ETS2 ``mod/`` directory: explicit arg > ``ETS2_MOD_DIR`` > platform default."""
    if explicit is not None:
        return Path(explicit)
    env_dir = os.environ.get("ETS2_MOD_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    if os.name == "nt":
        if _DEFAULT_WINDOWS_DATA_MOD_DIR.is_dir():
            return _DEFAULT_WINDOWS_DATA_MOD_DIR
        return Path.home() / "Documents" / "Euro Truck Simulator 2" / "mod"
    return Path.home() / ".local" / "share" / "Euro Truck Simulator 2" / "mod"


def _parse_version_tuple(version_str: str) -> tuple[int, ...]:
    parts = tuple(int(part) for part in version_str.split("."))
    if len(parts) == 1 and 100 <= parts[0] < 1000:
        return (parts[0] // 100, parts[0] % 100)
    return parts


def _is_st_variant(variant: str | None) -> bool:
    if variant is None:
        return False
    tokens = [tok for tok in variant.lower().split("_") if tok]
    return "st" in tokens


def _make_pack_spec(
    pack: ProModsPackId,
    role: ProModsPackRole,
    path: Path,
    *,
    version: tuple[int, ...] = (),
    is_explicit_override: bool = False,
    is_special_transport: bool = False,
) -> ProModsPackSpec:
    return ProModsPackSpec(
        pack=pack,
        role=role,
        path=path,
        version=version,
        layer_name=f"promods_{pack}_{role}",
        priority=_PACK_PRIORITIES[(pack, role)],
        is_explicit_override=is_explicit_override,
        is_special_transport=is_special_transport,
    )


def _resolve_override(
    pack: ProModsPackId,
    role: ProModsPackRole,
    override_path: Path | None,
) -> ProModsPackSpec | None:
    if override_path is None:
        return None
    if not override_path.exists():
        raise FileNotFoundError(
            f"Explicit ProMods {pack.upper()} {role} override does not exist: {override_path}"
        )
    pattern = _SLOT_PATTERNS[(pack, role)]
    match = pattern.fullmatch(override_path.name)
    version = _parse_version_tuple(match.group("version")) if match is not None else ()
    is_st = (
        _is_st_variant(match.group("variant"))
        if match is not None and "variant" in match.groupdict()
        else False
    )
    return _make_pack_spec(
        pack,
        role,
        override_path,
        version=version,
        is_explicit_override=True,
        is_special_transport=is_st,
    )


def _select_best_candidate(
    pack: ProModsPackId,
    role: ProModsPackRole,
    candidates: list[tuple[Path, tuple[int, ...], bool]],
) -> ProModsPackSpec | None:
    if not candidates:
        return None

    def _sort_key(
        item: tuple[Path, tuple[int, ...], bool],
    ) -> tuple[tuple[int, ...], int, int, str]:
        path, version, is_st = item
        name_lower = path.name.lower()
        # Highest numeric version first; non-ST preferred over ST at equal version;
        # explicit -eu- naming slightly preferred over legacy shorthand at equal version.
        return (
            version,
            0 if is_st else 1,
            1 if "-eu-" in name_lower else 0,
            name_lower,
        )

    best_path, best_version, best_is_st = max(candidates, key=_sort_key)
    return _make_pack_spec(
        pack,
        role,
        best_path,
        version=best_version,
        is_explicit_override=False,
        is_special_transport=best_is_st,
    )


def discover_promods_packs(
    mod_dir: Path | None = None,
    *,
    require_eu_def: bool = True,
    require_all_packs: bool = False,
    eu_def: Path | None = None,
    eu_assets: Path | None = None,
    me_def: Path | None = None,
    me_assets: Path | None = None,
    ma_def: Path | None = None,
    ma_assets: Path | None = None,
    tgs_def: Path | None = None,
    tgs_assets: Path | None = None,
) -> ProModsPackSet:
    """Auto-discover installed ProMods EU/TGS/ME/MA def/defmap + assets archives (D-06)."""
    discovered: dict[
        tuple[ProModsPackId, ProModsPackRole], list[tuple[Path, tuple[int, ...], bool]]
    ] = {slot: [] for slot in _SLOT_PATTERNS}

    if mod_dir is not None and mod_dir.is_dir():
        for entry in sorted(mod_dir.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_file():
                continue
            for slot, pattern in _SLOT_PATTERNS.items():
                match = pattern.fullmatch(entry.name)
                if match is not None:
                    version = _parse_version_tuple(match.group("version"))
                    variant = match.group("variant") if "variant" in match.groupdict() else None
                    discovered[slot].append((entry, version, _is_st_variant(variant)))
                    break

    resolved_eu_def = _resolve_override("eu", "def", eu_def) or _select_best_candidate(
        "eu", "def", discovered[("eu", "def")]
    )
    resolved_eu_assets = _resolve_override("eu", "assets", eu_assets) or _select_best_candidate(
        "eu", "assets", discovered[("eu", "assets")]
    )
    resolved_tgs_def = _resolve_override("tgs", "defmap", tgs_def) or _select_best_candidate(
        "tgs", "defmap", discovered[("tgs", "defmap")]
    )
    resolved_tgs_assets = _resolve_override("tgs", "assets", tgs_assets) or _select_best_candidate(
        "tgs", "assets", discovered[("tgs", "assets")]
    )
    resolved_me_def = _resolve_override("me", "defmap", me_def) or _select_best_candidate(
        "me", "defmap", discovered[("me", "defmap")]
    )
    resolved_me_assets = _resolve_override("me", "assets", me_assets) or _select_best_candidate(
        "me", "assets", discovered[("me", "assets")]
    )
    resolved_ma_def = _resolve_override("ma", "defmap", ma_def) or _select_best_candidate(
        "ma", "defmap", discovered[("ma", "defmap")]
    )
    resolved_ma_assets = _resolve_override("ma", "assets", ma_assets) or _select_best_candidate(
        "ma", "assets", discovered[("ma", "assets")]
    )

    pack_set = ProModsPackSet(
        mod_dir=mod_dir,
        eu_def=resolved_eu_def,
        eu_assets=resolved_eu_assets,
        tgs_def=resolved_tgs_def,
        tgs_assets=resolved_tgs_assets,
        me_def=resolved_me_def,
        me_assets=resolved_me_assets,
        ma_def=resolved_ma_def,
        ma_assets=resolved_ma_assets,
    )

    if require_all_packs:
        missing_slots: list[str] = []
        required_map: list[tuple[str, ProModsPackSpec | None]] = [
            ("EU def (--promods-eu)", pack_set.eu_def),
            ("EU assets (--promods-eu-assets)", pack_set.eu_assets),
            ("TGS defmap (--promods-tgs)", pack_set.tgs_def),
            ("TGS assets (--promods-tgs-assets)", pack_set.tgs_assets),
            ("ME defmap (--promods-me)", pack_set.me_def),
            ("ME assets (--promods-me-assets)", pack_set.me_assets),
            ("MA defmap (--promods-ma)", pack_set.ma_def),
        ]
        for label, spec in required_map:
            if spec is None:
                missing_slots.append(label)
        if missing_slots:
            joined = ", ".join(missing_slots)
            raise FileNotFoundError(
                f"Missing required ProMods packs under --require-all-packs "
                f"(mod_dir={mod_dir}): {joined}"
            )
    elif require_eu_def and pack_set.eu_def is None:
        raise FileNotFoundError(
            f"Required ProMods EU def archive not found in {mod_dir}; "
            "pass --mod-dir or --promods-eu <path>"
        )

    return pack_set


def ordered_pack_paths(pack_set: ProModsPackSet) -> list[tuple[str, Path]]:
    """Return ``(layer_name, path)`` pairs in official bottom-to-top EU < TGS < ME < MA order."""
    return [(spec.layer_name, spec.path) for spec in pack_set.ordered_packs()]


__all__ = [
    "ProModsPackEntry",
    "ProModsPackId",
    "ProModsPackRole",
    "ProModsPackSet",
    "ProModsPackSpec",
    "discover_promods_packs",
    "ordered_pack_paths",
    "resolve_mod_dir",
]
