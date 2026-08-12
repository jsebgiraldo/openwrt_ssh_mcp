#!/usr/bin/env python3
"""
Fix Edge Gateway HaLow - clean up config and debug association failure.
Connect via Ethernet (192.168.1.111)
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
    # STEP 1: Debug why Edge wlan0 failed to associate
    # ========================================
    print("=" * 70)
    print("  STEP 1: Debug Edge association failure")
    print("=" * 70, flush=True)

    await run_cmd(edge, "logread | grep -iE 'wlan|morse|wpa_supplicant|assoc|deauth|fail|error|sae|reject' | tail -50", "Edge logread wireless")
    await run_cmd(edge, "dmesg | grep -iE 'morse|wlan|error|fail' | tail -30", "Edge dmesg errors")
    
    # Check if default_radio0 was accidentally created (duplicate)
    await run_cmd(edge, "uci show wireless", "Edge full UCI wireless")

    # ========================================
    # STEP 2: Clean Edge wireless config completely
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 2: Clean and rebuild Edge wireless config")
    print("=" * 70, flush=True)

    # Remove any duplicate interface sections
    cleanup_cmds = [
        # Delete any accidental default_radio0 section
        "uci delete wireless.default_radio0 2>/dev/null; echo 'cleaned default_radio0'",
        # Delete existing wifinet0 to rebuild cleanly
        "uci delete wireless.wifinet0 2>/dev/null; echo 'cleaned wifinet0'",
        # Also clean any other wifi-iface sections
        "uci delete wireless.wifinet1 2>/dev/null; echo 'cleaned wifinet1'",
    ]
    for cmd in cleanup_cmds:
        await run_cmd(edge, cmd, quiet=True)
    
    # Now set radio config properly
    radio_cmds = [
        "uci set wireless.radio0=wifi-device",
        "uci set wireless.radio0.type='morse'",
        "uci set wireless.radio0.band='s1g'",
        "uci set wireless.radio0.hwmode='11ah'",
        "uci set wireless.radio0.channel='12'",
        "uci set wireless.radio0.country='US'",
        "uci set wireless.radio0.s1g_chanbw='8'",
        "uci set wireless.radio0.disabled='0'",
        "uci set wireless.radio0.bcf='bcf_mf15457.bin'",
        "uci set wireless.radio0.path='platform/soc/fe300000.mmc/mmc_host/mmc1/mmc1:0001/mmc1:0001:2'",
    ]
    for cmd in radio_cmds:
        await run_cmd(edge, cmd, quiet=True)
    
    # Create the STA interface fresh
    iface_cmds = [
        "uci set wireless.wifinet0=wifi-iface",
        "uci set wireless.wifinet0.device='radio0'",
        "uci set wireless.wifinet0.mode='sta'",
        "uci set wireless.wifinet0.network='wwan'",
        "uci set wireless.wifinet0.ssid='UNAL-HaLow-Tesis'",
        "uci set wireless.wifinet0.encryption='sae'",
        "uci set wireless.wifinet0.key='banano2026'",
        "uci set wireless.wifinet0.sae_pwe='1'",
        "uci commit wireless",
    ]
    for cmd in iface_cmds:
        await run_cmd(edge, cmd, quiet=True)
    
    print("Edge config rebuilt.", flush=True)
    await run_cmd(edge, "uci show wireless", "Edge final UCI wireless")
    await run_cmd(edge, "cat /etc/config/wireless", "Edge /etc/config/wireless")

    # ========================================
    # STEP 3: Also verify Tube AP config is clean
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 3: Verify Tube AP config")
    print("=" * 70, flush=True)
    
    # Clean Tube too - make sure it uses wifinet0 properly
    tube_cleanup = [
        "uci delete wireless.default_radio0 2>/dev/null; echo ok",
    ]
    for cmd in tube_cleanup:
        await run_cmd(tube, cmd, quiet=True)
    
    await run_cmd(tube, "uci show wireless", "Tube UCI wireless")

    # ========================================
    # STEP 4: Restart wifi - AP first, then STA
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 4: Restart wifi")
    print("=" * 70, flush=True)

    print("Restarting Tube AP...", flush=True)
    await run_cmd(tube, "wifi down; sleep 3; wifi up")
    print("Waiting 15s for AP...", flush=True)
    await asyncio.sleep(15)
    
    tube_status = await run_cmd(tube, "iwinfo wlan0 info 2>/dev/null | head -5", "Tube AP status")
    if "UNAL-HaLow-Tesis" not in tube_status:
        print("WARNING: Tube AP not ready yet, waiting 10 more seconds...", flush=True)
        await asyncio.sleep(10)
        await run_cmd(tube, "iwinfo wlan0 info | head -5", "Tube AP status retry")

    print("\nRestarting Edge STA...", flush=True)
    await run_cmd(edge, "wifi down; sleep 3; wifi up")
    print("Waiting 30s for STA association...", flush=True)
    await asyncio.sleep(30)

    # ========================================
    # STEP 5: Check association
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 5: Check association status")
    print("=" * 70, flush=True)

    edge_info = await run_cmd(edge, "iwinfo wlan0 info", "Edge iwinfo")
    await run_cmd(edge, "iwinfo wlan0 assoclist", "Edge assoclist")
    await run_cmd(edge, "wpa_cli -i wlan0 status 2>/dev/null || echo 'wpa_cli N/A'", "Edge wpa_cli status")
    await run_cmd(edge, "ip addr show wlan0", "Edge wlan0 IP")
    await run_cmd(edge, "morse_cli -i wlan0 channel", "Edge morse channel")
    await run_cmd(edge, "iwinfo wlan0 txpower", "Edge TX power")
    
    await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube assoclist")
    await run_cmd(tube, "morse_cli -i wlan0 channel", "Tube morse channel")
    
    # Check if associated
    if "No station" in edge_info or "unknown" in edge_info.split("ESSID:")[1][:20] if "ESSID:" in edge_info else True:
        print("\n⚠️  Edge NOT associated yet. Checking logs...", flush=True)
        await run_cmd(edge, "logread | grep -iE 'wpa_supplicant|sae|assoc|auth|fail|reject|timeout' | tail -30", "Edge association logs")
        await run_cmd(edge, "dmesg | tail -20", "Edge dmesg recent")
        
        # Try waiting more
        print("\nWaiting 20 more seconds...", flush=True)
        await asyncio.sleep(20)
        await run_cmd(edge, "iwinfo wlan0 info", "Edge iwinfo (retry)")
        await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube assoclist (retry)")
    
    # Final ping test using wlan0 source IP to ensure HaLow path
    print("\n--- Ping via HaLow (source 192.168.1.196) ---", flush=True)
    await run_cmd(edge, "ping -I wlan0 -c 5 -W 3 192.168.1.103 2>&1 || ping -I 192.168.1.196 -c 5 -W 3 192.168.1.103 2>&1", "Edge ping Tube via wlan0")

    edge.close()
    tube.close()

    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70, flush=True)

asyncio.run(main())
