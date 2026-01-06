from pydantic import BaseModel
from pydantic import Field


class ZabbixConfig(BaseModel):
    """Configuration for Zabbix API connection"""

    zabbix_url: str = Field(
        ...,
        description="Zabbix API URL, e.g. https://zabbix.example.com/api_jsonrpc.php",
    )
    # Authentication - either token OR user/password
    token: str | None = Field(
        None, description="Zabbix API token (preferred for Zabbix 5.4+)"
    )
    user: str | None = Field(
        None, description="Zabbix username (for user/password auth)"
    )
    password: str | None = Field(
        None, description="Zabbix password (for user/password auth)"
    )
    # Connection settings
    verify_ssl: bool = Field(True, description="Verify SSL certificates (true/false)")
    timeout: int = Field(30, description="Request timeout in seconds")
    skip_version_check: bool = Field(
        False, description="Skip Zabbix API version compatibility check"
    )
    # Server behavior
    read_only_mode: bool = Field(False, description="Read-only mode (true/false)")
    disabled_tags: set[str] = Field(
        default_factory=set, description="Set of tags to disable tools for"
    )
    # Rate limiting
    rate_limit_enabled: bool = Field(
        False, description="Enable rate limiting (true/false)"
    )
    rate_limit_max_requests: int = Field(60, description="Maximum requests per window")
    rate_limit_window_minutes: int = Field(
        1, description="Rate limit window in minutes"
    )


class TransportConfig(BaseModel):
    """Configuration for MCP transport layer"""

    transport_type: str = Field(
        "stdio",
        description="Transport type: 'stdio', 'sse' (Server-Sent Events), or 'http' (HTTP Streamable)",
    )
    # HTTP transport settings (for both SSE and HTTP Streamable)
    http_host: str = Field(
        "0.0.0.0", description="Host to bind for HTTP transports (SSE/HTTP Streamable)"
    )
    http_port: int = Field(
        8000, description="Port to bind for HTTP transports (SSE/HTTP Streamable)"
    )
    http_bearer_token: str | None = Field(
        None, description="Bearer token for HTTP authentication"
    )
