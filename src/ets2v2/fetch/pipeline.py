"""Full online European FX & Tier 1 fuel fetch pipeline orchestrator (DAT-01..DAT-03)."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

import httpx

from ets2v2.baseline.models import CountriesBaseline
from ets2v2.fetch.ec_bulletin import (
    fetch_ec_weekly_oil_bulletin,
    fetch_fionnhughes_fallback,
    fetch_fuel_prices_eu,
)
from ets2v2.fetch.fx import fetch_all_fx_quotes, run_fx_only_fetch
from ets2v2.fetch.http import DEFAULT_TIMEOUT_SECONDS, create_http_client, redact_url_secrets
from ets2v2.fetch.models import (
    FetchRunReport,
    ProviderFetchStatus,
    RawCountryFuelQuote,
    RawFuelFeedResult,
)
from ets2v2.fetch.national import fetch_all_national_feeds
from ets2v2.normalize.currencies import EUROPEAN_TERRITORY_ISO2S, TERRITORY_CURRENCIES
from ets2v2.normalize.fuel import (
    MAX_EUR_PER_LITER,
    MAX_WOW_JUMP_RATIO,
    MIN_EUR_PER_LITER,
    compute_secondary_grade_prices,
    normalize_country_fuel_prices,
    normalize_iso2_alias,
    round_local_price,
)
from ets2v2.normalize.fx import FxProviderQuote, cross_validate_fx_rates, round_eur_per_liter
from ets2v2.normalize.lockfile import (
    BASELINE_SEEDED_LICENSE,
    BASELINE_SEEDED_SOURCE,
    evaluate_lockfile_staleness,
    load_prices_lockfile,
    seed_initial_lockfile,
    write_prices_lockfile,
)
from ets2v2.normalize.models import (
    CountryFuelLockEntry,
    FuelGrade,
    FxRateLockEntry,
    LockAlert,
    PricesLockfile,
)

_NON_EU_VANILLA_ISO2S: Final[frozenset[str]] = frozenset(
    {"AL", "BA", "CH", "IS", "ME", "MK", "RS", "RU", "TR", "XK"}
)
_FEED_PRECEDENCE: Final[dict[str, int]] = {
    "fuel_prices_eu": 10,
    "fionnhughes_ec_wob": 20,
    "ec_weekly_oil_bulletin": 30,
    "uk_desnz": 40,
    "no_ssb_09654": 40,
    "fr_economie_ods": 40,
    "de_tankerkoenig": 40,
    "es_miteco": 40,
    "it_mimit": 40,
    "nl_cbs_80416ned": 40,
}
_SEED_PETROL_TO_DIESEL_RATIO: Final[float] = 1.03


@dataclass(frozen=True)
class _FuelCandidate:
    source: str
    license_name: str
    data_date: str
    feed_tier: str
    local_prices: dict[FuelGrade, float]


def _validate_supplemental_grade(
    iso2: str,
    grade: FuelGrade,
    local_val: float,
    *,
    source: str,
    fx_entry: FxRateLockEntry,
    previous_entry: CountryFuelLockEntry | None,
    normalized_allow: frozenset[str],
) -> tuple[float | None, LockAlert | None]:
    if not math.isfinite(local_val) or local_val <= 0.0:
        return None, LockAlert(
            severity="warning",
            code="supplemental_grade_rejected",
            scope=iso2,
            detail=(
                f"Dropped non-finite/non-positive supplemental {grade} price {local_val!r} "
                f"for {iso2} from {source}."
            ),
        )
    eur_equiv = local_val / fx_entry.rate_per_eur
    if not (MIN_EUR_PER_LITER <= eur_equiv <= MAX_EUR_PER_LITER):
        return None, LockAlert(
            severity="warning",
            code="supplemental_grade_rejected",
            scope=iso2,
            detail=(
                f"Dropped out-of-bounds supplemental {grade} price for {iso2} from {source}: "
                f"{local_val} {fx_entry.currency}/L ({eur_equiv:.4f} EUR/L)."
            ),
        )
    rounded_val = round_local_price(local_val)
    if (
        previous_entry is not None
        and previous_entry.source != BASELINE_SEEDED_SOURCE
        and iso2 not in normalized_allow
    ):
        prev_local = previous_entry.local_prices.get(grade)
        if prev_local is not None and prev_local > 0.0:
            prev_d = Decimal(str(prev_local))
            new_d = Decimal(str(rounded_val))
            ratio = abs(new_d - prev_d) / prev_d
            if ratio > Decimal(str(MAX_WOW_JUMP_RATIO)):
                return None, LockAlert(
                    severity="warning",
                    code="supplemental_grade_rejected",
                    scope=iso2,
                    detail=(
                        f"Dropped >25% WoW supplemental {grade} jump for {iso2} from {source}: "
                        f"{prev_local} -> {rounded_val} {fx_entry.currency} "
                        f"({float(ratio) * 100.0:.1f}%)."
                    ),
                )
    return rounded_val, None


def _sort_alerts(alerts: list[LockAlert]) -> list[LockAlert]:
    return sorted(alerts, key=lambda a: (a.severity, a.code, a.scope, a.detail))


def _load_baseline_countries(baseline_dir: Path) -> CountriesBaseline:
    countries_path = baseline_dir / "countries.json"
    if not countries_path.is_file():
        raise FileNotFoundError(f"Baseline countries.json does not exist: {countries_path}")
    return CountriesBaseline.model_validate_json(countries_path.read_text("utf-8"))


def _quote_to_local_prices(
    quote: RawCountryFuelQuote,
    *,
    fx_entry: FxRateLockEntry,
) -> dict[FuelGrade, float]:
    if quote.unit_basis == "eur_per_liter":
        return {
            grade: eur_price * fx_entry.rate_per_eur
            for grade, eur_price in quote.prices_by_grade.items()
        }
    if quote.currency != fx_entry.currency:
        raise ValueError(
            f"Quote currency {quote.currency!r} does not match territory currency "
            f"{fx_entry.currency!r} for {quote.iso2}"
        )
    return dict(quote.prices_by_grade)


def _build_baseline_entry(
    iso2: str,
    *,
    diesel_eur: float,
    fx_entry: FxRateLockEntry,
    data_date: str,
    fetched_at: str,
) -> CountryFuelLockEntry:
    rate = fx_entry.rate_per_eur
    diesel_eur_3dp = round_eur_per_liter(diesel_eur)
    petrol_95_eur_3dp = round_eur_per_liter(diesel_eur_3dp * _SEED_PETROL_TO_DIESEL_RATIO)
    anchors: dict[FuelGrade, float] = {
        "diesel": round_local_price(diesel_eur_3dp * rate),
        "petrol_95": round_local_price(petrol_95_eur_3dp * rate),
    }
    full_local, derived = compute_secondary_grade_prices(anchors)
    return CountryFuelLockEntry(
        iso2=iso2,
        currency=fx_entry.currency,
        eur_per_liter=diesel_eur_3dp,
        local_prices=full_local,
        derived_grades=derived,
        source=BASELINE_SEEDED_SOURCE,
        license=BASELINE_SEEDED_LICENSE,
        data_date=data_date,
        fetched_at=fetched_at,
        fallback_used=True,
    )


def run_price_fetch(
    *,
    lock_path: Path = Path("state/prices.lock.json"),
    baseline_dir: Path = Path("data/baselines/ets2_1.62_def"),
    allow_jump_iso2: frozenset[str] = frozenset(),
    fx_only: bool = False,
    seed_offline: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    write_lock: bool = True,
    transport: httpx.BaseTransport | None = None,
    tankerkoenig_api_key: str | None = None,
    now_utc: datetime | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> FetchRunReport:
    """Orchestrate online FX + Tier 1 fuel fetching, circuit breakers, and lockfile persistence."""
    if seed_offline:
        bl_countries = _load_baseline_countries(baseline_dir)
        seeded = seed_initial_lockfile(bl_countries)
        if write_lock:
            write_prices_lockfile(seeded, lock_path)
        return FetchRunReport(
            ok=True,
            fx_only=False,
            dry_run=not write_lock,
            lock_path=lock_path,
            tier1_feeds_succeeded=0,
            tier1_feeds_failed=0,
            countries_updated=0,
            countries_fallback=len(seeded.countries),
            fx_currencies_validated=len(seeded.fx_rates),
            alerts=[],
            provider_statuses=[],
        )

    now_dt = now_utc if now_utc is not None else datetime.now(UTC)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_date_str = now_dt.date().isoformat()

    if fx_only:
        return run_fx_only_fetch(
            lock_path=lock_path,
            timeout=timeout,
            write_lock=write_lock,
            transport=transport,
            fetched_at=now_iso if now_utc is not None else None,
            sleep_fn=sleep_fn,
        )

    existing_lock: PricesLockfile | None = (
        load_prices_lockfile(lock_path) if lock_path.is_file() else None
    )
    bl_countries = _load_baseline_countries(baseline_dir)
    baseline_seed = seed_initial_lockfile(
        bl_countries,
        seed_date=now_date_str,
        updated_at=now_iso,
    )

    alerts: list[LockAlert] = []
    provider_statuses: list[ProviderFetchStatus] = []

    with create_http_client(timeout=timeout, transport=transport) as client:
        fx_bundle = fetch_all_fx_quotes(client, sleep_fn=sleep_fn)
        provider_statuses.extend(fx_bundle.statuses)
        for status in fx_bundle.statuses:
            if not status.ok:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="fx_provider_outage",
                        scope=status.provider,
                        detail=redact_url_secrets(status.detail or "FX provider fetch failed"),
                    )
                )

        fx_provider_quotes = {
            name: FxProviderQuote(
                provider=q.provider,
                data_date=q.data_date,
                rates=dict(q.rates),
            )
            for name, q in fx_bundle.quotes.items()
        }
        fx_validation = cross_validate_fx_rates(
            fx_provider_quotes,
            previous_fx=existing_lock.fx_rates if existing_lock is not None else None,
            fetched_at=now_iso,
        )
        alerts.extend(fx_validation.alerts)

        if not fx_validation.ok:
            return FetchRunReport(
                ok=False,
                fx_only=False,
                dry_run=not write_lock,
                lock_path=lock_path,
                tier1_feeds_succeeded=0,
                tier1_feeds_failed=0,
                countries_updated=0,
                countries_fallback=0,
                fx_currencies_validated=len(fx_validation.rates),
                alerts=_sort_alerts(alerts),
                provider_statuses=provider_statuses,
            )

        ec_wob = fetch_ec_weekly_oil_bulletin(client, sleep_fn=sleep_fn)
        national_results = fetch_all_national_feeds(
            client,
            tankerkoenig_api_key=tankerkoenig_api_key,
            sleep_fn=sleep_fn,
        )
        fionnhughes: RawFuelFeedResult | None = None
        if not ec_wob.ok or len(ec_wob.quotes) < 27:
            fionnhughes = fetch_fionnhughes_fallback(client, sleep_fn=sleep_fn)
        fuel_prices_eu = fetch_fuel_prices_eu(client, sleep_fn=sleep_fn)

    all_fuel_results: list[RawFuelFeedResult] = [
        ec_wob,
        *national_results,
        *([fionnhughes] if fionnhughes is not None else []),
        fuel_prices_eu,
    ]

    for feed_res in all_fuel_results:
        if feed_res.skipped:
            provider_statuses.append(
                ProviderFetchStatus(
                    provider=feed_res.feed_name,
                    ok=True,
                    detail="skipped (TANKERKOENIG_API_KEY unset; using EC WOB)",
                    data_date=feed_res.data_date,
                )
            )
            continue
        provider_statuses.append(
            ProviderFetchStatus(
                provider=feed_res.feed_name,
                ok=feed_res.ok,
                detail=redact_url_secrets(feed_res.error) if feed_res.error else None,
                data_date=feed_res.data_date,
            )
        )
        if not feed_res.ok:
            alerts.append(
                LockAlert(
                    severity="warning",
                    code="feed_outage",
                    scope=feed_res.feed_name,
                    detail=redact_url_secrets(feed_res.error or "fuel feed fetch failed"),
                )
            )

    tier1_feeds_succeeded = sum(
        1 for r in all_fuel_results if r.tier == "tier1" and not r.skipped and r.ok
    )
    tier1_feeds_failed = sum(
        1 for r in all_fuel_results if r.tier == "tier1" and not r.skipped and not r.ok
    )

    if tier1_feeds_succeeded == 0:
        alerts.append(
            LockAlert(
                severity="error",
                code="total_tier1_outage",
                scope="pipeline",
                detail=(
                    "Zero Tier 1 European fuel feeds succeeded; "
                    "preserving previous lockfile (D-08)."
                ),
            )
        )
        return FetchRunReport(
            ok=False,
            fx_only=False,
            dry_run=not write_lock,
            lock_path=lock_path,
            tier1_feeds_succeeded=0,
            tier1_feeds_failed=tier1_feeds_failed,
            countries_updated=0,
            countries_fallback=0,
            fx_currencies_validated=len(fx_validation.rates),
            alerts=_sort_alerts(alerts),
            provider_statuses=provider_statuses,
        )

    # Group candidate quotes per ISO-2 in descending precedence so each feed is validated
    # independently before falling back to lower-precedence live feeds or lockfile retention.
    ordered_ok_feeds = sorted(
        (r for r in all_fuel_results if r.ok and not r.skipped),
        key=lambda r: (-_FEED_PRECEDENCE.get(r.feed_name, 0), r.feed_name),
    )

    candidates_by_iso2: dict[str, list[_FuelCandidate]] = {}
    for feed_res in ordered_ok_feeds:
        for quote in feed_res.quotes:
            if quote.iso2 not in EUROPEAN_TERRITORY_ISO2S:
                continue
            currency = TERRITORY_CURRENCIES[quote.iso2]
            fx_entry = fx_validation.rates[currency]
            try:
                local_map = _quote_to_local_prices(quote, fx_entry=fx_entry)
            except ValueError as exc:
                alerts.append(
                    LockAlert(
                        severity="warning",
                        code="quote_currency_mismatch",
                        scope=quote.iso2,
                        detail=redact_url_secrets(str(exc)),
                    )
                )
                continue
            candidates_by_iso2.setdefault(quote.iso2, []).append(
                _FuelCandidate(
                    source=quote.source,
                    license_name=quote.license,
                    data_date=quote.data_date,
                    feed_tier=feed_res.tier,
                    local_prices=local_map,
                )
            )

    normalized_allow = frozenset(normalize_iso2_alias(code) for code in allow_jump_iso2)
    countries: dict[str, CountryFuelLockEntry] = {}
    countries_updated = 0
    countries_fallback = 0

    for iso2 in sorted(EUROPEAN_TERRITORY_ISO2S):
        currency = TERRITORY_CURRENCIES[iso2]
        fx_entry = fx_validation.rates[currency]
        previous_entry = existing_lock.countries.get(iso2) if existing_lock is not None else None
        candidates = candidates_by_iso2.get(iso2, [])

        winning_idx: int | None = None
        winning_entry: CountryFuelLockEntry | None = None
        for idx, cand in enumerate(candidates):
            is_fallback_entry = cand.feed_tier == "fallback" and iso2 not in _NON_EU_VANILLA_ISO2S
            try:
                norm = normalize_country_fuel_prices(
                    iso2,
                    live_local_prices=cand.local_prices,
                    source=cand.source,
                    license_name=cand.license_name,
                    data_date=cand.data_date,
                    fx_entry=fx_entry,
                    previous_entry=previous_entry,
                    allow_jump_iso2=allow_jump_iso2,
                    fetched_at=now_iso,
                    is_fallback=is_fallback_entry,
                )
            except ValueError as exc:
                detail_msg = redact_url_secrets(str(exc))
                is_anchor_err = "anchor" in detail_msg.lower()
                alerts.append(
                    LockAlert(
                        severity="warning" if is_anchor_err else "error",
                        code="price_anchor_missing" if is_anchor_err else "price_bounds_rejected",
                        scope=iso2,
                        detail=detail_msg,
                    )
                )
                continue

            alerts.extend(norm.alerts)
            if norm.accepted:
                winning_idx = idx
                winning_entry = norm.entry
                break

        if winning_entry is not None and winning_idx is not None:
            winning_cand = candidates[winning_idx]
            accepted_live: dict[FuelGrade, float] = {
                grade: winning_entry.local_prices[grade] for grade in winning_cand.local_prices
            }
            supplemented = False
            for supp_cand in candidates[winning_idx + 1 :]:
                for grade, raw_local in sorted(supp_cand.local_prices.items()):
                    if grade in accepted_live:
                        continue
                    valid_val, supp_alert = _validate_supplemental_grade(
                        iso2,
                        grade,
                        raw_local,
                        source=supp_cand.source,
                        fx_entry=fx_entry,
                        previous_entry=previous_entry,
                        normalized_allow=normalized_allow,
                    )
                    if supp_alert is not None:
                        alerts.append(supp_alert)
                    if valid_val is not None:
                        accepted_live[grade] = valid_val
                        supplemented = True

            if supplemented:
                full_local, derived_grades = compute_secondary_grade_prices(accepted_live)
                winning_entry = winning_entry.model_copy(
                    update={"local_prices": full_local, "derived_grades": derived_grades}
                )

            countries[iso2] = winning_entry
            if not winning_entry.fallback_used:
                countries_updated += 1
            else:
                countries_fallback += 1
            continue

        # No valid live feed covered this territory -> retain lockfile or seed from 1.62 baseline.
        if previous_entry is not None:
            if previous_entry.source == BASELINE_SEEDED_SOURCE:
                countries[iso2] = _build_baseline_entry(
                    iso2,
                    diesel_eur=previous_entry.eur_per_liter,
                    fx_entry=fx_entry,
                    data_date=previous_entry.data_date,
                    fetched_at=now_iso,
                )
            else:
                countries[iso2] = previous_entry.model_copy(update={"fallback_used": True})
                if not candidates:
                    alerts.append(
                        LockAlert(
                            severity="warning",
                            code="price_lockfile_retained",
                            scope=iso2,
                            detail=(
                                f"No live feed returned data for {iso2}; retained previous "
                                f"lockfile entry ({previous_entry.source}, "
                                f"data_date={previous_entry.data_date})."
                            ),
                        )
                    )
        else:
            seed_eur = baseline_seed.countries[iso2].eur_per_liter
            countries[iso2] = _build_baseline_entry(
                iso2,
                diesel_eur=seed_eur,
                fx_entry=fx_entry,
                data_date=now_date_str,
                fetched_at=now_iso,
            )
        countries_fallback += 1

    sorted_fx = {code: fx_validation.rates[code] for code in sorted(fx_validation.rates)}
    sorted_countries = {code: countries[code] for code in sorted(countries)}
    preliminary_lock = PricesLockfile(
        schema_version=1,
        updated_at=now_iso,
        fx_rates=sorted_fx,
        countries=sorted_countries,
        alerts=[],
    )
    alerts.extend(evaluate_lockfile_staleness(preliminary_lock, now_dt.date()))
    sorted_alerts = _sort_alerts(alerts)

    final_lock = preliminary_lock.model_copy(update={"alerts": sorted_alerts})
    if write_lock:
        write_prices_lockfile(final_lock, lock_path)

    return FetchRunReport(
        ok=True,
        fx_only=False,
        dry_run=not write_lock,
        lock_path=lock_path,
        tier1_feeds_succeeded=tier1_feeds_succeeded,
        tier1_feeds_failed=tier1_feeds_failed,
        countries_updated=countries_updated,
        countries_fallback=countries_fallback,
        fx_currencies_validated=len(sorted_fx),
        alerts=sorted_alerts,
        provider_statuses=provider_statuses,
    )
