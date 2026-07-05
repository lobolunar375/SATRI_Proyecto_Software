"""
Motor de ventanas de tiempo para MCOR.
Gestiona contadores y cadenas de eventos con TTL en Redis
para la detección basada en ventanas temporales.
"""
import redis
import json
import os
from datetime import datetime, timezone
from loguru import logger

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)


def increment_counter(key: str, window_seconds: int) -> int:
    """Incrementa un contador con TTL. Retorna el valor actual."""
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)
    return count


def get_counter(key: str) -> int:
    """Obtiene el valor actual de un contador."""
    val = r.get(key)
    return int(val) if val else 0


def push_event(chain_key: str, event_data: dict, window_seconds: int):
    """Agrega un evento a una cadena temporal con TTL."""
    record = json.dumps({
        **event_data,
        "_ts": datetime.now(timezone.utc).isoformat()
    })
    r.rpush(chain_key, record)
    r.expire(chain_key, window_seconds)


def get_event_chain(chain_key: str) -> list:
    """Obtiene todos los eventos de una cadena temporal."""
    raw_events = r.lrange(chain_key, 0, -1)
    events = []
    for raw in raw_events:
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return events


def clear_chain(chain_key: str):
    """Limpia una cadena de eventos."""
    r.delete(chain_key)


def set_flag(key: str, value: str, ttl_seconds: int):
    """Establece un flag temporal (ej: IP marcada por regla X)."""
    r.setex(key, ttl_seconds, value)


def get_flag(key: str) -> str | None:
    """Obtiene un flag temporal."""
    return r.get(key)
