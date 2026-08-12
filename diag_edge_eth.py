#!/usr/bin/env python3
"""Full Edge Gateway HaLow diagnostic via Ethernet (192.168.1.111)"""
import asyncio, asyncssh

EDGE_ETH = {"host": "192.168.1.111", "username": "root", "password": "root"}

async def run_cmd(conn, cmd, label):
    print(f"\n--- {label} ---", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=15), timeout=20)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            print(out, flush=True)
        if err and not out:
            print(err, flush=True)
        if not out and not err:
            print("(empty)", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)

async def main():
    print("=" * 70)
    print("  EDGE GATEWAY HALOW DIAGNOSTICS (via Ethernet 192.168.1.111)")
    print("=" * 70, flush=True)

    conn = await asyncio.wait_for(
        asyncssh.connect(EDGE_ETH["host"], username=EDGE_ETH["username"],
                       password=EDGE_ETH["password"], known_hosts=None,
                       login_timeout=15),
        timeout=20
    )
    async with conn:
        # === WIRELESS CONFIG ===
        await run_cmd(conn, "uci show wireless", "UCI wireless config")
        await run_cmd(conn, "cat /etc/config/wireless", "/etc/config/wireless")
        
        # === INTERFACE STATUS ===
        await run_cmd(conn, "ifconfig wlan0 2>/dev/null || ip addr show wlan0", "wlan0 interface status")
        await run_cmd(conn, "iwinfo wlan0 info", "iwinfo wlan0 info")
        await run_cmd(conn, "iwinfo wlan0 assoclist", "iwinfo wlan0 assoclist")
        
        # === IW DETAILS ===
        await run_cmd(conn, "iw dev wlan0 info", "iw dev wlan0 info")
        await run_cmd(conn, "iw dev wlan0 station dump", "iw station dump")
        await run_cmd(conn, "iw dev wlan0 link", "iw dev wlan0 link")
        
        # === MORSE CLI ===
        await run_cmd(conn, "morse_cli -i wlan0 channel", "morse_cli channel")
        await run_cmd(conn, "morse_cli -i wlan0 channel -a", "morse_cli channel -a (all)")
        await run_cmd(conn, "morse_cli -i wlan0 stats", "morse_cli stats (first 100 lines)")
        
        # === TX POWER ===
        await run_cmd(conn, "iwinfo wlan0 txpower", "iwinfo TX power")
        await run_cmd(conn, "iwinfo wlan0 txpowerlist", "iwinfo TX power list")
        
        # === WPA SUPPLICANT CONFIG (STA mode) ===
        await run_cmd(conn, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null || find / -name 'wpa_supplicant*wlan0*' -type f 2>/dev/null | head -5", "wpa_supplicant config")
        
        # === DRIVER MODULE PARAMS ===
        await run_cmd(conn, "for f in /sys/module/morse*/parameters/*; do echo \"$(basename $f): $(cat $f 2>/dev/null)\"; done 2>/dev/null || echo 'no morse module params'", "morse module params")
        
        # === DMESG ===
        await run_cmd(conn, "dmesg | grep -iE 'morse|halow|s1g|fixed_|mcs|bandwidth|Bandwidth|SSID|txpower|tx_power|country|regulatory|wlan0' | tail -50", "dmesg morse/halow")
        
        # === NETWORK CONFIG ===
        await run_cmd(conn, "uci show network | grep -E 'ahwlan|halow|wlan'", "UCI network config (HaLow)")
        await run_cmd(conn, "ip route show", "IP routes")
        await run_cmd(conn, "ip addr show", "All IP addresses")
        
        # === LOGREAD ===
        await run_cmd(conn, "logread | grep -iE 'wlan|morse|halow|wpa_supplicant|assoc|deauth|disassoc' | tail -40", "logread wireless")
        
        # === CHECK IF HALOW IS ASSOCIATED ===
        await run_cmd(conn, "cat /tmp/morse_status 2>/dev/null || echo 'no morse_status'", "morse status file")
        await run_cmd(conn, "wpa_cli -i wlan0 status 2>/dev/null || echo 'wpa_cli not available'", "wpa_cli status")

    print("\n" + "=" * 70)
    print("  DIAGNOSTICS COMPLETE")
    print("=" * 70, flush=True)

asyncio.run(main())
