# Docker + MCP Toolkit Integration Guide

## 🐳 Docker Desktop con MCP

Esta guía muestra cómo usar tu servidor MCP OpenWRT con Docker Desktop y el MCP Toolkit.

## Arquitectura

```
Claude/VS Code → Docker Container → SSH → Router OpenWRT
                 (MCP Server)
```

## Setup Rápido

### 1. Construir la Imagen Docker

```powershell
cd "c:\Users\Luis Antonio\Documents\UNAL\MCPs-OpenWRT"

# Construir imagen optimizada
docker build -t openwrt-ssh-mcp:latest .

# Verificar imagen creada
docker images | Select-String openwrt
```

### 2. Probar el Container Standalone

```powershell
# Test interactivo con stdio transport
docker run -i --rm `
  --network host `
  --env-file .env `
  --mount type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly `
  --mount type=bind,src=$PWD\logs,dst=/app/logs `
  openwrt-ssh-mcp:latest
```

Deberías ver:
```
INFO - Starting OpenWRT SSH MCP Server...
INFO - SSH connection established successfully
INFO - MCP Server ready - waiting for requests...
```

Presiona `Ctrl+C` para salir.

### 3. Configurar Claude Desktop

Tienes **dos opciones** en `claude_desktop_config.json`:

#### Opción A: Via Docker (Recomendado para producción)
```json
"openwrt-router-docker": {
  "command": "docker",
  "args": ["run", "--rm", "-i", "--network", "host", ...]
}
```

#### Opción B: Local directo (Desarrollo)
```json
"openwrt-router-local": {
  "command": "python",
  "args": ["-m", "openwrt_ssh_mcp.server"]
}
```

**Copiar configuración:**
```powershell
copy claude_desktop_config.json "$env:APPDATA\Claude\claude_desktop_config.json"
```

### 4. Reiniciar Claude Desktop

1. Cierra completamente Claude Desktop
2. Vuelve a abrir
3. El servidor MCP debería estar disponible

## Verificación

### Ver logs de Docker

```powershell
# Si usas docker compose
docker-compose logs -f

# Si usas docker run directo
docker logs openwrt-ssh-mcp
```

### Ver logs del MCP Server

```powershell
# Logs del servidor
cat .\logs\openwrt_mcp.log

# Ver en tiempo real
Get-Content .\logs\openwrt_mcp.log -Wait
```

### Probar con MCP Inspector

```powershell
# Instalar inspector
npm install -g @modelcontextprotocol/inspector

# Probar servidor en Docker
npx @modelcontextprotocol/inspector docker run -i --rm openwrt-ssh-mcp:latest
```

## Comandos Útiles

### Docker Management

```powershell
# Construir y ejecutar
docker-compose up --build

# Ejecutar en background
docker-compose up -d

# Ver logs
docker-compose logs -f openwrt-mcp

# Detener
docker-compose down

# Limpiar todo
docker-compose down -v
docker rmi openwrt-ssh-mcp:latest
```

### Testing

```powershell
# Test rápido de conectividad
docker run -i --rm --network host --env-file .env `
  --mount type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly `
  openwrt-ssh-mcp:latest

# Test con comando específico
docker run -i --rm --network host --env-file .env `
  --mount type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly `
  openwrt-ssh-mcp:latest
```

## Seguridad

### SSH Keys

```powershell
# Generar llave dedicada para MCP
ssh-keygen -t ed25519 -f $HOME\.ssh\mcp_openwrt -C "MCP Docker"

# Copiar al router
type $HOME\.ssh\mcp_openwrt.pub | ssh root@192.168.1.1 "cat >> /etc/dropbear/authorized_keys"

# Actualizar .env
# OPENWRT_KEY_FILE=/root/.ssh/mcp_openwrt
```

### Permisos de Container

El container está configurado con:
- ✅ `read_only: true` - Sistema de archivos de solo lectura
- ✅ `cap_drop: ALL` - Sin capabilities
- ✅ `no-new-privileges` - Sin escalación de privilegios
- ✅ SSH keys montadas como read-only
- ✅ `/tmp` como tmpfs (volátil)

## Troubleshooting

### Container no puede conectar al router

```powershell
# Verificar que router es accesible desde host
ping 192.168.1.1

# Verificar SSH directo
ssh root@192.168.1.1 "uname -a"

# Si funciona, el container debería funcionar con --network host
```

### Permission denied en SSH

```powershell
# Verificar que la llave está montada
docker run -i --rm `
  --mount type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly `
  openwrt-ssh-mcp:latest `
  ls -la /root/.ssh

# Verificar permisos de la llave local
icacls $HOME\.ssh\mcp_openwrt
```

### MCP Server no responde en Claude

1. Verificar que imagen existe:
   ```powershell
   docker images openwrt-ssh-mcp
   ```

2. Verificar logs de Claude:
   ```powershell
   cat "$env:APPDATA\Claude\logs\mcp*.log"
   ```

3. Test standalone:
   ```powershell
   docker run -i --rm --network host --env-file .env `
     --mount type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly `
     openwrt-ssh-mcp:latest
   ```

### Container exits immediately

- Verifica que `.env` existe y tiene credenciales correctas
- Asegúrate de usar `--rm` y NO `restart: unless-stopped`
- Confirma que `-i` (interactive) está presente

## Multi-MCP Setup

Puedes orquestar múltiples MCP servers:

```yaml
# docker-compose-multi.yml
version: '3.8'

services:
  openwrt-mcp:
    image: openwrt-ssh-mcp:latest
    stdin_open: true
    tty: true
    env_file: ./openwrt.env
    volumes:
      - ~/.ssh:/root/.ssh:ro
    network_mode: host
    restart: "no"

  # Otro MCP server (ejemplo)
  filesystem-mcp:
    image: mcp/filesystem:latest
    stdin_open: true
    tty: true
    volumes:
      - ~/Documents:/workspace:ro
    restart: "no"
```

Claude Desktop config:
```json
{
  "mcpServers": {
    "openwrt": {
      "command": "docker",
      "args": ["compose", "-f", "docker-compose-multi.yml", "run", "--rm", "openwrt-mcp"]
    },
    "filesystem": {
      "command": "docker",
      "args": ["compose", "-f", "docker-compose-multi.yml", "run", "--rm", "filesystem-mcp"]
    }
  }
}
```

## Publicar en Docker Hub

```powershell
# Login
docker login

# Tag
docker tag openwrt-ssh-mcp:latest tuusuario/openwrt-ssh-mcp:latest
docker tag openwrt-ssh-mcp:latest tuusuario/openwrt-ssh-mcp:0.1.0

# Push
docker push tuusuario/openwrt-ssh-mcp:latest
docker push tuusuario/openwrt-ssh-mcp:0.1.0
```

## Próximos Pasos

1. ✅ Construir imagen Docker
2. ✅ Probar container standalone
3. ✅ Configurar Claude Desktop
4. ✅ Probar herramientas MCP
5. 📝 Documentar comandos específicos para tu router
6. 🚀 (Opcional) Publicar en Docker Hub

## Referencias

- [MCP Specification](https://modelcontextprotocol.io/docs)
- [Docker MCP Blog](https://www.docker.com/blog/dynamic-mcps-with-docker/)
- [MCP Servers GitHub](https://github.com/modelcontextprotocol/servers)
