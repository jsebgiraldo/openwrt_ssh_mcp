# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-10

### Added
- Three new MCP tools for edge gateway operations:
  - `otbr_persist_network`: Saves the active Thread dataset to `/etc/otbr/`, enables `otbr-agent` service, and adds files to `/etc/sysupgrade.conf` for persistence across reboots and firmware upgrades.
  - `thingsboard_probe`: Discovers ThingsBoard gateway config on the edge and verifies TCP/HTTP reachability on MQTT and HTTP ports.
  - `observability_health`: Checks Prometheus, Grafana, and blackbox-exporter health endpoints and listening sockets.
- Extended command security whitelist to cover OTBR persistence, observability, and ThingsBoard probe operations.

### Changed
- Rebranded from placeholder author to Sebastian Giraldo (GitHub: jsebgiraldo).
- Repository URLs updated to `github.com/jsebgiraldo/openwrt_ssh_mcp`.
- Version bumped from 1.0.0 to 0.2.0.
- All documentation and scripts converted to English only; Spanish guides renamed and translated.
- Removed stale Windows paths referencing previous contributor environment.

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
