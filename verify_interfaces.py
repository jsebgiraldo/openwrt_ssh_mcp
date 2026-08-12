#!/usr/bin/env python3
"""Verificar estado REAL de interfaces en ambos dispositivos"""
import asyncio, asyncssh

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "username": "root", "password": "root"}

async def run(conn, cmd, label):
    print(f"\n--- {label} ---", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=10), timeout=15)
        print((r.stdout or r.stderr or "(empty)").strip(), flush=True)
        return (r.stdout or "").strip()
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return ""

async def check(dev, name):
    print(f"\n{'='*60}", flush=True)
    print(f"  {name} ({dev['host']})", flush=True)
    print(f"{'='*60}", flush=True)
    conn = await asyncio.wait_for(
        asyncssh.connect(dev["host"], username=dev["username"],
                       password=dev["password"], known_hosts=None, login_timeout=15),
        timeout=20)
    async with conn:
        await run(conn, "ip addr show | grep -E '^[0-9]+:|inet '", "ALL interfaces + IPs")
        await run(conn, "iwinfo 2>/dev/null", "iwinfo (all wireless)")
        await run(conn, "brctl show 2>/dev/null", "bridges")
        await run(conn, "ip route show", "routes")
        await run(conn, "cat /etc/config/wireless", "/etc/config/wireless")
        await run(conn, "iwinfo wlan0 assoclist 2>/dev/null", "wlan0 assoclist")
        await run(conn, "morse_cli -i wlan0 channel 2>/dev/null", "morse_cli channel")

async def main():
    await check(TUBE, "Tube-AHM (AP)")
    await check(EDGE, "Edge Gateway (STA)")
    print(f"\n{'='*60}", flush=True)
    print("  DONE", flush=True)

asyncio.run(main())
