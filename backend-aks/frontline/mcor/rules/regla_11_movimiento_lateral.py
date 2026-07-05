"""
Regla 11: Movimiento lateral (login desde host comprometido)
Técnica MITRE: T1021 (Remote Services)
Condición: Login exitoso desde IP que previamente disparó Regla 01 o Regla 06
"""
from time_window_engine import get_flag

RULE_NAME = "LATERAL_MOVEMENT"
MITRE_ID = "T1021"


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()
    src_ip = event.get("src_ip")

    if not src_ip:
        return None

    if event_type not in ["login_success", "auth_success", "ssh_success", "rdp_login"]:
        return None

    # Verificar si la IP fue flaggeada por fuerza bruta (R01) o lista negra (R06)
    bf_flag = get_flag(f"mcor:bf_flagged:{src_ip}")
    bl_flag = get_flag(f"mcor:bl_flagged:{src_ip}")

    if bf_flag or bl_flag:
        origin = "fuerza bruta" if bf_flag else "IP en lista negra"
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "CRITICAL",
            "reason": f"MOVIMIENTO LATERAL: Login exitoso desde {src_ip} (previamente flaggeada por {origin})",
            "src_ip": src_ip,
            "origin_flag": origin
        }
    return None

