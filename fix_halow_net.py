#!/usr/bin/env python3
"""
Fix HaLow networking on Edge and investigate signal asymmetry.
"""
import asyncio, asyncssh

TUBE = {"host": "192.168.1.103", "username": "root", "password": "root"}
EDGE = {"host": "192.168.1.111", "username": "root", "password": "root"}

async def run_cmd(conn, cmd, label=None, timeout=15):
    if label:
        print(f"\n--- {label} ---", flush=True)
    try:
        r = await asyncio.wait_for(conn.run(cmd, timeout=timeout), timeout=timeout+5)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out or err or "(empty)"
        print(result, flush=True)
        return result
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return f"ERROR: {e}"

async def main():
    # ── EDGE: Fix networking ──
    print("="*70)
    print("  EDGE: Check and fix HaLow networking")
    print("="*70, flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(EDGE["host"], username=EDGE["username"],
                       password=EDGE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        # Check current network config for wwan
        await run_cmd(conn, "uci show network | grep -E 'wwan|ahwlan'", "Edge network config (wwan)")
        await run_cmd(conn, "ip addr show wlan0", "Edge wlan0 IP")
        await run_cmd(conn, "ip route show", "Edge routes")
        
        # Check if wwan interface exists in network config
        wwan = await run_cmd(conn, "uci get network.wwan 2>/dev/null || echo 'NOT_FOUND'", "wwan exists?")
        
        if "NOT_FOUND" in wwan:
            print("\n⚠ wwan interface not configured! Creating it...", flush=True)
            cmds = [
                "uci set network.wwan=interface",
                "uci set network.wwan.proto='dhcp'",
                "uci set network.wwan.metric='600'",
                "uci commit network",
                "/etc/init.d/network restart",
            ]
            for c in cmds:
                await run_cmd(conn, c)
            await asyncio.sleep(5)
        else:
            # Check proto
            proto = await run_cmd(conn, "uci get network.wwan.proto 2>/dev/null", "wwan proto")
            if "dhcp" not in proto:
                print("  Fixing wwan to use DHCP...", flush=True)
                await run_cmd(conn, "uci set network.wwan.proto='dhcp'; uci commit network; /etc/init.d/network restart")
                await asyncio.sleep(5)
        
        # Check wlan0 IP again
        await run_cmd(conn, "ip addr show wlan0", "Edge wlan0 IP after fix")
        await run_cmd(conn, "ip route show", "Edge routes after fix")
        
        # Check if DHCP gave us an IP
        await run_cmd(conn, "cat /tmp/dhcp.leases 2>/dev/null || echo 'no leases'", "DHCP leases")
        
        # ── Investigate signal asymmetry ──
        print("\n" + "="*70)
        print("  EDGE: Signal & TX diagnostics")
        print("="*70, flush=True)
        
        # Check actual TX power
        await run_cmd(conn, "iwinfo wlan0 txpower", "Edge TX power setting")
        
        # morse module params related to TX
        await run_cmd(conn, """for p in tx_max_power_mbm fixed_bw fixed_mcs enable_fixed_rate enable_rts_8mhz enable_sgi_rc enable_trav_pilot max_rate_tries mcs_mask; do
    val=$(cat /sys/module/morse/parameters/$p 2>/dev/null || cat /sys/module/morse_sdio/parameters/$p 2>/dev/null || echo 'N/A')
    echo "$p: $val"
done""", "Morse TX-related module params")
        
        # Check TX stats
        await run_cmd(conn, "iw dev wlan0 station dump", "Edge iw station dump (full)")
        
        # Check antenna info
        await run_cmd(conn, "iw phy phy0 info 2>/dev/null | grep -iE 'antenna|chain|stream|capability|band|freq' | head -20", "PHY antenna/capabilities")
        
        # dmesg TX power initialization
        await run_cmd(conn, "dmesg | grep -iE 'tx.*power|power.*limit|tx_max|eirp|antenna|gain' | tail -15", "dmesg TX power/antenna")
        
        # Check morse_cli for anything about TX
        await run_cmd(conn, "morse_cli -i wlan0 stats 2>&1 | grep -iE 'TX|power|MCS|bandwidth|rate' | head -30", "morse_cli TX stats")
        
        # Network interfaces and bridge
        await run_cmd(conn, "brctl show 2>/dev/null || bridge link show 2>/dev/null || echo 'no bridge'", "Bridge config")
    
    # ── TUBE: Check if Edge packets arrive ──
    print("\n" + "="*70)
    print("  TUBE: AP-side diagnostics")
    print("="*70, flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        # Check bridge and routing
        await run_cmd(conn, "brctl show 2>/dev/null", "Tube bridge config")
        await run_cmd(conn, "ip addr show", "Tube IP addresses")
        await run_cmd(conn, "ip route show", "Tube routes")
        
        # Check ARP for Edge
        await run_cmd(conn, "ip neigh show", "Tube ARP/neighbor table")
        
        # Assoclist with current rates
        await run_cmd(conn, "iwinfo wlan0 assoclist", "Tube assoclist (latest)")
        
        # morse module tx params
        await run_cmd(conn, """for p in tx_max_power_mbm fixed_bw fixed_mcs enable_fixed_rate enable_rts_8mhz mcs_mask; do
    val=$(cat /sys/module/morse/parameters/$p 2>/dev/null || cat /sys/module/morse_sdio/parameters/$p 2>/dev/null || echo 'N/A')
    echo "$p: $val"
done""", "Tube Morse TX-related module params")
        
        # Try ping Edge .196
        await run_cmd(conn, "ping -c 3 -W 3 192.168.1.196", "Ping Edge .196 from Tube", timeout=20)

    print("\n" + "="*70)
    print("  DIAGNOSTICS COMPLETE")
    print("="*70, flush=True)

asyncio.run(main())
