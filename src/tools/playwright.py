"""Playwright browser automation tool for RPA workflows.

Provides browser automation capabilities for:
- Web scraping with dynamic content
- Form filling and submission
- UI testing and verification
- Cross-site data extraction
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.tools.base import ToolBase


class PlaywrightTool(ToolBase):
    name = "playwright"
    description = (
        "Automates browser interactions using Playwright. Supports navigation, "
        "form filling, clicking, content extraction, and waiting for dynamic content."
    )
    parameters: dict[str, str] = {
        "action": "Action to perform: navigate, click, fill, extract, submit, screenshot",
        "url": "Target URL (required for navigate, optional for other actions)",
        "selector": "CSS selector for element (required for click, fill, submit)",
        "value": "Value to fill or text to extract (optional)",
        "wait_for": "Selector or timeout in seconds to wait for (optional)",
    }

    def execute(self, arguments: dict[str, Any]) -> str:
        action = arguments.get("action", "").lower().strip()
        url = arguments.get("url", "").strip()
        selector = arguments.get("selector", "").strip()
        value = arguments.get("value", "").strip()
        wait_for = arguments.get("wait_for", "").strip()

        if not action:
            return "Error: No action specified."

        return asyncio.run(self._execute_async(action, url, selector, value, wait_for))

    async def _execute_async(
        self, action: str, url: str, selector: str, value: str, wait_for: str
    ) -> str:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return (
                "Error: Playwright not installed. Run: pip install playwright && playwright install"
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                if action == "navigate":
                    if not url:
                        return "Error: URL required for navigate action."
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    title = await page.title()
                    return f"Navigated to {url}. Page title: {title}"

                elif action == "click":
                    if not selector:
                        return "Error: Selector required for click action."
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.click(selector)
                    return f"Clicked element: {selector}"

                elif action == "fill":
                    if not selector or not value:
                        return "Error: Selector and value required for fill action."
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.fill(selector, value)
                    return f"Filled '{value}' into {selector}"

                elif action == "extract":
                    if not selector and not url:
                        return "Error: URL or selector required for extract action."
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    if selector:
                        element = await page.wait_for_selector(selector, timeout=10000)
                        text = await element.inner_text()
                        return f"Extracted content: {text[:500]}"
                    content = await page.content()
                    return f"Extracted page content: {content[:500]}"

                elif action == "submit":
                    if not selector:
                        return "Error: Selector required for submit action."
                    await page.wait_for_selector(selector, timeout=10000)
                    await page.click(selector)
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    return f"Submitted form at {selector}"

                elif action == "screenshot":
                    if not url:
                        return "Error: URL required for screenshot action."
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.screenshot(path="/tmp/playwright_screenshot.png")
                    return "Screenshot saved to /tmp/playwright_screenshot.png"

                else:
                    return (
                        f"Unknown action: {action}. "
                        "Supported: navigate, click, fill, extract, submit, screenshot"
                    )

            finally:
                await browser.close()


_playwright_tool = PlaywrightTool()
