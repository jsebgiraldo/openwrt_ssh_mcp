#!/usr/bin/env python3
"""Read channels.csv and STA config generation to confirm root cause, then FIX it."""
import asyncio, asyncssh

async def run_cmd(conn, cmd, label=""):
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=15), timeout=20)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out if out else err if err else "(empty)"
        if label:
            print(f"\n--- {label} ---", flush=True)
        print(result, flush=True)
        return result
    except Exception as e:
        print(f"ERROR ({label}): {e}", flush=True)
        return f"ERROR: {e}"

async def main():
    edge = await asyncio.wait_for(
        asyncssh.connect("192.168.1.111", username="root", password="root",
                       known_hosts=None, login_timeout=15), timeout=20)

    # Check channels.csv for US channel 12
    await run_cmd(edge, "head -1 /usr/share/morse-regdb/channels.csv", "channels.csv header")
    await run_cmd(edge, "grep '^US' /usr/share/morse-regdb/channels.csv | head -30", "US channels from CSV")
    await run_cmd(edge, "grep '^US.*,12,' /usr/share/morse-regdb/channels.csv", "US channel 12 entries")
    
    # Read the STA wpa_supplicant network generation section (around lines 500-540)
    await run_cmd(edge, "sed -n '500,550p' /lib/netifd/wireless/morse.sh", "morse.sh lines 500-550")
    
    # Read the STA bringup function (around lines 880-930)
    await run_cmd(edge, "sed -n '870,940p' /lib/netifd/wireless/morse.sh", "morse.sh lines 870-940 (STA bringup)")
    
    edge.close()

asyncio.run(main())
