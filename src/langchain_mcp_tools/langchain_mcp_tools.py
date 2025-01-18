# Standard library imports
import asyncio
from anyio.streams.memory import (
    MemoryObjectReceiveStream, 
    MemoryObjectSendStream,
)
import logging
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    NoReturn,
    Tuple,
    Type,
    TypeAlias,
)

# Third-party imports
try:
    from jsonschema_pydantic import jsonschema_to_pydantic  # type: ignore
    from langchain_core.tools import BaseTool, ToolException
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import mcp.types as mcp_types
    from pydantic import BaseModel
    from pympler import asizeof
except ImportError as e:
    print(f'\nError: Required package not found: {e}')
    print('Please ensure all required packages are installed\n')
    sys.exit(1)


StdioTransport: TypeAlias = tuple[
    MemoryObjectReceiveStream[mcp_types.JSONRPCMessage | Exception],
    MemoryObjectSendStream[mcp_types.JSONRPCMessage]
]

async def spawn_mcp_server_and_get_transport(
    server_name: str,
    server_config: Dict[str, Any],
    exit_stack: AsyncExitStack,
    logger: logging.Logger = logging.getLogger(__name__)
) -> StdioTransport:
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

        stdio_transport = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
    except Exception as e:
        logger.error(f'Error spawning MCP server: {str(e)}')
        raise

    return stdio_transport


async def get_mcp_server_tools(
    server_name: str,
    stdio_transport: StdioTransport,
    exit_stack: AsyncExitStack,
    logger: logging.Logger = logging.getLogger(__name__)
) -> List[BaseTool]:
    try:
        read, write = stdio_transport

        # Use an intermediate `asynccontextmanager` to log the cleanup message
        @asynccontextmanager
        async def log_before_aexit(context_manager, message):
            yield await context_manager.__aenter__()
            try:
                logger.info(message)
            finally:
                await context_manager.__aexit__(None, None, None)

        session = await exit_stack.enter_async_context(
            log_before_aexit(
                ClientSession(read, write),
                f'MCP server "{server_name}": session closed'
            )
        )

        await session.initialize()
        logger.info(f'MCP server "{server_name}": connected')

        # Get MCP tools
        tools_response = await session.list_tools()

        # Wrap MCP tools to into LangChain tools
        langchain_tools: List[BaseTool] = []
        for tool in tools_response.tools:
            class McpToLangChainAdapter(BaseTool):
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

            langchain_tools.append(McpToLangChainAdapter())

        logger.info(f'MCP server "{server_name}": {len(langchain_tools)} '
                    f'tool(s) available:')
        for tool in langchain_tools:
            logger.info(f'- {tool.name}')
    except Exception as e:
        logger.error(f'Error getting MCP tools: {str(e)}')
        raise

    return langchain_tools


McpServerCleanupFn = Callable[[], Awaitable[None]]


async def convert_mcp_to_langchain_tools(
    server_configs: Dict[str, Dict[str, Any]],
    logger: logging.Logger = logging.getLogger(__name__)
) -> Tuple[List[BaseTool], McpServerCleanupFn]:
    """Initialize multiple MCP servers and convert their tools to
    LangChain format.

    This async function manages parallel initialization of multiple MCP
    servers, converts their tools to LangChain format, and provides a cleanup
    mechanism. It orchestrates the full lifecycle of multiple servers.

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

    # Concurrently initialize all the MCP servers
    stdio_transports: List[StdioTransport] = []
    async_exit_stack = AsyncExitStack()
    for server_name, server_config in server_configs.items():
        # NOTE: the following `await` only blocks until the server subprocess
        # is spawned, i.e. after returning from the `await`, the spawned
        # subprocess starts its initialization independently of (so in
        # parallel with) the Python execution of the following lines.
        stdio_transport = await spawn_mcp_server_and_get_transport(
            server_name,
            server_config,
            async_exit_stack,
            logger
        )
        stdio_transports.append(stdio_transport)

    langchain_tools: List[BaseTool] = []
    for (server_name, server_config), stdio_transport in zip(
        server_configs.items(),
        stdio_transports,
        strict=True
    ):
        tools = await get_mcp_server_tools(
            server_name,
            stdio_transport,
            async_exit_stack,
            logger
        )
        langchain_tools.extend(tools)

    # Define a cleanup callback to set cleanup_event and signal that
    # it is time to clean up the resources
    async def mcp_cleanup() -> None:    
        await async_exit_stack.aclose()

    logger.info(f'MCP servers initialized: {len(langchain_tools)} tool(s) '
                f'available in total')
    for tool in langchain_tools:
        logger.debug(f'- {tool.name}')

    return langchain_tools, mcp_cleanup
