"""
Zabbix MCP Server Users Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
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
                description="Number of results to skip (for pagination). Requires sortfield to be set.",
                ge=0,
            ),
        ] = 0,
        sortfield: Annotated[
            str | None,
            Field(default=None, description="Field to sort by."),
        ] = None,
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
            search: Dictionary with search criteria like {'alias': 'admin'} for username matching.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'users' list with user objects, 'count' of returned users,
                  and pagination metadata ('limit', 'offset').
                  Each user includes:
                  - userid: Unique user ID
                  - alias: Username login
                  - name: User's full name
                  - surname: User's last name
                  - type: User type (1=Zabbix user, 2=Zabbix admin, 3=Zabbix super admin)

        Note: Use user_create to add new users, user_delete to remove them.
        """
        try:
            await ctx.info("Retrieving users...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if userids:
                params["userids"] = userids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.user.get(**params)
                return {
                    "users": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving users: {e!s}")
            return {"error": str(e)}

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
            await ctx.error(f"Error creating user: {e!s}")
            return {"error": str(e)}

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
        type_: Annotated[
            int | None,
            Field(
                default=None,
                description="User type: 1=Zabbix user, 2=Zabbix admin, 3=Zabbix super admin.",
            ),
        ] = None,
    ) -> dict:
        """
        Update an existing user in Zabbix.

        Modifies properties of an existing user account. You can change name, surname,
        password, or user type. Only specify the fields you want to change.

        Args:
            userid: ID of the user to update (required). Find it with user_get.
            username: New username (not recommended - can cause issues).
            name: New first name.
            surname: New last name.
            passwd: New password.
            type_: New user type (1=user, 2=admin, 3=super admin).

        Returns:
            dict: Contains 'userids' list with updated user IDs and 'success' flag.
                  On error, contains 'error' key with the error message.
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
            if type_ is not None:
                params["type"] = type_

            async with ZabbixClient(config) as api:
                result = await api.user.update(**params)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating user: {e!s}")
            return {"error": str(e)}

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
        userids: Annotated[list[str], Field(description="User IDs to delete.")],
    ) -> dict:
        """
        Delete users from Zabbix.

        Permanently removes user accounts from the system. The user's access will be immediately revoked.
        Historical data and previous actions by the user are retained for audit purposes.

        Args:
            userids: List of user IDs to delete. Find them with user_get.

        Returns:
            dict: Contains 'userids' list with deleted user IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Warning: This action is permanent and immediate. Deleted users lose all access to Zabbix.
                 Consider disabling the user instead (modify type) if temporary removal is needed.
        """
        try:
            await ctx.info(f"Deleting users: {userids}...")
            async with ZabbixClient(config) as api:
                result = await api.user.delete(*userids)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting users: {e!s}")
            return {"error": str(e)}

    ##########################
    # Proxy Tools
    ##########################
