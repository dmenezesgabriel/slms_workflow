from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.tools import web_fetch


class TestUrlValidation:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com",
            "https://localhost/path",
            "https://127.0.0.1/path",
            "https://10.0.0.1/path",
            "https://[::1]/path",
        ],
    )
    def test_rejects_unsupported_or_internal_urls(self, url: str) -> None:
        error = web_fetch.validate_public_http_url(url)

        assert error is not None

    def test_accepts_public_url_when_dns_resolves_to_public_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        getaddrinfo = MagicMock(return_value=[(None, None, None, None, ("93.184.216.34", 443))])
        monkeypatch.setattr("src.tools.web_fetch.socket.getaddrinfo", getaddrinfo)

        error = web_fetch.validate_public_http_url("https://example.com/path")

        assert error is None

    def test_rejects_hostname_that_resolves_to_private_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        getaddrinfo = MagicMock(return_value=[(None, None, None, None, ("192.168.1.10", 443))])
        monkeypatch.setattr("src.tools.web_fetch.socket.getaddrinfo", getaddrinfo)

        error = web_fetch.validate_public_http_url("https://example.com/path")

        assert error == "Internal network URLs are not allowed."
