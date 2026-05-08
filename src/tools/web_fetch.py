from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

_WHITESPACE = re.compile(r"\s+")
_MAX_CHARS = 4000
_PRIVATE_URL_ERROR = "Internal network URLs are not allowed."
_ALLOWED_SCHEMES = {"http", "https"}
IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def validate_public_http_url(url: str) -> str | None:
    """Return an error message when the URL is unsupported or internal.

    The check parses the URL, validates scheme/host, resolves DNS, and rejects
    private, loopback, link-local, multicast, unspecified, and reserved IPs.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return "Only http:// and https:// URLs are supported."
    if not parsed.hostname:
        return "No host provided."
    if parsed.username or parsed.password:
        return "URLs with credentials are not supported."

    host = parsed.hostname.strip().lower()
    if host == "localhost" or host.endswith(".localhost"):
        return _PRIVATE_URL_ERROR

    try:
        addresses = _resolve_host(host, parsed.port)
    except OSError as exc:
        return f"Could not resolve host: {exc}"
    except ValueError as exc:
        return str(exc)

    if not addresses:
        return "Could not resolve host."
    if any(_is_blocked_ip(address) for address in addresses):
        return _PRIVATE_URL_ERROR
    return None


def _resolve_host(host: str, port: int | None) -> list[IPAddress]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass

    resolved: list[IPAddress] = []
    for info in socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM):
        sockaddr = info[4]
        resolved.append(ipaddress.ip_address(sockaddr[0]))
    return resolved


def _is_blocked_ip(address: IPAddress) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def run(arguments: dict[str, Any]) -> str:
    url = str(arguments.get("url", "")).strip()
    if not url:
        return "No URL provided."

    validation_error = validate_public_http_url(url)
    if validation_error is not None:
        return validation_error

    try:
        response = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; slm-workflow/1.0)"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"HTTP error: {exc}"
    except Exception as exc:
        return f"Fetch failed: {exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    text = _WHITESPACE.sub(" ", soup.get_text(separator=" ")).strip()
    return text[:_MAX_CHARS]
