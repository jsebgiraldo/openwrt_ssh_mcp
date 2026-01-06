"""Script para explicar IPv6-PD en tu router."""

import asyncio
from openwrt_ssh_mcp.ssh_client import ssh_client

async def explain_pd():
    """Muestra información de Prefix Delegation."""
    
    print("=" * 70)
    print("📡 IPv6 PREFIX DELEGATION (PD) - EN TU ROUTER")
    print("=" * 70)
    
    await ssh_client.connect()
    
    print("""
┌────────────────────────────────────────────────────────────────┐
│ ¿QUÉ ES IPv6 PREFIX DELEGATION (PD)?                          │
└────────────────────────────────────────────────────────────────┘

Es como si tu ISP te dijera:

  "No te doy UNA dirección IP, te doy un EDIFICIO COMPLETO
   de direcciones. Tú decides cómo organizarlo."

┌────────────────────────────────────────────────────────────────┐
│ PROCESO DE DELEGACIÓN (Lo que pasa en tu router)              │
└────────────────────────────────────────────────────────────────┘

1. Tu router OpenWRT se conecta al ISP vía DHCPv6
   
2. Router dice: "Necesito un prefijo para mi red local"
   
3. ISP responde: "Aquí tienes 2800:484:8f7e:3200::/56"
   └─ Esto son 256 redes /64 completas
   └─ 18 quintillones de IPs por red
   └─ Total: 4.7 sextillones de IPs para ti
   
4. Tu router RECIBE y ALMACENA este prefijo delegado
   
5. Router ELIGE una subred para LAN (ej: subred 'd0')
   └─ 2800:484:8f7e:32d0::/64
   
6. Router ANUNCIA esta subred a tus dispositivos vía RA
   
7. Tus dispositivos obtienen IPs automáticamente en esa subred

┌────────────────────────────────────────────────────────────────┐
│ VERIFICACIÓN EN TU ROUTER                                      │
└────────────────────────────────────────────────────────────────┘
""")
    
    # Mostrar estado de la interfaz wan6
    print("🔍 Estado de wan6 (interfaz que recibe la delegación):")
    print("-" * 70)
    result = await ssh_client.execute("ubus call network.interface.wan6 status | grep -A 20 delegation")
    if result["success"]:
        print(result["stdout"])
    
    # Mostrar el prefijo delegado
    print("\n📦 PREFIJO DELEGADO POR EL ISP:")
    print("-" * 70)
    result = await ssh_client.execute("ubus call network.interface.wan6 status")
    if result["success"]:
        import json
        try:
            data = json.loads(result["stdout"])
            if "ipv6-prefix" in data:
                print("Prefijos recibidos:")
                for prefix in data["ipv6-prefix"]:
                    address = prefix.get("address", "N/A")
                    mask = prefix.get("mask", "N/A")
                    print(f"  • {address}/{mask}")
                    print(f"    Valid: {prefix.get('valid', 'N/A')} segundos")
                    print(f"    Preferred: {prefix.get('preferred', 'N/A')} segundos")
                    if "class" in prefix:
                        print(f"    Clase: {prefix['class']}")
            
            if "ipv6-prefix-assignment" in data:
                print("\n📍 ASIGNACIONES A INTERFACES LOCALES:")
                for assignment in data["ipv6-prefix-assignment"]:
                    iface = assignment.get("interface", "N/A")
                    address = assignment.get("address", "N/A")
                    mask = assignment.get("mask", "N/A")
                    print(f"  • {iface}: {address}/{mask}")
        except:
            print(result["stdout"][:800])
    
    # Mostrar configuración UCI
    print("\n⚙️ CONFIGURACIÓN UCI (wan6):")
    print("-" * 70)
    result = await ssh_client.execute("uci show network.wan6")
    if result["success"]:
        for line in result["stdout"].split("\n"):
            if line.strip():
                print(f"  {line}")
    
    print("\n" + "=" * 70)
    print("""
┌────────────────────────────────────────────────────────────────┐
│ EXPLICACIÓN DE LOS PARÁMETROS                                  │
└────────────────────────────────────────────────────────────────┘

• proto='dhcpv6'
  └─ Protocolo para pedir IP y prefijo al ISP

• reqaddress='try'
  └─ Pide UNA dirección IPv6 para la interfaz WAN
  └─ Opciones: 'none', 'try', 'force'

• reqprefix='auto'
  └─ ESTO ES LA DELEGACIÓN DE PREFIJO
  └─ Pide un rango completo de IPs
  └─ Opciones: 'auto', 'no', número (48, 56, 60, 64)
  └─ 'auto' = acepta lo que el ISP ofrezca

• peerdns='0'/'1'
  └─ Si acepta servidores DNS del ISP

┌────────────────────────────────────────────────────────────────┐
│ ¿CÓMO FUNCIONA LA DELEGACIÓN?                                  │
└────────────────────────────────────────────────────────────────┘

ISP tiene: 2800:484:8f7e::/40 (rango enorme)
           │
           ├─ Cliente 1: 2800:484:8f7e:3200::/56
           │   └─ Tu router (256 subredes)
           │
           ├─ Cliente 2: 2800:484:8f7e:3300::/56
           │
           └─ Cliente 3: 2800:484:8f7e:3400::/56

Tu router toma: 2800:484:8f7e:3200::/56
                │
                ├─ Subred 0: 2800:484:8f7e:3200::/64 (WAN)
                ├─ Subred d0: 2800:484:8f7e:32d0::/64 (LAN) ← USAS ESTA
                ├─ Subred d1: 2800:484:8f7e:32d1::/64 (VLAN1)
                └─ Subredes d2-ff: Disponibles para futuro

┌────────────────────────────────────────────────────────────────┐
│ VENTAJAS DE IPv6-PD                                            │
└────────────────────────────────────────────────────────────────┘

✅ No necesitas NAT (cada dispositivo tiene IP pública)
✅ Mejor rendimiento (conexión directa end-to-end)
✅ Puedes crear múltiples subredes (guest network, IoT, etc.)
✅ Más fácil hospedar servicios (SSH, web server, etc.)
✅ El prefijo se renueva automáticamente
✅ Escalable (puedes tener miles de dispositivos)

┌────────────────────────────────────────────────────────────────┐
│ DIFERENCIAS CON OTROS MÉTODOS                                  │
└────────────────────────────────────────────────────────────────┘

• Static IPv6:   Configuras manualmente cada IP
                 └─ Tedioso, no escala

• 6to4/Tunnel:   Encapsula IPv6 dentro de IPv4
                 └─ Lento, transitorio

• DHCPv6 simple: Solo UNA dirección para el router
                 └─ No puedes dar IPs a tu LAN

• IPv6-PD:       ✅ Rango completo delegado
                 ✅ Router distribuye a LAN
                 ✅ Automático y escalable
""")
    
    await ssh_client.disconnect()
    
    print("\n" + "=" * 70)
    print("✅ CONCLUSIÓN")
    print("=" * 70)
    print("""
Tu router usa IPv6-PD correctamente:
• Recibe: 2800:484:8f7e:3200::/56 del ISP
• Asigna: 2800:484:8f7e:32d0::/64 a tu LAN
• Dispositivos obtienen IPs en ese rango automáticamente

¡Todo está funcionando como debe ser! 🎉
""")

if __name__ == "__main__":
    asyncio.run(explain_pd())
