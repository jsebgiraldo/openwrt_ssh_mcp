# OpenWRT SSH MCP Server 🐳

![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Docker](https://img.shields.io/badge/Docker-271MB-blue)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-SDK%201.0-purple)

A containerized MCP (Model Context Protocol) server for managing OpenWRT routers via SSH. This server allows AI agents (like Claude) to execute commands and manage OpenWRT routers remotely and securely.

🎉 **STATUS**: ✅ Fully functional and tested with physical router

## ✨ Features

- 🐳 **Docker Ready** - Optimized image with multi-stage build (271MB)
- 🔐 **Robust Security** - Command whitelist, read-only filesystem, audit logging
- 🛠️ **19 OpenWRT Tools** - Complete router management (network, system, Thread, packages)
- 🚀 **Easy Integration** - Compatible with Claude Desktop and VS Code
- 📊 **Monitoring** - Detailed logs of all operations
- 🔄 **MCP Toolkit** - Fully compatible with Docker Desktop MCP
- 📦 **Package Management** - Install/remove IPK packages with opkg
- 🔗 **OpenThread OTBR** - Support for Thread Border Router

## Architecture

```
┌─────────────────────┐
│ Claude / VS Code    │  ← Your AI agent
└──────────┬──────────┘
           │ MCP Protocol (stdio)
           │
┌──────────▼──────────┐
│ Docker Container    │  ← MCP Server
│  ┌──────────────┐   │
│  │ MCP Server   │   │
│  │ (Python)     │   │
│  └──────┬───────┘   │
└─────────┼───────────┘
          │ SSH
          │
┌─────────▼───────────┐
│ OpenWRT Router      │  ← Your physical router
│ (192.168.1.1)       │
└─────────────────────┘
```

## Features

- 🔐 Secure SSH authentication (password or key-based)
- 🛠️ OpenWRT-specific tools (ubus, uci)
- ✅ Command validation with whitelist
- 📝 Audit logging
- 🐳 Docker support (optional)
- 🔌 Integration with Claude Desktop and VS Code

## Requirements

- Python 3.10+
- OpenWRT router with SSH enabled
- SSH access to router (root user recommended)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/jsebgiraldo/openwrt_ssh_mcp.git
cd openwrt_ssh_mcp
```

### 2. Create virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows
pip install -e .
```

### 3. Configure SSH credentials

```bash
# Copy example file
cp .env.example .env

# Edit .env with your router credentials
```

### 4. Generate and copy SSH key (recommended)

```bash
# Generate dedicated key
ssh-keygen -t ed25519 -f ~/.ssh/openwrt_router -C "MCP Server"

# Copy to router
ssh-copy-id -i ~/.ssh/openwrt_router.pub root@192.168.1.1

# Update OPENWRT_KEY_FILE in .env
OPENWRT_KEY_FILE=~/.ssh/openwrt_router
```

## 🔧 Configuration

### Claude Desktop (Docker)

Includes optimized configuration in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "openwrt-router-docker": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "host",
        "--env-file", "${HOME}/Documents/openwrt_ssh_mcp/.env",
        "--mount", "type=bind,src=${HOME}/.ssh,dst=/root/.ssh,readonly",
        "openwrt-ssh-mcp:latest"
      ]
    }
  }
}
```

### VS Code with GitHub Copilot

The project includes complete VS Code configuration:

**Option 1: Direct Python (Recommended)**
```powershell
# Open workspace
code mcp-openwrt.code-workspace

# In Copilot Chat (Ctrl+Shift+I):
"What OpenWRT tools do I have available?"
```

**Option 2: With Tasks**
```
Terminal > Run Task > "Start MCP Server (Python)"
```

**Option 3: Startup Script**
```powershell
.\start-mcp-vscode.ps1
```

### Script Helper

Use `docker-mcp.ps1` for all operations:

```powershell
.\docker-mcp.ps1 build   # Build image
.\docker-mcp.ps1 run     # Run server
.\docker-mcp.ps1 test    # Test connection
.\docker-mcp.ps1 logs    # View logs
.\docker-mcp.ps1 shell   # Open shell
.\docker-mcp.ps1 clean   # Clean all
```

## 🛠️ Available Tools

### System & Network (8 tools)
- `openwrt_test_connection` - Test SSH connection
- `openwrt_execute_command` - Execute raw command (validated)
- `openwrt_get_system_info` - System info (uptime, memory, CPU)
- `openwrt_restart_interface` - Restart network interface
- `openwrt_get_wifi_status` - WiFi status and clients
- `openwrt_list_dhcp_leases` - List DHCP clients
- `openwrt_get_firewall_rules` - View firewall rules
- `openwrt_read_config` - Read UCI config file

### OpenThread Border Router (6 tools)
- `openwrt_thread_get_state` - Current Thread state
- `openwrt_thread_create_network` - Create new Thread network
- `openwrt_thread_get_dataset` - Get network credentials
- `openwrt_thread_get_info` - Complete Thread network info
- `openwrt_thread_enable_commissioner` - Allow new devices
- `openwrt_otbr_persist_network` - Save dataset + enable service + sysupgrade protection

### Edge Observability & ThingsBoard (2 tools)
- `openwrt_observability_health` - Check Prometheus, Grafana, blackbox-exporter status
- `openwrt_thingsboard_probe` - Discover ThingsBoard config and verify TCP/HTTP reachability

### Package Management (6 tools)
- `openwrt_opkg_update` - Update package lists
- `openwrt_opkg_install` - Install IPK packages
- `openwrt_opkg_remove` - Remove packages
- `openwrt_opkg_list_installed` - List installed packages
- `openwrt_opkg_info` - Detailed package info
- `openwrt_opkg_list_available` - List available packages

## 💬 Usage Examples

Once configured, you can ask Claude:

### System & Network
- "Show me the WiFi status on my router"
- "List connected devices"
- "Restart the wan interface"
- "What's the router's memory usage?"

### Package Management
- "Update the package repositories"
- "Install the luci-app-openthread package"
- "Show me installed packages"
- "Give me information about the ot-br-posix package"

### OpenThread
- "Create a Thread network called 'MyHome' on channel 15"
- "Show me the Thread network status"
- "Enable the commissioner to add new devices"
- "Give me the Thread network credentials"

## Security

⚠️ **IMPORTANT**: This server has root access to your router. Make sure to:

- Use SSH key authentication (not password)
- Keep `.env` out of version control
- Review commands before production execution
- Enable audit logging
- Limit SSH access from router to your PC

## 📚 Documentation

### 🚀 Quick Start
- **[QUICKSTART_DOCKER.md](QUICKSTART_DOCKER.md)** - Quick start with Docker
- **[TEST_OPKG.md](TEST_OPKG.md)** - Test IPK package management

### 📖 Detailed Guides
- **[DOCKER_GUIDE.md](DOCKER_GUIDE.md)** - Complete Docker guide

## 🧪 Testing

```powershell
# Test with helper script
.\docker-mcp.ps1 test

# Test with MCP Inspector
npm install -g @modelcontextprotocol/inspector
npx @modelcontextprotocol/inspector docker run -i --rm openwrt-ssh-mcp:latest

# View logs
.\docker-mcp.ps1 logs
```

## 🔐 Implemented Security

- ✅ **Read-only filesystem** - Immutable container
- ✅ **No capabilities** - No special permissions
- ✅ **SSH keys read-only** - Protected keys
- ✅ **Command whitelist** - Only safe commands
- ✅ **Audit logging** - Complete logging
- ✅ **Volatile tmpfs** - /tmp cleaned on restart
- ✅ **No privilege escalation** - No sudo

## 🎯 Use Cases

### Advanced Workflows

- 🔄 **Automated backup** of UCI configurations
- 📊 **Network monitoring** - Connected devices, resource usage
- 🔧 **AI-guided troubleshooting**
- 📝 **Automatic documentation** of changes
- 🚨 **Network anomaly alerts**
- 📦 **Package management** - Install/update software
- 🔗 **Thread configuration** - Create and manage Thread/Matter networks
- 🛡️ **Security auditing** - Review firewall rules

## 🐳 Docker Hub (Optional)

```bash
# Publish your image
docker login
docker tag openwrt-ssh-mcp:latest jsebgiraldo/openwrt-ssh-mcp:latest
docker push jsebgiraldo/openwrt-ssh-mcp:latest
```

## 🛠️ Development

```powershell
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check --fix .

# Rebuild after changes
.\docker-mcp.ps1 build
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the project
2. Create a branch for your feature
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📖 Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Docker MCP Blog](https://www.docker.com/blog/dynamic-mcps-with-docker/)
- [OpenWRT Documentation](https://openwrt.org/docs/start)
- [MCP Servers Repository](https://github.com/modelcontextprotocol/servers)

## 📄 License

MIT

## Edge 192.168.1.111 Runbook

This section documents operational procedures for Sebastian's edge gateway.

### Recreate Thread network

```
# Via Claude / MCP tools:
openwrt_thread_create_network(name="auto", channel=15)
openwrt_thread_enable_commissioner()
openwrt_otbr_persist_network()
```

The dataset TLV backup is stored locally at `~/.config/openwrt-mcp/edge-111-otbr-dataset.tlvs` (not committed).

### Check observability stack

```
openwrt_observability_health()
```

Prometheus: `http://192.168.1.111:9090` | Grafana: `http://192.168.1.111:3000` (default `admin/admin`) | Blackbox: `http://192.168.1.111:9115`

### Re-probe ThingsBoard

```
openwrt_thingsboard_probe()   # auto-discover mode
```

---

**Maintained by [Sebastian Giraldo](https://github.com/jsebgiraldo)**
