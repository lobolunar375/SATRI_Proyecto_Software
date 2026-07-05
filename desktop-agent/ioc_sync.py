import logging

logger = logging.getLogger("ioc_sync")

def sync_local_iocs():
    """
    Se comunica con el backend para descargar IoCs recientes
    y alimentar al firewall_local y process_monitor.
    """
    logger.info("Sincronizando Indicadores de Compromiso (IoCs) desde el cerebro...")
    # Mock de sincronización
    return ["192.168.1.99", "bad_hash_example"]
