"""Script para verificar el estado de IPv6 en OpenWRT."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openwrt_ssh_mcp.ssh_client import ssh_client
from openwrt_ssh_mcp.tools import OpenWRTTools

async def check_ipv6():
    """Verifica la configuración de IPv6."""
    
    print("=" * 70)
    print("📋 VERIFICACIÓN DE IPv6 EN OPENWRT")
    print("=" * 70)
    
    await ssh_client.connect()
    tools = OpenWRTTools()
    
    # 1. Ver configuración de red actual
    print("\n🌐 1. CONFIGURACIÓN DE RED ACTUAL (UCI)")
    print("-" * 70)
    result = await tools.read_config("network")
    if result["success"]:
        config = result.get("config", "")
        # Filtrar líneas relacionadas con IPv6
        for line in config.split("\n"):
            if "ipv6" in line.lower() or "ip6" in line.lower() or line.startswith("network.wan") or line.startswith("network.lan"):
                print(line)
    
    # 2. Interfaces y direcciones IPv6
    print("\n📡 2. DIRECCIONES IPv6 ASIGNADAS")
    print("-" * 70)
    result = await ssh_client.execute("ip -6 addr show")
    if result["success"]:
        print(result["stdout"])
    
    # 3. Rutas IPv6
    print("\n🛣️ 3. RUTAS IPv6")
    print("-" * 70)
    result = await ssh_client.execute("ip -6 route show")
    if result["success"]:
        routes = result["stdout"].strip()
        if routes:
            print(routes)
        else:
            print("⚠️ No hay rutas IPv6 configuradas")
    
    # 4. Estado de DHCPv6 y SLAAC
    print("\n🔧 4. ESTADO DE SERVICIOS IPv6")
    print("-" * 70)
    result = await ssh_client.execute("ps | grep -E 'odhcp|dhcp6'")
    if result["success"]:
        output = result["stdout"].strip()
        if output:
            print("Servicios DHCP activos:")
            print(output)
        else:
            print("⚠️ No se detectaron procesos DHCPv6")
    
    # 5. Configuración de firewall para IPv6
    print("\n🔒 5. REGLAS DE FIREWALL IPv6")
    print("-" * 70)
    result = await ssh_client.execute("ip6tables -L -n | head -20")
    if result["success"]:
        print(result["stdout"])
    
    # 6. Conectividad IPv6 externa
    print("\n🌍 6. PRUEBA DE CONECTIVIDAD IPv6")
    print("-" * 70)
    result = await ssh_client.execute("ping6 -c 3 2001:4860:4860::8888")
    if result["success"]:
        if "0% packet loss" in result["stdout"]:
            print("✅ Conectividad IPv6 exitosa a Google DNS")
        else:
            print("⚠️ Problemas de conectividad IPv6")
        print(result["stdout"][:300])
    else:
        print("❌ Sin conectividad IPv6 externa")
        print(result["stderr"][:200])
    
    # 7. Información del ISP
    print("\n📶 7. PREFIJO IPv6 DELEGADO (del ISP)")
    print("-" * 70)
    result = await ssh_client.execute("ubus call network.interface.wan6 status 2>/dev/null")
    if result["success"]:
        print(result["stdout"][:500])
    else:
        print("⚠️ Interfaz wan6 no disponible")
    
    await ssh_client.disconnect()
    
    print("\n" + "=" * 70)
    print("✅ VERIFICACIÓN COMPLETADA")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(check_ipv6())
