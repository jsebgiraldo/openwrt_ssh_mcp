"""Script to explain IPv6 Prefix Delegation on the router."""

import asyncio
from openwrt_ssh_mcp.ssh_client import ssh_client

async def explain_pd():
    """Show IPv6 Prefix Delegation information."""

    print("=" * 70)
    print("IPv6 PREFIX DELEGATION (PD) — YOUR ROUTER")
    print("=" * 70)

    await ssh_client.connect()

    print("""
┌────────────────────────────────────────────────────────────────┐
│ WHAT IS IPv6 PREFIX DELEGATION (PD)?                           │
└────────────────────────────────────────────────────────────────┘

Your ISP does not give you a single IP address. Instead it says:

  "Here is an entire block of addresses — organize it as you like."

┌────────────────────────────────────────────────────────────────┐
│ DELEGATION PROCESS                                             │
└────────────────────────────────────────────────────────────────┘

1. OpenWRT connects to the ISP via DHCPv6

2. Router requests: "I need a prefix for my local network"

3. ISP replies: "Here is 2800:484:8f7e:3200::/56"
   └─ = 256 complete /64 networks
   └─ 18 quintillion IPs per network

4. Router receives and stores the delegated prefix

5. Router chooses a subnet for LAN (e.g. subnet 'd0')
   └─ 2800:484:8f7e:32d0::/64

6. Router announces this subnet to devices via RA

7. Devices obtain IPs automatically within that subnet

┌────────────────────────────────────────────────────────────────┐
│ LIVE STATUS FROM YOUR ROUTER                                   │
└────────────────────────────────────────────────────────────────┘
""")

    # Show wan6 delegation status
    print("wan6 interface (receives delegation):")
    print("-" * 70)
    result = await ssh_client.execute("ubus call network.interface.wan6 status | grep -A 20 delegation")
    if result["success"]:
        print(result["stdout"])

    # Show delegated prefix
    print("\nDELEGATED PREFIX FROM ISP:")
    print("-" * 70)
    result = await ssh_client.execute("ubus call network.interface.wan6 status")
    if result["success"]:
        import json
        try:
            data = json.loads(result["stdout"])
            if "ipv6-prefix" in data:
                print("Received prefixes:")
                for prefix in data["ipv6-prefix"]:
                    address = prefix.get("address", "N/A")
                    mask = prefix.get("mask", "N/A")
                    print(f"  {address}/{mask}")
                    print(f"    Valid:     {prefix.get('valid', 'N/A')} seconds")
                    print(f"    Preferred: {prefix.get('preferred', 'N/A')} seconds")

            if "ipv6-prefix-assignment" in data:
                print("\nPREFIX ASSIGNMENTS TO LOCAL INTERFACES:")
                for assignment in data["ipv6-prefix-assignment"]:
                    iface = assignment.get("interface", "N/A")
                    address = assignment.get("address", "N/A")
                    mask = assignment.get("mask", "N/A")
                    print(f"  {iface}: {address}/{mask}")
        except Exception:
            print(result["stdout"][:800])

    # Show UCI config
    print("\nUCI CONFIGURATION (wan6):")
    print("-" * 70)
    result = await ssh_client.execute("uci show network.wan6")
    if result["success"]:
        for line in result["stdout"].split("\n"):
            if line.strip():
                print(f"  {line}")

    print("\n" + "=" * 70)
    print("""
┌────────────────────────────────────────────────────────────────┐
│ KEY UCI PARAMETERS                                             │
└────────────────────────────────────────────────────────────────┘

• proto='dhcpv6'
  └─ Protocol to request IP and prefix from ISP

• reqaddress='try'
  └─ Request one IPv6 address for the WAN interface
  └─ Options: 'none', 'try', 'force'

• reqprefix='auto'
  └─ THIS IS PREFIX DELEGATION
  └─ Requests a full IP range from ISP
  └─ Options: 'auto', 'no', or a number (48, 56, 60, 64)
  └─ 'auto' = accept whatever the ISP offers

┌────────────────────────────────────────────────────────────────┐
│ ADVANTAGES OF IPv6-PD                                          │
└────────────────────────────────────────────────────────────────┘

- No NAT needed (each device gets a public IP)
- Better performance (end-to-end connectivity)
- Multiple subnets possible (guest, IoT, servers, …)
- Easier to host services
- Prefix renews automatically
- Scales to thousands of devices
""")

    await ssh_client.disconnect()

    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(explain_pd())
