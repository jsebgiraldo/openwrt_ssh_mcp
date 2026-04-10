"""Interactive script to test the OpenWRT MCP server tools."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openwrt_ssh_mcp.ssh_client import ssh_client
from openwrt_ssh_mcp.tools import OpenWRTTools
from openwrt_ssh_mcp.config import settings

async def test_mcp_tools():
    """Test all MCP server tools."""

    print("=" * 70)
    print("OPENWRT MCP SERVER — TOOL TEST SUITE")
    print("=" * 70)
    print(f"\nConnecting to: {settings.openwrt_user}@{settings.openwrt_host}:{settings.openwrt_port}")

    connected = await ssh_client.connect()

    if not connected:
        print("Failed to connect to the OpenWRT router")
        return False

    print("SSH connection established\n")

    tools = OpenWRTTools()

    # Test 1: System information
    print("-" * 70)
    print("TEST 1: System Information")
    print("-" * 70)
    result = await tools.get_system_info()
    if result["success"]:
        print("System info retrieved:")
        sys_info = result.get("system_info", {})
        if "board" in sys_info and isinstance(sys_info["board"], dict):
            print(f"  Model:   {sys_info['board'].get('model', 'N/A')}")
            print(f"  Release: {sys_info['board'].get('release', {}).get('description', 'N/A')}")
        if "info" in sys_info and isinstance(sys_info["info"], dict):
            uptime_sec = sys_info['info'].get('uptime', 0)
            print(f"  Uptime:  {uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m")
    else:
        print(f"Error: {result.get('error', 'Unknown')}")

    # Test 2: Network interfaces
    print("\n" + "-" * 70)
    print("TEST 2: Network Interfaces")
    print("-" * 70)
    result = await ssh_client.execute("ip addr show")
    if result["success"]:
        print("Network interfaces:")
        lines = result["stdout"].split("\n")[:15]
        print("\n".join(lines))
    else:
        print(f"Error: {result.get('stderr', 'Unknown')}")

    # Test 3: UCI configuration
    print("\n" + "-" * 70)
    print("TEST 3: UCI Configuration")
    print("-" * 70)
    result = await tools.read_config("system")
    if result["success"]:
        print("System UCI config:")
        lines = result.get("config", "").split("\n")[:10]
        print("\n".join(lines))
    else:
        print(f"Error: {result.get('error', 'Unknown')}")

    # Test 4: Init scripts
    print("\n" + "-" * 70)
    print("TEST 4: System Services")
    print("-" * 70)
    result = await ssh_client.execute("ls /etc/init.d/ | head -10")
    if result["success"]:
        print("Available services:")
        print(result["stdout"])
    else:
        print(f"Error: {result.get('stderr', 'Unknown')}")

    # Test 5: System health
    print("\n" + "-" * 70)
    print("TEST 5: System Health (uptime, memory, CPU)")
    print("-" * 70)
    result = await ssh_client.execute("uptime")
    if result["success"]:
        print(f"Uptime: {result['stdout'].strip()}")

    result = await ssh_client.execute("free -m")
    if result["success"]:
        print(f"\nMemory:\n{result['stdout']}")

    # Test 6: OpenThread OTBR
    print("\n" + "-" * 70)
    print("TEST 6: OpenThread OTBR Check")
    print("-" * 70)
    result = await ssh_client.execute("which ot-ctl")
    if result["success"] and result["stdout"].strip():
        print(f"OpenThread CLI found: {result['stdout'].strip()}")
        ot_result = await tools.thread_get_info()
        if ot_result["success"]:
            thread_info = ot_result.get("thread_info", {})
            print("Thread network info:")
            print(f"  State:   {thread_info.get('state', 'N/A')}")
            print(f"  Channel: {thread_info.get('channel', 'N/A')}")
            print(f"  Name:    {thread_info.get('networkname', 'N/A')}")
        else:
            print("OpenThread CLI available but not configured")
    else:
        print("OpenThread is not installed on this router")

    # Test 7: Installed packages (sample)
    print("\n" + "-" * 70)
    print("TEST 7: Installed Packages (sample of 5)")
    print("-" * 70)
    result = await tools.opkg_list_installed()
    if result["success"]:
        packages = result.get("packages", [])[:5]
        print(f"Total installed packages: {result.get('count', 0)}")
        print("Sample:")
        for pkg in packages:
            print(f"  {pkg.get('name', 'N/A')} — {pkg.get('version', 'N/A')}")
    else:
        print(f"Error: {result.get('error', 'Unknown')}")

    await ssh_client.disconnect()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
    print("\nAvailable MCP tools:")
    print("   openwrt_test_connection")
    print("   openwrt_execute_command")
    print("   openwrt_get_system_info")
    print("   openwrt_get_network_info")
    print("   openwrt_uci_show / uci_set / uci_commit")
    print("   openwrt_ubus_call")
    print("   openwrt_list_services / service_status / service_action")
    print("   openwrt_thread_* (get_state, create_network, get_info, …)")
    print("   openwrt_otbr_persist_network")
    print("   openwrt_opkg_* (list, install, remove, update)")
    print("   openwrt_observability_health")
    print("   openwrt_thingsboard_probe")

    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_mcp_tools())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
