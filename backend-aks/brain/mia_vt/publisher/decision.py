"""
Microservicio MIA_VT: Ahora solo se encarga de la Inteligencia de Amenazas.
Publica sus hallazgos para que el SIEM Central los correlacione.
"""
from kafka import KafkaProducer
import json
import os
import logging

logger = logging.getLogger("publisher")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
producer = None
def get_producer():
    global producer
    if producer is None:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda m: json.dumps(m).encode()
        )
    return producer

def publish_decision(incident: dict, vt_label: str) -> None:
    """
    Publica el resultado de inteligencia al topico que lee MTA para triage.
    """
    intel_event = {
        **incident,
        "enrichment_status": "INTEL_READY",
        "vt_label": vt_label,
        "ioc_data": {"vt_label": vt_label},
        "src_ip": incident.get("artifacts", {}).get("src_ip", incident.get("src_ip")),
        "rule_name": incident.get("rule_name", incident.get("artifacts", {}).get("rule_name", "Unknown")),
    }
    
    # Publicar al topico que MTA consume para triage
    get_producer().send("satri.correlated.alerts", intel_event)
    # Tambien publicar a inteligencia para registros
    get_producer().send("satri.ioc.intelligence", intel_event)
    logger.info(f"[INTEL] Alerta enviada a MTA para triage: {incident.get('incident_id')} -> VT: {vt_label}")
