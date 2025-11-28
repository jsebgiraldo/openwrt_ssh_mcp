# Start MCP Server for VS Code
# This script starts the OpenWRT MCP server for use with GitHub Copilot

Write-Host "🚀 Starting OpenWRT MCP Server for VS Code..." -ForegroundColor Cyan
Write-Host ""

# Change to project directory
$ProjectDir = "c:\Users\Luis Antonio\Documents\UNAL\MCPs-OpenWRT"
Set-Location $ProjectDir

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Warning: .env file not found, using inline configuration" -ForegroundColor Yellow
}

Write-Host "📡 Router: 100.93.80.37:22" -ForegroundColor Green
Write-Host "👤 User: root" -ForegroundColor Green
Write-Host "🔐 Security: Validation + Audit Logging enabled" -ForegroundColor Green
Write-Host ""
Write-Host "💡 MCP Server will start in 3 seconds..." -ForegroundColor Yellow
Write-Host "   Use Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

Start-Sleep -Seconds 1
Write-Host "3..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Write-Host "2..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Write-Host "1..." -ForegroundColor Yellow
Write-Host ""

# Start the MCP server
Write-Host "🎯 Starting MCP Server..." -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

try {
    python -m openwrt_ssh_mcp.server
}
catch {
    Write-Host ""
    Write-Host "❌ Error starting MCP server" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Troubleshooting:" -ForegroundColor Yellow
    Write-Host "   1. Verify dependencies: pip install -e ." -ForegroundColor Gray
    Write-Host "   2. Check .env configuration" -ForegroundColor Gray
    Write-Host "   3. Test SSH: ssh root@100.93.80.37" -ForegroundColor Gray
    Write-Host "   4. Check logs: Get-Content openwrt_mcp.log -Tail 50" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "👋 MCP Server stopped" -ForegroundColor Yellow
