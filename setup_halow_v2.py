#!/usr/bin/env python3
"""
Configuración CORRECTA del enlace HaLow para tesis UNAL.

Topología (según usuario y config original de fábrica):
  [WAN Router 192.168.1.1] --eth--> [Edge Gateway 192.168.1.111 (STA)]
                                           ~~~~ HaLow 802.11ah ~~~~
                                     [Tube-AHM 192.168.1.103 (AP bridge)]

Tube-AHM  = AP  (provee red HaLow, bridge para obtener WAN)
Edge      = STA (se conecta al Tube-AHM a través de HaLow)
"""

import asyncio
import asyncssh

# === DISPOSITIVOS ===
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root"}
TUBE = {"host": "192.168.1.103", "user": "root", "password": "root"}

# === CONFIGURACIÓN HALOW ===
SSID = "UNAL-HaLow-Tesis"
KEY = "banano2026"
# Ch=48 y bw=8 funcionaban en el Tube-AHM original (HT40)
CHANNEL = "48"
S1G_CHANBW = "8"
COUNTRY = "US"
ENCRYPTION = "sae"


async def ssh_exec(device, cmd, timeout=30):
    async with asyncssh.connect(
        device["host"], 22, username=device["user"],
        password=device["password"], known_hosts=None
    ) as conn:
        result = await conn.run(cmd, timeout=timeout)
        return result.stdout.strip()


async def ssh_multi(device, cmds, label=""):
    async with asyncssh.connect(
        device["host"], 22, username=device["user"],
        password=device["password"], known_hosts=None
    ) as conn:
        for cmd in cmds:
            r = await conn.run(cmd, timeout=30)
            out = r.stdout.strip()
            print(f"  [{label}] {cmd}")
            if out:
                for line in out.split('\n')[:2]:
                    print(f"    -> {line}")


async def configure_tube_as_ap():
    """Paso 1: Tube-AHM como AP puro (sin mesh)."""
    print("\n" + "=" * 60)
    print("  PASO 1: Tube-AHM (192.168.1.103) como AP")
    print("=" * 60)

    cmds = [
        # Eliminar interfaces extra
        "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",
        "uci delete wireless.sta_radio0 2>/dev/null; echo ok",

        # Radio: ch=48, bw=8 (configuración que funcionaba)
        f"uci set wireless.radio0.channel='{CHANNEL}'",
        f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
        f"uci set wireless.radio0.country='{COUNTRY}'",
        "uci set wireless.radio0.disabled='0'",

        # Interfaz como AP (no mesh)
        "uci set wireless.default_radio0.mode='ap'",
        f"uci set wireless.default_radio0.ssid='{SSID}'",
        f"uci set wireless.default_radio0.encryption='{ENCRYPTION}'",
        f"uci set wireless.default_radio0.key='{KEY}'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='ahwlan'",
        "uci set wireless.default_radio0.wds='1'",
        # Limpiar configuración de mesh
        "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
        "uci delete wireless.default_radio0.ifname 2>/dev/null; echo ok",
        "uci delete wireless.default_radio0.beacon_int 2>/dev/null; echo ok",

        # Hostname
        "uci set system.@system[0].hostname='halow-router'",

        # Commit todo
        "uci commit wireless",
        "uci commit system",

        # Mostrar config
        "cat /etc/config/wireless",
    ]

    await ssh_multi(TUBE, cmds, "TUBE-AP")

    # Reboot para limpiar estado del driver Morse
    print("\n  Reiniciando Tube-AHM...")
    try:
        await ssh_exec(TUBE, "reboot", timeout=5)
    except:
        pass

    print("  Esperando 70s para reboot...")
    await asyncio.sleep(70)

    # Reconectar
    for attempt in range(10):
        try:
            info = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null; echo '---'; cat /sys/class/net/wlan0/operstate 2>/dev/null")
            print(f"\n  Tube-AHM reconectado. Estado wifi:")
            print(f"  {info}")
            if "Master" in info or "AP" in info:
                return True
            break
        except:
            print(f"  Intento {attempt+1}/10 - esperando 10s...")
            await asyncio.sleep(10)

    # Puede que necesite más tiempo
    await asyncio.sleep(30)
    try:
        info = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null")
        print(f"\n  {info}")
        return "Master" in info
    except Exception as e:
        print(f"  Error: {e}")
        return False


async def configure_edge_as_sta():
    """Paso 2: Edge como STA conectándose al Tube-AHM AP."""
    print("\n" + "=" * 60)
    print("  PASO 2: Edge (192.168.1.111) como STA")
    print("=" * 60)

    cmds = [
        # Limpiar interfaces extra
        "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",
        "uci delete wireless.sta_radio0 2>/dev/null; echo ok",

        # Radio: auto channel (el STA seguirá al AP), bw=8
        "uci set wireless.radio0.channel='auto'",
        f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
        f"uci set wireless.radio0.country='{COUNTRY}'",
        "uci set wireless.radio0.disabled='0'",

        # Interfaz como STA
        "uci set wireless.default_radio0.mode='sta'",
        f"uci set wireless.default_radio0.ssid='{SSID}'",
        f"uci set wireless.default_radio0.encryption='{ENCRYPTION}'",
        f"uci set wireless.default_radio0.key='{KEY}'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='ahwlan'",
        "uci set wireless.default_radio0.wds='1'",
        # Limpiar mesh leftovers  
        "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
        "uci delete wireless.default_radio0.ifname 2>/dev/null; echo ok",
        "uci delete wireless.default_radio0.beacon_int 2>/dev/null; echo ok",

        # Hostname
        "uci set system.@system[0].hostname='edge-gateway'",

        # Commit
        "uci commit wireless",
        "uci commit system",

        # Mostrar config
        "cat /etc/config/wireless",
    ]

    await ssh_multi(EDGE, cmds, "EDGE-STA")

    # Reboot Edge también para limpiar estado del driver
    print("\n  Reiniciando Edge...")
    try:
        await ssh_exec(EDGE, "reboot", timeout=5)
    except:
        pass

    print("  Esperando 70s para reboot...")
    await asyncio.sleep(70)

    # Reconectar
    for attempt in range(10):
        try:
            info = await ssh_exec(EDGE, "iwinfo wlan0 info 2>/dev/null")
            operstate = await ssh_exec(EDGE, "cat /sys/class/net/wlan0/operstate 2>/dev/null")
            print(f"\n  Edge reconectado. operstate: {operstate}")
            print(f"  {info}")
            return operstate == "up"
        except:
            print(f"  Intento {attempt+1}/10 - esperando 10s...")
            await asyncio.sleep(10)

    return False


async def verify():
    """Paso 3: Verificar enlace."""
    print("\n" + "=" * 60)
    print("  PASO 3: Verificación del enlace HaLow")
    print("=" * 60)

    # Tube-AHM AP
    print("\n--- Tube-AHM AP ---")
    info = await ssh_exec(TUBE, "iwinfo wlan0 info 2>/dev/null")
    print(info)
    assoc = await ssh_exec(TUBE, "iwinfo wlan0 assoclist 2>/dev/null")
    print(f"\nEstaciones conectadas: {assoc if assoc else '(ninguna)'}")

    # Edge STA
    print("\n--- Edge STA ---")
    info = await ssh_exec(EDGE, "iwinfo wlan0 info 2>/dev/null")
    print(info)
    link = await ssh_exec(EDGE, "iw dev wlan0 link 2>/dev/null")
    print(f"\niw link: {link}")
    operstate = await ssh_exec(EDGE, "cat /sys/class/net/wlan0/operstate 2>/dev/null")
    print(f"operstate: {operstate}")

    # Pings
    print("\n--- Pings ---")
    p1 = await ssh_exec(EDGE, "ping -c 3 -W 2 192.168.1.103")
    print(f"Edge -> Tube-AHM: {p1.split(chr(10))[-1] if p1 else 'FAIL'}")

    p2 = await ssh_exec(TUBE, "ping -c 3 -W 2 192.168.1.111")
    print(f"Tube-AHM -> Edge: {p2.split(chr(10))[-1] if p2 else 'FAIL'}")

    p3 = await ssh_exec(TUBE, "ping -c 3 -W 2 192.168.1.1")
    print(f"Tube-AHM -> WAN: {p3.split(chr(10))[-1] if p3 else 'FAIL'}")

    # Logs de asociación
    print("\n--- Logs wpa_supplicant (Edge) ---")
    logs = await ssh_exec(EDGE, "logread | grep -iE 'wpa_supplicant|assoc|connect|CTRL-EVENT' | tail -10")
    print(logs)

    connected = operstate == "up" or "Connected" in link
    return connected


async def main():
    print("=" * 60)
    print("  ENLACE HALOW - TOPOLOGÍA CORRECTA")
    print("  Tube-AHM (192.168.1.103) = AP")
    print("  Edge     (192.168.1.111) = STA")
    print(f"  SSID: {SSID} | Ch: {CHANNEL} | BW: {S1G_CHANBW} MHz | WPA3")
    print("=" * 60)

    # Paso 1: Tube-AHM como AP
    ap_ok = await configure_tube_as_ap()
    if ap_ok:
        print("\n  ++ Tube-AHM AP verificado!")
    else:
        print("\n  !! AP no verificado, continuando...")

    # Paso 2: Edge como STA
    sta_ok = await configure_edge_as_sta()

    # Esperar un poco más para la asociación
    print("\n  Esperando 30s para asociación...")
    await asyncio.sleep(30)

    # Paso 3: Verificar
    connected = await verify()

    print("\n" + "=" * 60)
    if connected:
        print("  ++ ENLACE HALOW ESTABLECIDO!")
    else:
        print("  !! Enlace no establecido - revisar logs")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
