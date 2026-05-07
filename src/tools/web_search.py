from __future__ import annotations

from typing import Any

from ddgs import DDGS


def run(arguments: dict[str, Any]) -> str:
    query = arguments.get("query", "").strip()
    if not query:
        return "No query provided."

    max_results = min(int(arguments.get("max_results", 3)), 5)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        return f"Search failed: {exc}"

    if not results:
        return "No results found."

    return "\n\n".join(f"Title: {r['title']}\nSnippet: {r['body']}" for r in results)
