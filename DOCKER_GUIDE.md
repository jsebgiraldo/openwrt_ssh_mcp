# Docker + MCP Toolkit Integration Guide

## Docker Desktop with MCP

This guide shows how to use the OpenWRT MCP server with Docker Desktop and the MCP Toolkit.

## Architecture

```
Claude/VS Code → Docker Container → SSH → OpenWRT Router
                 (MCP Server)
```

## Quick Setup

### 1. Build the Docker image

```bash
cd ~/Documents/openwrt_ssh_mcp

# Build optimized image
docker build -t openwrt-ssh-mcp:latest .

# Verify image
docker images | grep openwrt
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

### 3. Configure Claude Desktop

`claude_desktop_config.json` includes two configurations:

#### Option A: Via Docker (recommended for production)
```json
"openwrt-router-docker": {
  "command": "docker",
  "args": ["run", "--rm", "-i", "--network", "host", ...]
}
```

#### Option B: Local Python (development)
```json
"openwrt-router-local": {
  "command": "python",
  "args": ["-m", "openwrt_ssh_mcp.server"]
}
```

**Copy config (macOS/Linux):**
```bash
cp claude_desktop_config.json "${HOME}/Library/Application Support/Claude/claude_desktop_config.json"
```

**Copy config (Windows):**
```powershell
copy claude_desktop_config.json "$env:APPDATA\Claude\claude_desktop_config.json"
```

### 4. Restart Claude Desktop

1. Fully close Claude Desktop
2. Reopen it
3. The MCP server should be available

## Verification

### View Docker logs

```bash
# If using docker compose
docker compose logs -f

# If using docker run
docker logs openwrt-ssh-mcp
```

### View MCP server logs

```bash
# Server logs
cat ./logs/openwrt_mcp.log

# Follow in real time
tail -f ./logs/openwrt_mcp.log
```

### Test with MCP Inspector

```bash
npm install -g @modelcontextprotocol/inspector
npx @modelcontextprotocol/inspector docker run -i --rm openwrt-ssh-mcp:latest
```

## Useful Commands

### Docker management

```bash
# Build and run
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f openwrt-mcp

# Stop
docker compose down

# Clean everything
docker compose down -v
docker rmi openwrt-ssh-mcp:latest
```

### Testing

```bash
# Quick connectivity test
docker run -i --rm --network host --env-file .env \
  --mount type=bind,src=${HOME}/.ssh,dst=/root/.ssh,readonly \
  openwrt-ssh-mcp:latest
```

## Security

### SSH Keys

```bash
# Generate dedicated key for MCP
ssh-keygen -t ed25519 -f ~/.ssh/mcp_openwrt -C "MCP Docker"

# Copy to router
ssh-copy-id -i ~/.ssh/mcp_openwrt.pub root@192.168.1.111

# Set in .env
# OPENWRT_KEY_FILE=/root/.ssh/mcp_openwrt
```

### Container security

- `read_only: true` — read-only filesystem
- `cap_drop: ALL` — no Linux capabilities
- `no-new-privileges` — no privilege escalation
- SSH keys mounted read-only
- `/tmp` as volatile tmpfs

## Troubleshooting

### Container can't reach the router

```bash
# Verify router is reachable from host
ping 192.168.1.111
ssh root@192.168.1.111 "uname -a"

# With --network host, the container has the same network as the host
```

### SSH permission denied

```bash
# Verify keys are mounted
docker run -i --rm \
  --mount type=bind,src=${HOME}/.ssh,dst=/root/.ssh,readonly \
  openwrt-ssh-mcp:latest \
  ls -la /root/.ssh
```

### MCP server not detected in Claude

1. Verify image exists: `docker images openwrt-ssh-mcp`
2. Check Claude logs: `cat "${HOME}/Library/Logs/Claude/mcp*.log"`
3. Test standalone:
   ```bash
   docker run -i --rm --network host --env-file .env \
     --mount type=bind,src=${HOME}/.ssh,dst=/root/.ssh,readonly \
     openwrt-ssh-mcp:latest
   ```

### Container exits immediately

- Verify `.env` exists with valid credentials
- Ensure `-i` (interactive stdin) flag is present
- Do not use `restart: unless-stopped` for MCP containers

## Multi-MCP Setup

You can orchestrate multiple MCP servers:

```yaml
# docker-compose-multi.yml
version: '3.8'

services:
  openwrt-mcp:
    image: openwrt-ssh-mcp:latest
    stdin_open: true
    tty: true
    env_file: ./openwrt.env
    volumes:
      - ~/.ssh:/root/.ssh:ro
    network_mode: host
    restart: "no"

  # Another MCP server (example)
  filesystem-mcp:
    image: mcp/filesystem:latest
    stdin_open: true
    tty: true
    volumes:
      - ~/Documents:/workspace:ro
    restart: "no"
```

Claude Desktop config:
```json
{
  "mcpServers": {
    "openwrt": {
      "command": "docker",
      "args": ["compose", "-f", "docker-compose-multi.yml", "run", "--rm", "openwrt-mcp"]
    },
    "filesystem": {
      "command": "docker",
      "args": ["compose", "-f", "docker-compose-multi.yml", "run", "--rm", "filesystem-mcp"]
    }
  }
}
```

## Publish to Docker Hub

```bash
docker login
docker tag openwrt-ssh-mcp:latest jsebgiraldo/openwrt-ssh-mcp:latest
docker tag openwrt-ssh-mcp:latest jsebgiraldo/openwrt-ssh-mcp:0.2.0

docker push jsebgiraldo/openwrt-ssh-mcp:latest
docker push jsebgiraldo/openwrt-ssh-mcp:0.2.0
```

## Next steps

1. Build Docker image
2. Test standalone container
3. Configure Claude Desktop
4. Test MCP tools
5. Document commands specific to your router
6. (Optional) Publish to Docker Hub

## Referencias

- [MCP Specification](https://modelcontextprotocol.io/docs)
- [Docker MCP Blog](https://www.docker.com/blog/dynamic-mcps-with-docker/)
- [MCP Servers GitHub](https://github.com/modelcontextprotocol/servers)
