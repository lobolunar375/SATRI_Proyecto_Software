"""
Regla 01: Fuerza bruta SSH / autenticación
Técnica MITRE: T1110 (Brute Force)
Condición: >= 5 intentos fallidos desde la misma IP en 2 minutos
"""
from time_window_engine import increment_counter, set_flag

RULE_NAME = "BRUTE_FORCE_SSH"
MITRE_ID = "T1110"
THRESHOLD = 5
WINDOW_SECONDS = 120


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()
    src_ip = event.get("src_ip")

    if not src_ip:
        return None

    if any(kw in event_type for kw in ["auth_failure", "login_fail", "ssh_fail", "brute"]):
        key = f"mcor:r01:bf:{src_ip}"
        count = increment_counter(key, WINDOW_SECONDS)

        if count >= THRESHOLD:
            # Marcar IP como atacante para Regla 03 y 11
            set_flag(f"mcor:bf_flagged:{src_ip}", "1", 1800)
            return {
                "rule": RULE_NAME,
                "mitre": MITRE_ID,
                "severity": "CRITICAL",
                "reason": f"Fuerza bruta detectada: {count} intentos fallidos desde {src_ip} en {WINDOW_SECONDS}s",
                "src_ip": src_ip,
                "count": count
            }
    return None

