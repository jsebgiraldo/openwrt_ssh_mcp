#!/usr/bin/env python3
"""Check current wireless state on both devices, then configure HaLow from scratch"""
import asyncio, asyncssh, sys

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root", "name": "Tube-AHM (AP)"}
EDGE = {"host": "192.168.1.111", "username": "root", "password": "root", "name": "Edge Gateway (STA)"}

async def run_cmd(conn, cmd, label, timeout=15):
    print(f"\n--- {label} ---", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=timeout), timeout=timeout+5)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            print(out, flush=True)
        elif err:
            print(err, flush=True)
        else:
            print("(empty)", flush=True)
        return out or err or ""
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return f"ERROR: {e}"

async def check_device(dev):
    print(f"\n{'='*70}")
    print(f"  {dev['name']} ({dev['host']}) — CURRENT STATE")
    print(f"{'='*70}", flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(dev["host"], username=dev["username"],
                       password=dev["password"], known_hosts=None,
                       login_timeout=15),
        timeout=20
    )
    async with conn:
        await run_cmd(conn, "cat /etc/config/wireless", "/etc/config/wireless")
        await run_cmd(conn, "uci show wireless 2>/dev/null || echo 'no wireless config'", "uci show wireless")
        await run_cmd(conn, "ifconfig wlan0 2>/dev/null || echo 'wlan0 not found'", "wlan0 status")
        await run_cmd(conn, "iwinfo wlan0 info 2>/dev/null || echo 'no wlan0 info'", "iwinfo wlan0")
        await run_cmd(conn, "iw dev 2>/dev/null | head -20", "iw dev")
        # Check morse module is loaded
        await run_cmd(conn, "lsmod | grep morse", "morse module loaded?")
        # Check available BCF files
        await run_cmd(conn, "ls /lib/firmware/morse/*.bin 2>/dev/null | head -10", "available BCF firmware")
        # Check morse_cli available commands
        await run_cmd(conn, "morse_cli --help 2>&1 | grep -A1 'Interface Commands' | head -5", "morse_cli available?")
        # System info
        await run_cmd(conn, "cat /etc/openwrt_release | head -5", "OpenWrt release")
        await run_cmd(conn, "uname -a", "kernel")

async def main():
    for dev in [TUBE, EDGE]:
        try:
            await check_device(dev)
        except Exception as e:
            print(f"\nFAILED to connect to {dev['name']}: {e}", flush=True)
    
    print(f"\n{'='*70}")
    print("  STATE CHECK COMPLETE")
    print(f"{'='*70}", flush=True)

asyncio.run(main())
