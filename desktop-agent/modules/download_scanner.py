import os
import time
import logging
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from reporter import reporter

logger = logging.getLogger("download_scanner")
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
QUARANTINE_DIR = os.path.join(os.path.expanduser("~"), "SATRI_Quarantine")

class DownloadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            self.scan_file(event.src_path)
            
    def on_modified(self, event):
        if not event.is_directory:
            self.scan_file(event.src_path)

    def scan_file(self, filepath):
        try:
            filename = os.path.basename(filepath)
            ext = os.path.splitext(filename)[1].lower()
            
            dangerous_exts = [".exe", ".bat", ".ps1", ".vbs", ".scr", ".msi"]
            
            # Solo consideramos malicioso para la demo si el nombre contiene "malware" o "virus" o es una extension peligrosa
            # Para la demo, aislaremos todo lo que termine en estas extensiones y contenga 'malicious' o 'test_virus'.
            # O mejor aún, para hacer la prueba fácil: si descargan algo que se llama "virus.exe" o "malware.bat".
            if ext in dangerous_exts and ("virus" in filename.lower() or "malware" in filename.lower()):
                logger.critical(f"ARCHIVO MALICIOSO DETECTADO: {filename}")
                self.quarantine_file(filepath)
        except Exception as e:
            pass

    def quarantine_file(self, filepath):
        if not os.path.exists(QUARANTINE_DIR):
            os.makedirs(QUARANTINE_DIR)
            
        filename = os.path.basename(filepath)
        quarantine_path = os.path.join(QUARANTINE_DIR, filename + ".quarantine")
        
        try:
            # Esperar a que el archivo termine de descargarse (pequeño retardo)
            time.sleep(1)
            shutil.move(filepath, quarantine_path)
            logger.info(f"Archivo aislado en: {quarantine_path}")
            
            reporter.send_event(
                event_type="malicious_file_quarantined",
                message=f"Archivo malicioso '{filename}' aislado en cuarentena local.",
                severity="CRITICAL",
                artifacts={"original_path": filepath, "quarantine_path": quarantine_path}
            )
        except Exception as e:
            logger.error(f"Error al intentar aislar archivo: {e}")

def start_scanner():
    logger.info(f"Escáner de Descargas activo en {DOWNLOADS_DIR}...")
    if not os.path.exists(DOWNLOADS_DIR):
        return
        
    observer = Observer()
    observer.schedule(DownloadHandler(), DOWNLOADS_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except Exception:
        observer.stop()
    observer.join()
