# Standard library imports
import argparse
import asyncio
from enum import Enum
import json
import logging
import sys
from pathlib import Path
from typing import (
    Any,
    cast,
)

# Third-party imports
try:
    from dotenv import load_dotenv
    from langchain.chat_models import init_chat_model
    from langchain.schema import (
        AIMessage,
        BaseMessage,
        HumanMessage,
        SystemMessage,
    )
    from langchain_core.runnables.base import Runnable
    from langchain_core.messages.tool import ToolMessage
    from langgraph.prebuilt import create_react_agent
    from langchain_mcp_tools import (
        convert_mcp_to_langchain_tools,
        McpServerCleanupFn,
    )
except ImportError as e:
    print(f"\nError: Required package not found: {e}")
    print("Please ensure all required packages are installed\n")
    sys.exit(1)

# Local application imports
from config_loader import load_config

# Type definitions
ConfigType = dict[str, Any]


# ANSI color escape codes
class Colors(str, Enum):
    YELLOW = "\033[33m"  # color to yellow
    CYAN = "\033[36m"    # color to cyan
    RESET = "\033[0m"    # reset color

    def __str__(self):
        return self.value


def parse_arguments() -> argparse.Namespace:
    """Parse and return command line args for config path and verbosity."""
    parser = argparse.ArgumentParser(
        description="CLI Chat Application",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-c", "--config",
        default="llm_mcp_config.json5",
        help="path to config file",
        type=Path,
        metavar="PATH"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="run with verbose logging"
    )
    return parser.parse_args()


def init_logger(verbose: bool) -> logging.Logger:
    """Initialize and return a logger with appropriate verbosity level."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="\x1b[90m[%(levelname)s]\x1b[0m %(message)s"
    )
    return logging.getLogger()


def print_colored(text: str, color: Colors, end: str = "\n") -> None:
    """Print text in specified color and reset afterwards."""
    print(f"{color}{text}{Colors.RESET}", end=end)


def set_color(color: Colors) -> None:
    """Set terminal color."""
    print(color, end="")


def clear_line() -> None:
    """Move up one line and clear it."""
    print("\x1b[1A\x1b[2K", end="")


async def get_user_query(remaining_queries: list[str]) -> str | None:
    """Get user input or next example query, handling empty inputs
    and quit commands."""
    set_color(Colors.YELLOW)
    query = input("Query: ").strip()

    if len(query) == 0:
        if len(remaining_queries) > 0:
            query = remaining_queries.pop(0)
            clear_line()
            print_colored(f"Example Query: {query}", Colors.YELLOW)
        else:
            set_color(Colors.RESET)
            print("\nPlease type a query, or 'quit' or 'q' to exit\n")
            return await get_user_query(remaining_queries)

    print(Colors.RESET)  # Reset after input

    if query.lower() in ["quit", "q"]:
        print_colored("Goodbye!\n", Colors.CYAN)
        return None

    return query


async def handle_conversation(
    agent: Runnable,
    messages: list[BaseMessage],
    example_queries: list[str],
    verbose: bool
) -> None:
    """Manage an interactive conversation loop between the user and AI agent.

    Args:
        agent (Runnable): The initialized ReAct agent that processes queries
        messages (list[BaseMessage]): List to maintain conversation history
        example_queries (list[str]): list of example queries that can be used
            when user presses Enter
        verbose (bool): Flag to control detailed output of tool responses

    Exception handling:
    - TypeError: Ensures response is in correct string format
    - General exceptions: Allows conversation to continue after errors

    The conversation continues until user types "quit" or "q".
    """
    print("\nConversation started. "
          "Type 'quit' or 'q' to end the conversation.\n")
    if len(example_queries) > 0:
        print("Example Queries (just type Enter to supply them one by one):")
        for ex_q in example_queries:
            print(f"- {ex_q}")
        print()

    while True:
        try:
            query = await get_user_query(example_queries)
            if not query:
                break

            messages.append(HumanMessage(content=query))

            result = await agent.ainvoke({
                "messages": messages
            })

            result_messages = cast(list[BaseMessage], result["messages"])
            # the last message should be an AIMessage
            response = result_messages[-1].content
            if not isinstance(response, str):
                raise TypeError(
                    f"Expected string response, got {type(response)}"
                )

            # check if msg one before is a ToolMessage
            message_one_before = result_messages[-2]
            if isinstance(message_one_before, ToolMessage):
                if verbose:
                    # show tools call response
                    print(message_one_before.content)
                # new line after tool call output
                print()
            print_colored(f"{response}\n", Colors.CYAN)
            messages.append(AIMessage(content=response))

        except Exception as e:
            print(f"Error getting response: {str(e)}")
            print("You can continue chatting or type 'quit' to exit.")


async def init_react_agent(
    config: ConfigType,
    logger: logging.Logger
) -> tuple[Runnable, list[BaseMessage], McpServerCleanupFn]:
    """Initialize and configure a ReAct agent for conversation handling.

    Args:
        config (ConfigType): Configuration dictionary containing LLM and
            MCP server settings
        logger (logging.Logger): Logger instance for initialization
            status updates

    Returns:
        tuple[Runnable, list[BaseMessage], McpServerCleanupFn]:
            Returns a tuple containing:
            - Configured ReAct agent ready for conversation
            - Initial message list (empty or with system prompt)
            - Cleanup function for MCP server connections
    """
    llm_config = config["llm"]
    logger.info(f"Initializing model... {json.dumps(llm_config, indent=2)}\n")

    filtered_config = {
        k: v for k, v in llm_config.items() if k not in ["system_prompt"]
    }
    llm = init_chat_model(**filtered_config)

    mcp_servers = config["mcp_servers"]
    logger.info(f"Initializing {len(mcp_servers)} MCP server(s)...\n")

    tools, mcp_cleanup = await convert_mcp_to_langchain_tools(
        mcp_servers,
        logger
    )

    agent = create_react_agent(
        llm,
        tools
    )

    messages: list[BaseMessage] = []
    system_prompt = llm_config.get("system_prompt")
    if system_prompt and isinstance(system_prompt, str):
        messages.append(SystemMessage(content=system_prompt))

    return agent, messages, mcp_cleanup


async def run() -> None:
    """Main async function to set up and run the simple chat app."""
    mcp_cleanup: McpServerCleanupFn | None = None
    try:
        load_dotenv()
        args = parse_arguments()
        logger = init_logger(args.verbose)
        config = load_config(args.config)
        example_queries = (
            config.get("example_queries")[:]
            if config.get("example_queries") is not None
            else []
        )

        agent, messages, mcp_cleanup = await init_react_agent(config, logger)

        await handle_conversation(
            agent,
            messages,
            example_queries,
            args.verbose
        )

    finally:
        if mcp_cleanup is not None:
            await mcp_cleanup()


def main() -> None:
    """Entry point of the script."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
