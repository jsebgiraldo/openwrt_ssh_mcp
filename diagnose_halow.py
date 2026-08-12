"""Diagnose HaLow link issue - check channels, bandwidth compatibility, and scan."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from openwrt_ssh_mcp.devices import DeviceInventory
from openwrt_ssh_mcp.multi_ssh_client import MultiSSHClientManager

async def main():
    inv = DeviceInventory()
    topo = inv.load_from_yaml("network_topology.yaml")
    mgr = MultiSSHClientManager()
    mgr.register_topology(topo)
    await mgr.connect_all()

    for dev_id in ["edge_gateway", "halow_router"]:
        c = mgr.clients[dev_id]
        print(f"\n{'='*60}")
        print(f"  {dev_id.upper()}")
        print(f"{'='*60}")

        cmds = [
            ("Current wireless config", "uci show wireless"),
            ("iwinfo wlan0 info", "iwinfo wlan0 info"),
            ("iwinfo wlan0 freqlist", "iwinfo wlan0 freqlist 2>/dev/null | head -40"),
            ("iwinfo mesh0 info (router)", "iwinfo mesh0 info 2>/dev/null || echo 'no mesh0'"),
            ("wlan0 operstate", "cat /sys/class/net/wlan0/operstate 2>/dev/null || echo 'N/A'"),
            ("iw dev wlan0 link", "iw dev wlan0 link 2>/dev/null || echo 'iw not available'"),
            ("iw dev wlan0 scan (STA only)", "iw dev wlan0 scan 2>/dev/null | head -60 || echo 'scan unavailable'"),
            ("dmesg morse", "dmesg | grep -i 'morse\\|halow\\|wlan0\\|s1g' | tail -30"),
            ("logread wifi errors", "logread | grep -i 'wlan0\\|wireless\\|hostapd\\|wpa_supplicant\\|morse' | tail -30"),
            ("wpa_supplicant status", "wpa_cli -i wlan0 status 2>/dev/null || echo 'wpa_cli unavailable'"),
        ]

        for label, cmd in cmds:
            print(f"\n--- {label} ---")
            r = await c.execute(cmd)
            out = r["stdout"] if r["success"] else f"ERROR: {r['stderr']}"
            print(out[:2000])

    await mgr.disconnect_all()

asyncio.run(main())
