#!/usr/bin/env python3
"""Configure both devices for 4 MHz, associate, and run iperf3 tests."""
import asyncio, asyncssh, os, time

RESULTS = os.path.join(os.path.dirname(__file__), "results_4mhz_final.txt")

async def ssh_run(host, cmd, timeout=60):
    async with asyncssh.connect(host, username="root", password="root", known_hosts=None, login_timeout=10) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def wait_print(seconds, msg=""):
    for i in range(seconds):
        print(".", end="", flush=True)
        await asyncio.sleep(1)
    print(f" {msg}", flush=True)

async def main():
    E = "192.168.1.111"
    T = "192.168.1.103"
    
    # 4 MHz config from channels.csv: US,4,8,3,70,906.0
    # channel=8, s1g_chanbw=4, centre_freq=906 MHz, op_class=70
    CHAN = "8"
    BW = "4"
    FREQ = "906000"  # kHz
    
    print("=" * 60, flush=True)
    print("  4 MHz CONFIGURATION AND TEST", flush=True)
    print(f"  Channel={CHAN}, Freq=906 MHz, BW=4 MHz", flush=True)
    print("=" * 60, flush=True)
    
    # ===== PHASE 1: TUBE AP =====
    print("\n[TUBE AP] Configuring...", flush=True)
    cmds = [
        f"uci set wireless.radio0.channel='{CHAN}'",
        f"uci set wireless.radio0.s1g_chanbw='{BW}'",
        "uci set wireless.radio0.disabled='0'",
        "uci commit wireless",
    ]
    for cmd in cmds:
        await ssh_run(T, cmd, timeout=5)
    
    print("[TUBE AP] Restarting wifi...", flush=True)
    await ssh_run(T, "wifi down; sleep 2; wifi up", timeout=30)
    await wait_print(20, "AP init")
    
    out = await ssh_run(T, "iwinfo wlan0 info 2>/dev/null | head -8")
    print(f"Tube AP: {out}", flush=True)
    out = await ssh_run(T, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"Tube channel: {out}", flush=True)
    
    if "UNAL-HaLow" not in (await ssh_run(T, "iwinfo wlan0 info 2>/dev/null")):
        print("ERROR: Tube AP not up!", flush=True)
        return
    
    # Get wpa_supplicant generated params from AP's perspective
    # The AP's morse_cli channel will tell us the Operating BW and Primary BW
    
    # ===== PHASE 2: EDGE STA =====
    print("\n[EDGE STA] Configuring...", flush=True)
    cmds = [
        f"uci set wireless.radio0.channel='{CHAN}'",
        f"uci set wireless.radio0.s1g_chanbw='{BW}'",
        "uci commit wireless",
    ]
    for cmd in cmds:
        await ssh_run(E, cmd, timeout=5)
    
    print("[EDGE STA] Restarting wifi...", flush=True)
    await ssh_run(E, "wifi down; sleep 2; wifi up", timeout=30)
    await wait_print(8, "wifi up")
    
    # Read the generated wpa_supplicant config to get S1G params
    out = await ssh_run(E, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null")
    print(f"Generated wpa_supplicant:\n{out}", flush=True)
    
    # Extract op_class, s1g_prim_chwidth, s1g_prim_1mhz_chan_index
    # For 4 MHz: op_class=70, but what's prim_chwidth and prim_idx?
    # Let's read it from the AP's morse_cli
    ap_ch = await ssh_run(T, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"\nAP channel info: {ap_ch}", flush=True)
    
    # Parse primary BW and index from AP
    prim_bw = "2"  # default guess for 4 MHz
    prim_idx = "0"
    for line in ap_ch.split("\n"):
        if "Primary BW" in line:
            val = line.split(":")[-1].strip().replace(" MHz", "")
            prim_bw = val
        if "Primary Channel Index" in line:
            prim_idx = line.split(":")[-1].strip()
    
    print(f"Detected: prim_bw={prim_bw}, prim_idx={prim_idx}", flush=True)
    
    # Kill wpa_supplicant and set morse_cli
    print("[EDGE STA] Fix sequence...", flush=True)
    await ssh_run(E, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo ok", timeout=10)
    out = await ssh_run(E, f"morse_cli -i wlan0 channel -c {FREQ} -o {BW} -p {prim_bw} -n {prim_idx} 2>&1", timeout=10)
    print(f"morse_cli: {out}", flush=True)
    await ssh_run(E, "iw dev wlan0 set txpower fixed 2100 2>/dev/null; echo ok", timeout=5)
    await ssh_run(E, "iw dev wlan0 set power_save off 2>/dev/null; echo ok", timeout=5)
    await asyncio.sleep(1)
    
    # Restart wpa_supplicant
    await ssh_run(E,
        "wpa_supplicant_s1g -i wlan0 -c /var/run/wpa_supplicant-wlan0.conf "
        "-D nl80211 -B -P /var/run/wpa_supplicant_s1g-wlan0.pid",
        timeout=10)
    
    # Wait for association
    associated = False
    for t in range(2, 24, 2):
        await asyncio.sleep(2)
        out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit|Channel'")
        print(f"  {t}s: {out}", flush=True)
        if "UNAL-HaLow" in out:
            print("  *** ASSOCIATED! ***", flush=True)
            associated = True
            break
    
    if not associated:
        print("FAILED TO ASSOCIATE! Trying with different prim_bw...", flush=True)
        # Try prim_bw=1 instead
        await ssh_run(E, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo ok", timeout=10)
        alt_bw = "1" if prim_bw == "2" else "2"
        out = await ssh_run(E, f"morse_cli -i wlan0 channel -c {FREQ} -o {BW} -p {alt_bw} -n {prim_idx} 2>&1", timeout=10)
        print(f"morse_cli alt: {out}", flush=True)
        await asyncio.sleep(1)
        
        await ssh_run(E,
            "wpa_supplicant_s1g -i wlan0 -c /var/run/wpa_supplicant-wlan0.conf "
            "-D nl80211 -B -P /var/run/wpa_supplicant_s1g-wlan0.pid",
            timeout=10)
        
        for t in range(2, 24, 2):
            await asyncio.sleep(2)
            out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit|Channel'")
            print(f"  {t}s: {out}", flush=True)
            if "UNAL-HaLow" in out:
                print("  *** ASSOCIATED (alt)! ***", flush=True)
                associated = True
                break
    
    if not associated:
        print("COMPLETELY FAILED TO ASSOCIATE AT 4 MHz!", flush=True)
        return
    
    # ===== ROUTING =====
    print("\n[ROUTING] Setting up...", flush=True)
    await ssh_run(E, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    try:
        await ssh_run(E, "ip route replace default via 192.168.1.1 dev eth0 proto static src 192.168.1.111", timeout=5)
    except: pass
    await ssh_run(T, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    # Ping
    out = await ssh_run(E, "ping -c 5 -W 3 -i 0.5 192.168.1.103 2>&1 | tail -3", timeout=15)
    print(f"Ping: {out}", flush=True)
    
    # ===== IPERF3 TESTS =====
    print("\n" + "=" * 60, flush=True)
    print("  4 MHz iperf3 TESTS", flush=True)
    print("=" * 60, flush=True)
    
    # Signal baseline
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit|ESSID|Channel'")
    print(f"Edge: {out}", flush=True)
    out = await ssh_run(T, "iwinfo wlan0 assoclist 2>/dev/null | head -4")
    print(f"Tube: {out}", flush=True)
    out = await ssh_run(E, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"Edge channel: {out}", flush=True)
    
    tests = [
        ("TCP_UP",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 15 -i 3",            25),
        ("TCP_DOWN", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -R -t 15 -i 3",         25),
        ("UDP_500K", "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 500K -t 10 -i 5", 18),
        ("UDP_1M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 1M -t 10 -i 5",  18),
        ("UDP_2M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 2M -t 10 -i 5",  18),
        ("UDP_4M",   "iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b 4M -t 10 -i 5",  18),
    ]
    
    all_results = []
    
    for name, cmd, wait in tests:
        print(f"\n--- {name} ---", flush=True)
        for h in [E, T]:
            try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except: pass
        print("k", end="", flush=True)
        await asyncio.sleep(1)
        
        await ssh_run(T, "iperf3 -s -D -1", timeout=10)
        print("s", end="", flush=True)
        await asyncio.sleep(2)
        
        outf = f"/tmp/iperf_{name}.txt"
        await ssh_run(E, f"sh -c '({cmd}) > {outf} 2>&1 &'", timeout=10)
        print("c", end="", flush=True)
        
        await wait_print(wait, "done")
        
        try:
            out = await ssh_run(E, f"cat {outf} 2>&1", timeout=10)
            print(out, flush=True)
            all_results.append((name, out))
        except Exception as e:
            print(f"read error: {e}", flush=True)
            all_results.append((name, f"ERROR: {e}"))
    
    # Final
    print("\n--- FINAL ---", flush=True)
    out = await ssh_run(E, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    print(f"Edge: {out}", flush=True)
    out = await ssh_run(T, "iwinfo wlan0 assoclist 2>/dev/null | head -4")
    print(f"Tube: {out}", flush=True)
    
    with open(RESULTS, 'w') as f:
        for n, d in all_results:
            f.write(f"\n{'='*50}\n{n}\n{'='*50}\n{d}\n")
    print(f"\nSaved: {RESULTS}", flush=True)

asyncio.run(main())
