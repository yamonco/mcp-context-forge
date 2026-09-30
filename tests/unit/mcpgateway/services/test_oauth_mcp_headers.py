"""OAuth MCP group selection stays static across caller and hook headers."""

import pytest
from unittest.mock import AsyncMock

from mcpgateway.services.oauth_mcp_headers import apply_oauth_mcp_headers, oauth_mcp_headers
from mcpgateway.services.gateway_service import GatewayService


def test_static_group_overrides_untrusted_header_case_insensitively():
    headers = apply_oauth_mcp_headers(
        {"Authorization": "Bearer token", "x-mcp-tool-group-uid": "attacker"},
        {"mcp_tool_group_uid": "2PdT5OjlxW0"},
    )
    assert headers == {"Authorization": "Bearer token", "X-MCP-Tool-Group-UID": "2PdT5OjlxW0"}


@pytest.mark.parametrize("value", ["", "bad\nHeader: injected", "bad/other", 123, None])
def test_group_identifier_rejects_invalid_config(value):
    with pytest.raises(ValueError, match="mcp_tool_group_uid"):
        oauth_mcp_headers({"mcp_tool_group_uid": value})


def test_no_group_config_keeps_headers_unchanged():
    headers = {"Authorization": "Bearer token"}
    assert apply_oauth_mcp_headers(headers, {"grant_type": "authorization_code"}) == headers


@pytest.mark.asyncio
async def test_gateway_initialization_preserves_static_group_after_pre_auth_headers():
    service = GatewayService()
    service.connect_to_streamablehttp_server = AsyncMock(return_value=({}, [], [], [], []))
    try:
        await service._initialize_gateway(
            "https://api-langboard.yamon.io/mcp/stream",
            transport="streamablehttp",
            auth_type="oauth",
            oauth_config={"grant_type": "authorization_code", "mcp_tool_group_uid": "2PdT5OjlxW0"},
            pre_auth_headers={"Authorization": "Bearer token", "X-MCP-Tool-Group-UID": "attacker"},
            oauth_auto_fetch_tool_flag=True,
        )
        assert service.connect_to_streamablehttp_server.await_args.args[1] == {
            "Authorization": "Bearer token",
            "X-MCP-Tool-Group-UID": "2PdT5OjlxW0",
        }
    finally:
        await service._http_client.aclose()
