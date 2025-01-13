# Standard library imports
import argparse
import asyncio
import os
import sys
from typing import (
    List,
    Dict,
    NoReturn,
    Optional,
    Any,
    cast,
)
import json
from pathlib import Path

# Third-party imports
try:
    from langchain.chat_models import init_chat_model
    from langgraph.prebuilt import create_react_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain.schema import BaseMessage, HumanMessage, AIMessage
    from langchain.schema import SystemMessage
    from langchain_core.messages.tool import ToolMessage
    from dotenv import load_dotenv
except ImportError as e:
    print(f'\nError: Required package not found: {e}')
    print('Please ensure all required packages are installed\n')
    sys.exit(1)

# Local application imports
from config_loader import load_config
from langchain_mcp_tools import convert_mcp_to_langchain_tools


class Colors:  # ANSI color constants
    YELLOW = '\x1b[33m'
    CYAN = '\x1b[36m'
    RESET = '\x1b[0m'


def print_colored(text: str, color: str, end: str = "\n") -> None:
    """Print text in specified color and reset afterwards."""
    print(f"{color}{text}{Colors.RESET}", end=end)


def set_color(color: str) -> None:
    """Set terminal color."""
    print(color, end='')


def clear_line() -> None:
    """Move up one line and clear it."""
    print('\x1b[1A\x1b[2K', end='')


def exit_with_error(message: str) -> NoReturn:
    """Exit the program with an error message.

    Args:
        message: Error message to display before exiting
    """
    print(f'Error: {message}')
    sys.exit(1)


async def run() -> None:
    """Main function to run the chat application.

    Loads environment variables, initializes chat model and tools,
    and runs the main chat loop.

    Environment Variables:
        OPENAI_API_KEY: OpenAI API key for authentication

    Command Line Arguments:
        --config: Path to config JSON file

    Raises:
        SystemExit: If required environment variables are missing
        FileNotFoundError: If config file is not found
    """
    load_dotenv()

    if not os.getenv('OPENAI_API_KEY'):
        exit_with_error("OPENAI_API_KEY not found in .env file")

    parser = argparse.ArgumentParser(
        description='CLI Chat Application',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-c', '--config',
        default='llm_mcp_config.json5',
        help='path to config file',
        type=Path,
        metavar='PATH'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='run with verbose logging'
    )
    args = parser.parse_args()

    config = load_config(args.config)

    llm_config = config['llm']
    print('\nInitializing model...', json.dumps(llm_config, indent=2), '\n')

    # FIXME: how to avoid the following cast?
    llm: BaseChatModel = cast(
        BaseChatModel,
        init_chat_model(
            model=llm_config['model'],
            model_provider=llm_config['model_provider'],
            temperature=llm_config['temperature'],
            max_tokens=llm_config['max_tokens'],
        )
    )

    mcp_configs: Dict[str, Dict[str, Any]] = config['mcp_servers']
    print(f'Initializing {len(mcp_configs)} MCP server(s)...\n')
    tools, mcp_cleanup = await convert_mcp_to_langchain_tools(
        mcp_configs,
        args.verbose
    )

    agent = create_react_agent(
        llm,
        tools
    )

    messages: List[BaseMessage] = []
    system_prompt: Optional[str] = llm_config.get('system_prompt')
    if system_prompt and isinstance(system_prompt, str):
        messages.append(SystemMessage(content=system_prompt))

    print('\nConversation started. '
          'Type "quit" or "q" to end the conversation.\n')
    sample_queries = config.get('sample_queries')
    if sample_queries is not None:
        print('Sample Queries (just type Enter to supply them one by one):')
        for query in sample_queries:
            print(f"- {query}")
        print()
    else:
        sample_queries = []

    while True:
        try:
            set_color(Colors.YELLOW)
            query = input('Query: ').strip()

            if len(query) == 0:
                if len(sample_queries) > 0:
                    query = sample_queries.pop(0)
                    clear_line()
                    print_colored(f'Sample Query: {query}', Colors.YELLOW)
                else:
                    set_color(Colors.RESET)
                    print('\nPlease type a query, or "quit" or "q" to exit\n')
                    continue

            print(Colors.RESET)  # Reset after input

            if query.lower() in ['quit', 'q']:
                print_colored('Goodbye!\n', Colors.CYAN)
                break

            messages.append(HumanMessage(content=query))

            result: Dict[str, List[BaseMessage]] = await agent.ainvoke({
                'messages': messages
            })

            # the last message should be an AIMessage
            response = result['messages'][-1].content
            # check if msg one before is a ToolMessage
            message_one_before = result['messages'][-2]
            if isinstance(message_one_before, ToolMessage):
                if args.verbose:
                    # show tools call respose
                    print(message_one_before.content)
                # new line after tool call output
                print()
            print_colored(f"{response}\n", Colors.CYAN)
            messages.append(AIMessage(content=response))

        except KeyboardInterrupt:
            print_colored('Goodbye!\n', Colors.CYAN)
            break
        except Exception as e:
            print(f'Error getting response: {str(e)}')
            print('You can continue chatting or type "quit" to exit.')

    await mcp_cleanup()


def main() -> None:
    """Entry point of the script."""
    asyncio.run(run())


if __name__ == '__main__':
    main()
