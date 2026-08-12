#!/usr/bin/env python3
"""
Reboot Edge Gateway and check AP logs for auth frames.
Also check Tube hostapd logs to see if it receives the Edge's auth attempts.
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
    tube = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None,
                       login_timeout=15), timeout=20)

    # STEP 1: Check AP logs for Edge auth frames
    print("=" * 70)
    print("  STEP 1: Check AP (Tube) logs for Edge auth attempts")
    print("=" * 70, flush=True)
    
    await run_cmd(tube, "logread | grep -iE 'DE:87|auth|assoc|sta|wlan0' | tail -30", "Tube logread for Edge MAC")
    await run_cmd(tube, "dmesg | grep -iE 'DE:87|auth|assoc' | tail -20", "Tube dmesg for Edge auth")
    
    # Check if hostapd is running and its config
    await run_cmd(tube, "ps | grep hostapd", "hostapd process")
    await run_cmd(tube, "cat /var/run/hostapd-wlan0.conf 2>/dev/null | head -30", "Tube hostapd config")
    
    # STEP 2: Reboot Edge
    print("\n" + "=" * 70)
    print("  STEP 2: Rebooting Edge Gateway")
    print("=" * 70, flush=True)
    
    try:
        edge = await asyncio.wait_for(
            asyncssh.connect(EDGE_ETH["host"], username=EDGE_ETH["username"],
                           password=EDGE_ETH["password"], known_hosts=None,
                           login_timeout=15), timeout=20)
        
        # Verify config before reboot
        await run_cmd(edge, "cat /etc/config/wireless", "Edge wireless config (persisted)")
        
        # Reboot
        print("\nSending reboot command...", flush=True)
        try:
            await edge.run("reboot", timeout=5)
        except:
            pass  # Connection will drop
        print("Edge rebooting...", flush=True)
    except Exception as e:
        print(f"Edge connection: {e}", flush=True)
    
    # Wait for Edge to come back up
    print("Waiting 90s for Edge to reboot and associate...", flush=True)
    await asyncio.sleep(90)
    
    # STEP 3: Check if Edge came back and associated
    print("\n" + "=" * 70)
    print("  STEP 3: Check post-reboot status")
    print("=" * 70, flush=True)
    
    # First check if Edge is pingable
    try:
        edge2 = await asyncio.wait_for(
            asyncssh.connect(EDGE_ETH["host"], username=EDGE_ETH["username"],
                           password=EDGE_ETH["password"], known_hosts=None,
                           login_timeout=20), timeout=30)
        
        print("Edge back online via Ethernet!", flush=True)
        
        await run_cmd(edge2, "uptime", "Edge uptime")
        await run_cmd(edge2, "iwinfo wlan0 info", "Edge iwinfo")
        await run_cmd(edge2, "iwinfo wlan0 assoclist", "Edge assoclist")
        await run_cmd(edge2, "morse_cli -i wlan0 channel", "Edge morse channel")
        await run_cmd(edge2, "iwinfo wlan0 txpower", "Edge TX power")
        await run_cmd(edge2, "ip addr show wlan0", "Edge wlan0 IP")
        await run_cmd(edge2, "logread | grep -iE 'auth|assoc|SAE|connected|wlan0' | tail -30", "Edge logread wireless")
        
        # Check Tube side
        await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube assoclist")
        
        # If associated, test ping
        edge_info = await run_cmd(edge2, "iwinfo wlan0 info | head -5", quiet=True)
        if "UNAL-HaLow-Tesis" in edge_info:
            print("\n*** ASSOCIATED! Testing ping... ***", flush=True)
            await run_cmd(edge2, "ping -I wlan0 -c 5 -W 3 192.168.1.103", "Ping via HaLow")
        else:
            print("\n*** Still NOT associated after reboot ***", flush=True)
            await run_cmd(edge2, "logread | grep -iE 'error|fail|wpa_supplicant|morse' | tail -30", "Edge error logs")
            await run_cmd(edge2, "dmesg | grep -iE 'morse|wlan|error|fail|bandwidth|Bandwidth' | tail -30", "Edge dmesg")
            
            # Check if hostapd on Tube sees anything
            await run_cmd(tube, "logread | grep -iE 'DE:87|0c:bf:74|auth' | tail -20", "Tube logs for Edge")
        
        edge2.close()
    except Exception as e:
        print(f"Cannot connect to Edge after reboot: {e}", flush=True)
        print("Edge may still be booting. Try again in 30s.", flush=True)

    tube.close()
    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70, flush=True)

asyncio.run(main())
