# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


## [0.3.4] - 2026-08-23

### Changed
- Documentation-only release
- Clarify that this utility is based on `langchain-mcp-tools`,
  which supports MCP Protocol version 2025-03-26 and does not support
  the MCP 2026-07-28 specification


## [0.3.3] - 2026-03-28

### Changed
- Update to use langchain-mcp-tools 0.3.3
- Updated the example to include latest models, including gpt-5.4-mini,
  claude-sonnet-4-6, and gemini-3.1-flash-lite-preview
- Refine prompts in the example for more successful execution of MCP servers


## [0.3.2] - 2026-02-13

### Changed
- Show model provider name together with model name in the console log
- Update json5 example file to use 2 space for tabs
- Refine examples in README.md


## [0.3.1] - 2026-02-13

### Changed
- Update README.md to show latest supported models
- Use more explicit queries for github and notioin
- Remove unnecessary dependency on websocket


## [0.3.0] - 2026-02-11

### Changed
- Update for compatibility with LangChain 1.2.x and Gemini 3 preview
- README_DEV.md, which was totally broken


## [0.2.14] - 2025-08-27

### Changed
- Remove extra `print()`s from config_loader.py 
- Upgrade dependenies


## [0.2.13] - 2025-08-14

### Added
- Support for Cerebras and Groq
  primarily to try gpt-oss-* with the exceptional speed
- Add "provider" as an alias for "model_provider"
  to avoid confusion between the model provider and the API provider
- Usage examples of gpt-oss-120b/20b on Cerebras / Groq

### Changed
- Update dependencies
