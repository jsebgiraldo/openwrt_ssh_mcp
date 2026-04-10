# Quick Start: Docker Desktop + MCP Toolkit

## What you get

A containerized MCP server that lets Claude/VS Code manage your OpenWRT router over SSH through Docker.

## Architecture

```
Claude / VS Code → Docker Container → SSH → OpenWRT Router
   (MCP Client)      (MCP Server)
```

## Quick Start

### 1. Build the Docker image

```bash
# From the project root
docker build -t openwrt-ssh-mcp:latest .

# Verify
docker images openwrt-ssh-mcp
# OUTPUT: openwrt-ssh-mcp:latest (271MB)
```

### 2. Test the container standalone

```bash
docker run -i --rm \
  --network host \
  --env-file .env \
  --mount type=bind,src=${HOME}/.ssh,dst=/root/.ssh,readonly \
  --mount type=bind,src=$(pwd)/logs,dst=/app/logs \
  openwrt-ssh-mcp:latest
```

Expected output:
```
INFO - Starting OpenWRT SSH MCP Server...
INFO - SSH connection established successfully
INFO - MCP Server ready - waiting for requests...
```

Press `Ctrl+C` to stop.

### 3. Integrate with Claude Desktop

`claude_desktop_config.json` includes two configurations:

- **`openwrt-router-docker`** — Docker (recommended)
- **`openwrt-router-local`** — Local Python (development)

**Copy config (macOS/Linux):**
```bash
cp claude_desktop_config.json "${HOME}/Library/Application Support/Claude/claude_desktop_config.json"
```

**Copy config (Windows):**
```powershell
copy claude_desktop_config.json "$env:APPDATA\Claude\claude_desktop_config.json"
```

### 4. Restart Claude Desktop

Close and reopen Claude Desktop. The MCP server will appear as available.

### 5. Test from Claude

Ask Claude: *"What OpenWRT tools do you have available?"*

You should see 22 tools including:
- `openwrt_test_connection`
- `openwrt_get_system_info`
- `openwrt_otbr_persist_network`
- `openwrt_observability_health`
- `openwrt_thingsboard_probe`

## Helper script

Use `docker-mcp.ps1` (Windows) for common operations:

```powershell
.\docker-mcp.ps1 build   # Build image
.\docker-mcp.ps1 run     # Run server (interactive)
.\docker-mcp.ps1 test    # Test router connection
.\docker-mcp.ps1 logs    # View server logs
.\docker-mcp.ps1 shell   # Open shell in container
.\docker-mcp.ps1 clean   # Remove containers and image
```

## Configuration

### `.env` file (required)

```bash
OPENWRT_HOST=192.168.1.111
OPENWRT_PORT=22
OPENWRT_USER=root
OPENWRT_PASSWORD=
OPENWRT_KEY_FILE=/root/.ssh/id_ed25519
ENABLE_COMMAND_VALIDATION=true
ENABLE_AUDIT_LOGGING=true
SSH_TIMEOUT=30
```

### Generate SSH key (recommended)

```bash
# Generate key
ssh-keygen -t ed25519 -f ~/.ssh/openwrt_mcp -C "MCP Docker"

# Copy to router
ssh-copy-id -i ~/.ssh/openwrt_mcp.pub root@192.168.1.111

# Set in .env
OPENWRT_KEY_FILE=/root/.ssh/openwrt_mcp
```

## Docker Compose (alternative)

```bash
docker compose up          # Foreground
docker compose up -d       # Background
docker compose logs -f     # Follow logs
docker compose down        # Stop
```

## Testing

### MCP Inspector

```bash
npm install -g @modelcontextprotocol/inspector
npx @modelcontextprotocol/inspector docker run -i --rm openwrt-ssh-mcp:latest
```

### View logs

```bash
tail -f logs/openwrt_mcp.log
```

## Security implemented

- Read-only container filesystem
- No Linux capabilities (`cap_drop: ALL`)
- SSH keys mounted read-only
- Volatile `/tmp` (tmpfs)
- No privilege escalation
- Command whitelist validation
- Audit logging

## Networking

### Host network (default)

```yaml
network_mode: host
```

**Pros:** Direct LAN access to router
**Cons:** Less network isolation

### Bridge network (optional)

```yaml
networks:
  - openwrt-network
extra_hosts:
  - "router:192.168.1.111"
```

## Troubleshooting

### Container won't start
```bash
docker logs openwrt-mcp
cat .env  # verify credentials
```

### SSH permission denied
```bash
# Check keys are mounted
docker run -i --rm \
  --mount type=bind,src=${HOME}/.ssh,dst=/root/.ssh,readonly \
  openwrt-ssh-mcp:latest \
  ls -la /root/.ssh
```

### Claude doesn't detect the server
1. Verify config: `cat "${HOME}/Library/Application Support/Claude/claude_desktop_config.json"`
2. Verify image: `docker images openwrt-ssh-mcp`
3. Test standalone: `docker run -i --rm --network host --env-file .env openwrt-ssh-mcp:latest`
4. Fully restart Claude Desktop

### Container exits immediately
- Confirm `.env` exists with valid credentials
- Ensure `-i` (interactive stdin) flag is present
- Do not use `restart: unless-stopped` for MCP containers

## Publish to Docker Hub (optional)

```bash
docker login
docker tag openwrt-ssh-mcp:latest jsebgiraldo/openwrt-ssh-mcp:latest
docker push jsebgiraldo/openwrt-ssh-mcp:latest
```

Others can then use:
```json
{
  "mcpServers": {
    "openwrt": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "jsebgiraldo/openwrt-ssh-mcp:latest"]
    }
  }
}
```

## Next steps

1. Configure `.env` with your router credentials
2. Test: `docker run -i --rm --network host --env-file .env openwrt-ssh-mcp:latest`
3. Copy `claude_desktop_config.json` to Claude Desktop config directory
4. Restart Claude Desktop and verify tools are available

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Docker MCP Blog](https://www.docker.com/blog/dynamic-mcps-with-docker/)
- [MCP Servers](https://github.com/modelcontextprotocol/servers)
- [Project README](README.md) | [Docker Guide](DOCKER_GUIDE.md)
