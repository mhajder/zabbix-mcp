"""User and proxy tools."""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.asyncio


async def test_user_get_pages_by_userid(call_tool, zabbix):
    zabbix.queue(
        "user.get",
        "3",
        [{"userid": "1"}, {"userid": "2"}, {"userid": "3"}],
        [{"username": "guest", "userid": "3"}, {"username": "Admin", "userid": "2"}],
    )

    result = await call_tool(
        "user_get",
        {
            "userids": ["1", "2", "3"],
            "search": {"username": "a"},
            "filter_params": {"roleid": "3"},
            "output": ["username"],
            "offset": 1,
        },
    )

    # user.get omits the id unless asked for, so it is borrowed and dropped.
    assert result["users"] == [{"username": "Admin"}, {"username": "guest"}]
    assert result["has_more"] is False
    assert zabbix.params("user.get")[2] == {
        "userids": ["2", "3"],
        "search": {"username": "a"},
        "filter": {"roleid": "3"},
        "output": ["username", "userid"],
    }


async def test_user_get_count_output(call_tool, zabbix):
    zabbix.on("user.get", "2")

    assert await call_tool("user_get", {"count_output": True}) == {"total": 2}


async def test_user_create_update_delete(call_tool, zabbix):
    zabbix.on("user.create", {"userids": ["5"]})
    zabbix.on("user.update", {"userids": ["5"]})
    zabbix.on("user.delete", {"userids": ["5"]})
    groups = [{"usrgrpid": "7"}]

    assert await call_tool(
        "user_create",
        {
            "username": "jdoe",
            "passwd": "s3cret-Passw0rd",
            "usrgrps": groups,
            "name": "John",
            "surname": "Doe",
        },
    ) == {"userids": ["5"], "success": True}
    await call_tool(
        "user_create",
        {"username": "x", "passwd": "p", "usrgrps": groups, "roleid": "3"},
    )
    await call_tool(
        "user_update",
        {
            "userid": "5",
            "username": "jd",
            "name": "J",
            "surname": "D",
            "passwd": "n3w",
            "roleid": "2",
        },
    )
    await call_tool("user_update", {"userid": "5"})
    await call_tool("user_delete", {"userids": ["5"]})

    assert zabbix.calls == [
        (
            "user.create",
            {
                "username": "jdoe",
                "passwd": "s3cret-Passw0rd",
                "usrgrps": groups,
                "roleid": "1",
                "name": "John",
                "surname": "Doe",
            },
        ),
        (
            "user.create",
            {"username": "x", "passwd": "p", "usrgrps": groups, "roleid": "3"},
        ),
        (
            "user.update",
            {
                "userid": "5",
                "username": "jd",
                "name": "J",
                "surname": "D",
                "passwd": "n3w",
                "roleid": "2",
            },
        ),
        ("user.update", {"userid": "5"}),
        ("user.delete", ["5"]),
    ]


async def test_proxy_get(call_tool, zabbix):
    zabbix.queue("proxy.get", "1", [{"proxyid": "7"}])

    result = await call_tool(
        "proxy_get",
        {
            "proxyids": ["7"],
            "search": {"name": "dc1"},
            "filter_params": {"operating_mode": 0},
        },
    )

    assert result["proxies"] == [{"proxyid": "7"}]
    assert zabbix.params("proxy.get")[1] == {
        "proxyids": ["7"],
        "search": {"name": "dc1"},
        "filter": {"operating_mode": 0},
        "sortfield": "proxyid",
        "sortorder": "ASC",
        "output": "extend",
        "limit": 100,
    }


async def test_proxy_get_count_output(call_tool, zabbix):
    zabbix.on("proxy.get", "1")

    assert await call_tool("proxy_get", {"count_output": True}) == {"total": 1}


async def test_proxy_create_update_delete(call_tool, zabbix):
    zabbix.on("proxy.create", {"proxyids": ["7"]})
    zabbix.on("proxy.update", {"proxyids": ["7"]})
    zabbix.on("proxy.delete", {"proxyids": ["7"]})

    assert await call_tool(
        "proxy_create", {"name": "dc1", "operating_mode": 1, "description": "d"}
    ) == {"proxyids": ["7"], "success": True}
    await call_tool("proxy_create", {"name": "dc2"})
    await call_tool(
        "proxy_update",
        {"proxyid": "7", "name": "dc1b", "operating_mode": 0, "description": ""},
    )
    await call_tool("proxy_update", {"proxyid": "7"})
    await call_tool("proxy_delete", {"proxyids": ["7"]})

    assert zabbix.calls == [
        ("proxy.create", {"name": "dc1", "operating_mode": 1, "description": "d"}),
        ("proxy.create", {"name": "dc2", "operating_mode": 0}),
        (
            "proxy.update",
            {"proxyid": "7", "name": "dc1b", "operating_mode": 0, "description": ""},
        ),
        ("proxy.update", {"proxyid": "7"}),
        ("proxy.delete", ["7"]),
    ]


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "action"),
    [
        ("user_get", {}, "user.get", "Error retrieving users"),
        (
            "user_create",
            {"username": "u", "passwd": "p", "usrgrps": [{"usrgrpid": "7"}]},
            "user.create",
            "Error creating user",
        ),
        ("user_update", {"userid": "1"}, "user.update", "Error updating user"),
        ("user_delete", {"userids": ["1"]}, "user.delete", "Error deleting users"),
        ("proxy_get", {}, "proxy.get", "Error retrieving proxies"),
        ("proxy_create", {"name": "p"}, "proxy.create", "Error creating proxy"),
        ("proxy_update", {"proxyid": "1"}, "proxy.update", "Error updating proxy"),
        (
            "proxy_delete",
            {"proxyids": ["1"]},
            "proxy.delete",
            "Error deleting proxies",
        ),
    ],
)
async def test_zabbix_failures_become_tool_errors(
    call_tool, zabbix, tool, arguments, method, action
):
    zabbix.on(method, PermissionError("denied"))

    with pytest.raises(ToolError, match=f"^{action}: PermissionError: denied$"):
        await call_tool(tool, arguments)
