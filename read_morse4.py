#!/usr/bin/env python3
"""Find and read morse_override_wpa_supplicant_add_network."""
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

    # Find morse_override_wpa_supplicant_add_network
    await run_cmd(edge, "grep -rn 'morse_override_wpa_supplicant_add_network' /lib/netifd/ 2>/dev/null", "Find function")
    
    # Find all morse override files
    await run_cmd(edge, "find /lib/netifd -name '*override*' -o -name '*morse_overr*' 2>/dev/null", "Morse override files")
    
    # Read the overrides file
    await run_cmd(edge, "cat /lib/netifd/morse/morse_overrides.sh 2>/dev/null | head -100", "morse_overrides.sh (first 100 lines)")
    
    # If not there, search more broadly
    await run_cmd(edge, "grep -rn 'morse_override_wpa' /lib/ 2>/dev/null | head -10", "Search for function in /lib")
    
    edge.close()

asyncio.run(main())
