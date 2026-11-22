"""Fault-isolated Tier 1 national multi-grade fuel collectors (UK, NO, FR, DE, ES, IT, NL)."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import statistics
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Final, cast
from urllib.parse import urljoin

import httpx

from ets2v2.fetch._parsing import (
    AnchorExtractor,
    extract_iso_date,
    parse_positive_float,
)
from ets2v2.fetch.http import (
    HttpFetchError,
    fetch_bytes_with_retry,
    redact_url_secrets,
    validate_https_url,
)
from ets2v2.fetch.models import RawCountryFuelQuote, RawFuelFeedResult
from ets2v2.normalize.models import FuelGrade

UK_DESNZ_LANDING_URL: Final[str] = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "oil-and-petroleum-products-weekly-statistics"
)
UK_DESNZ_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"www.gov.uk", "assets.publishing.service.gov.uk"}
)

NO_SSB_09654_URL: Final[str] = (
    "https://data.ssb.no/api/pxwebapi/v2/tables/09654/data?lang=en&valueCodes[Tid]=top(3)"
)
NO_SSB_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"data.ssb.no"})

FR_ECONOMIE_URL: Final[str] = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "prix-des-carburants-en-france-flux-instantane-v2/records"
    "?select=avg(gazole_prix)%20as%20diesel,avg(sp95_prix)%20as%20petrol_95,"
    "avg(sp98_prix)%20as%20petrol_98,avg(e10_prix)%20as%20e10,"
    "avg(e85_prix)%20as%20e85,avg(gplc_prix)%20as%20lpg&limit=1"
)
FR_ECONOMIE_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"data.economie.gouv.fr"})

DE_TANKERKOENIG_URL: Final[str] = "https://creativecommons.tankerkoenig.de/json/list.php"
DE_TANKERKOENIG_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {"creativecommons.tankerkoenig.de"}
)
TANKERKOENIG_CITIES: Final[tuple[tuple[str, float, float], ...]] = (
    ("Berlin", 52.52, 13.405),
    ("Hamburg", 53.551, 9.994),
    ("Munich", 48.135, 11.582),
    ("Cologne", 50.938, 6.960),
    ("Frankfurt", 50.111, 8.682),
)

ES_MITECO_URL: Final[str] = (
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
    "PreciosCarburantes/EstacionesTerrestres/"
)
ES_MITECO_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"sedeaplicaciones.minetur.gob.es"})
ES_MITECO_MAX_BYTES: Final[int] = 52_428_800  # 50 MiB for ~12,000-station payload

IT_MIMIT_URL: Final[str] = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
IT_MIMIT_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"www.mimit.gov.it"})

NL_CBS_80416NED_URL: Final[str] = (
    "https://opendata.cbs.nl/ODataApi/odata/80416ned/TypedDataSet?$orderby=Perioden%20desc&$top=5"
)
NL_CBS_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"opendata.cbs.nl"})

_SSB_MONTH_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4})M(\d{2})$")
_CBS_DAILY_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4})(\d{2})(\d{2})$")

_ES_MITECO_GRADE_FIELDS: Final[tuple[tuple[str, FuelGrade], ...]] = (
    ("Precio Gasoleo A", "diesel"),
    ("Precio Gasoleo Premium", "diesel_plus"),
    ("Precio Gasolina 95 E5", "petrol_95"),
    ("Precio Gasolina 98 E5", "petrol_98"),
    ("Precio Gases licuados del petróleo", "lpg"),
)

_IT_MIMIT_DIESEL_PLUS: Final[frozenset[str]] = frozenset(
    {
        "blue diesel",
        "diesel max",
        "diesel+",
        "excellium diesel",
        "gasolio alpino",
        "gasolio plus",
        "gasolio special",
        "gasolio speciale",
        "hi-q diesel",
        "supreme diesel",
    }
)
_IT_MIMIT_PETROL_98: Final[frozenset[str]] = frozenset(
    {
        "benzina 100 ottani",
        "benzina special",
        "benzina speciale",
        "blu super",
        "hiq perform+",
        "v-power",
    }
)


def discover_uk_desnz_csv_url(
    html_text: str,
    base_url: str = UK_DESNZ_LANDING_URL,
) -> str:
    """Discover the UK DESNZ Weekly Road Fuel Prices CSV URL under strict GOV.UK allowlist."""
    parser = AnchorExtractor()
    parser.feed(html_text)
    parser.close()

    scored: list[tuple[int, str]] = []
    for href, text in parser.anchors:
        href_lower = href.lower()
        text_lower = text.lower()
        if ".csv" not in href_lower and "csv" not in text_lower:
            continue
        score = 0
        if ".csv" in href_lower:
            score += 5
        if "road" in f"{href_lower} {text_lower}" or "fuel" in f"{href_lower} {text_lower}":
            score += 6
        if "weekly" in f"{href_lower} {text_lower}":
            score += 4
        if score > 0:
            scored.append((score, href))

    if not scored:
        raise ValueError("Could not discover UK DESNZ weekly road fuel prices CSV link")

    scored.sort(key=lambda item: item[0], reverse=True)
    resolved = urljoin(base_url, scored[0][1])
    return validate_https_url(resolved, UK_DESNZ_ALLOWED_HOSTS)


def fetch_uk_desnz(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch UK DESNZ weekly road fuel prices CSV (pence/L -> GBP/L, OGL v3.0)."""
    try:
        landing_raw = fetch_bytes_with_retry(
            client,
            UK_DESNZ_LANDING_URL,
            allowed_hosts=UK_DESNZ_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        csv_url = discover_uk_desnz_csv_url(
            landing_raw.decode("utf-8", errors="replace"),
            UK_DESNZ_LANDING_URL,
        )
        csv_raw = fetch_bytes_with_retry(
            client,
            csv_url,
            allowed_hosts=UK_DESNZ_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        reader = csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig")))
        if not reader.fieldnames:
            raise ValueError("UK DESNZ CSV is missing header row")

        date_col: str | None = None
        ulsp_col: str | None = None
        ulsd_col: str | None = None
        for col in reader.fieldnames:
            if not col:
                continue
            lower = col.strip().lower()
            if date_col is None and "date" in lower:
                date_col = col
            if ulsp_col is None and ("ulsp" in lower or ("unleaded" in lower and "pump" in lower)):
                ulsp_col = col
            if ulsd_col is None and ("ulsd" in lower or ("diesel" in lower and "pump" in lower)):
                ulsd_col = col

        if not (date_col and ulsp_col and ulsd_col):
            raise ValueError(
                f"UK DESNZ CSV missing Date/ULSP/ULSD columns; got {list(reader.fieldnames)}"
            )

        best_date = ""
        best_prices: dict[FuelGrade, float] | None = None
        for row in reader:
            iso_date = extract_iso_date(str(row.get(date_col, "")))
            if iso_date is None:
                continue
            ulsp_pence = parse_positive_float(row.get(ulsp_col))
            ulsd_pence = parse_positive_float(row.get(ulsd_col))
            if ulsp_pence is None or ulsd_pence is None:
                continue
            if iso_date >= best_date:
                best_date = iso_date
                best_prices = {
                    "petrol_95": ulsp_pence / 100.0,
                    "diesel": ulsd_pence / 100.0,
                }

        if not best_date or best_prices is None:
            raise ValueError("UK DESNZ CSV contained no valid dated ULSP/ULSD rows")

        quote = RawCountryFuelQuote(
            iso2="GB",
            currency="GBP",
            prices_by_grade=best_prices,
            unit_basis="local_per_liter",
            source="uk_desnz",
            license="OGL v3.0",
            data_date=best_date,
        )
    except (HttpFetchError, httpx.HTTPError, ValueError, KeyError, OSError, csv.Error) as exc:
        return RawFuelFeedResult(
            feed_name="uk_desnz",
            tier="tier1",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="uk_desnz",
        tier="tier1",
        ok=True,
        quotes=[quote],
        data_date=best_date,
    )


def _json_stat2_index_map(cat_dict: dict[object, object]) -> dict[str, int]:
    raw_index = cat_dict.get("index")
    result: dict[str, int] = {}
    if isinstance(raw_index, dict):
        for k, v in cast(dict[object, object], raw_index).items():
            if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool):
                result[k] = v
    elif isinstance(raw_index, list):
        for idx, item in enumerate(cast(list[object], raw_index)):
            if isinstance(item, str):
                result[item] = idx
    return result


def _json_stat2_label_map(cat_dict: dict[object, object]) -> dict[str, str]:
    raw_label = cat_dict.get("label")
    result: dict[str, str] = {}
    if isinstance(raw_label, dict):
        for k, v in cast(dict[object, object], raw_label).items():
            if isinstance(k, str) and isinstance(v, str):
                result[k] = v
    return result


def fetch_no_ssb_09654(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Norway SSB Table 09654 JSON-stat2 monthly average retail fuel prices (NOK/L)."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            NO_SSB_09654_URL,
            allowed_hosts=NO_SSB_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("SSB 09654 payload is not a JSON object")
        obj = cast(dict[object, object], payload)

        raw_ids = obj.get("id")
        raw_sizes = obj.get("size")
        raw_dims = obj.get("dimension")
        raw_values = obj.get("value")
        if (
            not isinstance(raw_ids, list)
            or not isinstance(raw_sizes, list)
            or not isinstance(raw_dims, dict)
        ):
            raise ValueError("SSB 09654 JSON-stat2 missing id/size/dimension fields")

        dim_ids = [str(item) for item in cast(list[object], raw_ids)]
        sizes = [int(str(item)) for item in cast(list[object], raw_sizes)]
        if len(dim_ids) != len(sizes) or not dim_ids:
            raise ValueError("SSB 09654 JSON-stat2 id/size mismatch")

        dims = cast(dict[object, object], raw_dims)

        # Compute row-major strides
        strides: list[int] = [1] * len(sizes)
        for i in range(len(sizes) - 2, -1, -1):
            strides[i] = strides[i + 1] * sizes[i + 1]

        def _get_flat_value(flat_idx: int) -> float | None:
            if isinstance(raw_values, list):
                vals = cast(list[object], raw_values)
                if 0 <= flat_idx < len(vals):
                    return parse_positive_float(vals[flat_idx])
                return None
            if isinstance(raw_values, dict):
                val_map = cast(dict[object, object], raw_values)
                return parse_positive_float(val_map.get(str(flat_idx)))
            return None

        time_dim_pos: int | None = None
        time_entries: list[tuple[str, int]] = []  # (YYYY-MM-01, position)
        product_dim_pos: int | None = None
        product_grade_positions: dict[FuelGrade, int] = {}

        for dim_pos, dim_name in enumerate(dim_ids):
            dim_obj = dims.get(dim_name)
            if not isinstance(dim_obj, dict):
                continue
            cat_obj = cast(dict[object, object], dim_obj).get("category")
            if not isinstance(cat_obj, dict):
                continue
            cat = cast(dict[object, object], cat_obj)
            index_map = _json_stat2_index_map(cat)
            label_map = _json_stat2_label_map(cat)

            # Check if this dimension is the time dimension (YYYYM## keys)
            matched_times: list[tuple[str, int]] = []
            for key, pos in index_map.items():
                m = _SSB_MONTH_RE.match(key.strip())
                if m is not None:
                    year_s, month_s = m.groups()
                    try:
                        iso_month = date(int(year_s), int(month_s), 1).isoformat()
                    except ValueError:
                        continue
                    matched_times.append((iso_month, pos))
            if matched_times:
                time_dim_pos = dim_pos
                time_entries = sorted(matched_times, key=lambda item: item[0], reverse=True)
                continue

            # Check if this dimension maps fuel product labels
            matched_grades: dict[FuelGrade, int] = {}
            for key, pos in index_map.items():
                label = label_map.get(key, key).lower()
                if "duty-free" in label or "avgiftsfri" in label:
                    continue
                if (
                    "95" in label or "gasoline" in label or "bensin" in label
                ) and "petrol_95" not in matched_grades:
                    matched_grades["petrol_95"] = pos
                elif (
                    "diesel" in label or "autodiesel" in label
                ) and "diesel" not in matched_grades:
                    matched_grades["diesel"] = pos
            if matched_grades:
                product_dim_pos = dim_pos
                product_grade_positions = matched_grades

        if time_dim_pos is None or product_dim_pos is None or not product_grade_positions:
            raise ValueError("SSB 09654 JSON-stat2 missing recognizable time or fuel dimensions")

        # Validate all non-time, non-product dimensions have size == 1 or resolve ContentsCode price
        extra_dim_offset = 0
        for dim_pos, dim_name in enumerate(dim_ids):
            if dim_pos in {time_dim_pos, product_dim_pos}:
                continue
            dim_size = sizes[dim_pos]
            if dim_size == 1:
                continue
            if dim_name.lower() != "contentscode":
                raise ValueError(
                    f"SSB 09654 JSON-stat2 unexpected multi-valued dimension "
                    f"{dim_name!r} (size={dim_size})"
                )
            dim_obj = dims.get(dim_name)
            if not isinstance(dim_obj, dict):
                raise ValueError("SSB 09654 ContentsCode dimension missing metadata")
            cat_obj = cast(dict[object, object], dim_obj).get("category")
            if not isinstance(cat_obj, dict):
                raise ValueError("SSB 09654 ContentsCode dimension missing category")
            cat = cast(dict[object, object], cat_obj)
            index_map = _json_stat2_index_map(cat)
            label_map = _json_stat2_label_map(cat)
            price_positions: list[int] = []
            for key, pos in index_map.items():
                combined = f"{key} {label_map.get(key, '')}".lower()
                if ("pris" in combined or "price" in combined) and not any(
                    tok in combined for tok in ("percent", "prosent", "change", "endring")
                ):
                    price_positions.append(pos)
            if len(price_positions) != 1:
                raise ValueError(
                    f"SSB 09654 ContentsCode has size {dim_size} and ambiguous price series"
                )
            extra_dim_offset += price_positions[0] * strides[dim_pos]

        chosen_date = ""
        chosen_prices: dict[FuelGrade, float] = {}
        for iso_month, t_pos in time_entries:
            month_prices: dict[FuelGrade, float] = {}
            for grade, p_pos in product_grade_positions.items():
                flat_idx = (
                    extra_dim_offset
                    + p_pos * strides[product_dim_pos]
                    + t_pos * strides[time_dim_pos]
                )
                val = _get_flat_value(flat_idx)
                if val is not None:
                    month_prices[grade] = val
            if "diesel" in month_prices and "petrol_95" in month_prices:
                chosen_date = iso_month
                chosen_prices = month_prices
                break

        if not chosen_date or not chosen_prices:
            raise ValueError("SSB 09654 JSON-stat2 contained no non-null petrol_95/diesel month")

        quote = RawCountryFuelQuote(
            iso2="NO",
            currency="NOK",
            prices_by_grade=chosen_prices,
            unit_basis="local_per_liter",
            source="no_ssb_09654",
            license="CC BY 4.0 (NLOD)",
            data_date=chosen_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="no_ssb_09654",
            tier="tier1",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="no_ssb_09654",
        tier="tier1",
        ok=True,
        quotes=[quote],
        data_date=chosen_date,
    )


def fetch_fr_economie(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch France OpenDataSoft v2.1 national avg() multi-grade fuel prices (EUR/L)."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            FR_ECONOMIE_URL,
            allowed_hosts=FR_ECONOMIE_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("FR OpenDataSoft v2.1 payload is not a JSON object")
        results = cast(dict[object, object], payload).get("results")
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            raise ValueError("FR OpenDataSoft v2.1 response missing results[0]")
        row = cast(dict[object, object], results[0])

        def _norm_eur(key: str) -> float | None:
            val = parse_positive_float(row.get(key))
            if val is None:
                return None
            return val / 1000.0 if val > 100.0 else val

        prices: dict[FuelGrade, float] = {}
        diesel = _norm_eur("diesel")
        if diesel is not None:
            prices["diesel"] = diesel
        p95 = _norm_eur("petrol_95")
        if p95 is None:
            p95 = _norm_eur("e10")
        if p95 is not None:
            prices["petrol_95"] = p95
        extra_fr_grades: tuple[tuple[str, FuelGrade], ...] = (
            ("petrol_98", "petrol_98"),
            ("e85", "e85"),
            ("lpg", "lpg"),
        )
        for field_name, grade in extra_fr_grades:
            val = _norm_eur(field_name)
            if val is not None:
                prices[grade] = val

        if "diesel" not in prices or "petrol_95" not in prices:
            raise ValueError("FR OpenDataSoft v2.1 missing required diesel or petrol_95 averages")

        today = datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="FR",
            currency="EUR",
            prices_by_grade=prices,
            unit_basis="eur_per_liter",
            source="fr_economie_ods",
            license="Licence Ouverte v2.0",
            data_date=today,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="fr_economie_ods",
            tier="tier1",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="fr_economie_ods",
        tier="tier1",
        ok=True,
        quotes=[quote],
        data_date=today,
    )


def fetch_de_tankerkoenig(
    client: httpx.Client,
    *,
    api_key: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch optional Germany Tankerkoenig 5-city median (D-03 silent keyless fallback, T-03-07)."""
    resolved_key = (
        api_key if api_key is not None else os.environ.get("TANKERKOENIG_API_KEY", "")
    ).strip()
    if not resolved_key:
        return RawFuelFeedResult(
            feed_name="de_tankerkoenig",
            tier="tier1",
            ok=True,
            skipped=True,
            quotes=[],
        )

    def _scrub(message: str) -> str:
        return redact_url_secrets(message).replace(resolved_key, "***")

    try:
        diesel_samples: list[float] = []
        e5_samples: list[float] = []
        for _city, lat, lng in TANKERKOENIG_CITIES:
            raw = fetch_bytes_with_retry(
                client,
                DE_TANKERKOENIG_URL,
                allowed_hosts=DE_TANKERKOENIG_ALLOWED_HOSTS,
                params={
                    "lat": f"{lat:.3f}",
                    "lng": f"{lng:.3f}",
                    "rad": "15",
                    "sort": "dist",
                    "type": "all",
                    "apikey": resolved_key,
                },
                sleep_fn=sleep_fn,
            )
            payload: object = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Tankerkoenig payload is not a JSON object")
            obj = cast(dict[object, object], payload)
            if obj.get("ok") is not True:
                raise ValueError(f"Tankerkoenig API returned ok={obj.get('ok')!r}")
            stations = obj.get("stations")
            if not isinstance(stations, list):
                continue
            for item in cast(list[object], stations):
                if not isinstance(item, dict):
                    continue
                st = cast(dict[object, object], item)
                if st.get("isOpen") is not True:
                    continue
                d_val = parse_positive_float(st.get("diesel"))
                if d_val is not None:
                    diesel_samples.append(d_val)
                e5_val = parse_positive_float(st.get("e5"))
                if e5_val is not None:
                    e5_samples.append(e5_val)

        if not diesel_samples or not e5_samples:
            raise ValueError("Tankerkoenig returned zero open stations with valid diesel/e5 prices")

        today = datetime.now(UTC).date().isoformat()
        quote = RawCountryFuelQuote(
            iso2="DE",
            currency="EUR",
            prices_by_grade={
                "diesel": statistics.median(diesel_samples),
                "petrol_95": statistics.median(e5_samples),
            },
            unit_basis="eur_per_liter",
            source="de_tankerkoenig",
            license="CC BY 4.0",
            data_date=today,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="de_tankerkoenig",
            tier="tier1",
            ok=False,
            skipped=False,
            quotes=[],
            error=_scrub(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="de_tankerkoenig",
        tier="tier1",
        ok=True,
        skipped=False,
        quotes=[quote],
        data_date=today,
    )


def fetch_es_miteco(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Spain MITECO EstacionesTerrestres JSON and compute outlier-resilient medians."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            ES_MITECO_URL,
            allowed_hosts=ES_MITECO_ALLOWED_HOSTS,
            headers={"Accept": "application/json"},
            max_bytes=ES_MITECO_MAX_BYTES,
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("ES MITECO payload is not a JSON object")
        obj = cast(dict[object, object], payload)

        fecha_raw = str(obj.get("Fecha", ""))
        data_date = extract_iso_date(fecha_raw) or datetime.now(UTC).date().isoformat()
        stations = obj.get("ListaEESSPrecio")
        if not isinstance(stations, list) or not stations:
            raise ValueError("ES MITECO payload missing non-empty ListaEESSPrecio")

        samples: dict[FuelGrade, list[float]] = {}
        for item in cast(list[object], stations):
            if not isinstance(item, dict):
                continue
            st = cast(dict[object, object], item)
            for field_name, grade in _ES_MITECO_GRADE_FIELDS:
                val = parse_positive_float(st.get(field_name))
                if val is not None:
                    samples.setdefault(grade, []).append(val)

        prices: dict[FuelGrade, float] = {
            grade: statistics.median(vals) for grade, vals in samples.items() if vals
        }
        if "diesel" not in prices or "petrol_95" not in prices:
            raise ValueError("ES MITECO yielded no valid diesel or petrol_95 station prices")

        quote = RawCountryFuelQuote(
            iso2="ES",
            currency="EUR",
            prices_by_grade=prices,
            unit_basis="eur_per_liter",
            source="es_miteco",
            license="Spanish Open Gov Data (MITECO)",
            data_date=data_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="es_miteco",
            tier="tier1",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="es_miteco",
        tier="tier1",
        ok=True,
        quotes=[quote],
        data_date=data_date,
    )


def _map_it_mimit_grade(desc: str) -> FuelGrade | None:
    normalized = " ".join(desc.strip().lower().split())
    if normalized == "benzina":
        return "petrol_95"
    if normalized == "gasolio":
        return "diesel"
    if normalized == "gpl":
        return "lpg"
    if normalized in _IT_MIMIT_DIESEL_PLUS:
        return "diesel_plus"
    if normalized in _IT_MIMIT_PETROL_98:
        return "petrol_98"
    return None


def fetch_it_mimit(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Italy MIMIT Osservaprezzi CSV (strip Line-1 banner, filter isSelf=1, median)."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            IT_MIMIT_URL,
            allowed_hosts=IT_MIMIT_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        text = raw.decode("utf-8-sig", errors="replace")
        lines = text.splitlines()
        if len(lines) < 2:
            raise ValueError("IT MIMIT CSV has fewer than 2 lines")

        first_line = lines[0].strip()
        if first_line.lower().startswith("estrazione"):
            data_date = extract_iso_date(first_line) or datetime.now(UTC).date().isoformat()
            csv_lines = lines[1:]
        else:
            data_date = datetime.now(UTC).date().isoformat()
            csv_lines = lines

        if not csv_lines:
            raise ValueError("IT MIMIT CSV is missing header after banner line")

        header_line = csv_lines[0]
        delimiter = ";" if header_line.count(";") >= header_line.count(",") else ","
        reader = csv.DictReader(io.StringIO("\n".join(csv_lines)), delimiter=delimiter)

        samples: dict[FuelGrade, list[float]] = {}
        for row in reader:
            if str(row.get("isSelf", "")).strip() != "1":
                continue
            grade = _map_it_mimit_grade(str(row.get("descCarburante", "")))
            if grade is None:
                continue
            price = parse_positive_float(row.get("prezzo"))
            if price is not None:
                samples.setdefault(grade, []).append(price)

        prices: dict[FuelGrade, float] = {
            grade: statistics.median(vals) for grade, vals in samples.items() if vals
        }
        if "diesel" not in prices or "petrol_95" not in prices:
            raise ValueError("IT MIMIT CSV yielded no valid self-service diesel/petrol_95 prices")

        quote = RawCountryFuelQuote(
            iso2="IT",
            currency="EUR",
            prices_by_grade=prices,
            unit_basis="eur_per_liter",
            source="it_mimit",
            license="IODL 2.0",
            data_date=data_date,
        )
    except (HttpFetchError, httpx.HTTPError, ValueError, KeyError, OSError, csv.Error) as exc:
        return RawFuelFeedResult(
            feed_name="it_mimit",
            tier="tier1",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="it_mimit",
        tier="tier1",
        ok=True,
        quotes=[quote],
        data_date=data_date,
    )


def fetch_nl_cbs_80416ned(
    client: httpx.Client,
    *,
    sleep_fn: Callable[[float], None] | None = None,
) -> RawFuelFeedResult:
    """Fetch Netherlands CBS StatLine OData 80416ned filtering strictly daily YYYYMMDD rows."""
    try:
        raw = fetch_bytes_with_retry(
            client,
            NL_CBS_80416NED_URL,
            allowed_hosts=NL_CBS_ALLOWED_HOSTS,
            sleep_fn=sleep_fn,
        )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("NL CBS 80416ned payload is not a JSON object")
        rows = cast(dict[object, object], payload).get("value")
        if not isinstance(rows, list) or not rows:
            raise ValueError("NL CBS 80416ned payload missing non-empty 'value' list")

        best_period = ""
        best_date = ""
        best_prices: dict[FuelGrade, float] | None = None
        for item in cast(list[object], rows):
            if not isinstance(item, dict):
                continue
            row = cast(dict[object, object], item)
            period = str(row.get("Perioden", "")).strip()
            m = _CBS_DAILY_RE.match(period)
            if m is None:
                continue
            try:
                candidate_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
            except ValueError:
                continue
            p95 = parse_positive_float(row.get("BenzineEuro95_1"))
            diesel = parse_positive_float(row.get("Diesel_2"))
            if p95 is None or diesel is None:
                continue
            if period > best_period:
                best_period = period
                best_date = candidate_date
                prices: dict[FuelGrade, float] = {
                    "petrol_95": p95,
                    "diesel": diesel,
                }
                lpg = parse_positive_float(row.get("Lpg_3"))
                if lpg is not None:
                    prices["lpg"] = lpg
                best_prices = prices

        if not best_date or best_prices is None:
            raise ValueError("NL CBS 80416ned contained no valid daily YYYYMMDD observation rows")

        quote = RawCountryFuelQuote(
            iso2="NL",
            currency="EUR",
            prices_by_grade=best_prices,
            unit_basis="eur_per_liter",
            source="nl_cbs_80416ned",
            license="CC BY 4.0 (CBS)",
            data_date=best_date,
        )
    except (
        HttpFetchError,
        httpx.HTTPError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        return RawFuelFeedResult(
            feed_name="nl_cbs_80416ned",
            tier="tier1",
            ok=False,
            quotes=[],
            error=redact_url_secrets(str(exc)),
        )

    return RawFuelFeedResult(
        feed_name="nl_cbs_80416ned",
        tier="tier1",
        ok=True,
        quotes=[quote],
        data_date=best_date,
    )


def fetch_all_national_feeds(
    client: httpx.Client,
    *,
    tankerkoenig_api_key: str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> list[RawFuelFeedResult]:
    """Run all 7 isolated Tier 1 national fuel collectors in deterministic order."""
    return [
        fetch_uk_desnz(client, sleep_fn=sleep_fn),
        fetch_no_ssb_09654(client, sleep_fn=sleep_fn),
        fetch_fr_economie(client, sleep_fn=sleep_fn),
        fetch_de_tankerkoenig(client, api_key=tankerkoenig_api_key, sleep_fn=sleep_fn),
        fetch_es_miteco(client, sleep_fn=sleep_fn),
        fetch_it_mimit(client, sleep_fn=sleep_fn),
        fetch_nl_cbs_80416ned(client, sleep_fn=sleep_fn),
    ]
