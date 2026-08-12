#!/usr/bin/env python3
"""
Configure HaLow network on both AP and STA for maximum 8 MHz bandwidth.
Step 1: Configure and apply AP
Step 2: Configure and apply STA
Step 3: Wait for association
Step 4: Verify link
"""
import asyncio, asyncssh, sys, time

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root", "name": "Tube-AHM (AP)"}
EDGE = {"host": "192.168.1.111", "username": "root", "password": "root", "name": "Edge Gateway (STA)"}

SSID = "UNAL-HaLow-Tesis"
KEY = "banano2026"
CHANNEL = "12"          # 908 MHz
COUNTRY = "US"
S1G_CHANBW = "8"        # 8 MHz operating bandwidth — MAXIMUM

async def run_cmd(conn, cmd, label=None, timeout=15, quiet=False):
    if label and not quiet:
        print(f"  [{label}]", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=timeout), timeout=timeout+5)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if not quiet:
            if out:
                print(f"    {out[:500]}", flush=True)
            if err and not out:
                print(f"    {err[:300]}", flush=True)
        return out or err or ""
    except Exception as e:
        if not quiet:
            print(f"    ERROR: {e}", flush=True)
        return f"ERROR: {e}"

async def connect(dev):
    return await asyncio.wait_for(
        asyncssh.connect(dev["host"], username=dev["username"],
                       password=dev["password"], known_hosts=None,
                       login_timeout=15),
        timeout=20
    )

# ─────────────────────────────────────────────────────────
#  STEP 1: CONFIGURE AP (Tube-AHM)
# ─────────────────────────────────────────────────────────
async def configure_ap():
    print("\n" + "="*70)
    print("  STEP 1: Configure AP (Tube-AHM 192.168.1.103)")
    print("="*70, flush=True)
    
    conn = await connect(TUBE)
    async with conn:
        # Check BCF file
        bcf = await run_cmd(conn, "uci get wireless.radio0.bcf", "Current BCF", quiet=True)
        print(f"  BCF: {bcf}", flush=True)
        
        # Configure radio0 for maximum 8 MHz
        commands = [
            f"uci set wireless.radio0.country='{COUNTRY}'",
            f"uci set wireless.radio0.channel='{CHANNEL}'",
            f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
            "uci set wireless.radio0.disabled='0'",
            # WiFi interface
            f"uci set wireless.wifinet0.ssid='{SSID}'",
            "uci set wireless.wifinet0.mode='ap'",
            "uci set wireless.wifinet0.encryption='sae'",
            "uci set wireless.wifinet0.sae_pwe='1'",
            f"uci set wireless.wifinet0.key='{KEY}'",
            "uci set wireless.wifinet0.network='ahwlan'",
            "uci set wireless.wifinet0.wds='1'",
        ]
        
        for cmd in commands:
            await run_cmd(conn, cmd, quiet=True)
        
        # Show final config
        print("\n  Applying AP configuration:", flush=True)
        await run_cmd(conn, "uci changes wireless", "UCI changes")
        await run_cmd(conn, "uci commit wireless", "Commit", quiet=True)
        
        print("\n  Final /etc/config/wireless:", flush=True)
        await run_cmd(conn, "cat /etc/config/wireless", "Config file")
        
        # Apply
        print("\n  Restarting wifi on AP...", flush=True)
        await run_cmd(conn, "wifi down; sleep 2; wifi up", "wifi restart", timeout=30)
        
        # Wait for AP to come up
        print("  Waiting 10s for AP to initialize...", flush=True)
        await asyncio.sleep(10)
        
        # Verify
        result = await run_cmd(conn, "iwinfo wlan0 info", "AP status after restart")
        ch_info = await run_cmd(conn, "morse_cli -i wlan0 channel", "morse_cli channel")
        
        return "ESSID" in result

# ─────────────────────────────────────────────────────────
#  STEP 2: CONFIGURE STA (Edge Gateway)
# ─────────────────────────────────────────────────────────
async def configure_sta():
    print("\n" + "="*70)
    print("  STEP 2: Configure STA (Edge Gateway 192.168.1.111)")
    print("="*70, flush=True)
    
    conn = await connect(EDGE)
    async with conn:
        # Check BCF file existence
        bcf = await run_cmd(conn, "uci get wireless.radio0.bcf", "Current BCF", quiet=True)
        print(f"  BCF: {bcf}", flush=True)
        bcf_exists = await run_cmd(conn, f"ls -la /lib/firmware/morse/{bcf} 2>/dev/null || echo 'NOT FOUND'", quiet=True)
        if "NOT FOUND" in bcf_exists:
            print(f"  ⚠ BCF file {bcf} not found! Listing available:", flush=True)
            await run_cmd(conn, "ls /lib/firmware/morse/*.bin", "Available BCF files")
            # Try to find correct BCF for this board
            await run_cmd(conn, "cat /proc/device-tree/model 2>/dev/null || echo 'unknown model'", "Device model")
        else:
            print(f"  BCF file exists: {bcf_exists}", flush=True)
        
        # Configure radio0 for maximum 8 MHz
        commands = [
            f"uci set wireless.radio0.country='{COUNTRY}'",
            f"uci set wireless.radio0.channel='{CHANNEL}'",
            f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
            "uci set wireless.radio0.txpower='30'",          # MAX TX power
            "uci set wireless.radio0.disabled='0'",
            # WiFi interface
            f"uci set wireless.wifinet0.ssid='{SSID}'",
            "uci set wireless.wifinet0.mode='sta'",
            "uci set wireless.wifinet0.encryption='sae'",
            "uci set wireless.wifinet0.sae_pwe='1'",
            f"uci set wireless.wifinet0.key='{KEY}'",
            "uci set wireless.wifinet0.network='wwan'",
        ]
        
        for cmd in commands:
            await run_cmd(conn, cmd, quiet=True)
        
        # Show final config
        print("\n  Applying STA configuration:", flush=True)
        await run_cmd(conn, "uci changes wireless", "UCI changes")
        await run_cmd(conn, "uci commit wireless", "Commit", quiet=True)
        
        print("\n  Final /etc/config/wireless:", flush=True)
        await run_cmd(conn, "cat /etc/config/wireless", "Config file")
        
        # Apply
        print("\n  Restarting wifi on STA...", flush=True)
        await run_cmd(conn, "wifi down; sleep 2; wifi up", "wifi restart", timeout=30)

# ─────────────────────────────────────────────────────────
#  STEP 3: WAIT FOR ASSOCIATION
# ─────────────────────────────────────────────────────────
async def wait_for_association(max_wait=90):
    print("\n" + "="*70)
    print("  STEP 3: Waiting for STA association...")
    print("="*70, flush=True)
    
    start = time.time()
    while time.time() - start < max_wait:
        elapsed = int(time.time() - start)
        try:
            conn = await connect(EDGE)
            async with conn:
                result = await run_cmd(conn, "iwinfo wlan0 info 2>/dev/null | grep -E 'ESSID|Signal|Bit Rate|Channel'", quiet=True)
                if SSID in result and "Signal" in result:
                    print(f"  ✓ ASSOCIATED after {elapsed}s!", flush=True)
                    print(f"    {result}", flush=True)
                    return True
                else:
                    print(f"  [{elapsed}s] Not yet associated... ({result[:80]})", flush=True)
        except Exception as e:
            print(f"  [{elapsed}s] Connection error: {e}", flush=True)
        
        await asyncio.sleep(5)
    
    print(f"  ✗ Association timed out after {max_wait}s", flush=True)
    return False

# ─────────────────────────────────────────────────────────
#  STEP 4: VERIFY LINK
# ─────────────────────────────────────────────────────────
async def verify_link():
    print("\n" + "="*70)
    print("  STEP 4: Verify HaLow Link Quality")
    print("="*70, flush=True)
    
    # Check from AP side
    print("\n  --- AP Side (Tube-AHM) ---", flush=True)
    conn = await connect(TUBE)
    async with conn:
        await run_cmd(conn, "iwinfo wlan0 info", "AP iwinfo")
        await run_cmd(conn, "iwinfo wlan0 assoclist", "AP assoclist (shows STA rates)")
        await run_cmd(conn, "morse_cli -i wlan0 channel", "AP morse_cli channel")
    
    # Check from STA side
    print("\n  --- STA Side (Edge Gateway) ---", flush=True)
    conn = await connect(EDGE)
    async with conn:
        await run_cmd(conn, "iwinfo wlan0 info", "STA iwinfo")
        await run_cmd(conn, "iwinfo wlan0 assoclist", "STA assoclist (shows AP rates)")
        await run_cmd(conn, "morse_cli -i wlan0 channel", "STA morse_cli channel")
        await run_cmd(conn, "iwinfo wlan0 txpower", "STA TX power")
        await run_cmd(conn, "iw dev wlan0 station dump | head -30", "STA station dump")
    
    # Quick ping test over HaLow
    print("\n  --- HaLow connectivity test ---", flush=True)
    conn = await connect(TUBE)
    async with conn:
        await run_cmd(conn, "ping -c 5 -W 3 192.168.1.196", "Ping Edge over HaLow", timeout=25)

# ─────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────
async def main():
    print("HaLow Network Setup — Maximum 8 MHz Bandwidth")
    print(f"SSID: {SSID} | Channel: {CHANNEL} | BW: {S1G_CHANBW} MHz | WPA3-SAE")
    print(flush=True)
    
    # Step 1: Configure AP
    ap_ok = await configure_ap()
    if not ap_ok:
        print("\n⚠ AP might not be fully up. Continuing anyway...", flush=True)
    
    # Step 2: Configure STA
    await configure_sta()
    
    # Step 3: Wait for association
    print("\n  Waiting 15s for STA to scan and associate...", flush=True)
    await asyncio.sleep(15)
    associated = await wait_for_association(max_wait=90)
    
    if associated:
        # Step 4: Verify
        await verify_link()
    else:
        print("\n  STA did not associate. Checking logs...", flush=True)
        conn = await connect(EDGE)
        async with conn:
            await run_cmd(conn, "logread | grep -iE 'wlan|morse|wpa_supplicant|assoc|auth|sae' | tail -30", "Edge logread")
            await run_cmd(conn, "iwinfo wlan0 info", "Edge iwinfo")
            await run_cmd(conn, "dmesg | grep -i morse | tail -20", "Edge dmesg morse")
    
    print("\n" + "="*70)
    print("  SETUP COMPLETE")
    print("="*70, flush=True)

asyncio.run(main())
