from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

_WHITESPACE = re.compile(r"\s+")
_BLOCKED_HOSTS = re.compile(r"^(localhost|127\.|0\.|10\.|192\.168\.|::1)", re.IGNORECASE)
_MAX_CHARS = 4000


def run(arguments: dict[str, Any]) -> str:
    url = arguments.get("url", "").strip()
    if not url:
        return "No URL provided."

    if not url.startswith(("http://", "https://")):
        return "Only http:// and https:// URLs are supported."

    host = url.split("/")[2]
    if _BLOCKED_HOSTS.match(host):
        return "Internal network URLs are not allowed."

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
