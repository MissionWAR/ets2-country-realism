"""Integration, determinism, VFS/ZipArchive, and CLI tests for dual Core packaging."""

from __future__ import annotations

import hashlib
import pathlib
import zipfile

import pytest

from ets2v2.cli import main
from ets2v2.package.builder import (
    BuiltEditionPaths,
    build_core_edition,
    build_core_editions,
)
from ets2v2.registry.models import Season
from ets2v2.sii.country import parse_country_data
from ets2v2.sii.document import SiiDocument
from ets2v2.sii.hygiene import validate_sii_hygiene
from ets2v2.sii.lexer import unquote_sii_string
from ets2v2.sii.speed_limits import parse_speed_limits
from ets2v2.vfs import VfsStack, ZipArchive

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
ICONS_DIR = REPO_ROOT / "assets" / "icons"
PRICES_LOCK_PATH = REPO_ROOT / "state" / "prices.lock.json"

EXPECTED_TOTEM_BOARD_COUNT = 460
EXPECTED_LOCALE_MODULE_COUNT = 43
EXPECTED_WORKSHOP_FILE_COUNT = 76 + EXPECTED_TOTEM_BOARD_COUNT + EXPECTED_LOCALE_MODULE_COUNT
EXPECTED_LOCAL_ZIP_ENTRY_COUNT = 75 + EXPECTED_TOTEM_BOARD_COUNT + EXPECTED_LOCALE_MODULE_COUNT


def _hash_tree(root: pathlib.Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for file_path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = file_path.relative_to(root).as_posix()
        digests[rel] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return digests


def test_build_core_editions_workshop_tree_and_local_zip_contracts(
    tmp_path: pathlib.Path,
) -> None:
    built = build_core_editions(
        tmp_path,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
        package_version="1.62-2026.47",
    )
    assert set(built.keys()) == {"summer", "winter"}

    expected_zip_names: dict[Season, str] = {
        "summer": "ETS2V2_Core_Summer.zip",
        "winter": "ETS2V2_Core_Winter.zip",
    }

    for edition, info in built.items():
        assert isinstance(info, BuiltEditionPaths)
        assert info.edition == edition
        assert info.package_version == "1.62-2026.47"
        assert info.workshop_dir == tmp_path / "workshop" / edition
        assert info.local_zip_path == tmp_path / "local" / expected_zip_names[edition]
        assert info.workshop_file_count == EXPECTED_WORKSHOP_FILE_COUNT == 579

        # D-06: strictly unpacked universal/, NEVER universal.zip beside it
        assert (info.workshop_dir / "versions.sii").is_file()
        assert (info.workshop_dir / "universal").is_dir()
        assert not (info.workshop_dir / "universal.zip").exists()
        root_entries = sorted(p.name for p in info.workshop_dir.iterdir())
        assert root_entries == ["universal", "versions.sii"]

        workshop_files = sorted(
            p.relative_to(info.workshop_dir).as_posix()
            for p in info.workshop_dir.rglob("*")
            if p.is_file()
        )
        assert len(workshop_files) == EXPECTED_WORKSHOP_FILE_COUNT

        # D-05: ZERO def/country.sii or def/country.*.sii emitted
        assert not any(
            path.endswith("def/country.sii")
            or (path.startswith("universal/def/country.") and path.endswith(".sii"))
            for path in workshop_files
        )

        # TOT-01 / Zero-DDS checks in Workshop root
        assert "universal/def/sign/board/gas_de_big_diesel.sii" in workshop_files
        assert "universal/def/sign/board/gas_ie_pegi_95.sii" in workshop_files
        assert "universal/locale/fr_ca/local_module.ets2v2_fuel.sii" in workshop_files
        assert "universal/locale/fr_qc/local_module.ets2v2_fuel.sii" not in workshop_files
        assert "universal/def/sign/board/gas_empty.sii" not in workshop_files
        assert not any(path.lower().endswith((".dds", ".tobj")) for path in workshop_files)

        # Verbatim icon copy check (D-07)
        committed_icon = (ICONS_DIR / f"{edition}.jpg").read_bytes()
        assert (info.workshop_dir / "universal" / "mod_icon.jpg").read_bytes() == committed_icon

        # Workshop manifest strictly omits display_name and compatible_versions[]
        ws_manifest_raw = (info.workshop_dir / "universal" / "manifest.sii").read_bytes()
        assert validate_sii_hygiene(ws_manifest_raw, require_siinunit=True) == []
        ws_manifest_text = ws_manifest_raw.decode("utf-8")
        assert "display_name" not in ws_manifest_text
        assert "compatible_versions" not in ws_manifest_text

        # Local ZIP deterministic metadata, sorted POSIX paths, zero traversal/backslash
        assert info.local_zip_path.is_file()
        assert info.local_zip_sha256 == hashlib.sha256(info.local_zip_path.read_bytes()).hexdigest()

        with zipfile.ZipFile(info.local_zip_path, "r") as zf:
            infos = zf.infolist()
            assert len(infos) == EXPECTED_LOCAL_ZIP_ENTRY_COUNT == 578
            names = [entry.filename for entry in infos]
            assert names == sorted(names)
            assert "def/sign/board/gas_de_big_diesel.sii" in names
            assert "def/sign/board/gas_ie_pegi_95.sii" in names
            assert "locale/fr_ca/local_module.ets2v2_fuel.sii" in names
            assert "locale/fr_qc/local_module.ets2v2_fuel.sii" not in names
            assert "def/sign/board/gas_empty.sii" not in names
            assert not any(name.lower().endswith((".dds", ".tobj")) for name in names)
            for entry in infos:
                assert "\\" not in entry.filename
                assert ".." not in entry.filename
                assert not entry.filename.startswith("/")
                assert entry.date_time == (1980, 1, 1, 0, 0, 0)
                assert entry.create_system == 3
                assert entry.external_attr == (0o100644 << 16)
                assert entry.compress_type == zipfile.ZIP_DEFLATED

            assert zf.read("mod_icon.jpg") == committed_icon
            local_manifest_raw = zf.read("manifest.sii")
            assert validate_sii_hygiene(local_manifest_raw, require_siinunit=True) == []
            local_doc = SiiDocument.parse(local_manifest_raw, require_siinunit=True)
            unit = local_doc.get_unit(class_name="mod_package")
            assert unit is not None
            disp = unit.get_scalar("display_name")
            assert disp is not None
            assert edition.capitalize() in unquote_sii_string(disp.raw_value)[0]
            assert unit.get_attributes("compatible_versions") == []

        # Local ZIP mounts cleanly through ets2v2.vfs.ZipArchive and VfsStack
        with ZipArchive(info.local_zip_path) as archive:
            assert archive.diagnostics == []
            listed = archive.list_paths()
            assert len(listed) == EXPECTED_LOCAL_ZIP_ENTRY_COUNT
            assert "def/country.sii" not in listed
            assert "def/sign/board/gas_de_big_diesel.sii" in listed
            assert "locale/fr_ca/local_module.ets2v2_fuel.sii" in listed
            ee_sui = archive.read_bytes("def/country/estonia.sui")
            assert parse_country_data(ee_sui).name == "Eesti"
            is_speeds = archive.read_bytes("def/country/iceland/speed_limits.sii")
            is_truck = parse_speed_limits(is_speeds).get_block("truck")
            assert is_truck is not None
            assert [lane.limit for lane in is_truck.lanes] == [80, 80, 80]

        with VfsStack.from_paths([info.local_zip_path]) as stack:
            assert stack.diagnostics() == []
            assert stack.exists("manifest.sii")
            assert stack.exists("def/country/bosnia.sui")
            assert stack.exists("def/sign/board/gas_ie_pegi_95.sii")
            assert stack.exists("locale/fr_ca/local_module.ets2v2_fuel.sii")
            assert len(parse_country_data(stack.read_bytes("def/country/bosnia.sui")).regions) == 6


def test_build_core_editions_is_byte_deterministic_across_independent_runs(
    tmp_path: pathlib.Path,
) -> None:
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"

    built_a = build_core_editions(
        out_a,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
    )
    built_b = build_core_editions(
        out_b,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
    )

    for edition in ("summer", "winter"):
        assert built_a[edition].local_zip_sha256 == built_b[edition].local_zip_sha256
        assert (
            built_a[edition].local_zip_path.read_bytes()
            == built_b[edition].local_zip_path.read_bytes()
        )
        assert _hash_tree(built_a[edition].workshop_dir) == _hash_tree(
            built_b[edition].workshop_dir
        )

    assert built_a["summer"].local_zip_sha256 != built_a["winter"].local_zip_sha256


def test_build_core_edition_cleans_stale_workshop_files(tmp_path: pathlib.Path) -> None:
    stale_dir = tmp_path / "workshop" / "summer"
    stale_dir.mkdir(parents=True)
    stale_file = stale_dir / "universal.zip"
    stale_file.write_bytes(b"stale")

    built = build_core_edition(
        "summer",
        tmp_path,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
    )
    assert not stale_file.exists()
    assert built.workshop_file_count == EXPECTED_WORKSHOP_FILE_COUNT == 579


def test_build_core_edition_fails_on_missing_icon(tmp_path: pathlib.Path) -> None:
    empty_icons = tmp_path / "empty_icons"
    empty_icons.mkdir()
    with pytest.raises(FileNotFoundError, match=r"summer\.jpg"):
        build_core_edition(
            "summer",
            tmp_path / "out",
            laws_dir=LAWS_DIR,
            mappings_path=MAPPINGS_PATH,
            baseline_dir=BASELINE_DIR,
            icons_dir=empty_icons,
        )


def test_cli_package_icons_and_build(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    icons_out = tmp_path / "icons"
    exit_icons = main(["package", "icons", "--out-dir", str(icons_out)])
    captured_icons = capsys.readouterr()
    assert exit_icons == 0
    assert (icons_out / "summer.jpg").is_file()
    assert (icons_out / "winter.jpg").is_file()
    assert "summer" in captured_icons.out.lower()

    dist_out = tmp_path / "dist"
    exit_build = main(
        [
            "package",
            "build",
            "--edition",
            "all",
            "--out-dir",
            str(dist_out),
            "--laws-dir",
            str(LAWS_DIR),
            "--mappings",
            str(MAPPINGS_PATH),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--icons-dir",
            str(ICONS_DIR),
            "--prices-lock",
            str(PRICES_LOCK_PATH),
            "--package-version",
            "1.62-2026.47",
            "--author",
            "ETS2 World Realism",
        ]
    )
    captured_build = capsys.readouterr()
    assert exit_build == 0
    assert "summer" in captured_build.out.lower()
    assert "winter" in captured_build.out.lower()
    assert (dist_out / "workshop" / "summer" / "versions.sii").is_file()
    assert (dist_out / "workshop" / "winter" / "versions.sii").is_file()
    assert (dist_out / "local" / "ETS2V2_Core_Summer.zip").is_file()
    assert (dist_out / "local" / "ETS2V2_Core_Winter.zip").is_file()

    # Invalid --date returns exit code 1 with error on stderr
    exit_bad_date = main(
        [
            "package",
            "build",
            "--edition",
            "summer",
            "--out-dir",
            str(dist_out),
            "--date",
            "not-a-date",
        ]
    )
    captured_err = capsys.readouterr()
    assert exit_bad_date == 1
    assert "invalid --date" in captured_err.err.lower()
