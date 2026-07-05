from fastapi import FastAPI, Security, HTTPException, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer
from datetime import datetime, timezone
import json, uuid, os, asyncio
from loguru import logger
from prometheus_client import make_asgi_app
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from bloom_dedup import bloom
from normalizer import run_normalizer
from geoip_enrich import run_enricher
from opensearch_client import index_log

# Rate Limiter global
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="MML Alert Manager", version="2.0",
              description="Message Management Layer — Ingestion, normalización ECS, GeoIP, deduplicación Bloom")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

security = HTTPBearer()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

producer = None

async def get_producer():
    global producer
    if producer is None or not producer._sender.sender_task or producer._sender.sender_task.done():
        try:
            p = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda m: json.dumps(m).encode()
            )
            await p.start()
            producer = p
            logger.success("[MML] Producer Kafka conectado.")
        except Exception as e:
            logger.error(f"[MML] No se pudo conectar producer a Kafka: {e}")
            raise
    return producer

class Alert(BaseModel):
    correlation_id: str
    severity_score: int
    rule_name: str
    src_ip: str | None = None
    dst_ip: str | None = None
    event_type: str

def assign_priority(score: int) -> str:
    if score >= 75: return "P1"
    if score >= 50: return "P2"
    if score >= 25: return "P3"
    return "P4"

@app.post("/api/v1/alerts")
@limiter.limit("60/minute")
async def receive_alert(
    request: Request,
    alert: Alert,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    # En produccion: validar JWT aqui
    
    # Deduplicacion activada
    dedup_key = f"{alert.rule_name}:{alert.src_ip}"
    if bloom.is_duplicate(dedup_key):
        logger.info(f"Alerta duplicada descartada: {dedup_key}")
        return {"status": "skipped", "reason": "duplicate"}

    incident = {
        "incident_id": f"INC-{datetime.now().strftime('%Y-%m')}-{uuid.uuid4().hex[:6].upper()}",
        "correlation_id": alert.correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "HIGH" if alert.severity_score >= 75 else "MEDIUM",
        "priority": assign_priority(alert.severity_score),
        "source_microservice": "MML-v1.0",
        "event_type": alert.event_type,
        "artifacts": {
            "src_ip": alert.src_ip,
            "dst_ip": alert.dst_ip,
        },
        "enrichment_status": "PENDING"
    }
    prod = await get_producer()
    await prod.send_and_wait("satri.alerts.enrichment", incident)
    logger.info(f"Alerta enviada a enriquecimiento: {incident['incident_id']}")
    return {"status": "queued", "incident_id": incident["incident_id"]}

# Endpoint de ingestion de logs directos de agentes y extensiones
class IngestLogReq(BaseModel):
    message: str
    event_type: str
    source: str
    src_ip: str | None = None

@app.post("/api/v1/ingest-log")
@limiter.limit("300/minute")
async def ingest_log(request: Request, req: IngestLogReq):
    raw_log = {
        "message": req.message,
        "event_type": req.event_type,
        "source": req.source,
        "src_ip": req.src_ip,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        prod = await get_producer()
        await prod.send_and_wait("satri.logs.raw", raw_log)
        logger.info(f"[MML] Evento ingresado a Kafka: {req.event_type} desde {req.source}")
        return {"status": "ok", "log": raw_log}
    except Exception as e:
        logger.error(f"[MML] Error publicando en Kafka: {e}")
        return {"status": "error", "detail": str(e), "log": raw_log}

# Estado global temporal para IPs aisladas (en prod iría a Redis o Mongo)
agent_configs = {}

@app.get("/api/v1/agent/config/{ip}")
async def get_agent_config(ip: str):
    # Por defecto devolvemos la config base
    return agent_configs.get(ip, {
        "host_isolation": False,
        "block_enabled": True,
        "policy": {
            "blacklist_keywords": ["phishing", "scam", "malware", "hack"],
            "exclusion_keywords": ["google", "wikipedia"],
            "blacklist_apps": ["mimikatz.exe", "anydesk.exe"]
        }
    })

@app.post("/api/v1/agent/config/{ip}/isolate")
async def isolate_agent(ip: str):
    if ip not in agent_configs:
        agent_configs[ip] = {
            "host_isolation": True, 
            "block_enabled": True,
            "policy": {
                "blacklist_keywords": ["phishing", "scam", "malware", "hack"],
                "exclusion_keywords": ["google", "wikipedia"],
                "blacklist_apps": ["mimikatz.exe", "anydesk.exe"]
            }
        }
    else:
        agent_configs[ip]["host_isolation"] = True
    logger.critical(f"[MML] Comando de Aislamiento activado para la IP: {ip}")
    return {"status": "isolated", "ip": ip}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "MML-AlertManager", "version": "2.0"}

@app.get("/ready")
async def ready():
    """Readiness probe: verifica que Kafka esté accesible."""
    try:
        prod = await get_producer()
        if prod is not None:
            return {"status": "ready", "kafka": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kafka no disponible: {e}")
    raise HTTPException(status_code=503, detail="Producer no inicializado")

@app.on_event("startup")
async def startup():
    logger.info("MML microservice starting up...")
    # Intentar conectar el producer Kafka al arrancar (con reintentos)
    global producer
    for attempt in range(30):
        try:
            p = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda m: json.dumps(m).encode()
            )
            await p.start()
            producer = p
            logger.success(f"[MML] Producer Kafka conectado en intento {attempt+1}")
            break
        except Exception as e:
            logger.warning(f"[MML] Kafka no disponible para Producer (intento {attempt+1}/30): {e}")
            await asyncio.sleep(5)
    # Iniciar consumidores en threads separados
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_normalizer)
    loop.run_in_executor(None, run_enricher)

@app.on_event("shutdown")
async def shutdown():
    logger.info("MML microservice shutting down...")
    if producer:
        await producer.stop()
