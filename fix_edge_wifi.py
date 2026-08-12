#!/usr/bin/env python3
"""Restart wifi on Edge after network fix, then verify full connectivity"""
import asyncio, asyncssh, time

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "username": "root", "password": "root"}

async def run_cmd(conn, cmd, label=None, timeout=15):
    if label:
        print(f"  [{label}]", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=timeout), timeout=timeout+5)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out or err or "(empty)"
        if label:
            for line in result.split('\n')[:20]:
                print(f"    {line}", flush=True)
        return result
    except Exception as e:
        if label:
            print(f"    ERROR: {e}", flush=True)
        return f"ERROR: {e}"

async def main():
    # ── Restart wifi on Edge ──
    print("="*70)
    print("  Restarting wifi on Edge Gateway")
    print("="*70, flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(EDGE["host"], username=EDGE["username"],
                       password=EDGE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        # Check current state
        await run_cmd(conn, "iwinfo wlan0 info 2>/dev/null | head -5", "Current wlan0 state")
        
        # Restart wifi
        print("\n  Bringing wifi down then up...", flush=True)
        await run_cmd(conn, "wifi down", "wifi down", timeout=10)
        await asyncio.sleep(3)
        await run_cmd(conn, "wifi up", "wifi up", timeout=15)
        
        # Wait for association
        print("\n  Waiting for STA to associate...", flush=True)
        for i in range(24):  # up to 120 seconds
            await asyncio.sleep(5)
            result = await run_cmd(conn, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Channel'")
            if "UNAL-HaLow-Tesis" in result and "Signal" in result:
                print(f"  ✓ Associated after {(i+1)*5}s!", flush=True)
                print(f"    {result}", flush=True)
                break
            else:
                elapsed = (i+1)*5
                status = result.strip().split('\n')[0] if result else "no info"
                print(f"  [{elapsed}s] {status}", flush=True)
        else:
            print("  ✗ Timed out waiting for association!", flush=True)
            await run_cmd(conn, "logread | grep -iE 'wlan|morse|wpa_supplicant|assoc|auth|sae' | tail -20", "Logread")
            return
        
        # Check IP on wlan0
        await run_cmd(conn, "ip addr show wlan0", "wlan0 status")
        await run_cmd(conn, "ip route show", "Routes")
    
    # Wait a bit for IP/ARP to settle
    await asyncio.sleep(3)
    
    # ── Test connectivity in both directions ──
    print("\n" + "="*70)
    print("  Testing HaLow connectivity")
    print("="*70, flush=True)
    
    # From Edge to Tube
    conn = await asyncio.wait_for(
        asyncssh.connect(EDGE["host"], username=EDGE["username"],
                       password=EDGE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        await run_cmd(conn, "ping -c 10 -W 5 -I wlan0 192.168.1.103", "Edge→Tube ping via HaLow", timeout=60)
    
    # From Tube to Edge
    conn = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        await run_cmd(conn, "ping -c 10 -W 5 192.168.1.196", "Tube→Edge ping via HaLow", timeout=60)
        await run_cmd(conn, "iwinfo wlan0 assoclist", "AP current rates")
    
    # From Windows
    print("\n  Testing from Windows...", flush=True)
    
    # Final Edge check
    conn = await asyncio.wait_for(
        asyncssh.connect(EDGE["host"], username=EDGE["username"],
                       password=EDGE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        await run_cmd(conn, "iwinfo wlan0 info", "Edge final iwinfo")
        await run_cmd(conn, "iwinfo wlan0 assoclist", "Edge assoclist")
        await run_cmd(conn, "morse_cli -i wlan0 channel", "Edge morse_cli channel")
    
    print("\n" + "="*70)
    print("  CONNECTIVITY TEST COMPLETE")
    print("="*70, flush=True)

asyncio.run(main())
