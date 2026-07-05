"""
Regla 14: Anomalía de comportamiento UEBA (señal de MIA_ML)
Técnica MITRE: T1078 (Valid Accounts) — uso anómalo de cuentas legítimas
Condición: MIA_ML reporta anomaly_score > 0.7 para un evento de login/sesión
"""

RULE_NAME = "UEBA_ANOMALY"
MITRE_ID = "T1078"
SCORE_THRESHOLD = 0.7


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()

    if event_type not in ["anomalous_behavior_detected", "ueba_anomaly"]:
        # También puede venir el score como parte de un login normal
        score = event.get("anomaly_score")
        if score is None:
            return None
        
        try:
            score = float(score)
        except ValueError:
            return None

        if score > SCORE_THRESHOLD:
            return {
                "rule": RULE_NAME,
                "mitre": MITRE_ID,
                "severity": "MEDIUM",
                "reason": f"Comportamiento anómalo detectado (Score UEBA: {score:.2f}) desde {event.get('src_ip', 'desconocida')}",
                "src_ip": event.get("src_ip"),
                "anomaly_score": score
            }
        return None

    # Si el evento ya viene catalogado como anomalía explícita
    score = float(event.get("anomaly_score", 1.0))
    return {
        "rule": RULE_NAME,
        "mitre": MITRE_ID,
        "severity": "MEDIUM",
        "reason": f"Comportamiento anómalo explícito detectado (Score UEBA: {score:.2f}) desde {event.get('src_ip', 'desconocida')}",
        "src_ip": event.get("src_ip"),
        "anomaly_score": score
    }
