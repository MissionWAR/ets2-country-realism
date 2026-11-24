"""Contract and hygiene tests for CountryAliasRegistry (country_aliases.json)."""

from __future__ import annotations

import json
import pathlib
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from ets2v2.registry import (
    CountryAliasEntry,
    CountryAliasRegistry,
    load_country_aliases,
    serialize_registry_json_bytes,
    validate_country_aliases,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ALIASES_PATH = REPO_ROOT / "data" / "mappings" / "country_aliases.json"

BRAZILIAN_STATE_SLUGS: frozenset[str] = frozenset(
    {
        "acre",
        "alagoas",
        "amapa",
        "amazonas",
        "bahia",
        "ceara",
        "dfederal",
        "espsanto",
        "goias",
        "maranhao",
        "matogrosso",
        "matogrossos",
        "minasgerais",
        "para",
        "paraiba",
        "parana",
        "pernambuco",
        "piaui",
        "rgnorte",
        "rgsul",
        "rjaneiro",
        "rondonia",
        "roraima",
        "scatarina",
        "sergipe",
        "spaulo",
        "tocantins",
    }
)

JAPAN_PREFECTURE_SLUGS: frozenset[str] = frozenset(
    {
        "aichi",
        "akita",
        "aomori",
        "chiba",
        "ehime",
        "fukui",
        "fukuoka",
        "fukushima",
        "gifu",
        "gunma",
        "hiroshima",
        "hokkaido",
        "hyogo",
        "ibaraki",
        "ishikawa",
        "iwate",
        "kagawa",
        "kagoshima",
        "kanagawa",
        "kochi",
        "kumamoto",
        "kyoto",
        "mie",
        "miyagi",
        "miyazaki",
        "nagano",
        "nagasaki",
        "nara",
        "niigata",
        "oita",
        "okayama",
        "okinawa",
        "osaka",
        "saga",
        "saitama",
        "shiga",
        "shimane",
        "shizuoka",
        "tochigi",
        "tokushima",
        "tokyo",
        "tottori",
        "toyama",
        "wakayama",
        "yamagata",
        "yamaguchi",
        "yamanashi",
    }
)


def test_country_alias_schema_rejects_invalid_slug_iso2_tz_and_extra_keys() -> None:
    entry = CountryAliasEntry(
        iso2="ES",
        iana_timezone_override="Atlantic/Canary",
        note="ProMods Canary Islands",
    )
    reg = CountryAliasRegistry(schema_version=1, aliases={"can_islands": entry})
    assert reg.schema_version == 1
    assert reg.aliases["can_islands"].iso2 == "ES"

    with pytest.raises(ValidationError):
        CountryAliasEntry(iso2="es")

    with pytest.raises(ValidationError):
        CountryAliasEntry(iso2="ESP")

    with pytest.raises(ValidationError):
        CountryAliasEntry(iso2="ES", iana_timezone_override="Not/A_Real_Zone")

    with pytest.raises(ValidationError):
        CountryAliasEntry.model_validate_json(json.dumps({"iso2": "ES", "extra_field": True}))

    with pytest.raises(ValidationError):
        CountryAliasRegistry(
            schema_version=1,
            aliases={"Bad-Slug!": CountryAliasEntry(iso2="ES")},
        )

    with pytest.raises(ValidationError):
        CountryAliasRegistry.model_validate_json(json.dumps({"schema_version": 2, "aliases": {}}))


def test_country_aliases_loader_and_validator_reject_bom_crlf_and_non_canonical(
    tmp_path: pathlib.Path,
) -> None:
    valid = CountryAliasRegistry(
        schema_version=1,
        aliases={
            "can_islands": CountryAliasEntry(
                iso2="ES",
                iana_timezone_override="Atlantic/Canary",
                note="Canary Islands",
            ),
        },
    )
    canonical = serialize_registry_json_bytes(valid)

    ok_path = tmp_path / "aliases.json"
    ok_path.write_bytes(canonical)
    assert load_country_aliases(ok_path) == valid
    assert validate_country_aliases(ok_path) == []

    bom_path = tmp_path / "aliases_bom.json"
    bom_path.write_bytes(b"\xef\xbb\xbf" + canonical)
    with pytest.raises(ValueError, match="BOM"):
        load_country_aliases(bom_path)
    assert any("BOM" in issue for issue in validate_country_aliases(bom_path))

    crlf_path = tmp_path / "aliases_crlf.json"
    crlf_path.write_bytes(canonical.replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="LF"):
        load_country_aliases(crlf_path)
    assert any("LF" in issue for issue in validate_country_aliases(crlf_path))

    unsorted_path = tmp_path / "aliases_unsorted.json"
    unsorted_path.write_text('{"aliases": {}, "schema_version": 1}\n', encoding="utf-8")
    assert any("canonical" in issue.lower() for issue in validate_country_aliases(unsorted_path))


def test_committed_country_aliases_canonical_and_covers_all_map_ecosystems() -> None:
    assert ALIASES_PATH.is_file()
    assert validate_country_aliases(ALIASES_PATH) == []

    registry = load_country_aliases(ALIASES_PATH)
    assert registry.schema_version == 1
    assert serialize_registry_json_bytes(registry) == ALIASES_PATH.read_bytes()

    aliases = registry.aliases

    # ProMods & European sub-national / microstate variants
    expected_promods = {
        "nireland": "GB",
        "n_ireland": "GB",
        "northern_ireland": "GB",
        "can_islands": "ES",
        "libya1": "LY",
        "saudia": "SA",
        "westbank": "PS",
        "palestine": "PS",
        "liecht": "LI",
        "liechtenstein": "LI",
        "iom": "IM",
        "isle_of_man": "IM",
        "sanmarino": "SM",
        "san_marino": "SM",
        "faroe": "FO",
        "aland": "AX",
        "svalbard": "SJ",
        "jersey": "JE",
        "guernsey": "GG",
        "northern_cyprus": "CY",
        "transnistria": "MD",
        "gibraltar": "GI",
        "greenland": "GL",
        "monaco": "MC",
        "andorra": "AD",
        "malta": "MT",
        "ireland": "IE",
        "cyprus": "CY",
    }
    for slug, iso2 in expected_promods.items():
        assert slug in aliases, f"Missing ProMods alias {slug!r}"
        assert aliases[slug].iso2 == iso2

    # GMC Beyond / UMCF / RIW
    for slug, iso2 in {
        "iraq1": "IQ",
        "saudia1": "SA",
        "sudan1": "SD",
        "rta_azerbjn": "AZ",
        "abudhabi": "AE",
        "limpopo": "ZA",
    }.items():
        assert aliases[slug].iso2 == iso2

    # SEA / Africa / South America non-Brazil
    for slug, iso2 in {
        "equador": "EC",
        "paraguai": "PY",
        "uruguai": "UY",
        "guiana": "GY",
        "guianafr": "FR",
        "papuang": "PG",
        "timorleste": "TL",
        "equatorial_g": "GQ",
    }.items():
        assert aliases[slug].iso2 == iso2

    # SemEuropa 27 Brazilian state collision shields -> BR
    assert len(BRAZILIAN_STATE_SLUGS) == 27
    for br_slug in BRAZILIAN_STATE_SLUGS:
        assert br_slug in aliases, f"Missing Brazilian state alias {br_slug!r}"
        assert aliases[br_slug].iso2 == "BR"

    # All 47 Project Japan prefectures -> JP
    assert len(JAPAN_PREFECTURE_SLUGS) == 47
    for jp_slug in JAPAN_PREFECTURE_SLUGS:
        assert jp_slug in aliases, f"Missing Project Japan prefecture alias {jp_slug!r}"
        assert aliases[jp_slug].iso2 == "JP"

    # Sub-national IANA timezone overrides (D-02 / D-13)
    expected_tz_overrides = {
        "can_islands": ("ES", "Atlantic/Canary"),
        "indo_b": ("ID", "Asia/Jakarta"),
        "indo_th": ("ID", "Asia/Makassar"),
        "indo_tm": ("ID", "Asia/Jayapura"),
        "guianafr": ("FR", "America/Cayenne"),
    }
    for slug, (iso2, tz_name) in expected_tz_overrides.items():
        assert aliases[slug].iso2 == iso2
        assert aliases[slug].iana_timezone_override == tz_name

    # Every iana_timezone_override must resolve cleanly in stdlib zoneinfo
    for slug, entry in aliases.items():
        if entry.iana_timezone_override is not None:
            tz = ZoneInfo(entry.iana_timezone_override)
            assert tz.key == entry.iana_timezone_override, f"Bad tz override for {slug!r}"
