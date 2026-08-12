#!/usr/bin/env python3
"""
Fix HaLow configuration on both devices and bring the link up.
- Connect to Edge via Ethernet (192.168.1.111)
- Connect to Tube-AHM AP (192.168.1.103)
- Configure both for maximum 8 MHz bandwidth
- Restart wifi and verify association
"""
import asyncio, asyncssh, time

EDGE_ETH = {"host": "192.168.1.111", "username": "root", "password": "root", "name": "Edge Gateway (STA)"}
TUBE = {"host": "192.168.1.103", "username": "root", "password": "root", "name": "Tube-AHM (AP)"}

async def ssh_connect(dev):
    return await asyncio.wait_for(
        asyncssh.connect(dev["host"], username=dev["username"],
                       password=dev["password"], known_hosts=None,
                       login_timeout=15),
        timeout=20
    )

async def run_cmd(conn, cmd, label="", quiet=False):
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=15), timeout=20)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out or err or "(empty)"
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
    # ========================================
    # STEP 1: Check current state of both devices
    # ========================================
    print("=" * 70)
    print("  STEP 1: Check current wireless config on both devices")
    print("=" * 70, flush=True)

    edge = await ssh_connect(EDGE_ETH)
    tube = await ssh_connect(TUBE)

    # Check current configs
    print("\n>>> EDGE current config:", flush=True)
    await run_cmd(edge, "uci show wireless", "Edge UCI wireless")
    await run_cmd(edge, "ifconfig wlan0 2>/dev/null | head -5 || echo 'wlan0 not found'", "Edge wlan0 status")
    
    print("\n>>> TUBE current config:", flush=True)
    await run_cmd(tube, "uci show wireless", "Tube UCI wireless")
    await run_cmd(tube, "iwinfo wlan0 assoclist 2>/dev/null || echo 'no assoclist'", "Tube assoclist")

    # ========================================
    # STEP 2: Configure Tube-AHM (AP) for 8 MHz
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 2: Configure Tube-AHM (AP) - 8 MHz max bandwidth")
    print("=" * 70, flush=True)
    
    tube_cmds = [
        # Radio config - 8 MHz bandwidth, channel 12, max power
        "uci set wireless.radio0.type='morse'",
        "uci set wireless.radio0.band='s1g'",
        "uci set wireless.radio0.hwmode='11ah'",
        "uci set wireless.radio0.channel='12'",
        "uci set wireless.radio0.country='US'",
        "uci set wireless.radio0.s1g_chanbw='8'",        # KEY: 8 MHz operating BW
        "uci set wireless.radio0.txpower='30'",           # Max TX power
        "uci set wireless.radio0.disabled='0'",
        "uci set wireless.radio0.bcf='bcf_mf04151.bin'",
        # Interface config - AP mode
        "uci set wireless.default_radio0.mode='ap'",
        "uci set wireless.default_radio0.ssid='UNAL-HaLow-Tesis'",
        "uci set wireless.default_radio0.encryption='sae'",
        "uci set wireless.default_radio0.key='banano2026'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='ahwlan'",
        "uci set wireless.default_radio0.wds='1'",
        "uci commit wireless",
    ]
    
    for cmd in tube_cmds:
        await run_cmd(tube, cmd, quiet=True)
    print("Tube-AHM AP config committed.", flush=True)
    await run_cmd(tube, "uci show wireless", "Tube final config")

    # ========================================
    # STEP 3: Configure Edge Gateway (STA) for 8 MHz  
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 3: Configure Edge Gateway (STA) - 8 MHz max bandwidth")
    print("=" * 70, flush=True)
    
    edge_cmds = [
        # Radio config - 8 MHz, max power
        "uci set wireless.radio0.type='morse'",
        "uci set wireless.radio0.band='s1g'",
        "uci set wireless.radio0.hwmode='11ah'",
        "uci set wireless.radio0.channel='12'",
        "uci set wireless.radio0.country='US'",
        "uci set wireless.radio0.s1g_chanbw='8'",        # KEY: 8 MHz operating BW
        "uci set wireless.radio0.txpower='21'",           # Max for MM6108A1 SDIO
        "uci set wireless.radio0.disabled='0'",
        # Interface config - STA mode
        "uci set wireless.default_radio0.mode='sta'",
        "uci set wireless.default_radio0.ssid='UNAL-HaLow-Tesis'",
        "uci set wireless.default_radio0.encryption='sae'",
        "uci set wireless.default_radio0.key='banano2026'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='wwan'",
        "uci set wireless.default_radio0.wds='1'",
        "uci commit wireless",
    ]
    
    for cmd in edge_cmds:
        await run_cmd(edge, cmd, quiet=True)
    print("Edge Gateway STA config committed.", flush=True)
    await run_cmd(edge, "uci show wireless", "Edge final config")

    # ========================================
    # STEP 3b: Ensure Edge has network config for wwan (HaLow IP)
    # ========================================
    print("\n--- Configuring Edge network for wwan (HaLow) ---", flush=True)
    net_cmds = [
        "uci set network.wwan=interface",
        "uci set network.wwan.proto='static'",
        "uci set network.wwan.ipaddr='192.168.1.196'",
        "uci set network.wwan.netmask='255.255.255.0'",
        "uci set network.wwan.gateway='192.168.1.1'",
        "uci set network.wwan.dns='192.168.1.1'",
        "uci commit network",
    ]
    for cmd in net_cmds:
        await run_cmd(edge, cmd, quiet=True)
    print("Edge wwan network config committed.", flush=True)
    await run_cmd(edge, "uci show network.wwan", "Edge wwan config")

    # ========================================
    # STEP 4: Restart wifi on BOTH devices (AP first, then STA)
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 4: Restart wifi (AP first, then STA)")
    print("=" * 70, flush=True)
    
    print("\nRestarting Tube-AHM AP wifi...", flush=True)
    await run_cmd(tube, "wifi down; sleep 2; wifi up", "Tube wifi restart")
    
    print("Waiting 15s for AP to come up...", flush=True)
    await asyncio.sleep(15)
    
    await run_cmd(tube, "iwinfo wlan0 info 2>/dev/null | head -10 || echo 'wlan0 not ready'", "Tube AP status")
    
    print("\nRestarting Edge Gateway STA wifi...", flush=True)
    await run_cmd(edge, "wifi down; sleep 2; wifi up", "Edge wifi restart")
    
    print("Waiting 20s for STA to associate...", flush=True)
    await asyncio.sleep(20)

    # ========================================
    # STEP 5: Verify association and link quality
    # ========================================
    print("\n" + "=" * 70)
    print("  STEP 5: Verify HaLow link")
    print("=" * 70, flush=True)
    
    # Edge side
    await run_cmd(edge, "iwinfo wlan0 info", "Edge iwinfo")
    await run_cmd(edge, "iwinfo wlan0 assoclist", "Edge assoclist")
    await run_cmd(edge, "ip addr show wlan0", "Edge wlan0 IP")
    await run_cmd(edge, "morse_cli -i wlan0 channel", "Edge morse channel")
    await run_cmd(edge, "iwinfo wlan0 txpower", "Edge TX power")
    
    # Tube side
    await run_cmd(tube, "iwinfo wlan0 info", "Tube iwinfo")
    await run_cmd(tube, "iwinfo wlan0 assoclist", "Tube assoclist") 
    await run_cmd(tube, "morse_cli -i wlan0 channel", "Tube morse channel")
    await run_cmd(tube, "iwinfo wlan0 txpower", "Tube TX power")
    
    # Ping test
    print("\n--- Ping test from Edge to Tube via HaLow ---", flush=True)
    await run_cmd(edge, "ping -c 5 -W 3 192.168.1.103", "Edge ping Tube")
    
    print("\n--- Ping test from Tube to Edge via HaLow ---", flush=True)
    await run_cmd(tube, "ping -c 5 -W 3 192.168.1.196", "Tube ping Edge")

    edge.close()
    tube.close()

    print("\n" + "=" * 70)
    print("  CONFIGURATION COMPLETE")
    print("=" * 70, flush=True)

asyncio.run(main())
