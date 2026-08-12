#!/usr/bin/env python3
"""Quick iperf3 test over HaLow to verify data path works."""
import asyncio
import asyncssh


async def ssh_run(host, cmd, timeout=60):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()


async def main():
    EDGE = "192.168.1.111"  # SSH via Ethernet
    TUBE = "192.168.1.103"

    # Ensure host route is set
    print("[1] Setting host route on Edge...")
    out = await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196; ip route get 192.168.1.103")
    print(f"    {out}")

    # Ensure static ARP on Tube
    print("[2] Setting static ARP on Tube...")
    out = await ssh_run(TUBE, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent; echo OK")
    print(f"    {out}")

    # Kill any existing iperf3
    for host in [EDGE, TUBE]:
        try:
            await ssh_run(host, "killall iperf3 2>/dev/null; echo cleaned", timeout=5)
        except:
            pass
    await asyncio.sleep(1)

    # Test 1: Upload (Edge → Tube) - Server on Tube, client on Edge
    print("\n[3] UPLOAD TEST: Edge → Tube via HaLow (10s)...")
    # Start server on Tube
    await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
    await asyncio.sleep(2)

    try:
        # Client on Edge, bind to HaLow IP
        out = await ssh_run(EDGE,
            "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 10 -i 2 2>&1",
            timeout=30
        )
        print(out)
    except Exception as e:
        print(f"    Upload ERROR: {e}")

    await asyncio.sleep(2)
    try:
        await ssh_run(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    except:
        pass

    # Test 2: Download (Tube → Edge) - Server on Edge, client on Tube
    print("\n[4] DOWNLOAD TEST: Tube → Edge via HaLow (10s)...")
    # Start server on Edge bound to HaLow IP
    await ssh_run(EDGE, "iperf3 -s -B 192.168.1.196 -D -1", timeout=10)
    await asyncio.sleep(2)

    try:
        out = await ssh_run(TUBE,
            "iperf3 -c 192.168.1.196 -t 10 -i 2 2>&1",
            timeout=60
        )
        print(out)
    except Exception as e:
        print(f"    Download ERROR: {e}")

    # Cleanup
    try:
        await ssh_run(EDGE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    except:
        pass

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
