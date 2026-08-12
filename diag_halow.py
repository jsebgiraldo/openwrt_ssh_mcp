#!/usr/bin/env python3
"""Comprehensive HaLow link diagnostic for both AP (Tube-AHM) and STA (Edge)."""
import asyncio
import asyncssh

DEVICES = [
    {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM (AP)"},
    {"host": "192.168.1.196", "user": "root", "password": "root", "name": "Edge Gateway (STA)"},
]

COMMANDS = [
    ("UCI wireless config", "uci show wireless"),
    ("iwinfo wlan0 info", "iwinfo wlan0 info 2>/dev/null"),
    ("iwinfo assoclist", "iwinfo wlan0 assoclist 2>/dev/null"),
    ("iw dev wlan0 info", "iw dev wlan0 info 2>/dev/null"),
    ("iw phy info (capabilities)", "iw phy phy0 info 2>/dev/null | head -80"),
    ("iw station dump", "iw dev wlan0 station dump 2>/dev/null"),
    ("/etc/config/wireless", "cat /etc/config/wireless"),
    ("morse_cli status", "morse_cli status 2>/dev/null || echo N/A"),
    ("morse_cli stats", "morse_cli stats 2>/dev/null || echo N/A"),
    ("morse_cli channel", "morse_cli channel 2>/dev/null || echo N/A"),
    ("morse_cli bandwidth", "morse_cli bandwidth 2>/dev/null || echo N/A"),
    ("dmesg morse/halow", "dmesg | grep -iE 'morse|halow|s1g|mcs|bandwidth|bw' | tail -30"),
    ("logread halow", "logread | grep -iE 'morse|halow|s1g|wlan0|hostapd|wpa_supplicant' | tail -30"),
    ("hostapd config", "cat /var/run/hostapd-phy0.conf 2>/dev/null || echo N/A"),
    ("wpa_supplicant config", "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo N/A"),
    ("ip link wlan0", "ip -s link show wlan0 2>/dev/null"),
    ("ethtool wlan0", "ethtool wlan0 2>/dev/null || echo N/A"),
]


async def diagnose():
    for dev in DEVICES:
        print("=" * 70)
        print(f"  DEVICE: {dev['name']} ({dev['host']})")
        print("=" * 70)
        try:
            async with asyncssh.connect(
                dev["host"], username=dev["user"], password=dev["password"],
                known_hosts=None, login_timeout=20
            ) as conn:
                for label, cmd in COMMANDS:
                    print(f"\n--- {label} ---")
                    try:
                        r = await asyncio.wait_for(conn.run(cmd, timeout=15), timeout=20)
                        out = r.stdout.strip() if r.stdout else ""
                        err = r.stderr.strip() if r.stderr else ""
                        print(out if out else "(empty)")
                        if err and "not found" not in err:
                            print(f"  STDERR: {err}")
                    except Exception as e:
                        print(f"ERROR: {e}")
        except Exception as e:
            print(f"CONNECTION ERROR: {e}")
        print()


if __name__ == "__main__":
    asyncio.run(diagnose())
