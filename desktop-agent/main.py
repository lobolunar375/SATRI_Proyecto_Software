import threading
import time
import logging
import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from consent import verify_user_consent
from reporter import reporter
from config import load_config
from ioc_sync import sync_local_iocs
from local_api import run_local_api

from modules.process_monitor import start_monitor
from modules.ransomware_guard import start_ransomware_guard
from modules.download_scanner import start_scanner
from modules.wifi_check import start_wifi_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("agent_main")

def heartbeat_worker():
    while True:
        reporter.send_heartbeat()
        time.sleep(60)

if __name__ == "__main__":
    logger.info("Iniciando SATRI Desktop Agent v3.0 (Arquitectura Modular)")
    
    if not verify_user_consent():
        logger.error("Consentimiento no otorgado. Saliendo...")
        exit(1)
        
    cfg = load_config()
    logger.info(f"Configuración cargada: {cfg}")
    
    sync_local_iocs()

    # Iniciar hilos de los módulos
    threading.Thread(target=start_monitor, daemon=True).start()
    threading.Thread(target=start_ransomware_guard, daemon=True).start()
    threading.Thread(target=start_scanner, daemon=True).start()
    threading.Thread(target=start_wifi_check, daemon=True).start()
    threading.Thread(target=heartbeat_worker, daemon=True).start()
    
    from modules.network_monitor import start_network_monitor
    threading.Thread(target=start_network_monitor, daemon=True).start()
    
    from modules.activity_monitor import start_activity_monitor
    threading.Thread(target=start_activity_monitor, daemon=True).start()
    
    from modules.browser_bridge import start_browser_bridge
    threading.Thread(target=start_browser_bridge, daemon=True).start()

    # El hilo principal corre la API local para aislamientos
    logger.info("Agente iniciado. Exponiendo API local en el puerto 18001...")
    run_local_api()
