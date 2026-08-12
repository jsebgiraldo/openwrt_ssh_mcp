#!/usr/bin/env python3
"""Check iperf3 availability on all devices."""
import asyncio, asyncssh

DEVICES = [
    {"host": "192.168.1.111", "user": "root", "password": "root", "name": "Edge"},
    {"host": "192.168.1.103", "user": "root", "password": "root", "name": "Tube-AHM"},
    {"host": "192.168.1.1", "user": "root", "key": r"C:\Users\jsgir\.ssh\id_rsa", "name": "WAN"},
]

async def check(dev):
    kw = {"host": dev["host"], "port": 22, "username": dev["user"], "known_hosts": None}
    if "key" in dev:
        kw["client_keys"] = [dev["key"]]
    else:
        kw["password"] = dev["password"]
    async with asyncssh.connect(**kw) as c:
        r1 = await c.run("which iperf3 2>/dev/null; iperf3 --version 2>/dev/null | head -1", timeout=10)
        r2 = await c.run("which iperf 2>/dev/null; iperf --version 2>&1 | head -1", timeout=10)
        r3 = await c.run("which nuttcp nc netcat 2>/dev/null", timeout=10)
        r4 = await c.run("opkg list-installed | grep -iE 'iperf|nuttcp|netcat'", timeout=10)
        print(f"\n--- {dev['name']} ({dev['host']}) ---")
        print(f"  iperf3: {r1.stdout.strip() or 'NO'}")
        print(f"  iperf:  {r2.stdout.strip() or 'NO'}")
        print(f"  otros:  {r3.stdout.strip() or 'NO'}")
        print(f"  pkgs:   {r4.stdout.strip() or '(ninguno)'}")

async def main():
    for d in DEVICES:
        await check(d)

asyncio.run(main())
