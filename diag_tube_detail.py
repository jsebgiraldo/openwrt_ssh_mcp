#!/usr/bin/env python3
"""Get Tube-AHM AP detailed wireless config for diagnosis"""
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
    conn = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None,
                       login_timeout=15),
        timeout=20
    )
    async with conn:
        # Full UCI wireless
        await run_cmd(conn, "uci show wireless", "Tube UCI wireless")
        
        # /etc/config/wireless
        await run_cmd(conn, "cat /etc/config/wireless", "Tube /etc/config/wireless")
        
        # TX power info
        await run_cmd(conn, "iwinfo wlan0 txpower", "Tube TX power")
        await run_cmd(conn, "iwinfo wlan0 txpowerlist", "Tube TX power list")
        
        # morse_cli help to find correct commands
        await run_cmd(conn, "morse_cli --help 2>&1 | head -30", "morse_cli help")
        await run_cmd(conn, "morse_cli -i wlan0 --help 2>&1 | head -40", "morse_cli interface help")
        
        # morse_cli with correct syntax
        await run_cmd(conn, "morse_cli -i wlan0 stats get 2>/dev/null || morse_cli -i wlan0 get stats 2>/dev/null || echo 'tried both'", "morse_cli stats variants")
        
        # Check morse driver module params
        await run_cmd(conn, "for f in /sys/module/morse*/parameters/*; do echo \"$(basename $f): $(cat $f 2>/dev/null)\"; done 2>/dev/null || echo 'no module params'", "Tube morse module params")
        
        # dmesg for TX power and config
        await run_cmd(conn, "dmesg | grep -iE 'txpower|tx_power|power|morse.*init|morse.*start|country|regulatory' | tail -20", "dmesg TX power/regulatory")
        
        # Full iw dev info
        await run_cmd(conn, "iw dev wlan0 info", "iw dev wlan0 info")
        
        # Check ARP table for Edge
        await run_cmd(conn, "ip neigh show | grep -i '196\|de:87'", "ARP table for Edge")
        
        # Bridge info (Edge traffic goes through bridge)
        await run_cmd(conn, "brctl show 2>/dev/null || bridge link show 2>/dev/null", "Bridge info")
        
        # Check if Edge MAC is still in FDB
        await run_cmd(conn, "bridge fdb show | grep -i 'de:87' 2>/dev/null || echo 'no fdb entry'", "Bridge FDB for Edge")

    print("\nDone.", flush=True)

asyncio.run(main())
