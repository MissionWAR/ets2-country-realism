"""Deterministic 3-tier country alias resolution with SemEuropa collision shield (D-13)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ets2v2.registry.loader import load_country_aliases
from ets2v2.registry.models import CountryAliasEntry, CountryAliasRegistry
from ets2v2.registry.snapshot import RealismSnapshot, RealismSnapshotCountry
from ets2v2.sii.country import CountryDataModel

MatchTier = Literal["alias", "iso3", "iso2", "slug", "unmatched"]


class CountryResolution(BaseModel):
    """Structured outcome of resolving a discovered map country against a v1 snapshot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    country: RealismSnapshotCountry | None
    match_tier: MatchTier
    resolved_iso2: str | None = None
    iana_timezone_override: str | None = None
    unmatched_reason: str | None = None


def merge_alias_registries(
    bundled: CountryAliasRegistry,
    user_override: CountryAliasRegistry | None = None,
) -> CountryAliasRegistry:
    """Merge optional user ``--aliases`` overrides over bundled ``country_aliases.json``."""
    if user_override is None:
        return bundled

    merged: dict[str, CountryAliasEntry] = dict(bundled.aliases)
    for slug, entry in user_override.aliases.items():
        merged[slug.lower()] = entry
    sorted_merged = {slug: merged[slug] for slug in sorted(merged)}
    return CountryAliasRegistry(schema_version=1, aliases=sorted_merged)


class CountryResolver:
    """Pre-indexed O(1) 3-tier country resolver honoring D-13 and T-04-12 collision shields."""

    def __init__(
        self,
        snapshot: RealismSnapshot,
        aliases: CountryAliasRegistry | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._aliases: dict[str, CountryAliasEntry] = (
            {slug.lower(): entry for slug, entry in aliases.aliases.items()}
            if aliases is not None
            else {}
        )
        self._by_iso2: dict[str, RealismSnapshotCountry] = {
            iso2.upper(): country for iso2, country in snapshot.countries.items()
        }
        self._by_iso3: dict[str, RealismSnapshotCountry] = {
            country.iso3.lower(): country for country in snapshot.countries.values()
        }
        self._by_slug: dict[str, RealismSnapshotCountry] = {
            country.ets2_slug.lower(): country for country in snapshot.countries.values()
        }

    @classmethod
    def from_paths(
        cls,
        snapshot: RealismSnapshot,
        *,
        bundled_aliases_path: Path = Path("data/mappings/country_aliases.json"),
        user_aliases_path: Path | None = None,
    ) -> CountryResolver:
        """Build a ``CountryResolver`` loading bundled aliases and optional ``--aliases`` JSON."""
        bundled = load_country_aliases(bundled_aliases_path)
        user_override = (
            load_country_aliases(user_aliases_path) if user_aliases_path is not None else None
        )
        return cls(snapshot, merge_alias_registries(bundled, user_override))

    def resolve(self, slug: str, country_data: CountryDataModel) -> CountryResolution:
        """Resolve ``(slug, country_data)`` in strict Tier 1 -> Tier 2 -> Tier 3 order (D-13)."""
        norm_slug = slug.strip().lower()

        # Tier 1: Exact slug lookup in bundled + user aliases registry.
        # CRITICAL COLLISION GUARD (T-04-12): If slug is known in aliases, NEVER fall through
        # to Tier 2 country_code/iso_country_code when target_iso2 is absent from the snapshot
        # (prevents SemEuropa Brazilian states AL/AM/BA/ES/MA/MT/RS/RO/SE matching Europe!).
        alias_entry = self._aliases.get(norm_slug)
        if alias_entry is not None:
            target_iso2 = alias_entry.iso2.upper()
            matched_alias = self._by_iso2.get(target_iso2)
            if matched_alias is not None:
                return CountryResolution(
                    country=matched_alias,
                    match_tier="alias",
                    resolved_iso2=target_iso2,
                    iana_timezone_override=alias_entry.iana_timezone_override,
                    unmatched_reason=None,
                )
            return CountryResolution(
                country=None,
                match_tier="unmatched",
                resolved_iso2=target_iso2,
                iana_timezone_override=alias_entry.iana_timezone_override,
                unmatched_reason="alias_target_not_in_snapshot",
            )

        # Tier 2: Exact iso_country_code (ISO-3) or country_code (ISO-2)
        iso3 = country_data.iso_country_code.strip().lower()
        if iso3:
            matched_iso3 = self._by_iso3.get(iso3)
            if matched_iso3 is not None:
                return CountryResolution(
                    country=matched_iso3,
                    match_tier="iso3",
                    resolved_iso2=matched_iso3.iso2,
                )

        cc = country_data.country_code.strip().upper()
        if cc:
            matched_iso2 = self._by_iso2.get(cc)
            if matched_iso2 is not None:
                return CountryResolution(
                    country=matched_iso2,
                    match_tier="iso2",
                    resolved_iso2=matched_iso2.iso2,
                )

        # Tier 3: Canonical ets2_slug match
        matched_slug = self._by_slug.get(norm_slug)
        if matched_slug is not None:
            return CountryResolution(
                country=matched_slug,
                match_tier="slug",
                resolved_iso2=matched_slug.iso2,
            )

        return CountryResolution(
            country=None,
            match_tier="unmatched",
            resolved_iso2=None,
            iana_timezone_override=None,
            unmatched_reason="no_snapshot_match",
        )


__all__ = [
    "CountryResolution",
    "CountryResolver",
    "MatchTier",
    "merge_alias_registries",
]
