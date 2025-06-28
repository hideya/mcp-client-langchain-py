# Simple CLI MCP Client Using LangChain / Python [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/hideya/langchain-mcp-tools-py/blob/main/LICENSE)

This is a simple [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) client
that is intended for trying out MCP servers via a command-line interface.

When testing LLM and MCP servers, their settings can be conveniently configured via a configuration file, such as the following:

```json5
{
    "llm": {
        "model_provider": "openai",
        "model": "gpt-4o-mini",
        // "model_provider": "anthropic",
        // "model": "claude-3-5-haiku-latest",
        // "model_provider": "google_genai",
        // "model": "gemini-2.0-flash",
    },

    "mcp_servers": {
        "fetch": {
            "command": "uvx",
            "args": [ "mcp-server-fetch" ]
        },

        "weather": {
            "command": "npx",
            "args": [ "-y", "@h1deya/mcp-server-weather" ]
        },

        // Auto-detection: tries Streamable HTTP first, falls back to SSE
        "remote-mcp-server": {
            "url": "https://${SERVER_HOST}:${SERVER_PORT}/..."
        },

        // Example of authentication via Authorization header
        "github": {
            "type": "http",  // recommended to specify the protocol explicitly when authentication is used
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"
            }
        },
    }
}
```

It leverages  [LangChain ReAct Agent](https://langchain-ai.github.io/langgraph/reference/agents/) and
a utility function `convert_mcp_to_langchain_tools()` from
[`langchain_mcp_tools`](https://pypi.org/project/langchain-mcp-tools/).  
This function handles parallel initialization of specified multiple MCP servers
and converts their available tools into a list of LangChain-compatible tools
([list[BaseTool]](https://python.langchain.com/api_reference/core/tools/langchain_core.tools.base.BaseTool.html#langchain_core.tools.base.BaseTool)).

This client supports both local (stdio) MCP servers as well as
remote (Streamable HTTP / SSE / WebSocket) MCP servers
which are accessible via a simple URL and optional headers for authentication and other purposes.

This client only supports text results of MCP tool calls and disregards other result types.

For the convenience of debugging MCP servers, this client prints local (stdio) MCP server logs to the console.

LLMs from Anthropic, OpenAI and Google (GenAI) are currently supported.

A TypeScript version of this MCP client is available
[here](https://github.com/hideya/mcp-client-langchain-ts)

## Prerequisites

- Python 3.11+
- [optional] [`uv` (`uvx`)](https://docs.astral.sh/uv/getting-started/installation/)
  installed to run Python package-based MCP servers
- [optional] [npm 7+ (`npx`)](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)
  to run Node.js package-based MCP servers
- API keys from [Anthropic](https://console.anthropic.com/settings/keys),
  [OpenAI](https://platform.openai.com/api-keys), and/or
  [Groq](https://console.groq.com/keys)
  as needed

## Setup

1. Clone the repository:
    ```bash
    git clone https://github.com/hideya/mcp-client-langchain-py.git
    cd mcp-client-langchain-py
    ```

2. Install dependencies:
    ```bash
    make install
    ```

3. Setup API keys:
    ```bash
    cp .env.template .env
    ```
    - Update `.env` as needed.
    - `.gitignore` is configured to ignore `.env`
      to prevent accidental commits of the credentials.

4. Configure LLM and MCP Servers settings `llm_mcp_config.json5` as needed.

    - [The configuration file format](https://github.com/hideya/mcp-client-langchain-ts/blob/main/llm_mcp_config.json5)
      for MCP servers follows the same structure as
      [Claude for Desktop](https://modelcontextprotocol.io/quickstart/user),
      with one difference: the key name `mcpServers` has been changed
      to `mcp_servers` to follow the snake_case convention
      commonly used in JSON configuration files.
    - The file format is [JSON5](https://json5.org/),
      where comments and trailing commas are allowed.
    - The format is further extended to replace `${...}` notations
      with the values of corresponding environment variables.
    - Keep all the credentials and private info in the `.env` file
      and refer to them with `${...}` notation as needed.


## Usage

Run the app:
```bash
make start
```
It takes a while on the first run.

Run in verbose mode:
```bash
make start -- -v
```

See commandline options:
```bash
make start -- -h
```

At the prompt, you can simply press Enter to use example queries that perform MCP server tool invocations.

Example queries can be configured in  `llm_mcp_config.json5`
