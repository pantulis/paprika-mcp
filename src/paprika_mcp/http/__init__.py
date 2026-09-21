"""Remote (Streamable HTTP + OAuth) transport for paprika-mcp.

This subpackage exists alongside the stdio entrypoint in `paprika_mcp.server`
-- it does not replace it. Local MCP clients (e.g. Claude Code) keep using
stdio with no auth involved; this module is only for remote clients like
Gemini's custom-app connector, which require Streamable HTTP over OAuth 2.1.
"""
