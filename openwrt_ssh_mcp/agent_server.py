"""Multi-device MCP Server for OpenWRT network management agent.

This server exposes tools for managing multiple OpenWRT devices
in a local network, with topology awareness and cross-device operations.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .devices import device_inventory
from .multi_ssh_client import ssh_manager
from .multi_tools import NetworkAgentTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("openwrt-network-agent")
tools: NetworkAgentTools = None  # type: ignore


# ============================================================
# TOOL DEFINITIONS
# ============================================================

DEVICE_ID_PROPERTY = {
    "type": "string",
    "description": (
        "Device identifier from the inventory "
        "(e.g., 'wan_router', 'edge_gateway', 'halow_router'). "
        "Use 'network_list_devices' to see available devices."
    ),
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available network management tools."""
    return [
        # ---- Network-Wide Tools ----
        Tool(
            name="network_list_devices",
            description="List all OpenWRT devices in the network inventory with their connection status",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="network_test_all_connections",
            description="Test SSH connectivity to all devices in the network",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="network_overview",
            description="Get a comprehensive overview of all devices (system info, uptime, memory, etc.)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="network_connectivity_matrix",
            description="Test ping connectivity between all device pairs to verify network mesh health",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="network_ping",
            description="Ping a target IP from a specific device to test reachability",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROPERTY,
                    "target_ip": {
                        "type": "string",
                        "description": "Target IP address or hostname to ping",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of ping packets (default: 3)",
                        "default": 3,
                    },
                },
                "required": ["device_id", "target_ip"],
            },
        ),
        # ---- Per-Device Tools ----
        Tool(
            name="device_execute_command",
            description="Execute a validated shell command on a specific OpenWRT device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROPERTY,
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute (must be in security whitelist)",
                    },
                },
                "required": ["device_id", "command"],
            },
        ),
        Tool(
            name="device_get_system_info",
            description="Get system info (board, uptime, memory, load) from a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_get_network_config",
            description="Get the full UCI network configuration from a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_get_wifi_status",
            description="Get WiFi status including connected clients from a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_get_dhcp_leases",
            description="List DHCP leases (connected devices) from a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_get_firewall_rules",
            description="Get firewall rules (iptables) from a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_read_config",
            description="Read a UCI configuration file from a specific device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROPERTY,
                    "config_name": {
                        "type": "string",
                        "description": "Configuration name",
                        "enum": ["network", "wireless", "dhcp", "firewall", "system"],
                    },
                },
                "required": ["device_id", "config_name"],
            },
        ),
        Tool(
            name="device_restart_interface",
            description="Restart a network interface on a specific device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROPERTY,
                    "interface": {
                        "type": "string",
                        "description": "Interface name (e.g., 'wan', 'lan')",
                    },
                },
                "required": ["device_id", "interface"],
            },
        ),
        Tool(
            name="device_get_routes",
            description="Get the routing table from a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_get_interfaces",
            description="Get IP address and interface details from a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        # ---- OpenThread Tools ----
        Tool(
            name="device_thread_get_state",
            description="Get OpenThread state from a device (disabled, detached, child, router, leader)",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_thread_get_info",
            description="Get comprehensive Thread network info from a device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        # ---- Package Management ----
        Tool(
            name="device_opkg_update",
            description="Update package lists on a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="device_opkg_install",
            description="Install a package on a specific device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROPERTY,
                    "package_name": {
                        "type": "string",
                        "description": "Package name to install",
                    },
                },
                "required": ["device_id", "package_name"],
            },
        ),
        Tool(
            name="device_opkg_list_installed",
            description="List installed packages on a specific device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": DEVICE_ID_PROPERTY},
                "required": ["device_id"],
            },
        ),
    ]


# ============================================================
# TOOL ROUTER
# ============================================================


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Route tool calls to the appropriate handler."""
    try:
        logger.info(f"Tool called: {name} with args: {arguments}")
        result = await _dispatch(name, arguments or {})
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [
            TextContent(
                type="text",
                text=json.dumps({"success": False, "error": str(e)}, indent=2),
            )
        ]


async def _dispatch(name: str, args: dict) -> dict:
    """Dispatch a tool call to the correct method."""
    device_id = args.get("device_id")

    # Network-wide tools
    if name == "network_list_devices":
        return await tools.list_devices()
    elif name == "network_test_all_connections":
        return await tools.test_all_connections()
    elif name == "network_overview":
        return await tools.get_network_overview()
    elif name == "network_connectivity_matrix":
        return await tools.network_connectivity_matrix()
    elif name == "network_ping":
        return await tools.ping_between_devices(
            device_id, args["target_ip"], args.get("count", 3)
        )

    # Per-device tools (all require device_id)
    if not device_id:
        raise ValueError(f"Missing required argument: device_id for tool '{name}'")

    if name == "device_execute_command":
        return await tools.execute_command(device_id, args["command"])
    elif name == "device_get_system_info":
        return await tools.get_system_info(device_id)
    elif name == "device_get_network_config":
        return await tools.get_network_config(device_id)
    elif name == "device_get_wifi_status":
        return await tools.get_wifi_status(device_id)
    elif name == "device_get_dhcp_leases":
        return await tools.get_dhcp_leases(device_id)
    elif name == "device_get_firewall_rules":
        return await tools.get_firewall_rules(device_id)
    elif name == "device_read_config":
        return await tools.read_config(device_id, args["config_name"])
    elif name == "device_restart_interface":
        return await tools.restart_interface(device_id, args["interface"])
    elif name == "device_get_routes":
        return await tools.get_routes(device_id)
    elif name == "device_get_interfaces":
        return await tools.get_interfaces(device_id)
    elif name == "device_thread_get_state":
        return await tools.thread_get_state(device_id)
    elif name == "device_thread_get_info":
        return await tools.thread_get_info(device_id)
    elif name == "device_opkg_update":
        return await tools.opkg_update(device_id)
    elif name == "device_opkg_install":
        return await tools.opkg_install(device_id, args["package_name"])
    elif name == "device_opkg_list_installed":
        return await tools.opkg_list_installed(device_id)
    else:
        raise ValueError(f"Unknown tool: {name}")


# ============================================================
# MAIN
# ============================================================


async def main():
    """Main entry point for the multi-device MCP server."""
    global tools

    logger.info("=" * 60)
    logger.info("  OpenWRT Network Agent - Multi-Device MCP Server")
    logger.info("=" * 60)

    # Look for topology config in standard locations
    search_paths = [
        Path.cwd() / "network_topology.yaml",
        Path.cwd() / "topology.yaml",
        Path(__file__).parent.parent / "network_topology.yaml",
        Path(__file__).parent.parent / "topology.yaml",
    ]

    topology_path = None
    for p in search_paths:
        if p.exists():
            topology_path = p
            break

    if topology_path is None:
        logger.error("No network_topology.yaml found! Searched:")
        for p in search_paths:
            logger.error(f"  - {p}")
        raise FileNotFoundError(
            "network_topology.yaml not found. Create one in the project root."
        )

    logger.info(f"Loading topology from: {topology_path}")
    topology = device_inventory.load_from_yaml(topology_path)

    logger.info(f"Network: {topology.name}")
    logger.info(f"Devices: {len(topology.devices)}")
    for dev in topology.list_devices():
        logger.info(f"  - {dev.display_name}")

    # Register all devices with SSH manager
    ssh_manager.register_topology(topology)

    # Initialize tools
    tools = NetworkAgentTools(ssh_manager)

    # Try connecting to all devices
    logger.info("Connecting to devices...")
    conn_results = await ssh_manager.connect_all()
    for dev_id, ok in conn_results.items():
        status = "CONNECTED" if ok else "FAILED"
        logger.info(f"  {dev_id}: {status}")

    # Run MCP server
    logger.info("MCP Server ready - waiting for requests...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    except KeyboardInterrupt:
        logger.info("Server interrupted")
    finally:
        logger.info("Shutting down...")
        await ssh_manager.disconnect_all()
        logger.info("Server stopped")


def run():
    """Entry point for setuptools / command line."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
