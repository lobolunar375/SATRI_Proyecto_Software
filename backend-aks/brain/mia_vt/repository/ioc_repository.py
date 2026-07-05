from pymongo import MongoClient, ASCENDING
from datetime import datetime, timezone
import json
import os
import logging

logger = logging.getLogger("ioc_repository")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://satri:satri2025@mongodb:27017")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client["satri_ioc_db"]
    collection = db["ioc_intelligence"]
    
    # Indices para busqueda rapida
    collection.create_index([("ioc_value", ASCENDING)], unique=True)
    collection.create_index([("vt_label", ASCENDING)])
except Exception as e:
    logger.error(f"Error conectando a MongoDB: {e}")

def upsert_ioc(ioc_value: str, ioc_type: str, vt_result: dict) -> None:
    doc = {
        "ioc_value": ioc_value,
        "ioc_type": ioc_type,
        "vt_score": vt_result.get("vt_score", 0),
        "vt_label": vt_result.get("vt_label", "UNKNOWN"),
        "first_seen": datetime.now(timezone.utc).isoformat(),
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "raw_vt": vt_result,
        # Formato STIX 2.1 basico
        "stix": {
            "type": "indicator",
            "spec_version": "2.1",
            "id": f"indicator--{ioc_value[:36]}",
            "pattern": f"[network-traffic:dst_ref.value = '{ioc_value}']",
            "labels": [vt_result.get("vt_label", "UNKNOWN").lower()],
        }
    }
    
    try:
        collection.update_one(
            {"ioc_value": ioc_value},
            {"$set": doc, "$setOnInsert": {"created_at": doc["first_seen"]}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error guardando IoC en DB: {e}")
