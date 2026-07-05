/*
 * satri_driver.c — SATRI EDR Kernel-Mode Driver (Fase 4)
 *
 * Funcionalidades:
 *   1. Callback de creacion/terminacion de procesos (PsSetCreateProcessNotifyRoutineEx).
 *   2. Blocklist de procesos por nombre (configurable via IOCTL desde Ring 3).
 *   3. Buffer circular de eventos accesible desde user-mode via IOCTL.
 *   4. Capacidad de bloquear PIDs especificos bajo demanda.
 *   5. Comunicacion bidireccional segura Ring 0 ↔ Ring 3.
 *
 * IOCTLs expuestos:
 *   IOCTL_SATRI_GET_EVENTS   (0x800) — Leer buffer de eventos del kernel.
 *   IOCTL_SATRI_BLOCK_PID    (0x801) — Agregar PID a la lista de bloqueo.
 *   IOCTL_SATRI_SET_BLOCKLIST(0x802) — Configurar lista de nombres bloqueados.
 *   IOCTL_SATRI_GET_STATS    (0x803) — Obtener estadisticas del driver.
 *
 * Requiere: WDK + Visual Studio 2022 (compilacion nativa x64).
 */

#include <ntddk.h>
#include <wdf.h>
#include <wdm.h>

// ─────────────────────────────────────────────────────────────────────────────
// Constantes y definiciones
// ─────────────────────────────────────────────────────────────────────────────
#define DRIVER_PREFIX       "SatriDriver: "
#define MAX_EVENTS          256     // Tamano del buffer circular de eventos
#define MAX_BLOCKED_NAMES   32      // Maxima cantidad de nombres de proceso bloqueados
#define MAX_BLOCKED_PIDS    64      // Maxima cantidad de PIDs bloqueados puntualmente
#define MAX_PROC_NAME_LEN   64      // Longitud maxima de nombre de proceso (bytes)
#define MAX_PATH_LEN        260     // Longitud maxima de ruta

// Codigos IOCTL
#define IOCTL_SATRI_GET_EVENTS    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SATRI_BLOCK_PID     CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SATRI_SET_BLOCKLIST CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SATRI_GET_STATS     CTL_CODE(FILE_DEVICE_UNKNOWN, 0x803, METHOD_BUFFERED, FILE_ANY_ACCESS)

// ─────────────────────────────────────────────────────────────────────────────
// Estructuras de datos compartidas Ring 0 / Ring 3
// ─────────────────────────────────────────────────────────────────────────────

// Tipo de evento de proceso
typedef enum _SATRI_EVENT_TYPE {
    SATRI_PROCESS_CREATE    = 1,
    SATRI_PROCESS_TERMINATE = 2,
    SATRI_PROCESS_BLOCKED   = 3,
} SATRI_EVENT_TYPE;

// Estructura de un evento (transferida a user-mode)
#pragma pack(push, 1)
typedef struct _SATRI_KERNEL_EVENT {
    SATRI_EVENT_TYPE EventType;
    ULONG            ProcessId;
    ULONG            ParentProcessId;
    CHAR             ImageName[MAX_PATH_LEN];  // Nombre del ejecutable
    LARGE_INTEGER    Timestamp;                // Tiempo del sistema (100ns intervals)
    BOOLEAN          WasBlocked;              // TRUE si el proceso fue bloqueado
} SATRI_KERNEL_EVENT, *PSATRI_KERNEL_EVENT;

// Solicitud de bloqueo de PID (desde user-mode)
typedef struct _SATRI_BLOCK_PID_REQUEST {
    ULONG TargetPid;
} SATRI_BLOCK_PID_REQUEST, *PSATRI_BLOCK_PID_REQUEST;

// Configuracion de blocklist (desde user-mode)
typedef struct _SATRI_BLOCKLIST_CONFIG {
    ULONG EntryCount;
    CHAR  ProcessNames[MAX_BLOCKED_NAMES][MAX_PROC_NAME_LEN];
} SATRI_BLOCKLIST_CONFIG, *PSATRI_BLOCKLIST_CONFIG;

// Estadisticas del driver (retornadas a user-mode)
typedef struct _SATRI_DRIVER_STATS {
    ULONG TotalEventsGenerated;
    ULONG TotalProcessesBlocked;
    ULONG BlockedPidCount;
    ULONG BlocklistNameCount;
    ULONG EventBufferUsed;
} SATRI_DRIVER_STATS, *PSATRI_DRIVER_STATS;
#pragma pack(pop)

// ─────────────────────────────────────────────────────────────────────────────
// Estado global del driver (protegido por spinlock)
// ─────────────────────────────────────────────────────────────────────────────

// Buffer circular de eventos
static SATRI_KERNEL_EVENT g_EventBuffer[MAX_EVENTS];
static ULONG              g_EventHead = 0;    // Posicion de escritura
static ULONG              g_EventTail = 0;    // Posicion de lectura
static ULONG              g_EventCount = 0;   // Cantidad de eventos disponibles
static KSPIN_LOCK         g_EventLock;        // Spinlock para acceso al buffer

// Lista de nombres bloqueados (inmutable desde kernel, configurable via IOCTL)
static CHAR  g_BlockedNames[MAX_BLOCKED_NAMES][MAX_PROC_NAME_LEN];
static ULONG g_BlockedNameCount = 0;
static KSPIN_LOCK g_BlocklistLock;

// Lista de PIDs bloqueados puntualmente
static ULONG g_BlockedPids[MAX_BLOCKED_PIDS];
static ULONG g_BlockedPidCount = 0;
static KSPIN_LOCK g_PidLock;

// Estadisticas atomicas
static volatile LONG g_TotalEventsGenerated = 0;
static volatile LONG g_TotalProcessesBlocked = 0;

// ─────────────────────────────────────────────────────────────────────────────
// Funciones de utilidad internas
// ─────────────────────────────────────────────────────────────────────────────

/*
 * Agrega un evento al buffer circular. Llama desde IRQL <= DISPATCH_LEVEL.
 */
VOID SatriAddEvent(PSATRI_KERNEL_EVENT pEvent) {
    KIRQL oldIrql;
    KeAcquireSpinLock(&g_EventLock, &oldIrql);
    
    g_EventBuffer[g_EventHead] = *pEvent;
    g_EventHead = (g_EventHead + 1) % MAX_EVENTS;
    
    if (g_EventCount < MAX_EVENTS) {
        g_EventCount++;
    } else {
        // Buffer lleno: avanzar el tail (sobreescribir el mas antiguo)
        g_EventTail = (g_EventTail + 1) % MAX_EVENTS;
    }
    
    InterlockedIncrement(&g_TotalEventsGenerated);
    KeReleaseSpinLock(&g_EventLock, oldIrql);
}

/*
 * Extrae TODOS los eventos pendientes del buffer hacia un buffer de usuario.
 * Retorna la cantidad de eventos copiados.
 */
ULONG SatriDrainEvents(PSATRI_KERNEL_EVENT pDest, ULONG MaxCount) {
    KIRQL oldIrql;
    ULONG copied = 0;
    
    KeAcquireSpinLock(&g_EventLock, &oldIrql);
    
    while (g_EventCount > 0 && copied < MaxCount) {
        pDest[copied] = g_EventBuffer[g_EventTail];
        g_EventTail = (g_EventTail + 1) % MAX_EVENTS;
        g_EventCount--;
        copied++;
    }
    
    KeReleaseSpinLock(&g_EventLock, oldIrql);
    return copied;
}

/*
 * Verifica si un nombre de proceso esta en la blocklist.
 * pImageNameAnsi: nombre del ejecutable (solo el basename, ANSI).
 */
BOOLEAN SatriIsNameBlocked(const CHAR* pImageNameAnsi) {
    KIRQL oldIrql;
    BOOLEAN blocked = FALSE;
    
    KeAcquireSpinLock(&g_BlocklistLock, &oldIrql);
    
    for (ULONG i = 0; i < g_BlockedNameCount; i++) {
        // Comparacion case-insensitive manual (no podemos usar CRT en Ring 0)
        const CHAR* a = g_BlockedNames[i];
        const CHAR* b = pImageNameAnsi;
        BOOLEAN match = TRUE;
        while (*a && *b) {
            CHAR ca = (*a >= 'A' && *a <= 'Z') ? (*a + 32) : *a;
            CHAR cb = (*b >= 'A' && *b <= 'Z') ? (*b + 32) : *b;
            if (ca != cb) { match = FALSE; break; }
            a++; b++;
        }
        if (match && *a == '\0' && *b == '\0') {
            blocked = TRUE;
            break;
        }
    }
    
    KeReleaseSpinLock(&g_BlocklistLock, oldIrql);
    return blocked;
}

/*
 * Verifica si un PID esta en la lista de bloqueo por ID.
 */
BOOLEAN SatriIsPidBlocked(ULONG Pid) {
    KIRQL oldIrql;
    BOOLEAN blocked = FALSE;
    
    KeAcquireSpinLock(&g_PidLock, &oldIrql);
    for (ULONG i = 0; i < g_BlockedPidCount; i++) {
        if (g_BlockedPids[i] == Pid) { blocked = TRUE; break; }
    }
    KeReleaseSpinLock(&g_PidLock, oldIrql);
    return blocked;
}

/*
 * Extrae el basename (solo el nombre del exe) de una ruta Unicode.
 * Copia el resultado como ANSI a pOut (MAX_PATH_LEN bytes max).
 */
VOID SatriExtractBasename(PUNICODE_STRING pFull, CHAR* pOut, ULONG MaxLen) {
    if (!pFull || !pFull->Buffer || pFull->Length == 0) {
        pOut[0] = '\0';
        return;
    }
    
    // Buscar la ultima barra invertida
    WCHAR* start = pFull->Buffer;
    WCHAR* p = start + (pFull->Length / sizeof(WCHAR)) - 1;
    
    while (p > start && *p != L'\\' && *p != L'/') p--;
    if (*p == L'\\' || *p == L'/') p++;
    
    // Convertir WCHAR → CHAR (solo ASCII)
    ULONG i = 0;
    while (*p && i < MaxLen - 1) {
        pOut[i++] = (CHAR)(*p++ & 0xFF);
    }
    pOut[i] = '\0';
}

// ─────────────────────────────────────────────────────────────────────────────
// Callback de notificacion de procesos (Ring 0)
// ─────────────────────────────────────────────────────────────────────────────
VOID SatriProcessNotifyCallback(
    _Inout_ PEPROCESS Process,
    _In_ HANDLE ProcessId,
    _In_opt_ PPS_CREATE_NOTIFY_INFO CreateInfo
) {
    UNREFERENCED_PARAMETER(Process);
    ULONG pid = HandleToULong(ProcessId);
    
    SATRI_KERNEL_EVENT evt;
    RtlZeroMemory(&evt, sizeof(evt));
    evt.ProcessId = pid;
    KeQuerySystemTime(&evt.Timestamp);
    
    if (CreateInfo != NULL) {
        // ── Proceso siendo creado ──
        evt.EventType = SATRI_PROCESS_CREATE;
        evt.ParentProcessId = HandleToULong(CreateInfo->ParentProcessId);
        
        // Extraer nombre del ejecutable
        if (CreateInfo->ImageFileName) {
            SatriExtractBasename(CreateInfo->ImageFileName, evt.ImageName, sizeof(evt.ImageName));
        }
        
        // ── Verificar blocklist ──
        BOOLEAN shouldBlock = FALSE;
        
        // Por nombre de proceso
        if (evt.ImageName[0] != '\0' && SatriIsNameBlocked(evt.ImageName)) {
            shouldBlock = TRUE;
        }
        
        // Por PID (solicitud explícita del agente user-mode)
        if (!shouldBlock && SatriIsPidBlocked(pid)) {
            shouldBlock = TRUE;
        }
        
        if (shouldBlock) {
            CreateInfo->CreationStatus = STATUS_ACCESS_DENIED;
            evt.EventType  = SATRI_PROCESS_BLOCKED;
            evt.WasBlocked = TRUE;
            InterlockedIncrement(&g_TotalProcessesBlocked);
            KdPrint((DRIVER_PREFIX "BLOCKED PID=%u (%s)\n", pid, evt.ImageName));
        } else {
            evt.WasBlocked = FALSE;
            KdPrint((DRIVER_PREFIX "CREATE PID=%u (%s) PPID=%u\n",
                pid, evt.ImageName, evt.ParentProcessId));
        }
        
    } else {
        // ── Proceso siendo destruido ──
        evt.EventType = SATRI_PROCESS_TERMINATE;
        evt.WasBlocked = FALSE;
        KdPrint((DRIVER_PREFIX "TERMINATE PID=%u\n", pid));
    }
    
    // Guardar en buffer circular
    SatriAddEvent(&evt);
}

// ─────────────────────────────────────────────────────────────────────────────
// Handler de IOCTLs (Ring 3 → Ring 0)
// ─────────────────────────────────────────────────────────────────────────────
NTSTATUS SatriDeviceControl(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_ PIRP Irp
) {
    UNREFERENCED_PARAMETER(DeviceObject);
    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
    NTSTATUS status = STATUS_SUCCESS;
    ULONG bytesIO = 0;
    
    ULONG ctlCode   = stack->Parameters.DeviceIoControl.IoControlCode;
    ULONG inBufLen  = stack->Parameters.DeviceIoControl.InputBufferLength;
    ULONG outBufLen = stack->Parameters.DeviceIoControl.OutputBufferLength;
    PVOID buffer    = Irp->AssociatedIrp.SystemBuffer; // METHOD_BUFFERED

    switch (ctlCode) {

    // ── GET_EVENTS: Transferir buffer de eventos al user-mode ──
    case IOCTL_SATRI_GET_EVENTS: {
        ULONG maxEvents = outBufLen / sizeof(SATRI_KERNEL_EVENT);
        if (maxEvents == 0) {
            status = STATUS_BUFFER_TOO_SMALL;
            break;
        }
        ULONG drained = SatriDrainEvents((PSATRI_KERNEL_EVENT)buffer, maxEvents);
        bytesIO = drained * sizeof(SATRI_KERNEL_EVENT);
        KdPrint((DRIVER_PREFIX "GET_EVENTS → %u eventos enviados\n", drained));
        break;
    }
    
    // ── BLOCK_PID: Agregar un PID a la lista de bloqueo immediato ──
    case IOCTL_SATRI_BLOCK_PID: {
        if (inBufLen < sizeof(SATRI_BLOCK_PID_REQUEST)) {
            status = STATUS_INVALID_BUFFER_SIZE;
            break;
        }
        PSATRI_BLOCK_PID_REQUEST req = (PSATRI_BLOCK_PID_REQUEST)buffer;
        KIRQL oldIrql;
        KeAcquireSpinLock(&g_PidLock, &oldIrql);
        if (g_BlockedPidCount < MAX_BLOCKED_PIDS) {
            g_BlockedPids[g_BlockedPidCount++] = req->TargetPid;
            KdPrint((DRIVER_PREFIX "BLOCK_PID: PID %u agregado a blocklist\n", req->TargetPid));
        } else {
            status = STATUS_INSUFFICIENT_RESOURCES;
        }
        KeReleaseSpinLock(&g_PidLock, oldIrql);
        break;
    }
    
    // ── SET_BLOCKLIST: Reemplazar la lista de nombres bloqueados ──
    case IOCTL_SATRI_SET_BLOCKLIST: {
        if (inBufLen < sizeof(SATRI_BLOCKLIST_CONFIG)) {
            status = STATUS_INVALID_BUFFER_SIZE;
            break;
        }
        PSATRI_BLOCKLIST_CONFIG cfg = (PSATRI_BLOCKLIST_CONFIG)buffer;
        ULONG count = cfg->EntryCount;
        if (count > MAX_BLOCKED_NAMES) count = MAX_BLOCKED_NAMES;
        
        KIRQL oldIrql;
        KeAcquireSpinLock(&g_BlocklistLock, &oldIrql);
        g_BlockedNameCount = 0;
        for (ULONG i = 0; i < count; i++) {
            RtlCopyMemory(g_BlockedNames[i], cfg->ProcessNames[i], MAX_PROC_NAME_LEN - 1);
            g_BlockedNames[i][MAX_PROC_NAME_LEN - 1] = '\0';
            g_BlockedNameCount++;
            KdPrint((DRIVER_PREFIX "SET_BLOCKLIST: '%s' agregado\n", g_BlockedNames[i]));
        }
        KeReleaseSpinLock(&g_BlocklistLock, oldIrql);
        break;
    }
    
    // ── GET_STATS: Retornar estadisticas del driver ──
    case IOCTL_SATRI_GET_STATS: {
        if (outBufLen < sizeof(SATRI_DRIVER_STATS)) {
            status = STATUS_BUFFER_TOO_SMALL;
            break;
        }
        PSATRI_DRIVER_STATS stats = (PSATRI_DRIVER_STATS)buffer;
        stats->TotalEventsGenerated  = (ULONG)InterlockedCompareExchange(&g_TotalEventsGenerated, 0, -1) + 1;
        stats->TotalProcessesBlocked = (ULONG)InterlockedCompareExchange(&g_TotalProcessesBlocked, 0, -1) + 1;
        stats->BlockedPidCount       = g_BlockedPidCount;
        stats->BlocklistNameCount    = g_BlockedNameCount;
        stats->EventBufferUsed       = g_EventCount;
        bytesIO = sizeof(SATRI_DRIVER_STATS);
        break;
    }
    
    default:
        status = STATUS_INVALID_DEVICE_REQUEST;
        break;
    }

    Irp->IoStatus.Status = status;
    Irp->IoStatus.Information = bytesIO;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return status;
}

// ─────────────────────────────────────────────────────────────────────────────
// Handlers Create / Close (requeridos por el sistema)
// ─────────────────────────────────────────────────────────────────────────────
NTSTATUS SatriCreateClose(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_ PIRP Irp
) {
    UNREFERENCED_PARAMETER(DeviceObject);
    Irp->IoStatus.Status = STATUS_SUCCESS;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

// ─────────────────────────────────────────────────────────────────────────────
// Driver Unload (limpieza de recursos)
// ─────────────────────────────────────────────────────────────────────────────
VOID SatriDriverUnload(_In_ PDRIVER_OBJECT DriverObject) {
    KdPrint((DRIVER_PREFIX "Descargando driver...\n"));
    
    // Eliminar el callback de procesos ANTES de cualquier otra limpieza
    PsSetCreateProcessNotifyRoutineEx(SatriProcessNotifyCallback, TRUE);
    KdPrint((DRIVER_PREFIX "Callback de procesos eliminado.\n"));
    
    // Eliminar enlace simbolico y dispositivo
    UNICODE_STRING symLink;
    RtlInitUnicodeString(&symLink, L"\\DosDevices\\SatriDriver");
    IoDeleteSymbolicLink(&symLink);
    IoDeleteDevice(DriverObject->DeviceObject);
    KdPrint((DRIVER_PREFIX "Driver descargado limpiamente.\n"));
}

// ─────────────────────────────────────────────────────────────────────────────
// DriverEntry — Punto de entrada del driver
// ─────────────────────────────────────────────────────────────────────────────
NTSTATUS DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath
) {
    UNREFERENCED_PARAMETER(RegistryPath);
    KdPrint((DRIVER_PREFIX "=== SATRI EDR Kernel Driver v1.1 cargando ===\n"));
    
    // Inicializar spinlocks
    KeInitializeSpinLock(&g_EventLock);
    KeInitializeSpinLock(&g_BlocklistLock);
    KeInitializeSpinLock(&g_PidLock);
    
    // Inicializar buffers
    RtlZeroMemory(g_EventBuffer, sizeof(g_EventBuffer));
    RtlZeroMemory(g_BlockedNames, sizeof(g_BlockedNames));
    RtlZeroMemory(g_BlockedPids, sizeof(g_BlockedPids));
    
    // Poblar blocklist por defecto (herramientas de hacking comunes)
    const CHAR* defaultBlocklist[] = {
        "mimikatz.exe", "nc.exe", "netcat.exe", "psexec.exe",
        "wce.exe", "fgdump.exe", "procdump.exe"
    };
    g_BlockedNameCount = 0;
    for (ULONG i = 0; i < sizeof(defaultBlocklist)/sizeof(defaultBlocklist[0]); i++) {
        const CHAR* name = defaultBlocklist[i];
        ULONG len = 0;
        while (name[len]) len++;
        if (len < MAX_PROC_NAME_LEN) {
            RtlCopyMemory(g_BlockedNames[g_BlockedNameCount], name, len + 1);
            g_BlockedNameCount++;
        }
    }
    KdPrint((DRIVER_PREFIX "Blocklist inicial: %u entradas\n", g_BlockedNameCount));
    
    // Configurar dispatch routines
    DriverObject->DriverUnload                          = SatriDriverUnload;
    DriverObject->MajorFunction[IRP_MJ_CREATE]         = SatriCreateClose;
    DriverObject->MajorFunction[IRP_MJ_CLOSE]          = SatriCreateClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = SatriDeviceControl;
    
    // Crear objeto de dispositivo
    UNICODE_STRING devName, symLink;
    RtlInitUnicodeString(&devName,  L"\\Device\\SatriDriver");
    RtlInitUnicodeString(&symLink, L"\\DosDevices\\SatriDriver");
    
    PDEVICE_OBJECT deviceObject = NULL;
    NTSTATUS status = IoCreateDevice(
        DriverObject,
        0,
        &devName,
        FILE_DEVICE_UNKNOWN,
        FILE_DEVICE_SECURE_OPEN,
        FALSE,
        &deviceObject
    );
    
    if (!NT_SUCCESS(status)) {
        KdPrint((DRIVER_PREFIX "Error creando dispositivo: 0x%08X\n", status));
        return status;
    }
    
    // Crear enlace simbolico accesible desde user-mode
    status = IoCreateSymbolicLink(&symLink, &devName);
    if (!NT_SUCCESS(status)) {
        KdPrint((DRIVER_PREFIX "Error creando symbolic link: 0x%08X\n", status));
        IoDeleteDevice(deviceObject);
        return status;
    }
    
    // Habilitar acceso de buffer directo para IOCTLs METHOD_BUFFERED
    deviceObject->Flags |= DO_BUFFERED_IO;
    deviceObject->Flags &= ~DO_DEVICE_INITIALIZING;
    
    // Registrar callback de notificacion de procesoshttp://localhost:3000/
    status = PsSetCreateProcessNotifyRoutineEx(SatriProcessNotifyCallback, FALSE);
    if (!NT_SUCCESS(status)) {
        KdPrint((DRIVER_PREFIX "Error registrando callback de procesos: 0x%08X\n", status));
        IoDeleteSymbolicLink(&symLink);
        IoDeleteDevice(deviceObject);
        return status;
    }
    
    KdPrint((DRIVER_PREFIX "=== Driver inicializado correctamente. Device: \\Device\\SatriDriver ===\n"));
    return STATUS_SUCCESS;
}
