"""Unit tests for deterministic 3-tier country alias resolution & SemEuropa shield (D-13)."""

from __future__ import annotations

import pathlib

import pytest

from ets2v2.merge.aliases import (
    CountryResolution,
    CountryResolver,
    merge_alias_registries,
)
from ets2v2.registry.loader import load_country_aliases
from ets2v2.registry.models import CountryAliasEntry, CountryAliasRegistry
from ets2v2.registry.snapshot import RealismSnapshot, load_or_build_snapshot
from ets2v2.sii.country import CountryDataModel


@pytest.fixture(scope="module")
def phase4_snapshot() -> RealismSnapshot:
    return load_or_build_snapshot(
        "summer",
        laws_dir=pathlib.Path("data/laws"),
        mappings_path=pathlib.Path("data/mappings/ets2_countries.json"),
        baseline_dir=pathlib.Path("data/baselines/ets2_1.62_def"),
        prices_lock_path=pathlib.Path("state/prices.lock.json"),
    )


@pytest.fixture(scope="module")
def bundled_aliases() -> CountryAliasRegistry:
    return load_country_aliases(pathlib.Path("data/mappings/country_aliases.json"))


def _dummy_country(
    slug: str,
    *,
    country_code: str = "",
    iso_country_code: str = "",
) -> CountryDataModel:
    return CountryDataModel(
        unit_name=f"country.data.{slug}",
        country_id=1,
        name=slug,
        country_code=country_code,
        iso_country_code=iso_country_code,
    )


def test_tier1_promods_and_subnational_aliases_with_timezone_overrides(
    phase4_snapshot: RealismSnapshot,
    bundled_aliases: CountryAliasRegistry,
) -> None:
    resolver = CountryResolver(phase4_snapshot, bundled_aliases)

    cases: list[tuple[str, str, str | None]] = [
        ("nireland", "GB", None),
        ("can_islands", "ES", "Atlantic/Canary"),
        ("saudia", "SA", None),
        ("westbank", "PS", None),
        ("liecht", "LI", None),
        ("iom", "IM", None),
        ("sanmarino", "SM", None),
        ("northern_cyprus", "CY", None),
        ("transnistria", "MD", None),
        ("libya1", "LY", None),
        ("guianafr", "FR", "America/Cayenne"),
    ]

    for slug, expected_iso2, expected_tz in cases:
        res: CountryResolution = resolver.resolve(slug, _dummy_country(slug))
        assert res.match_tier == "alias", f"Failed tier for {slug}"
        assert res.resolved_iso2 == expected_iso2, f"Failed iso2 for {slug}"
        assert res.country is not None
        assert res.country.iso2 == expected_iso2
        assert res.iana_timezone_override == expected_tz
        assert res.unmatched_reason is None


def test_semeuropa_brazilian_state_iso2_collision_shield(
    phase4_snapshot: RealismSnapshot,
    bundled_aliases: CountryAliasRegistry,
) -> None:
    """All colliding SemEuropa Brazilian states MUST stop at Tier 1 (never match EU/MA ISO-2!)."""
    assert len(phase4_snapshot.countries) == 76
    assert "BR" not in phase4_snapshot.countries

    resolver = CountryResolver(phase4_snapshot, bundled_aliases)
    colliding_states: list[tuple[str, str]] = [
        ("alagoas", "AL"),  # Albania
        ("amazonas", "AM"),  # Armenia
        ("bahia", "BA"),  # Bosnia & Herzegovina
        ("espsanto", "ES"),  # Spain
        ("maranhao", "MA"),  # Morocco
        ("matogrosso", "MT"),  # Malta
        ("rgsul", "RS"),  # Serbia
        ("rondonia", "RO"),  # Romania
        ("sergipe", "SE"),  # Sweden
    ]

    for state_slug, colliding_cc in colliding_states:
        assert colliding_cc in phase4_snapshot.countries
        res = resolver.resolve(
            state_slug,
            _dummy_country(state_slug, country_code=colliding_cc, iso_country_code=""),
        )
        assert res.country is None, f"{state_slug} falsely matched {res.country}"
        assert res.match_tier == "unmatched"
        assert res.resolved_iso2 == "BR"
        assert res.unmatched_reason == "alias_target_not_in_snapshot"


def test_tier1_overrides_unexpected_iso_country_code(
    phase4_snapshot: RealismSnapshot,
    bundled_aliases: CountryAliasRegistry,
) -> None:
    resolver = CountryResolver(phase4_snapshot, bundled_aliases)
    res = resolver.resolve(
        "nireland",
        _dummy_country("nireland", country_code="NI", iso_country_code="nir"),
    )
    assert res.match_tier == "alias"
    assert res.resolved_iso2 == "GB"
    assert res.country is not None
    assert res.country.iso2 == "GB"


def test_tier2_iso3_and_iso2_resolution_for_non_standard_slugs(
    phase4_snapshot: RealismSnapshot,
    bundled_aliases: CountryAliasRegistry,
) -> None:
    resolver = CountryResolver(phase4_snapshot, bundled_aliases)

    res_iso3 = resolver.resolve(
        "custom_germany_map",
        _dummy_country("custom_germany_map", country_code="D", iso_country_code="DEU"),
    )
    assert res_iso3.match_tier == "iso3"
    assert res_iso3.resolved_iso2 == "DE"
    assert res_iso3.country is not None
    assert res_iso3.country.iso2 == "DE"

    res_iso2 = resolver.resolve(
        "custom_france_slug",
        _dummy_country("custom_france_slug", country_code="fr", iso_country_code=""),
    )
    assert res_iso2.match_tier == "iso2"
    assert res_iso2.resolved_iso2 == "FR"
    assert res_iso2.country is not None
    assert res_iso2.country.iso2 == "FR"


def test_tier3_canonical_ets2_slug_fallback_when_codes_blank(
    phase4_snapshot: RealismSnapshot,
    bundled_aliases: CountryAliasRegistry,
) -> None:
    resolver = CountryResolver(phase4_snapshot, bundled_aliases)
    res = resolver.resolve("uk", _dummy_country("uk", country_code="", iso_country_code=""))
    assert res.match_tier == "slug"
    assert res.resolved_iso2 == "GB"
    assert res.country is not None
    assert res.country.iso2 == "GB"


def test_user_aliases_override_merges_over_bundled(
    phase4_snapshot: RealismSnapshot,
    bundled_aliases: CountryAliasRegistry,
) -> None:
    user_override = CountryAliasRegistry(
        aliases={
            # Override an existing bundled entry with custom timezone
            "can_islands": CountryAliasEntry(
                iso2="ES",
                iana_timezone_override="Europe/Madrid",
                note="User custom override",
            ),
            # Add brand new custom map slug
            "custom_azores": CountryAliasEntry(
                iso2="PT",
                iana_timezone_override="Atlantic/Azores",
                note="Custom Azores map",
            ),
        }
    )

    merged = merge_alias_registries(bundled_aliases, user_override)
    assert "nireland" in merged.aliases  # Non-overridden bundled entry preserved
    assert merged.aliases["can_islands"].iana_timezone_override == "Europe/Madrid"
    assert merged.aliases["custom_azores"].iso2 == "PT"

    resolver = CountryResolver(phase4_snapshot, merged)
    res_can = resolver.resolve("can_islands", _dummy_country("can_islands"))
    assert res_can.match_tier == "alias"
    assert res_can.iana_timezone_override == "Europe/Madrid"

    res_azores = resolver.resolve("custom_azores", _dummy_country("custom_azores"))
    assert res_azores.match_tier == "alias"
    assert res_azores.resolved_iso2 == "PT"
    assert res_azores.iana_timezone_override == "Atlantic/Azores"
    assert res_azores.country is not None
    assert res_azores.country.iso2 == "PT"


def test_unknown_fictional_territory_is_skipped_untouched(
    phase4_snapshot: RealismSnapshot,
    bundled_aliases: CountryAliasRegistry,
) -> None:
    resolver = CountryResolver(phase4_snapshot, bundled_aliases)
    res = resolver.resolve(
        "atlantis",
        _dummy_country("atlantis", country_code="ZZ", iso_country_code="zzz"),
    )
    assert res.country is None
    assert res.match_tier == "unmatched"
    assert res.resolved_iso2 is None
    assert res.iana_timezone_override is None
    assert res.unmatched_reason == "no_snapshot_match"
