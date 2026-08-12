#!/usr/bin/env python3
"""Check Edge status and fix 2 MHz config."""
import asyncio
import asyncssh

async def ssh_run(host, cmd, timeout=30):
    async with asyncssh.connect(
        host, port=22, username="root", password="root",
        known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def main():
    EDGE = "192.168.1.111"
    TUBE = "192.168.1.103"
    
    # Check Edge status
    print("[1] Edge iwinfo:")
    out = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | head -10")
    print(out)
    
    print("\n[2] Edge morse_cli channel:")
    out = await ssh_run(EDGE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(out)
    
    print("\n[3] Edge wpa_supplicant S1G params:")
    out = await ssh_run(EDGE, "grep -E 'op_class|s1g_prim' /var/run/wpa_supplicant-wlan0.conf 2>/dev/null")
    print(out)
    
    print("\n[4] Tube morse_cli channel:")
    out = await ssh_run(TUBE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(out)
    
    # The AP shows Primary BW = 1 MHz. Let me re-do the Edge fix with -p 1
    print("\n[5] Fixing Edge: kill wpa_supplicant, set morse_cli with -p 1...")
    await ssh_run(EDGE, "killall wpa_supplicant_s1g 2>/dev/null; sleep 1; echo killed")
    await asyncio.sleep(2)
    
    # 2 MHz operating, 1 MHz primary (matching AP)
    out = await ssh_run(EDGE, "morse_cli -i wlan0 channel -c 909000 -o 2 -p 1 -n 0")
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
    print("\n[6] Waiting for association...")
    for i in range(15):
        await asyncio.sleep(2)
        info = await ssh_run(EDGE, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit|Channel'")
        print(f"    {(i+1)*2}s: {info}")
        if "UNAL-HaLow-Tesis" in info:
            print("    *** ASSOCIATED! ***")
            break
    
    # Verify channel
    print("\n[7] Edge morse_cli channel after fix:")
    out = await ssh_run(EDGE, "morse_cli -i wlan0 channel 2>/dev/null")
    print(out)
    
    # Quick ping
    print("\n[8] Quick ping Edge->Tube via HaLow (5 pings):")
    await ssh_run(EDGE, "ip route replace 192.168.1.103/32 dev wlan0 src 192.168.1.196")
    out = await ssh_run(EDGE, "ping -c 5 -W 3 -i 1 192.168.1.103 2>&1", timeout=30)
    print(out)

asyncio.run(main())
