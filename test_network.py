"""Quick connectivity test for all network devices."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from openwrt_ssh_mcp.devices import DeviceInventory
from openwrt_ssh_mcp.multi_ssh_client import MultiSSHClientManager


async def main():
    print("=" * 60)
    print("  OpenWRT Network Agent - Connectivity Test")
    print("=" * 60)

    # Load topology
    topology_path = Path(__file__).parent / "network_topology.yaml"
    inventory = DeviceInventory()
    topology = inventory.load_from_yaml(topology_path)

    print(f"\nNetwork: {topology.name}")
    print(f"Devices: {len(topology.devices)}\n")

    # Create SSH manager
    manager = MultiSSHClientManager()
    manager.register_topology(topology)

    # Test each device
    for device_id, client in manager.clients.items():
        dev = client.device
        print(f"[{device_id}] Testing {dev.user}@{dev.host}:{dev.port} ({dev.role})...")
        result = await client.test_connection()
        if result["connected"]:
            print(f"  ✓ Connected successfully")

            # Get basic info
            try:
                board = await client.execute("ubus call system board")
                if board["success"]:
                    import json
                    info = json.loads(board["stdout"])
                    hostname = info.get("hostname", "?")
                    model = info.get("model", "?")
                    release = info.get("release", {})
                    distro = release.get("description", "?")
                    print(f"  Hostname : {hostname}")
                    print(f"  Model    : {model}")
                    print(f"  Firmware : {distro}")
            except Exception as e:
                print(f"  (Could not get system info: {e})")

            # Get uptime
            try:
                uptime_res = await client.execute("uptime")
                if uptime_res["success"]:
                    print(f"  Uptime   : {uptime_res['stdout']}")
            except Exception:
                pass

            # Get IP addresses
            try:
                ip_res = await client.execute("ip addr show")
                if ip_res["success"]:
                    # Extract IPs  
                    import re
                    ips = re.findall(r'inet (\d+\.\d+\.\d+\.\d+/\d+)', ip_res["stdout"])
                    print(f"  IPs      : {', '.join(ips)}")
            except Exception:
                pass

        else:
            print(f"  ✗ FAILED: {result.get('error', 'Unknown error')}")
        print()

    # Cleanup
    await manager.disconnect_all()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
