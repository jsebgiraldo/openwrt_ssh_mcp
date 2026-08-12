#!/usr/bin/env python3
"""
Diagnose and fix Edge HaLow radio initialization.
The Edge radio shows 907.5 MHz @ 1 MHz instead of 908.0 MHz @ 8 MHz.
TX Power stuck at 0 dBm despite UCI setting of 21.
"""
import asyncio, asyncssh

EDGE_ETH = {"host": "192.168.1.111", "username": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}

async def run_cmd(conn, cmd, label="", quiet=False):
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=20), timeout=25)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out if out else err if err else "(empty)"
        if not quiet:
            if label:
                print(f"\n--- {label} ---", flush=True)
            print(result, flush=True)
        return result
    except Exception as e:
        if not quiet:
            print(f"ERROR ({label}): {e}", flush=True)
        return f"ERROR: {e}"

async def main():
    edge = await asyncio.wait_for(
        asyncssh.connect(EDGE_ETH["host"], username=EDGE_ETH["username"],
                       password=EDGE_ETH["password"], known_hosts=None,
                       login_timeout=15), timeout=20)
    tube = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None,
                       login_timeout=15), timeout=20)

    # ========================================
    # DIAGNOSIS: Check what wpa_supplicant config is generated
    # ========================================
    print("=" * 70)
    print("  DIAGNOSIS: Edge wpa_supplicant + radio state")
    print("=" * 70, flush=True)

    # Find and read wpa_supplicant config
    await run_cmd(edge, "find /var/run /tmp -name '*wpa_supplicant*' -type f 2>/dev/null", "wpa_supplicant config files")
    await run_cmd(edge, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo 'not found at standard paths'", "wpa_supplicant-wlan0.conf")
    
    # Check how netifd/wireless generates the config
    await run_cmd(edge, "cat /lib/netifd/wireless/morse.sh 2>/dev/null | head -80", "morse.sh wireless script (head)")
    await run_cmd(edge, "cat /lib/netifd/wireless/morse.sh 2>/dev/null | grep -n 's1g_chanbw\|chanbw\|bandwidth\|op_class\|oper_bw\|prim_ch' | head -20", "morse.sh bandwidth references")
    
    # Check if there's a hostapd template or setup script
    await run_cmd(edge, "grep -rn 's1g_chanbw\|s1g_prim\|op_class' /lib/netifd/ 2>/dev/null | head -20", "netifd s1g config references")
    
    # Edge driver parameters
    await run_cmd(edge, "for f in /sys/module/morse*/parameters/*; do n=$(basename $f); v=$(cat $f 2>/dev/null); echo \"$n: $v\"; done 2>/dev/null | grep -iE 'bw|band|channel|freq|power|mcs|fixed'", "Edge morse driver params (relevant)")
    
    # Tube driver params for comparison  
    await run_cmd(tube, "for f in /sys/module/morse*/parameters/*; do n=$(basename $f); v=$(cat $f 2>/dev/null); echo \"$n: $v\"; done 2>/dev/null | grep -iE 'bw|band|channel|freq|power|mcs|fixed'", "Tube morse driver params (relevant)")
    
    # Check hostapd generated config on Tube for comparison
    await run_cmd(tube, "cat /var/run/hostapd-wlan0.conf 2>/dev/null | grep -iE 's1g|op_class|channel|prim|freq'", "Tube hostapd s1g params")
    
    # ========================================
    # FIX ATTEMPT 1: Set channel/BW via morse_cli on Edge
    # ========================================
    print("\n" + "=" * 70)
    print("  FIX ATTEMPT 1: Set channel via morse_cli directly on Edge")
    print("=" * 70, flush=True)
    
    # First stop wifi
    await run_cmd(edge, "wifi down", "Edge wifi down")
    await asyncio.sleep(3)
    
    # Bring interface up manually to try morse_cli
    await run_cmd(edge, "wifi up", "Edge wifi up")
    await asyncio.sleep(5)
    
    # Try to set channel and bandwidth via morse_cli
    await run_cmd(edge, "morse_cli -i wlan0 channel -c 908000 -o 8 -p 2 -n 3", "morse_cli set channel 908MHz 8MHz")
    await asyncio.sleep(2)
    await run_cmd(edge, "morse_cli -i wlan0 channel", "Edge morse channel after set")
    
    # Try to set TX power via iw
    await run_cmd(edge, "iw dev wlan0 set txpower fixed 2100", "Set TX power 21 dBm via iw")
    await run_cmd(edge, "iwinfo wlan0 txpower", "Edge TX power after set")
    
    await asyncio.sleep(10)
    
    # Check if associated now
    await run_cmd(edge, "iwinfo wlan0 info", "Edge iwinfo after morse_cli fix")
    await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube assoclist after fix")

    # ========================================  
    # FIX ATTEMPT 2: Check Tube AP s1g params vs Edge
    # ========================================
    print("\n" + "=" * 70)
    print("  FIX ATTEMPT 2: Compare AP hostapd vs STA config")
    print("=" * 70, flush=True)
    
    # Full hostapd config on Tube
    await run_cmd(tube, "cat /var/run/hostapd-wlan0.conf 2>/dev/null | head -40", "Tube hostapd config (head)")
    
    # Full wpa_supplicant config on Edge
    await run_cmd(edge, "find / -name '*wpa*wlan*' -o -name '*supplicant*wlan*' 2>/dev/null | head -10", "Edge wpa_supplicant files")
    await run_cmd(edge, "for f in $(find /var /tmp -name '*wpa*' -type f 2>/dev/null); do echo '=== '$f' ==='; cat $f; echo '---'; done 2>/dev/null | head -80", "All wpa_supplicant configs")
    
    # Check if Edge firmware/version differs
    await run_cmd(edge, "cat /etc/openwrt_release", "Edge OpenWrt release")
    await run_cmd(tube, "cat /etc/openwrt_release", "Tube OpenWrt release")
    
    # Check specifically how morse netifd wireless script works
    await run_cmd(edge, "cat /lib/netifd/wireless/morse.sh 2>/dev/null | grep -A5 -B5 'chanbw'", "Edge morse.sh chanbw handling")
    
    # Check if there's a difference in how channel is mapped
    await run_cmd(edge, "wpa_cli -i wlan0 scan_results 2>/dev/null || echo 'wpa_cli not available'", "Edge scan results")
    await run_cmd(edge, "wpa_cli -i wlan0 status 2>/dev/null || echo 'N/A'", "Edge wpa_cli status")

    # ========================================
    # FIX ATTEMPT 3: Complete wifi restart after morse_cli channel set
    # ========================================
    print("\n" + "=" * 70)
    print("  Waiting 30s for association after fixes...")
    print("=" * 70, flush=True)
    await asyncio.sleep(30)
    
    await run_cmd(edge, "iwinfo wlan0 info", "Edge final status")
    await run_cmd(edge, "morse_cli -i wlan0 channel", "Edge final channel")
    await run_cmd(edge, "iwinfo wlan0 assoclist", "Edge final assoclist")
    await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube final assoclist")
    
    # Check auth logs
    await run_cmd(edge, "logread | grep -iE 'auth|assoc|connected|SAE' | tail -20", "Edge latest auth logs")

    edge.close()
    tube.close()

    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70, flush=True)

asyncio.run(main())
