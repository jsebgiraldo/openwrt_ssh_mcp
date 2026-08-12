#!/usr/bin/env python3
"""Rebuild Tube AP config and re-establish 2 MHz link."""
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

async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    # ==================== TUBE AP REBUILD ====================
    print("=" * 60)
    print("  PHASE 1: Rebuild Tube AP")
    print("=" * 60)
    
    # Check current state
    out = await ssh_run(TUBE, "uci show wireless 2>/dev/null")
    print(f"Current Tube config:\n{out}\n")
    
    # Recreate wifinet0 if missing
    if "wifinet0" not in out:
        print("wifinet0 MISSING - recreating...")
        cmds = [
            "uci set wireless.wifinet0=wifi-iface",
            "uci set wireless.wifinet0.device='radio0'",
            "uci set wireless.wifinet0.mode='ap'",
            "uci set wireless.wifinet0.ssid='UNAL-HaLow-Tesis'",
            "uci set wireless.wifinet0.encryption='sae'",
            "uci set wireless.wifinet0.sae_pwe='1'",
            "uci set wireless.wifinet0.key='banano2026'",
            "uci set wireless.wifinet0.network='ahwlan'",
            "uci set wireless.wifinet0.wds='1'",
        ]
        for cmd in cmds:
            await ssh_run(TUBE, cmd, timeout=5)
    
    # Set channel config
    print("Setting channel=14 (909 MHz), s1g_chanbw=2...")
    cmds = [
        "uci set wireless.radio0.channel='14'",
        "uci set wireless.radio0.s1g_chanbw='2'",
        "uci set wireless.radio0.disabled='0'",
        "uci commit wireless",
    ]
    for cmd in cmds:
        await ssh_run(TUBE, cmd, timeout=5)
    
    # Verify config
    out = await ssh_run(TUBE, "uci show wireless")
    print(f"\nTube config after fix:\n{out}\n")
    
    # Restart wifi
    print("Restarting Tube wifi...")
    await ssh_run(TUBE, "wifi down; sleep 2; wifi up", timeout=30)
    print("Waiting 20s for AP to come up...")
    await asyncio.sleep(20)
    
    # Check AP
    out = await ssh_run(TUBE, "iwinfo wlan0 info 2>/dev/null | head -8")
    print(f"Tube AP: {out}")
    out = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"Tube channel: {out}")
    
    if "UNAL-HaLow" not in (await ssh_run(TUBE, "iwinfo wlan0 info 2>/dev/null")):
        print("ERROR: Tube AP not coming up! Trying again...")
        await ssh_run(TUBE, "wifi down; sleep 3; wifi up", timeout=30)
        await asyncio.sleep(20)
        out = await ssh_run(TUBE, "iwinfo wlan0 info 2>/dev/null | head -8")
        print(f"Tube AP (2nd try): {out}")
    
    # ==================== EDGE STA ====================
    print("\n" + "=" * 60)
    print("  PHASE 2: Edge STA")
    print("=" * 60)
    
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal'")
    print(f"Edge: {out}")
    
    if "UNAL-HaLow" not in out:
        print("Edge not associated - running fix sequence...")
        
        # Ensure UCI correct
        await ssh_run(EDGE, "uci set wireless.radio0.channel='14'; uci set wireless.radio0.s1g_chanbw='2'; uci commit wireless")
        await ssh_run(EDGE, "wifi down; sleep 2; wifi up", timeout=30)
        await asyncio.sleep(5)
        
        # Kill + morse_cli + restart
        await ssh_run(EDGE, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo ok", timeout=10)
        out = await ssh_run(EDGE, "morse_cli -i wlan0 channel -c 909000 -o 2 -p 1 -n 0 2>&1", timeout=10)
        print(f"morse_cli: {out}")
        await ssh_run(EDGE, "iw dev wlan0 set txpower fixed 2100 2>/dev/null; echo ok", timeout=5)
        await ssh_run(EDGE, "iw dev wlan0 set power_save off 2>/dev/null; echo ok", timeout=5)
        await asyncio.sleep(1)
        
        await ssh_run(EDGE,
            "wpa_supplicant_s1g -i wlan0 -c /var/run/wpa_supplicant-wlan0.conf "
            "-D nl80211 -B -P /var/run/wpa_supplicant_s1g-wlan0.pid",
            timeout=10)
        
        for t in range(2, 20, 2):
            await asyncio.sleep(2)
            out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit'")
            print(f"  {t}s: {out}")
            if "UNAL-HaLow" in out:
                print("  *** ASSOCIATED! ***")
                break
        else:
            print("  FAILED TO ASSOCIATE!")
            return
    
    # Setup routing
    print("\nSetting route + ARP...")
    await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    await ssh_run(TUBE, "ip neigh replace 192.168.1.196 dev br-ahwlan lladdr 0c:bf:74:1c:de:87 nud permanent")
    
    # Ping check
    out = await ssh_run(EDGE, "ping -c 5 -W 3 -i 0.5 192.168.1.103 2>&1 | tail -3", timeout=15)
    print(f"Ping: {out}")
    
    if "0% packet loss" not in out:
        print("WARNING: Ping has issues, but continuing...")
    
    # ==================== IPERF3 TESTS ====================
    print("\n" + "=" * 60)
    print("  PHASE 3: iperf3 Tests at 2 MHz")
    print("=" * 60)
    
    f = open(RESULTS, 'w', encoding='utf-8')
    def log(msg):
        print(msg)
        f.write(msg + "\n")
        f.flush()
    
    # Signal baseline
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit|ESSID'")
    log(f"Edge: {out}")
    out = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null | head -3")
    log(f"Tube assoclist: {out}")
    
    # Kill any existing iperf3
    for h in [EDGE, TUBE]:
        try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except: pass
    await asyncio.sleep(1)
    
    # --- TCP UPLOAD ---
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
    for h in [EDGE, TUBE]:
        try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except: pass
    await asyncio.sleep(3)
    
    # --- TCP DOWNLOAD ---
    log(f"\n{'='*50}")
    log("[2] TCP DOWNLOAD (Tube -> Edge, 15s) via --reverse")
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
    for h in [EDGE, TUBE]:
        try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
        except: pass
    await asyncio.sleep(3)
    
    # --- UDP Tests ---
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
        for h in [EDGE, TUBE]:
            try: await ssh_run(h, "killall iperf3 2>/dev/null; echo ok", timeout=5)
            except: pass
        await asyncio.sleep(3)
    
    # Final signal
    log(f"\n{'='*50}")
    log("Signal after all tests:")
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'Signal|Bit'")
    log(f"  Edge: {out}")
    out = await ssh_run(TUBE, "iwinfo wlan0 assoclist 2>/dev/null | head -3")
    log(f"  Tube: {out}")
    
    log(f"\n=== 2 MHz TESTS COMPLETE ===")
    f.close()
    print(f"\nResults saved to: {RESULTS}")

asyncio.run(main())
