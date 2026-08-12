#!/usr/bin/env python3
"""
Fix routing and connectivity for HaLow tests - step by step with better timeouts.
"""
import asyncio
import asyncssh

EDGE_ETH = {"host": "192.168.1.111", "user": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root"}


async def ssh_run(dev, cmd, timeout=30):
    async with asyncssh.connect(
        dev["host"], port=22, username=dev["user"],
        password=dev["password"], known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()


async def main():
    print("=" * 60)
    print("  STEP-BY-STEP HALOW ROUTING FIX")
    print("=" * 60)

    # Step 1: Verify HaLow link is still associated
    print("\n[1] Edge HaLow status...")
    out = await ssh_run(EDGE_ETH,
        "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit Rate|Channel'"
    )
    print(f"    {out}")

    # Step 2: Check current morse_cli channel
    print("\n[2] Edge morse_cli channel...")
    out = await ssh_run(EDGE_ETH, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"    {out}")

    # Step 3: Add host route on Edge to force .103 via wlan0
    print("\n[3] Adding host route on Edge...")
    out = await ssh_run(EDGE_ETH,
        "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196; "
        "echo 'Route added'; ip route get 192.168.1.103"
    )
    print(f"    {out}")

    # Step 4: Longer ping test Edge -> Tube via HaLow (10 pings, longer timeout)
    print("\n[4] Edge -> Tube ping via HaLow (10 pings)...")
    out = await ssh_run(EDGE_ETH,
        "ping -c 10 -W 5 -i 1 192.168.1.103",
        timeout=60
    )
    # Just show summary
    for line in out.split('\n'):
        if 'transmitted' in line or 'rtt' in line or 'round-trip' in line:
            print(f"    {line.strip()}")

    # Step 5: On Tube, add static ARP for .196 with Edge's wlan0 MAC
    print("\n[5] Adding static ARP on Tube for .196...")
    out = await ssh_run(TUBE,
        "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent; "
        "ip neigh show | grep 196"
    )
    print(f"    {out}")

    # Step 6: Tube -> Edge .196 ping via HaLow
    print("\n[6] Tube -> Edge .196 ping via HaLow (10 pings)...")
    try:
        out = await ssh_run(TUBE,
            "ping -c 10 -W 5 -i 1 192.168.1.196",
            timeout=60
        )
        for line in out.split('\n'):
            if 'transmitted' in line or 'rtt' in line or 'round-trip' in line or 'bytes from' in line:
                print(f"    {line.strip()}")
    except Exception as e:
        print(f"    ERROR: {e}")

    # Step 7: Verify SSH management still works
    print("\n[7] SSH management via .111 OK...")
    out = await ssh_run(EDGE_ETH, "echo OK; uptime")
    print(f"    {out}")

    # Step 8: Check Tube assoclist for Edge
    print("\n[8] Tube assoclist (Edge signal as seen by AP)...")
    out = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
    print(f"    {out}")

    print("\n" + "=" * 60)
    print("  ROUTING FIX COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
