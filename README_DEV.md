# Building and Running from the Source

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- make
- git


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

3. Create a `.env` file for API keys

4. Configure LLM and MCP Servers settings `llm_mcp_config.json5` as needed


## Test Execution

Run the app:
```bash
make start
```

Run in verbose mode:
```bash
make start -- -v
```

See commandline options:
```bash
make start -- -h
```
