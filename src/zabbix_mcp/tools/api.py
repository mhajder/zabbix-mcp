"""
Zabbix MCP Server Api Tools
"""

from fastmcp import Context

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_api_tools(mcp, config: ZabbixConfig):
    """Register Zabbix api tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "api", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def api_version(ctx: Context) -> dict:
        """
        Get Zabbix API version information.

        This tool retrieves the current version of the Zabbix API you are connecting to.
        This is useful for understanding API capabilities and ensuring compatibility
        with specific features that may be version-dependent.

        Returns:
            dict: Contains 'version' key with the API version string (e.g., "6.0.10").
                  On error, contains 'error' key with the error message.
        """
        try:
            await ctx.info("Getting Zabbix API version...")
            async with ZabbixClient(config) as api:
                version = str(api.version)
                return {"version": version}
        except Exception as e:
            await ctx.error(f"Error getting API version: {e!s}")
            return {"error": str(e)}

    ##########################
    # Host Tools
    ##########################
