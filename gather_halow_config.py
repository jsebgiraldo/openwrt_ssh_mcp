"""Gather full configuration from both HaLow devices."""
import asyncio, json
from openwrt_ssh_mcp.devices import DeviceInventory
from openwrt_ssh_mcp.multi_ssh_client import MultiSSHClientManager

async def main():
    inv = DeviceInventory()
    topo = inv.load_from_yaml("network_topology.yaml")
    mgr = MultiSSHClientManager()
    mgr.register_topology(topo)
    await mgr.connect_all()

    for dev_id in ["edge_gateway", "halow_router"]:
        client = mgr.clients[dev_id]
        print(f"\n{'='*60}")
        print(f"  {dev_id.upper()} ({client.device.host})")
        print(f"{'='*60}")

        cmds = [
            ("WIRELESS CONFIG", "uci show wireless"),
            ("NETWORK CONFIG", "uci show network"),
            ("SYSTEM CONFIG", "uci show system"),
            ("WIFI STATUS", "ubus call network.wireless status"),
            ("IP ADDRESSES", "ip addr show"),
            ("ROUTES", "ip route show"),
            ("IWINFO", "iwinfo 2>/dev/null || echo 'iwinfo not available'"),
            ("MORSE CLI STATUS", "morse_cli -i wlan0 status 2>/dev/null || echo 'morse_cli not available'"),
            ("HALOW IFACE", "cat /sys/class/net/wlan0/operstate 2>/dev/null || echo 'no wlan0'"),
            ("BANDWIDTH CONFIG", "cat /etc/config/morse 2>/dev/null || echo 'no morse config'"),
        ]

        for label, cmd in cmds:
            print(f"\n--- {label} ---")
            r = await client.execute(cmd)
            if r["success"]:
                print(r["stdout"][:3000])
            else:
                err = r["stderr"]
                print(f"ERROR: {err}")

    await mgr.disconnect_all()

asyncio.run(main())
