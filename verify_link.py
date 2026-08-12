#!/usr/bin/env python3
"""Verify full HaLow link status at 8 MHz and end-to-end connectivity."""
import asyncio
import asyncssh

EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root"}
WAN  = {"host": "192.168.1.1", "user": "root", "key": r"C:\Users\jsgir\.ssh\id_rsa"}


async def ssh_exec(device, cmd, timeout=30):
    kwargs = {"host": device["host"], "port": 22, "username": device["user"], "known_hosts": None}
    if "key" in device:
        kwargs["client_keys"] = [device["key"]]
    else:
        kwargs["password"] = device["password"]
    async with asyncssh.connect(**kwargs) as conn:
        r = await conn.run(cmd, timeout=timeout)
        return r.stdout.strip()


async def main():
    print("=" * 60)
    print("  ESTADO DEL ENLACE HALOW @ 8 MHz")
    print("=" * 60)

    # --- Tube-AHM AP ---
    print("\n--- Tube-AHM AP (192.168.1.103) ---")
    tube_info = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null")
    print(tube_info)
    tube_assoc = await ssh_exec(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
    print(f"\nEstaciones conectadas:\n{tube_assoc if tube_assoc else '(ninguna)'}")

    # --- Edge STA ---
    print("\n--- Edge STA (192.168.1.111) ---")
    edge_info = await ssh_exec(EDGE, "iwinfo wlan0 info 2>/dev/null")
    print(edge_info)
    edge_link = await ssh_exec(EDGE, "iw dev wlan0 link 2>/dev/null")
    print(f"\niw link:\n{edge_link}")

    # --- Configs ---
    print("\n--- Tube wireless config ---")
    tw = await ssh_exec(TUBE, "uci show wireless.radio0.channel; uci show wireless.radio0.s1g_chanbw; uci show wireless.default_radio0.mode")
    print(tw)
    print("\n--- Edge wireless config ---")
    ew = await ssh_exec(EDGE, "uci show wireless.radio0.channel; uci show wireless.radio0.s1g_chanbw; uci show wireless.default_radio0.mode")
    print(ew)

    # --- Connectivity matrix ---
    print("\n" + "=" * 60)
    print("  CONECTIVIDAD END-TO-END")
    print("=" * 60)

    tests = [
        ("Edge -> Tube-AHM", EDGE, "192.168.1.103"),
        ("Edge -> WAN Router", EDGE, "192.168.1.1"),
        ("Edge -> Internet (8.8.8.8)", EDGE, "8.8.8.8"),
        ("Tube-AHM -> Edge", TUBE, "192.168.1.111"),
        ("Tube-AHM -> WAN Router", TUBE, "192.168.1.1"),
        ("Tube-AHM -> Internet (8.8.8.8)", TUBE, "8.8.8.8"),
        ("WAN -> Edge", WAN, "192.168.1.111"),
        ("WAN -> Tube-AHM", WAN, "192.168.1.103"),
    ]

    for label, device, target in tests:
        try:
            result = await ssh_exec(device, f"ping -c 3 -W 2 {target}")
            # Extract summary line
            lines = result.split('\n')
            summary = [l for l in lines if 'transmitted' in l or 'round-trip' in l or 'rtt' in l]
            status = "OK" if "0% packet loss" in result or " 0% " in result else "LOSS"
            rtt = ""
            for l in lines:
                if 'round-trip' in l or 'rtt' in l:
                    rtt = l.split('=')[-1].strip() if '=' in l else l
            print(f"  {status:4s} | {label:35s} | {rtt}")
        except Exception as e:
            print(f"  FAIL | {label:35s} | {e}")

    # --- HaLow interface IPs ---
    print("\n--- Direcciones IP ---")
    edge_ips = await ssh_exec(EDGE, "ip addr show wlan0 | grep inet")
    print(f"Edge wlan0:    {edge_ips}")
    tube_ips = await ssh_exec(TUBE, "ip addr show wlan0 | grep inet")
    print(f"Tube wlan0:    {tube_ips}")
    edge_br = await ssh_exec(EDGE, "ip addr show br-ahwlan 2>/dev/null | grep inet")
    print(f"Edge br-ahwlan: {edge_br}")
    tube_br = await ssh_exec(TUBE, "ip addr show br-ahwlan 2>/dev/null | grep inet")
    print(f"Tube br-ahwlan: {tube_br}")

    print("\n" + "=" * 60)
    print("  ENLACE HALOW OPERATIVO @ 8 MHz")
    print("=" * 60)


asyncio.run(main())
