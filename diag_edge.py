#!/usr/bin/env python3
"""Focused diagnostic for Edge Gateway (STA) - HaLow upload bottleneck diagnosis"""
import asyncio, asyncssh, sys

EDGE = {"host": "192.168.1.196", "username": "root", "password": "root"}

async def run_cmd(conn, cmd, label):
    print(f"\n--- {label} ---", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=15), timeout=20)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            print(out, flush=True)
        elif err:
            print(err, flush=True)
        else:
            print("(empty)", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)

async def main():
    print("=" * 70)
    print("  EDGE GATEWAY (STA) DIAGNOSTICS - 192.168.1.196")
    print("=" * 70, flush=True)

    try:
        conn = await asyncio.wait_for(
            asyncssh.connect(EDGE["host"], username=EDGE["username"],
                           password=EDGE["password"], known_hosts=None,
                           login_timeout=20),
            timeout=30
        )
    except Exception as e:
        print(f"FAILED to connect to Edge: {e}", flush=True)
        return

    async with conn:
        # UCI wireless config
        await run_cmd(conn, "uci show wireless", "UCI wireless config")
        
        # iwinfo
        await run_cmd(conn, "iwinfo wlan0 info", "iwinfo wlan0 info")
        await run_cmd(conn, "iwinfo wlan0 assoclist", "iwinfo wlan0 assoclist")
        
        # iw station dump
        await run_cmd(conn, "iw dev wlan0 station dump", "iw station dump")
        await run_cmd(conn, "iw dev wlan0 info", "iw dev wlan0 info")
        await run_cmd(conn, "iw phy phy0 info 2>/dev/null | head -80", "iw phy info (first 80 lines)")
        
        # morse_cli
        await run_cmd(conn, "morse_cli -i wlan0 status", "morse_cli status")
        await run_cmd(conn, "morse_cli -i wlan0 stats", "morse_cli stats")
        await run_cmd(conn, "morse_cli -i wlan0 channel", "morse_cli channel")
        await run_cmd(conn, "morse_cli -i wlan0 bandwidth", "morse_cli bandwidth")
        
        # wpa_supplicant config (STA mode uses wpa_supplicant, not hostapd)
        await run_cmd(conn, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo 'not found'", "wpa_supplicant config")
        
        # /etc/config/wireless
        await run_cmd(conn, "cat /etc/config/wireless", "/etc/config/wireless")
        
        # dmesg for morse driver params
        await run_cmd(conn, "dmesg | grep -E 'morse|halow|s1g|fixed_|mcs_mask|bandwidth|Bandwidth|SSID' | tail -40", "dmesg morse/halow")
        
        # Module parameters
        await run_cmd(conn, "cat /sys/module/morse/parameters/* 2>/dev/null || echo 'no module params'", "morse module params")
        await run_cmd(conn, "ls /sys/module/morse*/parameters/ 2>/dev/null && for f in /sys/module/morse*/parameters/*; do echo \"$f: $(cat $f)\"; done || echo 'no morse module'", "morse module params detailed")
        
        # Check if there's a rate control override
        await run_cmd(conn, "cat /sys/kernel/debug/ieee80211/phy0/morse/rate_control 2>/dev/null || echo 'no rate_control debug'", "rate control debug")
        
        # Network interface stats
        await run_cmd(conn, "cat /proc/net/dev | grep wlan", "proc net dev wlan")
        await run_cmd(conn, "ip -s link show wlan0", "ip link wlan0")
        
        # logread for wireless messages
        await run_cmd(conn, "logread | grep -iE 'wlan|morse|halow|wpa_supplicant|assoc' | tail -30", "logread wireless")

    print("\n" + "=" * 70)
    print("  EDGE DIAGNOSTICS COMPLETE")
    print("=" * 70, flush=True)

asyncio.run(main())
