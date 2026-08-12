#!/usr/bin/env python3
"""Run iperf3 tests using background execution and file output to avoid SSH timeout issues."""
import asyncio
import asyncssh
import os

async def ssh_run(host, cmd, timeout=60):
    async with asyncssh.connect(host, username="root", password="root", known_hosts=None, login_timeout=10) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def main():
    E = "192.168.1.111"  # Edge SSH via eth0
    T = "192.168.1.103"  # Tube SSH via eth0/bridge
    
    print("=== 2 MHz iperf3 Tests (file-based) ===\n")
    
    # Check link
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | head -8")
    print(f"Edge status:\n{out}\n")
    
    # Fix routing back to just host route (undo any aggressive routing changes)
    await ssh_run(E, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    # Restore eth0 default if needed 
    try:
        await ssh_run(E, "ip route replace default via 192.168.1.1 dev eth0 proto static src 192.168.1.111", timeout=5)
    except:
        pass
    
    # ARP
    await ssh_run(T, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    # Kill existing
    for h in [E, T]:
        try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except: pass
    await asyncio.sleep(2)
    
    # Ping check first
    out = await ssh_run(E, "ping -c 3 -W 3 192.168.1.103 2>&1 | tail -2", timeout=15)
    print(f"Ping check: {out}\n")
    
    tests = [
        ("TCP_UPLOAD", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 15 -i 3", E),
        ("TCP_DOWNLOAD", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -R -t 15 -i 3", E),
        ("UDP_500K", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 500K -t 10 -i 5", E),
        ("UDP_1M", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 1M -t 10 -i 5", E),
        ("UDP_2M", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 2M -t 10 -i 5", E),
    ]
    
    results = {}
    
    for name, client_cmd, client_host in tests:
        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")
        
        # Kill any existing
        for h in [E, T]:
            try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except: pass
        await asyncio.sleep(2)
        
        # Start server on Tube in background
        await ssh_run(T, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(3)
        
        # Run client on Edge, redirect output to file
        outfile = f"/tmp/iperf_{name}.txt"
        bg_cmd = f"({client_cmd}) > {outfile} 2>&1; echo DONE >> {outfile}"
        
        # Start the test in background on Edge
        await ssh_run(E, f"nohup sh -c '{bg_cmd}' &", timeout=10)
        
        # Wait for test to complete (15s test + buffer)
        wait_time = 30 if "TCP" in name else 20
        print(f"  Waiting {wait_time}s for test...")
        await asyncio.sleep(wait_time)
        
        # Read results
        try:
            out = await ssh_run(E, f"cat {outfile} 2>&1", timeout=10)
            print(out)
            results[name] = out
        except Exception as e:
            print(f"  Error reading: {e}")
            results[name] = f"ERROR: {e}"
    
    # Final signal
    print(f"\n{'='*50}")
    print("Signal after all tests:")
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"  Edge: {out}")
    out = await ssh_run(T, "iwinfo wlan0 assoclist 2>/dev/null | head -4")
    print(f"  Tube: {out}")
    
    # Save results
    res_file = os.path.join(os.path.dirname(__file__), "results_2mhz_final.txt")
    with open(res_file, 'w') as f:
        for name, data in results.items():
            f.write(f"\n{'='*50}\n{name}\n{'='*50}\n{data}\n")
    print(f"\nSaved to: {res_file}")

asyncio.run(main())
