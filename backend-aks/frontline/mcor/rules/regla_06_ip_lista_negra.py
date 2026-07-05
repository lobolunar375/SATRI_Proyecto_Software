"""
Regla 06: Conexión a IP en lista negra
Técnica MITRE: T1071 (Application Layer Protocol)
Condición: Conexión saliente a IP/dominio marcado como malicioso en IoC
"""
from pymongo import MongoClient
import os

RULE_NAME = "BLACKLISTED_IP_CONNECTION"
MITRE_ID = "T1071"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://satri:satri2025@mongodb:27017")

_client = None
_ioc_col = None


def _get_ioc_collection():
    global _client, _ioc_col
    if _ioc_col is None:
        _client = MongoClient(MONGO_URI)
        _ioc_col = _client["satri_ioc_db"]["ioc_intelligence"]
    return _ioc_col


def evaluate(event: dict) -> dict | None:
    src_ip = event.get("src_ip")
    dst_ip = event.get("dst_ip")

    target_ip = dst_ip or src_ip
    if not target_ip:
        return None

    try:
        ioc_col = _get_ioc_collection()
        ioc = ioc_col.find_one({"ioc_value": target_ip})
        if ioc and (ioc.get("vt_score", 0) > 0 or ioc.get("vt_label") not in [None, "CLEAN"]):
            return {
                "rule": RULE_NAME,
                "mitre": MITRE_ID,
                "severity": "HIGH",
                "reason": f"Conexión a IP en lista negra: {target_ip} (VT: {ioc.get('vt_label')}, Score: {ioc.get('vt_score', 0)})",
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "vt_label": ioc.get("vt_label"),
                "vt_score": ioc.get("vt_score", 0)
            }
    except Exception:
        pass
    return None
