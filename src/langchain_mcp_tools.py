# Standard library imports
import asyncio
import logging
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    NoReturn,
    Tuple,
    Type,
)

# Third-party imports
try:
    from jsonschema_pydantic import jsonschema_to_pydantic  # type: ignore
    from langchain_core.tools import BaseTool, ToolException
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from pydantic import BaseModel
    from pympler import asizeof
except ImportError as e:
    print(f'\nError: Required package not found: {e}')
    print('Please ensure all required packages are installed\n')
    sys.exit(1)


async def convert_single_mcp_to_langchain_tools(
    server_name: str,
    server_config: Dict[str, Any],
    langchain_tools: List[BaseTool],
    ready_event: asyncio.Event,
    cleanup_event: asyncio.Event,
    logger: logging.Logger = logging.getLogger(__name__)
) -> None:
    """Convert MCP server tools to LangChain compatible tools
    and manage lifecycle.

    This async function initializes an MCP server connection, converts its
    tools to LangChain format, and manages the connection lifecycle.
    It adds the tools to the provided langchain_tools list and uses events
    for synchronization.

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dictionary containing command,
            args, and env
        langchain_tools: List to which the converted LangChain tools will
            be appended
        ready_event: Event to signal when tools are ready for use
        cleanup_event: Event to trigger cleanup and connection closure
        logger: Logger instance to use for logging events and errors.
               Defaults to module logger.

    Returns:
        None

    Raises:
        Exception: If there's an error in server connection or tool conversion
    """
    try:
        logger.info(f'MCP server "{server_name}": initializing with:',
                    server_config)

        # NOTE: `uv` and `npx` seem to require PATH to be set.
        # To avoid confusion, it was decided to automatically append it
        # to the env if not explicitly set by the config.
        env = dict(server_config.get('env', {}))
        if 'PATH' not in env:
            env['PATH'] = os.environ.get('PATH', '')

        server_params = StdioServerParameters(
            command=server_config['command'],
            args=server_config.get('args', []),
            env=env
        )

        @asynccontextmanager
        async def print_before_aexit(context_manager, message):
            yield await context_manager.__aenter__()
            logger.info(message)
            await context_manager.__aexit__(None, None, None)

        exit_stack = AsyncExitStack()

        stdio_transport = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport

        session = await exit_stack.enter_async_context(
            print_before_aexit(
                ClientSession(read, write),
                f'MCP server "{server_name}": session closed'
            )
        )

        await session.initialize()
        logger.info(f'MCP server "{server_name}": connected')

        tools_response = await session.list_tools()

        for tool in tools_response.tools:
            class McpLangChainTool(BaseTool):
                name: str = tool.name or 'NO NAME'
                description: str = tool.description or ''
                args_schema: Type[BaseModel] = jsonschema_to_pydantic(
                    tool.inputSchema
                )

                def _run(self, **kwargs: Any) -> NoReturn:
                    raise NotImplementedError(
                        'Only async operation is supported'
                    )

                async def _arun(self, **kwargs: Any) -> Any:
                    logger.info(f'MCP tool "{server_name}"/"{tool.name}"'
                                f' received input:', kwargs)
                    result = await session.call_tool(self.name, kwargs)
                    if result.isError:
                        raise ToolException(result.content)

                    size = asizeof.asizeof(result.content)
                    logger.info(f'MCP tool "{server_name}"/"{tool.name}" '
                                f'received result (size: {size})')
                    return result.content

            langchain_tools.append(McpLangChainTool())

        logger.info(f'MCP server "{server_name}": {len(langchain_tools)} '
                    f'tool(s) available:')
        for tool in langchain_tools:
            logger.info(f'- {tool.name}')
    except Exception as e:
        logger.info(f'Error getting response: {str(e)}')
        raise

    ready_event.set()

    await cleanup_event.wait()

    await exit_stack.aclose()


async def convert_mcp_to_langchain_tools(
    server_configs: Dict[str, Dict[str, Any]],
    logger: logging.Logger = logging.getLogger(__name__)
) -> Tuple[List[BaseTool], Callable[[], Coroutine[Any, Any, None]]]:
    """Initialize multiple MCP servers and convert their tools to
    LangChain format.

    This async function manages parallel initialization of multiple
    MCP servers, converts their tools to LangChain format, and provides
    a cleanup mechanism. It synchronizes server initialization using events
    and combines all tools into a single list.

    Args:
        server_configs: Dictionary mapping server names to their
            configurations, where each configuration contains command, args,
            and env settings
        logger: Logger instance to use for logging events and errors.
               Defaults to module logger.

    Returns:
        A tuple containing:
            - List of converted LangChain tools from all servers
            - Async cleanup function to properly shutdown all server
                connections

    Example:
        server_configs = {
            "server1": {"command": "npm", "args": ["start"]},
            "server2": {"command": "./server", "args": ["-p", "8000"]}
        }
        tools, cleanup = await convert_mcp_to_langchain_tools(server_configs)
        # Use tools...
        await cleanup()
    """
    tools_list = []
    ready_event_list = []
    cleanup_event_list = []

    tasks = []
    for server_name, server_config in server_configs.items():
        tools_out: List[BaseTool] = []
        tools_list.append(tools_out)
        ready_event = asyncio.Event()
        ready_event_list.append(ready_event)
        cleanup_event = asyncio.Event()
        cleanup_event_list.append(cleanup_event)
        task = asyncio.create_task(convert_single_mcp_to_langchain_tools(
            server_name,
            server_config,
            tools_out,
            ready_event,
            cleanup_event,
            logger
        ))
        tasks.append(task)

    for ready_event in ready_event_list:
        await ready_event.wait()

    langchain_tools = [item for sublist in tools_list for item in sublist]

    async def mcp_cleanup() -> None:
        for cleanup_event in cleanup_event_list:
            cleanup_event.set()

    logger.info(f'MCP servers initialized: {len(langchain_tools)} tool(s) '
                f'available in total')
    for tool in langchain_tools:
        logger.debug(f'- {tool.name}')

    return langchain_tools, mcp_cleanup
