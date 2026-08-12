#!/usr/bin/env python3
"""
Fix HaLow - Revert to parameters closer to original working config.
Key insight: The original Tube had s1g_chanbw='2' and worked at 8 MHz operating BW.
The STA doesn't need s1g_chanbw - it auto-detects from AP.
"""
import asyncio, asyncssh

EDGE_ETH = {"host": "192.168.1.111", "username": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}

async def run_cmd(conn, cmd, label="", quiet=False):
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=20), timeout=25)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out if out else err if err else "(empty)"
        if not quiet:
            if label:
                print(f"\n--- {label} ---", flush=True)
            print(result, flush=True)
        return result
    except Exception as e:
        if not quiet:
            print(f"ERROR ({label}): {e}", flush=True)
        return f"ERROR: {e}"

async def main():
    edge = await asyncio.wait_for(
        asyncssh.connect(EDGE_ETH["host"], username=EDGE_ETH["username"],
                       password=EDGE_ETH["password"], known_hosts=None,
                       login_timeout=15), timeout=20)
    tube = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None,
                       login_timeout=15), timeout=20)

    # ========================================
    # STEP 1: Revert Tube AP to original working s1g_chanbw=2
    # ========================================
    print("=" * 70)
    print("  STEP 1: Configure Tube AP (revert s1g_chanbw to 2)")
    print("=" * 70, flush=True)
    
    tube_cmds = [
        "uci set wireless.radio0.s1g_chanbw='2'",    # Original working value!
        "uci delete wireless.radio0.txpower 2>/dev/null; echo ok",  # Let it auto
        "uci commit wireless",
    ]
    for cmd in tube_cmds:
        await run_cmd(tube, cmd, quiet=True)
    await run_cmd(tube, "uci show wireless.radio0", "Tube radio config")

    # ========================================
    # STEP 2: Configure Edge STA - remove s1g_chanbw, let it auto-detect
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 2: Configure Edge STA (remove s1g_chanbw, auto-detect)")
    print("=" * 70, flush=True)
    
    edge_cmds = [
        "uci delete wireless.radio0.s1g_chanbw 2>/dev/null; echo ok",  # Let STA auto-detect
        "uci delete wireless.radio0.txpower 2>/dev/null; echo ok",     # Let it auto
        "uci commit wireless",
    ]
    for cmd in edge_cmds:
        await run_cmd(edge, cmd, quiet=True)
    await run_cmd(edge, "uci show wireless", "Edge full config")

    # ========================================
    # STEP 3: Restart both - AP first, then STA
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 3: Restart wifi (AP first, STA second)")
    print("=" * 70, flush=True)
    
    # Stop both
    print("Stopping both...", flush=True)
    await run_cmd(edge, "wifi down", quiet=True)
    await run_cmd(tube, "wifi down", quiet=True)
    await asyncio.sleep(5)
    
    # Start AP
    print("Starting Tube AP...", flush=True)
    await run_cmd(tube, "wifi up", quiet=True)
    await asyncio.sleep(15)
    
    tube_status = await run_cmd(tube, "iwinfo wlan0 info | head -8", "Tube AP status")
    await run_cmd(tube, "morse_cli -i wlan0 channel", "Tube morse channel")

    # Start STA
    print("\nStarting Edge STA...", flush=True)
    await run_cmd(edge, "wifi up", quiet=True)
    
    # Wait in stages
    for wait_label, wait_secs in [("15s", 15), ("30s more", 15), ("Final 15s", 15)]:
        print(f"Waiting {wait_label}...", flush=True)
        await asyncio.sleep(wait_secs)
        
        edge_info = await run_cmd(edge, "iwinfo wlan0 info | head -8", f"Edge status after {wait_label}")
        tube_assoc = await run_cmd(tube, "iwinfo wlan0 assoclist", f"Tube assoclist after {wait_label}")
        
        # Check if associated
        if "UNAL-HaLow-Tesis" in edge_info and "Signal:" in edge_info and "unknown" not in edge_info.split("Signal:")[1][:15]:
            print("\n*** EDGE ASSOCIATED! ***", flush=True)
            break
        elif "No station" not in tube_assoc and tube_assoc != "(empty)":
            print("\n*** TUBE SEES EDGE! ***", flush=True)
            break
    
    # ========================================
    # STEP 4: Full status check
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 4: Full status check")
    print("=" * 70, flush=True)
    
    await run_cmd(edge, "iwinfo wlan0 info", "Edge iwinfo FULL")
    await run_cmd(edge, "iwinfo wlan0 assoclist", "Edge assoclist")
    await run_cmd(edge, "morse_cli -i wlan0 channel", "Edge morse channel")
    await run_cmd(edge, "iwinfo wlan0 txpower", "Edge TX power")
    await run_cmd(edge, "ip addr show wlan0", "Edge wlan0 IP")
    
    await run_cmd(tube, "iwinfo wlan0 info", "Tube iwinfo FULL")
    await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube assoclist")
    await run_cmd(tube, "morse_cli -i wlan0 channel", "Tube morse channel")
    
    # Check last auth logs
    await run_cmd(edge, "logread | grep -iE 'auth|assoc|SAE|connected' | tail -20", "Edge auth logs")
    
    # Ping test using HaLow interface
    await run_cmd(edge, "ping -I wlan0 -c 5 -W 3 192.168.1.103", "Ping via HaLow")

    edge.close()
    tube.close()

    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70, flush=True)

asyncio.run(main())
