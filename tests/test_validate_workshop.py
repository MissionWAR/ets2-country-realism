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
    FORBIDDEN_TOTEM_EXTENSIONS,
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
    """Enforce Layer 8 isolation: validate NEVER imports package/merge/normalize/fetch/publish."""
    py_files = sorted(VALIDATE_PKG_DIR.rglob("*.py"))
    assert py_files, "Expected Python modules under src/ets2v2/validate/"

    forbidden_subpkgs = ("package", "merge", "normalize", "fetch", "publish")
    forbidden_roots = ("httpx", "openpyxl")
    violations: list[str] = []
    for py_file in py_files:
        tree = ast.parse(py_file.read_text("utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for sub in forbidden_subpkgs:
                        if alias.name == f"ets2v2.{sub}" or alias.name.startswith(f"ets2v2.{sub}."):
                            violations.append(f"{py_file.name}: import {alias.name}")
                    for root in forbidden_roots:
                        if alias.name == root or alias.name.startswith(f"{root}."):
                            violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level > 0:
                    for sub in forbidden_subpkgs:
                        if module == sub or module.startswith(f"{sub}."):
                            violations.append(
                                f"{py_file.name}: from {'.' * node.level}{module} import ..."
                            )
                        elif module == "":
                            for alias in node.names:
                                if alias.name == sub:
                                    violations.append(
                                        f"{py_file.name}: from {'.' * node.level} import {sub}"
                                    )
                else:
                    for sub in forbidden_subpkgs:
                        if module == f"ets2v2.{sub}" or module.startswith(f"ets2v2.{sub}."):
                            violations.append(f"{py_file.name}: from {module} import ...")
                    for root in forbidden_roots:
                        if module == root or module.startswith(f"{root}."):
                            violations.append(f"{py_file.name}: from {module} import ...")
                    if module == "ets2v2":
                        for alias in node.names:
                            if alias.name in forbidden_subpkgs:
                                violations.append(
                                    f"{py_file.name}: from ets2v2 import {alias.name}"
                                )

    assert violations == [], f"Forbidden imports in ets2v2.validate: {violations}"


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


# ---------------------------------------------------------------------------
# HI-02, HI-03, HI-04: Allowlist, Archive/Link Boundaries, and SCS Protocol
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_filename",
    [
        "nested.zip",
        "preview.png",
        "backup.bak",
        "debug.log",
        "Thumbs.db",
        ".DS_Store",
        "LICENSE",
    ],
)
def test_hi02_unsupported_and_extensionless_files_rejected_as_00003(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
    bad_filename: str,
) -> None:
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / f"ws_{bad_filename}")
    (ws / "universal" / bad_filename).write_bytes(b"stray payload\n")
    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00003" in _issue_codes(report)


def test_hi03_pkg_zip_mount_errors_root_links_and_duplicate_noncanonical_zip_entries(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. ZipArchive(pkg_zip) PermissionError -> 00006, ValueError -> 00008
    ws_zip = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_zip_err")
    shutil.rmtree(ws_zip / "universal")
    shutil.copyfile(built_editions["summer"].local_zip_path, ws_zip / "universal.zip")

    def _raise_perm(_path: pathlib.Path) -> object:
        raise PermissionError("Simulated pkg_zip permission denial")

    def _raise_val(_path: pathlib.Path) -> object:
        raise ValueError("Simulated pkg_zip corruption")

    monkeypatch.setattr("ets2v2.validate.workshop.ZipArchive", _raise_perm)
    r_perm = validate_workshop_package(ws_zip)
    assert r_perm.ok is False
    assert "00006" in _issue_codes(r_perm)

    monkeypatch.setattr("ets2v2.validate.workshop.ZipArchive", _raise_val)
    r_val = validate_workshop_package(ws_zip)
    assert r_val.ok is False
    assert "00008" in _issue_codes(r_val)
    monkeypatch.undo()

    # 2. Root symlink / junction detection on versions.sii and universal/ -> 00003
    ws_link = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_root_link")
    versions_file = (ws_link / "versions.sii").resolve()
    orig_is_symlink = pathlib.Path.is_symlink

    def _fake_versions_symlink(self: pathlib.Path) -> bool:
        if self.exists() and self.resolve() == versions_file:
            return True
        return orig_is_symlink(self)

    monkeypatch.setattr(pathlib.Path, "is_symlink", _fake_versions_symlink)
    r_ver_link = validate_workshop_package(ws_link)
    assert r_ver_link.ok is False
    assert "00003" in _issue_codes(r_ver_link)
    monkeypatch.undo()

    univ_dir = (ws_link / "universal").resolve()

    def _fake_univ_junction(self: pathlib.Path) -> bool:
        return self.exists() and self.resolve() == univ_dir

    monkeypatch.setattr(pathlib.Path, "is_junction", _fake_univ_junction, raising=False)
    r_dir_junc = validate_workshop_package(ws_link)
    assert r_dir_junc.ok is False
    assert "00003" in _issue_codes(r_dir_junc)
    monkeypatch.undo()

    # 3. Duplicate normalized ZIP entry & non-canonical './' and '//' paths -> 00003
    dup_zip = _rebuild_zip_with_mutations(
        built_editions["summer"].local_zip_path,
        tmp_path / "dup.zip",
        extra_entries=[(zipfile.ZipInfo(filename="manifest.sii"), b"SiiNunit\n{\n}\n")],
    )
    r_dup = validate_local_zip(dup_zip)
    assert r_dup.ok is False
    assert "00003" in _issue_codes(r_dup)

    dot_zip = _rebuild_zip_with_mutations(
        built_editions["summer"].local_zip_path,
        tmp_path / "dotslash.zip",
        extra_entries=[(zipfile.ZipInfo(filename="./def/country/extra.sui"), b"")],
    )
    r_dot = validate_local_zip(dot_zip)
    assert r_dot.ok is False
    assert "00003" in _issue_codes(r_dot)

    dbl_zip = _rebuild_zip_with_mutations(
        built_editions["summer"].local_zip_path,
        tmp_path / "doubleslash.zip",
        extra_entries=[(zipfile.ZipInfo(filename="def//country/extra.sui"), b"")],
    )
    r_dbl = validate_local_zip(dbl_zip)
    assert r_dbl.ok is False
    assert "00003" in _issue_codes(r_dbl)


def test_hi04_unquoted_strings_category_rules_stray_units_and_icon_checks(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    # 1. Unquoted author and scalar category -> 00004
    ws_unq = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_unq")
    m_unq = ws_unq / "universal" / "manifest.sii"
    m_unq.write_bytes(
        m_unq.read_bytes()
        .replace(b'author: "ETS2 World Realism"', b"author: ETS2_Unquoted")
        .replace(b'category[]: "other"', b'category: "other"')
    )
    r_unq = validate_workshop_package(ws_unq)
    assert r_unq.ok is False
    assert "00004" in _issue_codes(r_unq)

    # 2. Duplicate category[] -> 00003
    ws_dup_cat = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_dup_cat")
    m_dup_cat = ws_dup_cat / "universal" / "manifest.sii"
    m_dup_cat.write_bytes(
        m_dup_cat.read_bytes().replace(b'category[]: "ai_traffic"', b'category[]: "other"')
    )
    r_dup_cat = validate_workshop_package(ws_dup_cat)
    assert r_dup_cat.ok is False
    assert "00003" in _issue_codes(r_dup_cat)

    # 3. Stray unit class in manifest.sii and versions.sii + duplicate package_name -> 00003
    ws_stray = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_stray")
    m_stray = ws_stray / "universal" / "manifest.sii"
    m_stray.write_bytes(
        m_stray.read_bytes().replace(
            b"\n}\n",
            b"\ncountry_data : .stray\n{\n\tcountry_id: 1\n}\n}\n",
            1,
        )
    )
    (ws_stray / "versions.sii").write_bytes(
        b"SiiNunit\n{\n"
        b'package_version_info : .universal\n{\n\tpackage_name: "universal"\n}\n'
        b'package_version_info : .dup\n{\n\tpackage_name: "universal"\n'
        b'\tcompatible_versions[]: "1.62.*"\n}\n'
        b"country_data : .stray\n{\n\tcountry_id: 1\n}\n"
        b"}\n"
    )
    r_stray = validate_workshop_package(ws_stray)
    assert r_stray.ok is False
    assert "00003" in _issue_codes(r_stray)

    # 4. Unquoted package_name in versions.sii -> 00004
    ws_unq_pkg = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_unq_pkg")
    (ws_unq_pkg / "versions.sii").write_bytes(
        b"SiiNunit\n{\npackage_version_info : .universal\n{\n\tpackage_name: universal\n}\n}\n"
    )
    r_unq_pkg = validate_workshop_package(ws_unq_pkg)
    assert r_unq_pkg.ok is False
    assert "00004" in _issue_codes(r_unq_pkg)

    # 5. CMYK JPEG icon -> 00007
    ws_cmyk = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_cmyk")
    cmyk_buf = io.BytesIO()
    Image.new("CMYK", (276, 162), (0, 0, 0, 0)).save(cmyk_buf, format="JPEG", quality=90)
    (ws_cmyk / "universal" / "mod_icon.jpg").write_bytes(cmyk_buf.getvalue())
    r_cmyk = validate_workshop_package(ws_cmyk)
    assert r_cmyk.ok is False
    assert "00007" in _issue_codes(r_cmyk)

    # 6. Progressive JPEG icon -> 00007
    ws_prog = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_prog")
    prog_buf = io.BytesIO()
    Image.new("RGB", (276, 162), (20, 40, 80)).save(
        prog_buf, format="JPEG", quality=90, progressive=True
    )
    (ws_prog / "universal" / "mod_icon.jpg").write_bytes(prog_buf.getvalue())
    r_prog = validate_workshop_package(ws_prog)
    assert r_prog.ok is False
    assert "00007" in _issue_codes(r_prog)

    # 7. Icon exceeding MAX_ICON_PIXELS -> 00009 without mutating Image.MAX_IMAGE_PIXELS
    ws_bomb = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / "ws_bomb")
    bomb_buf = io.BytesIO()
    Image.new("RGB", (2500, 2500), (10, 20, 30)).save(bomb_buf, format="JPEG", quality=50)
    (ws_bomb / "universal" / "mod_icon.jpg").write_bytes(bomb_buf.getvalue())
    orig_max_pixels = Image.MAX_IMAGE_PIXELS
    r_bomb = validate_workshop_package(ws_bomb)
    assert orig_max_pixels == Image.MAX_IMAGE_PIXELS
    assert r_bomb.ok is False
    assert "00009" in _issue_codes(r_bomb)


# ---------------------------------------------------------------------------
# D-12: Zero-DDS Hard Gate (ETS2V2-INV-ZERO-DDS)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext", [".dds", ".tobj"])
def test_d12_zero_dds_hard_gate_workshop_and_local_zip(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
    ext: str,
) -> None:
    assert ext in FORBIDDEN_TOTEM_EXTENSIONS

    # 1. Workshop root without baseline_dir AND with baseline_dir
    ws = _clone_workshop(built_editions["summer"].workshop_dir, tmp_path / f"ws_{ext[1:]}")
    tex_dir = ws / "universal" / "material" / "sign"
    tex_dir.mkdir(parents=True, exist_ok=True)
    (tex_dir / f"totem_price{ext}").write_bytes(b"DDS_OR_TOBJ_BINARY")

    r_no_bl = validate_workshop_package(ws)
    assert r_no_bl.ok is False
    assert "ETS2V2-INV-ZERO-DDS" in _issue_codes(r_no_bl)

    r_with_bl = validate_workshop_package(ws, baseline_dir=BASELINE_DIR)
    assert r_with_bl.ok is False
    assert "ETS2V2-INV-ZERO-DDS" in _issue_codes(r_with_bl)

    # 2. Local ZIP without baseline_dir AND with baseline_dir
    bad_zip = _rebuild_zip_with_mutations(
        built_editions["summer"].local_zip_path,
        tmp_path / f"local_{ext[1:]}.zip",
        extra_entries=[
            (
                zipfile.ZipInfo(
                    filename=f"material/sign/totem_price{ext}",
                    date_time=(1980, 1, 1, 0, 0, 0),
                ),
                b"DDS_OR_TOBJ_BINARY",
            )
        ],
    )
    rz_no_bl = validate_local_zip(bad_zip)
    assert rz_no_bl.ok is False
    assert "ETS2V2-INV-ZERO-DDS" in _issue_codes(rz_no_bl)

    rz_with_bl = validate_local_zip(bad_zip, baseline_dir=BASELINE_DIR)
    assert rz_with_bl.ok is False
    assert "ETS2V2-INV-ZERO-DDS" in _issue_codes(rz_with_bl)


@pytest.mark.parametrize(
    "rogue_path",
    [
        "locale/fuel_price_strings.sui",
        "locale/en_gb/localization.sui",
        "locale/en_gb/local_module.rogue.sii",
    ],
)
def test_scs_00003_rejects_rogue_locale_sii_and_sui_files(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
    rogue_path: str,
) -> None:
    ws = _clone_workshop(
        built_editions["summer"].workshop_dir,
        tmp_path / f"ws_rogue_{rogue_path.replace('/', '_')}",
    )
    target = ws / "universal" / rogue_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if rogue_path.endswith(".sii"):
        target.write_bytes(
            b'SiiNunit\n{\nlocalization_db : .rogue\n{\n\tkey[]: "k"\n\tval[]: "1"\n}\n}\n'
        )
    else:
        target.write_bytes(b'key[]: "fuel_price_diesel"\nval[]: "1.65"\n')

    report = validate_workshop_package(ws)
    assert report.ok is False
    assert "00003" in _issue_codes(report)


def _make_promods_workshop_clone(
    core_ws: pathlib.Path,
    dst: pathlib.Path,
    *,
    include_uk_regions: bool = True,
    pm_fuel_extra_pairs: list[tuple[str, str]] | None = None,
) -> pathlib.Path:
    ws = _clone_workshop(core_ws, dst)
    uni = ws / "universal"
    if include_uk_regions:
        uk_sui = uni / "def" / "country" / "uk.sui"
        uk_text = uk_sui.read_text("utf-8")
        uk_text = uk_text.replace(
            "\n}\n",
            '\n\tregions[]: "scotland"\n\tregions[]: "wales"\n}\n',
        )
        uk_sui.write_text(uk_text, encoding="utf-8", newline="\n")

    # Add a ProMods extra country omitting iso_country_code (valid in profile="promods")
    (uni / "def" / "country" / "andorra.sui").write_text(
        'country_data : country.data.andorra\n{\n\tcountry_id: 15\n\tname: "Andorra"\n'
        '\tcountry_code: "AND"\n\tfuel_price: 1.49\n\tlights_mandatory: false\n'
        '\tdriving_tired_offence: true\n\ttime_zone: 120\n\ttime_zone_name: "@@tz_cest@@"\n'
        "\tmass_limit_per_axle_count[]: 18000\n\tmass_limit_per_axle_count[]: 26000\n"
        "\tmass_limit_per_axle_count[]: 36000\n\tmass_limit_per_axle_count[]: 40000\n}\n",
        encoding="utf-8",
        newline="\n",
    )

    pairs = sorted(
        [
            ("custom_header", "PROMODS STATION"),
            ("fp_de_diesel_v4", "164.<sup>1</sup>"),
            ("fp_mn_diesel", "1.45"),
            *(pm_fuel_extra_pairs or []),
        ]
    )
    loc_lines = ["SiiNunit", "{", "localization_db : .pm_fuel", "{"]
    for k, v in pairs:
        loc_lines.append(f'\tkey[]: "{k}"')
        loc_lines.append(f'\tval[]: "{v}"')
    loc_lines.extend(["}", "}"])
    pm_payload = ("\n".join(loc_lines) + "\n").encode("utf-8")
    for lang_dir in sorted((uni / "locale").iterdir()):
        if lang_dir.is_dir():
            (lang_dir / "local_module.pm_fuel.sii").write_bytes(pm_payload)
    return ws


def test_profile_promods_accepts_valid_promods_package_and_rejects_faults(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    ws_ok = _make_promods_workshop_clone(
        built_editions["summer"].workshop_dir,
        tmp_path / "ws_pm_ok",
    )
    report_ok = validate_workshop_package(ws_ok, baseline_dir=BASELINE_DIR, profile="promods")
    assert report_ok.ok is True, report_ok.issues

    # Core profile still rejects pm_fuel & extra countries!
    report_as_core = validate_workshop_package(ws_ok, baseline_dir=BASELINE_DIR, profile="core")
    assert report_as_core.ok is False

    # Missing UK scotland/wales regions fails profile="promods"
    ws_no_uk_reg = _make_promods_workshop_clone(
        built_editions["summer"].workshop_dir,
        tmp_path / "ws_pm_no_uk",
        include_uk_regions=False,
    )
    r_no_uk = validate_workshop_package(ws_no_uk_reg, baseline_dir=BASELINE_DIR, profile="promods")
    assert r_no_uk.ok is False
    assert "ETS2V2-INV-REGIONS" in _issue_codes(r_no_uk)

    # Stray def/country.promods.sii registration file fails
    ws_reg = _make_promods_workshop_clone(
        built_editions["summer"].workshop_dir,
        tmp_path / "ws_pm_reg",
    )
    (ws_reg / "universal" / "def" / "country.promods.sii").write_bytes(
        b'SiiNunit\n{\n@include "country/andorra.sui"\n}\n'
    )
    r_reg = validate_workshop_package(ws_reg, baseline_dir=BASELINE_DIR, profile="promods")
    assert r_reg.ok is False
    assert "00003" in _issue_codes(r_reg)

    # Mismatched pm_fuel locale and stray fr_qc fail
    ws_bad_loc = _make_promods_workshop_clone(
        built_editions["summer"].workshop_dir,
        tmp_path / "ws_pm_loc",
    )
    de_pm = ws_bad_loc / "universal" / "locale" / "de_de" / "local_module.pm_fuel.sii"
    de_pm.write_bytes(de_pm.read_bytes().replace(b'"1.45"', b'"1.99"'))
    fr_qc = ws_bad_loc / "universal" / "locale" / "fr_qc"
    fr_qc.mkdir(parents=True, exist_ok=True)
    (fr_qc / "local_module.pm_fuel.sii").write_bytes(de_pm.read_bytes())
    r_loc = validate_workshop_package(ws_bad_loc, baseline_dir=BASELINE_DIR, profile="promods")
    assert r_loc.ok is False
    assert "ETS2V2-INV-LOCALE-SYNC" in _issue_codes(r_loc)


def test_profile_combo_accepts_sii_fragments_partial_blocks_and_rejects_faults(
    built_editions: dict[str, BuiltEditionPaths],
    tmp_path: pathlib.Path,
) -> None:
    # Build a minimal valid combo local ZIP with headerless .sii fragment, omitted iso_country_code,
    # omitted time_zone + time_zone_name, 1-road-block speed_limits.sii, and no totems.
    icon_bytes = (ICONS_DIR / "summer.jpg").read_bytes()
    manifest_bytes = (
        b"SiiNunit\n{\n# ets2v2:managed-package kind=combo\nmod_package : .package_name\n{\n"
        b'\tpackage_version: "1.62-2026.47"\n'
        b'\tdisplay_name: "ETS2V2 Combo Patch"\n'
        b'\tauthor: "ETS2 World Realism"\n'
        b'\tcategory[]: "other"\n'
        b'\ticon: "mod_icon.jpg"\n'
        b'\tdescription_file: "description.txt"\n'
        b"\tmp_mod_optional: true\n}\n}\n"
    )
    thailand_sii = (
        b"country_data : country.data.thailand\n{\n"
        b"\tcountry_id: 210\n"
        b'\tname: "Thailand"\n'
        b'\tcountry_code: "TH"\n'
        b"\tfuel_price: 0.95\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 25000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n}\n"
    )
    thailand_spd = (
        b"SiiNunit\n{\n"
        b"country_speed_limit : .speed_limit.car\n{\n"
        b"\tvehicle_speed_class: car\n"
        b"\tlane_speed_class[]: local_road\n"
        b"\tlimit[]: 90\n\turban_limit[]: 60\n}\n}\n"
    )

    def _write_combo_zip(path: pathlib.Path, extra: dict[str, bytes]) -> pathlib.Path:
        entries = {
            "manifest.sii": manifest_bytes,
            "mod_icon.jpg": icon_bytes,
            "description.txt": b"Combo patch test.\n",
            **extra,
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for k in sorted(entries):
                zi = zipfile.ZipInfo(filename=k, date_time=(1980, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zi, entries[k])
        return path

    ok_zip = _write_combo_zip(
        tmp_path / "combo_ok.scs",
        {
            "def/country/thailand.sii": thailand_sii,
            "def/country/thailand/speed_limits.sii": thailand_spd,
        },
    )
    r_ok = validate_local_zip(ok_zip, baseline_dir=BASELINE_DIR, profile="combo")
    assert r_ok.ok is True, r_ok.issues

    # Omitted speed_limits.sii is also valid in combo
    no_spd_zip = _write_combo_zip(
        tmp_path / "combo_no_spd.scs",
        {"def/country/thailand.sii": thailand_sii},
    )
    assert validate_local_zip(no_spd_zip, baseline_dir=BASELINE_DIR, profile="combo").ok is True

    # time_zone present without time_zone_name must fail
    half_tz_zip = _write_combo_zip(
        tmp_path / "combo_half_tz.scs",
        {
            "def/country/thailand.sii": thailand_sii.replace(
                b"\tlights_mandatory: false\n",
                b"\tlights_mandatory: false\n\ttime_zone: 420\n",
            )
        },
    )
    r_half_tz = validate_local_zip(half_tz_zip, baseline_dir=BASELINE_DIR, profile="combo")
    assert r_half_tz.ok is False
    assert "00005" in _issue_codes(r_half_tz)

    # 0 road blocks in speed_limits.sii (only train) must fail
    zero_road_zip = _write_combo_zip(
        tmp_path / "combo_zero_road.scs",
        {
            "def/country/thailand.sii": thailand_sii,
            "def/country/thailand/speed_limits.sii": (
                b"SiiNunit\n{\ncountry_speed_limit : .speed_limit.train\n{\n"
                b"\tvehicle_speed_class: train\n\tlane_speed_class[]: local_road\n"
                b"\tlimit[]: 80\n}\n}\n"
            ),
        },
    )
    r_zero_road = validate_local_zip(zero_road_zip, baseline_dir=BASELINE_DIR, profile="combo")
    assert r_zero_road.ok is False
    assert "00005" in _issue_codes(r_zero_road)

    # Invalid @@tz_fake@@, duplicate country_id, .dds, and def/country.sii fail in combo
    bad_combo_zip = _write_combo_zip(
        tmp_path / "combo_bad.scs",
        {
            "def/country.sii": b'SiiNunit\n{\n@include "country/thailand.sii"\n}\n',
            "def/country/thailand.sii": thailand_sii.replace(
                b"\tlights_mandatory: false\n",
                b'\tlights_mandatory: false\n\ttime_zone: 420\n\ttime_zone_name: "@@tz_fake@@"\n',
            ),
            "def/country/laos.sui": thailand_sii.replace(
                b"country.data.thailand", b"country.data.laos"
            ),
            "material/bad.dds": b"DDS ",
        },
    )
    r_bad = validate_local_zip(bad_combo_zip, baseline_dir=BASELINE_DIR, profile="combo")
    assert r_bad.ok is False
    codes = _issue_codes(r_bad)
    assert "00003" in codes
    assert "ETS2V2-INV-ZERO-DDS" in codes
    assert "ETS2V2-INV-COUNTRY-COUNT" in codes
    assert "ETS2V2-INV-TZ-TOKEN" in codes

    # MD-03: duplicate .sui + .sii for same slug rejected with 00003
    dup_slug_zip = _write_combo_zip(
        tmp_path / "combo_dup_slug.scs",
        {
            "def/country/thailand.sui": thailand_sii,
            "def/country/thailand.sii": thailand_sii,
        },
    )
    r_dup_slug = validate_local_zip(dup_slug_zip, baseline_dir=BASELINE_DIR, profile="combo")
    assert r_dup_slug.ok is False
    assert any(i.code == "00003" and "Duplicate country" in i.detail for i in r_dup_slug.issues)

    # MD-03: rogue .sii files outside realism allowlist rejected with 00003
    rogue_zip = _write_combo_zip(
        tmp_path / "combo_rogue.scs",
        {
            "def/country/thailand.sii": thailand_sii,
            "def/economy_data.sii": b"SiiNunit\n{\neconomy_data : economy.data.storage\n{\n}\n}\n",
            "def/country/germany/traffic.sii": b"SiiNunit\n{\ncountry_traffic_info : .t\n{\n}\n}\n",
        },
    )
    r_rogue = validate_local_zip(rogue_zip, baseline_dir=BASELINE_DIR, profile="combo")
    assert r_rogue.ok is False
    rogue_paths = {i.path for i in r_rogue.issues if i.code == "00003"}
    assert "def/economy_data.sii" in rogue_paths
    assert "def/country/germany/traffic.sii" in rogue_paths

    # MD-03: dangling sign-board token when fuel_locales is absent fails combo validation
    dangling_board_zip = _write_combo_zip(
        tmp_path / "combo_dangling_board.scs",
        {
            "def/country/thailand.sii": thailand_sii,
            "def/sign/board/custom_board.sii": (
                b"SiiNunit\n{\n"
                b"sign_board_template : _nameless.100.a\n{\n"
                b'\tboard_name: "custom_board"\n'
                b"\twidth: 1.5\n\theight: 0.6\n"
                b'\tmodel_name: ""\n\titems: 1\n\titems[0]: _nameless.200.slot0\n'
                b"}\n"
                b"sign_template_text : _nameless.200.slot0\n{\n"
                b'\tfont_face: "/font/sign/dot_matrix.font"\n'
                b'\ttext: "@@fp_xx_missing_ets2v2@@"\n'
                b"}\n}\n"
            ),
        },
    )
    r_dangling = validate_local_zip(dangling_board_zip, baseline_dir=BASELINE_DIR, profile="combo")
    assert r_dangling.ok is False
    assert "ETS2V2-INV-TOTEM-BOARDS" in _issue_codes(r_dangling)
