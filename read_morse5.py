#!/usr/bin/env python3
"""Read morse_override_wpa_supplicant_add_network function (line 744+)."""
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

    # Read the function at line 744
    await run_cmd(edge, "sed -n '744,900p' /lib/netifd/morse/morse_overrides.sh", "morse_overrides.sh lines 744-900")
    
    edge.close()

asyncio.run(main())
