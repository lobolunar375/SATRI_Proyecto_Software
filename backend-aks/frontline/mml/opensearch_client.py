"""
Cliente de OpenSearch para persistir logs normalizados y enriquecidos.
Actualizado para soportar Mapas de Calor (Geo-Point).
"""
from opensearchpy import OpenSearch
from datetime import datetime, timezone
import os
import logging

logger = logging.getLogger("opensearch_client")

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_ADMIN_PASSWORD = os.getenv("OPENSEARCH_ADMIN_PASSWORD", "Satri@2025!")

_client = None

def get_os_client() -> OpenSearch:
    global _client
    if _client is None:
        _client = OpenSearch(
            hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
            http_auth=("admin", OPENSEARCH_ADMIN_PASSWORD),
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=10,
        )
        # Crear el indice con mapeo geografico
        index = "satri-logs"
        if not _client.indices.exists(index=index):
            _client.indices.create(
                index=index,
                body={
                    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                    "mappings": {
                        "properties": {
                            "message": {"type": "text"},
                            "event_type": {"type": "keyword"},
                            "source": {"type": "keyword"},
                            "src_ip": {"type": "ip"},
                            "dst_ip": {"type": "ip"},
                            "timestamp": {"type": "date"},
                            "ingested_at": {"type": "date"},
                            "correlation_id": {"type": "keyword"},
                            "severity": {"type": "keyword"},
                            # Campo crucial para el Mapa de Calor
                            "location": {"type": "geo_point"},
                            "geo_country": {"type": "keyword"},
                            "geo_city": {"type": "keyword"},
                            "asn_org": {"type": "keyword"}
                        }
                    },
                },
            )
            logger.info(f"Indice '{index}' con soporte Geo-Point creado.")
    return _client


def index_log(log_data: dict) -> None:
    """Inserta un log normalizado y enriquecido en OpenSearch."""
    try:
        client = get_os_client()
        
        # Preparar campo location para Grafana Heatmap
        if "geo_lat" in log_data and "geo_lon" in log_data:
            log_data["location"] = {
                "lat": log_data["geo_lat"],
                "lon": log_data["geo_lon"]
            }
            
        doc = {
            **log_data,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        client.index(index="satri-logs", body=doc)
        logger.info(f"Log enriquecido indexado en OpenSearch: {log_data.get('correlation_id', 'N/A')}")
    except Exception as e:
        logger.error(f"Error indexando log en OpenSearch: {e}")
