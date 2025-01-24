# MCP Client Using LangChain / Python [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/hideya/langchain-mcp-tools-py/blob/main/LICENSE)

This simple [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
client demonstrates the use of MCP server tools by LangChain ReAct Agent.

It leverages a utility function `convert_mcp_to_langchain_tools()` from
[`langchain_mcp_tools`](https://pypi.org/project/langchain-mcp-tools/).  
This function handles parallel initialization of specified multiple MCP servers
and converts their available tools into a list of LangChain-compatible tools
([List[BaseTool]](https://python.langchain.com/api_reference/core/tools/langchain_core.tools.base.BaseTool.html#langchain_core.tools.base.BaseTool)).

LLMs from Anthropic, OpenAI and Groq are currently supported.

A typescript version of this MCP client is available
[here](https://github.com/hideya/mcp-client-langchain-ts)

## Prerequisites

- Python 3.11+
- [`uv` (`uvx`)](https://docs.astral.sh/uv/) installed to run Python-based MCP servers
- npm 7+ (`npx`) to run Node.js-based MCP servers
- API keys from [Anthropic](https://console.anthropic.com/settings/keys),
  [OpenAI](https://platform.openai.com/api-keys), and/or
  [Groq](https://console.groq.com/keys)
  as needed

## Setup

1. Install dependencies:
    ```bash
    make install
    ```

2. Setup API keys:
    ```bash
    cp .env.template .env
    ```
    - Update `.env` as needed.
    - `.gitignore` is configured to ignore `.env`
      to prevent accidental commits of the credentials.

3. Configure LLM and MCP Servers settings `llm_mcp_config.json5` as needed.

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
make start-v
```

See commandline options:
```bash
make start-h
```

At the prompt, you can simply press Enter to use example queries that perform MCP server tool invocations.

Example queries can be configured in  `llm_mcp_config.json5`
