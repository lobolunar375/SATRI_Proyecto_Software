import redis
import json
import os
from extractor.ioc_extractor import IoC
import logging

logger = logging.getLogger("ioc_cache")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# TTL en segundos por tipo de IoC (segun volatilidad)
TTL_BY_TYPE = {
    "hash_sha256": 86400,  # 24h - hashes son estables
    "hash_md5":    86400,
    "hash_sha1":   86400,
    "domain":      21600,  # 6h - dominios cambian mas
    "ip":          21600,  # 6h - IPs pueden rotar
    "url":         43200,  # 12h
    "email":       86400,
}

def get_cached(ioc: IoC) -> dict | None:
    key = f"vt:{ioc.type}:{ioc.value}"
    raw = r.get(key)
    if raw:
        r.incr("cache:hits")
        logger.info(f"[TELEMETRIA] Cache HIT para {ioc.value}")
    else:
        logger.info(f"[TELEMETRIA] Cache MISS para {ioc.value}")
    r.incr("cache:total")
    return json.loads(raw) if raw else None

def set_cached(ioc: IoC, result: dict, ttl_override: int = None) -> None:
    key = f"vt:{ioc.type}:{ioc.value}"
    ttl = ttl_override if ttl_override is not None else TTL_BY_TYPE.get(ioc.type, 3600)
    r.setex(key, ttl, json.dumps(result))
    logger.info(f"[TELEMETRIA] IoC cacheado: {ioc.value} (TTL: {ttl}s)")

def cache_hit_rate() -> float:
    """Retorna tasa de aciertos de cache"""
    hits = int(r.get("cache:hits") or 0)
    total = int(r.get("cache:total") or 1)
    return hits / total

