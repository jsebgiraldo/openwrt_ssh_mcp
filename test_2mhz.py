#!/usr/bin/env python3
"""Quick test: configure both devices to 2 MHz and verify association."""
import asyncio
import asyncssh

async def ssh_run(host, cmd, timeout=30):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=15
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    print("=" * 60)
    print("  QUICK 2 MHz BW TEST")
    print("=" * 60)
    
    # Step 1: Configure Tube AP to channel 14, 2 MHz
    print("\n[1] Configuring Tube AP: channel=14, s1g_chanbw=2...")
    await ssh_run(TUBE,
        "uci set wireless.radio0.channel='14'; "
        "uci set wireless.radio0.s1g_chanbw='2'; "
        "uci commit wireless"
    )
    
    # Restart Tube
    print("[2] Restarting Tube wifi...")
    try:
        await ssh_run(TUBE, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    
    print("[3] Waiting 15s for AP...")
    await asyncio.sleep(15)
    
    # Verify Tube
    print("[4] Tube AP status:")
    out = await ssh_run(TUBE, "iwinfo wlan0 info 2>/dev/null | head -8")
    print(f"    {out}")
    ch = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"    {ch}")
    
    # Step 2: Configure Edge STA to channel 14, 2 MHz
    print("\n[5] Configuring Edge STA: channel=14, s1g_chanbw=2...")
    await ssh_run(EDGE,
        "uci set wireless.radio0.channel='14'; "
        "uci set wireless.radio0.s1g_chanbw='2'; "
        "uci set wireless.radio0.txpower='21'; "
        "uci commit wireless"
    )
    
    # wifi down/up
    print("[6] Restarting Edge wifi...")
    try:
        await ssh_run(EDGE, "wifi down; sleep 2; wifi up", timeout=30)
    except:
        pass
    
    print("[7] Waiting 10s...")
    await asyncio.sleep(10)
    
    # Read wpa_supplicant config
    print("[8] Edge wpa_supplicant config:")
    wpa = await ssh_run(EDGE, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null")
    print(f"    {wpa}")
    
    # Kill wpa_supplicant + morse_cli channel + restart
    print("\n[9] Fix sequence: kill + morse_cli + restart...")
    await ssh_run(EDGE, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo killed")
    await asyncio.sleep(2)
    
    # For 2 MHz: freq=909000, oper=2, prim=2
    out = await ssh_run(EDGE, "morse_cli -i wlan0 channel -c 909000 -o 2 -p 2 -n 0")
    print(f"    morse_cli: {out}")
    
    await ssh_run(EDGE, "iw dev wlan0 set txpower fixed 2100 2>/dev/null; echo ok")
    await ssh_run(EDGE, "iw dev wlan0 set power_save off 2>/dev/null; echo ok")
    await asyncio.sleep(3)
    
    # Restart wpa_supplicant
    await ssh_run(EDGE,
        "/usr/sbin/wpa_supplicant_s1g -t -D nl80211 -s -i wlan0 "
        "-c /var/run/wpa_supplicant-wlan0.conf -B"
    )
    
    # Wait for association
    print("[10] Waiting for association...")
    for i in range(15):
        await asyncio.sleep(2)
        info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit Rate|Channel'")
        print(f"    {(i+1)*2}s: {info}")
        if "UNAL-HaLow-Tesis" in info:
            print(f"    *** ASSOCIATED! ***")
            break
    
    # Quick ping test via HaLow
    print("\n[11] Setting route and testing ping via HaLow...")
    await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    
    out = await ssh_run(EDGE, "ping -c 10 -W 5 -i 1 192.168.1.103 2>&1", timeout=60)
    for line in out.split('\n'):
        if 'bytes from' in line or 'transmitted' in line or 'rtt' in line:
            print(f"    {line.strip()}")
    
    # Final status
    print("\n[12] Final status:")
    info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | head -10")
    print(f"    {info}")
    ch = await ssh_run(EDGE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(f"    {ch}")
    
    print("\nDone!")

asyncio.run(main())
