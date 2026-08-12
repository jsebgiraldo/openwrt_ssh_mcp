#!/usr/bin/env python3
"""Read the morse.sh and morse_utils.sh to understand STA channel setup."""
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

    # Read _get_regulatory function
    await run_cmd(edge, "cat /lib/netifd/morse/morse_utils.sh", "morse_utils.sh FULL")
    
    # Read the STA setup section of morse.sh (around line 950-1050)
    await run_cmd(edge, "wc -l /lib/netifd/wireless/morse.sh", "morse.sh line count")
    await run_cmd(edge, "sed -n '940,1060p' /lib/netifd/wireless/morse.sh", "morse.sh lines 940-1060 (STA channel + morse_cli)")
    
    # Also check the wpa_supplicant network block generation for STA
    await run_cmd(edge, "grep -n 'op_class\\|s1g_prim_chwidth\\|s1g_prim_1mhz\\|network_data\\|wpa_supplicant' /lib/netifd/wireless/morse.sh | head -30", "morse.sh wpa_supplicant/network lines")
    
    edge.close()

asyncio.run(main())
