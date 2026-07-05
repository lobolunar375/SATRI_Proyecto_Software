"""
Regla 03: Ataque multi-etapa (fuerza bruta + escalada)
Técnica MITRE: T1110 + T1548 correlacionadas
Condición: Regla 01 disparada seguida de Regla 02, mismo origen, ventana 10 min
"""
from time_window_engine import get_flag

RULE_NAME = "MULTI_STAGE_BRUTE_ESCALATION"
MITRE_ID = "T1110+T1548"


def evaluate(event: dict) -> dict | None:
    src_ip = event.get("src_ip")
    if not src_ip:
        return None

    bf_flagged = get_flag(f"mcor:bf_flagged:{src_ip}")
    esc_flagged = get_flag(f"mcor:esc_flagged:{src_ip}")

    if bf_flagged and esc_flagged:
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "CRITICAL",
            "reason": f"ATAQUE MULTI-ETAPA: Fuerza bruta + escalada de privilegios desde {src_ip} en ventana de 10 min",
            "src_ip": src_ip
        }
    return None

