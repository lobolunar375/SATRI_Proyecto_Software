"""
Regla 02: Escalada de privilegios vía sudo fallido
Técnica MITRE: T1548 (Abuse Elevation Control Mechanism)
Condición: >= 3 intentos fallidos de sudo/su tras login exitoso en 5 minutos
"""
from time_window_engine import increment_counter, set_flag

RULE_NAME = "PRIVILEGE_ESCALATION_SUDO"
MITRE_ID = "T1548"
THRESHOLD = 3
WINDOW_SECONDS = 300


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()
    src_ip = event.get("src_ip")

    if not src_ip:
        return None

    if any(kw in event_type for kw in ["sudo_fail", "su_fail", "privilege_fail", "escalation_fail"]):
        key = f"mcor:r02:esc:{src_ip}"
        count = increment_counter(key, WINDOW_SECONDS)

        if count >= THRESHOLD:
            set_flag(f"mcor:esc_flagged:{src_ip}", "1", 600)
            return {
                "rule": RULE_NAME,
                "mitre": MITRE_ID,
                "severity": "HIGH",
                "reason": f"Escalada de privilegios: {count} intentos fallidos de sudo/su desde {src_ip} en {WINDOW_SECONDS}s",
                "src_ip": src_ip,
                "count": count
            }
    return None

