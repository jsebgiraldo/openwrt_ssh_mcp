#!/usr/bin/env python3
"""Quick ping test after power save disabled."""
import asyncio
import asyncssh

async def main():
    async with asyncssh.connect(
        "192.168.1.111", port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as c:
        # Ensure route and power save off
        r = await c.run(
            "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196; "
            "iw dev wlan0 set power_save off 2>/dev/null; "
            "ping -c 10 -W 5 -i 1 192.168.1.103 2>&1",
            timeout=60
        )
        print("Edge -> Tube via HaLow (after PS off):")
        print(r.stdout)
        
        # Also check signal/rate
        r = await c.run(
            "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit Rate'",
            timeout=10
        )
        print(f"\nEdge signal/rate: {r.stdout}")

asyncio.run(main())
