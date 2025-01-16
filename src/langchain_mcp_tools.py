# Standard library imports
import asyncio
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


"""
Resource Management Pattern for Parallel Server Initialization
--------------------------------------------------------------
This code implements a specific pattern for managing async resources that
require context managers while enabling parallel initialization.
The key aspects are:

1. Challenge:

   A key requirement for parallel initialization is that each server must be
   initialized in its own dedicated task - there's no way around this as far as
   I know. However, this poses a challenge when combined with
   `asynccontextmanager`.

   - Resources management for `stdio_client` and `ClientSession` seems
     to require relying exclusively on `asynccontextmanager` for cleanup,
     with no manual cleanup options
     (based on the mcp python-sdk impl as of Jan 14, 2025)
   - Initializing multiple MCP servers in parallel requires a dedicated
     `asyncio.Task` per server
   - Server cleanup can be initiated later by a task other than the one that
     initialized the resources

2. Solution:

   The key insight is to keep the initialization tasks alive throughout the
   session lifetime, rather than letting them complete after initialization.

   By using `asyncio.Event`s for coordination, we can:
   - Allow parallel initialization while maintaining proper context management
   - Keep each initialization task running until explicit cleanup is requested
   - Ensure cleanup occurs in the same task that created the resources
   - Provide a clean interface for the caller to manage the lifecycle

   Alternative Considered:
   A generator/coroutine approach using `finally` block for cleanup was
   considered but rejected because:
   - It turned out that the `finally` block in a generator/coroutine can be
     executed by a different task than the one that ran the main body of
     the code
   - This breaks the requirement that `AsyncExitStack.aclose()` must be
     called from the same task that created the context

3. Task Lifecycle:

   The following task lifecyle diagram illustrates how the above strategy
   was impelemented:
   ```
   [Task starts]
     ↓
   Initialize server & convert tools
     ↓
   Set ready_event (signals tools are ready)
     ↓
   await cleanup_event.wait() (keeps task alive)
     ↓
   When cleanup_event is set:
   exit_stack.aclose() (cleanup in original task)
   ```
This approach indeed enables parallel initialization while maintaining proper
async resource lifecycle management through context managers.
However, I'm afraid I'm twisting things around too much.
It usually means I'm doing something very worng...

I think it is a natural assumption that MCP SDK is designed with consideration
for parallel server initialization.
I'm not sure what I'm missing...
(FYI, with the TypeScript MCP SDK, parallel initialization was
pretty straightforward.
"""


async def spawn_mcp_server_tools_task(
    server_name: str,
    server_config: Dict[str, Any],
    langchain_tools: List[BaseTool],
    ready_event: asyncio.Event,
    cleanup_event: asyncio.Event,
    logger: logging.Logger = logging.getLogger(__name__)
) -> None:
    """Convert MCP server tools to LangChain compatible tools
    and manage lifecycle.

    This task initializes an MCP server connection, converts its tools
    to LangChain format, and manages the connection lifecycle.
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
        async def log_before_aexit(context_manager, message):
            yield await context_manager.__aenter__()
            logger.info(message)
            await context_manager.__aexit__(None, None, None)

        exit_stack = AsyncExitStack()

        stdio_transport = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport

        session = await exit_stack.enter_async_context(
            log_before_aexit(
                ClientSession(read, write),
                f'MCP server "{server_name}": session closed'
            )
        )

        await session.initialize()
        logger.info(f'MCP server "{server_name}": connected')

        tools_response = await session.list_tools()

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
        logger.error(f'Error getting response: {str(e)}')
        raise

    ready_event.set()

    await cleanup_event.wait()

    await exit_stack.aclose()


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
    per_server_tools = []
    ready_event_list = []
    cleanup_event_list = []

    tasks = []
    for server_name, server_config in server_configs.items():
        server_tools_accumulator: List[BaseTool] = []
        per_server_tools.append(server_tools_accumulator)
        ready_event = asyncio.Event()
        ready_event_list.append(ready_event)
        cleanup_event = asyncio.Event()
        cleanup_event_list.append(cleanup_event)
        task = asyncio.create_task(spawn_mcp_server_tools_task(
            server_name,
            server_config,
            server_tools_accumulator,
            ready_event,
            cleanup_event,
            logger
        ))
        tasks.append(task)

    await asyncio.gather(*(event.wait() for event in ready_event_list))

    langchain_tools = [
        item for sublist in per_server_tools for item in sublist
    ]

    async def mcp_cleanup() -> None:
        for event in cleanup_event_list:
            event.set()

    logger.info(f'MCP servers initialized: {len(langchain_tools)} tool(s) '
                f'available in total')
    for tool in langchain_tools:
        logger.debug(f'- {tool.name}')

    return langchain_tools, mcp_cleanup
