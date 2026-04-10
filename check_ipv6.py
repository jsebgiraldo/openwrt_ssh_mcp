"""Script to verify IPv6 status on OpenWRT."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openwrt_ssh_mcp.ssh_client import ssh_client
from openwrt_ssh_mcp.tools import OpenWRTTools

async def check_ipv6():
    """Verify the IPv6 configuration on the router."""

    print("=" * 70)
    print("IPv6 STATUS CHECK — OPENWRT")
    print("=" * 70)

    await ssh_client.connect()
    tools = OpenWRTTools()

    # 1. Current network UCI config
    print("\n1. CURRENT NETWORK CONFIGURATION (UCI)")
    print("-" * 70)
    result = await tools.read_config("network")
    if result["success"]:
        config = result.get("config", "")
        for line in config.split("\n"):
            if "ipv6" in line.lower() or "ip6" in line.lower() or line.startswith("network.wan") or line.startswith("network.lan"):
                print(line)

    # 2. Assigned IPv6 addresses
    print("\n2. ASSIGNED IPv6 ADDRESSES")
    print("-" * 70)
    result = await ssh_client.execute("ip -6 addr show")
    if result["success"]:
        print(result["stdout"])

    # 3. IPv6 routes
    print("\n3. IPv6 ROUTES")
    print("-" * 70)
    result = await ssh_client.execute("ip -6 route show")
    if result["success"]:
        routes = result["stdout"].strip()
        if routes:
            print(routes)
        else:
            print("No IPv6 routes configured")

    # 4. DHCPv6 / SLAAC services
    print("\n4. IPv6 SERVICE STATUS")
    print("-" * 70)
    result = await ssh_client.execute("ps | grep -E 'odhcp|dhcp6'")
    if result["success"]:
        output = result["stdout"].strip()
        if output:
            print("Active DHCP processes:")
            print(output)
        else:
            print("No DHCPv6 processes detected")

    # 5. IPv6 firewall rules
    print("\n5. IPv6 FIREWALL RULES")
    print("-" * 70)
    result = await ssh_client.execute("ip6tables -L -n | head -20")
    if result["success"]:
        print(result["stdout"])

    # 6. External IPv6 connectivity
    print("\n6. IPv6 CONNECTIVITY TEST")
    print("-" * 70)
    result = await ssh_client.execute("ping6 -c 3 2001:4860:4860::8888")
    if result["success"]:
        if "0% packet loss" in result["stdout"]:
            print("IPv6 connectivity to Google DNS: OK")
        else:
            print("IPv6 connectivity issues detected")
        print(result["stdout"][:300])
    else:
        print("No external IPv6 connectivity")
        print(result["stderr"][:200])

    # 7. ISP delegated prefix
    print("\n7. DELEGATED IPv6 PREFIX (from ISP)")
    print("-" * 70)
    result = await ssh_client.execute("ubus call network.interface.wan6 status 2>/dev/null")
    if result["success"]:
        print(result["stdout"][:500])
    else:
        print("wan6 interface not available")

    await ssh_client.disconnect()

    print("\n" + "=" * 70)
    print("CHECK COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(check_ipv6())
