#Requires -RunAsAdministrator
<#
.SYNOPSIS
    install_driver.ps1  Script de instalacion del SATRI Kernel-Mode Driver

.DESCRIPTION
    Automatiza la carga y configuracion del SatriDriver.sys en un entorno
    de prueba (requiere Modo de Prueba activo) o en produccion (requiere
    firma EV de Microsoft).

    Pasos que realiza:
      1. Verifica que se ejecuta como Administrador.
      2. Verifica que el archivo satri_driver.sys existe.
      3. Crea el servicio de kernel (sc create).
      4. Inicia el servicio (sc start).
      5. Verifica que el dispositivo \\.\\SatriDriver es accesible.

.PARAMETER DriverPath
    Ruta al archivo satri_driver.sys compilado.
    Default: .\satri_driver.sys (en el directorio actual)

.PARAMETER Mode
    'install'   -> Instalar y arrancar el driver
    'uninstall' -> Detener y eliminar el driver
    'status'    -> Solo verificar el estado actual

.EXAMPLE
    # Instalar (desde el directorio agent_kernel\ despues de compilar):
    .\install_driver.ps1 -Mode install

    # Verificar estado:
    .\install_driver.ps1 -Mode status

    # Desinstalar:
    .\install_driver.ps1 -Mode uninstall
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$DriverPath = ".\satri_driver.sys",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("install", "uninstall", "status")]
    [string]$Mode = "status"
)

# -----------------------------------------------------------------------------
# Constantes
# -----------------------------------------------------------------------------
$SERVICE_NAME = "SatriDriver"
$SERVICE_DISPLAY = "SATRI EDR Kernel Mode Driver"
$DEVICE_PATH = "\\.\SatriDriver"

# -----------------------------------------------------------------------------
# Funciones de utilidad
# -----------------------------------------------------------------------------
function Write-Header {
    Write-Host ""
    Write-Host "+----------------------------------------------+" -ForegroundColor Cyan
    Write-Host "|  SATRI Kernel Driver Installer v1.1          |" -ForegroundColor Cyan
    Write-Host "|  Ring-0 Protection Layer  Phase 4           |" -ForegroundColor Cyan
    Write-Host "+----------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Status($msg, $color = "White") {
    Write-Host "  [*] $msg" -ForegroundColor $color
}

function Write-OK($msg) {
    Write-Host "  [[OK]] $msg" -ForegroundColor Green
}

function Write-Fail($msg) {
    Write-Host "  [[FAIL]] $msg" -ForegroundColor Red
}

function Write-Warn($msg) {
    Write-Host "  [!] $msg" -ForegroundColor Yellow
}

function Test-AdminPrivileges {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal] $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-TestSigningMode {
    try {
        $output = & bcdedit /enum current 2>&1 | Out-String
        return $output -match "testsigning\s+Yes"
    } catch {
        return $false
    }
}

function Get-ServiceStatus {
    try {
        $svc = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
        if ($null -eq $svc) { return "NotInstalled" }
        return $svc.Status.ToString()
    } catch {
        return "NotInstalled"
    }
}

function Test-DeviceAccessible {
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class Win32 {
        [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        public static extern IntPtr CreateFile(string lpFileName, uint dwAccess,
            uint dwShare, IntPtr sec, uint dwCreationDisposition,
            uint dwFlags, IntPtr hTemplate);
        [DllImport("kernel32.dll")]
        public static extern bool CloseHandle(IntPtr hObject);
    }
"@ -ErrorAction SilentlyContinue

    try {
        $handle = [Win32]::CreateFile($DEVICE_PATH, 0xC0000000, 0, [IntPtr]::Zero, 3, 0, [IntPtr]::Zero)
        if ($handle -ne [IntPtr]::new(-1)) {
            [Win32]::CloseHandle($handle) | Out-Null
            return $true
        }
    } catch {}
    return $false
}

# -----------------------------------------------------------------------------
# Acciones
# -----------------------------------------------------------------------------

function Invoke-Status {
    Write-Status "Verificando estado del SATRI Kernel Driver..."
    Write-Host ""
    
    # Admin
    if (Test-AdminPrivileges) {
        Write-OK "Privilegios de Administrador: Si"
    } else {
        Write-Warn "Privilegios de Administrador: No (se requiere para cargar drivers)"
    }
    
    # Test Signing Mode
    if (Test-TestSigningMode) {
        Write-Warn "Modo de Prueba (TestSigning): ACTIVO <- OK para desarrollo"
    } else {
        Write-Status "Modo de Prueba (TestSigning): Inactivo (produccion requiere firma EV)"
    }
    
    # Servicio
    $svcStatus = Get-ServiceStatus
    switch ($svcStatus) {
        "Running"      { Write-OK "Servicio SatriDriver: En ejecucion [OK]" }
        "Stopped"      { Write-Warn "Servicio SatriDriver: Detenido" }
        "NotInstalled" { Write-Fail "Servicio SatriDriver: No instalado" }
        default        { Write-Warn "Servicio SatriDriver: $svcStatus" }
    }
    
    # Dispositivo
    if (Test-DeviceAccessible) {
        Write-OK "Dispositivo \\.\\SatriDriver: Accesible (Ring-0 activo) [OK]"
    } else {
        Write-Fail "Dispositivo \\.\\SatriDriver: No accesible"
    }
    
    Write-Host ""
}

function Invoke-Install {
    Write-Status "Iniciando instalacion del SATRI Kernel Driver..."
    Write-Host ""
    
    # Verificar admin
    if (-not (Test-AdminPrivileges)) {
        Write-Fail "Se requiere ejecutar como Administrador."
        exit 1
    }
    Write-OK "Privilegios de Administrador confirmados."
    
    # Verificar TestSigning
    if (-not (Test-TestSigningMode)) {
        Write-Warn "ADVERTENCIA: Test Signing Mode NO esta activo."
        Write-Warn "El driver no firmado digitalmente sera rechazado por Windows."
        Write-Host ""
        Write-Host "  Para activar el Modo de Prueba:" -ForegroundColor Yellow
        Write-Host "    bcdedit /set testsigning on" -ForegroundColor Cyan
        Write-Host "    (Luego reiniciar la maquina)" -ForegroundColor Cyan
        Write-Host ""
        Write-Warn "NUNCA actives TestSigning en una maquina de produccion."
        Write-Host ""
        $confirm = Read-Host "  Continuar de todas formas? (s/N)"
        if ($confirm -ne 's' -and $confirm -ne 'S') {
            Write-Status "Instalacion cancelada."
            exit 0
        }
    } else {
        Write-OK "Test Signing Mode: Activo."
    }
    
    # Verificar que el .sys existe
    $absDriverPath = Resolve-Path $DriverPath -ErrorAction SilentlyContinue
    if (-not $absDriverPath -or -not (Test-Path $absDriverPath)) {
        Write-Fail "No se encontro el archivo del driver: $DriverPath"
        Write-Host ""
        Write-Host "  Para compilar el driver:" -ForegroundColor Yellow
        Write-Host "    1. Abre Visual Studio 2022 con el WDK instalado." -ForegroundColor Cyan
        Write-Host "    2. Crea un proyecto 'Empty WDM Driver'." -ForegroundColor Cyan
        Write-Host "    3. Copia satri_driver.c en el proyecto." -ForegroundColor Cyan
        Write-Host "    4. Compila para x64 -> obtendras satri_driver.sys" -ForegroundColor Cyan
        exit 1
    }
    Write-OK "Driver encontrado: $absDriverPath"
    
    # Verificar si ya existe el servicio
    $svcStatus = Get-ServiceStatus
    if ($svcStatus -ne "NotInstalled") {
        Write-Warn "El servicio ya existe (estado: $svcStatus). Deteniendo..."
        Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
        & sc.exe delete $SERVICE_NAME | Out-Null
        Start-Sleep -Seconds 1
    }
    
    # Crear el servicio de kernel
    Write-Status "Creando servicio de kernel..."
    $result = & sc.exe create $SERVICE_NAME type= kernel start= demand error= normal `
        binPath= "$absDriverPath" DisplayName= "$SERVICE_DISPLAY" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Error creando el servicio: $result"
        exit 1
    }
    Write-OK "Servicio '$SERVICE_NAME' creado."
    
    # Iniciar el driver
    Write-Status "Iniciando el driver (sc start)..."
    $result = & sc.exe start $SERVICE_NAME 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Error iniciando el driver: $result"
        Write-Warn "Verifica DebugView (Sysinternals) para mensajes del kernel."
        exit 1
    }
    Write-OK "Driver iniciado correctamente."
    
    # Verificar acceso al dispositivo
    Start-Sleep -Seconds 1
    if (Test-DeviceAccessible) {
        Write-OK "Dispositivo \\.\\SatriDriver accesible desde user-mode. [OK]"
    } else {
        Write-Warn "El dispositivo no es accesible aun. Puede necesitar unos segundos."
    }
    
    Write-Host ""
    Write-Host "  +---------------------------------------+" -ForegroundColor Green
    Write-Host "  |  SATRI Ring-0 Protection: ACTIVA  [SHIELD]  |" -ForegroundColor Green
    Write-Host "  +---------------------------------------+" -ForegroundColor Green
    Write-Host ""
    Write-Status "Ahora puedes iniciar el agente Python:"
    Write-Host "    python satri_agent.py" -ForegroundColor Cyan
    Write-Host ""
}

function Invoke-Uninstall {
    Write-Status "Desinstalando SATRI Kernel Driver..."
    Write-Host ""
    
    if (-not (Test-AdminPrivileges)) {
        Write-Fail "Se requiere ejecutar como Administrador."
        exit 1
    }
    
    $svcStatus = Get-ServiceStatus
    if ($svcStatus -eq "NotInstalled") {
        Write-Warn "El servicio '$SERVICE_NAME' no esta instalado."
        return
    }
    
    # Detener el servicio
    Write-Status "Deteniendo el servicio..."
    Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    Write-OK "Servicio detenido."
    
    # Eliminar el servicio
    Write-Status "Eliminando el servicio del registro..."
    & sc.exe delete $SERVICE_NAME | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Servicio '$SERVICE_NAME' eliminado."
    } else {
        Write-Warn "No se pudo eliminar el servicio (puede requerir reinicio)."
    }
    
    Write-Host ""
    Write-OK "Desinstalacion completada. Reinicia si el servicio persiste."
    Write-Host ""
}

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
Write-Header

switch ($Mode) {
    "install"   { Invoke-Install }
    "uninstall" { Invoke-Uninstall }
    "status"    { Invoke-Status }
}
