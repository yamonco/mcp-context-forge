"""Tests for the MCP 1.29 Streamable HTTP compatibility wrapper."""

from contextlib import asynccontextmanager

import httpx
import pytest

from mcpgateway.utils import streamable_http_client as compat


@pytest.mark.asyncio
async def test_legacy_options_configure_current_sdk_client(monkeypatch):
    """Headers and a numeric timeout reach the explicit HTTPX client."""
    captured = {}

    def factory(*, headers=None, timeout=None, auth=None):
        captured.update(headers=headers, timeout=timeout, auth=auth)
        return httpx.AsyncClient()

    @asynccontextmanager
    async def sdk_client(*, url, http_client, terminate_on_close):
        captured.update(url=url, http_client=http_client, terminate_on_close=terminate_on_close)
        yield ("read", "write", "session")

    monkeypatch.setattr(compat, "_streamable_http_client", sdk_client)

    async with compat.streamable_http_client(
        "https://mcp.example.test/mcp",
        headers={"Authorization": "Bearer token"},
        timeout=7,
        httpx_client_factory=factory,
        terminate_on_close=False,
    ) as streams:
        assert streams == ("read", "write", "session")

    assert captured["headers"] == {"Authorization": "Bearer token"}
    assert captured["timeout"] == httpx.Timeout(7)
    assert captured["auth"] is None
    assert captured["url"] == "https://mcp.example.test/mcp"
    assert captured["terminate_on_close"] is False
    assert captured["http_client"].is_closed
