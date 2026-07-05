import geoip2.database
import redis
import json
import os
import logging
from kafka import KafkaConsumer, KafkaProducer
from opensearch_client import index_log

logger = logging.getLogger("geoip")
logger.setLevel(logging.INFO)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

try:
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    reader_city = geoip2.database.Reader("/geoip/GeoLite2-City.mmdb")
    reader_asn = geoip2.database.Reader("/geoip/GeoLite2-ASN.mmdb")
except Exception as e:
    logger.warning(f"Base de datos GeoIP no encontrada: {e}")
    reader_city = None
    reader_asn = None

def enrich_ip(ip: str) -> dict:
    if reader_city and reader_asn:
        try:
            city_resp = reader_city.city(ip)
            asn_resp = reader_asn.asn(ip)
            return {
                "geo_country": city_resp.country.iso_code,
                "geo_city": city_resp.city.name,
                "geo_lat": float(city_resp.location.latitude or 0),
                "geo_lon": float(city_resp.location.longitude or 0),
                "asn_org": asn_resp.autonomous_system_organization,
            }
        except Exception as e:
            logger.warning(f"No se pudo enriquecer IP {ip}: {e}")
    return {
        "geo_country": "UNKNOWN",
        "geo_city": "Unknown",
        "geo_lat": 0.0,
        "geo_lon": 0.0,
        "asn_org": "Unknown"
    }

def run_enricher():
    import time
    logger.info("Iniciando Enricher GeoIP (Con Modo Simulación)...")
    consumer = None
    for attempt in range(30):
        try:
            consumer = KafkaConsumer(
                "satri.logs.normalized",
                bootstrap_servers=KAFKA_BROKER,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="enricher-group"
            )
            logger.info(f"Enricher conectado a Kafka en intento {attempt + 1}")
            break
        except Exception as e:
            logger.warning(f"Kafka no disponible para Enricher (intento {attempt + 1}/30): {e}")
            time.sleep(5)
    if consumer is None:
        logger.error("Enricher: No se pudo conectar a Kafka")
        return
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda m: json.dumps(m).encode("utf-8")
    )

    for message in consumer:
        event = message.value
        if event.get("src_ip"):
            enrichment = enrich_ip(event["src_ip"])
            event.update(enrichment)
        
        # PERSISTENCIA EN DB LOGS (OpenSearch)
        index_log(event)
        
        # Enviar al correlador
        producer.send("satri.logs.enriched", event)
        logger.info(f"Log enriquecido e indexado: {event.get('correlation_id')} -> {event.get('geo_country')}")

if __name__ == "__main__":
    run_enricher()

