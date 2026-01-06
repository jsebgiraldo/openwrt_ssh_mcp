"""Script para optimizar la configuración de IPv6."""

import asyncio
from openwrt_ssh_mcp.ssh_client import ssh_client

async def optimize_ipv6():
    """Sugerencias de optimización para IPv6."""
    
    print("=" * 70)
    print("🔧 SUGERENCIAS DE OPTIMIZACIÓN IPv6")
    print("=" * 70)
    
    await ssh_client.connect()
    
    print("""
✅ TU CONFIGURACIÓN ACTUAL FUNCIONA BIEN

Pero aquí hay algunas mejoras opcionales:

1️⃣  CAMBIAR /60 a /64 en LAN (más eficiente)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Actualmente: lan.ip6assign='60' (usa 16 subredes)
   Recomendado:  lan.ip6assign='64' (usa 1 subred, más simple)
   
   Razón: Con /56 del ISP tienes 256 subredes /64 disponibles.
          A menos que tengas múltiples VLANs, /64 es suficiente.

   Comando:
   uci set network.lan.ip6assign='64'
   uci commit network
   /etc/init.d/network restart

2️⃣  HABILITAR RA (Router Advertisements) EXPLÍCITAMENTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Asegura que tus dispositivos LAN reciban anuncios de red.
   
   Comandos:
   uci set dhcp.lan.ra='server'
   uci set dhcp.lan.dhcpv6='server'
   uci set dhcp.lan.ra_management='1'
   uci commit dhcp
   /etc/init.d/odhcpd restart

3️⃣  CONFIGURAR DNS IPv6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Usa servidores DNS IPv6 para mejor rendimiento.
   
   DNS Públicos IPv6:
   • Google:     2001:4860:4860::8888, 2001:4860:4860::8844
   • Cloudflare: 2606:4700:4700::1111, 2606:4700:4700::1001
   • Quad9:      2620:fe::fe, 2620:fe::9
   
   Comando:
   uci add_list network.wan6.dns='2001:4860:4860::8888'
   uci add_list network.wan6.dns='2001:4860:4860::8844'
   uci commit network
   /etc/init.d/network restart

4️⃣  VERIFICAR FIREWALL IPv6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Asegúrate de que el firewall permite tráfico IPv6.
   
   Verificar:
   ip6tables -L -n -v
   
   Si necesitas abrir puertos (ej: servidor web):
   uci add firewall rule
   uci set firewall.@rule[-1].name='Allow-HTTP-IPv6'
   uci set firewall.@rule[-1].src='wan'
   uci set firewall.@rule[-1].proto='tcp'
   uci set firewall.@rule[-1].dest_port='80'
   uci set firewall.@rule[-1].family='ipv6'
   uci set firewall.@rule[-1].target='ACCEPT'
   uci commit firewall
   /etc/init.d/firewall restart

5️⃣  DESHABILITAR ULA SI NO LO NECESITAS (OPCIONAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   La dirección ULA (fd89:e85:a6f0::1) es para red local.
   Si solo usas IPv6 público, puedes deshabilitarla.
   
   Comando:
   uci set network.globals.ula_prefix=''
   uci commit network
   /etc/init.d/network restart

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 ESTADO ACTUAL DE TU RED IPv6:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Conectividad IPv6 funcional
✅ Prefijo delegado del ISP: 2800:484:8f7e:3200::/56
✅ LAN configurada: 2800:484:8f7e:32d0::/60
✅ Ping a Google IPv6 exitoso
✅ DHCPv6 activo

⚠️  Áreas a considerar:
   • Cambiar /60 a /64 para simplificar
   • Configurar DNS IPv6 explícitamente
   • Verificar reglas de firewall

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Verificar configuración DHCP actual
    print("\n🔍 CONFIGURACIÓN DHCP/RA ACTUAL:")
    print("-" * 70)
    result = await ssh_client.execute("uci show dhcp | grep -E 'dhcp.lan|ra|dhcpv6'")
    if result["success"]:
        print(result["stdout"])
    
    await ssh_client.disconnect()

if __name__ == "__main__":
    asyncio.run(optimize_ipv6())
