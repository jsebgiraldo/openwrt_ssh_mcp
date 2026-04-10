# OpenWRT MCP Server - Docker Helper Script

param(
    [Parameter(Position=0)]
    [ValidateSet("build", "run", "test", "logs", "stop", "clean", "shell")]
    [string]$Action = "run"
)

$ErrorActionPreference = "Stop"
$ProjectDir = "$HOME\Documents\openwrt_ssh_mcp"
$ImageName = "openwrt-ssh-mcp:latest"

function Show-Usage {
    Write-Host @"
OpenWRT MCP Docker Helper

Usage: .\docker-mcp.ps1 [action]

Actions:
  build   - Build Docker image
  run     - Run MCP server (interactive)
  test    - Test router connection
  logs    - View server logs
  stop    - Stop container
  clean   - Remove image and containers
  shell   - Open shell in container

Examples:
  .\docker-mcp.ps1 build
  .\docker-mcp.ps1 run
  .\docker-mcp.ps1 test
"@
}

function Build-Image {
    Write-Host "Building Docker image..." -ForegroundColor Cyan
    Set-Location $ProjectDir
    docker build -t $ImageName .

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Image built successfully" -ForegroundColor Green
        docker images $ImageName
    } else {
        Write-Host "Error building image" -ForegroundColor Red
        exit 1
    }
}

function Run-Server {
    Write-Host "Starting MCP server in Docker..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow

    Set-Location $ProjectDir

    if (-not (Test-Path ".env")) {
        Write-Host "Error: .env not found. Copy .env.example to .env and configure it." -ForegroundColor Red
        exit 1
    }

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
    Write-Host "Testing router connection..." -ForegroundColor Cyan

    Set-Location $ProjectDir

    $result = docker run -i --rm `
        --network host `
        --env-file .env `
        --mount "type=bind,src=$HOME\.ssh,dst=/root/.ssh,readonly" `
        --cap-drop ALL `
        $ImageName 2>&1 | Select-String -Pattern "SSH connection established|Connection failed|Error"

    if ($result) {
        Write-Host "Test result:" -ForegroundColor Cyan
        Write-Host $result
    } else {
        Write-Host "Test started — check logs/openwrt_mcp.log for details" -ForegroundColor Yellow
    }
}

function Show-Logs {
    Write-Host "Showing logs..." -ForegroundColor Cyan
    Set-Location $ProjectDir

    $logFile = "logs\openwrt_mcp.log"

    if (Test-Path $logFile) {
        Get-Content $logFile -Tail 50
        Write-Host "`nTo follow logs in real time: Get-Content $logFile -Wait" -ForegroundColor Yellow
    } else {
        Write-Host "No logs found at $logFile" -ForegroundColor Red
        Write-Host "Run first: .\docker-mcp.ps1 run" -ForegroundColor Yellow
    }
}

function Stop-Container {
    Write-Host "Stopping container..." -ForegroundColor Cyan

    $running = docker ps --filter "name=openwrt-mcp" -q
    if ($running) {
        docker stop openwrt-mcp
        Write-Host "Container stopped" -ForegroundColor Green
    } else {
        Write-Host "No container running" -ForegroundColor Yellow
    }
}

function Clean-All {
    Write-Host "Removing containers and image..." -ForegroundColor Cyan

    Stop-Container

    $containers = docker ps -a --filter "name=openwrt-mcp" -q
    if ($containers) {
        docker rm $containers
        Write-Host "Containers removed" -ForegroundColor Green
    }

    $image = docker images -q $ImageName
    if ($image) {
        $confirmation = Read-Host "Remove image $ImageName? (y/N)"
        if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
            docker rmi $ImageName
            Write-Host "Image removed" -ForegroundColor Green
        }
    } else {
        Write-Host "No image to remove" -ForegroundColor Yellow
    }
}

function Open-Shell {
    Write-Host "Opening shell in container..." -ForegroundColor Cyan

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
