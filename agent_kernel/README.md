# SATRI Kernel-Mode Driver (Fase 4) — Silicon Valley Level

> **Advertencia de Seguridad**: El desarrollo de drivers de kernel es extremadamente delicado.  
> Un solo error de puntero causa un BSOD (pantallazo azul). Usa **siempre** una Máquina Virtual con snapshots.

---

## Arquitectura Ring 0 ↔ Ring 3

```
┌─────────────────────────────────────────────────────────────────┐
│                     SATRI AGENT v3.0 (Ring 3)                   │
│                                                                  │
│  satri_agent.py ──── kernel_bridge.py ─────────────────────┐   │
│       │                    │                                │   │
│  FIM Monitor          ctypes IOCTLs                        │   │
│  Net Monitor        (DeviceIoControl)                      │   │
│  Process Monitor                                           │   │
└──────────────────────────────────────────────────────────────│───┘
                                                              │
              ════════════════════════════════════════════════╪════
              Ring 3 / Ring 0 Boundary (Windows Kernel)      │
              ════════════════════════════════════════════════╪════
                                                              │
┌─────────────────────────────────────────────────────────────│───┐
│                  SatriDriver.sys (Ring 0)                    │   │
│                                                              │   │
│  DriverEntry ──── PsSetCreateProcessNotifyRoutineEx          │   │
│       │                      │                              │   │
│  IoCreateDevice        SatriProcessNotifyCallback ◄─────────┘   │
│       │                      │                                   │
│  IOCTL Dispatch         ┌────┴──────────────────┐               │
│  ├─ GET_EVENTS (0x800)  │ g_EventBuffer[256]    │               │
│  ├─ BLOCK_PID  (0x801)  │ g_BlockedPids[64]     │               │
│  ├─ SET_BLOCKLIST(0x802)│ g_BlockedNames[32]    │               │
│  └─ GET_STATS  (0x803)  └───────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Archivos de la Fase 4

| Archivo | Descripción |
|---------|-------------|
| [`satri_driver.c`](satri_driver.c) | Driver WDM completo (Ring 0). Callbacks de proceso, buffer circular, blocklist de PIDs y nombres. |
| [`satri_driver.inf`](satri_driver.inf) | Metadata de instalación del driver para Windows. |
| [`usermode_client.cpp`](usermode_client.cpp) | Cliente C++ completo para comunicación IOCTL. Modos: events, block, stats, monitor. |
| [`install_driver.ps1`](install_driver.ps1) | Script PowerShell automatizado de instalación/desinstalación/verificación. |
| [`../agent/kernel_bridge.py`](../agent/kernel_bridge.py) | Bridge Python ↔ Kernel via ctypes. Poller de eventos, sincronización de blocklist, fallback gracioso. |
| [`../agent/satri_agent.py`](../agent/satri_agent.py) | Agente v3.0 con integración Fase 4 (`start_kernel_bridge()`). |

---

## IOCTLs del Driver

```c
// Definidos en satri_driver.c y mirrored en usermode_client.cpp / kernel_bridge.py
IOCTL_SATRI_GET_EVENTS    = 0x222000  // Leer hasta 256 eventos del buffer circular
IOCTL_SATRI_BLOCK_PID     = 0x222004  // Agregar PID a la lista de bloqueo
IOCTL_SATRI_SET_BLOCKLIST = 0x222008  // Reemplazar lista de nombres bloqueados
IOCTL_SATRI_GET_STATS     = 0x22200C  // Estadísticas del driver
```

---

## Cómo Compilar el Driver

### Requisitos
1. **Windows 10/11** (nativo, no WSL)
2. **Visual Studio 2022** con la carga de trabajo "Desarrollo para el escritorio con C++"
3. **Windows Driver Kit (WDK)** ([Descargar WDK](https://docs.microsoft.com/windows-hardware/drivers/download-the-wdk))

### Pasos
```
1. Abre Visual Studio 2022
2. Nuevo Proyecto → "Empty WDM Driver" (buscar "WDM")
3. Copia satri_driver.c y satri_driver.inf al proyecto
4. Configura la plataforma: x64
5. Compilar → obtendrás satri_driver.sys
```

### Compilar el cliente C++ (opcional)
```cmd
g++ usermode_client.cpp -o satri_client.exe -std=c++17
:: o con MSVC:
cl.exe usermode_client.cpp /std:c++17 /EHsc /Fe:satri_client.exe
```

---

## Cómo Instalar y Probar el Driver

> [!CAUTION]
> **NUNCA** instales un driver en desarrollo en tu máquina de producción.  
> Un bug de memoria en Ring 0 = **BSOD inmediato**. Usa una VM con snapshots.

### Paso 1 — Preparar la VM

```cmd
:: En la VM (como Administrador), activar Modo de Prueba:
bcdedit /set testsigning on
:: Reiniciar la VM
```

### Paso 2 — Instalar con el script automatizado

```powershell
# Copia satri_driver.sys compilado a agent_kernel\
# Luego ejecuta (como Administrador):
cd C:\Proyecto_Software\agent_kernel
powershell -ExecutionPolicy Bypass -File .\install_driver.ps1 -Mode install
```

O manualmente:
```cmd
sc create SatriDriver type= kernel binPath= "C:\ruta\satri_driver.sys"
sc start SatriDriver
```

### Paso 3 — Verificar el estado

```powershell
.\install_driver.ps1 -Mode status
```

### Paso 4 — Iniciar el agente Python

```bash
cd C:\Proyecto_Software\agent
python satri_agent.py
```

El agente detectará automáticamente el driver y mostrará:
```
[*] Fase 4: Iniciando Kernel-Mode Bridge...
[✓] Ring 0 activo: SatriDriver conectado.
[*] Kernel blocklist sincronizada: 12 apps.
[*] Kernel event poller iniciado.
```

### Paso 5 — Monitorear eventos del kernel con el cliente C++

```cmd
satri_client.exe monitor        # Monitor continuo
satri_client.exe events         # Leer eventos pendientes
satri_client.exe stats          # Ver estadísticas
satri_client.exe block 1234     # Bloquear PID 1234 a nivel kernel
```

### Paso 6 — Ver en el Dashboard SOC

Navega a `http://localhost:8080` → sección **"Ring-0 Agents"** (⚙️ en el sidebar).

---

## Desinstalar

```powershell
.\install_driver.ps1 -Mode uninstall
# o manualmente:
sc stop SatriDriver
sc delete SatriDriver
bcdedit /set testsigning off
# Reiniciar
```

---

## Próximos Pasos (Nivel Producción/Comercial)

Para desplegar en endpoints empresariales **sin** desactivar Secure Boot:

1. **Obtener un Certificado EV Code Signing** (de DigiCert, Sectigo, etc.)
2. **Firmar el driver** con `signtool.exe`
3. **Pasar el Windows Hardware Lab Kit (HLK)**
4. **Enviar a Microsoft** para firma WHQL (Windows Hardware Quality Labs)

Estos pasos permiten que el driver se instale en cualquier Windows moderno sin deshabilitar el arranque seguro.

---

## Bloqueadas por defecto (Blocklist Inicial del Driver)

El driver incluye una blocklist pre-configurada de herramientas de hacking conocidas:

```
mimikatz.exe  nc.exe     netcat.exe  psexec.exe
wce.exe       fgdump.exe procdump.exe
```

Esta lista se **sincroniza automáticamente** desde `config.json → policy.blacklist_apps` cada vez que arranca el agente Python, vía `IOCTL_SATRI_SET_BLOCKLIST`.

---

**Desarrollado como parte de SATRI — Sistema de Análisis y Triage de Incidentes (Silicon Valley Level)**
