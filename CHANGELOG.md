# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-28

### Added
- Initial production release
- 8 core OpenWRT management tools (system, network, WiFi, DHCP, firewall, UCI)
- 5 OpenThread Border Router (OTBR) tools for Thread network management
- 6 package management tools (opkg) for installing/removing IPK packages
- SSH connection management with key-based and password authentication
- Command validation with security whitelist
- Audit logging for all operations
- Docker containerization with optimized multi-stage build (271MB)
- VS Code integration with GitHub Copilot
- Claude Desktop integration
- Comprehensive documentation (README, QUICKSTART, DOCKER_GUIDE)

### Security
- Read-only filesystem in Docker container
- Dropped all Linux capabilities
- Command whitelist validation
- SSH keys mounted as read-only
- No privilege escalation allowed
- Audit logging enabled by default

## [1.1.0] - 2026-05-18

### Added
- Chat CLI (`openwrt-mcp-chat`) for natural language router management via local LLMs
- OpenAI-compatible endpoint configuration (Ollama, LM Studio, vLLM, LocalAI)
- New config settings: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`, `OPENAI_TEMPERATURE`
- `openai>=1.0.0` dependency for chat mode
- Interactive chat loop with tool calling, conversation history pruning, and slash commands (`/quit`, `/tools`, `/new`)
- Comprehensive IPv6 support and tools for OpenWRT
- IPv6 optimization and diagnostic scripts
- Connection and MCP tool test scripts
- IPv6 setup documentation (IPv6_GUIA_COMPLETA.md, SETUP_COMPLETADO.md)

### Changed
- Relaxed auth validation to allow default SSH key authentication without explicit password or key file
- Updated `.env.example` with OpenAI endpoint configuration section and chat mode setup instructions

### Fixed
- Added `node_modules/`, `package.json`, `package-lock.json` to `.gitignore`

## [Unreleased]

### Planned
- Web UI for monitoring
- Metrics and alerting
- Multi-router support
- Configuration backup/restore automation
- Integration tests
- CI/CD pipeline
