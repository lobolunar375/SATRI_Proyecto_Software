# Script para compilar y subir imágenes a ACR
Write-Host "Iniciando proceso de Build & Push..." -ForegroundColor Cyan

$ACR_NAME = Get-Content .\acr_name.txt
$ACR_SERVER = "$ACR_NAME.azurecr.io"

Write-Host "Iniciando sesión en $ACR_SERVER..."
az acr login --name $ACR_NAME

$services = @(
    @{ Name="satri-mml"; Path=".\backend-aks\frontline\mml" },
    @{ Name="satri-mcor"; Path=".\backend-aks\frontline\mcor" },
    @{ Name="satri-mia-ml"; Path=".\backend-aks\frontline\mia_ml" },
    @{ Name="satri-mia-vt"; Path=".\backend-aks\brain\mia_vt" },
    @{ Name="satri-mta"; Path=".\backend-aks\brain\mta" },
    @{ Name="satri-integrations"; Path=".\backend-aks\brain\integrations" },
    @{ Name="satri-dashboard"; Path=".\backend-aks\brain\dashboard-soc" }
)

foreach ($svc in $services) {
    $imageTag = "$ACR_SERVER/$($svc.Name):latest"
    Write-Host "Compilando $($svc.Name)..." -ForegroundColor Yellow
    docker build -t $imageTag $svc.Path
    
    Write-Host "Subiendo $($svc.Name) a ACR..." -ForegroundColor Green
    docker push $imageTag
}

Write-Host "Todas las imágenes han sido subidas a Azure." -ForegroundColor Cyan
