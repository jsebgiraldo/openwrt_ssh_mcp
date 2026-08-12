#!/usr/bin/env python3
"""Read morse_wpa_supplicant_add and the pre-STA setup where s1g_chanbw is used."""
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

    # Read morse_wpa_supplicant_add at line 1219
    await run_cmd(edge, "sed -n '1219,1415p' /lib/netifd/wireless/morse.sh", "morse.sh lines 1219-1415 (wpa_supplicant_add)")
    
    # Also read the part where STA gets its channel configured (pre-STA setup, around 390-500)
    await run_cmd(edge, "sed -n '380,500p' /lib/netifd/wireless/morse.sh", "morse.sh lines 380-500 (pre-STA channel setup)")
    
    edge.close()

asyncio.run(main())
