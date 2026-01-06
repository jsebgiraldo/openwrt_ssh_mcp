"""Script simple para probar la conexión SSH a OpenWRT."""

import asyncio
import asyncssh
import sys

async def test_connection():
    """Prueba de conexión SSH al router OpenWRT."""
    host = "192.168.1.1"
    port = 22
    username = "root"
    
    try:
        print(f"Intentando conectar a {username}@{host}:{port}...")
        print("Usando autenticación por clave SSH por defecto...")
        
        # Conectar sin contraseña, usando claves SSH por defecto
        conn = await asyncssh.connect(
            host=host,
            port=port,
            username=username,
            known_hosts=None,  # Deshabilitar verificación de host
            connect_timeout=10,
        )
        
        print("✅ Conexión SSH establecida exitosamente!")
        
        # Ejecutar comando de prueba
        result = await conn.run("uname -a", check=True)
        print(f"\n📋 Información del sistema:")
        print(result.stdout)
        
        # Obtener versión de OpenWRT
        result = await conn.run("cat /etc/openwrt_version 2>/dev/null || cat /etc/openwrt_release | grep DISTRIB_DESCRIPTION", check=False)
        if result.stdout:
            print(f"🔧 Versión OpenWRT:")
            print(result.stdout)
        
        # Probar uci (comando específico de OpenWRT)
        result = await conn.run("uci show system.@system[0].hostname 2>/dev/null", check=False)
        if result.stdout:
            print(f"\n🏠 Hostname:")
            print(result.stdout)
        
        conn.close()
        await conn.wait_closed()
        
        print("\n✅ Prueba completada exitosamente!")
        print("El servidor MCP está listo para usar con tu router OpenWRT.")
        return True
        
    except asyncssh.Error as e:
        print(f"\n❌ Error de conexión SSH: {e}")
        print("\nPosibles soluciones:")
        print("1. Verifica que el router esté accesible en 192.168.1.1")
        print("2. Verifica que SSH esté habilitado en el router")
        print("3. Asegúrate de tener tu clave SSH pública en el router:")
        print("   - Copia tu clave: type %USERPROFILE%\\.ssh\\id_rsa.pub")
        print("   - En el router: cat >> /etc/dropbear/authorized_keys")
        print("4. O configura autenticación por contraseña en el archivo .env")
        return False
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
