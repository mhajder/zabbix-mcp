"""Read-only mode and DISABLED_TAGS filter by tag, so tags must match behaviour."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

README = Path(__file__).resolve().parent.parent / "README.md"


async def test_read_only_tag_matches_the_read_only_hint(mcp_server):
    """A write tool tagged read-only would stay exposed in READ_ONLY_MODE."""
    tools = await mcp_server.list_tools()
    assert tools
    for tool in tools:
        hint = tool.annotations.read_only_hint
        assert ("read-only" in tool.tags) is hint, tool.name
        if not hint:
            assert tool.annotations.destructive_hint is not None, tool.name


async def test_read_only_tools_are_gets_and_export(mcp_server):
    read_only = {t.name for t in await mcp_server.list_tools() if "read-only" in t.tags}
    assert {
        name
        for name in read_only
        if not name.endswith("_get") and name != "api_version"
    } == {"configuration_export"}
    assert "script_execute" not in read_only
    assert "event_acknowledge" not in read_only


async def test_every_tool_has_the_zabbix_tag_and_one_category(mcp_server):
    for tool in await mcp_server.list_tools():
        categories = tool.tags - {"zabbix", "read-only"}
        assert "zabbix" in tool.tags, tool.name
        assert len(categories) == 1, (tool.name, tool.tags)


async def test_readme_lists_every_tool(mcp_server):
    section = README.read_text().split("## 🧰 Available Tools")[1].split("\n## ")[0]
    documented = set(re.findall(r"^- `(\w+)`:", section, re.MULTILINE))
    assert documented == {t.name for t in await mcp_server.list_tools()}


async def test_readme_tag_examples_exist(mcp_server):
    """DISABLED_TAGS examples must name tags a user can actually disable."""
    tags = set().union(*(t.tags for t in await mcp_server.list_tools()))
    examples = re.findall(r"DISABLED_TAGS=([\w,-]+)", README.read_text())
    assert examples
    for example in examples:
        assert set(example.split(",")) <= tags, example
