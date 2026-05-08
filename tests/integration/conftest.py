"""
Integration test fixtures.

These tests require a running llama.cpp server at 127.0.0.1:8080.
Run with:  pytest tests/integration/ -m integration
Skip with: pytest -m 'not integration'  (default)
"""

from __future__ import annotations

import socket

import pytest


def _llm_server_available(host: str = "127.0.0.1", port: int = 8080) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def llm_client() -> object:
    """Return an OpenAILocalClient, skipping the session if the server is unreachable."""
    if not _llm_server_available():
        pytest.skip("LLM server not available at 127.0.0.1:8080 — start llama.cpp first")
    from src.providers.openai_local import OpenAILocalClient

    return OpenAILocalClient()
