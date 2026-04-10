"""Script with IPv6 optimization suggestions for OpenWRT."""

import asyncio
from openwrt_ssh_mcp.ssh_client import ssh_client

async def optimize_ipv6():
    """Print IPv6 optimization suggestions for the router."""

    print("=" * 70)
    print("IPv6 OPTIMIZATION SUGGESTIONS")
    print("=" * 70)

    await ssh_client.connect()

    print("""
Your current IPv6 configuration is functional. The following are
optional improvements:

1. CHANGE /60 TO /64 ON LAN (simpler)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Current:     lan.ip6assign='60'  (16 subnets)
   Recommended: lan.ip6assign='64'  (1 subnet, simpler)

   With a /56 from the ISP you have 256 /64 subnets available.
   Unless you need multiple VLANs, /64 is sufficient.

   Commands:
   uci set network.lan.ip6assign='64'
   uci commit network
   /etc/init.d/network restart

2. ENABLE RA EXPLICITLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Ensures LAN devices receive network advertisements.

   Commands:
   uci set dhcp.lan.ra='server'
   uci set dhcp.lan.dhcpv6='server'
   uci set dhcp.lan.ra_management='1'
   uci commit dhcp
   /etc/init.d/odhcpd restart

3. CONFIGURE IPv6 DNS SERVERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Public IPv6 DNS options:
   • Google:     2001:4860:4860::8888, 2001:4860:4860::8844
   • Cloudflare: 2606:4700:4700::1111, 2606:4700:4700::1001
   • Quad9:      2620:fe::fe, 2620:fe::9

   Commands:
   uci add_list network.wan6.dns='2001:4860:4860::8888'
   uci add_list network.wan6.dns='2001:4860:4860::8844'
   uci commit network
   /etc/init.d/network restart

4. VERIFY IPv6 FIREWALL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Check:
   ip6tables -L -n -v

   To open a port (e.g. HTTP):
   uci add firewall rule
   uci set firewall.@rule[-1].name='Allow-HTTP-IPv6'
   uci set firewall.@rule[-1].src='wan'
   uci set firewall.@rule[-1].proto='tcp'
   uci set firewall.@rule[-1].dest_port='80'
   uci set firewall.@rule[-1].family='ipv6'
   uci set firewall.@rule[-1].target='ACCEPT'
   uci commit firewall
   /etc/init.d/firewall restart

5. DISABLE ULA IF NOT NEEDED (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   If you only use public IPv6, you can disable ULA.

   Command:
   uci set network.globals.ula_prefix=''
   uci commit network
   /etc/init.d/network restart

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    # Current DHCP/RA config
    print("CURRENT DHCP/RA CONFIGURATION:")
    print("-" * 70)
    result = await ssh_client.execute("uci show dhcp | grep -E 'dhcp.lan|ra|dhcpv6'")
    if result["success"]:
        print(result["stdout"])

    await ssh_client.disconnect()

if __name__ == "__main__":
    asyncio.run(optimize_ipv6())
