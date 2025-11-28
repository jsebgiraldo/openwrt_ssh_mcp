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

## [Unreleased]

### Planned
- Web UI for monitoring
- Metrics and alerting
- Multi-router support
- Configuration backup/restore automation
- Integration tests
- CI/CD pipeline
