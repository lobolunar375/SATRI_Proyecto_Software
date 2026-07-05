"""
kernel_bridge.py — SATRI Kernel-Mode Driver Bridge (Fase 4)

Este módulo actúa como el puente entre el agente Python (Ring 3, user-space)
y el driver del kernel de SATRI (satri_driver.sys, Ring 0).

Funcionalidades:
  1. Detectar si el driver está cargado en el sistema.
  2. Enviar IOCTLs al driver:
       - GET_EVENTS     → leer buffer de eventos del kernel.
       - BLOCK_PID      → bloquear un PID específico a nivel kernel.
       - SET_BLOCKLIST  → actualizar la blocklist del driver.
       - GET_STATS      → consultar estadísticas del driver.
  3. Poller en hilo separado que lee eventos del kernel y los reenvía al SATRI MML.
  4. Fallback gracioso cuando el driver NO está disponible (modo user-space puro).

Nota:
  Esta integración usa ctypes para llamadas directas a la Windows API
  (CreateFile, DeviceIoControl, CloseHandle) sin dependencias externas extra.
  Solo requiere Python en Windows. Sin driver → modo pasivo (no falla).
"""

import ctypes
import ctypes.wintypes
import struct
import threading
import time
import json
import os
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional, Callable

# ─────────────────────────────────────────────────────────────────────────────
# Constantes IOCTL (deben coincidir con satri_driver.c)
# ─────────────────────────────────────────────────────────────────────────────

FILE_DEVICE_UNKNOWN      = 0x00000022
METHOD_BUFFERED          = 0
FILE_ANY_ACCESS          = 0

def _ctl_code(device_type, function, method, access):
    return (device_type << 16) | (access << 14) | (function << 2) | method

IOCTL_SATRI_GET_EVENTS    = _ctl_code(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
IOCTL_SATRI_BLOCK_PID     = _ctl_code(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
IOCTL_SATRI_SET_BLOCKLIST = _ctl_code(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)
IOCTL_SATRI_GET_STATS     = _ctl_code(FILE_DEVICE_UNKNOWN, 0x803, METHOD_BUFFERED, FILE_ANY_ACCESS)

# Limites (deben coincidir con el driver)
MAX_EVENTS        = 256
MAX_BLOCKED_NAMES = 32
MAX_PROC_NAME_LEN = 64
MAX_PATH_LEN      = 260

# Windows API constants
GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Set up kernel32 function signatures for 64-bit compatibility
_kernel32 = ctypes.windll.kernel32

_kernel32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR,  # lpFileName
    ctypes.wintypes.DWORD,    # dwDesiredAccess
    ctypes.wintypes.DWORD,    # dwShareMode
    ctypes.c_void_p,          # lpSecurityAttributes
    ctypes.wintypes.DWORD,    # dwCreationDisposition
    ctypes.wintypes.DWORD,    # dwFlagsAndAttributes
    ctypes.wintypes.HANDLE    # hTemplateFile
]
_kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE

_kernel32.CloseHandle.argtypes = [
    ctypes.wintypes.HANDLE    # hObject
]
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL

_kernel32.DeviceIoControl.argtypes = [
    ctypes.wintypes.HANDLE,   # hDevice
    ctypes.wintypes.DWORD,    # dwIoControlCode
    ctypes.c_void_p,          # lpInBuffer
    ctypes.wintypes.DWORD,    # nInBufferSize
    ctypes.c_void_p,          # lpOutBuffer
    ctypes.wintypes.DWORD,    # nOutBufferSize
    ctypes.c_void_p,          # lpBytesReturned
    ctypes.c_void_p           # lpOverlapped
]
_kernel32.DeviceIoControl.restype = ctypes.wintypes.BOOL

# ─────────────────────────────────────────────────────────────────────────────
# Estructuras ctypes (espejo de las estructuras C del driver)
# ─────────────────────────────────────────────────────────────────────────────

class LARGE_INTEGER(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("QuadPart", ctypes.c_int64)]


class SatriKernelEvent(ctypes.Structure):
    """Espejo de SATRI_KERNEL_EVENT en satri_driver.c"""
    _pack_ = 1
    _fields_ = [
        ("EventType",        ctypes.c_uint32),
        ("ProcessId",        ctypes.c_uint32),
        ("ParentProcessId",  ctypes.c_uint32),
        ("ImageName",        ctypes.c_char * MAX_PATH_LEN),
        ("Timestamp",        LARGE_INTEGER),
        ("WasBlocked",       ctypes.c_bool),
    ]


class SatriBlockPidRequest(ctypes.Structure):
    """Espejo de SATRI_BLOCK_PID_REQUEST en satri_driver.c"""
    _pack_ = 1
    _fields_ = [("TargetPid", ctypes.c_uint32)]


class SatriBlocklistConfig(ctypes.Structure):
    """Espejo de SATRI_BLOCKLIST_CONFIG en satri_driver.c"""
    _pack_ = 1
    _fields_ = [
        ("EntryCount",    ctypes.c_uint32),
        ("ProcessNames",  (ctypes.c_char * MAX_PROC_NAME_LEN) * MAX_BLOCKED_NAMES),
    ]


class SatriDriverStats(ctypes.Structure):
    """Espejo de SATRI_DRIVER_STATS en satri_driver.c"""
    _pack_ = 1
    _fields_ = [
        ("TotalEventsGenerated",  ctypes.c_uint32),
        ("TotalProcessesBlocked", ctypes.c_uint32),
        ("BlockedPidCount",       ctypes.c_uint32),
        ("BlocklistNameCount",    ctypes.c_uint32),
        ("EventBufferUsed",       ctypes.c_uint32),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tipos de eventos del driver
# ─────────────────────────────────────────────────────────────────────────────

EVENT_TYPE_NAMES = {
    1: "PROCESS_CREATE",
    2: "PROCESS_TERMINATE",
    3: "PROCESS_BLOCKED",
}


@dataclass
class KernelEvent:
    """Representación Python de un evento del kernel."""
    event_type:   str
    pid:          int
    ppid:         int
    image_name:   str
    was_blocked:  bool
    source:       str = "kernel_driver"
    
    def to_satri_log(self, hostname: str = "", src_ip: str = "") -> dict:
        """Convierte el evento a formato compatible con SATRI MML."""
        return {
            "message": (
                f"KERNEL [{self.event_type}]: Process '{self.image_name}' "
                f"(PID:{self.pid}, PPID:{self.ppid})"
                + (" ← BLOQUEADO" if self.was_blocked else "")
            ),
            "event_type": f"kernel_{self.event_type.lower()}",
            "source":     f"kernel_driver_{hostname}",
            "src_ip":     src_ip,
            "metadata": {
                "pid":         self.pid,
                "ppid":        self.ppid,
                "image":       self.image_name,
                "was_blocked": self.was_blocked,
                "kernel_level": True,
            }
        }


# ─────────────────────────────────────────────────────────────────────────────
# Clase principal: SatriKernelBridge
# ─────────────────────────────────────────────────────────────────────────────

class SatriKernelBridge:
    """
    Puente entre el agente Python (user-space) y el SatriDriver (kernel-space).
    
    Uso:
        bridge = SatriKernelBridge()
        if bridge.connect():
            bridge.start_event_poller(callback=send_to_satri)
            bridge.block_pid(1234)
            stats = bridge.get_stats()
    """
    
    DEVICE_PATH = r"\\.\SatriDriver"
    POLL_INTERVAL = 2.0  # segundos entre lecturas del buffer del kernel
    
    def __init__(self):
        self._handle = None
        self._connected = False
        self._poller_thread: Optional[threading.Thread] = None
        self._poller_running = False
        self._kernel32 = ctypes.windll.kernel32
        self._log = logging.getLogger("SatriKernelBridge")
        
    # ── Conexión ──────────────────────────────────────────────────────────────
    
    def connect(self) -> bool:
        """Abre handle al driver del kernel. Retorna True si tuvo éxito."""
        try:
            handle = self._kernel32.CreateFileW(
                self.DEVICE_PATH,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            
            if handle == INVALID_HANDLE_VALUE or handle is None or handle == 0:
                err = self._kernel32.GetLastError()
                self._log.warning(
                    f"[KernelBridge] Driver no disponible (código: {err}). "
                    f"Modo user-space activo."
                )
                self._connected = False
                return False
            
            self._handle = handle
            self._connected = True
            self._log.info("[KernelBridge] [OK] Conectado al SatriDriver (Ring 0).")
            return True
            
        except Exception as e:
            self._log.warning(f"[KernelBridge] Error de conexión: {e}. Modo user-space activo.")
            self._connected = False
            return False
    
    def disconnect(self):
        """Cierra el handle al driver."""
        self._stop_poller()
        if self._handle:
            try:
                self._kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None
            self._connected = False
            self._log.info("[KernelBridge] Desconectado del driver.")
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._handle is not None
    
    # ── Comunicación IOCTL ────────────────────────────────────────────────────
    
    def _ioctl(self, code: int, in_buf=None, out_buf=None) -> int:
        """
        Wrapper genérico para DeviceIoControl.
        Retorna bytes_returned, o -1 si hay error.
        """
        if not self.is_connected:
            return -1
        
        bytes_returned = ctypes.c_ulong(0)
        
        in_ptr  = ctypes.addressof(in_buf)  if in_buf  else None
        in_size = ctypes.sizeof(in_buf)     if in_buf  else 0
        out_ptr = ctypes.addressof(out_buf) if out_buf else None
        out_size = ctypes.sizeof(out_buf)   if out_buf else 0
        
        ok = self._kernel32.DeviceIoControl(
            self._handle,
            code,
            in_ptr,  in_size,
            out_ptr, out_size,
            ctypes.addressof(bytes_returned),
            None
        )
        
        if not ok:
            err = self._kernel32.GetLastError()
            # ERROR_INSUFFICIENT_BUFFER (122) es esperado cuando el buffer está vacío
            if err not in (122, 0):
                self._log.debug(f"[KernelBridge] IOCTL 0x{code:X} → error {err}")
            return -1
        
        return bytes_returned.value
    
    def get_events(self) -> List[KernelEvent]:
        """Lee y vacía el buffer de eventos del kernel."""
        if not self.is_connected:
            return []
        
        # Crear buffer de salida para MAX_EVENTS eventos
        EventArray = SatriKernelEvent * MAX_EVENTS
        out_buf = EventArray()
        
        returned = self._ioctl(IOCTL_SATRI_GET_EVENTS, out_buf=out_buf)
        if returned <= 0:
            return []
        
        count = returned // ctypes.sizeof(SatriKernelEvent)
        events = []
        
        for i in range(count):
            raw = out_buf[i]
            evt = KernelEvent(
                event_type  = EVENT_TYPE_NAMES.get(raw.EventType, "UNKNOWN"),
                pid         = raw.ProcessId,
                ppid        = raw.ParentProcessId,
                image_name  = raw.ImageName.decode("utf-8", errors="replace").rstrip('\x00'),
                was_blocked = bool(raw.WasBlocked),
            )
            events.append(evt)
        
        return events
    
    def block_pid(self, pid: int) -> bool:
        """Instruye al driver a bloquear un PID específico (matará su próxima creación)."""
        if not self.is_connected:
            self._log.warning(f"[KernelBridge] No conectado → no se puede bloquear PID {pid} a nivel kernel.")
            return False
        
        req = SatriBlockPidRequest(TargetPid=ctypes.c_uint32(pid))
        returned = self._ioctl(IOCTL_SATRI_BLOCK_PID, in_buf=req)
        
        if returned >= 0:
            self._log.info(f"[KernelBridge] [SHIELD] PID {pid} agregado a blocklist del kernel.")
            return True
        return False
    
    def set_blocklist(self, process_names: List[str]) -> bool:
        """
        Reemplaza la blocklist de nombres del driver.
        
        Args:
            process_names: Lista de nombres de ejecutables (ej: ["mimikatz.exe", "nc.exe"])
        """
        if not self.is_connected:
            return False
        
        cfg = SatriBlocklistConfig()
        count = min(len(process_names), MAX_BLOCKED_NAMES)
        cfg.EntryCount = count
        
        for i, name in enumerate(process_names[:count]):
            encoded = name.encode("ascii", errors="replace")[:MAX_PROC_NAME_LEN - 1]
            cfg.ProcessNames[i] = (ctypes.c_char * MAX_PROC_NAME_LEN)(*encoded, 0)
        
        returned = self._ioctl(IOCTL_SATRI_SET_BLOCKLIST, in_buf=cfg)
        
        if returned >= 0:
            self._log.info(f"[KernelBridge] Blocklist actualizada: {count} entradas.")
            return True
        return False
    
    def get_stats(self) -> Optional[dict]:
        """Obtiene estadísticas del driver. Retorna dict o None si no disponible."""
        if not self.is_connected:
            return None
        
        stats = SatriDriverStats()
        returned = self._ioctl(IOCTL_SATRI_GET_STATS, out_buf=stats)
        
        if returned < ctypes.sizeof(SatriDriverStats):
            return None
        
        return {
            "total_events_generated":  stats.TotalEventsGenerated,
            "total_processes_blocked": stats.TotalProcessesBlocked,
            "blocked_pid_count":       stats.BlockedPidCount,
            "blocklist_name_count":    stats.BlocklistNameCount,
            "event_buffer_used":       stats.EventBufferUsed,
        }
    
    # ── Poller de eventos en background ──────────────────────────────────────
    
    def start_event_poller(
        self, 
        callback: Callable[[KernelEvent], None],
        interval: float = None
    ):
        """
        Inicia un hilo daemon que lee eventos del kernel periódicamente.
        
        Args:
            callback: Función que recibe cada KernelEvent detectado.
            interval: Segundos entre polling (default: POLL_INTERVAL).
        """
        if not self.is_connected:
            self._log.info("[KernelBridge] Poller desactivado (driver no disponible).")
            return
        
        if self._poller_thread and self._poller_thread.is_alive():
            return  # Ya está corriendo
        
        self._poller_running = True
        poll_interval = interval or self.POLL_INTERVAL
        
        def _poller_loop():
            self._log.info(f"[KernelBridge] Poller iniciado (intervalo: {poll_interval}s)")
            while self._poller_running and self.is_connected:
                try:
                    events = self.get_events()
                    for event in events:
                        try:
                            callback(event)
                        except Exception as e:
                            self._log.error(f"[KernelBridge] Error en callback: {e}")
                except Exception as e:
                    self._log.error(f"[KernelBridge] Error en poller: {e}")
                time.sleep(poll_interval)
            self._log.info("[KernelBridge] Poller detenido.")
        
        self._poller_thread = threading.Thread(
            target=_poller_loop,
            name="SatriKernelPoller",
            daemon=True
        )
        self._poller_thread.start()
    
    def _stop_poller(self):
        self._poller_running = False
        if self._poller_thread:
            self._poller_thread.join(timeout=3)
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, *_):
        self.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# Función de verificación del driver (sin conexión completa)
# ─────────────────────────────────────────────────────────────────────────────

def is_satri_driver_loaded() -> bool:
    """
    Verifica si el SatriDriver está cargado verificando el servicio de Windows
    y el dispositivo \\.\\SatriDriver.
    
    No requiere privilegios de administrador para la verificación básica.
    """
    try:
        # Método 1: Intentar abrir el dispositivo
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            r"\\.\SatriDriver",
            GENERIC_READ | GENERIC_WRITE,
            0, None, OPEN_EXISTING, 0, None
        )
        if handle != INVALID_HANDLE_VALUE and handle not in (None, 0):
            kernel32.CloseHandle(handle)
            return True
    except Exception:
        pass
    
    try:
        # Método 2: Consultar el servicio de Windows
        import subprocess
        result = subprocess.run(
            ["sc", "query", "SatriDriver"],
            capture_output=True, text=True, timeout=5
        )
        return "RUNNING" in result.stdout
    except Exception:
        pass
    
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Script de prueba (ejecutar directamente para verificar integración)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )
    
    print("=" * 55)
    print("  SATRI Kernel Bridge — Test de Integración v1.1")
    print("=" * 55)
    
    # Verificación rápida
    loaded = is_satri_driver_loaded()
    print(f"\n[*] Driver detectado: {'[SI]' if loaded else '[NO] (modo pasivo)'}")
    
    bridge = SatriKernelBridge()
    connected = bridge.connect()
    
    if not connected:
        print("\n[!] Driver no disponible. Esto es NORMAL si no tienes el .sys compilado.")
        print("[!] El agente funcionará en modo user-space únicamente.")
        sys.exit(0)
    
    print("\n[1] Probando GET_STATS...")
    stats = bridge.get_stats()
    if stats:
        print(f"    Eventos generados: {stats['total_events_generated']}")
        print(f"    Procesos bloqueados: {stats['total_processes_blocked']}")
        print(f"    Nombres en blocklist: {stats['blocklist_name_count']}")
    
    print("\n[2] Probando GET_EVENTS (leer buffer actual)...")
    events = bridge.get_events()
    print(f"    {len(events)} evento(s) en el buffer:")
    for e in events:
        flag = " [BLOQUEADO]" if e.was_blocked else ""
        print(f"    [{e.event_type}] PID={e.pid} → {e.image_name}{flag}")
    
    print("\n[3] Probando SET_BLOCKLIST...")
    test_blocklist = ["mimikatz.exe", "nc.exe", "netcat.exe", "wce.exe"]
    ok = bridge.set_blocklist(test_blocklist)
    print(f"    {'[OK]' if ok else '[Error]'}")
    
    print("\n[4] Iniciando monitor por 5 segundos...")
    captured = []
    def on_event(event: KernelEvent):
        captured.append(event)
        flag = " [BLOQUEADO]" if event.was_blocked else ""
        print(f"    [{event.event_type}] {event.image_name} (PID:{event.pid}){flag}")
    
    bridge.start_event_poller(callback=on_event, interval=1.0)
    time.sleep(5)
    
    print(f"\n    Total eventos capturados: {len(captured)}")
    
    bridge.disconnect()
    print("\n[*] Test completado.\n")
