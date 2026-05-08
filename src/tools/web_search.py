from __future__ import annotations

import time
from typing import Any

from ddgs import DDGS

from src.config import WEB_SEARCH_RETRY_BACKOFF
from src.tools.base import ToolBase


class WebSearch(ToolBase):
    name = "web_search"
    description = "Searches the web via DuckDuckGo and returns page snippets"
    parameters: dict[str, str] = {
        "query": "search query string",
        "max_results": "number of results to return (default 3, max 5)",
    }

    def execute(self, arguments: dict[str, Any]) -> str:
        query = arguments.get("query", "").strip()
        if not query:
            return "No query provided."

        max_results = min(int(arguments.get("max_results", 3)), 5)

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
                break
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(WEB_SEARCH_RETRY_BACKOFF * (attempt + 1))
        else:
            return f"Search failed: {last_error}"

        if not results:
            return "No results found."

        return "\n\n".join(
            f"Title: {r['title']}\nURL: {r.get('href', '')}\nSnippet: {r['body']}" for r in results
        )
