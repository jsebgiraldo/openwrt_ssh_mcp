#!/usr/bin/env python3
"""Check routing on both devices to understand traffic paths."""
import asyncio
import asyncssh

EDGE_ETH = {"host": "192.168.1.111", "user": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root"}

async def ssh_run(dev, cmd, timeout=20):
    async with asyncssh.connect(
        dev["host"], port=22, username=dev["user"],
        password=dev["password"], known_hosts=None, login_timeout=10
    ) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()

async def main():
    print("=" * 60)
    print("  TUBE-AHM (AP)")
    print("=" * 60)
    
    cmds_tube = [
        ("Bridge", "brctl show 2>/dev/null"),
        ("br-lan IP", "ifconfig br-lan 2>/dev/null | head -3"),
        ("wlan0 IP", "ifconfig wlan0 2>/dev/null | head -3"),
        ("Routes", "ip route show"),
        ("ARP for Edge", "ip neigh show | grep -E '196|111|de:87'"),
        ("Route to .196", "ip route get 192.168.1.196 2>/dev/null"),
    ]
    
    for label, cmd in cmds_tube:
        try:
            out = await ssh_run(TUBE, cmd)
            print(f"\n[{label}]\n{out}")
        except Exception as e:
            print(f"\n[{label}] ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("  EDGE GATEWAY (STA)")
    print("=" * 60)
    
    cmds_edge = [
        ("Routes", "ip route show"),
        ("ARP for Tube", "ip neigh show | grep 103"),
        ("Route to .103", "ip route get 192.168.1.103"),
        ("Interfaces", "ip -4 addr show | grep -E 'inet |^[0-9]'"),
    ]
    
    for label, cmd in cmds_edge:
        try:
            out = await ssh_run(EDGE_ETH, cmd)
            print(f"\n[{label}]\n{out}")
        except Exception as e:
            print(f"\n[{label}] ERROR: {e}")

asyncio.run(main())
