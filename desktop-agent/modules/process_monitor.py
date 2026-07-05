import time
import logging
import psutil
from reporter import reporter
from config import should_auto_block

logger = logging.getLogger("process_monitor")

MALICIOUS_PROCESSES = [
    "malware.exe",
    "ransomware.exe", 
    "miner.exe",
    "virus.exe",
    "trojan.exe",
    "worm.exe",
    "spyware.exe",
    "mimikatz.exe"
]

def start_monitor():
    logger.info("Iniciando Monitor de Procesos (User-mode)...")
    while True:
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = proc.info['name'].lower()
                    if name in MALICIOUS_PROCESSES:
                        logger.warning(f"Proceso malicioso detectado: {name} (PID: {proc.info['pid']})")
                        reporter.send_event(
                            event_type="malicious_process_detected",
                            message=f"Se detectó proceso malicioso: {name}",
                            severity="HIGH",
                            artifacts={"pid": proc.info['pid'], "process_name": name}
                        )
                        
                        if should_auto_block():
                            block_process(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            logger.error(f"Error en monitor de procesos: {e}")
            
        time.sleep(5)

def block_process(pid: int):
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        logger.info(f"Bloqueando (matando) proceso con PID {pid} ({name})")
        proc.kill()
        reporter.send_event(
            event_type="malicious_process_killed",
            message=f"Proceso malicioso aniquilado: {name}",
            severity="CRITICAL",
            artifacts={"pid": pid, "process_name": name, "action": "killed"}
        )
    except Exception as e:
        logger.error(f"Error al matar proceso {pid}: {e}")

def unblock_process(pid: int):
    logger.info(f"Desbloqueando proceso con PID {pid} (No aplicable al hacer kill)")
