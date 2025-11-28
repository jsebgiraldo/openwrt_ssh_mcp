# OpenWRT MCP Server - Docker Helper Script
# Facilita el uso del servidor MCP con Docker

param(
    [Parameter(Position=0)]
    [ValidateSet("build", "run", "test", "logs", "stop", "clean", "shell")]
    [string]$Action = "run"
)

$ErrorActionPreference = "Stop"
$ProjectDir = "c:\Users\Luis Antonio\Documents\UNAL\MCPs-OpenWRT"
$ImageName = "openwrt-ssh-mcp:latest"

function Show-Usage {
    Write-Host @"
OpenWRT MCP Docker Helper

Usage: .\docker-mcp.ps1 [action]

Actions:
  build   - Construir imagen Docker
  run     - Ejecutar servidor MCP (interactivo)
  test    - Probar conexión al router
  logs    - Ver logs del servidor
  stop    - Detener container
  clean   - Limpiar imagen y containers
  shell   - Abrir shell en el container

Examples:
  .\docker-mcp.ps1 build
  .\docker-mcp.ps1 run
  .\docker-mcp.ps1 test
"@
}

function Build-Image {
    Write-Host "🔨 Construyendo imagen Docker..." -ForegroundColor Cyan
    Set-Location $ProjectDir
    docker build -t $ImageName .
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Imagen construida exitosamente" -ForegroundColor Green
        docker images $ImageName
    } else {
        Write-Host "❌ Error construyendo imagen" -ForegroundColor Red
        exit 1
    }
}

function Run-Server {
    Write-Host "🚀 Iniciando servidor MCP en Docker..." -ForegroundColor Cyan
    Write-Host "Presiona Ctrl+C para detener" -ForegroundColor Yellow
    
    Set-Location $ProjectDir
    
    # Verificar que .env existe
    if (-not (Test-Path ".env")) {
        Write-Host "❌ Archivo .env no encontrado. Copia .env.example a .env y configúralo." -ForegroundColor Red
        exit 1
    }
    
    # Crear directorio de logs si no existe
    if (-not (Test-Path "logs")) {
        New-Item -ItemType Directory -Path "logs" | Out-Null
    }
    
    docker run -i --rm `
        --name openwrt-mcp `
        --network host `
        --env-file .env `
        --mount "type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly" `
        --mount "type=bind,src=$ProjectDir\logs,dst=/app/logs" `
        --read-only `
        --tmpfs "/tmp:rw,noexec,nosuid,size=50m" `
        --cap-drop ALL `
        --security-opt "no-new-privileges:true" `
        $ImageName
}

function Test-Connection {
    Write-Host "🔍 Probando conexión al router..." -ForegroundColor Cyan
    
    Set-Location $ProjectDir
    
    # Test rápido ejecutando un comando simple
    Write-Host "Ejecutando test de conexión..." -ForegroundColor Yellow
    
    $result = docker run -i --rm `
        --network host `
        --env-file .env `
        --mount "type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly" `
        --cap-drop ALL `
        $ImageName 2>&1 | Select-String -Pattern "SSH connection established|Connection failed|Error"
    
    if ($result) {
        Write-Host "Resultado del test:" -ForegroundColor Cyan
        Write-Host $result
    } else {
        Write-Host "⏱️ Test iniciado, revisa logs/openwrt_mcp.log para detalles" -ForegroundColor Yellow
    }
}

function Show-Logs {
    Write-Host "📋 Mostrando logs..." -ForegroundColor Cyan
    Set-Location $ProjectDir
    
    $logFile = "logs\openwrt_mcp.log"
    
    if (Test-Path $logFile) {
        Get-Content $logFile -Tail 50
        Write-Host "`n💡 Para seguir logs en tiempo real: Get-Content $logFile -Wait" -ForegroundColor Yellow
    } else {
        Write-Host "❌ No se encontraron logs en $logFile" -ForegroundColor Red
        Write-Host "Ejecuta primero: .\docker-mcp.ps1 run" -ForegroundColor Yellow
    }
}

function Stop-Container {
    Write-Host "🛑 Deteniendo container..." -ForegroundColor Cyan
    
    $running = docker ps --filter "name=openwrt-mcp" -q
    if ($running) {
        docker stop openwrt-mcp
        Write-Host "✅ Container detenido" -ForegroundColor Green
    } else {
        Write-Host "ℹ️  No hay container corriendo" -ForegroundColor Yellow
    }
}

function Clean-All {
    Write-Host "🧹 Limpiando containers e imagen..." -ForegroundColor Cyan
    
    # Detener container si está corriendo
    Stop-Container
    
    # Remover containers detenidos
    $containers = docker ps -a --filter "name=openwrt-mcp" -q
    if ($containers) {
        docker rm $containers
        Write-Host "✅ Containers removidos" -ForegroundColor Green
    }
    
    # Remover imagen
    $image = docker images -q $ImageName
    if ($image) {
        $confirmation = Read-Host "¿Remover imagen $ImageName? (y/N)"
        if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
            docker rmi $ImageName
            Write-Host "✅ Imagen removida" -ForegroundColor Green
        }
    } else {
        Write-Host "ℹ️  No hay imagen para remover" -ForegroundColor Yellow
    }
}

function Open-Shell {
    Write-Host "🐚 Abriendo shell en container..." -ForegroundColor Cyan
    
    Set-Location $ProjectDir
    
    docker run -it --rm `
        --name openwrt-mcp-shell `
        --network host `
        --env-file .env `
        --mount "type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly" `
        --entrypoint /bin/bash `
        $ImageName
}

# Main execution
switch ($Action) {
    "build" { Build-Image }
    "run" { Run-Server }
    "test" { Test-Connection }
    "logs" { Show-Logs }
    "stop" { Stop-Container }
    "clean" { Clean-All }
    "shell" { Open-Shell }
    default { Show-Usage }
}
