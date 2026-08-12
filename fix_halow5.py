#!/usr/bin/env python3
"""
FIX: Inject S1G channel parameters into Edge STA wpa_supplicant config.

ROOT CAUSE: morse_overrides.sh morse_override_wpa_supplicant_add_network()
only adds op_class, s1g_prim_chwidth, s1g_prim_1mhz_chan_index for adhoc/mesh,
NOT for STA mode. This leaves the STA scanning at 1 MHz on the wrong sub-channel.

From channels.csv:  US,8,12,4,71,908.0  (channel 12 only at 8 MHz)
AP hostapd uses:    op_class=71, s1g_prim_chwidth=1, s1g_prim_1mhz_chan_index=3
STA wpa_supplicant: MISSING all S1G parameters

FIX: Add these parameters to the STA's wpa_supplicant network block, 
set morse_cli channel, and restart wpa_supplicant.
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
    print("=" * 70)
    print("  FIX: Inject S1G parameters into Edge STA wpa_supplicant config")
    print("=" * 70, flush=True)
    
    edge = await asyncio.wait_for(
        asyncssh.connect(EDGE_ETH["host"], username=EDGE_ETH["username"],
                       password=EDGE_ETH["password"], known_hosts=None,
                       login_timeout=15), timeout=20)
    tube = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None,
                       login_timeout=15), timeout=20)

    # STEP 1: Verify Tube AP is running correctly
    print("\n--- STEP 1: Verify AP ---", flush=True)
    ap_info = await run_cmd(tube, "iwinfo wlan0 info | head -5", "Tube AP status")
    ap_channel = await run_cmd(tube, "morse_cli -i wlan0 channel", "Tube channel")
    
    if "UNAL-HaLow-Tesis" not in ap_info:
        print("ERROR: Tube AP not running! Starting it...")
        await run_cmd(tube, "wifi up", quiet=True)
        await asyncio.sleep(10)
    
    # STEP 2: Read current wpa_supplicant config on Edge
    print("\n--- STEP 2: Current Edge wpa_supplicant config ---", flush=True)
    current_config = await run_cmd(edge, "cat /tmp/run/wpa_supplicant-wlan0.conf")
    
    # STEP 3: Stop wpa_supplicant_s1g on Edge
    print("\n--- STEP 3: Stop wpa_supplicant and set channel ---", flush=True)
    await run_cmd(edge, "killall wpa_supplicant_s1g 2>/dev/null; sleep 2", "Kill wpa_supplicant")
    
    # Set morse_cli channel to match AP exactly: 908 MHz center, 8 MHz op BW, 2 MHz primary, index 3
    await run_cmd(edge, "morse_cli -i wlan0 channel -c 908000 -o 8 -p 2 -n 3", "Set morse_cli channel")
    await run_cmd(edge, "morse_cli -i wlan0 channel", "Verify morse channel")
    
    # STEP 4: Modify wpa_supplicant config to include S1G parameters
    print("\n--- STEP 4: Inject S1G parameters into wpa_supplicant config ---", flush=True)
    
    # Build the new wpa_supplicant config with S1G parameters in the network block
    new_config = """country=US
ctrl_interface=/var/run/wpa_supplicant_s1g
sae_pwe=1

network={
\tscan_ssid=1
\tssid="UNAL-HaLow-Tesis"
\tkey_mgmt=SAE
\tsae_password="banano2026"
\tpairwise=CCMP
\tproto=RSN
\tieee80211w=2
\top_class=71
\ts1g_prim_chwidth=1
\ts1g_prim_1mhz_chan_index=3
}
"""
    
    # Write the new config
    await run_cmd(edge, f"cat > /tmp/run/wpa_supplicant-wlan0.conf << 'WPAEOF'\n{new_config}WPAEOF", "Write new config")
    
    # Verify
    await run_cmd(edge, "cat /tmp/run/wpa_supplicant-wlan0.conf", "New wpa_supplicant config")
    
    # STEP 5: Start wpa_supplicant_s1g with the modified config
    print("\n--- STEP 5: Start wpa_supplicant_s1g ---", flush=True)
    await run_cmd(edge, "/usr/sbin/wpa_supplicant_s1g -t -D nl80211 -s -i wlan0 -c /tmp/run/wpa_supplicant-wlan0.conf -B", "Start wpa_supplicant")
    
    # Wait for association
    for wait_secs in [10, 15, 20, 30]:
        print(f"\nWaiting {wait_secs}s...", flush=True)
        await asyncio.sleep(wait_secs)
        
        edge_info = await run_cmd(edge, "iwinfo wlan0 info | head -10", f"Edge status after {wait_secs}s")
        tube_assoc = await run_cmd(tube, "iwinfo wlan0 assoclist", f"Tube assoclist")
        
        if "UNAL-HaLow-Tesis" in edge_info and "unknown" not in edge_info.split("ESSID:")[1].split("\n")[0]:
            print("\n*** ASSOCIATED SUCCESSFULLY! ***", flush=True)
            break
        
        # Check morse channel
        await run_cmd(edge, "morse_cli -i wlan0 channel", "Edge morse channel", quiet=True)
        
        # Check auth logs
        await run_cmd(edge, "logread | grep -iE 'auth|assoc' | tail -5", f"Recent auth logs")
    else:
        print("\n*** Still not associated. Checking details... ***", flush=True)
    
    # Final status check
    print("\n" + "=" * 70)
    print("  FINAL STATUS")
    print("=" * 70, flush=True)
    
    await run_cmd(edge, "iwinfo wlan0 info", "Edge iwinfo FINAL")
    await run_cmd(edge, "morse_cli -i wlan0 channel", "Edge morse channel FINAL")
    await run_cmd(edge, "ip addr show wlan0", "Edge wlan0 IP")
    await run_cmd(edge, "logread | grep -iE 'auth|assoc|SAE|connected' | tail -20", "Edge wireless logs")
    await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube assoclist FINAL")
    
    # Test ping
    await run_cmd(edge, "ping -I wlan0 -c 5 -W 3 192.168.1.103", "Ping via HaLow")
    
    edge.close(); tube.close()
    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70, flush=True)

asyncio.run(main())
