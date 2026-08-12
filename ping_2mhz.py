#!/usr/bin/env python3
"""Quick ping test at 2 MHz - debug version."""
import asyncio
import asyncssh

async def main():
    EDGE = "192.168.1.111"
    
    async with asyncssh.connect(
        EDGE, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as c:
        # Check current state
        r = await c.run("iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit'", timeout=10)
        print(f"Status: {r.stdout.strip()}")
        
        # Check route
        r = await c.run("ip route get 192.168.1.103", timeout=5)
        print(f"Route: {r.stdout.strip()}")
        
        # Set route if needed
        r = await c.run("ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196; echo ROUTE_SET", timeout=5)
        print(r.stdout.strip())
        
        # Check ARP
        r = await c.run("ip neigh show dev wlan0 2>/dev/null; echo ---; arp -a 2>/dev/null | grep 103", timeout=5)
        print(f"ARP: {r.stdout.strip()}")
        
        # Try arping first to resolve ARP
        r = await c.run("arping -c 3 -I wlan0 192.168.1.103 2>&1; echo RC=$?", timeout=15)
        print(f"Arping: {r.stdout.strip()}")
        
        # Now ping
        print("\nPing test (5 pings):")
        r = await c.run("ping -c 5 -W 3 192.168.1.103 2>&1", timeout=30)
        print(r.stdout.strip())

asyncio.run(main())
