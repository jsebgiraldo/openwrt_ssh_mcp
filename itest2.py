#!/usr/bin/env python3
"""Run iperf3 tests - prints during waits to prevent terminal killing."""
import asyncio, asyncssh, os, time

async def ssh_run(host, cmd, timeout=60):
    async with asyncssh.connect(host, username="root", password="root", known_hosts=None, login_timeout=10) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def wait_with_output(seconds, msg=""):
    """Sleep while printing dots to keep stdout alive."""
    for i in range(seconds):
        print(".", end="", flush=True)
        await asyncio.sleep(1)
    print(f" {msg}")

async def main():
    E = "192.168.1.111"
    T = "192.168.1.103"
    
    print("=== 2 MHz iperf3 ALL TESTS ===\n", flush=True)
    
    # Check
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit|ESSID'")
    print(f"Edge: {out}", flush=True)
    
    # Routing
    await ssh_run(E, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    try:
        await ssh_run(E, "ip route replace default via 192.168.1.1 dev eth0 proto static src 192.168.1.111", timeout=5)
    except: pass
    await ssh_run(T, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    tests = [
        ("TCP_UP",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 15 -i 3",            25),
        ("TCP_DOWN", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -R -t 15 -i 3",         25),
        ("UDP_500K", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 500K -t 10 -i 5", 18),
        ("UDP_1M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 1M -t 10 -i 5",  18),
        ("UDP_2M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 2M -t 10 -i 5",  18),
    ]
    
    all_results = []
    
    for name, cmd, wait in tests:
        print(f"\n--- {name} ---", flush=True)
        
        # Kill
        for h in [E, T]:
            try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except: pass
        print("k", end="", flush=True)
        await asyncio.sleep(1)
        
        # Server
        await ssh_run(T, "iperf3 -s -D -1", timeout=10)
        print("s", end="", flush=True)
        await asyncio.sleep(2)
        
        # Client in background
        outf = f"/tmp/iperf_{name}.txt"
        await ssh_run(E, f"sh -c '({cmd}) > {outf} 2>&1 &'", timeout=10)
        print("c", end="", flush=True)
        
        # Wait with output
        await wait_with_output(wait, "done")
        
        # Read
        try:
            out = await ssh_run(E, f"cat {outf} 2>&1", timeout=10)
            print(out, flush=True)
            all_results.append((name, out))
        except Exception as e:
            print(f"read error: {e}", flush=True)
            all_results.append((name, f"ERROR: {e}"))
    
    # Final
    print("\n--- FINAL SIGNAL ---", flush=True)
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"Edge: {out}", flush=True)
    out = await ssh_run(T, "iwinfo wlan0 assoclist 2>/dev/null | head -4")
    print(f"Tube: {out}", flush=True)
    
    # Save
    rf = os.path.join(os.path.dirname(__file__), "results_2mhz_final.txt")
    with open(rf, 'w') as f:
        for n, d in all_results:
            f.write(f"\n{'='*50}\n{n}\n{'='*50}\n{d}\n")
    print(f"\nSaved: {rf}", flush=True)

asyncio.run(main())
