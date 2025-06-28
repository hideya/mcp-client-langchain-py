"""MCP Client Using LangChain / Python."""

try:
    from importlib.metadata import version
    __version__ = version("mcp-chat")
except ImportError:
    __version__ = "unknown"
