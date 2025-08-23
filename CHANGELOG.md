# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

### Changed
- Replace "model_provider" with "provider" while keeping backward compatibility
- Minor fixes in README.md, the json5 example, and .env.template 


## [0.2.13] - 2025-08-14

### Added
- Support for Cerebras and Groq
  primarily to try gpt-oss-* with the exceptional speed
- Add "provider" as an alias for "model_provider"
  to avoid confusion between the model provider and the API provider
- Usage examples of gpt-oss-120b/20b on Cerebras / Groq

### Changed
- Update dependencies
