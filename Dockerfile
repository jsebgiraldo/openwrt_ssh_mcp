# Multi-stage build for optimal image size
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY openwrt_ssh_mcp/ ./openwrt_ssh_mcp/

# Install dependencies
RUN pip install --no-cache-dir mcp asyncssh pydantic pydantic-settings python-dotenv

# Final stage - minimal runtime
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY openwrt_ssh_mcp/ ./openwrt_ssh_mcp/

# Create SSH directory with correct permissions
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

# Add MCP labels for discovery
LABEL mcp.server.name="openwrt-ssh"
LABEL mcp.server.description="OpenWRT router management via SSH"
LABEL mcp.server.version="0.1.0"
LABEL mcp.server.transport="stdio"
LABEL mcp.server.tools="execute_command,get_system_info,restart_interface,get_wifi_status,list_dhcp_leases"

# Default environment variables (override at runtime)
ENV OPENWRT_HOST=192.168.1.1
ENV OPENWRT_PORT=22
ENV OPENWRT_USER=root
ENV ENABLE_COMMAND_VALIDATION=true
ENV ENABLE_AUDIT_LOGGING=true
ENV LOG_FILE=/app/logs/openwrt_mcp.log

# Use ENTRYPOINT for stdio transport (required for MCP)
ENTRYPOINT ["python", "-u", "-m", "openwrt_ssh_mcp.server"]
