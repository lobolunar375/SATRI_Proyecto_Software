import time
import logging
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from reporter import reporter

logger = logging.getLogger("ransomware_guard")
CANARY_DIR = os.path.join(os.path.expanduser("~"), "SATRI_Canary_Files")

class CanaryHandler(FileSystemEventHandler):
    def on_created(self, event):
        self.check_file(event.src_path)
        
    def on_modified(self, event):
        self.check_file(event.src_path)
        
    def on_moved(self, event):
        self.check_file(event.dest_path)

    def check_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in [".locked", ".encrypted", ".cry", ".crypt", ".enc", ".locky", ".cerber"]:
            logger.critical(f"RANSOMWARE DETECTADO: Archivo sospechoso: {path}")
            reporter.send_event(
                event_type="ransomware_behavior_detected",
                message="Modificación sospechosa tipo ransomware en archivos canary",
                severity="CRITICAL",
                artifacts={"file_name": os.path.basename(path), "path": path}
            )
            isolate_network()

def start_ransomware_guard():
    logger.info(f"Iniciando Escudo Anti-Ransomware (Canary Files) en {CANARY_DIR}...")
    if not os.path.exists(CANARY_DIR):
        try:
            os.makedirs(CANARY_DIR)
            with open(os.path.join(CANARY_DIR, "passwords_canary.txt"), "w") as f:
                f.write("Do not modify. Canary file.")
        except Exception as e:
            logger.error(f"No se pudo crear el directorio canary: {e}")
            
    observer = Observer()
    observer.schedule(CanaryHandler(), CANARY_DIR, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except Exception:
        observer.stop()
    observer.join()

def isolate_network():
    logger.critical("RANSOMWARE DETECTADO: Simulando aislamiento de red (Regla de SOAR enviada)")

def restore_network():
    logger.info("Ransomware guard: Restaurando conexión de red...")
