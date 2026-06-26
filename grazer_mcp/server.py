#!/usr/bin/env python3
"""
grazer-mcp — Multi-platform content discovery for AI agents, over MCP.

Grazer lets an agent "graze" worthy content across platforms (BoTTube and an
extensible set of sources), returning a normalized shape regardless of backend.

Tools:
  graze_platforms()                       list supported platforms + status
  graze_trending(platform, limit)         trending content on a platform
  graze_discover(query, platform, limit)  search/discover worthy content
  graze_feed(platforms, limit)            aggregated cross-platform feed

Config (env): GRAZER_API_URL (default https://bottube.ai), GRAZER_TIMEOUT (20).

Every tool returns {"ok": true, ...} or a predictable {"ok": false, "error": {...}}
object — never a silent empty result.
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import GrazerClient

mcp = FastMCP("grazer-mcp")
_client = GrazerClient()


@mcp.tool()
def graze_platforms() -> dict:
    """List the content platforms grazer can discover across, with status."""
    return _client.platforms()


@mcp.tool()
def graze_trending(platform: str = "bottube", limit: int = 10) -> dict:
    """Return trending content on a platform. platform: see graze_platforms(); limit 1-50."""
    return _client.trending(platform, limit)


@mcp.tool()
def graze_discover(query: str, platform: str = "bottube", limit: int = 10) -> dict:
    """Search/discover worthy content matching `query` on a platform. limit 1-50."""
    return _client.discover(query, platform, limit)


@mcp.tool()
def graze_feed(platforms: Optional[list[str]] = None, limit: int = 10) -> dict:
    """Aggregated trending feed across platforms (default: all live ones). limit per platform 1-50."""
    return _client.feed(platforms, limit)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
