#!/usr/bin/env python3
"""Quick iperf3 test at 2 MHz."""
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
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    print("2 MHz iperf3 Quick Test")
    print("=" * 50)
    
    # Ensure route
    await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    
    # Kill existing
    for h in [EDGE, TUBE]:
        try:
            await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(1)
    
    # Test 1: Upload (Edge -> Tube) 
    print("\n[1] TCP UPLOAD (Edge->Tube, 15s):")
    await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
    await asyncio.sleep(2)
    try:
        out = await ssh_run(EDGE, 
            "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 15 -i 3 2>&1",
            timeout=40)
        print(out)
    except Exception as e:
        print(f"Error: {e}")
    
    try:
        await ssh_run(TUBE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    except:
        pass
    await asyncio.sleep(2)
    
    # Test 2: Download (Tube -> Edge)
    print("\n[2] TCP DOWNLOAD (Tube->Edge, 15s):")
    # Static ARP on Tube
    await ssh_run(TUBE, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent; echo ok")
    
    await ssh_run(EDGE, "iperf3 -s -B 192.168.1.196 -D -1", timeout=10)
    await asyncio.sleep(2)
    try:
        out = await ssh_run(TUBE,
            "iperf3 -c 192.168.1.196 -t 15 -i 3 2>&1",
            timeout=40)
        print(out)
    except Exception as e:
        print(f"Error: {e}")
    
    try:
        await ssh_run(EDGE, "killall iperf3 2>/dev/null; echo ok", timeout=5)
    except:
        pass
    
    # Signal after tests
    print("\n[3] Signal levels after tests:")
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"  Edge: {out}")
    out = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
    print(f"  Tube: {out}")
    
    print("\nDone!")

asyncio.run(main())
