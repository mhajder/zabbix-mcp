"""
Zabbix MCP Server Configuration Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_configuration_tools(mcp, config: ZabbixConfig):
    """Register Zabbix configuration tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "configuration", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def configuration_export(
        ctx: Context,
        format_type: Annotated[
            str,
            Field(
                default="json",
                description="Export format: 'json', 'xml', or 'yaml'.",
            ),
        ] = "json",
        prettyprint: Annotated[
            bool,
            Field(default=False, description="If true, returns pretty-printed output."),
        ] = False,
        templateids: Annotated[
            list[str] | None,
            Field(default=None, description="List of template IDs to export."),
        ] = None,
        hostids: Annotated[
            list[str] | None,
            Field(default=None, description="List of host IDs to export."),
        ] = None,
    ) -> dict:
        """
        Export Zabbix configurations.

        Exports monitored hosts, templates, and their complete configurations to JSON, XML, or YAML format.
        Useful for backup, migration, disaster recovery, or sharing configurations.

        When you export templates or hosts, the export includes:
        - All associated items (metrics/data sources)
        - All triggers and their dependencies
        - Discovery rules and prototypes
        - Graphs and visualizations
        - Macros and variable definitions
        - Host groups and interfaces (for hosts)
        - Inventory data (for hosts)
        - And all other configuration elements

        Args:
            format_type: Export format. Options:
                - 'json': JSON format (most compact and machine-friendly)
                - 'xml': XML format (human-readable, verbose)
                - 'yaml': YAML format (Zabbix 5.4+, human-readable and structured)
                Default is 'json'.
            prettyprint: If true, returns pretty-printed/indented output for readability. Default is false.
            templateids: List of specific template IDs to export. If provided, only these templates are exported.
                Omit or pass None to export all templates.
            hostids: List of specific host IDs to export. If provided, only these hosts are exported.
                Omit or pass None to export all hosts.

        Returns:
            dict: Contains:
                - 'content': The exported configuration in the requested format
                - 'success': Boolean indicating if export was successful
                - 'error': Error message if export failed

        Examples:
            Export all templates as pretty YAML:
                format_type='yaml', prettyprint=True

            Export specific host as compact JSON:
                format_type='json', prettyprint=False

            Export multiple templates for backup:
                format_type='xml', prettyprint=True

        Note:
            - Large exports may take time to complete
            - If no IDs specified, exports entire Zabbix configuration
            - Export can be used with configuration.import to restore or clone configurations
        """
        try:
            await ctx.info(f"Exporting configuration as {format_type}...")
            options: dict[str, Any] = {}

            if templateids:
                options["templates"] = templateids
            if hostids:
                options["hosts"] = hostids

            params: dict[str, Any] = {
                "format": format_type,
                "prettyprint": prettyprint,
                "options": options,
            }

            async with ZabbixClient(config) as api:
                result = await api.configuration.export(**params)
                return {"content": result, "success": True}
        except Exception as e:
            await ctx.error(f"Error exporting configuration: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "configuration"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def configuration_import(
        ctx: Context,
        content: Annotated[str, Field(description="Configuration content to import.")],
        format_type: Annotated[
            str,
            Field(
                default="json",
                description="Import format: 'json' or 'xml'.",
            ),
        ] = "json",
    ) -> dict:
        """
        Import configurations into Zabbix.

        Imports hosts, templates, and other configurations from JSON or XML format.
        Useful for migration, cloning, or restoring configurations.

        Args:
            content: Configuration content to import (JSON or XML string).
            format_type: Import format: 'json' or 'xml'. Default is 'json'.

        Returns:
            dict: Contains import result with created/updated object counts.
                  Returns success flag and summary of imported items.

        Warning: Importing can create or overwrite existing configurations.
                 Verify content before importing in production environments.
        """
        try:
            await ctx.info("Importing configuration...")
            params: dict[str, Any] = {"format": format_type, "source": content}

            async with ZabbixClient(config) as api:
                result = await api.configuration.import_config(**params)
                return {"result": result, "success": True}
        except Exception as e:
            await ctx.error(f"Error importing configuration: {e!s}")
            return {"error": str(e)}

    ##########################
    # SLA Tools
    ##########################
