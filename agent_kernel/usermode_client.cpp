/*
 * usermode_client.cpp — SATRI EDR Kernel Bridge Client (User-Mode)
 *
 * Cliente C++ para comunicarse con el SatriDriver (Ring 0) desde Ring 3.
 * Expone funciones para:
 *   - Leer el buffer de eventos del kernel.
 *   - Bloquear un PID especifico.
 *   - Actualizar la blocklist de nombres de proceso.
 *   - Consultar estadisticas del driver.
 *
 * Compilacion:
 *   g++ usermode_client.cpp -o satri_client.exe -std=c++17
 *   cl.exe usermode_client.cpp /std:c++17 /EHsc /Fe:satri_client.exe
 *
 * Uso (como Administrador):
 *   satri_client.exe events          → Leer eventos pendientes del kernel
 *   satri_client.exe block <PID>     → Bloquear un PID especifico
 *   satri_client.exe stats           → Ver estadisticas del driver
 *   satri_client.exe monitor         → Modo monitor continuo (polling)
 */

#include <windows.h>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <thread>
#include <chrono>
#include <vector>
#include <ctime>

// ─────────────────────────────────────────────────────────────────────────────
// Estructuras compartidas con el kernel (debe coincidir con satri_driver.c)
// ─────────────────────────────────────────────────────────────────────────────
#define MAX_EVENTS          256
#define MAX_BLOCKED_NAMES   32
#define MAX_BLOCKED_PIDS    64
#define MAX_PROC_NAME_LEN   64
#define MAX_PATH_LEN        260

#define IOCTL_SATRI_GET_EVENTS    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SATRI_BLOCK_PID     CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SATRI_SET_BLOCKLIST CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SATRI_GET_STATS     CTL_CODE(FILE_DEVICE_UNKNOWN, 0x803, METHOD_BUFFERED, FILE_ANY_ACCESS)

typedef enum _SATRI_EVENT_TYPE {
    SATRI_PROCESS_CREATE    = 1,
    SATRI_PROCESS_TERMINATE = 2,
    SATRI_PROCESS_BLOCKED   = 3,
} SATRI_EVENT_TYPE;

#pragma pack(push, 1)
typedef struct _SATRI_KERNEL_EVENT {
    DWORD         EventType;
    DWORD         ProcessId;
    DWORD         ParentProcessId;
    CHAR          ImageName[MAX_PATH_LEN];
    LARGE_INTEGER Timestamp;
    BOOL          WasBlocked;
} SATRI_KERNEL_EVENT;

typedef struct _SATRI_BLOCK_PID_REQUEST {
    DWORD TargetPid;
} SATRI_BLOCK_PID_REQUEST;

typedef struct _SATRI_BLOCKLIST_CONFIG {
    DWORD EntryCount;
    CHAR  ProcessNames[MAX_BLOCKED_NAMES][MAX_PROC_NAME_LEN];
} SATRI_BLOCKLIST_CONFIG;

typedef struct _SATRI_DRIVER_STATS {
    DWORD TotalEventsGenerated;
    DWORD TotalProcessesBlocked;
    DWORD BlockedPidCount;
    DWORD BlocklistNameCount;
    DWORD EventBufferUsed;
} SATRI_DRIVER_STATS;
#pragma pack(pop)

// ─────────────────────────────────────────────────────────────────────────────
// Clase SatriKernelClient
// ─────────────────────────────────────────────────────────────────────────────
class SatriKernelClient {
private:
    HANDLE m_hDevice;
    bool   m_isOpen;
    
    static const char* DEVICE_PATH;
    
public:
    SatriKernelClient() : m_hDevice(INVALID_HANDLE_VALUE), m_isOpen(false) {}
    
    ~SatriKernelClient() {
        Close();
    }
    
    // Abrir handle al driver
    bool Open() {
        m_hDevice = CreateFileW(
            L"\\\\.\\SatriDriver",
            GENERIC_READ | GENERIC_WRITE,
            0,
            NULL,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            NULL
        );
        
        if (m_hDevice == INVALID_HANDLE_VALUE) {
            std::cerr << "[SATRI-CLIENT][ERROR] No se pudo abrir handle al driver."
                      << " Codigo: " << GetLastError() << std::endl;
            std::cerr << "  > ¿Esta el driver cargado? ¿Tienes privilegios de Administrador?" << std::endl;
            return false;
        }
        
        m_isOpen = true;
        std::cout << "[SATRI-CLIENT][OK] Conectado a SatriDriver." << std::endl;
        return true;
    }
    
    void Close() {
        if (m_isOpen && m_hDevice != INVALID_HANDLE_VALUE) {
            CloseHandle(m_hDevice);
            m_hDevice = INVALID_HANDLE_VALUE;
            m_isOpen = false;
        }
    }
    
    bool IsOpen() const { return m_isOpen; }
    
    // ── IOCTL: Leer eventos del kernel ──
    std::vector<SATRI_KERNEL_EVENT> GetEvents() {
        std::vector<SATRI_KERNEL_EVENT> events;
        if (!m_isOpen) return events;
        
        const DWORD bufSize = sizeof(SATRI_KERNEL_EVENT) * MAX_EVENTS;
        std::vector<BYTE> outBuf(bufSize, 0);
        DWORD bytesReturned = 0;
        
        BOOL ok = DeviceIoControl(
            m_hDevice,
            IOCTL_SATRI_GET_EVENTS,
            NULL, 0,
            outBuf.data(), bufSize,
            &bytesReturned,
            NULL
        );
        
        if (!ok) {
            DWORD err = GetLastError();
            if (err != ERROR_INSUFFICIENT_BUFFER) {
                std::cerr << "[SATRI-CLIENT][ERROR] GET_EVENTS fallo. Codigo: " << err << std::endl;
            }
            return events;
        }
        
        DWORD count = bytesReturned / sizeof(SATRI_KERNEL_EVENT);
        SATRI_KERNEL_EVENT* pEvt = reinterpret_cast<SATRI_KERNEL_EVENT*>(outBuf.data());
        for (DWORD i = 0; i < count; i++) {
            events.push_back(pEvt[i]);
        }
        return events;
    }
    
    // ── IOCTL: Bloquear un PID especifico ──
    bool BlockPid(DWORD pid) {
        if (!m_isOpen) return false;
        
        SATRI_BLOCK_PID_REQUEST req;
        req.TargetPid = pid;
        DWORD bytesReturned = 0;
        
        BOOL ok = DeviceIoControl(
            m_hDevice,
            IOCTL_SATRI_BLOCK_PID,
            &req, sizeof(req),
            NULL, 0,
            &bytesReturned,
            NULL
        );
        
        if (!ok) {
            std::cerr << "[SATRI-CLIENT][ERROR] BLOCK_PID fallo para PID=" << pid
                      << ". Codigo: " << GetLastError() << std::endl;
            return false;
        }
        
        std::cout << "[SATRI-CLIENT][OK] PID " << pid << " agregado a la blocklist del kernel." << std::endl;
        return true;
    }
    
    // ── IOCTL: Actualizar blocklist de nombres ──
    bool SetBlocklist(const std::vector<std::string>& names) {
        if (!m_isOpen) return false;
        
        SATRI_BLOCKLIST_CONFIG cfg;
        ZeroMemory(&cfg, sizeof(cfg));
        cfg.EntryCount = (DWORD)min(names.size(), (size_t)MAX_BLOCKED_NAMES);
        
        for (DWORD i = 0; i < cfg.EntryCount; i++) {
            strncpy_s(cfg.ProcessNames[i], MAX_PROC_NAME_LEN, names[i].c_str(), _TRUNCATE);
        }
        
        DWORD bytesReturned = 0;
        BOOL ok = DeviceIoControl(
            m_hDevice,
            IOCTL_SATRI_SET_BLOCKLIST,
            &cfg, sizeof(cfg),
            NULL, 0,
            &bytesReturned,
            NULL
        );
        
        if (!ok) {
            std::cerr << "[SATRI-CLIENT][ERROR] SET_BLOCKLIST fallo. Codigo: " << GetLastError() << std::endl;
            return false;
        }
        
        std::cout << "[SATRI-CLIENT][OK] Blocklist actualizada con " << cfg.EntryCount << " entradas." << std::endl;
        return true;
    }
    
    // ── IOCTL: Obtener estadisticas del driver ──
    bool GetStats(SATRI_DRIVER_STATS& stats) {
        if (!m_isOpen) return false;
        
        DWORD bytesReturned = 0;
        BOOL ok = DeviceIoControl(
            m_hDevice,
            IOCTL_SATRI_GET_STATS,
            NULL, 0,
            &stats, sizeof(stats),
            &bytesReturned,
            NULL
        );
        
        if (!ok || bytesReturned < sizeof(stats)) {
            std::cerr << "[SATRI-CLIENT][ERROR] GET_STATS fallo. Codigo: " << GetLastError() << std::endl;
            return false;
        }
        return true;
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// Funciones de visualizacion
// ─────────────────────────────────────────────────────────────────────────────
std::string EventTypeStr(DWORD type) {
    switch (type) {
        case 1: return "CREATE";
        case 2: return "TERMINATE";
        case 3: return "BLOCKED";
        default: return "UNKNOWN";
    }
}

void PrintEvent(const SATRI_KERNEL_EVENT& evt) {
    std::string typeStr = EventTypeStr(evt.EventType);
    const char* color = "";
    if (evt.EventType == 3) color = "\033[31m";       // Rojo para BLOCKED
    else if (evt.EventType == 1) color = "\033[32m";  // Verde para CREATE
    else color = "\033[33m";                           // Amarillo para TERMINATE
    
    std::cout << color
              << "[" << std::setw(9) << std::left << typeStr << "] "
              << "PID=" << std::setw(6) << evt.ProcessId
              << " PPID=" << std::setw(6) << evt.ParentProcessId
              << " Image=" << evt.ImageName
              << "\033[0m" << std::endl;
}

void PrintStats(const SATRI_DRIVER_STATS& stats) {
    std::cout << "\n╔══════════════════════════════╗\n";
    std::cout << "║  SATRI Kernel Driver Stats   ║\n";
    std::cout << "╠══════════════════════════════╣\n";
    std::cout << "║  Eventos generados: " << std::setw(9) << std::right << stats.TotalEventsGenerated << " ║\n";
    std::cout << "║  Procesos bloqueados: " << std::setw(7) << stats.TotalProcessesBlocked << " ║\n";
    std::cout << "║  PIDs en blocklist: " << std::setw(9) << stats.BlockedPidCount << " ║\n";
    std::cout << "║  Nombres en blocklist: " << std::setw(6) << stats.BlocklistNameCount << " ║\n";
    std::cout << "║  Eventos en buffer: " << std::setw(9) << stats.EventBufferUsed << " ║\n";
    std::cout << "╚══════════════════════════════╝\n";
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────
int main(int argc, char* argv[]) {
    // Habilitar colores ANSI en la consola de Windows
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD mode = 0;
    GetConsoleMode(hOut, &mode);
    SetConsoleMode(hOut, mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);

    std::cout << "\033[36m";
    std::cout << "╔════════════════════════════════════════╗\n";
    std::cout << "║  SATRI Kernel Bridge Client v1.1       ║\n";
    std::cout << "║  Ring 0 ↔ Ring 3 Communication Layer   ║\n";
    std::cout << "╚════════════════════════════════════════╝\n";
    std::cout << "\033[0m\n";

    SatriKernelClient client;
    if (!client.Open()) {
        std::cerr << "[ERROR] Asegurate de cargar el driver primero." << std::endl;
        return 1;
    }

    std::string cmd = (argc > 1) ? argv[1] : "help";

    if (cmd == "events") {
        std::cout << "\n[SATRI] Leyendo eventos del kernel...\n\n";
        auto events = client.GetEvents();
        if (events.empty()) {
            std::cout << "  (Sin eventos pendientes en el buffer)\n";
        } else {
            std::cout << "  " << events.size() << " evento(s) recibidos:\n\n";
            for (const auto& e : events) {
                PrintEvent(e);
            }
        }
        
    } else if (cmd == "block" && argc > 2) {
        DWORD pid = (DWORD)std::stoul(argv[2]);
        client.BlockPid(pid);
        
    } else if (cmd == "stats") {
        SATRI_DRIVER_STATS stats;
        if (client.GetStats(stats)) {
            PrintStats(stats);
        }
        
    } else if (cmd == "monitor") {
        std::cout << "[SATRI-MONITOR] Modo monitor activo. Ctrl+C para salir.\n\n";
        int pollIntervalMs = (argc > 2) ? std::stoi(argv[2]) : 1000;
        
        while (true) {
            auto events = client.GetEvents();
            for (const auto& e : events) {
                PrintEvent(e);
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(pollIntervalMs));
        }
        
    } else {
        std::cout << "Uso:\n";
        std::cout << "  satri_client.exe events              → Leer eventos del kernel\n";
        std::cout << "  satri_client.exe block <PID>         → Bloquear PID especifico\n";
        std::cout << "  satri_client.exe stats               → Ver estadisticas del driver\n";
        std::cout << "  satri_client.exe monitor [ms]        → Monitor continuo (default: 1000ms)\n";
    }

    client.Close();
    return 0;
}
