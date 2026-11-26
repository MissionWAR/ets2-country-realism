"""Opt-in Overpass (`out tags 500;`) and Taginfo v4 maxspeed spot-check clients (GLB-04, D-13)."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Final, cast

import httpx

from ets2v2.audit.models import (
    OverpassSpotCheck,
    OverpassTagCount,
    TaginfoDistribution,
    TaginfoValueEntry,
)
from ets2v2.fetch.http import (
    HttpFetchError,
    fetch_bytes_with_retry,
    post_form_bytes_with_retry,
    redact_url_secrets,
)

MAX_OVERPASS_ISO2S: Final[int] = 10
DEFAULT_OVERPASS_URL: Final[str] = "https://overpass-api.de/api/interpreter"
OVERPASS_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"overpass-api.de"})
DEFAULT_OVERPASS_SLEEP_SECONDS: Final[float] = 1.5
DEFAULT_TAGINFO_URL: Final[str] = "https://taginfo.openstreetmap.org/api/4/key/values"
TAGINFO_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"taginfo.openstreetmap.org"})
DEFAULT_TAGINFO_KEYS: Final[tuple[str, ...]] = ("maxspeed", "maxspeed:hgv", "maxspeed:bus")

_ISO2_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2}$")
_TOP_N_MODAL: Final[int] = 3


def build_overpass_speed_query(iso2: str) -> str:
    """Build a strict tags-only (`out tags 500;`) Overpass QL query for one ISO-2 code."""
    if _ISO2_RE.fullmatch(iso2) is None:
        raise ValueError(f"Invalid ISO-2 country code for Overpass query: {iso2!r}")
    return (
        "[out:json][timeout:25];\n"
        f'area["ISO3166-1"="{iso2}"][admin_level=2]->.searchArea;\n'
        "(\n"
        '  way(area.searchArea)["highway"="motorway"]["maxspeed"];\n'
        '  way(area.searchArea)["highway"="trunk"]["maxspeed"];\n'
        ");\n"
        "out tags 500;\n"
    )


def _top_counts_by_highway(
    buckets: dict[str, Counter[str]],
    *,
    top_n: int = _TOP_N_MODAL,
) -> dict[str, list[OverpassTagCount]]:
    result: dict[str, list[OverpassTagCount]] = {}
    for highway in sorted(buckets):
        ranked = sorted(buckets[highway].items(), key=lambda pair: (-pair[1], pair[0]))[:top_n]
        if ranked:
            result[highway] = [OverpassTagCount(value=val, count=cnt) for val, cnt in ranked]
    return result


def fetch_overpass_speed_spot_checks(
    client: httpx.Client,
    iso2s: Sequence[str],
    *,
    url: str = DEFAULT_OVERPASS_URL,
    sleep_fn: Callable[[float], None] | None = None,
    sleep_seconds: float = DEFAULT_OVERPASS_SLEEP_SECONDS,
) -> list[OverpassSpotCheck]:
    """Run opt-in tags-only Overpass spot-checks with strict ISO-2 validation and <=10 cap."""
    if sleep_seconds < 0.0:
        raise ValueError(f"sleep_seconds must be >= 0.0, got {sleep_seconds!r}")

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_code in iso2s:
        code = raw_code.strip()
        if _ISO2_RE.fullmatch(code) is None:
            raise ValueError(f"Invalid ISO-2 country code for Overpass spot-check: {raw_code!r}")
        if code not in seen:
            seen.add(code)
            normalized.append(code)

    if len(normalized) > MAX_OVERPASS_ISO2S:
        raise ValueError(
            f"Overpass spot-checks accept at most {MAX_OVERPASS_ISO2S} ISO-2 codes per run "
            f"(received {len(normalized)})"
        )

    sleeper = sleep_fn if sleep_fn is not None else time.sleep
    results: list[OverpassSpotCheck] = []

    for idx, iso2 in enumerate(sorted(normalized)):
        if idx > 0 and sleep_seconds > 0.0:
            sleeper(sleep_seconds)
        query = build_overpass_speed_query(iso2)
        try:
            raw = post_form_bytes_with_retry(
                client,
                url,
                allowed_hosts=OVERPASS_ALLOWED_HOSTS,
                data={"data": query},
                sleep_fn=sleeper,
            )
            payload_obj: object = json.loads(raw.decode("utf-8"))
            if not isinstance(payload_obj, dict):
                raise ValueError("Overpass response root is not a JSON object")
            payload = cast(dict[str, object], payload_obj)
            elements_obj = payload.get("elements", [])
            if not isinstance(elements_obj, list):
                raise ValueError("Overpass response 'elements' field is not a list")

            car_buckets: dict[str, Counter[str]] = {}
            hgv_buckets: dict[str, Counter[str]] = {}
            bus_buckets: dict[str, Counter[str]] = {}
            ways_sampled = 0

            for elem in cast(list[object], elements_obj):
                if not isinstance(elem, dict):
                    continue
                elem_map = cast(dict[str, object], elem)
                tags_obj = elem_map.get("tags")
                if not isinstance(tags_obj, dict):
                    continue
                tags = cast(dict[str, object], tags_obj)
                highway_obj = tags.get("highway")
                if not isinstance(highway_obj, str) or not highway_obj.strip():
                    continue
                highway = highway_obj.strip()
                ways_sampled += 1

                maxspeed_obj = tags.get("maxspeed")
                if isinstance(maxspeed_obj, str) and maxspeed_obj.strip():
                    car_buckets.setdefault(highway, Counter())[maxspeed_obj.strip()] += 1

                hgv_obj = tags.get("maxspeed:hgv")
                if isinstance(hgv_obj, str) and hgv_obj.strip():
                    hgv_buckets.setdefault(highway, Counter())[hgv_obj.strip()] += 1

                bus_obj = tags.get("maxspeed:bus")
                if isinstance(bus_obj, str) and bus_obj.strip():
                    bus_buckets.setdefault(highway, Counter())[bus_obj.strip()] += 1

            results.append(
                OverpassSpotCheck(
                    iso2=iso2,
                    ok=True,
                    ways_sampled=ways_sampled,
                    top_maxspeed_by_highway=_top_counts_by_highway(car_buckets),
                    top_maxspeed_hgv_by_highway=_top_counts_by_highway(hgv_buckets),
                    top_maxspeed_bus_by_highway=_top_counts_by_highway(bus_buckets),
                )
            )
        except (HttpFetchError, httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            results.append(
                OverpassSpotCheck(
                    iso2=iso2,
                    ok=False,
                    error=redact_url_secrets(str(exc)),
                )
            )

    return results


def fetch_taginfo_maxspeed_distributions(
    client: httpx.Client,
    *,
    keys: Sequence[str] = DEFAULT_TAGINFO_KEYS,
    url: str = DEFAULT_TAGINFO_URL,
    rp: int = 25,
    sleep_fn: Callable[[float], None] | None = None,
    sleep_seconds: float = 0.5,
) -> list[TaginfoDistribution]:
    """Fetch opt-in Taginfo API v4 way value distributions for maxspeed tag keys."""
    if rp < 1 or rp > 100:
        raise ValueError(f"Taginfo rp must be in 1..100, got {rp}")

    sleeper = sleep_fn if sleep_fn is not None else time.sleep
    results: list[TaginfoDistribution] = []

    for idx, key in enumerate(keys):
        if idx > 0 and sleep_seconds > 0.0:
            sleeper(sleep_seconds)
        try:
            raw = fetch_bytes_with_retry(
                client,
                url,
                allowed_hosts=TAGINFO_ALLOWED_HOSTS,
                params={
                    "key": key,
                    "filter": "ways",
                    "sortname": "count",
                    "sortorder": "desc",
                    "rp": str(rp),
                    "page": "1",
                },
                sleep_fn=sleeper,
            )
            payload_obj: object = json.loads(raw.decode("utf-8"))
            if not isinstance(payload_obj, dict):
                raise ValueError("Taginfo response root is not a JSON object")
            payload = cast(dict[str, object], payload_obj)
            rows_obj = payload.get("data", [])
            if not isinstance(rows_obj, list):
                raise ValueError("Taginfo response 'data' field is not a list")

            entries: list[TaginfoValueEntry] = []
            for row in cast(list[object], rows_obj):
                if not isinstance(row, dict):
                    continue
                row_map = cast(dict[str, object], row)
                val_obj = row_map.get("value")
                cnt_obj = row_map.get("count")
                frac_obj = row_map.get("fraction", 0.0)
                if not isinstance(val_obj, str) or not val_obj.strip():
                    continue
                if isinstance(cnt_obj, bool) or not isinstance(cnt_obj, int) or cnt_obj < 0:
                    continue
                if isinstance(frac_obj, bool) or not isinstance(frac_obj, (int, float)):
                    continue
                entries.append(
                    TaginfoValueEntry(
                        value=val_obj.strip(),
                        count=cnt_obj,
                        fraction=float(frac_obj),
                    )
                )

            results.append(TaginfoDistribution(key=key, ok=True, values=entries))
        except (HttpFetchError, httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            results.append(
                TaginfoDistribution(
                    key=key,
                    ok=False,
                    error=redact_url_secrets(str(exc)),
                )
            )

    return results
