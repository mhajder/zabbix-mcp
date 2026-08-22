"""
Zabbix MCP Server Configuration Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.errors import fail
from zabbix_mcp.zabbix_client import ZabbixClient

# Object types configuration.import accepts rules for. Zabbix only acts on the
# types named in 'rules', so anything missing here is silently not imported.
_IMPORTABLE = (
    "discoveryRules",
    "graphs",
    "host_groups",
    "hosts",
    "httptests",
    "images",
    "items",
    "maps",
    "mediaTypes",
    "template_groups",
    "templateDashboards",
    "templateLinkage",
    "templates",
    "triggers",
    "valueMaps",
)

# Not every type accepts every flag, and sending an unsupported one is a hard
# error. Both sets were read back from a Zabbix 7.4 server, not from the docs.
_NO_UPDATE = frozenset({"templateLinkage"})
_NO_DELETE = frozenset(
    {
        "host_groups",
        "hosts",
        "images",
        "maps",
        "mediaTypes",
        "template_groups",
        "templates",
    }
)


def _default_import_rules(delete_missing: bool) -> dict[str, dict[str, bool]]:
    """Build permissive import rules covering every supported object type.

    Args:
        delete_missing: Whether to also remove objects absent from the import.

    Returns:
        dict: Rules keyed by object type, as configuration.import expects.
    """
    rules: dict[str, dict[str, bool]] = {}
    for name in _IMPORTABLE:
        rule = {"createMissing": True}
        if name not in _NO_UPDATE:
            rule["updateExisting"] = True
        if delete_missing and name not in _NO_DELETE:
            rule["deleteMissing"] = True
        rules[name] = rule
    return rules


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
            templateids: Template IDs to export. Required unless hostids is given - there is
                no "export everything" option.
            hostids: Host IDs to export. Required unless templateids is given.

        Returns:
            dict: Contains:
                - 'content': The exported configuration in the requested format
                - 'success': Boolean indicating if export was successful

        Examples:
            Export all templates as pretty YAML:
                format_type='yaml', prettyprint=True

            Export specific host as compact JSON:
                format_type='json', prettyprint=False

            Export multiple templates for backup:
                format_type='xml', prettyprint=True

        Note:
            - Large exports may take time to complete
            - Zabbix exports only what the ids ask for. With no ids the API succeeds but
              returns an empty document containing just the version, so at least one of
              templateids or hostids is required here.
            - Export can be used with configuration.import to restore or clone configurations
        """
        try:
            await ctx.info(f"Exporting configuration as {format_type}...")
            if not templateids and not hostids:
                raise ValueError(
                    "Give at least one of 'templateids' or 'hostids'. Zabbix has no "
                    "export-everything option and returns an empty document instead. "
                    "Use template_get or host_get to collect the ids first."
                )

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
            await fail(ctx, "Error exporting configuration", e)

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
                description="Import format: 'json', 'xml' or 'yaml'.",
            ),
        ] = "json",
        rules: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Per-object import rules, e.g. {'hosts': {'createMissing': true, "
                    "'updateExisting': true}}. Defaults to creating and updating every "
                    "object type, without deleting anything."
                ),
            ),
        ] = None,
        delete_missing: Annotated[
            bool,
            Field(
                default=False,
                description="If true, the default rules also delete objects absent from the import. Ignored when 'rules' is given.",
            ),
        ] = False,
    ) -> dict:
        """
        Import configurations into Zabbix.

        Imports hosts, templates, and other configurations from JSON, XML or YAML.
        Useful for migration, cloning, or restoring configurations.

        Args:
            content: Configuration content to import (JSON, XML or YAML string).
            format_type: Import format: 'json', 'xml' or 'yaml'. Default is 'json'.
            rules: Per-object rules controlling what the import may do. Zabbix requires
                   this and applies nothing for object types the rules do not mention,
                   so omitting it silently imports nothing. When not given, a default
                   of createMissing + updateExisting for every supported object type is
                   sent.
            delete_missing: Extends the *default* rules with deleteMissing, removing
                   objects that exist in Zabbix but not in the import. Has no effect if
                   'rules' is supplied explicitly.

        Returns:
            dict: Contains import result with created/updated object counts.
                  Returns success flag and summary of imported items.

        Warning: Importing can create or overwrite existing configurations, and
                 delete_missing can remove them. Verify content before importing in
                 production environments.
        """
        try:
            await ctx.info("Importing configuration...")
            import_rules = (
                rules if rules is not None else _default_import_rules(delete_missing)
            )
            params: dict[str, Any] = {
                "format": format_type,
                "source": content,
                "rules": import_rules,
            }

            async with ZabbixClient(config) as api:
                result = await api.configuration.import_(**params)
                return {"result": result, "success": True}
        except Exception as e:
            await fail(ctx, "Error importing configuration", e)

    ##########################
    # SLA Tools
    ##########################
