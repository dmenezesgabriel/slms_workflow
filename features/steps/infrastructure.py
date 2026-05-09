"""Infrastructure adapters for BDD tests.

Provides port adapters for external dependencies:
- LLM server availability (external service)
- Environment setup/teardown

This module follows the Ports & Adapters pattern by isolating
infrastructure concerns from business logic in step definitions.
"""

from __future__ import annotations

import socket
from typing import Any


class LLMServerPort:
    """Port interface for LLM server connectivity."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        self._host = host
        self._port = port

    def is_available(self) -> bool:
        try:
            with socket.create_connection((self._host, self._port), timeout=1.0):
                return True
        except OSError:
            return False

    def create_client(self) -> Any:
        from src.providers.openai_local import OpenAILocalClient

        return OpenAILocalClient()


_default_llm_port = LLMServerPort()


def set_llm_port(port: LLMServerPort) -> None:
    global _default_llm_port
    _default_llm_port = port


def get_llm_port() -> LLMServerPort:
    return _default_llm_port


def check_server_availability(context: Any) -> None:
    port = get_llm_port()
    if not port.is_available():
        context.scenario.skip("LLM server not available at 127.0.0.1:8080")
        return

    context.llm_client = port.create_client()
