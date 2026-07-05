"""
Regla 10: Exfiltración de datos por volumen
Técnica MITRE: T1048 (Exfiltration Over Alternative Protocol)
Condición: >= 500MB enviados desde un host en 10 minutos
"""
from time_window_engine import r as redis_client

RULE_NAME = "DATA_EXFILTRATION_VOLUME"
MITRE_ID = "T1048"
THRESHOLD_BYTES = 500 * 1024 * 1024  # 500 MB
WINDOW_SECONDS = 600


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()
    src_ip = event.get("src_ip")

    if not src_ip:
        return None

    if event_type not in ["network_traffic", "data_transfer", "upload"]:
        return None

    bytes_sent = event.get("bytes_sent", event.get("bytes_out", 0))
    if not bytes_sent:
        return None

    key = f"mcor:r10:exfil:{src_ip}"
    total = redis_client.incrbyfloat(key, float(bytes_sent))
    if redis_client.ttl(key) < 0:
        redis_client.expire(key, WINDOW_SECONDS)

    if total >= THRESHOLD_BYTES:
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "HIGH",
            "reason": f"Posible exfiltración: {total / (1024*1024):.1f} MB enviados desde {src_ip} en {WINDOW_SECONDS}s",
            "src_ip": src_ip,
            "bytes_total": total
        }
    return None

