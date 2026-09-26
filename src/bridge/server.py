#!/usr/bin/env python3
"""claude-muse-bridge: MCP server entry point.

Lets Claude read briefs/reports produced by Muse (or anyone) via MCP tools.

Run locally (stdio):
    BRIDGE_BRIEFS_DIR=~/briefs python -m bridge.server

Run hosted (streamable HTTP, API-key auth):
    BRIDGE_TRANSPORT=http BRIDGE_API_KEY=secret BRIDGE_BACKEND=azure \\
        BRIDGE_STORAGE_ACCOUNT=... BRIDGE_SAS_TOKEN=... python -m bridge.server

CLI flags override env vars: --transport, --backend, --briefs-dir, --port.
"""

from __future__ import annotations

import argparse
import os
import sys

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from bridge.backends import get_backend
from bridge.config import Settings, load_settings

SERVER_INSTRUCTIONS = (
    "A bridge to documents ('briefs') produced by another AI assistant. "
    "Use list_briefs to see what is available, get_latest_brief for the newest "
    "brief, or get_brief for a specific one by name. Briefs are markdown reports "
    "with data and recommendations — ground your answers in them."
)


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    """Simple shared-secret auth for the hosted HTTP transport."""

    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request, call_next):
        if request.headers.get("x-api-key") != self.api_key:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def create_server(settings: Settings) -> MCPServer:
    backend = get_backend(settings)
    server = MCPServer("claude-muse-bridge", instructions=SERVER_INSTRUCTIONS)

    @server.tool()
    def list_briefs() -> list[str]:
        """List available briefs, oldest first."""
        names = backend.list_briefs()
        if not names:
            return ["No briefs found. Ask the producer to publish one first."]
        return names

    @server.tool()
    def get_latest_brief() -> str:
        """Return the newest brief (markdown): data, findings, recommendations."""
        try:
            name, content = backend.read_latest()
        except FileNotFoundError:
            return "No briefs found. Ask the producer to publish one first."
        return f"# {name}\n\n{content}"

    @server.tool()
    def get_brief(name: str) -> str:
        """Return one brief by name (see list_briefs)."""
        try:
            return backend.read_brief(name)
        except FileNotFoundError:
            return f"Brief not found: {name}"

    return server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="claude-muse-bridge MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"])
    parser.add_argument("--backend", choices=["local", "azure"])
    parser.add_argument("--briefs-dir")
    parser.add_argument("--port", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = load_settings()
    if args.transport:
        settings.transport = args.transport
    if args.backend:
        settings.backend = args.backend
    if args.briefs_dir:
        from pathlib import Path

        settings.briefs_dir = Path(args.briefs_dir).expanduser()
    if args.port:
        settings.port = args.port
    settings.validate()

    server = create_server(settings)

    if settings.transport == "stdio":
        server.run(transport="stdio")
    else:
        app = server.streamable_http_app()
        app.add_middleware(_ApiKeyMiddleware, api_key=settings.api_key)
        print(
            f"Serving MCP on http://{settings.host}:{settings.port}/mcp "
            f"(backend={settings.backend})",
            file=sys.stderr,
        )
        uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
