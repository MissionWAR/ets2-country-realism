"""Online-only hardened HTTP/XML transport and multi-provider FX fetchers."""

from __future__ import annotations

from ets2v2.fetch.fx import (
    CBR_DAILY_XML_URL,
    ECB_DAILY_XML_URL,
    FAWAZ_CLOUDFLARE_URL,
    FAWAZ_JSDELIVR_URL,
    FRANKFURTER_V2_URL,
    fetch_all_fx_quotes,
    fetch_cbr_daily_xml,
    fetch_ecb_daily_xml,
    fetch_fawazahmed0_eur,
    fetch_frankfurter_v2,
    run_fx_only_fetch,
)
from ets2v2.fetch.http import (
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_XML_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    HttpFetchError,
    create_http_client,
    fetch_bytes_with_retry,
    parse_xml_safe,
    redact_url_secrets,
    validate_https_url,
)
from ets2v2.fetch.models import (
    FetchRunReport,
    FxFetchBundle,
    ProviderFetchStatus,
    RawCountryFuelQuote,
    RawFuelFeedResult,
    RawFxProviderQuote,
)

__all__ = [
    "CBR_DAILY_XML_URL",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_XML_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_USER_AGENT",
    "ECB_DAILY_XML_URL",
    "FAWAZ_CLOUDFLARE_URL",
    "FAWAZ_JSDELIVR_URL",
    "FRANKFURTER_V2_URL",
    "FetchRunReport",
    "FxFetchBundle",
    "HttpFetchError",
    "ProviderFetchStatus",
    "RawCountryFuelQuote",
    "RawFuelFeedResult",
    "RawFxProviderQuote",
    "create_http_client",
    "fetch_all_fx_quotes",
    "fetch_bytes_with_retry",
    "fetch_cbr_daily_xml",
    "fetch_ecb_daily_xml",
    "fetch_fawazahmed0_eur",
    "fetch_frankfurter_v2",
    "parse_xml_safe",
    "redact_url_secrets",
    "run_fx_only_fetch",
    "validate_https_url",
]
