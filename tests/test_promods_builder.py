"""Synthetic clean-room and @pytest.mark.local_promods tests for ProMods Companion Builder."""

from __future__ import annotations

import json
import pathlib
import zipfile
from typing import cast

import pytest

from ets2_realism.baseline.models import CountriesBaseline, LocalesBaseline
from ets2_realism.cli import main
from ets2_realism.merge.promods_builder import (
    ProModsBuildReport,
    assert_out_dir_not_tracked,
    build_promods_edition,
    build_promods_editions,
)
from ets2_realism.merge.promods_discovery import discover_promods_packs, resolve_mod_dir
from ets2_realism.package.totems import snapshot_to_totem_lockfile
from ets2_realism.registry.loader import load_law_registry
from ets2_realism.registry.snapshot import (
    build_realism_snapshot,
    load_or_build_snapshot,
    write_realism_snapshot,
    write_sha256sums,
)
from ets2_realism.sii.country import parse_country_data
from ets2_realism.sii.localization import parse_localization_db
from ets2_realism.sii.speed_limits import parse_speed_limits
from ets2_realism.validate import validate_local_zip, validate_workshop_package

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"
LAWS_DIR = REPO_ROOT / "data" / "laws"
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "ets2_countries.json"
ALIASES_PATH = REPO_ROOT / "data" / "mappings" / "country_aliases.json"
ICONS_DIR = REPO_ROOT / "assets" / "icons"


def _write_zip(path: pathlib.Path, entries: dict[str, bytes]) -> pathlib.Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(entries):
            zi = zipfile.ZipInfo(filename=rel, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, entries[rel])
    return path


def _make_loc_sii(unit_name: str, pairs: list[tuple[str, str]]) -> bytes:
    lines = ["SiiNunit", "{", f"localization_db : {unit_name}", "{"]
    for k, v in pairs:
        lines.append(f'\tkey[]: "{k}"')
        lines.append(f'\tval[]: "{v}"')
    lines.extend(["}", "}"])
    return ("\n".join(lines) + "\n").encode("utf-8")


def _create_synthetic_promods_mod_dir(mod_dir: pathlib.Path) -> pathlib.Path:
    """Create clean-room synthetic ProMods EU + TGS + ME + MA def/defmap + assets ZIP fixtures."""
    mod_dir.mkdir(parents=True, exist_ok=True)

    # 1. ProMods EU def (uk.sui with scotland/wales, can_islands, armenia, ireland + speed_limits)
    uk_promods_sui = (
        b"country_data : country.data.uk\n{\n"
        b"\tcountry_id: 10\n"
        b'\tname: "United Kingdom"\n'
        b'\tname_localized: "@@uk@@"\n'
        b'\tcountry_code: "UK"\n'
        b"\tiso_country_code: gbr\n"
        b"\tpos: (-50000, 0, -15000)\n"
        b"\tfuel_price: 1.50\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\timperial_units: true\n"
        b"\tleftside_traffic: true\n"
        b"\ttime_zone: 60\n"
        b'\ttime_zone_name: "@@tz_bst@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 26000\n"
        b"\tmass_limit_per_axle_count[]: 38000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"\tmass_limit_per_axle_count[]: 44000\n"
        b'\tregions[]: "scotland"\n'
        b'\tregions[]: "wales"\n'
        b"\tregion_areas[]: (-60000, -40000, -30000, -20000)\n"
        b"\tregion_areas[]: (-58000, -50000, -18000, -12000)\n"
        b"}\n"
    )

    can_islands_sui = (
        b"country_data : country.data.can_islands\n{\n"
        b"\tcountry_id: 240\n"
        b'\tname: "Canary Islands"\n'
        b'\tcountry_code: "E"\n'
        b"\tiso_country_code: esp\n"
        b"\tfuel_price: 1.30\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\ttime_zone: 60\n"
        b'\ttime_zone_name: "@@tz_west@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 26000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )

    armenia_sui = (
        b"country_data : country.data.armenia\n{\n"
        b"\tcountry_id: 47\n"
        b'\tname: "Armenia"\n'
        b'\tcountry_code: "AM"\n'
        b"\tiso_country_code: arm\n"
        b"\tfuel_price: 1.10\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\tleftside_traffic: false\n"
        b"\ttime_zone: 240\n"
        b'\ttime_zone_name: "AMT"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 25000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )

    ireland_sui = (
        b"country_data : country.data.ireland\n{\n"
        b"\tcountry_id: 27\n"
        b'\tname: "Ireland"\n'
        b'\tcountry_code: "IRL"\n'
        b"\tiso_country_code: irl\n"
        b"\tfuel_price: 1.60\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\tleftside_traffic: true\n"
        b"\ttime_zone: 60\n"
        b'\ttime_zone_name: "IST"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 26000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )

    ireland_spd = (
        b"SiiNunit\n{\n"
        b"country_speed_limit : .speed_limit.car\n{\n"
        b"\tvehicle_speed_class: car\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n"
        b"\tlane_speed_class[]: expressway\n\tlimit[]: 100\n\turban_limit[]: 50\n"
        b"\tlane_speed_class[]: motorway\n\tlimit[]: 120\n\turban_limit[]: 50\n"
        b"\tlane_speed_class[]: pm_custom_lane\n\tlimit[]: 65\n\turban_limit[]: 40\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.truck\n{\n"
        b"\tvehicle_speed_class: truck\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n\tmax_limit[]: 80\n"
        b"\tlane_speed_class[]: expressway\n\tlimit[]: 80\n\turban_limit[]: 50\n\tmax_limit[]: 80\n"
        b"\tlane_speed_class[]: motorway\n\tlimit[]: 90\n\turban_limit[]: 50\n\tmax_limit[]: 90\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.bus\n{\n"
        b"\tvehicle_speed_class: bus\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 80\n\turban_limit[]: 50\n"
        b"\tlane_speed_class[]: expressway\n\tlimit[]: 100\n\turban_limit[]: 50\n"
        b"\tlane_speed_class[]: motorway\n\tlimit[]: 100\n\turban_limit[]: 50\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.train\n{\n"
        b"\tvehicle_speed_class: train\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 120\n"
        b"}\n"
        b"country_speed_limit : .speed_limit.tram\n{\n"
        b"\tvehicle_speed_class: tram\n"
        b"\tlane_speed_class[]: local_road\n\tlimit[]: 45\n"
        b"}\n}\n"
    )

    _write_zip(
        mod_dir / "promods-eu-def-v285.scs",
        {
            "def/country.promods.sii": (
                b'SiiNunit\n{\n@include "country/can_islands.sui"\n'
                b'@include "country/armenia.sui"\n@include "country/ireland.sui"\n}\n'
            ),
            "def/country/uk.sui": uk_promods_sui,
            "def/country/can_islands.sui": can_islands_sui,
            "def/country/armenia.sui": armenia_sui,
            "def/country/ireland.sui": ireland_sui,
            "def/country/ireland/speed_limits.sii": ireland_spd,
            # Unreferenced file should NOT be emitted (not in any def/country*.sii)
            "def/country/unused_draft.sui": armenia_sui.replace(
                b"country.data.armenia", b"country.data.unused_draft"
            ),
        },
    )

    _write_zip(
        mod_dir / "promods-eu-assets-v285.scs",
        {
            "locale/en_gb/local_module.pm_fuel.sii": _make_loc_sii(
                ".pm_fuel",
                [
                    ("fp_de_diesel_v4", "160.<sup>0</sup>"),
                    ("fp_mn_diesel", "1.00"),
                    ("fp_cni_diesel", "1.00"),
                    ("fp_future_unknown", "KEEP_ME"),
                ],
            ),
            "locale/fr_qc/local_module.pm_fuel.sii": _make_loc_sii(
                ".pm_fuel", [("fp_mn_diesel", "1.00")]
            ),
        },
    )

    # 2. ProMods TGS defmap + assets (15-TZ russia.sui, kazakhstan, uzbekistan with stale tz=360)
    russia_tgs_sui = (
        "country_data : country.data.russia\n{\n"
        "\tcountry_id: 38\n"
        '\tname: "Россия"\n'
        '\tname_localized: "@@russia@@"\n'
        '\tcountry_code: "RUS"\n'
        "\tiso_country_code: rus\n"
        "\tpos: (35000, 0, -25000)\n"
        "\tfuel_price: 0.65\n"
        "\tlights_mandatory: true\n"
        "\tdriving_tired_offence: true\n"
        "\ttime_zone: 180\n"
        '\ttime_zone_name: "@@tz_msk@@"\n'
        "\tsecondary_time_zone_area[]: (10000, 20000, -30000, -20000)\n"
        "\tsecondary_time_zone[]: 120\n"
        '\tsecondary_time_zone_name[]: "@@tz_eet@@"\n'
        "\tsecondary_time_zone_area[]: (60000, 80000, -30000, -10000)\n"
        "\tsecondary_time_zone[]: 300\n"
        '\tsecondary_time_zone_name[]: "@@tz_yekt@@"\n'
        "\tmass_limit_per_axle_count[]: 18000\n"
        "\tmass_limit_per_axle_count[]: 25000\n"
        "\tmass_limit_per_axle_count[]: 36000\n"
        "\tmass_limit_per_axle_count[]: 40000\n"
        "\tmass_limit_per_axle_count[]: 44000\n"
        "}\n"
    ).encode()

    kazakhstan_sui = (
        b"country_data : country.data.kazakhstan\n{\n"
        b"\tcountry_id: 64\n"
        b'\tname: "Kazakhstan"\n'
        b'\tcountry_code: "KZ"\n'
        b"\tiso_country_code: kaz\n"
        b"\tfuel_price: 0.50\n"
        b"\tlights_mandatory: true\n"
        b"\tdriving_tired_offence: true\n"
        b"\ttime_zone: 300\n"
        b'\ttime_zone_name: "AQTT"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 25000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )

    uzbekistan_sui = (
        b"country_data : country.data.uzbekistan\n{\n"
        b"\tcountry_id: 90\n"
        b'\tname: "Uzbekistan"\n'
        b'\tcountry_code: "UZ"\n'
        b"\tiso_country_code: uzb\n"
        b"\tfuel_price: 0.90\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\ttime_zone: 360\n"
        b'\ttime_zone_name: "UTC+6"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 25000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )

    _write_zip(
        mod_dir / "promods-tgs-defmap-v171.scs",
        {
            "def/country.kz.sii": (
                b'SiiNunit\n{\n@include "country/kazakhstan.sui"\n'
                b'@include "country/uzbekistan.sui"\n}\n'
            ),
            "def/country/russia.sui": russia_tgs_sui,
            "def/country/kazakhstan.sui": kazakhstan_sui,
            "def/country/uzbekistan.sui": uzbekistan_sui,
        },
    )
    _write_zip(
        mod_dir / "promods-tgs-assets-v171.scs",
        {
            "locale/en_gb/local_module.pm_tgs_fuel.sii": _make_loc_sii(
                ".pm_tgs_fuel",
                [("fp_kz_diesel", "100"), ("fp_mn_diesel", "100")],
            ),
        },
    )

    # 3. ProMods ME defmap + assets
    jordan_sui = (
        b"country_data : country.data.jordan\n{\n"
        b"\tcountry_id: 63\n"
        b'\tname: "Jordan"\n'
        b'\tcountry_code: "HKJ"\n'
        b"\tiso_country_code: jor\n"
        b"\tfuel_price: 1.00\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\ttime_zone: 180\n"
        b'\ttime_zone_name: "AST"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 26000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )

    _write_zip(
        mod_dir / "promods-me-defmap-v285.scs",
        {
            "def/country.mideast.sii": (
                b'SiiNunit\r\n{\r\n@include "country/jordan.sui"\r\n'
                b"# 235 \xc5land legacy cp1252 comment\r\n}\r\n"
            ),
            "def/country/jordan.sui": jordan_sui,
        },
    )
    _write_zip(
        mod_dir / "promods-me-assets-v285.scs",
        {
            "locale/en_gb/local_module.pm_me_fuel.sii": _make_loc_sii(
                ".pm_me_fuel",
                [("fp_syr_diesel", "150"), ("fp_jor_diesel_v1", "0.800")],
            ),
        },
    )

    # 4. ProMods MA defmap
    morocco_sui = (
        b"country_data : country.data.morocco\n{\n"
        b"\tcountry_id: 126\n"
        b'\tname: "Morocco"\n'
        b'\tcountry_code: "MA"\n'
        b"\tiso_country_code: mar\n"
        b"\tfuel_price: 1.15\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\ttime_zone: 60\n"
        b'\ttime_zone_name: "@@tz_west@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 26000\n"
        b"\tmass_limit_per_axle_count[]: 36000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )

    _write_zip(
        mod_dir / "promods-ma-defmap-v105.scs",
        {
            "def/country.mgm.sii": b'SiiNunit\n{\n@include "country/morocco.sui"\n}\n',
            "def/country/morocco.sui": morocco_sui,
        },
    )
    return mod_dir


def test_snapshot_to_totem_lockfile_converts_priced_and_rejects_baseline_only() -> None:
    priced_snap = load_or_build_snapshot("summer")
    converted = snapshot_to_totem_lockfile(priced_snap)
    assert len(converted.countries) == len(priced_snap.countries)
    assert "DE" in converted.countries
    assert converted.countries["DE"].local_prices["diesel"] > 0.0

    # Baseline-only snapshot (empty local_prices) must raise an actionable ValueError
    registry = load_law_registry(LAWS_DIR, MAPPINGS_PATH)
    bl_countries = CountriesBaseline.model_validate_json(
        (BASELINE_DIR / "countries.json").read_text("utf-8")
    )
    bl_locales = LocalesBaseline.model_validate_json(
        (BASELINE_DIR / "locales.json").read_text("utf-8")
    )
    baseline_only = build_realism_snapshot(
        registry,
        bl_countries,
        bl_locales,
        "summer",
        prices_lock=None,
    )
    with pytest.raises(ValueError, match="local_prices"):
        snapshot_to_totem_lockfile(baseline_only)


def test_assert_out_dir_not_tracked_refuses_all_repo_subdirs(tmp_path: pathlib.Path) -> None:
    # HI-04: refuse repo root itself
    with pytest.raises(ValueError, match="repository root"):
        assert_out_dir_not_tracked(REPO_ROOT, repo_root=REPO_ROOT)

    for subdir in (
        "data",
        "src",
        "tests",
        "state",
        "assets",
        ".github",
        ".git",
        ".planning",
        "scripts",
        ".agents",
        "workshop",
        "local",
    ):
        with pytest.raises(ValueError, match="tracked"):
            assert_out_dir_not_tracked(REPO_ROOT / subdir, repo_root=REPO_ROOT)
        with pytest.raises(ValueError, match="tracked"):
            assert_out_dir_not_tracked(REPO_ROOT / subdir / "nested", repo_root=REPO_ROOT)

    # Allowed gitignored repo subdirs and external tmp_path are permitted
    for allowed in ("dist", "out", "build", "raw", "vendor"):
        assert_out_dir_not_tracked(REPO_ROOT / allowed / "promods_out", repo_root=REPO_ROOT)
    assert_out_dir_not_tracked(tmp_path / "safe_out", repo_root=REPO_ROOT)


def test_assert_out_dir_not_tracked_allows_non_repo_external_cwd(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-repo CWD (e.g. ETS2 user data dir) must allow ./mod without false positives
    ets2_user_dir = tmp_path / "ets2_user_data"
    ets2_user_dir.mkdir()
    monkeypatch.chdir(ets2_user_dir)
    assert_out_dir_not_tracked(pathlib.Path("mod"))

    # A second checkout with .git or pyproject.toml IS still protected when CWD
    alt_repo = tmp_path / "alt_checkout"
    (alt_repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(alt_repo)
    with pytest.raises(ValueError, match="tracked"):
        assert_out_dir_not_tracked(pathlib.Path("mod"))
    assert_out_dir_not_tracked(pathlib.Path("dist/promods"))


def test_promods_builder_synthetic_full_summer_and_winter_repo_fallback(
    tmp_path: pathlib.Path,
) -> None:
    mod_dir = _create_synthetic_promods_mod_dir(tmp_path / "mod")
    out_dir = tmp_path / "dist"

    reports = build_promods_editions(
        out_dir,
        mod_dir=mod_dir,
        require_all_packs=True,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        aliases_path=ALIASES_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
    )
    assert set(reports.keys()) == {"summer", "winter"}

    for edition in ("summer", "winter"):
        report = reports[edition]
        assert isinstance(report, ProModsBuildReport)
        assert report.validation_ok is True
        assert report.vanilla_countries_emitted == 36
        assert report.promods_countries_emitted == 7
        assert report.countries_patched == 43
        assert report.pm_fuel_modules_emitted == ["pm_fuel", "pm_me_fuel", "pm_tgs_fuel"]
        assert report.workshop_dir == out_dir / "workshop" / f"promods-{edition}"
        assert report.local_zip_path == (
            out_dir / "local" / f"ETS2_Country_Realism_ProMods_{edition.capitalize()}.zip"
        )

        # Independent Offline SCS Validator check on both Workshop root and local ZIP
        ws_val = validate_workshop_package(
            report.workshop_dir, baseline_dir=BASELINE_DIR, profile="promods"
        )
        assert ws_val.ok is True, ws_val.issues
        zip_val = validate_local_zip(
            report.local_zip_path, baseline_dir=BASELINE_DIR, profile="promods"
        )
        assert zip_val.ok is True, zip_val.issues

        uni = report.workshop_dir / "universal"
        # Minimal realism-only footprint: ZERO def/country*.sii, ZERO .dds/.tobj, ZERO unused_draft
        assert list((uni / "def").glob("country*.sii")) == []
        assert not (uni / "def" / "country" / "unused_draft.sui").exists()
        assert list(uni.rglob("*.dds")) == []
        assert list(uni.rglob("*.tobj")) == []

        # ProMods UK preserves scotland & wales regions
        uk = parse_country_data((uni / "def" / "country" / "uk.sui").read_bytes())
        assert {"scotland", "wales"} <= set(uk.regions)

        # TGS russia.sui preserves its multi-TZ secondary_time_zone entries
        ru = parse_country_data((uni / "def" / "country" / "russia.sui").read_bytes())
        assert len(ru.secondary_time_zone) == 2
        assert ru.secondary_time_zone_name == ["@@tz_eet@@", "@@tz_yekt@@"]

        # Canary Islands resolves Atlantic/Canary (WET in winter, @@tz_west@@ in summer)
        cni = parse_country_data((uni / "def" / "country" / "can_islands.sui").read_bytes())
        if edition == "summer":
            assert cni.time_zone == 60
            assert cni.time_zone_name == "@@tz_west@@"
        else:
            assert cni.time_zone == 0
            assert cni.time_zone_name == "WET"

        # Uzbekistan fixes stale UTC+6 (360) -> +300 (UZT)
        uz = parse_country_data((uni / "def" / "country" / "uzbekistan.sui").read_bytes())
        assert uz.time_zone == 300
        assert uz.time_zone_name == "UZT"

        # Ireland speed_limits.sii preserves custom lane class + train/tram
        ie_spd = parse_speed_limits(
            (uni / "def" / "country" / "ireland" / "speed_limits.sii").read_bytes()
        )
        car_block = ie_spd.get_block("car")
        assert car_block is not None
        assert any(lane.lane_speed_class == "pm_custom_lane" for lane in car_block.lanes)
        assert ie_spd.get_block("train") is not None
        assert ie_spd.get_block("tram") is not None

        # All 43 active locales present for ets2r_fuel + pm_fuel + pm_me_fuel + pm_tgs_fuel
        locale_dirs = sorted(p.name for p in (uni / "locale").iterdir() if p.is_dir())
        assert len(locale_dirs) == 43
        assert "fr_ca" in locale_dirs
        assert "fr_qc" not in locale_dirs

        pm_eu_entries = {
            e.key: e.val
            for e in parse_localization_db(
                (uni / "locale" / "en_gb" / "local_module.pm_fuel.sii").read_bytes()
            )
        }
        pm_tgs_entries = {
            e.key: e.val
            for e in parse_localization_db(
                (uni / "locale" / "en_gb" / "local_module.pm_tgs_fuel.sii").read_bytes()
            )
        }
        assert float(pm_eu_entries["fp_mn_diesel"]) < 10.0  # Montenegro EUR
        assert pm_eu_entries["fp_future_unknown"] == "KEEP_ME"
        assert pm_tgs_entries["fp_mn_diesel"].isdigit()
        assert int(pm_tgs_entries["fp_mn_diesel"]) > 1000  # Mongolia MNT integer


def test_promods_builder_offline_snapshot_checksums_and_cli_json(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod_dir = _create_synthetic_promods_mod_dir(tmp_path / "mod")
    snap_dir = tmp_path / "snapshots"
    snap_path = snap_dir / "realism-snapshot-summer.json"
    checksums_path = snap_dir / "SHA256SUMS.txt"

    summer_snap = load_or_build_snapshot("summer")
    write_realism_snapshot(summer_snap, snap_path)
    write_sha256sums([snap_path], checksums_path)

    out_dir = tmp_path / "cli_out"
    rc = main(
        [
            "package",
            "promods",
            "--edition",
            "summer",
            "--mod-dir",
            str(mod_dir),
            "--out-dir",
            str(out_dir),
            "--snapshot",
            str(snap_path),
            "--checksums",
            str(checksums_path),
            "--require-all-packs",
            "--json",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    parsed = cast(dict[str, object], json.loads(captured.out))
    assert "summer" in parsed

    # CLI validate workshop/local with --profile promods
    rc_ws = main(
        [
            "validate",
            "workshop",
            str(out_dir / "workshop" / "promods-summer"),
            "--profile",
            "promods",
        ]
    )
    assert rc_ws == 0
    rc_zip = main(
        [
            "validate",
            "local",
            str(out_dir / "local" / "ETS2_Country_Realism_ProMods_Summer.zip"),
            "--profile",
            "promods",
        ]
    )
    assert rc_zip == 0


def test_promods_builder_modular_eu_only_and_require_all_packs_fast_fail(
    tmp_path: pathlib.Path,
) -> None:
    full_mod = _create_synthetic_promods_mod_dir(tmp_path / "full_mod")
    eu_only_mod = tmp_path / "eu_only_mod"
    eu_only_mod.mkdir()
    (eu_only_mod / "promods-eu-def-v285.scs").write_bytes(
        (full_mod / "promods-eu-def-v285.scs").read_bytes()
    )

    with pytest.raises(FileNotFoundError, match="require-all-packs"):
        build_promods_edition(
            "summer",
            tmp_path / "fail_out",
            mod_dir=eu_only_mod,
            require_all_packs=True,
        )

    # Without --require-all-packs, EU-only def succeeds cleanly (0 pm_fuel modules)
    report = build_promods_edition(
        "summer",
        tmp_path / "eu_ok_out",
        mod_dir=eu_only_mod,
        require_all_packs=False,
    )
    assert report.validation_ok is True
    assert report.pm_fuel_modules_emitted == []


def test_hi05_promods_builder_stages_and_preserves_prior_build_on_validation_failure(
    tmp_path: pathlib.Path,
) -> None:
    """HI-05: failed validation must not leave unvalidated artifacts or clobber prior builds."""
    good_mod = _create_synthetic_promods_mod_dir(tmp_path / "good_mod")
    bad_mod = tmp_path / "bad_mod"
    bad_mod.mkdir()
    # Missing UK scotland/wales regions triggers profile="promods" validation failure
    _write_zip(
        bad_mod / "promods-eu-def-v285.scs",
        {
            "def/country.promods.sii": b'SiiNunit\n{\n@include "country/uk.sui"\n}\n',
            "def/country/uk.sui": (
                b"country_data : country.data.uk\n{\n"
                b"\tcountry_id: 10\n"
                b'\tname: "United Kingdom"\n'
                b'\tname_localized: "@@uk@@"\n'
                b'\tcountry_code: "UK"\n'
                b"\tiso_country_code: gbr\n"
                b"\tfuel_price: 1.50\n"
                b"\tlights_mandatory: false\n"
                b"\tdriving_tired_offence: true\n"
                b"\timperial_units: true\n"
                b"\tleftside_traffic: true\n"
                b"\ttime_zone: 60\n"
                b'\ttime_zone_name: "@@tz_bst@@"\n'
                b"\tmass_limit_per_axle_count[]: 18000\n"
                b"\tmass_limit_per_axle_count[]: 26000\n"
                b"\tmass_limit_per_axle_count[]: 40000\n"
                b"}\n"
            ),
        },
    )

    # Case 1: Clean output dir -> validation fails and leaves ZERO final or temp artifacts
    fresh_out = tmp_path / "fresh_out"
    with pytest.raises(ValueError, match="ProMods Workshop validation failed"):
        build_promods_edition(
            "summer",
            fresh_out,
            mod_dir=bad_mod,
            require_all_packs=False,
        )
    assert not (fresh_out / "workshop" / "promods-summer").exists()
    assert not (fresh_out / "local" / "ETS2_Country_Realism_ProMods_Summer.zip").exists()
    assert list((fresh_out / "workshop").glob(".tmp_*")) == []
    assert list((fresh_out / "local").glob(".tmp_*")) == []

    # Case 2: Existing valid build -> subsequent failed build preserves prior valid files untouched
    existing_out = tmp_path / "existing_out"
    good_report = build_promods_edition(
        "summer",
        existing_out,
        mod_dir=good_mod,
        require_all_packs=False,
    )
    prev_zip_bytes = good_report.local_zip_path.read_bytes()
    prev_uk_bytes = (
        good_report.workshop_dir / "universal" / "def" / "country" / "uk.sui"
    ).read_bytes()

    with pytest.raises(ValueError, match="ProMods Workshop validation failed"):
        build_promods_edition(
            "summer",
            existing_out,
            mod_dir=bad_mod,
            require_all_packs=False,
        )
    assert good_report.local_zip_path.read_bytes() == prev_zip_bytes
    assert (
        good_report.workshop_dir / "universal" / "def" / "country" / "uk.sui"
    ).read_bytes() == prev_uk_bytes
    assert list((existing_out / "workshop").glob(".tmp_*")) == []
    assert list((existing_out / "local").glob(".tmp_*")) == []


def test_md05_promods_builder_handles_wrapper_sii_3nk_and_root_absolute_include(
    tmp_path: pathlib.Path,
) -> None:
    """MD-05 regression: wrapper .sii under def/country/, 3nK files, and /def/ includes work."""
    mod_dir = tmp_path / "wrapper_mod"
    mod_dir.mkdir()
    uk_promods_sui = (
        b"country_data : country.data.uk\n{\n"
        b"\tcountry_id: 10\n"
        b'\tname: "United Kingdom"\n'
        b'\tname_localized: "@@uk@@"\n'
        b'\tcountry_code: "UK"\n'
        b"\tiso_country_code: gbr\n"
        b"\tfuel_price: 1.50\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\timperial_units: true\n"
        b"\tleftside_traffic: true\n"
        b"\ttime_zone: 60\n"
        b'\ttime_zone_name: "@@tz_bst@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 26000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b'\tregions[]: "scotland"\n'
        b'\tregions[]: "wales"\n'
        b"}\n"
    )
    andorra_sui = (
        b"country_data : country.data.andorra\n{\n"
        b"\tcountry_id: 111\n"
        b'\tname: "Andorra"\n'
        b'\tcountry_code: "AND"\n'
        b"\tiso_country_code: and\n"
        b"\tfuel_price: 1.40\n"
        b"\tlights_mandatory: false\n"
        b"\tdriving_tired_offence: true\n"
        b"\ttime_zone: 60\n"
        b'\ttime_zone_name: "@@tz_cet@@"\n'
        b"\tmass_limit_per_axle_count[]: 18000\n"
        b"\tmass_limit_per_axle_count[]: 26000\n"
        b"\tmass_limit_per_axle_count[]: 40000\n"
        b"}\n"
    )
    _write_zip(
        mod_dir / "promods-eu-def-v285.scs",
        {
            "def/country.promods.sii": (
                b'SiiNunit\n{\n@include "country/wrapper.sii"\n@include "country/obf_3nk.sui"\n}\n'
            ),
            "def/country/wrapper.sii": b'@include "/def/country/andorra.sui"\n',
            "def/country/andorra.sui": andorra_sui,
            "def/country/obf_3nk.sui": b"3nK\x01\x00\x01obfuscated_country",
            "def/country/uk.sui": uk_promods_sui,
        },
    )

    out_dir = tmp_path / "wrapper_out"
    report = build_promods_edition(
        "summer",
        out_dir,
        mod_dir=mod_dir,
        require_all_packs=False,
    )
    assert report.validation_ok is True
    uni = report.workshop_dir / "universal"
    assert (uni / "def" / "country" / "andorra.sui").is_file()
    assert not (uni / "def" / "country" / "wrapper.sii").exists()
    assert not (uni / "def" / "country" / "obf_3nk.sui").exists()


def _has_local_promods() -> bool:
    mod_dir = resolve_mod_dir()
    if not mod_dir.is_dir():
        return False
    pack_set = discover_promods_packs(mod_dir, require_eu_def=False)
    return bool(pack_set.ordered_packs())


@pytest.mark.local_promods
@pytest.mark.skipif(not _has_local_promods(), reason="Local ProMods archives not present")
def test_local_promods_companion_build_and_validate(tmp_path: pathlib.Path) -> None:
    mod_dir = resolve_mod_dir()
    pack_set = discover_promods_packs(mod_dir, require_eu_def=False)

    # Use real EU def if present; otherwise supply a minimal clean-room EU def override so all
    # real local ME/MA/TGS defmaps + EU/ME/TGS assets are still exercised end-to-end.
    eu_def_override: pathlib.Path | None = None
    if pack_set.eu_def is None:
        eu_def_override = _write_zip(
            tmp_path / "synthetic_eu_def_override.scs",
            {
                "def/country/uk.sui": (
                    b"country_data : country.data.uk\n{\n"
                    b"\tcountry_id: 10\n"
                    b'\tname: "United Kingdom"\n'
                    b'\tname_localized: "@@uk@@"\n'
                    b'\tcountry_code: "UK"\n'
                    b"\tiso_country_code: gbr\n"
                    b"\tpos: (-50000, 0, -15000)\n"
                    b"\tfuel_price: 1.50\n"
                    b"\tlights_mandatory: false\n"
                    b"\tdriving_tired_offence: true\n"
                    b"\timperial_units: true\n"
                    b"\tleftside_traffic: true\n"
                    b"\ttime_zone: 60\n"
                    b'\ttime_zone_name: "@@tz_bst@@"\n'
                    b"\tmass_limit_per_axle_count[]: 18000\n"
                    b"\tmass_limit_per_axle_count[]: 26000\n"
                    b"\tmass_limit_per_axle_count[]: 38000\n"
                    b"\tmass_limit_per_axle_count[]: 40000\n"
                    b"\tmass_limit_per_axle_count[]: 44000\n"
                    b'\tregions[]: "scotland"\n'
                    b'\tregions[]: "wales"\n'
                    b"}\n"
                ),
            },
        )

    report = build_promods_edition(
        "summer",
        tmp_path / "local_promods_out",
        mod_dir=mod_dir,
        eu_def=eu_def_override,
        require_all_packs=False,
        laws_dir=LAWS_DIR,
        mappings_path=MAPPINGS_PATH,
        aliases_path=ALIASES_PATH,
        baseline_dir=BASELINE_DIR,
        icons_dir=ICONS_DIR,
    )
    assert report.validation_ok is True
    assert report.vanilla_countries_emitted == 36
    assert report.countries_patched >= 36
    if pack_set.eu_assets is not None:
        assert "pm_fuel" in report.pm_fuel_modules_emitted
    if pack_set.me_assets is not None:
        assert "pm_me_fuel" in report.pm_fuel_modules_emitted
    if pack_set.tgs_assets is not None:
        assert "pm_tgs_fuel" in report.pm_fuel_modules_emitted

    ws_val = validate_workshop_package(
        report.workshop_dir, baseline_dir=BASELINE_DIR, profile="promods"
    )
    assert ws_val.ok is True, ws_val.issues
    zip_val = validate_local_zip(
        report.local_zip_path, baseline_dir=BASELINE_DIR, profile="promods"
    )
    assert zip_val.ok is True, zip_val.issues
