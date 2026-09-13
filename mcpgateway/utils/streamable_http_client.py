# -*- coding: utf-8 -*-
"""Compatibility wrapper for the MCP Streamable HTTP client.

MCP 1.29 moved HTTP configuration onto an explicit ``httpx.AsyncClient``.
ContextForge still has call sites that supply the earlier ``headers``,
``timeout``, and ``httpx_client_factory`` arguments, including custom CA and
mTLS client factories.  This wrapper keeps that internal contract while using
the current SDK API.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional

import httpx
from mcp.client.streamable_http import create_mcp_http_client
from mcp.client.streamable_http import streamable_http_client as _streamable_http_client


HttpxClientFactory = Callable[
    [Optional[dict[str, str]], Optional[httpx.Timeout], Optional[httpx.Auth]],
    httpx.AsyncClient,
]


@asynccontextmanager
async def streamable_http_client(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    timeout: Optional[httpx.Timeout | float] = None,
    httpx_client_factory: Optional[HttpxClientFactory] = None,
    terminate_on_close: bool = True,
) -> AsyncIterator[tuple]:
    """Open a current MCP Streamable HTTP transport with legacy options."""
    normalized_timeout = httpx.Timeout(timeout) if isinstance(timeout, (int, float)) else timeout
    factory = httpx_client_factory or create_mcp_http_client
    client = factory(headers=headers, timeout=normalized_timeout, auth=None)

    async with client:
        async with _streamable_http_client(
            url=url,
            http_client=client,
            terminate_on_close=terminate_on_close,
        ) as streams:
            yield streams
