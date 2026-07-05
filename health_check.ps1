# Health check completo del sistema SATRI
$services = @(
    @{ name="MML (Ingesta)";      url="http://localhost:8000/health" },
    @{ name="MIA_VT (Threat Intel)"; url="http://localhost:8001/health" },
    @{ name="MCOR (Correlador)";  url="http://localhost:8002/health" },
    @{ name="MTA (Triage)";       url="http://localhost:8003/health" },
    @{ name="Integrations (SOAR)";url="http://localhost:8004/health" },
    @{ name="Dashboard SOC";      url="http://localhost:8005/health" },
    @{ name="MIA_ML (UEBA)";      url="http://localhost:8006/health" }
)

Write-Host ""
Write-Host "============================================="
Write-Host "   SATRI - Health Check Completo"
Write-Host "============================================="

$allOk = $true
foreach ($svc in $services) {
    try {
        $resp = Invoke-RestMethod -Uri $svc.url -Method GET -TimeoutSec 5
        Write-Host "  [OK] $($svc.name)" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] $($svc.name) -> $_" -ForegroundColor Red
        $allOk = $false
    }
}

Write-Host "============================================="
if ($allOk) {
    Write-Host "  TODOS LOS SERVICIOS OPERATIVOS" -ForegroundColor Green
} else {
    Write-Host "  ALGUNOS SERVICIOS TIENEN PROBLEMAS" -ForegroundColor Yellow
}
Write-Host "============================================="
Write-Host ""

# Verificar Kafka topics
Write-Host "[Kafka] Verificando topicos..."
$kafkaTopics = docker exec satri-kafka kafka-topics --bootstrap-server localhost:9092 --list 2>&1
$topics = @("satri.logs.raw","satri.logs.normalized","satri.logs.enriched","satri.alerts.enrichment","satri.ioc.intelligence","satri.correlated.alerts","satri.incidents.triage")
foreach ($t in $topics) {
    if ($kafkaTopics -match [regex]::Escape($t)) {
        Write-Host "  [OK] $t" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $t" -ForegroundColor Red
    }
}
Write-Host "============================================="
