#!/usr/bin/env python3
"""Re-establish 2 MHz link and run all iperf3 tests."""
import asyncio
import asyncssh
import os

RESULTS = os.path.join(os.path.dirname(__file__), "results_2mhz.txt")

async def ssh_run(host, cmd, timeout=60):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def kill_iperf(hosts):
    for h in hosts:
        try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except: pass
    await asyncio.sleep(1)

async def establish_2mhz():
    """Re-establish 2 MHz link."""
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    print("[SETUP] Checking Tube AP...")
    out = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"  Tube channel: {out}")
    
    if "909000" not in out or "2 MHz" not in out:
        print("[SETUP] Configuring Tube for 2 MHz (ch14, 909 MHz)...")
        cmds = [
            "uci set wireless.radio0.channel=14",
            "uci set wireless.radio0.s1g_chanbw=2",
            "uci commit wireless",
            "wifi down; sleep 2; wifi up"
        ]
        await ssh_run(TUBE, "; ".join(cmds), timeout=30)
        print("[SETUP] Waiting 15s for Tube AP...")
        await asyncio.sleep(15)
        out = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
        print(f"  Tube channel: {out}")
    
    print("[SETUP] Checking Edge STA...")
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
    print(f"  Edge: {out}")
    
    if "UNAL-HaLow" not in out:
        print("[SETUP] Edge not associated, configuring...")
        cmds = [
            "uci set wireless.radio0.channel=14",
            "uci set wireless.radio0.s1g_chanbw=2",
            "uci commit wireless",
            "wifi down; sleep 2; wifi up"
        ]
        await ssh_run(EDGE, "; ".join(cmds), timeout=30)
        await asyncio.sleep(5)
        
        # Fix sequence
        print("[SETUP] Fix sequence: kill + morse_cli + restart...")
        await ssh_run(EDGE, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo ok", timeout=10)
        await ssh_run(EDGE, "morse_cli -i wlan0 channel -c 909000 -o 2 -p 1 -n 0", timeout=10)
        await ssh_run(EDGE, "iw dev wlan0 set txpower fixed 2100 2>/dev/null; echo ok", timeout=5)
        await ssh_run(EDGE, "iw dev wlan0 set power_save off 2>/dev/null; echo ok", timeout=5)
        await asyncio.sleep(1)
        
        # Restart wpa_supplicant
        await ssh_run(EDGE,
            "wpa_supplicant_s1g -i wlan0 -c /var/run/wpa_supplicant-wlan0.conf "
            "-D nl80211 -B -P /var/run/wpa_supplicant_s1g-wlan0.pid",
            timeout=10)
        
        # Wait for association
        for t in range(2, 16, 2):
            await asyncio.sleep(2)
            out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit'")
            print(f"  {t}s: {out}")
            if "UNAL-HaLow" in out:
                print("  *** ASSOCIATED! ***")
                break
        else:
            print("  FAILED TO ASSOCIATE!")
            return False
    
    # Setup route + ARP
    await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    await ssh_run(TUBE, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    # Quick ping check
    out = await ssh_run(EDGE, "ping -c 3 -W 3 192.168.1.103 2>&1 | tail -2", timeout=15)
    print(f"[SETUP] Ping: {out}")
    if "0% packet loss" in out:
        print("[SETUP] Link OK!")
        return True
    else:
        print("[SETUP] Link has issues")
        return True  # proceed anyway

async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    f = open(RESULTS, 'w', encoding='utf-8')
    
    def log(msg):
        print(msg)
        f.write(msg + "\n")
        f.flush()
    
    # First establish link
    ok = await establish_2mhz()
    if not ok:
        log("FAILED to establish 2 MHz link")
        f.close()
        return
    
    # Signal baseline
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit|ESSID'")
    log(f"\n{'='*50}")
    log("2 MHz iperf3 Test Results")
    log(f"{'='*50}")
    log(f"Edge: {out}")
    out = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
    log(f"Tube channel: {out}")
    
    await kill_iperf([EDGE, TUBE])
    
    # =================== TCP UPLOAD ===================
    log(f"\n{'='*50}")
    log("[1] TCP UPLOAD (Edge -> Tube, 15s)")
    log(f"{'='*50}")
    await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
    await asyncio.sleep(3)
    try:
        out = await ssh_run(EDGE,
            "iperf3 -c 192.168.1.103 -B 192.168.1.196 -t 15 -i 3 2>&1",
            timeout=50)
        log(out)
    except Exception as e:
        log(f"Error: {e}")
    await kill_iperf([EDGE, TUBE])
    await asyncio.sleep(3)
    
    # =================== TCP DOWNLOAD ===================
    log(f"\n{'='*50}")
    log("[2] TCP DOWNLOAD (Tube -> Edge, 15s) --reverse")
    log(f"{'='*50}")
    await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
    await asyncio.sleep(3)
    try:
        out = await ssh_run(EDGE,
            "iperf3 -c 192.168.1.103 -B 192.168.1.196 -R -t 15 -i 3 2>&1",
            timeout=50)
        log(out)
    except Exception as e:
        log(f"Error: {e}")
    await kill_iperf([EDGE, TUBE])
    await asyncio.sleep(3)
    
    # =================== UDP TESTS ===================
    for i, rate in enumerate(["500K", "1M", "2M"], start=3):
        log(f"\n{'='*50}")
        log(f"[{i}] UDP UPLOAD {rate} (Edge->Tube, 10s)")
        log(f"{'='*50}")
        await ssh_run(TUBE, "iperf3 -s -D -1", timeout=10)
        await asyncio.sleep(3)
        try:
            out = await ssh_run(EDGE,
                f"iperf3 -c 192.168.1.103 -B 192.168.1.196 -u -b {rate} -t 10 -i 5 2>&1",
                timeout=35)
            log(out)
        except Exception as e:
            log(f"Error: {e}")
        await kill_iperf([EDGE, TUBE])
        await asyncio.sleep(3)
    
    # Final signal
    log(f"\n{'='*50}")
    log("Signal after all tests:")
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    log(f"  Edge: {out}")
    out = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null | head -3")
    log(f"  Tube assoc: {out}")
    
    log(f"\n=== 2 MHz TESTS COMPLETE ===")
    f.close()
    print(f"\nResults saved to: {RESULTS}")

asyncio.run(main())
