from fastapi import FastAPI
from kafka import KafkaConsumer, KafkaProducer
from loguru import logger
from pymongo import MongoClient
import json
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

app = FastAPI(title="SATRI - MTA (Triage Automatizado) v2.0")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
MONGO_URI    = os.getenv("MONGO_URI", "mongodb://satri:satri2025@mongodb:27017")
INTEGRATIONS_URL = os.getenv("INTEGRATIONS_URL", "http://integrations:8004")

# ── MongoDB Client (sync, para uso en hilo ThreadPool) ──
mongo_client = None
def get_db():
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(MONGO_URI)
    return mongo_client["satri_ioc_db"]

producer = None
def get_producer():
    global producer
    if producer is None:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda m: json.dumps(m).encode()
        )
    return producer

from severity_matrix import get_triage_action

def run_triage_consumer():
    import time
    logger.info("Iniciando Kafka Consumer MTA v2.0 (Triage + MongoDB)...")
    consumer = None
    for attempt in range(30):
        try:
            consumer = KafkaConsumer(
                "satri.correlated.alerts",
                bootstrap_servers=KAFKA_BROKER,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="mta-group"
            )
            logger.success(f"MTA conectado a Kafka en intento {attempt + 1}")
            break
        except Exception as e:
            logger.warning(f"Kafka no disponible (intento {attempt + 1}/30): {e}")
            time.sleep(5)

    if consumer is None:
        logger.error("No se pudo conectar a Kafka despues de 30 intentos")
        return

    for message in consumer:
        alert = message.value
        alert_id  = alert.get("alert_id") or alert.get("incident_id", "UNKNOWN")
        severity  = alert.get("severity", "MEDIUM")
        vt_label  = alert.get("ioc_data", {}).get("vt_label") or alert.get("vt_label", "SUSPICIOUS")
        ueba_score = float(alert.get("anomaly_score", 0.0))
        src_ip    = alert.get("src_ip") or alert.get("log_data", {}).get("src_ip") or alert.get("artifacts", {}).get("src_ip", "N/A")
        rule_name = alert.get("correlation_rule") or alert.get("rule_name") or alert.get("artifacts", {}).get("rule_name", "Desconocido")

        # Aplicar matriz de decision cruzando MCOR, MIA_VT y MIA_ML
        action, priority, ir, final_severity = get_triage_action(severity, vt_label, ueba_score)

        triage_result = {
            **alert,
            "alert_id":       alert_id,
            "src_ip":         src_ip,
            "rule_name":      rule_name,
            "triage_decision":action,
            "priority":       priority,
            "initiate_ir":    ir,
            "final_severity": final_severity,
            "status":         "COMPLETED",
            "triage_ts":      datetime.now(timezone.utc).isoformat()
        }

        logger.success(
            f"[TRIAGE] {rule_name} | IP: {src_ip} | Severidad Final: {final_severity} (Base: {severity}, UEBA: {ueba_score:.2f}) | Decision: {action} ({priority})"
        )

        # ── Persistir en MongoDB para el Dashboard ──
        try:
            db = get_db()
            db["triage_incidents"].insert_one({**triage_result})
            logger.debug(f"[MTA] Alerta persistida en MongoDB: {alert_id}")
        except Exception as e:
            logger.error(f"[MTA] Error guardando en MongoDB: {e}")

        # Publicar resultado final en Kafka
        get_producer().send("satri.incidents.triage", triage_result)
        
        # FASE 5: Generar Webhooks para CRITICAL
        if severity == "CRITICAL" or action == "BLOCK":
            logger.info(f"[MTA] Generando Webhook para incidente crítico: {alert_id}")
            try:
                import requests
                # Llamar a Integrations (SOAR) para que dispare notificaciones Discord/Slack
                res = requests.post(f"{INTEGRATIONS_URL}/api/v1/notify", json=triage_result, timeout=5)
                res.raise_for_status()
            except Exception as e:
                logger.error(f"[MTA] Fallo al generar Webhook en Integrations: {e}")

@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(ThreadPoolExecutor(max_workers=1), run_triage_consumer)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "mta-v2"}


