import logging

from fastmcp.exceptions import PromptError
from fastmcp.exceptions import ResourceError
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware import MiddlewareContext

logger = logging.getLogger(__name__)


class ReadOnlyTagMiddleware(Middleware):
    """
    Middleware that disables all tools, resources, or prompts that do NOT have the 'read-only' tag.

    In read-only mode, only components explicitly marked as read-only (via tag) are enabled and visible.
    All others are disabled and hidden from lists.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Disable tool execution if the tool is not marked as read-only (by tag).
        """
        if context.fastmcp_context:
            tool = await context.fastmcp_context.fastmcp.get_tool(context.message.name)
            tags = getattr(tool, "tags", set())
            name = getattr(tool, "name", repr(tool))
            if "read-only" not in tags:
                logger.debug(f"[READ-ONLY] Disabling tool: {name} (tags: {tags})")
                if hasattr(tool, "disable"):
                    tool.disable()
                raise ToolError("This tool is disabled in read-only mode.")
            else:
                logger.debug(f"[READ-ONLY] Allowing tool: {name} (tags: {tags})")

        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """
        Disable resource access if the resource is not marked as read-only (by tag).
        """
        if context.fastmcp_context:
            resource = await context.fastmcp_context.fastmcp.get_resource(
                context.message.uri
            )
            tags = getattr(resource, "tags", set())
            name = getattr(resource, "name", repr(resource))
            if "read-only" not in tags:
                logger.debug(f"[READ-ONLY] Disabling resource: {name} (tags: {tags})")
                if hasattr(resource, "disable"):
                    resource.disable()
                raise ResourceError("This resource is disabled in read-only mode.")
            else:
                logger.debug(f"[READ-ONLY] Allowing resource: {name} (tags: {tags})")

        return await call_next(context)

    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        """
        Disable prompt access if the prompt is not marked as read-only (by tag).
        """
        if context.fastmcp_context:
            prompt = await context.fastmcp_context.fastmcp.get_prompt(
                context.message.name
            )
            tags = getattr(prompt, "tags", set())
            name = getattr(prompt, "name", repr(prompt))
            if "read-only" not in tags:
                logger.debug(f"[READ-ONLY] Disabling prompt: {name} (tags: {tags})")
                if hasattr(prompt, "disable"):
                    prompt.disable()
                raise PromptError("This prompt is disabled in read-only mode.")
            else:
                logger.debug(f"[READ-ONLY] Allowing prompt: {name} (tags: {tags})")

        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """
        Only show tools that are marked as read-only (by tag); disable and hide all others.
        """
        result = await call_next(context)
        if context.fastmcp_context:
            filtered = []
            for tool in result:
                tags = getattr(tool, "tags", set())
                name = getattr(tool, "name", repr(tool))
                if "read-only" in tags:
                    logger.debug(
                        f"[READ-ONLY] Allowing tool in list: {name} (tags: {tags})"
                    )
                    filtered.append(tool)
                else:
                    logger.debug(
                        f"[READ-ONLY] Disabling tool in list: {name} (tags: {tags})"
                    )
                    if hasattr(tool, "disable"):
                        tool.disable()
            return filtered
        return result

    async def on_list_resources(self, context: MiddlewareContext, call_next):
        """
        Only show resources that are marked as read-only (by tag); disable and hide all others.
        """
        result = await call_next(context)
        if context.fastmcp_context:
            filtered = []
            for resource in result:
                tags = getattr(resource, "tags", set())
                name = getattr(resource, "name", repr(resource))
                if "read-only" in tags:
                    logger.debug(
                        f"[READ-ONLY] Allowing resource in list: {name} (tags: {tags})"
                    )
                    filtered.append(resource)
                else:
                    logger.debug(
                        f"[READ-ONLY] Disabling resource in list: {name} (tags: {tags})"
                    )
                    if hasattr(resource, "disable"):
                        resource.disable()
            return filtered
        return result

    async def on_list_prompts(self, context: MiddlewareContext, call_next):
        """
        Only show prompts that are marked as read-only (by tag); disable and hide all others.
        """
        result = await call_next(context)
        if context.fastmcp_context:
            filtered = []
            for prompt in result:
                tags = getattr(prompt, "tags", set())
                name = getattr(prompt, "name", repr(prompt))
                if "read-only" in tags:
                    logger.debug(
                        f"[READ-ONLY] Allowing prompt in list: {name} (tags: {tags})"
                    )
                    filtered.append(prompt)
                else:
                    logger.debug(
                        f"[READ-ONLY] Disabling prompt in list: {name} (tags: {tags})"
                    )
                    if hasattr(prompt, "disable"):
                        prompt.disable()
            return filtered
        return result


class DisabledTagsMiddleware(Middleware):
    """
    Middleware that disables all tools, resources, or prompts that have any of the specified disabled tags.

    Tools/resources/prompts with any tag in the disabled_tags set will be disabled and hidden from lists.
    """

    def __init__(self, disabled_tags: set[str]):
        """
        Initialize the middleware with a set of disabled tags.

        Args:
            disabled_tags: Set of tags that should disable tools/resources/prompts
        """
        self.disabled_tags = disabled_tags
        logger.info(
            f"DisabledTagsMiddleware initialized with disabled tags: {disabled_tags}"
        )

    def _has_disabled_tag(self, tags: set[str]) -> bool:
        """Check if any of the item's tags are in the disabled tags set."""
        return bool(self.disabled_tags.intersection(tags))

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Disable tool execution if the tool has any disabled tag.
        """
        if context.fastmcp_context:
            tool = await context.fastmcp_context.fastmcp.get_tool(context.message.name)
            tags = getattr(tool, "tags", set())
            name = getattr(tool, "name", repr(tool))

            if self._has_disabled_tag(tags):
                disabled_tags_found = self.disabled_tags.intersection(tags)
                logger.debug(
                    f"[DISABLED-TAGS] Disabling tool: {name} (disabled tags found: {disabled_tags_found})"
                )
                if hasattr(tool, "disable"):
                    tool.disable()
                raise ToolError(
                    f"This tool is disabled due to disabled tags: {disabled_tags_found}"
                )
            else:
                logger.debug(f"[DISABLED-TAGS] Allowing tool: {name} (tags: {tags})")

        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """
        Disable resource access if the resource has any disabled tag.
        """
        if context.fastmcp_context:
            resource = await context.fastmcp_context.fastmcp.get_resource(
                context.message.uri
            )
            tags = getattr(resource, "tags", set())
            name = getattr(resource, "name", repr(resource))

            if self._has_disabled_tag(tags):
                disabled_tags_found = self.disabled_tags.intersection(tags)
                logger.debug(
                    f"[DISABLED-TAGS] Disabling resource: {name} (disabled tags found: {disabled_tags_found})"
                )
                if hasattr(resource, "disable"):
                    resource.disable()
                raise ResourceError(
                    f"This resource is disabled due to disabled tags: {disabled_tags_found}"
                )
            else:
                logger.debug(
                    f"[DISABLED-TAGS] Allowing resource: {name} (tags: {tags})"
                )

        return await call_next(context)

    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        """
        Disable prompt access if the prompt has any disabled tag.
        """
        if context.fastmcp_context:
            prompt = await context.fastmcp_context.fastmcp.get_prompt(
                context.message.name
            )
            tags = getattr(prompt, "tags", set())
            name = getattr(prompt, "name", repr(prompt))

            if self._has_disabled_tag(tags):
                disabled_tags_found = self.disabled_tags.intersection(tags)
                logger.debug(
                    f"[DISABLED-TAGS] Disabling prompt: {name} (disabled tags found: {disabled_tags_found})"
                )
                if hasattr(prompt, "disable"):
                    prompt.disable()
                raise PromptError(
                    f"This prompt is disabled due to disabled tags: {disabled_tags_found}"
                )
            else:
                logger.debug(f"[DISABLED-TAGS] Allowing prompt: {name} (tags: {tags})")

        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """
        Only show tools that don't have any disabled tags; disable and hide all others.
        """
        result = await call_next(context)
        if context.fastmcp_context:
            filtered = []
            for tool in result:
                tags = getattr(tool, "tags", set())
                name = getattr(tool, "name", repr(tool))

                if self._has_disabled_tag(tags):
                    disabled_tags_found = self.disabled_tags.intersection(tags)
                    logger.debug(
                        f"[DISABLED-TAGS] Disabling tool in list: {name} (disabled tags found: {disabled_tags_found})"
                    )
                    if hasattr(tool, "disable"):
                        tool.disable()
                else:
                    logger.debug(
                        f"[DISABLED-TAGS] Allowing tool in list: {name} (tags: {tags})"
                    )
                    filtered.append(tool)
            return filtered
        return result

    async def on_list_resources(self, context: MiddlewareContext, call_next):
        """
        Only show resources that don't have any disabled tags; disable and hide all others.
        """
        result = await call_next(context)
        if context.fastmcp_context:
            filtered = []
            for resource in result:
                tags = getattr(resource, "tags", set())
                name = getattr(resource, "name", repr(resource))

                if self._has_disabled_tag(tags):
                    disabled_tags_found = self.disabled_tags.intersection(tags)
                    logger.debug(
                        f"[DISABLED-TAGS] Disabling resource in list: {name} (disabled tags found: {disabled_tags_found})"
                    )
                    if hasattr(resource, "disable"):
                        resource.disable()
                else:
                    logger.debug(
                        f"[DISABLED-TAGS] Allowing resource in list: {name} (tags: {tags})"
                    )
                    filtered.append(resource)
            return filtered
        return result

    async def on_list_prompts(self, context: MiddlewareContext, call_next):
        """
        Only show prompts that don't have any disabled tags; disable and hide all others.
        """
        result = await call_next(context)
        if context.fastmcp_context:
            filtered = []
            for prompt in result:
                tags = getattr(prompt, "tags", set())
                name = getattr(prompt, "name", repr(prompt))

                if self._has_disabled_tag(tags):
                    disabled_tags_found = self.disabled_tags.intersection(tags)
                    logger.debug(
                        f"[DISABLED-TAGS] Disabling prompt in list: {name} (disabled tags found: {disabled_tags_found})"
                    )
                    if hasattr(prompt, "disable"):
                        prompt.disable()
                else:
                    logger.debug(
                        f"[DISABLED-TAGS] Allowing prompt in list: {name} (tags: {tags})"
                    )
                    filtered.append(prompt)
            return filtered
        return result
