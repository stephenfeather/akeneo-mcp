from __future__ import annotations

import logging

from .server import get_settings, mcp


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.settings.host = settings.mcp_bind_host
    mcp.settings.port = settings.mcp_bind_port
    mcp.settings.streamable_http_path = "/mcp"
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
