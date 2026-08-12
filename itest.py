#!/usr/bin/env python3
"""Run single iperf3 test. Usage: python itest.py [upload|download|udp500k|udp1m|udp2m]"""
import asyncio, asyncssh, sys, os

async def r(h, c, t=60):
    async with asyncssh.connect(h, username="root", password="root", known_hosts=None, login_timeout=10) as conn:
        return (await conn.run(c, timeout=t)).stdout.strip()

async def main():
    E = "192.168.1.111"
    T = "192.168.1.103"
    mode = sys.argv[1] if len(sys.argv) > 1 else "upload"
    
    # Ensure route + ARP
    await r(E, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    await r(T, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    # Kill existing
    for h in [E, T]:
        try: await r(h, "killall iperf3 2>/dev/null; echo ok", t=5)
        except: pass
    await asyncio.sleep(2)
    
    # Signal before
    out = await r(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"Signal: {out}")
    
    if mode == "upload":
        print("\n=== TCP UPLOAD (Edge->Tube, 15s) ===")
        await r(T, "iperf3 -s -D -1", t=10)
        await asyncio.sleep(3)
        out = await r(E, "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 15 -i 3 2>&1", t=50)
        print(out)
        
    elif mode == "download":
        print("\n=== TCP DOWNLOAD (Tube->Edge, 15s) via --reverse ===")
        await r(T, "iperf3 -s -D -1", t=10)
        await asyncio.sleep(3)
        out = await r(E, "iperf3 -c 192.168.1.103 -B 192.168.1.196 -R -t 15 -i 3 2>&1", t=50)
        print(out)
        
    elif mode.startswith("udp"):
        rate = mode.replace("udp", "").upper()
        if not rate: rate = "1M"
        print(f"\n=== UDP UPLOAD {rate} (Edge->Tube, 10s) ===")
        await r(T, "iperf3 -s -D -1", t=10)
        await asyncio.sleep(3)
        out = await r(E, f"iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b {rate} -t 10 -i 5 2>&1", t=30)
        print(out)
    
    # Cleanup
    for h in [E, T]:
        try: await r(h, "killall iperf3 2>/dev/null; echo ok", t=5)
        except: pass

asyncio.run(main())
