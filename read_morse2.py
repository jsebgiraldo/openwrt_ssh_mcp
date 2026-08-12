#!/usr/bin/env python3
"""Read morse_wpa_supplicant_add and how STA channel/BW is actually configured."""
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

    # Find the morse_wpa_supplicant_add function
    await run_cmd(edge, "grep -n 'morse_wpa_supplicant_add\\|morse_wpa_s1g' /lib/netifd/wireless/morse.sh | head -20", "Find morse_wpa_supplicant_add")
    
    # Read the function (likely before 880)
    await run_cmd(edge, "sed -n '700,870p' /lib/netifd/wireless/morse.sh", "morse.sh lines 700-870")
    
    edge.close()

asyncio.run(main())
