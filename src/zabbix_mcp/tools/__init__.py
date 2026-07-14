"""
Zabbix MCP Server Tools package
"""

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.actions import register_actions_tools
from zabbix_mcp.tools.api import register_api_tools
from zabbix_mcp.tools.configuration import register_configuration_tools
from zabbix_mcp.tools.discovery import register_discovery_tools
from zabbix_mcp.tools.graphs import register_graphs_tools
from zabbix_mcp.tools.history import register_history_tools
from zabbix_mcp.tools.hosts import register_hosts_tools
from zabbix_mcp.tools.items import register_items_tools
from zabbix_mcp.tools.macros import register_macros_tools
from zabbix_mcp.tools.maintenance import register_maintenance_tools
from zabbix_mcp.tools.mediatypes import register_mediatypes_tools
from zabbix_mcp.tools.problems import register_problems_tools
from zabbix_mcp.tools.proxies import register_proxies_tools
from zabbix_mcp.tools.scripts import register_scripts_tools
from zabbix_mcp.tools.services import register_services_tools
from zabbix_mcp.tools.sla import register_sla_tools
from zabbix_mcp.tools.templates import register_templates_tools
from zabbix_mcp.tools.triggers import register_triggers_tools
from zabbix_mcp.tools.users import register_users_tools


def register_tools(mcp, config: ZabbixConfig):
    """Register all Zabbix tools with the MCP server"""
    register_api_tools(mcp, config)
    register_hosts_tools(mcp, config)
    register_templates_tools(mcp, config)
    register_items_tools(mcp, config)
    register_triggers_tools(mcp, config)
    register_problems_tools(mcp, config)
    register_history_tools(mcp, config)
    register_users_tools(mcp, config)
    register_proxies_tools(mcp, config)
    register_maintenance_tools(mcp, config)
    register_actions_tools(mcp, config)
    register_mediatypes_tools(mcp, config)
    register_graphs_tools(mcp, config)
    register_discovery_tools(mcp, config)
    register_configuration_tools(mcp, config)
    register_sla_tools(mcp, config)
    register_services_tools(mcp, config)
    register_scripts_tools(mcp, config)
    register_macros_tools(mcp, config)
