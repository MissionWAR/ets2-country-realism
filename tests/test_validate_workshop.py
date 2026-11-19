"""Offline SCS Workshop Validator tests: DAG isolation, positive builds, CLI, and SCS rules."""

from __future__ import annotations

import ast
import io
import json
import pathlib
import shutil
import zipfile
from typing import cast

import pytest
from PIL import Image

from ets2v2.cli import main
from ets2v2.package import BuiltEditionPaths, build_core_editions
from ets2v2.validate import (
    MAX_DESCRIPTION_BYTES,
    MAX_ICON_BYTES,
    VALID_SCS_CATEGORIES,
    ValidationCollector,
    ValidationIssue,
    ValidationReport,
    validate_local_zip,
    validate_workshop_package,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
ICONS_DIR = REPO_ROOT / "assets" / "icons"
VALIDATE_PKG_DIR = REPO_ROOT / "src" / "ets2v2" / "validate"


@pytest.fixture(scope="module")
def built_editions(tmp_path_factory: pytest.TempPathFactory) -> dict[str, BuiltEditionPaths]:
    out_dir = tmp_path_factory.mktemp("core_dist")
    built = build_core_editions(
        out_dir,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
    )
    return {"summer": built["summer"], "winter": built["winter"]}


def _clone_workshop(src: pathlib.Path, dst: pathlib.Path) -> pathlib.Path:
    shutil.copytree(src, dst)
    return dst


def _rebuild_zip_with_mutations(
    src_zip: pathlib.Path,
    dst_zip: pathlib.Path,
    *,
    overrides: dict[str, bytes] | None = None,
    removals: set[str] | None = None,
    extra_entries: list[tuple[zipfile.ZipInfo, bytes]] | None = None,
) -> pathlib.Path:
    overrides = overrides or {}
    removals = removals or set()
    extra_entries = extra_entries or []

    with (
        zipfile.ZipFile(src_zip, "r") as zin,
        zipfile.ZipFile(dst_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout,
    ):
        for info in zin.infolist():
            if info.filename in removals:
                continue
            payload = overrides.get(info.filename, zin.read(info.filename))
            new_info = zipfile.ZipInfo(filename=info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            new_info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(new_info, payload)
        for zinfo, payload in extra_entries:
            zout.writestr(zinfo, payload)
    return dst_zip


def _issue_codes(report: ValidationReport) -> set[str]:
    return {issue.code for issue in report.issues}


def test_validate_package_has_zero_imports_from_ets2v2_package() -> None:
    """Enforce strictly acyclic Layer 7 DAG: ets2v2.validate NEVER imports ets2v2.package."""
    py_files = sorted(VALIDATE_PKG_DIR.rglob("*.py"))
    assert py_files, "Expected Python modules under src/ets2v2/validate/"

    violations: list[str] = []
    for py_file in py_files:
        tree = ast.parse(py_file.read_text("utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "ets2v2.package" or alias.name.startswith("ets2v2.package."):
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "ets2v2.package" or module.startswith("ets2v2.package."):
                    violations.append(f"{py_file.name}: from {module} import ...")
                elif module == "ets2v2":
                    for alias in node.names:
                        if alias.name == "package":
                            violations.append(f"{py_file.name}: from ets2v2 import package")

    assert violations == [], f"Forbidden imports from ets2v2.package: {violations}"


def test_valid_scs_categories_has_all_18_official_entries() -> None:
    assert len(VALID_SCS_CATEGORIES) == 18
    assert {"other", "ai_traffic", "truck", "map", "ui"} <= VALID_SCS_CATEGORIES


def test_validation_collector_treats_warnings_as_hard_failures_and_deduplicates() -> None:
    collector = ValidationCollector()
    collector.warning("WARN 00001", "manifest.sii", "display_name is not allowed in Workshop")
    collector.warning("WARN 00001", "manifest.sii", "display_name is not allowed in Workshop")

    report = collector.build_report("dist/workshop/summer", "workshop")
    assert isinstance(report, ValidationReport)
    assert report.ok is False
    assert report.error_count == 0
    assert report.warning_count == 1
    assert len(report.issues) == 1
    assert report.issues[0] == ValidationIssue(
        code="WARN 00001",
        severity="warning",
        path="manifest.sii",
        detail="display_name is not allowed in Workshop",
    )


def test_positive_validation_on_compiled_summer_and_winter_bundles(
    built_editions: dict[str, BuiltEditionPaths],
) -> None:
    for edition in ("summer", "winter"):
        info = built_editions[edition]
        workshop_report = validate_workshop_package(info.workshop_dir, baseline_dir=BASELINE_DIR)
        assert workshop_report.ok is True, workshop_report.issues
        assert workshop_report.mode == "workshop"
        assert workshop_report.error_count == 0
        assert workshop_report.warning_count == 0
        assert workshop_report.issues == []

        local_report = validate_local_zip(info.local_zip_path, baseline_dir=BASELINE_DIR)
        assert local_report.ok is True, local_report.issues
        assert local_report.mode == "local_zip"
        assert local_report.error_count == 0
        assert local_report.warning_count == 0
        assert local_report.issues == []


def test_cli_validate_workshop_and_local_end_to_end(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    info = built_editions["summer"]

    exit_help = main(["validate"])
    help_out = capsys.readouterr()
    assert exit_help == 0
    assert "workshop" in help_out.out
    assert "local" in help_out.out

    exit_ws = main(
        [
            "validate",
            "workshop",
            str(info.workshop_dir),
            "--baseline-dir",
            str(BASELINE_DIR),
            "--json",
        ]
    )
    ws_captured = capsys.readouterr()
    assert exit_ws == 0, ws_captured.err
    ws_payload = cast(dict[str, object], json.loads(ws_captured.out))
    assert ws_payload["ok"] is True
    assert ws_payload["mode"] == "workshop"
    assert ws_payload["error_count"] == 0
    assert ws_payload["warning_count"] == 0

    exit_local = main(
        [
            "validate",
            "local",
            str(info.local_zip_path),
            "--baseline-dir",
            str(BASELINE_DIR),
        ]
    )
    local_captured = capsys.readouterr()
    assert exit_local == 0, local_captured.err
    assert "passed" in local_captured.out.lower()

    missing = tmp_path / "does_not_exist"
    exit_missing_ws = main(
        ["validate", "workshop", str(missing), "--baseline-dir", str(BASELINE_DIR)]
    )
    missing_ws_out = capsys.readouterr()
    assert exit_missing_ws == 1
    assert "00002" in missing_ws_out.err

    exit_missing_zip = main(
        [
            "validate",
            "local",
            str(missing / "nope.zip"),
            "--baseline-dir",
            str(BASELINE_DIR),
        ]
    )
    missing_zip_out = capsys.readouterr()
    assert exit_missing_zip == 1
    assert "00002" in missing_zip_out.err


# ---------------------------------------------------------------------------
# SCS 00001: Generic error
# ---------------------------------------------------------------------------


def test_scs_00001_empty_versions_sii(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws")
    (ws / "versions.sii").write_bytes(b"SiiNunit\n{\n}\n")
    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00001" in _issue_codes(report)


def test_scs_00001_wrong_icon_dimensions(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws")
    buf = io.BytesIO()
    Image.new("RGB", (200, 100), (20, 40, 80)).save(buf, format="JPEG", quality=90)
    (ws / "universal" / "mod_icon.jpg").write_bytes(buf.getvalue())
    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00001" in _issue_codes(report)


def test_scs_00001_icon_path_with_subdirectory(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws")
    sub = ws / "universal" / "icons"
    sub.mkdir()
    shutil.move(str(ws / "universal" / "mod_icon.jpg"), str(sub / "mod_icon.jpg"))
    manifest = ws / "universal" / "manifest.sii"
    manifest.write_bytes(
        manifest.read_bytes().replace(b'icon: "mod_icon.jpg"', b'icon: "icons/mod_icon.jpg"')
    )
    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00001" in _issue_codes(report)


# ---------------------------------------------------------------------------
# SCS 00002: File not found
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_to_delete",
    [
        "versions.sii",
        "universal/manifest.sii",
        "universal/mod_icon.jpg",
        "universal/description.txt",
        "universal/def/country/albania.sui",
        "universal/def/country/albania/speed_limits.sii",
    ],
)
def test_scs_00002_missing_required_files(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
    rel_to_delete: str,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws")
    (ws / rel_to_delete).unlink()
    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00002" in _issue_codes(report)


def test_scs_00002_missing_declared_universal_dir(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws")
    shutil.rmtree(ws / "universal")
    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00002" in _issue_codes(report)


# ---------------------------------------------------------------------------
# SCS 00003: Not allowed
# ---------------------------------------------------------------------------


def test_scs_00003_stray_root_file_and_side_by_side_zip(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws1 = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_readme")
    (ws1 / "README.md").write_text("# Stray file\n", encoding="utf-8")
    r1 = validate_workshop_package(ws1)
    assert r1.ok is False
    assert "00003" in _issue_codes(r1)

    ws2 = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_both")
    shutil.copyfile(built_editions["summer"].local_zip_path, ws2 / "universal.zip")
    r2 = validate_workshop_package(ws2)
    assert r2.ok is False
    assert "00003" in _issue_codes(r2)


def test_scs_00003_two_universal_entries_and_invalid_package_name(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws1 = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_two_univ")
    (ws1 / "versions.sii").write_bytes(
        b"SiiNunit\n{\n"
        b'package_version_info : .universal\n{\n\tpackage_name: "universal"\n}\n'
        b'package_version_info : .universal2\n{\n\tpackage_name: "universal2"\n}\n'
        b"}\n"
    )
    shutil.copytree(ws1 / "universal", ws1 / "universal2")
    r1 = validate_workshop_package(ws1)
    assert r1.ok is False
    assert "00003" in _issue_codes(r1)

    ws2 = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_bad_pkg")
    (ws2 / "versions.sii").write_bytes(
        b'SiiNunit\n{\npackage_version_info : .universal\n{\n\tpackage_name: "Bad-Name!"\n}\n}\n'
    )
    r2 = validate_workshop_package(ws2)
    assert r2.ok is False
    assert "00003" in _issue_codes(r2)


def test_scs_00003_zip_renamed_scs_unreferenced_assets_and_forbidden_files(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_scs = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_scs")
    shutil.copyfile(built_editions["summer"].local_zip_path, ws_scs / "universal" / "mod.scs")
    r_scs = validate_workshop_package(ws_scs)
    assert r_scs.ok is False
    assert "00003" in _issue_codes(r_scs)

    ws_extra = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_extra")
    (ws_extra / "universal" / "extra.txt").write_text("unreferenced\n", encoding="utf-8")
    (ws_extra / "universal" / "extra.jpg").write_bytes(
        (ws_extra / "universal" / "mod_icon.jpg").read_bytes()
    )
    r_extra = validate_workshop_package(ws_extra)
    assert r_extra.ok is False
    assert "00003" in _issue_codes(r_extra)

    ws_json = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_json")
    (ws_json / "universal" / "debug.json").write_text("{}\n", encoding="utf-8")
    r_json = validate_workshop_package(ws_json)
    assert r_json.ok is False
    assert "00003" in _issue_codes(r_json)

    ws_csii = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_csii")
    (ws_csii / "universal" / "def" / "country.sii").write_bytes(b"SiiNunit\n{\n}\n")
    r_csii = validate_workshop_package(ws_csii)
    assert r_csii.ok is False
    assert "00003" in _issue_codes(r_csii)


def test_scs_00003_mod_package_outside_manifest_and_raw_zip_traversal(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_mod = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_mod")
    (ws_mod / "universal" / "def" / "extra.sii").write_bytes(
        b'SiiNunit\n{\nmod_package : .stray\n{\n\tauthor: "Bad"\n}\n}\n'
    )
    r_mod = validate_workshop_package(ws_mod)
    assert r_mod.ok is False
    assert "00003" in _issue_codes(r_mod)

    bad_bs_zip = _rebuild_zip_with_mutations(
        built_editions["summer"].local_zip_path,
        tmp_path / "backslash.zip",
        extra_entries=[(zipfile.ZipInfo(filename=r"def\country\extra.txt"), b"x\n")],
    )
    r_bs = validate_local_zip(bad_bs_zip)
    assert r_bs.ok is False
    assert "00003" in _issue_codes(r_bs)

    bad_dotdot_zip = _rebuild_zip_with_mutations(
        built_editions["summer"].local_zip_path,
        tmp_path / "dotdot.zip",
        extra_entries=[(zipfile.ZipInfo(filename="../escape.txt"), b"x\n")],
    )
    r_dd = validate_local_zip(bad_dotdot_zip)
    assert r_dd.ok is False
    assert "00003" in _issue_codes(r_dd)


# ---------------------------------------------------------------------------
# SCS 00004: Malformed file
# ---------------------------------------------------------------------------


def test_scs_00004_bom_crlf_missing_siinunit_3nk_and_corrupt_jpeg(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_bom = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_bom")
    manifest = ws_bom / "universal" / "manifest.sii"
    manifest.write_bytes(b"\xef\xbb\xbf" + manifest.read_bytes())
    r_bom = validate_workshop_package(ws_bom)
    assert r_bom.ok is False
    assert "00004" in _issue_codes(r_bom)

    ws_crlf = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_crlf")
    desc = ws_crlf / "universal" / "description.txt"
    desc.write_bytes(desc.read_bytes().replace(b"\n", b"\r\n"))
    r_crlf = validate_workshop_package(ws_crlf)
    assert r_crlf.ok is False
    assert "00004" in _issue_codes(r_crlf)

    ws_hdr = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_hdr")
    spd = ws_hdr / "universal" / "def" / "country" / "albania" / "speed_limits.sii"
    spd.write_bytes(b"country_speed_limit : .limit.car\n{\n\tvehicle_speed_class: car\n}\n")
    r_hdr = validate_workshop_package(ws_hdr)
    assert r_hdr.ok is False
    assert "00004" in _issue_codes(r_hdr)

    ws_3nk = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_3nk")
    (ws_3nk / "universal" / "def" / "country" / "albania" / "speed_limits.sii").write_bytes(
        b"3nK\x01\x00\x00\x00obfuscated"
    )
    r_3nk = validate_workshop_package(ws_3nk)
    assert r_3nk.ok is False
    assert "00004" in _issue_codes(r_3nk)

    ws_jpg = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_jpg")
    (ws_jpg / "universal" / "mod_icon.jpg").write_bytes(b"\xff\xd8\xff\xe0truncated_garbage")
    r_jpg = validate_workshop_package(ws_jpg)
    assert r_jpg.ok is False
    assert "00004" in _issue_codes(r_jpg)


# ---------------------------------------------------------------------------
# SCS 00005: Missing required attribute
# ---------------------------------------------------------------------------


def test_scs_00005_missing_mp_optional_invalid_category_and_missing_author(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_mp = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_mp")
    m_mp = ws_mp / "universal" / "manifest.sii"
    m_mp.write_bytes(m_mp.read_bytes().replace(b"\tmp_mod_optional: true\n", b""))
    r_mp = validate_workshop_package(ws_mp)
    assert r_mp.ok is False
    assert "00005" in _issue_codes(r_mp)

    ws_cat = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_cat")
    m_cat = ws_cat / "universal" / "manifest.sii"
    m_cat.write_bytes(m_cat.read_bytes().replace(b'category[]: "other"', b'category[]: "realism"'))
    r_cat = validate_workshop_package(ws_cat)
    assert r_cat.ok is False
    assert "00005" in _issue_codes(r_cat)

    ws_auth = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_auth")
    m_auth = ws_auth / "universal" / "manifest.sii"
    m_auth.write_bytes(m_auth.read_bytes().replace(b'\tauthor: "ETS2 World Realism"\n', b""))
    r_auth = validate_workshop_package(ws_auth)
    assert r_auth.ok is False
    assert "00005" in _issue_codes(r_auth)


# ---------------------------------------------------------------------------
# SCS 00006: Access denied
# ---------------------------------------------------------------------------


def test_scs_00006_permission_error_reported_cleanly(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_perm")
    target_file = (ws / "universal" / "manifest.sii").resolve()
    orig_read_bytes = pathlib.Path.read_bytes

    def _deny_manifest(self: pathlib.Path) -> bytes:
        if self.resolve() == target_file:
            raise PermissionError("Simulated OS permission denial")
        return orig_read_bytes(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", _deny_manifest)
    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00006" in _issue_codes(report)


# ---------------------------------------------------------------------------
# SCS 00007: Not supported
# ---------------------------------------------------------------------------


def test_scs_00007_png_as_jpg_long_unit_segment_and_encrypted_zip(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_png = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_png")
    buf = io.BytesIO()
    Image.new("RGB", (276, 162), (10, 20, 30)).save(buf, format="PNG")
    (ws_png / "universal" / "mod_icon.jpg").write_bytes(buf.getvalue())
    r_png = validate_workshop_package(ws_png)
    assert r_png.ok is False
    assert "00007" in _issue_codes(r_png)

    ws_seg = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_seg")
    manifest = ws_seg / "universal" / "manifest.sii"
    manifest.write_bytes(
        manifest.read_bytes().replace(
            b"mod_package : .package_name",
            b"mod_package : .this_segment_is_too_long",
        )
    )
    r_seg = validate_workshop_package(ws_seg)
    assert r_seg.ok is False
    assert "00007" in _issue_codes(r_seg)

    enc_zip = tmp_path / "encrypted.zip"
    shutil.copyfile(built_editions["summer"].local_zip_path, enc_zip)
    raw_zip = bytearray(enc_zip.read_bytes())
    # Set bit 0 (encrypted) in first local header (offset 6) and central directory header
    sig_cd = raw_zip.find(b"PK\x01\x02")
    assert sig_cd != -1
    raw_zip[6] |= 0x01
    raw_zip[sig_cd + 8] |= 0x01
    enc_zip.write_bytes(bytes(raw_zip))
    r_enc = validate_local_zip(enc_zip)
    assert r_enc.ok is False
    assert "00007" in _issue_codes(r_enc)


# ---------------------------------------------------------------------------
# SCS 00008: Unable to load
# ---------------------------------------------------------------------------


def test_scs_00008_unparseable_sui_speed_limits_and_corrupt_zip(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_sui = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_sui")
    (ws_sui / "universal" / "def" / "country" / "albania.sui").write_bytes(
        b"country_data : country.data.albania\n{\n\tcountry_id: not_an_int\n}\n"
    )
    r_sui = validate_workshop_package(ws_sui)
    assert r_sui.ok is False
    assert "00008" in _issue_codes(r_sui)

    ws_spd = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_spd")
    (ws_spd / "universal" / "def" / "country" / "albania" / "speed_limits.sii").write_bytes(
        b"SiiNunit\n{\ncountry_speed_limit : .limit.car\n{\n\tlimit[]: 80\n}\n}\n"
    )
    r_spd = validate_workshop_package(ws_spd)
    assert r_spd.ok is False
    assert "00008" in _issue_codes(r_spd)

    corrupt_zip = tmp_path / "corrupt.zip"
    corrupt_zip.write_bytes(b"not a valid zip file at all")
    r_zip = validate_local_zip(corrupt_zip)
    assert r_zip.ok is False
    assert "00008" in _issue_codes(r_zip)


# ---------------------------------------------------------------------------
# SCS 00009: File is too big
# ---------------------------------------------------------------------------


def test_scs_00009_oversized_icon_and_description(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_icon = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_big_icon")
    icon_path = ws_icon / "universal" / "mod_icon.jpg"
    icon_path.write_bytes(icon_path.read_bytes() + b"\x00" * (MAX_ICON_BYTES + 1))
    r_icon = validate_workshop_package(ws_icon)
    assert r_icon.ok is False
    assert "00009" in _issue_codes(r_icon)

    ws_desc = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_big_desc")
    (ws_desc / "universal" / "description.txt").write_bytes(b"a" * (MAX_DESCRIPTION_BYTES + 1))
    r_desc = validate_workshop_package(ws_desc)
    assert r_desc.ok is False
    assert "00009" in _issue_codes(r_desc)


# ---------------------------------------------------------------------------
# SCS 00010 & WARN 00002: Unused / unknown manifest attributes
# ---------------------------------------------------------------------------


def test_scs_00010_and_warn_00002_compatible_versions_and_unknown_attr(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_compat = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_compat")
    m_compat = ws_compat / "universal" / "manifest.sii"
    m_compat.write_bytes(
        m_compat.read_bytes().replace(
            b"\tmp_mod_optional: true\n",
            b'\tmp_mod_optional: true\n\tcompatible_versions[]: "1.62.*"\n',
        )
    )
    r_compat = validate_workshop_package(ws_compat)
    assert r_compat.ok is False
    assert "00010" in _issue_codes(r_compat)
    assert "WARN 00002" in _issue_codes(r_compat)

    ws_unk = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_unk")
    m_unk = ws_unk / "universal" / "manifest.sii"
    m_unk.write_bytes(
        m_unk.read_bytes().replace(
            b"\tmp_mod_optional: true\n",
            b'\tmp_mod_optional: true\n\tfoo: "bar"\n',
        )
    )
    r_unk = validate_workshop_package(ws_unk)
    assert r_unk.ok is False
    assert "WARN 00002" in _issue_codes(r_unk)


# ---------------------------------------------------------------------------
# WARN 00001: display_name in Workshop & >2 categories
# ---------------------------------------------------------------------------


def test_scs_warn_00001_display_name_in_workshop_and_excess_categories(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_dn = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_dn")
    m_dn = ws_dn / "universal" / "manifest.sii"
    m_dn.write_bytes(
        m_dn.read_bytes().replace(
            b'\tauthor: "ETS2 World Realism"\n',
            b'\tdisplay_name: "Should Fail In Workshop"\n\tauthor: "ETS2 World Realism"\n',
        )
    )
    r_dn = validate_workshop_package(ws_dn)
    assert r_dn.ok is False
    assert "WARN 00001" in _issue_codes(r_dn)
    assert r_dn.warning_count >= 1

    ws_cats = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_cats")
    m_cats = ws_cats / "universal" / "manifest.sii"
    m_cats.write_bytes(
        m_cats.read_bytes().replace(
            b'\tcategory[]: "ai_traffic"\n',
            b'\tcategory[]: "ai_traffic"\n\tcategory[]: "ui"\n',
        )
    )
    r_cats = validate_workshop_package(ws_cats)
    assert r_cats.ok is False
    assert "WARN 00001" in _issue_codes(r_cats)


def test_scs_additional_edge_cases_hashfs_bzip2_braces_include_and_country_suffix(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    # HashFS SCS# magic rejected as 00007
    hashfs_file = tmp_path / "fake_hashfs.zip"
    hashfs_file.write_bytes(b"SCS#\x01\x00\x00\x00" + b"\x00" * 32)
    r_hfs = validate_local_zip(hashfs_file)
    assert r_hfs.ok is False
    assert "00007" in _issue_codes(r_hfs)

    # Unsupported ZIP compression method (BZIP2) rejected as 00007
    bzip_info = zipfile.ZipInfo(filename="manifest.sii", date_time=(1980, 1, 1, 0, 0, 0))
    bzip_info.compress_type = zipfile.ZIP_BZIP2
    bzip_zip = _rebuild_zip_with_mutations(
        built_editions["summer"].local_zip_path,
        tmp_path / "bzip2.zip",
        removals={"manifest.sii"},
        extra_entries=[
            (
                bzip_info,
                b"SiiNunit\n{\nmod_package : .pkg\n{\n}\n}\n",
            )
        ],
    )
    r_bz = validate_local_zip(bzip_zip)
    assert r_bz.ok is False
    assert "00007" in _issue_codes(r_bz)

    # Unbalanced brace + non-column-0 @include -> 00004, def/country.ets2v2.sii -> 00003
    ws_edge = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_edge")
    (ws_edge / "universal" / "def" / "country.ets2v2.sii").write_bytes(b"SiiNunit\n{\n}\n")
    (ws_edge / "universal" / "def" / "bad_inc.sii").write_bytes(
        b'SiiNunit\n{\n  @include "foo.sui"\n'
    )
    r_edge = validate_workshop_package(ws_edge)
    assert r_edge.ok is False
    codes = _issue_codes(r_edge)
    assert "00003" in codes
    assert "00004" in codes
