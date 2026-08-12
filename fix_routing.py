#!/usr/bin/env python3
"""
Fix routing to ensure iperf3 traffic flows over HaLow, not Ethernet.

Problems found:
  1. Edge routes to 192.168.1.103 via eth0 (Ethernet) NOT wlan0 (HaLow)
  2. Tube ARP for .196 = FAILED (can't reach Edge over HaLow for download tests)

Fix:
  1. Add host route on Edge: 192.168.1.103 via wlan0 (HaLow)
  2. Fix ARP/connectivity from Tube to Edge .196
  3. Verify bidirectional ping over HaLow
"""
import asyncio
import asyncssh

EDGE_ETH = {"host": "192.168.1.111", "user": "root", "password": "root", "name": "Edge (Ethernet)"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM"}


async def ssh_run(dev, cmd, timeout=20):
    async with asyncssh.connect(
        dev["host"], port=22, username=dev["user"],
        password=dev["password"], known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip()


async def main():
    print("=" * 60)
    print("  FIX ROUTING FOR HALOW TESTS")
    print("=" * 60)

    # Step 1: Add host route on Edge forcing .103 via wlan0
    print("\n[1] Adding host route on Edge: 192.168.1.103 via wlan0...")
    out, err = await ssh_run(EDGE_ETH,
        "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196; "
        "ip route get 192.168.1.103"
    )
    print(f"    Route: {out}")
    if err:
        print(f"    Err: {err}")

    # Step 2: Verify Edge now routes to .103 via wlan0
    print("\n[2] Verifying Edge ping to Tube via HaLow...")
    out, err = await ssh_run(EDGE_ETH,
        "ping -c 5 -W 3 192.168.1.103",
        timeout=30
    )
    print(f"    {out}")

    # Step 3: Check if Tube can reach .196 via HaLow
    print("\n[3] Testing Tube -> Edge (.196) via HaLow bridge...")
    out, err = await ssh_run(TUBE,
        "ping -c 5 -W 3 192.168.1.196",
        timeout=30
    )
    print(f"    {out}")

    if "0% packet loss" not in out and "0 packets received" not in out:
        # If Tube can't reach .196, try adding static ARP
        print("\n[3b] Trying static ARP on Tube for .196...")
        # Edge's wlan0 MAC: 0C:BF:74:1C:DE:87
        out, err = await ssh_run(TUBE,
            "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent; "
            "ping -c 5 -W 3 192.168.1.196",
            timeout=30
        )
        print(f"    {out}")

    # Step 4: Final bidirectional verification
    print("\n[4] Final bidirectional ping verification...")
    
    # Edge -> Tube (should now go via HaLow wlan0)
    out, err = await ssh_run(EDGE_ETH,
        "ip route get 192.168.1.103; echo ---; "
        "ping -c 3 -W 2 192.168.1.103",
        timeout=20
    )
    print(f"\n  Edge -> Tube:\n    {out}")

    # Tube -> Edge .196 (should go via HaLow bridge)
    out, err = await ssh_run(TUBE,
        "ip route get 192.168.1.196; echo ---; "
        "ping -c 3 -W 2 192.168.1.196",
        timeout=20
    )
    print(f"\n  Tube -> Edge:\n    {out}")

    # Step 5: Verify SSH management via .111 still works
    print("\n[5] Verifying SSH management via .111 still works...")
    out, err = await ssh_run(EDGE_ETH, "echo OK; uptime")
    print(f"    {out}")

    print("\n" + "=" * 60)
    print("  ROUTING FIX COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
