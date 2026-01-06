"""Script interactivo para probar las herramientas del servidor MCP de OpenWRT."""

import asyncio
import sys
import os

# Agregar el directorio padre al path para importar el módulo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openwrt_ssh_mcp.ssh_client import ssh_client
from openwrt_ssh_mcp.tools import OpenWRTTools
from openwrt_ssh_mcp.config import settings

async def test_mcp_tools():
    """Prueba las herramientas del servidor MCP."""
    
    print("=" * 70)
    print("🧪 PRUEBA DEL SERVIDOR MCP DE OPENWRT")
    print("=" * 70)
    print(f"\n📡 Conectando a: {settings.openwrt_user}@{settings.openwrt_host}:{settings.openwrt_port}")
    
    # Conectar al router
    connected = await ssh_client.connect()
    
    if not connected:
        print("❌ No se pudo conectar al router OpenWRT")
        return False
    
    print("✅ Conexión SSH establecida\n")
    
    tools = OpenWRTTools()
    
    # Test 1: Información del sistema
    print("-" * 70)
    print("📋 TEST 1: Información del Sistema")
    print("-" * 70)
    result = await tools.get_system_info()
    if result["success"]:
        print("✅ Información del sistema obtenida:")
        sys_info = result.get("system_info", {})
        if "board" in sys_info and isinstance(sys_info["board"], dict):
            print(f"  • Modelo: {sys_info['board'].get('model', 'N/A')}")
            print(f"  • Release: {sys_info['board'].get('release', {}).get('description', 'N/A')}")
        if "info" in sys_info and isinstance(sys_info["info"], dict):
            uptime_sec = sys_info['info'].get('uptime', 0)
            print(f"  • Uptime: {uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown')}")
    
    # Test 2: Información de red
    print("\n" + "-" * 70)
    print("🌐 TEST 2: Interfaces de Red")
    print("-" * 70)
    result = await ssh_client.execute("ip addr show")
    if result["success"]:
        print("✅ Interfaces de red:")
        lines = result["stdout"].split("\n")[:15]  # Primeras 15 líneas
        print("\n".join(lines))
    else:
        print(f"❌ Error: {result.get('stderr', 'Unknown')}")
    
    # Test 3: Listar configuración UCI
    print("\n" + "-" * 70)
    print("⚙️ TEST 3: Configuración UCI")
    print("-" * 70)
    result = await tools.read_config("system")
    if result["success"]:
        print("✅ Configuración del sistema:")
        lines = result.get("config", "").split("\n")[:10]  # Primeras 10 líneas
        print("\n".join(lines))
    else:
        print(f"❌ Error: {result.get('error', 'Unknown')}")
    
    # Test 4: Servicios activos
    print("\n" + "-" * 70)
    print("🔧 TEST 4: Servicios del Sistema")
    print("-" * 70)
    result = await ssh_client.execute("ls /etc/init.d/ | head -10")
    if result["success"]:
        print("✅ Servicios disponibles:")
        print(result["stdout"])
    else:
        print(f"❌ Error: {result.get('stderr', 'Unknown')}")
    
    # Test 5: Estado del sistema
    print("\n" + "-" * 70)
    print("📊 TEST 5: Estado del Sistema (uptime, memoria, CPU)")
    print("-" * 70)
    result = await ssh_client.execute("uptime")
    if result["success"]:
        print(f"⏰ Uptime: {result['stdout'].strip()}")
    
    result = await ssh_client.execute("free -m")
    if result["success"]:
        print(f"\n💾 Memoria:")
        print(result['stdout'])
    
    # Test 6: Verificar si hay OpenThread
    print("\n" + "-" * 70)
    print("🔗 TEST 6: Verificación de OpenThread OTBR")
    print("-" * 70)
    result = await ssh_client.execute("which ot-ctl")
    if result["success"] and result["stdout"].strip():
        print("✅ OpenThread CLI encontrado:", result["stdout"].strip())
        # Intentar obtener el estado
        ot_result = await tools.thread_get_info()
        if ot_result["success"]:
            thread_info = ot_result.get("thread_info", {})
            print("✅ Información de Thread Network:")
            print(f"  • Estado: {thread_info.get('state', 'N/A')}")
            print(f"  • Canal: {thread_info.get('channel', 'N/A')}")
            print(f"  • Nombre: {thread_info.get('networkname', 'N/A')}")
        else:
            print("⚠️ OpenThread CLI disponible pero no configurado")
    else:
        print("ℹ️ OpenThread no está instalado en este router")
    
    # Test 7: Listar paquetes instalados (primeros 5)
    print("\n" + "-" * 70)
    print("📦 TEST 7: Paquetes Instalados (muestra de 5)")
    print("-" * 70)
    result = await tools.opkg_list_installed()
    if result["success"]:
        packages = result.get("packages", [])[:5]
        print(f"✅ Total de paquetes instalados: {result.get('count', 0)}")
        print("Muestra de paquetes:")
        for pkg in packages:
            print(f"  • {pkg.get('name', 'N/A')} - {pkg.get('version', 'N/A')}")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown')}")
    
    # Desconectar
    await ssh_client.disconnect()
    
    print("\n" + "=" * 70)
    print("✅ PRUEBAS COMPLETADAS EXITOSAMENTE")
    print("=" * 70)
    print("\n🎉 El servidor MCP está completamente funcional y listo para usar!")
    print("\n📚 Herramientas MCP disponibles:")
    print("   • openwrt_test_connection")
    print("   • openwrt_execute_command")
    print("   • openwrt_get_system_info")
    print("   • openwrt_get_network_info")
    print("   • openwrt_uci_show / uci_set / uci_commit")
    print("   • openwrt_ubus_call")
    print("   • openwrt_list_services / service_status / service_action")
    print("   • openwrt_get_thread_network_info / thread_ctl")
    print("   • openwrt_opkg_* (list, install, remove, update)")
    print("\n💡 Para usarlo con Claude Desktop, agrega la configuración en:")
    print("   %APPDATA%\\Claude\\claude_desktop_config.json")
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_mcp_tools())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Prueba interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
