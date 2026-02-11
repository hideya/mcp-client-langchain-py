# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


## [Unreleased]


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
