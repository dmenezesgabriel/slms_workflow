from __future__ import annotations

from typing import Any

import httpx

from src.config import HTTP_TIMEOUT, HTTP_USER_AGENT
from src.tools.base import ToolBase

_API = "https://en.wikipedia.org/w/api.php"
_MAX_CHARS = 2000


class Wikipedia(ToolBase):
    name = "wikipedia"
    description = "Returns the introductory section of a Wikipedia article"
    parameters: dict[str, str] = {"query": "article title or subject to look up"}

    def execute(self, arguments: dict[str, Any]) -> str:
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
                timeout=HTTP_TIMEOUT,
                headers={"User-Agent": HTTP_USER_AGENT},
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
