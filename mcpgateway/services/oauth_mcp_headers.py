# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/services/oauth_mcp_headers.py
Copyright contributors to the MCP-CONTEXT-FORGE project
SPDX-License-Identifier: Apache-2.0

Static, validated MCP headers carried by an OAuth gateway configuration.
"""

import re
from typing import Any, Mapping


_GROUP_UID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def oauth_mcp_headers(oauth_config: Mapping[str, Any] | None) -> dict[str, str]:
    """Return the configured tool group header without accepting arbitrary headers.

    A group selects a catalog; the OAuth bearer token still determines the
    caller's identity and permissions at the upstream MCP server.
    """
    if not oauth_config or "mcp_tool_group_uid" not in oauth_config:
        return {}
    group_uid = oauth_config["mcp_tool_group_uid"]
    if not isinstance(group_uid, str) or not _GROUP_UID.fullmatch(group_uid):
        raise ValueError("mcp_tool_group_uid must be a 1-128 character MCP group identifier")
    return {"X-MCP-Tool-Group-UID": group_uid}


def apply_oauth_mcp_headers(headers: dict[str, str], oauth_config: Mapping[str, Any] | None) -> dict[str, str]:
    """Ensure caller, passthrough, and hook headers cannot override the static group."""
    static_headers = oauth_mcp_headers(oauth_config)
    if static_headers:
        headers = {key: value for key, value in headers.items() if key.lower() != "x-mcp-tool-group-uid"}
        headers.update(static_headers)
    return headers
