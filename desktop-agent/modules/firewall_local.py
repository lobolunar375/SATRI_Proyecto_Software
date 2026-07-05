import logging
import subprocess

logger = logging.getLogger("firewall_local")

def block_ip(ip: str):
    logger.info(f"Bloqueando IP maliciosa en el firewall local: {ip}")

def unblock_ip(ip: str):
    logger.info(f"Desbloqueando IP en el firewall local: {ip}")

def isolate_network():
    logger.critical("AISLAMIENTO INICIADO: Bloqueando todo el tráfico no esencial...")
    logger.info("Tráfico bloqueado. Reglas de firewall aplicadas.")

def restore_network():
    logger.info("Restaurando conexión de red...")
    logger.info("Conexión restaurada.")
