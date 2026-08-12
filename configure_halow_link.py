"""
Configure HaLow link between Edge Gateway and HaLow Router for UNAL thesis.

Topology:
  Internet ── WAN Router (192.168.1.1) ── [eth] ── HaLow Router (AP) ~~~ HaLow ~~~ Edge Gateway (STA)

Changes:
  1. HaLow Router: Rename AP SSID, set channel 48, s1g_chanbw=8, password sync
  2. Edge Gateway: Switch from AP to STA, point to router's AP, DHCP on ahwlan
  3. Both: Update hostnames for thesis

"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from openwrt_ssh_mcp.devices import DeviceInventory
from openwrt_ssh_mcp.multi_ssh_client import MultiSSHClientManager

# ============ THESIS CONFIGURATION ============
HALOW_SSID = "UNAL-HaLow-Tesis"
HALOW_KEY = "banano2026"
HALOW_CHANNEL = "48"
HALOW_CHANBW = "8"           # 8 MHz = maximum bandwidth for S1G
HALOW_ENCRYPTION = "sae"     # WPA3 SAE

EDGE_HOSTNAME = "edge-gateway"
ROUTER_HOSTNAME = "halow-router"
# ===============================================


async def run_cmd(client, cmd, desc=""):
    """Execute command and print result."""
    tag = f"[{client.device.device_id}]"
    r = await client.execute(cmd)
    status = "OK" if r["success"] else "FAIL"
    if desc:
        print(f"  {tag} {desc}: {status}")
    if not r["success"]:
        print(f"    ERROR: {r['stderr']}")
    return r


async def configure_halow_router(mgr):
    """Configure the HaLow Router as AP with thesis parameters."""
    c = mgr.clients["halow_router"]
    print("\n" + "=" * 60)
    print("  PASO 1: Configurar HaLow Router como AP")
    print("=" * 60)

    # -- Radio: channel + max bandwidth --
    await run_cmd(c, f"uci set wireless.radio0.channel='{HALOW_CHANNEL}'", "Set channel")
    await run_cmd(c, f"uci set wireless.radio0.s1g_chanbw='{HALOW_CHANBW}'", "Set bandwidth 8MHz")

    # -- AP interface (meshap_radio0): rename SSID + password --
    await run_cmd(c, f"uci set wireless.meshap_radio0.ssid='{HALOW_SSID}'", "Set AP SSID")
    await run_cmd(c, f"uci set wireless.meshap_radio0.key='{HALOW_KEY}'", "Set AP password")
    await run_cmd(c, f"uci set wireless.meshap_radio0.encryption='{HALOW_ENCRYPTION}'", "Set AP encryption")
    await run_cmd(c, "uci set wireless.meshap_radio0.wds='1'", "Enable WDS on AP")
    await run_cmd(c, "uci set wireless.meshap_radio0.disabled='0'", "Ensure AP enabled")

    # -- Mesh interface: update password to match --
    await run_cmd(c, f"uci set wireless.default_radio0.key='{HALOW_KEY}'", "Sync mesh password")

    # -- System: hostname for thesis --
    await run_cmd(c, f"uci set system.system.hostname='{ROUTER_HOSTNAME}'", "Set hostname")

    # -- Commit & apply --
    print("\n  Committing changes...")
    await run_cmd(c, "uci commit wireless", "Commit wireless")
    await run_cmd(c, "uci commit system", "Commit system")

    print("  Restarting wifi (takes ~15s)...")
    await run_cmd(c, "wifi down; sleep 2; wifi up", "Restart wifi")
    await asyncio.sleep(15)

    # Reload system hostname
    await run_cmd(c, "/etc/init.d/system reload", "Reload system")

    # Verify
    print("\n  Verifying...")
    r = await run_cmd(c, "iwinfo wlan0 info", "Check AP iwinfo")
    if r["success"]:
        print(f"    {r['stdout'][:500]}")

    print("\n  HaLow Router configured!")


async def configure_edge_gateway(mgr):
    """Configure the Edge Gateway as STA connecting to HaLow Router."""
    c = mgr.clients["edge_gateway"]
    print("\n" + "=" * 60)
    print("  PASO 2: Configurar Edge Gateway como STA (cliente)")
    print("=" * 60)

    # -- Radio: match channel + bandwidth --
    await run_cmd(c, f"uci set wireless.radio0.channel='{HALOW_CHANNEL}'", "Set channel")
    await run_cmd(c, f"uci set wireless.radio0.s1g_chanbw='{HALOW_CHANBW}'", "Set bandwidth 8MHz")

    # -- Switch from AP to STA mode --
    await run_cmd(c, "uci set wireless.default_radio0.mode='sta'", "Set STA mode")
    await run_cmd(c, f"uci set wireless.default_radio0.ssid='{HALOW_SSID}'", "Set SSID to connect")
    await run_cmd(c, f"uci set wireless.default_radio0.key='{HALOW_KEY}'", "Set password")
    await run_cmd(c, f"uci set wireless.default_radio0.encryption='{HALOW_ENCRYPTION}'", "Set encryption")
    await run_cmd(c, "uci set wireless.default_radio0.wds='1'", "Enable WDS")

    # -- Network: ahwlan should get IP via DHCP through the HaLow bridge --
    await run_cmd(c, "uci set network.ahwlan.proto='dhcp'", "Set ahwlan to DHCP")
    # Remove static IP (it will get one from WAN router through the bridge)
    await run_cmd(c, "uci delete network.ahwlan.ipaddr 2>/dev/null; echo done", "Remove static IP")
    await run_cmd(c, "uci delete network.ahwlan.netmask 2>/dev/null; echo done", "Remove static netmask")

    # -- System: hostname for thesis --
    await run_cmd(c, f"uci set system.@system[0].hostname='{EDGE_HOSTNAME}'", "Set hostname")

    # -- Commit & apply --
    print("\n  Committing changes...")
    await run_cmd(c, "uci commit wireless", "Commit wireless")
    await run_cmd(c, "uci commit network", "Commit network")
    await run_cmd(c, "uci commit system", "Commit system")

    print("  Restarting wifi + network (takes ~20s)...")
    await run_cmd(c, "wifi down; sleep 2; wifi up", "Restart wifi")
    await asyncio.sleep(10)
    await run_cmd(c, "/etc/init.d/network restart", "Restart network")
    await asyncio.sleep(15)

    # Reload system hostname
    await run_cmd(c, "/etc/init.d/system reload", "Reload system")

    # Verify connection
    print("\n  Verifying HaLow STA connection...")
    r = await run_cmd(c, "iwinfo wlan0 info", "Check STA iwinfo")
    if r["success"]:
        print(f"    {r['stdout'][:500]}")

    r = await run_cmd(c, "ip addr show", "Check IPs")
    if r["success"]:
        print(f"    {r['stdout'][:800]}")

    print("\n  Edge Gateway configured!")


async def verify_link(mgr):
    """Verify the HaLow link between both devices."""
    print("\n" + "=" * 60)
    print("  PASO 3: Verificar enlace HaLow")
    print("=" * 60)

    # Check stations on router AP
    router = mgr.clients["halow_router"]
    r = await run_cmd(router, "iwinfo wlan0 assoclist", "Router: check connected stations")
    if r["success"]:
        print(f"    Stations:\n    {r['stdout'][:500]}")

    # Ping from edge to router
    edge = mgr.clients["edge_gateway"]

    # Ping to WAN router through HaLow
    print("\n  Testing connectivity from Edge through HaLow...")
    r = await run_cmd(edge, "ping -c 3 192.168.1.1", "Edge → WAN Router (192.168.1.1)")
    if r["success"]:
        print(f"    {r['stdout']}")

    r = await run_cmd(edge, "ping -c 3 192.168.1.103", "Edge → HaLow Router (192.168.1.103)")
    if r["success"]:
        print(f"    {r['stdout']}")

    # Check edge's new IP on ahwlan
    r = await run_cmd(edge, "ip addr show wlan0", "Edge wlan0 interface")
    if r["success"]:
        print(f"    {r['stdout']}")


async def main():
    print("=" * 60)
    print("  UNAL Tesis - HaLow Network Configuration")
    print("  Edge Gateway ←── HaLow ──→ Router")
    print("=" * 60)

    inv = DeviceInventory()
    topo = inv.load_from_yaml("network_topology.yaml")
    mgr = MultiSSHClientManager()
    mgr.register_topology(topo)

    print("\nConnecting to devices...")
    results = await mgr.connect_all()
    for dev, ok in results.items():
        print(f"  {dev}: {'OK' if ok else 'FAILED'}")

    if not all(results.values()):
        print("\nERROR: Not all devices connected. Aborting.")
        await mgr.disconnect_all()
        return

    try:
        # Step 1: Configure router first (it provides the AP)
        await configure_halow_router(mgr)

        # Step 2: Configure edge to connect as STA
        await configure_edge_gateway(mgr)

        # Step 3: Verify the link
        await verify_link(mgr)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await mgr.disconnect_all()

    print("\n" + "=" * 60)
    print("  Configuration complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
