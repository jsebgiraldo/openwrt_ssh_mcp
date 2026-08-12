#!/usr/bin/env python3
"""
HaLow link v3: Use ch=12 (908 MHz) / bw=2 (2 MHz) which Edge hardware supports.

Root cause of v2 failure:
  - Tube-AHM AP on ch=48 (926 MHz) operates at 4 MHz
  - Edge BCF (MM6108A1) rejects 926 MHz at 4 MHz: "HW does not permit channel"
  - Edge only worked at ch=12 (908 MHz) with 2 MHz (HT20)

Strategy: Use a channel+bandwidth that BOTH devices support.
"""

import asyncio
import asyncssh

EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root"}

SSID = "UNAL-HaLow-Tesis"
KEY = "banano2026"
ENCRYPTION = "sae"
COUNTRY = "US"

# Use ch/bw that Edge hardware accepts
CHANNEL = "12"
S1G_CHANBW = "2"   # 2 MHz - most compatible


async def ssh_exec(device, cmd, timeout=30):
    async with asyncssh.connect(
        device["host"], 22, username=device["user"],
        password=device["password"], known_hosts=None
    ) as conn:
        result = await conn.run(cmd, timeout=timeout)
        return result.stdout.strip()


async def configure_and_reboot(device, label, cmds):
    print(f"\n  Configurando {label}...")
    async with asyncssh.connect(
        device["host"], 22, username=device["user"],
        password=device["password"], known_hosts=None
    ) as conn:
        for cmd in cmds:
            r = await conn.run(cmd, timeout=30)
            out = r.stdout.strip()
            if out and 'config wifi' in out:
                # Show first few lines of wireless config
                lines = out.split('\n')
                for l in lines[:20]:
                    print(f"    {l}")
            elif out and len(out) < 200:
                print(f"    [{cmd[:40]}] -> {out}")

    # Reboot
    print(f"  Reiniciando {label}...")
    try:
        await ssh_exec(device, "reboot", timeout=5)
    except:
        pass

    print(f"  Esperando 80s para reboot de {label}...")
    await asyncio.sleep(80)

    # Reconnect
    for attempt in range(12):
        try:
            info = await ssh_exec(device, "iwinfo wlan0 info 2>/dev/null")
            state = await ssh_exec(device, "cat /sys/class/net/wlan0/operstate 2>/dev/null")
            print(f"\n  {label} reconectado! operstate={state}")
            for line in info.split('\n')[:6]:
                print(f"    {line}")
            return info, state
        except:
            print(f"  Intento {attempt+1}/12 - esperando 10s...")
            await asyncio.sleep(10)

    return "", "unknown"


async def main():
    print("=" * 60)
    print("  ENLACE HALOW v3 - Canal compatible para ambos")
    print(f"  Ch={CHANNEL} (908 MHz) | BW={S1G_CHANBW} MHz | WPA3 SAE")
    print("=" * 60)

    # === PASO 1: Tube-AHM como AP ===
    print("\n" + "-" * 50)
    print("  PASO 1: Tube-AHM AP en ch=12, bw=2")
    print("-" * 50)

    tube_cmds = [
        "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",
        "uci delete wireless.sta_radio0 2>/dev/null; echo ok",
        f"uci set wireless.radio0.channel='{CHANNEL}'",
        f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
        f"uci set wireless.radio0.country='{COUNTRY}'",
        "uci set wireless.radio0.disabled='0'",
        "uci set wireless.default_radio0.mode='ap'",
        f"uci set wireless.default_radio0.ssid='{SSID}'",
        f"uci set wireless.default_radio0.encryption='{ENCRYPTION}'",
        f"uci set wireless.default_radio0.key='{KEY}'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='ahwlan'",
        "uci set wireless.default_radio0.wds='1'",
        "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
        "uci commit wireless",
        "cat /etc/config/wireless",
    ]

    tube_info, tube_state = await configure_and_reboot(TUBE, "Tube-AHM", tube_cmds)

    if "Master" not in tube_info:
        print("\n  !! Tube-AHM AP no se levantó. Verificando logs...")
        try:
            logs = await ssh_exec(TUBE, "logread | grep -i 'netifd.*radio\\|hostapd\\|error\\|range\\|channel' | tail -15")
            print(logs)
        except:
            pass

        # If ch=12/bw=2 failed, try bw=4
        print("\n  Intentando con bw=4...")
        tube_cmds_v2 = [
            "uci set wireless.radio0.s1g_chanbw='4'",
            "uci commit wireless",
            "wifi down; sleep 2; wifi up",
        ]
        try:
            for cmd in tube_cmds_v2:
                await ssh_exec(TUBE, cmd, timeout=30)
            await asyncio.sleep(15)
            tube_info = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null")
            print(f"  bw=4 result: {'Master' in tube_info}")
            if "Master" not in tube_info:
                # Try auto channel
                print("  Intentando ch=auto...")
                await ssh_exec(TUBE, "uci set wireless.radio0.channel='auto'")
                await ssh_exec(TUBE, "uci commit wireless")
                await ssh_exec(TUBE, "wifi down; sleep 2; wifi up", timeout=30)
                await asyncio.sleep(20)
                tube_info = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null")
                print(f"  ch=auto result: {'Master' in tube_info}")
                for line in tube_info.split('\n')[:4]:
                    print(f"    {line}")
        except Exception as e:
            print(f"  Error: {e}")

    # Get the actual channel the AP ended up on
    actual_channel = "unknown"
    if tube_info:
        for line in tube_info.split('\n'):
            if 'Channel:' in line:
                # Extract channel number
                import re
                m = re.search(r'Channel:\s*(\d+)', line)
                if m:
                    actual_channel = m.group(1)
    print(f"\n  Tube-AHM AP actual channel: {actual_channel}")

    # === PASO 2: Edge como STA ===
    print("\n" + "-" * 50)
    print("  PASO 2: Edge STA (auto channel, same bw)")
    print("-" * 50)

    edge_cmds = [
        "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",
        "uci delete wireless.sta_radio0 2>/dev/null; echo ok",
        "uci set wireless.radio0.channel='auto'",
        f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
        f"uci set wireless.radio0.country='{COUNTRY}'",
        "uci set wireless.radio0.disabled='0'",
        "uci set wireless.default_radio0.mode='sta'",
        f"uci set wireless.default_radio0.ssid='{SSID}'",
        f"uci set wireless.default_radio0.encryption='{ENCRYPTION}'",
        f"uci set wireless.default_radio0.key='{KEY}'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='ahwlan'",
        "uci set wireless.default_radio0.wds='1'",
        "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
        "uci commit wireless",
        "cat /etc/config/wireless",
    ]

    edge_info, edge_state = await configure_and_reboot(EDGE, "Edge", edge_cmds)

    # Wait extra for STA association
    print("\n  Esperando 40s adicionales para asociación...")
    await asyncio.sleep(40)

    # === PASO 3: Verificación ===
    print("\n" + "=" * 60)
    print("  VERIFICACIÓN")
    print("=" * 60)

    # Edge status
    edge_info = await ssh_exec(EDGE, "iwinfo wlan0 info 2>/dev/null")
    edge_state = await ssh_exec(EDGE, "cat /sys/class/net/wlan0/operstate 2>/dev/null")
    edge_link = await ssh_exec(EDGE, "iw dev wlan0 link 2>/dev/null")
    print(f"\n--- Edge STA (operstate={edge_state}) ---")
    print(edge_info)
    print(f"iw link: {edge_link}")

    # wpa_cli_s1g status
    wpa_status = await ssh_exec(EDGE, "wpa_cli_s1g -i wlan0 status 2>/dev/null")
    print(f"\nwpa_cli_s1g status: {wpa_status}")

    # Tube AP
    tube_info = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null")
    tube_assoc = await ssh_exec(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
    print(f"\n--- Tube-AHM AP ---")
    print(tube_info)
    print(f"Estaciones: {tube_assoc if tube_assoc else '(ninguna)'}")

    # Scan from Edge
    print(f"\n--- Edge scan ---")
    scan = await ssh_exec(EDGE, "iwinfo wlan0 scan 2>/dev/null")
    if scan:
        for line in scan.split('\n'):
            if any(k in line for k in ['ESSID', 'Channel', 'Signal', 'Width', 'Primary']):
                print(f"  {line.strip()}")

    # Auth logs
    print(f"\n--- Edge wpa_supplicant logs (last 10) ---")
    logs = await ssh_exec(EDGE, "logread | grep -iE 'wpa_supplicant_s1g.*wlan0|morse.*channel|auth|CTRL-EVENT' | tail -10")
    print(logs)

    # Tube hostapd logs
    print(f"\n--- Tube hostapd_s1g logs ---")
    tlogs = await ssh_exec(TUBE, "logread | grep -iE 'hostapd_s1g|netifd.*radio|Operating|morse.*channel' | tail -15")
    print(tlogs)

    connected = edge_state == "up" or "Connected" in edge_link
    print("\n" + "=" * 60)
    if connected:
        print("  ++ ENLACE ESTABLECIDO!")
    else:
        print("  !! Enlace no establecido")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
