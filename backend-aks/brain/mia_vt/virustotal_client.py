import vt
import asyncio
import os
import logging
from extractor.ioc_extractor import IoC

logger = logging.getLogger("vt_client")

VT_API_KEY = os.environ.get("VIRUSTOTAL_API_KEY", "")

# Control de Rate Limiting en memoria para la capa gratis (4 req/min)
# Usaremos un semáforo y delays para hacer backoff
MAX_REQ_PER_MIN = 4
request_timestamps = []

async def _wait_for_rate_limit():
    global request_timestamps
    now = asyncio.get_event_loop().time()
    
    # Limpiar timestamps viejos (> 60s)
    request_timestamps = [ts for ts in request_timestamps if now - ts < 60.0]
    
    if len(request_timestamps) >= MAX_REQ_PER_MIN:
        # Implementar backoff
        oldest = request_timestamps[0]
        wait_time = 60.0 - (now - oldest)
        if wait_time > 0:
            logger.warning(f"[VT_CLIENT] Rate limit excedido (4 req/min). Backoff de {wait_time:.1f}s en cola...")
            await asyncio.sleep(wait_time)
            
    # Registrar la nueva solicitud
    request_timestamps.append(asyncio.get_event_loop().time())

async def query_virustotal(ioc: IoC) -> dict:
    """Consulta la API v3 de VirusTotal con control de Backoff."""
    if not VT_API_KEY:
        logger.error("VIRUSTOTAL_API_KEY no esta configurada")
        return {"error": "API Key missing"}

    await _wait_for_rate_limit()
    
    try:
        async with asyncio.timeout(10.0): # Timeout más alto para permitir resolución
            async with vt.Client(VT_API_KEY) as client:
                if ioc.type == "ip":
                    obj = await client.get_object_async(f"/ip_addresses/{ioc.value}")
                elif ioc.type == "domain":
                    obj = await client.get_object_async(f"/domains/{ioc.value}")
                else:
                    return {"last_analysis_stats": {"malicious": 0}, "reputation": 0}
                
                stats = obj.get("last_analysis_stats", {})
                return {
                    "last_analysis_stats": {str(k): int(v) for k, v in stats.items()} if isinstance(stats, dict) else {},
                    "reputation": int(obj.get("reputation", 0)),
                }
    except Exception as e:
        logger.warning(f"Error consultando VT para IP {ioc.value}: {e}")
        return {"last_analysis_stats": {"malicious": 1}, "reputation": 0}
