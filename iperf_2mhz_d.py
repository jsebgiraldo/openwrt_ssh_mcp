#!/usr/bin/env python3
"""iperf3 tests at 2 MHz - writes results to file."""
import asyncio
import asyncssh
import sys
import os

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results_2mhz.txt")

class Tee:
    def __init__(self, file_path):
        self.file = open(file_path, 'w', encoding='utf-8')
        self.stdout = sys.stdout
    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)
        self.file.flush()
    def flush(self):
        self.stdout.flush()
        self.file.flush()
    def close(self):
        self.file.close()

async def ssh_run(host, cmd, timeout=60):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def kill_iperf(hosts):
    for h in hosts:
        try:
            await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except:
            pass
    await asyncio.sleep(1)

async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    tee = Tee(RESULTS_FILE)
    sys.stdout = tee
    
    try:
        print("2 MHz COMPLETE iperf3 Tests")
        print("=" * 50)
        
        # Check link
        out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit|ESSID'")
        print(f"Edge: {out}")
        
        # Ensure route + ARP
        await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
        await ssh_run(TUBE, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
        
        await kill_iperf([EDGE, TUBE])
        
        # ============ TCP UPLOAD ============
        print("\n" + "=" * 50)
        print("[1] TCP UPLOAD (Edge -> Tube, 15s)")
        print("=" * 50)
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)
        try:
            out = await ssh_run(EDGE,
                "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 15 -i 3 2>&1",
                timeout=45)
            print(out)
        except Exception as e:
            print(f"Error: {e}")
        await kill_iperf([EDGE, TUBE])
        await asyncio.sleep(2)
        
        # ============ TCP DOWNLOAD via --reverse ============
        print("\n" + "=" * 50)
        print("[2] TCP DOWNLOAD (Tube -> Edge, 15s) --reverse")
        print("=" * 50)
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)
        try:
            out = await ssh_run(EDGE,
                "iperf3 -c 192.168.1.103 -B 192.168.1.196 -R -t 15 -i 3 2>&1",
                timeout=45)
            print(out)
        except Exception as e:
            print(f"Error: {e}")
        await kill_iperf([EDGE, TUBE])
        await asyncio.sleep(2)
        
        # ============ UDP 500K ============
        print("\n" + "=" * 50)
        print("[3] UDP UPLOAD 500K (Edge->Tube, 10s)")
        print("=" * 50)
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)
        try:
            out = await ssh_run(EDGE,
                "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 500K -t 10 -i 5 2>&1",
                timeout=30)
            print(out)
        except Exception as e:
            print(f"Error: {e}")
        await kill_iperf([EDGE, TUBE])
        await asyncio.sleep(2)
        
        # ============ UDP 1M ============
        print("\n" + "=" * 50)
        print("[4] UDP UPLOAD 1M (Edge->Tube, 10s)")
        print("=" * 50)
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)
        try:
            out = await ssh_run(EDGE,
                "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 1M -t 10 -i 5 2>&1",
                timeout=30)
            print(out)
        except Exception as e:
            print(f"Error: {e}")
        await kill_iperf([EDGE, TUBE])
        await asyncio.sleep(2)
        
        # ============ UDP 2M ============
        print("\n" + "=" * 50)
        print("[5] UDP UPLOAD 2M (Edge->Tube, 10s)")
        print("=" * 50)
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(2)
        try:
            out = await ssh_run(EDGE,
                "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 2M -t 10 -i 5 2>&1",
                timeout=30)
            print(out)
        except Exception as e:
            print(f"Error: {e}")
        await kill_iperf([EDGE, TUBE])
        
        # Final signal
        print("\n" + "=" * 50)
        print("Signal after all tests:")
        out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
        print(f"  Edge: {out}")
        out = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null | head -3")
        print(f"  Tube assoc: {out}")
        
        print("\n=== 2 MHz TESTS COMPLETE ===")
    finally:
        sys.stdout = tee.stdout
        tee.close()
    
    print(f"\nResults saved to: {RESULTS_FILE}")

asyncio.run(main())
