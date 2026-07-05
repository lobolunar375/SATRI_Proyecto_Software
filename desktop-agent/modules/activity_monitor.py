import time
import logging
import ctypes
from reporter import reporter

logger = logging.getLogger("activity_monitor")

def get_foreground_window_title():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def kill_active_tab():
    # Send Ctrl+W using ctypes
    VK_CONTROL = 0x11
    VK_W = 0x57
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_W, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_W, 0, 2, 0) # KEYEVENTF_KEYUP
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 2, 0)

def start_activity_monitor():
    logger.info("Iniciando Monitor de Actividad del Usuario (Soporte Universal de Navegadores)...")
    last_title = ""
    
    # Lista negra de dominios y palabras clave de certificados inválidos / errores
    blacklist = [
        "malicious-test.com", 
        "phishing-demo.com", 
        "anonymous-proxy-servers.net",
        "la conexión no es privada", 
        "privacy error",
        "no se puede acceder a este sitio web",
        "site can't be reached",
        "error de privacidad"
    ]
    
    while True:
        try:
            current_title = get_foreground_window_title()
            if current_title and current_title != last_title:
                last_title = current_title
                
                # Ignorar ventanas sin nombre o muy genéricas
                if len(current_title) > 2 and current_title not in ["Program Manager", "Task Switching"]:
                    
                    # 1. VISIBILIDAD: Reportar en el tráfico crudo (Funciona para CUALQUIER navegador)
                    reporter.send_event(
                        event_type="user_activity",
                        message=f"El usuario está viendo: {current_title}",
                        severity="INFO",
                        artifacts={"window_title": current_title}
                    )
                    
                    # 2. PROTECCIÓN UNIVERSAL: Si el título contiene un sitio bloqueado, MATAR la pestaña
                    title_lower = current_title.lower()
                    for bad_site in blacklist:
                        if bad_site in title_lower:
                            logger.critical(f"¡Sitio malicioso detectado en navegador! Cerrando pestaña: {bad_site}")
                            reporter.send_event(
                                event_type="universal_tab_killer",
                                message=f"Pestaña maliciosa aniquilada en cualquier navegador: {bad_site}",
                                severity="CRITICAL"
                            )
                            # Disparar Ctrl+W para cerrar la pestaña
                            kill_active_tab()
                            last_title = "" # reset
                            break
        except Exception as e:
            pass
            
        time.sleep(2)
