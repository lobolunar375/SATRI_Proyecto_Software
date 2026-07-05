from kafka import KafkaConsumer, KafkaProducer
from pydantic import BaseModel
from typing import Optional
import json, re, logging
from datetime import datetime, timezone
import os

logger = logging.getLogger("normalizer")
logger.setLevel(logging.INFO)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

# Esquema ECS minimo
class ECSEvent(BaseModel):
    correlation_id: str
    timestamp: str
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    severity: str = "LOW"
    event_type: str
    host: Optional[str] = None
    message: str
    source_microservice: str = "MML-v1.0"

# Patrones Grok simplificados con regex
PATTERNS = {
    "src_ip": r"\b(?:src|source|from)[\s=:]+(\d{1,3}(?:\.\d{1,3}){3})\b",
    "dst_ip": r"\b(?:dst|dest|to)[\s=:]+(\d{1,3}(?:\.\d{1,3}){3})\b",
    "severity": r"\b(CRITICAL|HIGH|MEDIUM|LOW|INFO|WARN|ERROR)\b",
}

def normalize(raw: dict) -> ECSEvent:
    message = raw.get("message", "")
    extracted = {}
    for field, pattern in PATTERNS.items():
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            extracted[field] = match.group(1).upper() if field == "severity" \
                               else match.group(1)
    # Si no se extrajo del mensaje, intentar buscarlo en la raiz del JSON (ej. si viene del Agent)
    if "src_ip" not in extracted and "src_ip" in raw:
        extracted["src_ip"] = raw["src_ip"]
        
    return ECSEvent(
        correlation_id=raw.get("correlation_id", ""),
        timestamp=raw.get("timestamp", datetime.now(timezone.utc).isoformat()),
        message=message,
        event_type=raw.get("event_type", "generic"),
        **extracted
    )

def run_normalizer():
    import time
    logger.info("Iniciando Normalizer ECS...")
    consumer = None
    for attempt in range(30):
        try:
            consumer = KafkaConsumer(
                "satri.logs.raw",
                bootstrap_servers=KAFKA_BROKER,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="normalizer-group"
            )
            logger.info(f"Normalizer conectado a Kafka en intento {attempt + 1}")
            break
        except Exception as e:
            logger.warning(f"Kafka no disponible para Normalizer (intento {attempt + 1}/30): {e}")
            time.sleep(5)
    if consumer is None:
        logger.error("Normalizer: No se pudo conectar a Kafka")
        return
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda m: json.dumps(m).encode("utf-8")
    )

    for message in consumer:
        try:
            ecs_event = normalize(message.value)
            producer.send("satri.logs.normalized", ecs_event.model_dump())
            logger.info(f"Log normalizado: {ecs_event.correlation_id}")
        except Exception as e:
            logger.error(f"Error normalizando: {e}")
            producer.send("satri.logs.quarantine", message.value)

if __name__ == "__main__":
    run_normalizer()
