#!/usr/bin/env python3
"""
Zabbix MCP Server

Provides a Model Context Protocol (MCP) server exposing tools that interact with the Zabbix API.
"""

import logging
import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware

from zabbix_mcp.sentry_init import init_sentry
from zabbix_mcp.zabbix_client import get_transport_config_from_env
from zabbix_mcp.zabbix_client import get_zabbix_config_from_env
from zabbix_mcp.zabbix_middlewares import DisabledTagsMiddleware
from zabbix_mcp.zabbix_middlewares import ReadOnlyTagMiddleware
from zabbix_mcp.zabbix_tools import register_tools

# Load environment variables
load_dotenv()

# Initialize optional Sentry monitoring
init_sentry()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get package version
try:
    __version__ = version("zabbix-mcp")
except PackageNotFoundError:
    __version__ = "0.0.1"

try:
    ZABBIX_CONFIG = get_zabbix_config_from_env()
    TRANSPORT_CONFIG = get_transport_config_from_env()
except Exception as e:
    logger.error(f"Invalid configuration: {e}")
    raise

# Create auth provider if bearer token is configured
auth_provider = None
if getattr(TRANSPORT_CONFIG, "http_bearer_token", None):
    auth_provider = StaticTokenVerifier(
        tokens={
            TRANSPORT_CONFIG.http_bearer_token: {
                "client_id": "authenticated-client",
                "scopes": ["read", "write"],
            }
        }
    )

# Initialize FastMCP server
mcp = FastMCP(
    name="Zabbix MCP Server",
    version=__version__,
    instructions=(
        "This MCP server exposes tools for interacting with the Zabbix API, "
        "supporting both read and write operations if not in read-only mode. "
        "Use these tools to manage hosts, templates, triggers, items, problems, "
        "events, users, proxies, maintenance periods, and more."
    ),
    auth=auth_provider,
)

# Register all tools
register_tools(mcp, ZABBIX_CONFIG)

# Apply disabled tags middleware if any tags are disabled
if getattr(ZABBIX_CONFIG, "disabled_tags", set()):
    logger.info(
        f"Disabled tags configured: {ZABBIX_CONFIG.disabled_tags} - applying middleware"
    )
    mcp.add_middleware(DisabledTagsMiddleware(ZABBIX_CONFIG.disabled_tags))

# Enforce read-only behavior via middleware
if getattr(ZABBIX_CONFIG, "read_only_mode", False):
    logger.info("Read-only mode is enabled - applying middleware")
    mcp.add_middleware(ReadOnlyTagMiddleware())

# Optional rate limiting
if getattr(ZABBIX_CONFIG, "rate_limit_enabled", False):
    logger.info("Rate limiting is enabled - applying middleware")
    mcp.add_middleware(
        SlidingWindowRateLimitingMiddleware(
            max_requests=ZABBIX_CONFIG.rate_limit_max_requests,
            window_minutes=ZABBIX_CONFIG.rate_limit_window_minutes,
        )
    )


def main():
    # Basic validation - need either token OR user/password
    has_token = bool(ZABBIX_CONFIG.token)
    has_user_pass = bool(ZABBIX_CONFIG.user and ZABBIX_CONFIG.password)

    if not ZABBIX_CONFIG.zabbix_url:
        logger.error("Missing required Zabbix URL (ZABBIX_URL). Check your .env file.")
        raise SystemExit(1)

    if not has_token and not has_user_pass:
        logger.error(
            "Missing Zabbix authentication. Provide either ZABBIX_TOKEN or both ZABBIX_USER and ZABBIX_PASSWORD."
        )
        raise SystemExit(1)

    auth_method = "token" if has_token else "user/password"
    logger.info(
        f"Starting Zabbix MCP Server connecting to {ZABBIX_CONFIG.zabbix_url} (auth: {auth_method})..."
    )

    # Choose transport based on configuration
    if TRANSPORT_CONFIG.transport_type == "sse":
        logger.info(
            f"Using HTTP SSE transport on {TRANSPORT_CONFIG.http_host}:{TRANSPORT_CONFIG.http_port}"
        )
        if TRANSPORT_CONFIG.http_bearer_token:
            logger.info("Bearer token authentication enabled for SSE transport")

        # Run with HTTP SSE transport
        mcp.run(
            transport="sse",
            host=TRANSPORT_CONFIG.http_host,
            port=TRANSPORT_CONFIG.http_port,
        )
    elif TRANSPORT_CONFIG.transport_type == "http":
        logger.info(
            f"Using HTTP Streamable transport on {TRANSPORT_CONFIG.http_host}:{TRANSPORT_CONFIG.http_port}"
        )
        if TRANSPORT_CONFIG.http_bearer_token:
            logger.info("Bearer token authentication enabled for Streamable transport")

        # Run with HTTP Streamable transport
        mcp.run(
            transport="http",
            host=TRANSPORT_CONFIG.http_host,
            port=TRANSPORT_CONFIG.http_port,
        )
    else:
        # Default to STDIO transport
        logger.info("Using STDIO transport")
        mcp.run()


if __name__ == "__main__":
    main()
