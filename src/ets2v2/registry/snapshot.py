"""Locked schema_version=1 realism-snapshot models, SHA-256 manifest, and air-gapped verifier."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ets2v2.baseline.models import BaselineManifest, CountriesBaseline, LocalesBaseline
from ets2v2.normalize.fx import round_eur_per_liter
from ets2v2.normalize.lockfile import load_prices_lockfile
from ets2v2.normalize.models import PricesLockfile
from ets2v2.registry.loader import load_law_registry, serialize_registry_json_bytes
from ets2v2.registry.models import (
    LaneSpeedOverride,
    LawRegistryBundle,
    RoadVehicleClass,
    Season,
)
from ets2v2.registry.timezone import (
    DEFAULT_ANCHOR_YEAR,
    resolve_ets2_timezone,
    resolve_season_anchor_date,
)

_ROAD_VEHICLE_CLASSES: Final[tuple[RoadVehicleClass, ...]] = ("car", "truck", "bus")
_BASELINE_FUEL_SOURCE: Final[str] = "baseline_1.62"
_SHA256SUM_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^([0-9a-f]{64})  ([^\r\n/\\]+)$")
MAX_SNAPSHOT_BYTES: Final[int] = 64 * 1024 * 1024
MAX_CHECKSUMS_BYTES: Final[int] = 1 * 1024 * 1024


class RealismSnapshotFuel(BaseModel):
    """Per-country fuel snapshot block (extensible in Phase 3 for live local grades)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    currency: str = Field(pattern=r"^[A-Z]{3}$")
    eur_per_liter: float = Field(ge=0.0, allow_inf_nan=False)
    local_prices: dict[str, float] = Field(default_factory=dict)
    source: str = Field(min_length=1)


class RealismSnapshotCountry(BaseModel):
    """Resolved per-country seasonal realism parameters inside a v1 snapshot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    iso2: str = Field(pattern=r"^[A-Z]{2}$")
    iso3: str = Field(pattern=r"^[a-z]{3}$")
    ets2_slug: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    iana_timezone: str = Field(min_length=1)
    time_zone: int
    time_zone_name: str = Field(min_length=1)
    observes_dst: bool
    lights_mandatory: bool
    driving_tired_offence: bool
    imperial_units: bool
    mass_limit_per_axle_count: list[int] = Field(min_length=3, max_length=12)
    speed_limits: dict[RoadVehicleClass, list[LaneSpeedOverride]]
    fuel: RealismSnapshotFuel


class RealismSnapshot(BaseModel):
    """Locked D-11 / D-02 ``schema_version: 1`` seasonal realism snapshot contract."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    edition: Season
    anchor_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    baseline_game_version: str = Field(min_length=1)
    countries: dict[str, RealismSnapshotCountry]

    @field_validator("anchor_date")
    @classmethod
    def _validate_calendar_anchor_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"Invalid ISO calendar anchor_date {value!r}: {exc}") from exc
        return value


class SnapshotVerificationResult(BaseModel):
    """Structured offline verification report for a v1 realism snapshot (D-03, D-04)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ok: bool
    snapshot_path: str
    schema_version: int | None = None
    edition: Season | None = None
    anchor_date: str | None = None
    country_count: int = 0
    sha256: str | None = None
    checksum_verified: bool = False
    issues: list[str] = Field(default_factory=list)


def build_realism_snapshot(
    registry: LawRegistryBundle,
    baseline_countries: CountriesBaseline,
    baseline_locales: LocalesBaseline,
    edition: Season,
    *,
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
    override_date: date | None = None,
    baseline_game_version: str = "1.62.3.3",
    prices_lock: PricesLockfile | None = None,
    vanilla_only: bool | None = None,
) -> RealismSnapshot:
    """Resolve registry countries for ``edition`` into a deterministic v1 snapshot."""
    ref_date = resolve_season_anchor_date(
        edition,
        anchor_year=anchor_year,
        override_date=override_date,
    )
    effective_vanilla_only = (prices_lock is None) if vanilla_only is None else vanilla_only
    baseline_by_slug = {country.slug: country for country in baseline_countries.countries}
    mapping_by_iso2 = {entry.iso2: entry for entry in registry.mappings.countries}

    countries: dict[str, RealismSnapshotCountry] = {}
    for iso2 in sorted(registry.laws_by_iso2):
        law = registry.laws_by_iso2[iso2]
        mapping_entry = mapping_by_iso2[iso2]
        if effective_vanilla_only and not mapping_entry.vanilla_1_62:
            continue

        bl_country = baseline_by_slug.get(law.ets2_slug)
        if mapping_entry.vanilla_1_62:
            if bl_country is None:
                raise ValueError(f"Missing baseline country entry for {iso2} ({law.ets2_slug!r})")
            imperial_units = bl_country.imperial_units is True
            if imperial_units != (law.speed_unit == "mph"):
                raise ValueError(f"imperial_units parity mismatch for {iso2} ({law.ets2_slug!r})")
        else:
            imperial_units = law.speed_unit == "mph"

        if prices_lock is not None:
            lock_entry = prices_lock.countries.get(iso2)
            if lock_entry is None:
                raise ValueError(f"Prices lockfile is missing entry for {iso2!r}")
            if lock_entry.currency != law.currency:
                raise ValueError(
                    f"Currency mismatch for {iso2}: prices lockfile has "
                    f"{lock_entry.currency!r}, law registry expects {law.currency!r}"
                )
            fuel = RealismSnapshotFuel(
                currency=lock_entry.currency,
                eur_per_liter=round_eur_per_liter(lock_entry.eur_per_liter),
                local_prices={
                    grade: float(price) for grade, price in sorted(lock_entry.local_prices.items())
                },
                source=lock_entry.source,
            )
        else:
            if bl_country is None or bl_country.fuel_price is None:
                raise ValueError(f"Missing baseline fuel_price for {iso2} ({law.ets2_slug!r})")
            fuel = RealismSnapshotFuel(
                currency=law.currency,
                eur_per_liter=bl_country.fuel_price,
                local_prices={},
                source=_BASELINE_FUEL_SOURCE,
            )

        resolved_tz = resolve_ets2_timezone(
            law.iana_timezone,
            ref_date,
            baseline_locales.tz_keys,
        )
        seasonal_rules = law.summer if edition == "summer" else law.winter
        speed_limits: dict[RoadVehicleClass, list[LaneSpeedOverride]] = {
            vehicle_class: list(seasonal_rules.speed_limits[vehicle_class])
            for vehicle_class in _ROAD_VEHICLE_CLASSES
        }

        countries[iso2] = RealismSnapshotCountry(
            iso2=law.iso2,
            iso3=law.iso3,
            ets2_slug=law.ets2_slug,
            iana_timezone=law.iana_timezone,
            time_zone=resolved_tz.offset_minutes,
            time_zone_name=resolved_tz.ets2_time_zone_name,
            observes_dst=resolved_tz.observes_dst,
            lights_mandatory=seasonal_rules.lights_mandatory,
            driving_tired_offence=law.driving_tired_offence,
            imperial_units=imperial_units,
            mass_limit_per_axle_count=list(law.mass_limit_per_axle_count),
            speed_limits=speed_limits,
            fuel=fuel,
        )

    return RealismSnapshot(
        schema_version=1,
        edition=edition,
        anchor_date=ref_date.isoformat(),
        baseline_game_version=baseline_game_version,
        countries=countries,
    )


def serialize_snapshot_bytes(snapshot: RealismSnapshot) -> bytes:
    """Serialize a v1 realism snapshot to canonical UTF-8 no-BOM LF sorted JSON bytes."""
    return serialize_registry_json_bytes(snapshot)


def write_realism_snapshot(snapshot: RealismSnapshot, path: Path) -> bytes:
    """Write a canonical v1 realism snapshot JSON file to ``path`` and return its bytes."""
    raw = serialize_snapshot_bytes(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _read_bounded_bytes(path: Path, *, max_bytes: int, label: str) -> bytes:
    """Read file bytes up to ``max_bytes`` to guard against unbounded untrusted reads."""
    if not path.is_file():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"{label} {path} exceeds maximum allowed size ({size} > {max_bytes} bytes)"
        )
    with path.open("rb") as fh:
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"{label} {path} exceeded maximum allowed size ({max_bytes} bytes)")
    return data


def load_realism_snapshot(path: Path) -> RealismSnapshot:
    """Strictly load and validate a UTF-8 no-BOM LF ``schema_version=1`` realism snapshot."""
    raw = _read_bounded_bytes(path, max_bytes=MAX_SNAPSHOT_BYTES, label="Realism snapshot")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"Realism snapshot must not contain a UTF-8 BOM: {path}")
    if b"\r" in raw:
        raise ValueError(f"Realism snapshot must use LF line endings only: {path}")
    return RealismSnapshot.model_validate_json(raw.decode("utf-8"))


def render_sha256sums(paths: Sequence[Path]) -> bytes:
    """Render GNU coreutils ``SHA256SUMS.txt`` (``<sha256>  <filename>\\n``) sorted by filename."""
    entries: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Cannot checksum missing file: {path}")
        name = path.name
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise ValueError(f"Invalid filename for SHA256SUMS manifest: {name!r}")
        if name in seen_names:
            raise ValueError(f"Duplicate filename in SHA256SUMS manifest: {name!r}")
        seen_names.add(name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append((name, digest))
    entries.sort(key=lambda item: item[0])
    text = "".join(f"{digest}  {name}\n" for name, digest in entries)
    return text.encode("utf-8")


def write_sha256sums(paths: Sequence[Path], out_path: Path) -> bytes:
    """Write a deterministic ``SHA256SUMS.txt`` manifest to ``out_path`` and return its bytes."""
    raw = render_sha256sums(paths)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(raw)
    return raw


def parse_sha256sums(path: Path) -> dict[str, str]:
    """Strictly parse a UTF-8 no-BOM LF ``SHA256SUMS.txt`` manifest into filename -> hex sha256."""
    raw = _read_bounded_bytes(path, max_bytes=MAX_CHECKSUMS_BYTES, label="SHA256SUMS manifest")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"SHA256SUMS manifest must not contain a UTF-8 BOM: {path}")
    if b"\r" in raw:
        raise ValueError(f"SHA256SUMS manifest must use LF line endings only: {path}")
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"SHA256SUMS manifest is empty: {path}")

    entries: dict[str, str] = {}
    for line_no, line in enumerate(lines, start=1):
        match = _SHA256SUM_LINE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"Malformed SHA256SUMS line {line_no} in {path}: {line!r}")
        digest, name = match.group(1), match.group(2)
        if name in {".", ".."}:
            raise ValueError(f"Invalid filename {name!r} at line {line_no} in {path}")
        if name in entries:
            raise ValueError(f"Duplicate filename {name!r} in SHA256SUMS manifest {path}")
        entries[name] = digest
    return entries


def _verify_and_parse_snapshot(
    snapshot_path: Path,
    *,
    checksums_path: Path | None = None,
    expected_edition: Season | None = None,
) -> tuple[SnapshotVerificationResult, RealismSnapshot | None]:
    """Verify & parse a v1 snapshot from a single bounded read (eliminates TOCTOU double-read)."""
    issues: list[str] = []
    try:
        raw = _read_bounded_bytes(
            snapshot_path,
            max_bytes=MAX_SNAPSHOT_BYTES,
            label="Realism snapshot",
        )
    except FileNotFoundError as exc:
        return (
            SnapshotVerificationResult(
                ok=False,
                snapshot_path=str(snapshot_path),
                issues=[str(exc)],
            ),
            None,
        )
    except (OSError, ValueError) as exc:
        return (
            SnapshotVerificationResult(
                ok=False,
                snapshot_path=str(snapshot_path),
                issues=[f"Unable to read realism snapshot {snapshot_path}: {exc}"],
            ),
            None,
        )

    digest = hashlib.sha256(raw).hexdigest()
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(f"UTF-8 BOM detected in realism snapshot: {snapshot_path}")
    if b"\r" in raw:
        issues.append(f"Non-LF line endings detected in realism snapshot: {snapshot_path}")

    text: str | None = None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(f"Invalid UTF-8 in realism snapshot {snapshot_path}: {exc}")

    snapshot: RealismSnapshot | None = None
    if text is not None:
        try:
            snapshot = RealismSnapshot.model_validate_json(text)
        except ValidationError as exc:
            issues.append(f"Invalid schema_version=1 realism snapshot: {exc}")

    if snapshot is not None:
        if not snapshot.countries:
            issues.append("Realism snapshot contains zero countries")
        for key, country in snapshot.countries.items():
            if key != country.iso2:
                issues.append(f"Country key {key!r} does not match country.iso2 {country.iso2!r}")
        if expected_edition is not None and snapshot.edition != expected_edition:
            issues.append(
                f"Edition mismatch: expected {expected_edition!r}, got {snapshot.edition!r}"
            )

    effective_checksums: Path | None = checksums_path
    if effective_checksums is None:
        sibling = snapshot_path.parent / "SHA256SUMS.txt"
        if sibling.is_file():
            effective_checksums = sibling

    checksum_verified = False
    if effective_checksums is not None:
        try:
            manifest = parse_sha256sums(effective_checksums)
        except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as exc:
            issues.append(f"Invalid checksum manifest {effective_checksums}: {exc}")
        else:
            expected_digest = manifest.get(snapshot_path.name)
            if expected_digest is None:
                issues.append(
                    f"Snapshot {snapshot_path.name!r} not found in checksum manifest "
                    f"{effective_checksums}"
                )
            elif not hmac.compare_digest(digest, expected_digest):
                issues.append(
                    f"SHA-256 mismatch for {snapshot_path.name!r}: "
                    f"expected {expected_digest}, got {digest}"
                )
            else:
                checksum_verified = True

    result = SnapshotVerificationResult(
        ok=not issues,
        snapshot_path=str(snapshot_path),
        schema_version=snapshot.schema_version if snapshot is not None else None,
        edition=snapshot.edition if snapshot is not None else None,
        anchor_date=snapshot.anchor_date if snapshot is not None else None,
        country_count=len(snapshot.countries) if snapshot is not None else 0,
        sha256=digest,
        checksum_verified=checksum_verified,
        issues=issues,
    )
    return result, (snapshot if result.ok else None)


def verify_snapshot_file(
    snapshot_path: Path,
    *,
    checksums_path: Path | None = None,
    expected_edition: Season | None = None,
) -> SnapshotVerificationResult:
    """Verify a v1 realism snapshot offline (hygiene, schema, edition, constant-time SHA-256)."""
    result, _ = _verify_and_parse_snapshot(
        snapshot_path,
        checksums_path=checksums_path,
        expected_edition=expected_edition,
    )
    return result


def load_or_build_snapshot(
    edition: Season,
    *,
    snapshot_path: Path | None = None,
    checksums_path: Path | None = None,
    laws_dir: Path = Path("data/laws"),
    mappings_path: Path = Path("data/mappings/ets2_countries.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    prices_lock_path: Path = Path("state/prices.lock.json"),
    anchor_year: int = DEFAULT_ANCHOR_YEAR,
) -> RealismSnapshot:
    """Load & verify an explicit v1 snapshot (incl. sibling SHA256SUMS.txt) or build offline."""
    if snapshot_path is not None:
        verification, parsed_snapshot = _verify_and_parse_snapshot(
            snapshot_path,
            checksums_path=checksums_path,
            expected_edition=edition,
        )
        if not verification.ok or parsed_snapshot is None:
            joined = "; ".join(verification.issues)
            raise ValueError(f"Snapshot verification failed for {snapshot_path}: {joined}")
        return parsed_snapshot

    registry = load_law_registry(laws_dir, mappings_path)
    bl_countries = CountriesBaseline.model_validate_json(
        (baseline_dir / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (baseline_dir / "locales.json").read_text("utf-8")
    )
    manifest_path = baseline_dir / "manifest.json"
    if manifest_path.is_file():
        bl_manifest = BaselineManifest.model_validate_json(manifest_path.read_text("utf-8"))
        game_version = bl_manifest.game_version
    else:
        game_version = registry.mappings.baseline_game_version

    prices_lock = load_prices_lockfile(prices_lock_path)
    return build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        edition,
        anchor_year=anchor_year,
        baseline_game_version=game_version,
        prices_lock=prices_lock,
    )
