from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from loguru import logger
import json
import os
import asyncio
from datetime import datetime, timezone

# Importar el motor que corre todas las 14 reglas
from rules import run_all_rules

app = FastAPI(title="SATRI - MCOR v3.0 (Correlación con 14 Reglas MITRE ATT&CK)")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

# Contadores para métricas
correlation_stats = {
    "total_events_processed": 0,
    "total_alerts_generated": 0,
    "alerts_by_rule": {}
}

producer = None
async def get_producer():
    global producer
    if producer is None:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda m: json.dumps(m).encode()
        )
        await producer.start()
    return producer


async def run_correlator_consumer():
    logger.info("Iniciando MCOR v3.0 con 14 Reglas MITRE ATT&CK...")
    consumer = AIOKafkaConsumer(
        "satri.logs.enriched",
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="mcor-group"
    )
    
    for attempt in range(30):
        try:
            await consumer.start()
            logger.info("MCOR conectado a Kafka")
            break
        except Exception as e:
            logger.warning(f"Kafka no disponible (intento {attempt + 1}/30): {e}")
            await asyncio.sleep(5)
    
    async for message in consumer:
        event = message.value
        correlation_stats["total_events_processed"] += 1
        
        # Ejecutar el motor de reglas sobre el evento
        alerts_to_send = run_all_rules(event)

        for alert_info in alerts_to_send:
            rule_name = alert_info.get("rule", "UNKNOWN_RULE")
            correlation_stats["total_alerts_generated"] += 1
            correlation_stats["alerts_by_rule"][rule_name] = correlation_stats["alerts_by_rule"].get(rule_name, 0) + 1
            
            logger.warning(f"¡ALERTA SIEM [{rule_name}]! -> {alert_info.get('reason')}")
            
            correlated_alert = {
                "alert_id": f"ALRT-{os.urandom(4).hex().upper()}",
                "log_data": event,
                "correlation_reason": alert_info.get("reason"),
                "correlation_rule": rule_name,
                "mitre_technique": alert_info.get("mitre"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": alert_info.get("severity")
            }
            
            prod = await get_producer()
            await prod.send_and_wait("satri.correlated.alerts", correlated_alert)
            logger.info(f"Alerta [{alert_info.get('severity')}] enviada a Triage: {correlated_alert['alert_id']}")


@app.on_event("startup")
async def startup():
    asyncio.create_task(run_correlator_consumer())


@app.on_event("shutdown")
async def shutdown():
    if producer:
        await producer.stop()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcor-v3"}

@app.get("/ready")
async def ready():
    try:
        prod = await get_producer()
        if prod is not None:
            return {"status": "ready"}
    except Exception:
        pass
    from fastapi import HTTPException
    raise HTTPException(status_code=503, detail="Kafka not connected")

@app.get("/api/v1/mcor/stats")
async def get_stats():
    return correlation_stats
