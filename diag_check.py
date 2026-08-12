#!/usr/bin/env python3
"""Quick check Tube-AHM AP to see if Edge is associated and get Edge UCI config via proxy"""
import asyncio, asyncssh

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}

async def run_cmd(conn, cmd, label):
    print(f"\n--- {label} ---", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=10), timeout=15)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if out:
            print(out, flush=True)
        elif err:
            print(err, flush=True)
        else:
            print("(empty)", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)

async def main():
    print("Checking Tube-AHM AP...", flush=True)
    conn = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None,
                       login_timeout=15),
        timeout=20
    )
    async with conn:
        await run_cmd(conn, "iwinfo wlan0 assoclist", "Tube assoclist (Edge connected?)")
        await run_cmd(conn, "morse_cli -i wlan0 status", "Tube morse_cli status")
        
        # Try to ping Edge from Tube
        await run_cmd(conn, "ping -c 3 -W 5 192.168.1.196", "Ping Edge from Tube")
        
        # Try SSH proxy: SSH from Tube to Edge
        print("\n--- Attempting SSH proxy to Edge via Tube ---", flush=True)
        try:
            edge_conn = await asyncio.wait_for(
                asyncssh.connect("192.168.1.196", username="root", password="root",
                               known_hosts=None, login_timeout=20,
                               tunnel=conn),
                timeout=30
            )
            async with edge_conn:
                print("SUCCESS: Connected to Edge via Tube proxy!", flush=True)
                await run_cmd(edge_conn, "uci show wireless", "Edge UCI wireless")
                await run_cmd(edge_conn, "iwinfo wlan0 info", "Edge iwinfo")
                await run_cmd(edge_conn, "iwinfo wlan0 assoclist", "Edge iwinfo assoclist")
                await run_cmd(edge_conn, "morse_cli -i wlan0 status", "Edge morse_cli status")
                await run_cmd(edge_conn, "morse_cli -i wlan0 stats", "Edge morse_cli stats")
                await run_cmd(edge_conn, "morse_cli -i wlan0 channel", "Edge morse_cli channel")
                await run_cmd(edge_conn, "morse_cli -i wlan0 bandwidth", "Edge morse_cli bandwidth")
                await run_cmd(edge_conn, "cat /etc/config/wireless", "Edge /etc/config/wireless")
                await run_cmd(edge_conn, "dmesg | grep -E 'morse|fixed_|mcs_mask|bandwidth|Bandwidth|SSID' | tail -30", "Edge dmesg morse")
                await run_cmd(edge_conn, "ls /sys/module/morse*/parameters/ 2>/dev/null && for f in /sys/module/morse*/parameters/*; do echo \"$f: $(cat $f)\"; done || echo 'no morse module params'", "Edge morse module params")
                await run_cmd(edge_conn, "cat /var/run/wpa_supplicant-wlan0.conf 2>/dev/null || cat /tmp/run/wpa_supplicant-wlan0.conf 2>/dev/null || echo 'wpa_supplicant conf not found'", "Edge wpa_supplicant config")
                await run_cmd(edge_conn, "iw dev wlan0 station dump", "Edge iw station dump")
        except Exception as e:
            print(f"SSH proxy failed: {e}", flush=True)
            print("Edge may be offline or HaLow link is down", flush=True)

asyncio.run(main())
