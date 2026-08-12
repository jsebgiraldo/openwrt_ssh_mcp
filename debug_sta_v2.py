#!/usr/bin/env python3
"""Debug Edge STA connection failure to Tube-AHM AP."""
import asyncio
import asyncssh

EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root"}


async def ssh_exec(device, cmd):
    async with asyncssh.connect(
        device["host"], 22, username=device["user"],
        password=device["password"], known_hosts=None
    ) as conn:
        r = await conn.run(cmd, timeout=30)
        return r.stdout.strip()


async def main():
    print("=== EDGE STA DEBUG ===\n")

    # Full wpa_supplicant logs
    print("--- wpa_supplicant_s1g logs (Edge) ---")
    logs = await ssh_exec(EDGE, "logread | grep -i 'wpa_supplicant\\|hostapd\\|netifd.*radio\\|morse\\|wlan0\\|CTRL-EVENT\\|auth\\|assoc\\|sae'")
    print(logs)

    print("\n--- Edge wireless config ---")
    wconf = await ssh_exec(EDGE, "cat /etc/config/wireless")
    print(wconf)

    print("\n--- Edge wlan0 status ---")
    info = await ssh_exec(EDGE, "iwinfo wlan0 info 2>/dev/null")
    print(info)
    
    print("\n--- Edge wpa_supplicant_s1g process ---")
    proc = await ssh_exec(EDGE, "ps | grep wpa_supplicant")
    print(proc)
    
    print("\n--- Edge wpa_supplicant_s1g control ---")
    ctrl = await ssh_exec(EDGE, "ls -la /var/run/wpa_supplicant_s1g/ 2>/dev/null")
    print(ctrl)

    # Try to interact with wpa_supplicant_s1g via socket
    print("\n--- wpa_cli_s1g status (if available) ---")
    status = await ssh_exec(EDGE, "wpa_cli_s1g -i wlan0 status 2>/dev/null || echo 'wpa_cli_s1g not available'")
    print(status)

    print("\n--- Edge iwinfo scan ---")
    scan = await ssh_exec(EDGE, "iwinfo wlan0 scan 2>/dev/null || echo 'scan failed'")
    print(scan)

    # Check Tube-AHM AP side logs
    print("\n\n=== TUBE-AHM AP DEBUG ===\n")
    print("--- hostapd_s1g logs (Tube) ---")
    hlogs = await ssh_exec(TUBE, "logread | grep -i 'hostapd\\|wpa_supplicant\\|netifd.*radio\\|morse\\|wlan0\\|auth\\|assoc\\|sae'")
    print(hlogs)

    print("\n--- Tube AP iwinfo ---")
    tinfo = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null")
    print(tinfo)

    # Check if Edge's BCF supports channel 48
    print("\n\n=== CHANNEL COMPATIBILITY ===")
    print("\n--- Edge freqlist ---")
    freq = await ssh_exec(EDGE, "iwinfo wlan0 freqlist 2>/dev/null")
    print(freq)
    
    print("\n--- Tube freqlist ---")
    tfreq = await ssh_exec(TUBE, "iwinfo wlan0 freqlist 2>/dev/null")
    print(tfreq)

    # netifd errors
    print("\n--- Edge netifd errors ---")
    nerr = await ssh_exec(EDGE, "logread | grep 'netifd' | grep -i 'error\\|fail\\|range'")
    print(nerr)


asyncio.run(main())
