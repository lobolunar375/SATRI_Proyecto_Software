from fastapi import FastAPI
from prometheus_client import make_asgi_app
from aiokafka import AIOKafkaConsumer
from loguru import logger
import json
import os
import asyncio

from extractor.ioc_extractor import extract_iocs
from cache.ioc_cache import get_cached, set_cached, cache_hit_rate
from virustotal_client import query_virustotal
from yara_scanner import calculate_vt_score, analyze_offline_intelligence
from repository.ioc_repository import upsert_ioc
from publisher.decision import publish_decision

app = FastAPI(
    title="SATRI - MIA_VT (Inteligencia de Amenazas)",
    description="Microservicio de Análisis y Triage con VirusTotal",
    version="1.0.0"
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

async def process_alert(alert: dict):
    """Procesa una alerta de MML, consulta VT y emite triage."""
    incident_id = alert.get("incident_id", "UNKNOWN")
    logger.info(f"Procesando alerta: {incident_id}")
    
    # Extraer texto de artefactos para IoC
    artifacts = alert.get("artifacts", {})
    text_to_analyze = " ".join([str(v) for v in artifacts.values() if v])
    iocs = extract_iocs(text_to_analyze)
    
    if not iocs:
        logger.info(f"No IoCs encontrados en {incident_id}. Publicando como UNKNOWN.")
        publish_decision(alert, "UNKNOWN")
        return

    # Para simplificar, tomaremos el peor score de todos los IoC encontrados
    worst_score = -1
    worst_label = "CLEAN"
    
    for ioc in iocs:
        logger.debug(f"Analizando IoC: {ioc.type} -> {ioc.value}")
        
        # 1. Inteligencia Local / Offline (Mock YARA)
        offline_result = analyze_offline_intelligence(ioc)
        if offline_result:
            logger.info(f"Detección de Inteligencia Local (YARA) para {ioc.type}: {ioc.value}")
            vt_result = offline_result
        else:
            # 2. Inteligencia Externa (VirusTotal)
            cached = get_cached(ioc)
            if cached:
                vt_response = cached
                logger.debug("Cache HIT")
            else:
                logger.debug("Cache MISS, consultando VT API...")
                vt_response = await query_virustotal(ioc)
                
                if "error" not in vt_response and vt_response.get("status") != "NOT_FOUND":
                    set_cached(ioc, vt_response)
                else:
                    # FASE 4: Cachear fallos por 24h (86400 segundos) para evitar agotar la API en reintentos inútiles
                    set_cached(ioc, vt_response, ttl_override=86400)
                    logger.warning(f"[TELEMETRIA] Fallo de VT cacheado por 24h: {ioc.value}")
                    
            vt_result = calculate_vt_score(vt_response)

        
        # Guardar en BD
        upsert_ioc(ioc.value, ioc.type, vt_result.model_dump())
        
        # Evaluar peor caso
        if vt_result.vt_score > worst_score:
            worst_score = vt_result.vt_score
            worst_label = vt_result.vt_label

    publish_decision(alert, worst_label)

async def run_mia_consumer():
    logger.info("Iniciando Kafka Consumer MIA_VT...")
    consumer = AIOKafkaConsumer(
        "satri.alerts.enrichment",
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="mia-vt-group"
    )
    
    for attempt in range(30):
        try:
            await consumer.start()
            logger.success(f"MIA_VT conectado a Kafka en intento {attempt + 1}")
            break
        except Exception as e:
            logger.warning(f"Kafka no disponible (intento {attempt + 1}/30): {e}")
            await asyncio.sleep(5)
    else:
        logger.error("No se pudo conectar a Kafka despues de 30 intentos")
        return
    
    async for message in consumer:
        alert = message.value
        try:
            # Ahora podemos usar await directamente
            await process_alert(alert)
        except Exception as e:
            logger.error(f"Error procesando alerta: {e}")

@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "service": "mia_vt",
        "cache_hit_rate": cache_hit_rate()
    }

@app.on_event("startup")
async def startup():
    logger.info("MIA_VT microservice starting up...")
    asyncio.create_task(run_mia_consumer())

@app.on_event("shutdown")
async def shutdown():
    logger.info("MIA_VT microservice shutting down...")
