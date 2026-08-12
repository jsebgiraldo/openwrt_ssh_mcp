#!/usr/bin/env python3
"""
Configuración correcta del enlace HaLow para tesis UNAL.

Topología:
  [WAN Router 192.168.1.1] --eth--> [Edge Gateway 192.168.1.111 (AP HaLow)]
                                           ~~~~ HaLow 802.11ah ~~~~
                                     [Tube-AHM 192.168.1.103 (STA bridge)]

Edge Gateway = AP (provee conectividad HaLow)
Tube-AHM     = STA bridge (obtiene WAN a través del enlace HaLow)
"""

import asyncio
import asyncssh
import time

# === DISPOSITIVOS ===
EDGE = {"host": "192.168.1.111", "user": "root", "password": "root", "name": "EDGE_GATEWAY (AP)"}
ROUTER = {"host": "192.168.1.103", "user": "root", "password": "root", "name": "TUBE-AHM (STA bridge)"}

# === CONFIGURACIÓN HALOW ===
SSID = "UNAL-HaLow-Tesis"
KEY = "banano2026"
CHANNEL = "36"          # 919.500 MHz - dentro del rango de ambos dispositivos
S1G_CHANBW = "4"        # 4 MHz = HT20, soportado por ambos BCFs
COUNTRY = "US"
ENCRYPTION = "sae"      # WPA3


async def ssh_exec(device, cmd):
    """Ejecutar comando SSH y retornar salida."""
    try:
        async with asyncssh.connect(
            device["host"], port=22, username=device["user"],
            password=device["password"], known_hosts=None
        ) as conn:
            result = await conn.run(cmd, timeout=30)
            return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


async def ssh_exec_multi(device, cmds):
    """Ejecutar múltiples comandos en una sesión SSH."""
    results = []
    try:
        async with asyncssh.connect(
            device["host"], port=22, username=device["user"],
            password=device["password"], known_hosts=None
        ) as conn:
            for cmd in cmds:
                result = await conn.run(cmd, timeout=30)
                out = result.stdout.strip()
                results.append((cmd, out, result.returncode))
                print(f"  [{device['name']}] {cmd}")
                if out:
                    for line in out.split('\n')[:3]:
                        print(f"    → {line}")
    except Exception as e:
        print(f"  ERROR connecting to {device['name']}: {e}")
        results.append(("connection", str(e), -1))
    return results


async def configure_edge_as_ap():
    """Configurar Edge Gateway como AP HaLow."""
    print("\n" + "=" * 60)
    print("  PASO 1: Configurar Edge Gateway como AP")
    print("=" * 60)

    cmds = [
        # Limpiar interfaces extra si existen
        "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",
        "uci delete wireless.sta_radio0 2>/dev/null; echo ok",

        # Configurar radio
        f"uci set wireless.radio0.channel='{CHANNEL}'",
        f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
        f"uci set wireless.radio0.country='{COUNTRY}'",
        "uci set wireless.radio0.disabled='0'",

        # Configurar interfaz como AP
        "uci set wireless.default_radio0.mode='ap'",
        f"uci set wireless.default_radio0.ssid='{SSID}'",
        f"uci set wireless.default_radio0.encryption='{ENCRYPTION}'",
        f"uci set wireless.default_radio0.key='{KEY}'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='ahwlan'",
        "uci set wireless.default_radio0.wds='1'",
        # Eliminar mesh_id si existía
        "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
        "uci delete wireless.default_radio0.ifname 2>/dev/null; echo ok",

        # Hostname
        "uci set system.@system[0].hostname='edge-gateway'",

        # Commit
        "uci commit wireless",
        "uci commit system",

        # Reiniciar wifi
        "wifi down; sleep 2; wifi up",
    ]

    results = await ssh_exec_multi(EDGE, cmds)
    print("\n  ⏳ Esperando 15s a que el AP levante...")
    await asyncio.sleep(15)

    # Verificar
    print("\n  --- Verificación AP ---")
    info = await ssh_exec(EDGE, "iwinfo wlan0 info 2>/dev/null || echo 'wlan0 no disponible'")
    print(f"  {info}")

    operstate = await ssh_exec(EDGE, "cat /sys/class/net/wlan0/operstate 2>/dev/null")
    print(f"  operstate: {operstate}")

    return "Master" in info or "AP" in info


async def configure_router_as_sta():
    """Configurar Tube-AHM como STA bridge."""
    print("\n" + "=" * 60)
    print("  PASO 2: Configurar Tube-AHM como STA bridge")
    print("=" * 60)

    cmds = [
        # Eliminar interfaces extra (mesh, meshap)
        "uci delete wireless.meshap_radio0 2>/dev/null; echo ok",

        # Configurar radio
        f"uci set wireless.radio0.channel='{CHANNEL}'",
        f"uci set wireless.radio0.s1g_chanbw='{S1G_CHANBW}'",
        f"uci set wireless.radio0.country='{COUNTRY}'",
        "uci set wireless.radio0.disabled='0'",

        # Configurar interfaz como STA (cliente)
        "uci set wireless.default_radio0.mode='sta'",
        f"uci set wireless.default_radio0.ssid='{SSID}'",
        f"uci set wireless.default_radio0.encryption='{ENCRYPTION}'",
        f"uci set wireless.default_radio0.key='{KEY}'",
        "uci set wireless.default_radio0.device='radio0'",
        "uci set wireless.default_radio0.network='ahwlan'",
        "uci set wireless.default_radio0.wds='1'",
        # Eliminar mesh settings
        "uci delete wireless.default_radio0.mesh_id 2>/dev/null; echo ok",
        "uci delete wireless.default_radio0.ifname 2>/dev/null; echo ok",
        "uci delete wireless.default_radio0.beacon_int 2>/dev/null; echo ok",

        # Hostname
        "uci set system.@system[0].hostname='halow-router'",

        # Commit
        "uci commit wireless",
        "uci commit system",

        # Reiniciar wifi
        "wifi down; sleep 2; wifi up",
    ]

    results = await ssh_exec_multi(ROUTER, cmds)
    print("\n  ⏳ Esperando 20s a que el STA asocie...")
    await asyncio.sleep(20)

    # Verificar
    print("\n  --- Verificación STA ---")
    info = await ssh_exec(ROUTER, "iwinfo wlan0 info 2>/dev/null || echo 'wlan0 no disponible'")
    print(f"  {info}")

    operstate = await ssh_exec(ROUTER, "cat /sys/class/net/wlan0/operstate 2>/dev/null")
    print(f"  operstate: {operstate}")

    link = await ssh_exec(ROUTER, "iw dev wlan0 link 2>/dev/null")
    print(f"  iw link: {link}")

    return "up" in operstate


async def verify_link():
    """Verificar el enlace HaLow completo."""
    print("\n" + "=" * 60)
    print("  PASO 3: Verificación del enlace")
    print("=" * 60)

    # Verificar que el AP ve la estación
    print("\n  --- Edge AP: estaciones conectadas ---")
    stations = await ssh_exec(EDGE, "iwinfo wlan0 assoclist 2>/dev/null")
    print(f"  {stations if stations else '(ninguna estación)'}")

    # Verificar que el STA está asociado
    print("\n  --- Tube-AHM STA: estado de conexión ---")
    link = await ssh_exec(ROUTER, "iw dev wlan0 link 2>/dev/null")
    print(f"  {link}")

    # Estado del bridge
    print("\n  --- Tube-AHM: bridge status ---")
    bridge = await ssh_exec(ROUTER, "brctl show br-ahwlan 2>/dev/null || bridge link show 2>/dev/null")
    print(f"  {bridge}")

    # IPs
    print("\n  --- IPs ---")
    edge_ip = await ssh_exec(EDGE, "ip addr show br-ahwlan 2>/dev/null | grep inet")
    print(f"  Edge br-ahwlan: {edge_ip}")

    router_ip = await ssh_exec(ROUTER, "ip addr show br-ahwlan 2>/dev/null | grep inet")
    print(f"  Router br-ahwlan: {router_ip}")

    # Ping entre dispositivos por HaLow (si hay IPs en br-ahwlan)
    print("\n  --- Ping Edge → WAN Router ---")
    ping_wan = await ssh_exec(EDGE, "ping -c 3 -W 2 192.168.1.1 2>/dev/null")
    print(f"  {ping_wan}")

    print("\n  --- Ping Tube-AHM → WAN Router (a través del enlace HaLow) ---")
    ping_wan2 = await ssh_exec(ROUTER, "ping -c 3 -W 2 192.168.1.1 2>/dev/null")
    print(f"  {ping_wan2}")

    # Verificar si el Tube-AHM llega al Edge
    print("\n  --- Ping Tube-AHM → Edge ---")
    ping_edge = await ssh_exec(ROUTER, "ping -c 3 -W 2 192.168.1.111 2>/dev/null")
    print(f"  {ping_edge}")

    # dmesg reciente
    print("\n  --- Edge dmesg reciente (morse) ---")
    dmesg_e = await ssh_exec(EDGE, "dmesg | grep -i 'morse\\|wlan0\\|ahwlan' | tail -5")
    print(f"  {dmesg_e}")

    print("\n  --- Router dmesg reciente (morse) ---")
    dmesg_r = await ssh_exec(ROUTER, "dmesg | grep -i 'morse\\|wlan0\\|ahwlan' | tail -5")
    print(f"  {dmesg_r}")


async def main():
    print("=" * 60)
    print("  CONFIGURACIÓN ENLACE HALOW - TESIS UNAL")
    print("  Edge Gateway (192.168.1.111) = AP")
    print("  Tube-AHM     (192.168.1.103) = STA bridge")
    print(f"  SSID: {SSID} | Canal: {CHANNEL} | BW: {S1G_CHANBW} MHz | WPA3 SAE")
    print("=" * 60)

    # Paso 1: Edge como AP
    ap_ok = await configure_edge_as_ap()
    if not ap_ok:
        print("\n  ⚠️  AP no verificado, pero continuamos con STA...")

    # Paso 2: Router como STA
    sta_ok = await configure_router_as_sta()

    # Paso 3: Verificar enlace
    await verify_link()

    print("\n" + "=" * 60)
    if ap_ok and sta_ok:
        print("  ✅ Enlace HaLow configurado exitosamente")
    else:
        print("  ⚠️  Verificar enlace manualmente")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
