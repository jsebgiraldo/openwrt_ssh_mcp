# 🐳 Guía Rápida: Docker Desktop + MCP Toolkit

## ✨ Lo que acabamos de crear

Has configurado exitosamente un **servidor MCP containerizado** que permite a Claude/VS Code gestionar tu router OpenWRT a través de Docker.

## 🎯 Arquitectura Final

```
┌─────────────────────────┐
│   Claude / VS Code      │
│   (MCP Client)          │
└──────────┬──────────────┘
           │ stdio
           │
┌──────────▼──────────────┐
│   Docker Container      │
│  ┌──────────────────┐   │
│  │  MCP Server      │   │
│  │  (Python)        │   │
│  └────────┬─────────┘   │
└───────────┼─────────────┘
            │ SSH
            │
┌───────────▼─────────────┐
│   Router OpenWRT        │
│   (192.168.1.1)         │
└─────────────────────────┘
```

## 🚀 Quick Start

### 1. Ya tienes la imagen construida ✅

```powershell
docker images openwrt-ssh-mcp
# OUTPUT: openwrt-ssh-mcp:latest (271MB)
```

### 2. Probar el servidor

```powershell
# Opción A: Usando script helper
.\docker-mcp.ps1 run

# Opción B: Docker directo
docker run -i --rm --network host --env-file .env `
  --mount type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly `
  openwrt-ssh-mcp:latest
```

### 3. Integrar con Claude Desktop

**Ubicación:** `%APPDATA%\Claude\claude_desktop_config.json`

Ya tienes dos configuraciones en `claude_desktop_config.json`:

- **`openwrt-router-docker`** → Usa Docker (recomendado)
- **`openwrt-router-local`** → Usa Python local (desarrollo)

**Copiar config:**
```powershell
copy claude_desktop_config.json "$env:APPDATA\Claude\claude_desktop_config.json"

# Reiniciar Claude Desktop
```

### 4. Probar desde Claude

Abre Claude Desktop y pregunta:

> "¿Qué herramientas tienes disponibles para gestionar el router OpenWRT?"

Deberías ver 8 herramientas:
- `openwrt_test_connection`
- `openwrt_get_system_info`
- `openwrt_restart_interface`
- `openwrt_get_wifi_status`
- `openwrt_list_dhcp_leases`
- `openwrt_get_firewall_rules`
- `openwrt_read_config`
- `openwrt_execute_command`

## 📋 Scripts Helper

### `docker-mcp.ps1` - Tu herramienta principal

```powershell
# Ver ayuda
.\docker-mcp.ps1

# Construir imagen
.\docker-mcp.ps1 build

# Ejecutar servidor (interactivo)
.\docker-mcp.ps1 run

# Probar conexión
.\docker-mcp.ps1 test

# Ver logs
.\docker-mcp.ps1 logs

# Abrir shell en container
.\docker-mcp.ps1 shell

# Limpiar todo
.\docker-mcp.ps1 clean
```

## 🔧 Configuración

### Archivo `.env` (obligatorio)

```bash
# Router OpenWRT
OPENWRT_HOST=192.168.1.1
OPENWRT_PORT=22
OPENWRT_USER=root

# Autenticación (usar KEY_FILE recomendado)
OPENWRT_PASSWORD=
OPENWRT_KEY_FILE=/root/.ssh/id_ed25519

# Seguridad
ENABLE_COMMAND_VALIDATION=true
ENABLE_AUDIT_LOGGING=true
SSH_TIMEOUT=30
```

### Generar SSH Key (recomendado)

```powershell
# Generar llave
ssh-keygen -t ed25519 -f $HOME\.ssh\openwrt_mcp -C "MCP Docker"

# Copiar al router
type $HOME\.ssh\openwrt_mcp.pub | ssh root@192.168.1.1 "cat >> /etc/dropbear/authorized_keys"

# Actualizar .env
# OPENWRT_KEY_FILE=/root/.ssh/openwrt_mcp
```

## 🎛️ Docker Compose (alternativo)

```powershell
# Usar docker-compose
docker-compose up

# En background
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener
docker-compose down
```

## 🧪 Testing

### Test 1: Conexión SSH desde container

```powershell
.\docker-mcp.ps1 shell

# Dentro del container:
ssh -i /root/.ssh/openwrt_mcp root@192.168.1.1 "uname -a"
exit
```

### Test 2: MCP Server standalone

```powershell
.\docker-mcp.ps1 run

# Deberías ver:
# INFO - Starting OpenWRT SSH MCP Server...
# INFO - SSH connection established successfully
# INFO - MCP Server ready - waiting for requests...
```

### Test 3: Con MCP Inspector

```powershell
# Instalar (una vez)
npm install -g @modelcontextprotocol/inspector

# Inspeccionar servidor
npx @modelcontextprotocol/inspector docker run -i --rm openwrt-ssh-mcp:latest
```

## 📊 Monitoreo

### Ver logs del servidor

```powershell
# Últimas 50 líneas
.\docker-mcp.ps1 logs

# Seguir en tiempo real
Get-Content .\logs\openwrt_mcp.log -Wait
```

### Ver containers corriendo

```powershell
docker ps | Select-String openwrt
```

### Ver uso de recursos

```powershell
docker stats openwrt-mcp
```

## 🔐 Seguridad Implementada

✅ **Read-only filesystem** - El container no puede modificar archivos
✅ **No capabilities** - Sin permisos especiales del kernel
✅ **SSH keys read-only** - Llaves montadas como solo lectura
✅ **tmpfs volátil** - `/tmp` se limpia al apagar
✅ **No privilege escalation** - Sin sudo ni escalación
✅ **Command validation** - Whitelist de comandos permitidos
✅ **Audit logging** - Todos los comandos registrados

## 🌐 Networking

### Host Network (actual)

```yaml
network_mode: host
```

**Pros:** Acceso directo al router en LAN
**Contras:** Menos aislamiento

### Bridge Network (alternativo)

```yaml
networks:
  - openwrt-network
extra_hosts:
  - "router:192.168.1.1"
```

**Pros:** Mejor aislamiento
**Contras:** Configuración adicional

## 🔄 Workflow de Desarrollo

```powershell
# 1. Hacer cambios en código
code openwrt_ssh_mcp\tools.py

# 2. Rebuild imagen
.\docker-mcp.ps1 build

# 3. Probar
.\docker-mcp.ps1 run

# 4. Ver logs
.\docker-mcp.ps1 logs

# 5. Si funciona, usar desde Claude
```

## 📦 Publicar en Docker Hub

```powershell
# Login
docker login

# Tag
docker tag openwrt-ssh-mcp:latest tuusuario/openwrt-ssh-mcp:latest

# Push
docker push tuusuario/openwrt-ssh-mcp:latest
```

Luego otros pueden usar:

```json
{
  "mcpServers": {
    "openwrt": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "tuusuario/openwrt-ssh-mcp:latest"]
    }
  }
}
```

## 🐛 Troubleshooting

### Container no inicia

```powershell
# Ver logs de Docker
docker logs openwrt-mcp

# Verificar .env
cat .env
```

### No puede conectar al router

```powershell
# Test directo desde host
ping 192.168.1.1
ssh root@192.168.1.1

# Test desde container
.\docker-mcp.ps1 shell
ping 192.168.1.1
```

### Claude no detecta el servidor

1. Verificar config: `cat "$env:APPDATA\Claude\claude_desktop_config.json"`
2. Verificar imagen: `docker images openwrt-ssh-mcp`
3. Test standalone: `.\docker-mcp.ps1 run`
4. Reiniciar Claude Desktop completamente

### SSH Permission Denied

```powershell
# Verificar que key está montada
docker run -i --rm `
  --mount type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly `
  openwrt-ssh-mcp:latest `
  ls -la /root/.ssh

# Verificar permisos locales
icacls $HOME\.ssh\openwrt_mcp
```

## 🎓 Próximos Pasos

1. ✅ **Ya tienes:** Imagen Docker construida
2. ✅ **Ya tienes:** Scripts helper funcionando
3. 🔄 **Siguiente:** Configurar `.env` con credenciales reales
4. 🔄 **Siguiente:** Probar conexión con `.\docker-mcp.ps1 run`
5. 🔄 **Siguiente:** Integrar con Claude Desktop
6. 🎯 **Siguiente:** Usar desde Claude para gestionar tu router

## 📚 Recursos

- **MCP Docs:** https://modelcontextprotocol.io/
- **Docker MCP:** https://www.docker.com/blog/dynamic-mcps-with-docker/
- **MCP Servers:** https://github.com/modelcontextprotocol/servers
- **Este proyecto:** `DOCKER_GUIDE.md` y `README.md`

## 💡 Tips

- Usa `.\docker-mcp.ps1` para todas las operaciones comunes
- Los logs se guardan en `logs/openwrt_mcp.log`
- Puedes tener múltiples servidores MCP corriendo
- Docker Desktop debe estar corriendo
- La imagen es pequeña (271MB) gracias al multi-stage build

## ✅ Checklist Final

- [x] Imagen Docker construida
- [x] Script helper creado
- [x] Configuración de Claude preparada
- [x] Documentación completa
- [ ] Archivo `.env` configurado con tu router
- [ ] SSH key generada y copiada al router
- [ ] Probado con `.\docker-mcp.ps1 run`
- [ ] Integrado con Claude Desktop
- [ ] Primera prueba exitosa desde Claude

---

**¡Todo listo!** 🎉 Ahora solo necesitas configurar tu `.env` con las credenciales de tu router y probar.

**Comando para empezar:**
```powershell
.\docker-mcp.ps1 run
```
