from __future__ import annotations

from typing import Any

import httpx

_API = "https://en.wikipedia.org/w/api.php"
_MAX_CHARS = 2000


def run(arguments: dict[str, Any]) -> str:
    query = arguments.get("query", "").strip()
    if not query:
        return "No query provided."

    try:
        response = httpx.get(
            _API,
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "redirects": 1,
                "titles": query,
                "format": "json",
            },
            timeout=10,
            headers={"User-Agent": "slm-workflow/1.0 (educational)"},
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return f"Wikipedia lookup failed: {exc}"

    pages: dict[str, Any] = data.get("query", {}).get("pages", {})
    page: dict[str, Any] = next(iter(pages.values()), {})

    if "missing" in page:
        return f"No Wikipedia article found for: {query}"

    extract = page.get("extract", "").strip()
    return extract[:_MAX_CHARS] if extract else f"No content found for: {query}"
