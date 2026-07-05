Write-Host "=============================================="
Write-Host "   Iniciando Entorno SATRI Completo"
Write-Host "=============================================="

Write-Host "[1/4] Limpiando e iniciando contenedores Docker..."
docker compose down --remove-orphans
$satriContainers = docker ps -a -q --filter "name=satri"
if ($satriContainers) {
    $satriContainers | ForEach-Object { docker rm -f $_ }
}
docker compose up -d

Write-Host "[2/4] Inicializando tópicos de Kafka..."
powershell -ExecutionPolicy Bypass -File .\init.ps1

Write-Host "[3/4] Deteniendo instancias previas del agente..."
Get-Process -Name "SATRI_Protection" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match "main.py" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "[4/4] Iniciando Agente EDR (Desktop Agent)..."
Start-Process -FilePath "$PSScriptRoot\dist\SATRI_Protection.exe" -WorkingDirectory "$PSScriptRoot\desktop-agent" -WindowStyle Hidden

Write-Host "=============================================="
Write-Host "Todo el entorno se ha iniciado correctamente."
Write-Host "Dashboard Directo: http://localhost:8005"
Write-Host "=============================================="
