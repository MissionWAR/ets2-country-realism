"""Hardened HTTPS transport, SSRF allowlist, secret redaction, and XXE-safe XML helpers."""

from __future__ import annotations

import math
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from typing import Final
from urllib.parse import urljoin, urlsplit

import httpx

DEFAULT_TIMEOUT_SECONDS: Final[float] = 20.0
DEFAULT_MAX_RETRIES: Final[int] = 2
DEFAULT_MAX_RESPONSE_BYTES: Final[int] = 31_457_280  # 30 MiB
DEFAULT_MAX_XML_BYTES: Final[int] = 2_097_152  # 2 MiB
DEFAULT_USER_AGENT: Final[str] = (
    "ets2-world-realism/0.1.0 (+https://github.com/ets2-world-realism; clean-room open-data fetch)"
)

_RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})
_REDIRECT_STATUS_CODES: Final[frozenset[int]] = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS: Final[int] = 5

_SECRET_QUERY_RE: Final[re.Pattern[str]] = re.compile(
    r"([?&]|^)(apikey|api_key|token|key|code)=([^&\s'\"`)]+)",
    flags=re.IGNORECASE,
)
_XML_FORBIDDEN_DECL_RE: Final[re.Pattern[str]] = re.compile(
    r"<!(?:DOCTYPE|ENTITY)\b",
    flags=re.IGNORECASE,
)
_XML_PROLOG_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*<\?xml\b[^>]*\?>",
    flags=re.IGNORECASE,
)


class HttpFetchError(RuntimeError):
    """Redacted HTTP transport or status error raised by hardened fetch helpers."""


def redact_url_secrets(text: str) -> str:
    """Mask query-parameter credentials (``apikey``, ``api_key``, ``token``, ``key``, ``code``)."""
    return _SECRET_QUERY_RE.sub(r"\1\2=***", text)


def validate_https_url(url: str, allowed_hosts: frozenset[str]) -> str:
    """Enforce HTTPS scheme, standard port 443, no credentials, and exact host allowlist."""
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise ValueError(f"Only HTTPS URLs are permitted, got scheme {parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL must not contain embedded credentials")
    if parsed.port not in (None, 443):
        raise ValueError(f"Non-standard HTTPS port {parsed.port} is not permitted")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"URL is missing a valid hostname: {redact_url_secrets(url)!r}")
    normalized_allowed = {host.lower() for host in allowed_hosts}
    if hostname.lower() not in normalized_allowed:
        raise ValueError(f"Host {hostname.lower()!r} is not in HTTPS allowlist")
    return url


def create_http_client(
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    """Create a hardened synchronous ``httpx.Client`` with TLS verification unconditionally on."""
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise ValueError(f"HTTP timeout must be finite and > 0.0, got {timeout!r}")
    return httpx.Client(
        verify=True,
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": DEFAULT_USER_AGENT},
        follow_redirects=False,
        transport=transport,
    )


def _read_bounded_response(response: httpx.Response, *, max_bytes: int) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = -1
        if declared > max_bytes:
            raise ValueError(f"Response Content-Length {declared} exceeds max_bytes ({max_bytes})")

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"Response body exceeded max_bytes ({max_bytes})")
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_bytes_with_retry(
    client: httpx.Client,
    url: str,
    *,
    allowed_hosts: frozenset[str],
    params: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = 0.5,
    sleep_fn: Callable[[float], None] | None = None,
) -> bytes:
    """Perform a hardened GET with allowlisted redirect checking, byte cap, and bounded retries."""
    validate_https_url(url, allowed_hosts)
    sleeper = sleep_fn if sleep_fn is not None else time.sleep

    resolved_params: Mapping[str, str] | tuple[tuple[str, str], ...] | None = (
        params if params is None or isinstance(params, Mapping) else tuple(params)
    )

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        current_url = url
        current_params: Mapping[str, str] | tuple[tuple[str, str], ...] | None = resolved_params
        try:
            for _redirect_hop in range(_MAX_REDIRECTS + 1):
                with client.stream(
                    "GET",
                    current_url,
                    params=current_params,
                    headers=headers,
                ) as response:
                    status = response.status_code
                    if status in _REDIRECT_STATUS_CODES:
                        location = response.headers.get("location")
                        if not location:
                            raise HttpFetchError(
                                f"HTTP {status} redirect missing Location header for "
                                f"{redact_url_secrets(current_url)}"
                            )
                        next_url = urljoin(current_url, location)
                        validate_https_url(next_url, allowed_hosts)
                        current_url = next_url
                        current_params = None
                        continue

                    if status in _RETRYABLE_STATUS_CODES:
                        if attempt < max_retries:
                            sleeper(backoff_seconds * (2**attempt))
                            break
                        raise HttpFetchError(
                            f"HTTP {status} for {redact_url_secrets(str(response.url))}"
                        )

                    if status >= 400:
                        raise HttpFetchError(
                            f"HTTP {status} for {redact_url_secrets(str(response.url))}"
                        )

                    return _read_bounded_response(response, max_bytes=max_bytes)
            else:
                raise HttpFetchError(
                    f"Exceeded maximum redirects ({_MAX_REDIRECTS}) for {redact_url_secrets(url)}"
                )
        except httpx.TransportError as exc:
            last_error = HttpFetchError(redact_url_secrets(str(exc)))
            if attempt < max_retries:
                sleeper(backoff_seconds * (2**attempt))
                continue
            raise last_error from None
        except (httpx.DecodingError, httpx.StreamError) as exc:
            raise HttpFetchError(redact_url_secrets(str(exc))) from None
        except HttpFetchError:
            raise

    assert last_error is not None
    raise last_error


def post_form_bytes_with_retry(
    client: httpx.Client,
    url: str,
    *,
    allowed_hosts: frozenset[str],
    data: Mapping[str, str],
    headers: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = 0.5,
    sleep_fn: Callable[[float], None] | None = None,
) -> bytes:
    """Perform a hardened form-encoded POST with allowlist checking, byte cap, and retries."""
    validate_https_url(url, allowed_hosts)
    sleeper = sleep_fn if sleep_fn is not None else time.sleep
    form_data = dict(data)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        current_url = url
        try:
            for _redirect_hop in range(_MAX_REDIRECTS + 1):
                with client.stream(
                    "POST",
                    current_url,
                    data=form_data,
                    headers=headers,
                ) as response:
                    status = response.status_code
                    if status in {307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise HttpFetchError(
                                f"HTTP {status} redirect missing Location header for "
                                f"{redact_url_secrets(current_url)}"
                            )
                        next_url = urljoin(current_url, location)
                        validate_https_url(next_url, allowed_hosts)
                        current_url = next_url
                        continue

                    if status in _REDIRECT_STATUS_CODES:
                        raise HttpFetchError(
                            f"HTTP {status} non-POST-preserving redirect for "
                            f"{redact_url_secrets(current_url)}"
                        )

                    if status in _RETRYABLE_STATUS_CODES:
                        if attempt < max_retries:
                            sleeper(backoff_seconds * (2**attempt))
                            break
                        raise HttpFetchError(
                            f"HTTP {status} for {redact_url_secrets(str(response.url))}"
                        )

                    if status >= 400:
                        raise HttpFetchError(
                            f"HTTP {status} for {redact_url_secrets(str(response.url))}"
                        )

                    return _read_bounded_response(response, max_bytes=max_bytes)
            else:
                raise HttpFetchError(
                    f"Exceeded maximum redirects ({_MAX_REDIRECTS}) for {redact_url_secrets(url)}"
                )
        except httpx.TransportError as exc:
            last_error = HttpFetchError(redact_url_secrets(str(exc)))
            if attempt < max_retries:
                sleeper(backoff_seconds * (2**attempt))
                continue
            raise last_error from None
        except (httpx.DecodingError, httpx.StreamError) as exc:
            raise HttpFetchError(redact_url_secrets(str(exc))) from None
        except HttpFetchError:
            raise

    assert last_error is not None
    raise last_error


def parse_xml_safe(
    raw: bytes,
    *,
    encoding: str = "utf-8",
    max_bytes: int = DEFAULT_MAX_XML_BYTES,
) -> ET.Element:
    """Safely parse untrusted XML enforcing a byte cap and rejecting DOCTYPE/ENTITY (T-03-02)."""
    if len(raw) > max_bytes:
        raise ValueError(f"XML payload size {len(raw)} exceeds max_bytes ({max_bytes})")
    text = raw.decode(encoding).removeprefix("\ufeff")
    if _XML_FORBIDDEN_DECL_RE.search(text):
        raise ValueError("XML payload contains forbidden DOCTYPE or ENTITY declaration")
    cleaned = _XML_PROLOG_RE.sub("", text, count=1)
    return ET.fromstring(cleaned)
