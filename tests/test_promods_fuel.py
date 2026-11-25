"""Unit tests for dynamic ProMods 43-locale local_module.pm*_fuel.sii compiler and formatting."""

from __future__ import annotations

import pathlib
import zipfile

import pytest

from ets2v2.baseline.models import LocalesBaseline
from ets2v2.merge.promods_fuel import (
    PM_EU_PREFIX_TO_ISO2,
    PM_FUEL_MODULES,
    PM_ME_PREFIX_TO_ISO2,
    PM_TGS_PREFIX_TO_ISO2,
    compile_promods_fuel_locales,
    compile_promods_fuel_module,
    format_pm_fuel_value,
)
from ets2v2.normalize.totem_format import format_national_pump_price
from ets2v2.registry.snapshot import load_or_build_snapshot
from ets2v2.sii.hygiene import validate_sii_hygiene, validate_unit_name_segments
from ets2v2.sii.localization import parse_localization_db
from ets2v2.vfs.hashfs import open_archive
from ets2v2.vfs.stack import VfsLayer, VfsStack

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "data" / "baselines" / "ets2_1.62_def"


def _load_locales() -> LocalesBaseline:
    return LocalesBaseline.model_validate_json((BASELINE_DIR / "locales.json").read_text("utf-8"))


def _make_loc_sii(unit_name: str, pairs: list[tuple[str, str]]) -> bytes:
    lines = ["SiiNunit", "{", f"localization_db : {unit_name}", "{"]
    for key, val in pairs:
        lines.append(f'\tkey[]: "{key}"')
        lines.append(f'\tval[]: "{val}"')
    lines.extend(["}", "}"])
    return ("\n".join(lines) + "\n").encode("utf-8")


@pytest.mark.parametrize(
    ("iso2", "price", "expected"),
    [
        # GBP pence Crown Dependencies (GG/IM/JE) vs 2-decimal Gibraltar (GI)
        ("GG", 1.429, "142.9"),
        ("IM", 1.554, "155.4"),
        ("JE", 1.6195, "162.0"),
        ("GI", 1.315, "1.32"),
        # 3-decimal dinar markets (JOD / TND / LYD)
        ("JO", 0.885, "0.885"),
        ("TN", 2.235, "2.235"),
        ("LY", 0.147, "0.147"),
        # Integer extended ProMods currencies
        ("AM", 579.6, "580"),
        ("DZ", 29.4, "29"),
        ("IQ", 339.38, "339"),
        ("KZ", 347.75, "348"),
        ("LB", 121929.0, "121929"),
        ("MN", 3626.0, "3626"),
        ("SY", 153.16, "153"),
        ("UA", 59.4, "59"),
        ("UZ", 14595.0, "14595"),
        # 2-decimal EUR microstates & standard markets
        ("AD", 1.49, "1.49"),
        ("AX", 1.88, "1.88"),
        ("MC", 1.85, "1.85"),
        ("SM", 1.78, "1.78"),
        ("CY", 1.52, "1.52"),
        ("MT", 1.21, "1.21"),
    ],
)
def test_format_national_pump_price_extended_promods_territories(
    iso2: str, price: float, expected: str
) -> None:
    assert format_national_pump_price(iso2, price) == expected


def test_module_scoped_prefix_tables_prevent_mn_collision() -> None:
    assert PM_FUEL_MODULES == ("pm_fuel", "pm_me_fuel", "pm_tgs_fuel")
    assert len(PM_EU_PREFIX_TO_ISO2) == 58
    assert len(PM_ME_PREFIX_TO_ISO2) == 8
    assert len(PM_TGS_PREFIX_TO_ISO2) == 7

    # Critical collision guard: mn = Montenegro (ME) in pm_fuel vs Mongolia (MN) in pm_tgs_fuel
    assert PM_EU_PREFIX_TO_ISO2["mn"] == "ME"
    assert PM_TGS_PREFIX_TO_ISO2["mn"] == "MN"
    assert PM_EU_PREFIX_TO_ISO2["cni"] == "ES"
    # IN-01: proactive microstate prefixes for Liechtenstein & San Marino
    assert PM_EU_PREFIX_TO_ISO2["li"] == "LI"
    assert PM_EU_PREFIX_TO_ISO2["sm"] == "SM"


def test_format_pm_fuel_value_all_regimes_and_variants() -> None:
    # Decimal sub-10 (EUR/GBP/JOD/SAR/TMT)
    assert format_pm_fuel_value(1.641, None, "decimal") == "1.64"
    assert format_pm_fuel_value(1.641, "v0", "decimal") == "1.64"
    assert format_pm_fuel_value(1.641, "v1", "decimal") == "1.641"
    assert format_pm_fuel_value(1.641, "v2", "decimal") == "1.64<sup>1</sup>"
    assert format_pm_fuel_value(1.641, "v3", "decimal") == "164.1"
    assert format_pm_fuel_value(0.994, "v3", "decimal") == "099.4"
    assert format_pm_fuel_value(1.641, "v4", "decimal") == "164.<sup>1</sup>"
    assert format_pm_fuel_value(0.994, "v4", "decimal") == "099.<sup>4</sup>"

    # Mid-range 10-99 (CZK/NOK/SEK/EGP/CNY/MAD)
    assert format_pm_fuel_value(40.28, None, "midrange") == "40.28"
    assert format_pm_fuel_value(40.28, "v0", "midrange") == "40.28"
    assert format_pm_fuel_value(40.28, "v1", "midrange") == "40.3"
    assert format_pm_fuel_value(40.28, "v2", "midrange") == "40.<sup>3</sup>"

    # High-unit integer (HUF/KZT/IQD/LBP/SYP/UZS/MNT)
    assert format_pm_fuel_value(153.16, None, "integer") == "153"
    assert format_pm_fuel_value(153.16, "v0", "integer") == "153"
    assert format_pm_fuel_value(587.9, "v1", "integer") == "587.9"
    assert format_pm_fuel_value(587.9, "v2", "integer") == "587.<sup>9</sup>"
    assert format_pm_fuel_value(3626.0, None, "integer") == "3626"


def test_compile_promods_fuel_module_mn_split_cni_derived_grades_and_unknown_verbatim() -> None:
    snapshot = load_or_build_snapshot("summer")

    # Build synthetic pm_fuel (EU) with Montenegro mn, Canary cni, all _v0.._v4, 5 derived grades,
    # and unrecognized/future keys.
    es_diesel = snapshot.countries["ES"].fuel.local_prices["diesel"]
    me_diesel = snapshot.countries["ME"].fuel.local_prices["diesel"]
    de_p95 = snapshot.countries["DE"].fuel.local_prices["petrol_95"]
    lt_diesel = snapshot.countries["LT"].fuel.local_prices["diesel"]
    hu_diesel = snapshot.countries["HU"].fuel.local_prices["diesel"]
    se_p95 = snapshot.countries["SE"].fuel.local_prices["petrol_95"]
    dk_p95 = snapshot.countries["DK"].fuel.local_prices["petrol_95"]

    eu_raw = _make_loc_sii(
        ".pm_fuel",
        [
            ("fp_mn_diesel", "0.01"),
            ("fp_cni_diesel", "0.01"),
            ("fp_de_diesel_v0", "0.01"),
            ("fp_de_diesel_v1", "0.01"),
            ("fp_de_diesel_v2", "0.01"),
            ("fp_de_diesel_v3", "0.01"),
            ("fp_de_diesel_v4", "0.01"),
            ("fp_de_natural95_plus", "0.01"),
            ("fp_lt_diesel_colour", "0.01"),
            ("fp_hu_adblue", "0.01"),
            ("fp_se_biogas", "0.01"),
            ("fp_dk_electric", "0.01"),
            ("fp_gl_diesel", "0.01"),
            ("fp_cz_diesel_v2", "0.01"),
            ("fp_zz_future", "9.99"),
            ("custom_station_header", "WELCOME"),
        ],
    )
    eu_res = compile_promods_fuel_module("pm_fuel", eu_raw, snapshot, source_path="en_gb")
    assert eu_res.unit_name == ".pm_fuel"
    assert eu_res.updated_keys == 14
    assert eu_res.preserved_keys == 2
    assert eu_res.preserved_key_names == ["custom_station_header", "fp_zz_future"]

    # Montenegro (ME, EUR) formatted as decimal, NOT Mongolia MNT!
    assert eu_res.entries["fp_mn_diesel"] == format_pm_fuel_value(me_diesel, None, "decimal")
    assert float(eu_res.entries["fp_mn_diesel"]) < 10.0

    # Canary Islands cni uses 0.92 multiplier over ES
    assert eu_res.entries["fp_cni_diesel"] == format_pm_fuel_value(
        es_diesel * 0.92, None, "decimal"
    )
    # 5 derived grades
    assert eu_res.entries["fp_de_natural95_plus"] == format_pm_fuel_value(
        de_p95 * 1.04, None, "decimal"
    )
    assert eu_res.entries["fp_lt_diesel_colour"] == format_pm_fuel_value(
        lt_diesel * 0.85, None, "decimal"
    )
    assert eu_res.entries["fp_hu_adblue"] == format_pm_fuel_value(hu_diesel * 0.65, None, "integer")
    assert eu_res.entries["fp_se_biogas"] == format_pm_fuel_value(se_p95 * 1.80, None, "midrange")
    assert eu_res.entries["fp_dk_electric"] == format_pm_fuel_value(dk_p95 * 0.30, None, "midrange")
    # Unknown / non-price keys preserved verbatim
    assert eu_res.entries["fp_zz_future"] == "9.99"
    assert eu_res.entries["custom_station_header"] == "WELCOME"

    # Keys emitted sorted ascending & SII hygiene + <=12 char unit segments valid
    parsed_eu = parse_localization_db(eu_res.rendered_bytes)
    keys_emitted = [e.key for e in parsed_eu]
    assert keys_emitted == sorted(keys_emitted)
    assert validate_sii_hygiene(eu_res.rendered_bytes, require_siinunit=True) == []
    assert validate_unit_name_segments(eu_res.unit_name) == []

    # Now test pm_tgs_fuel where mn = Mongolia (MN, MNT integer "3626")!
    mn_diesel = snapshot.countries["MN"].fuel.local_prices["diesel"]
    tgs_raw = _make_loc_sii(
        ".pm_tgs_fuel",
        [
            ("fp_mn_diesel", "100"),
            ("fp_kz_diesel", "100"),
            ("fp_uz_diesel_v1", "100"),
            ("fp_tm_diesel_v3", "001.0"),
        ],
    )
    tgs_res = compile_promods_fuel_module("pm_tgs_fuel", tgs_raw, snapshot, source_path="en_gb")
    assert tgs_res.entries["fp_mn_diesel"] == format_pm_fuel_value(mn_diesel, None, "integer")
    assert tgs_res.entries["fp_mn_diesel"] == "3626"
    assert validate_sii_hygiene(tgs_res.rendered_bytes, require_siinunit=True) == []
    assert validate_unit_name_segments(tgs_res.unit_name) == []

    # Test pm_me_fuel including post-2026 redenominated SYP ("153") and JOD/SAR/EGP/IQD/LBP
    me_raw = _make_loc_sii(
        ".pm_me_fuel",
        [
            ("fp_syr_diesel", "150"),
            ("fp_jor_diesel_v1", "0.885"),
            ("fp_ksa_diesel_v4", "075.<sup>0</sup>"),
            ("fp_eg_diesel_v2", "18.<sup>0</sup>"),
            ("fp_irq_diesel", "300"),
            ("fp_lbn_diesel", "90000"),
        ],
    )
    me_res = compile_promods_fuel_module("pm_me_fuel", me_raw, snapshot, source_path="en_gb")
    assert me_res.entries["fp_syr_diesel"] == "153"
    assert "<sup>" in me_res.entries["fp_ksa_diesel_v4"]
    assert "<sup>" in me_res.entries["fp_eg_diesel_v2"]
    assert validate_sii_hygiene(me_res.rendered_bytes, require_siinunit=True) == []
    assert validate_unit_name_segments(me_res.unit_name) == []


def test_compile_promods_fuel_locales_emits_exact_43_active_locales_excluding_fr_qc(
    tmp_path: pathlib.Path,
) -> None:
    snapshot = load_or_build_snapshot("summer")
    locales = _load_locales()

    # Create synthetic assets ZIP containing en_gb AND dead fr_qc
    assets_zip = tmp_path / "promods-eu-assets-v285.scs"
    pm_fuel_bytes = _make_loc_sii(".pm_fuel", [("fp_de_diesel", "1.00"), ("fp_mn_diesel", "1.00")])
    with zipfile.ZipFile(assets_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("locale/en_gb/local_module.pm_fuel.sii", pm_fuel_bytes)
        zf.writestr("locale/fr_qc/local_module.pm_fuel.sii", pm_fuel_bytes)

    archive = open_archive(assets_zip)
    try:
        stack = VfsStack([VfsLayer(name="promods_eu_assets", priority=10, archive=archive)])
        compiled = compile_promods_fuel_locales(stack, locales, snapshot)
    finally:
        archive.close()

    assert list(compiled.modules.keys()) == ["pm_fuel"]
    assert len(compiled.locale_files) == 43
    assert "locale/fr_ca/local_module.pm_fuel.sii" in compiled.locale_files
    assert "locale/fr_qc/local_module.pm_fuel.sii" not in compiled.locale_files
    # Every emitted file is byte-identical across all 43 locales and passes hygiene
    unique_payloads = set(compiled.locale_files.values())
    assert len(unique_payloads) == 1
    payload = next(iter(unique_payloads))
    assert validate_sii_hygiene(payload, require_siinunit=True) == []


def test_md01_in01_3nk_cp1252_backslashes_empty_values_and_li_sm_prefixes(
    tmp_path: pathlib.Path,
) -> None:
    """MD-01 + IN-01 regressions: 3nK guard, cp1252, verbatim backslash, empty vals, li/sm."""
    snapshot = load_or_build_snapshot("summer")
    locales = _load_locales()

    # 1. Direct 3nK bytes rejected by compile_promods_fuel_module()
    with pytest.raises(ValueError, match="3nK"):
        compile_promods_fuel_module(
            "pm_fuel",
            b"3nK\x01" + b"\x00" * 32,
            snapshot,
            source_path="locale/en_gb/local_module.pm_fuel.sii",
        )

    # 2. Direct empty localization_db rejected
    with pytest.raises(ValueError, match="zero entries"):
        compile_promods_fuel_module(
            "pm_fuel",
            b"SiiNunit\n{\nlocalization_db : .pm_fuel\n{\n}\n}\n",
            snapshot,
            source_path="locale/en_gb/local_module.pm_fuel.sii",
        )

    # 3. 3nK in en_gb skipped in VfsStack so fallback locale (de_de) or clean skip works
    obf_zip = tmp_path / "obf_assets.scs"
    with zipfile.ZipFile(obf_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("locale/en_gb/local_module.pm_fuel.sii", b"3nK\x01" + b"\x00" * 32)
    with open_archive(obf_zip) as arch:
        stack = VfsStack([VfsLayer(name="obf", priority=10, archive=arch)])
        compiled_empty = compile_promods_fuel_locales(stack, locales, snapshot)
    assert compiled_empty.modules == {}
    assert compiled_empty.locale_files == {}

    # 4. cp1252 comment byte (0xe9), verbatim backslash string, empty placeholder, and li/sm keys
    cp1252_and_bs = (
        b"SiiNunit\n{\n# Caf\xe9 legacy cp1252 comment\n"
        b"localization_db : .pm_fuel\n{\n"
        b'\tkey[]: "fp_li_diesel"\n\tval[]: "1.00"\n'
        b'\tkey[]: "fp_sm_diesel"\n\tval[]: "1.00"\n'
        b'\tkey[]: "pm_path_note"\n\tval[]: "A\\\\B"\n'
        b'\tkey[]: "pm_empty_placeholder"\n\tval[]: ""\n'
        b"}\n}\n"
    )
    res = compile_promods_fuel_module("pm_fuel", cp1252_and_bs, snapshot, source_path="en_gb")
    assert res.updated_keys == 2
    assert res.preserved_keys == 1
    assert res.entries["pm_path_note"] == r"A\B"
    assert "pm_empty_placeholder" not in res.entries
    assert float(res.entries["fp_li_diesel"]) > 0.0
    assert float(res.entries["fp_sm_diesel"]) > 0.0
    assert validate_sii_hygiene(res.rendered_bytes, require_siinunit=True) == []
    roundtripped = {e.key: e.val for e in parse_localization_db(res.rendered_bytes)}
    assert roundtripped["pm_path_note"] == r"A\B"
    assert "pm_empty_placeholder" not in roundtripped
