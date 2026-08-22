"""
Zabbix MCP Server Users Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.errors import fail
from zabbix_mcp.tools.pagination import fetch_page
from zabbix_mcp.tools.pagination import fetch_total
from zabbix_mcp.zabbix_client import ZabbixClient


def register_users_tools(mcp, config: ZabbixConfig):
    """Register Zabbix users tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "user", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def user_get(
        ctx: Context,
        userids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str | list[str], Field(default="extend")] = "extend",
        limit: Annotated[
            int,
            Field(
                default=100,
                description="Maximum number of results to return. Default is 100.",
                ge=1,
            ),
        ] = 100,
        offset: Annotated[
            int,
            Field(
                default=0,
                description="Number of matching records to skip. Use with 'limit' to page through results; check 'has_more' and 'total' in the response.",
                ge=0,
            ),
        ] = 0,
        sortfield: Annotated[
            str,
            Field(
                default="userid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "userid",
        sortorder: Annotated[
            str,
            Field(default="ASC", description="Sort direction - 'ASC' or 'DESC'."),
        ] = "ASC",
        count_output: Annotated[
            bool,
            Field(
                default=False,
                description="If true, returns only the count of matched objects as an integer.",
            ),
        ] = False,
    ) -> dict:
        """
        Get users from Zabbix.

        Users represent people with access to the Zabbix system. Each user has authentication
        credentials and permission level determining what they can view and modify.

        Args:
            userids: List of user IDs to get. If empty, returns all users.
            search: Dictionary with search criteria like {'username': 'admin'}. Zabbix 5.4
                    renamed 'alias' to 'username' and rejects the old name.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'users' list with user objects, 'count' of returned users,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each user includes:
                  - userid: Unique user ID
                  - username: Login name
                  - name: User's full name
                  - surname: User's last name
                  - roleid: The user's role, which determines permissions. Zabbix 5.2
                    replaced the numeric 'type' field with role objects.

        Note: Use user_create to add new users, user_delete to remove them.
        """
        try:
            await ctx.info("Retrieving users...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if userids:
                filters["userids"] = userids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.user, filters)}

                rows, total = await fetch_page(
                    api.user,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="userid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "users": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving users", e)

    @mcp.tool(
        tags={"zabbix", "user"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def user_create(
        ctx: Context,
        username: Annotated[str, Field(description="Username.")],
        passwd: Annotated[str, Field(description="Password.")],
        usrgrps: Annotated[
            list[dict[str, str]], Field(description="User groups [{'usrgrpid': '1'}].")
        ],
        name: Annotated[str | None, Field(default=None)] = None,
        surname: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Create a new user in Zabbix.

        Creates a new user account with specified credentials and group membership. New users
        inherit permissions from their assigned user groups.

        Args:
            username: Login username. Must be unique and alphanumeric.
            passwd: Password for the user account. Should follow security policy (min length, complexity).
            usrgrps: List of user group assignments in format [{'usrgrpid': 'group_id'}, ...].
                    Users inherit permissions from their groups. At least one group is required.
            name: User's first name (optional).
            surname: User's last name (optional).

        Returns:
            dict: Contains 'userids' list with newly created user ID(s) and 'success' flag.

        Note: New users receive default permissions from their assigned groups. Change passwords
              through user_update if needed. Username cannot be changed after creation.
        """
        try:
            await ctx.info(f"Creating user '{username}'...")
            params: dict[str, Any] = {
                "username": username,
                "passwd": passwd,
                "usrgrps": usrgrps,
            }
            if name:
                params["name"] = name
            if surname:
                params["surname"] = surname

            async with ZabbixClient(config) as api:
                result = await api.user.create(**params)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await fail(ctx, "Error creating user", e)

    @mcp.tool(
        tags={"zabbix", "user"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def user_update(
        ctx: Context,
        userid: Annotated[str, Field(description="ID of the user to update.")],
        username: Annotated[str | None, Field(default=None)] = None,
        name: Annotated[str | None, Field(default=None)] = None,
        surname: Annotated[str | None, Field(default=None)] = None,
        passwd: Annotated[str | None, Field(default=None)] = None,
        roleid: Annotated[
            str | None,
            Field(
                default=None,
                description="ID of the user's role, which is what grants permissions. Roles are objects in Zabbix 5.2+; the old numeric user 'type' no longer exists.",
            ),
        ] = None,
    ) -> dict:
        """
        Update an existing user in Zabbix.

        Modifies properties of an existing user account. You can change name, surname,
        password, or role. Only specify the fields you want to change.

        Args:
            userid: ID of the user to update (required). Find it with user_get.
            username: New username (not recommended - can cause issues).
            name: New first name.
            surname: New last name.
            passwd: New password.
            roleid: New role for the user. Zabbix 5.2 replaced the numeric user type
                    (1=user, 2=admin, 3=super admin) with role objects, and the default
                    roles keep those ids - 'User role' is 1, 'Admin role' 2, 'Super admin
                    role' 3. Confirm against your instance with role.get.

        Returns:
            dict: Contains 'userids' list with updated user IDs and 'success' flag.
        """
        try:
            await ctx.info(f"Updating user {userid}...")
            params: dict[str, Any] = {"userid": userid}
            if username is not None:
                params["username"] = username
            if name is not None:
                params["name"] = name
            if surname is not None:
                params["surname"] = surname
            if passwd is not None:
                params["passwd"] = passwd
            if roleid is not None:
                params["roleid"] = roleid

            async with ZabbixClient(config) as api:
                result = await api.user.update(**params)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await fail(ctx, "Error updating user", e)

    @mcp.tool(
        tags={"zabbix", "user"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def user_delete(
        ctx: Context,
        userids: Annotated[
            list[str],
            Field(description="User IDs to delete.", min_length=1),
        ],
    ) -> dict:
        """
        Delete users from Zabbix.

        Permanently removes user accounts from the system. The user's access will be immediately revoked.
        Historical data and previous actions by the user are retained for audit purposes.

        Args:
            userids: List of user IDs to delete. Find them with user_get.

        Returns:
            dict: Contains 'userids' list with deleted user IDs and 'success' flag.

        Warning: This action is permanent and immediate. Deleted users lose all access to Zabbix.
                 Consider disabling the user instead (modify type) if temporary removal is needed.
        """
        try:
            await ctx.info(f"Deleting users: {userids}...")
            async with ZabbixClient(config) as api:
                result = await api.user.delete(*userids)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await fail(ctx, "Error deleting users", e)

    ##########################
    # Proxy Tools
    ##########################
