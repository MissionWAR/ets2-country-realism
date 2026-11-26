"""Unit tests for canonical SHA-256 hashing, ISO-week versioning, and PublishedLedger."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from ets2_realism.package.builder import build_core_edition
from ets2_realism.publish.ledger import (
    CANONICAL_VERSION_SENTINEL,
    PublishedEditionState,
    PublishedLedger,
    compute_workshop_canonical_sha256,
    load_published_ledger,
    resolve_next_package_version,
    serialize_ledger_bytes,
    write_published_ledger,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
ICONS_DIR = REPO_ROOT / "assets" / "icons"


def _sample_edition_state(
    *,
    package_version: str = "1.62-2026.47",
    payload_sha256: str | None = None,
    snapshot_sha256: str | None = None,
    anchor_date: str = "2026-07-15",
) -> PublishedEditionState:
    return PublishedEditionState(
        anchor_date=anchor_date,
        baseline_game_version="1.62.3.3",
        country_count=36,
        file_count=76,
        package_version=package_version,
        payload_sha256=payload_sha256 or hashlib.sha256(b"payload").hexdigest(),
        snapshot_sha256=snapshot_sha256 or hashlib.sha256(b"snapshot").hexdigest(),
    )


def test_canonical_sha256_ignores_manifest_package_version_only(tmp_path: Path) -> None:
    out_a = tmp_path / "week47"
    out_b = tmp_path / "week48"

    built_a = build_core_edition(
        "summer",
        out_a,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        package_version="1.62-2026.47",
    )
    built_b = build_core_edition(
        "summer",
        out_b,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        package_version="1.62-2026.48",
    )

    manifest_a = (built_a.workshop_dir / "universal" / "manifest.sii").read_text("utf-8")
    manifest_b = (built_b.workshop_dir / "universal" / "manifest.sii").read_text("utf-8")
    assert '"1.62-2026.47"' in manifest_a
    assert '"1.62-2026.48"' in manifest_b
    assert manifest_a != manifest_b
    assert CANONICAL_VERSION_SENTINEL == "__CANONICAL__"

    hash_a = compute_workshop_canonical_sha256(built_a.workshop_dir)
    hash_b = compute_workshop_canonical_sha256(built_b.workshop_dir)
    assert len(hash_a) == 64
    assert hash_a == hash_b


@pytest.mark.parametrize(
    "rel_path",
    [
        "universal/def/country/germany.sui",
        "universal/def/country/germany/speed_limits.sii",
        "universal/description.txt",
        "versions.sii",
        "universal/mod_icon.jpg",
    ],
)
def test_canonical_sha256_detects_single_byte_mutation(tmp_path: Path, rel_path: str) -> None:
    built = build_core_edition(
        "winter",
        tmp_path / "build",
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        package_version="1.62-2026.47",
    )
    baseline_hash = compute_workshop_canonical_sha256(built.workshop_dir)

    target = built.workshop_dir / rel_path
    original = target.read_bytes()
    mutated = original + (b" " if rel_path.endswith((".sui", ".sii", ".txt")) else b"\x00")
    target.write_bytes(mutated)

    mutated_hash = compute_workshop_canonical_sha256(built.workshop_dir)
    assert mutated_hash != baseline_hash


def test_resolve_next_package_version_lifecycle() -> None:
    hash_v1 = hashlib.sha256(b"v1").hexdigest()
    hash_v2 = hashlib.sha256(b"v2").hexdigest()
    hash_v3 = hashlib.sha256(b"v3").hexdigest()
    hash_v4 = hashlib.sha256(b"v4").hexdigest()

    # 2026-11-20 is ISO week 2026-W47
    friday_w47 = date(2026, 11, 20)
    friday_w48 = date(2026, 11, 27)

    # First build
    version, changed = resolve_next_package_version(None, hash_v1, friday_w47)
    assert (version, changed) == ("1.62-2026.47", True)

    state_v1 = _sample_edition_state(package_version=version, payload_sha256=hash_v1)

    # Unchanged hash on a later ISO week -> clean no-op
    version_noop, changed_noop = resolve_next_package_version(state_v1, hash_v1, friday_w48)
    assert (version_noop, changed_noop) == ("1.62-2026.47", False)

    # Same-week change -> .2 suffix
    version_hotfix2, changed_hotfix2 = resolve_next_package_version(state_v1, hash_v2, friday_w47)
    assert (version_hotfix2, changed_hotfix2) == ("1.62-2026.47.2", True)

    state_v2 = _sample_edition_state(package_version=version_hotfix2, payload_sha256=hash_v2)

    # Third same-week change -> .3 suffix
    version_hotfix3, changed_hotfix3 = resolve_next_package_version(state_v2, hash_v3, friday_w47)
    assert (version_hotfix3, changed_hotfix3) == ("1.62-2026.47.3", True)

    state_v3 = _sample_edition_state(package_version=version_hotfix3, payload_sha256=hash_v3)

    # Next-week change -> resets to 1.62-2026.48
    version_next, changed_next = resolve_next_package_version(state_v3, hash_v4, friday_w48)
    assert (version_next, changed_next) == ("1.62-2026.48", True)

    # Non-ASCII Unicode digit suffix (e.g. superscript '²') falls back safely to .2
    state_unicode = _sample_edition_state(
        package_version="1.62-2026.47.\u00b2",
        payload_sha256=hash_v1,
    )
    version_u, changed_u = resolve_next_package_version(state_unicode, hash_v2, friday_w47)
    assert (version_u, changed_u) == ("1.62-2026.47.2", True)


def test_canonical_sha256_rejects_directory_junction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = build_core_edition(
        "summer",
        tmp_path / "build",
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        package_version="1.62-2026.47",
    )
    target_dir = (built.workshop_dir / "universal").resolve()

    def _fake_is_junction(self: Path) -> bool:
        return self.resolve() == target_dir

    monkeypatch.setattr(Path, "is_junction", _fake_is_junction, raising=False)
    with pytest.raises(ValueError, match="junction"):
        compute_workshop_canonical_sha256(built.workshop_dir)


def test_published_ledger_round_trip_and_strict_validation(tmp_path: Path) -> None:
    summer_state = _sample_edition_state(
        package_version="1.62-2026.47",
        payload_sha256=hashlib.sha256(b"summer-payload").hexdigest(),
        snapshot_sha256=hashlib.sha256(b"summer-snapshot").hexdigest(),
        anchor_date="2026-07-15",
    )
    winter_state = _sample_edition_state(
        package_version="1.62-2026.48",
        payload_sha256=hashlib.sha256(b"winter-payload").hexdigest(),
        snapshot_sha256=hashlib.sha256(b"winter-snapshot").hexdigest(),
        anchor_date="2026-01-15",
    )
    ledger = PublishedLedger(editions={"summer": summer_state, "winter": winter_state})

    out_path = tmp_path / "state" / "published.json"
    written = write_published_ledger(ledger, out_path)
    assert written == serialize_ledger_bytes(ledger)
    assert not written.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in written
    assert written.endswith(b"\n")

    parsed_text = written.decode("utf-8")
    assert parsed_text == json.dumps(json.loads(parsed_text), indent=2, sort_keys=True) + "\n"

    loaded = load_published_ledger(out_path)
    assert loaded == ledger
    assert loaded.editions["summer"].package_version == "1.62-2026.47"
    assert loaded.editions["winter"].package_version == "1.62-2026.48"

    # Strict schema rejects unknown fields and malformed SHA-256 digests
    with pytest.raises(ValidationError):
        PublishedLedger.model_validate_json('{"editions": {}, "schema_version": 1, "extra": true}')

    with pytest.raises(ValidationError):
        PublishedEditionState(
            anchor_date="2026-07-15",
            baseline_game_version="1.62.3.3",
            country_count=36,
            file_count=76,
            package_version="1.62-2026.47",
            payload_sha256="NOT-A-VALID-HEX-HASH",
            snapshot_sha256=hashlib.sha256(b"snap").hexdigest(),
        )
