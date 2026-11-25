"""End-to-end synthetic multi-map combo tests and @pytest.mark.local_promods dry-run check."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from zipfile import ZipFile

import pytest

from ets2v2.baseline.models import CountriesBaseline, LocalesBaseline
from ets2v2.cli import main as cli_main
from ets2v2.merge.compose import COMBO_SCS_FILENAMES, ComposeReport, compose_local
from ets2v2.package.metadata import ETS2V2_MANIFEST_MARKER
from ets2v2.registry.loader import load_law_registry
from ets2v2.registry.snapshot import (
    build_realism_snapshot,
    load_or_build_snapshot,
    write_realism_snapshot,
    write_sha256sums,
)
from ets2v2.sii.country import parse_country_data
from ets2v2.sii.document import SiiDocument
from ets2v2.sii.localization import parse_localization_db
from ets2v2.sii.sign_board import parse_sign_board
from ets2v2.sii.speed_limits import parse_speed_limits
from ets2v2.validate.workshop import validate_local_zip

_BASELINE_DIR = Path("data/baselines/ets2_1.62_def")
_LOCAL_ETS2_DATA_DIR = Path(r"D:\ETS2Data\Euro Truck Simulator 2")


def _write_encrypted_flag_zip(zip_path: Path, entries: dict[str, bytes]) -> None:
    """Create a valid ZIP with bit 0 (encrypted) set in local + central headers (no decryption)."""
    with ZipFile(zip_path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)

    buf = bytearray(zip_path.read_bytes())
    # Patch general purpose bit flag bit 0 on all LFH (PK\x03\x04) and CDH (PK\x01\x02)
    pos = 0
    while True:
        idx = buf.find(b"PK\x03\x04", pos)
        if idx == -1:
            break
        flag = struct.unpack_from("<H", buf, idx + 6)[0]
        struct.pack_into("<H", buf, idx + 6, flag | 0x0001)
        pos = idx + 4

    pos = 0
    while True:
        idx = buf.find(b"PK\x01\x02", pos)
        if idx == -1:
            break
        flag = struct.unpack_from("<H", buf, idx + 8)[0]
        struct.pack_into("<H", buf, idx + 8, flag | 0x0001)
        pos = idx + 4

    zip_path.write_bytes(bytes(buf))


def _single_text_board(board_name: str, text: str) -> bytes:
    return (
        "SiiNunit\n"
        "{\n"
        f"sign_board_template : _nameless.100.{board_name[:8]}\n"
        "{\n"
        f'\tboard_name: "{board_name}"\n'
        "\twidth: 1.5\n"
        "\theight: 0.6\n"
        '\tmodel_name: ""\n'
        "\titems: 1\n"
        "\titems[0]: _nameless.200.slot0\n"
        "\tdynamic_attributes: 0\n"
        "}\n"
        "sign_template_text : _nameless.200.slot0\n"
        "{\n"
        '\tfont_face: "/font/sign/dot_matrix.font"\n'
        "\tfont_size: 0.35\n"
        '\ttext_halign: "center"\n'
        '\ttext_valign: "center"\n'
        f'\ttext: "{text}"\n'
        "}\n"
        "}\n"
    ).encode()


def _build_synthetic_combo_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build a rich synthetic multi-map combo with snapshot, mods, modlist, and unpacked defs."""
    mod_dir = tmp_path / "mods"
    mod_dir.mkdir(parents=True, exist_ok=True)

    # 1. ProMods EU def (UK scotland/wales + can_islands)
    with ZipFile(mod_dir / "promods-eu-def-v285.scs", "w") as zf:
        zf.writestr(
            "def/country.promods.sii",
            'SiiNunit\n{\n@include "country/uk.sui"\n@include "country/can_islands.sui"\n}\n',
        )
        zf.writestr(
            "def/country/uk.sui",
            (
                "country_data : country.data.uk\n"
                "{\n"
                "\tcountry_id: 10\n"
                '\tname: "United Kingdom"\n'
                '\tname_localized: "@@uk@@"\n'
                '\tcountry_code: "UK"\n'
                "\tiso_country_code: gbr\n"
                "\tpos: (-45000, 0, -25000)\n"
                "\tfuel_price: 1.50\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\timperial_units: true\n"
                "\tleftside_traffic: true\n"
                "\ttime_zone: 0\n"
                '\ttime_zone_name: "@@tz_gmt@@"\n'
                "\tregions[]: scotland\n"
                "\tregions[]: wales\n"
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 36000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "\tmass_limit_per_axle_count[]: 44000\n"
                "}\n"
            ),
        )
        zf.writestr(
            "def/country/can_islands.sui",
            (
                "country_data : country.data.can_islands\n"
                "{\n"
                "\tcountry_id: 199\n"
                '\tname: "Canary Islands"\n'
                '\tcountry_code: "E"\n'
                "\tiso_country_code: esp\n"
                "\tfuel_price: 1.40\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: 60\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )

    # 2. ProMods EU assets (local_module.pm_fuel.sii)
    with ZipFile(mod_dir / "promods-eu-assets-v285.scs", "w") as zf:
        zf.writestr(
            "locale/en_gb/local_module.pm_fuel.sii",
            (
                "SiiNunit\n"
                "{\n"
                "localization_db : .pm_fuel\n"
                "{\n"
                '\tkey[]: "fp_de_diesel"\n'
                '\tval[]: "1.50"\n'
                '\tkey[]: "fp_cni_natural95"\n'
                '\tval[]: "1.40"\n'
                '\tkey[]: "pm_custom_unrecognized"\n'
                '\tval[]: "KEEP_ME"\n'
                "}\n"
                "}\n"
            ),
        )

    # 3. EAA + SemEuropa (base/ mount prefix + 80t multi-TZ Brazil + Alagoas "AL" collision trap)
    with ZipFile(mod_dir / "eaa_semeuropa.scs", "w") as zf:
        zf.writestr(
            "base/def/country.eaa.sii",
            'SiiNunit\n{\n@include "country/brasil.sui"\n@include "country/alagoas.sui"\n}\n',
        )
        zf.writestr(
            "base/def/country/brasil.sui",
            (
                "country_data : country.data.brasil\n"
                "{\n"
                "\tcountry_id: 201\n"
                '\tname: "Brasil"\n'
                '\tcountry_code: "BR"\n'
                "\tiso_country_code: bra\n"
                "\tfuel_price: 1.05\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: -180\n"
                '\ttime_zone_name: "BRT"\n'
                '\tsecondary_time_zone_name[]: "AMT"\n'
                "\tmass_limit_per_axle_count[]: 16000\n"
                "\tmass_limit_per_axle_count[]: 23000\n"
                "\tmass_limit_per_axle_count[]: 33000\n"
                "\tmass_limit_per_axle_count[]: 45000\n"
                "\tmass_limit_per_axle_count[]: 57000\n"
                "\tmass_limit_per_axle_count[]: 74000\n"
                "\tmass_limit_per_axle_count[]: 80000\n"
                "}\n"
            ),
        )
        zf.writestr(
            "base/def/country/alagoas.sui",
            (
                "country_data : country.data.alagoas\n"
                "{\n"
                "\tcountry_id: 202\n"
                '\tname: "Alagoas"\n'
                '\tcountry_code: "AL"\n'
                "\tiso_country_code: ala\n"
                "\tfuel_price: 1.05\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: -180\n"
                '\ttime_zone_name: "BRT"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 45000\n"
                "\tmass_limit_per_axle_count[]: 80000\n"
                "}\n"
            ),
        )

    # 4. TST (multi-TZ Russia + 48t axles)
    with ZipFile(mod_dir / "tst_map.scs", "w") as zf:
        zf.writestr("def/country.tst.sii", 'SiiNunit\n{\n@include "country/russia.sui"\n}\n')
        zf.writestr(
            "def/country/russia.sui",
            (
                "country_data : country.data.russia\n"
                "{\n"
                "\tcountry_id: 38\n"
                '\tname: "Russia"\n'
                '\tname_localized: "@@russia@@"\n'
                '\tcountry_code: "RUS"\n'
                "\tiso_country_code: rus\n"
                "\tfuel_price: 0.60\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: 180\n"
                '\ttime_zone_name: "@@tz_msk@@"\n'
                "\tsecondary_time_zone_area[]: (1000, 2000, 3000, 4000)\n"
                "\tsecondary_time_zone[]: 300\n"
                '\tsecondary_time_zone_name[]: "@@tz_yekt@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 25000\n"
                "\tmass_limit_per_axle_count[]: 32000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "\tmass_limit_per_axle_count[]: 44000\n"
                "\tmass_limit_per_axle_count[]: 48000\n"
                "}\n"
            ),
        )

    # 5. Lower 7RM (suppressed by UMCF empty stub) + 7RM/JRR hardcoded gas boards
    with ZipFile(mod_dir / "7rm_base.scs", "w") as zf:
        zf.writestr(
            "def/country.7rm2.sii", 'SiiNunit\n{\n@include "country/suppressed_old.sui"\n}\n'
        )
        zf.writestr(
            "def/country/suppressed_old.sui",
            (
                "country_data : country.data.suppressed\n"
                "{\n"
                "\tcountry_id: 404\n"
                '\tname: "Suppressed"\n'
                '\tcountry_code: "DE"\n'
                "\tiso_country_code: deu\n"
                "\tfuel_price: 1.0\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: 60\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )
        zf.writestr(
            "def/sign/board/indo_gas_totem_01a.sii",
            _single_text_board("indo_gas_totem_01a", "15100"),
        )
        zf.writestr(
            "def/sign/board/indo_gas_totem_01j.sii",
            _single_text_board("indo_gas_totem_01j", "34.138.06"),
        )
        zf.writestr(
            "def/sign/board/kz_gas_totem_95.sii", _single_text_board("kz_gas_totem_95", "205")
        )

    # 6. UMCF (5-TZ Kazakhstan + empty SiiNunit {} suppression stub for def/country.7rm2.sii)
    with ZipFile(mod_dir / "umcf_map.scs", "w") as zf:
        zf.writestr("def/country.7rm2.sii", "SiiNunit\n{\n}\n")
        zf.writestr("def/country.umcf.sii", 'SiiNunit\n{\n@include "country/kazakhstan.sui"\n}\n')
        zf.writestr(
            "def/country/kazakhstan.sui",
            (
                "country_data : country.data.kazakhstan\n"
                "{\n"
                "\tcountry_id: 88\n"
                '\tname: "Kazakhstan"\n'
                '\tcountry_code: "KZ"\n'
                "\tiso_country_code: kaz\n"
                "\tfuel_price: 0.45\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: 300\n"
                '\ttime_zone_name: "@@tz_aqtt@@"\n'
                "\tsecondary_time_zone_area[]: (10, 20, 30, 40)\n"
                "\tsecondary_time_zone[]: 360\n"
                '\tsecondary_time_zone_name[]: "@@tz_almt@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 25000\n"
                "\tmass_limit_per_axle_count[]: 38000\n"
                "}\n"
            ),
        )

    # 7. SEA/RoC headerless .sii country fragment + custom lane autobahn_special + train/tram
    with ZipFile(mod_dir / "sea_custom.scs", "w") as zf:
        zf.writestr("def/country.sea.sii", 'SiiNunit\n{\n@include "country/custom_de.sii"\n}\n')
        zf.writestr(
            "def/country/custom_de.sii",
            (
                "country_data : country.data.custom_de\n"
                "{\n"
                "\tcountry_id: 501\n"
                '\tname: "Custom DE"\n'
                '\tcountry_code: "D"\n'
                "\tiso_country_code: deu\n"
                "\tfuel_price: 1.45\n"
                "\tlights_mandatory: true\n"
                "\tdriving_tired_offence: true\n"
                "\timperial_units: false\n"
                "\ttime_zone: 60\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )
        zf.writestr(
            "def/country/custom_de/speed_limits.sii",
            (
                "SiiNunit\n"
                "{\n"
                "country_speed_limit : .speed_limit.car\n"
                "{\n"
                "\tvehicle_speed_class: car\n"
                "\tlane_speed_class[]: local_road\n"
                "\tlimit[]: 80\n"
                "\turban_limit[]: 50\n"
                "\tlane_speed_class[]: autobahn_special\n"
                "\tlimit[]: 150\n"
                "\turban_limit[]: 60\n"
                "\tlane_speed_class[]: motorway\n"
                "\tlimit[]: 120\n"
                "\turban_limit[]: 50\n"
                "\tmax_limit[]: 130\n"
                "}\n"
                "country_speed_limit : .speed_limit.train\n"
                "{\n"
                "\tvehicle_speed_class: train\n"
                "\tlane_speed_class[]: local_road\n"
                "\tlimit[]: 160\n"
                "}\n"
                "country_speed_limit : .speed_limit.tram\n"
                "{\n"
                "\tvehicle_speed_class: tram\n"
                "\tlane_speed_class[]: local_road\n"
                "\tlimit[]: 45\n"
                "}\n"
                "}\n"
            ),
        )

    # 8. Encrypted Beyond archive + higher plain-ZIP gmc.beyond.fix
    _write_encrypted_flag_zip(
        mod_dir / "Beyond_by_TerraMaps_1.scs",
        {
            "def/country.beyond.sii": b'SiiNunit\n{\n@include "country/beyond_x.sui"\n}\n',
            "def/country/beyond_x.sui": b"encrypted placeholder",
        },
    )
    with ZipFile(mod_dir / "gmc.beyond.fix.scs", "w") as zf:
        zf.writestr("def/country.beyond.sii", "SiiNunit\n{\n}\n")

    # Stem-matched unpacked-defs directory for Beyond_by_TerraMaps_1
    unpacked_root = tmp_path / "unpacked"
    beyond_dir = unpacked_root / "Beyond_by_TerraMaps_1" / "def" / "country"
    beyond_dir.mkdir(parents=True, exist_ok=True)
    (unpacked_root / "Beyond_by_TerraMaps_1" / "def" / "country.beyond_unp.sii").write_text(
        'SiiNunit\n{\n@include "country/jordan.sui"\n}\n',
        encoding="utf-8",
        newline="\n",
    )
    (beyond_dir / "jordan.sui").write_text(
        (
            "country_data : country.data.jordan\n"
            "{\n"
            "\tcountry_id: 502\n"
            '\tname: "Jordan"\n'
            '\tcountry_code: "JOR"\n'
            "\tiso_country_code: jor\n"
            "\tfuel_price: 0.90\n"
            "\tlights_mandatory: false\n"
            "\tdriving_tired_offence: true\n"
            "\ttime_zone: 120\n"
            '\ttime_zone_name: "EET"\n'
            "\tmass_limit_per_axle_count[]: 18000\n"
            "\tmass_limit_per_axle_count[]: 26000\n"
            "\tmass_limit_per_axle_count[]: 40000\n"
            "}\n"
        ),
        encoding="utf-8",
        newline="\n",
    )

    # 9. Prior zz_ETS2V2_ComboPatch_Summer.scs already present in load order (D-10 self-exclusion)
    with ZipFile(mod_dir / "zz_ETS2V2_ComboPatch_Summer.scs", "w") as zf:
        zf.writestr(
            "manifest.sii",
            (
                "SiiNunit\n{\n"
                f"{ETS2V2_MANIFEST_MARKER} kind=combo\n"
                "mod_package : .package_name { }\n}\n"
            ),
        )
        zf.writestr(
            "def/country.self_should_ignore.sii", 'SiiNunit\n{\n@include "country/uk.sui"\n}\n'
        )

    # Top-to-bottom Mod Manager load order
    modlist_path = tmp_path / "mods.txt"
    modlist_path.write_text(
        "\n".join(
            [
                "# Top of Mod Manager (highest priority)",
                "zz_ETS2V2_ComboPatch_Summer.scs",
                "gmc.beyond.fix.scs",
                "Beyond_by_TerraMaps_1.scs",
                "sea_custom.scs",
                "umcf_map.scs",
                "7rm_base.scs",
                "tst_map.scs",
                "eaa_semeuropa.scs",
                "promods-eu-def-v285.scs",
                "promods-eu-assets-v285.scs",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # Standalone v1 snapshot JSON + SHA256SUMS.txt (no state/prices.lock.json needed!)
    snap_dir = tmp_path / "snapshots"
    snap_path = snap_dir / "realism-snapshot-summer.json"
    summer_snap = load_or_build_snapshot("summer")
    write_realism_snapshot(summer_snap, snap_path)
    write_sha256sums([snap_path], snap_dir / "SHA256SUMS.txt")

    return mod_dir, modlist_path, snap_path, unpacked_root


def test_compose_local_default_cli_standalone_snapshot(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod_dir, modlist_path, snap_path, _ = _build_synthetic_combo_fixture(tmp_path)
    out_dir = tmp_path / "out_default"

    rc = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(snap_path),
            "--out-dir",
            str(out_dir),
            "--prices-lock",
            str(tmp_path / "nonexistent_prices.lock.json"),
            "--json",
        ]
    )
    assert rc == 0
    report = ComposeReport.model_validate_json(capsys.readouterr().out)
    assert report.ok is True
    assert report.validation_ok is True
    assert len(report.excluded_self_packages) == 1
    assert report.excluded_self_packages[0].archive_path.name == "zz_ETS2V2_ComboPatch_Summer.scs"
    assert len(report.protected_archives) == 1
    assert report.protected_archives[0].protection_kind == "encrypted_zip"
    assert report.warnings  # Warns clearly on encrypted Beyond archive
    assert "pm_fuel" in report.promods_fuel_modules_emitted

    scs_path = out_dir / COMBO_SCS_FILENAMES["summer"]
    assert scs_path.is_file()
    val_report = validate_local_zip(scs_path, baseline_dir=_BASELINE_DIR, profile="combo")
    assert val_report.ok is True, val_report.issues

    with ZipFile(scs_path, "r") as zf:
        names = set(zf.namelist())
        # Zero registration files, zero .dds/.tobj
        assert not any(n.startswith("def/country.") and n.endswith(".sii") for n in names)
        assert not any(n.endswith((".dds", ".tobj")) for n in names)
        assert "def/country/suppressed_old.sui" not in names
        # SemEuropa alagoas & EAA brasil unmatched -> never emitted (zero Albania clobber!)
        assert "def/country/alagoas.sui" not in names
        assert "def/country/brasil.sui" not in names
        # Hardcoded 7RM/JRR boards untouched by default
        assert "def/sign/board/kz_gas_totem_95.sii" not in names
        assert "def/sign/board/indo_gas_totem_01a.sii" not in names

        # UK scotland/wales preserved
        uk = parse_country_data(zf.read("def/country/uk.sui"))
        assert uk.regions == ["scotland", "wales"]
        assert uk.time_zone == 60
        assert uk.time_zone_name == "@@tz_bst@@"

        # Canary Islands Atlantic/Canary summer override (60 / @@tz_west@@)
        can = parse_country_data(zf.read("def/country/can_islands.sui"))
        assert can.time_zone == 60
        assert can.time_zone_name == "@@tz_west@@"

        # TST Russia multi-TZ + 48t preserved
        ru = parse_country_data(zf.read("def/country/russia.sui"))
        assert ru.time_zone == 180
        assert ru.time_zone_name == "@@tz_msk@@"
        assert ru.secondary_time_zone == [300]
        assert ru.mass_limit_per_axle_count[-1] == 48000

        # UMCF Kazakhstan 5-TZ preserved
        kz = parse_country_data(zf.read("def/country/kazakhstan.sui"))
        assert kz.time_zone == 300
        assert kz.time_zone_name == "@@tz_aqtt@@"
        assert kz.secondary_time_zone == [360]

        # SEA/RoC headerless .sii fragment stays headerless + custom lane & train/tram preserved
        raw_cde = zf.read("def/country/custom_de.sii")
        assert not SiiDocument.parse(raw_cde).has_siinunit
        assert b"SiiNunit" not in raw_cde
        spd_cde = parse_speed_limits(zf.read("def/country/custom_de/speed_limits.sii"))
        car_block = spd_cde.get_block("car")
        assert car_block is not None
        assert [lane.lane_speed_class for lane in car_block.lanes] == [
            "local_road",
            "autobahn_special",
            "motorway",
        ]
        assert car_block.lanes[1].limit == 150
        assert spd_cde.get_block("train") is not None
        assert spd_cde.get_block("tram") is not None

        # 43-locale Vanilla Option 4b + pm_fuel emitted
        ets2v2_loc_files = [n for n in names if n.endswith("/local_module.ets2v2_fuel.sii")]
        pm_loc_files = [n for n in names if n.endswith("/local_module.pm_fuel.sii")]
        assert len(ets2v2_loc_files) == 43
        assert len(pm_loc_files) == 43
        pm_entries = {e.key: e.val for e in parse_localization_db(zf.read(pm_loc_files[0]))}
        assert pm_entries["pm_custom_unrecognized"] == "KEEP_ME"

        # Manifest marker embedded cleanly
        assert ETS2V2_MANIFEST_MARKER.encode("utf-8") in zf.read("manifest.sii")


def test_compose_local_strict_protected_and_unpacked_defs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod_dir, modlist_path, snap_path, unpacked_root = _build_synthetic_combo_fixture(tmp_path)
    out_fail = tmp_path / "out_strict_fail"

    rc_fail = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(snap_path),
            "--out-dir",
            str(out_fail),
            "--strict-protected",
            "--json",
        ]
    )
    assert rc_fail == 1
    rep_fail = ComposeReport.model_validate_json(capsys.readouterr().out)
    assert rep_fail.ok is False
    assert rep_fail.errors
    assert not (out_fail / COMBO_SCS_FILENAMES["summer"]).exists()

    # Supplying stem-matched --unpacked-defs satisfies --strict-protected and includes Jordan!
    out_ok = tmp_path / "out_strict_ok"
    rc_ok = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(snap_path),
            "--unpacked-defs",
            str(unpacked_root),
            "--out-dir",
            str(out_ok),
            "--strict-protected",
            "--json",
        ]
    )
    assert rc_ok == 0
    rep_ok = ComposeReport.model_validate_json(capsys.readouterr().out)
    assert rep_ok.ok is True
    assert rep_ok.protected_archives[0].substituted_by is not None
    scs_ok = out_ok / COMBO_SCS_FILENAMES["summer"]
    assert scs_ok.is_file()
    with ZipFile(scs_ok, "r") as zf:
        assert "def/country/jordan.sui" in zf.namelist()


def test_compose_local_patch_hardcoded_totems(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod_dir, modlist_path, snap_path, _ = _build_synthetic_combo_fixture(tmp_path)
    out_dir = tmp_path / "out_hc"

    rc = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(snap_path),
            "--out-dir",
            str(out_dir),
            "--patch-hardcoded-totems",
            "--json",
        ]
    )
    assert rc == 0
    rep = ComposeReport.model_validate_json(capsys.readouterr().out)
    assert rep.hardcoded_totems_enabled is True
    assert rep.hardcoded_totems_patched == 1

    scs_path = out_dir / COMBO_SCS_FILENAMES["summer"]
    assert validate_local_zip(scs_path, baseline_dir=_BASELINE_DIR, profile="combo").ok is True
    with ZipFile(scs_path, "r") as zf:
        names = set(zf.namelist())
        assert "def/sign/board/kz_gas_totem_95.sii" in names
        assert "def/sign/board/indo_gas_totem_01j.sii" not in names
        assert "def/sign/board/indo_gas_totem_01a.sii" not in names  # ID not in Phase 4 snapshot
        kz_board = parse_sign_board(zf.read("def/sign/board/kz_gas_totem_95.sii"))
        assert kz_board.text_slots[0].localization_key == "fp_kz_petrol_95_ets2v2"
        loc_entries = {
            e.key: e.val
            for e in parse_localization_db(zf.read("locale/en_gb/local_module.ets2v2_fuel.sii"))
        }
        assert "fp_kz_petrol_95_ets2v2" in loc_entries
        assert loc_entries["fp_kz_petrol_95_ets2v2"].isdigit()


def test_compose_local_no_totems_and_baseline_only_snapshot(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod_dir, modlist_path, snap_path, _ = _build_synthetic_combo_fixture(tmp_path)
    out_nototem = tmp_path / "out_no_totems"

    rc = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(snap_path),
            "--out-dir",
            str(out_nototem),
            "--no-totems",
            "--json",
        ]
    )
    assert rc == 0
    rep = ComposeReport.model_validate_json(capsys.readouterr().out)
    assert rep.totems_enabled is False
    assert rep.vanilla_totem_boards_emitted == 0
    assert rep.promods_fuel_modules_emitted == []
    scs_path = out_nototem / COMBO_SCS_FILENAMES["summer"]
    assert validate_local_zip(scs_path, baseline_dir=_BASELINE_DIR, profile="combo").ok is True
    with ZipFile(scs_path, "r") as zf:
        names = zf.namelist()
        assert not any(n.startswith("def/sign/board/") for n in names)
        assert not any(n.startswith("locale/") for n in names)

    # Baseline-only snapshot (empty local_prices) fails with actionable error unless --no-totems
    registry = load_law_registry(Path("data/laws"), Path("data/mappings/ets2_countries.json"))
    bl_countries = CountriesBaseline.model_validate_json(
        (_BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (_BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    baseline_snap = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        "summer",
        prices_lock=None,
        vanilla_only=True,
    )
    baseline_snap_path = tmp_path / "baseline_only_summer.json"
    write_realism_snapshot(baseline_snap, baseline_snap_path)

    rc_err = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(baseline_snap_path),
            "--out-dir",
            str(tmp_path / "out_bl_err"),
        ]
    )
    assert rc_err == 1
    err_out = capsys.readouterr().err
    assert "--no-totems" in err_out

    rc_bl_ok = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(baseline_snap_path),
            "--out-dir",
            str(tmp_path / "out_bl_ok"),
            "--no-totems",
        ]
    )
    assert rc_bl_ok == 0


def test_compose_local_dry_run_report_json_and_tracked_out_dir_guard(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod_dir, modlist_path, snap_path, _ = _build_synthetic_combo_fixture(tmp_path)
    out_dry = tmp_path / "out_dry"
    report_path = tmp_path / "audit" / "compose_report.json"

    rc = cli_main(
        [
            "compose-local",
            "--season",
            "summer",
            "--modlist",
            str(modlist_path),
            "--mod-dir",
            str(mod_dir),
            "--snapshot",
            str(snap_path),
            "--out-dir",
            str(out_dry),
            "--dry-run",
            "--report-json",
            str(report_path),
            "--json",
        ]
    )
    assert rc == 0
    stdout_json = json.loads(capsys.readouterr().out)
    assert report_path.is_file()
    raw_report = report_path.read_bytes()
    assert not raw_report.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw_report
    disk_json = json.loads(raw_report.decode("utf-8"))
    assert disk_json == stdout_json
    assert disk_json["dry_run"] is True
    assert disk_json["output_path"] is None
    assert not (out_dry / COMBO_SCS_FILENAMES["summer"]).exists()

    # Tracked-repo --out-dir guard rejects data/, src/, tests/, state/
    for tracked_sub in ("data", "src", "tests", "state"):
        with pytest.raises(ValueError, match="Refusing to write"):
            compose_local(
                "summer",
                out_dir=Path(tracked_sub) / "combo_bad",
                modlist=modlist_path,
                mod_dir=mod_dir,
                snapshot_path=snap_path,
            )


def test_compose_local_nested_wrapper_include_end_to_end(tmp_path: Path) -> None:
    """HI-02 regression: nested def/ wrapper @include resolves cleanly in compose_local()."""
    mod_dir = tmp_path / "mods"
    mod_dir.mkdir()
    with ZipFile(mod_dir / "nested_wrap_map.scs", "w") as zf:
        zf.writestr(
            "def/country.wrap.sii",
            'SiiNunit\n{\n@include "country_wrap_list.sui"\n}\n',
        )
        zf.writestr(
            "def/country_wrap_list.sui",
            '@include "country/nested_dir/list.sii"\n',
        )
        zf.writestr(
            "def/country/nested_dir/list.sii",
            '@include "/def/country/wrap_germany.sui"\n',
        )
        zf.writestr(
            "def/country/wrap_germany.sui",
            (
                "country_data : country.data.wrap_germany\n"
                "{\n"
                "\tcountry_id: 612\n"
                '\tname: "Wrap Germany"\n'
                '\tcountry_code: "D"\n'
                "\tiso_country_code: deu\n"
                "\tfuel_price: 1.40\n"
                "\tlights_mandatory: true\n"
                "\tdriving_tired_offence: true\n"
                "\timperial_units: false\n"
                "\ttime_zone: 60\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )

    modlist = tmp_path / "mods.txt"
    modlist.write_text("nested_wrap_map.scs\n", encoding="utf-8", newline="\n")
    snap_path = tmp_path / "snap.json"
    write_realism_snapshot(load_or_build_snapshot("summer"), snap_path)
    out_dir = tmp_path / "out_wrap"

    report = compose_local(
        "summer",
        out_dir=out_dir,
        modlist=modlist,
        mod_dir=mod_dir,
        snapshot_path=snap_path,
        no_totems=True,
    )
    assert report.ok is True
    scs_path = out_dir / COMBO_SCS_FILENAMES["summer"]
    with ZipFile(scs_path, "r") as zf:
        assert "def/country/wrap_germany.sui" in zf.namelist()
        parsed = parse_country_data(zf.read("def/country/wrap_germany.sui"))
        assert parsed.time_zone == 120
        assert parsed.time_zone_name == "@@tz_cest@@"


def test_md02_md07_in03_compose_fault_isolation_malformed_fragments_and_atomic_report(
    tmp_path: Path,
) -> None:
    """MD-02 + MD-07 + IN-03: malformed speed_limits, hygiene/half-TZ/missing-code skip cleanly."""
    mod_dir = tmp_path / "mods"
    mod_dir.mkdir()
    with ZipFile(mod_dir / "broken_third_party.scs", "w") as zf:
        zf.writestr(
            "def/country.broken.sii",
            (
                "SiiNunit\n{\n"
                '@include "country/bad_hygiene_de.sui"\n'
                '@include "country/half_tz_de.sui"\n'
                '@include "country/missing_cc_de.sui"\n'
                '@include "country/bad_spd_de.sui"\n'
                "}\n"
            ),
        )
        # 1. >12-char unit segment triggers apply_country_policy() hygiene ValueError (MD-02)
        zf.writestr(
            "def/country/bad_hygiene_de.sui",
            (
                "country_data : country.data.superlongcountryname\n{\n"
                "\tcountry_id: 701\n"
                '\tname: "Bad Hygiene DE"\n'
                '\tcountry_code: "D"\n'
                "\tiso_country_code: deu\n"
                "\tfuel_price: 1.50\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: 60\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )
        # 2. Half-TZ: time_zone_name set without time_zone (MD-07)
        zf.writestr(
            "def/country/half_tz_de.sui",
            (
                "country_data : country.data.half_tz_de\n{\n"
                "\tcountry_id: 702\n"
                '\tname: "Half TZ DE"\n'
                '\tcountry_code: "D"\n'
                "\tiso_country_code: deu\n"
                "\tfuel_price: 1.50\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )
        # 3. Missing country_code (MD-07)
        zf.writestr(
            "def/country/missing_cc_de.sui",
            (
                "country_data : country.data.missing_cc\n{\n"
                "\tcountry_id: 703\n"
                '\tname: "Missing Code DE"\n'
                "\tiso_country_code: deu\n"
                "\tfuel_price: 1.50\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: 60\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )
        # 4. Valid country with malformed speed_limits.sii (limit[] before lane_speed_class[])
        zf.writestr(
            "def/country/bad_spd_de.sui",
            (
                "country_data : country.data.bad_spd_de\n{\n"
                "\tcountry_id: 704\n"
                '\tname: "Bad Speed DE"\n'
                '\tcountry_code: "D"\n'
                "\tiso_country_code: deu\n"
                "\tfuel_price: 1.50\n"
                "\tlights_mandatory: false\n"
                "\tdriving_tired_offence: true\n"
                "\ttime_zone: 60\n"
                '\ttime_zone_name: "@@tz_cet@@"\n'
                "\tmass_limit_per_axle_count[]: 18000\n"
                "\tmass_limit_per_axle_count[]: 26000\n"
                "\tmass_limit_per_axle_count[]: 40000\n"
                "}\n"
            ),
        )
        zf.writestr(
            "def/country/bad_spd_de/speed_limits.sii",
            (
                "SiiNunit\n{\n"
                "country_speed_limit : .speed_limit.car\n{\n"
                "\tvehicle_speed_class: car\n"
                "\tlimit[]: 80\n"
                "\tlane_speed_class[]: local_road\n"
                "}\n}\n"
            ),
        )

    modlist = tmp_path / "mods.txt"
    modlist.write_text("broken_third_party.scs\n", encoding="utf-8", newline="\n")
    snap_path = tmp_path / "snap.json"
    write_realism_snapshot(load_or_build_snapshot("summer"), snap_path)
    out_dir = tmp_path / "out_fault"
    report_path = tmp_path / "report_dir" / "compose.json"

    report = compose_local(
        "summer",
        out_dir=out_dir,
        modlist=modlist,
        mod_dir=mod_dir,
        snapshot_path=snap_path,
        no_totems=True,
        report_json_path=report_path,
    )
    assert report.ok is True
    assert report.validation_ok is True
    by_slug = {c.slug: c for c in report.countries}
    assert by_slug["bad_hygiene_de"].emitted is False
    assert by_slug["half_tz_de"].emitted is False
    assert by_slug["missing_cc_de"].emitted is False
    assert by_slug["bad_spd_de"].emitted is True
    assert by_slug["bad_spd_de"].speed_limits_status == "skipped_parse_error"

    scs_path = out_dir / COMBO_SCS_FILENAMES["summer"]
    assert validate_local_zip(scs_path, baseline_dir=_BASELINE_DIR, profile="combo").ok is True
    with ZipFile(scs_path, "r") as zf:
        names = set(zf.namelist())
        assert "def/country/bad_hygiene_de.sui" not in names
        assert "def/country/half_tz_de.sui" not in names
        assert "def/country/missing_cc_de.sui" not in names
        assert "def/country/bad_spd_de.sui" in names
        assert "def/country/bad_spd_de/speed_limits.sii" not in names

    # IN-03: atomic report written cleanly with no temp files left behind
    assert report_path.is_file()
    assert list(report_path.parent.glob(".tmp_*")) == []


def _find_local_combo_inputs() -> tuple[Path, Path, Path] | None:
    mod_dir = _LOCAL_ETS2_DATA_DIR / "mod"
    if not mod_dir.is_dir():
        return None
    profiles_dir = _LOCAL_ETS2_DATA_DIR / "profiles"
    if profiles_dir.is_dir():
        for prof_dir in sorted(profiles_dir.iterdir()):
            prof_sii = prof_dir / "profile.sii"
            if prof_sii.is_file() and not prof_sii.read_bytes()[:4].startswith(b"ScsC"):
                return mod_dir, prof_sii, Path("profile")
    game_log = _LOCAL_ETS2_DATA_DIR / "game.log.txt"
    if game_log.is_file():
        return mod_dir, game_log, Path("game_log")
    return None


@pytest.mark.local_promods
@pytest.mark.skipif(
    _find_local_combo_inputs() is None,
    reason="Local ETS2 profile/mod directory not present",
)
def test_local_combo_dry_run_audit(tmp_path: Path) -> None:
    found = _find_local_combo_inputs()
    assert found is not None
    mod_dir, source_path, kind = found
    report_path = tmp_path / "local_combo_report.json"

    if str(kind) == "profile":
        report = compose_local(
            "summer",
            profile=source_path,
            mod_dir=mod_dir,
            dry_run=True,
            report_json_path=report_path,
        )
    else:
        report = compose_local(
            "summer",
            game_log=source_path,
            mod_dir=mod_dir,
            dry_run=True,
            report_json_path=report_path,
        )

    assert report.ok is True
    assert report.dry_run is True
    assert report.countries_scanned >= 36
    assert report.countries_patched >= 36
    assert report_path.is_file()
