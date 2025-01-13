# Standard library imports
from contextlib import AsyncExitStack, asynccontextmanager
import os
import sys
from typing import (
    List,
    Dict,
    Type,
    NoReturn,
    Callable,
    Coroutine,
    Any,
    Tuple,
    cast,
)
import asyncio

# Third-party imports
try:
    from langchain_core.tools import BaseTool, ToolException
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from pydantic import BaseModel
    from jsonschema_pydantic import jsonschema_to_pydantic  # type: ignore
    from pympler import asizeof
except ImportError as e:
    print(f'\nError: Required package not found: {e}')
    print('Please ensure all required packages are installed\n')
    sys.exit(1)


async def convert_single_mcp_to_langchain_tools(
    server_name: str,
    server_config: Dict[str, Any],
    langchain_tools,
    ready_event,
    cleanup_event
) -> None:
    """Convert MCP server tools to LangChain compatible tools.

    Args:
        server_name: Name of the server
        server_config: Server configuration dictionary

    Returns:
        Tuple containing list of LangChain tools and cleanup callback
    """
    try:
        print(f'MCP server "{server_name}": initializing with:', server_config)

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
            print(message)
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
        print(f'MCP server "{server_name}": connected')

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
                    print(f'MCP tool "{server_name}"/"{tool.name}"'
                          f' received input:', kwargs)
                    result = await session.call_tool(self.name, kwargs)
                    if result.isError:
                        raise ToolException(result.content)

                    size = asizeof.asizeof(result.content)
                    print(f'MCP tool "{server_name}"/"{tool.name}" received '
                          f'result (size: {size})')
                    return result.content

            langchain_tools.append(McpLangChainTool())

        print(f'MCP server "{server_name}": {len(langchain_tools)} tool(s) '
              f'available:')
        for tool in langchain_tools:
            print(f'- {tool.name}')
    except Exception as e:
        print(f'Error getting response: {str(e)}')
        raise

    ready_event.set()

    await cleanup_event.wait()

    await exit_stack.aclose()


async def convert_mcp_to_langchain_tools(
    server_configs: Dict[str, Dict[str, Any]], verbose=False
) -> Tuple[List[BaseTool], Callable[[], Coroutine[Any, Any, None]]]:
    """Convert multiple MCP servers' tools to LangChain tools.

    Args:
        server_configs: Dictionary of server configurations

    Returns:
        Tuple containing list of LangChain tools and cleanup callback
    """
    tools_list = []
    ready_event_list = []
    cleanup_event_list = []

    tasks = []
    for server_name, server_config in server_configs.items():
        tools_out: List[AsyncExitStack] = []
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
            cleanup_event
        ))
        tasks.append(task)

    for ready_event in ready_event_list:
        await ready_event.wait()

    langchain_tools = [item for sublist in tools_list for item in sublist]

    async def mcp_cleanup() -> None:
        for cleanup_event in cleanup_event_list:
            cleanup_event.set()

    print(f'MCP servers initialized: {len(langchain_tools)} tool(s) '
          f'available in total')
    if verbose:
        for tool in langchain_tools:
            print(f'- {tool.name}')

    return langchain_tools, mcp_cleanup
