# grazer-mcp

**Multi-platform content discovery for AI agents, over the [Model Context Protocol](https://modelcontextprotocol.io) (MCP).**

Grazer lets an agent *graze* worthy content across platforms — starting with
[BoTTube](https://bottube.ai) and an extensible set of sources — returning a
normalized result shape regardless of backend.

Part of the [Elyan Labs](https://elyanlabs.ai) agent ecosystem (RustChain, BoTTube,
Beacon). Sibling of [`rustchain-mcp`](https://github.com/Scottcjn/rustchain-mcp).

## Tools

| Tool | What it does |
|------|--------------|
| `graze_platforms()` | List supported platforms and their status |
| `graze_trending(platform, limit)` | Trending content on a platform |
| `graze_discover(query, platform, limit)` | Search / discover worthy content |
| `graze_feed(platforms, limit)` | Aggregated trending feed across platforms |

Every tool returns a **stable contract**: `{"ok": true, ...}` on success, or a
predictable `{"ok": false, "error": {code, message, retryable, source, details}}`
on failure — never a silent empty result, so clients treat upstream failures as
verification failures, not zero values.

## Install

```bash
pip install grazer-mcp
```

## Quick start (Claude Desktop)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "grazer": { "command": "grazer-mcp" }
  }
}
```

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `GRAZER_API_URL` | `https://bottube.ai` | Discovery backend base URL |
| `GRAZER_TIMEOUT` | `20` | Per-request timeout (seconds) |

## Platforms

| Platform | Status |
|----------|--------|
| `bottube` | live |

More sources resolve through the same backend as Grazer grows. Status in
`graze_platforms()` is kept honest — only `live` platforms are backed today.

## Development

```bash
python3 -m pytest -q          # or: python3 tests/test_client.py
```

The discovery logic lives in `grazer_mcp/client.py` (pure, network-mocked tests,
no MCP dependency); `grazer_mcp/server.py` is a thin MCP wrapper over it.

## License

MIT — see [LICENSE](LICENSE). © 2026 Scott Boudreaux / Elyan Labs LLC.
