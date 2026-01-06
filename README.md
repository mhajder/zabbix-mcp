# Zabbix MCP Server

Zabbix MCP Server is a Python-based Model Context Protocol (MCP) server designed to provide advanced, programmable access to Zabbix monitoring data and management features. It exposes a modern API for querying, automating, and integrating Zabbix resources such as hosts, templates, triggers, items, problems, events, users, proxies, maintenance periods, and more. The server supports both read and write operations, robust security features, and is suitable for integration with AI assistants, automation tools, dashboards, and custom monitoring workflows.

## Features

### Core Features

- Query Zabbix hosts, templates, items, triggers, and host groups with flexible filtering
- Retrieve problems, events, and alerts with severity filtering
- Access history and trend data for monitored items
- Monitor trigger states and problem severity
- Manage maintenance periods and scheduled downtimes
- Retrieve user macros and configuration data
- Get SLA and service information

### Management Operations

- Create, update, and delete hosts, templates, and host groups (if enabled)
- Manage triggers, items, and discovery rules
- Configure maintenance periods and user macros
- Execute scripts on monitored hosts
- Acknowledge events and close problems
- Create and manage users and proxies
- Support for bulk operations on hosts and templates

### Advanced Capabilities

- Rate limiting and API security features
- Read-only mode to restrict all write operations for safe monitoring
- Bearer token authentication for HTTP transport
- Comprehensive logging and audit trails
- SSL/TLS support and configurable timeouts
- Multiple transport options (STDIO, SSE, HTTP)
- Optional Sentry integration for error tracking

## Installation

### Prerequisites

- Python 3.11, 3.12 or 3.13
- Access to a Zabbix server (5.4+)
- Valid Zabbix API token or user credentials with appropriate permissions

### Quick Install from PyPI

The easiest way to get started is to install from PyPI:

```sh
# Using UV (recommended)
uvx zabbix-mcp

# Or using pip
pip install zabbix-mcp
```

Remember to configure the environment variables for your Zabbix instance before running the server:

```sh
# Create environment configuration
export ZABBIX_URL=https://zabbix.example.com/api_jsonrpc.php
export ZABBIX_TOKEN=your-zabbix-api-token
```

### Install from Source

1. Clone the repository:

```sh
git clone https://github.com/mhajder/zabbix-mcp.git
cd zabbix-mcp
```

2. Install dependencies:

```sh
# Using UV (recommended)
uv sync

# Or using pip
pip install -e .
```

3. Configure environment variables:

```sh
cp .env.example .env
# Edit .env with your Zabbix URL and credentials
```

4. Run the server:

```sh
# Using UV
uv run python run_server.py

# Or directly with Python
python run_server.py

# Or using the installed script
zabbix-mcp
```

### Using Docker

Docker images are available on GitHub Packages for easy deployment.

```sh
# Normal STDIO image
docker pull ghcr.io/mhajder/zabbix-mcp:latest

# MCPO image for usage with Open WebUI
docker pull ghcr.io/mhajder/zabbix-mcpo:latest
```

### Development Setup

For development with additional tools:

```sh
# Clone and install with development dependencies
git clone https://github.com/mhajder/zabbix-mcp.git
cd zabbix-mcp
uv sync --group dev

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/

# Run linting and formatting
uv run ruff check .
uv run ruff format .

# Setup pre-commit hooks
uv run pre-commit install
```

## Configuration

### Environment Variables

```env
# Zabbix Connection Details
ZABBIX_URL=https://zabbix.example.com/api_jsonrpc.php

# Authentication - use EITHER token OR user/password
# API Token (preferred for Zabbix 5.4+)
ZABBIX_TOKEN=your-api-token
# OR Username/Password (for older versions)
# ZABBIX_USER=Admin
# ZABBIX_PASSWORD=zabbix

# SSL Configuration
ZABBIX_VERIFY_SSL=true
ZABBIX_TIMEOUT=30
ZABBIX_SKIP_VERSION_CHECK=false

# Read-Only Mode
# Set READ_ONLY_MODE true to disable all write operations (create, update, delete)
READ_ONLY_MODE=false

# Disabled Tags
# Comma-separated list of tags to disable tools for (empty by default)
# Example: DISABLED_TAGS=host,user,maintenance
DISABLED_TAGS=

# Logging Configuration
LOG_LEVEL=INFO

# Rate Limiting
# Set RATE_LIMIT_ENABLED true to enable rate limiting
RATE_LIMIT_ENABLED=false
RATE_LIMIT_MAX_REQUESTS=60
RATE_LIMIT_WINDOW_MINUTES=1

# Sentry Error Tracking (Optional)
# Set SENTRY_DSN to enable error tracking and performance monitoring
# SENTRY_DSN=https://your-key@o12345.ingest.us.sentry.io/6789
# Optional Sentry configuration
# SENTRY_TRACES_SAMPLE_RATE=1.0
# SENTRY_SEND_DEFAULT_PII=true
# SENTRY_ENVIRONMENT=production
# SENTRY_RELEASE=1.2.3
# SENTRY_PROFILE_SESSION_SAMPLE_RATE=1.0
# SENTRY_PROFILE_LIFECYCLE=trace
# SENTRY_ENABLE_LOGS=true

# MCP Transport Configuration
# Transport type: 'stdio' (default), 'sse' (Server-Sent Events), or 'http' (HTTP Streamable)
MCP_TRANSPORT=stdio

# HTTP Transport Settings (used when MCP_TRANSPORT=sse or MCP_TRANSPORT=http)
# Host to bind the HTTP server (default: 0.0.0.0 for all interfaces)
MCP_HTTP_HOST=0.0.0.0
# Port to bind the HTTP server (default: 8000)
MCP_HTTP_PORT=8000
# Optional bearer token for authentication (leave empty for no auth)
MCP_HTTP_BEARER_TOKEN=
```

## Available Tools

### API Information

- `api_version`: Get Zabbix API version information

### Host Management

- `host_get`: List hosts with optional filtering by groups, templates, proxies, and search criteria
- `host_create`: Create a new host with interfaces and template linking
- `host_update`: Update host properties (name, status, description)
- `host_delete`: Delete hosts by ID

### Host Group Management

- `hostgroup_get`: List host groups with optional filtering
- `hostgroup_create`: Create a new host group
- `hostgroup_update`: Update an existing host group's properties (name)
- `hostgroup_delete`: Delete host groups

### Template Management

- `template_get`: List templates with optional filtering
- `template_create`: Create a new template
- `template_update`: Update template properties (name, description)
- `template_delete`: Delete templates

### Item Management

- `item_get`: List items with optional filtering by hosts, groups, templates
- `item_create`: Create a new item on a host
- `item_update`: Update item properties (name, delay, units, description, status)
- `item_delete`: Delete items

### Trigger Management

- `trigger_get`: List triggers with severity and state filtering
- `trigger_create`: Create a new trigger with expression
- `trigger_update`: Update trigger properties (description, expression, priority, status, comments)
- `trigger_delete`: Delete triggers

### Problem & Event Management

- `problem_get`: Get current problems with severity and time filtering
- `event_get`: Get events with time range filtering
- `event_acknowledge`: Acknowledge events with optional messages

### History & Trends

- `history_get`: Get historical data for items
- `trend_get`: Get trend data for items

### User Management

- `user_get`: List users with optional filtering
- `user_create`: Create a new user
- `user_update`: Update user properties (name, surname, password, type)
- `user_delete`: Delete users

### Proxy Management

- `proxy_get`: List proxies with optional filtering
- `proxy_create`: Create a new proxy
- `proxy_update`: Update proxy properties (name, operating mode, description)
- `proxy_delete`: Delete proxies

### Maintenance Management

- `maintenance_get`: List maintenance periods
- `maintenance_create`: Create a new maintenance period
- `maintenance_update`: Update maintenance period properties (name, times, description)
- `maintenance_delete`: Delete maintenance periods

### Action & Media

- `action_get`: List actions (triggers, autoregistration, etc.)
- `mediatype_get`: List media types

### Graph & Discovery

- `graph_get`: List graphs with optional filtering
- `discoveryrule_get`: List LLD discovery rules
- `drule_get`: List network discovery rules
- `itemprototype_get`: Get item prototypes from discovery rules

### SLA & Services

- `sla_get`: List SLAs
- `service_get`: List services

### Scripts

- `script_get`: List scripts
- `script_execute`: Execute a script on a host

### User Macros

- `usermacro_get`: List user macros (host and global)
- `usermacro_create`: Create a host macro
- `usermacro_delete`: Delete host macros

### Configuration Management

- `configuration_export`: Export Zabbix configurations to JSON or XML
- `configuration_import`: Import Zabbix configurations from JSON or XML

## Security & Safety Features

### Read-Only Mode

The server supports a read-only mode that disables all write operations for safe monitoring:

```env
READ_ONLY_MODE=true
```

### Tag-Based Tool Filtering

You can disable specific categories of tools by setting disabled tags:

```env
DISABLED_TAGS=alert,bills
```

### Rate Limiting

The server supports rate limiting to control API usage and prevent abuse. If enabled, requests are limited per client using a sliding window algorithm.

Enable rate limiting by setting the following environment variables in your `.env` file:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=100   # Maximum requests allowed per window
RATE_LIMIT_WINDOW_MINUTES=1   # Window size in minutes
```

If `RATE_LIMIT_ENABLED` is set to `true`, the server will apply rate limiting middleware. Adjust `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_MINUTES` as needed for your environment.

### Sentry Error Tracking & Monitoring (Optional)

The server optionally supports **Sentry** for error tracking, performance monitoring, and debugging. Sentry integration is completely optional and only initialized if configured.

#### Installation

To enable Sentry monitoring, install the optional dependency:

```sh
# Using UV (recommended)
uv sync --extra sentry
```

#### Configuration

Enable Sentry by setting the `SENTRY_DSN` environment variable in your `.env` file:

```env
# Required: Sentry DSN for your project
SENTRY_DSN=https://your-key@o12345.ingest.us.sentry.io/6789

# Optional: Performance monitoring sample rate (0.0-1.0, default: 1.0)
SENTRY_TRACES_SAMPLE_RATE=1.0

# Optional: Include personally identifiable information (default: true)
SENTRY_SEND_DEFAULT_PII=true

# Optional: Environment name (e.g., "production", "staging")
SENTRY_ENVIRONMENT=production

# Optional: Release version (auto-detected from package if not set)
SENTRY_RELEASE=1.2.3

# Optional: Profiling - continuous profiling sample rate (0.0-1.0, default: 1.0)
SENTRY_PROFILE_SESSION_SAMPLE_RATE=1.0

# Optional: Profiling - lifecycle mode for profiling (default: "trace")
# Options: "all", "continuation", "trace"
SENTRY_PROFILE_LIFECYCLE=trace

# Optional: Enable log capture as breadcrumbs and events (default: true)
SENTRY_ENABLE_LOGS=true
```

#### Features

When enabled, Sentry automatically captures:

- **Exceptions & Errors**: All unhandled exceptions with full context
- **Performance Metrics**: Request/response times and traces
- **MCP Integration**: Detailed MCP server activity and interactions
- **Logs & Breadcrumbs**: Application logs and event trails for debugging
- **Context Data**: Environment, client info, and request parameters

#### Getting a Sentry DSN

1. Create a free account at [sentry.io](https://sentry.io)
2. Create a new Python project
3. Copy your DSN from the project settings
4. Set it in your `.env` file

#### Disabling Sentry

Sentry is completely optional. If you don't set `SENTRY_DSN`, the server will run normally without any Sentry integration, and no monitoring data will be collected.

### SSL/TLS Configuration

The server supports SSL certificate verification and custom timeout settings:

```env
ZABBIX_VERIFY_SSL=true    # Enable SSL certificate verification
ZABBIX_TIMEOUT=30         # Connection timeout in seconds
```

### Transport Configuration

The server supports multiple transport mechanisms for the MCP protocol:

#### STDIO Transport (Default)

The default transport uses standard input/output for communication. This is ideal for local usage and integration with tools that communicate via stdin/stdout:

```env
MCP_TRANSPORT=stdio
```

#### HTTP SSE Transport (Server-Sent Events)

For network-based deployments, you can use HTTP with Server-Sent Events. This allows the MCP server to be accessed over HTTP with real-time streaming:

```env
MCP_TRANSPORT=sse
MCP_HTTP_HOST=0.0.0.0        # Bind to all interfaces (or specific IP)
MCP_HTTP_PORT=8000           # Port to listen on
MCP_HTTP_BEARER_TOKEN=your-secret-token  # Optional authentication token
```

When using SSE transport with a bearer token, clients must include the token in their requests:

```bash
curl -H "Authorization: Bearer your-secret-token" http://localhost:8000/sse
```

#### HTTP Streamable Transport

The HTTP Streamable transport provides HTTP-based communication with request/response streaming. This is ideal for web integrations and tools that need HTTP endpoints:

```env
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0        # Bind to all interfaces (or specific IP)
MCP_HTTP_PORT=8000           # Port to listen on
MCP_HTTP_BEARER_TOKEN=your-secret-token  # Optional authentication token
```

When using streamable transport with a bearer token:

```sh
curl -H "Authorization: Bearer your-secret-token" \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
     http://localhost:8000/mcp
```

**Note**: The HTTP transport requires proper JSON-RPC formatting with `jsonrpc` and `id` fields. The server may also require session initialization for some operations.

For more information on FastMCP transports, see the [FastMCP documentation](https://gofastmcp.com/deployment/running-server#transport-protocols).

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and ensure code quality (`uv run pytest && uv run ruff check .`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see LICENSE file for details.
