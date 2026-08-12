#!/usr/bin/env python3
"""Continue 8 MHz tests — pick up from UDP_1M after crash.
Link already associated at 8 MHz, routing in place.
Better error handling: retry SSH, catch timeouts.
"""
import asyncio, asyncssh, os, traceback

RESULTS = os.path.join(os.path.dirname(__file__), "results_8mhz_final.txt")

async def ssh_run(host, cmd, timeout=60, retries=3):
    for attempt in range(retries):
        try:
            async with asyncssh.connect(host, username="root", password="root",
                                         known_hosts=None, login_timeout=15) as conn:
                r = await conn.run(cmd, timeout=timeout)
                return r.stdout.strip()
        except Exception as e:
            print(f"  SSH attempt {attempt+1} failed: {e}", flush=True)
            if attempt < retries - 1:
                await asyncio.sleep(3)
    return f"SSH_ERROR after {retries} attempts"

async def wait_print(seconds, msg=""):
    for i in range(seconds):
        print(".", end="", flush=True)
        await asyncio.sleep(1)
    print(f" {msg}", flush=True)

async def main():
    E = "192.168.1.111"
    T = "192.168.1.103"
    
    print("=" * 60, flush=True)
    print("  8 MHz CONTINUATION — remaining tests", flush=True)
    print("=" * 60, flush=True)
    
    # Check link is still up
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Channel'")
    print(f"Edge status: {out}", flush=True)
    
    if "UNAL-HaLow" not in out:
        print("Link DOWN - need to re-associate...", flush=True)
        # Re-run morse_cli fix
        await ssh_run(E, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo ok", timeout=10)
        await ssh_run(E, "morse_cli -i wlan0 channel -c 908000 -o 8 -p 2 -n 3 2>&1", timeout=10)
        await ssh_run(E, "iw dev wlan0 set txpower fixed 2100 2>/dev/null; echo ok", timeout=5)
        await ssh_run(E, "iw dev wlan0 set power_save off 2>/dev/null; echo ok", timeout=5)
        await asyncio.sleep(1)
        await ssh_run(E,
            "wpa_supplicant_s1g -i wlan0 -c /var/run/wpa_supplicant-wlan0.conf "
            "-D nl80211 -B -P /var/run/wpa_supplicant_s1g-wlan0.pid", timeout=10)
        
        for t in range(2, 30, 2):
            await asyncio.sleep(2)
            out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
            print(f"  {t}s: {out}", flush=True)
            if "UNAL-HaLow" in out:
                print("  *** RE-ASSOCIATED ***", flush=True)
                break
        else:
            print("FAILED TO RE-ASSOCIATE!", flush=True)
            return
    
    # Make sure routing is correct
    print("[ROUTING] Verifying...", flush=True)
    await ssh_run(E, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    try:
        await ssh_run(E, "ip route replace default via 192.168.1.1 dev eth0 proto static src 192.168.1.111", timeout=5)
    except: pass
    await ssh_run(T, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    out = await ssh_run(E, "ping -c 3 -W 3 -i 0.5 192.168.1.103 2>&1 | tail -2", timeout=10)
    print(f"Ping: {out}", flush=True)
    
    # Signal info
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit|ESSID|Channel'")
    print(f"Edge: {out}", flush=True)
    out = await ssh_run(T, "iwinfo wlan0 assoclist 2>/dev/null | head -4")
    print(f"Tube: {out}", flush=True)
    
    # Previously completed (from terminal output):
    # TCP_UP:   1.43 Mbps sender / 819 Kbps receiver, 62 retrans
    # TCP_DOWN: 6.06 Mbps sender / 5.63 Mbps receiver, 0 retrans
    # UDP_500K: 500/487 Kbps, 2.1% loss, 11.6ms jitter
    
    prev_results = [
        ("TCP_UP", """Connecting to host 192.168.1.103, port 5201
[  5] local 192.168.1.196 port 47867 connected to 192.168.1.103 port 5201
[ ID] Interval           Transfer     Bitrate         Retr  Cwnd
[  5]   0.00-3.00   sec  2.00 MBytes  5.59 Mbits/sec   20   63.6 KBytes
[  5]   3.00-6.00   sec  0.00 Bytes  0.00 bits/sec   13   90.5 KBytes
[  5]   6.00-9.00   sec  0.00 Bytes  0.00 bits/sec   13   82.0 KBytes
[  5]   9.00-12.00  sec   573 KBytes  1.56 Mbits/sec    7   76.4 KBytes
[  5]  12.00-15.00  sec  0.00 Bytes  0.00 bits/sec    9    127 KBytes
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-15.00  sec  2.56 MBytes  1.43 Mbits/sec   62             sender
[  5]   0.00-15.35  sec  1.50 MBytes   819 Kbits/sec                  receiver

iperf Done."""),
        ("TCP_DOWN", """Connecting to host 192.168.1.103, port 5201
Reverse mode, remote host 192.168.1.103 is sending
[  5] local 192.168.1.196 port 48775 connected to 192.168.1.103 port 5201
[ ID] Interval           Transfer     Bitrate
[  5]   0.00-3.19   sec  2.75 MBytes  7.24 Mbits/sec
[  5]   3.19-6.10   sec  1.75 MBytes  5.04 Mbits/sec
[  5]   6.10-9.09   sec  1.12 MBytes  3.16 Mbits/sec
[  5]   9.09-12.07  sec  2.00 MBytes  5.62 Mbits/sec
[  5]  12.07-15.08  sec  2.50 MBytes  6.96 Mbits/sec
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-15.13  sec  10.9 MBytes  6.06 Mbits/sec    0             sender
[  5]   0.00-15.08  sec  10.1 MBytes  5.63 Mbits/sec                  receiver

iperf Done."""),
        ("UDP_500K", """Connecting to host 192.168.1.103, port 5201
[  5] local 192.168.1.196 port 34125 connected to 192.168.1.103 port 5201
[ ID] Interval           Transfer     Bitrate         Total Datagrams
[  5]   0.00-5.00   sec   305 KBytes   500 Kbits/sec  216
[  5]   5.00-10.00  sec   305 KBytes   500 Kbits/sec  216
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Jitter    Lost/Total Datagrams
[  5]   0.00-10.00  sec   611 KBytes   500 Kbits/sec  0.000 ms  0/432 (0%)  sender
[  5]   0.00-10.06  sec   598 KBytes   487 Kbits/sec  11.591 ms  9/432 (2.1%)  receiver

iperf Done."""),
    ]

    # Run remaining tests with error handling
    tests = [
        ("UDP_1M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 1M -t 10 -i 5",  20),
        ("UDP_2M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 2M -t 10 -i 5",  20),
        ("UDP_4M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 4M -t 10 -i 5",  20),
        ("UDP_8M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 8M -t 10 -i 5",  20),
    ]
    
    new_results = []
    
    for name, cmd, wait in tests:
        print(f"\n--- {name} ---", flush=True)
        try:
            for h in [E, T]:
                try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=8)
                except: pass
            print("k", end="", flush=True)
            await asyncio.sleep(2)
            
            out = await ssh_run(T, "iperf3 -s -D -1", timeout=10)
            print("s", end="", flush=True)
            await asyncio.sleep(3)
            
            outf = f"/tmp/iperf_{name}.txt"
            await ssh_run(E, f"sh -c '({cmd}) > {outf} 2>&1 &'", timeout=10)
            print("c", end="", flush=True)
            
            await wait_print(wait, "done")
            
            out = await ssh_run(E, f"cat {outf} 2>&1", timeout=15)
            print(out, flush=True)
            new_results.append((name, out))
        except Exception as e:
            err = f"ERROR: {e}\n{traceback.format_exc()}"
            print(err, flush=True)
            new_results.append((name, err))
            # Wait a bit before retrying next test
            await asyncio.sleep(5)
    
    # Final signal
    print("\n--- FINAL ---", flush=True)
    try:
        out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
        print(f"Edge: {out}", flush=True)
        out = await ssh_run(T, "iwinfo wlan0 assoclist 2>/dev/null | head -4")
        print(f"Tube: {out}", flush=True)
    except Exception as e:
        print(f"Final signal read error: {e}", flush=True)
    
    # Combine all results
    all_results = prev_results + new_results
    
    with open(RESULTS, 'w') as f:
        for n, d in all_results:
            f.write(f"\n{'='*50}\n{n}\n{'='*50}\n{d}\n")
    print(f"\nSaved: {RESULTS}", flush=True)

asyncio.run(main())
