#!/usr/bin/env python3
"""
Fix Edge HaLow networking:
1. Set static IP 192.168.1.196 on wwan (avoids DHCP issues over lossy link)
2. Add firewall/routing rules
3. Test connectivity
"""
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
            for line in result.split('\n')[:15]:
                print(f"    {line}", flush=True)
        return result
    except Exception as e:
        if label:
            print(f"    ERROR: {e}", flush=True)
        return f"ERROR: {e}"

async def main():
    # ── STEP 1: Fix Edge wwan network with static IP ──
    print("="*70)
    print("  STEP 1: Fix Edge wwan network (static IP)")
    print("="*70, flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(EDGE["host"], username=EDGE["username"],
                       password=EDGE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        # Set static IP on wwan interface
        cmds = [
            # Configure wwan with static IP
            "uci set network.wwan.proto='static'",
            "uci set network.wwan.ipaddr='192.168.1.196'",
            "uci set network.wwan.netmask='255.255.255.0'",
            "uci set network.wwan.gateway='192.168.1.1'",
            "uci set network.wwan.dns='192.168.1.1'",
            "uci set network.wwan.metric='600'",
            "uci commit network",
        ]
        for cmd in cmds:
            await run_cmd(conn, cmd)
        
        await run_cmd(conn, "uci show network.wwan", "wwan config after fix")
        
        # Restart network
        print("\n  Restarting network...", flush=True)
        await run_cmd(conn, "/etc/init.d/network restart", "network restart", timeout=20)
        await asyncio.sleep(5)
        
        # Check wlan0 IP
        await run_cmd(conn, "ip addr show wlan0", "wlan0 IP")
        await run_cmd(conn, "ip route show", "routes")
    
    # Wait for IP to propagate
    await asyncio.sleep(3)
    
    # ── STEP 2: Test HaLow connectivity from Tube ──
    print("\n" + "="*70)
    print("  STEP 2: Test HaLow connectivity")
    print("="*70, flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        # Ping Edge over HaLow
        result = await run_cmd(conn, "ping -c 5 -W 5 192.168.1.196", "Ping Edge .196 from Tube", timeout=35)
        
        halow_works = "bytes from" in result
        if halow_works:
            print("\n  ✓ HaLow L3 connectivity works!", flush=True)
        else:
            print("\n  ✗ HaLow ping failed. Trying ARP...", flush=True)
            await run_cmd(conn, "arping -I br-ahwlan -c 3 192.168.1.196", "ARP ping Edge", timeout=15)
            await run_cmd(conn, "ip neigh show | grep 196", "ARP table for .196")
    
    # ── STEP 3: Test from Edge over HaLow ──
    print("\n" + "="*70)
    print("  STEP 3: Test from Edge → Tube over HaLow")
    print("="*70, flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(EDGE["host"], username=EDGE["username"],
                       password=EDGE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        # Check wlan0 has IP now
        wlan_ip = await run_cmd(conn, "ip addr show wlan0 | grep 'inet '", "wlan0 IPv4")
        
        if "192.168.1.196" not in wlan_ip:
            print("  ⚠ IP not on wlan0 yet. Trying ifup wwan...", flush=True)
            await run_cmd(conn, "ifup wwan", "ifup wwan", timeout=10)
            await asyncio.sleep(5)
            await run_cmd(conn, "ip addr show wlan0 | grep 'inet '", "wlan0 IPv4 after ifup")
        
        # Ping Tube from Edge via HaLow
        await run_cmd(conn, "ping -c 5 -W 5 -I wlan0 192.168.1.103", "Ping Tube from Edge via wlan0", timeout=35)
        
        # Ping WAN router
        await run_cmd(conn, "ping -c 3 -W 5 -I wlan0 192.168.1.1", "Ping WAN from Edge via wlan0", timeout=25)
        
        # Check current link quality
        await run_cmd(conn, "iwinfo wlan0 info | grep -E 'Signal|Bit Rate|Channel'", "Current link quality")
        
    # ── STEP 4: Verify link from AP side ──
    print("\n" + "="*70)
    print("  STEP 4: Verify link from AP side")
    print("="*70, flush=True)
    
    conn = await asyncio.wait_for(
        asyncssh.connect(TUBE["host"], username=TUBE["username"],
                       password=TUBE["password"], known_hosts=None, login_timeout=15),
        timeout=20
    )
    async with conn:
        await run_cmd(conn, "iwinfo wlan0 assoclist", "AP assoclist (current rates)")
        await run_cmd(conn, "morse_cli -i wlan0 channel", "AP morse_cli channel")

    print("\n" + "="*70)
    print("  NETWORKING FIX COMPLETE")
    print("="*70, flush=True)

asyncio.run(main())
